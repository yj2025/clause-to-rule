"""Qwen3-8B QLoRA — 조문 → 조건식 (2026-10-20).

V100 32GB 기준: NF4 4비트 · fp16 계산(bf16 세대 아님) · gradient checkpointing · 배치 1 × 누적 8.
손실은 **정답(assistant) 토큰에만** 건다. 입력은 추론 때와 글자까지 같게 만든다 —
`apply_chat_template(..., add_generation_prompt=True, enable_thinking=False)` 뒤에 정답 + <|im_end|>.

    python lora/train_lora.py --out lora/adapters/r16 --epochs 3
"""

import argparse
import json
import math
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer,
                          TrainingArguments)

HERE = Path(__file__).resolve().parent
BASE = "Qwen/Qwen3-8B"


def encode(tok, s, max_len):
    sys_, user, ans = s["messages"]
    prompt = tok.apply_chat_template([sys_, user], tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False)
    p = tok(prompt, add_special_tokens=False)["input_ids"]
    t = tok(ans["content"] + "<|im_end|>\n", add_special_tokens=False)["input_ids"]
    if len(p) + len(t) > max_len:
        return None
    return {"input_ids": p + t, "labels": [-100] * len(p) + t}


def load_jsonl(path, tok, max_len):
    rows, skipped = [], 0
    for line in open(path, encoding="utf-8"):
        e = encode(tok, json.loads(line), max_len)
        if e is None:
            skipped += 1
        else:
            rows.append(e)
    return rows, skipped


def collate(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    ids = torch.full((len(batch), n), pad_id)
    lab = torch.full((len(batch), n), -100)
    att = torch.zeros((len(batch), n), dtype=torch.long)
    for i, b in enumerate(batch):
        k = len(b["input_ids"])
        ids[i, :k] = torch.tensor(b["input_ids"])
        lab[i, :k] = torch.tensor(b["labels"])
        att[i, :k] = 1
    return {"input_ids": ids, "labels": lab, "attention_mask": att}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--train", default=str(HERE / "data/train.jsonl"))
    ap.add_argument("--dev", default=str(HERE / "data/dev.jsonl"))
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=6144)
    a = ap.parse_args(argv)

    tok = AutoTokenizer.from_pretrained(BASE)
    train, sk1 = load_jsonl(a.train, tok, a.max_len)
    dev, sk2 = load_jsonl(a.dev, tok, a.max_len)
    print(f"train {len(train)} (길어서 뺌 {sk1}) · dev {len(dev)} (뺌 {sk2}) · "
          f"최장 {max(len(r['input_ids']) for r in train)} 토큰", flush=True)

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=quant, dtype=torch.float16,
                                                 device_map={"": 0}, attn_implementation="sdpa")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()

    steps_per_epoch = math.ceil(len(train) / a.accum)
    args = TrainingArguments(
        output_dir=a.out, num_train_epochs=a.epochs, per_device_train_batch_size=1,
        per_device_eval_batch_size=1, gradient_accumulation_steps=a.accum, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_steps=max(1, steps_per_epoch // 5), weight_decay=0.0,
        fp16=True, logging_steps=5, eval_strategy="epoch", save_strategy="epoch",
        save_total_limit=None, report_to="none", gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False}, optim="paged_adamw_8bit",
        remove_unused_columns=False, seed=0, dataloader_num_workers=0)
    trainer = Trainer(model=model, args=args, train_dataset=train, eval_dataset=dev,
                      data_collator=lambda b: collate(b, tok.pad_token_id))
    t0 = time.time()
    trainer.train()
    model.save_pretrained(Path(a.out) / "final")
    tok.save_pretrained(Path(a.out) / "final")
    hist = [h for h in trainer.state.log_history]
    (Path(a.out) / "log_history.json").write_text(json.dumps(hist, ensure_ascii=False, indent=1), "utf-8")
    print(f"학습 끝 {time.time() - t0:.0f}초 → {a.out}", flush=True)


if __name__ == "__main__":
    main()
