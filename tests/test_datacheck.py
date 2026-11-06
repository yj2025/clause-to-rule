"""데이터가 주는 것과 카탈로그가 말하는 것을 맞대는 시험.

`tools/datacheck.py` 의 표는 **손으로 적은 것**이다. DB 가 바뀌면 조용히 틀린다.
여기서 DB 를 직접 읽어 맞대므로, 남이 스키마를 고치면 이 시험이 먼저 운다.
"""

import pytest

import datacheck as D


needs_db = pytest.mark.skipif(not D.DB.exists(),
                              reason=f"고객 DB 가 없다: {D.DB}")


@needs_db
@pytest.mark.parametrize("qualified", sorted(D.CHECKS))
def test_the_hand_written_enum_matches_the_db(qualified):
    """DDL 의 `CHECK` 가 값의 주인이다. 베껴 적은 것이 어긋나면 터진다."""
    assert D.db_enum(qualified) == D.CHECKS[qualified]


@needs_db
def test_every_backed_column_really_exists(root):
    """«있다» 고 적은 칼럼이 진짜 있는지 본다. 파생·실행 시점은 뺀다."""
    import os
    import sqlite3
    os.chdir(root)
    with sqlite3.connect(f"file:{D.DB}?mode=ro", uri=True) as c:
        have = set()
        for (t,) in c.execute("select name from sqlite_master where type='table'"):
            for r in c.execute(f'pragma table_info("{t}")'):
                have.add(f"{t}.{r[1]}")
    missing = []
    for var, spec in D.BACKING.items():
        if spec is None or spec[0].startswith("("):
            continue
        if spec[0] not in have:
            missing.append((var, spec[0]))
    assert not missing, f"없는 칼럼을 «있다» 고 적었다: {missing}"


def test_the_table_covers_every_catalog_variable(root):
    """카탈로그에 변수를 더하면 여기도 판정을 적어야 한다.

    안 적고 넘어가면 «판정 가능 몇 조문» 이 조용히 틀린다.
    """
    import os
    os.chdir(root)
    import catalog
    assert set(D.BACKING) == set(catalog.VARIABLES), (
        f"빠짐 {set(catalog.VARIABLES) - set(D.BACKING)} · "
        f"군더더기 {set(D.BACKING) - set(catalog.VARIABLES)}")


def test_no_event_claims_to_be_backed(root):
    """거래 내역 테이블이 생기기 전까지 이벤트는 전부 못 쓴다.

    생기면 이 시험을 고치고 `EVENTS_BACKED` 를 채운다.
    """
    import os
    import sqlite3
    os.chdir(root)
    assert D.EVENTS_BACKED == frozenset()
    if D.DB.exists():
        with sqlite3.connect(f"file:{D.DB}?mode=ro", uri=True) as c:
            tables = {t for (t,) in c.execute(
                "select name from sqlite_master where type='table'")}
        assert not any("TRANSACTION" in t.upper() or "TRADE" in t.upper()
                       for t in tables), (
            f"거래 내역 테이블이 생겼다 — EVENTS_BACKED 를 채워라: {tables}")


@needs_db
@pytest.mark.xfail(strict=True, reason=(
    "`UNREGISTERED_ASSOCIATION` 은 2026-09-21 에 `ORGANIZATION` 으로 고쳤다. "
    "남은 것은 `JOINT`(공동명의)다 — DB 에 담을 칼럼이 없어 조건이 영영 거짓이다. "
    "덜 탈락시키는 쪽이라 급하지 않다. 정하고 나면 이 xfail 을 떼라"))
def test_gold_holder_type_values_exist_in_the_db(root):
    """정답이 쓰는 명의 유형이 DB 의 값 목록 안에 있어야 한다.

    `JOINT`(공동명의)가 DB 에 없다. 조건이 영영 거짓이라 공동명의를 못 거른다 —
    **덜** 탈락시키는 쪽이라 오차가 고객에게 유리해서 급하지 않다.
    `UNREGISTERED_ASSOCIATION` 은 반대 방향이라 먼저 고쳤다. DECISIONS.md 를 보라.
    """
    import json
    import os
    import re
    os.chdir(root)
    allowed = set(D.db_enum("Customer_Defaults.customer_kind"))
    used = set()
    for f in sorted((root / "data" / "gold").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        for r in (d.get("rules") or []):
            t = json.dumps(r.get("condition"), ensure_ascii=False)
            if "holder_type" in t:
                used |= set(re.findall(r'"([A-Z_]{4,})"', t))
    assert used <= allowed, f"DB 에 없는 값: {sorted(used - allowed)}"
