"""판별 결과 → 최종 적용금리.

하나의 숫자로 뭉개지 않는다. 모르는 것이 남으면 **구간**으로 낸다.
급여이체 데이터가 없는 고객은 0.10~1.10 이고 needs_review 가 선다 (§7.2).

override 가 지운 rule 은 기록한다. 안 그러면 조용히 우대금리를 지우고도
①~⑤ 를 전부 통과할 수 있다 (§9 17번).

한계 — exclusive_groups 는 금리 effect 에만 적용된다. 이 상품의 핵심 혜택은
금리가 아니라 수수료 면제인데 배타 처리가 거기까지 안 간다 (§9 남은 작업 5번).
"""

import catalog
from tv import TV

_RATE = {"RATE_ADD": 1, "RATE_SUBTRACT": -1, "PENALTY_RATE": -1}


class Resolution:
    """최종 금리 한 건. min 과 max 가 다르면 아직 모르는 것이 있다는 뜻이다."""

    __slots__ = ("base_rate", "min", "max", "needs_review", "applied",
                 "unknown", "overridden_rules", "other_effects", "disqualified")

    def __init__(self, base_rate):
        self.base_rate = base_rate
        self.min = self.max = base_rate
        self.needs_review = False
        self.applied, self.unknown, self.overridden_rules = [], [], []
        self.other_effects, self.disqualified = [], False

    @property
    def final_rate_min(self):
        """구간의 아래끝. 모르는 감점이 전부 걸린다고 봤을 때의 금리."""
        return f"{self.min:.2f}"

    @property
    def final_rate_max(self):
        """구간의 위끝. 모르는 우대가 전부 걸린다고 봤을 때의 금리."""
        return f"{self.max:.2f}"

    def __repr__(self):
        return (f"<{self.final_rate_min}~{self.final_rate_max}"
                f"{' 검토필요' if self.needs_review else ''}>")


def _delta(eff):
    """금리 effect 하나가 더하거나 빼는 값. 금리가 아닌 effect 는 0.0 이다.

    값이 수가 아니면 (모델이 `"0.5%"` 같은 문자열을 낸 때) 0.0 으로 둔다 —
    여기서 터뜨리지 않는 이유는 ⑤ 가 이미 그것을 세고 있기 때문이다.
    `bool` 은 `int` 의 하위형이라 명시적으로 뺀다.
    """
    sign = _RATE.get(eff.get("type"))
    if sign is None:
        return 0.0
    v = eff.get("value")
    return sign * float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def resolve(judgements, aggregation="SUM", base_rate=0.0):
    """판별 목록 → Resolution.

    aggregation 은 금리 effect 를 합치는 방식이다. 지금은 SUM 과 MAX 만 있다.

    처리 순서가 곧 우선순위다.

    1. **DISQUALIFY 가 먼저다.** 확정이면 우대를 전부 버리고 기본금리만 낸다.
       모르면 단정하지 않고 `needs_review` 만 세운다
    2. 금리가 아닌 effect(수수료 면제 · 제한 · 상품 전환 …)는 `other_effects`
       로 모은다. 금리 구간 계산에 섞지 않는다
    3. **RATE_OVERRIDE 는 덮어쓴다.** 지워 버린 rule 을 `overridden_rules` 에
       남긴다 — 안 그러면 우대금리를 조용히 지우고도 관문을 다 통과한다
    4. 나머지 금리 effect 를 합친다. **MET 은 구간을 고정하고 UNKNOWN 은
       구간을 벌린다** — 모르는 감점은 아래끝에, 모르는 우대는 위끝에 넣는다

    U 가 하나라도 관여하면 `needs_review` 가 선다. 단정하지 않는 것이 규칙이다.
    """
    if aggregation not in ("SUM", "MAX"):
        raise ValueError(f"모르는 aggregation: {aggregation}")

    res = Resolution(float(base_rate))

    # 자격 상실이 확정이면 우대는 전부 무효다.
    for j in judgements:
        if (j.effect or {}).get("type") == "DISQUALIFY":
            if j.status == "MET":
                res.disqualified = True
            elif j.status == "UNKNOWN":
                res.needs_review = True

    met, unk, override = [], [], None
    for j in judgements:
        eff = j.effect or {}
        t = eff.get("type")
        if j.error:
            res.needs_review = True
            continue
        if t in ("FEE_WAIVE", "LIMIT_AMOUNT", "REQUIRE", "SERVICE_PROVIDE",
                 "FEE_WAIVE_NO_CARRYOVER", "DORMANT_CONTRIBUTION", "RESTRICT",
                 "TAX_EXEMPT_ELIGIBLE", "PRODUCT_SWITCH_TO", "STATE_CHANGE"):
            if j.status in ("MET", "UNKNOWN"):
                res.other_effects.append({"rule_id": j.rule_id, "status": j.status, **eff})
            if j.status == "UNKNOWN":
                res.needs_review = True
            continue
        if t == "RATE_OVERRIDE" and j.status == "MET":
            override = j
        elif t in _RATE:
            (met if j.status == "MET" else unk if j.status == "UNKNOWN" else []).append(j)
        if j.status == "UNKNOWN" and t in _RATE:
            res.needs_review = True

    if res.disqualified:
        res.min = res.max = res.base_rate
        res.applied = []
        return res

    if override is not None:
        v = (override.effect or {}).get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            res.min = res.max = float(v)
        res.applied = [override.rule_id]
        res.overridden_rules = [j.rule_id for j in met + unk]
        if unk:
            res.needs_review = True
        return res

    pos = [_delta(j.effect) for j in met]
    if aggregation == "SUM":
        fixed = sum(pos)
    else:
        fixed = max(pos, default=0.0)

    maybe = [_delta(j.effect) for j in unk]
    lo = fixed + (sum(d for d in maybe if d < 0) if aggregation == "SUM" else 0.0)
    hi = fixed + (sum(d for d in maybe if d > 0) if aggregation == "SUM"
                  else max(maybe, default=0.0))

    res.min = res.base_rate + lo
    res.max = res.base_rate + hi
    res.applied = [j.rule_id for j in met]
    res.unknown = [j.rule_id for j in unk]
    if unk:
        res.needs_review = True
    return res
