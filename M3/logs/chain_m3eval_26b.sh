#!/bin/bash
# 10-14 · v0.3 / v0.4 개인화 요약 프롬프트를 Gemma 4 26B-A4B(전문가 NF4 · 나머지 fp16 · greedy)로 T1~T4 실행 후 채점
cd "$(dirname "$0")/../m3eval"
export PYTHONUNBUFFERED=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=${PY:-/workspace/.venv/bin/python}
SNAP=$(ls -d ${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}/hub/models--google--gemma-4-26B-A4B-it/snapshots/*)
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
say "v0.3 시작"
$PY run_m3.py --system prompts/personalized_summary_v0.3.system.txt --cases testcases --model $SNAP --out runs/v0.3_gemma26 --experts-nf4
say "v0.3 끝 (종료코드 $?)"
say "v0.4 시작"
$PY run_m3.py --system prompts/personalized_summary_v0.4.system.txt --cases testcases_v0.4 --model $SNAP --out runs/v0.4_gemma26 --experts-nf4
say "v0.4 끝 (종료코드 $?)"
$PY grade.py --cases testcases --expect expectations.json --outputs runs/v0.3_gemma26 runs/v0.4_gemma26=testcases_v0.4 \
  --report runs/compare_gemma26.md --csv runs/compare_gemma26.csv
say "채점 끝 · 체인 끝"
