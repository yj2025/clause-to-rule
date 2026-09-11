"""⑥ 이 못 보는 것 — UNSUPPORTED 와 빈 배열은 실행 결과가 같다.

gold 를 쓰던 에이전트 둘이 각자 같은 자리에서 이걸 발견했다.

    status "UNSUPPORTED" 인 rule 은 effect 가 없다.
    effect 가 없으면 resolver 가 other_effects 에 싣지 않는다.
    그래서 outcome() 이 빈 배열과 완전히 같다.

뜻으로는 다르다. 빈 배열은 "옮길 것이 없다" 이고 UNSUPPORTED 는 "옮길 수단이
없다" 다. 후자는 카탈로그를 넓혀야 한다는 신호이고 전자는 아니다.

**⑥ 으로 이 둘을 가르려 하면 안 된다.** 별도 축이 필요하다.
§6.4 에서 "①~⑤ 는 형식만 잰다" 고 했던 것과 같은 구조의 한계가 ⑥ 에도 있다.
"""

import pytest

from scoring import outcome, score

UNSUP = [{"rule_id": "R-01", "status": "UNSUPPORTED",
          "source": {"quote": "영업점장이 필요하다고 인정하는 경우"},
          "condition": {}}]
ADD = [{"rule_id": "R-01", "source": {"quote": "x"}, "condition": {},
        "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}]


def test_unsupported_and_empty_have_the_same_outcome(profiles):
    _, ctx = profiles[0]
    assert outcome(UNSUP, ctx, "SUM", 0.1) == outcome([], ctx, "SUM", 0.1)


def test_metric_six_cannot_tell_them_apart(profiles):
    assert score(UNSUP, [], "SUM", profiles, 0.1)["rate"] == 1.0


def test_it_is_symmetric(profiles):
    assert score([], UNSUP, "SUM", profiles, 0.1)["rate"] == 1.0


def test_metric_six_still_sees_a_real_effect(profiles):
    # 구멍은 UNSUPPORTED 에만 있다. 진짜 effect 는 여전히 잡힌다
    assert score(ADD, [], "SUM", profiles, 0.1)["rate"] < 1.0


def test_the_axis_that_does_tell_them_apart():
    """세려면 이렇게 세야 한다 — 실행 결과가 아니라 status 를 본다."""
    unsup = sum(1 for r in UNSUP if r.get("status") == "UNSUPPORTED")
    assert unsup == 1 and sum(1 for r in [] if r.get("status") == "UNSUPPORTED") == 0


# ── gold 의 변별력 점검 ─────────────────────────────────────────────────
import gold


def test_verdict_empty():
    assert gold.verdict([]) == "빈 배열"


def test_verdict_all_unsupported():
    assert gold.verdict(UNSUP) == "UNSUPPORTED 뿐"


def test_verdict_mixed():
    assert gold.verdict(UNSUP + ADD) == "일부 UNSUPPORTED"


def test_verdict_normal():
    assert gold.verdict(ADD) == "정상 rule"


def test_empty_gold_has_no_discriminating_power():
    assert gold.outcome_neutral([]) is True


def test_unsupported_gold_has_no_discriminating_power():
    assert gold.outcome_neutral(UNSUP) is True


def test_a_real_effect_has_discriminating_power():
    assert gold.outcome_neutral(ADD) is False


def test_neutrality_is_checked_across_every_profile():
    """한 프로필에서만 안 걸리는 rule 을 변별력 없음으로 세면 안 된다."""
    narrow = [{"rule_id": "R", "source": {"quote": "x"},
               "condition": {">=": [{"var": "customer.age"}, 19]},
               "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}]
    first = gold.profiles()[0][1]
    assert first["customer"]["age"] == 17          # 첫 프로필에서는 안 걸린다
    assert gold.outcome_neutral(narrow) is False   # 그래도 변별력은 있다


# ── ⑧ UNSUPPORTED 사용 축 ───────────────────────────────────────────────
import report


def _rec(rules):
    return {"clause_id": "X", "run": 0, "output": None if rules is None else {"rules": rules}}


OK = {"rule_id": "R", "status": "OK", "condition": {},
      "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
UN = {"rule_id": "R", "status": "UNSUPPORTED", "condition": {}}


def test_unsupported_rate_of_all_ok():
    assert report.unsupported_stats([_rec([OK, OK])])["rate"] == 0.0


def test_unsupported_rate_of_all_unsupported():
    assert report.unsupported_stats([_rec([UN, UN])])["rate"] == 100.0


def test_unsupported_rate_is_per_rule():
    assert report.unsupported_stats([_rec([OK, UN, UN, UN])])["rate"] == 75.0


def test_empty_output_contributes_no_rules():
    assert report.unsupported_stats([_rec([])])["rule"] == 0


def test_no_rules_anywhere_is_zero_not_a_crash():
    assert report.unsupported_stats([_rec(None), _rec([])])["rate"] == 0.0


@pytest.mark.parametrize("rules,want", [
    ([OK], "OK 뿐"), ([UN], "UNSUPPORTED 뿐"),
    ([OK, UN], "섞임"), ([], "빈 배열"), (None, "무출력"),
])
def test_record_kind(rules, want):
    assert report.unsupported_stats([_rec(rules)])["kind"][want] == 1


def test_garbage_rules_are_ignored():
    assert report.unsupported_stats([_rec(["문자열", None, OK])])["rule"] == 1


def test_the_axis_exists_before_the_treatment_that_needs_it():
    """v5 후보(섞인 예시)는 UNSUPPORTED 를 늘려 ③ 을 공짜로 딸 수 있다.

    탈출구를 열기 전에 그것을 세는 축부터 세운다 (§9 11번).
    """
    gamed = report.unsupported_stats([_rec([UN, UN, UN])])
    honest = report.unsupported_stats([_rec([OK, OK, OK])])
    assert gamed["rate"] > honest["rate"]
