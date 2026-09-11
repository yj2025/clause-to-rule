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

# 표현할 수 없는 조문은 빈 배열이 정답이다 (§9 10번).
# 예시 1~3 이 전부 rule 을 내놓는 형태여서 모델이 본 빈 배열이 하나도 없었다.
FEWSHOT_EMPTY_CLAUSE = "이 통장은 「예금자보호법」에 따라 보호됩니다."
FEWSHOT_EMPTY_OUTPUT = {"rules": []}

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
# 한 조문 안에서 **일부만** UNSUPPORTED 로 두는 장면을 보여준다.
#
# v2 실측: ③ 를 처음 못 넘는 34건 중 이름을 지어낸 16건은 전부 "rule 1~5개 중
# 위반은 1~2개" 형태이고, 그 위반 rule 만 UNSUPPORTED 로 바꾸면 16/16 이 통과한다.
# 모델은 UNSUPPORTED 를 이미 많이 쓴다(rule 250개 중 77개). 부족한 것은 선택지가
# 아니라 **쪼개는 형태**다 — 138건 중 섞인 출력은 10건뿐이었다.
#
# 조판은 v4 에서 바꾼 것을 그대로 둔다. 이 라운드에서 더하는 것은 OK rule 하나뿐이다.
FEWSHOT_UNSUPPORTED_CLAUSE = (
    "[한도 예외]\n"
    "▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우 한도를 달리 정할 수 있습니다.\n"
    "▪ 가입금액이 1천만원 이상인 경우 연 0.2%p의 우대금리를 제공합니다.\n"
    "※ 이 경우의 한도는 영업점에 고시한 바에 따릅니다."
)
FEWSHOT_UNSUPPORTED_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-99-01",
            "status": "UNSUPPORTED",
            "label": "영업점장 재량 — 옮길 수단이 목록에 없다",
            "source": {"quote": "[한도 예외] ▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우"},
            "condition": {},
        },
        {
            "rule_id": "R-EX-99-02",
            "status": "OK",
            "label": "가입금액 우대금리",
            "source": {"quote": "가입금액이 1천만원 이상인 경우 연 0.2%p의 우대금리를 제공합니다"},
            "condition": {">=": [{"var": "contract.amount"}, 10000000]},
            "effect": {"type": "RATE_ADD", "value": 0.2,
                       "unit": "%p", "applies_to": "BASE_RATE"},
        },
    ]
}

FEWSHOTS = (
    (FEWSHOT_CLAUSE, FEWSHOT_OUTPUT),
    (FEWSHOT_EMPTY_CLAUSE, FEWSHOT_EMPTY_OUTPUT),
    (FEWSHOT_UNSUPPORTED_CLAUSE, FEWSHOT_UNSUPPORTED_OUTPUT),
)
