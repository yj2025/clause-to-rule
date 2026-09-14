"""골드 초안을 기계로 따지는 검사 — 사람 판단이 필요한 것만 남기려고."""

import pytest

import goldaudit as G


@pytest.fixture
def gold(root):
    import os
    os.chdir(root)
    return G._gold()


def test_no_stale_blocker_claims(gold):
    """카탈로그에 생긴 것을 '없다' 고 적고 있으면 안 된다.

    v17 이 WITHDRAWAL 을 넣었는데 골드 라벨 4개가 그대로 '출금 이벤트 없음'
    이었다. `blockers.py` 가 출금을 살아 있는 걸림돌로 세서 확장 순위가
    틀어져 있었다. 카탈로그를 넓힐 때마다 이 시험이 골드를 같이 보게 한다.
    """
    stale, live = G.stale_claims(gold)
    assert not stale, f"낡은 주장: {[(c, n) for c, _, n, _ in stale]}"


def test_gold_teaches_no_vacuous_condition(gold):
    """정답에 언제나 참인 조건이 있으면 ⑥ 이 그것을 정답으로 가르친다."""
    assert not G.gold_vacuity(gold)


def test_detrimental_effects_never_approximate(gold):
    """불이익·관문 effect 를 가진 OK rule 은 조건이 완전해야 한다 — DECISIONS.md.

    오차가 고객에게 유리하면 근사를 허용하고, 불리하면 금지한다.
    아래 목록은 **완전하다고 확인한** rule 이다. 새 rule 이 여기 없이
    불이익 effect 로 OK 를 받으면 이 시험이 막는다.
    """
    CONFIRMED = {
        "KBONE-S2-R01-01",   # DISQUALIFY 1인 1계좌 — 조문에 타 상품 합산 문구 없음
        "KBONE-S2-R12-01",   # REQUIRE    인터넷·스타뱅킹 해지 시 본인 계좌 필요
        "KBONE-S2-R20-01",   # DISQUALIFY 1인 1계좌
        "KBYY-S2-R01-01",    # DISQUALIFY 만 19세 미만이 아니면 가입 불가
        "KBYY-S2-R01-03",    # DISQUALIFY 1인 1계좌 — '포함하여' 를 못 옮겨 좁다.
                             #            덜 박탈하므로 오차가 고객에게 유리하다
        "KBYY-S2-R07-02",    # LIMIT_AMOUNT 저금통 한도 100만원 — 조건 없음이 맞다
        "KBYY-S2-R23-01",    # DISQUALIFY 1인 1계좌 — 위와 같다
        "KBYY-S2-R23-03",    # LIMIT_AMOUNT 저금통 한도 100만원
    }
    BENEFIT = {"RATE_ADD", "RATE_OVERRIDE", "FEE_WAIVE"}
    unlisted = []
    for cid, d in gold.items():
        for r in d.get("rules") or []:
            eff = (r.get("effect") or {}).get("type")
            if r.get("status") == "OK" and eff and eff not in BENEFIT:
                if r.get("rule_id") not in CONFIRMED:
                    unlisted.append((cid, r.get("rule_id"), eff))
    assert not unlisted, (
        "불이익 effect 로 OK 를 받은 새 rule 이다. 조건이 완전한지 확인하고 "
        f"CONFIRMED 에 넣어라: {unlisted}")


def test_the_review_is_marked_provisional(gold):
    """사람 검토와 구별한다. reviewed 는 여전히 false 다."""
    for cid, d in gold.items():
        assert d.get("reviewed") is False, f"{cid} 가 사람 검토로 표시됐다"
        assert d.get("provisional_review", {}).get("by") == "claude"
