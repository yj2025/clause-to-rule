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
# 2026-09-24 · **v46 · v47 · v48 · v49 — 프로세스 넷.** 지금 코드(v46 처방
# 포함)로 1회차씩 따로 띄웠다. 재현은 `python floors.py v46 v47 v48 v49`.
#
# **처방이 흔들림을 줄였다.** v46 이 「목록에 없는 이름이 필요하면 기권한다」를
# 이으면서 출력이 굳었다 — ⑥ 판정선이 ±6.7p → **±3.9p**, B 갈래가 ±13.6p →
# **±5.8p** 다. 앞으로 라운드를 읽기가 훨씬 쉽다. 반대로 ② 는 ±4.7p → ±9.0p 로
# 넓어졌다 (v47 하나가 73.9 로 튀었다).
#
# 조문 하나가 뒤집히면 46분의 1 = 2.2p 다. **σ 가 0 이어도 그보다 가늘게 판정하지
# 않는다.** 아래 값은 전부 `max(2σ, 단위 하나)` 다.
#
# 앞 구성(v41·v43·v44·v45 · 처방 전)의 값은 `NOISE.md` 에 남겼다.
FLOORS = {"①": 2.2, "②": 9.0, "③": 3.6, "④": 3.8, "⑤": 4.7,
          "⑥": 3.9, "⑦": 2.2, "⑫": 3.6, "⑬": 3.9, "⑭": 2.0,
          # ⑮ 는 v46~v49 에서 4.2 · 3.8 · 3.9 · 4.2 로 σ 0.17p 다.
          # 분모가 비교 개수(50 안팎)라 해상도 하한 2.0p 를 쓴다.
          "⑮": 2.0,
          # ⑯ 은 2026-09-25 에 붙였다. v46~v49 에서 11.8 · 11.3 · 5.9 · 11.3
          # (σ 2.43p). **조문이 둘뿐이라 비율로 읽지 말 것** — rule 3개가 통째로
          # 나타났다 사라진다. 조문 단위로 읽는다.
          "⑯": 4.9}

# ⑥ 은 정답의 모양에 따라 판정선이 다르다. **갈래별로 봐야 한다.**
# A기권(9)·M(4)은 조문이 적어 해상도 자체가 ±11.1p · ±25.0p 다 —
# **M 갈래는 1회차로는 어떤 처방도 못 읽는다.**
GROUP_FLOORS = {"A빈": 8.3, "A기권": 11.1, "M": 25.0, "B": 5.8}

# 처방과 무관하게 프로세스마다 뒤집히는 조문. **일곱이다** (앞 구성에선 여덟).
# 목록이 절반쯤 바뀌었다 — 처방이 어떤 자리를 굳히고 어떤 자리를 흔든다.
# 앞 구성에서 동전이던 `KBONE-S2-R07` · `KBONE-S2-R14` · `KBONE-S2-R17` ·
# `KBONE-S2-R20` · `KBYY-S3-R01` 이 굳었고, `KBONE-S2-R15` · `KBYY-S2-R04` ·
# `KBYY-S2-R12` 가 새로 흔들린다 (셋 다 v46 이 연 자리다 — **열린 자리가 곧장
# 굳는 것은 아니다**).
COINS = ("KBONE-S2-R05", "KBONE-S2-R15", "KBYY-S2-R04", "KBYY-S2-R12",
         "KBYY-S2-R14", "KBYY-S2-R20", "KBYY-S5-R02")

# **동전을 뺀 값에는 판정선을 붙이지 않는다 — 순환이다.** 동전은 「이 표본에서
# 갈린 조문」으로 정의했으니, 그것을 빼고 같은 표본으로 흔들림을 재면 0 이 나올
# 수밖에 없다. 반반으로 갈라 확인만 한다 (앞 둘로 뽑고 뒤 둘에서 재니 폭 4.9p).
# 남은 39조문은 하나가 2.56p 이므로 **2.6p 보다 가늘게는 못 읽는다.**
FLOOR_NO_COIN = 2.6


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
