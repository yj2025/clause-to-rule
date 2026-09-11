"""카탈로그 — 모델이 쓸 수 있는 어휘 전부.

여기 없는 이름을 쓰면 ③ 카탈로그 준수 실패다.

복원 근거: 노트북 §3 의 저장된 출력(개수와 앞머리 순서)과 v3 생성물 139개 rule
에서 실측한 이름. 개수는 맞췄고, 출력에 이름이 안 찍힌 몇 개는 상품설명서 본문에
근거가 있는 것으로 채웠다 — RECOVERY.md 의 "복원 신뢰도" 참고.

확장 대기 4건은 일부러 넣지 않았다 (팀 io 명세 합의 필요) —
상품 전환 effect · 적용 기준 금액 effect · 압류 계열 이벤트 · 출금 이벤트.
"""

# ── 변수 (17) ───────────────────────────────────────────────────────────
def _v(t, d):
    return {"type": t, "desc": d}


VARIABLES = {
    "contract.start_date":       _v("date", "가입일"),
    "contract.maturity_date":    _v("date", "만기일"),
    "contract.term_months":      _v("int",  "가입기간(개월)"),
    "contract.amount":           _v("int",  "가입금액(원)"),
    "contract.monthly_amount":   _v("int",  "월 납입금액(원)"),
    "contract.base_rate":        _v("num",  "기본금리(%)"),
    "contract.channel":          _v("enum", "가입/거래 채널"),
    "contract.reference_date":   _v("date", "판별 기준일"),
    "contract.switch_date":      _v("date", "이 통장으로 전환한 날"),
    "contract.termination_date": _v("date", "해지일"),
    "contract.termination_type": _v("enum", "해지 유형"),
    "account.balance":           _v("int",  "예금 잔액(원)"),
    "account.reserved_amount":   _v("int",  "저금통 적립액(원)"),
    "customer.age":              _v("int",  "만 나이"),
    "customer.is_youth":         _v("bool", "만 19세 미만 Youth 고객"),
    "customer.has_product":      _v("bool", "해당 상품 보유 여부"),
    "customer.is_first_deposit": _v("bool", "첫 거래 여부"),
}

# 값은 v3 생성물에서 실제로 쓰인 것을 기준으로 복원했다.
# PARTIAL(일부해지) 과 ONLINE 은 v3 의 ③ 이 통과시킨 값이라 카탈로그에 있었다고 본다.
ENUM_VALUES = {
    "contract.channel":          ("BRANCH", "ONLINE", "INTERNET", "MOBILE", "ATM", "CALL"),
    "contract.termination_type": ("MATURITY", "EARLY", "PARTIAL", "MID_TERM", "NONE"),
}

# ── 이벤트 (10) ─────────────────────────────────────────────────────────
EVENTS = {
    "SALARY_TRANSFER":        "급여이체",
    "AUTO_TRANSFER":          "자동이체 · 공과금이체",
    "CARD_USAGE":             "카드 결제실적(현금서비스 포함)",
    "DEPOSIT":                "입금",
    "PENSION_RECEIPT":        "연금 수령",
    "FX_TRANSACTION":         "외환 거래",
    "PRODUCT_SWITCH":         "상품 전환",
    "TERMINATION":            "해지",
    "APP_LOGIN":              "앱 로그인",
    "TRANSACTION_CORRECTION": "거래 정정",
}

# ── 연산자 (14) ─────────────────────────────────────────────────────────
COMPARISONS = (">=", ">", "<=", "<", "==", "!=", "in")
LOGICAL     = ("and", "or", "not")
QUANTIFIERS = ("exists", "count_events",
               "count_distinct_months", "count_consecutive_months")
OPERATORS   = (">=", ">", "<=", "<", "==", "!=", "and", "or", "not", "in",
               "exists", "count_events",
               "count_distinct_months", "count_consecutive_months")

# 수를 돌려주는 것들. 비교의 피연산자 자리에 들어간다.
COUNTERS = ("count_events", "count_distinct_months", "count_consecutive_months")

# ── effect (8) ──────────────────────────────────────────────────────────
# 이름 → 필수 키
EFFECTS = {
    "RATE_ADD":      ("value", "unit"),
    "RATE_SUBTRACT": ("value", "unit"),
    "RATE_OVERRIDE": ("value", "unit"),
    "PENALTY_RATE":  ("value", "unit"),
    "DISQUALIFY":    (),
    "LIMIT_AMOUNT":  ("value",),
    "REQUIRE":       ("value",),
    "FEE_WAIVE":     ("target", "value"),
}

# value 가 반드시 수여야 하는 것들 — check_effect_value 가 쓴다
RATE_EFFECTS = ("RATE_ADD", "RATE_SUBTRACT", "RATE_OVERRIDE", "PENALTY_RATE")

# ── 수수료 대상 (6) ─────────────────────────────────────────────────────
FEES = {
    "EBANK_TRANSFER":           "전자금융 이체수수료",
    "ATM_TRANSFER":             "자동화기기 이체수수료",
    "ATM_WITHDRAW_AFTER_HOURS": "자동화기기 시간외 출금수수료",
    "OTHER_BANK_ATM_WITHDRAW":  "타행 자동화기기 출금수수료",
    "AUTO_DEBIT":               "납부자자동이체 수수료",
    "SMS_NOTICE":               "입출금 알림 수수료",
}

UNITS = ("%p", "%", "원", "회", "회/월", "개월", "age", "channel", "date", "")

APPLIES_TO = ("BASE_RATE", "FINAL_RATE")

# 표현 수단이 없는 조문의 탈출구. effect 가 아니라 rule 의 status 다 (§9 11번).
STATUSES = ("OK", "UNSUPPORTED")


# ── 조문에 붙일 후보 고르기 ──────────────────────────────────────────────
# 카탈로그 전체를 프롬프트에 넣으면 길어지고, 안 쓰는 이름을 부르면 오히려
# 가르친다 (§9 2번). 조문 본문에 근거가 있는 것만 골라 붙인다.
_HINTS = {
    "contract.start_date":       ("가입일", "신규", "개설"),
    "contract.maturity_date":    ("만기",),
    "contract.term_months":      ("가입기간", "개월"),
    "contract.amount":           ("가입금액", "예치금액"),
    "contract.monthly_amount":   ("월", "매월"),
    "contract.base_rate":        ("기본금리", "기본 금리", "고시"),
    "contract.channel":          ("채널", "인터넷", "모바일", "창구", "영업점", "자동화기기"),
    "contract.reference_date":   ("기준일", "결산일", "전월", "당월", "이번 달", "다음달"),
    "contract.switch_date":      ("전환",),
    "contract.termination_date": ("해지일",),
    "contract.termination_type": ("해지", "만기", "중도"),
    "account.balance":           ("잔액", "예금액", "금액", "원"),
    "account.reserved_amount":   ("저금통", "적립"),
    "customer.age":              ("세", "나이", "만 "),
    "customer.is_youth":         ("Youth", "청소년", "미성년"),
    "customer.has_product":      ("보유", "가입한"),
    "customer.is_first_deposit": ("첫 거래", "최초"),
    "SALARY_TRANSFER":           ("급여이체", "급여"),
    "AUTO_TRANSFER":             ("자동이체", "공과금", "지로", "CMS"),
    "CARD_USAGE":                ("카드", "결제실적"),
    "DEPOSIT":                   ("입금", "예치"),
    "PENSION_RECEIPT":           ("연금",),
    "FX_TRANSACTION":            ("외화", "환전", "외환"),
    "PRODUCT_SWITCH":            ("전환",),
    "TERMINATION":               ("해지",),
    "APP_LOGIN":                 ("로그인", "앱", "스타뱅킹"),
    "TRANSACTION_CORRECTION":    ("정정", "취소"),
}


def pick_candidates(text):
    """조문 본문에 근거가 있는 변수와 이벤트만 고른다.

    반환: (변수 목록, 이벤트 목록). 둘 다 정렬돼 있다.
    """
    hit = {k for k, words in _HINTS.items() if any(w in text for w in words)}
    return (sorted(k for k in hit if k in VARIABLES),
            sorted(k for k in hit if k in EVENTS))


def pick_fees(text):
    """수수료 면제 조문에 붙일 대상."""
    words = {"EBANK_TRANSFER": ("전자금융", "이체수수료"),
             "ATM_TRANSFER": ("자동화기기", "ATM"),
             "ATM_WITHDRAW_AFTER_HOURS": ("시간외",),
             "OTHER_BANK_ATM_WITHDRAW": ("타행",),
             "AUTO_DEBIT": ("자동이체", "납부자"),
             "SMS_NOTICE": ("알림", "SMS", "문자")}
    return sorted(k for k, ws in words.items() if any(w in text for w in ws))


def is_known_value(var, value):
    """enum 변수의 값이 카탈로그에 있나."""
    return value in ENUM_VALUES[var] if var in ENUM_VALUES else True
