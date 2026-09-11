"""부록 A.3 · A.5 의 채점 수정을 고정하는 테스트.

지표의 구멍은 점수를 틀리게 만드는 데 그치지 않는다. 분산을 눌러 판정을
거짓으로 세우기도 한다. 기권군 문턱 0.4p 가 그렇게 생겼다.
"""

import pytest

import gold


# ── 조문 가중 ───────────────────────────────────────────────────────────
def test_equal_runs_both_methods_agree():
    per = {"A": [1.0, 0.0], "B": [1.0, 0.0]}
    assert gold.clause_weighted(per) == gold.run_weighted(per)


def test_uneven_runs_make_the_methods_disagree():
    # A 는 회차가 하나만 남았다. 회차 가중이면 A 의 몫이 줄어든다.
    per = {"A": [0.0], "B": [1.0, 1.0, 1.0]}
    assert gold.clause_weighted(per) != gold.run_weighted(per)


def test_clause_weighting_keeps_each_clause_equal():
    per = {"A": [0.0], "B": [1.0, 1.0, 1.0]}
    assert gold.clause_weighted(per) == pytest.approx(0.5)


def test_run_weighting_understates_the_truncated_clause():
    per = {"A": [0.0], "B": [1.0, 1.0, 1.0]}
    assert gold.run_weighted(per) == pytest.approx(0.75)


def test_dropping_runs_does_not_change_clause_weight():
    before = gold.clause_weighted({"A": [0.4, 0.4, 0.4], "B": [0.8]})
    after = gold.clause_weighted({"A": [0.4], "B": [0.8]})
    assert before == after


def test_dropping_runs_does_change_run_weight():
    before = gold.run_weighted({"A": [0.4, 0.4, 0.4], "B": [0.8]})
    after = gold.run_weighted({"A": [0.4], "B": [0.8]})
    assert before != after


def test_empty_input_is_zero():
    assert gold.clause_weighted({}) == 0.0


def test_clause_with_no_runs_is_ignored():
    assert gold.clause_weighted({"A": [], "B": [1.0]}) == 1.0


# ── 무출력 회차 ─────────────────────────────────────────────────────────
def rec(rules):
    return {"clause_id": "X", "output": None if rules is None else {"rules": rules}}


def test_missing_output_is_dropped():
    assert gold.drop_empty_runs([rec(None)]) == []


def test_empty_array_is_kept():
    assert len(gold.drop_empty_runs([rec([])])) == 1


def test_real_rules_are_kept():
    assert len(gold.drop_empty_runs([rec([{"rule_id": "R"}])])) == 1


def test_missing_output_and_empty_array_are_different():
    runs = [rec(None), rec([])]
    assert len(gold.drop_empty_runs(runs)) == 1


def test_output_without_rules_key_is_dropped():
    assert gold.drop_empty_runs([{"clause_id": "X", "output": {}}]) == []


def test_both_branches_are_reported_together():
    # 섞인 갈래와 무출력 제외 갈래가 다른 값을 낼 수 있어야 한다
    runs = [rec(None), rec([]), rec([])]
    mixed = len(runs)
    clean = len(gold.drop_empty_runs(runs))
    assert mixed != clean
