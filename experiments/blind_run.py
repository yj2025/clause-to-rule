"""팀원 Part 2-1 모델(Qwen3.5-9B QLoRA)을 블라인드 43조문에 돌린다.

    python experiments/blind_run.py --tag e3                       # checkpoint-102 (Dev 가 고른 것)
    python experiments/blind_run.py --tag base --adapter none      # 학습 전 기준
    python experiments/blind_run.py --tag e3 --limit 2             # 연기 시험

**팀원 노트북과 같은 조건으로 돈다.** 프롬프트는 옮겨 적지 않고 노트북 `Cell 04` 를
그대로 실행해 가져온다 — 옮겨 적으면 한 글자만 달라도 다른 실험이 된다. 모델 적재
(4bit nf4 · fp16 · eager)와 생성(탐욕 · 토큰 6144)도 노트북 `Cell 07` 과 같다.
노트북 · 어댑터 · 모델 판의 해시를 결과 머리에 적는다.

결과는 `results/blind43_<tag>.jsonl` 에 **한 조문씩** 덧붙인다. 도중에 끊기면 같은 명령으로
이어 돈다 (이미 있는 sample_id 는 건너뛴다). 머리의 조건이 다르면 이어 돌지 않는다.

팀원 폴더는 **읽기만 한다.** 어댑터는 읽기로 적재하고 아무것도 쓰지 않는다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKETS = ROOT / "data" / "blind43_packets.jsonl"

SYS = Path("/workspace/personal_workplace_SYS/experiment_code")
NOTEBOOK = SYS / "finance_part2_1_qwen35_9b_qlora_pilot_v1_1.ipynb"
TRAINER = SYS / "qwen35_9b_part2_1_qlora_pilot_v1_1" / "trainer"
ADAPTERS = {"e1": TRAINER / "checkpoint-34", "e2": TRAINER / "checkpoint-68",
            "e3": TRAINER / "checkpoint-102"}

MODEL_ID = "Qwen/Qwen3.5-9B"
MAX_NEW_TOKENS = 6144                 # 노트북 EVAL_MAX_NEW_TOKENS


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def team_prompt(notebook=NOTEBOOK):
    """노트북 Cell 04 를 실행해 SYSTEM_PROMPT · user_prompt 를 가져온다."""
    nb = json.loads(Path(notebook).read_text("utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    src = [c for c in cells if "Cell 04." in c]
    if len(src) != 1:
        raise SystemExit(f"노트북에서 Cell 04 를 하나로 못 찾았다: {len(src)}개")
    ns = {}
    exec(src[0].replace("print(SYSTEM_PROMPT[:1000])", ""), ns)
    return ns["SYSTEM_PROMPT"], ns["user_prompt"]


def load_packets(path=PACKETS):
    rows = [json.loads(line) for line in Path(path).read_text("utf-8").splitlines() if line.strip()]
    return [r for r in rows if "_meta" not in r]


def header(tag, adapter):
    import peft
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    snap = Path(snapshot_download(MODEL_ID, local_files_only=True))
    return {
        "_meta": {
            "tag": tag,
            "model": MODEL_ID, "model_revision": snap.name,
            "adapter": str(adapter) if adapter else None,
            "adapter_sha256": sha256(Path(adapter) / "adapter_model.safetensors") if adapter else None,
            "notebook_sha256": sha256(NOTEBOOK),
            "packets_sha256": sha256(PACKETS),
            "generation": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS,
                           "quant": "4bit nf4 double · compute fp16", "attn": "eager",
                           "enable_thinking": False},
            "versions": {"transformers": transformers.__version__, "peft": peft.__version__,
                         "torch": torch.__version__},
            "git": subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--short", "HEAD"],
                                  cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        }
    }


def _same_conditions(a, b):
    keys = ("model", "model_revision", "adapter_sha256", "notebook_sha256", "packets_sha256",
            "generation")
    return all(a["_meta"].get(k) == b["_meta"].get(k) for k in keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--adapter", default=None, help="e1 · e2 · e3 · none · 경로 (기본: tag)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    name = a.adapter or a.tag
    adapter = None if name == "none" else ADAPTERS.get(name, Path(name))
    if adapter is not None and not (Path(adapter) / "adapter_model.safetensors").exists():
        raise SystemExit(f"어댑터가 없다: {adapter}")

    out = ROOT / "results" / (f"blind43_{a.tag}.jsonl" if a.limit is None
                              else f"blind43_{a.tag}.smoke{a.limit}.jsonl")
    head = header(a.tag, adapter)
    done = set()
    if out.exists():
        prev = [json.loads(x) for x in out.read_text("utf-8").splitlines() if x.strip()]
        if not prev or not _same_conditions(prev[0], head):
            raise SystemExit(f"{out} 가 다른 조건으로 이미 있다 — 덮어쓰지 않는다")
        done = {r["sample_id"] for r in prev[1:]}
    else:
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(head, ensure_ascii=False) + "\n", "utf-8")

    packets = load_packets()[: a.limit]
    todo = [p for p in packets if p["sample_id"] not in done]
    print(f"{a.tag}: {len(todo)} / {len(packets)} 조문 남음 → {out}", flush=True)
    if not todo:
        return

    import torch
    from peft import PeftModel
    from transformers import AutoModelForMultimodalLM, AutoProcessor, BitsAndBytesConfig

    system_prompt, user_prompt = team_prompt()
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    tok = processor.tokenizer
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForMultimodalLM.from_pretrained(
        MODEL_ID,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_use_double_quant=True,
                                               bnb_4bit_compute_dtype=torch.float16),
        device_map="auto", attn_implementation="eager", dtype=torch.float16,
        trust_remote_code=True)
    if adapter is not None:
        model = PeftModel.from_pretrained(model, str(adapter))
    model.eval()

    for i, p in enumerate(todo, 1):
        prompt = tok.apply_chat_template(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user_prompt(p["packet_text"])}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        enc = tok(prompt, return_tensors="pt", add_special_tokens=False)
        enc = {k: v.to(next(model.parameters()).device) for k, v in enc.items()}
        t0 = time.time()
        with torch.inference_mode():
            ids = model.generate(**enc, do_sample=False, max_new_tokens=MAX_NEW_TOKENS,
                                 pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id,
                                 use_cache=True)
        new = ids[0, enc["input_ids"].shape[1]:]
        rec = {"sample_id": p["sample_id"], "novelty": p["novelty"],
               "prompt_tokens": int(enc["input_ids"].shape[1]), "new_tokens": int(new.shape[0]),
               "truncated": int(new.shape[0]) >= MAX_NEW_TOKENS,
               "seconds": round(time.time() - t0, 1),
               "raw_output": tok.decode(new, skip_special_tokens=True).strip()}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {p['sample_id']} {rec['new_tokens']}tok {rec['seconds']}s"
              + (" TRUNCATED" if rec["truncated"] else ""), flush=True)


if __name__ == "__main__":
    sys.exit(main())
