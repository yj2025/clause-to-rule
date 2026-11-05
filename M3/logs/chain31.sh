#!/bin/bash
# 10-12 · Gemma 4 31B (NF4) — ① 요약입력 조항 ② 원문 전체
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=${PY:-/workspace/.venv/bin/python}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
say "다운로드 시작"
$PY -c "from huggingface_hub import snapshot_download as s; print(s('google/gemma-4-31B-it'))" 2>&1 | tail -1
say "받음"
say "① 요약입력 시작"
$PY compare_terms.py --terms terms_kbstar.txt --prompt prompt_target.txt --out results/kbstar_03_gemma31 \
  --models gemma31 --max-input-tokens 8192 --max-new-tokens 6144 --gpu-gb 30
say "① 끝 (종료코드 $?)"
say "② 원문 전체 시작"
$PY compare_terms.py --terms terms_kbstar_full.txt --prompt prompt_target_full.txt --out results/kbstar_full_03_gemma31 \
  --models gemma31 --max-input-tokens 8192 --max-new-tokens 6144 --gpu-gb 30
say "② 끝 (종료코드 $?) · 31B 체인 끝"
