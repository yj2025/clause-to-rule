"""로컬 생성 — 조문 하나를 모델에 물리고, 검증에 걸리면 오류 메시지를 붙여 다시 묻는다.

자기수정 루프가 이 프로젝트에서 가장 크게 기여한다. 오류 메시지를 고쳤더니
재시도 기여가 +10.8p 에서 +36.0p 로 커졌고 생성 호출은 257 에서 211 회로 줄었다.
메시지가 좋아지니 한 번에 고쳐지고, 최대 재시도까지 가는 경우가 줄었다 (§6.3).

진행 줄에 **조문별 시간과 남의 GPU 점유**를 같이 찍는다. 누적만 찍으면 마지막
조문 하나가 5,016초를 먹은 것을 빼서 계산해야 하고, 남의 점유가 안 찍히면
GPU 경합 가설을 확인할 수 없다 (부록 A.6).

    python run_local_v2.py --out results/results_kbyy_v20.json --runs 9
"""

import argparse
import json
import sys
import time
from pathlib import Path

import validate
from prompt import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt

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


def run_clause(tok, model, clause, runs=1, temperature=0.1, allow_retry=True,
               max_new_tokens=MAX_NEW_TOKENS, batch_size=1, max_attempts=3):
    """조문 하나를 runs 회 생성한다. 각 회차가 레코드 하나다."""
    out = []
    for run in range(runs):
        user = build_user_prompt(clause["text"], clause["id"])
        first = final = None
        output, raw_first, truncated, attempts, errors = None, None, False, 0, []

        for attempt in range(max_attempts if allow_retry else 1):
            attempts += 1
            raw, trunc = _generate(tok, model, user, temperature, max_new_tokens)
            truncated = truncated or trunc
            if raw_first is None:
                raw_first = raw
            parsed = parse_json(raw)
            marks = validate.score_record(parsed, clause["text"])
            if first is None:
                first = marks
            output, final = parsed, marks
            errors = marks["errors"]
            if marks["schema_ok"] and marks["catalog_ok"] and \
               marks["quote_ok"] and marks["exec_ok"]:
                break
            if not allow_retry or parsed is None:
                break
            user = build_retry_prompt(clause["text"], parsed, errors, clause["id"])

        out.append({"clause_id": clause["id"], "run": run, "n_attempts": attempts,
                    "first": _marks(first), "final": _marks(final),
                    "errors": errors, "output": output,
                    "raw_first": raw_first, "truncated": truncated})
    return out


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
