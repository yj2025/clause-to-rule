"""시스템 · 사용자 프롬프트를 그대로 넣어 한 모델로 생성한다 (2026-10-13 · 개인화 요약 프롬프트 시험).

    python run_prompt.py --model gemma31 --system <system.txt> --user <user.txt> --out <out.json>
설정은 compare_terms.py 와 같다: NF4 4비트 · V100 이면 fp16 · greedy · 생각 모드 끔. 사용자 메시지에 다른 글을 붙이지 않는다.
"""
import argparse
import json
import time
from pathlib import Path

import compare_terms as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=C.MODELS, required=True)
    ap.add_argument("--system", type=Path, required=True)
    ap.add_argument("--user", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=6144)
    a = ap.parse_args()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    enc = C.load_encoder(a.model)
    cls = getattr(transformers, "AutoModelForMultimodalLM") if a.model.startswith("gemma") else AutoModelForCausalLM
    t0 = time.perf_counter()
    model = cls.from_pretrained(C.MODELS[a.model], quantization_config=quant, dtype=dtype, device_map={"": 0},
                                attn_implementation="sdpa", trust_remote_code=(a.model == "exaone")).eval()
    load = time.perf_counter() - t0
    msgs = [{"role": "system", "content": a.system.read_text("utf-8")}, {"role": "user", "content": a.user.read_text("utf-8")}]
    inputs = enc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True,
                                     return_tensors="pt", enable_thinking=False).to("cuda:0")
    n_in = inputs["input_ids"].shape[-1]
    t0 = time.perf_counter()
    with torch.inference_mode():
        seq = model.generate(**inputs, do_sample=False, max_new_tokens=a.max_new_tokens, use_cache=True, num_beams=1)
    gen = time.perf_counter() - t0
    tok = getattr(enc, "tokenizer", enc)
    out = tok.decode(seq[0, n_in:], skip_special_tokens=True)
    a.out.write_text(json.dumps({"model": C.MODELS[a.model], "load_seconds": load, "input_tokens": n_in,
                                 "output_tokens": int(seq.shape[-1] - n_in), "generation_seconds": gen,
                                 "peak_reserved_gb": torch.cuda.max_memory_reserved(0) / 1e9, "output": out},
                                ensure_ascii=False, indent=1), "utf-8")
    print(f"{a.model}: 입력 {n_in} · 생성 {seq.shape[-1] - n_in} · {gen:.0f}초", flush=True)


if __name__ == "__main__":
    main()
