#!/bin/bash
# 10-12 · 원문 전체(상품설명서 txt 전체 + 특약 조항) — chain_kbstar 끝난 뒤
cd "$(dirname "$0")/.."
export HF_HOME=${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') $*"; }
until grep -q "체인 끝" logs/chain_kbstar.log; do sleep 20; done
sleep 10
say "원문 전체 실행 시작"
${PY:-/workspace/.venv/bin/python} compare_terms.py --terms terms_kbstar_full.txt --prompt prompt_target_full.txt --out results/kbstar_full_01 \
  --models gemma exaone qwen --max-input-tokens 8192 --max-new-tokens 6144
say "원문 전체 체인 끝 (종료코드 $?)"
