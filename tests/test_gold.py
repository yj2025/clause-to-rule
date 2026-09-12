import pytest

import gold


def test_profile_count(profiles):
    assert len(profiles) == 256


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
