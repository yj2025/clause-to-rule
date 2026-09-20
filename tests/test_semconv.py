"""의미 규칙 → 실행 규칙 변환기 (`semconv.py`).

대응표는 여기서 손으로 만든 작은 것을 쓴다. 실제 대응표의 판정이 옳은지는
시험이 아니라 사람 검토의 몫이다 — 여기서는 **구조 변환이 뜻을 보존하는지**만 본다.
옮긴 규칙은 실행기와 합산기에 실제로 넣어 고객별 결과까지 확인한다.
"""

import semconv
from engine import evaluate_rules
from resolver import resolve
from semconv import Lexicon, convert_record, convert_unit, parse_range

TRUE = {"type": "literal", "value": True, "value_type": "boolean"}


def pred(surface, op="EQ", right=TRUE):
    return {"kind": "predicate", "left": {"surface": surface}, "operator": op, "right": right}


def ce(cond, *effects, **extra):
    return {"form": "CONDITIONAL_EFFECT", "evidence": [{"text": "원문"}],
            "body": {"condition": cond, "effects": list(effects)}, **extra}


def lex(**tables):
    return Lexicon(tables)


# ── 구간 읽기 ───────────────────────────────────────────────────────────
def test_range_with_tilde_reads_years_as_months():
    assert parse_range("6개월 ~ 5년") == {"kind": "months", "lo": 6, "lo_inc": True,
                                          "hi": 60, "hi_inc": True}


def test_range_open_upper_bound_is_exclusive_for_mimman():
    r = parse_range("1년~2년미만")
    assert (r["lo"], r["hi"], r["hi_inc"]) == (12, 24, False)


def test_range_reads_korean_amount_units():
    assert parse_range("20만원 이상")["lo"] == 200_000
    assert parse_range("3백만원 이하의 금액까지") is None       # "의 금액" 이 남는다
    assert parse_range("10억원 이하")["hi"] == 1_000_000_000


def test_range_refuses_leftover_words():
    # "만기후" 는 대상에 관한 말이다. 수만 떼어 읽으면 만기 전 기간으로 뜻이 바뀐다
    assert parse_range("만기후 1개월 이내") is None


def test_range_refuses_mixed_units():
    assert parse_range("30일 이상 1년 이내") is None


# ── 조건부 효과 ─────────────────────────────────────────────────────────
def test_boolean_condition_and_rate_effect_become_one_executable_rule():
    unit = ce(pred("급여이체 실적이 있는 경우"),
              {"type": "ADD_VALUE", "target": {"surface": "급여이체 우대금리"},
               "value": {"type": "literal", "value": 0.3, "unit": "PERCENT_POINT"}})
    L = lex(cond={"급여이체 실적이 있는 경우": {"dsl": {"exists": {"event": "SALARY_TRANSFER"}}}},
            target={"ADD_VALUE::급여이체 우대금리": {"effect": "RATE_ADD"}})
    res = convert_unit(unit, L)
    assert res["outcome"] == "CONVERTED"
    (rule,) = res["rules"]
    assert rule["effect"] == {"type": "RATE_ADD", "value": 0.3, "unit": "%p"}

    paid = {"_provided": ["events.SALARY_TRANSFER"], "events": {"SALARY_TRANSFER": [{"date": "2026-08-25"}]}}
    unpaid = {"_provided": ["events.SALARY_TRANSFER"], "events": {"SALARY_TRANSFER": []}}
    unknown = {"_provided": []}
    assert resolve(evaluate_rules(res["rules"], paid), base_rate=0.1).final_rate_max == "0.40"
    assert resolve(evaluate_rules(res["rules"], unpaid), base_rate=0.1).final_rate_max == "0.10"
    r = resolve(evaluate_rules(res["rules"], unknown), base_rate=0.1)
    assert (r.final_rate_min, r.final_rate_max, r.needs_review) == ("0.10", "0.40", True)


def test_false_literal_negates_the_condition():
    unit = ce(pred("미성년자", right={"type": "literal", "value": False, "value_type": "boolean"}),
              {"type": "PROHIBIT", "target": {"surface": "담보제공"}})
    L = lex(cond={"미성년자": {"dsl": {"<": [{"var": "customer.age"}, 19]}}},
            target={"PROHIBIT::담보제공": {"effect": "RESTRICT", "target": "PLEDGE"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert rule["condition"] == {"not": {"<": [{"var": "customer.age"}, 19]}}


def test_or_group_keeps_its_logic():
    unit = ce({"kind": "group", "op": "OR", "children": [pred("카드 실적"), pred("자동이체 실적")]},
              {"type": "SET_VALUE", "target": {"surface": "전자금융 이체수수료"},
               "value": {"type": "literal", "value": 0}})
    L = lex(cond={"카드 실적": {"dsl": {"exists": {"event": "CARD_USAGE"}}},
                  "자동이체 실적": {"dsl": {"exists": {"event": "AUTO_TRANSFER"}}}},
            target={"SET_VALUE::전자금융 이체수수료": {"effect": "FEE_WAIVE", "target": "EBANK_TRANSFER"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert list(rule["condition"]) == ["or"]
    assert rule["effect"] == {"type": "FEE_WAIVE", "target": "EBANK_TRANSFER", "value": "UNLIMITED"}


def test_every_blocker_is_collected_not_just_the_first():
    unit = ce(pred("모르는 조건"), {"type": "PAY", "target": {"surface": "이자"}},
              {"type": "ADD_VALUE", "target": {"surface": "없는 대상"},
               "value": {"type": "literal", "value": 1, "unit": "PERCENT_POINT"}})
    L = lex(target={"ADD_VALUE::없는 대상": {"gap": "무슨 우대금리 변수 없음", "layer": "VOCAB",
                                          "family": "금리·이율값"}})
    res = convert_unit(unit, L)
    assert res["outcome"] == "BLOCKED"
    assert res["layers"] == ["SCOPE", "VOCAB", "UNLABELED"]
    assert res["n_effects"] == res["n_blocked_effects"] == 2


def test_rate_from_posted_reference_is_not_invented():
    unit = ce({"kind": "always"},
              {"type": "APPLY_VALUE", "target": {"surface": "만기후이율"},
               "value": {"type": "reference", "surface": "영업점에 게시한 만기후이율"}})
    L = lex(target={"APPLY_VALUE::만기후이율": {"effect": "RATE_OVERRIDE"}})
    res = convert_unit(unit, L)
    assert res["rules"] == [] and res["layers"] == ["STRUCTURE"]


def test_procedure_is_not_a_rule_rather_than_blocked():
    unit = ce({"kind": "always"}, {"type": "ALLOW", "target": {"surface": "가입"}})
    L = lex(target={"ALLOW::가입": {"not_rule": "절차: 거래 경로"}})
    res = convert_unit(unit, L)
    assert res["outcome"] == "NOT_A_RULE" and res["not_rule"] == ["절차: 거래 경로"]


def test_unconditional_disqualify_is_refused():
    unit = ce({"kind": "always"}, {"type": "PROHIBIT", "target": {"surface": "가입"}})
    L = lex(target={"PROHIBIT::가입": {"effect": "DISQUALIFY"}})
    assert convert_unit(unit, L)["layers"] == ["STRUCTURE"]


def test_cancel_modifier_is_anded_as_negation():
    unit = ce(pred("카드 실적"), {"type": "SET_VALUE", "target": {"surface": "수수료"},
                                 "value": {"type": "literal", "value": 0}},
              modifiers=[{"type": "OVERRIDE", "operation": "CANCEL_EFFECT", "surface": "중도해지 계좌 제외"}])
    L = lex(cond={"카드 실적": {"dsl": {"exists": {"event": "CARD_USAGE"}}}},
            target={"SET_VALUE::수수료": {"effect": "FEE_WAIVE", "target": "EBANK_TRANSFER"}},
            modifier={"중도해지 계좌 제외": {"and_not": {"==": [{"var": "contract.termination_type"}, "EARLY"]}}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert rule["condition"]["and"][1] == {"not": {"==": [{"var": "contract.termination_type"}, "EARLY"]}}


def test_conflicting_windows_in_one_unit_are_caught():
    w1 = {"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -1, "day": "first"},
                          "to": {"anchor": "contract.reference_date", "offset_months": -1, "day": "last"}}}
    w3 = {"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -3, "day": "first"},
                          "to": {"anchor": "contract.reference_date", "offset_months": -1, "day": "last"}}}
    unit = ce({"kind": "group", "op": "AND", "children": [pred("전월 카드"), pred("3개월 카드")]},
              {"type": "SET_VALUE", "target": {"surface": "수수료"}, "value": {"type": "literal", "value": 0}})
    dsl = {"exists": {"event": "CARD_USAGE", "within": {"ref": "$window"}}}
    L = lex(cond={"전월 카드": {"dsl": dsl, "let": {"window": w1}},
                  "3개월 카드": {"dsl": dsl, "let": {"window": w3}}},
            target={"SET_VALUE::수수료": {"effect": "FEE_WAIVE", "target": "EBANK_TRANSFER"}})
    assert "CONVERTER" in convert_unit(unit, L)["layers"]


# ── 직접 제약 ───────────────────────────────────────────────────────────
def test_range_constraint_becomes_disqualify_outside_the_range():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "계약기간 6개월 ~ 5년"}],
            "body": {"constraint": {"kind": "range", "surface": "6개월 ~ 5년"},
                     "applies_to": {"surface": "계약기간"}}}
    L = lex(subject={"계약기간": {"var": "contract.term_months", "unit": "months",
                                  "violation": "DISQUALIFY"}})
    res = convert_unit(unit, L)
    assert res["outcome"] == "CONVERTED"
    (rule,) = res["rules"]
    assert rule["effect"] == {"type": "DISQUALIFY"}
    for months, out in ((3, True), (6, False), (60, False), (61, True)):
        r = resolve(evaluate_rules(res["rules"], {"contract": {"term_months": months}}))
        assert r.disqualified is out, months


def test_boolean_constraint_uses_requirement():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "1인 1계좌"}],
            "body": {"constraint": pred("1인 1계좌")}}
    L = lex(constraint={"1인 1계좌": {"requirement": {"==": [{"var": "customer.has_product"}, False]},
                                     "violation": "DISQUALIFY"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert resolve(evaluate_rules([rule], {"customer": {"has_product": True}})).disqualified
    assert not resolve(evaluate_rules([rule], {"customer": {"has_product": False}})).disqualified


def test_false_boolean_constraint_negates_requirement():
    # "공동명의로 가입 == false" — 공동명의면 가입 불가. 대응표 요건은 표현이 참이라는 뜻이다
    FALSE = {"type": "literal", "value": False, "value_type": "boolean"}
    L = lex(constraint={"공동명의로 가입": {"requirement": {"==": [{"var": "customer.holder_type"}, "JOINT"]},
                                          "violation": "DISQUALIFY"}})
    for right, joint_out in ((FALSE, True), (TRUE, False)):
        unit = {"form": "CONSTRAINT", "evidence": [{"text": "공동명의 가입 불가"}],
                "body": {"constraint": pred("공동명의로 가입", right=right)}}
        (rule,) = convert_unit(unit, L)["rules"]
        for holder, out in (("JOINT", joint_out), ("INDIVIDUAL", not joint_out)):
            r = resolve(evaluate_rules([rule], {"customer": {"holder_type": holder}}))
            assert r.disqualified is out, (right["value"], holder)


def test_non_boolean_value_in_boolean_constraint_is_blocked():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "x"}],
            "body": {"constraint": pred("1인 1계좌", right={"type": "literal", "value": "Y",
                                                         "value_type": "boolean"})}}
    L = lex(constraint={"1인 1계좌": {"requirement": {"==": [{"var": "customer.has_product"}, False]},
                                     "violation": "DISQUALIFY"}})
    res = convert_unit(unit, L)
    assert res["rules"] == [] and res["layers"] == ["STRUCTURE"]


def test_upper_limit_constraint_becomes_limit_amount():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "최고 100만원"}],
            "body": {"constraint": pred("저금통 한도", "LE",
                                        {"type": "literal", "value": 1000000, "unit": "KRW"})}}
    L = lex(subject={"저금통 한도": {"var": "account.reserved_amount", "unit": "won",
                                    "violation": "LIMIT_AMOUNT"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert rule["effect"] == {"type": "LIMIT_AMOUNT", "value": 1000000}


def test_unit_mismatch_is_a_structure_gap_not_a_silent_conversion():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "30일"}],
            "body": {"constraint": pred("예치기간", "GE", {"type": "literal", "value": 30, "unit": "DAY"})}}
    L = lex(subject={"예치기간": {"var": "contract.term_months", "unit": "months", "violation": "DISQUALIFY"}})
    res = convert_unit(unit, L)
    assert res["rules"] == [] and res["layers"] == ["STRUCTURE"]


def test_in_set_maps_members():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "가입대상"}],
            "body": {"constraint": pred("가입대상", "IN", {"type": "set", "values": [
                {"surface": "실명의 개인"}, {"surface": "개인사업자"}]})}}
    L = lex(subject={"가입대상": {"var": "customer.holder_type", "unit": "enum", "violation": "DISQUALIFY"}},
            member={"실명의 개인": {"value": "INDIVIDUAL"}, "개인사업자": {"value": "SOLE_PROPRIETOR"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert rule["condition"] == {"not": {"in": [{"var": "customer.holder_type"},
                                                ["INDIVIDUAL", "SOLE_PROPRIETOR"]]}}
    assert resolve(evaluate_rules([rule], {"customer": {"holder_type": "JOINT"}})).disqualified


# ── 선택 규칙 ───────────────────────────────────────────────────────────
def _shopping():
    def branch(lo, rate):
        return {"match": {"kind": "range", "surface": f"{lo}만원 이상"},
                "effects": [{"type": "ADD_VALUE", "target": {"surface": "쇼핑 우대금리"},
                             "value": {"type": "literal", "value": rate, "unit": "PERCENT_POINT"}}]}
    return {"form": "SELECTOR", "evidence": [{"text": "쇼핑"}],
            "body": {"selector": {"surface": "잔액"}, "mode": "BUCKET",
                     "branches": [branch(20, 0.5), branch(30, 1.0)],
                     "selection_policy": "HIGHEST_MATCHING"}}


def test_highest_matching_thresholds_do_not_double_count():
    L = lex(subject={"잔액": {"var": "account.balance", "unit": "won"}},
            target={"ADD_VALUE::쇼핑 우대금리": {"effect": "RATE_ADD"}})
    res = convert_unit(_shopping(), L)
    assert res["outcome"] == "CONVERTED" and len(res["rules"]) == 2
    for bal, rate in ((100_000, "0.10"), (250_000, "0.60"), (350_000, "1.10")):
        got = resolve(evaluate_rules(res["rules"], {"account": {"balance": bal}}), base_rate=0.1)
        assert got.final_rate_max == rate, bal


def test_slice_mode_is_structure_gap():
    unit = _shopping()
    unit["body"]["mode"] = "SLICE"
    res = convert_unit(unit, lex())
    assert res["layers"] == ["STRUCTURE"] and res["n_blocked_effects"] == 2


# ── 레코드 ──────────────────────────────────────────────────────────────
def test_no_executable_rule_matches_empty_array():
    assert convert_record({"status": "NO_EXECUTABLE_RULE", "rule_units": []}, lex())["outcome"] == "EMPTY"


def test_record_unresolved_is_source():
    rec = {"status": "UNRESOLVED", "rule_units": [],
           "unresolved": [{"type": "MISSING_EVIDENCE", "surface": "아래 표 참조"}]}
    out = convert_record(rec, lex())
    assert out["outcome"] == "SOURCE" and out["blockers"][0]["layer"] == "SOURCE"


def test_families_are_fixed():
    assert "기타" in semconv.FAMILIES and len(set(semconv.FAMILIES)) == len(semconv.FAMILIES)


def test_procedural_condition_makes_the_unit_not_a_rule():
    unit = ce(pred("고객센터 해지"), {"type": "ALLOW", "target": {"surface": "해지"}})
    L = lex(cond={"고객센터 해지": {"not_rule": "절차: 거래 경로"}},
            target={"ALLOW::해지": {"not_rule": "절차: 거래 경로"}})
    res = convert_unit(unit, L)
    assert res["outcome"] == "NOT_A_RULE" and res["n_blocked_effects"] == 0


def test_target_entry_can_carry_its_own_condition():
    unit = ce({"kind": "always"}, {"type": "PROHIBIT", "target": {"surface": "공동명의 가입"}})
    L = lex(target={"PROHIBIT::공동명의 가입": {
        "effect": "DISQUALIFY", "and": {"==": [{"var": "customer.holder_type"}, "JOINT"]}}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert resolve(evaluate_rules([rule], {"customer": {"holder_type": "JOINT"}})).disqualified
    assert not resolve(evaluate_rules([rule], {"customer": {"holder_type": "INDIVIDUAL"}})).disqualified


def test_one_account_per_person_count_maps_to_has_product_only_for_that_count():
    def unit(n):
        return {"form": "CONSTRAINT", "evidence": [{"text": "1인 1계좌"}],
                "body": {"constraint": pred("1인 1계좌", "LE",
                                            {"type": "literal", "value": n, "unit": "ACCOUNT_COUNT"})}}
    L = lex(subject={"1인 1계좌": {"requirement": {"==": [{"var": "customer.has_product"}, False]},
                                  "when": {"operator": "LE", "value": 1}, "violation": "DISQUALIFY"}})
    (rule,) = convert_unit(unit(1), L)["rules"]
    assert resolve(evaluate_rules([rule], {"customer": {"has_product": True}})).disqualified
    assert convert_unit(unit(3), L)["layers"] == ["STRUCTURE"]


def test_unconverted_modifier_withholds_every_rule_of_the_unit():
    # 예외를 못 옮긴 채 면제를 내보내면 예외 대상까지 면제받는다
    unit = ce({"kind": "always"}, {"type": "SET_VALUE", "target": {"surface": "수수료"},
                                   "value": {"type": "literal", "value": 0}},
              modifiers=[{"type": "OVERRIDE", "operation": "CANCEL_EFFECT", "surface": "제휴 ATM 제외"}])
    L = lex(target={"SET_VALUE::수수료": {"effect": "FEE_WAIVE", "target": "EBANK_TRANSFER"}},
            modifier={"제휴 ATM 제외": {"gap": "ATM 운영 주체 구분 없음", "layer": "VOCAB", "family": "수수료"}})
    res = convert_unit(unit, L)
    assert res["rules"] == [] and res["outcome"] == "BLOCKED" and res["n_blocked_effects"] == 1


def test_boolean_when_is_compared_as_a_boolean_not_a_number():
    unit = {"form": "CONSTRAINT", "evidence": [{"text": "개인사업자, 공동명의 가입 불가"}],
            "body": {"constraint": pred("개인사업자, 공동명의", "NE",
                                        {"type": "literal", "value": True, "value_type": "boolean"})}}
    req = {"not": {"in": [{"var": "customer.holder_type"}, ["SOLE_PROPRIETOR", "JOINT"]]}}
    L = lex(subject={"개인사업자, 공동명의": {"requirement": req, "when": {"operator": "NE", "value": True},
                                           "violation": "DISQUALIFY"}})
    (rule,) = convert_unit(unit, L)["rules"]
    assert resolve(evaluate_rules([rule], {"customer": {"holder_type": "JOINT"}})).disqualified
    assert not resolve(evaluate_rules([rule], {"customer": {"holder_type": "INDIVIDUAL"}})).disqualified
