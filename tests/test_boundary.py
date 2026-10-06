"""⑥b 경계 (2026-10-06)."""
import boundary
import gold
from scoring import score

_W = {"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -1, "day": "first"},
                      "to": {"anchor": "contract.reference_date", "offset_months": -1, "day": "last"}}}


def _rule(cond):
    return [{"rule_id": "R1", "status": "OK", "condition": cond,
             "effect": {"type": "RATE_ADD", "value": 0.5, "unit": "%p", "applies_to": "BASE_RATE"}}]


SUM = _rule({">=": [{"sum_events": {"event": "DEPOSIT", "within": _W}}, 500000]})
ANY = _rule({"exists": {"event": "DEPOSIT", "within": _W}})
AGE = _rule({">=": [{"var": "customer.age"}, 19]})
AGE_WRONG = _rule({">": [{"var": "customer.age"}, 19]})


def test_thresholds_are_read_from_ok_rules():
    assert boundary.thresholds(SUM) == [("sum_events", "DEPOSIT", 500000)]
    assert boundary.thresholds(AGE) == [("var", "customer.age", 19)]
    assert boundary.thresholds([{**AGE[0], "status": "UNSUPPORTED"}]) == []


def test_a_sum_written_as_any_deposit_is_seen_only_at_the_boundary():
    base = gold.profiles()[:64]
    assert score(SUM, ANY, "SUM", base)["rate"] == 1.0                     # ⑥ 은 못 가른다
    assert score(SUM, ANY, "SUM", boundary.profiles_for(SUM, base))["rate"] < 1.0


def test_an_off_by_one_age_is_seen_at_the_boundary():
    base = gold.profiles()[:64]
    assert score(AGE, AGE_WRONG, "SUM", base)["rate"] == 1.0              # 앞 64 프로필은 나이가 17 뿐이라 못 가른다
    b = boundary.profiles_for(AGE, base)
    assert score(AGE, AGE_WRONG, "SUM", b)["rate"] < 1.0
    assert score(AGE, AGE, "SUM", b)["rate"] == 1.0


def test_no_threshold_no_profiles():
    assert boundary.profiles_for(_rule({}), gold.profiles()[:4]) == []
