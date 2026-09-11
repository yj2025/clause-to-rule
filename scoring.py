"""지표 ⑥ — 뜻이 맞는지 재기.

구조가 아니라 **실행 결과**를 비교한다. JSON 문자열이나 필드 일치율로 재면
잘못된 신호를 얻는다. 구조 유사도가 높은 생성물의 36% 가 결과 일치도 50% 미만이고,
결과 일치도가 높은 것의 39% 는 구조 유사도가 낮다 (§8).

gold 와 생성물을 **둘 다 실행해서** 결과를 비교한다. rule 을 2개로 쪼개든
1개로 합치든 고객에게 같은 금리가 나오면 같은 뜻이다.

outcome 에 `other_effects` 를 포함한다. 안 넣었더니 수수료 면제와 한도 0원을
⑥ 조차 구분하지 못했다. `rule_id` 는 일부러 뺀다 — 쪼갰는지 합쳤는지는 뜻이 아니다.
"""

from engine import evaluate_rules
from resolver import resolve


def _key(eff):
    """other_effect 하나를 비교 가능한 형태로. rule_id 는 빼고 status 는 넣는다."""
    return (eff.get("status"), eff.get("type"), eff.get("target"),
            str(eff.get("value")), eff.get("unit"))


def outcome(rules, ctx, aggregation="SUM", base_rate=0.0):
    """고객 한 명에게 이 조건식들이 내는 결과."""
    res = resolve(evaluate_rules(rules, ctx), aggregation, base_rate=base_rate)
    return (res.final_rate_min, res.final_rate_max, res.needs_review,
            res.disqualified, frozenset(_key(e) for e in res.other_effects))


def score(gold_rules, gen_rules, aggregation, profiles, base_rate=0.0):
    """gold 와 생성물을 모든 프로필에 돌려 결과가 같은 비율을 낸다.

    반환: {"rate": 0.0~1.0, "match": 맞은 수, "total": 프로필 수,
           "mismatch": 처음 어긋난 프로필 몇 개}
    """
    match, mismatch = 0, []
    for name, ctx in profiles:
        a = outcome(gold_rules, ctx, aggregation, base_rate)
        b = outcome(gen_rules, ctx, aggregation, base_rate)
        if a == b:
            match += 1
        elif len(mismatch) < 5:
            mismatch.append({"profile": name, "gold": a, "gen": b})
    total = len(profiles) or 1
    return {"rate": match / total, "match": match, "total": len(profiles),
            "mismatch": mismatch}
