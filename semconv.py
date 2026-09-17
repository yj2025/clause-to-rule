"""의미 규칙(semantic_rule v1.1) → 실행 규칙(이 저장소의 condition + effect).

팀원 Part 2-1 의 모델은 **사용자와 무관한 의미 규칙**을 낸다. 이 저장소의
실행기(`engine.py`)와 합산기(`resolver.py`)는 **카탈로그 이름으로 적힌 조건식**을
읽는다. 둘 사이를 잇는 것이 이 모듈이다.

두 층으로 나눈다.

  구조   형태 · AND/OR · 연산자 · 단위 · effect 종류   → 이 모듈 (결정론)
  어휘   원문 표현(surface) → 카탈로그 이름            → `data/semconv_lexicon.json`

의미 규칙은 조건의 대상을 **원문 문장 그대로** 들고 온다
(`{"surface": "합산 50만원 이상 입금 이력이 있는 경우"}`). 이것을 카탈로그 이름으로
옮기는 일은 코드가 추측할 수 없다. 그래서 대응표를 데이터로 두고 사람이 검토한다.
대응표에 "없다" 고 적힌 자리가 곧 **어휘가 없어서 막힌 자리**다.

막힌 이유는 층으로 가른다. 한 단위에 여럿이 겹칠 수 있고 전부 적는다.

  SOURCE     의미 규칙 스스로 미해결로 남겼다
  SCOPE      판별 범위 밖 — 지급 · 이체 · 통지 · 보호 · 이자 계산식 (`DECISIONS.md` 결정 2-0)
  STRUCTURE  이 DSL 에 그 구조가 없다 — 구간 분할, 규칙 간 예외 관계, 배수 조건 …
  VOCAB      구조는 있는데 카탈로그에 그 이름이 없다
  UNLABELED  대응표에 아직 판정이 없다 (0 이어야 결과를 읽을 수 있다)
  CONVERTER  옮긴 규칙이 이 저장소의 관문(②③⑤)을 못 넘었다 — 대응표나 이 모듈의 결함

"옮길 규칙이 아니다" 도 따로 센다 (NOT_A_RULE). 거래 경로 안내는 절차이고
기본금리는 상품 설정이다 — 이 저장소의 gold 원칙이다 (`DECISIONS.md`).
팀원 쪽은 이것을 규칙으로 두므로 **막힌 것이 아니라 원칙이 다른 것**이다.
"""

import copy
import json
import re
from pathlib import Path

import validate

LAYERS = ("SOURCE", "SCOPE", "STRUCTURE", "VOCAB", "UNLABELED", "CONVERTER")

LEXICON_PATH = Path(__file__).resolve().parent / "data" / "semconv_lexicon.json"

# 대응표의 칸. 같은 표현도 칸마다 뜻이 다르다 — "해지" 는 금지 대상일 때와
# 허용 대상일 때가 다르므로 effect 는 "종류::표현" 으로 찾는다.
KINDS = ("cond", "constraint", "subject", "member", "target", "scope", "modifier", "relation")

# 대응표 없이도 판정되는 effect. 판별이 아니라 급부 · 절차다.
_SCOPE_EFFECTS = {
    "PAY": ("지급", "이자계산·지급"), "TRANSFER": ("이체", "이자계산·지급"),
    "NOTIFY": ("통지", "명의·서류·절차"), "PROTECT": ("예금자보호", "기타"),
    "COPY_VALUE": ("값 복사", "기타"),
}

_OPS = {"EQ": "==", "NE": "!=", "GE": ">=", "LE": "<=", "GT": ">", "LT": "<"}


def _norm(s):
    return " ".join(str(s or "").split())


# 막힌 이유를 개념별로 묶는 갈래. 대응표의 gap 판정이 하나를 고른다.
FAMILIES = ("가입자격", "가입금액·한도", "계약기간·만기", "금리·이율값", "이자계산·지급",
            "거래실적·이벤트", "거래제한·금지", "해지·중도해지", "수수료", "부가서비스·제휴",
            "휴면·장기미거래", "명의·서류·절차", "세금·비과세", "날짜·영업일", "상품전환·재예치",
            "외화·송금", "규칙간관계·예외", "기타")


def _blk(layer, slot, surface, reason, family=None):
    return {"layer": layer, "slot": slot, "surface": _norm(surface), "reason": reason,
            "family": family}


# ── 대응표 ──────────────────────────────────────────────────────────────
class Lexicon:
    """칸 → {표현: 판정}. 표현은 공백을 하나로 접어 찾는다."""

    def __init__(self, data=None):
        data = data or {}
        self.table = {k: {_norm(s): v for s, v in (data.get(k) or {}).items()}
                      for k in KINDS}

    @classmethod
    def load(cls, path=LEXICON_PATH):
        p = Path(path)
        return cls(json.loads(p.read_text("utf-8")) if p.exists() else {})

    def get(self, kind, surface):
        return self.table[kind].get(_norm(surface))


# ── 수 읽기 ─────────────────────────────────────────────────────────────
_MUL = {"억": 10**8, "천만": 10**7, "백만": 10**6, "십만": 10**5, "만": 10**4,
        "천": 10**3, "백": 10**2, "": 1}
_Q = re.compile(
    r"(?P<n>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?:(?P<mul>억|천만|백만|십만|만|천|백)?\s*(?P<won>원)"
    r"|(?P<per>개월|년|일)"
    r"|(?P<cnt>회|건|계좌|좌)"
    r"|(?P<age>세))")
_BOUND = re.compile(r"이상|초과|이하|미만|이내|까지|부터")
_FILLER = re.compile(r"[\s~\-–,()만]|최소|최대|단위")


def _quantities(s):
    """표현 안의 수 → [(값, 종류, 끝 위치)]. 종류는 won · months · days · count · age."""
    out = []
    for m in _Q.finditer(s):
        n = float(m["n"].replace(",", ""))
        if m["won"]:
            v, kind = n * _MUL[m["mul"] or ""], "won"
        elif m["per"]:
            v, kind = (n * 12, "months") if m["per"] == "년" else \
                      (n, "months") if m["per"] == "개월" else (n, "days")
        elif m["cnt"]:
            v, kind = n, "count"
        else:
            v, kind = n, "age"
        out.append((int(v) if float(v).is_integer() else v, kind, m.start(), m.end()))
    return out


def parse_range(surface):
    """"6개월 ~ 5년" · "20만원 이상" · "1년~2년미만" → 구간. 못 읽으면 None.

    남는 글자가 있으면 읽지 않는다 — "만기후 1개월 이내" 의 "만기후" 는
    대상에 관한 말이라 수만 떼어 읽으면 뜻이 바뀐다.
    """
    s = _norm(surface)
    qs = _quantities(s)
    if not qs or len(qs) > 2 or len({k for _, k, _, _ in qs}) != 1:
        return None
    rest = s
    for _, _, a, b in reversed(qs):
        rest = rest[:a] + " " + rest[b:]
    if _FILLER.sub("", _BOUND.sub("", rest)):
        return None

    def bound_after(i):
        end = qs[i][3]
        nxt = qs[i + 1][2] if i + 1 < len(qs) else len(s)
        m = _BOUND.search(s[end:nxt])
        return m.group(0) if m else None

    kind = qs[0][1]
    r = {"kind": kind, "lo": None, "lo_inc": True, "hi": None, "hi_inc": True}
    if len(qs) == 2:
        if "~" not in s and "부터" not in s and bound_after(0) not in ("이상", "초과", "부터"):
            return None
        r["lo"], r["lo_inc"] = qs[0][0], bound_after(0) != "초과"
        b = bound_after(1)
        r["hi"], r["hi_inc"] = qs[1][0], b not in ("미만",)
        return r
    b = bound_after(0)
    if b in ("이상", "초과", "부터"):
        r["lo"], r["lo_inc"] = qs[0][0], b != "초과"
    elif b in ("이하", "미만", "이내", "까지"):
        r["hi"], r["hi_inc"] = qs[0][0], b != "미만"
    else:
        return None
    return r


def _range_dsl(operand, r):
    parts = []
    if r["lo"] is not None:
        parts.append({">=" if r["lo_inc"] else ">": [copy.deepcopy(operand), r["lo"]]})
    if r["hi"] is not None:
        parts.append({"<=" if r["hi_inc"] else "<": [copy.deepcopy(operand), r["hi"]]})
    return parts[0] if len(parts) == 1 else {"and": parts}


_UNIT_KIND = {"KRW": "won", "MONTH": "months", "YEAR": "years", "DAY": "days",
              "COUNT": "count", "ACCOUNT_COUNT": "count"}


def _literal(right, want):
    """오른쪽 값 → 대상 단위의 수. 못 옮기면 (None, 이유)."""
    unit = right.get("unit")
    v = right.get("value")
    if isinstance(v, str):
        try:
            v = float(v.replace(",", ""))
        except ValueError:
            v = None
    kind = _UNIT_KIND.get(unit)
    if v is None or isinstance(v, bool):
        qs = _quantities(_norm(right.get("surface")))
        if len(qs) != 1:
            return None, f"값이 수가 아니다: {right.get('value')!r}"
        v, kind = qs[0][0], qs[0][1]
    if kind == "years":
        v, kind = (v * 12, "months") if want == "months" else (v, "age")
    if want and kind and kind != want:
        return None, f"단위가 다르다: 대상은 {want}, 값은 {kind}"
    return (int(v) if float(v).is_integer() else v), None


# ── 조건 ────────────────────────────────────────────────────────────────
class _Unit:
    """단위 하나를 옮기는 동안의 상태 — 막힌 이유와 let 을 모은다."""

    def __init__(self, lex):
        self.lex = lex
        self.blockers = []
        self.let = {}
        self.procedural = []                # 조건 자체가 절차라 규칙이 아닌 자리

    def block(self, *a):
        self.blockers.append(_blk(*a))
        return None

    def entry(self, kind, surface, slot):
        e = self.lex.get(kind, surface)
        if e is None:
            return self.block("UNLABELED", slot, surface, f"대응표 {kind} 칸에 판정이 없다")
        if "gap" in e:
            return self.block(e.get("layer", "VOCAB"), slot, surface, e["gap"], e.get("family"))
        for name, win in (e.get("let") or {}).items():
            if name in self.let and self.let[name] != win:
                return self.block("CONVERTER", slot, surface,
                                  f"창 이름 ${name} 이 단위 안에서 다른 기간으로 두 번 묶였다")
            self.let[name] = win
        return e

    def subject(self, surface, slot):
        e = self.entry("subject", surface, slot)
        if e is None:
            return None
        if "not_rule" in e:
            return e
        if "var" in e:
            return {**e, "operand": {"var": e["var"]}}
        if "operand" in e or "requirement" in e:
            return e
        return self.block("CONVERTER", slot, surface,
                          "subject 판정에 var · operand · requirement · not_rule 이 없다")

    def members(self, values, slot):
        out = []
        for m in values or []:
            e = self.entry("member", m.get("surface"), slot)
            if e is None:
                continue
            out.append(e["value"])
        return out if len(out) == len(values or []) else None

    def condition(self, node, slot="condition"):
        """의미 규칙의 조건 → DSL. 막히면 None (이유는 self.blockers)."""
        kind = (node or {}).get("kind", "always")
        if kind == "always":
            return {}
        if kind == "group":
            op = node.get("op")
            kids = [self.condition(c, slot) for c in node.get("children") or []]
            if op not in ("AND", "OR"):
                return self.block("STRUCTURE", slot, op, f"묶음 연산자 {op} 없음")
            if any(k is None for k in kids):
                return None
            return {op.lower(): kids}
        if kind == "predicate":
            return self.predicate(node, slot)
        return self.block("STRUCTURE", slot, node.get("surface"),
                          f"{kind} 조건은 선택 규칙의 구간 자리에서만 읽는다")

    def predicate(self, node, slot):
        left = (node.get("left") or {}).get("surface")
        op, right = node.get("operator"), node.get("right") or {}
        if op == "MULTIPLE_OF":
            return self.block("STRUCTURE", slot, left, "금액 단위(배수) 요건 없음", "가입금액·한도")
        if op == "EQ" and right.get("value_type") == "boolean":
            e = self.entry("cond", left, slot)
            if e is None:
                return None
            if "not_rule" in e:
                self.procedural.append(e["not_rule"])
                return None
            if "dsl" not in e:
                return self.block("CONVERTER", slot, left, "cond 판정에 dsl 이 없다")
            dsl = copy.deepcopy(e["dsl"])
            return dsl if right.get("value") in (True, "True", "true") else {"not": dsl}
        subj = self.subject(left, slot)
        if subj is None:
            return None
        if "not_rule" in subj:
            return self.block("STRUCTURE", slot, left,
                              f"조건 자리의 대상이 규칙 밖이다: {subj['not_rule']}")
        if op in ("IN", "NOT_IN"):
            vals = self.members(right.get("values"), slot)
            if vals is None:
                return None
            dsl = {"in": [subj["operand"], vals]}
            return dsl if op == "IN" else {"not": dsl}
        if op in _OPS:
            v, why = _literal(right, subj.get("unit"))
            if why:
                return self.block("STRUCTURE", slot, left, why)
            return {_OPS[op]: [subj["operand"], v]}
        return self.block("STRUCTURE", slot, left, f"연산자 {op} 없음")

    def requirement(self, node, subj_surface, slot):
        """제약 → "지켜야 할 조건" DSL 과 위반 시 effect. 막히면 (None, None)."""
        kind = node.get("kind")
        if kind == "group":
            got = [self.requirement(c, subj_surface, slot) for c in node.get("children") or []]
            if any(d is None for d, _ in got):
                return None, None
            skipped = [d["not_rule"] for d, _ in got if "not_rule" in d]
            if skipped:
                if len(skipped) == len(got):
                    return {"not_rule": skipped[0]}, None
                return self.block("STRUCTURE", slot, subj_surface,
                                  "묶음 안에 규칙인 제약과 절차가 섞였다"), None
            effs = {e for _, e in got}
            if len(effs) != 1:
                return self.block("STRUCTURE", slot, subj_surface,
                                  f"묶음 안에서 위반 효과가 갈린다: {sorted(map(str, effs))}"), None
            return {node.get("op", "AND").lower(): [d for d, _ in got]}, effs.pop()
        if kind == "range":
            subj = self.subject(subj_surface, slot) if subj_surface else \
                self.block("STRUCTURE", slot, node.get("surface"), "구간 제약에 대상이 없다")
            if subj is None:
                return None, None
            if "not_rule" in subj:
                return {"not_rule": subj["not_rule"]}, None
            r = parse_range(node.get("surface"))
            if r is None or r["kind"] != subj.get("unit"):
                return self.block("STRUCTURE", slot, node.get("surface"),
                                  "구간 표현을 대상 단위로 읽지 못했다"), None
            return _range_dsl(subj["operand"], r), subj.get("violation")
        if kind != "predicate":
            return self.block("STRUCTURE", slot, node.get("surface"), f"제약 형태 {kind} 없음"), None
        left = (node.get("left") or {}).get("surface")
        right = node.get("right") or {}
        if node.get("operator") == "EQ" and right.get("value_type") == "boolean":
            e = self.entry("constraint", left, slot)
            if e is None:
                return None, None
            if "not_rule" in e:
                return {"not_rule": e["not_rule"]}, None
            return copy.deepcopy(e["requirement"]), e.get("violation")
        subj = self.subject(left, slot)
        if subj is None:
            return None, None
        if "not_rule" in subj:
            return {"not_rule": subj["not_rule"]}, None
        if "requirement" in subj:
            # 수 비교가 카탈로그의 참/거짓 하나와 같은 자리 — "1인 1계좌" (보유 계좌 수 ≤ 1)
            # 는 "이미 보유하면 가입 불가" 다. 대응표가 적은 연산자 · 값과 같을 때만 쓴다.
            want = subj.get("when") or {}
            v, why = _literal(right, None)
            if node.get("operator") != want.get("operator") or v != want.get("value"):
                return self.block("STRUCTURE", slot, left,
                                  f"대응표의 요건은 {want} 일 때만이다: {node.get('operator')} {v}"), None
            return copy.deepcopy(subj["requirement"]), subj.get("violation")
        dsl = self.predicate(node, slot)
        return (dsl, subj.get("violation")) if dsl is not None else (None, None)


# ── effect ──────────────────────────────────────────────────────────────
_RATE_UNITS = {"PERCENT_POINT": "%p", "PERCENT_PER_YEAR": "%", "PERCENT": "%"}


def _effect(u, eff, cond, slot):
    """effect 하나 → ("rule", 실행 규칙 조각) | ("not_rule", 이유) | None(막힘)."""
    t = eff.get("type")
    tgt = (eff.get("target") or {}).get("surface")
    val = eff.get("value") or {}
    e = u.lex.get("target", f"{t}::{_norm(tgt)}")
    if e is None:
        if t in _SCOPE_EFFECTS:
            what, fam = _SCOPE_EFFECTS[t]
            return u.block("SCOPE", slot, tgt, f"판별 범위 밖: {what}", fam)
        if val.get("type") == "expression":
            return u.block("SCOPE", slot, tgt, "판별 범위 밖: 계산식 (이자·금액 산출)",
                           "이자계산·지급")
        return u.block("UNLABELED", slot, f"{t}::{tgt}", "대응표 target 칸에 판정이 없다")
    if "gap" in e:
        return u.block(e.get("layer", "VOCAB"), slot, f"{t}::{tgt}", e["gap"], e.get("family"))
    if "not_rule" in e:
        return "not_rule", e["not_rule"]

    out = {"type": e["effect"]}
    for k in ("target", "unit", "renewable", "applies_to"):
        if k in e:
            out[k] = e[k]
    typ = e["effect"]
    if typ in ("RATE_ADD", "RATE_SUBTRACT", "RATE_OVERRIDE", "PENALTY_RATE"):
        num = val.get("value")
        if val.get("type") != "literal" or isinstance(num, bool) or not isinstance(num, (int, float)):
            return u.block("STRUCTURE", slot, tgt,
                           "금리 값이 문서 안의 수가 아니다 (게시값 참조 · 계산식)")
        out["value"] = num
        out.setdefault("unit", _RATE_UNITS.get(val.get("unit"), "%p"))
    elif typ in ("LIMIT_AMOUNT", "FEE_WAIVE", "SERVICE_PROVIDE", "REQUIRE"):
        if "value" in e:
            out["value"] = e["value"]
        elif typ == "LIMIT_AMOUNT":
            v, why = _literal(val, "won")
            if why:
                return u.block("STRUCTURE", slot, tgt, why)
            out["value"] = v
        elif typ == "FEE_WAIVE" and t == "SET_VALUE" and val.get("value") in (0, "0"):
            out["value"] = "UNLIMITED"
        else:
            return u.block("STRUCTURE", slot, tgt, f"{typ} 의 value 를 의미 규칙에서 못 읽었다")
    if cond is None:
        return "rule", None                 # 조건이 막혔다 — effect 쪽 이유만 모으고 버린다
    if e.get("negate_condition"):
        # 허용 목록 → 자격 상실. 대응표가 "이 조건이 허용의 전부다" 라고 판정한 자리만.
        if not cond:
            return "not_rule", "조건 없는 허용 — 모두에게 열려 있다"
        cond = {"not": cond}
    if "and" in e:
        # 대상 표현이 조건을 품는 자리 — "PROHIBIT::개인사업자" 는 개인사업자의 가입 금지다
        cond = _with(cond, [copy.deepcopy(e["and"])])
    if typ == "DISQUALIFY" and not cond:
        return u.block("STRUCTURE", slot, tgt, "조건 없는 자격 상실은 모든 고객을 떨어뜨린다")
    return "rule", {"condition": cond, "effect": out}


# ── 단위 하나 ───────────────────────────────────────────────────────────
def _decorate(u, unit, slot):
    """scope · modifier · relation → (조건에 AND 할 조각 목록). 막히면 blocker 만 남긴다."""
    extra = []
    for s in unit.get("scope") or []:
        e = u.entry("scope", s.get("surface"), f"{slot}.scope")
        if e and "and" in e:
            extra.append(copy.deepcopy(e["and"]))
    for m in unit.get("modifiers") or []:
        e = u.entry("modifier", m.get("surface"), f"{slot}.modifier")
        if e and "and_not" in e:
            extra.append({"not": copy.deepcopy(e["and_not"])})
    for r in unit.get("relations") or []:
        if r.get("type") == "REFERENCE":
            continue                        # 출처 표시다. 값이 필요하면 effect 가 막힌다
        u.entry("relation", r.get("surface"), f"{slot}.relation")
    return extra


def _with(cond, extra):
    if not extra:
        return cond
    parts = ([cond] if cond else []) + extra
    return parts[0] if len(parts) == 1 else {"and": parts}


def convert_unit(unit, lex, rid_prefix="SEM"):
    """rule_unit 하나 → 결과 사전.

    outcome: CONVERTED (전부 옮김) · PARTIAL (일부 옮김) · NOT_A_RULE · BLOCKED
    """
    u = _Unit(lex)
    form = unit.get("form")
    body = unit.get("body") or {}
    quote = next((e.get("text") for e in unit.get("evidence") or [] if e.get("text")), "")
    for x in unit.get("unresolved") or []:
        u.block("SOURCE", "unresolved", x.get("surface"), f"의미 규칙이 미해결로 남김: {x.get('type')}")

    before_decorate = len(u.blockers)
    extra = _decorate(u, unit, form or "unit")
    # 시점 · 예외 · 관계 중 하나라도 못 옮겼으면 어느 effect 에 걸리는지 모른다.
    # 그대로 내보내면 예외를 빼먹은 채 **더 넓게** 준다 — 규칙을 내지 않는다.
    undecorated = len(u.blockers) > before_decorate
    made, not_rule, n_eff, n_blocked_eff = [], [], 0, 0

    def take(kind_val, label):
        nonlocal n_blocked_eff
        if kind_val is None:
            n_blocked_eff += 1
            return
        kind, val = kind_val
        if kind == "not_rule":
            not_rule.append(val)
        elif undecorated:
            n_blocked_eff += 1
        else:
            val["condition"] = _with(val["condition"], extra)
            made.append((label, val))

    if form == "CONDITIONAL_EFFECT":
        before = len(u.blockers)
        cond = u.condition(body.get("condition"))
        for eff in body.get("effects") or []:
            n_eff += 1
            # 조건이 막혀도 effect 는 본다 — 막힌 이유를 한 번에 다 모아야 센다
            got = _effect(u, eff, cond, "effect")
            take(None if cond is None else got, (eff.get("target") or {}).get("surface"))
        if cond is None and len(u.blockers) == before:
            if u.procedural:
                not_rule.extend(u.procedural)
                n_blocked_eff = 0
            else:
                u.block("CONVERTER", "condition", "", "조건이 막혔는데 이유가 없다")
    elif form == "CONSTRAINT":
        n_eff = 1
        node = body.get("constraint") or {}
        subj = (body.get("applies_to") or {}).get("surface")
        req, viol = u.requirement(node, subj, "constraint")
        if req is None:
            n_blocked_eff += 1
        elif "not_rule" in req:
            not_rule.append(req["not_rule"])
        elif viol == "LIMIT_AMOUNT":
            op = next(iter(req))
            if op in ("<=", "<") and isinstance(req[op][1], (int, float)):
                take(("rule", {"condition": {}, "effect": {"type": "LIMIT_AMOUNT",
                                                           "value": req[op][1]}}), subj)
            else:
                n_blocked_eff += 1
                u.block("STRUCTURE", "constraint", subj, "한도 제약이 단일 상한이 아니다")
        elif viol == "DISQUALIFY":
            take(("rule", {"condition": {"not": req}, "effect": {"type": "DISQUALIFY"}}), subj)
        else:
            n_blocked_eff += 1
            u.block("CONVERTER", "constraint", subj, f"위반 효과가 없다: {viol!r}")
    elif form == "SELECTOR":
        n_eff = sum(len(b.get("effects") or []) for b in body.get("branches") or [])
        if body.get("mode") != "BUCKET":
            n_blocked_eff = n_eff
            u.block("STRUCTURE", "selector", (body.get("selector") or {}).get("surface"),
                    f"구간 분할 계산({body.get('mode')}) — 구간마다 나눠 셈하는 구조가 없다",
                    "이자계산·지급")
        else:
            _selector(u, body, take)
    else:
        u.block("STRUCTURE", "form", form, f"형태 {form} 없음")

    rules = []
    for i, (label, frag) in enumerate(made, 1):
        r = {"rule_id": f"{rid_prefix}-{i:02d}", "status": "OK",
             "label": f"{form} · {_norm(label)[:40]}", "source": {"quote": quote},
             "condition": frag["condition"], "effect": frag["effect"]}
        if u.let:
            r["let"] = copy.deepcopy(u.let)
        errs = (validate.check_schema({"rules": [r]}) + validate.check_catalog(r)
                + validate.check_executable(r))
        if errs:
            u.block("CONVERTER", "rule", label, "; ".join(errs)[:300])
            n_blocked_eff += 1
            continue
        rules.append(r)

    blocked = bool(u.blockers)
    if not blocked:
        outcome = "CONVERTED" if rules else "NOT_A_RULE"
    else:
        outcome = "PARTIAL" if rules else "BLOCKED"
    return {"form": form, "outcome": outcome, "rules": rules, "not_rule": not_rule,
            "n_effects": n_eff, "n_blocked_effects": n_blocked_eff,
            "blockers": u.blockers, "layers": sorted({b["layer"] for b in u.blockers},
                                                     key=LAYERS.index)}


def _selector(u, body, take):
    subj_s = (body.get("selector") or {}).get("surface")
    branches = body.get("branches") or []
    conds = []
    for b in branches:
        m = b.get("match") or {}
        if m.get("kind") in ("range", "threshold"):
            subj = u.subject(subj_s, "selector")
            if subj is None or "not_rule" in subj:
                if subj is not None:
                    u.block("STRUCTURE", "selector", subj_s,
                            f"선택 대상이 규칙 밖이다: {subj['not_rule']}")
                conds.append(None)
                continue
            r = parse_range(m.get("surface"))
            if r is None or r["kind"] != subj.get("unit"):
                u.block("STRUCTURE", "selector.match", m.get("surface"),
                        "구간 표현을 대상 단위로 읽지 못했다")
                conds.append(None)
                continue
            conds.append((_range_dsl(subj["operand"], r), r))
        else:
            c = u.condition(m, "selector.match")
            conds.append(None if c is None else (c, None))

    if body.get("selection_policy") == "HIGHEST_MATCHING":
        # 겹치는 문턱("20만원 이상" · "30만원 이상")은 가장 높은 것 하나만 걸려야 한다.
        # 합산기는 금리를 더하므로 그대로 두면 두 번 더해진다. 문턱이 오름차순일 때만
        # 뒤 문턱의 부정을 붙인다 — 순서를 모르면 옮기지 않는다.
        los = [c[1]["lo"] if c and c[1] else None for c in conds]
        if None in los or los != sorted(los):
            for b in branches:
                for eff in b.get("effects") or []:
                    _effect(u, eff, None, "selector.effect")
                    take(None, None)
            if None in conds:
                return                      # 가지가 이미 다른 이유로 막혔다 — 순서 탓으로 또 세지 않는다
            u.block("STRUCTURE", "selector", subj_s, "가장 높은 구간 선택인데 문턱 순서를 확인 못 했다",
                "금리·이율값")
            return
        excl = []
        for i, c in enumerate(conds):
            later = [x[0] for x in conds[i + 1:]]
            excl.append(c[0] if not later else {"and": [c[0]] + [{"not": x} for x in later]})
        conds = [(x, None) for x in excl]

    for b, c in zip(branches, conds):
        for eff in b.get("effects") or []:
            if c is None:
                _effect(u, eff, None, "selector.effect")
                take(None, None)
                continue
            take(_effect(u, eff, c[0], "selector.effect"), (eff.get("target") or {}).get("surface"))


# ── 레코드 하나 ─────────────────────────────────────────────────────────
def convert_record(sem, lex, rid_prefix="SEM"):
    """semantic_rule 하나 → {"status", "outcome", "units", "blockers"}.

    레코드 outcome:
      EMPTY       NO_EXECUTABLE_RULE — 이 저장소의 빈 배열과 같은 판정
      SOURCE      레코드 자체가 UNRESOLVED
      나머지      단위 결과의 합 — ALL_CONVERTED · SOME_CONVERTED · NONE_CONVERTED · NOT_A_RULE
    """
    status = sem.get("status")
    rec_blk = [_blk("SOURCE", "record", x.get("surface"),
                    f"의미 규칙이 미해결로 남김: {x.get('type')}")
               for x in sem.get("unresolved") or []]
    if status == "NO_EXECUTABLE_RULE":
        return {"status": status, "outcome": "EMPTY", "units": [], "blockers": rec_blk}
    units = [convert_unit(x, lex, f"{rid_prefix}-U{i:02d}")
             for i, x in enumerate(sem.get("rule_units") or [], 1)]
    if status == "UNRESOLVED" and not units:
        return {"status": status, "outcome": "SOURCE", "units": [], "blockers": rec_blk}
    outs = {x["outcome"] for x in units}
    if outs <= {"CONVERTED", "NOT_A_RULE"} and "CONVERTED" in outs and not rec_blk:
        outcome = "ALL_CONVERTED"
    elif outs == {"NOT_A_RULE"} and not rec_blk:
        outcome = "NOT_A_RULE"
    elif outs & {"CONVERTED", "PARTIAL"}:
        outcome = "SOME_CONVERTED"
    else:
        outcome = "NONE_CONVERTED"
    return {"status": status, "outcome": outcome, "units": units, "blockers": rec_blk}
