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


def test_overgeneration_dominates(root):
    """모델은 과하게 만드는 쪽으로 틀린다 — 유실된 기록이 지목한 다음 과녁."""
    import json, os
    os.chdir(root)
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    conf = D.audit(recs, run=0)["conf"]
    over = sum(n for (w, g), n in conf.items()
               if w in (D.EMPTY, D.UNSUP) and g in (D.OK, D.MIXED))
    under = sum(n for (w, g), n in conf.items()
                if w in (D.OK, D.MIXED) and g in (D.EMPTY, D.UNSUP))
    assert over > under
