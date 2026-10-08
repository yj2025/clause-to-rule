"""fields.py — 상품별로 조건식이 읽는 입력 필드 (2026-10-08)."""
import catalog
import explain
import fields as F


def test_every_catalog_variable_has_a_source():
    """카탈로그에 필드를 더하면 «어디서 얻나»를 여기서 정해야 한다."""
    assert set(catalog.VARIABLES) == set(F.SOURCE)


def test_events_are_never_collected():
    assert {F.source_of(f"events.{e}") for e in catalog.EVENTS} == {F.NOT_COLLECTED}


def test_salary_rule_is_traced_to_its_event():
    f, n = F.product_fields(explain.load_gold("KBNR"))
    assert "KBNR-S2-R05-01" in f["events.SALARY_TRANSFER"]["rules"]
    assert f["events.SALARY_TRANSFER"]["source"] == F.NOT_COLLECTED


def test_counts_cover_every_ok_rule():
    for p in explain.BASE_RATE:
        rules = explain.load_gold(p)
        _, n = F.product_fields(rules)
        assert sum(n.values()) == sum(r.get("status") == "OK" for rs in rules.values() for r in rs)
