import json

import pytest

import catalog
from prompt import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt

CLAUSE = "전월 중 KB국민카드 결제실적이 있는 경우 전자금융 이체수수료를 면제합니다."


def test_system_prompt_is_not_empty():
    assert len(SYSTEM_PROMPT) > 200


def test_system_prompt_does_not_name_forbidden_tokens():
    # 안 하던 실수를 미리 막으려고 이름을 부르면 오히려 가르친다 (§9 2번)
    assert "literal" not in SYSTEM_PROMPT


def test_system_prompt_does_not_name_other_invented_operators():
    for bad in ("left", "right", "op\"", "month\":"):
        assert bad not in SYSTEM_PROMPT


def test_system_prompt_demands_json_only():
    assert "JSON" in SYSTEM_PROMPT


def test_system_prompt_separates_empty_from_unsupported():
    assert "빈 배열" in SYSTEM_PROMPT and "UNSUPPORTED" in SYSTEM_PROMPT


def test_system_prompt_tells_to_wrap_counters():
    assert "count_distinct_months" in SYSTEM_PROMPT


# ── user 프롬프트 ───────────────────────────────────────────────────────
def test_user_prompt_contains_the_clause():
    assert CLAUSE in build_user_prompt(CLAUSE)


def test_user_prompt_contains_examples():
    assert "[예시 1 · 조문]" in build_user_prompt(CLAUSE)


def test_user_prompt_still_shows_an_empty_array_scene():
    """v9 는 이 장면을 잃고 ⑦ 13.0% → 6.5%, v18 은 30.4% → 8.7% 가 됐다.

    두 번 잃어 보고 두 번 되돌렸다. **이 장면은 맞바꿀 수 없다.**
    """
    assert '"rules": []' in build_user_prompt(CLAUSE)


def test_user_prompt_shows_a_fee_waiver_example():
    """일곱 라운드 동안 UNLIMITED 를 한 번도 안 썼다 — 장면이 없었다."""
    assert '"UNLIMITED"' in build_user_prompt(CLAUSE)


def test_fewshot_json_is_indented():
    # 한 줄로 압축하면 모델이 중괄호 깊이를 놓친다
    p = build_user_prompt(CLAUSE)
    assert '\n  "rules"' in p or '\n "rules"' in p


def test_fewshot_indent_is_adjustable():
    assert len(build_user_prompt(CLAUSE, fewshot_indent=2)) > \
           len(build_user_prompt(CLAUSE, fewshot_indent=1))


def test_user_prompt_includes_clause_id_when_given():
    assert "KBYY-S2-R12" in build_user_prompt(CLAUSE, "KBYY-S2-R12")


def test_user_prompt_omits_id_when_absent():
    assert "[조문 id]" not in build_user_prompt(CLAUSE)


def test_user_prompt_narrows_the_catalog():
    p = build_user_prompt(CLAUSE)
    assert "CARD_USAGE" in p and "PENSION_RECEIPT" not in p


def test_user_prompt_falls_back_to_the_whole_catalog():
    p = build_user_prompt("xyz")
    assert "PENSION_RECEIPT" in p


def test_user_prompt_lists_fee_targets_for_fee_clauses():
    assert "EBANK_TRANSFER" in build_user_prompt(CLAUSE)


def test_fee_names_leak_only_through_the_example():
    """예시에 수수료 장면을 넣은 대가다. 어휘 목록은 여전히 조문별로 추려진다.

    안 쓸 이름을 보여주면 그 이름을 쓴다 — 이 프로젝트가 실측한 함정이라
    누출 크기를 테스트로 고정한다. 예시 안에서 대상당 한 번씩만 나와야 한다.
    """
    p = build_user_prompt("만 19세 미만 고객")
    assert "[면제 대상]" not in p                    # 어휘 목록에는 안 실린다
    assert p.count("EBANK_TRANSFER") == 1            # 예시 안에서만
    assert "OTHER_BANK_ATM_WITHDRAW" not in p        # 예시에 없는 대상은 안 샌다


def test_user_prompt_lists_every_effect():
    p = build_user_prompt(CLAUSE)
    assert all(e in p for e in catalog.EFFECTS)


def test_user_prompt_ends_with_the_output_marker():
    assert build_user_prompt(CLAUSE).rstrip().endswith("[출력]")


def test_enum_values_appear_when_the_variable_does():
    p = build_user_prompt("중도해지 시에는 우대금리가 적용되지 않습니다")
    assert "MATURITY" in p


# ── 재시도 프롬프트 ─────────────────────────────────────────────────────
def test_retry_prompt_carries_the_errors():
    p = build_retry_prompt(CLAUSE, {"rules": []}, ["미바인딩 참조: $window"])
    assert "미바인딩 참조: $window" in p


def test_retry_prompt_carries_the_bad_output():
    p = build_retry_prompt(CLAUSE, {"rules": [{"rule_id": "R-9"}]}, ["e"])
    assert "R-9" in p


def test_retry_prompt_caps_the_error_list():
    p = build_retry_prompt(CLAUSE, {}, [f"오류{i}" for i in range(20)])
    assert "오류9" not in p.split("[위 출력의 문제]")[1] or p.count("  - ") <= 8


def test_retry_prompt_still_contains_the_clause():
    assert CLAUSE in build_retry_prompt(CLAUSE, {}, ["e"])


def test_retry_prompt_asks_to_keep_good_rules():
    assert "그대로 둔다" in build_retry_prompt(CLAUSE, {}, ["e"])
