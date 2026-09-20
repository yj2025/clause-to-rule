"""⑬ 지어낸 코드 — 카탈로그에 없는 개념을 문자열에 담아 밀어 넣나.

스키마가 REQUIRE/DISQUALIFY 의 value 를 자유 문자열로 허용한다.
관문 다섯은 이것을 전부 통과시킨다 — ③ 은 condition 안의 이름만 본다.
"""

import pytest

import invent


def rule(t="REQUIRE", v="PLEDGE_NOT_ALLOWED"):
    return {"rule_id": "R", "source": {"quote": "x"}, "condition": {},
            "effect": {"type": t, "value": v}}


def test_an_invented_code_is_caught():
    assert invent.check_rule(rule()) != []


def test_the_message_points_at_unsupported():
    assert "UNSUPPORTED" in invent.check_rule(rule())[0]


@pytest.mark.parametrize("name", ["EBANK_TRANSFER", "MATURITY", "BASE_RATE",
                                  "DEPOSIT", "RATE_ADD", "MOBILE"])
def test_a_catalog_name_is_fine(name):
    assert invent.check_rule(rule(v=name)) == []


def test_a_korean_sentence_is_caught(root):
    """한국어 설명문도 잡는다 (2026-09-14 사람 검토로 바뀐 기준).

    전에는 "이 축의 대상이 아니다" 로 빼고 있었다. 그 구멍으로 정답
    데이터가 REQUIRE 의 value 에 한국어 문장을 넣고도 0점을 받았다.
    """
    import os
    os.chdir(root)
    assert invent.check_rule(rule(v="본인명의의 입출금이자유로운예금 계좌"))

def test_a_short_token_is_caught_too(root):
    """짧아도 카탈로그 코드가 아니면 지어낸 것이다 (2026-09-14 사람 검토).

    전에는 세 글자 미만을 봐줬다. 기준이 "실행기가 읽을 수 있나" 로
    바뀌었으므로 길이는 상관없다.
    """
    import os
    os.chdir(root)
    assert invent.check_rule(rule(v="AB"))


def test_a_numeric_value_is_out_of_scope():
    r = rule()
    r["effect"]["value"] = 10
    assert invent.check_rule(r) == []


@pytest.mark.parametrize("t", ["RATE_ADD", "FEE_WAIVE", "LIMIT_AMOUNT"])
def test_other_effects_are_out_of_scope(t):
    assert invent.check_rule(rule(t=t, v="ANYTHING_HERE")) == []


def test_disqualify_is_in_scope():
    assert invent.check_rule(rule(t="DISQUALIFY", v="TAXABLE")) != []


def test_an_event_name_in_the_wrong_slot_is_allowed_by_this_axis():
    # PRODUCT_SWITCH 는 이벤트 이름이라 카탈로그에 있다. 자리가 틀린 것은
    # 이 축이 아니라 다른 축이 잡아야 한다 — 여기서는 봐준다
    assert invent.check_rule(rule(v="PRODUCT_SWITCH")) == []


def test_known_vocabulary_covers_every_catalog_family():
    import catalog
    v = invent.known()
    assert set(catalog.FEES) <= v and set(catalog.EVENTS) <= v
    assert set(catalog.APPLIES_TO) <= v and set(catalog.STATUSES) <= v


# ── 실제 라운드 ─────────────────────────────────────────────────────────
def test_the_escape_hatch_is_used_more_over_time(root):
    """라운드를 거듭할수록 이 경로를 더 많이 쓴다."""
    import json
    def n(v):
        d = [x for x in json.loads((root / f"results/results_{v}.json").read_text("utf-8"))
             if x["run"] == 0]
        return invent.audit(d)["bad"]
    assert n("v10") > n("v1")


def test_the_gate_now_catches_it(root):
    """v12 에서 ③ 에 물렸다. 축을 먼저 세우고 탈출구를 막는 순서를 지켰다.

    막기 전(v1~v10)에는 관문 다섯이 전부 통과시켰다 — 그 사실은
    `results/` 에 남은 라운드들이 증언한다.
    """
    import validate as V
    assert V.check_catalog(rule()) != []


def test_the_gate_blocks_free_text_too(root):
    """③ 관문까지 막는다 (2026-09-14 사람 검토).

    실행기가 읽을 수 없는 값이면 한국어든 소문자든 카탈로그 준수 실패다.
    v12 에서 대문자 코드를 ③ 에 물린 것과 같은 논리다.

    이 결정으로 ③ 이 전 라운드에서 최대 6.5p 내려간다.
    **모델이 나빠진 것이 아니라 관문을 엄하게 만든 것이다.**
    실제로 걸리는 값은 "BRANCH, ONLINE, INTERNET" · "1 year" ·
    "contact_branch_or_call_center" 처럼 전부 실행 불가능한 것이었다.
    """
    import os
    os.chdir(root)
    import validate as V
    assert V.check_catalog(rule(v="본인명의의 입출금이 자유로운 예금 계좌"))
    assert V.check_catalog(rule(v="1 year"))
    assert V.check_catalog(rule(v="BRANCH, ONLINE, INTERNET"))


def test_the_rounds_before_v12_were_not_caught(root):
    """막기 전 라운드에서 이 형태가 ③ 를 통과했다는 증거."""
    import json
    d = [x for x in json.loads((root / "results/results_v10.json").read_text("utf-8"))
         if x["run"] == 0]
    caught = [x for x in d
              if any(invent.check_rule(r)
                     for r in (x.get("output") or {}).get("rules") or []
                     if isinstance(r, dict))
              and x["final"]["catalog_ok"]]
    assert caught, "그때는 통과했어야 한다"


def test_a_free_korean_string_is_also_an_invented_code(root):
    """자유 문자열도 지어낸 코드로 센다 (2026-09-14 사람 검토).

    ⑬ 이 대문자 코드만 보고 한국어 설명문은 일부러 빼고 있었다.
    그 구멍으로 정답 데이터가 REQUIRE 의 value 에
    "본인명의의 입출금이자유로운예금 계좌" 를 넣고도 0점을 받았다.
    실행기가 읽을 수 없는 값이면 코드든 문장이든 같다.
    """
    import os
    os.chdir(root)
    import invent
    r = {"rule_id": "x", "status": "OK", "label": "L",
         "source": {"quote": "q"}, "condition": {},
         "effect": {"type": "REQUIRE",
                    "value": "본인명의의 입출금이자유로운예금 계좌"}}
    errs = invent.check_rule(r)
    assert errs and "자유 문자열" in errs[0]


def test_a_catalog_code_still_passes(root):
    import os
    os.chdir(root)
    import invent, catalog
    good = sorted(catalog.FEES)[0]
    r = {"rule_id": "x", "status": "OK", "label": "L",
         "source": {"quote": "q"}, "condition": {},
         "effect": {"type": "REQUIRE", "value": good}}
    assert not invent.check_rule(r)


# ── 2026-09-20 정의를 넓혔다 — 이름 자리 전부를 본다 ────────────────────
def _rule(**eff):
    return {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
            "condition": {"exists": {"event": "CARD_USAGE"}}, "effect": {"type": "RESTRICT", **eff}}


def test_an_invented_target_next_to_a_new_effect_is_counted():
    """v28 이 찾은 자리 — RESTRICT 에 target 셋을 주자 네 번째를 지어냈다."""
    recs = [{"clause_id": "C1", "run": 0,
             "output": {"rules": [_rule(target="WITHDRAWAL")]}}]
    a = invent.audit_names(recs)
    assert a["bad"] == 1 and a["names"]["WITHDRAWAL"] == 1
    assert a["slots"]["effect.target"] == 1
    # 옛 정의는 이것을 못 본다 — 그래서 넓혔다
    assert invent.audit(recs)["bad"] == 0


def test_catalog_names_are_not_invented():
    for target in ("PLEDGE", "PARTIAL_TERMINATION"):
        recs = [{"clause_id": "C1", "run": 0, "output": {"rules": [_rule(target=target)]}}]
        assert invent.audit_names(recs)["bad"] == 0, target
    prod = [{"clause_id": "C1", "run": 0, "output": {"rules": [
        {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
         "condition": {}, "effect": {"type": "PRODUCT_SWITCH_TO", "target": "KB국민ONE통장"}}]}}]
    assert invent.audit_names(prod)["bad"] == 0


def test_condition_names_count_too():
    recs = [{"clause_id": "C1", "run": 0, "output": {"rules": [{
        "rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
        "condition": {"and": [{"==": [{"var": "account.status"}, "OK"]},
                              {"exists": {"event": "CARD_USAGE"}}]},
        "effect": {"type": "DISQUALIFY"}}]}}]
    a = invent.audit_names(recs)
    assert a["names"]["account.status"] == 1 and a["bad"] == 1
    assert a["checked"] == 2, "쓴 이름은 둘이다 — 분모가 이름 수여야 한다"


def test_the_amount_filter_is_a_number_not_a_name():
    recs = [{"clause_id": "C1", "run": 0, "output": {"rules": [{
        "rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
        "condition": {"exists": {"event": "DEPOSIT", "where": {"min_amount": 500000}}},
        "effect": {"type": "DISQUALIFY"}}]}}]
    assert invent.audit_names(recs)["bad"] == 0
