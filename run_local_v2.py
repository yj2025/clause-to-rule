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
from prompt import SYSTEM_PROMPT, build_json_retry_prompt, build_retry_prompt, build_user_prompt


def prompt_fingerprint():
    """이 라운드가 무엇으로 만들어졌는지 한 줄로 남긴다.

    v22 를 되돌린 뒤 "지금 지문이 v19 와 같나" 를 확인하려고 git 으로
    커밋을 찾아 파일을 풀어 대조해야 했다. 결과 파일에 적어 두면 안 해도 된다.

    지문·예시·카탈로그·스키마를 각각 따로 센다.
    하나만 바뀌어도 어느 쪽인지 보인다.

    **스키마를 빠뜨렸다가 v23 에서 물렸다.** 스키마에 제약을 더했는데
    해시가 그대로라 기준선과 구별이 안 됐다. 스키마는 ② 관문을 정의하므로
    출력을 바꾼다 — 지문과 똑같이 기록해야 한다.
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
        "schema": h(json.dumps(schema.SCHEMA, ensure_ascii=False,
                               sort_keys=True, default=str)),
        # 2026-09-15 — 어휘 확장 여섯이 catalog 해시에 안 잡혔다 (대상 목록 · 이벤트 속성 ·
        # 열거값). catalog 를 고치면 옛 라운드와 견줄 값이 바뀌므로 키를 따로 둔다.
        "vocab": h(json.dumps(
            [catalog.SERVICES, catalog.RESTRICTIONS, catalog.EVENT_ATTRIBUTES,
             catalog.ENUM_VALUES, list(catalog.UNITS)],
            ensure_ascii=False, sort_keys=True, default=str)),
        # 2026-09-16 — **스키마와 같은 이유로 검증기도 센다.** 위 주석이 "스키마는
        # ② 관문을 정의하므로 출력을 바꾼다" 고 적어 두고 ③④⑤ 를 정의하는 검증기는
        # 빠뜨렸다. 검증기가 바뀌면 재시도에 되먹이는 오류 문구가 바뀌고, 그래서
        # **생성물 자체가 바뀐다** — 재시도가 관문의 36% 를 만든다 (v24 기준).
        # v25 에서 물릴 뻔했다. 지문·스키마·어휘를 하나도 안 건드리고 ③ 만 좁히는
        # 라운드라, 이 키가 없으면 v24 와 지문 해시가 완전히 같아 구별이 안 된다.
        "validator": h("".join(
            (Path(__file__).parent / f).read_text("utf-8")
            for f in ("validate.py", "invent.py", "vacuous.py", "grounding.py"))),
        # 2026-09-24 — **같은 이유로 `prompt.py` 자체도 센다.** 위 주석이
        # 「검증기가 바뀌면 재시도에 되먹이는 문구가 바뀐다」고 적어 두고,
        # **재시도 지문을 만드는 코드 자체**는 빠뜨렸다. v46 이 그 코드에
        # 조건부 블록을 붙였는데 **지문 해시가 v41 과 완전히 같았다** —
        # 처방 전 라운드와 처방 후 라운드가 구별이 안 됐다. 판정선을 재는
        # 도구가 「지문 1종이니 같은 구성」으로 읽고 섞을 뻔했다.
        #
        # `SYSTEM_PROMPT` 는 위에서 따로 세지만 그것만으로는 모자란다 —
        # `build_retry_prompt` · 조건부 블록 · `_USAGE` 가 전부 이 파일에 있다.
        "retry": h((Path(__file__).parent / "prompt.py").read_text("utf-8")),
        # 2026-09-28 — **또 같은 구멍이 있었다.** `retry` 키가 `prompt.py` 만
        # 세는데, **조건부 블록을 «어느 조문에 붙일지» 정하는 방아쇠는
        # `catalog.py` 에 있다** (`wants_non_binding` · `wants_change_kinds` 등).
        # 그것만 바꾸는 라운드는 지문 해시가 하나도 안 바뀐다.
        #
        # 실제로 물었다 — **v36↔v37 과 v38↔v39 가 지문으로 구별되지 않는다.**
        # v37 은 「같은 네 줄을 그대로 두고 붙는 조문만 17 → 12 로 줄였다」는
        # 라운드다. 판정선 계산에는 피해가 없었지만(섞어 쓴 표본이 전부 실제로
        # 같은 코드였다) 「지문이 같으면 같은 구성」이라는 가정이 세 번 깨졌다.
        "triggers": h((Path(__file__).parent / "catalog.py").read_text("utf-8")),
        # 2026-09-30 — **세 번째 같은 구멍.** 재시도를 할지 말지 · 어느 시도를 남길지
        # (`run_clause` · `_score_of`) 는 이 파일에 있는데 지문이 이 파일을 안 셌다.
        # 09-29 에 「⑮ 가 잡히면 관문을 다 넘어도 재시도」를 준비하다 봤다 — 그 처방은
        # 이 루프만 바꾸므로 **지문이 v66 과 같았을 것**이다. 아직 이 루프를 바꾼 라운드는
        # 없어 물리지는 않았다.
        #
        # **이 키가 들어간 뒤의 라운드는 코드가 같아도 앞 라운드와 지문이 다르다** (키가
        # 하나 늘었다). 앞 라운드와 섞을 때는 이 키를 빼고 견준다.
        "runner": h(Path(__file__).read_text("utf-8")),
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


def _free_cache():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


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


def _json_body(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if len(s.split("```")) > 1 else s
        s = s[s.index("\n") + 1:] if "\n" in s else s
    i, j = s.find("{"), s.rfind("}")
    return None if i < 0 or j < i else s[i:j + 1]


def parse_json(raw):
    """코드펜스와 앞뒤 군더더기를 걷어내고 JSON 을 읽는다. 실패하면 None."""
    body = _json_body(raw)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def parse_error(raw):
    """읽히지 않는 까닭 — (본문, 파서 메시지, 줄 번호). 본문이 없으면 줄 번호는 None."""
    body = _json_body(raw)
    if body is None:
        return raw, "JSON 객체가 없다 — `{` 로 시작해 `}` 로 끝나는 본문이 안 보인다", None
    try:
        json.loads(body)
    except json.JSONDecodeError as e:
        return body, e.msg, e.lineno
    return body, None, None


GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")


def _score_of(marks, semantic=None):
    """시도 하나를 견주는 열쇠. 앞에 올수록 세다.

    (통과한 관문 수, 뜻 오류가 적은 것, 오류가 적은 것)

    **뜻 오류**(`validate.semantic_errors`, 2026-09-30 · v70)는 관문 **다음** 자리다 —
    관문을 잃으면서 뜻 오류를 없앤 시도는 고르지 않는다.

    **관문 수만으로는 부족하다.** v12 에서 확인했다 — 재시도가 지어낸 코드를
    고쳤는데 관문 수가 그대로라 "동점이면 앞" 규칙에 걸려 채택되지 않았다.
    네 건 전부 그랬다. 앞 처방이 뒤 처방의 천장이 된 것이다.

    관문 수가 같으면 **오류가 적은 쪽**을 고른다. 같은 관문을 통과했어도
    위반이 셋인 것과 하나인 것은 다르다.
    """
    if not marks:
        return (0, 0, 0)
    return (sum(1 for k in GATES if marks[k]), -len(semantic or []),
            -len(marks.get("errors") or []))


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
        retry_oom = False
        best = None          # (관문 수, 시도번호, marks, output, errors)

        for attempt in range(max_attempts if allow_retry else 1):
            attempts += 1
            try:
                raw, trunc = _generate(tok, model, user, temperature, max_new_tokens)
            except Exception as e:
                # v100 (2026-10-02). 재시도 입력이 길면 V100 32GB 에서 생성 중 OOM 이 난다 — v98 · v99 에서
                # 프로세스가 통째로 죽고 같은 조문에서 여섯 번 되풀이했다. **재시도 중**의 OOM 은 그 조문의
                # 재시도만 멈추고 그때까지 가장 나은 시도를 낸다. 첫 시도의 OOM 은 전처럼 올려 보낸다.
                if attempts == 1 or type(e).__name__ != "OutOfMemoryError":
                    raise
                retry_oom = True
                attempts -= 1
                _free_cache()
                break
            truncated = truncated or trunc
            if raw_first is None:
                raw_first = raw
            raw_last = raw
            parsed = parse_json(raw)
            marks = validate.score_record(parsed, clause["text"])
            # 관문이 못 보는 뜻 오류 — 관문 정의는 그대로 두고 재시도만 부른다 (v70)
            sem = validate.semantic_errors(parsed, clause["text"])
            if first is None:
                first = marks

            got = _score_of(marks, sem)
            if best is None or got > best[0]:
                best = (got, attempts, marks, parsed, marks["errors"], sem)

            if got[0] == len(GATES) and not sem:
                break
            if not allow_retry:
                break
            if parsed is None and trunc:
                # v100. 토큰 한도에서 잘린 출력은 다시 내도 또 잘린다(v98 `KBSSG-S2-R08` 세 시도 다) —
                # 그리고 그 재시도가 입력+생성 6.7천 토큰으로 OOM 을 냈다(v99). 잘린 것은 재시도하지 않는다.
                break
            if parsed is None:
                # 2026-10-02 · v98. 읽히지 않는 출력은 **재시도 없이** 끝났다 — kb10 105조문 중
                # 5~6조문이 세 라운드 다 같은 자리에서 괄호 짝(`]` ↔ `}`)을 틀리고 시도 1회로 끝났다.
                # 깨진 본문과 파서가 멈춘 줄을 보여 주고 다시 내게 한다.
                body, msg, line = parse_error(raw)
                user = build_json_retry_prompt(clause["text"], body, msg, line, trunc,
                                               clause["id"])
                continue
            # 2026-10-04 · v113. **뜻 오류를 관문 오류보다 앞에 싣는다.** 재시도 프롬프트는 오류를 앞에서 8개만 싣는데
            # (`prompt.build_retry_prompt`), 뜻 오류가 뒤에 붙어 관문 오류가 8개를 넘는 조문에선 **한 번도 안 보였다** —
            # v109 의 문구가 잘린 조문 0/6 · 보인 조문 4/4 (kb10). 뜻 오류의 「통째로 바꾼 꼴」은 그 rule 의 관문 오류도 같이 없앤다.
            user = build_retry_prompt(clause["text"], parsed, sem + marks["errors"],
                                      clause["id"])

        _, n_best, marks, output, errors, sem = best
        out.append({"clause_id": clause["id"], "run": run, "n_attempts": attempts,
                    "prompt": _FINGERPRINT,
                    "n_best": n_best,
                    "first": _marks(first), "final": _marks(marks),
                    "errors": errors, "semantic_errors": sem, "output": output,
                    "raw_first": raw_first, "raw_last": raw_last,
                    "truncated": truncated, "retry_oom": retry_oom})
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
