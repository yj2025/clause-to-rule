"""⑥ 의 사각지대가 얼마나 큰가 — 프로필을 넓혀 다시 채점한다 (2026-09-30).

**공식 지표는 안 바꾼다.** `gold.profiles()` 1024개는 그대로 두고, 여기서만 프로필을 더해
«넓힌 ⑥» 을 따로 잰다. 두 값이 갈리는 조문이 ⑥ 이 과대평가한 자리다.

2026-09-29 에 발표용으로 고르다 찾은 사각지대 둘을 연다 (`METHOD.md` 6절).

  1. **「기본실적」 축이 세 이벤트를 한꺼번에 켠다** — 카드결제 · 자동이체 · 출금.
     「카드만」 「자동이체만」 「출금만」 인 고객을 더한다
  2. **신규 직후 고객이 없다** — 두 시기(NOW · OLD) 모두 기준일이 가입일에서 8개월 넘게
     떨어져 있다. 「신규 후 다음 다음 달 10일까지 무조건 면제」 같은 rule 이 어디서도 안 걸린다.
     가입일을 기준일 한 달 전으로 옮긴 고객을 더한다

    python blindspot.py v58 v59 v60 v61 v66 v67 v68 v69
"""

import copy
import json
import sys
from pathlib import Path

import gold
from scoring import score

ROOT = Path(__file__).resolve().parent
ONLY = ("CARD_USAGE", "AUTO_TRANSFER", "WITHDRAWAL")


def _month_back(date, k=1):
    y, m, d = (int(x) for x in date.split("-"))
    m -= k
    while m < 1:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}-{d:02d}"


def extra_profiles(base):
    """기존 프로필에서 사각지대를 여는 변형만 만든다. [(이름, ctx)]"""
    out = []
    for label, ctx in base:
        ev = ctx.get("events") or {}
        if all(k in ev for k in ONLY):              # 기본실적이 켜진 프로필
            for keep in ONLY:
                c = copy.deepcopy(ctx)
                for k in ONLY:
                    if k != keep:
                        c["events"].pop(k, None)
                out.append((f"{label} +{keep}만", c))
        c = copy.deepcopy(ctx)                      # 신규 직후
        c["contract"]["start_date"] = _month_back(c["contract"]["reference_date"])
        out.append((f"{label} +신규직후", c))
    return out


def main(argv):
    rounds = argv or ["v58", "v59", "v60", "v61", "v66", "v67", "v68", "v69"]
    prod, tpl, base = gold._product(), gold._templates(), gold.profiles()
    wide = base + extra_profiles(base)
    agg, br = prod["aggregation"], prod["base_rate"]
    recs = {v: {r["clause_id"]: r for r in
                json.loads((ROOT / "results" / f"results_{v}.json").read_text("utf-8"))}
            for v in rounds}
    print(f"프로필 {len(base)} → {len(wide)} (넓힌 것 {len(wide) - len(base)})\n")

    # 정답끼리 먼저 — 넓힌 프로필에서도 정답은 정답과 100 이어야 한다 (자기 검사)
    bad = [c for c, g in tpl.items()
           if score(g.get("rules") or [], g.get("rules") or [], agg, wide, br)["rate"] < 0.999]
    print(f"자기 검사 — 정답을 정답으로 채점해 100 이 아닌 조문: {bad or '없음'}\n")

    rows, tot = [], {v: [0.0, 0.0] for v in rounds}
    for cid, g in sorted(tpl.items()):
        gr = g.get("rules") or []
        a, b = [], []
        for v in rounds:
            r = recs[v].get(cid)
            if r is None:
                continue
            rules = (r.get("output") or {}).get("rules") or []
            s0 = score(gr, rules, agg, base, br)["rate"]
            s1 = score(gr, rules, agg, wide, br)["rate"]
            a.append(s0)
            b.append(s1)
            tot[v][0] += s0
            tot[v][1] += s1
        full0 = sum(x >= 0.999 for x in a)
        full1 = sum(x >= 0.999 for x in b)
        if full0 != full1 or abs(sum(a) - sum(b)) > 1e-9:
            rows.append((cid, full0, full1, sum(a) / len(a), sum(b) / len(b)))

    print(f"{'조문':<15}{'⑥100 (기존)':>12}{'⑥100 (넓힘)':>12}{'평균 (기존)':>12}{'평균 (넓힘)':>12}")
    print("-" * 63)
    for cid, f0, f1, m0, m1 in rows:
        print(f"{cid:<15}{f0:>9}/{len(rounds)}{f1:>9}/{len(rounds)}{m0 * 100:>11.1f}%{m1 * 100:>11.1f}%")
    n = len(tpl)
    print("-" * 63)
    print("라운드별 ⑥ (조문 평균)")
    for v in rounds:
        print(f"  {v}: {tot[v][0] / n * 100:5.1f}% → {tot[v][1] / n * 100:5.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
