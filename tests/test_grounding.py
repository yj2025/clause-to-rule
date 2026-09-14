"""⑨ 근거 축 — 생성물의 숫자가 조문에 있나.

`KBYY-S1-P01` 은 숫자가 하나도 없는 조문인데 생성물이 금리 0.5%p 와 면제횟수 100
을 만들어 내고 **관문 다섯을 전부 통과했다.** ①~⑤ 중 어느 것도 값의 출처를 묻지
않고, ⑥ 도 그 rule 이 어느 프로필에서도 발화하지 않으면 못 잡는다.
"""

import pytest

import grounding as G

CLAUSE = "만 19세 미만 고객에게 연 1.9%p 의 특별금리를 최대 100만원까지 제공합니다."


def rule(t="RATE_ADD", v=1.9, **kw):
    eff = {"type": t, "value": v}
    eff.update(kw)
    return {"rule_id": "R", "source": {"quote": "x"}, "condition": {}, "effect": eff}


@pytest.mark.parametrize("text,want", [
    ("연 1.9%p", 1.9), ("만 19세", 19.0), ("1,000,000원", 1000000.0),
    ("최대 100만원", 1000000.0), ("월 10회", 10.0), ("0.1%", 0.1),
])
def test_numbers_are_read(text, want):
    assert want in G.numbers_in(text)


def test_korean_unit_is_expanded():
    assert 1000000.0 in G.numbers_in("최대 100만원까지")


def test_billion_unit():
    assert 100000000.0 in G.numbers_in("1억원")


def test_no_numbers_is_empty():
    assert G.numbers_in("제한없음") == set()


# ── 근거 검사 ───────────────────────────────────────────────────────────
def test_a_value_from_the_clause_passes():
    assert G.check_rule(rule(v=1.9), CLAUSE) == []


def test_an_invented_value_is_caught():
    assert G.check_rule(rule(v=0.5), CLAUSE) != []


def test_the_message_lists_the_clause_numbers():
    assert "19" in G.check_rule(rule(v=0.5), CLAUSE)[0]


def test_a_limit_from_the_clause_passes():
    assert G.check_rule(rule("LIMIT_AMOUNT", 1000000), CLAUSE) == []


def test_zero_is_forgiven():
    # "불가" 를 한도 0 으로 옮긴 것일 수 있다. 보수적으로 봐준다
    assert G.check_rule(rule("LIMIT_AMOUNT", 0), CLAUSE) == []


def test_a_string_value_is_out_of_scope():
    assert G.check_rule(rule("FEE_WAIVE", "UNLIMITED", target="EBANK_TRANSFER"),
                        CLAUSE) == []


def test_a_numeric_fee_count_is_in_scope():
    assert G.check_rule(rule("FEE_WAIVE", 7, target="EBANK_TRANSFER"), CLAUSE) != []


def test_disqualify_has_no_value_to_check():
    assert G.check_rule({"effect": {"type": "DISQUALIFY"}}, CLAUSE) == []


def test_a_clause_with_no_numbers_catches_everything():
    errs = G.check_rule(rule(v=0.5), "상품특징 안내 문장입니다")
    assert errs and "없음" in errs[0]


def test_a_rule_without_effect_is_skipped():
    assert G.check_rule({"rule_id": "R"}, CLAUSE) == []


# ── 실제 라운드 ─────────────────────────────────────────────────────────
def test_the_known_invention_is_caught(root):
    """v6 의 KBYY-S1-P01 — 숫자 없는 조문에서 0.5%p 를 만들어 냈다."""
    import json
    d = {x["clause_id"]: x for x in
         json.loads((root / "results/results_v6.json").read_text("utf-8"))}
    texts = {c["id"]: c["text"] for c in
             json.loads((root / "data/corpus.json").read_text("utf-8"))}
    x = d["KBYY-S1-P01"]
    caught = [r for r in x["output"]["rules"]
              if G.check_rule(r, texts["KBYY-S1-P01"])]
    assert caught, "지어낸 수를 못 잡으면 이 축은 쓸모가 없다"


def test_that_invention_passed_every_existing_gate(root):
    """①~⑤ 는 이것을 전부 통과시켰다. 그래서 ⑨ 가 필요하다."""
    import json
    d = {x["clause_id"]: x for x in
         json.loads((root / "results/results_v6.json").read_text("utf-8"))}
    m = d["KBYY-S1-P01"]["final"]
    assert all(m[k] for k in
               ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok"))


@pytest.mark.parametrize("text,want", [
    ("2천만원", 20000000.0), ("5백만원", 5000000.0),
    ("3천원", 3000.0), ("1억원", 100000000.0),
])
def test_korean_compound_units(text, want):
    """예시가 스스로 검증기를 통과해야 한다 — v14 에서 "2천만원" 에 걸렸다."""
    assert want in G.numbers_in(text)


def test_every_fewshot_value_is_grounded():
    from schema import FEWSHOTS
    for clause, out in FEWSHOTS:
        for r in out["rules"]:
            assert G.check_rule(r, clause) == [], f"{r['rule_id']} 가 근거 축에 걸린다"


def test_the_axis_is_compared_on_matched_runs(root):
    """회차 수가 다른 라운드를 그냥 비교하면 틀린다.

    v1 은 3회차 138건, v9 이후는 1회차 46건이다. 같은 표에 나란히 놓으면
    분모가 세 배 다른 값을 견주게 된다. 이 축은 분모가 작아 차이가 크게 나온다.
    """
    import json
    import report
    d = json.loads((root / "results/results_v1.json").read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in
             json.loads((root / "data/corpus.json").read_text("utf-8"))}
    whole = G.audit(d, texts)["rate"]
    first = G.audit([x for x in d if x["run"] == 0], texts)["rate"]
    assert whole != first          # 실제로 다르다


def test_the_denominator_is_clauses_not_rules(root):
    """rule 을 분모로 두면 모델이 덜 내기만 해도 비율이 좋아진다.

    3회 반복으로 재 보니 rule 단위는 1회 기준 최대 ±46.5p 였다 —
    라운드 비교에 못 쓴다. 조문 단위는 ±2.5p 다.
    """
    import os, json
    os.chdir(root)
    texts = {x["id"]: x["text"] for x in
             json.loads((root / "data/corpus.json").read_text("utf-8"))}
    # 같은 조문에서 지어낸 수를 두 개 내도 조문 단위로는 한 건이다
    recs = [{"clause_id": "KBYY-S2-R03", "run": 0, "output": {"rules": [
        {"effect": {"type": "RATE_ADD", "value": 0.7, "unit": "PERCENT_POINT"}},
        {"effect": {"type": "RATE_ADD", "value": 1.3, "unit": "PERCENT_POINT"}},
    ]}}]
    a = G.audit(recs, texts)
    assert a["invented"] == 2, "rule 단위로는 두 건"
    assert a["bad_clauses"] == 1 and a["clauses"] == 1
    assert a["rate"] == 100.0, "조문 단위 비율이 주 지표다"
    assert a["rule_rate"] == 100.0


def test_making_fewer_rules_does_not_flatter_the_clause_rate(root):
    """rule 을 하나만 내도 그 조문은 여전히 '지어냈다' 로 센다."""
    import os, json
    os.chdir(root)
    texts = {x["id"]: x["text"] for x in
             json.loads((root / "data/corpus.json").read_text("utf-8"))}
    one = [{"clause_id": "KBYY-S2-R03", "run": 0, "output": {"rules": [
        {"effect": {"type": "RATE_ADD", "value": 0.7, "unit": "PERCENT_POINT"}}]}}]
    assert G.audit(one, texts)["rate"] == 100.0
