#!/usr/bin/env bash
# 라운드 하나를 돌린다. 라운드 간 조건이 우연히 달라지지 않게 한 곳에 묶어 둔다.
#
#   ./run_round.sh v3          탐색 라운드 (1회차, 약 25분)
#   ./run_round.sh v3 3        확인 라운드 (3회차, 약 70~120분)
#
# 조문 셋 중 둘은 3회가 글자까지 같다 (v1 실측 65%). 탐색은 1회차로 충분하고,
# 처방이 먹은 것으로 보일 때만 3회차로 확인한다.
#
# 바뀌어도 되는 것은 지문(prompt.py)뿐이다. 코퍼스·회차·온도·토큰 예산을
# 여기서 고정한다. 이 값을 바꾸면 그 라운드는 앞 라운드와 비교할 수 없다.
set -euo pipefail

VER="${1:?사용법: ./run_round.sh <버전> [회차]  (예: v3 또는 v3 3)}"
RUNS="${2:-1}"
ROOT="/workspace/personal_workplace_CHO/model/M2-2"
PY="/workspace/.venv/bin/python"
export HF_HOME="/workspace/personal_workplace_CHO/.hf_cache"

CORPUS="data/corpus.json"
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

# GPU 여유를 먼저 본다. 라운드는 16.4GB 를 예약하고 긴 조문에서 20GB 안팎까지 간다.
# v23 과 v27 이 **도중에 들어온 남의 작업** 때문에 OOM 으로 끊겼다 (8/46 · 11/46).
# 시작할 때 여유가 없으면 아예 띄우지 않는다. 도중에 들어오는 것은 못 막지만,
# 처음부터 모자란 채로 한 시간을 버리는 것은 막는다.
NEED_MIB="${NEED_MIB:-24000}"
FREE=$(( $(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)        - $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) ))
if [ "$FREE" -lt "$NEED_MIB" ]; then
  echo "GPU 여유 ${FREE}MiB < ${NEED_MIB}MiB — 안 띄운다." >&2
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv >&2
  echo "비기를 기다리거나 NEED_MIB 를 낮춰 강행한다 (그러면 OOM 위험을 아는 채로 도는 것이다)." >&2
  exit 2
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
