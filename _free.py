"""카탈로그 정의역 전체를 훑는 문맥 표본.

`gold.profiles()` 는 골드 채점용이라 축이 여덟 개뿐이다. `term_months` 는
12 로, `reference_date` 는 한 날짜로 **고정**돼 있다. 그래서
`term_months >= 12` 같은 조건이 "프로필 전부에서 참" 으로 잡힌다 —
모델의 헛조건이 아니라 **내 프로필의 구멍**이다.

여기서는 카탈로그가 선언한 타입과 열거값만 보고 값을 넓게 뽑는다.
이 표본에서 반례가 나오면 "미가동", 안 나오면 "헛조건" 이다.
"""

import random

import catalog

_INT = [0, 1, 5, 6, 11, 12, 13, 24, 36, 9_999, 1_000_000, 50_000_000]
_NUM = [0.0, 0.1, 1.5, 3.0, 5.5, 12.0]
_DATE = ["2019-01-01", "2021-06-30", "2023-04-10", "2023-04-11", "2024-02-29",
         "2026-01-01", "2026-08-15", "2026-09-11", "2026-12-01", "2030-05-05"]
_BOOL = [True, False]

_EVENT_DATES = ["2025-03-10", "2026-02-15", "2026-08-10", "2026-08-25",
                "2026-09-05"]


def _value(rng, spec):
    t = spec["type"]
    if t == "int":
        return rng.choice(_INT)
    if t == "num":
        return rng.choice(_NUM)
    if t == "date":
        return rng.choice(_DATE)
    if t == "bool":
        return rng.choice(_BOOL)
    return None


def _ctx(rng):
    ctx = {"customer": {}, "account": {}, "contract": {}, "events": {}}
    for name, spec in catalog.VARIABLES.items():
        group, _, key = name.partition(".")
        if spec["type"] == "enum":
            ctx[group][key] = rng.choice(catalog.ENUM_VALUES[name])
        else:
            ctx[group][key] = _value(rng, spec)
    # 나이와 Youth 는 묶여 있다 — 따로 뽑으면 있을 수 없는 문맥이 된다
    age = rng.choice([7, 18, 19, 30, 64, 80])
    ctx["customer"]["age"] = age
    ctx["customer"]["is_youth"] = age < 19

    for name in catalog.EVENTS:
        n = rng.choice([0, 0, 1, 2, 4])
        ctx["events"][name] = [
            {"date": rng.choice(_EVENT_DATES), "amount": rng.choice(_INT)}
            for _ in range(n)]

    ctx["_provided"] = ([f"events.{k}" for k in catalog.EVENTS]
                        + list(catalog.VARIABLES))
    return ctx


def sample(n=400, seed=20260913):
    """정의역을 넓게 훑는 문맥 n개. 씨앗 고정 — 라운드 사이 비교 가능하게."""
    rng = random.Random(seed)
    return [_ctx(rng) for _ in range(n)]
