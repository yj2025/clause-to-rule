"""출력 스키마와 few-shot 예시.

few-shot 이 틀린 형태를 가르치면 모델은 그대로 따라 한다. 그래서 이 파일의
예시는 §4 에서 검증기 넷에 태운다 — 통과하지 못하면 그게 버그다.
"""

import catalog

# ── JSON 스키마 ─────────────────────────────────────────────────────────
_OPERAND = {
    "anyOf": [
        {"type": ["string", "number", "boolean", "null"]},
        {"type": "object", "properties": {"var": {"type": "string"}},
         "required": ["var"], "additionalProperties": False},
        {"type": "object", "properties": {"ref": {"type": "string"}},
         "required": ["ref"], "additionalProperties": False},
        {"type": "object", "minProperties": 1, "maxProperties": 1},
    ]
}

_CONDITION = {
    "type": "object",
    "maxProperties": 1,
    "description": "키가 하나인 객체. and/or 는 배열을, 비교는 피연산자 2개를 받는다. "
                   "빈 객체는 조건 없음(항상 적용)이고 UNSUPPORTED 에만 쓴다.",
}

_ANCHOR = {
    "type": "object",
    "properties": {
        "anchor": {"type": "string", "enum": sorted(catalog.VARIABLES)},
        "offset_months": {"type": "integer"},
        "day": {"anyOf": [{"enum": ["first", "last"]}, {"type": "integer"}]},
    },
    "required": ["anchor"],
    "additionalProperties": False,
}

_WINDOW = {
    "type": "object",
    "properties": {
        "month_range": {
            "type": "object",
            "properties": {"from": _ANCHOR, "to": _ANCHOR},
            "required": ["from", "to"],
            "additionalProperties": False,
        }
    },
    "required": ["month_range"],
    "additionalProperties": False,
}

_EFFECT = {
    "type": "object",
    "properties": {
        "type": {"enum": sorted(catalog.EFFECTS)},
        "value": {"type": ["number", "string", "boolean"]},
        "unit": {"enum": list(catalog.UNITS)},
        "target": {"enum": sorted(catalog.FEES)},
        "applies_to": {"enum": list(catalog.APPLIES_TO)},
    },
    "required": ["type"],
    "additionalProperties": False,
}

_RULE = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string"},
        "status": {"enum": ["OK", "UNSUPPORTED"]},
        "label": {"type": "string"},
        "source": {
            "type": "object",
            "properties": {"quote": {"type": "string"}},
            "required": ["quote"],
            "additionalProperties": False,
        },
        "let": {"type": "object", "additionalProperties": _WINDOW},
        "guard": _CONDITION,
        "condition": _CONDITION,
        "effect": _EFFECT,
    },
    "required": ["rule_id", "source", "condition"],
    "additionalProperties": False,
    # status 가 UNSUPPORTED 면 옮길 effect 가 없다. 그 경우만 effect 를 뺄 수 있다.
    "anyOf": [
        {"required": ["effect"]},
        {"properties": {"status": {"const": "UNSUPPORTED"}}, "required": ["status"]},
    ],
}

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"rules": {"type": "array", "items": _RULE}},
    "required": ["rules"],
    "additionalProperties": False,
}

# ── few-shot ────────────────────────────────────────────────────────────
# 이 예시 하나가 창(let), 가드, 개월 수 세기, 단위를 한 번에 보여준다.
FEWSHOT_CLAUSE = (
    "적금 가입월 1일부터 만기월의 전전월 마지막일까지 급여이체가 발생한 월이 "
    "총 6개월 이상인 경우 연 1.0%p의 우대금리를 제공합니다. "
    "단, 중도해지 시에는 우대금리가 적용되지 않습니다."
)

FEWSHOT_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-01",
            "status": "OK",
            "label": "급여이체 우대금리",
            "source": {
                "quote": "급여이체가 발생한 월이 총 6개월 이상인 경우 "
                         "연 1.0%p의 우대금리를 제공합니다"
            },
            "let": {
                "window": {
                    "month_range": {
                        "from": {"anchor": "contract.start_date",
                                 "offset_months": 0, "day": "first"},
                        "to": {"anchor": "contract.maturity_date",
                               "offset_months": -2, "day": "last"},
                    }
                }
            },
            "guard": {"==": [{"var": "contract.termination_type"}, "MATURITY"]},
            "condition": {
                ">=": [{"count_distinct_months": {"event": "SALARY_TRANSFER",
                                                  "within": {"ref": "$window"}}}, 6]
            },
            "effect": {"type": "RATE_ADD", "value": 1.0,
                       "unit": "%p", "applies_to": "BASE_RATE"},
        }
    ]
}

# 면제횟수 표를 옮기는 장면. **일곱 라운드 동안 FEE_WAIVE rule 62개가 나왔는데
# "UNLIMITED" 를 쓴 것이 0개였다.** 카탈로그에 있고 스키마도 허용하는데 모델이
# 그 표현을 한 번도 못 봤다. 조문의 "제한없음" 을 전부 숫자 1 로 적었다.
#
# 보여주는 것 셋 —
#   "제한없음" → "UNLIMITED"      (수가 아니다)
#   "월 10회"  → 10               (조문에 적힌 수 그대로)
#   빈 칸      → 윗행 값을 물려받는다 (표가 그렇게 생겼다)
#
# rule 수는 표의 행 수와 같다. 표에 없는 대상은 출력에도 없다.
# 마지막 ※ 줄은 안내문이라 rule 이 되지 않는다 — 빈 배열 장면을 일부 벌충한다.
FEWSHOT_EMPTY_CLAUSE = (
    "[수수료 면제]\n"
    "▪ 면제조건: 전월 중 이 통장에서 급여이체 실적이 있는 경우\n"
    "▪ 면제대상 수수료 및 면제횟수\n"
    "\n"
    "[참조표: 면제 대상 수수료 및 면제횟수]\n"
    "면제 대상 수수료 | 면제횟수\n"
    "전자금융 이체수수료 | 제한없음\n"
    "자동화기기 시간외출금수수료 | \n"
    "자동화기기 이체수수료 | 월 10회\n"
    "※ 면제 내용은 영업점에 게시한 바에 따릅니다."
)
FEWSHOT_EMPTY_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-02-01",
            "status": "OK",
            "label": "전자금융 이체수수료 면제",
            "source": {"quote": "전자금융 이체수수료 | 제한없음"},
            "let": {"window": {"month_range": {
                "from": {"anchor": "contract.reference_date",
                         "offset_months": -1, "day": "first"},
                "to": {"anchor": "contract.reference_date",
                       "offset_months": -1, "day": "last"}}}},
            "condition": {"exists": {"event": "SALARY_TRANSFER",
                                     "within": {"ref": "$window"}}},
            "effect": {"type": "FEE_WAIVE", "target": "EBANK_TRANSFER",
                       "value": "UNLIMITED"},
        },
        {
            "rule_id": "R-EX-02-02",
            "status": "OK",
            "label": "시간외출금수수료 면제",
            "source": {"quote": "자동화기기 시간외출금수수료 |"},
            "let": {"window": {"month_range": {
                "from": {"anchor": "contract.reference_date",
                         "offset_months": -1, "day": "first"},
                "to": {"anchor": "contract.reference_date",
                       "offset_months": -1, "day": "last"}}}},
            "condition": {"exists": {"event": "SALARY_TRANSFER",
                                     "within": {"ref": "$window"}}},
            "effect": {"type": "FEE_WAIVE",
                       "target": "ATM_WITHDRAW_AFTER_HOURS",
                       "value": "UNLIMITED"},
        },
        {
            "rule_id": "R-EX-02-03",
            "status": "OK",
            "label": "자동화기기 이체수수료 면제",
            "source": {"quote": "자동화기기 이체수수료 | 월 10회"},
            "let": {"window": {"month_range": {
                "from": {"anchor": "contract.reference_date",
                         "offset_months": -1, "day": "first"},
                "to": {"anchor": "contract.reference_date",
                       "offset_months": -1, "day": "last"}}}},
            "condition": {"exists": {"event": "SALARY_TRANSFER",
                                     "within": {"ref": "$window"}}},
            "effect": {"type": "FEE_WAIVE", "target": "ATM_TRANSFER",
                       "value": 10},
        },
    ]
}

# 표현 수단이 없을 때의 탈출구. 가르치기 전에 검증기부터 막았다 (§9 11번).
#
# 조문은 **코퍼스와 같은 조판**으로 적는다. 코퍼스 46조문이 전부 대괄호 머리로
# 시작하고 44조문이 줄머리 기호를 갖는데, 예시 조문 셋은 전부 장식 없는 평문이었다.
# 모델은 장식이 붙은 줄에서 옮기는 장면을 한 번도 못 봤다 (§9 10번과 같은 자리).
#
# v2 실측: ④ 실패 15건 중 지어낸 것이 0건이고, 전부 원문의 올바른 위치를 짚은 뒤
# 옮기면서 대괄호·줄머리 기호·굽은 따옴표를 정리해 버렸다.
#
# quote 는 머리줄과 다음 줄에 걸치고 기호를 그대로 안고 간다. 줄이 바뀐 자리만
# 띄어쓰기로 잇는다 — 채점은 공백만 무시한다. quote 안에 진짜 줄바꿈을 넣으면
# JSON 문자열 이스케이프를 새로 가르치게 되어 ① 을 흔들 수 있다.
FEWSHOT_UNSUPPORTED_CLAUSE = (
    "[한도 예외]\n"
    "▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우 한도를 달리 정할 수 있습니다.\n"
    "※ 이 경우의 한도는 영업점에 고시한 바에 따릅니다."
)
FEWSHOT_UNSUPPORTED_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-99",
            "status": "UNSUPPORTED",
            "label": "영업점장 재량",
            "source": {"quote": "[한도 예외] ▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우"},
            "condition": {},
        }
    ]
}

# 혜택이 **말로만** 언급된 조문. 숫자도 조건도 없으면 rule 이 없다.
#
# v9 에서 이 장면을 면제횟수 장면과 맞바꿨더니, 빈 배열을 내야 할 조문들이
# rule 을 만들기 시작했다 — ⑦ 13.0% → 6.5%, ⑩ 합성 46.9% → 12.5%.
# 예시 자리는 유한한 자원이고, 빼는 것이 무엇을 가르치고 있었는지 먼저 알아야 한다.
#
# 맞바꾸지 않고 **더한다.** 상품 소개 문장에서 우대금리를 지어내는 것이
# ⑨ 의 대표 실패라, 그 모양을 그대로 보여준다. 코퍼스 문장을 베끼지는 않는다.
FEWSHOT_INTRO_CLAUSE = (
    "[상품 개요]\n"
    "상 품 명 : 예시적금\n"
    "상품특징 : 자동이체를 등록한 고객에게 금리 혜택과 창구 수수료 감면을 "
    "제공하는 자유적립식 적금"
)
FEWSHOT_INTRO_OUTPUT = {"rules": []}

FEWSHOTS = (
    (FEWSHOT_CLAUSE, FEWSHOT_OUTPUT),
    (FEWSHOT_EMPTY_CLAUSE, FEWSHOT_EMPTY_OUTPUT),
    (FEWSHOT_UNSUPPORTED_CLAUSE, FEWSHOT_UNSUPPORTED_OUTPUT),
    (FEWSHOT_INTRO_CLAUSE, FEWSHOT_INTRO_OUTPUT),
)
