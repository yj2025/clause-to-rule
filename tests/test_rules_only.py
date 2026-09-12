"""③④⑤ 는 rule 을 많이 낼수록 유리한 축이다.

빈 배열은 검사할 이름도, 인용문도, 실행할 것도 없어서 ③④⑤ 가 자동 실패다.
**gold 가 빈 배열인 조문에서 모델이 정답을 내도 벌점을 받는다.**
v10 에서 `KBYY-S2-R06` 과 `KBONE-S2-R04` 가 그랬다.
"""

import json

import pytest

import report
import validate as V

CLAUSE = "만 19세 미만 고객에게 연 1.9%p 의 특별금리를 제공합니다."


def test_an_empty_array_fails_three_gates():
    m = V.score_record({"rules": []}, CLAUSE)
    assert (m["catalog_ok"], m["quote_ok"], m["exec_ok"]) == (False, False, False)


def test_but_it_passes_schema():
    assert V.score_record({"rules": []}, CLAUSE)["schema_ok"] is True


def test_with_rules_filters_empty_records():
    recs = [{"output": {"rules": []}}, {"output": {"rules": [{"rule_id": "R"}]}},
            {"output": None}]
    assert len(report.with_rules(recs)) == 1


def test_with_rules_of_nothing_is_empty():
    assert report.with_rules([]) == []


def test_garbage_output_is_excluded():
    assert report.with_rules([{"output": "문자열"}]) == []


# ── 실제 라운드 ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def rounds(root):
    out = {}
    for v in ("v1", "v6", "v10"):
        d = json.loads((root / f"results/results_{v}.json").read_text("utf-8"))
        out[v] = [x for x in d if x["run"] == 0]
    return out


def test_the_bias_is_large(rounds):
    """편향의 크기 — 전체와 rule 있는 것만의 차이가 30p 를 넘는 라운드가 있다."""
    d = rounds["v1"]
    a = report._rate(d, "final", "catalog_ok")
    b = report._rate(report.with_rules(d), "final", "catalog_ok")
    assert b - a > 30.0


def test_catalog_gain_mostly_vanishes(rounds):
    """③ 의 v1 → v10 상승분 대부분이 빈 배열이 줄어든 것이었다."""
    def pair(v):
        d = rounds[v]
        return (report._rate(d, "final", "catalog_ok"),
                report._rate(report.with_rules(d), "final", "catalog_ok"))
    a_all, a_rule = pair("v1")
    b_all, b_rule = pair("v10")
    assert b_all - a_all > 10.0            # 전체로는 크게 올랐는데
    assert abs(b_rule - a_rule) < 5.0      # 편향을 빼면 제자리다


def test_quote_gain_survives_the_correction(rounds):
    """④ 는 이 갈래에서도 올랐다 — 조판 처방이 실제로 작동한 자리다."""
    a = report._rate(report.with_rules(rounds["v1"]), "final", "quote_ok")
    b = report._rate(report.with_rules(rounds["v10"]), "final", "quote_ok")
    assert b > a
