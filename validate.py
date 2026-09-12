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

import jsonschema

import catalog
import invent
from engine import DslError, evaluate
from schema import SCHEMA

_validator = jsonschema.Draft202012Validator(SCHEMA)


# ── ② 스키마 ────────────────────────────────────────────────────────────
def check_schema(output):
    return [f"스키마 위반: {e.message} (위치 {'/'.join(str(p) for p in e.path) or '최상위'})"
            for e in _validator.iter_errors(output)]


# ── ③ 카탈로그 ──────────────────────────────────────────────────────────
def _walk(node, hit):
    if isinstance(node, dict):
        for k, v in node.items():
            hit.append((k, v))
            _walk(v, hit)
    elif isinstance(node, list):
        for v in node:
            _walk(v, hit)
    return hit


def check_catalog(rule):
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

    # enum 변수를 카탈로그에 없는 값과 비교하는 경우
    for k, v in hit:
        if k in catalog.COMPARISONS and isinstance(v, list) and len(v) == 2:
            left, right = v
            if isinstance(left, dict) and "var" in left and isinstance(right, str):
                name = left["var"]
                if not catalog.is_known_value(name, right):
                    errs.append(f"{name} 의 값이 아님: {right}. 쓸 수 있는 것: "
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

    eff = rule.get("effect") or {}
    t = eff.get("type")
    if t is not None and t not in catalog.EFFECTS:
        errs.append(f"카탈로그에 없는 effect: {t}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.EFFECTS))}")
    if t == "FEE_WAIVE" and eff.get("target") not in catalog.FEES:
        errs.append(f"수수료 대상이 아님: {eff.get('target')}. 쓸 수 있는 것: "
                    f"{', '.join(sorted(catalog.FEES))}")
    if eff.get("unit") is not None and eff["unit"] not in catalog.UNITS:
        errs.append(f"카탈로그에 없는 단위: {eff['unit']}. 쓸 수 있는 것: "
                    f"{', '.join(catalog.UNITS)}")
    return errs


# ── ④ quote ────────────────────────────────────────────────────────────
def _norm(s):
    return "".join(str(s).split())


def check_quote(rule, clause_text):
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
    if t not in catalog.RATE_EFFECTS:
        return []
    v = eff.get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return [f"{t} 의 value 는 수여야 한다. {v!r} 은 계산할 수 없다 — "
                f"조문에 적힌 숫자를 그대로 넣는다"]
    return []


def check_executable(rule):
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
