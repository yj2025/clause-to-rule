"""⑭ 헛조건 — 조건이 붙어 있는데 언제나 참인가.

v19 에서 거래중지가 `count_events(WITHDRAWAL) >= 0` 으로 나왔다.
항상 참이라 잔액 조건만으로 거래를 제한한다 — 정상 계좌가 전부 걸린다.
**관문 다섯이 전부 통과시키고 ⑫ 도 못 본다** (판정은 맞기 때문이다).
"""

import pytest

import vacuous as V


@pytest.mark.parametrize("cond", [
    {">=": [{"count_events": {"event": "DEPOSIT"}}, 0]},
    {"in": [{"var": "contract.termination_type"},
            ["MATURITY", "EARLY", "PARTIAL", "MID_TERM", "NONE"]]},
    {"or": [{"==": [{"var": "customer.age"}, 17]},
            {"!=": [{"var": "customer.age"}, 17]}]},
    {">=": [{"var": "account.balance"}, 0]},
])
def test_always_true_conditions_are_caught(cond):
    assert V.is_vacuous(cond)


@pytest.mark.parametrize("cond", [
    {"==": [{"var": "customer.age"}, 17]},
    {"<": [{"var": "account.balance"}, 10000]},
    {"==": [{"count_events": {"event": "DEPOSIT"}}, 0]},
    {"and": [{"==": [{"var": "customer.age"}, 17]},
             {">=": [{"var": "account.balance"}, 1]}]},
])
def test_real_conditions_are_not_caught(cond):
    assert not V.is_vacuous(cond)


def test_empty_condition_is_not_counted():
    """빈 조건은 '항상 적용' 을 밝힌 것이다. 숨은 헛조건과 다르다."""
    assert not V.is_vacuous({})


def test_missing_condition_is_not_counted():
    assert not V.is_vacuous(None)


def test_broken_condition_is_not_counted():
    """실행 불가는 ⑤ 가 잡는다. 여기서는 세지 않는다."""
    assert not V.is_vacuous({"nope": 1})


def test_guard_is_checked_too():
    r = {"condition": {"==": [{"var": "customer.age"}, 17]},
         "guard": {">=": [{"var": "account.balance"}, 0]}}
    assert any("guard" in e for e in V.check_rule(r))


def test_the_known_v19_shape_is_caught():
    """조문은 '거래가 없는 계좌' 인데 생성물은 '거래가 0건 이상' 이다.

    조건 **전체**는 헛것이 아니다 — 잔액 조건이 진짜다.
    헛것인 것은 **갈래 하나**이고, 빼도 결과가 같다.
    """
    cond = {"and": [{"<": [{"var": "account.balance"}, 10000]},
                    {">=": [{"count_events": {"event": "WITHDRAWAL"}}, 0]}]}
    assert not V.is_vacuous(cond)
    assert len(V.vacuous_branches(cond)) == 1
    r = {"condition": cond}
    assert any("한 갈래가" in e for e in V.check_rule(r))


def test_the_correct_shape_is_not_caught():
    cond = {"and": [{"<": [{"var": "account.balance"}, 10000]},
                    {"==": [{"count_events": {"event": "WITHDRAWAL"}}, 0]},
                    {"==": [{"count_events": {"event": "DEPOSIT"}}, 0]}]}
    assert not V.is_vacuous(cond) and V.vacuous_branches(cond) == []


def test_the_special_rate_bug_is_caught(root):
    """저금통 0원 고객에게 1.9% 를 주는 조건 — 사람이 읽어 찾던 것이다."""
    cond = {"and": [{">=": [{"var": "account.reserved_amount"}, 0]},
                    {"<=": [{"var": "account.reserved_amount"}, 1000000]}]}
    assert V.is_vacuous(cond)


def test_audit_runs_on_a_real_round(root):
    import json, os
    os.chdir(root)
    recs = [x for x in json.loads((root / "results/results_v16.json").read_text("utf-8"))
            if x["run"] == 0]
    a = V.audit(recs)
    assert a["checked"] > 20 and a["bad"] > 0


def test_every_gate_lets_it_pass():
    """이 축이 필요한 이유 — 관문 다섯이 못 잡는다."""
    import validate as VA
    r = {"rule_id": "R", "source": {"quote": "x"},
         "condition": {">=": [{"count_events": {"event": "DEPOSIT"}}, 0]},
         "effect": {"type": "DISQUALIFY"}}
    assert VA.check_catalog(r) == [] and VA.check_executable(r) == []
    assert V.check_rule(r) != []
