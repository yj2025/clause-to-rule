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
    # `condition` 은 **status 가 OK 일 때만** 요구한다.
    #
    # UNSUPPORTED 는 "옮길 수단이 없다" 는 선언이라 담을 조건 자체가 없다.
    # `{}` 를 적으라는 것은 우리 관례일 뿐 형식이 요구하는 것이 아니다.
    #
    # 예시 3 이 `"condition": {}` 을 보여주고 지시문에도 적혀 있는데
    # **기준선에서 46조문 중 8개가 그래도 빠뜨렸다.** ② 실패 11건 중 8건이
    # 이것뿐이었다. 가르쳐서 안 되고, 요구해서 얻는 것도 없다.
    #
    # 푸니 ② 76.1% → 93.5%, 관문 다섯 전부 통과 37.0% → 50.0% 다.
    # **이 이득은 모델이 좋아진 것이 아니라 셈을 고친 것이다.**
    # 전 라운드를 다시 채점했다 — ROUNDS.md 참고.
    "required": ["rule_id", "source"],
    "additionalProperties": False,
    # status 가 UNSUPPORTED 면 옮길 effect 가 없다. 그 경우만 effect 를 뺄 수 있다.
    "anyOf": [
        {"required": ["effect"]},
        {"properties": {"status": {"const": "UNSUPPORTED"}}, "required": ["status"]},
    ],
    # v23 — **조건 없는 DISQUALIFY 를 막는다.**
    #
    # `{"condition": {}, "effect": {"type": "DISQUALIFY"}}` 는 모든 고객의
    # 예금 자격을 없앤다. 관문 다섯을 전부 통과하고 ⑭ 도 못 본다
    # (빈 조건은 "항상 적용" 이라는 뜻을 밝힌 것이라 일부러 뺀다).
    # 기준선 3회차에서 세 회차 모두 2개, 전부 `KBYY-S2-R18` 이었다.
    #
    # 산문으로는 세 번 실패했다 (v17 이름 · v19 설명 줄 · v20 금지).
    # 스키마는 v12 에서 한 번 통했다 — 지어낸 코드를 ③ 에 물려 ⑬ 을 0% 로
    # 만들었다. 여기서도 ② 가 잡고 재시도가 오류를 그대로 돌려준다.
    #
    # `LIMIT_AMOUNT` 는 조건 `{}` 가 맞다 — 저금통 한도 100만원은 누구에게나
    # 적용된다. `DISQUALIFY` 만 다르다. 골드의 다섯 개는 전부 조건이 있다.
    "allOf": [{
        # OK 면 condition 을 적어야 한다. 조건이 없으면 `{}` 로 "항상 적용" 을
        # 분명히 밝힌다 — 빠뜨린 것과 구별되어야 한다.
        "if": {"properties": {"status": {"const": "OK"}}, "required": ["status"]},
        "then": {"required": ["condition"]},
    }, {
        "if": {
            "properties": {
                "status": {"const": "OK"},
                "effect": {"properties": {"type": {"const": "DISQUALIFY"}},
                           "required": ["type"]},
            },
            "required": ["effect"],
        },
        "then": {
            "anyOf": [
                {"properties": {"condition": {"minProperties": 1}}},
                {"properties": {"guard": {"minProperties": 1}},
                 "required": ["guard"]},
            ],
        },
    }],
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
# **본문과 단서를 가른다.** gold 가 "섞임" 인 조문 5개를 전부 열어 보니
# 옮길 수 없는 부분이 모두 `※` 단서 줄이었고, 본문은 옮길 수 있었다.
# 모델은 다섯 개 전부를 틀린다 — 쪼개지 못하고 전부 아니면 전무로 간다.
#
# 그래서 본문 줄을 하나 더하고 그것을 옮긴 OK rule 을 먼저 놓는다.
# **OK 가 먼저, UNSUPPORTED 가 나중**이다 — v5 는 "UNSUPPORTED 를 써도 된다" 만
# 가르쳐서 ⑧ 이 83.7% 로 무너졌다. 여기서 가르치는 것은 **가르는 법**이다.
FEWSHOT_UNSUPPORTED_CLAUSE = (
    "[한도 예외]\n"
    "▪ 가입금액이 500만원 이상인 경우 이체한도를 2천만원으로 한다.\n"
    "▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우 한도를 달리 정할 수 있습니다.\n"
    "※ 이 경우의 한도는 영업점에 고시한 바에 따릅니다."
)
FEWSHOT_UNSUPPORTED_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-99-01",
            "status": "OK",
            "label": "가입금액에 따른 이체한도",
            "source": {"quote": "▪ 가입금액이 500만원 이상인 경우 이체한도를 2천만원으로 한다."},
            "condition": {">=": [{"var": "contract.amount"}, 5000000]},
            "effect": {"type": "LIMIT_AMOUNT", "value": 20000000},
        },
        {
            "rule_id": "R-EX-99-02",
            "status": "UNSUPPORTED",
            "label": "영업점장 재량 — 옮길 수단이 목록에 없다",
            "source": {"quote": "▪ \u201c영업점장\u201d이 필요하다고 인정하는 경우"},
            "condition": {},
        },
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

# **무거래 기간을 세는 법.** v17~v20 에서 산문으로 세 번 시도해 세 번 다 실패했다.
# 이름만 주면 `contract.term_months`(가입기간)로 옮기고, 어휘에 설명 줄을 붙이면
# `count(WITHDRAWAL) >= 0` 이라는 헛조건을 내고, 지시문에 금지하면 그 모양을
# 그대로 낸다. **장면만 먹는다** — v18 에서 확인했다.
#
# v18 은 이 장면을 넣으려고 `FEWSHOT_INTRO`(빈 배열)를 **맞바꿔서** 되돌렸다.
# ⑦ 이 30.4% → 8.7% 로 무너졌다. 여기서는 **더한다.** 넷을 그대로 두고 다섯째다.
# v10 이 더하기는 된다는 것을 이미 보였다.
#
# 보여주는 것 —
#   입금과 출금을 **둘 다** 세어야 무거래다
#   `count_events` 가 **0 인 것**이 "거래가 없다" 다 (`>= 0` 은 언제나 참이다)
#   창은 `contract.reference_date` 기준이다. 가입일이 아니다
#   혜택이 말로만 언급된 줄은 rule 이 되지 않는다
FEWSHOT_DORMANT_CLAUSE = (
    "[거래 제한]\n"
    "▪ 최근 1년간 입금과 출금이 모두 없는 계좌는 거래를 제한합니다.\n"
    "▪ 편리한 금융 서비스를 제공합니다."
)

FEWSHOT_DORMANT_OUTPUT = {
    "rules": [
        {
            "rule_id": "R-EX-05-01",
            "status": "OK",
            "label": "장기 무거래 계좌",
            "source": {"quote": "▪ 최근 1년간 입금과 출금이 모두 없는 계좌는 거래를 제한합니다."},
            "let": {"window": {"month_range": {
                "from": {"anchor": "contract.reference_date",
                         "offset_months": -12, "day": "first"},
                "to": {"anchor": "contract.reference_date",
                       "offset_months": -1, "day": "last"}}}},
            "condition": {"and": [
                {"==": [{"count_events": {"event": "DEPOSIT",
                                          "within": {"ref": "$window"}}}, 0]},
                {"==": [{"count_events": {"event": "WITHDRAWAL",
                                          "within": {"ref": "$window"}}}, 0]},
            ]},
            "effect": {"type": "DISQUALIFY"},
        }
    ]
}


FEWSHOTS = (
    (FEWSHOT_CLAUSE, FEWSHOT_OUTPUT),
    (FEWSHOT_EMPTY_CLAUSE, FEWSHOT_EMPTY_OUTPUT),
    (FEWSHOT_UNSUPPORTED_CLAUSE, FEWSHOT_UNSUPPORTED_OUTPUT),
    # **다섯째(무거래 장면)는 v22 판정으로 뺐다.** 장면 자체는 먹었다 —
    # 산문 셋(v17·v19·v20)이 못 한 것을 두 번(v18·v21) 해냈다.
    # 그런데 예시를 하나 더 놓으면 ⑦ 빈 배열이 10.9p 무너진다.
    # v21(끝자리)과 v22(넷째 자리)가 **소수점까지 같았다** — 자리가 아니라 개수다.
    # 얻는 것도 있었다: ③ 카탈로그 준수가 rule 있는 회차 기준 +12.9p.
    # 카탈로그가 넓어지면 이 계산이 뒤집힌다 — CATALOG_PROPOSAL.md 참고.
    # 되살리려면 `FEWSHOT_DORMANT_*` 를 이 자리에 넣으면 된다.
    (FEWSHOT_INTRO_CLAUSE, FEWSHOT_INTRO_OUTPUT),
)
