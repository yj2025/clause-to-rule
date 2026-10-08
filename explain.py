"""판정 결과를 다음 단계로 넘기는 JSON — 모르는 조건은 «조건부»로 (2026-10-08).

    python explain.py KBNR --start 2025-03-02 --maturity 2028-03-02 --monthly 200000
    python explain.py KBSSG --start 2026-01-05 --age 30 --results showcase/results_kb10v127a.json

**사용자 결정(10-08):** 서비스는 기본 정보만 받고 거래 내역은 모으지 않는다. 거래 조건
(급여이체 · 카드 사용 · 자동이체 · 연금 입금 …)을 «충족한다고 가정»하지 않는다 — 혜택이
부풀고(10-06 KB스타통장 시범: 틀린 넷이 전부 잘못 면제), 불리한 조건은 뜻이 뒤집힌다.
엔진이 낸 UNKNOWN 을 그대로 «조건부»로 넘긴다.

**이 단계의 범위는 조건식까지다(10-08 사용자).** 쉬운 말로 옮기는 것은 다음 단계 모델의 일이라
여기는 문장을 만들지 않는다 — 조건식(아는 갈래를 걷어 낸 것) · 효과 · 원문 인용 · 모자란 입력을 JSON 으로 낸다.
판정은 `engine.evaluate_rules`, 금리 구간은 `resolver.resolve` 를 그대로 쓴다.

입력하지 않은 필드는 `_provided` 에 넣지 않는다 — 그래야 «없다(NOT_MET)»가 아니라
«모른다(UNKNOWN)»가 된다(`engine._events`). 거래 내역은 늘 입력하지 않은 것이다.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "showcase"))
import catalog  # noqa: E402
import engine  # noqa: E402
import resolver  # noqa: E402
from tv import TV  # noqa: E402
from kb10six import BASE_RATE  # noqa: E402

GOLD = ROOT / "showcase" / "gold_draft"

# 사용자에게 유리한 효과(BENEFIT) · 불리한 효과(CAUTION). 어느 쪽도 아닌 것(REQUIRE · 상품 전환 …)은 OTHER.
FAVORABLE = {"RATE_ADD", "FEE_WAIVE", "FEE_WAIVE_NO_CARRYOVER", "SERVICE_PROVIDE", "TAX_EXEMPT_ELIGIBLE"}
UNFAVORABLE = {"DISQUALIFY", "RATE_SUBTRACT", "PENALTY_RATE", "RESTRICT", "STATE_CHANGE",
               "DORMANT_CONTRIBUTION"}
# RATE_OVERRIDE 는 양쪽이다 — 연금 실적별 우대 이율(KBGL)도, 중도해지 이율도 이 꼴이다. 기본이율과 견준다.


def user_ctx(today, start=None, maturity=None, monthly=None, holder=None, age=None,
             has_product=None, channel=None, base_rate=None):
    """기본 정보 → 엔진 ctx. 준 값만 «제공했다»로 선언한다. 거래 이벤트는 선언하지 않는다."""
    ctx = {"customer": {}, "account": {}, "contract": {"reference_date": today}, "events": {}}
    provided = ["contract.reference_date"]

    def put(path, value):
        if value is None:
            return
        grp, key = path.split(".")
        ctx[grp][key] = value
        provided.append(path)

    put("contract.start_date", start)
    put("contract.maturity_date", maturity)
    put("contract.monthly_amount", monthly)
    put("contract.channel", channel)
    put("contract.base_rate", base_rate)
    put("customer.holder_type", holder)
    put("customer.has_product", has_product)
    if age is not None:
        put("customer.age", age)
        put("customer.is_youth", age < 19)
    if start and maturity:
        s, m = dt.date.fromisoformat(start), dt.date.fromisoformat(maturity)
        put("contract.term_months", (m.year - s.year) * 12 + m.month - s.month)
    ctx["_provided"] = provided
    return ctx


def uses(rule):
    """rule 이 읽는 필드 · 이벤트 이름."""
    out = set()

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("var"), str):
                out.add(n["var"])
            if isinstance(n.get("event"), str):
                out.add(f"events.{n['event']}")
            if isinstance(n.get("anchor"), str) and "." in n["anchor"]:
                out.add(n["anchor"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk([rule.get("condition"), rule.get("guard"), rule.get("let")])
    return out


def _missing(rule, ctx):
    """판정에 모자란 입력 — (기본 정보로 물을 수 있는 필드, 모으지 않는 거래 이벤트)."""
    miss = sorted(u for u in uses(rule) if u not in set(ctx["_provided"]))
    return ([u for u in miss if not u.startswith("events.")],
            [u[len("events."):] for u in miss if u.startswith("events.")])


def prune(node, ctx, env):
    """UNKNOWN 인 조건에서 이미 아는 갈래를 걷어 낸다 — 다음 단계에 «남은 조건»만 넘기려고.

    「판정일이 11일 이후면 전월 실적, 10일 이전이면 전전월 실적」은 판정일을 알므로
    한 갈래만 남는다. and 에서 참인 것 · or 에서 거짓인 것을 뺀다. 판정 자체는 바꾸지 않는다.
    """
    try:
        v = engine.evaluate(node, ctx, env)
    except Exception:
        return node
    if v is not TV.U or not isinstance(node, dict) or len(node) != 1:
        return node
    (op, arg), = node.items()
    if op in ("and", "or") and isinstance(arg, list):
        drop = TV.T if op == "and" else TV.F
        keep = []
        for x in arg:
            try:
                if engine.evaluate(x, ctx, env) is drop:
                    continue
            except Exception:
                pass
            keep.append(prune(x, ctx, env))
        return keep[0] if len(keep) == 1 else {op: keep}
    if op == "not":
        return {"not": prune(arg[0] if isinstance(arg, list) else arg, ctx, env)}
    return node


def _side(eff, base_rate=0.0):
    t = (eff or {}).get("type")
    if t == "RATE_OVERRIDE" and isinstance(eff.get("value"), (int, float)):
        return "BENEFIT" if eff["value"] > base_rate else "CAUTION"
    return "BENEFIT" if t in FAVORABLE else "CAUTION" if t in UNFAVORABLE else "OTHER"


def explain(rules_by_clause, ctx, base_rate=0.0, aggregation="SUM"):
    """{조문: rules} + ctx → 넘길 묶음 (dict). 입력은 건드리지 않는다."""
    items, judgements, overrides = [], [], []
    for cid, rules in rules_by_clause.items():
        ok = [r for r in rules or [] if r.get("status") == "OK"]
        for r, j in zip(ok, engine.evaluate_rules(ok, ctx)):
            judgements.append(j)
            if j.status == "UNKNOWN" and (r.get("effect") or {}).get("type") == "RATE_OVERRIDE":
                overrides.append((r, j))
            env = dict(r.get("let") or {})
            status = {"MET": "APPLIES", "UNKNOWN": "CONDITIONAL", "ERROR": "ERROR"}.get(j.status, "NOT_APPLICABLE")
            it = {"clause_id": cid, "rule_id": r.get("rule_id"), "status": status, "side": _side(r.get("effect"), base_rate),
                  "condition": prune(r.get("condition"), ctx, env) if j.status == "UNKNOWN" else r.get("condition"),
                  "effect": r.get("effect"), "quote": (r.get("source") or {}).get("quote", "")}
            if env:
                it["let"] = env
            if status == "CONDITIONAL":
                it["missing_inputs"], it["missing_events"] = _missing(r, ctx)
            if j.error:
                it["error"] = j.error
            items.append(it)
    res = resolver.resolve(judgements, aggregation, base_rate)
    # resolver 는 UNKNOWN 인 RATE_OVERRIDE 를 구간에 넣지 않는다(⑥ 채점이 쓰는 동작이라 거기는 그대로 둔다).
    # 그대로 보이면 «연금 9건 이상이면 연 1.5%» 가 있는데도 «0.10% 확정»이 된다 — 여기서 구간을 넓힌다.
    # 해지에 걸린 이율(중도해지 · 만기후)은 넣지 않는다 — «지금 받는 금리»가 아니라 «해지하면»이다. CAUTION 으로만 남는다.
    lo, hi = res.min, res.max
    if not res.disqualified:
        maybe = [j.effect["value"] for r, j in overrides
                 if isinstance(j.effect.get("value"), (int, float))
                 and not uses(r) & {"contract.termination_type", "contract.termination_date"}]
        lo, hi = min([lo] + maybe), max([hi] + maybe)
    return {"base_rate": base_rate, "rate_range": [lo, hi], "disqualified": res.disqualified,
            "provided": sorted(ctx["_provided"]), "rules": items}


def load_gold(prefix):
    return {p.stem: json.loads(p.read_text("utf-8")).get("rules") or []
            for p in sorted(GOLD.glob(f"{prefix}-*.json"))}


def load_results(path, prefix):
    return {x["clause_id"]: ((x.get("output") or {}).get("rules") or [])
            for x in json.loads(Path(path).read_text("utf-8"))
            if x["clause_id"].startswith(prefix + "-") and isinstance((x.get("output") or {}).get("rules"), list)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("product", help="상품 접두어 (KBNR · KBSSG …)")
    ap.add_argument("--results", help="정답 대신 이 결과 파일의 모델 출력을 쓴다")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--start")
    ap.add_argument("--maturity")
    ap.add_argument("--monthly", type=int)
    ap.add_argument("--holder", choices=catalog.ENUM_VALUES.get("customer.holder_type"))
    ap.add_argument("--age", type=int)
    ap.add_argument("--has-product", type=lambda s: s.lower() in ("1", "y", "yes", "true"))
    a = ap.parse_args(argv)
    if a.product not in BASE_RATE:
        ap.error(f"모르는 상품: {a.product}. 있는 것: {', '.join(BASE_RATE)}")
    rules = load_results(a.results, a.product) if a.results else load_gold(a.product)
    base = BASE_RATE[a.product]
    ctx = user_ctx(a.today, a.start, a.maturity, a.monthly, a.holder, a.age, a.has_product, base_rate=base)
    out = explain(rules, ctx, base)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
