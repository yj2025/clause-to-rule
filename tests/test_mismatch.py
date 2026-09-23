"""⑮ 타입이 안 맞는 비교.

**이 지표가 있는 이유는 관문 다섯이 이것을 통과시키기 때문이다.**
`KBYY-S2-R18` 이 압류 상태를 물으려고 저금통 적립액(원)을 문자열 목록과
견준다. 이름은 카탈로그에 있으니 ③ 이 통과시키고, 실행하면 그냥 False 라
⑤ 도 통과시킨다.
"""


def test_the_five_gates_really_do_miss_it():
    """**이 시험이 깨지면 ⑮ 는 필요 없어진 것이다.**

    관문이 잡게 되면 이 축은 지워도 된다. 그때까지는 따로 센다.
    """
    import validate as V
    rule = {"rule_id": "T-1", "status": "OK", "label": "t",
            "source": {"quote": "x"},
            "condition": {"in": [{"var": "account.reserved_amount"},
                                 ["SEIZED", "PRESERVED_SEIZED"]]},
            "effect": {"type": "RESTRICT", "target": "ALL_TRANSACTIONS"}}
    r = V.score_record({"rules": [rule]}, "x 조문 본문 x")
    for k in ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok"):
        assert r[k], f"{k} 가 잡는다 — ⑮ 를 다시 봐야 한다"


def test_gold_is_clean():
    """**새 지표는 반드시 정답에 먼저 돌린다.**

    ⑪ 이 정답에서 34건을 내 지표가 틀렸던 것을 찾은 적이 있다 (2026-09-21).
    """
    import json
    import pathlib

    import mismatch
    root = pathlib.Path(__file__).resolve().parent.parent
    recs = [{"clause_id": p.stem, "run": 0,
             "output": json.loads(p.read_text("utf-8"))}
            for p in sorted((root / "data" / "gold").glob("*.json"))
            if not p.name.startswith("_")]
    a = mismatch.audit(recs)
    assert a["checked"] > 0, "정답에 비교가 하나도 없다 — 지표가 아무것도 안 보고 있다"
    assert a["bad"] == 0, f"정답에서 걸렸다: {a['kinds']}"


def test_it_catches_each_shape():
    import mismatch
    cases = [
        ({"in": [{"var": "account.reserved_amount"}, ["SEIZED"]]}, "수 변수 in 문자열 목록"),
        ({"==": [{"var": "account.reserved_amount"}, "SEIZED"]}, "수 변수 == 문자열"),
        ({">": [{"var": "customer.holder_type"}, 0]}, "enum 변수 > 수"),
        ({"==": [{"var": "customer.is_youth"}, "true"]}, "bool 변수 == 문자열"),
    ]
    for cond, why in cases:
        assert mismatch.find(cond), f"못 잡는다: {why}"


def test_it_does_not_cry_on_good_conditions():
    import mismatch
    good = [
        {">": [{"var": "account.reserved_amount"}, 0]},
        {"==": [{"var": "customer.has_product"}, True]},
        {"==": [{"var": "customer.holder_type"}, "JOINT"]},
        {"and": [{">=": [{"var": "contract.term_months"}, 6]},
                 {"==": [{"var": "customer.is_youth"}, True]}]},
        {">=": [{"count_distinct_months": {"event": "DEPOSIT"}}, 6]},
    ]
    for cond in good:
        assert not mismatch.find(cond), f"헛잡는다: {cond}"


def test_enum_values_outside_the_catalog_are_caught():
    """enum 변수를 **목록에 없는 값**과 견주는 것도 같은 병이다."""
    import catalog
    import mismatch
    vals = catalog.VARIABLES["customer.holder_type"].get("values")
    if not vals:
        return
    assert mismatch.find({"==": [{"var": "customer.holder_type"}, "NO_SUCH_VALUE"]})
    assert not mismatch.find({"==": [{"var": "customer.holder_type"}, vals[0]]})
