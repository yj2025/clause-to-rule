"""SERVICE_PROVIDE — 확장 여섯 항목의 첫째 (2026-09-15 임시 확정).

제휴서비스는 금리도 수수료도 한도도 아닌 급부다. 자리가 없어 KBYY-S3 의
세 조문이 통째로 UNSUPPORTED 였다.
"""

import json
from pathlib import Path

import blockers
import catalog
import prompt
import validate
from engine import evaluate_rules
from resolver import resolve

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"


def rule(**eff):
    return {"rule_id": "X-01", "status": "OK", "label": "x",
            "source": {"quote": "x"}, "condition": {},
            "effect": {"type": "SERVICE_PROVIDE", "target": "NE_TIMES_TRIAL",
                       "value": 1, "unit": "회", **eff}}


def test_service_provide_needs_target_value_unit():
    assert catalog.EFFECTS["SERVICE_PROVIDE"] == ("target", "value", "unit")


def test_valid_rule_passes_every_gate():
    r = rule()
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == []
    assert validate.check_executable(r) == []


def test_fee_target_is_not_a_service():
    assert validate.check_catalog(rule(target="EBANK_TRANSFER")) != []


def test_value_must_be_a_number():
    """원칙 4 — effect 의 value 에 자유 문자열을 쓰지 않는다."""
    assert validate.check_executable(rule(value="무료체험 1회")) != []


def test_renewable_is_optional_and_boolean():
    assert validate.check_schema({"rules": [rule(unit="년", renewable=True)]}) == []
    assert validate.check_schema({"rules": [rule(renewable="yes")]}) != []


def test_goes_to_other_effects_and_leaves_the_rate():
    res = resolve(evaluate_rules([rule()], {}), "SUM", base_rate=0.1)
    assert res.other_effects[0]["type"] == "SERVICE_PROVIDE"
    assert res.final_rate_max == "0.10"


def test_prompt_lists_services_only_for_service_clauses():
    assert "[제휴서비스 대상]" in prompt.build_user_prompt("온라인수강권 1개월 및 영자신문 2회")
    assert "[제휴서비스 대상]" not in prompt.build_user_prompt("만 19세 미만 고객")


def _gold(cid):
    return json.loads((GOLD / f"{cid}.json").read_text("utf-8"))


def test_partner_service_clauses_are_now_ok():
    for cid in ("KBYY-S3-R01", "KBYY-S3-R02", "KBYY-S3-R05"):
        rs = _gold(cid)["rules"]
        assert rs and all(r["status"] == "OK" for r in rs), cid


def test_age_band_separates_profiles():
    rs = _gold("KBYY-S3-R05")["rules"]
    young = resolve(evaluate_rules(rs, {"customer": {"age": 17}}), "SUM")
    adult = resolve(evaluate_rules(rs, {"customer": {"age": 19}}), "SUM")
    assert len(young.other_effects) == 2 and adult.other_effects == []


def test_performance_duty_still_blocked_by_the_change_event():
    """이행책임은 효과가 생겨도 '축소·변경' 사건을 가리킬 변수가 없다."""
    b = blockers.load()["KBYY-S3-R04"]
    assert all(v == {"서비스변경"} for v in b.values())
