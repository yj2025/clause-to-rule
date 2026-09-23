"""노이즈 바닥 — 같은 조건에서 얼마나 흔들리나.

**바닥을 모르면 개선을 주장할 수 없다.** 유실된 기록 §9 6번이 그 이야기다.
거기서는 재시도에만 영향을 주는 변경이 1차 지표의 공짜 통제군이 된다는 방법을
썼다. 여기서는 두 가지로 잰다.

1. **회차 간** — 한 라운드 안에서 같은 조문을 여러 번 돌린 결과의 흔들림.
   3회차 라운드에서만 된다.
2. **라운드 간** — 지문이 같은 두 라운드의 1차 지표 차이.
   v4 와 v6 이 그런 짝이었다 (v6 은 어느 시도를 낼지만 바꿨다).

    python noise.py results/results_v7.json
    python noise.py results/results_v6.json --against results/results_v4.json
"""

import argparse
import collections
import itertools
import json
import statistics
import sys
from pathlib import Path

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
SYM = dict(zip(KEYS, "①②③④⑤"))

# ── 판정선 — 한 곳에 둔다 ────────────────────────────────────────────────
#
# 2026-09-23 · v37 1회차 + v38 3회차 (같은 구성 네 회차 · 지문 해시 7종 일치).
# 값의 근거와 회차별 수치는 `NOISE.md` 에 있다. **여기가 코드의 유일한 출처다** —
# 전에는 `report.py` 가 「노이즈 바닥은 ±2~4p」 한 줄로 뭉뚱그렸고, 축마다 두 배
# 넘게 다른 것을 못 봤다. ⑤ 는 ±7.4p 인데 4.0p 로 판정하고 있었다.
#
# **3회차 하나로 내지 말 것.** 한 프로세스에서 연달아 돌린 회차는 서로 닮는다 —
# v38 세 회차만으로는 ±1.3p 인데 다른 프로세스의 v37 을 더하면 ±4.1p 다.
FLOORS = {"①": 0.0, "②": 6.1, "③": 4.3, "④": 0.0, "⑤": 7.4,
          "⑥": 4.1, "⑦": 0.0, "⑫": 5.4, "⑬": 9.2, "⑭": 2.7}

# ⑥ 은 정답의 모양에 따라 판정선이 열 배 넘게 다르다. **갈래별로 봐야 한다.**
GROUP_FLOORS = {"A빈": 0.0, "A기권": 11.1, "M": 14.4, "B": 8.1}

# 처방과 무관하게 회차마다 뒤집히는 조문. 넷이 같이 뒤집히면 ⑥ 이 6.5p 움직인다 —
# 어떤 처방보다 크다. 라운드를 읽을 때 따로 표시한다 (2026-09-23 · v38 세 회차).
COINS = ("KBONE-S2-R05", "KBONE-S2-R14", "KBONE-S2-R20", "KBYY-S2-R04")

# 그 넷을 빼고 보면 판정선이 크게 줄어든다. **A기권과 M 의 흔들림은 동전 하나씩이
# 전부였다** — 빼면 네 회차가 소수점까지 같다. 처방이 겨냥한 자리가 동전이 아니면
# 이 값으로 읽는 것이 훨씬 예민하다 (2026-09-23 · 같은 네 회차).
#
# **다만 이것은 읽는 보조선이지 지표가 아니다.** 조문을 빼고 잰 값을 「⑥ 이
# 61.3% 다」로 인용하면 안 된다. 겨냥한 조문이 동전이면 이 값도 못 쓴다.
# 2026-09-23 · v42 판정. **이 목록은 모자란다.** 일곱 회차(v38 3회 + v39~v42)로
# 보면 뒤집히는 조문이 **여덟**이다. 아래 넷은 3회차 하나로 잰 값이라 놓쳤다.
#
#   KBONE-S2-R07 · KBONE-S2-R17 · KBYY-S2-R20 · KBYY-S5-R02
#
# **다만 그 넷을 바로 COINS 에 넣지 않는다.** v39~v42 는 라운드마다 지문이 달라
# 처방 효과와 흔들림이 섞여 있다 — `KBONE-S2-R17` 은 v39 가 연 조문이고 세 라운드를
# 버텼다. 흔들림인지 처방 효과가 무너진 것인지 **지금 표본으로는 못 가른다.**
#
# 제대로 재려면 **지금 코드로 3회차를, 프로세스를 나눠** 돌려야 한다 (`NOISE.md`).
SUSPECT_COINS = ("KBONE-S2-R07", "KBONE-S2-R17", "KBYY-S2-R20", "KBYY-S5-R02")

FLOOR_NO_COIN = 2.4
GROUP_FLOORS_NO_COIN = {"A빈": 0.0, "A기권": 0.0, "M": 0.0, "B": 5.3}


def _rate(recs, phase, key):
    return sum(bool(x[phase][key]) for x in recs) / len(recs) * 100 if recs else 0.0


def within_round(recs, phase="final"):
    """회차별로 지표를 따로 내고 그 폭을 본다."""
    runs = sorted({x["run"] for x in recs})
    if len(runs) < 2:
        print("회차가 하나뿐이라 회차 간 바닥은 못 잰다.\n")
        return
    by = {r: [x for x in recs if x["run"] == r] for r in runs}

    print(f"회차 간 흔들림 ({phase}, 회차 {len(runs)}개 × 조문 "
          f"{len({x['clause_id'] for x in recs})}개)\n")
    head = "".join(f"{'run' + str(r):>9}" for r in runs)
    print(f"{'지표':<18}{head}{'폭':>8}{'표준편차':>10}")
    print("-" * (18 + 9 * len(runs) + 18))
    widest = 0.0
    for k in KEYS:
        vals = [_rate(by[r], phase, k) for r in runs]
        span = max(vals) - min(vals)
        widest = max(widest, span)
        sd = statistics.pstdev(vals)
        print(f"{SYM[k]} {k:<15}" + "".join(f"{v:>8.1f}%" for v in vals)
              + f"{span:>7.1f}p{sd:>9.1f}p")

    def allp(x):
        return all(x[phase][k] for k in KEYS)

    vals = [sum(allp(x) for x in by[r]) for r in runs]
    n = len(by[runs[0]])
    print(f"{'전부 통과':<18}" + "".join(f"{v:>8}건" for v in vals)
          + f"{(max(vals) - min(vals)) / n * 100:>7.1f}p")
    sds = [statistics.pstdev([_rate(by[r], phase, k) for r in runs]) for k in KEYS]
    sd = statistics.mean(sds)
    se = sd / len(runs) ** 0.5
    print(f"\n폭(최대−최소) {widest:.1f}p — **판정선으로 쓰지 말 것.**")
    print(f"폭은 표본이 적을수록 우연히 커진다. 회차 수가 다른 라운드끼리 비교하면 틀린다.")
    print(f"\n관문별 표준편차 평균 {sd:.2f}p")
    print(f"  1회차 값의 판정선 (2σ)        ±{2 * sd:.1f}p")
    print(f"  {len(runs)}회 평균의 판정선 (2 표준오차) ±{2 * se:.1f}p")

    # 판정이 회차별로 갈린 조문
    by_clause = collections.defaultdict(list)
    for x in recs:
        by_clause[x["clause_id"]].append(x)
    flip = [c for c, rs in by_clause.items()
            if len({tuple(x[phase][k] for k in KEYS) for x in rs}) > 1]
    same_text = [c for c, rs in by_clause.items()
                 if len({(x.get("raw_first") or "") for x in rs}) == 1]
    print(f"\n출력이 회차 내내 글자까지 같은 조문 {len(same_text)}/{len(by_clause)}")
    print(f"관문 판정이 회차별로 갈린 조문 {len(flip)}/{len(by_clause)}")
    if flip:
        print("  " + ", ".join(sorted(flip)[:10]))


def between_rounds(a, b, phase="first"):
    """지문이 같은 두 라운드의 차이. 1차 지표로 본다."""
    ka = {(x["clause_id"], x["run"]) for x in a}
    kb = {(x["clause_id"], x["run"]) for x in b}
    common = ka & kb
    A = [x for x in a if (x["clause_id"], x["run"]) in common]
    B = [x for x in b if (x["clause_id"], x["run"]) in common]
    print(f"\n라운드 간 흔들림 ({phase}, 공통 {len(common)}건)\n")
    print(f"{'지표':<18}{'A':>9}{'B':>9}{'차이':>8}")
    print("-" * 44)
    widest = 0.0
    for k in KEYS:
        ra, rb = _rate(A, phase, k), _rate(B, phase, k)
        widest = max(widest, abs(rb - ra))
        print(f"{SYM[k]} {k:<15}{ra:>8.1f}%{rb:>8.1f}%{rb - ra:>+7.1f}p")
    ta = {(x["clause_id"], x["run"]): (x.get("raw_first") or "") for x in A}
    tb = {(x["clause_id"], x["run"]): (x.get("raw_first") or "") for x in B}
    same = sum(1 for k in common if ta[k] == tb[k])
    print(f"\n**관문별 바닥 {widest:.1f}p**")
    print(f"1차 출력이 글자까지 같은 건 {same}/{len(common)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--against", help="지문이 같은 다른 라운드")
    ap.add_argument("--phase", default="final", choices=["first", "final"])
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    print(f"=== {Path(a.results).name} ===\n")
    within_round(recs, a.phase)
    if a.against:
        between_rounds(json.loads(Path(a.against).read_text("utf-8")), recs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
