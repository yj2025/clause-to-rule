

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


def test_coin_free_floors_exist_and_are_smaller():
    """동전을 뺀 판정선은 **더 작아야** 뜻이 있다.

    빼고도 같거나 크면 그 조문들이 흔들림의 원인이 아니라는 뜻이고,
    그러면 목록이 낡은 것이다.
    """
    import noise
    assert noise.FLOOR_NO_COIN < noise.FLOORS["⑥"]
    for k, v in noise.GROUP_FLOORS_NO_COIN.items():
        assert v <= noise.GROUP_FLOORS[k], f"{k}: 동전을 뺐는데 판정선이 안 줄었다"
