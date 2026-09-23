"""⑮ 타입이 안 맞는 비교 — **이름은 목록에 있는데 뜻이 다른 변수**를 쓴 것.

2026-09-23 에 찾았다. `KBYY-S2-R18` 이 압류 상태를 물으려고

    {"in": [{"var": "account.reserved_amount"}, ["SEIZED", "PRESERVED_SEIZED"]]}

를 냈다. `account.reserved_amount` 는 **저금통 적립액(원)** 이다. 이름은 카탈로그에
있으니 ③ 이 통과시키고, 실행해도 그냥 False 라 ⑤ 도 통과시킨다. ⑬(지어낸 이름)도
못 본다 — **지어낸 게 아니라 고른 것**이기 때문이다.

**「없는 이름을 지어내는 것」보다 이쪽이 나쁘다.** 지어낸 이름은 관문이 잡아서
재시도가 돌지만, 이건 아무도 안 잡는다. 관문 다섯이 전부 통과시키는 것을
확인했다 (`tests/test_mismatch.py`).

⑭(헛조건)는 「언제나 참」을 본다. 이것은 **언제나 거짓**인 쪽이다.

    python mismatch.py results/results_v45.json
    python mismatch.py --gold          # 정답에 먼저 돌린다

**새 지표는 반드시 정답에 먼저 돌린다.** ⑪ 이 정답에서 34건을 내 지표가 틀렸던
것을 찾은 적이 있다 (2026-09-21).
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import catalog

# 비교 연산자 — 양쪽의 타입이 맞아야 한다.
_CMP = ("==", "!=", "<", "<=", ">", ">=")

# 그 타입의 변수와 견줄 수 있는 리터럴
_OK = {
    "int": (int, float),
    "num": (int, float),
    "date": (str,),        # 날짜는 문자열로 적는다. 모양은 ⑤ 가 본다
    "enum": (str,),
    "bool": (bool,),
    "list": (str,),        # list 변수는 in 의 오른쪽에 온다 — 아래에서 따로 본다
}


def _vtype(node):
    if isinstance(node, dict) and isinstance(node.get("var"), str):
        return catalog.VARIABLES.get(node["var"], {}).get("type"), node["var"]
    return None, None


def _lit(node):
    """리터럴이면 (True, 값). 변수·집계·참조면 (False, None)."""
    if isinstance(node, (str, int, float, bool)):
        return True, node
    return False, None


def _check_cmp(op, args, out):
    if not isinstance(args, list) or len(args) != 2:
        return
    for i in (0, 1):
        t, name = _vtype(args[i])
        if t is None:
            continue
        is_lit, val = _lit(args[1 - i])
        if not is_lit:
            continue
        ok = _OK.get(t)
        if ok is None:
            continue
        # bool 은 int 의 부분집합이라 따로 본다
        if t == "bool":
            good = isinstance(val, bool)
        elif t in ("int", "num"):
            good = isinstance(val, (int, float)) and not isinstance(val, bool)
        else:
            good = isinstance(val, ok) and not isinstance(val, bool)
        if not good:
            out.append((name, t, op, val))
        elif t == "enum":
            vals = catalog.VARIABLES.get(name, {}).get("values")
            if vals and val not in vals:
                out.append((name, t, op, val))


def _check_in(args, out):
    """`in` — 왼쪽이 변수면 오른쪽 목록의 원소와 타입이 맞아야 한다."""
    if not isinstance(args, list) or len(args) != 2:
        return
    t, name = _vtype(args[0])
    if t is None or not isinstance(args[1], list):
        return
    for val in args[1]:
        is_lit, v = _lit(val)
        if not is_lit:
            continue
        if t in ("int", "num"):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                out.append((name, t, "in", v))
        elif t == "bool":
            if not isinstance(v, bool):
                out.append((name, t, "in", v))
        elif t in ("enum", "date"):
            if not isinstance(v, str):
                out.append((name, t, "in", v))
            else:
                vals = catalog.VARIABLES.get(name, {}).get("values")
                if t == "enum" and vals and v not in vals:
                    out.append((name, t, "in", v))


def find(node, out=None):
    """조건식 하나에서 타입이 안 맞는 비교를 전부 찾는다."""
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _CMP:
                _check_cmp(k, v, out)
            elif k == "in":
                _check_in(v, out)
            find(v, out)
    elif isinstance(node, list):
        for v in node:
            find(v, out)
    return out


def audit(recs, run=0):
    """레코드 묶음에서 센다. 분모는 **비교** 개수다."""
    bad = collections.Counter()
    by_clause = collections.Counter()
    n_cmp = n_bad = 0
    for x in recs:
        if run is not None and x.get("run") != run:
            continue
        for rule in ((x.get("output") or {}).get("rules") or []):
            if not isinstance(rule, dict):
                continue
            for key in ("condition", "guard", "let"):
                hits = find(rule.get(key))
                n_cmp += _count_cmp(rule.get(key))
                for name, t, op, val in hits:
                    n_bad += 1
                    bad[f"{name}({t}) {op} {val!r}"] += 1
                    by_clause[x["clause_id"]] += 1
    return {"checked": n_cmp, "bad": n_bad,
            "rate": n_bad / n_cmp * 100 if n_cmp else 0.0,
            "kinds": bad, "by_clause": by_clause}


def _count_cmp(node):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _CMP or k == "in":
                n += 1
            n += _count_cmp(v)
    elif isinstance(node, list):
        for v in node:
            n += _count_cmp(v)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?")
    ap.add_argument("--gold", action="store_true", help="정답에 돌린다")
    a = ap.parse_args(argv)

    if a.gold:
        recs = []
        for p in sorted(Path("data/gold").glob("*.json")):
            if p.name.startswith("_"):
                continue
            recs.append({"clause_id": p.stem, "run": 0,
                         "output": json.loads(p.read_text("utf-8"))})
        label = "정답 (data/gold)"
    else:
        recs = json.loads(Path(a.results).read_text("utf-8"))
        label = Path(a.results).name

    r = audit(recs)
    print(f"=== ⑮ 타입이 안 맞는 비교 — {label} ===\n")
    print(f"비교 {r['checked']}개 중 {r['bad']}개 = {r['rate']:.1f}%")
    if r["kinds"]:
        for k, n in r["kinds"].most_common(10):
            print(f"  {k}  ×{n}")
        print("\n조문별: " + " · ".join(f"{c} {n}" for c, n in r["by_clause"].most_common()))
    else:
        print("  없다.")
    if a.gold and r["bad"]:
        print("\n⚠ **정답에서 걸렸다. 지표가 틀렸다.** 고치기 전에는 쓰지 않는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
