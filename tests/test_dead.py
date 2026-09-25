"""⑯ 셈이 안 맞는 집계 비교 — ⑭(헛조건)의 **안 보이던 절반**.

⑭ 는 「언제나 참」만 본다. 「언제나 거짓」인 조건은 아무도 안 봤다.
v50 에서 연산자가 `>=` 에서 `<=` 로 뒤집히며 죽은 조건이 헛조건이 되자
⑭ 가 갑자기 올랐고, **처방의 부작용으로 읽힐 뻔했다.**
"""


def _rule(cond):
    return {"rule_id": "T-1", "status": "OK", "label": "t",
            "source": {"quote": "x"}, "condition": cond,
            "effect": {"type": "RESTRICT", "target": "ALL_TRANSACTIONS"}}


def _window(a, b):
    return {"month_range": {
        "from": {"anchor": "contract.reference_date", "offset_months": a,
                 "day": "first"},
        "to": {"anchor": "contract.reference_date", "offset_months": b,
               "day": "last"}}}


def test_gold_is_clean():
    """**새 지표는 반드시 정답에 먼저 돌린다.**

    처음에는 「표본 문맥에서 한 번도 참이 아니면 죽은 조건」으로 짰다가
    정답에서 3개가 걸렸다 (`customer.age == 19` 처럼 표본이 그 값을 안 가진
    경우). 표본이 정의역을 다 덮지 않으므로 그 방식은 과다 검출이다.
    그래서 **산술로 증명되는 것만** 센다.
    """
    import json
    import pathlib

    import dead
    root = pathlib.Path(__file__).resolve().parent.parent
    recs = [{"clause_id": p.stem, "run": 0,
             "output": json.loads(p.read_text("utf-8"))}
            for p in sorted((root / "data" / "gold").glob("*.json"))
            if not p.name.startswith("_")]
    a = dead.audit(recs)
    assert a["checked"] > 0
    assert a["bad"] == 0, f"정답에서 걸렸다: {a['examples']}"


def test_it_catches_a_threshold_bigger_than_the_window():
    """한 달짜리 창에서 서로 다른 달은 많아야 하나다."""
    import dead
    cond = {">=": [{"count_distinct_months": {"event": "WITHDRAWAL",
                                              "within": _window(-1, -1)}}, 12]}
    assert dead.check_rule(_rule(cond)), "될 수 없는 비교를 못 잡는다"


def test_it_catches_the_always_true_side_too():
    import dead
    cond = {"<=": [{"count_distinct_months": {"event": "WITHDRAWAL",
                                              "within": _window(-1, -1)}}, 12]}
    assert dead.check_rule(_rule(cond)), "언제나 참인 비교를 못 잡는다"


def test_a_window_that_fits_is_not_flagged():
    """12달짜리 창에서 `>= 12` 는 될 수 있다 — 헛잡으면 안 된다."""
    import dead
    cond = {">=": [{"count_distinct_months": {"event": "WITHDRAWAL",
                                              "within": _window(-12, -1)}}, 12]}
    assert not dead.check_rule(_rule(cond)), f"헛잡는다: {dead.check_rule(_rule(cond))}"


def test_the_defect_predates_v50():
    """**v50 이 이 결함을 만들지 않았다.** 같은 여섯이 v49 에도 있다 —
    셋이 「될 수 없다」에서 「언제나 참」으로 뒤집혔을 뿐이다."""
    import json
    import pathlib

    import dead
    root = pathlib.Path(__file__).resolve().parent.parent
    n = {}
    for t in ("v49", "v50"):
        r = json.loads((root / "results" / f"results_{t}.json").read_text("utf-8"))
        n[t] = dead.audit(r)["bad"]
    assert n["v49"] == n["v50"] == 6, n
