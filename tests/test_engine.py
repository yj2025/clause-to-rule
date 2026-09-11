import pytest
from conftest import WINDOW, ctx

import catalog
from engine import DslError, Judgement, evaluate, evaluate_rules
from tv import TV

T, F, U = TV.T, TV.F, TV.U
C = ctx()


@pytest.mark.parametrize("node,want", [
    ({"==": [{"var": "customer.age"}, 17]}, T),
    ({"==": [{"var": "customer.age"}, 19]}, F),
    ({"!=": [{"var": "customer.age"}, 19]}, T),
    ({">=": [{"var": "customer.age"}, 17]}, T),
    ({">": [{"var": "customer.age"}, 17]}, F),
    ({"<": [{"var": "customer.age"}, 19]}, T),
    ({"<=": [{"var": "customer.age"}, 17]}, T),
    ({"in": [{"var": "contract.channel"}, ["MOBILE", "BRANCH"]]}, T),
    ({"in": [{"var": "contract.channel"}, ["ATM"]]}, F),
])
def test_comparisons(node, want):
    assert evaluate(node, C) is want


def test_missing_data_is_unknown_not_false():
    assert evaluate({">=": [{"var": "account.reserved_amount"}, 1]}, {"account": {}}) is U


def test_empty_condition_is_true():
    assert evaluate({}, C) is T


def test_none_condition_is_true():
    assert evaluate(None, C) is T


def test_and_of_list():
    assert evaluate({"and": [{"==": [1, 1]}, {"==": [2, 2]}]}, C) is T


def test_or_of_list():
    assert evaluate({"or": [{"==": [1, 2]}, {"==": [2, 2]}]}, C) is T


def test_not():
    assert evaluate({"not": {"==": [1, 2]}}, C) is T


def test_not_accepts_list_form():
    assert evaluate({"not": [{"==": [1, 2]}]}, C) is T


def test_nested_and_or():
    node = {"and": [{"or": [{"==": [1, 2]}, {"==": [2, 2]}]}, {"==": [3, 3]}]}
    assert evaluate(node, C) is T


def test_dates_compare_as_dates():
    node = {"<": [{"var": "contract.start_date"}, {"var": "contract.maturity_date"}]}
    assert evaluate(node, C) is T


# ── 창과 이벤트 ─────────────────────────────────────────────────────────
def test_exists_inside_window():
    node = {"exists": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}
    assert evaluate(node, ctx(salary=3), WINDOW) is T


def test_exists_outside_window_is_false():
    node = {"exists": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}
    assert evaluate(node, ctx(salary=0), WINDOW) is F


def test_exists_without_data_is_unknown():
    node = {"exists": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}
    assert evaluate(node, ctx(provide_salary=False), WINDOW) is U


def test_empty_list_and_missing_data_differ():
    node = {"exists": {"event": "SALARY_TRANSFER"}}
    assert evaluate(node, ctx(salary=0)) is F
    assert evaluate(node, ctx(provide_salary=False)) is U


@pytest.mark.parametrize("months,want", [(0, F), (5, F), (6, T), (9, T)])
def test_count_distinct_months(months, want):
    node = {">=": [{"count_distinct_months": {"event": "SALARY_TRANSFER",
                                              "within": {"ref": "$window"}}}, 6]}
    assert evaluate(node, ctx(salary=months), WINDOW) is want


def test_count_events():
    node = {">=": [{"count_events": {"event": "SALARY_TRANSFER"}}, 3]}
    assert evaluate(node, ctx(salary=3)) is T


def test_count_consecutive_months():
    node = {">=": [{"count_consecutive_months": {"event": "SALARY_TRANSFER"}}, 3]}
    assert evaluate(node, ctx(salary=3)) is T


def test_window_day_last_is_month_end():
    node = {"exists": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}
    # 2026-10-31 은 만기월 -2 = 10월의 마지막일. 창 밖이 아니다.
    c = ctx(salary=0)
    c["events"]["SALARY_TRANSFER"] = [{"date": "2026-10-31"}]
    assert evaluate(node, c, WINDOW) is T


# ── 실행 불가 ───────────────────────────────────────────────────────────
def test_unbound_ref_raises():
    node = {"exists": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}
    with pytest.raises(DslError, match="미바인딩"):
        evaluate(node, C)


def test_var_alone_is_not_a_condition():
    with pytest.raises(DslError, match="var 단독"):
        evaluate({"var": "customer.age"}, C)


def test_and_with_object_names_the_right_shape():
    with pytest.raises(DslError) as e:
        evaluate({"and": {"a": {"==": [1, 1]}}}, C)
    assert str(e.value) == ('and: 배열을 기대했으나 dict 이 옴. '
                            '올바른 형태: {"and": [ {...}, {...} ]}')


def test_unknown_operator_message():
    with pytest.raises(DslError, match="정의되지 않은 연산자: between"):
        evaluate({"between": [1, 2]}, C)


def test_unknown_variable():
    with pytest.raises(DslError, match="카탈로그에 없는 변수"):
        evaluate({"==": [{"var": "customer.income"}, 1]}, C)


def test_unknown_event():
    with pytest.raises(DslError, match="카탈로그에 없는 이벤트"):
        evaluate({"exists": {"event": "LOTTERY_WIN"}}, C)


def test_two_keys_in_condition():
    with pytest.raises(DslError, match="키는 하나"):
        evaluate({"==": [1, 1], "!=": [1, 2]}, C)


def test_comparison_needs_two_operands():
    with pytest.raises(DslError, match="피연산자 2개"):
        evaluate({"==": [1]}, C)


def test_counter_alone_is_not_a_condition():
    with pytest.raises(DslError, match="비교로 감싸야"):
        evaluate({"count_events": {"event": "DEPOSIT"}}, C)


def test_counter_rejects_stray_keys():
    with pytest.raises(DslError, match="모르는 키"):
        evaluate({">=": [{"count_events": {"event": "DEPOSIT", "operator": ">="}}, 1]}, C)


def test_bad_date_is_reported():
    c = ctx()
    c["contract"]["start_date"] = "어제"
    with pytest.raises(DslError, match="날짜로 못 읽음"):
        evaluate({"<": [{"var": "contract.start_date"},
                        {"var": "contract.maturity_date"}]}, c)


# ── evaluate_rules ──────────────────────────────────────────────────────
def _rule(**kw):
    base = {"rule_id": "R", "source": {"quote": "x"},
            "condition": {"==": [{"var": "customer.age"}, 17]},
            "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
    base.update(kw)
    return base


@pytest.mark.parametrize("age,want", [(17, "MET"), (19, "NOT_MET")])
def test_status_met_and_not_met(age, want):
    assert evaluate_rules([_rule()], ctx(age=age))[0].status == want


def test_status_unknown():
    r = _rule(condition={">=": [{"var": "account.reserved_amount"}, 1]})
    assert evaluate_rules([r], {"account": {}})[0].status == "UNKNOWN"


def test_guard_false_skips():
    r = _rule(guard={"==": [{"var": "contract.termination_type"}, "MATURITY"]})
    assert evaluate_rules([r], ctx(term="EARLY"))[0].status == "SKIPPED_GUARD"


def test_guard_true_keeps_condition():
    r = _rule(guard={"==": [{"var": "contract.termination_type"}, "MATURITY"]})
    assert evaluate_rules([r], ctx(term="MATURITY"))[0].status == "MET"


def test_error_becomes_status_error():
    r = _rule(condition={"exists": {"event": "DEPOSIT", "within": {"ref": "$nope"}}})
    j = evaluate_rules([r], C)[0]
    assert j.status == "ERROR" and "미바인딩" in j.error


def test_evaluate_rules_never_raises():
    assert evaluate_rules([_rule(condition={"nope": 1})], C)[0].status == "ERROR"


def test_empty_rules_gives_empty_list():
    assert evaluate_rules([], C) == []


def test_none_rules_gives_empty_list():
    assert evaluate_rules(None, C) == []


def test_judgement_repr():
    assert "MET" in repr(evaluate_rules([_rule()], ctx(age=17))[0])


def test_every_catalog_operator_is_reachable():
    # 카탈로그에 있는데 엔진이 모르는 연산자가 있으면 안 된다
    unknown = []
    for op in catalog.OPERATORS:
        try:
            evaluate({op: [] if op in ("and", "or") else [1, 1]}, C, WINDOW)
        except DslError as e:
            if "정의되지 않은 연산자" in str(e):
                unknown.append(op)
        except Exception:
            pass
    assert unknown == []


# ── 생성물이 이상해도 죽지 않는다 ───────────────────────────────────────
@pytest.mark.parametrize("bad", [
    {"exists": []},
    {"exists": "DEPOSIT"},
    {"exists": 3},
    {"and": "x"},
    {"or": 1},
    {"==": {"a": 1}},
    {"not": []},
    {">=": [{"count_events": []}, 1]},
    {"exists": {"event": "DEPOSIT", "within": []}},
    {"exists": {"event": "DEPOSIT", "within": {"month_range": "x"}}},
])
def test_malformed_condition_never_crashes(bad):
    r = {"rule_id": "R", "source": {"quote": "x"}, "condition": bad,
         "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
    j = evaluate_rules([r], C)[0]
    assert j.status == "ERROR" and j.error


def test_exists_with_list_names_the_right_shape():
    with pytest.raises(DslError, match="exists: 객체를 기대했으나 list"):
        evaluate({"exists": []}, C)


def test_scoring_survives_malformed_generation(profiles=None):
    from scoring import outcome
    bad = [{"rule_id": "R", "source": {"quote": "x"},
            "condition": {"exists": []}, "effect": {"type": "DISQUALIFY"}}]
    assert outcome(bad, C, "SUM", 0.1)
