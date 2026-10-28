"""증류 라벨 — Gemma 4 31B(NF4)로 조문 풀의 조건식을 만든다 (2026-10-20).

생성 루프는 `run_local_v2.run_clause` 를 그대로 쓴다 — 같은 지문 · 같은 검증 · 같은 재시도 ·
같은 후처리(v123 grounding · v127 reasons). 바꾸는 것은 모델 로딩과 `_generate` 뿐이다.
학습에 쓸지는 `make_sft.py` 가 관문 통과 여부로 거른다.

    python lora/distill.py --clauses lora/data/pool.json --out lora/data/distill_gemma31.json
    python lora/distill.py --clauses showcase/clauses_key.json --out lora/results/kb10_gemma31.json   ← 선생 천장 (10-26)
    python lora/distill.py --clauses showcase/clauses_key.json --ids <id,...> --samples 5 --temperature 0.7 \
        --out lora/results/vote_kb10_gemma31.json   ← 8단계 투표 표본 (10-27, top_k · top_p 는 모델 기본값 64 · 0.95)
    (memguard 로: ../M3/logs/memguard.sh lora/logs/distill.log <위 명령>)

끊기면 같은 명령으로 다시 — 이미 된 조문은 건너뛴다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_local_v2 as R  # noqa: E402

MODEL = "google/gemma-4-31B-it"


def load(name):
    import torch
    import transformers
    from transformers import AutoProcessor, BitsAndBytesConfig
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    torch.cuda.set_per_process_memory_fraction(28e9 / torch.cuda.mem_get_info(0)[1], 0)
    tok = AutoProcessor.from_pretrained(name).tokenizer
    model = transformers.AutoModelForMultimodalLM.from_pretrained(
        name, quantization_config=quant, dtype=torch.float16, device_map={"": 0},
        attn_implementation="sdpa").eval()
    return tok, model


def _generate(tok, model, user, temperature, max_new_tokens):
    """run_local_v2._generate 와 같되, 템플릿이 이미 <bos> 를 붙이므로 다시 붙이지 않는다.
    temperature 0 이면 탐욕 (증류 · 선생 천장), 0 보다 크면 표본 (8단계 투표)."""
    import torch
    conv = [{"role": "system", "content": R.SYSTEM_PROMPT}, {"role": "user", "content": user}]
    text = tok.apply_chat_template(conv, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tok(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    with torch.inference_mode():
        out = model.generate(**ids, max_new_tokens=max_new_tokens, num_beams=1,
                             **({"do_sample": True, "temperature": temperature} if temperature > 0 else {"do_sample": False}),
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    gen = out[0][ids["input_ids"].shape[1]:]
    return tok.decode(gen, skip_special_tokens=True), len(gen) >= max_new_tokens


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clauses", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-new-tokens", type=int, default=2048)
    ap.add_argument("--ids", help="쉼표로 나눈 조문 id — 이것만 돈다")
    ap.add_argument("--samples", type=int, default=1, help="8단계 투표 — 조문당 회차 수 (레코드가 회차마다 하나)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--p1", action="store_true", help="러너 P1(관문 탈락 → 빈 배열)을 켠다. 기본은 끈 채 — P1 은 채점 때 얹는다")
    a = ap.parse_args(argv)

    clauses = json.loads(Path(a.clauses).read_text("utf-8"))
    # 짧은 것부터 — 긴 조문의 OOM 이 앞을 막지 않게
    clauses.sort(key=lambda c: len(c["text"]))
    if a.ids:
        want = set(a.ids.split(","))
        clauses = [c for c in clauses if c["id"] in want]
        assert len(clauses) == len(want), "없는 조문 id"
    if a.limit:
        clauses = clauses[:a.limit]
    out = Path(a.out)
    recs = json.loads(out.read_text("utf-8")) if out.exists() else []
    done = {r["clause_id"] for r in recs}
    todo = [c for c in clauses if c["id"] not in done]
    print(f"조문 {len(clauses)} · 된 것 {len(done)} · 남은 것 {len(todo)}", flush=True)
    if not todo:
        return 0

    R._generate = _generate
    if not a.p1:                                    # 10-26 · 증류(10-21)는 P1 이전이었다 — 같은 조건으로
        R.drop_gate_failed = lambda output, marks: (output, None)
    t0 = time.time()
    tok, model = load(a.model)
    print(f"모델 로딩 {time.time() - t0:.0f}초", flush=True)
    t0 = time.time()
    for i, c in enumerate(todo, 1):
        tc = time.time()
        try:
            got = R.run_clause(tok, model, c, runs=a.samples, temperature=a.temperature, max_new_tokens=a.max_new_tokens)
        except Exception as e:                      # 첫 시도 OOM — 기록하고 다음
            if type(e).__name__ != "OutOfMemoryError":
                raise
            R._free_cache()
            got = [{"clause_id": c["id"], "error": "OOM"}]
        for g in got:
            g.update(teacher=a.model, temperature=a.temperature)
        recs += got
        R._release()
        fin = got[0].get("final") or {}
        print(f"진행 {i}/{len(todo)} [{c['id']}] 관문{sum(bool(fin.get(k)) for k in R.GATES)} "
              f"시도{got[0].get('n_attempts', 0)} 조문{time.time() - tc:.0f}s ({time.time() - t0:.0f}s)", flush=True)
        out.write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    print(f"완료 {len(recs)}건 → {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
