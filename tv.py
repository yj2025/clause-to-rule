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
    a = TV.of(a)
    return TV.U if a is TV.U else (TV.F if a is TV.T else TV.T)


def tv_and(*args):
    vals = _flat(args)
    if any(v is TV.F for v in vals):
        return TV.F
    if any(v is TV.U for v in vals):
        return TV.U
    return TV.T


def tv_or(*args):
    vals = _flat(args)
    if any(v is TV.T for v in vals):
        return TV.T
    if any(v is TV.U for v in vals):
        return TV.U
    return TV.F


def _flat(args):
    out = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out.extend(_flat(a))
        else:
            out.append(TV.of(a))
    return out
