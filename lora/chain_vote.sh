#!/bin/bash
# NEXT_PLAN 8단계 (2026-10-27) — 자기 일관성 투표용 표본. e1, 온도 0.7, 조문당 5회 (재시도 · 관문 · P1 은 회차마다 그대로).
# 8-1 보류 풀 111 (정답 없이 일치 분포) → 8-2 kb10 dev · test (k 고르기, 참고 숫자). 투표 · 채점은 vote.py (GPU 없음).
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=lora/adapters/r16/checkpoint-52
../M3/logs/memguard.sh lora/logs/vote_pool_e1.log /workspace/.venv/bin/python lora/eval_pool.py \
  --adapter $A --samples 5 --temperature 0.7 --out lora/results/vote_pool_e1.json || exit 1
for s in dev test; do
  ../M3/logs/memguard.sh lora/logs/vote_${s}_e1.log /workspace/.venv/bin/python lora/eval_adapter.py \
    --adapter $A --samples 5 --temperature 0.7 --split $s --out lora/results/vote_${s}_e1.json || exit 1
done
echo "전부 끝" >> lora/logs/vote_test_e1.log
