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
