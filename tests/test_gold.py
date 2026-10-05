import pytest

import gold


def test_profile_count(profiles):
    assert len(profiles) == 1024


def test_term_and_epoch_axes_actually_discriminate(profiles):
    """넓힌 두 축이 실제로 값을 흔드는지.

    생성물의 변수 참조 40%가 프로필이 고정한 변수를 가리키고 있었다.
    `term_months` 27회 · `reference_date` 20회 — 둘이 대부분이었다.
    고정돼 있으면 ⑥ 이 맞는 조건과 틀린 조건을 구별하지 못한다.
    """
    terms = {c["contract"]["term_months"] for _, c in profiles}
    refs = {c["contract"]["reference_date"] for _, c in profiles}
    assert len(terms) > 1 and len(refs) > 1

    # 날짜가 기준일을 따라 움직여야 한다. 안 그러면 OLD 프로필에서
    # 실적이 전부 창 밖으로 나가 "실적 없음" 한 가지로 뭉개진다.
    for _, c in profiles:
        for ev in c["events"].get("SALARY_TRANSFER", []):
            assert ev["date"] < c["contract"]["reference_date"]


def test_profile_count_is_the_product_of_axes(profiles):
    n = 1
    for v in gold.AXES.values():
        n *= len(v)
    assert len(profiles) == n


def test_profiles_are_unique(profiles):
    assert len({name for name, _ in profiles}) == len(profiles)


def test_profiles_are_deterministic():
    assert [n for n, _ in gold.profiles()] == [n for n, _ in gold.profiles()]


@pytest.mark.parametrize("key", ["customer", "account", "contract", "events", "_provided"])
def test_profile_shape(profiles, key):
    assert key in profiles[0][1]


def test_provided_declares_salary(profiles):
    assert all("events.SALARY_TRANSFER" in c["_provided"] for _, c in profiles)


def test_some_profiles_have_salary(profiles):
    assert any(c["events"].get("SALARY_TRANSFER") for _, c in profiles)


def test_some_profiles_have_none(profiles):
    assert any(not c["events"].get("SALARY_TRANSFER") for _, c in profiles)


def test_both_termination_types_appear(profiles):
    kinds = {c["contract"]["termination_type"] for _, c in profiles}
    assert kinds == {"MATURITY", "EARLY"}


def test_both_ages_appear(profiles):
    assert {c["customer"]["age"] for _, c in profiles} == {17, 19}


def test_is_youth_follows_age(profiles):
    assert all(c["customer"]["is_youth"] == (c["customer"]["age"] < 19)
               for _, c in profiles)


def test_targets_are_real_clauses(clauses):
    ids = {c["id"] for c in clauses}
    assert set(gold.TARGETS) <= ids


def test_target_count():
    assert len(gold.TARGETS) == 15


def test_every_target_has_a_reason():
    assert all(len(v) > 10 for v in gold.TARGETS.values())


def test_targets_include_a_passing_clause():
    # 실패한 것만 라벨링하면 "지표가 못 보는 실패" 를 영원히 못 본다
    assert "KBYY-S2-R12" in gold.TARGETS


def test_targets_include_a_control_point():
    assert any("기준점" in v for v in gold.TARGETS.values())


def test_targets_cover_several_categories(clauses):
    by = {c["id"]: c["category"] for c in clauses}
    assert len({by[t] for t in gold.TARGETS}) >= 4


# ── 2026-10-05 · ⑥ 계약 변경: 프로필에 해지일 ─────────────────────────────────────────
def test_profiles_carry_a_termination_date():
    import gold
    P = gold.profiles()
    assert len(P) == 1024
    for _, ctx in P:
        c = ctx["contract"]
        assert c["termination_date"] and "contract.termination_date" in ctx["_provided"]
        if c["termination_type"] == "EARLY":
            assert c["termination_date"] < c["maturity_date"]
        else:
            assert c["termination_date"] == c["maturity_date"]
