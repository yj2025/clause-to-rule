import pytest

import catalog
import validate as V
from schema import FEWSHOTS, FEWSHOT_CLAUSE, FEWSHOT_OUTPUT

CLAUSE = "만 19세 미만 고객에게 연 1.9%p 의 특별금리를 제공합니다."


def rule(**kw):
    base = {"rule_id": "R-01", "source": {"quote": "연 1.9%p 의 특별금리를 제공합니다"},
            "condition": {"<": [{"var": "customer.age"}, 19]},
            "effect": {"type": "RATE_ADD", "value": 1.9, "unit": "%p"}}
    base.update(kw)
    return base


# ── few-shot 은 검증기를 통과해야 한다 ──────────────────────────────────
@pytest.mark.parametrize("i", list(range(len(FEWSHOTS))))
def test_fewshot_passes_schema(i):
    assert V.check_schema(FEWSHOTS[i][1]) == []


@pytest.mark.parametrize("i", list(range(len(FEWSHOTS))))
def test_fewshot_passes_catalog(i):
    for r in FEWSHOTS[i][1]["rules"]:
        assert V.check_catalog(r) == []


@pytest.mark.parametrize("i", list(range(len(FEWSHOTS))))
def test_fewshot_passes_executable(i):
    for r in FEWSHOTS[i][1]["rules"]:
        assert V.check_executable(r) == []


@pytest.mark.parametrize("i", list(range(len(FEWSHOTS))))
def test_fewshot_passes_quote(i):
    clause, out = FEWSHOTS[i]
    for r in out["rules"]:
        assert V.check_quote(r, clause) == []


def test_fewshot_validator_agrees_with_iter_errors():
    assert not list(V._validator.iter_errors(FEWSHOT_OUTPUT))


# ── ② 스키마 ────────────────────────────────────────────────────────────
def test_schema_rejects_missing_rules_key():
    assert V.check_schema({}) != []


def test_schema_rejects_unknown_top_key():
    assert V.check_schema({"rules": [], "extra": 1}) != []


def test_schema_rejects_unknown_rule_key():
    assert V.check_schema({"rules": [rule(extra=1)]}) != []


def test_schema_rejects_missing_effect():
    r = rule()
    del r["effect"]
    assert V.check_schema({"rules": [r]}) != []


def test_schema_accepts_empty_rules():
    assert V.check_schema({"rules": []}) == []


# ── ③ 카탈로그 ──────────────────────────────────────────────────────────
def test_catalog_rejects_unknown_variable():
    r = rule(condition={"<": [{"var": "customer.income"}, 1]})
    assert any("카탈로그에 없는 변수" in e for e in V.check_catalog(r))


def test_catalog_rejects_unknown_event():
    r = rule(condition={"exists": {"event": "LOTTERY_WIN"}})
    assert any("카탈로그에 없는 이벤트" in e for e in V.check_catalog(r))


def test_catalog_rejects_unknown_effect():
    assert any("카탈로그에 없는 effect" in e
               for e in V.check_catalog(rule(effect={"type": "GIVE_GIFT"})))


def test_catalog_rejects_unknown_fee_target():
    r = rule(effect={"type": "FEE_WAIVE", "target": "PARKING", "value": "UNLIMITED"})
    assert any("수수료 대상이 아님" in e for e in V.check_catalog(r))


def test_catalog_rejects_unknown_unit():
    assert any("카탈로그에 없는 단위" in e
               for e in V.check_catalog(rule(effect={"type": "RATE_ADD",
                                                     "value": 1, "unit": "bp"})))


def test_catalog_rejects_bad_enum_value():
    r = rule(condition={"==": [{"var": "contract.termination_type"}, "취소"]})
    assert any("값이 아님" in e for e in V.check_catalog(r))


def test_catalog_accepts_good_enum_value():
    r = rule(condition={"==": [{"var": "contract.termination_type"}, "MATURITY"]})
    assert V.check_catalog(r) == []


def test_catalog_checks_anchor_variable():
    r = rule(let={"w": {"month_range": {
        "from": {"anchor": "contract.nope", "day": "first"},
        "to": {"anchor": "contract.maturity_date", "day": "last"}}}})
    assert any("기준 변수" in e for e in V.check_catalog(r))


def test_catalog_message_lists_alternatives():
    r = rule(condition={"<": [{"var": "customer.income"}, 1]})
    assert "customer.age" in V.check_catalog(r)[0]


# ── ④ quote ────────────────────────────────────────────────────────────
def test_quote_must_be_verbatim():
    assert V.check_quote(rule(), CLAUSE) == []


def test_quote_rejects_paraphrase():
    r = rule(source={"quote": "미성년자에게 특별금리를 준다"})
    assert V.check_quote(r, CLAUSE) != []


def test_quote_ignores_whitespace():
    r = rule(source={"quote": "연 1.9%p 의  특별금리를\n제공합니다"})
    assert V.check_quote(r, CLAUSE) == []


def test_quote_missing_is_an_error():
    assert V.check_quote({"source": {}}, CLAUSE) != []


# ── ⑤ 실행 ──────────────────────────────────────────────────────────────
def test_executable_accepts_good_rule():
    assert V.check_executable(rule()) == []


def test_executable_catches_unbound_ref():
    r = rule(condition={"exists": {"event": "DEPOSIT", "within": {"ref": "$w"}}})
    assert any("미바인딩" in e for e in V.check_executable(r))


def test_executable_message_is_prefixed():
    r = rule(condition={"and": {"a": {"==": [1, 1]}}})
    assert V.check_executable(r)[0].startswith("실행 불가: DslError: ")


def test_executable_checks_guard_too():
    r = rule(guard={"nope": 1})
    assert V.check_executable(r) != []


def test_executable_requires_effect_keys():
    r = rule(effect={"type": "FEE_WAIVE", "value": "UNLIMITED"})
    assert any("필요한 키가 없다" in e for e in V.check_executable(r))


def test_executable_never_raises():
    for bad in ({"rule_id": "R"}, rule(condition=[]), rule(condition="x")):
        V.check_executable(bad)


# ── check_effect_value (⑤ 계약 ③) ───────────────────────────────────────
@pytest.mark.parametrize("t", catalog.RATE_EFFECTS)
def test_rate_value_must_be_a_number(t):
    r = rule(effect={"type": t, "value": "contract.base_rate", "unit": "%p"})
    assert V.check_effect_value(r) != []


@pytest.mark.parametrize("t", catalog.RATE_EFFECTS)
def test_rate_value_number_is_fine(t):
    assert V.check_effect_value(rule(effect={"type": t, "value": 1.0, "unit": "%p"})) == []


def test_rate_value_bool_is_not_a_number():
    assert V.check_effect_value(rule(effect={"type": "RATE_ADD",
                                             "value": True, "unit": "%p"})) != []


def test_non_rate_effect_value_is_free():
    r = rule(effect={"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                     "value": "UNLIMITED"})
    assert V.check_effect_value(r) == []


# ── ⑦ 빈 배열 (⑤ 계약 ②) ───────────────────────────────────────────────
def test_empty_output_is_marked_empty():
    assert V.score_record({"rules": []}, CLAUSE)["empty"] is True


def test_empty_output_does_not_pass_catalog_for_free():
    m = V.score_record({"rules": []}, CLAUSE)
    assert (m["catalog_ok"], m["quote_ok"], m["exec_ok"]) == (False, False, False)


def test_empty_output_still_passes_schema():
    assert V.score_record({"rules": []}, CLAUSE)["schema_ok"] is True


def test_unparsed_output_fails_json():
    assert V.score_record(None, CLAUSE)["json_ok"] is False


def test_good_output_passes_all():
    m = V.score_record({"rules": [rule()]}, CLAUSE)
    assert all(m[k] for k in ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok"))


def test_n_rules_counted():
    assert V.score_record({"rules": [rule(), rule()]}, CLAUSE)["n_rules"] == 2


def test_schema_failure_does_not_drag_the_other_axes_down():
    # 하나가 무너지면 나머지가 같이 0 이 되어 어느 축이 움직였는지 못 읽게 된다
    m = V.score_record({"rules": [rule(extra=1)]}, CLAUSE)
    assert m["schema_ok"] is False
    assert (m["catalog_ok"], m["quote_ok"], m["exec_ok"]) == (True, True, True)


def test_axes_are_independent():
    bad_quote = rule(source={"quote": "없는 문장"})
    m = V.score_record({"rules": [bad_quote]}, CLAUSE)
    assert m["quote_ok"] is False and m["catalog_ok"] is True and m["exec_ok"] is True


# ── 생성물이 이상해도 검증기가 죽지 않는다 ──────────────────────────────
@pytest.mark.parametrize("bad", [
    {"type": "FEE_WAIVE", "target": ["EBANK_TRANSFER", "ATM_TRANSFER"],
     "value": "UNLIMITED"},
    {"type": "FEE_WAIVE", "target": {"a": 1}, "value": "UNLIMITED"},
    {"type": "RATE_ADD", "value": 1.0, "unit": ["%p"]},
    {"type": "RATE_ADD", "value": 1.0, "unit": {"x": 1}},
])
def test_catalog_check_survives_unhashable_values(bad):
    """v19 에서 모델이 target 에 배열을 넣어 라운드가 37/46 에서 멈췄다.

    `x in set` 이 TypeError 로 죽었다. 생성물 때문에 검증기가 죽으면
    그 라운드 전체를 못 읽는다.
    """
    r = {"rule_id": "R", "source": {"quote": "x"}, "condition": {}, "effect": bad}
    assert V.check_catalog(r) != []          # 잡아내되 죽지 않는다


def test_score_record_survives_unhashable_values():
    out = {"rules": [{"rule_id": "R", "source": {"quote": "x"}, "condition": {},
                      "effect": {"type": "FEE_WAIVE", "target": ["A", "B"],
                                 "value": "UNLIMITED"}}]}
    assert V.score_record(out, "조문")["catalog_ok"] is False


# ── DISQUALIFY 를 좁힌다 (2026-09-16 · v24) ─────────────────────────────
def _r(effect):
    return {"rule_id": "x", "status": "OK", "label": "L",
            "source": {"quote": "q"},
            "condition": {"==": [{"var": "customer.age"}, 17]},
            "effect": effect}


def test_a_holder_type_in_the_require_value_is_caught():
    """v24 가 사람 검토 완료 조문 둘을 깨뜨린 경로다.

    gold 는 holder_type 을 조건에서 비교해 DISQUALIFY 한다.
    모델은 REQUIRE 의 value 에 담았고 관문 다섯이 전부 통과시켰다.
    """
    errs = V.check_catalog(_r({"type": "REQUIRE", "value": "INDIVIDUAL"}))
    assert errs and "customer.holder_type" in errs[0]


def test_a_restriction_code_in_the_disqualify_value_is_caught():
    errs = V.check_catalog(_r({"type": "DISQUALIFY", "value": "ALL_TRANSACTIONS"}))
    assert errs and "RESTRICT" in errs[0]


def test_disqualify_takes_no_target():
    errs = V.check_catalog(_r({"type": "DISQUALIFY", "target": "ALL_TRANSACTIONS"}))
    assert errs and "RESTRICT" in errs[0]


def test_a_bare_disqualify_is_still_fine():
    assert V.check_catalog(_r({"type": "DISQUALIFY"})) == []


def test_restrict_with_its_own_target_is_fine():
    assert V.check_catalog(_r({"type": "RESTRICT", "target": "ALL_TRANSACTIONS"})) == []


def test_the_new_constraint_costs_gold_nothing(root):
    """gold 46조문이 전부 통과해야 한다. 비용 0 이 이 제약의 근거다."""
    import json, os
    os.chdir(root)
    bad = []
    for p in sorted((root / "data/gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        for r in json.loads(p.read_text("utf-8")).get("rules", []):
            eff = r.get("effect") or {}
            if eff.get("type") in ("REQUIRE", "DISQUALIFY"):
                v, t = eff.get("value"), eff.get("target")
                if (isinstance(v, str) and __import__("catalog").slot_of(v.strip())) or t:
                    bad.append((p.name, eff))
    assert not bad, f"gold 가 새 제약에 걸린다: {bad}"
