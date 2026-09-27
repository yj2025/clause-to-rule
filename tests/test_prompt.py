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


def test_examples_are_neither_swapped_nor_added():
    """예시 넷이 예산이다. 맞바꿔도(v9·v18) 더해도(v21·v22) ⑦ 이 무너진다."""
    from schema import FEWSHOTS
    assert len(FEWSHOTS) == 4
    assert any(o == {"rules": []} for _, o in FEWSHOTS)


def test_the_prompt_length_stays_inside_the_registered_bound():
    """v21 이 다섯째 예시를 더하면서 프롬프트가 길어졌다 — **사전에 잰 비용**이다.

    v21·v22(예시 5개)는 7,0xx자였고 되돌린 지금은 5,9xx자다.
    길이 자체는 ⑦ 의 원인이 아니었다 — v21 과 v22 가 같은 길이에
    같은 ⑦ 을 냈다. 그래도 상한은 남겨 둔다.
    """
    import json
    corpus = json.loads(__import__("pathlib").Path("data/corpus.json").read_text("utf-8"))
    lens = [len(build_user_prompt(c["text"], c["id"])) for c in corpus]
    assert sum(lens) / len(lens) < 8000


# ── v46 · 목록에 없는 이름이 필요할 때 기권을 쓰라고 잇는다 ────────────────
def _retry(errors):
    import prompt
    return prompt.build_retry_prompt("조문 본문", {"rules": []}, errors)


def test_no_name_block_only_fires_on_missing_name_errors():
    """**이름이 목록에 없을 때만** 붙는다.

    연산자가 틀린 것(`eq`)은 기권할 일이 아니라 `==` 로 고칠 일이다.
    거기까지 기권을 권하면 **어려우면 도망가라**를 가르치게 된다 — v5 가
    회피로 무너진 그 길이다.
    """
    on = _retry(["카탈로그에 없는 변수: notice.methods. 쓸 수 있는 것: account.balance"])
    off = _retry(["정의되지 않은 연산자: `eq`. 쓸 수 있는 것: =="])
    assert "목록에 없는 이름이 필요할 때" in on
    assert "목록에 없는 이름이 필요할 때" not in off
    assert "UNSUPPORTED" in on


def test_no_name_block_appears_once_however_many_errors():
    """오류는 여덟 줄까지 들어간다. 줄마다 붙이면 같은 말이 여덟 번 나온다."""
    p = _retry([f"카탈로그에 없는 변수: x{i}. 쓸 수 있는 것: y" for i in range(8)])
    assert p.count("목록에 없는 이름이 필요할 때") == 1


def test_no_name_block_names_nothing():
    """**이름을 하나도 적지 않는다** — v34 가 메시지에 예시를 박아 실패했다."""
    import catalog
    p = _retry(["카탈로그에 없는 이벤트: PLEDGE. 쓸 수 있는 것: APP_LOGIN"])
    block = p.split("[목록에 없는 이름이 필요할 때]")[1].split("문제만 고쳐서")[0]
    for name in set(catalog.VARIABLES) | set(catalog.EVENTS):
        assert name not in block, f"블록이 이름을 흘린다: {name}"


def test_retry_prompt_is_unchanged_when_the_block_does_not_fire():
    """안 걸리는 조문의 지문은 **한 글자도 안 는다.**"""
    import prompt
    errs = ["스키마 위반: 'condition' is a required property"]
    got = prompt.build_retry_prompt("조문", {"rules": []}, errs)
    assert "\n\n문제만 고쳐서" in got


# ── v50 · 기권할 때는 조건도 효과도 적지 않는다 ──────────────────────────
def test_the_block_says_what_an_abstain_rule_looks_like():
    """v46 이 「기권하라」만 말해서 조건이 남았다.

    `KBYY-S2-R09` 가 status 를 UNSUPPORTED 로 바꾸고도 0점이다 — 조건에 남은
    이름이 계속 관문에 걸린다. 정답의 기권 rule 28개 중 조건이 든 것은 둘,
    effect 가 든 것은 없다.
    """
    p = _retry(["카탈로그에 없는 변수: notice.methods. 쓸 수 있는 것: account.balance"])
    block = p.split("[목록에 없는 이름이 필요할 때]")[1].split("문제만 고쳐서")[0]
    assert "조건도 효과도 적지 않는다" in block


def test_the_abstain_shape_matches_the_gold():
    """지문이 말하는 모양과 **정답의 모양이 같아야 한다.**

    지문 5번은 아직 「effect 도 그렇게 적는다」고 한다 — 스키마·검증기·정답과
    어긋난다. 그것은 v51 에서 1차 지문을 고칠 때 잡는다. 이 시험은 **정답이
    실제로 어떤 모양인지**를 박아 둔다.
    """
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    n = with_cond = with_eff = 0
    for f in sorted((root / "data" / "gold").glob("*.json")):
        if f.name.startswith("_"):
            continue
        for r in (json.loads(f.read_text("utf-8")).get("rules") or []):
            if r.get("status") == "UNSUPPORTED":
                n += 1
                with_cond += bool(r.get("condition"))
                with_eff += "effect" in r
    assert n >= 20
    assert with_eff == 0, f"정답의 기권 rule {with_eff}개가 effect 를 단다"
    assert with_cond <= 3, f"정답의 기권 rule {with_cond}개가 조건을 단다"


# ── v54 · 옮길 것이 아예 없으면 rule 을 만들지 않는다 ────────────────────
def test_the_block_separates_nothing_to_translate_from_cannot_translate():
    """v46 이 「기권하라」만 말해서 **규칙이 아닌 서술**에도 기권 rule 이 붙었다.

    정답이 «빈 배열»인 조문에 기권 rule 을 다는 자리가 3~4 에서 6 으로 늘었고
    네 라운드 내내 6 이었다 — 「기본이율 적용」 · 「해지 방법」 같은 문장들이다.
    지문 5번은 그 둘을 가르는데 블록이 한쪽만 되풀이하고 있었다.
    """
    p = _retry(["카탈로그에 없는 변수: notice.methods. 쓸 수 있는 것: account.balance"])
    block = p.split("[목록에 없는 이름이 필요할 때]")[1].split("문제만 고쳐서")[0]
    assert "rule 을 만들지 않는다" in block
    assert "「옮길 것이 없다」와 「옮길 수 없다」는 다르다" in block


def test_the_two_cases_match_the_system_prompt():
    """블록이 가르는 둘은 **지문 5번이 이미 가르는 둘**이다. 말이 어긋나면 안 된다."""
    from prompt import SYSTEM_PROMPT
    assert "빈 배열" in SYSTEM_PROMPT
    assert "옮길 것이 없는 경우" in SYSTEM_PROMPT
    assert "옮길 수 없는 경우" in SYSTEM_PROMPT
