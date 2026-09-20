"""상품 코드 체계 — 2026-09-20.

「KB국민ONE통장으로 자동전환」 처럼 **다른 상품을 가리키는** 조문이 있다. 이름을 자유 문자열로
쓰면 ⑬ 이 막고 실행기도 못 읽는다. DB(`Products`)의 은행 채번 코드를 출처로 삼고 한글 키를 붙였다.
"""

import json
from pathlib import Path

import pytest

import blockers
import catalog
import prompt
import validate
from engine import evaluate_rules
from resolver import resolve

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"


def test_the_table_comes_from_the_db_and_keeps_its_hash():
    d = json.loads((ROOT / "data" / "products.json").read_text("utf-8"))
    assert d["_meta"]["db_sha256"] and d["_meta"]["bank"] == "KB국민은행"
    assert len(d["products"]) == len(catalog.PRODUCTS) == 74
    one = catalog.PRODUCTS["KB국민ONE통장"]
    assert one["code"] == "DP01000802" and one["category"] == "DEMAND_DEPOSIT"


def test_a_switch_rule_passes_every_gate_and_is_reported():
    r = {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
         "condition": {"==": [{"var": "customer.age"}, 19]},
         "effect": {"type": "PRODUCT_SWITCH_TO", "target": "KB국민ONE통장"}}
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == [] and validate.check_executable(r) == []
    res = resolve(evaluate_rules([r], {"customer": {"age": 19}}), "SUM", base_rate=0.1)
    assert [e["type"] for e in res.other_effects] == ["PRODUCT_SWITCH_TO"]
    assert res.final_rate_max == "0.10" and not res.disqualified


def test_an_invented_product_name_is_refused():
    r = {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
         "condition": {}, "effect": {"type": "PRODUCT_SWITCH_TO", "target": "KB없는통장"}}
    assert validate.check_catalog(r) != [] and validate.check_schema({"rules": [r]}) != []


def test_the_two_switch_rules_do_not_fire_together():
    """만 19세에 ONE 통장을 이미 가진 고객은 KB종합통장으로만 간다."""
    rs = json.loads((GOLD / "KBYY-S2-R04.json").read_text("utf-8"))["rules"]
    assert [r["status"] for r in rs] == ["OK", "OK"]
    for held, want in (([], "KB국민ONE통장"), (["KB국민ONE통장"], "KB종합통장")):
        ctx = {"customer": {"age": 19, "held_products": held}}
        got = [e["target"] for e in resolve(evaluate_rules(rs, ctx), "SUM").other_effects]
        assert got == [want], held
    none = resolve(evaluate_rules(rs, {"customer": {"age": 18, "held_products": []}}), "SUM")
    assert none.other_effects == []


def test_the_reserve_is_released_only_when_switching_out():
    r = next(x for x in json.loads((GOLD / "KBYY-S2-R11.json").read_text("utf-8"))["rules"]
             if x["rule_id"] == "KBYY-S2-R11-03")
    assert r["status"] == "OK" and r["effect"] == {"type": "STATE_CHANGE", "target": "RESERVE_OFF"}
    def ctx(direction):
        return {"_provided": ["events.PRODUCT_SWITCH"],
                "events": {"PRODUCT_SWITCH": [{"date": "2026-09-01", "direction": direction}]}}
    assert resolve(evaluate_rules([r], ctx("OUT")), "SUM").other_effects
    assert not resolve(evaluate_rules([r], ctx("IN")), "SUM").other_effects


def test_switch_direction_values_are_checked():
    bad = {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
           "condition": {"exists": {"event": "PRODUCT_SWITCH", "where": {"direction": ["BOTH"]}}},
           "effect": {"type": "STATE_CHANGE", "target": "RESERVE_OFF"}}
    assert validate.check_catalog(bad) != []


def test_prompt_offers_only_the_products_the_clause_names():
    text = "만 19세인 경우 「KB국민ONE통장」으로 자동전환"
    assert "[상품 키]" in prompt.build_user_prompt(text)
    assert "KB국민ONE통장" in catalog.pick_products(text)
    assert "KB스타통장" not in catalog.pick_products(text)
    assert "[상품 키]" not in prompt.build_user_prompt("만 19세 미만 고객만 가입 가능")


def test_the_switch_blocker_is_gone(root):
    import os
    os.chdir(root)
    everywhere = {b for rs in blockers.load().values() for bs in rs.values() for b in bs}
    assert "상품전환" not in everywhere, "카탈로그에 있는 것은 걸림돌이 아니다"


def test_online_termination_needs_a_demand_deposit_account():
    """사람 검토(9/14)가 «REQUIRE 의 value 가 자유 문장» 이라 막았던 자리.

    값이 아니라 조건으로 옮겼다 — 채널이 인터넷·모바일이고 본인명의 입출금 계좌가 없으면
    그 경로로는 해지할 수 없다. 영업점 해지에는 걸리지 않는다.
    """
    rs = json.loads((GOLD / "KBONE-S2-R12.json").read_text("utf-8"))["rules"]
    assert [r["status"] for r in rs] == ["OK"]
    def hit(channel, held):
        ctx = {"contract": {"channel": channel}, "customer": {"held_categories": held}}
        return [e["target"] for e in resolve(evaluate_rules(rs, ctx), "SUM").other_effects]
    assert hit("INTERNET", []) == ["TERMINATION"]
    assert hit("INTERNET", ["DEMAND_DEPOSIT"]) == []
    assert hit("BRANCH", []) == []
