import pytest
from conftest import ctx

from engine import evaluate_rules
from resolver import resolve

C = ctx(age=17)


def rule(rid="R", effect=None, cond=None, **kw):
    r = {"rule_id": rid, "source": {"quote": "x"},
         "condition": cond if cond is not None else {"==": [{"var": "customer.age"}, 17]},
         "effect": effect or {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
    r.update(kw)
    return r


def run(rules, c=C, agg="SUM", base=0.10):
    return resolve(evaluate_rules(rules, c), agg, base_rate=base)


def test_no_rules_is_base_rate():
    r = run([])
    assert (r.final_rate_min, r.final_rate_max) == ("0.10", "0.10")


def test_met_rate_add():
    assert run([rule()]).final_rate_max == "1.10"


def test_not_met_stays_at_base():
    assert run([rule()], ctx(age=19)).final_rate_max == "0.10"


def test_sum_adds_all_met():
    assert run([rule("A"), rule("B")]).final_rate_max == "2.10"


def test_max_takes_the_largest():
    rules = [rule("A"), rule("B", effect={"type": "RATE_ADD", "value": 0.4, "unit": "%p"})]
    assert run(rules, agg="MAX").final_rate_max == "1.10"


def test_rate_subtract():
    assert run([rule(effect={"type": "RATE_SUBTRACT", "value": 0.05,
                             "unit": "%p"})]).final_rate_max == "0.05"


def test_penalty_rate_subtracts():
    assert run([rule(effect={"type": "PENALTY_RATE", "value": 0.1,
                             "unit": "%p"})]).final_rate_max == "0.00"


def test_override_replaces_base():
    assert run([rule(effect={"type": "RATE_OVERRIDE", "value": 2.0,
                             "unit": "%p"})]).final_rate_max == "2.00"


def test_override_records_what_it_erased():
    rules = [rule("ADD"), rule("OVER", effect={"type": "RATE_OVERRIDE",
                                               "value": 2.0, "unit": "%p"})]
    assert run(rules).overridden_rules == ["ADD"]


def test_override_without_erasing_anything():
    assert run([rule(effect={"type": "RATE_OVERRIDE", "value": 2.0,
                             "unit": "%p"})]).overridden_rules == []


def test_unknown_opens_an_interval():
    r = run([rule(cond={">=": [{"var": "account.reserved_amount"}, 1]})],
            {"account": {}})
    assert (r.final_rate_min, r.final_rate_max) == ("0.10", "1.10")


def test_unknown_sets_needs_review():
    r = run([rule(cond={">=": [{"var": "account.reserved_amount"}, 1]})], {"account": {}})
    assert r.needs_review is True


def test_certain_result_does_not_need_review():
    assert run([rule()]).needs_review is False


def test_disqualify_wipes_benefits():
    rules = [rule("ADD"), rule("DQ", effect={"type": "DISQUALIFY"})]
    r = run(rules)
    assert r.disqualified is True and r.final_rate_max == "0.10"


def test_disqualify_not_met_leaves_benefits():
    rules = [rule("ADD"), rule("DQ", effect={"type": "DISQUALIFY"},
                               cond={"==": [{"var": "customer.age"}, 99]})]
    assert run(rules).final_rate_max == "1.10"


def test_fee_waive_goes_to_other_effects():
    r = run([rule(effect={"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                          "value": "UNLIMITED"})])
    assert r.other_effects[0]["type"] == "FEE_WAIVE"


def test_fee_waive_does_not_move_the_rate():
    r = run([rule(effect={"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                          "value": "UNLIMITED"})])
    assert r.final_rate_max == "0.10"


def test_limit_amount_goes_to_other_effects():
    r = run([rule(effect={"type": "LIMIT_AMOUNT", "value": 0})])
    assert r.other_effects[0]["type"] == "LIMIT_AMOUNT"


def test_require_goes_to_other_effects():
    r = run([rule(effect={"type": "REQUIRE", "value": "실명확인"})])
    assert r.other_effects[0]["type"] == "REQUIRE"


def test_guard_skipped_rule_does_not_apply():
    r = run([rule(guard={"==": [{"var": "contract.termination_type"}, "MATURITY"]})],
            ctx(age=17, term="EARLY"))
    assert r.final_rate_max == "0.10"


def test_broken_rule_sets_needs_review():
    r = run([rule(cond={"nope": 1})])
    assert r.needs_review is True


def test_unknown_aggregation_is_refused():
    with pytest.raises(ValueError):
        resolve([], "AVERAGE")


def test_repr_shows_interval():
    assert "0.10~1.10" in repr(run([rule(cond={">=": [{"var": "account.reserved_amount"},
                                                      1]})], {"account": {}}))


def test_applied_lists_met_rules():
    assert run([rule("A"), rule("B")]).applied == ["A", "B"]


def test_rate_value_that_is_not_a_number_contributes_nothing():
    # 검증기가 막지만, resolver 도 죽지 않아야 한다
    r = run([rule(effect={"type": "RATE_ADD", "value": "contract.base_rate",
                          "unit": "%p"})])
    assert r.final_rate_max == "0.10"
