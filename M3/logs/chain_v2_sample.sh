#!/bin/bash
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
for m in gemma31 gemma qwen; do
  echo "$(TZ=Asia/Seoul date '+%F %T') $m 시작"
  ${PY:-/workspace/.venv/bin/python} run_prompt.py --model $m --system results/v2_sample/system.txt --user results/v2_sample/user.txt --out results/v2_sample/$m.json
done
echo "$(TZ=Asia/Seoul date '+%F %T') 체인 끝"
