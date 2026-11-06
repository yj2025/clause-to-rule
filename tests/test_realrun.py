"""실행기를 진짜 고객 데이터로 돌리는 시험.

합성 프로필은 데이터가 늘 갖춰져 있다고 가정한다. 진짜 데이터는 안 그렇다.
여기서 보는 것은 «조건식이 맞나» 가 아니라 **«지금 데이터로 돌아가기는 하나»** 다.
"""

import pytest

import realrun


needs_db = pytest.mark.skipif(not realrun.CUSTOMER_DB.exists(),
                              reason="고객 DB 가 없다")


@needs_db
def test_every_customer_becomes_a_context(root):
    import os
    os.chdir(root)
    rows = realrun.customers()
    assert rows, "고객이 하나도 없다"
    for aid, ctx, held in rows:
        assert ctx["customer"]["holder_type"], f"계정 {aid} 에 명의 유형이 없다"
        assert isinstance(ctx["customer"]["age"], int), f"계정 {aid} 나이"
        assert all(h in __import__("catalog").PRODUCTS for h in held), (
            f"계정 {aid} 의 보유 상품이 상품 키가 아니다: {held}")


@needs_db
def test_no_rule_crashes_on_real_data(root):
    """진짜 데이터로 돌렸을 때 `DslError` 가 나오면 안 된다.

    합성 프로필에서만 돌려 보면 «데이터가 없을 때» 경로를 한 번도 안 밟는다.
    DB 가 주지 않는 값이 실제로 얼마나 되는지는 `tools/datacheck.py` 가 센다.
    """
    import os
    from engine import evaluate_rules
    os.chdir(root)
    rules = realrun.gold_rules()
    assert rules, "정답 rule 이 없다"
    for aid, ctx, _ in realrun.customers():
        for j in evaluate_rules(rules, ctx):
            assert j.error is None, f"계정 {aid} · {j.rule_id}: {j.error}"


@needs_db
def test_missing_data_becomes_unknown_not_false(root):
    """«없다» 와 «모른다» 를 안 뭉갠다.

    DB 가 거래 내역을 안 주므로 이벤트를 보는 rule 은 **UNKNOWN** 이어야 한다.
    빈 리스트로 뭉개서 `NOT_MET` 을 내면 실적 없는 고객과 데이터 없는 고객이
    같은 답을 받는다 — 수수료 면제를 조용히 빼앗는 쪽이다.
    """
    import json
    import os
    import re
    from engine import evaluate_rules
    os.chdir(root)
    rules = realrun.gold_rules()
    event_rules = {r["rule_id"] for r in rules
                   if re.search(r'"event":', json.dumps(r, ensure_ascii=False))}
    assert event_rules, "이벤트를 보는 정답 rule 이 없다 — 시험이 무의미해졌다"
    aid, ctx, _ = realrun.customers()[0]
    for j in evaluate_rules(rules, ctx):
        if j.rule_id in event_rules:
            v = j.value.name if hasattr(j.value, "name") else str(j.value)
            assert v == "U", f"{j.rule_id} 가 데이터 없이 {v} 를 냈다"


@needs_db
def test_provided_keys_follow_datacheck(root):
    """«준다» 고 선언하는 목록이 `datacheck.BACKING` 과 따로 놀면 안 된다."""
    import os
    os.chdir(root)
    import datacheck
    keys = set(realrun.provided_keys())
    assert keys == {k for k, v in datacheck.BACKING.items() if v is not None}
    assert not any(k.startswith("events.") for k in keys), (
        "거래 내역 테이블이 없는데 이벤트를 준다고 선언했다")
