import json

import pytest

import catalog
import schema
from schema import (FEWSHOT_CLAUSE, FEWSHOT_EMPTY_OUTPUT, FEWSHOT_INTRO_CLAUSE,
                    FEWSHOT_INTRO_OUTPUT, FEWSHOT_OUTPUT, FEWSHOTS, SCHEMA)


def test_schema_is_json_serialisable():
    json.dumps(SCHEMA)


def test_schema_requires_rules():
    assert SCHEMA["required"] == ["rules"]


def test_effect_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["effect"]["properties"]["type"]["enum"]) == set(catalog.EFFECTS)


def _target_enum(effect_type):
    """effect 종류를 정해 놓았을 때 스키마가 허용하는 target 목록."""
    eff = SCHEMA["properties"]["rules"]["items"]["properties"]["effect"]
    for branch in eff["allOf"]:
        t = branch["if"]["properties"]["type"]
        names = {t["const"]} if "const" in t else set(t["enum"])
        if effect_type in names:
            return set(branch["then"].get("properties", {})
                       .get("target", {}).get("enum", []))
    return set()


def test_each_effect_gets_its_own_target_vocabulary():
    """효과 종류마다 목록이 갈려 있어야 한다 — 2026-09-21.

    하나를 공유하면 `RESTRICT::WITHDRAWAL` 처럼 **있는 이름을 틀린 자리에**
    쓴 것이 스키마를 통과한다. ③ 이 뒤에서 잡지만 ② 가 못 잡고,
    오류 메시지가 아흔 개짜리 목록을 재시도 프롬프트에 흘린다.
    """
    assert _target_enum("FEE_WAIVE") == set(catalog.FEES)
    assert _target_enum("FEE_WAIVE_NO_CARRYOVER") == set(catalog.FEES)
    assert _target_enum("SERVICE_PROVIDE") == set(catalog.SERVICES)
    assert _target_enum("RESTRICT") == set(catalog.RESTRICTIONS)
    assert _target_enum("STATE_CHANGE") == set(catalog.STATES)
    assert _target_enum("PRODUCT_SWITCH_TO") == set(catalog.PRODUCTS)


def test_every_target_name_belongs_to_exactly_one_vocabulary():
    """카탈로그를 넓힐 때 이름이 두 목록에 걸치면 이 시험이 먼저 막는다.

    걸치는 이름이 생기면 «틀린 자리» 판정 자체가 흐려진다.
    면제 효과 둘(이월 가능·불가)은 **같은 목록**을 쓰므로 걸침이 아니다.
    """
    seen = {}
    for eff, names in schema.TARGETS.items():
        for n in names:
            seen.setdefault(n, set()).add(frozenset(names))
    shared = {n: len(v) for n, v in seen.items() if len(v) > 1}
    assert not shared, f"여러 목록에 걸친 이름: {shared}"


def test_effects_without_a_target_slot_refuse_one():
    """`DISQUALIFY` 처럼 대상이 없는 효과에 target 을 달면 ② 가 막는다."""
    assert "DISQUALIFY" in schema.NO_TARGET
    assert not (set(schema.NO_TARGET) & set(schema.TARGETS))
    assert set(schema.NO_TARGET) | set(schema.TARGETS) == set(catalog.EFFECTS)


def test_the_message_names_only_the_slot_that_was_used():
    """재시도 프롬프트에 무엇을 쓸 수 있는지 **짧게** 돌려주어야 한다.

    v29 에서 `RESTRICT` target 위반 하나가 상품 키 일흔네 개를 포함한
    아흔 개짜리 목록을 돌려주었다. 자리를 가른 뒤에는 그 자리 것만 나온다.
    """
    import validate

    rule = {"rule_id": "X-01", "status": "OK", "label": "x",
            "source": {"quote": "x"},
            "condition": {"==": [{"var": "customer.age"}, 19]},
            "effect": {"type": "RESTRICT", "target": "WITHDRAWAL"}}
    errs = validate.check_schema({"rules": [rule]})
    assert errs, "이벤트 이름을 금지 대상 자리에 쓴 것을 ② 가 잡아야 한다"
    msg = errs[0]
    for name in catalog.PRODUCTS:
        assert name not in msg, f"메시지에 남의 자리 이름이 섞였다: {name}"
    assert "ALL_TRANSACTIONS" in msg


def test_unit_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["effect"]["properties"]["unit"]["enum"]) == set(catalog.UNITS)


def test_status_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["status"]["enum"]) == set(catalog.STATUSES)


def test_the_example_budget_is_four():
    """다섯째를 놓으면 ⑦ 빈 배열이 10.9p 무너진다 — **자리와 무관하게.**

    v21 은 다섯째를 끝에, v22 는 넷째에 놓았다. ⑦ 이 **둘 다 13.0%** 로
    소수점까지 같았다 (v19 는 23.9%). 프롬프트 길이도 같았으므로
    "길어서" 도 아니다. **개수다.**

    맞바꿈은 v9·v18 에서 두 번 확인했고 더하기는 v21·v22 에서 확인했다.
    양쪽 다 ⑦ 을 문다.

    다섯째를 되살리려면 그 비용을 다시 사전 등록하고 재야 한다.
    카탈로그가 넓어지면 계산이 뒤집힐 수 있다 — ③ 이 +12.9p 였다.
    """
    assert len(FEWSHOTS) == 4


def test_the_empty_array_scene_is_never_dropped():
    """v18 에서 무거래 장면으로 바꿨다가 되돌렸다.

    장면은 **먹었다** — WITHDRAWAL 사용이 1 rule → 10 rule, 표적 2/2.
    그러나 빈 배열 장면을 잃은 대가가 컸다: ⑦ 30.4% → 8.7%,
    과생성 9 → 15건. 사전 등록한 되돌림 선 둘을 다 넘었다.

    **확장 항목마다 예시 자리가 필요한데 자리가 모자란다** —
    이것이 `CATALOG_PROPOSAL.md` 에 붙는 결론이다.

    자리 번호로 찾지 않는다 — 차례는 v22 가 재는 변수다.
    """
    assert FEWSHOT_INTRO_OUTPUT == {"rules": [], "no_rule_reason": "SUMMARY"}   # v125
    assert (FEWSHOT_INTRO_CLAUSE, FEWSHOT_INTRO_OUTPUT) in FEWSHOTS


def test_the_intro_scene_mentions_benefits_without_numbers():
    """혜택이 말로만 언급된 조문 — ⑨ 의 대표 실패 모양이다."""
    import grounding
    clause = FEWSHOT_INTRO_CLAUSE
    assert "금리" in clause and grounding.numbers_in(clause) == set()


def test_first_fewshot_shows_a_rule():
    assert FEWSHOT_OUTPUT["rules"]


def test_second_fewshot_shows_the_fee_table():
    """일곱 라운드 동안 FEE_WAIVE rule 62개에서 UNLIMITED 가 0개였다.

    카탈로그에 있고 스키마도 허용하는데 모델이 그 장면을 못 봤다.
    """
    vals = [r["effect"]["value"] for r in FEWSHOT_EMPTY_OUTPUT["rules"]]
    assert "UNLIMITED" in vals


def test_second_fewshot_shows_a_numeric_count_too():
    vals = [r["effect"]["value"] for r in FEWSHOT_EMPTY_OUTPUT["rules"]]
    assert 10 in vals


def test_second_fewshot_rule_count_matches_the_table():
    # 표가 3행이면 rule 도 3개. 표에 없는 대상은 출력에도 없다
    assert len(FEWSHOT_EMPTY_OUTPUT["rules"]) == 3


def test_second_fewshot_values_are_grounded():
    import grounding
    clause = FEWSHOTS[1][0]
    assert all(not grounding.check_rule(r, clause)
               for r in FEWSHOT_EMPTY_OUTPUT["rules"])


def test_third_fewshot_splits_body_from_proviso():
    """v14 — 본문은 옮기고 단서는 UNSUPPORTED 로 둔다.

    gold 가 "섞임" 인 조문 5개에서 옮길 수 없는 부분이 전부 단서 줄이었다.
    **OK 가 먼저, UNSUPPORTED 가 나중**이다 — v5 는 "써도 된다" 만 가르쳐
    ⑧ 이 83.7% 로 무너졌다.
    """
    st = [r["status"] for r in FEWSHOTS[2][1]["rules"]]
    assert st == ["OK", "UNSUPPORTED"]


def test_the_unsupported_rule_has_no_effect():
    un = [r for r in FEWSHOTS[2][1]["rules"] if r["status"] == "UNSUPPORTED"]
    assert un and all("effect" not in r for r in un)


def test_the_ok_rule_in_the_mixed_example_has_an_effect():
    ok = [r for r in FEWSHOTS[2][1]["rules"] if r["status"] == "OK"]
    assert ok and all("effect" in r for r in ok)


def test_fewshot_quote_is_verbatim():
    q = FEWSHOT_OUTPUT["rules"][0]["source"]["quote"]
    assert q in FEWSHOT_CLAUSE


@pytest.mark.parametrize("i", [0, 1, 2, 3])
def test_every_fewshot_quote_is_verbatim(i):
    clause, out = FEWSHOTS[i]
    for r in out["rules"]:
        assert "".join(r["source"]["quote"].split()) in "".join(clause.split())


# 아래 넷은 **재워 둔** 금리 예시(`FEWSHOT_RATE_*`)의 불변식이다.
# 2026-09-16 에 첫째 자리를 명의유형 장면으로 맞바꾸면서 이 예시가 빠졌다.
# 되살릴 때를 대비해 그대로 지킨다 — 재워 둔 동안 썩는 것을 막는 것이
# `test_parked_examples_are_kept_current` 와 같은 뜻이다.
def test_parked_rate_fewshot_uses_a_window_binding():
    from schema import FEWSHOT_RATE_OUTPUT
    r = FEWSHOT_RATE_OUTPUT["rules"][0]
    assert "window" in r["let"] and "$window" in json.dumps(r["condition"])


def test_parked_rate_fewshot_wraps_the_counter_in_a_comparison():
    from schema import FEWSHOT_RATE_OUTPUT
    assert list(FEWSHOT_RATE_OUTPUT["rules"][0]["condition"]) == [">="]


def test_parked_rate_fewshot_guard_excludes_early_termination():
    from schema import FEWSHOT_RATE_OUTPUT
    assert FEWSHOT_RATE_OUTPUT["rules"][0]["guard"]["=="][1] == "MATURITY"


def test_parked_rate_fewshot_value_is_a_number():
    from schema import FEWSHOT_RATE_OUTPUT
    assert isinstance(FEWSHOT_RATE_OUTPUT["rules"][0]["effect"]["value"],
                      (int, float))


# ── 재워 둔 명의유형 예시 (2026-09-16 에 넣었다가 v26 판정으로 뺐다) ─────
def test_the_holder_type_fewshot_compares_in_the_condition():
    """**명의 유형은 조건에서 비교한다.** effect 의 value 가 아니다.

    v24 에서 모델이 `REQUIRE value=INDIVIDUAL` 을 냈고 사람 검토를 마친
    조문 둘이 그렇게 깨졌다. v25 에서 ③ 이 세 번 막았는데 세 번 다 같은 것을
    냈다 — 막는 것으로는 구조를 못 바꾼다. 이 예시가 그 구조를 보여준다.
    """
    from schema import FEWSHOT_HOLDER_OUTPUT
    r = FEWSHOT_HOLDER_OUTPUT["rules"][0]
    assert "customer.holder_type" in json.dumps(r["condition"], ensure_ascii=False)
    assert r["effect"]["type"] == "DISQUALIFY"
    assert "value" not in r["effect"], "명의 유형을 effect 의 value 에 담지 않는다"


def test_the_holder_type_fewshot_excludes_by_enumeration():
    from schema import FEWSHOT_HOLDER_OUTPUT
    r = FEWSHOT_HOLDER_OUTPUT["rules"][0]
    assert list(r["condition"]) == ["not"] and "in" in r["condition"]["not"]
    import catalog
    vals = r["condition"]["not"]["in"][1]
    assert set(vals) <= set(catalog.ENUM_VALUES["customer.holder_type"])


def test_disqualify_appears_only_with_a_real_condition():
    """v15 에서 **조건 없는** DISQUALIFY 를 넣었다가 되돌렸다.

    DISQUALIFY 는 줄었지만(13 → 8) 그 자리가 다른 남발로 채워졌다 —
    거래중지가 LIMIT_AMOUNT 3개로 가고, 지어낸 코드가 1 → 7 로 늘었다.
    게다가 v14 에서 맞던 조문 8개가 틀렸고 그중 6개가
    "표현 불가" 에서 "정상 rule" 로 갔다. **예시에 rule 이 하나 는 것이
    "더 내라" 로 읽혔다.**

    막힌 조문에서 수단을 찾는 행동 자체는 그대로이고 도구만 바뀐다.

    v18 에서 다시 넣었는데 **조건이 있다** — 무거래 판정이라는 구체적인 조건이다.
    v15 의 위험은 "DISQUALIFY 라는 도구를 보여준 것" 이 아니라
    **"막히면 여기에 밀어 넣어도 된다" 로 읽힌 것**이었다.
    조건이 붙어 있으면 그렇게 읽힐 여지가 줄어든다 — 이것이 v18 의 가설이고,
    틀리면 ⑫ 과생성이 13건을 넘어 되돌린다.
    """
    dq = [r for _, o in FEWSHOTS for r in o["rules"]
          if (r.get("effect") or {}).get("type") == "DISQUALIFY"]
    assert all(r.get("condition") for r in dq), "조건 없는 DISQUALIFY 는 넣지 않는다"


def test_every_example_with_rules_passes_its_own_gates(root):
    """예시가 내 검증기를 못 넘으면 그것을 그대로 가르치게 된다.

    빈 배열 예시는 뺀다 — ③④⑤ 가 빈 배열에 False 를 주는 것은
    채점의 알려진 결함이다 (v10 판정 · v11 에서 갈래를 따로 세웠다).
    """
    import os
    os.chdir(root)
    import schema
    import validate as V
    GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
    for i, (clause, out) in enumerate(schema.FEWSHOTS, 1):
        rules = out.get("rules") or []
        if not rules:
            continue
        r = V.score_record(out, clause)
        bad = [k for k in GATES if not r[k]]
        assert not bad, f"예시 {i} 가 {bad} 를 못 넘는다: {r['errors']}"


def test_no_example_teaches_a_vacuous_condition(root):
    """예시의 조건이 언제나 참이면 그 모양을 가르친다 (⑭)."""
    import os
    os.chdir(root)
    import schema
    import vacuous as VA
    for i, (_, out) in enumerate(schema.FEWSHOTS, 1):
        for r in out.get("rules") or []:
            bad = [k for k, _ in VA.check_rule(r) if k == "헛조건"]
            assert not bad, f"예시 {i} 가 헛조건을 가르친다"


def test_the_empty_array_example_is_last():
    """빈 배열 예시는 맨 끝이다 — v19 까지의 차례를 지킨다.

    차례 자체는 ⑦ 에 영향이 없었다 (v21 대 v22 가 같았다).
    그래도 근거 없이 바꾸지 않는다 — v19 구성으로 되돌린 상태다.
    """
    assert FEWSHOTS[-1][1]["rules"] == []   # v125 부터 no_rule_reason 이 붙는다


def _rule(**kw):
    base = {"rule_id": "x", "status": "OK", "label": "L",
            "source": {"quote": "q"}, "condition": {}}
    return {"rules": [dict(base, **kw)]}


def test_unconditional_disqualify_is_a_schema_violation(root):
    """조건 없는 DISQUALIFY 는 모든 고객의 예금 자격을 없앤다 (v23).

    관문 다섯을 전부 통과하고 ⑭ 도 못 본다 — 빈 조건은 "항상 적용" 이라는
    뜻을 밝힌 것이라 일부러 뺀다. 기준선 3회차에서 세 회차 모두 2개였다.
    """
    import os
    os.chdir(root)
    import validate as V
    errs = V.check_schema(_rule(effect={"type": "DISQUALIFY"}))
    assert errs, "막아야 한다"
    assert "UNSUPPORTED" in errs[0], (
        "재시도 프롬프트가 이 문구를 그대로 돌려준다 — 무엇을 하라는지 적어야 한다")


def test_a_condition_or_a_guard_is_enough(root):
    import os
    os.chdir(root)
    import validate as V
    cond = {"==": [{"var": "customer.has_product"}, True]}
    assert not V.check_schema(_rule(condition=cond,
                                    effect={"type": "DISQUALIFY"}))
    assert not V.check_schema(_rule(guard=cond, effect={"type": "DISQUALIFY"}))


def test_other_effects_may_have_no_condition(root):
    """저금통 한도 100만원은 누구에게나 적용된다 — 조건 {} 가 맞다.

    골드의 KBYY-S2-R07-02 가 그 형태다. DISQUALIFY 만 다르다.
    """
    import os
    os.chdir(root)
    import validate as V
    assert not V.check_schema(_rule(
        effect={"type": "LIMIT_AMOUNT", "value": 1000000, "unit": "원"}))
    assert not V.check_schema(_rule(
        effect={"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                "value": "UNLIMITED"}))


def test_every_gold_rule_still_passes_the_schema(root):
    """제약을 넣어 골드가 깨지면 안 된다. 골드의 DISQUALIFY 다섯 개는 전부 조건이 있다."""
    import os, json
    os.chdir(root)
    from pathlib import Path
    import validate as V
    for p in sorted(Path("data/gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        d = json.loads(p.read_text("utf-8"))
        errs = V.check_schema({"rules": d.get("rules") or []})
        assert not errs, f"{d['clause_id']}: {errs[:1]}"


def test_parked_examples_are_kept_current(root):
    """**쓰지 않는 예시도 채점기와 카탈로그를 따라가야 한다.**

    `FEWSHOT_DORMANT_*` 는 v22 에 빠진 뒤 09-15 카탈로그 확장을 못 따라갔다.
    조문이 "거래를 제한합니다" 인데 effect 가 `DISQUALIFY` 로 남아 있었다 —
    되살렸으면 v24·v25 가 싸운 바로 그 혼동을 예시가 직접 가르칠 뻔했다.
    관문 다섯은 맨 `DISQUALIFY` 를 합법으로 통과시키므로 잡히지도 않는다.
    """
    import os
    os.chdir(root)
    import schema
    import validate as V
    GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
    parked = [("FEWSHOT_DORMANT", schema.FEWSHOT_DORMANT_CLAUSE,
               schema.FEWSHOT_DORMANT_OUTPUT),
              ("FEWSHOT_RATE", schema.FEWSHOT_RATE_CLAUSE,
               schema.FEWSHOT_RATE_OUTPUT),
              ("FEWSHOT_HOLDER", schema.FEWSHOT_HOLDER_CLAUSE,
               schema.FEWSHOT_HOLDER_OUTPUT)]
    for name, clause, out in parked:
        r = V.score_record(out, clause)
        bad = [k for k in GATES if not r[k]]
        assert not bad, f"{name} 이 {bad} 를 못 넘는다: {r['errors']}"


def test_no_example_uses_disqualify_for_a_transaction_limit(root):
    """거래 제한은 `RESTRICT` 다. 예시가 `DISQUALIFY` 로 가르치면 안 된다.

    v24 에서 `RESTRICT` 가 필요한 5조문 중 4조문이 `DISQUALIFY` 로 갔다.
    예시가 그 혼동을 거들면 안 된다 — 쓰는 예시든 재워 둔 예시든.
    """
    import os
    os.chdir(root)
    import schema
    pools = list(schema.FEWSHOTS) + [
        (schema.FEWSHOT_DORMANT_CLAUSE, schema.FEWSHOT_DORMANT_OUTPUT),
        (schema.FEWSHOT_RATE_CLAUSE, schema.FEWSHOT_RATE_OUTPUT),
        (schema.FEWSHOT_HOLDER_CLAUSE, schema.FEWSHOT_HOLDER_OUTPUT)]
    for i, (clause, out) in enumerate(pools):
        for r in out.get("rules") or []:
            if (r.get("effect") or {}).get("type") != "DISQUALIFY":
                continue
            assert "제한" not in clause, (
                f"예시 {i} 의 조문이 «제한» 을 말하는데 DISQUALIFY 를 가르친다 — "
                "RESTRICT 여야 한다")


def test_at_most_one_fewshot_quotes_a_bullet_line(root):
    """**예시의 인용 모양이 «무엇을 rule 로 만들까» 까지 옮긴다** (v26).

    v26 에서 quote 가 `▪` 로 시작하는 예시를 **둘째로** 넣었더니(첫째 자리에)
    생성물의 quote 중 `▪` 로 시작하는 비율이 44.7% → 66.7% 로 뛰었고,
    빈 배열을 내야 할 조문 7개에서 `▪` 줄을 인용해 rule 을 만들었다.
    ④ 가 +19.6p 오른 것과 ⑦ 이 −15.2p 떨어진 것이 같은 뿌리다.

    **하나는 괜찮다.** 예시[2](한도 예외)가 v1 부터 `▪` 를 인용해 왔고
    v25 의 ⑦ 은 19.6% 였다. 무너진 것은 **둘이 됐을 때**다.
    그래서 금지가 아니라 **개수**를 고정한다 — 예시 예산이 넷인 것과 같은 모양의
    제약이다 (`test_the_example_budget_is_four`).

    둘째를 놓으려면 그 비용을 다시 사전 등록하고 재야 한다.
    """
    import os
    os.chdir(root)
    import schema
    n = sum(1 for _, out in schema.FEWSHOTS
            if any((r.get("source") or {}).get("quote", "").startswith("▪")
                   for r in out.get("rules") or []))
    assert n <= 1, f"`▪` 를 인용하는 예시가 {n}개다 — v26 이 둘의 비용을 쟀다"


# 2026-10-06 · v125 — 빈 배열의 이유
def test_a_no_rule_reason_passes_the_schema_and_a_wrong_one_does_not():
    import jsonschema
    from schema import SCHEMA
    jsonschema.validate({"rules": [], "no_rule_reason": "SUMMARY"}, SCHEMA)
    jsonschema.validate({"rules": []}, SCHEMA)          # 없어도 ② 는 통과한다
    import pytest as _p
    with _p.raises(jsonschema.ValidationError):
        jsonschema.validate({"rules": [], "no_rule_reason": "OTHER"}, SCHEMA)


def test_every_empty_gold_has_a_reason():
    import json
    from pathlib import Path
    from schema import NO_RULE_REASONS
    for p in [*Path("data/gold").glob("K*.json"), *Path("showcase/gold_draft").glob("K*.json")]:
        g = json.loads(p.read_text("utf-8"))
        if not g.get("rules"):
            assert g.get("no_rule_reason") in NO_RULE_REASONS, p.stem
