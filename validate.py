"""검증기 — ①~⑤ 와 ⑦.

각 check_* 는 **오류 문자열 목록**을 돌려준다. 빈 목록이 통과다.

    통과 여부는  not check_catalog(rule)  으로 읽는다.

메시지는 재시도 프롬프트에 그대로 들어간다 (§6.3). 무엇이 틀렸는지가 아니라
**무엇을 대신 써야 하는지**를 적는다.

⑤ 의 채점 계약은 9/8 에 두 번 바뀌었고 지금은 세 번째다 (§9).
  ② 빈 배열을 ⑦ 로 뗀다 — 빈 배열이 ③④⑤ 를 공짜로 통과하던 것을 끊었다
  ③ check_effect_value 추가 — 금리 effect 의 value 가 수가 아니면 실패다
앞으로의 비교는 이 계약으로 한다.
"""

import copy
import json
import re

import jsonschema

import catalog
import invent
from engine import DslError, evaluate
from schema import SCHEMA

_validator = jsonschema.Draft202012Validator(SCHEMA)


# ── ② 스키마 ────────────────────────────────────────────────────────────
def check_schema(output):
    """② 스키마 적합 — 출력 전체가 `schema.SCHEMA` 를 지키나.

    오류 **목록**을 돌려준다 (빈 목록 = 통과). 이 문구가 재시도 프롬프트에
    그대로 들어가므로 메시지가 곧 성능이다 — v6 에서 메시지를 고치자
    재시도 기여가 +10.8p 에서 +36.0p 로 커졌다.
    """
    return [_phrase(e) for e in _validator.iter_errors(output)]


# 재시도 프롬프트가 이 문구를 그대로 모델에게 돌려준다. rule 전체를 찍으면
# 무엇이 문제인지 안 보인다. 규칙이 분명한 것은 사람 말로 바꿔 준다.
def _phrase(e):
    """jsonschema 오류를 사람 말로. 규칙이 분명한 것만 바꾼다.

    `allOf` 위반은 라이브러리가 rule 전체를 찍어 주는데 그러면 무엇이
    문제인지 안 보인다. 조건 없는 DISQUALIFY 가 대표라서 그것만 따로 짚고,
    **무엇을 해야 하는지까지** 적는다 (\"옮길 조건이 없으면 UNSUPPORTED\").
    """
    at = "/".join(str(p) for p in e.path) or "최상위"
    # 2026-09-21 · v31. 조건식을 재귀로 검사하게 되면서 jsonschema 가
    # `is not valid under any of the given schemas` 만 돌려주기 시작했다.
    # **모델이 그 말로는 못 고친다.** 조건식은 우리가 직접 짚어 준다.
    if e.path and e.path[-1] in ("condition", "guard"):
        why = _why_condition(e.instance)
        if why:
            return f"조건식이 틀렸다: {why} (위치 {at})"
    if e.validator == "allOf" or "'DISQUALIFY'" in str(e.message)[:400]:
        inst = e.instance if isinstance(e.instance, dict) else {}
        eff = (inst.get("effect") or {}).get("type")
        if eff == "DISQUALIFY" and not (inst.get("condition") or inst.get("guard")):
            return (f"스키마 위반: DISQUALIFY 에는 condition 이나 guard 가 있어야 한다. "
                    f"비어 있으면 모든 고객이 예금 자격을 잃는다. "
                    f"옮길 조건이 없으면 status 를 UNSUPPORTED 로 한다 (위치 {at})")
    return f"스키마 위반: {e.message} (위치 {at})"


# ── 조건식을 짚어 주기 ──────────────────────────────────────────────────
# v31. 스키마가 잡아 주는 것과 **무엇을 고쳐야 하는지 말해 주는 것**은 다르다.
# v6 에서 메시지가 좋아지자 재시도 기여가 +10.8p → +36.0p 로 커졌고,
# v25 는 그 반대를 보여 줬다 — 막기만 하면 낱말만 바꾸며 재시도를 태운다.
_OPS = sorted(catalog.COMPARISONS) + ["and", "or", "not", "exists"] + sorted(catalog.COUNTERS)


def _why_operand(v, where):
    """비교의 한쪽이 왜 틀렸는지. 멀쩡하면 None."""
    if not isinstance(v, dict):
        return None                                   # 수·문자열은 그대로 쓴다
    # 기준점은 키를 여럿 갖는다 (anchor · month_of · day · offset_*) — 먼저 본다
    if "anchor" in v:
        return _why_anchor(v, where)
    if len(v) != 1:
        return None                                   # 바깥에서 이미 짚는다
    (k, arg), = v.items()
    if k in catalog.COUNTERS:
        return _why_eventspec(arg, f"`{k}`")
    if k == "var":
        if arg in catalog.COUNTERS:
            return (f"{where}의 `{arg}` 는 변수가 아니라 **집계**다. "
                    f'{{"{arg}": {{...}}}} 꼴로 쓰고 비교로 감싼다: '
                    f'{{">=": [{{"{arg}": {{...}}}}, 6]}}')
        if arg not in catalog.VARIABLES:
            # 2026-09-23 · v41. **이벤트를 변수 자리에 쓴다.** `event.type` 이 네
            # 라운드 내내 지어낸 이름 1위다 (28회 · 2조문). 그런데 이 모델은
            # `exists` 를 **이미 여덟 조문에서 쓰고 있고**, `KBYY-S2-R09` 는 같은
            # 출력 안에서 `exists` 를 쓰면서 `event.*` 변수도 쓴다 — 수단을 모르는
            # 것이 아니라 **자리를 헷갈리는 것**이다.
            #
            # 이 라운드는 가설을 시험한다 — 「이미 쓰는 수단을 다른 자리에 쓰라」는
            # 먹히고(v31 · v33 · v39) 「안 쓰던 것을 새로 쓰라」는 안 먹힌다
            # (v34 · v40). 여기는 앞쪽이다.
            if arg.startswith("event."):
                return (f"{where}의 이벤트는 **변수 자리에 오지 않는다.** "
                        '거래가 있었는지는 {"exists": {"event": …}} 로 묻고, '
                        '횟수는 집계로 센다. 쓸 수 있는 이벤트 이름은 지문의 '
                        '[이벤트] 에 있다')
            return (f"{where}에 카탈로그에 없는 변수: `{arg}`. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.VARIABLES))}")
    elif k == "anchor":
        return _why_anchor(v, where)
    elif k == "ref":
        return None
    elif k in _OPS:
        return f"{where}에 조건식이 왔다. 비교의 피연산자는 값이어야 한다"
    return None



_WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _why_anchor(spec, where):
    """기준점이 왜 틀렸는지. 멀쩡하면 None.

    2026-09-21 에 n째 요일을 더하면서 붙였다. 「6·12월 셋째 금요일」은
    손잡이가 셋(`month_of` · `weekday` · `nth`)이라 틀릴 자리가 많다.
    """
    if spec.get("anchor") not in catalog.VARIABLES:
        return (f"{where}의 anchor 가 카탈로그에 없는 변수다: `{spec.get('anchor')}`. "
                f"쓸 수 있는 것: {', '.join(sorted(catalog.VARIABLES))}")
    day = spec.get("day")
    months = spec.get("month_of")
    if isinstance(day, dict):
        wd, nth = day.get("weekday"), day.get("nth")
        if wd not in _WEEKDAYS:
            return (f"요일은 영문 세 글자다: {', '.join(_WEEKDAYS)}. 온 것: {wd!r}")
        if not isinstance(nth, int) or not 1 <= nth <= 5:
            return f"nth 는 1~5 다 (몇째 {wd} 인가). 온 것: {nth!r}"
        if not months:
            return ('n째 요일을 쓰려면 어느 달인지 같이 적는다: '
                    '{"anchor": "contract.reference_date", "month_of": [6, 12], '
                    '"day": {"weekday": "FRI", "nth": 3}}')
    if months is not None:
        if not isinstance(months, list) or not all(
                isinstance(x, int) and 1 <= x <= 12 for x in months):
            return f"month_of 는 1~12 의 월 목록이다: [6, 12]. 온 것: {months!r}"
        if not isinstance(day, dict):
            return ('month_of 를 쓰면 day 는 n째 요일이어야 한다: '
                    '{"weekday": "FRI", "nth": 3}')
    extra = set(spec) - {"anchor", "offset_months", "offset_days", "month_of", "day"}
    if extra:
        return (f"기준점에 모르는 키: {sorted(extra)}. 쓸 수 있는 것: "
                "anchor · offset_months · offset_days · month_of · day")
    return None



def _why_eventspec(spec, where):
    """`exists` · 집계가 받는 것이 왜 틀렸는지. 멀쩡하면 None.

    2026-09-22 · v32 판정. 모델이 **기준점을 창 자리에** 넣었다 —
    둘 다 `anchor` 를 품어 닮았는데 뜻이 다르다. 전에는 ⑤ 에서만 잡혀
    재시도가 못 고쳤다. ② 로 올리고 무엇이 다른지 말해 준다.
    """
    if not isinstance(spec, dict):
        return f"{where}는 객체여야 한다. {type(spec).__name__} 이 왔다"
    ev = spec.get("event")
    if ev not in catalog.EVENTS:
        return (f"{where}의 event 가 카탈로그에 없다: `{ev}`. "
                f"쓸 수 있는 것: {', '.join(sorted(catalog.EVENTS))}")
    win = spec.get("within")
    if win is not None:
        if not isinstance(win, dict):
            return f"{where}의 within 은 객체여야 한다"
        if "anchor" in win:
            return ('within 에는 **창**이 온다. 기준점(anchor)이 아니다 — '
                    '창은 시작과 끝이 있다: '
                    '{"within": {"month_range": {"from": {"anchor": …}, "to": {"anchor": …}}}}. '
                    'let 에 묶었으면 {"within": {"ref": "$window"}} 로 쓴다')
        if "ref" not in win and "month_range" not in win:
            return (f'{where}의 within 이 창이 아니다. 온 키: {sorted(win)}. '
                    'month_range 를 쓰거나 let 에 묶어 {"ref": "$…"} 로 부른다')
        if "month_range" in win:
            mr = win["month_range"]
            if not isinstance(mr, dict) or set(mr) != {"from", "to"}:
                return ('month_range 는 from 과 to 를 둘 다 받는다: '
                        '{"month_range": {"from": {"anchor": …}, "to": {"anchor": …}}}')
            for end in ("from", "to"):
                why = _why_anchor(mr[end], f"창의 {end}") if isinstance(mr[end], dict) else None
                if why:
                    return why
    extra = set(spec) - {"event", "within", "where"}
    if extra:
        return (f"{where}에 모르는 키: {sorted(extra)}. "
                "쓸 수 있는 것: event · within · where")
    return None


def _why_condition(node, where="조건"):
    """조건식이 왜 스키마를 못 지키는지 **한 문장**으로. 멀쩡하면 None.

    재귀로 내려가며 처음 만난 문제를 짚는다. 여러 개를 한꺼번에 쏟으면
    재시도 프롬프트가 오염된다 — v29 에서 아흔 개짜리 목록을 돌려준 적이 있다.
    """
    if node in (None, {}):
        return None
    if not isinstance(node, dict):
        return f"{where}은 객체여야 한다. {type(node).__name__} 이 왔다"

    keys = sorted(node)
    if len(node) != 1:
        if set(keys) >= {"left", "right"}:
            return ('조건식은 `{"연산자": [왼쪽, 오른쪽]}` 꼴이다. '
                    '`left`/`op`/`right` 를 따로 두지 않는다 — '
                    '예: {"==": [{"var": "customer.age"}, 19]}')
        return (f"{where}의 키는 하나여야 한다. 온 것: {keys}. "
                f'여러 개를 묶으려면 {{"and": [ … ]}} 를 쓴다')

    (op, arg), = node.items()

    if op not in _OPS:
        if op == "var":
            return ('`var` 단독은 조건식이 아니다. 비교로 감싼다: '
                    '{"==": [{"var": "…"}, 값]}')
        return (f"정의되지 않은 연산자: `{op}`. 쓸 수 있는 것: {', '.join(_OPS)}")

    if op in ("and", "or"):
        if not isinstance(arg, list):
            return f'`{op}` 는 배열을 받는다. {{"{op}": [ {{...}}, {{...}} ]}}'
        for x in arg:
            why = _why_condition(x, where="안쪽 조건")
            if why:
                return why
        return None

    if op == "not":
        return _why_condition(arg[0] if isinstance(arg, list) else arg, where="not 안쪽")

    if op == "exists":
        return _why_eventspec(arg, "exists")

    if op in catalog.COUNTERS:
        return (f"`{op}` 는 수를 돌려준다. 조건식이 되려면 비교로 감싼다: "
                f'{{">=": [{{"{op}": {{...}}}}, 6]}}')

    if op in catalog.COMPARISONS:
        if not isinstance(arg, list) or len(arg) != 2:
            n = len(arg) if isinstance(arg, list) else "배열이 아닌 것"
            return f"`{op}` 는 피연산자 2개를 받는다. 온 것: {n}"
        if op == "in":
            if not isinstance(arg[1], (list, dict)):
                return ('`in` 의 오른쪽은 목록이다 — 그대로 적거나(["A", "B"]) '
                        '목록을 값으로 갖는 변수여야 한다')
            # 왼쪽이 값이고 오른쪽이 목록 변수인 꼴도 맞다 (「보유 갈래에 X 가 있나」)
            return _why_operand(arg[0], "`in` 의 왼쪽 ") or _why_operand(arg[1], "`in` 의 오른쪽 ")
        for i, v in enumerate(arg):
            why = _why_operand(v, f"`{op}` 의 {'왼쪽' if i == 0 else '오른쪽'} ")
            if why:
                return why
    return None


# ── ③ 카탈로그 ──────────────────────────────────────────────────────────
def _walk(node, hit):
    """중첩된 조건식을 훑어 `(키, 값)` 쌍을 전부 모은다.

    조건식은 깊이가 정해져 있지 않아서 («and 안의 or 안의 비교») 평평하게
    펴 놓고 이름을 검사한다.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            hit.append((k, v))
            _walk(v, hit)
    elif isinstance(node, list):
        for v in node:
            _walk(v, hit)
    return hit


def check_catalog(rule):
    """③ 카탈로그 준수 — rule 이 **있는 이름만** 쓰나.

    변수 · 이벤트 · effect · 단위, 그리고 effect 종류마다 다른 **대상 목록**을
    본다. 없는 이름을 쓰면 실행기가 못 읽고, 있는 이름을 틀린 자리에 쓰면
    뜻이 조용히 달라진다 (`RESTRICT::WITHDRAWAL` 처럼).

    메시지에 **그 자리에 쓸 수 있는 것**을 같이 적는다. 2026-09-21 에
    스키마에서도 자리를 가르면서 이 목록이 짧아졌다.
    """
    errs = []
    hit = _walk({k: rule.get(k) for k in ("condition", "guard", "let")}, [])

    for k, v in hit:
        if k == "var" and isinstance(v, str) and v not in catalog.VARIABLES:
            errs.append(f"카탈로그에 없는 변수: {v}. 쓸 수 있는 것: "
                        f"{', '.join(sorted(catalog.VARIABLES))}")
        elif k == "event" and isinstance(v, str) and v not in catalog.EVENTS:
            errs.append(f"카탈로그에 없는 이벤트: {v}. 쓸 수 있는 것: "
                        f"{', '.join(sorted(catalog.EVENTS))}")
        elif k == "anchor" and isinstance(v, str) and v not in catalog.VARIABLES:
            errs.append(f"카탈로그에 없는 기준 변수: {v}")

    # 이벤트 where 의 속성 이름과 값 (2026-09-15 확장 여섯째)
    for k, v in hit:
        if k in ("exists",) + catalog.COUNTERS and isinstance(v, dict) \
                and isinstance(v.get("where"), dict):
            kind = v.get("event")
            attrs = catalog.EVENT_ATTRIBUTES.get(kind, {}) if isinstance(kind, str) else {}
            for a, want in v["where"].items():
                if a == "min_amount":
                    continue
                if a not in attrs:
                    errs.append(f"{kind} 에 없는 속성: {a}. 쓸 수 있는 것: min_amount"
                                + "".join(f", {x}" for x in attrs))
                elif isinstance(want, list):
                    bad = [x for x in want if x not in attrs[a]]
                    if bad:
                        errs.append(f"{kind}.{a} 의 값이 아님: {bad}. 쓸 수 있는 것: "
                                    f"{', '.join(attrs[a])}")

    # enum 변수를 카탈로그에 없는 값과 비교하는 경우
    for k, v in hit:
        if k in catalog.COMPARISONS and isinstance(v, list) and len(v) == 2:
            left, right = v
            if isinstance(left, dict) and "var" in left and isinstance(right, str):
                name = left["var"]
                if not catalog.is_known_value(name, right):
                    errs.append(f"{name} 의 값이 아님: {right}. 쓸 수 있는 것: "
                                f"{', '.join(catalog.ENUM_VALUES[name])}")
            # 2026-10-03 · v101. `in` 의 **목록** 안 값은 안 봤다 — `holder_type in [..., "REGISTERED_ASSOCIATION"]`
            # 이 ③ 을 조용히 통과했다(코퍼스 v86~v100 · kb10 다섯 판에서 DB 밖 값 9조문). 목록의 값도 본다.
            elif (k == "in" and isinstance(left, dict) and left.get("var") in catalog.ENUM_VALUES
                    and isinstance(right, list)):
                name = left["var"]
                bad = [x for x in right if isinstance(x, str) and not catalog.is_known_value(name, x)]
                if bad:
                    errs.append(f"{name} 의 값이 아님: {', '.join(bad)}. 쓸 수 있는 것: "
                                f"{', '.join(catalog.ENUM_VALUES[name])}")

    # effect 의 문자열 값에 지어낸 코드를 담는 경로를 막는다.
    #
    # 스키마가 REQUIRE/DISQUALIFY 의 value 를 자유 문자열로 허용해서, 모델이
    # 카탈로그에 없는 개념을 대문자 코드로 지어내 그 자리에 담았다 —
    # "PLEDGE_NOT_ALLOWED" · "TAXABLE" · "REAL_NAME". v10 에서 16개 중 12개다.
    # ③ 이 condition 안의 이름만 보느라 못 잡던 자리다.
    #
    # 한글 설명문은 막지 않는다. 대문자 코드형만 본다.
    errs += invent.check_rule(rule)

    # 2026-09-16 · v24. ⑬ 은 "카탈로그 어딘가에 있나" 만 본다 — 자리는 **③ 이
    # 본다.** 확장으로 새 이름이 들어올 때마다 그 이름이 REQUIRE/DISQUALIFY 의
    # value 로도 공짜로 통과하게 되는데, 실행기는 그 자리에서 읽지 않는다.
    # v24 에서 `REQUIRE value=INDIVIDUAL` 과 `DISQUALIFY value=ALL_TRANSACTIONS`
    # 가 관문 다섯을 전부 통과했다. gold 는 REQUIRE 를 한 번도 쓰지 않고
    # DISQUALIFY 의 value 가 전부 None 이라 **이 제약의 비용은 0 이다.**
    _eff = rule.get("effect") or {}
    if _eff.get("type") in ("REQUIRE", "DISQUALIFY"):
        _v = _eff.get("value")
        _slot = catalog.slot_of(_v.strip()) if isinstance(_v, str) else None
        if _slot:
            errs.append(f"{_eff['type']} 의 value \"{_v.strip()}\" 는 {_slot} 코드다. "
                        f"거기서 쓴다 — 실행기는 {_eff['type']} 의 value 를 읽지 않는다")

    eff = rule.get("effect") or {}
    t = eff.get("type")
    if t is not None and t not in catalog.EFFECTS:
        errs.append(f"카탈로그에 없는 effect: {t}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.EFFECTS))}")
    # `in` 검사 전에 해시 가능한지 본다. 모델이 target 이나 unit 에
    # **배열**을 넣으면 `x in set` 이 TypeError 로 죽는다 — v19 에서 라운드가
    # 37/46 에서 멈췄다. 생성물 때문에 검증기가 죽으면 안 된다.
    def _known(v, vocab):
        """`v in vocab` 을 안전하게. **배열이 와도 검증기가 안 죽는다.**

        모델이 target 에 배열을 넣으면 `x in set` 이 TypeError 로 죽는다 —
        v19 에서 라운드가 37/46 에서 멈췄다. 생성물 때문에 검증기가
        죽으면 그 라운드를 통째로 버린다.
        """
        try:
            return v in vocab
        except TypeError:
            return False

    if t == "FEE_WAIVE" and not _known(eff.get("target"), catalog.FEES):
        errs.append(f"수수료 대상이 아님: {eff.get('target')}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.FEES))}")
    if t == "SERVICE_PROVIDE" and not _known(eff.get("target"), catalog.SERVICES):
        errs.append(f"제휴서비스 대상이 아님: {eff.get('target')}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.SERVICES))}")
    if (t == "FEE_WAIVE_NO_CARRYOVER" and eff.get("target") is not None
            and not _known(eff.get("target"), catalog.FEES)):
        errs.append(f"수수료 대상이 아님: {eff.get('target')}. 모든 면제에 걸리면 "
                    f"target 을 빼고, 하나에만 걸리면 이 중에서 고른다: "
                    f"{', '.join(sorted(catalog.FEES))}")
    if t == "PRODUCT_SWITCH_TO" and not _known(eff.get("target"), catalog.PRODUCTS):
        errs.append(f"상품 키가 아님: {eff.get('target')}. `data/products.json` 의 키를 쓴다 "
                    f"(예: {', '.join(list(catalog.PRODUCTS)[:3])})")
    if t == "STATE_CHANGE" and not _known(eff.get("target"), catalog.STATES):
        errs.append(f"상태 변경 대상이 아님: {eff.get('target')}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.STATES))}")
    if t == "RESTRICT" and not _known(eff.get("target"), catalog.RESTRICTIONS):
        errs.append(f"금지 대상이 아님: {eff.get('target')}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.RESTRICTIONS))}")
    # 2026-09-16 · v24. DISQUALIFY 는 **가입 자격 상실**이라 대상을 안 받는다.
    # 자리를 만들어 줘도 모델은 거래 제한을 DISQUALIFY 로 밀어 넣었고, 그러면서
    # 금지 대상 이름만 target 에 얹었다 — `KBONE-S2-R16` 이 그렇다.
    # 실행기는 DISQUALIFY 의 target 을 읽지 않으므로 **전 거래가 아니라 계좌 자격이
    # 날아간다.** 뜻이 다른데 관문 다섯이 전부 통과시키던 자리다.
    # gold 의 DISQUALIFY 8건은 전부 target 이 없어 비용이 0 이다.
    if t == "DISQUALIFY" and eff.get("target") is not None:
        tgt = eff.get("target")
        if _known(tgt, catalog.RESTRICTIONS):
            errs.append(f"DISQUALIFY 는 대상을 받지 않는다. {tgt} 는 거래 제한 대상이므로 "
                        f"RESTRICT 를 쓴다 — DISQUALIFY 는 가입 자격 상실이라 뜻이 다르다")
        else:
            errs.append(f"DISQUALIFY 는 대상을 받지 않는다 (target={tgt}). "
                        f"자격 상실은 계좌 전체에 걸린다 — 일부만 막으려면 RESTRICT 를 쓴다")
    if eff.get("unit") is not None and not _known(eff["unit"], catalog.UNITS):
        errs.append(f"카탈로그에 없는 단위: {eff['unit']}. 쓸 수 있는 것: "
                    f"{', '.join(catalog.UNITS)}")
    return errs


# ── ④ quote ────────────────────────────────────────────────────────────
def _norm(s):
    """공백을 전부 지운다. 줄바꿈·들여쓰기 차이로 인용이 어긋나는 것을 막는다."""
    return "".join(str(s).split())


def check_quote(rule, clause_text):
    """④ quote 원문 일치 — 근거 문장을 **그대로** 옮겼나.

    공백만 무시하고 부분 문자열로 본다. 요약하거나 바꿔 쓰면 막는다.

    **이 검사는 하한이다** — 인용문이 원문에 있는지만 보지, 그 인용이
    정말 이 rule 을 받치는지는 안 본다. 사람이 읽으면 어긋남이 더 많다
    (그쪽은 ⑪ 이 따로 센다).
    """
    q = (rule.get("source") or {}).get("quote")
    if not q:
        return ["source.quote 가 없다. 조문 원문에서 근거 문장을 그대로 옮겨야 한다"]
    if _norm(q) not in _norm(clause_text):
        return [f"quote 가 조문 원문에 없다: {q[:40]!r}. "
                f"요약하거나 바꿔 쓰지 말고 원문을 그대로 옮긴다"]
    return []


# ── ⑤ 실행 ──────────────────────────────────────────────────────────────
_PROBE = {
    "customer": {"age": 17, "has_product": True, "is_first_deposit": False},
    "account": {"balance": 1_000_000, "reserved_amount": 0},
    "contract": {"base_rate": 0.1, "channel": "MOBILE",
                 "start_date": "2026-01-01", "reference_date": "2026-09-11",
                 "maturity_date": "2026-12-01", "termination_date": None,
                 "termination_type": "MATURITY"},
    "events": [],
}


def check_effect_value(rule):
    """금리 effect 의 value 가 수인가.

    `"value": "contract.base_rate"` 같은 변수 이름이 세 라운드 내내 ⑤ 를
    통과하고 있었다. resolver 는 이 형태에서 실제로 죽는다 (§9 15번).
    """
    eff = rule.get("effect") or {}
    t = eff.get("type")
    if t not in catalog.RATE_EFFECTS and t != "SERVICE_PROVIDE":
        return []
    v = eff.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return [f"{t} 의 value 는 수여야 한다. {v!r} 은 계산할 수 없다 — "
                f"조문에 적힌 숫자를 그대로 넣는다"]
    return []


def check_executable(rule):
    """⑤ 실행 가능 — 조건식이 **실제로 돌아가나**.

    `_PROBE` 라는 가짜 고객 하나로 `guard` 와 `condition` 을 돌려 본다.
    판별 결과가 무엇인지는 안 본다 — **터지지 않는지**만 본다.

    `DslError` 가 나면 조건식이 틀린 것이다. 그 밖의 예외도 잡는데,
    검증기가 죽으면 라운드를 버려야 하기 때문이다.
    effect 값의 꼴(금리가 수인가 등)도 여기서 같이 본다.
    """
    errs = []
    env = dict(rule.get("let") or {})
    for part in ("guard", "condition"):
        if part not in rule:
            continue
        try:
            evaluate(rule[part], _PROBE, env)
        except DslError as e:
            errs.append(f"실행 불가: DslError: {e}")
        except Exception as e:                      # 검증기가 죽으면 안 된다
            errs.append(f"실행 불가: {type(e).__name__}: {e}")
    errs += check_effect_value(rule)

    if rule.get("status") == "UNSUPPORTED":
        if rule.get("effect"):
            errs.append("status 가 UNSUPPORTED 인 rule 에는 effect 를 적지 않는다")
        return errs
    eff = rule.get("effect")
    if not eff:
        errs.append('effect 가 없다. 옮길 수단이 없으면 status 를 "UNSUPPORTED" 로 한다')
        return errs
    need = catalog.EFFECTS.get(eff.get("type"), ())
    missing = [k for k in need if eff.get(k) is None]
    if missing:
        errs.append(f"{eff.get('type')} 에 필요한 키가 없다: {', '.join(missing)}")
    return errs


# ── 레코드 한 건 채점 ───────────────────────────────────────────────────
# 2026-09-30 · v70. **관문 다섯이 통과시키는 뜻 오류 중 짚을 수 있는 것.**
#
# `KBYY-S2-R07` 「▪ 연 1.9% (최대 100만원까지)」를 모델이 여덟 라운드 내내
# `reserved >= 1000000 → RATE_OVERRIDE` · `reserved > 1000000 → DISQUALIFY` 로 적는다.
# 관문을 다 넘으므로 재시도가 한 번도 안 돈다. v66 이 지문 블록으로 «미리» 말했는데 안 닿았다.
#
# **관문(①~⑤)의 정의는 안 바꾼다.** 여기서 찾은 것은 `score_record` 에 안 들어가고
# 재시도 루프(`run_local_v2.run_clause`)만 쓴다 — 과거 라운드와 지표를 그대로 견주려고.
#
# 방아쇠는 v66 블록과 같은 「최대 N만원」이다(`catalog.wants_limit_block`). 정답 46조문에서
# 0 · 여덟 라운드에서 `KBYY-S2-R07` 만 8/8 걸린다 (2026-09-30 실측).
_CAP_AMOUNTS = re.compile(r"최대\s*([\d,]+)\s*만\s*원")


_ABOVE = (">=", ">")
# v78 — 한도 금액을 금리 조건의 **위쪽 끝**으로 쓴 것. v70 이 `>=` 를 짚자 R07 이 `<=` 로
# 뒤집었다(v70~v77 8/8). 뜻은 맞아 보이지만 금액이 0 인 고객도 금리를 받는다.
_BELOW = ("<=", "<", "==", "!=")


def _thresholds(node, out):
    """조건식에서 `var <비교> 수` 를 전부 찾는다 (`_ABOVE` · `_BELOW`)."""
    if isinstance(node, dict):
        for op, args in node.items():
            if op in _ABOVE + _BELOW and isinstance(args, list) and len(args) == 2 \
                    and isinstance(args[0], dict) and isinstance(args[0].get("var"), str) \
                    and isinstance(args[1], (int, float)) and not isinstance(args[1], bool):
                out.append((args[0]["var"], op, args[1]))
            _thresholds(args, out)
    elif isinstance(node, list):
        for x in node:
            _thresholds(x, out)
    return out


def _conditioned_limits(output):
    """조건을 단 `LIMIT_AMOUNT` (v74).

    2026-09-30. 한도는 누구에게나 걸리는 상한이다 — 정답의 `LIMIT_AMOUNT` 둘
    (`KBYY-S2-R07` · `KBYY-S2-R23`)은 둘 다 조건이 없다. 모델은 v63 이후 R23 에 6번 ·
    v71~v73 R07 에 3번 조건을 달았다(`> 1000000` · 앞 rule 의 조건을 베낀 것 등).
    v66 블록도 v70 재시도 문구도 「조건 없는」이라고 말했는데 안 먹었다 — **조건을 단
    그 rule 을 짚는다.** 「최대 N만원」 방아쇠와 달리 조문 글에 기대지 않는다
    (정답 0 · kb10 105조문에서 1 — 그것도 틀린 출력이다).
    """
    errs = []
    for r in output.get("rules") or []:
        if not isinstance(r, dict) or r.get("status") != "OK":
            continue
        if (r.get("effect") or {}).get("type") != "LIMIT_AMOUNT" or not r.get("condition"):
            continue
        errs.append(f"{r.get('rule_id')}: LIMIT_AMOUNT 에 조건을 달았다 — 한도는 누구에게나 "
                    f"걸리는 상한이라 조건이 없다. 이 rule 의 condition 을 {{}} 로 비운다. "
                    f"금액이 한도를 넘는지 따지는 조건(`> N`)은 한도를 두 번 적은 것이다")
    return errs


# 2026-09-30 · v82. 「N년 이상 입출금 거래가 **없는** 계좌」를 모델이 거래가 **있는** 쪽으로 센다.
# `KBYY-S2-R19` 는 v40~v81 42/42, 쌍둥이 `KBONE-S2-R16` 은 기권한 여섯 번 말고 36/42 —
# `count_distinct_months(WITHDRAWAL, 12개월) >= 12`(매달 출금한 계좌) · `>= 1` · 언제나 참인 `<= 12`.
# 정답은 둘 다 `not exists` 다. 정답 0 · kb10 0 (방아쇠 조문이 없다).
_ABSENT = re.compile(r"(\d+)\s*년\s*이상[^.\n]{0,15}거래\s*가\s*없")
_COUNTS = ("count_events", "count_distinct_months")


def _presence(node, neg=False, out=None):
    """부정 밖에서 거래가 «있는지» 묻는 자리 — `exists` · 횟수 비교(`== 0` · `<= 0` · `< 1` 은 뺀다)."""
    out = [] if out is None else out
    if isinstance(node, dict):
        for op, args in node.items():
            if op == "not":
                _presence(args, not neg, out)
                continue
            if op == "exists" and not neg:
                out.append("exists")
            if op in _ABOVE + _BELOW and not neg and isinstance(args, list) and len(args) == 2 \
                    and isinstance(args[0], dict) and any(k in args[0] for k in _COUNTS) \
                    and isinstance(args[1], (int, float)) and not isinstance(args[1], bool):
                n = args[1]
                if not ((op in ("==", "<=") and n == 0) or (op == "<" and n <= 1)):
                    out.append(f"{op} {n}")
            _presence(args, neg, out)
    elif isinstance(node, list):
        for x in node:
            _presence(x, neg, out)
    return out


# 2026-10-01 · v86. v82 의 말은 여덟 번 다 닿았다(세 번째 시도가 `not exists` 를 썼다). 그런데
# 다섯은 `and` 의 한 항을 닫는 `}` 하나를 40번째 줄에서 빠뜨려 JSON 으로 안 읽혔고, R16 셋은 WITHDRAWAL
# 만 적었다. 뼈대(`{"not": {"exists": …}}`)만 주지 말고 **고친 condition 전체를 괄호까지 닫아** 준다.
# 모델 자신의 condition 에서 거래가 있는지 묻던 항만 바꾼다. 기간은 **조문의 N년으로 새로 짓는다** —
# 모델이 쓴 `within` 은 R16 에서 「지난 한 달」(-1 ~ -1)이라 그대로 두면 N년이 한 달이 된다.
def _no_transactions(years):
    w = {"month_range": {
        "from": {"anchor": "contract.reference_date", "offset_months": -12 * years, "day": "first"},
        "to": {"anchor": "contract.reference_date", "offset_months": -1, "day": "last"}}}
    return [{"not": {"exists": {"event": e, "within": w}}} for e in ("DEPOSIT", "WITHDRAWAL")]


def _is_presence(node):
    """거래가 있는지 묻는 항 하나 (and · or · not 으로 묶인 덩어리는 아니다)."""
    return isinstance(node, dict) and not ({"and", "or", "not"} & set(node)) and bool(_presence(node))


def _absence_fixed(cond, years):
    """거래가 있는지 묻던 항을 「입금도 출금도 없음」 두 항으로 바꾼 condition."""
    def walk(node):
        if _is_presence(node):
            return {"and": _no_transactions(years)}
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "and" and isinstance(v, list):
                    out[k] = [y for x in v
                              for y in (_no_transactions(years) if _is_presence(x) else [walk(x)])]
                elif k == "not":
                    out[k] = v
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node
    return walk(copy.deepcopy(cond))


def _absence_errors(output, clause_text):
    m = _ABSENT.search(clause_text or "")
    if not m:
        return []
    errs = []
    for r in output.get("rules") or []:
        if not isinstance(r, dict) or r.get("status") != "OK":
            continue
        found = _presence(r.get("condition"))
        if found:
            src = r.get("source") if isinstance(r.get("source"), dict) else {}
            n = int((_ABSENT.search(str(src.get("quote") or "")) or m).group(1))
            # 한 줄로 주면 중괄호 깊이를 놓친다 (`prompt.build_retry_prompt` 머리말) — 되돌려 주는 출력처럼 들여쓴다
            fix = json.dumps(_absence_fixed(r.get("condition"), n), ensure_ascii=False, indent=1)
            errs.append(f"{r.get('rule_id')}: 「{n}년 이상 거래가 없는」은 그 기간에 거래가 "
                        f"**한 번도 없다**는 뜻인데 조건이 거래가 있는지를 센다({', '.join(found)}) — "
                        f"그러면 거래가 있는 계좌가 걸리거나 조건이 늘 참이다. 기간 안에 입금도 출금도 "
                        f"없어야 한다(DEPOSIT · WITHDRAWAL 둘 다). 이 rule 의 condition 을 **통째로** "
                        f"아래로 바꾼다 — 괄호 수까지 그대로 옮긴다:\n{fix}")
    return errs


# 2026-10-01 · v90. 「양도 및 상속에 의한 명의변경 불가능 · 담보제공 불가능」(`KBYY-S2-R17`)을
# v40~v89 50/50 라운드가 `RESTRICT NAME_CHANGE` 에 **그 거래가 있었는지** 묻는 조건을 달고
# (`exists NAME_CHANGE` · 첫 시도는 `event.type in [NAME_CHANGE]`), 담보제공은 44/50 기권했다.
# 「불가능」은 늘 걸리는 금지다 — 조건이 붙으면 그 거래를 한 고객만 막는다. 정답은 둘 다 `{}`.
# 쌍둥이 `KBONE-S2-R14` 는 같은 「담보제공 불가능」을 `RESTRICT PLEDGE` 로 옮긴다.
# 기권 쪽은 quote 에 「불가」가 있고 「경우」가 없을 때만 짚는다 — 「…로 이용될 경우 … 제한조치」
# (정답이 기권 · 조건을 옮길 변수가 없다)를 「송금지연」의 「금지」로 잘못 잡지 않으려고.
# v86 처럼 **고친 rule 전체를 괄호까지 닫아** 준다.
def _asks_event(node, ev):
    if isinstance(node, dict):
        if node.get("event") == ev:
            return True
        args = node.get("in")
        if isinstance(args, list) and len(args) == 2 and args[0] == {"var": "event.type"} \
                and isinstance(args[1], list) and ev in args[1]:
            return True
        return any(_asks_event(v, ev) for v in node.values())
    if isinstance(node, list):
        return any(_asks_event(v, ev) for v in node)
    return False


def _ban_errors(output):
    errs = []
    for r in output.get("rules") or []:
        if not isinstance(r, dict):
            continue
        eff = r.get("effect") if isinstance(r.get("effect"), dict) else {}
        src = r.get("source") if isinstance(r.get("source"), dict) else {}
        quote = str(src.get("quote") or "")
        target = eff.get("target")
        if r.get("status") == "OK" and eff.get("type") == "RESTRICT" and isinstance(target, str) \
                and _asks_event(r.get("condition"), target):
            fixed = dict(r, condition={})
            errs.append(f"{r.get('rule_id')}: 「불가능」은 늘 걸리는 금지다 — 조건이 {target} 거래가 "
                        f"있었는지를 물어서 그 거래를 한 고객만 막는다. condition 을 {{}} 로 비운다. "
                        f"이 rule 을 **통째로** 아래로 바꾼다 — 괄호 수까지 그대로 옮긴다:\n"
                        + json.dumps(fixed, ensure_ascii=False, indent=1))
        elif r.get("status") == "UNSUPPORTED" and "불가" in quote and "경우" not in quote:
            found = catalog.pick_restrictions(quote)
            if len(found) != 1:
                continue
            fixed = {"rule_id": r.get("rule_id"), "status": "OK", "label": r.get("label"),
                     "source": src, "condition": {},
                     "effect": {"type": "RESTRICT", "target": found[0]}}
            errs.append(f"{r.get('rule_id')}: 「{quote.strip('▪ ').strip()}」은 옮길 수단이 있다 — "
                        f"RESTRICT 의 대상 {found[0]}({catalog.RESTRICTIONS[found[0]]}). 조건 없는 금지다. "
                        f"이 rule 을 **통째로** 아래로 바꾼다 — 괄호 수까지 그대로 옮긴다:\n"
                        + json.dumps(fixed, ensure_ascii=False, indent=1))
    return errs


def semantic_errors(output, clause_text):
    """재시도가 짚을 뜻 오류. 관문과 따로 센다 — `score_record` 에는 안 들어간다."""
    if not isinstance(output, dict):
        return []
    errs = _conditioned_limits(output) + _absence_errors(output, clause_text) + _ban_errors(output)
    caps = {int(m.replace(",", "")) * 10000 for m in _CAP_AMOUNTS.findall(clause_text or "")}
    if not caps:
        return errs
    for r in output.get("rules") or []:
        if not isinstance(r, dict) or r.get("status") != "OK":
            continue
        t = (r.get("effect") or {}).get("type")
        if t not in catalog.RATE_EFFECTS and t != "DISQUALIFY":
            continue
        for var, op, n in _thresholds(r.get("condition"), []):
            if n not in caps:
                continue
            won = f"{n // 10000}만원"
            if op in _BELOW:
                if t == "DISQUALIFY":
                    continue
                errs.append(f"{r.get('rule_id')}: 「최대 {won}」은 한도이지 금리를 받는 조건이 "
                            f"아니다 — `{var} {op} {n}` 이면 금액이 0 인 고객도 금리를 받는다. "
                            f"금리 조건에서 이 금액을 빼고, 금리가 붙는 대상이 **있는지**로 적는다 "
                            f"(예: `{var} > 0`). 한도는 조건 없는 LIMIT_AMOUNT rule 로 따로 적는다")
            elif t == "DISQUALIFY":
                errs.append(f"{r.get('rule_id')}: 「최대 {won}」을 넘는다고 자격을 잃지 않는다 — "
                            f"`{var} {op} {n}` → DISQUALIFY 를 지우고, 한도는 조건 없는 "
                            f"LIMIT_AMOUNT rule 로 적는다")
            else:
                errs.append(f"{r.get('rule_id')}: 「최대 {won}」은 상한인데 금리 조건을 "
                            f"`{var} {op} {n}` 으로 적었다 — 그러면 {n}원 이상인 고객만 금리를 "
                            f"받는다. 금리 rule 의 조건에서 이 금액을 빼고, 한도는 조건 없는 "
                            f"LIMIT_AMOUNT rule 로 따로 적는다")
    return errs


def score_record(output, clause_text):
    """생성물 하나 → ①~⑤ 와 ⑦.

    빈 배열은 ③④⑤ 를 공짜로 통과하지 못한다. 별도 축 ⑦ 로 뗀다.
    """
    out = {"json_ok": output is not None, "schema_ok": False, "catalog_ok": False,
           "quote_ok": False, "exec_ok": False, "empty": False, "n_rules": 0,
           "errors": []}
    if output is None:
        return out

    errs = check_schema(output)
    out["schema_ok"] = not errs
    out["errors"] += errs

    # 스키마가 깨져도 ③④⑤ 는 따로 센다. 하나가 무너지면 나머지가 같이 0 이 되어
    # 지표가 서로를 가린다 — 어느 축이 실제로 움직였는지 못 읽게 된다.
    rules = [r for r in (output.get("rules") if isinstance(output, dict) else None) or []
             if isinstance(r, dict)]
    out["n_rules"] = len(rules)
    if not rules:
        out["empty"] = True
        return out

    for name, fn in (("catalog_ok", lambda r: check_catalog(r)),
                     ("quote_ok", lambda r: check_quote(r, clause_text)),
                     ("exec_ok", lambda r: check_executable(r))):
        e = [m for r in rules for m in fn(r)]
        out[name] = not e
        out["errors"] += e
    return out
