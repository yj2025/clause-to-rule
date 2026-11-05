"""상품 여러 개를 한 모델로 이어서 요약한다 — 모델은 한 번만 올린다 (2026-10-13 · 전 상품 key 요약).

    python run_batch.py --model gemma31 --out results/all_gemma31 [--only-failed-from results/all_gemma31] [--src <요약입력 json>]

입력: 팀 요약입력의 상품마다 특약 + 상품설명서 조항(m2_inputs.build — M2 docsab/run_merged.py 에서 옮김) + prompt_target.txt(목표 형식 지시문).
설정은 compare_terms.py 와 같다(NF4 · V100 이면 fp16 · greedy · 생각 끔 · 출력 6144). 사용자 메시지에 다른 글을 붙이지 않는다.
상품마다 <out>/<product_id>.json 을 쓴다. 이미 있으면 건너뛴다(이어 돌리기). OOM 은 그 상품만 기록하고 넘어간다.
"""
import argparse
import json
import time
from pathlib import Path

import compare_terms as C
import m2_inputs as R
from m2_inputs import parse_json

DONE = {"KB스타통장", "KB 프리N통장", "KB 별별통장2"}   # 10-12~13 에 이미 돌린 상품


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=C.MODELS, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only-failed-from", type=Path)
    ap.add_argument("--max-new-tokens", type=int, default=6144)
    ap.add_argument("--src", type=Path, default=R.SRC, help="팀 요약 입력 json (기본: docs/요약입력_상품별.json)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    system = Path("prompt_target.txt").read_text("utf-8")
    packets = [p for p in json.loads(a.src.read_text("utf-8"))["packets"] if p["product_name"] not in DONE]
    if a.only_failed_from:
        failed = {json.loads(f.read_text("utf-8"))["product_id"] for f in a.only_failed_from.glob("*.json")
                  if json.loads(f.read_text("utf-8")).get("error")}
        packets = [p for p in packets if p["product_id"] in failed]
    enc = C.load_encoder(a.model)
    msgs = lambda p: [{"role": "system", "content": system}, {"role": "user", "content": R.build(p)}]
    ntok = {p["product_id"]: enc.apply_chat_template(msgs(p), tokenize=True, add_generation_prompt=True, return_dict=True,
                                                     return_tensors="pt", enable_thinking=False)["input_ids"].shape[-1] for p in packets}
    packets.sort(key=lambda p: ntok[p["product_id"]])        # 짧은 것부터
    todo = [p for p in packets if not (a.out / f"{p['product_id']}.json").exists()]
    print(f"{a.model}: 대상 {len(packets)} · 남은 것 {len(todo)}", flush=True)
    if not todo:
        return
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    cls = getattr(transformers, "AutoModelForMultimodalLM") if a.model.startswith("gemma") else AutoModelForCausalLM
    torch.cuda.set_per_process_memory_fraction(28e9 / torch.cuda.mem_get_info(0)[1], 0)   # compare_terms --gpu-gb 30 과 같은 상한
    model = cls.from_pretrained(C.MODELS[a.model], quantization_config=quant, dtype=dtype, device_map={"": 0},
                                attn_implementation="sdpa", trust_remote_code=(a.model == "exaone")).eval()
    tok = getattr(enc, "tokenizer", enc)
    for i, p in enumerate(todo, 1):
        inputs = enc.apply_chat_template(msgs(p), tokenize=True, add_generation_prompt=True, return_dict=True,
                                         return_tensors="pt", enable_thinking=False).to("cuda:0")
        n_in = inputs["input_ids"].shape[-1]
        rec = {"product_id": p["product_id"], "product_name": p["product_name"], "model": C.MODELS[a.model], "in_tokens": n_in}
        t0 = time.perf_counter()
        try:
            with torch.inference_mode():
                seq = model.generate(**inputs, do_sample=False, max_new_tokens=a.max_new_tokens, use_cache=True, num_beams=1)
            raw = tok.decode(seq[0, n_in:], skip_special_tokens=True)
            rec.update(gen_tokens=int(seq.shape[-1] - n_in), raw=raw, parsed=parse_json(raw),
                       truncated=int(seq.shape[-1] - n_in) >= a.max_new_tokens)
        except torch.OutOfMemoryError:
            rec.update(error="OOM", parsed=None)
            torch.cuda.empty_cache()
        rec["sec"] = round(time.perf_counter() - t0, 1)
        (a.out / f"{p['product_id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), "utf-8")
        state = rec.get("error") or ("읽힘" if rec["parsed"] else "안 읽힘")
        print(f"[{i}/{len(todo)}] {p['product_name']} · 입력 {n_in} · 생성 {rec.get('gen_tokens', 0)} · {rec['sec']:.0f}초 · {state}", flush=True)
        del inputs
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
