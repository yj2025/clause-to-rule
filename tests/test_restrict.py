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


@pytest.mark.parametrize("cid", DORMANCY)
@pytest.mark.parametrize("balance,events,want", [
    (5_000, {}, True),
    (5_000, {"WITHDRAWAL": ["2025-08-01"]}, True),        # 13개월 전 — 1년 무거래
    (5_000, {"WITHDRAWAL": ["2026-01-01"]}, False),
    (5_000, {"NAME_CHANGE": ["2026-01-01"]}, False),      # 명의변경 거래도 거래다
    (5_000, {"SALARY_TRANSFER": ["2026-01-01"]}, False),  # 넓게 센다 — 고객에게 유리한 쪽
    (30_000, {"DEPOSIT": ["2025-08-01"]}, False),         # 2년이어야 한다
    (30_000, {"DEPOSIT": ["2024-08-01"]}, True),
    (70_000, {"DEPOSIT": ["2024-08-01"]}, False),         # 3년이어야 한다
    (150_000, {}, False),                                 # 10만원 이상은 대상 아님
])
def test_dormancy_restricts_only_idle_small_accounts(cid, balance, events, want):
    res = resolve(evaluate_rules(_rules(cid), _ctx(balance, **events)), "SUM")
    assert [e["type"] for e in res.other_effects] == (["RESTRICT"] if want else [])
    assert not res.disqualified, "거래중지는 예금 자격 상실이 아니다"


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
def test_profiles_tell_restricted_from_not(cid):
    """잔액 0 · 거래 없음 프로필에서만 걸린다 — ⑥ 이 이 rule 을 가린다."""
    fired = {bool(resolve(evaluate_rules(_rules(cid), ctx), "SUM").other_effects)
             for _, ctx in gold.profiles()}
    assert fired == {True, False}


def test_blockers_are_gone_and_the_rest_are_relabelled(root):
    import os
    os.chdir(root)
    left = blockers.load()
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
