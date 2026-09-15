"""account.last_transaction_date · DORMANT_CONTRIBUTION — 확장 여섯 항목의 넷째 (2026-09-15).

최종거래일 변수만으로는 휴면예금 두 조문이 안 열린다. 라벨이 처음부터
"최종거래일 변수와 출연 effect 없음" 이었는데 `blockers.py` 가 출연을 못 읽어
"단독으로 2조문" 이라 셌다. 둘을 같이 넣었다.
"""

import json
from pathlib import Path

import pytest

import _free
import blockers
import catalog
import gold
import validate
from engine import evaluate
from resolver import resolve
from engine import evaluate_rules
from tv import TV

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"
PAIR = (("KBONE-S2-R17", "KBONE-S2-R17-01"), ("KBYY-S2-R20", "KBYY-S2-R20-01"))


def _rule(cid, rid):
    rs = json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]
    return next(r for r in rs if r["rule_id"] == rid)


def _ctx(ref, last, terminated=False):
    return {"contract": {"reference_date": ref},
            "account": {"last_transaction_date": last},
            "events": {"TERMINATION": [{"date": ref}] if terminated else []}}


FIVE_YEARS = {">=": [{"var": "contract.reference_date"},
                     {"anchor": "account.last_transaction_date", "offset_months": 60}]}


def test_the_variable_is_a_date_and_the_effect_needs_nothing():
    assert catalog.VARIABLES["account.last_transaction_date"]["type"] == "date"
    assert catalog.EFFECTS["DORMANT_CONTRIBUTION"] == ()


@pytest.mark.parametrize("ref,want", [("2031-09-11", TV.T), ("2031-09-10", TV.F)])
def test_anchor_operand_compares_as_a_date(ref, want):
    assert evaluate(FIVE_YEARS, _ctx(ref, "2026-09-11")) is want


def test_missing_last_transaction_is_unknown():
    assert evaluate(FIVE_YEARS, {"contract": {"reference_date": "2031-09-11"}}) is TV.U


def test_anchor_operand_passes_the_schema_and_an_unknown_anchor_does_not():
    r = {"rule_id": "X-01", "status": "OK", "label": "x", "source": {"quote": "x"},
         "condition": FIVE_YEARS, "effect": {"type": "DORMANT_CONTRIBUTION"}}
    assert validate.check_schema({"rules": [r]}) == []
    assert validate.check_catalog(r) == [] and validate.check_executable(r) == []
    bad = json.loads(json.dumps(r).replace("account.last_transaction_date", "account.last_txn"))
    assert validate.check_catalog(bad) != []


@pytest.mark.parametrize("cid,rid", PAIR)
def test_dormancy_gold_is_ok(cid, rid):
    r = _rule(cid, rid)
    assert r["status"] == "OK" and r["effect"] == {"type": "DORMANT_CONTRIBUTION"}


@pytest.mark.parametrize("cid,rid", PAIR)
def test_five_years_without_termination_is_needed(cid, rid):
    r = [_rule(cid, rid)]
    hit = resolve(evaluate_rules(r, _ctx("2031-09-11", "2026-09-11")), "SUM", base_rate=0.1)
    assert [e["type"] for e in hit.other_effects] == ["DORMANT_CONTRIBUTION"]
    assert hit.final_rate_max == "0.10", "출연 대상이 되어도 금리는 그대로다"
    early = resolve(evaluate_rules(r, _ctx("2031-09-10", "2026-09-11")), "SUM")
    closed = resolve(evaluate_rules(r, _ctx("2031-09-11", "2026-09-11", terminated=True)), "SUM")
    assert early.other_effects == [] and closed.other_effects == []


@pytest.mark.parametrize("cid,rid", PAIR)
def test_no_scoring_profile_fires_it(cid, rid):
    """프로필은 최종거래일을 기준일로 고정했다 — 판정선을 지키는 대가."""
    r = [_rule(cid, rid)]
    assert all(resolve(evaluate_rules(r, ctx), "SUM").other_effects == []
               for _, ctx in gold.profiles())


def test_free_sample_varies_it_without_moving_other_values():
    s = _free.sample()
    assert len({c["account"]["last_transaction_date"] for c in s}) > 1
    assert [c["customer"]["holder_type"] for c in s[:20]] == \
           [c["customer"]["holder_type"] for c in _free.sample()[:20]]


def test_prompt_candidates_pick_it_only_for_dormancy_clauses():
    v, _ = catalog.pick_candidates("최종거래일 이후 5년 이내 계좌를 해지하지 않을 경우 휴면예금")
    assert "account.last_transaction_date" in v
    v, _ = catalog.pick_candidates("1년 이상 입출금 거래가 없는 계좌")
    assert "account.last_transaction_date" not in v


def test_blockers_now_read_the_contribution_effect(root):
    import os
    os.chdir(root)
    left = blockers.load()
    assert "KBONE-S2-R17" not in left and "KBYY-S2-R20" not in left
    everywhere = {b for rs in left.values() for bs in rs.values() for b in bs}
    assert not {"최종거래일", "출연"} & everywhere


def test_interest_rows_stay_blocked_by_interest_only(root):
    """같은 '최종거래일 5년' 이 이자 쪽 조문에도 있다. 이자 산출은 결정 0 에서 뺐다."""
    import os
    os.chdir(root)
    left = blockers.load()
    assert left["KBONE-S2-R05"]["KBONE-S2-R05-03"] == {"이자가산"}
    assert left["KBYY-S2-R08"]["KBYY-S2-R08-02"] == {"이자가산"}
