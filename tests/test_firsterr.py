"""재시도에 붙는 처방은 **1차 출력**으로 선측정한다.

v46 에서 최종 오류로 세어 「닿는 조문 8개」라고 적었는데 실제로는 27개였다.
"""


def test_first_errors_are_not_the_final_errors():
    """최종 오류만 보면 **재시도가 고친 것을 못 본다.**

    이 시험이 「같다」로 깨지면 재시도가 아무것도 안 고치고 있는 것이다.
    """
    import json
    import pathlib

    import firsterr
    root = pathlib.Path(__file__).resolve().parent.parent
    recs = json.loads((root / "results" / "results_v45.json").read_text("utf-8"))
    texts = firsterr._texts()
    more = 0
    for x in recs:
        es = firsterr.first_errors(x, texts)
        if es is None:
            continue
        if len(es) > len(x.get("errors") or []):
            more += 1
    assert more > 0, "1차 오류가 최종 오류보다 많은 조문이 하나도 없다"


def test_the_v46_trigger_reaches_far_more_than_the_final_errors_suggest():
    """v46 의 방아쇠는 8조문이 아니라 27조문에 닿았다 — 그 사실을 박아 둔다."""
    import firsterr
    from prompt import _NO_NAME
    hit, _ = firsterr.clauses_hit(["v41", "v43", "v44", "v45"], _NO_NAME)
    assert len(hit) > 20, f"닿는 조문 {len(hit)}개 — 27 근처여야 한다"
