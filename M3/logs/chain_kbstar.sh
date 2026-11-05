#!/bin/bash
# 10-12 · Gemma 4 12B / EXAONE 3.5 7.8B / Qwen3-8B — KB스타통장 합친 입력 + 목표 형식 지시문
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}
PY=${PY:-/workspace/.venv/bin/python}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
say "다운로드 시작"
for m in google/gemma-4-12B-it LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct; do
  $PY -c "from huggingface_hub import snapshot_download as s; p=s('$m'); print(p)" 2>&1 | tail -1
  say "받음 $m"
done
say "실행 시작"
$PY compare_terms.py --terms terms_kbstar.txt --prompt prompt_target.txt --out results/kbstar_01 \
  --models gemma exaone qwen --max-input-tokens 8192 --max-new-tokens 6144
say "체인 끝 (종료코드 $?)"
