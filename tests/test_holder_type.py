"""customer.holder_type — 확장 여섯 항목의 셋째 (2026-09-15 임시 확정).

두 상품에서 방향이 반대다. KBYY 는 개인사업자 가입 불가, KBONE 은 포함이다.
"""

import json
from pathlib import Path

import _free
import blockers
import catalog
import validate
from engine import evaluate_rules
from resolver import resolve

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"


def _rules(cid):
    return json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]


def _dq(rules, holder):
    ctx = {"customer": {"holder_type": holder, "has_product": False, "age": 17}}
    return resolve(evaluate_rules(rules, ctx), "SUM").disqualified


def test_holder_type_is_an_enum_with_its_values():
    assert catalog.VARIABLES["customer.holder_type"]["type"] == "enum"
    assert "JOINT" in catalog.ENUM_VALUES["customer.holder_type"]


def test_unknown_value_fails_the_catalog_gate():
    r = {"rule_id": "X", "status": "OK", "source": {"quote": "x"},
         "condition": {"==": [{"var": "customer.holder_type"}, "개인"]},
         "effect": {"type": "DISQUALIFY"}}
    assert validate.check_catalog(r) != []


def test_prompt_candidates_pick_it_for_holder_clauses():
    v, _ = catalog.pick_candidates("※ 개인사업자 및 서류미제출 임의단체, 공동명의 가입 불가")
    assert "customer.holder_type" in v


def test_the_two_products_point_opposite_ways():
    kbyy, kbone = _rules("KBYY-S2-R01"), _rules("KBONE-S2-R01")
    assert _dq(kbyy, "SOLE_PROPRIETOR") and not _dq(kbone, "SOLE_PROPRIETOR")
    assert not _dq(kbyy, "INDIVIDUAL") and not _dq(kbone, "INDIVIDUAL")
    assert _dq(kbone, "CORPORATION")


def test_missing_holder_type_is_unknown_not_eligible():
    res = resolve(evaluate_rules(_rules("KBYY-S2-R23"), {"customer": {"has_product": False}}), "SUM")
    assert not res.disqualified and res.needs_review


def test_holder_type_no_longer_blocks():
    left = blockers.load()
    assert "KBONE-S2-R01" not in left and "KBYY-S2-R01" not in left
    assert all("명의유형" not in b for rs in left.values() for b in rs.values())


def test_free_sample_varies_holder_type_without_moving_other_values():
    s = _free.sample()
    assert len({c["customer"]["holder_type"] for c in s}) > 1
    assert s[0]["customer"]["age"] == _free.sample()[0]["customer"]["age"]
