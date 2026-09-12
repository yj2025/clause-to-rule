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


def test_a_korean_sentence_is_out_of_scope():
    # 한글 설명문은 이 축이 겨냥하는 것이 아니다
    assert invent.check_rule(rule(v="본인명의의 입출금이 자유로운 예금 계좌")) == []


def test_a_short_token_is_out_of_scope():
    assert invent.check_rule(rule(v="AB")) == []


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


def test_the_gate_still_allows_korean_text(root):
    import validate as V
    assert V.check_catalog(rule(v="본인명의의 입출금이 자유로운 예금 계좌")) == []


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
