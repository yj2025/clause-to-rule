#!/bin/bash
# 10-13 · 남은 55상품 key 요약 — ① Gemma 4 31B 전부 ② OOM 난 상품만 Gemma 4 12B
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=${PY:-/workspace/.venv/bin/python}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
say "① 31B 시작"
$PY run_batch.py --model gemma31 --out results/all_gemma31
say "① 끝 (종료코드 $?)"
say "② OOM 상품 12B 시작"
$PY run_batch.py --model gemma --out results/all_gemma12_fallback --only-failed-from results/all_gemma31
say "② 끝 (종료코드 $?) · 전체 체인 끝"
