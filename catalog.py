"""카탈로그 — 모델이 쓸 수 있는 어휘 전부.

여기 없는 이름을 쓰면 ③ 카탈로그 준수 실패다.

**이 목록은 복원본이다.** 2026-09-11 에 원본 저장소가 유실돼 노트북에 저장된
출력에서 다시 세웠다. 신뢰도가 이름마다 다르다.

* **개수** — 저장된 출력과 맞췄다. 확실하다
* **대부분의 이름** — 저장된 출력의 앞머리 순서와 v3 생성물 139개 rule 에서
  실측했다. 근거가 있다
* **몇 개** — 출력에 이름이 안 찍혀 **상품설명서 본문을 근거로 채웠다. 추측이다**

카탈로그 확장을 정할 때 이것을 알아야 한다. "이 이름이 카탈로그에 없다" 는
판정이 추측으로 채운 이름 때문일 수 있다. 원본 이름이 나오면 맞춰야 한다.

확장 대기 4건은 일부러 넣지 않았다 (팀 io 명세 합의 필요) —
상품 전환 effect · 적용 기준 금액 effect · 압류 계열 이벤트 · 출금 이벤트.
"""

# ── 변수 (19) ───────────────────────────────────────────────────────────
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
    # 2026-09-15 확장 셋째 항목. 두 상품에서 방향이 반대다 — KBYY 는 개인사업자
    # 가입 불가, KBONE 은 포함. 불리언 하나로는 둘 다 못 담아 열거형으로 둔다.
    "customer.holder_type":      _v("enum", "명의 유형"),
    # 2026-09-15 확장 넷째 항목. 휴면예금 조문의 "예금 만기일 또는 이자지급을 포함한
    # 최종거래일" 을 이 하나로 받는다 — 만기 지급도 거래로 친다. 무거래 창을 이벤트로
    # 세면 명의변경 거래가 빠져(카탈로그에 없다) 거래중지 조문과 같은 자리에 막힌다.
    "account.last_transaction_date": _v("date", "최종거래일(입출금·이자지급·만기지급 포함)"),
    # 2026-09-20 실행기 범위 결정. 「예금주가 만기일 전에 지급청구할 때」 처럼 **인출을 요구한 날**이
    # 중도해지이율·만기후이율을 가른다. 해지일과 다르다 — 일부 지급도 지급청구다.
    # **데이터 쪽 확인 필요:** 고객 데이터에 이 날짜가 있는지 아직 안 물었다.
    "contract.payout_request_date": _v("date", "지급청구일(인출을 요구한 날)"),
}

# 값은 v3 생성물에서 실제로 쓰인 것을 기준으로 복원했다.
# PARTIAL(일부해지) 과 ONLINE 은 v3 의 ③ 이 통과시킨 값이라 카탈로그에 있었다고 본다.
ENUM_VALUES = {
    "contract.channel":          ("BRANCH", "ONLINE", "INTERNET", "MOBILE", "ATM", "CALL"),
    "contract.termination_type": ("MATURITY", "EARLY", "PARTIAL", "MID_TERM", "NONE"),
    # 임의단체는 관련서류(고유번호 등) 제출 여부로 둘로 가른다 — 조문이 그렇게 가른다.
    "customer.holder_type":      ("INDIVIDUAL", "SOLE_PROPRIETOR",
                                  "UNREGISTERED_ASSOCIATION", "REGISTERED_ASSOCIATION",
                                  "JOINT", "CORPORATION"),
}

# ── 이벤트 (10) ─────────────────────────────────────────────────────────
EVENTS = {
    "SALARY_TRANSFER":        "급여이체",
    "AUTO_TRANSFER":          "자동이체 · 공과금이체",
    "CARD_USAGE":             "카드 결제실적(현금서비스 포함)",
    "DEPOSIT":                "입금",
    # v17 에서 더했다. `CATALOG_PROPOSAL.md` 2순위 — 8조문 18 rule 이 여기 걸린다.
    # DEPOSIT 만 있으면 **출금만 있던 계좌가 무거래로 판정된다.** 부호가 뒤집힌다.
    "WITHDRAWAL":             "출금",
    "PENSION_RECEIPT":        "연금 수령",
    "FX_TRANSACTION":         "외환 거래",
    "PRODUCT_SWITCH":         "상품 전환",
    "TERMINATION":            "해지",
    "APP_LOGIN":              "앱 로그인",
    "TRANSACTION_CORRECTION": "거래 정정",
    # 2026-09-15 확장 다섯째 항목. 거래중지 조문의 "무거래기간 산정기준: 입출금 거래 또는
    # 명의변경 거래 최종 발생일로부터". 출금(v17)만 넣어서는 이 갈래가 빠져 한 조문도 안 열렸다.
    "NAME_CHANGE":            "명의변경 거래",
}

# ── 이벤트 속성 ─────────────────────────────────────────────────────────
# 2026-09-15 확장 여섯째 항목. exists · count_* 의 "where" 에 건다.
# 건별 금액은 속성이 아니라 where 의 min_amount 키다 ("건별 50만원 이상").
# 속성이 없는 이벤트는 "모른다" — 맞췄다고도 못 맞췄다고도 하지 않는다.
# 쪼개서 이벤트 이름을 늘리지 않은 이유는 `DECISIONS.md` 결정 2 · 3.
EVENT_ATTRIBUTES = {
    # 공과금이체 인정범위 "아파트관리비, 지로, CMS, 펌뱅킹을 통한 자동납부(카드결제분 제외)"
    "AUTO_TRANSFER":   {"route": ("APARTMENT_FEE", "GIRO", "CMS", "FIRM_BANKING", "CARD")},
    # "급여이체 계약에 의하지 않은 일반 이체거래에 의한 입금 건은 급여이체실적으로 인정되지 않는다"
    "SALARY_TRANSFER": {"source": ("SALARY_CONTRACT", "GENERAL_TRANSFER")},
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

# ── effect (10) ──────────────────────────────────────────────────────────
# 이름 → 필수 키
EFFECTS = {
    "RATE_ADD":      ("value", "unit"),
    "RATE_SUBTRACT": ("value", "unit"),
    "RATE_OVERRIDE": ("value", "unit"),
    "PENALTY_RATE":  ("value", "unit"),
    # **가입 자격 상실만.** 대상(target)을 받지 않는다 — 계좌 전체에 걸린다.
    # 2026-09-16 · v24 에서 여기가 새는 자리로 확인됐다. 거래 제한(RESTRICT)과
    # 휴면예금 출연(DORMANT_CONTRIBUTION) 의 자리를 만들어 줬는데도, 그 일곱 조문 중
    # 여섯이 DISQUALIFY 로 왔다. 이름만 준 도구는 **기존에 그럴듯한 자리가 있으면
    # 안 열린다.** 그래서 이쪽을 좁힌다 (validate.check_effect · invent.check_rule).
    "DISQUALIFY":    (),
    "LIMIT_AMOUNT":  ("value",),
    "REQUIRE":       ("value",),
    "FEE_WAIVE":     ("target", "value"),
    # 2026-09-15 확장 첫째 항목 (`DECISIONS.md` 임시 확정). 금리·수수료·한도가 아닌
    # 급부를 담는다. value 는 수량이고 unit 이 그 뜻을 정한다 — 회(횟수) · 개월/년(기간).
    # 선택 키 renewable 은 "1년 단위 갱신" 처럼 기간이 되풀이될 때만 쓴다.
    "SERVICE_PROVIDE": ("target", "value", "unit"),
    # 2026-09-15 확장 둘째 항목. "수수료면제 잔여횟수는 이월되지 않습니다".
    # 자리가 없을 때 FEE_WAIVE 에 횟수 0 을 적으면 면제 자체가 사라져 뜻이 뒤집힌다.
    # 필수 키가 없다. 선택 키 target(FEES)이 없으면 모든 면제에 걸린다.
    # 잔여횟수 변수는 넣지 않았다 — 판별 범위에서는 이월 금지라는 사실만 담으면 된다.
    "FEE_WAIVE_NO_CARRYOVER": (),
    # 2026-09-15 넷째 항목에 붙였다 (합의한 여섯 밖, 사람 확인 09-15). "휴면예금은
    # 서민금융진흥원에 출연될 수 있으며". 최종거래일 변수만으로는 조문이 안 열린다.
    # DISQUALIFY 는 가입 자격 상실이라 뜻이 다르다. 불이익 effect — 조건이 완전해야 한다.
    "DORMANT_CONTRIBUTION": (),
    # 2026-09-15 확장 다섯째 항목. 특정 거래만 막는다 — 예금 자격은 그대로다.
    # 자리가 없을 때 모델이 가장 많이 DISQUALIFY 로 밀어 넣었다 (v14 에서 13개 중 다수).
    # target 은 RESTRICTIONS 에서 고른다. 불이익 effect — 조건이 완전해야 한다.
    "RESTRICT": ("target",),
    # 2026-09-20 실행기 범위 결정 5. 「비과세종합저축으로 가입 가능」 — 세율·세금 계산은 범위 밖이지만
    # **가입 자격**은 고객을 가른다. 필수 키가 없다 — 조건이 붙으면 그 조건이 자격을 좁힌다.
    "TAX_EXEMPT_ELIGIBLE": (),
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

# ── 제휴서비스 대상 (3) ─────────────────────────────────────────────────
# SERVICE_PROVIDE 의 target. 이 자리가 없을 때 모델은 REQUIRE 에 서비스명을 적거나
# "고객별 1회" 를 LIMIT_AMOUNT 1 로 옮겼다 — 1원 한도로 읽혀 뜻이 뒤집힌다.
# 표의 품목이 둘(수강권 · 영자신문)이라 단위만으로는 무엇을 주는지 못 가른다.
SERVICES = {
    "NE_TIMES_TRIAL":         "㈜NE능률 NE Times 무료체험프로그램",
    "NE_TIMES_ONLINE_COURSE": "NE Times 온라인수강권",
    "NE_TIMES_NEWSPAPER":     "NE Times 영자신문",
}

# ── 금지 대상 (3) ───────────────────────────────────────────────────────
# RESTRICT 의 target. 담보제공과 질권설정은 조문마다 이름만 달라 하나로 둔다.
RESTRICTIONS = {
    "ALL_TRANSACTIONS": "입출금·잔액조회·이관 등 거래 전반 (거래중지)",
    "PLEDGE":           "담보제공 · 질권설정",
    "NAME_CHANGE":      "양도·상속에 의한 명의변경",
    # 2026-09-20 실행기 범위 결정. 「일부해지 불가」 · 「중도해지 불가」 · 「만기 앞당김 지급 불가」 는
    # 이율을 고르는 문제가 아니라 **그 거래를 막는다.** 팀원 gold 에서 9자리가 여기 걸려 있었다.
    "PARTIAL_TERMINATION": "일부해지 · 일부인출",
    "EARLY_TERMINATION":   "중도해지",
    "EARLY_PAYOUT":        "만기 앞당김 지급 · 만기 전 지급청구",
}

UNITS = ("%p", "%", "원", "회", "회/월", "개월", "년", "age", "channel", "date", "")


# ── 코드가 원래 있어야 할 자리 (2026-09-16) ─────────────────────────────
#
# 카탈로그가 넓어질 때마다 **새 이름이 REQUIRE/DISQUALIFY 의 value 로도 공짜로
# 통과하게 된다.** 그 자리는 자유 문자열이고, ⑬ 은 "카탈로그 어딘가에 있나" 만
# 보기 때문이다 (일부러 그렇게 뒀다 — 자리 오류는 ⑬ 이 아니라 ③ 이 볼 일이다.
# `tests/test_invent.py::test_an_event_name_in_the_wrong_slot_is_allowed_by_this_axis`).
#
# v24 에서 그 대가를 치렀다. 09-15 에 명의유형을 넣자 `INDIVIDUAL` ·
# `SOLE_PROPRIETOR` 가 카탈로그에 들어왔고, 모델이 그것을 `REQUIRE` 의 value 에
# 담았다. gold 는 `holder_type` 을 조건에서 비교해 `DISQUALIFY` 하는 자리다.
# **사람 검토를 마친 조문 둘이 그렇게 깨졌다** (`KBONE-S2-R01` · `KBYY-S2-R01`).
#
# 확장할 때마다 손으로 막을 수는 없다. 이름이 어느 자리 것인지를 카탈로그가
# 직접 들고 있게 해서, 새 이름이 들어와도 자동으로 제자리를 갖게 한다.
def slot_of(code):
    """이 코드가 원래 있어야 할 자리. 어디에도 없으면 None."""
    return _SLOTS().get(code)


_SLOTS_CACHE = None


def _SLOTS():
    global _SLOTS_CACHE
    if _SLOTS_CACHE is not None:
        return _SLOTS_CACHE
    out = {}
    for name, vals in ENUM_VALUES.items():
        for v in vals:
            out.setdefault(v, f"조건에서 `{name}` 과 비교하는 자리")
    for v in RESTRICTIONS:
        out[v] = "`RESTRICT` 의 target"
    for v in SERVICES:
        out[v] = "`SERVICE_PROVIDE` 의 target"
    for v in FEES:
        out[v] = "`FEE_WAIVE` 의 target"
    for v in EVENTS:
        out.setdefault(v, "조건의 `exists` · `count_events` 자리")
    for v in VARIABLES:
        out.setdefault(v, "조건의 `var` 자리")
    _SLOTS_CACHE = out
    return out

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
    "customer.holder_type":      ("개인사업자", "임의단체", "공동명의", "실명의 개인"),
    # "거래가 없는" 은 넣지 않는다 — 거래중지 조문은 명의변경 거래까지 세야 해 아직 막혀 있다
    "account.last_transaction_date": ("최종거래일", "휴면"),
    "contract.payout_request_date":   ("지급청구", "찾고자"),
    "NAME_CHANGE":               ("명의변경",),
    "SALARY_TRANSFER":           ("급여이체", "급여"),
    "AUTO_TRANSFER":             ("자동이체", "공과금", "지로", "CMS"),
    "CARD_USAGE":                ("카드", "결제실적"),
    "DEPOSIT":                   ("입금", "예치"),
    "WITHDRAWAL":                ("출금", "인출"),
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


def pick_services(text):
    """제휴서비스 조문에 붙일 대상."""
    words = {"NE_TIMES_TRIAL": ("무료체험", "NE Times", "NE능률", "제공기간"),
             "NE_TIMES_ONLINE_COURSE": ("수강권",),
             "NE_TIMES_NEWSPAPER": ("영자신문",)}
    return sorted(k for k, ws in words.items() if any(w in text for w in ws))


def pick_restrictions(text):
    """금지 조문에 붙일 대상."""
    words = {"ALL_TRANSACTIONS": ("거래 제한", "거래중지", "잔액조회"),
             "PLEDGE": ("담보", "질권"),
             "NAME_CHANGE": ("명의변경", "양도", "상속"),
             "PARTIAL_TERMINATION": ("일부해지", "일부 해지", "일부인출"),
             "EARLY_TERMINATION": ("중도해지", "중도 해지"),
             "EARLY_PAYOUT": ("만기앞당김", "만기 앞당김", "만기전 지급")}
    return sorted(k for k, ws in words.items() if any(w in text for w in ws))


def is_known_value(var, value):
    """enum 변수의 값이 카탈로그에 있나."""
    return value in ENUM_VALUES[var] if var in ENUM_VALUES else True
