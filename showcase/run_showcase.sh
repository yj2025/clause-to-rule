#!/usr/bin/env bash
# 라운드 하나를 돌린다. 라운드 간 조건이 우연히 달라지지 않게 한 곳에 묶어 둔다.
#
#   ./run_round.sh v39            탐색 라운드 (1회차, 약 40~60분)
#   ./run_round.sh v39 3          확인 라운드 (3회차, 약 2~3시간)
#
#   setsid nohup ./run_round.sh v39 >/dev/null 2>&1 &     ← 길게 도는 것은 이렇게
#
# 조문 셋 중 둘은 3회가 글자까지 같다 (v1 실측 65%). 탐색은 1회차로 충분하고,
# 처방이 먹은 것으로 보일 때만 3회차로 확인한다.
#
# **판정선을 3회차 하나로 내지 마라.** 한 프로세스에서 연달아 돌린 회차는 서로
# 닮는다 — v38 세 회차만으로는 ⑥ 이 ±1.3p 인데, 다른 프로세스의 v37 을 더하면
# ±4.1p 다 (`NOISE.md` 2026-09-23). 잡음을 재려면 **프로세스를 나눠야** 한다.
#
# 바뀌어도 되는 것은 지문(prompt.py)뿐이다. 코퍼스·회차·온도·토큰 예산을
# 여기서 고정한다. 이 값을 바꾸면 그 라운드는 앞 라운드와 비교할 수 없다.
#
# ── 끊겨도 잃지 않는다 ─────────────────────────────────────────────────
# 라운드는 한 시간 안팎이 들고 **세 번 끊겼다** — v23(8/46) · v27(11/46) 은 남의
# 작업이 들어와 OOM, v33(12/46) 은 세션이 초기화됐다. 그래서 이렇게 짰다.
#
#   * 조문마다 결과를 디스크에 쓴다 (`run_local_v2.py` 가 한다)
#   * **시작할 때 남은 부분결과부터 거둔다** — 이게 없어서 v33 에서 잃을 뻔했다
#   * 끊기면 **안 된 조문만** 다시 돈다. 모델은 시도당 한 번만 올린다
#   * GPU 가 모자라면 기다린다 (전에는 그냥 끝냈다)
#   * `flock` 으로 두 개가 겹쳐 도는 것을 막는다 — 겹치면 서로를 OOM 으로 민다
set -uo pipefail

VER="${1:?사용법: ./run_round.sh <버전> [회차]  (예: v39 또는 v39 3)}"
RUNS="${2:-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # M2-2/ — 이 스크립트는 showcase/ 안에 있다
PY="${PY:-/workspace/.venv/bin/python}"
export HF_HOME="${HF_HOME:-/workspace/personal_workplace_CHO/.hf_cache}"
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TQDM_DISABLE=1
# 긴 조문의 KV 캐시가 할당자를 조각내 「여유는 있는데 OOM」 이 난다. 생성 결과는 안 바뀐다.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

CORPUS="${CORPUS:-showcase/clauses.json}"
TEMP=0.1
MAXTOK=3072

NEED_MIB="${NEED_MIB:-24000}"   # 라운드는 16.4GB 를 예약하고 긴 조문에서 20GB 안팎까지 간다
WAIT="${WAIT:-1}"               # 0 이면 GPU 가 모자랄 때 기다리지 않고 끝낸다
POLL="${POLL:-60}"
MAX_WAIT_MIN="${MAX_WAIT_MIN:-720}"
MAX_TRIES="${MAX_TRIES:-6}"

cd "$ROOT"
mkdir -p results logs
OUT="showcase/results_${VER}.json"
LOG="showcase/${VER}_run.log"

exec 9>"showcase/.${VER}.lock"
if ! flock -n 9; then
  echo "이미 $VER 가 돌고 있다 — 겹쳐 띄우지 않는다" >&2
  exit 3
fi

say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

missing() {
  "$PY" - "$CORPUS" "$OUT" "$RUNS" <<'EOF'
import collections, json, sys
corpus = [c["id"] for c in json.load(open(sys.argv[1], encoding="utf-8"))]
try:
    recs = json.load(open(sys.argv[2], encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    recs = []
cnt = collections.Counter(r["clause_id"] for r in recs)
need = int(sys.argv[3])
print(" ".join(i for i in corpus if cnt.get(i, 0) < need))
EOF
}

merge() {          # merge <부분결과>
  "$PY" - "$CORPUS" "$OUT" "$1" <<'EOF'
import json, os, sys
corpus_path, out_path, part_path = sys.argv[1:4]
order = {c["id"]: i for i, c in enumerate(json.load(open(corpus_path, encoding="utf-8")))}

def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []

recs = load(out_path)
seen = {(r["clause_id"], r["run"]) for r in recs}
added = 0
for r in load(part_path):
    if (r["clause_id"], r["run"]) not in seen:     # 이미 있는 것은 안 덮는다
        seen.add((r["clause_id"], r["run"]))
        recs.append(r)
        added += 1
recs.sort(key=lambda r: (order.get(r["clause_id"], 1 << 30), r["run"]))

fps = {json.dumps(r["prompt"], sort_keys=True, ensure_ascii=False) for r in recs}
if len(fps) > 1:
    print("!! 지문이 섞였다 — 같은 라운드가 아니다. 판정 전에 봐야 한다", file=sys.stderr)

tmp = out_path + ".tmp"                            # 덮어쓰다 죽는 것을 막는다
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(recs, f, ensure_ascii=False, indent=1)
os.replace(tmp, out_path)
print(f"합쳤다 +{added}건 · 누적 {len(recs)}건 · 지문 {len(fps)}종")
EOF
}

wait_gpu() {
  local waited=0 total used free
  while :; do
    total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
    free=$(( total - used ))
    if [ "$free" -ge "$NEED_MIB" ]; then
      say "GPU 여유 ${free}MiB ≥ ${NEED_MIB}MiB — 띄운다 (기다린 시간 ${waited}분)"
      return 0
    fi
    if [ "$WAIT" = "0" ]; then
      say "GPU 여유 ${free}MiB < ${NEED_MIB}MiB — 안 띄운다 (WAIT=0)"
      nvidia-smi --query-compute-apps=pid,used_memory --format=csv >&2
      return 1
    fi
    [ $(( waited % 10 )) -eq 0 ] && say "GPU 여유 ${free}MiB < ${NEED_MIB}MiB — 기다린다 (${waited}분째)"
    [ "$waited" -ge "$MAX_WAIT_MIN" ] && { say "${MAX_WAIT_MIN}분을 기다렸다. 멈춘다."; return 1; }
    sleep "$POLL"
    waited=$(( waited + POLL / 60 ))
  done
}

say "── 라운드 $VER · 회차 $RUNS · 온도 $TEMP · 토큰 $MAXTOK · git $(git rev-parse --short HEAD 2>/dev/null || echo '?')"

# 앞서 죽은 회차가 남긴 부분결과부터 거둔다. 생성은 비싸다 — 한 조문도 안 버린다.
for leftover in showcase/.${VER}_part_*.json; do
  [ -e "$leftover" ] || continue
  say "남은 부분결과를 거둔다: $(basename "$leftover")"
  merge "$leftover" 2>&1 | tee -a "$LOG"
done

for try in $(seq 1 "$MAX_TRIES"); do
  REST=$(missing)
  if [ -z "$REST" ]; then
    say "== $VER 완주 · $("$PY" -c "import json;print(len(json.load(open('$OUT'))))")건 =="
    exit 0
  fi
  N=$(echo "$REST" | wc -w)
  say "시도 $try — 남은 ${N}조문을 한 프로세스로 돈다"
  wait_gpu || exit 2

  PART="showcase/.${VER}_part_${try}.json"
  "$PY" run_local_v2.py --out "$PART" --clauses "$CORPUS" \
      --runs "$RUNS" --temperature "$TEMP" --max-new-tokens "$MAXTOK" \
      --only $REST >> "$LOG" 2>&1
  say "시도 $try 끝 (종료코드 $?)"
  merge "$PART" 2>&1 | tee -a "$LOG"
done

LEFT=$(missing)
say "== $VER 미완 · 남은 $(echo "$LEFT" | wc -w)조문: $LEFT =="
exit 1
