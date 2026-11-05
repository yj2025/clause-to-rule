#!/bin/bash
# 10-14 · C안 카드·약관요약 한두 줄 요약 시험 — KB Global Star 적금 1건, 모델마다 memguard.sh 를 따로 건다
# (한 모델이 멈춰도 다음 모델은 돈다). 큰 가중치를 읽을 때 디스크 캐시로 PSI 가 잠깐 튀어서 PSI 기준은 50% × 5회(10초).
# 쓰기: chain_cardsum_gstar.sh [모델...]   (기본: 다섯 개 전부)
cd "$(dirname "$0")/../cardsum"
export PYTHONUNBUFFERED=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}
export PSI_MAX=50 PSI_HITS=5
PY=${PY:-/workspace/.venv/bin/python}
LOG=$PWD/../logs/chain_cardsum_gstar.log
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
for m in ${@:-qwen exaone gemma12 gemma26 gemma31}; do
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  [ "$free" -lt 28000 ] && { say "$m 건너뜀: GPU 여유 ${free}MiB < 28000MiB"; continue; }
  say "$m 시작"
  ../logs/memguard.sh "$LOG" $PY run_cardsum.py --model $m --units units_gstar.json --out runs/gstar
  say "$m 끝 (종료코드 $?)"
done
say "체인 끝"
