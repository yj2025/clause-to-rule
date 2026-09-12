"""⑩ 합성 축 — 조문을 합쳐야만 보이는 파괴가 있다.

⑥ 은 조문을 하나씩 고립시켜 잰다. `RATE_OVERRIDE 0.1` 은 단독으로 보면
기본금리 0.1 과 같아 무해해 보이지만, 특별금리 1.9 와 합성되면 그것을 지운다.
gold 노트가 미리 경고해 둔 형태인데 ⑥ 은 100점을 준다.
"""

import pytest

import compose
from engine import evaluate_rules
from resolver import resolve
from scoring import score


def r(rid, t, v, unit="%p", cond=None):
    return {"rule_id": rid, "source": {"quote": "x"},
            "condition": cond if cond is not None else {},
            "effect": {"type": t, "value": v, "unit": unit}}


SPECIAL = r("SPECIAL", "RATE_ADD", 1.9)
BASE_OVERRIDE = r("BASE", "RATE_OVERRIDE", 0.1)


def test_override_looks_harmless_alone(profiles):
    """단독으로 재면 기본금리와 같아 차이가 없다 — ⑥ 이 못 보는 이유다."""
    got = score([], [BASE_OVERRIDE], "SUM", profiles, 0.1)
    assert got["rate"] == 1.0


def test_but_it_destroys_the_special_rate(profiles):
    """합성하면 특별금리가 사라진다."""
    _, ctx = profiles[0]
    with_only = resolve(evaluate_rules([SPECIAL], ctx), "SUM", base_rate=0.1)
    with_both = resolve(evaluate_rules([SPECIAL, BASE_OVERRIDE], ctx),
                        "SUM", base_rate=0.1)
    assert with_only.final_rate_max == "2.00"
    assert with_both.final_rate_max == "0.10"


def test_composition_records_what_was_erased(profiles):
    _, ctx = profiles[0]
    res = resolve(evaluate_rules([SPECIAL, BASE_OVERRIDE], ctx), "SUM", base_rate=0.1)
    assert res.overridden_rules == ["SPECIAL"]


def test_an_invented_override_pins_the_rate(profiles):
    """조문에 없는 0.5 를 덮어쓰면 최종금리가 0.50 에 못 박힌다."""
    _, ctx = profiles[0]
    res = resolve(evaluate_rules([SPECIAL, r("X", "RATE_OVERRIDE", 0.5)], ctx),
                  "SUM", base_rate=0.1)
    assert res.final_rate_min == res.final_rate_max == "0.50"


# ── 합성 도구 ───────────────────────────────────────────────────────────
def test_gold_rules_are_collected(root):
    import os
    os.chdir(root)
    rules, used = compose._gold_rules("KBYY")
    assert rules and all(c.startswith("KBYY") for c in used)


def test_product_filter_splits_the_two_products(root):
    import os
    os.chdir(root)
    _, kbyy = compose._gold_rules("KBYY")
    _, kbone = compose._gold_rules("KBONE")
    assert kbyy and kbone                       # 감사가 지적한 구멍을 메웠다
    assert not (set(kbyy) & set(kbone))


def test_missing_output_is_reported(root):
    import os, json
    os.chdir(root)
    recs = json.loads((root / "results/results_v1.json").read_text("utf-8"))
    got = compose.compare(recs, run=0)
    assert "missing" in got and got["total"] == 256


def test_composed_rate_is_a_percentage(root):
    import os, json
    os.chdir(root)
    recs = json.loads((root / "results/results_v6.json").read_text("utf-8"))
    got = compose.compare(recs, run=0)
    assert 0.0 <= got["rate"] <= 100.0


def test_v6_beats_v1_on_composition(root):
    """형식 작업이 완전히 헛되지는 않았다는 증거."""
    import os, json
    os.chdir(root)
    a = compose.compare(json.loads((root / "results/results_v1.json").read_text("utf-8")))
    b = compose.compare(json.loads((root / "results/results_v6.json").read_text("utf-8")))
    assert b["rate"] > a["rate"]
