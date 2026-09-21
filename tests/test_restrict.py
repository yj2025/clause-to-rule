"""RESTRICT · NAME_CHANGE — 확장 여섯 항목의 다섯째 (2026-09-15).

특정 거래만 막는 자리가 없어 모델이 DISQUALIFY 로 밀어 넣던 곳이다. 거래중지 두 조문은
무거래기간을 '입출금 거래 또는 명의변경 거래' 로 정의해, 명의변경 이벤트가 같이 있어야 열린다.
"""

import json
from pathlib import Path

import pytest

import _free
import blockers
import catalog
import gold
import prompt
import validate
from engine import evaluate_rules
from resolver import resolve

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"
OPENED = ("KBONE-S2-R14", "KBONE-S2-R16", "KBYY-S2-R16", "KBYY-S2-R17", "KBYY-S2-R19")
DORMANCY = ("KBONE-S2-R16", "KBYY-S2-R19")


def _rules(cid):
    return json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]


def _ctx(balance, **events):
    ev = {k: [] for k in catalog.EVENTS}
    for kind, dates in events.items():
        ev[kind] = [{"date": d, "amount": 10_000} for d in dates]
    return {"account": {"balance": balance},
            "contract": {"reference_date": "2026-09-11"}, "events": ev}


def rule(**eff):
    return {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
            "condition": {}, "effect": {"type": "RESTRICT", "target": "PLEDGE", **eff}}


def test_restrict_needs_a_target_from_its_own_list():
    assert catalog.EFFECTS["RESTRICT"] == ("target",)
    r = rule()
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == [] and validate.check_executable(r) == []
    assert validate.check_catalog(rule(target="EBANK_TRANSFER")) != []
    no_target = rule()
    del no_target["effect"]["target"]
    assert validate.check_executable(no_target) != []


# 2026-09-20 에 UNSUPPORTED 로 되돌렸다가 **2026-09-21 에 다시 열었다.**
# 막고 있던 것은 편입시기(연 2회 · 6·12월 셋째 금요일 다음날)였고, 그날을
# 계산할 수단이 없어 «조건이 맞는 즉시 제한» 으로 판별하면 실제보다 최대
# 6개월 일찍 막았다 — 불리한 오차라 허용하지 않았다.
#
# 이제 `month_of` + n째 요일로 그날을 계산한다. 조건식은 그대로 두고
# **창의 양끝만 편입일로 옮겼다** — 무거래를 «오늘까지» 가 아니라
# «편입일까지» 센다.
@pytest.mark.parametrize("cid", DORMANCY)
def test_dormancy_is_judged_against_the_sweep_date(cid):
    """열렸다. 그리고 **편입일을 실제로 보고 있는지** 조건식에서 확인한다."""
    rs = _rules(cid)
    assert [r["status"] for r in rs] == ["OK"]
    assert rs[0]["effect"] == {"type": "RESTRICT", "target": "ALL_TRANSACTIONS"}
    for win in rs[0]["let"].values():
        for end in ("from", "to"):
            a = win["month_range"][end]
            assert a["month_of"] == [6, 12], (cid, end)
            assert a["day"] == {"weekday": "FRI", "nth": 3}, (cid, end)
            assert a["offset_days"] == 1, (cid, end)


def test_the_sweep_date_is_the_saturday_after_the_third_friday():
    """「6·12월 셋째 금요일 기준 다음날」 — 토요일이어야 한다."""
    from engine import _anchor
    got = _anchor({"anchor": "contract.reference_date", "month_of": [6, 12],
                   "day": {"weekday": "FRI", "nth": 3}, "offset_days": 1},
                  {"contract": {"reference_date": "2026-09-11"}})
    assert got.isoformat() == "2026-06-20"        # 2026-06-19 이 셋째 금요일
    assert got.weekday() == 5                      # 토요일


@pytest.mark.parametrize("cid", DORMANCY)
# 기준일 2026-09-11 일 때 **편입일은 2026-06-20** 이다 (6월 셋째 금요일 19일의 다음날).
# 그래서 창은 오늘이 아니라 그날에서 뒤로 잡힌다.
#
#     $y1  2025-06-20 ~ 2026-06-20
#     $y2  2024-06-20 ~ 2026-06-20
#     $y3  2023-06-20 ~ 2026-06-20
#
# 경계 두 개가 2026-09-20 판 시험에서 뒤집혔고 **뒤집힌 쪽이 맞다.**
# 2025-08-01 에 출금한 5천원 계좌는 편입일 기준 10개월 전 거래라 아직 1년이
# 안 됐다. 옛 판(오늘까지 세기)은 이것을 제한 대상으로 봤다 —
# 그것이 «최대 6개월 일찍 막는다» 의 실제 모습이다.
@pytest.mark.parametrize("balance,events,want", [
    (5_000, {}, True),
    (5_000, {"WITHDRAWAL": ["2025-06-01"]}, True),        # 편입일 기준 12.6개월 전
    (5_000, {"WITHDRAWAL": ["2025-08-01"]}, False),       # 10.6개월 전 — 아직 1년이 아니다
    (5_000, {"WITHDRAWAL": ["2026-01-01"]}, False),
    (5_000, {"NAME_CHANGE": ["2026-01-01"]}, False),      # 명의변경 거래도 거래다
    (5_000, {"SALARY_TRANSFER": ["2026-01-01"]}, False),  # 넓게 센다 — 고객에게 유리한 쪽
    (5_000, {"WITHDRAWAL": ["2026-08-01"]}, True),        # **편입일 뒤의 거래는 안 본다**
    (30_000, {"DEPOSIT": ["2025-08-01"]}, False),         # 2년이어야 한다
    (30_000, {"DEPOSIT": ["2024-06-01"]}, True),          # 편입일 기준 24.6개월 전
    (30_000, {"DEPOSIT": ["2024-08-01"]}, False),         # 22.6개월 — 아직 2년이 아니다
    (70_000, {"DEPOSIT": ["2024-08-01"]}, False),         # 3년이어야 한다
    (70_000, {"DEPOSIT": ["2023-06-01"]}, True),          # 36.6개월 전
    (150_000, {}, False),                                 # 10만원 이상은 대상 아님
])
def test_dormancy_is_counted_from_the_sweep_date_not_today(cid, balance, events, want):
    """무거래 기간을 **편입일에서** 센다. 경계가 여기 박혀 있다."""
    from engine import evaluate
    from tv import TV
    r = _rules(cid)[0]
    got = evaluate(r["condition"], {**_ctx(balance, **events), "_provided": None},
                   dict(r.get("let") or {}))
    assert got is (TV.T if want else TV.F)


def test_unconditional_bans_carry_their_target():
    want = {"KBONE-S2-R14-01": "PLEDGE", "KBYY-S2-R16-01": "PLEDGE",
            "KBYY-S2-R17-01": "NAME_CHANGE", "KBYY-S2-R17-02": "PLEDGE"}
    got = {r["rule_id"]: r for cid in ("KBONE-S2-R14", "KBYY-S2-R16", "KBYY-S2-R17")
           for r in _rules(cid)}
    for rid, target in want.items():
        assert got[rid]["condition"] == {} and got[rid]["effect"]["target"] == target, rid


def test_a_ban_keeps_eligibility_and_the_rate():
    res = resolve(evaluate_rules(_rules("KBYY-S2-R17"), {}), "SUM", base_rate=0.1)
    assert not res.disqualified and res.final_rate_max == "0.10"
    assert len(res.other_effects) == 2


@pytest.mark.parametrize("cid", DORMANCY)
def test_profiles_would_tell_restricted_from_not_if_it_were_ok(cid):
    """되살렸을 때 ⑥ 이 이 rule 을 가리지 않는지 — 조건식으로 확인한다."""
    from engine import evaluate
    from tv import TV
    r = _rules(cid)[0]
    fired = {evaluate(r["condition"], ctx, dict(r.get("let") or {})) is TV.T
             for _, ctx in gold.profiles()}
    assert fired == {True, False}


def test_blockers_are_gone_and_the_rest_are_relabelled(root):
    import os
    os.chdir(root)
    left = blockers.load()
    # 2026-09-21 에 편입시기를 날짜 계산으로 풀어 거래중지 둘도 열렸다
    assert not set(OPENED) & set(left)
    everywhere = {b for rs in left.values() for bs in rs.values() for b in bs}
    assert not {"거래금지", "명의변경", "질권"} & everywhere
    assert left["KBYY-S2-R11"]["KBYY-S2-R11-02"] == {"기준금액"}
    assert left["KBYY-S2-R18"]["KBYY-S2-R18-02"] == {"발급일"}


def test_prompt_lists_restrictions_only_for_ban_clauses():
    assert "[금지 대상]" in prompt.build_user_prompt("▪ 담보제공 불가능")
    assert "[금지 대상]" not in prompt.build_user_prompt("만 19세 미만 고객")


def test_free_sample_varies_name_change():
    s = _free.sample()
    assert len({len(c["events"]["NAME_CHANGE"]) for c in s}) > 1


# ── 2026-09-21 · 날짜 계산을 모델에게 어떻게 알리나 ────────────────────────
def test_the_recurring_date_block_only_appears_where_it_is_needed():
    """「n째 요일」을 말하는 조문에만 붙는다.

    장면 하나가 ⑦ 빈 배열을 10.9p 무너뜨린다 (v21·v22). 그래서 few-shot 자리를
    안 먹고, 필요한 조문에만 붙는 블록으로 넣었다. 나머지 조문의 지문은
    **한 글자도 안 는다** — 그것이 이 방식을 고른 이유다.
    """
    import json
    corpus = json.loads((GOLD.parent / "corpus.json").read_text("utf-8"))
    hit = [c["id"] for c in corpus if catalog.wants_recurring_date(c["text"])]
    assert set(hit) == {"KBYY-S2-R08", "KBYY-S2-R19", "KBYY-S2-R23",
                        "KBONE-S2-R05", "KBONE-S2-R16"}, hit
    for c in corpus:
        p = prompt.build_user_prompt(c["text"])
        assert ("month_of" in p) == (c["id"] in hit), c["id"]


@pytest.mark.parametrize("text,want", [
    ("매년 6월, 12월 셋째 금요일 기준으로 다음날 편입", True),
    ("매년 2월, 5월, 8월, 11월의 둘째 금요일에 결산", True),
    ("(나) 예금잔액이 10,000원 이상", False),        # 항목 번호는 n째가 아니다
    ("금요일에 지급합니다", False),                   # 요일만 있으면 아니다
    ("둘째 자녀부터 우대", False),                    # n째만 있으면 아니다
])
def test_recurring_date_needs_both_an_ordinal_and_a_weekday(text, want):
    assert catalog.wants_recurring_date(text) is want
