"""TAX_EXEMPT_ELIGIBLE · 해지 제한 대상 — 2026-09-20 실행기 범위 결정.

세율·세금 계산은 범위 밖이고 **가입 자격**만 들인다 (결정 5).
「일부해지 불가」 · 「중도해지 불가」 는 이율 문제가 아니라 그 거래를 막는 것이라 RESTRICT 다.
"""

import json
from pathlib import Path

import pytest

import blockers
import catalog
import validate
from engine import evaluate_rules
from resolver import resolve

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"
TAX = ("KBYY-S2-R13", "KBONE-S2-R10")


def rule(**eff):
    return {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
            "condition": {}, "effect": {"type": "TAX_EXEMPT_ELIGIBLE", **eff}}


def test_the_effect_needs_no_key_and_passes_every_gate():
    assert catalog.EFFECTS["TAX_EXEMPT_ELIGIBLE"] == ()
    r = rule()
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == [] and validate.check_executable(r) == []


def test_it_is_reported_as_an_effect_and_does_not_move_the_rate():
    res = resolve(evaluate_rules([rule()], {}), "SUM", base_rate=0.1)
    assert [e["type"] for e in res.other_effects] == ["TAX_EXEMPT_ELIGIBLE"]
    assert res.final_rate_max == "0.10" and not res.disqualified


@pytest.mark.parametrize("cid", TAX)
def test_the_tax_clauses_are_open_now(cid):
    """세법 개정 안내는 2026-09-20 에 뺐고, 남은 rule 은 가입 자격 하나다."""
    rules = json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]
    assert [r["status"] for r in rules] == ["OK"]
    assert rules[0]["effect"]["type"] == "TAX_EXEMPT_ELIGIBLE"


def test_no_tax_blocker_is_left(root):
    import os
    os.chdir(root)
    left = blockers.load()
    assert not set(TAX) & set(left)
    everywhere = {b for rs in left.values() for bs in rs.values() for b in bs}
    assert "세제" not in everywhere


@pytest.mark.parametrize("target", ("PARTIAL_TERMINATION", "EARLY_TERMINATION", "EARLY_PAYOUT"))
def test_termination_bans_are_restrict_targets(target):
    r = {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
         "condition": {}, "effect": {"type": "RESTRICT", "target": target}}
    assert validate.check_catalog(r) == [] and validate.check_executable(r) == []
    assert catalog.slot_of(target) == "`RESTRICT` 의 target"


def test_prompt_offers_them_only_for_termination_clauses():
    assert catalog.pick_restrictions("이 예금은 일부해지 불가") == ["PARTIAL_TERMINATION"]
    assert catalog.pick_restrictions("담보제공 불가") == ["PLEDGE"]


def test_payout_request_date_is_offered_only_where_the_text_asks_for_it():
    v, _ = catalog.pick_candidates("예금주가 만기일 전에 지급청구할 때")
    assert "contract.payout_request_date" in v
    v, _ = catalog.pick_candidates("만 19세 미만 고객")
    assert "contract.payout_request_date" not in v
