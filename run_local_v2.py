"""로컬 생성 — 조문 하나를 모델에 물리고, 검증에 걸리면 오류 메시지를 붙여 다시 묻는다.

자기수정 루프가 이 프로젝트에서 가장 크게 기여한다. 오류 메시지를 고쳤더니
재시도 기여가 +10.8p 에서 +36.0p 로 커졌고 생성 호출은 257 에서 211 회로 줄었다.
메시지가 좋아지니 한 번에 고쳐지고, 최대 재시도까지 가는 경우가 줄었다 (§6.3).

진행 줄에 **조문별 시간과 남의 GPU 점유**를 같이 찍는다. 누적만 찍으면 마지막
조문 하나가 5,016초를 먹은 것을 빼서 계산해야 하고, 남의 점유가 안 찍히면
GPU 경합 가설을 확인할 수 없다 (부록 A.6).

    python run_local_v2.py --out results/results_v1.json --runs 3
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import catalog
import schema
import validate
from prompt import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt


def prompt_fingerprint():
    """이 라운드가 무엇으로 만들어졌는지 한 줄로 남긴다.

    v22 를 되돌린 뒤 "지금 지문이 v19 와 같나" 를 확인하려고 git 으로
    커밋을 찾아 파일을 풀어 대조해야 했다. 결과 파일에 적어 두면 안 해도 된다.

    지문·예시·카탈로그를 각각 따로 센다. 하나만 바뀌어도 어느 쪽인지 보인다.
    """
    def h(x):
        return hashlib.sha256(x.encode("utf-8")).hexdigest()[:12]
    return {
        "system": h(SYSTEM_PROMPT),
        "fewshots": h(json.dumps(schema.FEWSHOTS, ensure_ascii=False,
                                 sort_keys=True, default=str)),
        "n_fewshots": len(schema.FEWSHOTS),
        "catalog": h(json.dumps(
            [sorted(catalog.VARIABLES), sorted(catalog.EVENTS),
             sorted(catalog.EFFECTS), sorted(catalog.FEES)],
            ensure_ascii=False)),
    }

MODEL = "Qwen/Qwen3-8B"
MAX_NEW_TOKENS = 3072


# ── GPU ─────────────────────────────────────────────────────────────────
def gpu_mem():
    """(예약, 여유, 남이 쓰는 양) GB. GPU 가 없으면 전부 0."""
    try:
        import torch
        if not torch.cuda.is_available():
            return 0.0, 0.0, 0.0
        free, total = torch.cuda.mem_get_info()
        reserved = torch.cuda.memory_reserved()
        other = total - free - reserved          # 이 프로세스 밖에서 쓰는 양
        return reserved / 1e9, free / 1e9, max(other, 0) / 1e9
    except Exception:
        return 0.0, 0.0, 0.0


def pick_dtype():
    """카드에 맞는 dtype. V100(7.0)은 bf16 세대가 아니라 fp16 이 안전하다."""
    import torch
    if not torch.cuda.is_available():
        return torch.float32
    major, _ = torch.cuda.get_device_capability(0)
    return torch.bfloat16 if major >= 8 else torch.float16


def _release():
    """조문 사이에 캐시를 비운다.

    긴 조문의 KV 캐시를 할당자가 계속 쥐고 있으면 예약이 카드를 다 채운다.
    v2 에서 32.5GB / 여유 1.1GB 까지 갔다. 비우는 비용은 조문당 1초 미만이다.
    """
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def load_model(name=MODEL):
    """(tokenizer, model). transformers 4.51 이상이어야 Qwen3 tokenizer 를 읽는다."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(
        name, dtype=pick_dtype(), device_map="auto")
    model.eval()
    return tok, model


def _generate(tok, model, user, temperature, max_new_tokens):
    import torch
    conv = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]
    text = tok.apply_chat_template(conv, tokenize=False, add_generation_prompt=True,
                                   enable_thinking=False)   # 매핑 태스크다
    ids = tok(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=max_new_tokens,
                             do_sample=temperature > 0, temperature=temperature or None,
                             pad_token_id=tok.eos_token_id)
    gen = out[0][ids["input_ids"].shape[1]:]
    truncated = len(gen) >= max_new_tokens
    return tok.decode(gen, skip_special_tokens=True), truncated


def parse_json(raw):
    """코드펜스와 앞뒤 군더더기를 걷어내고 JSON 을 읽는다. 실패하면 None."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if len(s.split("```")) > 1 else s
        s = s[s.index("\n") + 1:] if "\n" in s else s
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        return json.loads(s[i:j + 1])
    except json.JSONDecodeError:
        return None


GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")


def _score_of(marks):
    """시도 하나를 견주는 열쇠. 앞에 올수록 세다.

    (통과한 관문 수, 오류가 적은 것)

    **관문 수만으로는 부족하다.** v12 에서 확인했다 — 재시도가 지어낸 코드를
    고쳤는데 관문 수가 그대로라 "동점이면 앞" 규칙에 걸려 채택되지 않았다.
    네 건 전부 그랬다. 앞 처방이 뒤 처방의 천장이 된 것이다.

    관문 수가 같으면 **오류가 적은 쪽**을 고른다. 같은 관문을 통과했어도
    위반이 셋인 것과 하나인 것은 다르다.
    """
    if not marks:
        return (0, 0)
    return (sum(1 for k in GATES if marks[k]), -len(marks.get("errors") or []))


def run_clause(tok, model, clause, runs=1, temperature=0.1, allow_retry=True,
               max_new_tokens=MAX_NEW_TOKENS, batch_size=1, max_attempts=3):
    """조문 하나를 runs 회 생성한다. 각 회차가 레코드 하나다.

    **시도 중 가장 나은 것을 낸다. 마지막 것이 아니다.**

    옛 구현은 마지막 시도를 그대로 냈다. 그래서 재시도가 결과를 **망가뜨릴** 수
    있었다 — v2 에서 재시도 94회 중 8회가 그랬고, 1차에 통과했던 관문을 잃었다.
    고치라고 물었는데 더 나빠진 답을 받아들일 이유가 없다.

    **보장되는 것은 관문 "총수" 가 줄지 않는 것이다.** 개별 관문은 잃을 수 있다 —
    하나를 잃고 둘을 얻으면 총수는 늘어 채택된다. v16(3회차)에서 5건이 그랬다.
    v13 판정에서 "회귀가 구조적으로 0" 이라고 적은 것은 **틀렸다.**
    1회차 라운드에서 우연히 0이 나온 것을 잘못 일반화했다.

    동점이면 **먼저 나온 시도**를 쓴다. 재시도가 관문 수를 안 바꾸면서 rule 을
    포기 선언으로 갈아치우는 경로가 있는데(v3 에서 ⑧ 이 26.3% → 43.8%),
    동점 시 앞을 택하면 그 갈아타기가 채택되지 않는다.

    `raw_first` 와 `raw_last` 를 둘 다 남긴다. `n_best` 가 몇 번째 시도를 냈는지다.
    채점 기준(`validate`)은 건드리지 않는다 — 고르는 방식만 바뀐다.
    """
    out = []
    for run in range(runs):
        user = build_user_prompt(clause["text"], clause["id"])
        first = None
        raw_first = raw_last = None
        truncated, attempts = False, 0
        best = None          # (관문 수, 시도번호, marks, output, errors)

        for attempt in range(max_attempts if allow_retry else 1):
            attempts += 1
            raw, trunc = _generate(tok, model, user, temperature, max_new_tokens)
            truncated = truncated or trunc
            if raw_first is None:
                raw_first = raw
            raw_last = raw
            parsed = parse_json(raw)
            marks = validate.score_record(parsed, clause["text"])
            if first is None:
                first = marks

            got = _score_of(marks)
            if best is None or got > best[0]:
                best = (got, attempts, marks, parsed, marks["errors"])

            if got[0] == len(GATES):
                break
            if not allow_retry or parsed is None:
                break
            user = build_retry_prompt(clause["text"], parsed, marks["errors"],
                                      clause["id"])

        _, n_best, marks, output, errors = best
        out.append({"clause_id": clause["id"], "run": run, "n_attempts": attempts,
                    "prompt": _FINGERPRINT,
                    "n_best": n_best,
                    "first": _marks(first), "final": _marks(marks),
                    "errors": errors, "output": output,
                    "raw_first": raw_first, "raw_last": raw_last,
                    "truncated": truncated})
    return out


_FINGERPRINT = prompt_fingerprint()


def _marks(m):
    keys = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok", "empty", "n_rules")
    return {k: m[k] for k in keys} if m else {k: False for k in keys}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--clauses", default="data/clauses.json")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--max-new-tokens", type=int, default=MAX_NEW_TOKENS)
    ap.add_argument("--no-retry", action="store_true")
    ap.add_argument("--only", nargs="*", help="조문 id 를 지정하면 그것만 돌린다")
    a = ap.parse_args(argv)

    clauses = json.loads(Path(a.clauses).read_text("utf-8"))
    if a.only:
        clauses = [c for c in clauses if c["id"] in set(a.only)]

    t0 = time.time()
    tok, model = load_model()
    print(f"모델 로딩 {time.time() - t0:.0f}초", flush=True)

    recs, t0 = [], time.time()
    for i, c in enumerate(clauses, 1):
        tc = time.time()
        got = run_clause(tok, model, c, runs=a.runs, temperature=a.temperature,
                         allow_retry=not a.no_retry, max_new_tokens=a.max_new_tokens)
        recs += got
        _release()
        res, free, other = gpu_mem()
        print(f"진행 {i}/{len(clauses)} [{c['id']}] "
              f"시도{sum(x['n_attempts'] for x in got)} "
              f"조문{time.time() - tc:.0f}s "
              f"예약{res:.1f}GB 여유{free:.1f}GB 타{other:.1f}GB  "
              f"({time.time() - t0:.0f}s, 누적 {len(recs)}건)", flush=True)
        Path(a.out).write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")

    print(f"\n완료 {len(recs)}건 · {time.time() - t0:.0f}초 → {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
