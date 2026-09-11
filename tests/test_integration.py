"""끝에서 끝까지 — 조문 하나가 조건식이 되고 금리가 나오기까지.

태스크 2·3 이 합성 ctx 로만 검증돼 있다는 §9 의 경고는 그대로다.
여기서 도는 것도 실제 생성물이 아니라 gold 형태의 조건식이다.
"""

import json

import pytest

import validate
from engine import evaluate_rules
from resolver import resolve
from scoring import score


@pytest.fixture(scope="module")
def fee_rule(clauses):
    """수수료면제 조문에 대한 손으로 쓴 조건식 하나."""
    c = next(x for x in clauses if x["id"] == "KBYY-S2-R12")
    quote = "전월 중 이 통장에서 KB국민카드"
    assert quote in c["text"]
    return c, {"rules": [{
        "rule_id": "KBYY-S2-R12-01",
        "status": "OK",
        "label": "카드결제 실적 수수료 면제",
        "source": {"quote": quote},
        "let": {"window": {"month_range": {
            "from": {"anchor": "contract.reference_date",
                     "offset_months": -1, "day": "first"},
            "to": {"anchor": "contract.reference_date",
                   "offset_months": -1, "day": "last"}}}},
        "condition": {"exists": {"event": "CARD_USAGE", "within": {"ref": "$window"}}},
        "effect": {"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                   "value": "UNLIMITED"}}]}


def test_hand_written_rule_passes_every_gate(fee_rule):
    clause, out = fee_rule
    m = validate.score_record(out, clause["text"])
    assert all(m[k] for k in ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok"))


def test_rule_fires_for_a_card_user(fee_rule, profiles):
    _, out = fee_rule
    ctxs = [c for _, c in profiles if c["events"].get("CARD_USAGE")]
    got = {evaluate_rules(out["rules"], c)[0].status for c in ctxs}
    assert got == {"MET"}


def test_rule_does_not_fire_without_card_usage(fee_rule, profiles):
    _, out = fee_rule
    ctxs = [c for _, c in profiles if not c["events"].get("CARD_USAGE")]
    got = {evaluate_rules(out["rules"], c)[0].status for c in ctxs}
    assert got == {"NOT_MET"}


def test_fee_waiver_does_not_move_the_rate(fee_rule, profiles, product):
    _, out = fee_rule
    _, ctx = profiles[0]
    r = resolve(evaluate_rules(out["rules"], ctx),
                product["aggregation"], base_rate=product["base_rate"])
    assert r.final_rate_min == f"{product['base_rate']:.2f}"


def test_fee_waiver_shows_up_in_other_effects(fee_rule, profiles, product):
    _, out = fee_rule
    ctx = next(c for _, c in profiles if c["events"].get("CARD_USAGE"))
    r = resolve(evaluate_rules(out["rules"], ctx),
                product["aggregation"], base_rate=product["base_rate"])
    assert r.other_effects and r.other_effects[0]["target"] == "EBANK_TRANSFER"


def test_scoring_a_rule_against_itself_is_perfect(fee_rule, profiles, product):
    _, out = fee_rule
    got = score(out["rules"], out["rules"], product["aggregation"],
                profiles, product["base_rate"])
    assert got["rate"] == 1.0


def test_limit_amount_instead_of_fee_waive_is_caught(fee_rule, profiles, product):
    """§6.4 의 실패. ①~⑤ 는 통과하지만 ⑥ 은 구분해야 한다."""
    _, out = fee_rule
    wrong = json.loads(json.dumps(out))
    wrong["rules"][0]["effect"] = {"type": "LIMIT_AMOUNT", "value": 0}
    m = validate.score_record(wrong, "전월 중 이 통장에서 KB국민카드")
    assert all(m[k] for k in ("schema_ok", "catalog_ok", "quote_ok", "exec_ok"))
    got = score(out["rules"], wrong["rules"], product["aggregation"],
                profiles, product["base_rate"])
    assert got["rate"] < 1.0


def test_every_clause_can_be_prompted(clauses):
    from prompt import build_user_prompt
    assert all(build_user_prompt(c["text"], c["id"]) for c in clauses)


def test_every_clause_text_is_quotable(clauses):
    # quote 검사가 조문 본문으로 항상 통과 가능해야 한다
    for c in clauses:
        head = c["text"].splitlines()[-1][:20]
        if len(head) < 8:
            continue
        r = {"source": {"quote": head}}
        assert validate.check_quote(r, c["text"]) == []


def test_product_base_rate_matches_the_document(product, root):
    doc = (root / "data" / product["document"]).read_text("utf-8")
    assert "연 0.1%" in doc and product["base_rate"] == 0.1


def test_product_special_rate_matches_the_document(product, root):
    doc = (root / "data" / product["document"]).read_text("utf-8")
    assert "연 1.9%" in doc and product["special_rate"] == 1.9


def test_fee_truth_table_matches_the_document(product, root):
    doc = (root / "data" / product["document"]).read_text("utf-8")
    assert "월 10회" in doc and product["fee_waiver_truth"]["ATM_TRANSFER"] == 10
    assert "월 5회" in doc and product["fee_waiver_truth"]["OTHER_BANK_ATM_WITHDRAW"] == 5
