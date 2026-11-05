#!/bin/bash
# 10-14 · v0.3 / v0.4 개인화 요약 프롬프트를 Gemma 4 12B(fp16 · greedy)로 T1~T4 실행 후 채점. memguard.sh 로 띄움
cd "$(dirname "$0")/../m3eval"
export PYTHONUNBUFFERED=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=${PY:-/workspace/.venv/bin/python}
SNAP=$(ls -d ${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}/hub/models--google--gemma-4-12B-it/snapshots/*)
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
# GPU 가 덜 비어 있으면 device_map=auto 가 CPU 로 넘겨 컨테이너 메모리를 씀 → 시작하지 않음
free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
[ "$free" -lt 28000 ] && { say "GPU 여유 ${free}MiB < 28000MiB → 시작 안 함"; exit 1; }
say "v0.3 시작"
$PY run_m3.py --system prompts/personalized_summary_v0.3.system.txt --cases testcases --model $SNAP --out runs/v0.3_gemma12
say "v0.3 끝 (종료코드 $?)"
say "v0.4 시작"
$PY run_m3.py --system prompts/personalized_summary_v0.4.system.txt --cases testcases_v0.4 --model $SNAP --out runs/v0.4_gemma12
say "v0.4 끝 (종료코드 $?)"
$PY grade.py --cases testcases --expect expectations.json --outputs runs/v0.3_gemma12 runs/v0.4_gemma12=testcases_v0.4 \
  --report runs/compare_gemma12.md --csv runs/compare_gemma12.csv
say "채점 끝 · 체인 끝"
