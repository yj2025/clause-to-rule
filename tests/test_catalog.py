import pytest

import catalog as C


def test_variable_count():
    """2026-09-15 customer.holder_type 을 더해 18개가 됐다."""
    assert len(C.VARIABLES) == 18


def test_event_count():
    """v17 에서 WITHDRAWAL 을 더해 11개가 됐다 (`CATALOG_PROPOSAL.md` 2순위)."""
    assert len(C.EVENTS) == 11


def test_operator_count():
    assert len(C.OPERATORS) == 14


def test_effect_count():
    """2026-09-15 SERVICE_PROVIDE · FEE_WAIVE_NO_CARRYOVER 를 더해 10개가 됐다."""
    assert len(C.EFFECTS) == 10


def test_fee_count():
    assert len(C.FEES) == 6


@pytest.mark.parametrize("name", sorted(C.VARIABLES))
def test_every_variable_has_type_and_desc(name):
    assert C.VARIABLES[name]["type"] and C.VARIABLES[name]["desc"]


@pytest.mark.parametrize("name", sorted(C.EVENTS))
def test_every_event_has_a_description(name):
    assert C.EVENTS[name]


def test_operators_have_no_duplicates():
    assert len(set(C.OPERATORS)) == len(C.OPERATORS)


def test_comparisons_are_operators():
    assert set(C.COMPARISONS) <= set(C.OPERATORS)


def test_counters_are_operators():
    assert set(C.COUNTERS) <= set(C.OPERATORS)


def test_rate_effects_are_effects():
    assert set(C.RATE_EFFECTS) <= set(C.EFFECTS)


def test_unsupported_is_a_status_not_an_effect():
    assert "UNSUPPORTED" in C.STATUSES and "UNSUPPORTED" not in C.EFFECTS


@pytest.mark.parametrize("name", sorted(C.ENUM_VALUES))
def test_enum_variables_are_declared_enum(name):
    assert C.VARIABLES[name]["type"] == "enum"


def test_fee_waive_needs_a_target():
    assert "target" in C.EFFECTS["FEE_WAIVE"]


def test_disqualify_needs_nothing():
    assert C.EFFECTS["DISQUALIFY"] == ()


# ── 확장 대기 4건은 아직 없어야 한다 ────────────────────────────────────
@pytest.mark.parametrize("name", ["PRODUCT_SWITCH_EFFECT", "THRESHOLD_AMOUNT"])
def test_pending_effects_are_absent(name):
    assert name not in C.EFFECTS


@pytest.mark.parametrize("name", ["SEIZURE", "PROVISIONAL_SEIZURE"])
def test_pending_events_are_absent(name):
    """아직 합의 전인 것. 압류 계열은 `CATALOG_PROPOSAL.md` 7순위다."""
    assert name not in C.EVENTS


def test_withdrawal_pairs_with_deposit():
    """DEPOSIT 만 있으면 출금만 있던 계좌가 무거래로 판정된다 — 부호가 뒤집힌다."""
    assert "WITHDRAWAL" in C.EVENTS and "DEPOSIT" in C.EVENTS


def test_withdrawal_is_picked_for_transaction_clauses():
    _, ev = C.pick_candidates("1년 이상 입출금 거래가 없는 계좌")
    assert "WITHDRAWAL" in ev


# ── pick_candidates ─────────────────────────────────────────────────────
def test_pick_returns_two_lists():
    v, e = C.pick_candidates("카드 결제실적")
    assert isinstance(v, list) and isinstance(e, list)


def test_pick_finds_card_usage():
    _, e = C.pick_candidates("KB국민카드 결제실적이 있는 경우")
    assert "CARD_USAGE" in e


def test_pick_finds_salary_transfer():
    _, e = C.pick_candidates("급여이체가 발생한 월")
    assert "SALARY_TRANSFER" in e


def test_pick_finds_reserved_amount():
    v, _ = C.pick_candidates("저금통으로 설정된 금액")
    assert "account.reserved_amount" in v


def test_pick_is_empty_without_evidence():
    v, e = C.pick_candidates("xyz")
    assert v == [] and e == []


def test_pick_results_are_sorted():
    v, e = C.pick_candidates("급여이체 카드 결제실적 저금통 만기 해지")
    assert v == sorted(v) and e == sorted(e)


def test_pick_only_returns_known_names():
    v, e = C.pick_candidates("급여이체 카드 저금통 만기 해지 전환 연금 외환")
    assert set(v) <= set(C.VARIABLES) and set(e) <= set(C.EVENTS)


def test_pick_fees_finds_ebank():
    assert "EBANK_TRANSFER" in C.pick_fees("전자금융 이체수수료")


def test_pick_fees_is_empty_without_evidence():
    assert C.pick_fees("xyz") == []


@pytest.mark.parametrize("name,value,want", [
    ("contract.termination_type", "MATURITY", True),
    ("contract.termination_type", "취소", False),
    ("contract.channel", "MOBILE", True),
    ("contract.channel", "카카오", False),
    ("customer.age", 17, True),
])
def test_is_known_value(name, value, want):
    assert C.is_known_value(name, value) is want
