"""⑯ 셈이 안 맞는 집계 비교 — **창보다 큰 개월수를 요구한다.**

2026-09-25 에 찾았다. `KBYY-S2-R19` 가 「1년 이상 무거래」를 이렇게 적는다.

    {">=": [{"count_distinct_months": {"event": "WITHDRAWAL",
                                       "within": <한 달짜리 창>}}, 12]}

**한 달짜리 창에서 서로 다른 달은 많아야 하나다.** 12 이상이 될 수 없으니
이 rule 은 어떤 고객에게도 안 걸린다. 그런데 관문 다섯이 전부 통과시키고
⑭(헛조건)도 못 본다 — 언제나 참이 아니라 **언제나 거짓**이기 때문이다.

v50 에서 이 조문의 연산자가 `>=` 에서 `<=` 로 뒤집혔다. 그러자 ⑭ 가 잡기
시작했다 — 죽은 조건이 헛조건으로 바뀐 것이다. **지표가 절반만 보고 있어서
「v50 이 부작용을 냈다」로 읽힐 뻔했다.**

### 왜 표본으로 안 재나

처음에는 「표본 문맥 400개에서 한 번도 참이 아니면 죽은 조건」으로 짰다.
**정답에서 3개가 걸려 버렸다** (`customer.age == 19` 처럼 표본이 그 값을 안
가진 경우). 표본이 정의역을 다 덮지 않으므로 그 방식은 **과다 검출**이다.
⑭ 는 「전부 참」을 요구해서 표본이 모자라면 적게 잡는 쪽으로 기우는데,
이쪽은 반대로 기운다.

그래서 **산술로 증명되는 것만 센다.** 창의 길이와 임계값을 직접 견준다.

    python dead.py results/results_v50.json
    python dead.py --gold          # 새 지표는 정답에 먼저 돌린다
"""

import argparse
import collections
import json
import sys
from pathlib import Path


def _window_months(within):
    """창이 몇 달짜리인가. 못 세면 None."""
    if not isinstance(within, dict):
        return None
    mr = within.get("month_range")
    if not isinstance(mr, dict):
        return None
    f, t = mr.get("from"), mr.get("to")
    if not (isinstance(f, dict) and isinstance(t, dict)):
        return None
    if f.get("anchor") != t.get("anchor"):
        return None
    try:
        a = int(f.get("offset_months", 0))
        b = int(t.get("offset_months", 0))
    except (TypeError, ValueError):
        return None
    return b - a + 1


_CNT = ("count_distinct_months",)


def check_rule(rule):
    """[(자리, 왜, 조건), ...] — 산술로 불가능하거나 언제나 참인 집계 비교."""
    out = []

    def walk(node, where):
        if isinstance(node, dict):
            for op, args in node.items():
                if op in (">=", ">", "<=", "<") and isinstance(args, list) \
                        and len(args) == 2:
                    left, right = args
                    if isinstance(left, dict) and isinstance(right, (int, float)):
                        for k in _CNT:
                            if k in left:
                                n = _window_months((left[k] or {}).get("within"))
                                if n is None:
                                    continue
                                if op in (">=", ">") and (
                                        right > n or (op == ">" and right >= n)):
                                    out.append((where,
                                                f"{n}달짜리 창에서 {op} {right} 는 "
                                                f"될 수 없다", node))
                                if op in ("<=", "<") and (
                                        right >= n or (op == "<" and right > n)):
                                    out.append((where,
                                                f"{n}달짜리 창에서 {op} {right} 는 "
                                                f"언제나 참이다", node))
                walk(args, where)
        elif isinstance(node, list):
            for v in node:
                walk(v, where)

    for part in ("condition", "guard"):
        walk(rule.get(part), part)
    return out


def audit(recs, run=0):
    checked = bad = 0
    by_clause = collections.Counter()
    examples = []
    for x in recs:
        if run is not None and x.get("run") != run:
            continue
        for rule in ((x.get("output") or {}).get("rules") or []):
            if not isinstance(rule, dict):
                continue
            if not rule.get("condition") and not rule.get("guard"):
                continue
            checked += 1
            for where, why, c in check_rule(rule):
                bad += 1
                by_clause[x["clause_id"]] += 1
                if len(examples) < 6:
                    examples.append((x["clause_id"], f"{where} — {why}", c))
    return {"checked": checked, "bad": bad,
            "rate": bad / checked * 100 if checked else 0.0,
            "by_clause": by_clause, "examples": examples}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--gold", action="store_true")
    a = ap.parse_args(argv)
    if a.gold:
        recs = [{"clause_id": p.stem, "run": 0,
                 "output": json.loads(p.read_text("utf-8"))}
                for p in sorted(Path("data/gold").glob("*.json"))
                if not p.name.startswith("_")]
        label = "정답 (data/gold)"
    else:
        recs = json.loads(Path(a.results).read_text("utf-8"))
        label = Path(a.results).name
    r = audit(recs)
    print(f"=== ⑯ 셈이 안 맞는 집계 비교 — {label} ===\n")
    print(f"조건이 있는 rule {r['checked']}개 중 {r['bad']}개 = {r['rate']:.1f}% "
          f"(창의 길이와 임계값이 안 맞는다)")
    for cid, where, c in r["examples"]:
        print(f"  {cid} · {where}: {json.dumps(c, ensure_ascii=False)[:110]}")
    if r["by_clause"]:
        print("\n조문별: " + " · ".join(f"{k} {v}" for k, v in r["by_clause"].most_common()))
    if a.gold and r["bad"]:
        print("\n⚠ **정답에서 걸렸다. 지표가 틀렸다.** 고치기 전에는 쓰지 않는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
