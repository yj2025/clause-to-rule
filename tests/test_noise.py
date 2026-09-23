

# ── 2026-09-23 · 판정선을 코드 한 곳에 둔다 ──────────────────────────────
def test_floors_cover_every_axis_the_report_compares():
    """`report.py` 가 견주는 축에는 **전부** 판정선이 있어야 한다.

    전에는 모든 축에 4.0p 를 썼다. ⑤ 는 ±7.4p 인데 4.0p 로 판정해
    「움직였다」고 적을 뻔한 자리가 있었다. 축이 늘면 이 시험이 잡는다.
    """
    import noise
    import report
    for sym in report.SYMS:
        assert sym in noise.FLOORS, f"{sym} 의 판정선이 없다"
    assert "⑦" in noise.FLOORS


def test_group_floors_exist_for_every_group():
    """⑥ 은 갈래마다 판정선이 열 배 넘게 다르다. 갈래가 늘면 같이 채워야 한다."""
    import json
    import pathlib

    import gold
    import noise
    seen = set()
    for f in sorted((pathlib.Path(__file__).resolve().parent.parent
                     / "data" / "gold").glob("*.json")):
        if f.name.startswith("_"):
            continue
        seen.add(gold.group_of(json.loads(f.read_text("utf-8"))))
    assert seen <= set(noise.GROUP_FLOORS), f"판정선 없는 갈래: {seen - set(noise.GROUP_FLOORS)}"


def test_group_of_reads_the_gold_shape():
    import gold
    assert gold.group_of({"rules": []}) == "A빈"
    assert gold.group_of({"rules": [{"status": "UNSUPPORTED"}]}) == "A기권"
    assert gold.group_of({"rules": [{"status": "OK"}]}) == "B"
    assert gold.group_of({"rules": [{"status": "OK"},
                                    {"status": "UNSUPPORTED"}]}) == "M"


def test_coin_clauses_are_real_clause_ids():
    """「동전」 목록이 낡으면 조용히 아무것도 표시하지 않는다."""
    import json
    import pathlib

    import noise
    root = pathlib.Path(__file__).resolve().parent.parent
    ids = {c["id"] for c in json.loads((root / "data" / "corpus.json").read_text("utf-8"))}
    assert set(noise.COINS) <= ids, f"코퍼스에 없는 조문: {set(noise.COINS) - ids}"


def test_coin_free_floor_respects_resolution():
    """동전을 뺀 값에는 **판정선을 붙이지 않는다 — 순환이기 때문이다.**

    동전은 「이 표본에서 갈린 조문」으로 정의했다. 그것을 빼고 같은 표본으로
    흔들림을 재면 0 이 나올 수밖에 없다. 2026-09-23 아침의 `FLOOR_NO_COIN = 2.4`
    와 `GROUP_FLOORS_NO_COIN` 이 그렇게 나온 값이라 지웠다.

    남긴 `FLOOR_NO_COIN` 은 **남은 조문 수가 정하는 해상도**다 — 그보다 가늘게
    읽으면 조문 하나보다 작은 차이를 판정하는 것이다.
    """
    import noise
    rest = 46 - len(noise.COINS)
    assert noise.FLOOR_NO_COIN >= 100 / rest, "동전 뺀 값이 해상도보다 가늘다"
    assert noise.FLOOR_NO_COIN < noise.FLOORS["⑥"]
    assert not hasattr(noise, "GROUP_FLOORS_NO_COIN"), (
        "갈래별 동전 뺀 판정선은 순환이라 지웠다. 되살리려면 표본을 나눠 재야 한다")


def test_no_floor_is_finer_than_one_clause():
    """**조문 하나보다 가는 판정선은 없다.**

    46조문에서 하나가 뒤집히면 2.2p 다. σ 가 0 이어도 그보다 가늘게 판정하지
    않는다 — 네 프로세스에서 안 흔들렸다는 것이 흔들릴 수 없다는 뜻은 아니다.
    갈래별 판정선도 그 갈래의 조문 수가 하한을 정한다 (M 은 4조문이라 25.0p).

    **⑬⑭ 는 빼고 본다** — 단위가 조문이 아니라 이름 자리와 rule 이라 분모가 다르다.
    """
    import json
    import pathlib

    import gold
    import noise
    for sym in "①②③④⑤⑥⑦⑫":
        v = noise.FLOORS[sym]
        assert v >= 100 / 46 - 0.05, f"{sym} 판정선 {v}p 가 조문 하나보다 가늘다"
    n = {}
    for f in sorted((pathlib.Path(__file__).resolve().parent.parent
                     / "data" / "gold").glob("*.json")):
        if f.name.startswith("_"):
            continue
        g = gold.group_of(json.loads(f.read_text("utf-8")))
        n[g] = n.get(g, 0) + 1
    for g, c in n.items():
        assert noise.GROUP_FLOORS[g] >= 100 / c - 0.05, (
            f"{g} 갈래 판정선 {noise.GROUP_FLOORS[g]}p 가 조문 하나({100 / c:.1f}p)보다 가늘다")
