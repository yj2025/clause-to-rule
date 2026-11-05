# -*- coding: utf-8 -*-
"""eval_v2 gold (Fable 판정) — 23조문을 JSON 으로 쓴다."""
import json
from pathlib import Path

OUT = Path(r"C:\HuggingFace_demo\eval_v2\judges\gold_fable")
OUT.mkdir(parents=True, exist_ok=True)
TRIAGE = json.loads(Path(r"C:\HuggingFace_demo\eval_v2\gold\_triage.json").read_text("utf-8"))
VERDICT = {it["id"]: it["verdict"] for it in TRIAGE["items"]}
LABEL = {it["id"]: it["label"] for it in TRIAGE["items"]}


def V(name):
    return {"var": name}


def A(anchor, months=None, day=None):
    d = {"anchor": anchor}
    if months is not None:
        d["offset_months"] = months
    if day is not None:
        d["day"] = day
    return d


def WIN(frm, to):
    return {"month_range": {"from": frm, "to": to}}


MAT = {"==": [V("contract.termination_type"), "MATURITY"]}
EARLY = {"==": [V("contract.termination_type"), "EARLY"]}


def rule(rid, status, label, quote, condition=None, effect=None, let=None, guard=None):
    r = {"rule_id": rid, "status": status, "label": label, "source": {"quote": quote}}
    if let is not None:
        r["let"] = let
    if guard is not None:
        r["guard"] = guard
    r["condition"] = {} if condition is None else condition
    if effect is not None:
        r["effect"] = effect
    return r


def rate_add(v):
    return {"type": "RATE_ADD", "value": v, "unit": "%p", "applies_to": "BASE_RATE"}


def override(v):
    return {"type": "RATE_OVERRIDE", "value": v, "unit": "%"}


DISQ = {"type": "DISQUALIFY"}

GOLD = {}


def put(cid, note, rules):
    GOLD[cid] = {"clause_id": cid, "label": LABEL[cid], "verdict": VERDICT[cid],
                 "note": note, "rules": rules}


# ── 공통 조각 ────────────────────────────────────────────────────────────
def early_first_row(cid, quote, value):
    """중도해지 「1개월 미만 | 고정 이율」 — 해지일 < 가입일+1개월. kb10 KBMY-S2-R11-01 꼴."""
    return rule(f"{cid}-01", "OK", f"예치 1개월 미만 중도해지 → 중도해지금리 연 {value}%", quote,
                {"and": [EARLY, {"<": [V("contract.termination_date"), A("contract.start_date", 1)]}]},
                override(value))


EARLY_NOTE = (
    "rule 4개 · OK 1 · UNSUPPORTED 3. 01 「1개월미만 | 연0.10%」: 중도해지(termination_type EARLY)이고 "
    "해지일 < 가입일+1개월이면 RATE_OVERRIDE 0.1% — 적금은 예치기간이 입금 건별이지만 계좌가 1개월이 안 됐으면 "
    "모든 입금 건이 1개월 미만이라 어느 읽기에서도 맞다(kb10 KBMY-S2-R11-01 과 같은 판단). "
    "02·03 「1~3개월 0.15% · 3~6개월 0.20%」: 값은 수인데 행을 가르는 것이 «입금 건별 예치기간»이다 — "
    "계좌 단위 날짜(해지일-가입일)로 적으면 늦게 넣은 입금 건에 더 높은 이율을 주는 유리한 근사이긴 하나, "
    "행의 유일한 조건을 다른 개념(계좌 경과기간)으로 바꾸는 것이라 UNSUPPORTED 로 두고 조건도 비웠다 "
    "(KBMY-S2-R11 이 적금 행의 조건을 {} 로 둔 것과 같다). 가장 자신 없는 자리 — OK(유리한 근사)로 볼 여지가 있다. "
    "04 「6개월 이상 | 기본금리 × 차등율 × 경과율 (최저 0.20%)」: 비율식 · 경과일수 어휘 없음 → UNSUPPORTED. "
    "(주) 차등율 · 경과율 정의, 소수점 절사, 아래 도해 줄은 산출 세부라 rule 이 아니다."
)


def early_clause(cid, q1, q2, q3, q4):
    put(cid, EARLY_NOTE, [
        early_first_row(cid, q1, 0.1),
        rule(f"{cid}-02", "UNSUPPORTED", "중도해지금리 1개월 이상~3개월 미만 연 0.15% — 입금 건별 예치기간을 담을 변수 없음", q2),
        rule(f"{cid}-03", "UNSUPPORTED", "중도해지금리 3개월 이상~6개월 미만 연 0.20% — 입금 건별 예치기간을 담을 변수 없음", q3),
        rule(f"{cid}-04", "UNSUPPORTED", "중도해지금리 6개월 이상 — 기본금리 × 차등율 × 경과율 (최저 0.20%) 비율식 없음", q4),
    ])


AFTER_NOTE = (
    "rule 2개 · 전부 UNSUPPORTED. 만기후 금리 두 행이 모두 「지급당시 고시 정기적금(상호부금) 기본금리의 ½ · ¼」이라 "
    "값이 수가 아니고(비율식 · 지급당시 고시금리 변수 없음), 만기후 이율을 RATE_OVERRIDE 로 두면 만기 전 약정이율까지 "
    "지운다(kb10 KBSTR-S2-R13 · KBGEN-S2-R08-08~10 과 같은 판단). 구간 조건(만기일 < 해지일 ≤ 만기일+1개월 · 해지일 > 만기일+1개월)은 "
    "날짜 비교로 온전히 표현되므로 남겼다 — 지급청구일 대신 해지일(termination_date)을 예치기간의 끝으로 봤다(kb10 관례). "
    "아래 도해 줄은 표의 되풀이라 rule 이 아니다."
)


def after_clause(cid, q1, q2):
    put(cid, AFTER_NOTE, [
        rule(f"{cid}-01", "UNSUPPORTED", "만기후 1개월 이내 — 지급당시 기본금리 ½ (비율식 없음)", q1,
             {"and": [{">": [V("contract.termination_date"), V("contract.maturity_date")]},
                      {"<=": [V("contract.termination_date"), A("contract.maturity_date", 1)]}]}),
        rule(f"{cid}-02", "UNSUPPORTED", "만기후 1개월 초과 — 지급당시 기본금리 ¼ (비율식 없음)", q2,
             {">": [V("contract.termination_date"), A("contract.maturity_date", 1)]}),
    ])


CALC_NOTE = ("rule 1개 · UNSUPPORTED. 이자계산식(저축금마다 입금일~만기일 전일 × 약정금리)은 이자 금액 산출이라 판별 범위 밖이다 "
             "(kb10 KBMY-S2-R10 · KBSME-S2-R10 관례). 회차별 산식 줄은 같은 식의 되풀이라 rule 하나로 묶었다. "
             "빈 배열로 볼 여지도 있으나 코퍼스 관례(이자 계산식 서술 → UNSUPPORTED)를 따랐다.")


def calc_clause(cid, q):
    put(cid, CALC_NOTE, [rule(f"{cid}-01", "UNSUPPORTED", "이자계산식 — 이자 산출은 판별 범위 밖", q)])


def eligibility_rules(cid, quote, extra_first=None):
    rules = []
    n = 1
    if extra_first:
        rules.append(extra_first(f"{cid}-0{n}"))
        n += 1
    rules.append(rule(f"{cid}-0{n}", "OK", "이미 이 상품을 보유하면 가입 불가 (1인 1계좌)", quote,
                      {"==": [V("customer.has_product"), True]}, DISQ))
    n += 1
    rules.append(rule(f"{cid}-0{n}", "OK", "법인은 가입 불가 (실명의 개인)", quote,
                      {"in": [V("customer.holder_type"), ["CORPORATION"]]}, DISQ))
    return rules


# ═══════════════════════════════════════════════════════════════════════
# HNSAL 급여하나월복리적금
# ═══════════════════════════════════════════════════════════════════════
put("HNSAL-S2-R01",
    "rule 3개 · OK 2 · UNSUPPORTED 1. 01 「1인1계좌」→ customer.has_product 참이면 DISQUALIFY. "
    "02 「실명의개인또는개인사업자」→ 확실히 밖인 법인(CORPORATION)만 탈락시킨다 — kb10 KBGL-S2-R01 · KBMY-S2-R01 의 "
    "가장 좁은 탈락 관례(원칙 1 · 결정 9: 조문이 명시하지 않은 임의단체·공동명의는 탈락시키지 않는다). "
    "개인 · 개인사업자가 허용 목록이므로 not in [INDIVIDUAL, SOLE_PROPRIETOR] 로 넓게 적을 수도 있으나 좁은 쪽을 택했다. "
    "03 「연금하나월복리적금 · 주거래하나월복리적금 과 중복가입 불가」는 customer.held_products 로 적을 자리인데 "
    "상품 키 목록(PRODUCTS)에 하나은행 상품이 없다 → UNSUPPORTED.",
    eligibility_rules("HNSAL-S2-R01", "실명의개인또는개인사업자(1인1계좌)") + [
        rule("HNSAL-S2-R01-03", "UNSUPPORTED", "연금하나·주거래하나월복리적금과 중복가입 불가 — 상품 키 없음",
             "(※”연금하나월복리적금“ 또는“주거래 하나월복리적금”과중복가입이불가합니다.)"),
    ])

put("HNSAL-S2-R04",
    "rule 2개 · 전부 UNSUPPORTED. 01 「만기일시지급식(월복리식): 만기(후)해지 시 이자 지급」은 이자 지급 시기 — "
    "옮길 effect 가 없다(kb10 KBSME-S2-R06 관례). 02 「중도해지금리 및 만기후금리는 단리로 계산」은 이자 산출 방식 — "
    "판별 범위 밖. 둘 다 고객을 가르지 않아 빈 배열로 볼 여지가 있으나 코퍼스 관례를 따랐다.",
    [rule("HNSAL-S2-R04-01", "UNSUPPORTED", "만기일시지급식(월복리) — 이자 지급 시기 effect 없음 (판별 범위 밖)",
          "만기일시지급식(월복리식) : 만기(후) 해지시이자를지급"),
     rule("HNSAL-S2-R04-02", "UNSUPPORTED", "중도해지·만기후 금리는 단리 계산 — 이자 산출 방식 (판별 범위 밖)",
          "단, 중도해지금리및만기후금리는단리로 계산하여이자를지급함")])

put("HNSAL-S2-R06",
    "rule 3개 · OK 2 · UNSUPPORTED 1. 01 「1만원 이상」→ contract.amount < 10,000 이면 DISQUALIFY "
    "(kb10 KBSUP-S2-R04-01 「1백만원 이상」과 같은 꼴 · 경계: 1만원은 가입 가능). "
    "02 「300만원 이하」는 상한 — 지문의 「최대 N까지는 상한 · LIMIT_AMOUNT · 조건 없음」 대로 LIMIT_AMOUNT 3,000,000 (한도를 넘는다고 자격을 잃는 것이 아니다). "
    "03 「청년응원 특별금리 등록 시 150만원 이하」는 등록 여부 변수가 없다 — 나이(만35세 이하)로 바꾸면 등록하지 않은 고객의 한도를 "
    "낮추는 다른 개념이라 UNSUPPORTED. 자유적립식이라 「가입금액」이 초입금인지 매 입금 건인지 조문이 말하지 않는다 — "
    "contract.amount(가입금액)로 읽었다. Sonnet 판정이 표현불가였던 자리인데, 01·02 는 조문 그대로라 규칙이 맞다고 본다.",
    [rule("HNSAL-S2-R06-01", "OK", "가입금액 1만원 미만이면 가입 불가", "1만원 이상 300만원 이하 (원단위)",
          {"<": [V("contract.amount"), 10000]}, DISQ),
     rule("HNSAL-S2-R06-02", "OK", "가입금액 상한 300만원", "1만원 이상 300만원 이하 (원단위)",
          {}, {"type": "LIMIT_AMOUNT", "value": 3000000}),
     rule("HNSAL-S2-R06-03", "UNSUPPORTED", "청년응원 특별금리 등록 시 가입금액 상한 150만원 — 특별금리 등록 여부 변수 없음",
          "(단, 청년응원 특별금리등록시 1만원이상 150만원 이하)")])

put("HNSAL-S2-R07",
    "rule 2개 · 전부 UNSUPPORTED. 01 「분기당 1만원 이상 300만원 이하」는 분기 단위 입금 합계 한도 — LIMIT_AMOUNT 에 기간 단위가 없어 "
    "총액 한도로 읽히고(다른 개념), 입금 한 건에 걸리는 한도 검증은 실행기 범위 3(회차 · 건별 · 이체한도) 밖이다. "
    "02 「특별금리 적용기간은 분기당 150만원 이하」는 거기에 특별금리 등록 변수까지 없다.",
    [rule("HNSAL-S2-R07-01", "UNSUPPORTED", "분기당 적립한도 1만원 이상 300만원 이하 — 분기 단위 한도 effect 없음 (입금 검증은 범위 밖)",
          "분기당 1만원 이상 300만원 이하 (원단위)"),
     rule("HNSAL-S2-R07-02", "UNSUPPORTED", "특별금리 적용기간 분기당 150만원 이하 — 특별금리 등록 변수 · 분기 단위 한도 없음",
          "(단, 청년응원 특별금리적용기간은분기당 1만원이상 150만원 이하)")])

_Q_HNSAL_BASE = "가입기간 1년 2년 3년 기본금리 연 2.95% 연 3.00% 연 3.10%"
put("HNSAL-S2-R08",
    "rule 3개 · 전부 OK. 계약기간별 기본금리 표(1년 2.95 · 2년 3.00 · 3년 3.10)를 행마다 contract.term_months == 12/24/36 → RATE_OVERRIDE 로 옮겼다 "
    "(kb10 KBMER-S2-R07 과 같은 꼴 · 기간이 셋뿐이라 == 로 적었다). 표가 가로로 찍혀 행별 인용이 안 되므로 세 rule 이 같은 두 줄을 인용한다. "
    "「신규일 당시 … 고시한 계약기간별 기본금리 적용」은 출처 안내라 rule 이 아니다.",
    [rule(f"HNSAL-S2-R08-0{i+1}", "OK", f"계약기간 {y}년 기본금리 연 {v}%", _Q_HNSAL_BASE,
          {"==": [V("contract.term_months"), y * 12]}, override(v))
     for i, (y, v) in enumerate([(1, 2.95), (2, 3.0), (3, 3.1)])])

_WIN_SAL = WIN(A("contract.start_date", 0, "first"), A("contract.maturity_date", -2, "last"))


def half_term(event):
    """「계약기간의 1/2 이상」— 1·2·3년제라 기간마다 문턱을 갈라 적는다 (kb10 KBSME-S2-R08 꼴)."""
    return {"or": [{"and": [{"==": [V("contract.term_months"), t]},
                            {">=": [{"count_distinct_months": {"event": event, "within": {"ref": "$window"}}}, t // 2]}]}
                   for t in (12, 24, 36)]}


put("HNSAL-S2-R09",
    "rule 3개 · OK 2 · UNSUPPORTED 1. 머리말 「최대 연 1.00% … 만기해지시 추가 제공 · 중도해지 시 미적용」→ 합산 상한은 규칙이 아니고(결정 1-5), "
    "만기해지 한정은 guard termination_type == MATURITY. "
    "01 급여하나우대 0.90%: 창 = 가입월 1일 ~ 만기 전전월 말일, 「계약기간의 1/2 이상」은 1·2·3년제라 term_months 12/24/36 → 6/12/18개월로 갈라 "
    "count_distinct_months(SALARY_TRANSFER) 로 옮겼다(kb10 KBSME-S2-R08-01 꼴). 주1) 급여 인정기준 ①②는 «월 50만원 이상»(월 합계)이고 ③만 건당 50만원이라 "
    "셋 공통의 건별 하한이 없다 — where.min_amount 를 걸면 소액 여러 건으로 월 50만원을 채운 고객을 놓치므로(불리) 금액 조건을 뺐다. "
    "급여 적요·급여코드·급여일 지정 요건과 ※ 제외 항목도 못 담았다 — 전부 넓게 인정하는 우대 쪽 오차(원칙 1). "
    "02 온라인채널 가입 0.10%: 「스마트폰뱅킹/인터넷뱅킹」→ contract.channel in [MOBILE, INTERNET, ONLINE] (ONLINE 은 열거에 있는 비대면 값이라 넣었다 · 넓은 쪽). "
    "03 「만기재예치 우대(최초 계약기간 이후 재예치된 기간에 적용)」는 재예치 여부 변수가 없다(kb10 KBMY-S2-R16 과 같다) → UNSUPPORTED. "
    "예시 줄 · 주1) · ※ 줄은 인정기준 안내라 rule 이 아니다.",
    [rule("HNSAL-S2-R09-01", "OK", "급여 입금 개월수가 계약기간의 1/2 이상이면 우대금리 연 0.90%p (만기해지 계좌)",
          "급여하나우대 이예금만기전전월말기준, 계약기간의1/2 이상본인명의하나은행입출금통장을 (연0.90%) 통해급여입금실적(주1) 보유한경우(월1회이체)",
          half_term("SALARY_TRANSFER"), rate_add(0.9), let={"window": _WIN_SAL}, guard=MAT),
     rule("HNSAL-S2-R09-02", "OK", "온라인채널(스마트폰뱅킹·인터넷뱅킹) 가입 시 우대금리 연 0.10%p (만기해지 계좌)",
          "온라인채널가입 이예금을온라인채널(스마트폰뱅킹/인터넷뱅킹)을통해가입또는만기재예치하는",
          {"in": [V("contract.channel"), ["MOBILE", "INTERNET", "ONLINE"]]}, rate_add(0.1), guard=MAT),
     rule("HNSAL-S2-R09-03", "UNSUPPORTED", "만기재예치 우대 연 0.10% — 재예치 여부 변수 없음",
          "만기재예치우대는최초계약기간이후재예치된기간에대해적용")])

put("HNSAL-S2-R10",
    "rule 2개 · OK 1 · UNSUPPORTED 1. 01 청년응원 특별금리 1.30%p: 조건 넷을 and 로 묶었다 — "
    "(가) 「가입일기준 만35세 이하」→ customer.age <= 35 (판별 시점 나이로 근사 · 가입 뒤 생일이 지난 고객은 불리할 수 있으나 가입대상 조문들과 같은 관례), "
    "(나) 「1년제」→ term_months == 12, (다)(라) 「만기 전전월말 기준 6개월 이상」 급여 입금실적 · 하나카드 결제실적 → 창(가입월 1일 ~ 만기 전전월 말일) 안 "
    "count_distinct_months(SALARY_TRANSFER) >= 6 와 count_distinct_months(CARD_USAGE) >= 6 (「모두 충족」). 카드 「월 30만원 이상」은 월 합계라 "
    "where.min_amount(건별)로 담을 수 없어 뺐고, 하나카드 한정 · 하나머니 충전 제외 · 급여 인정기준(주1)도 못 담았다 — 전부 넓게 인정하는 우대 쪽 오차(원칙 1). "
    "「만기해지시」→ guard MATURITY(※ 중도해지 미적용도 여기서 받는다). "
    "02 ※ 「고객별 1회에 한해 · 재예치기간 미적용」은 특별금리 수령 이력 · 재예치 여부 변수가 없다 → UNSUPPORTED. "
    "가입금액 150만원 한도는 R06 소관이라 여기 없다.",
    [rule("HNSAL-S2-R10-01", "OK", "만35세 이하 · 1년제 · 6개월 이상 급여입금+하나카드 결제 → 특별금리 연 1.30%p (만기해지 계좌)",
          "[특별금리 (연1.30%) ※ 가입일기준 만35세이하만가능] 이 예금을 1년제로 가입하고, 아래 항목을 모두 충족하는 경우 만기해지시 추가 제공합니다",
          {"and": [{"<=": [V("customer.age"), 35]},
                   {"==": [V("contract.term_months"), 12]},
                   {">=": [{"count_distinct_months": {"event": "SALARY_TRANSFER", "within": {"ref": "$window"}}}, 6]},
                   {">=": [{"count_distinct_months": {"event": "CARD_USAGE", "within": {"ref": "$window"}}}, 6]}]},
          rate_add(1.3), let={"window": _WIN_SAL}, guard=MAT),
     rule("HNSAL-S2-R10-02", "UNSUPPORTED", "고객별 1회 한정 · 재예치기간 미적용 — 특별금리 수령 이력 · 재예치 여부 변수 없음",
          "※ 고객별1회에한해제공되는 특별금리로, 중도해지 및재예치기간은미적용.")])

put("HNSAL-S2-R11",
    "rule 2개 · 전부 UNSUPPORTED. 01 「금리우대쿠폰 발급 시 기본금리에 가산」은 규칙인데 쿠폰 적용 여부 · 쿠폰 금리 변수가 없고 값도 조문에 없다 "
    "(kb10 KBMY-S2-R08-10 · KBSUP-S2-R05-01 과 같다). 02 「신규 가입시에만 사용 · 재예치 또는 중도해지시 미적용」은 본체(쿠폰)가 표현 불가라 "
    "매개변수도 UNSUPPORTED(원칙 5 · KBMY-S2-R08-11 꼴). 「쿠폰함 또는 가입시 제공되는 쿠폰의 우대금리를 따릅니다」는 출처 안내다.",
    [rule("HNSAL-S2-R11-01", "UNSUPPORTED", "금리우대쿠폰 우대금리 가산 — 쿠폰 적용 여부·쿠폰 금리 변수 없음",
          "금리우대쿠폰을 발급받을 경우 기본금리에 가산하여 우대금리를 지급합니다."),
     rule("HNSAL-S2-R11-02", "UNSUPPORTED", "쿠폰은 신규 가입시에만 · 재예치·중도해지 시 미적용 — 본체(쿠폰)가 표현 불가",
          "단, 신규 가입시에 만 쿠폰 사용이 가능하며, 재예치 또는 중도해지시에는 적용되지 않습니다.")])

early_clause("HNSAL-S2-R12",
             "1개월미만 연0.10%",
             "1개월이상~ 3개월미만 연0.15%",
             "3개월이상~ 6개월미만 연0.20%",
             "가입(재예치)당시해당상품의기본금리x 차등율(주2)x 경과율(주3) 6개월이상 (단, 연0.20% 미만시연0.20% 적용)")

after_clause("HNSAL-S2-R13",
             "• 1개월 이내 : 지급당시 해당기간별 정기적금 기본금리 ½",
             "• 1개월 초과 : 지급당시 해당기간별 정기적금 기본금리 ¼")

calc_clause("HNSAL-S2-R14", "• 저축금마다입금일로부터 만기일 전일까지 기간에 대하여 약정금리를 월복리로 계산하여 지급")

# ═══════════════════════════════════════════════════════════════════════
# HNDRM (아이) 꿈하나적금
# ═══════════════════════════════════════════════════════════════════════
put("HNDRM-S2-R01",
    "rule 3개 · 전부 OK. 01 「만 18세 이하」→ customer.age > 18 이면 DISQUALIFY (경계: 만 18세는 가입 가능). "
    "02 「1인 1계좌」→ has_product 참이면 DISQUALIFY. 03 「실명의 개인」→ 확실히 밖인 법인만 탈락 — kb10 KBGL-S2-R01 (같은 문구) 관례. "
    "어린이 상품이라 개인사업자 · 임의단체도 사실상 밖이지만 조문이 말하지 않아 좁은 쪽을 택했다(원칙 1 · 결정 9).",
    eligibility_rules("HNDRM-S2-R01", "만 18세 이하 실명의 개인(1인 1계좌)",
                      extra_first=lambda rid: rule(rid, "OK", "만 18세 초과면 가입 불가", "만 18세 이하 실명의 개인(1인 1계좌)",
                                                   {">": [V("customer.age"), 18]}, DISQ)))

put("HNDRM-S2-R11",
    "rule 5개 · OK 2 · UNSUPPORTED 3. 머리말 「최대 연 0.80% 우대(재예치시에도 적용, 중도해지시 미적용)」→ 상한은 규칙이 아니고(결정 1-5), "
    "중도해지 미적용은 guard termination_type == MATURITY. "
    "① 가입우대 「최초 가입 · 해지 후 재가입 시 미제공」: 이 상품의 과거 가입 이력 변수가 없다(customer.is_first_deposit 은 은행 첫 거래라 다른 개념 · kb10 KBSSG-S2-R08-08 과 같다) → UNSUPPORTED. "
    "② 청약우대 「주택청약종합저축 보유」: 상품 키 목록에 없다(KBMY-S2-R08-08 과 같다) → UNSUPPORTED. "
    "③ 자동이체우대 0.20%: 「계약기간중 6회 이상 월 자동이체로 적립(월 1회만 인정)」→ 창(가입월 1일 ~ 만기일) 안 count_distinct_months(AUTO_TRANSFER) >= 6 — "
    "이벤트에 계좌 구분이 없어 하나은행 입출금통장에서 이 적금으로의 자동이체만 세지 못한다(고객 단위 이벤트 · 넓게 인정하는 우대 쪽 오차). "
    "④ 카드우대 0.20%: 「가입 후 3개월이 되는 달의 말일까지 체크카드 결제실적」→ 창(가입월 1일 ~ 가입월+3개월 말일) 안 exists CARD_USAGE — "
    "체크카드 · 하나(현대)카드 한정은 이벤트 속성이 없어 못 담았다(우대 쪽 오차). ③④ 의 「(또는 재예치후)」는 재예치 변수가 없어 가입일 기준만 적었다. "
    "⑤ 아동수당우대: 아동수당 수령 이벤트가 없다 — PENSION_RECEIPT(연금) · DEPOSIT(일반 입금)으로 바꾸면 다른 개념(원칙 2) → UNSUPPORTED 로 두고 ※ 보호자계좌 줄도 여기에 속한다.",
    [rule("HNDRM-S2-R11-01", "UNSUPPORTED", "가입우대 연 0.20% (최초 가입 · 재가입 제외) — 이 상품 과거 가입 이력 변수 없음",
          "① 가입우대 : 이 예금을 최초 가입한 경우 연 0.20% (해지후 재가입하는 경우 제공하지 않음)"),
     rule("HNDRM-S2-R11-02", "UNSUPPORTED", "청약우대 연 0.40% — 상품 키에 주택청약종합저축 없음",
          "② 청약우대 : 가입일(또는 재예치일)에 본인명의 주택청약종합저축을 보유한 경우 연 0.40%"),
     rule("HNDRM-S2-R11-03", "OK", "계약기간 중 6개월 이상 자동이체 적립 → 우대금리 연 0.20%p (만기해지 계좌)",
          "③ 자동이체우대 : 계약기간중 하나은행 입출금통장을 통하여 6 회 이상 월 자동이체로 적립한 경우 연 0.20%(월 1 회만 인정)",
          {">=": [{"count_distinct_months": {"event": "AUTO_TRANSFER", "within": {"ref": "$window"}}}, 6]},
          rate_add(0.2), let={"window": WIN(A("contract.start_date", 0, "first"), A("contract.maturity_date", 0))}, guard=MAT),
     rule("HNDRM-S2-R11-04", "OK", "가입 후 3개월째 달 말일까지 체크카드 결제실적 → 우대금리 연 0.20%p (만기해지 계좌)",
          "④ 카드우대 : 가입후(또는 재예치후) 3개월이 되는 달의 말일까지 하나은행 본인명의 입출금통장 에서 하나(현대)카드사의 체크카드 결제 실적 보유한 경우 연 0.20%",
          {"exists": {"event": "CARD_USAGE", "within": {"ref": "$window"}}},
          rate_add(0.2), let={"window": WIN(A("contract.start_date", 0, "first"), A("contract.start_date", 3, "last"))}, guard=MAT),
     rule("HNDRM-S2-R11-05", "UNSUPPORTED", "아동수당우대 연 0.20% — 아동수당 수령 이벤트 없음",
          "⑤ 아동수당우대 : 가입후(또는 재예치후) 만기 전전월말 기준, 하나은행 계좌로 아동수당법에서 정한 아동수당을 1 회 이상 수령한 경우 연 0.20%")])

put("HNDRM-S2-R12",
    "rule 4개 · OK 1 · UNSUPPORTED 3. 01 가항 「출생 후 1년 이내 · 만7세 · 만13세 · 만16세가 되는 계약기간 1년간 연 0.30%」→ "
    "customer.age in [0, 7, 13, 16] → RATE_ADD 0.3%p. «그 나이가 되는 계약기간»을 판별 시점 나이로 근사했다 — 계약기간 안에 생일이 오는데 "
    "판별일에는 아직 전 나이인 고객을 놓칠 수 있고(불리), 나이가 바뀐 뒤 판별하면 넓게 준다(유리). 양방향 근사라 가장 자신 없는 자리 — "
    "나이 조건이 조문 그대로이고 가입대상 조문들이 customer.age 를 같은 식으로 쓰므로 OK 로 뒀다. "
    "①의 「다항 해당 시 다항만 적용(가·나 중복 불가) · 가·나는 계약기간별 최대 0.30%」는 rule 들 위의 우선순위·상한이라 rule 이 아니다(결정 1-5). "
    "02 나항 「단체 신규 10인 이상」: 단체 가입 변수 없음. 03 다항 「만3세 이하 + 대리인이 (태아)사랑하나적금 보유(했던) 경우 1.00%」: "
    "상품 키 없음 · 대리인 보유 이력 변수 없음 (만3세 조건만 옮기면 다른 rule 이 된다). 04 ② 「희망대학입학축하금리 만기 전 1년간 2.00%」: "
    "희망대학 등록 · 입학 사건 변수 없음. 셋 다 UNSUPPORTED. 특별금리에 중도해지 미적용 문구가 없어 guard 를 두지 않았다.",
    [rule("HNDRM-S2-R12-01", "OK", "출생 후 1년 이내·만7세·만13세·만16세가 되는 계약기간 → 특별금리 연 0.30%p",
          "가. 이예금가입고객이출생후1 년이내, 만7 세, 만13 세, 만16 세가되는해당계약기간별1 년간 연0.30%",
          {"in": [V("customer.age"), [0, 7, 13, 16]]}, rate_add(0.3)),
     rule("HNDRM-S2-R12-02", "UNSUPPORTED", "단체 신규 10인 이상 가입 시 1년간 연 0.30% — 단체 가입 변수 없음",
          "나. 이예금가입고객이동일기관, 학교등단체신규10 인이상가입한경우, 가입후1 년간연0.30%"),
     rule("HNDRM-S2-R12-03", "UNSUPPORTED", "만3세 이하 + 대리인 (태아)사랑하나적금 보유 시 1년간 연 1.00% — 상품 키·대리인 보유 이력 변수 없음",
          "다. 예금주가만3세이하이고대리인이「(아이) 꿈하나적금」을신규하는시점에「(태아)사랑하나적금」을 보유하고있거나보유한적이있는경우, 가입후1 년간연1.00%(단, 최초1 회에한함)"),
     rule("HNDRM-S2-R12-04", "UNSUPPORTED", "희망대학 입학축하금리 만기 전 1년간 연 2.00% — 희망대학 등록·입학 변수 없음",
          "②희망대학입학축하금리: 만기전1 년간연2.00%(만14 세까지희망대학등록가능)")])

early_clause("HNDRM-S2-R13",
             "1개월미만 연0.10%",
             "1개월이상~ 3개월미만 연0.15%",
             "3개월이상~ 6개월미만 연0.20%",
             "가입(재예치)당시해당상품의기본금리x 차등율(주1)x 경과율(주2) 6개월이상 (단, 연0.20% 미만시연0.20% 적용)")

after_clause("HNDRM-S2-R14",
             "• 1개월이내: 지급당시해당기간별정기적금기본금리½",
             "• 1개월초과: 지급당시해당기간별정기적금기본금리¼")

calc_clause("HNDRM-S2-R15", "저축금마다입금일부터만기일전일까지기간에대하여약정금리로계산한이자를합계하여지급")

# ═══════════════════════════════════════════════════════════════════════
# HNWSH 나의 소원 적금
# ═══════════════════════════════════════════════════════════════════════
put("HNWSH-S2-R01",
    "rule 2개 · 전부 OK. 01 「1인 1계좌까지만 가능」→ has_product 참이면 DISQUALIFY. 02 「실명의 개인」→ 확실히 밖인 법인만 탈락 "
    "(kb10 KBGL-S2-R01 관례 · 개인사업자 · 임의단체 · 공동명의는 조문이 말하지 않아 넣지 않았다 — 원칙 1 · 결정 9).",
    eligibility_rules("HNWSH-S2-R01", "실명의 개인 (1인 1계좌까지만 가능)"))

_Q_WSH_BASE = "6개월이상 12개월이상 24개월이상 기간 36개월 ~12개월미만 ~24개월미만 ~36개월미만 금리(세전) 연0.65% 연0.75% 연0.85% 연0.95%"
_WSH_ROWS = [("6개월 이상 12개월 미만", 6, 12, 0.65), ("12개월 이상 24개월 미만", 12, 24, 0.75),
             ("24개월 이상 36개월 미만", 24, 36, 0.85), ("36개월", 36, None, 0.95)]
put("HNWSH-S2-R09",
    "rule 4개 · 전부 OK. 계약기간별 기본금리 표 네 열(6~12개월 0.65 · 12~24개월 0.75 · 24~36개월 0.85 · 36개월 0.95)을 열마다 "
    "contract.term_months 구간 → RATE_OVERRIDE 로 옮겼다(kb10 KBMER-S2-R07 과 같은 꼴 · 이상 >= · 미만 < · 36개월 ==). "
    "표가 가로로 찍혀 열별 인용이 안 되므로 네 rule 이 같은 표 블록을 인용한다. 「실제 예금 가입일에 … 고시한 금리 적용 (’21.03.25 현재, 세전)」은 출처 안내라 rule 이 아니다.",
    [rule(f"HNWSH-S2-R09-0{i+1}", "OK", f"계약기간 {name} 기본금리 연 {v}%", _Q_WSH_BASE,
          ({"==": [V("contract.term_months"), lo]} if hi is None else
           {"and": [{">=": [V("contract.term_months"), lo]}, {"<": [V("contract.term_months"), hi]}]}),
          override(v))
     for i, (name, lo, hi, v) in enumerate(_WSH_ROWS)])

put("HNWSH-S2-R10",
    "rule 6개 · 전부 UNSUPPORTED. ① 「신규 시 설정한 목표 불입금액을 만기해지 시 달성」: 목표 불입금액 변수가 없다(contract.amount 는 가입금액이라 다른 개념). "
    "② 「하나체크카드 사용에 따른 자동 적립 횟수 10/20/30/40회 이상 → 0.1/0.2/0.3/0.4%」: 소비재테크 자동적립 이벤트가 없다 — DEPOSIT 으로 세면 일반 입금까지 세는 "
    "다른 개념(원칙 2). 조건·효과가 넷이라 구간마다 rule 로 나눴다. ③ 「추천인 번호 입력 · 계좌별 최대 0.2%」: 추천인 변수 없음. "
    "머리말 「최대 연 0.4% · 만기해지 시에 한하여」는 상한(규칙 아님)과 guard 자리인데 본체가 전부 표현 불가라 조건을 비웠다. "
    "원 판정에서 나는 규칙으로 봤으나(①을 금액 비교로 옮길 수 있다고 봤다) 목표 불입금액은 카탈로그 변수가 아니므로 표현불가 판정이 맞다.",
    [rule("HNWSH-S2-R10-01", "UNSUPPORTED", "목표 불입금액 달성 우대 연 0.2% — 목표 불입금액 변수 없음",
          ": 신규 시 설정한 목표 불입금액을 만기해지 시 달성한 경우 (연 0.2%) 우대금리 제공"),
     rule("HNWSH-S2-R10-02", "UNSUPPORTED", "소비 재테크 자동 적립 10회 이상 연 0.1% — 체크카드 자동적립 이벤트 없음",
          "하나체크카드 사용에 따른 자동 적립 횟수가 10회 이상이면 (연 0.1%)"),
     rule("HNWSH-S2-R10-03", "UNSUPPORTED", "소비 재테크 자동 적립 20회 이상 연 0.2% — 체크카드 자동적립 이벤트 없음",
          "20회 이상이면 (연 0.2%)"),
     rule("HNWSH-S2-R10-04", "UNSUPPORTED", "소비 재테크 자동 적립 30회 이상 연 0.3% — 체크카드 자동적립 이벤트 없음",
          "30회 이상이면 (연 0.3%)"),
     rule("HNWSH-S2-R10-05", "UNSUPPORTED", "소비 재테크 자동 적립 40회 이상 연 0.4% — 체크카드 자동적립 이벤트 없음",
          "40회 이상이면 (연 0.4%) 우대금리 제공"),
     rule("HNWSH-S2-R10-06", "UNSUPPORTED", "추천인 우대 계좌별 연 0.1% (최대 0.2%) — 추천인 번호 입력 변수 없음",
          "나의 소원 적금 신규 시 제공되는 추천인 번호를 타인이 동 예금 신규 시 입력하는 경우, 추천인 번호를 제공하는 계좌 및 추천인 번호를 입력하여 신규한 계좌 각각에 (연 0.1%) 우대금리를 제공하며 계좌별 최대 (연 0.2%)까지 가능")])

early_clause("HNWSH-S2-R12",
             "1개월 미만 연 0.1%",
             "1개월 이상 ~ 3개월 미만 연 0.15%",
             "3개월 이상 ~ 6개월 미만 연 0.2%",
             "가입(재예치)당시 해당상품의 기본금리ⅹ차등률(주1)ⅹ경과율(주2) 6개월 이상 (단, 0.2% 미만 시 0.2% 적용)")

after_clause("HNWSH-S2-R13",
             "- 1개월 이내 : 지급 당시 해당기간별 상호부금 기본금리의1/2",
             "- 1개월 초과 : 지급 당시 해당기간별 상호부금 기본금리의 1/4")

calc_clause("HNWSH-S2-R14", "저축금 마다 입금일부터 만기일 전일까지의 기간에 대하여 약정금리로 이자 계산")

# ── 쓰기 ─────────────────────────────────────────────────────────────────
want = {k for k, v in VERDICT.items() if v != "없음"}
assert set(GOLD) == want, (want - set(GOLD), set(GOLD) - want)
for cid, g in GOLD.items():
    (OUT / f"{cid}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), "utf-8")
ok = sum(1 for g in GOLD.values() for r in g["rules"] if r["status"] == "OK")
un = sum(1 for g in GOLD.values() for r in g["rules"] if r["status"] == "UNSUPPORTED")
print(f"files {len(GOLD)} · OK {ok} · UNSUPPORTED {un}")
