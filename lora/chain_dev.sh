#!/bin/bash
# epoch 별 체크포인트를 dev 22 조문으로 (2026-10-22). e2(dev 손실 최저) → e3 → e1 순.
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
for e in 2:104 3:156 1:52; do
  n=${e%%:*}; s=${e##*:}
  ../M3/logs/memguard.sh lora/logs/dev_e$n.log /workspace/.venv/bin/python lora/eval_adapter.py \
    --adapter lora/adapters/r16/checkpoint-$s --split dev --out lora/results/dev_e$n.json || exit 1
done
echo "전부 끝" >> lora/logs/dev_e1.log
