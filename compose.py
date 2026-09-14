"""⑩ 합성 — 조문을 합쳐서 한 고객의 금리를 낸다.

**왜 이 축이 필요한가.**

⑥ 은 조문을 **하나씩 고립시켜** 채점한다. 그래서 가장 비싼 오류가 원리적으로 안 보인다.

`KBYY-S2-R06` 의 gold 노트는 이렇게 적어 두었다.

    RATE_OVERRIDE 0.1 을 적으면 min=max=0.1 로 특별금리 1.9 를 통째로 지운다.
    그래서 rule 0개가 정답이다.

v6 생성물은 정확히 그 `RATE_OVERRIDE 0.1` 이다. **그런데 ⑥ 은 100점을 준다.**
이 조문만 단독으로 돌리면 override 결과 0.1 이 기본금리 0.1 과 같아 차이가 안 난다.
gold 가 경고한 파괴는 `S2-R07` 의 특별금리와 **합성될 때만** 드러나는데,
⑥ 은 합성을 하지 않는다.

실제 서비스는 조문을 합쳐 한 고객의 금리를 낸다. 그렇게 재야 한다.

**기존 축을 건드리지 않는다.** ⑥ 은 그대로 두고 따로 센다.

## 이 비율이 무엇을 재고 있나 — 어긋남을 열어 봤다 (2026-09-14)

여섯 라운드에서 어긋난 프로필을 종류별로 갈라 봤다.

| 라운드 | 어긋남 | 자격 판정 | 금리 |
|---|---:|---:|---:|
| v1 | 768 | 768 | 0 |
| v7 · v15 · v21 · v22 | 256 | 256 | 0 |
| **v13** | 896 | 768 | **128** |

**대부분이 자격 판정이다.** 그리고 언제나 한 방향이다 — 생성물이 gold 보다
자격을 더 박탈한다. 금리가 어긋나는 것은 v13 에서만 나왔고
(gold 2.00 대 생성 0.10) 특별금리를 통째로 놓친 경우다.

### 자격 박탈의 한 갈래 — 조건 없는 `DISQUALIFY`

    {"rule_id": "R-KBYY-S2-R17-01", "condition": {},
     "effect": {"type": "DISQUALIFY"}}    ← 모든 고객이 탈락한다

양도·담보제공 조문("양도 및 상속에 의한 명의변경 불가능")에서 나온다.
금지라는 효과는 분명한데 '특정 거래만 금지' 를 담을 effect 가 없어서
`DISQUALIFY` 로 밀고, 조건을 못 붙여 `{}` 로 둔다.

**이것이 전부는 아니다.** v13 은 조건 없는 `DISQUALIFY` 가 **0개**인데도
⑩ 이 12.5% 로 가장 낮다 — 조건이 붙었는데 너무 넓게 걸리는 rule 도 같은
피해를 준다. 그래서 `unconditional_disqualify` 는 **한 갈래를 세는 것**이지
⑩ 을 대신하지 않는다.

**⑭ 도 이것을 못 본다** — 빈 조건은 "항상 적용" 이라는 뜻을 분명히 밝힌 것이라
일부러 제외하기 때문이다. 그래서 따로 센다.

### 비율이 딱 떨어지는 값만 나오는 이유

25.0% · 56.2% · 75.0% · 12.5%. gold 가 자격을 남겨 두는 프로필 수로
정해지기 때문이다. 연속적인 품질 지표가 아니라 **불연속 계단**이고,
그 계단을 표준편차로 재서 "판정선 ±21.6p" 라고 적어 둔 것은 오해를 부른다.
**비율보다 어긋남의 종류와 조건 없는 `DISQUALIFY` 개수를 본다.**

## 이 축은 흔들림이 크다 — 1회차로 판정하면 안 된다

3회차 라운드 안에서 회차별로 재면 이렇다.

    v1   25.0 · 25.0 · 25.0    표준편차 0.0p
    v2   75.0 · 75.0 · 56.2    표준편차 8.8p
    v7   28.1 · 43.8 · 43.8    표준편차 7.4p

**1회차 판정선이 ±15~18p 다.** 형식 관문의 ±2.6p 보다 여섯 배 넓다.

구조적인 이유가 있다 — 조문 30개의 rule 을 **전부 합쳐 한 값**을 내므로,
조문 하나가 `RATE_OVERRIDE` 를 내면 결과가 통째로 바뀐다. 표본이 사실상 1 이다.

그래서 **1회차 라운드의 ⑩ 변화는 대부분 판정 불가다.**
3회차로 재거나, 회차별 값을 나란히 보아야 한다.

    python compose.py results/results_v6.json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import gold
from engine import evaluate_rules
from resolver import resolve

GOLD_DIR = Path("data/gold")


def _gold_rules(product=None):
    """gold 조문들의 rule 을 한 덩어리로. (rule 목록, 쓴 조문 목록)"""
    rules, used = [], []
    for p in sorted(GOLD_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        if product and not p.stem.startswith(product):
            continue
        d = json.loads(p.read_text("utf-8"))
        rs = d.get("rules") or []
        rules += rs
        used.append(p.stem)
    return rules, used


def _gen_rules(recs, clause_ids, run=0):
    """같은 조문들에 대한 생성물을 한 덩어리로."""
    by = {x["clause_id"]: x for x in recs if x["run"] == run}
    out, missing = [], []
    for cid in clause_ids:
        x = by.get(cid)
        rs = (x or {}).get("output") or {}
        rs = rs.get("rules") if isinstance(rs, dict) else None
        if not isinstance(rs, list):
            missing.append(cid)
            continue
        out += [r for r in rs if isinstance(r, dict)]
    return out, missing


def unconditional_disqualify(recs, run=0):
    """조건 없이 자격을 박탈하는 rule. **모든 고객이 탈락한다.**

    `LIMIT_AMOUNT` 같은 것은 조건 `{}` 가 맞다 — 저금통 한도 100만원은
    누구에게나 적용된다. `DISQUALIFY` 만 다르다. 예금 자격 자체를 없애는
    효과라 조건이 없으면 뜻이 뒤집힌다.

    ⑩ 의 어긋남이 사실상 전부 이것이었다. 비율보다 이 개수가 훨씬 안정적이다.
    """
    out = []
    for x in recs:
        if x["run"] != run:
            continue
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict) or r.get("status") != "OK":
                continue
            if (r.get("effect") or {}).get("type") != "DISQUALIFY":
                continue
            if not (r.get("condition") or {}) and not (r.get("guard") or {}):
                out.append((x["clause_id"], r.get("rule_id"),
                            (r.get("source") or {}).get("quote", "")[:50]))
    return out


def compare(recs, run=0, product="KBYY"):
    prod = json.loads((GOLD_DIR / "_product.json").read_text("utf-8"))
    agg, base = prod["aggregation"], prod["base_rate"]
    P = gold.profiles()

    g, used = _gold_rules(product)
    gen, missing = _gen_rules(recs, used, run)

    match = 0
    diffs = collections.Counter()
    worst = []
    for name, ctx in P:
        a = resolve(evaluate_rules(g, ctx), agg, base_rate=base)
        b = resolve(evaluate_rules(gen, ctx), agg, base_rate=base)
        ka = (a.final_rate_min, a.final_rate_max, a.disqualified)
        kb = (b.final_rate_min, b.final_rate_max, b.disqualified)
        if ka == kb:
            match += 1
        else:
            diffs[(ka, kb)] += 1
            if len(worst) < 5:
                worst.append((name, ka, kb))
    return {"rate": match / len(P) * 100, "match": match, "total": len(P),
            "gold_rules": len(g), "gen_rules": len(gen), "clauses": len(used),
            "missing": missing, "diffs": diffs, "worst": worst}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--run", type=int, default=0)
    ap.add_argument("--product", default="KBYY")
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    r = compare(recs, a.run, a.product)

    print(f"=== {Path(a.results).name} · {a.product} 조문 {r['clauses']}개 합성 ===\n")
    print(f"gold rule {r['gold_rules']}개 · 생성 rule {r['gen_rules']}개"
          + (f" · 무출력 조문 {len(r['missing'])}개" if r["missing"] else ""))
    print(f"\n⑩ 합성 일치 — 프로필 {r['total']}개 중 최종금리가 같은 것 "
          f"{r['match']}개 = **{r['rate']:.1f}%**\n")
    if r["diffs"]:
        print(f"{'gold 금리':<22}{'생성 금리':<22}{'프로필 수':>8}")
        print("-" * 54)
        for (ka, kb), n in r["diffs"].most_common(8):
            fa = f"{ka[0]}~{ka[1]}" + (" 실격" if ka[2] else "")
            fb = f"{kb[0]}~{kb[1]}" + (" 실격" if kb[2] else "")
            print(f"{fa:<22}{fb:<22}{n:>8}")
    print("\n⑥ 은 조문을 하나씩 고립시켜 잰다. 합성할 때만 드러나는 파괴가 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
