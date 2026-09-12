"""⑪ 뒷받침 축 — 인용문이 그 rule 을 받치나.

④ 는 인용문이 원문에 있는지만 본다. 원문 아무 문장이나 붙이면 통과한다.
이 축은 기계적으로 확실한 불일치만 센다 — **하한이다.**
"""

import pytest

import support as S

CLAUSE = ("[수수료면제 서비스]\n"
          "▪ 면제조건: 전월 중 KB국민카드 결제실적이 있는 경우\n"
          "▪ 면제기간: 이번 달 11일부터 다음 달 10일까지\n"
          "▪ 우대금리 연 1.9%p 를 제공합니다")


def rule(quote, cond=None, eff=None):
    return {"rule_id": "R", "source": {"quote": quote},
            "condition": cond if cond is not None else {},
            "effect": eff or {"type": "DISQUALIFY"}}


def test_a_matching_quote_passes():
    r = rule("전월 중 KB국민카드 결제실적이 있는 경우",
             {"exists": {"event": "CARD_USAGE"}})
    assert S.check_rule(r, CLAUSE) == []


def test_a_quote_about_something_else_is_caught():
    r = rule("면제기간: 이번 달 11일부터 다음 달 10일까지",
             {"exists": {"event": "CARD_USAGE"}})
    assert S.check_rule(r, CLAUSE) != []


def test_the_message_names_the_event():
    r = rule("면제기간: 이번 달 11일부터 다음 달 10일까지",
             {"exists": {"event": "CARD_USAGE"}})
    assert "CARD_USAGE" in S.check_rule(r, CLAUSE)[0]


def test_a_value_not_in_the_quote_is_caught():
    r = rule("면제기간: 이번 달 11일부터 다음 달 10일까지", {},
             {"type": "RATE_ADD", "value": 1.9, "unit": "%p"})
    assert S.check_rule(r, CLAUSE) != []


def test_a_value_in_the_quote_passes():
    r = rule("우대금리 연 1.9%p 를 제공합니다", {},
             {"type": "RATE_ADD", "value": 1.9, "unit": "%p"})
    assert S.check_rule(r, CLAUSE) == []


def test_a_value_absent_from_the_whole_clause_is_grounding_not_support():
    # 조문 어디에도 없는 수는 ⑨ 의 일이다. ⑪ 은 안 잡는다
    r = rule("우대금리 연 1.9%p 를 제공합니다", {},
             {"type": "RATE_ADD", "value": 0.5, "unit": "%p"})
    assert S.check_rule(r, CLAUSE) == []


def test_zero_is_out_of_scope():
    r = rule("면제기간: 이번 달 11일부터 다음 달 10일까지", {},
             {"type": "LIMIT_AMOUNT", "value": 0})
    assert S.check_rule(r, CLAUSE) == []


def test_a_quote_pointing_at_a_table_is_forgiven():
    # "기본실적 중 하나 이상" 은 참조표가 카드결제로 정의한다 — 근거가 맞다
    r = rule("아래 기본실적 중 하나 이상 발생된 경우",
             {"exists": {"event": "CARD_USAGE"}})
    assert S.check_rule(r, CLAUSE) == []


def test_quoting_a_short_clause_whole_is_fine():
    short = "[질권설정]\n▪ 불가"
    assert S.check_rule(rule(short), short) == []


def test_quoting_a_long_clause_whole_is_caught():
    assert any("조문 전체" in e for e in S.check_rule(rule(CLAUSE), CLAUSE))


def test_no_quote_is_out_of_scope():
    assert S.check_rule({"source": {}}, CLAUSE) == []


def test_events_are_found_in_nested_conditions():
    cond = {"and": [{"or": [{"exists": {"event": "CARD_USAGE"}}]}]}
    assert S._events_in(cond) == {"CARD_USAGE"}


def test_events_in_guard_are_checked():
    r = rule("면제기간: 이번 달 11일부터 다음 달 10일까지",
             {}, None)
    r["guard"] = {"exists": {"event": "CARD_USAGE"}}
    assert S.check_rule(r, CLAUSE) != []


# ── 실제 라운드 ─────────────────────────────────────────────────────────
def test_the_axis_is_a_lower_bound(root):
    """사람이 읽으면 훨씬 많다. 이 숫자가 낮다고 안심하면 안 된다."""
    import json
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in
             json.loads((root / "data/corpus.json").read_text("utf-8"))}
    r = S.audit(recs, texts)
    assert r["rate"] < 20.0          # 하한이므로 낮게 나온다
    assert r["checked"] > 50
