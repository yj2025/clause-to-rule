"""제약 디코딩용 얇은 스키마 — 이름 자리를 enum 으로만 묶는다 (2026-10-26).

`schema.SCHEMA` 를 xgrammar 에 그대로 주면 컴파일은 되지만 rule 항목이 «아무 JSON» 갈래로 빠진다
(rule 의 `anyOf: [{required: [effect]}, …]` 처럼 type 없는 갈래 · `if/then` 을 버리기 때문). 그래서 이름을 하나도 못 막는다.
여기서는 같은 모양을 `if/then` 없이 `anyOf` 로 풀어 쓴다. 형식의 나머지(OK 면 condition 필수 · 조건 없는 DISQUALIFY 등)는
기존 관문이 그대로 본다 — 문법은 «카탈로그 밖 이름을 못 짓게»만 하면 된다.

막는 자리: 변수(`var` · `anchor`) · 이벤트(`event`) · 연산자 키 · 집계 키 · `effect.type` · 종류별 `target` · `unit` · `applies_to`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog  # noqa: E402
import schema as S  # noqa: E402

VARS = sorted(catalog.VARIABLES)
REF = {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"], "additionalProperties": False}
VAR = {"type": "object", "properties": {"var": {"enum": VARS}}, "required": ["var"], "additionalProperties": False}


def _one(key, value):
    return {"type": "object", "properties": {key: value}, "required": [key], "additionalProperties": False}


ANCHOR = {k: v for k, v in S._ANCHOR.items() if k != "allOf"}
WINDOW = {**S._WINDOW, "properties": {"month_range": {
    **S._WINDOW["properties"]["month_range"], "properties": {"from": ANCHOR, "to": ANCHOR}}}}

EVENTSPEC = {
    "type": "object",
    "properties": {"event": {"enum": sorted(catalog.EVENTS)},
                   "within": {"anyOf": [WINDOW, REF]},
                   "where": {"type": "object"}},
    "required": ["event"], "additionalProperties": False,
}

OPERAND = {"anyOf": [{"type": ["string", "number", "boolean", "null"]}, VAR, REF, {"$ref": "#/$defs/anchor"}]
           + [_one(k, {"$ref": "#/$defs/eventspec"}) for k in sorted(catalog.COUNTERS)]}

_PAIR = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"$ref": "#/$defs/operand"}}
_IN = {"type": "array", "minItems": 2, "maxItems": 2,
       "items": {"anyOf": [{"$ref": "#/$defs/operand"}, {"type": "array"}]}}
CONDITION = {"anyOf": (
    [_one(k, {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/condition"}}) for k in ("and", "or")]
    + [_one("not", {"$ref": "#/$defs/condition"}), _one("exists", {"$ref": "#/$defs/eventspec"}), _one("in", _IN)]
    + [_one(c, _PAIR) for c in sorted(catalog.COMPARISONS) if c != "in"])}
COND_OR_EMPTY = {"anyOf": [{"type": "object", "maxProperties": 0}, {"$ref": "#/$defs/condition"}]}

_EFF_COMMON = {"value": {"type": ["number", "string", "boolean"]}, "unit": {"enum": list(catalog.UNITS)},
               "renewable": {"type": "boolean"}, "applies_to": {"enum": list(catalog.APPLIES_TO)}}
EFFECT = {"anyOf": (
    [{"type": "object", "properties": {"type": {"const": t}, "target": {"enum": names}, **_EFF_COMMON},
      "required": ["type"], "additionalProperties": False} for t, names in sorted(S.TARGETS.items())]
    + [{"type": "object", "properties": {"type": {"enum": list(S.NO_TARGET)}, **_EFF_COMMON},
        "required": ["type"], "additionalProperties": False}])}

RULE = {
    "type": "object",
    "properties": {**{k: v for k, v in S._RULE["properties"].items() if k not in ("let", "guard", "condition", "effect")},
                   "let": {"type": "object", "additionalProperties": WINDOW},
                   "guard": COND_OR_EMPTY, "condition": COND_OR_EMPTY, "effect": EFFECT},
    "required": ["rule_id", "source"], "additionalProperties": False,
}

THIN = {
    "type": "object",
    "properties": {"rules": {"type": "array", "items": RULE},
                   "no_rule_reason": {"enum": list(S.NO_RULE_REASONS)}},
    "required": ["rules"], "additionalProperties": False,
    "$defs": {"operand": OPERAND, "anchor": ANCHOR, "condition": CONDITION, "eventspec": EVENTSPEC},
}
