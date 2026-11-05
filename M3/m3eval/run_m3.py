#!/usr/bin/env python3
"""M3 개인화 요약 프롬프트 실행기.

system 프롬프트 파일 + 테스트 입력(JSON) 폴더를 받아 Qwen2.5-7B-Instruct 로 출력을 만들고
케이스별 원문 출력과 실행 정보를 저장한다. 채점은 grade.py 가 따로 한다.

예)
  python run_m3.py \
      --system prompts/personalized_summary_v0.3.system.txt \
      --cases testcases \
      --model /workspace/models/Qwen2.5-7B-Instruct \
      --out runs/v0.3

V100: bf16 미지원 → fp16 고정, FlashAttention-2 미사용(sdpa).
10-14 추가: --experts-nf4 — Gemma 4 26B-A4B(MoE)는 전문가 가중치가 nn.Parameter 라 BitsAndBytesConfig 4비트로
안 줄어 V100 32GB 에 못 올린다(컨테이너 RAM 도 28GB 라 CPU 에 둘 수 없음). 전문가를 전문가별 NF4 로 직접 압축해
GPU 에 두고, 고른 전문가만 그때그때 풀어 계산한다. 나머지 층은 fp16.
일치율 테스트용이므로 기본은 greedy(do_sample=False). 같은 입력이면 같은 출력이 나와야 비교가 된다.
"""
import argparse
import json
import time
from pathlib import Path

# user 메시지 끝에 붙이는 출력 형식 리마인더. --no-reminder 로 끌 수 있다(A/B 비교용).
REMINDER = "위 입력만 근거로, system 에 적힌 출력 형식의 JSON 하나만 출력하라. 다른 글은 쓰지 않는다."


def build_user_message(case: dict, reminder: bool) -> str:
    body = json.dumps(case, ensure_ascii=False, indent=1)
    return body + ("\n\n" + REMINDER if reminder else "")


def nf4_experts_forward(self, hidden_states, top_k_index, top_k_weights):
    """Gemma4TextExperts 의 eager 계산과 같다. 고른 전문가의 NF4 가중치만 그때그때 fp16 으로 풀어 쓴다."""
    import torch
    from bitsandbytes.functional import dequantize_4bit
    out = torch.zeros_like(hidden_states)
    mask = torch.nn.functional.one_hot(top_k_index, num_classes=self.num_experts).permute(2, 1, 0)
    for e in torch.greater(mask.sum(dim=(-1, -2)), 0).nonzero()[:, 0].tolist():
        pos, tok = torch.where(mask[e])
        gate, up = torch.nn.functional.linear(hidden_states[tok], dequantize_4bit(*self.q_gate_up_proj[e])).chunk(2, dim=-1)
        x = torch.nn.functional.linear(self.act_fn(gate) * up, dequantize_4bit(*self.q_down_proj[e]))
        out.index_add_(0, tok, (x * top_k_weights[tok, pos, None]).to(out.dtype))
    return out


def load_experts_nf4(model_path):
    """Gemma 4 26B-A4B 용. 컨테이너 RAM 한도(28GB) · V100 32GB 안에서 올리려고
    전문가 층만 meta 로 만들고, 체크포인트를 텐서 하나씩 읽어 전문가는 전문가별 NF4 로 GPU 에 둔다. 나머지는 fp16."""
    import json
    import types
    import torch
    import transformers
    from bitsandbytes.functional import quantize_4bit
    from safetensors import safe_open

    config = transformers.AutoConfig.from_pretrained(model_path)
    cls = getattr(transformers, "AutoModelForMultimodalLM", None) or transformers.AutoModelForCausalLM
    exp_cls = transformers.models.gemma4.modeling_gemma4.Gemma4TextExperts
    orig_init = exp_cls.__init__

    def meta_init(self, *a, **k):
        with torch.device("meta"):
            orig_init(self, *a, **k)
    exp_cls.__init__ = meta_init
    try:
        with torch.device("cuda:0"):
            model = cls.from_config(config, dtype=torch.float16, attn_implementation="sdpa")
    finally:
        exp_cls.__init__ = orig_init
    model.eval()

    params = dict(model.named_parameters(remove_duplicate=False))
    buffers = dict(model.named_buffers(remove_duplicate=False))
    mods = dict(model.named_modules())
    loaded = set()
    weight_map = json.loads((Path(model_path) / "model.safetensors.index.json").read_text())["weight_map"]
    for shard in sorted(set(weight_map.values())):
        with safe_open(str(Path(model_path) / shard), framework="pt", device="cpu") as f:
            for k in f.keys():
                t = f.get_tensor(k)
                mod_name, _, leaf = k.rpartition(".")
                if leaf in ("gate_up_proj", "down_proj") and type(mods[mod_name]).__name__ == "Gemma4TextExperts":
                    g = t.to("cuda:0", torch.float16)
                    q = [quantize_4bit(g[e].contiguous(), quant_type="nf4", blocksize=64) for e in range(g.shape[0])]
                    m = mods[mod_name]
                    setattr(m, "q_" + leaf, q)
                    del m._parameters[leaf]
                    del g
                else:
                    dst = params.get(k, buffers.get(k))
                    if dst is None:
                        raise KeyError(f"모델에 없는 체크포인트 키: {k}")
                    dst.data.copy_(t.to(dst.dtype))
                loaded.add(k)
                del t
    for m in model.modules():
        if type(m).__name__ == "Gemma4TextExperts":
            assert hasattr(m, "q_gate_up_proj") and hasattr(m, "q_down_proj")
            m.forward = types.MethodType(nf4_experts_forward, m)
    missing = [n for n in params if n not in loaded and not n.endswith(("gate_up_proj", "down_proj"))]
    print(f"체크포인트에 없는 파라미터(묶인 가중치여야 함): {missing}")
    model.tie_weights()
    torch.cuda.empty_cache()
    print(f"전문가 NF4 로드 끝, GPU {torch.cuda.memory_allocated() / 2**30:.1f}GB")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, help="system 프롬프트 txt 경로")
    ap.add_argument("--cases", required=True, help="테스트 입력 JSON 폴더 (T*.json)")
    ap.add_argument("--model", required=True, help="모델 경로 또는 HF 이름")
    ap.add_argument("--out", required=True, help="출력 저장 폴더")
    ap.add_argument("--max-new-tokens", type=int, default=2560)
    ap.add_argument("--no-reminder", action="store_true", help="user 끝 출력 형식 리마인더를 넣지 않음")
    ap.add_argument("--sample", action="store_true", help="샘플링 사용(기본은 greedy)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--repeat", type=int, default=1, help="케이스당 반복 횟수(샘플링 안정성 확인용)")
    ap.add_argument("--only", nargs="*", help="특정 케이스만 실행, 예: --only T1 T3")
    ap.add_argument("--experts-nf4", action="store_true", help="MoE 전문가를 전문가별 NF4 로 GPU 에 둠(Gemma 4 26B-A4B 용)")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    system_text = Path(args.system).read_text(encoding="utf-8")
    case_files = sorted(Path(args.cases).glob("T*.json"))
    if args.only:
        case_files = [p for p in case_files if p.stem in set(args.only)]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(args.model)
    if args.experts_nf4:
        model = load_experts_nf4(args.model)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.float16, device_map="auto", attn_implementation="sdpa"
        )
    model.eval()

    gen_kwargs = dict(max_new_tokens=args.max_new_tokens, repetition_penalty=1.0)
    if args.sample:
        gen_kwargs.update(do_sample=True, temperature=args.temperature, top_p=0.8)
    else:
        # generation_config 의 기본 샘플링 값을 덮어써 greedy 로 고정
        gen_kwargs.update(do_sample=False, temperature=None, top_p=None, top_k=None)

    meta = {
        "system": str(args.system),
        "cases": str(args.cases),
        "experts_nf4": args.experts_nf4,
        "model": args.model,
        "reminder": not args.no_reminder,
        "gen_kwargs": {k: v for k, v in gen_kwargs.items() if v is not None},
        "system_tokens": len(tok(system_text)["input_ids"]),
        "runs": [],
    }

    for cf in case_files:
        case = json.loads(cf.read_text(encoding="utf-8"))
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": build_user_message(case, not args.no_reminder)},
        ]
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda:0" if args.experts_nf4 else model.device)
        for r in range(args.repeat):
            t0 = time.time()
            with torch.no_grad():
                out = model.generate(**inputs, **gen_kwargs, pad_token_id=tok.eos_token_id)
            new_ids = out[0][inputs["input_ids"].shape[1]:]
            text = tok.decode(new_ids, skip_special_tokens=True)
            name = cf.stem if args.repeat == 1 else f"{cf.stem}_r{r + 1}"
            (out_dir / f"{name}.out.txt").write_text(text, encoding="utf-8")
            info = {
                "case": cf.stem,
                "file": f"{name}.out.txt",
                "input_tokens": int(inputs["input_ids"].shape[1]),
                "output_tokens": int(new_ids.shape[0]),
                "hit_max_new_tokens": int(new_ids.shape[0]) >= args.max_new_tokens,
                "seconds": round(time.time() - t0, 1),
            }
            meta["runs"].append(info)
            print(json.dumps(info, ensure_ascii=False))

    (out_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {out_dir}")


if __name__ == "__main__":
    main()
