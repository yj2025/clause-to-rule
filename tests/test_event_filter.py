"""이벤트 where (건별 금액 · 속성) + 기간표현 — 확장 여섯 항목의 여섯째 (2026-09-15).

필터만으로는 한 조문도 안 열렸다. 속성이 걸린 두 rule 의 조문에 기간표현(KBYY-S5-R02)과
계좌지정(KBONE-S2-R20)이 같이 남아 있었다. 기간표현은 4/6 의 anchor 비교로 풀어 묶었다.
"""

import json
from pathlib import Path

import pytest

import blockers
import catalog
import prompt
import validate
from engine import DslError, evaluate, evaluate_rules
from resolver import resolve
from tv import TV

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"


def _rules(cid):
    return json.loads((GOLD / f"{cid}.json").read_text("utf-8"))["rules"]


# 2026-11-05 사람 검토로 KBYY-S5-R02 정답이 빈 배열이 됐다(ONE통장 안내라 상품 범위 밖).
# 경로 필터 · 신규 면제 기간이 실제 rule 에서 도는지는 지운 rule 을 예시로 남겨 본다.
REMOVED_S5_R02 = json.loads((Path(__file__).resolve().parent / "fixture_kbyy_s5_r02_removed.json")
                            .read_text("utf-8"))["rules"]


def _ctx(ref="2026-09-11", start="2020-01-01", **events):
    ev = {k: [] for k in catalog.EVENTS}
    ev.update(events)
    return {"contract": {"reference_date": ref, "start_date": start}, "events": ev}


SALARY_500K = {"exists": {"event": "SALARY_TRANSFER", "where": {"min_amount": 500_000}}}
UTILITY = {"exists": {"event": "AUTO_TRANSFER",
                      "where": {"route": ["APARTMENT_FEE", "GIRO", "CMS", "FIRM_BANKING"]}}}


@pytest.mark.parametrize("amounts,want", [([300_000, 600_000], TV.T), ([300_000], TV.F),
                                          ([None], TV.U), ([], TV.F)])
def test_min_amount_counts_each_transfer(amounts, want):
    evs = [{"date": "2026-08-25"} if a is None else {"date": "2026-08-25", "amount": a}
           for a in amounts]
    assert evaluate(SALARY_500K, _ctx(SALARY_TRANSFER=evs)) is want


@pytest.mark.parametrize("routes,want", [(["GIRO"], TV.T), (["CARD"], TV.F),
                                         ([None], TV.U), (["CARD", None], TV.U)])
def test_route_attribute_and_unknown_route(routes, want):
    evs = [{"date": "2026-08-20"} if r is None else {"date": "2026-08-20", "route": r}
           for r in routes]
    assert evaluate(UTILITY, _ctx(AUTO_TRANSFER=evs)) is want


def test_a_count_with_an_unsure_event_is_unknown():
    node = {">=": [{"count_events": {"event": "AUTO_TRANSFER", "where": {"route": ["GIRO"]}}}, 1]}
    assert evaluate(node, _ctx(AUTO_TRANSFER=[{"date": "2026-08-20"}])) is TV.U
    assert evaluate(node, _ctx(AUTO_TRANSFER=[{"date": "2026-08-20", "route": "GIRO"}])) is TV.T


def test_bad_filters_are_dsl_errors_and_catalog_errors():
    bad_attr = {"exists": {"event": "CARD_USAGE", "where": {"route": ["GIRO"]}}}
    with pytest.raises(DslError, match="없는 속성"):
        evaluate(bad_attr, _ctx(CARD_USAGE=[{"date": "2026-08-01"}]))
    with pytest.raises(DslError, match="배열"):
        evaluate({"exists": {"event": "AUTO_TRANSFER", "where": {"route": "GIRO"}}},
                 _ctx(AUTO_TRANSFER=[{"date": "2026-08-01", "route": "GIRO"}]))
    r = {"rule_id": "X", "status": "OK", "source": {"quote": "x"}, "condition": bad_attr,
         "effect": {"type": "FEE_WAIVE", "target": "EBANK_TRANSFER", "value": 1}}
    assert validate.check_catalog(r) != []
    r["condition"] = {"exists": {"event": "AUTO_TRANSFER", "where": {"route": ["BANK"]}}}
    assert any("값이 아님" in e for e in validate.check_catalog(r))
    r["condition"] = UTILITY
    assert validate.check_catalog(r) == [] and validate.check_schema({"rules": [r]}) == []


def test_card_paid_utilities_do_not_earn_the_waiver():
    rs = [r for r in REMOVED_S5_R02 if r["rule_id"] in
          ("KBYY-S5-R02-01", "KBYY-S5-R02-02", "KBYY-S5-R02-03")]
    card = resolve(evaluate_rules(rs, _ctx(AUTO_TRANSFER=[{"date": "2026-08-20", "route": "CARD"}])), "SUM")
    giro = resolve(evaluate_rules(rs, _ctx(AUTO_TRANSFER=[{"date": "2026-08-20", "route": "GIRO"}])), "SUM")
    assert card.other_effects == [] and len(giro.other_effects) == 3


@pytest.mark.parametrize("cid,n", [("KBYY-S5-R02", 3), ("KBYY-S2-R12", 2)])
@pytest.mark.parametrize("ref,want", [("2026-09-10", True), ("2026-09-11", False)])
def test_new_account_waiver_lasts_to_the_tenth_two_months_on(cid, n, ref, want):
    """2026-07-15 가입 → 다음 다음 달 10일 = 2026-09-10 까지 실적 없이 면제."""
    rules = REMOVED_S5_R02 if cid == "KBYY-S5-R02" else _rules(cid)
    res = resolve(evaluate_rules(rules, _ctx(ref=ref, start="2026-07-15")), "SUM")
    assert len(res.other_effects) == (n if want else 0)


def test_blockers_opened_and_the_reviewed_approximation_is_kept(root):
    import os
    os.chdir(root)
    left = blockers.load()
    assert "KBYY-S5-R02" not in left and "KBYY-S2-R12" not in left
    assert left["KBONE-S2-R20"] == {"KBONE-S2-R20-04": {"계좌지정"}}
    assert all("이벤트속성" not in b for rs in left.values() for b in rs.values())
    # 사람 검토가 '고객에게 유리한 근사라 유지' 로 확정한 자리 — 필터를 넣지 않았다
    # KBYY-S5-R03 은 2026-11-05 정답 세트에서 뺐다(ONE통장 안내) — 파일은 out_of_scope 에 남아 있다
    r03 = json.dumps([r["condition"] for r in json.loads((GOLD / "out_of_scope" / "KBYY-S5-R03.json")
                      .read_text("utf-8"))["rules"] if r["status"] == "OK"])
    assert "min_amount" not in r03


def test_prompt_shows_filters_only_where_they_apply():
    assert "[이벤트 조건]" in prompt.build_user_prompt("공과금이체 자동이체 지로 CMS")
    assert "[이벤트 조건]" in prompt.build_user_prompt("건별 50만원 이상의 급여이체")
    # 근거가 전혀 없는 조문은 어휘 전체를 받으므로 이 블록도 붙는다 — 속성 없는 이벤트만 걸린 조문으로 본다
    assert "[이벤트 조건]" not in prompt.build_user_prompt("KB국민카드 결제실적이 있는 경우")
