"""조건식 실행기 — 조건식 JSON 하나와 고객 ctx 하나로 판별을 낸다.

두 가지를 구분한다.

  데이터가 없다   → U. 정상이다. resolver 가 구간으로 받는다.
  조건식이 틀렸다 → DslError. ⑤ 실행 가능 실패다.

"없다" 와 "모른다" 도 구분한다. `ctx["events"]["SALARY_TRANSFER"] = []` 는
급여이체가 없었다는 뜻이고, `_provided` 에 그 키가 없으면 모른다는 뜻이다.
빈 리스트로 뭉개면 실적 없는 고객과 데이터 없는 고객이 같은 답을 받는다.

미바인딩 `$window` 가 DslError 의 대표다. `let` 없이 `{"ref": "$window"}` 를
쓰면 옛 구현은 KeyError 로 죽었다. 지금은 DslError 로 잡아 ⑤ 가 센다.

오류 메시지는 재시도 프롬프트에 그대로 들어간다. 메시지가 좋아지자 재시도
기여가 +10.8p 에서 +36.0p 로 커졌고 생성 호출은 257 에서 211 회로 줄었다 (§6.3).
그래서 "무엇이 왔고 올바른 형태가 무엇인지" 를 같이 적는다.
"""

import calendar
import datetime as _dt

import catalog
from tv import TV, tv_and, tv_not, tv_or


class DslError(Exception):
    """조건식 자체가 실행 불가능하다 — ⑤ 실패."""


class Judgement:
    """rule 하나의 판별 결과."""

    __slots__ = ("rule_id", "status", "value", "effect", "error")

    def __init__(self, rule_id, value, effect, error=None, skipped=False):
        self.rule_id = rule_id
        self.value = value
        self.effect = effect
        self.error = error
        if error is not None:
            self.status = "ERROR"
        elif skipped:
            self.status = "SKIPPED_GUARD"
        else:
            self.status = {TV.T: "MET", TV.F: "NOT_MET", TV.U: "UNKNOWN"}[value]

    def __repr__(self):
        return f"<{self.rule_id} {self.status}>"


# ── 날짜 ────────────────────────────────────────────────────────────────
def _date(v):
    if v is None:
        return None
    if isinstance(v, _dt.date):
        return v
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        raise DslError(f"날짜로 못 읽음: {v!r}. YYYY-MM-DD 형태여야 한다")


def _shift(d, n):
    y, m = d.year, d.month + n
    return y + (m - 1) // 12, (m - 1) % 12 + 1


def _anchor(spec, ctx):
    if not isinstance(spec, dict) or "anchor" not in spec:
        raise DslError('창의 from/to 에는 anchor 가 있어야 한다. 올바른 형태: '
                       '{"anchor": "contract.start_date", "offset_months": 0, "day": "first"}')
    name = spec["anchor"]
    if name not in catalog.VARIABLES:
        raise DslError(f"카탈로그에 없는 변수: {name}")
    base = _date(_lookup(name, ctx))
    if base is None:
        return None
    y, m = _shift(base, int(spec.get("offset_months", 0)))
    day = spec.get("day", base.day)
    if day == "first":
        d = 1
    elif day == "last":
        d = calendar.monthrange(y, m)[1]
    else:
        d = min(int(day), calendar.monthrange(y, m)[1])
    return _dt.date(y, m, d)


def _window(spec, ctx, env):
    if isinstance(spec, dict) and "ref" in spec:
        name = str(spec["ref"]).lstrip("$")
        if name not in env:
            raise DslError(f"미바인딩 참조: ${name}. "
                           f'let 에 먼저 묶어야 한다: {{"let": {{"{name}": {{...}}}}}}')
        spec = env[name]
    if not isinstance(spec, dict):
        raise DslError(f"창 명세가 아님: {spec!r}")
    if "month_range" not in spec:
        raise DslError(f"모르는 창 형태: {sorted(spec)}. 지금은 month_range 만 있다")
    mr = spec["month_range"]
    lo, hi = _anchor(mr.get("from"), ctx), _anchor(mr.get("to"), ctx)
    return None if lo is None or hi is None else (lo, hi)


# ── 값 ──────────────────────────────────────────────────────────────────
def _lookup(name, ctx):
    cur = ctx
    for part in name.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _operand(node, ctx, env):
    if not isinstance(node, dict):
        return node
    if "var" in node:
        name = node["var"]
        if name not in catalog.VARIABLES:
            raise DslError(f"카탈로그에 없는 변수: {name}")
        return _lookup(name, ctx)
    if "ref" in node:
        key = str(node["ref"]).lstrip("$")
        if key not in env:
            raise DslError(f"미바인딩 참조: ${key}")
        return env[key]
    if "anchor" in node:
        # 2026-09-15 최종거래일 확장. "최종거래일 이후 5년" 은 이벤트 창이 아니라
        # 날짜 하나와의 비교다 — 창의 from/to 와 같은 모양을 피연산자 자리에도 받는다.
        return _anchor(node, ctx)
    for op in catalog.COUNTERS:
        if op in node:
            return _count(op, node[op], ctx, env)
    raise DslError(f"피연산자가 아님: {sorted(node)}")


def _events(ctx, kind, win):
    """창 안의 해당 이벤트. 모르면 None."""
    if kind not in catalog.EVENTS:
        raise DslError(f"카탈로그에 없는 이벤트: {kind}. 쓸 수 있는 것: "
                       f"{', '.join(catalog.EVENTS)}")
    provided = ctx.get("_provided")
    declared = provided is not None and f"events.{kind}" in provided
    if provided is not None and not declared:
        return None                       # 데이터 미제공 — 없는 것과 다르다
    evs = (ctx.get("events") or {})
    if isinstance(evs, dict):
        evs = evs.get(kind)
        if evs is None:
            # 제공한다고 선언했으면 키가 없는 것은 "실적 0건" 이다
            evs = [] if declared else None
    else:
        evs = [e for e in evs if e.get("type") == kind]
    if evs is None:
        return None
    if win is None:
        return list(evs)
    out = []
    for e in evs:
        d = _date(e.get("date"))
        if d is not None and win[0] <= d <= win[1]:
            out.append(e)
    return out


def _match(e, where, kind):
    """이벤트 한 건이 where 를 만족하나 — T/F/U. 값이 없으면 U 다."""
    vals = []
    attrs = catalog.EVENT_ATTRIBUTES.get(kind, {})
    for key, want in where.items():
        if key == "min_amount":
            if isinstance(want, bool) or not isinstance(want, (int, float)):
                raise DslError(f"where 의 min_amount 는 수여야 한다: {want!r}. "
                               f'올바른 형태: {{"min_amount": 500000}}')
            a = e.get("amount")
            vals.append(TV.U if a is None else TV.of(a >= want))
            continue
        if key not in attrs:
            raise DslError(f"{kind} 에 없는 속성: {key}. 쓸 수 있는 것: min_amount"
                           + "".join(f", {a}" for a in attrs))
        if not isinstance(want, list):
            raise DslError(f"where 의 {key} 는 허용 값의 배열이어야 한다. "
                           f'올바른 형태: {{"{key}": ["{attrs[key][0]}"]}}')
        v = e.get(key)
        vals.append(TV.U if v is None else TV.of(v in want))
    return tv_and(vals) if vals else TV.T


def _filter(evs, spec, kind):
    """where 를 건 이벤트 → (확실히 맞는 것, 맞는지 모르는 것이 있나)."""
    where = spec.get("where")
    if where is None:
        return evs, False
    if not isinstance(where, dict) or not where:
        raise DslError('where 는 조건 객체여야 한다. 올바른 형태: '
                       '{"min_amount": 500000} 또는 {"route": ["GIRO", "CMS"]}')
    hit, unsure = [], False
    for e in evs:
        m = _match(e, where, kind)
        if m is TV.T:
            hit.append(e)
        elif m is TV.U:
            unsure = True
    return hit, unsure


def _count(op, spec, ctx, env):
    if not isinstance(spec, dict):
        raise DslError(f"{op}: 객체를 기대했으나 {type(spec).__name__} 이 옴")
    extra = set(spec) - {"event", "within", "where"}
    if extra:
        raise DslError(f"{op}: 모르는 키 {sorted(extra)}. 올바른 형태: "
                       f'{{">=": [{{"{op}": {{"event": …, "within": …, "where": …}}}}, 6]}}')
    win = _window(spec["within"], ctx, env) if "within" in spec else None
    if "within" in spec and win is None:
        return None
    evs = _events(ctx, spec.get("event"), win)
    if evs is None:
        return None
    evs, unsure = _filter(evs, spec, spec.get("event"))
    if unsure:
        return None                       # 한 건이라도 맞는지 모르면 수도 모른다
    if op == "count_events":
        return len(evs)
    months = sorted({_date(e.get("date")).strftime("%Y-%m")
                     for e in evs if _date(e.get("date")) is not None})
    if op == "count_distinct_months":
        return len(months)
    best = run = 0
    prev = None
    for ym in months:
        y, m = map(int, ym.split("-"))
        run = run + 1 if prev is not None and _shift(_dt.date(y, m, 1), -1) == prev else 1
        prev, best = (y, m), max(best, run)
    return best


# ── 조건식 ──────────────────────────────────────────────────────────────
def _compare(op, a, b):
    if a is None or b is None:
        return TV.U
    try:
        if op == "==":
            return TV.of(a == b)
        if op == "!=":
            return TV.of(a != b)
        if op == "in":
            return TV.of(a in b)
        # anchor 피연산자는 date 를 돌려준다 — 한쪽만 문자열이어도 날짜로 맞춘다
        if isinstance(a, (str, _dt.date)) and isinstance(b, (str, _dt.date)):
            a, b = _date(a), _date(b)
        return TV.of({">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op])
    except (TypeError, KeyError):
        raise DslError(f"비교할 수 없다: {op} 에 {a!r} 와 {b!r}")


def evaluate(node, ctx, env=None):
    env = env or {}
    if node is None or node == {}:
        return TV.T                       # 조건 없음 = 항상 적용
    if not isinstance(node, dict):
        raise DslError(f"조건식은 객체여야 한다. {type(node).__name__} 이 옴")
    if len(node) != 1:
        raise DslError(f"조건식의 키는 하나여야 한다: {sorted(node)}. "
                       f'여러 개를 묶으려면 {{"and": [ … ]}} 를 쓴다')

    (op, arg), = node.items()

    if op in ("and", "or"):
        if not isinstance(arg, list):
            raise DslError(f"{op}: 배열을 기대했으나 {type(arg).__name__} 이 옴. "
                           f'올바른 형태: {{"{op}": [ {{...}}, {{...}} ]}}')
        vals = [evaluate(x, ctx, env) for x in arg]
        return tv_and(vals) if op == "and" else tv_or(vals)

    if op == "not":
        return tv_not(evaluate(arg[0] if isinstance(arg, list) else arg, ctx, env))

    if op == "exists":
        if not isinstance(arg, dict):
            raise DslError(f'exists: 객체를 기대했으나 {type(arg).__name__} 이 옴. '
                           f'올바른 형태: {{"exists": {{"event": …, "within": …}}}}')
        win = _window(arg["within"], ctx, env) if "within" in arg else None
        if "within" in arg and win is None:
            return TV.U
        evs = _events(ctx, arg.get("event"), win)
        if evs is None:
            return TV.U
        hit, unsure = _filter(evs, arg, arg.get("event"))
        return TV.T if hit else TV.U if unsure else TV.F

    if op in catalog.COUNTERS:
        raise DslError(f"{op} 는 수를 돌려준다. 조건식이 되려면 비교로 감싸야 한다: "
                       f'{{">=": [{{"{op}": {{...}}}}, 6]}}')

    if op in catalog.COMPARISONS:
        if not isinstance(arg, list) or len(arg) != 2:
            raise DslError(f'{op}: 피연산자 2개가 필요하다. '
                           f'올바른 형태: {{"{op}": [ {{"var": "…"}}, 값 ]}}')
        return _compare(op, _operand(arg[0], ctx, env), _operand(arg[1], ctx, env))

    if op == "var":
        raise DslError('var 단독은 조건식이 아니다. 비교로 감싸야 한다: '
                       '{"==": [ {"var": "…"}, 값 ]}')

    raise DslError(f"정의되지 않은 연산자: {op}. 쓸 수 있는 것: "
                   f"{', '.join(catalog.OPERATORS)}")


def evaluate_rules(rules, ctx):
    """rule 목록 → Judgement 목록."""
    out = []
    for r in rules or []:
        rid = r.get("rule_id")
        eff = r.get("effect")
        try:
            env = dict(r.get("let") or {})
            if "guard" in r and evaluate(r["guard"], ctx, env) is TV.F:
                out.append(Judgement(rid, TV.F, eff, skipped=True))
                continue
            value = evaluate(r.get("condition"), ctx, env)
            if "guard" in r and evaluate(r["guard"], ctx, env) is TV.U and value is TV.T:
                value = TV.U
            out.append(Judgement(rid, value, eff))
        except DslError as e:
            out.append(Judgement(rid, TV.U, eff, error=str(e)))
        except Exception as e:
            # 생성물 때문에 채점기가 죽으면 안 된다. 못 본 형태는 실행 실패로 센다.
            out.append(Judgement(rid, TV.U, eff,
                                 error=f"{type(e).__name__}: {e}"))
    return out
