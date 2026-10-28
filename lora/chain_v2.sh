#!/bin/bash
# NEXT_PLAN 10단계 (2026-10-27) — 새 평가셋 gold_v2 에 후보를 한 번씩. 후보는 lora/final_candidates.md 에 고정.
# 순정 → e1 → Gemma 탐욕 → (Gemma 가 끼어드는 조문만) Gemma 투표 표본 → score_v2.py 채점 한 번.
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/workspace/.venv/bin/python
CL=data/gold_v2/_clauses.json
MG=../M3/logs/memguard.sh
$MG lora/logs/v2_base.log $PY lora/eval_pool.py --clauses $CL --out lora/results/v2_base.json || exit 1
$MG lora/logs/v2_e1.log $PY lora/eval_pool.py --clauses $CL --adapter lora/adapters/r16/checkpoint-52 \
  --out lora/results/v2_e1.json || exit 1
$MG lora/logs/v2_gemma31.log $PY lora/distill.py --clauses $CL --out lora/results/v2_gemma31.json || exit 1
IDS=$($PY lora/score_v2.py --vote-ids 2>/dev/null | tail -1)
echo "Gemma 투표 조문: $IDS" >> lora/logs/v2_gemma31.log
if [ -n "$IDS" ]; then
  $MG lora/logs/v2_vote_gemma31.log $PY lora/distill.py --clauses $CL --ids "$IDS" --samples 5 --temperature 0.7 \
    --out lora/results/v2_vote_gemma31.json || exit 1
else
  echo "[]" > lora/results/v2_vote_gemma31.json
fi
{ echo "# $(TZ=Asia/Seoul date '+%F %T KST') · $(hostname) · git $(git rev-parse --short HEAD) · score_v2.py md5 $(md5sum lora/score_v2.py | cut -c1-8) · final_candidates.md md5 $(md5sum lora/final_candidates.md | cut -c1-8)"
  $PY lora/score_v2.py 2>&1 | grep -v -i warn; } > lora/logs/score_v2.log
echo "모두 끝" >> lora/logs/score_v2.log
