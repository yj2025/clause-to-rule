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
    assert any("guard" in t for _, t in V.check_rule(r))


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
    assert any("한 갈래가" in t for _, t in V.check_rule(r))


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


def test_window_bindings_must_be_passed(root):
    """rule 의 `let` 을 안 넘기면 창을 쓰는 조건이 전부 검사에서 빠진다.

    v19 에서 이 구멍 때문에 표적 조문의 헛조건을 놓쳤다 —
    창을 쓰는 형태가 이 코퍼스에서 가장 흔하다.
    """
    LET = {"window": {"month_range": {
        "from": {"anchor": "contract.reference_date", "offset_months": -12,
                 "day": "first"},
        "to": {"anchor": "contract.reference_date", "offset_months": -1,
               "day": "last"}}}}
    arm = {">=": [{"count_events": {"event": "WITHDRAWAL",
                                    "within": {"ref": "$window"}}}, 0]}
    assert not V.is_vacuous(arm)                 # let 없이는 실행 실패
    assert V.is_vacuous(arm, LET)                # 넘기면 헛조건으로 잡힌다


def test_the_real_v19_rule_is_caught(root):
    import json, os
    os.chdir(root)
    d = {x["clause_id"]: x for x in
         json.loads((root / "results/results_v19.json").read_text("utf-8"))
         if x["run"] == 0}
    r = (d["KBYY-S2-R19"].get("output") or {}).get("rules")[0]
    assert V.check_rule(r), "창을 쓰는 헛조건을 잡아야 한다"


def test_profile_gap_is_not_called_a_defect():
    """프로필이 안 흔든 변수는 '미가동' 이지 헛조건이 아니다.

    `monthly_amount` 는 골드 프로필에서 0 으로 고정이다. `>= 0` 이 프로필
    전부에서 참이지만 월 납입금이 0 이 아닌 계약은 얼마든지 있다 —
    모델 잘못이 아니다. 첫 측정에서 이 둘을 안 갈라 수치가 8배 부풀었다.

    `term_months` 가 원래 이 자리였다. 프로필에 기간 축을 넣어 풀었다.
    """
    cond = {">=": [{"var": "contract.monthly_amount"}, 1]}
    assert not V.is_vacuous(cond)                # 프로필에서 거짓이다
    cond = {"==": [{"var": "contract.monthly_amount"}, 0]}
    assert V.is_vacuous(cond)                    # 프로필에서는 언제나 참
    assert V.has_counterexample(cond)            # 정의역에는 반례가 있다
    assert V.classify(cond) == "미가동"


def test_real_vacuity_has_no_counterexample():
    """셀 수 없는 값이 0 이상인지 묻는 조건은 어떤 문맥에서도 참이다."""
    cond = {">=": [{"count_events": {"event": "WITHDRAWAL"}}, 0]}
    assert not V.has_counterexample(cond)
    assert V.classify(cond) == "헛조건"


def test_enum_fully_enumerated_is_vacuous():
    """열거값 전부를 나열하면 조건이 아무 일도 하지 않는다."""
    import catalog
    cond = {"in": [{"var": "contract.termination_type"},
                   list(catalog.ENUM_VALUES["contract.termination_type"])]}
    assert V.classify(cond) == "헛조건"


def test_audit_counts_the_two_separately():
    recs = [{"clause_id": "X", "run": 0, "output": {"rules": [
        {"condition": {">=": [{"count_events": {"event": "DEPOSIT"}}, 0]}},
        {"condition": {"==": [{"var": "contract.monthly_amount"}, 0]}},
        {"condition": {"<": [{"var": "account.balance"}, 10000]}}]}}]
    a = V.audit(recs)
    assert (a["checked"], a["bad"], a["idle"]) == (3, 1, 1)


def test_sampler_straddles_every_threshold_the_model_uses():
    """조건에 쓰이는 문턱값과 그 양옆이 표본에 있어야 한다.

    문턱을 안 밟으면 `balance != 10000` 같은 조건이 반례를 못 만나
    헛조건으로 잘못 잡힌다.
    """
    import _free
    for t in (10_000, 50_000, 100_000, 1_000_000):
        for v in (t - 1, t, t + 1):
            assert v in _free._INT, f"{v} 가 표본에 없다"


def test_a_rare_counterexample_is_still_found():
    """400개 표본으로 드문 반례도 찾는가."""
    import _free
    V._FREE = _free.sample()
    cond = {"!=": [{"var": "account.balance"}, 10_000]}
    assert V.has_counterexample(cond)
    V._FREE = None


def test_vacuity_is_stable_across_seeds():
    """씨앗을 바꿔도 같은 답이 나와야 판정에 쓸 수 있다."""
    import _free
    cond = {">=": [{"count_events": {"event": "DEPOSIT"}}, 0]}
    near = {"<": [{"var": "account.balance"}, 50_000_000]}
    for seed in (20260913, 7, 99):
        V._FREE = _free.sample(400, seed)
        assert V.classify(cond) == "헛조건"
        assert V.classify(near) == "미가동"
    V._FREE = None
