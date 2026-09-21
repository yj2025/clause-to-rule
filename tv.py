"""3치 논리 — 참 / 거짓 / 모름.

데이터가 없으면 거짓이 아니라 U 다. 급여이체 실적을 모르는 고객에게
우대금리를 "못 받는다" 로 답하면 안 된다. resolver 는 U 가 남으면 금리를
구간으로 내고 needs_review 를 세운다 (§7.2).

Kleene 의 강한 3치 논리를 쓴다. 모르는 값이 있어도 결론이 나는 두 경우가 요점이다.

    F and U = F     거짓이 하나 있으면 나머지는 볼 필요 없다
    T or  U = T     참이 하나 있으면 나머지는 볼 필요 없다
"""

import enum


class TV(enum.Enum):
    """판별 결과 세 값.

    `__bool__` 을 일부러 막아 두었다. `if tv:` 라고 쓰면 U 가 조용히
    거짓으로 떨어지는데, 그것이 이 파일이 막으려는 바로 그 사고다.
    """

    T = "TRUE"
    F = "FALSE"
    U = "UNKNOWN"

    def __bool__(self):
        raise TypeError("TV 를 그대로 참·거짓으로 쓰면 U 가 조용히 F 가 된다. "
                        "tv_and / tv_or 를 쓰거나 == TV.T 로 비교한다")

    @staticmethod
    def of(x):
        """파이썬 값을 TV 로. None 은 U 다."""
        if isinstance(x, TV):
            return x
        if x is None:
            return TV.U
        return TV.T if x else TV.F


def tv_not(a):
    """부정. **모르는 것의 부정은 여전히 모르는 것이다.**

    `not U = U` 가 2치 논리와 갈리는 자리다. "급여이체를 안 했다" 를
    모르면 "했다" 도 모른다.
    """
    a = TV.of(a)
    return TV.U if a is TV.U else (TV.F if a is TV.T else TV.T)


def tv_and(*args):
    """그리고. **거짓 하나가 모름을 이긴다** (`F and U = F`).

    조건 셋 중 하나가 확실히 거짓이면 나머지를 몰라도 결론이 난다.
    이 규칙이 없으면 데이터가 조금만 비어도 전부 U 로 뭉개진다.

    인수는 낱개로도 리스트로도 받는다 — `tv_and(a, b)` · `tv_and([a, b])`.
    빈 인수는 T 다 (조건 없음 = 항상 참).
    """
    vals = _flat(args)
    if any(v is TV.F for v in vals):
        return TV.F
    if any(v is TV.U for v in vals):
        return TV.U
    return TV.T


def tv_or(*args):
    """또는. **참 하나가 모름을 이긴다** (`T or U = T`).

    `tv_and` 와 대칭이다. 빈 인수는 F 다.
    """
    vals = _flat(args)
    if any(v is TV.T for v in vals):
        return TV.T
    if any(v is TV.U for v in vals):
        return TV.U
    return TV.F


def _flat(args):
    """중첩된 리스트를 펴서 TV 목록으로. 호출부가 모양을 안 맞춰도 되게 한다."""
    out = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out.extend(_flat(a))
        else:
            out.append(TV.of(a))
    return out
