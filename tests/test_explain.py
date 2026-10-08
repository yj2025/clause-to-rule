"""explain.py — 모르는 조건을 «조건부»로 보이는 층 (2026-10-08)."""
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


def test_transactions_are_never_declared():
    """거래 내역을 «제공했다»로 선언하면 실적 0건(NOT_MET)이 되어 혜택을 «못 받는다»로 단정한다."""
    ctx = X.user_ctx(TODAY, **BASIC)
    assert not [p for p in ctx["_provided"] if p.startswith("events.")]


def test_salary_preference_is_conditional_not_assumed():
    out = _run("KBNR")
    assert out["금리 범위"] == [0.1, 2.0]
    sal = [it for it in out["항목"] if it["rule_id"] == "KBNR-S2-R05-01"][0]
    assert sal["상태"] == "조건부" and sal["구분"] == "혜택"
    assert sal["거래 내역(모으지 않음)"] == ["급여이체"]
    assert "급여이체 실적" in sal["근거"]


def test_underage_is_disqualified_and_benefits_hidden():
    out = _run("KBSSG", age=15)
    assert out["가입 불가 확정"]
    text = X.render(out)
    assert "가입할 수 없습니다" in text and "면제" not in text


def test_unknown_override_widens_range():
    """resolver 는 UNKNOWN RATE_OVERRIDE 를 구간에 안 넣는다 — 연금 9건 이상 연 1.5% 가 «0.10% 확정»으로 보이면 안 된다."""
    out = _run("KBGL", age=70)
    assert out["금리 범위"] == [0.1, 1.5]
    tiers = [it for it in out["항목"] if it["결과"].get("값") == "연 1.5%"]
    assert tiers and tiers[0]["구분"] == "혜택"


def test_termination_rates_stay_out_of_range():
    """중도해지 이율은 «지금 받는 금리»가 아니다 — 구간에 안 넣고 «주의»로만."""
    out = _run("KBSME", maturity="2028-06-10")
    assert out["금리 범위"][0] == BASE_RATE["KBSME"]
    early = [it for it in out["항목"] if it["결과"].get("값") == "연 0.1%"]
    assert early and all(it["구분"] == "주의" for it in early)


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


def test_every_product_renders_and_input_untouched():
    for prefix in BASE_RATE:
        rules = X.load_gold(prefix)
        before = copy.deepcopy(rules)
        ctx = X.user_ctx(TODAY, **BASIC)
        text = X.render(X.explain(rules, ctx, BASE_RATE[prefix]))
        assert text.startswith("■") and "None" not in text
        assert rules == before


def test_cli_json(capsys):
    X.main(["KBNR", "--today", TODAY, "--start", "2025-03-02", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["기본이율"] == BASE_RATE["KBNR"]


def test_date_conditions_read_as_sentences():
    """「해지일 가입일 기준 다음 달 이전」은 못 읽는다(10-08 사용자) — 날짜 비교는 문장으로 옮긴다."""
    early = {"and": [{"==": [{"var": "contract.termination_type"}, "EARLY"]},
                     {"<": [{"var": "contract.termination_date"}, {"anchor": "contract.start_date", "offset_months": 1}]}]}
    assert X.cond_sentence(early, {}) == "가입 후 1개월이 되기 전에 중도해지하면"
    grace = {"<=": [{"var": "contract.reference_date"}, {"anchor": "contract.start_date", "offset_months": 2, "day": 10}]}
    assert X.cond_sentence(grace, {}) == "가입한 달의 다음다음 달 10일까지"
    text = X.render(_run("KBSME", maturity="2028-06-10"))
    assert "가입 후 1개월이 되기 전에 중도해지하면 → 이율 연 0.1% 적용" in text
    assert "기준 다음 달 이전" not in text
