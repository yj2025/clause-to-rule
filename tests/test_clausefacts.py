"""조문 단위 사실 — 비율 대신 이것으로 판정한다.

**이 도구의 값은 「몇 조문이냐」가 아니라 「그 수가 흔들림 밖이냐」다.**
자기 검사가 없으면 조문 수도 비율과 같은 함정에 빠진다 — 처방이 없어도
줄이 밖으로 나간다.
"""


def test_facts_are_clause_sets_not_counts():
    """조문 **집합**이어야 한다. 수만 있으면 어느 조문이 움직였는지 못 본다."""
    import clausefacts as C
    f = C.facts(C.load("v45"))
    assert f, "아무것도 못 셌다"
    for k, v in f.items():
        assert isinstance(v, set), f"{k} 가 집합이 아니다"
        assert all(isinstance(c, str) for c in v)


def test_the_axes_that_survived_are_all_here():
    """판정선이 바뀌어도 버틴 사실들이 이 도구로 읽혀야 한다.

    v36(`RESTRICT`) · v39(`DORMANT_CONTRIBUTION`) · v41(`event.*` → `exists`) ·
    v46(지어낸 이름) · ⑮(타입 안 맞는 비교).
    """
    import clausefacts as C
    f = C.facts(C.load("v45"))
    for k in ("effect:RESTRICT", "effect:DORMANT_CONTRIBUTION",
              "기권(UNSUPPORTED)", "지어낸 이름", "타입 안 맞는 비교", "빈 배열"):
        assert k in f, f"{k} 를 안 센다"


def test_dormant_contribution_is_still_two_clauses():
    """v39 가 연 자리 — 다섯 프로세스 전부 2조문이다.

    이 시험이 깨지면 v39 판정에서 **유일하게 남은 주장**이 무너진 것이다.
    """
    import clausefacts as C
    for t in ("v41", "v43", "v44", "v45"):
        n = len(C.facts(C.load(t)).get("effect:DORMANT_CONTRIBUTION", ()))
        assert n == 2, f"{t}: {n}조문"
