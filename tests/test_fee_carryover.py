"""FEE_WAIVE_NO_CARRYOVER — 확장 여섯 항목의 둘째 (2026-09-15 임시 확정).

"수수료면제 잔여횟수는 이월되지 않습니다" 를 담을 자리가 없어 세 rule 이
UNSUPPORTED 였다. FEE_WAIVE 에 횟수 0 을 적으면 면제 자체가 사라진다.
"""

import json
from pathlib import Path

import blockers
import catalog
import validate
from engine import evaluate_rules
from resolver import resolve

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"


def rule(**eff):
    return {"rule_id": "X-01", "status": "OK", "label": "x",
            "source": {"quote": "x"}, "condition": {},
            "effect": {"type": "FEE_WAIVE_NO_CARRYOVER", **eff}}


def test_needs_no_keys():
    assert catalog.EFFECTS["FEE_WAIVE_NO_CARRYOVER"] == ()


def test_without_target_passes_every_gate():
    r = rule()
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == []
    assert validate.check_executable(r) == []


def test_target_must_be_a_fee():
    assert validate.check_catalog(rule(target="ATM_TRANSFER")) == []
    assert validate.check_catalog(rule(target="NE_TIMES_TRIAL")) != []


def test_keeps_the_waiver_and_the_rate():
    """이월 금지는 면제를 없애지 않는다 — 횟수 0 과 다른 점이다."""
    waive = {"rule_id": "W-01", "status": "OK", "label": "w", "source": {"quote": "w"},
             "condition": {}, "effect": {"type": "FEE_WAIVE", "target": "ATM_TRANSFER",
                                         "value": 10}}
    res = resolve(evaluate_rules([waive, rule()], {}), "SUM", base_rate=0.1)
    assert {e["type"] for e in res.other_effects} == {"FEE_WAIVE", "FEE_WAIVE_NO_CARRYOVER"}
    assert res.final_rate_max == "0.10"


def test_gold_rules_are_ok():
    # KBYY-S5-R01-01 은 2026-11-05 사람 검토로 지웠다 — ONE통장 안내라 Young Youth 상품 범위 밖
    for cid, rid in (("KBONE-S2-R07", "KBONE-S2-R07-01"), ("KBONE-S2-R20", "KBONE-S2-R20-02")):
        rs = json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]
        r = next(x for x in rs if x["rule_id"] == rid)
        assert r["status"] == "OK" and r["effect"]["type"] == "FEE_WAIVE_NO_CARRYOVER"


def test_carryover_is_no_longer_a_blocker():
    left = blockers.load()
    assert "KBONE-S2-R07" not in left and "KBYY-S5-R01" not in left
    assert all("면제이월" not in b for rs in left.values() for b in rs.values())
