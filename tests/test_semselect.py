"""대응표에 글자 그대로 없는 표현을 이미 판정된 표현에 잇는다 (`tools/semselect.py`).

기본(canon)은 표지 · 따옴표 · 띄어쓰기 차이만 잇는다. 뜻이 달라질 수 있는 것은 잇지 않는다.
"""

import semconv
from semselect import LOOSE, STRICT, SelectingLexicon, canon, match, numbers

GAP = {"gap": "없음", "layer": "VOCAB", "family": "기타"}
DSL = {"dsl": {">=": [{"var": "customer.age"}, 19]}}


def lex(**tables):
    return semconv.Lexicon(tables)


def test_canon_drops_markers_quotes_spacing_and_end_punctuation():
    assert canon("단, ‘0원 계좌’로만 가입 .") == canon("0원계좌로만 가입")
    assert canon("※ ① 가입 대상") == canon("가입대상")


def test_numbers_are_read_without_commas():
    assert numbers("합산 500,000원 이상") == ["500000"]


def test_different_numbers_never_link_even_loosely():
    assert match("cond", "30만원 이상 입금", ["20만원 이상 입금"], LOOSE) == (None, [])


def test_effect_type_must_match_for_target():
    keys = ["SET_VALUE::개입할 의무"]
    assert match("target", "PROHIBIT::개입할 의무", keys, LOOSE) == (None, [])
    assert match("target", "SET_VALUE::개입 할 의무", keys, STRICT)[0] == "canon"


def test_strict_does_not_link_a_dropped_qualifier():
    # Dev50 에서 fuzzy 가 이은 실제 사례 — 가입 자격이 달라진다
    keys = ["실명의 개인사업자"]
    assert match("constraint", "실명의 개인 및 개인사업자", keys, STRICT) == (None, [])


def test_selecting_lexicon_reuses_the_verdict_and_logs_it():
    base = lex(cond={"만 19세 이상인 경우": DSL})
    s = SelectingLexicon(base)
    assert s.get("cond", "단, 만 19세 이상인 경우") == DSL
    assert s.log[-1]["tier"] == "canon" and s.log[-1]["chosen"] == "만 19세 이상인 경우"


def test_conflicting_candidates_are_left_blocked():
    base = lex(cond={"가입 대상": DSL, "가입대상": GAP})
    s = SelectingLexicon(base)
    assert s.get("cond", "‘가입대상’") is None
    assert s.log[-1]["tier"] == "ambiguous"


def test_candidates_that_differ_only_in_explanation_agree():
    base = lex(cond={"가입 대상": {**DSL, "why": "a"}, "가입대상": {**DSL, "why": "b"}})
    assert SelectingLexicon(base).get("cond", "‘가입대상’")["dsl"] == DSL["dsl"]


def test_hidden_keys_are_invisible_to_exact_and_selection():
    base = lex(cond={"만 19세 이상인 경우": DSL})
    s = SelectingLexicon(base, hide={("cond", "만 19세 이상인 경우")})
    assert s.get("cond", "만 19세 이상인 경우") is None


def test_no_tiers_means_literal_only():
    base = lex(cond={"만 19세 이상인 경우": DSL})
    assert SelectingLexicon(base, tiers=()).get("cond", "단, 만 19세 이상인 경우") is None


def test_circled_list_marker_is_not_read_as_a_number():
    assert numbers("① 가입 대상") == []
