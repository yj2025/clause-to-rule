#!/usr/bin/env bash
# 라운드 하나를 돌린다. 라운드 간 조건이 우연히 달라지지 않게 한 곳에 묶어 둔다.
#
#   ./run_round.sh v2
#
# 바뀌어도 되는 것은 지문(prompt.py)뿐이다. 코퍼스·회차·온도·토큰 예산을
# 여기서 고정한다. 이 값을 바꾸면 그 라운드는 앞 라운드와 비교할 수 없다.
set -euo pipefail

VER="${1:?사용법: ./run_round.sh <버전>  (예: v2)}"
ROOT="/workspace/personal_workplace_CHO/model/M2-2"
PY="/workspace/.venv/bin/python"
export HF_HOME="/workspace/personal_workplace_CHO/.hf_cache"

CORPUS="data/corpus.json"
RUNS=3
TEMP=0.1
MAXTOK=3072

cd "$ROOT"
mkdir -p results logs
OUT="results/results_${VER}.json"
LOG="logs/${VER}_run.log"

if [ -e "$OUT" ]; then
  echo "이미 있다: $OUT — 덮어쓰지 않는다" >&2
  exit 1
fi

{
  echo "라운드 $VER"
  echo "  코퍼스   $CORPUS ($($PY -c "import json;print(len(json.load(open('$CORPUS'))))") 조문)"
  echo "  회차     $RUNS · 온도 $TEMP · 토큰 예산 $MAXTOK"
  echo "  git      $(git rev-parse --short HEAD)"
  echo "  시작     $(date '+%F %T')"
  echo
} | tee "$LOG"

nohup "$PY" run_local_v2.py --out "$OUT" --clauses "$CORPUS" \
  --runs "$RUNS" --temperature "$TEMP" --max-new-tokens "$MAXTOK" >> "$LOG" 2>&1 &

echo "시작 pid $! · 로그 $LOG"
