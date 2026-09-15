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
        # FEE_WAIVE_NO_CARRYOVER 이월 불가 — 조문이 모든 면제에 건다. 조건 없음이 완전하다
        "KBONE-S2-R07-01",
        "KBONE-S2-R20-02",
        "KBYY-S5-R01-01",
        # DISQUALIFY 명의 유형 — 인용문이 나열한 유형을 그대로 옮겼다
        "KBONE-S2-R01-02",   # 개인 · 개인사업자 · 서류미제출 임의단체가 아니면 탈락
        "KBYY-S2-R01-02",    # 개인사업자 · 서류미제출 임의단체 · 공동명의면 탈락
        "KBYY-S2-R23-02",    # 공동명의면 탈락
        # DORMANT_CONTRIBUTION 휴면예금 출연 — 최종거래일 5년 경과 · 미해지 둘 다 옮겼다.
        # '만기일 또는' 갈래는 변수 정의(만기 지급도 거래)가 받는다
        "KBONE-S2-R17-01",
        "KBYY-S2-R20-01",
        # RESTRICT 거래유형별 금지 — 조문이 누구에게나 금지한다. 조건 없음이 완전하다
        "KBONE-S2-R14-01",   # 담보제공 불가
        "KBYY-S2-R16-01",    # 질권설정 불가
        "KBYY-S2-R17-01",    # 양도·상속에 의한 명의변경 불가
        "KBYY-S2-R17-02",    # 담보제공 불가
        # RESTRICT 거래중지 — 잔액 구간 · 무거래(입출금·명의변경) 둘 다 옮겼다.
        # 입출금 이벤트를 넓게 세어 오차는 고객에게 유리하다. 편입시기(연 2회)는
        # 절차로 두었다 — 사람 확인이 필요한 자리다 (DECISIONS.md)
        "KBONE-S2-R16-01",
        "KBYY-S2-R19-01",
    }
    BENEFIT = {"RATE_ADD", "RATE_OVERRIDE", "FEE_WAIVE", "SERVICE_PROVIDE"}
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


def test_reviewed_and_provisional_are_never_both_set(gold):
    """사람 검토와 잠정 판정을 구별한다.

    사람이 본 조문은 `reviewed: true` 와 `review` 를 갖고
    `provisional_review` 가 없어야 한다. 아직 안 본 조문은 그 반대다.
    2026-09-14 부터 사람 검토가 들어오기 시작했다.
    """
    done = []
    for cid, d in gold.items():
        if d.get("reviewed"):
            assert "provisional_review" not in d, f"{cid} 에 잠정 표시가 남았다"
            assert d.get("review", {}).get("by"), f"{cid} 에 검토자가 없다"
            done.append(cid)
        else:
            assert d.get("principles_applied", {}).get("by") == "claude", cid
            assert "provisional_review" not in d, cid
    assert done, "사람 검토가 하나도 없다"
