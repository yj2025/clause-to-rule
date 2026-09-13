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


def test_withdrawal_alone_unlocked_nothing(clauses):
    """v17 이 출금 이벤트를 넣었다. 제안서 2순위였고 푼 조문은 0개다.

    출금을 요구한 조문은 전부 명의변경·'거래 금지' effect 같은
    다른 것도 같이 요구했다. 확장은 묶음으로 와야 값을 낸다.
    """
    need_w = [cid for cid, rs in clauses.items()
              if any("출금" in b for b in rs.values())]
    assert need_w, "출금을 요구하는 조문이 있어야 한다"
    assert B.unlocked(clauses, {"출금"}) == []


def test_labels_and_notes_agree_on_the_dormancy_clauses():
    """거래중지 두 조문은 출금 말고 명의변경도 요구한다.

    조문이 '입출금 거래 **또는 명의변경 거래**' 로 무거래기간을 정의한다.
    라벨이 출금만 적고 있어서 도구가 '출금만 넣으면 풀린다' 고 셌었다.
    """
    for cid in ("KBYY-S2-R19", "KBONE-S2-R16"):
        d = json.loads(Path(f"data/gold/{cid}.json").read_text("utf-8"))
        lab = d["rules"][0]["label"]
        assert "출금" in lab and "명의변경" in lab
