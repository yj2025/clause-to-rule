#!/bin/bash
# 선생 천장 (2026-10-26) — Gemma 4 31B 로 kb10 105조문, P1 끈 채. P1 은 score_split.py 가 채점 때 얹는다.
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
../M3/logs/memguard.sh lora/logs/kb10_gemma31.log /workspace/.venv/bin/python lora/distill.py \
  --clauses showcase/clauses_key.json --out lora/results/kb10_gemma31.json
