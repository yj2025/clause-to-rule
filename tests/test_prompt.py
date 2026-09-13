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


# ── v19: 어휘에 쓰는 법을 붙인다 (예시 자리를 안 쓴다) ──────────────────
def test_usage_lines_attach_to_misused_names():
    """v17 — 이름만 주면 안 쓴다. 46조문에서 WITHDRAWAL 을 1번 썼다."""
    p = build_user_prompt("1년 이상 입출금 거래가 없는 계좌")
    assert "무거래 판정은 DEPOSIT 과 WITHDRAWAL 을 둘 다 센다" in p


def test_usage_lines_only_for_measured_misuse():
    """전부에 붙이면 길어지고, 안 쓸 이름을 설명하면 그 이름을 쓰게 된다."""
    from prompt import _USAGE
    assert set(_USAGE) == {"WITHDRAWAL", "DISQUALIFY", "customer.has_product"}


def test_disqualify_usage_names_what_it_is_not():
    p = build_user_prompt("만 19세 미만 고객")
    assert "특정 거래만 금지하는 것이 아니다" in p


def test_one_account_hint_reaches_the_right_clause():
    p = build_user_prompt("이 상품은 1인 1계좌만 가입이 가능합니다")
    assert "1인 1계좌" in p.split("[쓸 수 있는 이름]")[1]


def test_nothing_was_swapped_out_to_make_room():
    """새 장면은 **더한** 것이다. 기존 넷은 자리를 지킨다.

    v9 와 v18 이 맞바꿔서 두 번 다 되돌렸다 (⑦ 이 무너진다).
    """
    from schema import FEWSHOTS
    assert len(FEWSHOTS) >= 5
    assert any(o == {"rules": []} for _, o in FEWSHOTS)


def test_the_prompt_length_stays_inside_the_registered_bound():
    """v21 이 다섯째 예시를 더하면서 프롬프트가 길어졌다 — **사전에 잰 비용**이다.

    v19(설명 줄)는 평균 5,9xx자였고 v21 은 7,0xx자다.
    되돌리는 선 2번(①~⑤ 중 하나가 10p 넘게 떨어짐)이 이 비용을 잡는다.
    여기서는 **더 늘어나지 않게** 막는다 — 8,000자를 넘으면 새 장면을
    더 넣기 전에 예산을 다시 따져야 한다.
    """
    import json
    corpus = json.loads(__import__("pathlib").Path("data/corpus.json").read_text("utf-8"))
    lens = [len(build_user_prompt(c["text"], c["id"])) for c in corpus]
    assert sum(lens) / len(lens) < 8000
