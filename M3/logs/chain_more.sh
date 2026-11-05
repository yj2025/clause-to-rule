#!/bin/bash
# 10-13 · 상품 2개 더 (프리N통장 · 별별통장2) — Gemma 4 31B · Gemma 4 12B · Qwen3-8B, 요약입력 조항 + 목표 형식 지시문
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=${PY:-/workspace/.venv/bin/python}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
for t in freen byul2; do
  say "$t 시작"
  $PY compare_terms.py --terms terms_$t.txt --prompt prompt_target.txt --out results/${t}_01 \
    --models gemma31 gemma qwen --max-input-tokens 10240 --max-new-tokens 6144 --gpu-gb 30
  say "$t 끝 (종료코드 $?)"
done
say "체인 끝"
