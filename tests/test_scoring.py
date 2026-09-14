import copy

import pytest

from scoring import outcome, score

BASE = {"rule_id": "R-01", "source": {"quote": "x"},
        "condition": {">=": [{"var": "customer.age"}, 19]},
        "effect": {"type": "RATE_ADD", "value": 0.5, "unit": "%p"}}
AGG, RATE = "SUM", 0.1


def split():
    return [{**BASE, "rule_id": f"R-0{i}",
             "effect": {"type": "RATE_ADD", "value": 0.25, "unit": "%p"}} for i in (1, 2)]


def waive():
    return {**BASE, "effect": {"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                               "value": "UNLIMITED"}}


def limit():
    return {**BASE, "effect": {"type": "LIMIT_AMOUNT", "value": 0}}


# ── §8.1 의 네 줄 ───────────────────────────────────────────────────────
def test_split_rules_mean_the_same(profiles):
    assert score([BASE], split(), AGG, profiles, RATE)["rate"] == 1.0


def test_different_rate_value_is_caught(profiles):
    other = copy.deepcopy(BASE)
    other["effect"]["value"] = 1.5
    assert score([BASE], [other], AGG, profiles, RATE)["rate"] == 0.5


def test_fee_waive_is_not_limit_amount(profiles):
    assert score([waive()], [limit()], AGG, profiles, RATE)["rate"] == 0.5


def test_empty_generation_is_caught(profiles):
    assert score([BASE], [], AGG, profiles, RATE)["rate"] == 0.5


# ── 성질 ────────────────────────────────────────────────────────────────
def test_identical_rules_score_one(profiles):
    assert score([BASE], [BASE], AGG, profiles, RATE)["rate"] == 1.0


def test_both_empty_score_one(profiles):
    assert score([], [], AGG, profiles, RATE)["rate"] == 1.0


def test_score_is_symmetric(profiles):
    a = score([BASE], split(), AGG, profiles, RATE)["rate"]
    b = score(split(), [BASE], AGG, profiles, RATE)["rate"]
    assert a == b


def test_rule_id_is_not_part_of_meaning(profiles):
    renamed = [{**BASE, "rule_id": "완전히-다른-이름"}]
    assert score([BASE], renamed, AGG, profiles, RATE)["rate"] == 1.0


def test_label_is_not_part_of_meaning(profiles):
    assert score([BASE], [{**BASE, "label": "아무거나"}], AGG, profiles, RATE)["rate"] == 1.0


def test_quote_is_not_part_of_meaning(profiles):
    other = copy.deepcopy(BASE)
    other["source"]["quote"] = "다른 문장"
    assert score([BASE], [other], AGG, profiles, RATE)["rate"] == 1.0


def test_other_effects_are_part_of_meaning(profiles):
    # outcome 이 other_effects 를 안 보면 이 둘이 같아 보인다
    assert score([waive()], [limit()], AGG, profiles, RATE)["rate"] < 1.0


def test_fee_target_matters(profiles):
    other = copy.deepcopy(waive())
    other["effect"]["target"] = "ATM_TRANSFER"
    assert score([waive()], [other], AGG, profiles, RATE)["rate"] < 1.0


def test_fee_value_matters(profiles):
    other = copy.deepcopy(waive())
    other["effect"]["value"] = 10
    assert score([waive()], [other], AGG, profiles, RATE)["rate"] < 1.0


def test_mismatch_examples_are_reported(profiles):
    r = score([BASE], [], AGG, profiles, RATE)
    assert r["mismatch"] and "profile" in r["mismatch"][0]


def test_counts_add_up(profiles):
    r = score([BASE], [], AGG, profiles, RATE)
    assert r["total"] == len(profiles) and 0 <= r["match"] <= r["total"]


def test_no_profiles_does_not_divide_by_zero():
    assert score([BASE], [], AGG, [], RATE)["rate"] == 0.0


def test_outcome_is_hashable(profiles):
    _, ctx = profiles[0]
    assert isinstance(hash(outcome([BASE], ctx, AGG, RATE)), int)


def test_outcome_ignores_rule_order(profiles):
    _, ctx = profiles[0]
    rules = [BASE, waive()]
    assert outcome(rules, ctx, AGG, RATE) == outcome(rules[::-1], ctx, AGG, RATE)


def test_unknown_is_part_of_outcome(profiles):
    _, ctx = profiles[0]
    unknown = {**BASE, "condition": {">=": [{"var": "contract.monthly_amount"}, 1]}}
    bare = dict(ctx)
    bare["contract"] = {k: v for k, v in ctx["contract"].items() if k != "monthly_amount"}
    assert outcome([unknown], bare, AGG, RATE) != outcome([BASE], bare, AGG, RATE)


def test_a_list_where_a_scalar_belongs_does_not_kill_the_round():
    """모델이 FEE_WAIVE.target 에 목록을 넣으면 frozenset 이 터졌다.

    그러면 그 라운드의 ⑥ 채점이 통째로 중단된다. v19 에서 실제로 났고,
    같은 모양이 ③ 에서도 한 번 터졌었다. 비교만 하면 되므로 눕힌다.
    """
    import gold
    from scoring import score
    P = gold.profiles()[:8]
    bad = [{"rule_id": "X", "status": "OK", "label": "목록을 넣었다",
            "source": {"quote": "q"}, "condition": {},
            "effect": {"type": "FEE_WAIVE",
                       "target": ["전자금융이체", "자동화기기"],
                       "value": "UNLIMITED"}}]
    r = score([], bad, "SUM", P, 0.0)
    assert 0.0 <= r["rate"] <= 1.0
