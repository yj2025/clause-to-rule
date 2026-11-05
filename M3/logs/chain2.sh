#!/bin/bash
# 10-12 체인2 · ① EXAONE 재실행(요약입력 조항, 고친 사본) ② 원문 전체 세 모델
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache} M3_EXAONE_PATH=exaone_local
PY=${PY:-/workspace/.venv/bin/python}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
say "① EXAONE 재실행 시작"
$PY compare_terms.py --terms terms_kbstar.txt --prompt prompt_target.txt --out results/kbstar_02_exaone \
  --models exaone --max-input-tokens 8192 --max-new-tokens 6144
say "① 끝 (종료코드 $?)"
say "② 원문 전체 시작"
$PY compare_terms.py --terms terms_kbstar_full.txt --prompt prompt_target_full.txt --out results/kbstar_full_01 \
  --models gemma exaone qwen --max-input-tokens 8192 --max-new-tokens 6144
say "② 끝 (종료코드 $?) · 체인2 끝"
