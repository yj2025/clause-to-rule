import json

import pytest

import catalog
from schema import (FEWSHOT_CLAUSE, FEWSHOT_EMPTY_OUTPUT, FEWSHOT_OUTPUT,
                    FEWSHOTS, SCHEMA)


def test_schema_is_json_serialisable():
    json.dumps(SCHEMA)


def test_schema_requires_rules():
    assert SCHEMA["required"] == ["rules"]


def test_effect_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["effect"]["properties"]["type"]["enum"]) == set(catalog.EFFECTS)


def test_fee_target_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["effect"]["properties"]["target"]["enum"]) == set(catalog.FEES)


def test_unit_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["effect"]["properties"]["unit"]["enum"]) == set(catalog.UNITS)


def test_status_enum_matches_catalog():
    props = SCHEMA["properties"]["rules"]["items"]["properties"]
    assert set(props["status"]["enum"]) == set(catalog.STATUSES)


def test_there_are_four_fewshots():
    """v10 에서 빈 배열 장면을 되살렸다 — 맞바꾸지 않고 더했다."""
    assert len(FEWSHOTS) == 4


def test_the_fourth_fewshot_is_an_empty_array():
    """v18 에서 무거래 장면으로 바꿨다가 되돌렸다.

    장면은 **먹었다** — WITHDRAWAL 사용이 1 rule → 10 rule, 표적 2/2.
    그러나 빈 배열 장면을 잃은 대가가 컸다: ⑦ 30.4% → 8.7%,
    과생성 9 → 15건. 사전 등록한 되돌림 선 둘을 다 넘었다.

    **확장 항목마다 예시 자리가 필요한데 자리가 모자란다** —
    이것이 `CATALOG_PROPOSAL.md` 에 붙는 결론이다.
    """
    assert FEWSHOTS[3][1] == {"rules": []}


def test_the_intro_scene_mentions_benefits_without_numbers():
    """혜택이 말로만 언급된 조문 — ⑨ 의 대표 실패 모양이다."""
    import grounding
    clause = FEWSHOTS[3][0]
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


def test_fewshot_uses_a_window_binding():
    r = FEWSHOT_OUTPUT["rules"][0]
    assert "window" in r["let"] and "$window" in json.dumps(r["condition"])


def test_fewshot_wraps_the_counter_in_a_comparison():
    assert list(FEWSHOT_OUTPUT["rules"][0]["condition"]) == [">="]


def test_fewshot_guard_excludes_early_termination():
    assert FEWSHOT_OUTPUT["rules"][0]["guard"]["=="][1] == "MATURITY"


def test_fewshot_rate_value_is_a_number():
    assert isinstance(FEWSHOT_OUTPUT["rules"][0]["effect"]["value"], (int, float))


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
