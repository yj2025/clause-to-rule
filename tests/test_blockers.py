"""카탈로그 확장이 실제로 무엇을 푸는지 세는 도구."""

import json
from pathlib import Path

import pytest

import blockers as B


@pytest.fixture
def clauses(root):
    import os
    os.chdir(root)
    return B.load()


def test_every_unsupported_rule_has_a_readable_blocker(clauses):
    """걸림돌을 못 읽는 rule 이 있으면 셈이 틀어진다.

    라벨이 "— X 없음" 꼴이어야 읽힌다. 새 골드를 쓸 때 이 시험이 지킨다.
    """
    bad = [(cid, rid) for cid, rs in clauses.items()
           for rid, b in rs.items() if not b]
    assert not bad, f"걸림돌을 못 읽은 rule: {bad}"


def test_a_clause_unlocks_only_when_every_blocker_is_filled(clauses):
    """한 조문이 두 가지를 요구하면 하나만 넣어서는 안 풀린다."""
    two = {cid: rs for cid, rs in clauses.items()
           if any(len(b) > 1 for b in rs.values())}
    assert two, "걸림돌을 둘 이상 요구하는 조문이 있어야 이 셈이 의미가 있다"
    cid = next(iter(two))
    need = set().union(*two[cid].values())
    one = next(iter(need))
    assert cid not in B.unlocked(clauses, {one})
    assert cid in B.unlocked(clauses, need)


def test_withdrawal_is_no_longer_a_blocker_at_all(clauses):
    """v17 이 출금 이벤트를 넣었다. 제안서 2순위였고 푼 조문은 0개다.

    출금을 요구한 조문은 전부 명의변경·'거래 금지' effect 같은
    다른 것도 같이 요구했다. 확장은 묶음으로 와야 값을 낸다.

    2026-09-14: 골드 라벨이 아직 '출금 이벤트 없음' 이라 적고 있었다.
    카탈로그에 있는 것을 걸림돌로 세면 확장 순위가 틀어진다 —
    `goldaudit.py` 가 찾았다. 라벨에서 뺐고 이 시험이 지킨다.
    """
    import catalog
    assert "WITHDRAWAL" in catalog.EVENTS
    everywhere = {b for rs in clauses.values() for bs in rs.values() for b in bs}
    assert "출금" not in everywhere, "카탈로그에 있는 것은 걸림돌이 아니다"


def test_the_dormancy_clauses_are_no_longer_blocked(clauses):
    """거래중지 두 조문이 열렸다 — 마지막 걸림돌이 **편입시기**였다.

    2026-09-15 확장에서 명의변경 이벤트와 거래 제한 effect 가 들어왔고,
    2026-09-20 에 편입시기(연 2회 · 6·12월 셋째 금요일 다음날)를 못 옮겨
    UNSUPPORTED 로 되돌렸다 — 조건이 맞는 즉시 막으면 최대 6개월 일찍 막는다.
    2026-09-21 에 날짜 계산(`month_of` + n째 요일)이 생겨 되살렸다.

    `blockers.load()` 는 UNSUPPORTED rule 만 세므로, 열린 조문은 아예 안 나온다.
    """
    import catalog
    assert "NAME_CHANGE" in catalog.EVENTS and "RESTRICT" in catalog.EFFECTS
    for cid in ("KBYY-S2-R19", "KBONE-S2-R16"):
        d = json.loads(Path(f"data/gold/{cid}.json").read_text("utf-8"))
        r = d["rules"][0]
        assert r["status"] == "OK" and r["effect"]["type"] == "RESTRICT"
        assert "NAME_CHANGE" in json.dumps(r["condition"]), "무거래에 명의변경 거래가 빠졌다"
        assert cid not in clauses, "열린 조문이 걸림돌 목록에 남아 있다"
    everywhere = {b for rs in clauses.values() for bs in rs.values() for b in bs}
    assert "편입시기" not in everywhere
