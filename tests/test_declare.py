"""⑫ 선언 축 — 모델이 gold 와 같은 판정을 내렸나.

⑥ 은 빈 배열과 UNSUPPORTED 를 못 가른다. 둘 다 실행 결과가 같기 때문이다.
gold 15개 중 10개가 그 상태라 ⑥ 의 변별력이 5개에서만 나온다.
이 축은 실행 결과가 아니라 **선언**을 본다.
"""

import pytest

import declare as D

OK = {"rule_id": "R", "status": "OK", "condition": {},
      "effect": {"type": "RATE_ADD", "value": 1.0, "unit": "%p"}}
UN = {"rule_id": "R", "status": "UNSUPPORTED", "condition": {}}


@pytest.mark.parametrize("rules,want", [
    ([], D.EMPTY),
    ([UN], D.UNSUP),
    ([UN, UN], D.UNSUP),
    ([OK], D.OK),
    ([OK, OK], D.OK),
    ([OK, UN], D.MIXED),
    (None, None),
    ("망가진 값", None),
])
def test_verdict(rules, want):
    assert D.verdict(rules) == want


def test_garbage_entries_are_ignored():
    assert D.verdict(["문자열", None, OK]) == D.OK


def test_empty_and_unsupported_are_different():
    """⑥ 이 못 가르는 둘을 이 축은 가른다."""
    assert D.verdict([]) != D.verdict([UN])


def test_six_cannot_tell_them_apart(profiles):
    from scoring import score
    assert score([], [UN], "SUM", profiles, 0.1)["rate"] == 1.0


# ── 실제 라운드 ─────────────────────────────────────────────────────────
def test_every_gold_clause_is_judged(root):
    import json, os
    os.chdir(root)
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    r = D.audit(recs, run=0)
    assert r["n"] >= 15


def test_the_rate_is_a_percentage(root):
    import json, os
    os.chdir(root)
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    assert 0.0 <= D.audit(recs, run=0)["rate"] <= 100.0


def test_overgeneration_no_longer_dominates_after_the_catalog_grew(root):
    """**2026-09-20 에 뒤집혔고 09-21 에 한 번 더 움직였다.**

    전에는 과생성이 과소생성보다 많았다. 카탈로그를 넓히자(비과세 · 해지/전환
    제한 · 상품 코드 · 계좌 갈래) 정답이 열렸고, «정답은 빈 배열인데 모델이
    만들었다» 로 세던 자리가 «둘 다 rule» 로 바뀌어 11 대 11 이 됐다.

    2026-09-21 에 날짜 계산으로 거래중지 두 조문을 열면서 **9 대 11** 이 됐다.
    v6 생성물은 한 글자도 안 바뀌었다 — **정답이 또 움직인 것**이다.
    이 수가 바뀌면 그때마다 무엇이 열렸는지 여기 적는다.

    2026-11-05 사람 검토로 **11 대 10** 이 됐다. 이번에도 v6 생성물은 그대로고 정답이 움직였다.
    KBYY-S2-R04 자동전환이 UNSUPPORTED 로(불이익 · 첫 영업일 미반영) — v6 은 정상 rule 이라 과생성 +1.
    KBYY-S5-R02 가 빈 배열로(ONE통장 안내) — v6 은 정상 rule 이라 과생성 +1.
    KBYY-S5-R01 이 빈 배열로 — v6 도 빈 배열이라 과소생성 −1 (이제 맞힌 자리).

    같은 날 2차 검토로 **10 대 9** — KBYY-S5-R01~R03(ONE통장 안내)을 정답 세트에서 뺐다(`data/gold/out_of_scope/`).
    S5-R02 의 과생성 하나와 S5-R03 의 과소생성 하나가 셈에서 빠졌다.
    """
    import json, os
    os.chdir(root)
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    conf = D.audit(recs, run=0)["conf"]
    over = sum(n for (w, g), n in conf.items()
               if w in (D.EMPTY, D.UNSUP) and g in (D.OK, D.MIXED))
    under = sum(n for (w, g), n in conf.items()
                if w in (D.OK, D.MIXED) and g in (D.EMPTY, D.UNSUP))
    assert (over, under) == (10, 9), (over, under)
