#!/bin/bash
# NEXT_PLAN 4단계 (2026-10-27) — 3단계에서 고른 e1 + 제약 (P1 은 러너에 켜져 있음) 으로 kb10 dev → test 각 한 번.
# test 는 원인 분석에 이미 쓴 셋 — 참고 숫자. P1 · 제약 둘 다 test 를 본 뒤 고른 처방이다.
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=/workspace/personal_workplace_CHO/pylib
for s in dev test; do
  ../M3/logs/memguard.sh lora/logs/${s}_e1_c.log /workspace/.venv/bin/python lora/eval_adapter.py \
    --adapter lora/adapters/r16/checkpoint-52 --constrain --split $s --out lora/results/${s}_e1_c.json || exit 1
done
/workspace/.venv/bin/python lora/score_split.py --runs lora/results/dev_e1.json lora/results/test_e1.json \
  lora/results/dev_e1_c.json lora/results/test_e1_c.json lora/results/kb10_gemma31.json \
  --json lora/results/score_split_final.json > lora/results/score_split_final.txt 2>/dev/null
echo "전부 끝" >> lora/logs/test_e1_c.log
