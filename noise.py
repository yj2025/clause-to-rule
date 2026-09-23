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
# 2026-09-23 · **v41 · v43 · v44 · v45 — 프로세스 넷.** 처방이 같고(지문 1종)
# 각각 1회차씩 **따로 띄운 프로세스**다. 재현은 `python floors.py v41 v43 v44 v45`.
#
# **두 번째로 다시 쟀다.** 앞의 값(v37+v38)은 3회차 하나에 1회차 하나를 더한
# 것이라 프로세스가 둘뿐이었고, **⑥ 을 ±4.1p 로 세 배 이상 과소평가했다.**
# 그 값으로 v39 를 「⑥ 이 처음 판정선을 넘었다」고 읽었고 **그 판정을 취소했다.**
#
# 조문 하나가 뒤집히면 46분의 1 = 2.2p 다. **σ 가 0 이어도 그보다 가늘게 판정하지
# 않는다** — 네 번 안 흔들렸다는 것이 흔들릴 수 없다는 뜻은 아니다. 아래 값은
# 전부 `max(2σ, 단위 하나)` 이고, 별표가 붙은 축은 해상도 쪽이 이겼다는 뜻이다.
FLOORS = {"①": 2.2, "②": 4.7, "③": 2.2, "④": 2.2, "⑤": 2.2,
          "⑥": 6.7, "⑦": 2.2, "⑫": 7.8, "⑬": 3.6, "⑭": 1.8}

# ⑥ 은 정답의 모양에 따라 판정선이 세 배 넘게 다르다. **갈래별로 봐야 한다.**
# A기권(9)·M(4)은 조문 수가 적어 해상도 자체가 ±11.1p · ±25.0p 다 —
# **M 갈래는 1회차로는 어떤 처방도 못 읽는다.** 읽으려면 조문을 늘려야 한다.
GROUP_FLOORS = {"A빈": 8.3, "A기권": 11.1, "M": 25.0, "B": 13.6}

# 처방과 무관하게 프로세스마다 뒤집히는 조문. **여덟이다** (넷이 아니었다).
# 앞 표본(v38 3회차)은 한 프로세스라 넷밖에 못 봤다. `SUSPECT_COINS` 로 적어
# 뒀던 넷 중 셋이 확인됐고(R07 · R17 · KBYY-S5-R02), `KBYY-S2-R20` 은 아니었다.
# 새로 둘이 나왔다 — `KBYY-S2-R14` (A빈인데 뒤집힌다) · `KBYY-S3-R01`.
COINS = ("KBONE-S2-R05", "KBONE-S2-R07", "KBONE-S2-R14", "KBONE-S2-R17",
         "KBONE-S2-R20", "KBYY-S2-R14", "KBYY-S3-R01", "KBYY-S5-R02")

# **동전을 뺀 값에는 판정선을 붙이지 않는다 — 순환이다.** 동전은 「이 표본에서
# 갈린 조문」으로 정의했으니, 그것을 빼고 같은 표본으로 흔들림을 재면 0 이 나올
# 수밖에 없다. 옛 `FLOOR_NO_COIN = 2.4` 와 `GROUP_FLOORS_NO_COIN` 이 그렇게 나온
# 값이라 **지웠다.** 대신 반반으로 갈라 확인했다 — 앞 두 프로세스로 동전을 뽑고
# 뒤 두 프로세스에서 재니 폭이 2.4p 였다. 남은 38조문은 하나가 2.63p 이므로
# **그보다 가늘게는 못 읽는다** — 올려서 2.7p 로 둔다. 동전을 뺀 ⑥ 은 여전히
# **읽는 보조선이지 지표가 아니고**, 겨냥한 조문이 동전이면 그 값도 못 쓴다.
FLOOR_NO_COIN = 2.7


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
