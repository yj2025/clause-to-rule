"""판정 결과를 사용자에게 보여 주는 층 — 모르는 조건은 «조건부»로 (2026-10-08).

    python explain.py KBNR --start 2025-03-02 --maturity 2028-03-02 --monthly 200000
    python explain.py KBSSG --start 2026-01-05 --age 30 --json

**사용자 결정(10-08):** 서비스는 기본 정보만 받고 거래 내역은 모으지 않는다. 거래 조건
(급여이체 · 카드 사용 · 자동이체 · 연금 입금 …)을 «충족한다고 가정»하지 않는다 — 혜택이
부풀고(10-06 KB스타통장 시범: 틀린 넷이 전부 잘못 면제), 불리한 조건은 뜻이 뒤집힌다.
대신 엔진이 낸 UNKNOWN 을 그대로 두고 «이 조건이면 이렇게 된다 + 약관 원문»으로 보여 준다.

여기는 **보여 주기만** 한다. 판정은 `engine.evaluate_rules`, 금리 구간은 `resolver.resolve`,
조건 · 효과의 한국어는 `export_manual.cond` · `result` 를 그대로 쓴다.

입력하지 않은 필드는 `_provided` 에 넣지 않는다 — 그래야 «없다(NOT_MET)»가 아니라
«모른다(UNKNOWN)»가 된다(`engine._events`). 거래 내역은 늘 입력하지 않은 것이다.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "showcase"))
import catalog  # noqa: E402
import engine  # noqa: E402
import export_manual as E  # noqa: E402
import resolver  # noqa: E402
from tv import TV  # noqa: E402
from kb10six import BASE_RATE  # noqa: E402

GOLD = ROOT / "showcase" / "gold_draft"

# 사용자에게 유리한 효과 · 불리한 효과. 어느 쪽도 아닌 것(REQUIRE · 상품 전환 …)은 «그 밖의 조건».
FAVORABLE = {"RATE_ADD", "FEE_WAIVE", "FEE_WAIVE_NO_CARRYOVER", "SERVICE_PROVIDE", "TAX_EXEMPT_ELIGIBLE"}
UNFAVORABLE = {"DISQUALIFY", "RATE_SUBTRACT", "PENALTY_RATE", "RESTRICT", "STATE_CHANGE",
               "DORMANT_CONTRIBUTION"}
# RATE_OVERRIDE 는 양쪽이다 — 연금 실적별 우대 이율(KBGL)도, 중도해지 이율도 이 꼴이다. 기본이율과 견준다.


def user_ctx(today, start=None, maturity=None, monthly=None, holder=None, age=None,
             has_product=None, channel=None, base_rate=None):
    """기본 정보 → 엔진 ctx. 준 값만 «제공했다»로 선언한다. 거래 이벤트는 선언하지 않는다."""
    ctx = {"customer": {}, "account": {}, "contract": {"reference_date": today}, "events": {}}
    provided = ["contract.reference_date"]

    def put(path, value):
        if value is None:
            return
        grp, key = path.split(".")
        ctx[grp][key] = value
        provided.append(path)

    put("contract.start_date", start)
    put("contract.maturity_date", maturity)
    put("contract.monthly_amount", monthly)
    put("contract.channel", channel)
    put("contract.base_rate", base_rate)
    put("customer.holder_type", holder)
    put("customer.has_product", has_product)
    if age is not None:
        put("customer.age", age)
        put("customer.is_youth", age < 19)
    if start and maturity:
        s, m = dt.date.fromisoformat(start), dt.date.fromisoformat(maturity)
        put("contract.term_months", (m.year - s.year) * 12 + m.month - s.month)
    ctx["_provided"] = provided
    return ctx


def _uses(rule):
    """rule 이 읽는 필드 · 이벤트 이름."""
    out = set()

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("var"), str):
                out.add(n["var"])
            if isinstance(n.get("event"), str):
                out.add(f"events.{n['event']}")
            if isinstance(n.get("anchor"), str) and "." in n["anchor"]:
                out.add(n["anchor"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk([rule.get("condition"), rule.get("guard"), rule.get("let")])
    return out


def _missing(rule, ctx):
    """판정에 모자란 정보 — (입력하면 확정되는 것, 모으지 않는 거래 내역)."""
    have = set(ctx["_provided"])
    miss = sorted(u for u in _uses(rule) if u not in have)
    ask = [catalog.VARIABLES.get(u, {}).get("desc", u) for u in miss if not u.startswith("events.")]
    txn = [catalog.EVENTS.get(u[7:], u[7:]) for u in miss if u.startswith("events.")]
    return ask, txn


def prune(node, ctx, env):
    """UNKNOWN 인 조건에서 이미 아는 갈래를 걷어 낸다 — 사용자에게 «남은 조건»만 보이려고.

    「판정일이 11일 이후면 전월 실적, 10일 이전이면 전전월 실적」은 판정일을 알므로
    한 갈래만 남는다. and 에서 참인 것 · or 에서 거짓인 것을 뺀다. 판정 자체는 바꾸지 않는다.
    """
    try:
        v = engine.evaluate(node, ctx, env)
    except Exception:
        return node
    if v is not TV.U or not isinstance(node, dict) or len(node) != 1:
        return node
    (op, arg), = node.items()
    if op in ("and", "or") and isinstance(arg, list):
        drop = TV.T if op == "and" else TV.F
        keep = []
        for x in arg:
            try:
                if engine.evaluate(x, ctx, env) is drop:
                    continue
            except Exception:
                pass
            keep.append(prune(x, ctx, env))
        return keep[0] if len(keep) == 1 else {op: keep}
    if op == "not":
        return {"not": prune(arg[0] if isinstance(arg, list) else arg, ctx, env)}
    return node


def _side(eff, base_rate=0.0):
    t = (eff or {}).get("type")
    if t == "RATE_OVERRIDE" and isinstance(eff.get("value"), (int, float)):
        return "혜택" if eff["value"] > base_rate else "주의"
    return "혜택" if t in FAVORABLE else "주의" if t in UNFAVORABLE else "그 밖의 조건"


def explain(rules_by_clause, ctx, base_rate=0.0, aggregation="SUM"):
    """{조문: rules} + ctx → 보여 줄 묶음 (dict). 입력은 건드리지 않는다."""
    items, judgements, overrides = [], [], []
    for cid, rules in rules_by_clause.items():
        ok = [r for r in rules or [] if r.get("status") == "OK"]
        for r, j in zip(ok, engine.evaluate_rules(ok, ctx)):
            judgements.append(j)
            if j.status == "UNKNOWN" and (r.get("effect") or {}).get("type") == "RATE_OVERRIDE":
                overrides.append((r, j))
            env = dict(r.get("let") or {})
            status = {"MET": "적용", "UNKNOWN": "조건부", "ERROR": "판정 불가"}.get(j.status, "해당 없음")
            it = {"조문": cid, "rule_id": r.get("rule_id"), "상태": status, "구분": _side(r.get("effect"), base_rate),
                  "조건": E.cond(prune(r.get("condition"), ctx, env)
                                 if j.status == "UNKNOWN" else r.get("condition"), env),
                  "조건 문장": cond_sentence(prune(r.get("condition"), ctx, env)
                                            if j.status == "UNKNOWN" else r.get("condition"), env),
                  "결과": E.result(r.get("effect")),
                  "근거": (r.get("source") or {}).get("quote", "")}
            if status == "조건부":
                it["입력하면 확정"], it["거래 내역(모으지 않음)"] = _missing(r, ctx)
            if j.error:
                it["오류"] = j.error
            items.append(it)
    res = resolver.resolve(judgements, aggregation, base_rate)
    # resolver 는 UNKNOWN 인 RATE_OVERRIDE 를 구간에 넣지 않는다(⑥ 채점이 쓰는 동작이라 거기는 그대로 둔다).
    # 그대로 보이면 «연금 9건 이상이면 연 1.5%» 가 있는데도 «0.10% 확정»이 된다 — 여기서 구간을 넓힌다.
    # 해지에 걸린 이율(중도해지 · 만기후)은 넣지 않는다 — «지금 받는 금리»가 아니라 «해지하면»이다. «주의»에만 남는다.
    lo, hi = res.min, res.max
    if not res.disqualified:
        maybe = [j.effect["value"] for r, j in overrides
                 if isinstance(j.effect.get("value"), (int, float))
                 and not _uses(r) & {"contract.termination_type", "contract.termination_date"}]
        lo, hi = min([lo] + maybe), max([hi] + maybe)
    return {"기본이율": base_rate, "금리 범위": [lo, hi],
            "가입 불가 확정": res.disqualified, "항목": items}


# ── 글로 옮기기 ─────────────────────────────────────────────────────────

def _cond_text(c):
    if "모두" in c:
        return " 그리고 ".join(_cond_text(x) for x in c["모두"])
    if "하나 이상" in c:
        return "(" + " 또는 ".join(_cond_text(x) for x in c["하나 이상"]) + ")"
    if "아님" in c:
        return f"{_cond_text(c['아님'])}이(가) 아님"
    if "해석 못 한 조건" in c:
        return c["해석 못 한 조건"]
    if c.get("비교") == "항상":
        return "항상"
    if c.get("비교") == "있음":
        return c["항목"]
    v = c.get("값")
    if isinstance(v, bool):
        return f"{c['항목']}: {'예' if v == (c['비교'] == '같음') else '아니오'}"
    item = str(c["항목"])
    if isinstance(v, (int, float)) and abs(v) >= 1000:
        v = f"{v:,}원" if "(원)" in item else f"{v:,}"
        item = item.replace("(원)", "")
    if c.get("비교") == "같음":
        return f"{item}: {v}"
    if c.get("비교") == "다름":
        return f"{item}이(가) {v} 아님"
    if c.get("비교") == "포함" and isinstance(v, list):
        return f"{item}이(가) {', '.join(map(str, v))} 중 하나"
    v = ", ".join(map(str, v)) if isinstance(v, list) else v
    return f"{item} {v} {c['비교']}"


# export_manual.result 가 한국어로 못 옮기는 효과 — 카탈로그의 설명을 쓴다
_EFFECT_KO = {"RESTRICT": "제한", "STATE_CHANGE": "", "SERVICE_PROVIDE": "제공", "REQUIRE": "필요",
              "PRODUCT_SWITCH_TO": "(으)로 전환", "TAX_EXEMPT_ELIGIBLE": "비과세 대상",
              "DORMANT_CONTRIBUTION": "휴면예금 출연", "PENALTY_RATE": "벌칙 이율"}


def _target_ko(t):
    for table in (catalog.RESTRICTIONS, catalog.STATES, catalog.SERVICES, catalog.FEES):
        if t in table:
            return table[t]
    return t


_DATE_BASE = {"contract.start_date": "가입", "contract.maturity_date": "만기"}


def _rel_date(node):
    """「해지일 < 가입일 + 1개월」 → 「가입 후 1개월이 되기 전에 해지하면」. 이 꼴이 아니면 None.

    export_manual 은 낱말을 이어 「해지일 가입일 기준 다음 달 이전」으로 쓴다 — 팀 서식 칸(항목 · 비교 · 값)에는
    맞지만 사용자 문장으로는 못 읽는다(10-08 사용자). 정답에 이 꼴이 7번 나온다(중도해지 이율 표 6 · 가입 직후 1).
    """
    (op, arg), = node.items()
    if op not in ("<", "<=", ">", ">=") or not isinstance(arg, list) or len(arg) != 2:
        return None
    left, right = arg
    if not (isinstance(left, dict) and left.get("var") in ("contract.termination_date", "contract.reference_date")):
        return None
    if not (isinstance(right, dict) and right.get("anchor") in _DATE_BASE and set(right) <= {"anchor", "offset_months", "day"}):
        return None
    base, m, d = _DATE_BASE[right["anchor"]], right.get("offset_months") or 0, right.get("day")
    if m <= 0 or not (d is None or isinstance(d, int)):
        return None
    if d is None:
        s = f"{base} 후 {m}개월이 " + {"<": "되기 전", "<=": "되는 날까지", ">": "지난 뒤", ">=": "되는 날부터"}[op]
    else:
        s = f"{base}한 달의 {({1: '다음 달', 2: '다음다음 달'}).get(m, f'{m}개월 뒤')} {d}일" + {"<": " 전", "<=": "까지", ">": " 이후", ">=": "부터"}[op]
    if left["var"] == "contract.termination_date":
        return s + ("에 해지하면" if s.endswith("전") else " 해지하면")
    return s


def _is_term_type(node):
    return (isinstance(node, dict) and "==" in node and isinstance(node["=="], list)
            and node["=="][0] == {"var": "contract.termination_type"} and isinstance(node["=="][1], str))


def cond_sentence(node, env):
    """조건식 → 사용자가 읽을 한 문장. 날짜 비교만 따로 옮기고 나머지는 export_manual 을 쓴다."""
    if not node:
        return "항상"
    if not isinstance(node, dict) or len(node) != 1:
        return _cond_text(E.cond(node, env))
    (op, arg), = node.items()
    if op == "and" and isinstance(arg, list):
        rest = list(arg)
        # 「해지 유형 = 중도해지」 + 「… 전에 해지하면」 → 「… 전에 중도해지하면」
        kind = next((x for x in rest if _is_term_type(x)), None)
        when = next((x for x in rest if isinstance(x, dict) and len(x) == 1
                     and (_rel_date(x) or "").endswith("해지하면")), None)
        tail = None
        if kind is not None and when is not None:
            tail = _rel_date(when)[:-len("해지하면")] + E.ko(kind["=="][1]) + "하면"
            rest = [x for x in rest if x is not kind and x is not when]
        parts = [cond_sentence(x, env) for x in rest]
        # «…하면» 으로 끝나는 갈래는 맨 뒤로 — 「A 그리고 B하면」
        parts = [p for p in parts if not p.endswith("면")] + [p for p in parts if p.endswith("면")]
        if tail:
            parts.append(tail)
        return " 그리고 ".join(parts)
    if op == "or" and isinstance(arg, list):
        return "(" + " 또는 ".join(cond_sentence(x, env) for x in arg) + ")"
    if op == "not":
        return f"{cond_sentence(arg[0] if isinstance(arg, list) else arg, env)}이(가) 아님"
    return _rel_date(node) or _cond_text(E.cond(node, env))


def _result_text(r):
    if r.get("동작") in _EFFECT_KO:
        tgt = _target_ko(r.get("대상")) if r.get("대상") else ""
        v = r.get("값")
        return " ".join(x for x in (tgt, str(v) if v not in (None, "") and not tgt else "",
                                    _EFFECT_KO[r["동작"]]) if x) or r["동작"]
    if r.get("동작") == "수수료 면제":
        lim = r.get("한도")
        return f"{r.get('대상')} 면제" + (" (횟수 제한 없음)" if lim == "제한없음" else f" (최대 {lim})" if lim else "")
    return " ".join(str(r[k]) for k in ("대상", "값", "동작", "한도") if r.get(k) not in (None, ""))


def render(out):
    lo, hi = out["금리 범위"]
    lines = []
    if out["가입 불가 확정"]:
        lines.append("■ 입력한 정보로는 이 상품에 가입할 수 없습니다 (아래 «적용» 참고).")
    elif abs(hi - lo) < 1e-9:
        lines.append(f"■ 금리 연 {lo:.2f}% (확정)")
    else:
        lines.append(f"■ 금리 연 {lo:.2f}% ~ {hi:.2f}% — 아래 조건에 따라 달라집니다 (기본 연 {out['기본이율']:.2f}%)")

    def block(title, pick):
        rows = [it for it in out["항목"] if pick(it)]
        if not rows:
            return
        lines.append(f"\n[{title}]")
        for it in rows:
            c, r = it["조건 문장"], _result_text(it["결과"])
            lines.append(f"• {r}" if c == "항상" else
                         f"• {c if c.endswith('면') else c + '이면'} → {r}" if it["상태"] == "조건부"
                         else f"• {r}  ({c})")
            need = it.get("입력하면 확정") or []
            txn = it.get("거래 내역(모으지 않음)") or []
            if need:
                lines.append(f"    입력하면 확정: {', '.join(need)}")
            if txn:
                lines.append(f"    직접 확인 필요: {', '.join(txn)} 내역")
            if it.get("오류"):
                lines.append(f"    판정 불가: {it['오류'][:80]}")
            lines.append(f"    근거: 「{it['근거']}」")

    if out["가입 불가 확정"]:      # 가입할 수 없으면 혜택 목록은 뜻이 없다 — 막는 규칙만 보인다
        block("적용", lambda it: it["상태"] == "적용" and it["결과"].get("동작") == "가입 불가")
        return "\n".join(lines)
    block("적용", lambda it: it["상태"] == "적용")
    block("조건부 혜택", lambda it: it["상태"] == "조건부" and it["구분"] == "혜택")
    block("조건부 주의", lambda it: it["상태"] == "조건부" and it["구분"] == "주의")
    block("그 밖의 조건", lambda it: it["상태"] == "조건부" and it["구분"] == "그 밖의 조건")
    block("판정 불가", lambda it: it["상태"] == "판정 불가")
    n = sum(it["상태"] == "해당 없음" for it in out["항목"])
    if n:
        lines.append(f"\n(입력한 정보로 해당하지 않는 규칙 {n}개는 생략)")
    return "\n".join(lines)


def load_gold(prefix):
    return {p.stem: json.loads(p.read_text("utf-8")).get("rules") or []
            for p in sorted(GOLD.glob(f"{prefix}-*.json"))}


def load_results(path, prefix):
    return {x["clause_id"]: ((x.get("output") or {}).get("rules") or [])
            for x in json.loads(Path(path).read_text("utf-8"))
            if x["clause_id"].startswith(prefix + "-") and isinstance((x.get("output") or {}).get("rules"), list)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("product", help="상품 접두어 (KBNR · KBSSG …)")
    ap.add_argument("--results", help="정답 대신 이 결과 파일의 모델 출력을 쓴다")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--start")
    ap.add_argument("--maturity")
    ap.add_argument("--monthly", type=int)
    ap.add_argument("--holder", choices=catalog.ENUM_VALUES.get("customer.holder_type"))
    ap.add_argument("--age", type=int)
    ap.add_argument("--has-product", type=lambda s: s.lower() in ("1", "y", "yes", "true"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.product not in BASE_RATE:
        ap.error(f"모르는 상품: {a.product}. 있는 것: {', '.join(BASE_RATE)}")
    rules = load_results(a.results, a.product) if a.results else load_gold(a.product)
    base = BASE_RATE[a.product]
    ctx = user_ctx(a.today, a.start, a.maturity, a.monthly, a.holder, a.age, a.has_product, base_rate=base)
    out = explain(rules, ctx, base)
    print(json.dumps(out, ensure_ascii=False, indent=1) if a.json else render(out))


if __name__ == "__main__":
    main()
