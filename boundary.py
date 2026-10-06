"""⑥b 경계 — 정답의 숫자 문턱 바로 아래 · 정확히 · 바로 위에 고객을 세워 뜻을 다시 잰다 (2026-10-06).

    python boundary.py <결과들> [--gold data/gold | showcase/gold_draft]

**왜.** ⑥ 의 합성 프로필은 축마다 값이 둘이다(잔액 0 · 100만, 나이 17 · 19, 입금은 50만원 한 건). 그래서
«합산 50만원 이상»을 «입금이 있으면»으로 적어도, «30만원 이상»으로 적어도 ⑥ 은 같다(KB스타통장 시범 · 결정 문서 10-06).
Codex 제안(499,999 / 500,000)을 받아, **정답 rule 에 적힌 수**마다 그 아래 · 그 수 · 그 위 값을 넣은 고객을 만든다.

⑥ 은 건드리지 않는다 — 프로필 1,024 를 바꾸면 앞 판들의 ⑥ 을 다 다시 재야 하고 판정선도 다시 재야 한다. 별도 축이다.
문턱이 없는 조문(대부분)은 이 축에 안 들어간다. 조문 수를 같이 적는다.

만드는 법: 기존 프로필 1,024 각각에 대해, 문턱 하나의 변수만 N−δ · N · N+δ 로 바꾼다(δ = 1 원 · 1 살 · 1 개월 · 1 건).
  변수(`customer.age` · `contract.term_months` · `account.balance` …) → 그 값을 바꾼다
  `count_events` · `min_amount` · `sum_events` 의 이벤트 → 기준일 전월에 그만큼 이벤트를 놓는다
  `count_distinct_months` → 전월로 끝나는 연속한 달에 한 건씩
전월 창이 아닌 문턱(직전 3개월 등)도 전월은 그 안에 든다. 창 밖에 놓이는 문턱은 없다고 본다 — 모르면 쉬운 쪽으로 센다.
"""
import argparse
import copy
import datetime as _dt
import json
import sys
from pathlib import Path

import gold
from scoring import score

VARS = {"customer.age": ("customer", "age"), "contract.term_months": ("contract", "term_months"),
        "account.balance": ("account", "balance"), "account.reserved_amount": ("account", "reserved_amount"),
        "contract.amount": ("contract", "amount")}
_OPS = (">=", ">", "<=", "<", "==")


def thresholds(rules):
    """정답 rule 들의 (종류, 대상, N) 집합."""
    out = set()

    def walk(x, spec_event=None):
        if isinstance(x, dict):
            for op in _OPS:
                if op in x and isinstance(x[op], list) and len(x[op]) == 2:
                    a, b = x[op]
                    if isinstance(b, (int, float)) and not isinstance(b, bool) and isinstance(a, dict):
                        if "var" in a and a["var"] in VARS:
                            out.add(("var", a["var"], b))
                        for k in ("count_events", "sum_events", "count_distinct_months"):
                            if k in a and isinstance(a[k], dict) and a[k].get("event"):
                                out.add((k, a[k]["event"], b))
            where = x.get("where")
            if isinstance(where, dict) and isinstance(where.get("min_amount"), (int, float)) and x.get("event"):
                out.add(("min_amount", x["event"], where["min_amount"]))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for r in rules or []:
        if r.get("status") == "OK":
            walk(r.get("condition"))
            walk(r.get("guard"))
    return sorted(out, key=str)


def _prev_month(ref):
    d = _dt.date.fromisoformat(ref).replace(day=1) - _dt.timedelta(days=1)
    return d


def _months_back(ref, k):
    d = _prev_month(ref)
    for _ in range(k):
        d = d.replace(day=1) - _dt.timedelta(days=1)
    return d


def _with(ctx, kind, target, value):
    c = copy.deepcopy(ctx)
    ref = c["contract"]["reference_date"]
    prev = _prev_month(ref)
    if kind == "var":
        part, key = VARS[target]
        c[part][key] = value
        if target == "customer.age":
            c["customer"]["is_youth"] = value < 19
        return c
    n = max(0, int(value))
    if kind == "count_events":
        evs = [{"date": prev.replace(day=1 + i % 28).isoformat(), "amount": 100_000} for i in range(n)]
    elif kind == "count_distinct_months":
        evs = [{"date": _months_back(ref, i).replace(day=15).isoformat(), "amount": 100_000} for i in range(n)]
    elif kind == "min_amount":
        evs = [{"date": prev.replace(day=15).isoformat(), "amount": value}]
    else:                                  # sum_events — 두 건으로 나눠 합이 value
        evs = [{"date": prev.replace(day=10).isoformat(), "amount": value - value // 2},
               {"date": prev.replace(day=20).isoformat(), "amount": value // 2}]
    for e in evs:
        if target == "AUTO_TRANSFER":
            e["route"] = "GIRO"
        if target == "SALARY_TRANSFER":
            e["source"] = "SALARY_CONTRACT"
    c["events"] = {**c["events"], target: evs}
    return c


def profiles_for(rules, base=None):
    """문턱마다 N−δ · N · N+δ 를 기존 프로필 각각에 얹는다. 문턱이 없으면 빈 목록."""
    base = gold.profiles() if base is None else base
    out = []
    for kind, target, n in thresholds(rules):
        for v in (n - 1, n, n + 1):
            if v < 0:
                continue
            for name, ctx in base:
                out.append((f"{name} {kind}:{target}={v}", _with(ctx, kind, target, v)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--gold", default="data/gold")
    a = ap.parse_args(argv)
    sys.path.insert(0, "showcase")
    base_rate = (lambda cid: 0.0)
    if "gold_draft" in a.gold:
        from kb10six import BASE_RATE
        base_rate = (lambda cid: BASE_RATE[cid.split("-")[0]])
    golds = {p.stem: json.loads(p.read_text("utf-8")) for p in Path(a.gold).glob("K*.json")}
    golds = {k: g for k, g in golds.items() if thresholds(g.get("rules"))}
    base = gold.profiles()
    prof = {k: profiles_for(g["rules"], base) for k, g in golds.items()}
    runs = {}
    for r in a.results:
        recs = {x["clause_id"]: x for x in json.loads(Path(r).read_text("utf-8"))}
        row = {}
        for cid, g in golds.items():
            x = recs.get(cid)
            if x is None:
                continue
            got = (x.get("output") or {}).get("rules") if isinstance(x.get("output"), dict) else None
            row[cid] = score(g["rules"], got if isinstance(got, list) else [], "SUM", prof[cid],
                             base_rate(cid))["rate"] * 100
        runs[Path(r).stem.split("results_")[-1]] = row
    print(f"⑥b 경계 — 문턱이 있는 정답 {len(golds)}조문")
    print(f"{'':16}" + "".join(f"{k[-8:]:>10}" for k in runs))
    for cid in sorted(golds):
        print(f"{cid:16}" + "".join(f"{r.get(cid, float('nan')):10.1f}" for r in runs.values()))
    print(f"{'평균':16}" + "".join(f"{sum(r.values()) / max(1, len(r)):10.1f}" for r in runs.values()))


if __name__ == "__main__":
    main()
