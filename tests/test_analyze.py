import pytest

import analyze


def rec(first=None, final=None, output=None, errors=None):
    ok = dict(json_ok=True, schema_ok=True, catalog_ok=True, quote_ok=True, exec_ok=True)
    return {"clause_id": "X", "run": 0, "first": {**ok, **(first or {})},
            "final": {**ok, **(final or {})}, "output": output, "errors": errors or []}


def test_rate_all_true():
    assert analyze.rate([rec(), rec()], "final", "exec_ok") == 100.0


def test_rate_half():
    assert analyze.rate([rec(), rec(final={"exec_ok": False})], "final", "exec_ok") == 50.0


def test_rate_none():
    assert analyze.rate([rec(final={"exec_ok": False})], "final", "exec_ok") == 0.0


def test_rate_of_empty_is_zero():
    assert analyze.rate([], "final", "exec_ok") == 0.0


def test_rate_reads_the_requested_phase():
    r = rec(first={"exec_ok": False})
    assert analyze.rate([r], "first", "exec_ok") == 0.0
    assert analyze.rate([r], "final", "exec_ok") == 100.0


@pytest.mark.parametrize("key", analyze.KEYS)
def test_rate_works_for_every_key(key):
    assert analyze.rate([rec()], "final", key) == 100.0


# ── forms ───────────────────────────────────────────────────────────────
def with_rule(r):
    return [rec(output={"rules": [r]})]


def test_forms_counts_unbound_ref():
    r = {"rule_id": "R", "condition": {"exists": {"event": "DEPOSIT",
                                                  "within": {"ref": "$window"}}}}
    assert analyze.forms(with_rule(r))["미바인딩 $ref"] == 1


def test_forms_ignores_bound_ref():
    r = {"rule_id": "R", "let": {"window": {}},
         "condition": {"exists": {"event": "DEPOSIT", "within": {"ref": "$window"}}}}
    assert analyze.forms(with_rule(r))["미바인딩 $ref"] == 0


def test_forms_counts_var_alone():
    r = {"rule_id": "R", "condition": {"var": "customer.age"}}
    assert analyze.forms(with_rule(r))["var 단독 조건식"] == 1


def test_forms_ignores_var_as_operand():
    r = {"rule_id": "R", "condition": {"==": [{"var": "customer.age"}, 17]}}
    assert analyze.forms(with_rule(r))["var 단독 조건식"] == 0


def test_forms_counts_and_with_object():
    r = {"rule_id": "R", "condition": {"and": {"a": 1}}}
    assert analyze.forms(with_rule(r))["and 에 배열 아닌 것"] == 1


def test_forms_counts_stray_counter_keys():
    r = {"rule_id": "R", "condition": {">=": [
        {"count_events": {"event": "DEPOSIT", "operator": ">="}}, 1]}}
    assert analyze.forms(with_rule(r))["count_* 에 군더더기 키"] == 1


def test_forms_counts_non_numeric_rate_value():
    r = {"rule_id": "R", "condition": {}, "effect": {"type": "RATE_ADD",
                                                     "value": "contract.base_rate"}}
    assert analyze.forms(with_rule(r))["금리 value 가 수가 아님"] == 1


def test_forms_counts_invented_operators():
    c = analyze.forms([rec(errors=["정의되지 않은 연산자: literal. 쓸 수 있는 것"])])
    assert c["지어낸 연산자 literal"] == 1


def test_forms_of_empty_records_is_empty():
    assert analyze.forms([]) == {}


def test_forms_of_clean_rules_is_empty():
    r = {"rule_id": "R", "condition": {"==": [{"var": "customer.age"}, 17]},
         "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
    assert sum(analyze.forms(with_rule(r)).values()) == 0


def test_forms_survives_garbage_rules():
    analyze.forms([rec(output={"rules": ["문자열", None, 3]})])


def test_forms_survives_missing_output():
    analyze.forms([rec(output=None)])
