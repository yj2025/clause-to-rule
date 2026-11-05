#!/bin/bash
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True M3_EXAONE_PATH=exaone_local
P=m3eval/prompts   # 시스템 프롬프트 (M2 docsab/prompts 와 같은 파일)
for m in gemma31 gemma qwen; do
  echo "$(TZ=Asia/Seoul date '+%F %T') $m 시작"
  ${PY:-/workspace/.venv/bin/python} run_prompt.py --model $m --system $P/personalized_summary_v0.3.system.txt --user prompts/example_kbstar_user.txt --out results/personal_01/$m.json
done
echo "$(TZ=Asia/Seoul date '+%F %T') 체인 끝"
