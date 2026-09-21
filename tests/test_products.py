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


# ── 2026-09-21 · 스냅샷을 만드는 코드가 생겼다 (`products.py`) ──────────────
def test_the_snapshot_still_matches_the_db(root):
    """DB 에 상품이 늘거나 줄면 이 시험이 먼저 운다.

    `catalog.py` 가 «`products.py` 로 만든다» 고 적고 있었는데 **그 파일이
    없었다.** 스냅샷을 어떻게 떴는지가 코드로 안 남으면 다시 뜰 때 조용히
    달라진다. 이제 코드가 있고, 이 시험이 그것을 DB 와 맞댄다.
    """
    import json
    import os
    import pytest
    os.chdir(root)
    import products
    if not products.DB.exists():
        pytest.skip(f"상품 DB 가 없다: {products.DB}")
    have = json.loads(products.OUT.read_text("utf-8"))["products"]
    now = products.snapshot()
    assert set(now) == set(have), (
        f"DB 와 어긋난다 — 새로 생김 {sorted(set(now) - set(have))[:5]} · "
        f"없어짐 {sorted(set(have) - set(now))[:5]}. "
        "`python products.py --write` 로 다시 떠라")


def test_every_product_carries_a_db_id(root):
    """이름이 아니라 `product_id` 로 잇는다.

    `Customer_Subscriptions` 는 **이름 스냅샷을 따로 저장한다** — 상품 이름이
    바뀌기 때문이다. 이름으로 맞추면 그때 조용히 끊긴다.
    """
    import json
    import os
    os.chdir(root)
    import products
    have = json.loads(products.OUT.read_text("utf-8"))["products"]
    missing = [k for k, v in have.items() if not isinstance(v.get("id"), int)]
    assert not missing, f"id 가 없는 상품: {missing[:5]}"
    ids = [v["id"] for v in have.values()]
    assert len(set(ids)) == len(ids), "id 가 겹친다"


def test_a_customer_holding_resolves_to_a_product_key(root):
    """고객 DB 의 가입 이력이 내 상품 키로 풀리는지 **끝까지** 확인한다.

    `customer.held_products` 는 상품 키의 목록이다. DB 쪽 `product_id` 가
    이 목록에 못 닿으면 그 변수는 늘 비어 있고, 조건은 조용히 거짓이 된다.
    """
    import json
    import os
    import sqlite3
    import pytest
    os.chdir(root)
    import datacheck
    import products
    if not (datacheck.DB.exists() and products.DB.exists()):
        pytest.skip("DB 가 없다")
    by_id = {v["id"]: k
             for k, v in json.loads(products.OUT.read_text("utf-8"))["products"].items()}
    with sqlite3.connect(f"file:{datacheck.DB}?mode=ro", uri=True) as c:
        rows = c.execute("select product_id, product_name "
                         "  from Customer_Subscriptions where bank_id = 1").fetchall()
    if not rows:
        pytest.skip("KB 가입 이력이 없다")
    lost = [(pid, name) for pid, name in rows if pid not in by_id]
    assert not lost, f"상품 키로 못 푸는 가입 이력: {lost}"
