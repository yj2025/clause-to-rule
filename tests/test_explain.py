"""explain.py — 모르는 조건을 «조건부»로 넘기는 JSON (2026-10-08)."""
import copy
import json

import engine
import explain as X
from kb10six import BASE_RATE

TODAY = "2026-10-08"
BASIC = dict(start="2025-06-10", maturity="2027-06-10", monthly=300_000, holder="INDIVIDUAL",
             age=35, has_product=False)


def _run(prefix, **kw):
    ctx = X.user_ctx(TODAY, **{**BASIC, **kw}, base_rate=BASE_RATE[prefix])
    return X.explain(X.load_gold(prefix), ctx, BASE_RATE[prefix])


def _rule(out, rid):
    return next(it for it in out["rules"] if it["rule_id"] == rid)


def test_transactions_are_never_declared():
    """거래 내역을 «제공했다»로 선언하면 실적 0건(NOT_MET)이 되어 혜택을 «못 받는다»로 단정한다."""
    ctx = X.user_ctx(TODAY, **BASIC)
    assert not [p for p in ctx["_provided"] if p.startswith("events.")]


def test_salary_preference_is_conditional_not_assumed():
    out = _run("KBNR")
    assert out["rate_range"] == [0.1, 2.0]
    sal = _rule(out, "KBNR-S2-R05-01")
    assert sal["status"] == "CONDITIONAL" and sal["side"] == "BENEFIT"
    assert sal["missing_events"] == ["SALARY_TRANSFER"] and sal["missing_inputs"] == []
    assert sal["effect"]["type"] == "RATE_ADD" and sal["effect"]["value"] == 1.9
    assert "급여이체 실적" in sal["quote"]


def test_underage_is_disqualified():
    out = _run("KBSSG", age=15)
    assert out["disqualified"] and _rule(out, "KBSSG-S2-R01-01")["status"] == "APPLIES"


def test_unknown_override_widens_range():
    """resolver 는 UNKNOWN RATE_OVERRIDE 를 구간에 안 넣는다 — 연금 9건 이상 연 1.5% 가 «0.10% 확정»이 되면 안 된다."""
    out = _run("KBGL", age=70)
    assert out["rate_range"] == [0.1, 1.5]
    tiers = [it for it in out["rules"] if (it["effect"] or {}).get("value") == 1.5]
    assert tiers and tiers[0]["side"] == "BENEFIT"


def test_termination_rates_stay_out_of_range():
    """중도해지 이율은 «지금 받는 금리»가 아니다 — 구간에 안 넣고 CAUTION 으로만."""
    out = _run("KBSME", maturity="2028-06-10")
    assert out["rate_range"][0] == BASE_RATE["KBSME"]
    early = [it for it in out["rules"] if (it["effect"] or {}).get("value") == 0.1]
    assert early and all(it["side"] == "CAUTION" for it in early)
    assert "contract.termination_date" in early[0]["missing_inputs"]


def test_prune_keeps_the_judgement():
    """걷어 낸 조건은 원래 조건과 판정이 같아야 한다 — 정답 105조문 전부, 기본 정보만 준 고객으로."""
    n = 0
    for prefix in BASE_RATE:
        ctx = X.user_ctx(TODAY, **BASIC)
        for rules in X.load_gold(prefix).values():
            for r in rules:
                if r.get("status") != "OK":
                    continue
                env = dict(r.get("let") or {})
                pruned = X.prune(r.get("condition"), ctx, env)
                assert engine.evaluate(pruned, ctx, env) is engine.evaluate(r.get("condition"), ctx, env)
                n += pruned != r.get("condition")
    assert n > 0


def test_every_product_and_input_untouched():
    for prefix in BASE_RATE:
        rules = X.load_gold(prefix)
        before = copy.deepcopy(rules)
        out = X.explain(rules, X.user_ctx(TODAY, **BASIC), BASE_RATE[prefix])
        json.dumps(out)
        assert {it["status"] for it in out["rules"]} <= {"APPLIES", "CONDITIONAL", "NOT_APPLICABLE", "ERROR"}
        assert rules == before


def test_cli(capsys):
    X.main(["KBNR", "--today", TODAY, "--start", "2025-03-02"])
    out = json.loads(capsys.readouterr().out)
    assert out["base_rate"] == BASE_RATE["KBNR"]
