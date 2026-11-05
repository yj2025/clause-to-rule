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
    """rule 하나의 판별 결과.

    `status` 가 다섯 가지인 것이 요점이다.

        MET / NOT_MET / UNKNOWN   조건식이 돌아갔다
        ERROR                     조건식이 실행 불가였다 (DslError)
        SKIPPED_GUARD             guard 가 먼저 걸러 조건을 안 봤다

    **ERROR 를 UNKNOWN 에 섞으면 안 된다.** 앞은 우리가 만든 조건식이
    틀린 것이고 (⑤ 가 센다), 뒤는 고객 데이터가 없는 것이다 (정상이다).
    """

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
    """무엇이 와도 `date` 로. 못 읽으면 U 가 아니라 **DslError** 다.

    값이 없는 것(None → None)과 값이 망가진 것(`"2026년 3월"` → 오류)을
    가른다. 앞은 «모른다», 뒤는 «조건식이 틀렸다» 라 ⑤ 로 센다.
    """
    if v is None:
        return None
    if isinstance(v, _dt.date):
        return v
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        raise DslError(f"날짜로 못 읽음: {v!r}. YYYY-MM-DD 형태여야 한다")


def _shift(d, n):
    """날짜에서 n 개월 옮긴 `(연, 월)`. 일(day)은 호출부가 따로 정한다.

    31일에서 한 달을 옮기면 없는 날이 되므로 일을 여기서 안 정한다.
    """
    y, m = d.year, d.month + n
    return y + (m - 1) // 12, (m - 1) % 12 + 1


WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _nth_weekday(y, m, weekday, nth):
    """그 달의 n째 아무 요일. 없으면 None (다섯째 금요일이 없는 달이 있다).

    「6월 셋째 금요일」 같은 날짜가 약관에 자주 나온다 — 거래중지 편입시기와
    이자 결산일이 둘 다 이 꼴이다 (2026-09-21 · 어휘 확장 2차 안건 1순위).
    """
    if weekday not in WEEKDAYS or not isinstance(nth, int) or not 1 <= nth <= 5:
        raise DslError(f"n째 요일이 아니다: {weekday!r} {nth!r}. "
                       f'요일은 {", ".join(WEEKDAYS)} 중 하나이고 nth 는 1~5 다')
    want = WEEKDAYS.index(weekday)
    first = _dt.date(y, m, 1)
    day = 1 + (want - first.weekday()) % 7 + (nth - 1) * 7
    return _dt.date(y, m, day) if day <= calendar.monthrange(y, m)[1] else None


def _resolve_day(y, m, day, base_day):
    """그 달 안에서 며칠인지. 없는 날은 말일로 줄인다."""
    last = calendar.monthrange(y, m)[1]
    if day == "first":
        return 1
    if day == "last":
        return last
    if day is None:
        return min(base_day, last)
    return min(int(day), last)


def _anchor(spec, ctx):
    """기준점 명세 → 실제 날짜. **변수가 비면 None** 을 돌려준다 (= 모른다).

        {"anchor": "contract.start_date", "offset_months": -6, "day": "first"}

    `day` 는 수 · `"first"` · `"last"` 를 받고, 그 달에 없는 날은 말일로 줄인다
    (1월 31일에서 한 달 뒤는 2월 28일이다).
    카탈로그에 없는 변수를 쓰면 DslError 다 — 조용히 넘기면 ③ 이 못 잡는다.

    **`month_of` 와 n째 요일** (2026-09-21). 「매년 6·12월 셋째 금요일」처럼
    해마다 돌아오는 날을 가리킨다.

        {"anchor": "contract.reference_date",
         "month_of": [6, 12], "day": {"weekday": "FRI", "nth": 3},
         "offset_days": 1}

    `month_of` 가 있으면 기준일에서 **뒤로 거슬러** 그 달들 중 가장 가까운
    날을 찾는다. 기준일보다 뒤면 그 앞 것을 쓴다. 손잡이를 적게 둔 것은
    일부러다 — «가장 가까운 지난 것» 하나만 있으면 약관이 말하는 것을
    다 담고, 고를 것이 없으면 모델이 틀릴 자리도 없다.

    «지난 것» 은 `offset_days` 를 **더한 뒤의 날**로 따진다 (2026-11-05 사람 검토).
    옛 구현은 n째 요일만 기준일 이하로 찾고 나서 날짜를 더해, 기준일이 셋째 금요일
    당일이면 다음 날(아직 안 온 편입일)을 돌려줬다 — 편입 전 계좌를 편입된 것으로 본다.
    """
    if not isinstance(spec, dict) or "anchor" not in spec:
        raise DslError('창의 from/to 에는 anchor 가 있어야 한다. 올바른 형태: '
                       '{"anchor": "contract.start_date", "offset_months": 0, "day": "first"}')
    name = spec["anchor"]
    if name not in catalog.VARIABLES:
        raise DslError(f"카탈로그에 없는 변수: {name}")
    base = _date(_lookup(name, ctx))
    if base is None:
        return None
    day = spec.get("day")
    months = spec.get("month_of")

    if months:
        if not isinstance(months, list) or not all(
                isinstance(x, int) and 1 <= x <= 12 for x in months):
            raise DslError(f"month_of 는 1~12 의 월 목록이다. 온 것: {months!r}")
        if not (isinstance(day, dict) and "weekday" in day):
            raise DslError('month_of 를 쓰면 day 는 n째 요일이어야 한다: '
                           '{"weekday": "FRI", "nth": 3}')
        off = int(spec.get("offset_days") or 0)
        got = _backwards(base - _dt.timedelta(days=off), sorted(set(months)), day)
        if got is None:
            raise DslError(f"{sorted(set(months))}월에서 n째 요일을 못 찾았다")
        y, m, d = got.year, got.month, got.day
        y, m = _shift(_dt.date(y, m, 1), int(spec.get("offset_months", 0)))
        d = min(d, calendar.monthrange(y, m)[1])
    else:
        if isinstance(day, dict):
            raise DslError('n째 요일을 쓰려면 month_of 로 어느 달인지 적어야 한다: '
                           '{"month_of": [6, 12], "day": {"weekday": "FRI", "nth": 3}}')
        y, m = _shift(base, int(spec.get("offset_months", 0)))
        d = _resolve_day(y, m, day, base.day)

    out = _dt.date(y, m, d)
    off = spec.get("offset_days")
    return out + _dt.timedelta(days=int(off)) if off else out


def _backwards(base, months, day):
    """`base` 이하이면서 `months` 에 드는 달의 n째 요일 중 **가장 가까운 것**.

    해를 최대 둘까지만 거슬러 본다 — 월 목록이 비어 있지 않으면 한 해 안에
    반드시 하나는 있으므로 둘이면 넉넉하다.
    """
    wd, nth = day.get("weekday"), day.get("nth", 1)
    for y in (base.year, base.year - 1, base.year - 2):
        best = None
        for m in months:
            got = _nth_weekday(y, m, wd, nth)
            if got is not None and got <= base and (best is None or got > best):
                best = got
        if best is not None:
            return best
    return None


def _window(spec, ctx, env):
    """기간 창 명세 → `(시작일, 끝일)`. 양끝 중 하나라도 모르면 None 이다.

    `{"ref": "$window"}` 면 `let` 에 묶인 것을 먼저 푼다. 안 묶여 있으면
    **DslError** 다 — 옛 구현은 KeyError 로 죽었고 그것이 ⑤ 의 대표 실패였다.
    지금은 창 형태가 `month_range` 하나뿐이다.
    """
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
    """`"customer.age"` 처럼 점으로 이어진 이름을 ctx 에서 꺼낸다.

    없으면 None 이다. **«없다» 와 «모른다» 를 가르는 것은 여기가 아니라
    호출부의 `_provided` 검사다** — 여기는 값만 꺼낸다.
    """
    cur = ctx
    for part in name.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _operand(node, ctx, env):
    """비교의 한쪽 피연산자를 값으로. 수·문자열 같은 날것은 그대로 돌려준다.

    받는 꼴은 넷이다 — `{"var": …}` · `{"ref": "$…"}` · `{"anchor": …}` ·
    그리고 집계(`count_*`). 카탈로그에 없는 변수는 DslError 다.
    """
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
    """이벤트를 센다 — 건수 · 서로 다른 달 수 · 연속한 달 수.

    셀 수 없으면 (이벤트 종류를 안 줬거나 창을 못 잡으면) **None** 이고,
    호출부가 그것을 U 로 바꾼다. 0 과 None 을 섞으면 «실적이 없는 고객» 과
    «데이터가 없는 고객» 이 같은 답을 받는다.
    """
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
    if op == "sum_events":
        # 금액이 하나라도 없으면 합도 모른다 — 0 으로 치면 «입금이 적은 고객»과 «금액을 모르는 고객»이 같은 답을 받는다
        amounts = [e.get("amount") for e in evs]
        if any(isinstance(a, bool) or not isinstance(a, (int, float)) for a in amounts):
            return None
        return sum(amounts)
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
    """피연산자 둘을 비교해 TV 로. **한쪽이라도 None 이면 U 다.**

    날짜는 한쪽만 문자열이어도 맞춰서 비교한다 (anchor 는 `date` 를 준다).
    타입이 안 맞아 비교 자체가 불가능하면 U 가 아니라 DslError 다.
    """
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
    """조건식 하나를 3치로 판별한다. 이 파일의 입구다.

    `node` 는 키가 **하나뿐인** 객체다 — `{"and": [...]}` · `{">=": [a, b]}`.
    키가 여럿이면 DslError 로 막는다. 모델이 자주 내는 실수라
    오류 메시지에 올바른 형태를 같이 적어 재시도에서 고치게 한다.

    `None` 과 `{}` 는 **조건 없음 = 항상 적용(T)** 이다. 빈 조건을 F 로
    두면 «누구에게나 걸리는 금지» 를 옮길 수 없다.

    `env` 는 `let` 이 묶은 이름들이다. 재귀로 내려갈 때 그대로 넘긴다.
    """
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
