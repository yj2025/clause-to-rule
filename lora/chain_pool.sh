#!/bin/bash
# NEXT_PLAN 3단계 (2026-10-26) — 보류 풀 111조문 네 벌. 선생 kb10(chain_teacher.sh)이 GPU 를 비울 때까지 기다린다.
# 제약 쪽을 먼저 — 새 코드라 터지면 일찍 멈춘다.
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=/workspace/personal_workplace_CHO/pylib
while pgrep -f "^/workspace/.venv/bin/python lora/distill.py" >/dev/null; do sleep 60; done   # 10-26 고침: 앞이 ^ 없이 띄운 셸 명령줄까지 잡아 두 시간 넘게 멈춤
A=lora/adapters/r16/checkpoint-52
for job in "e1_c:--adapter $A --constrain" "base_c:--constrain" "e1:--adapter $A" "base:"; do
  n=${job%%:*}; args=${job#*:}
  ../M3/logs/memguard.sh lora/logs/pool_$n.log /workspace/.venv/bin/python lora/eval_pool.py \
    --out lora/results/pool_$n.json $args || exit 1
done
/workspace/.venv/bin/python lora/eval_pool.py --score lora/results/pool_{base,base_c,e1,e1_c}.json >> lora/logs/pool_base.log 2>&1
echo "전부 끝" >> lora/logs/pool_base.log
