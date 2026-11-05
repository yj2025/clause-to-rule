import json
import re
from pathlib import Path

ROOT = Path(r"C:\HuggingFace_demo\eval_v2")
OUT = ROOT / "judges" / "gold_opus"
OUT.mkdir(parents=True, exist_ok=True)
CL = {c["id"]: c for c in json.loads((ROOT / "clauses.json").read_text("utf-8"))}
TRI = {i["id"]: i for i in json.loads((ROOT / "gold" / "_triage.json").read_text("utf-8"))["items"]}


def _n(s):
    return re.sub(r"\s+", "", s)


def span(cid, start, end=None):
    """조문 원문에서 start 로 시작해 end 로 끝나는 부분을 그대로 떼어 온다."""
    t = CL[cid]["text"]
    i = t.index(start)
    if end is None:
        return t[i:i + len(start)]
    j = t.index(end, i) + len(end)
    return t[i:j]


def V(name):
    return {"var": name}


def A(anchor, **kw):
    d = {"anchor": anchor}
    d.update(kw)
    return d


MATURITY = {"==": [V("contract.termination_type"), "MATURITY"]}
DQ = {"type": "DISQUALIFY"}


def add(v):
    return {"type": "RATE_ADD", "value": v, "unit": "%p", "applies_to": "BASE_RATE"}


def ovr(v):
    return {"type": "RATE_OVERRIDE", "value": v, "unit": "%"}


def win(frm, to):
    return {"month_range": {"from": frm, "to": to}}


# 가입월 1일 ~ 만기 전전월 말일
WIN_TO_PREPRE = win(A("contract.start_date", offset_months=0, day="first"),
                    A("contract.maturity_date", offset_months=-2, day="last"))


def cdm(event, n, ref="$window"):
    return {">=": [{"count_distinct_months": {"event": event, "within": {"ref": ref}}}, n]}


def term_eq(n):
    return {"==": [V("contract.term_months"), n]}


def ok(rid, label, quote, condition, effect, let=None, guard=None):
    r = {"rule_id": rid, "status": "OK", "label": label, "source": {"quote": quote}}
    if let:
        r["let"] = let
    if guard:
        r["guard"] = guard
    r["condition"] = condition
    r["effect"] = effect
    return r


def un(rid, label, quote, condition=None):
    return {"rule_id": rid, "status": "UNSUPPORTED", "label": label,
            "source": {"quote": quote}, "condition": condition or {}}


G = {}

# ───────────────────────── HNSAL 급여하나 월복리 적금 ─────────────────────────
c = "HNSAL-S2-R01"
G[c] = ("rule 3개 · OK 2 · UNSUPPORTED 1. 01: 「(1인1계좌)」→ customer.has_product 참이면 DISQUALIFY (kb10 KBGL-S2-R01-01 과 같은 꼴). "
        "02: 「실명의개인또는개인사업자」→ 명의 유형으로 확실히 탈락하는 것은 법인(CORPORATION)뿐이라 그것만 DISQUALIFY. "
        "임의단체(ORGANIZATION)는 조문이 말하지 않고(관련서류 미제출 임의단체는 개인으로 취급되는 경우가 있다), 공동명의(JOINT)도 말하지 않아 넣지 않았다 — "
        "탈락을 넓히면 고객에게 불리한 오차라 kb10 결정(가장 좁은 탈락만 · KBGL/KBMY)을 따랐다. 덜 탈락시키는 쪽 근사. "
        "03: 「연금하나월복리적금 또는 주거래하나월복리적금과 중복가입 불가」는 다른 상품 보유 여부(customer.held_products)로 옮길 자리인데 "
        "두 상품이 상품 키 목록에 없다 → 탈락 쪽이라 근사 금지, UNSUPPORTED.", [
    ok(f"{c}-01", "이미 이 상품을 보유하면 가입 불가 (1인1계좌)", span(c, "실명의개인또는개인사업자(1인1계좌)"),
       {"==": [V("customer.has_product"), True]}, DQ),
    ok(f"{c}-02", "법인은 가입 불가 (실명의 개인 또는 개인사업자)", span(c, "실명의개인또는개인사업자(1인1계좌)"),
       {"in": [V("customer.holder_type"), ["CORPORATION"]]}, DQ),
    un(f"{c}-03", "연금하나월복리적금·주거래하나월복리적금과 중복가입 불가 — 두 상품의 상품 키가 없음",
       span(c, "(※", "중복가입이불가합니다.)")),
])

c = "HNSAL-S2-R04"
G[c] = ("rule 2개 · 전부 UNSUPPORTED. 01: 「만기일시지급식(월복리식) : 만기(후) 해지시 이자를 지급」은 이자 지급 시기다 — "
        "kb10 KBSME-S2-R06 관례대로 지급 시기를 담을 effect 가 없어 UNSUPPORTED. 02: 「중도해지금리 및 만기후금리는 단리로 계산」은 이자 산출 방식이라 "
        "판별 범위 밖 → UNSUPPORTED. 둘 다 조건은 {} (모든 고객에게 같은 사실이라 빈 배열로 볼 여지도 있으나 판정이 표현불가로 정해져 있다).", [
    un(f"{c}-01", "만기일시지급식(월복리) — 이자 지급 시기 effect 없음", span(c, "만기일시지급식(월복리식)", "해지시이자를지급")),
    un(f"{c}-02", "중도해지금리·만기후금리는 단리 계산 — 이자 산출은 판별 범위 밖", span(c, "단, 중도해지금리및만기후금리는단리로", "계산하여이자를지급함")),
])

c = "HNSAL-S2-R06"
G[c] = ("rule 3개 · OK 2 · UNSUPPORTED 1. 01: 「1만원 이상」→ contract.amount < 10,000 이면 DISQUALIFY (경계: 1만원은 가입 가능 · kb10 KBSUP-S2-R04-01 꼴). "
        "02: 「300만원 이하」→ 금액 상한이라 LIMIT_AMOUNT 3,000,000 · 조건 {} (상한을 넘는다고 자격을 잃는 것이 아니라 그 이상을 못 넣는 것 — 지문의 「한도와 금리」 원칙). "
        "03: 「청년응원 특별금리 등록 시 1만원 이상 150만원 이하」는 특별금리 «등록» 여부를 가리킬 변수가 없다 — 한도를 좁히는 불리한 쪽이라 근사 금지, UNSUPPORTED. "
        "근사·주의: 적금의 「가입금액」을 contract.amount(가입금액)로 읽었다 — 신규 시 입금액인지 매회 납입 한도인지 조문만으로는 갈리지 않는다(월 납입으로 읽으면 monthly_amount 자리). "
        "**판정 의견:** 02 를 DISQUALIFY(amount > 3,000,000)로 둘 여지도 있다 — 판정(규칙)과는 일치한다.", [
    ok(f"{c}-01", "가입금액 1만원 미만이면 가입 불가", span(c, "1만원 이상 300만원 이하 (원단위)"),
       {"<": [V("contract.amount"), 10000]}, DQ),
    ok(f"{c}-02", "가입금액 상한 300만원", span(c, "1만원 이상 300만원 이하 (원단위)"),
       {}, {"type": "LIMIT_AMOUNT", "value": 3000000}),
    un(f"{c}-03", "청년응원 특별금리 등록 시 가입금액 1만원~150만원 — 특별금리 등록 여부 변수 없음",
       span(c, "(단, 청년응원 특별금리등록시 1만원이상 150만원 이하)")),
])

c = "HNSAL-S2-R07"
G[c] = ("rule 2개 · 전부 UNSUPPORTED. 01: 「분기당 1만원 이상 300만원 이하」는 분기마다의 적립 합계에 걸리는 거래 제약(건별·기간별 입금 검증)이다 — "
        "입금을 막거나 거르는 effect 가 없다(LIMIT_AMOUNT 는 분기 단위를 못 담아 총액 한도로 읽힌다) → UNSUPPORTED. "
        "02: 「청년응원 특별금리 적용기간은 분기당 1만원 이상 150만원 이하」— 같은 이유에 특별금리 적용기간 여부 변수도 없다 → UNSUPPORTED. 조건은 {}.", [
    un(f"{c}-01", "분기당 적립한도 1만원~300만원 — 분기 단위 입금 한도 effect 없음", span(c, "분기당 1만원 이상 300만원 이하 (원단위)")),
    un(f"{c}-02", "청년응원 특별금리 적용기간 분기당 1만원~150만원 — 특별금리 적용기간 변수·분기 한도 effect 없음",
       span(c, "(단, 청년응원 특별금리적용기간은분기당 1만원이상 150만원 이하)")),
])

c = "HNSAL-S2-R08"
q = span(c, "가입기간 1년 2년 3년", "연 3.10%")
G[c] = ("rule 3개 · 전부 OK. 계약기간별 기본금리 표(1년 2.95 · 2년 3.00 · 3년 3.10)를 행마다 RATE_OVERRIDE 로 옮겼다 (kb10 KBMER-S2-R07 꼴). "
        "표가 가로로 놓여 있어 세 rule 이 같은 표 줄을 인용한다. 계약기간이 1·2·3년뿐이라 term_months == 12/24/36 으로 적었다. "
        "「신규일 당시 영업점 및 은행 홈페이지에 고시한 … 적용」은 출처 안내라 rule 이 아니다. 재예치 시의 기본금리(재예치일 고시 금리)는 조문이 말하지 않는다.", [
    ok(f"{c}-01", "가입기간 1년 기본금리 연 2.95%", q, term_eq(12), ovr(2.95)),
    ok(f"{c}-02", "가입기간 2년 기본금리 연 3.00%", q, term_eq(24), ovr(3.0)),
    ok(f"{c}-03", "가입기간 3년 기본금리 연 3.10%", q, term_eq(36), ovr(3.1)),
])

c = "HNSAL-S2-R09"
G[c] = ("rule 3개 · OK 2 · UNSUPPORTED 1. 머리 「만기해지시 추가 제공 · 중도해지 시 미적용」→ OK rule 마다 guard termination_type == MATURITY. "
        "01 급여하나우대 연 0.90%p: 「만기 전전월말 기준, 계약기간의 1/2 이상 … 급여입금실적 보유 (월1회)」→ 창 = 가입월 1일 ~ 만기 전전월 말일, "
        "count_distinct_months(SALARY_TRANSFER) 가 계약기간의 1/2 이상 — 계약기간이 1·2·3년이라 12→6 · 24→12 · 36→18 로 갈라 or 로 묶었다(kb10 KBSME-S2-R08 꼴). "
        "근사(모두 더 인정하는 쪽 · 원칙 1): 주1) 인정기준(① 적요 · ② 급여코드 입금이 «월» 합계 50만원 이상 · ③ 급여일 전후 건당 50만원)은 월 합계라 where.min_amount(건별)로 못 담아 금액 조건을 뺐다 — "
        "건별 50만원으로 적으면 월 합계 50만원인 고객을 놓쳐 불리하다. 본인거래·비급여성·자동화기기 입금 제외, 직장명/급여일 등록 이후 건부터 적용, «본인명의 하나은행 입출금통장» 계좌 구분도 못 담았다(이벤트는 고객 단위). "
        "「매 계약기간별 · 재예치후」는 contract.start_date 를 현재 계약기간의 시작으로 본다. "
        "02 온라인채널가입 연 0.10%p: contract.channel 이 MOBILE·INTERNET·ONLINE 이면 (스마트폰뱅킹/인터넷뱅킹). "
        "03 만기재예치 우대(같은 0.10% 칸의 다른 갈래 · 최초 계약기간 이후 재예치된 기간에만): 재예치 여부·회차 변수가 없다 → UNSUPPORTED. "
        "「최대 연 1.00%」는 합산 상한(0.90+0.10)이라 규칙이 아니다(kb10 결정 1-5). 예시) 줄은 설명이다.", [
    ok(f"{c}-01", "계약기간 1/2 이상 급여입금 실적 → 우대금리 연 0.90%p (만기해지)",
       span(c, "급여하나우대 이예금만기전전월말기준", "보유한경우(월1회이체)"),
       {"or": [{"and": [term_eq(12), cdm("SALARY_TRANSFER", 6)]},
               {"and": [term_eq(24), cdm("SALARY_TRANSFER", 12)]},
               {"and": [term_eq(36), cdm("SALARY_TRANSFER", 18)]}]},
       add(0.9), let={"window": WIN_TO_PREPRE}, guard=MATURITY),
    ok(f"{c}-02", "온라인채널(스마트폰뱅킹/인터넷뱅킹) 가입 → 우대금리 연 0.10%p (만기해지)",
       span(c, "온라인채널가입 이예금을온라인채널(스마트폰뱅킹/인터넷뱅킹)을통해가입"),
       {"in": [V("contract.channel"), ["MOBILE", "INTERNET", "ONLINE"]]}, add(0.1), guard=MATURITY),
    un(f"{c}-03", "만기재예치 우대 연 0.10% (최초 계약기간 이후 재예치 기간) — 재예치 여부 변수 없음",
       span(c, "또는만기재예치하는", "재예치된기간에대해적용)")),
])

c = "HNSAL-S2-R10"
G[c] = ("rule 2개 · OK 1 · UNSUPPORTED 1. 01 청년응원 특별금리 연 1.30%p: 네 조건을 and 로 — (a) 「가입일기준 만35세이하」→ customer.age <= 35, "
        "(b) 「1년제로 가입」→ term_months == 12, (c) 「만기 전전월말 기준 6개월 이상 … 급여 입금실적 (월 1회 인정)」→ 창(가입월 1일 ~ 만기 전전월 말일)에서 count_distinct_months(SALARY_TRANSFER) >= 6, "
        "(d) 「하나카드 결제실적 월 30만원 이상」(6개월 이상이 ①② 둘에 걸린다고 읽었다) → count_distinct_months(CARD_USAGE) >= 6. guard: 「만기해지시 추가 제공 · 중도해지 미적용」→ MATURITY. "
        "근사: (a) customer.age 는 판별 기준일의 나이라 가입일 나이와 다르다 — 가입 때 35세였다가 기준일에 36세가 된 고객을 놓친다(경계에서 불리한 쪽 · 가입일 나이 변수가 없다. 나이 조건을 빼면 36세 이상 전원에게 주게 되어 오차가 훨씬 크다). "
        "(c) 주1) 인정기준의 금액 · 제외 항목은 못 담았다(더 인정 · 원칙 1). (d) «월 30만원 이상»은 월 합계라 월별 합계를 세는 수단이 없어 금액 조건을 빼고 카드 결제가 있는 달만 셌다 — 더 인정하는 쪽. 하나머니 충전방식 제외 · 하나카드 한정도 못 담았다(같은 방향). "
        "02: 「고객별 1회에 한해 제공 · 재예치기간 미적용」은 과거 수령 이력 · 재예치 여부 변수가 없다 → 우대를 막는 쪽이라 근사 금지, UNSUPPORTED.", [
    ok(f"{c}-01", "만 35세 이하 · 1년제 · 6개월 이상 급여입금 및 하나카드 결제 → 특별금리 연 1.30%p (만기해지)",
       span(c, "특별금리 (연1.30%) ※ 가입일기준 만35세이하만가능]", "만기해지시 추가 제공합니다"),
       {"and": [{"<=": [V("customer.age"), 35]}, term_eq(12),
                cdm("SALARY_TRANSFER", 6), cdm("CARD_USAGE", 6)]},
       add(1.3), let={"window": WIN_TO_PREPRE}, guard=MATURITY),
    un(f"{c}-02", "고객별 1회 한정 · 재예치기간 미적용 — 특별금리 수령 이력·재예치 여부 변수 없음",
       span(c, "※ 고객별1회에한해제공되는 특별금리로, 중도해지 및재예치기간은미적용.")),
])

c = "HNSAL-S2-R11"
G[c] = ("rule 2개 · 전부 UNSUPPORTED. kb10 KBSTR-S2-R08 · KBMY-S2-R08-10/11 과 같은 꼴. 01: 금리우대쿠폰을 발급받으면 쿠폰 우대금리를 가산 — 쿠폰 발급·적용 여부도 쿠폰 금리 값도 없다. "
        "02: 「신규 가입시에만 쿠폰 사용 · 재예치 또는 중도해지시 미적용」— 중도해지 조건은 표현되지만 본체(쿠폰 우대금리)가 표현 불가라 같이 UNSUPPORTED. "
        "「금리우대쿠폰의 금리는 … 쿠폰의 우대금리를 따릅니다」는 출처 안내라 rule 이 아니다.", [
    un(f"{c}-01", "금리우대쿠폰 우대금리 가산 — 쿠폰 발급 여부·쿠폰 금리 변수 없음",
       span(c, "금리우대쿠폰을 발급받을 경우 기본금리에 가산하여 우대금리를 지급합니다.")),
    un(f"{c}-02", "쿠폰은 신규 가입시에만 · 재예치·중도해지 시 미적용 — 본체(쿠폰)가 표현 불가",
       span(c, "단, 신규 가입시에", "적용되지 않습니다.")),
])


def early_rules(c, row1, row2, row3, row6, extra_note):
    note = ("rule 4개 · OK 1 · UNSUPPORTED 3. 적립식이라 중도해지금리는 «입금금액마다» 그 입금일부터 해지일 전일까지의 예치기간으로 정해진다. "
            "01 「1개월미만 | 연0.10%」: 중도해지(termination_type EARLY)이고 해지일 < 가입일 + 1개월이면 RATE_OVERRIDE 0.1 — 계좌가 1개월이 안 됐으면 모든 입금 건이 1개월 미만이라 "
            "입금 건별로 읽어도 정확하다(kb10 KBMY-S2-R11-01 · KBSME-S2-R12-01 과 같은 판단). "
            "02 「1개월이상~3개월미만 연0.15%」· 03 「3개월이상~6개월미만 연0.20%」: 값은 수지만 구간이 입금 건마다 달라(같은 해지일에 오래된 입금은 0.15·0.20, 최근 입금은 0.10) "
            "계좌 단위 날짜 조건으로 세우면 다른 입금 건의 이율까지 덮는다 → UNSUPPORTED, 조건 {} (kb10 KBMY-S2-R11 의 적금 관례). "
            "04 「6개월이상 | 기본금리 × 차등율(60·70·90%) × 경과율(경과일수/계약일수), 최저 연0.20%」: 비율식이라 수가 아니다 → UNSUPPORTED. 표의 행이 하나라 rule 하나로 두고 차등율 세 구간은 같은 rule 의 매개변수로 봤다. "
            "차등율·경과율 정의, 소수점 절사, (예시), 아래 도해 문자열은 산출 세부라 rule 이 아니다." + extra_note)
    return note, [
        ok(f"{c}-01", "예치 1개월 미만 중도해지 → 중도해지금리 연 0.10%", row1,
           {"and": [{"==": [V("contract.termination_type"), "EARLY"]},
                    {"<": [V("contract.termination_date"), A("contract.start_date", offset_months=1)]}]},
           ovr(0.1)),
        un(f"{c}-02", "예치 1개월 이상~3개월 미만 연 0.15% — 적립식이라 입금 건별 예치기간 필요", row2),
        un(f"{c}-03", "예치 3개월 이상~6개월 미만 연 0.20% — 적립식이라 입금 건별 예치기간 필요", row3),
        un(f"{c}-04", "예치 6개월 이상 — 기본금리 × 차등율 × 경과율 (최저 연 0.20%) · 비율식 없음", row6),
    ]


c = "HNSAL-S2-R12"
G[c] = early_rules(c, span(c, "1개월미만 연0.10%"), span(c, "1개월이상~ 3개월미만 연0.15%"),
                   span(c, "3개월이상~ 6개월미만 연0.20%"),
                   span(c, "가입(재예치)당시해당상품의기본금리x 차등율(주2)x 경과율(주3)", "(단, 연0.20% 미만시연0.20% 적용)"), "")

c = "HNDRM-S2-R13"
G[c] = early_rules(c, span(c, "1개월미만 연0.10%"), span(c, "1개월이상~ 3개월미만 연0.15%"),
                   span(c, "3개월이상~ 6개월미만 연0.20%"),
                   span(c, "가입(재예치)당시해당상품의기본금리x 차등율(주1)x 경과율(주2)", "(단, 연0.20% 미만시연0.20% 적용)"), "")

c = "HNWSH-S2-R12"
G[c] = early_rules(c, span(c, "1개월 미만 연 0.1%"), span(c, "1개월 이상 ~ 3개월 미만 연 0.15%"),
                   span(c, "3개월 이상 ~ 6개월 미만 연 0.2%"),
                   span(c, "가입(재예치)당시 해당상품의 기본금리ⅹ차등률(주1)ⅹ경과율(주2)", "(단, 0.2% 미만 시 0.2% 적용)"), "")


def after_rules(c, q1, q2, kind):
    note = (f"rule 2개 · 전부 UNSUPPORTED. 만기후 금리 두 구간 — 값이 「지급당시 해당기간별 {kind} 기본금리의 ½ · ¼」라 수가 아니고(다른 상품의 기본금리에 대한 비율식) "
            "만기 이후 기간에만 붙는 이율을 담을 자리도 없다(RATE_OVERRIDE 는 계좌 이율 전체를 덮는다) → UNSUPPORTED. "
            "kb10 KBSTR-S2-R13 · KBSME-S2-R12-08/09 관례대로 구간 조건은 계좌 단위 날짜 비교로 온전히 서므로 남겼다: "
            "01 만기일 < 해지일 <= 만기일 + 1개월, 02 해지일 > 만기일 + 1개월. 「지급당시」를 지급청구일(payout_request_date)로 볼 여지가 있으나 kb10 관례대로 해지일로 적었다. 아래 도해 문자열은 같은 표의 반복이다.")
    return note, [
        un(f"{c}-01", f"만기후 1개월 이내 — {kind} 기본금리 ½ (비율식 없음)", q1,
           {"and": [{">": [V("contract.termination_date"), V("contract.maturity_date")]},
                    {"<=": [V("contract.termination_date"), A("contract.maturity_date", offset_months=1)]}]}),
        un(f"{c}-02", f"만기후 1개월 초과 — {kind} 기본금리 ¼ (비율식 없음)", q2,
           {">": [V("contract.termination_date"), A("contract.maturity_date", offset_months=1)]}),
    ]


c = "HNSAL-S2-R13"
G[c] = after_rules(c, span(c, "• 1개월 이내 : 지급당시 해당기간별 정기적금 기본금리 ½"),
                   span(c, "• 1개월 초과 : 지급당시 해당기간별 정기적금 기본금리 ¼"), "정기적금")
c = "HNDRM-S2-R14"
G[c] = after_rules(c, span(c, "• 1개월이내: 지급당시해당기간별정기적금기본금리½"),
                   span(c, "• 1개월초과: 지급당시해당기간별정기적금기본금리¼"), "정기적금")
c = "HNWSH-S2-R13"
G[c] = after_rules(c, span(c, "- 1개월 이내 : 지급 당시 해당기간별 상호부금 기본금리의1/2"),
                   span(c, "- 1개월 초과 : 지급 당시 해당기간별 상호부금 기본금리의 1/4"), "상호부금")


def interest_rule(c, q, kind):
    note = (f"rule 1개 · UNSUPPORTED. 「저축금마다 입금일부터 만기일 전일까지 약정금리로{kind} 계산」은 이자 금액 산출이라 판별 범위 밖이다 — "
            "kb10 KBSME-S2-R10 · KBMY-S2-R10 관례대로 UNSUPPORTED 하나로 둔다. 회차별 계산식 줄은 같은 내용의 도해다.")
    return note, [un(f"{c}-01", "만기이자 계산방법 — 이자 산출은 판별 범위 밖", q)]


c = "HNSAL-S2-R14"
G[c] = interest_rule(c, span(c, "• 저축금마다입금일로부터 만기일 전일까지 기간에 대하여 약정금리를 월복리로 계산하여 지급"), " 월복리로")
c = "HNDRM-S2-R15"
G[c] = interest_rule(c, span(c, "저축금마다입금일부터만기일전일까지기간에대하여약정금리로계산한이자를합계하여지급"), "")
c = "HNWSH-S2-R14"
G[c] = interest_rule(c, span(c, "저축금 마다 입금일부터 만기일 전일까지의 기간에 대하여 약정금리로 이자 계산"), "")

# ───────────────────────── HNDRM (아이) 꿈하나 적금 ─────────────────────────
c = "HNDRM-S2-R01"
q = span(c, "만 18세 이하 실명의 개인(1인 1계좌)")
G[c] = ("rule 3개 · 전부 OK. 01: 「만 18세 이하」→ customer.age > 18 이면 DISQUALIFY (경계: 만 18세는 가입 가능). 가입 판정이라 기준일 = 가입 시점으로 본다. "
        "02: 「1인 1계좌」→ has_product 참이면 DISQUALIFY. 03: 「실명의 개인」에서 확실한 탈락은 법인(CORPORATION)뿐이라 그것만 DISQUALIFY "
        "(kb10 KBGL-S2-R01 의 가장 좁은 탈락 결정. 개인사업자·임의단체·공동명의는 조문이 말하지 않는다 — 덜 탈락시키는 쪽).", [
    ok(f"{c}-01", "만 18세 초과면 가입 불가", q, {">": [V("customer.age"), 18]}, DQ),
    ok(f"{c}-02", "이미 이 상품을 보유하면 가입 불가 (1인 1계좌)", q, {"==": [V("customer.has_product"), True]}, DQ),
    ok(f"{c}-03", "법인은 가입 불가 (실명의 개인)", q, {"in": [V("customer.holder_type"), ["CORPORATION"]]}, DQ),
])

c = "HNDRM-S2-R11"
G[c] = ("rule 5개 · OK 2 · UNSUPPORTED 3. 머리 「매 계약기간별 · 재예치시에도 적용 · 단 중도해지시 미적용」→ OK rule 에 guard termination_type == MATURITY "
        "(kb10 관례 · 「매 계약기간별」은 contract.start_date 를 현재 계약기간의 시작으로 본다). "
        "01 ① 가입우대 연 0.20%(최초 가입 · 해지후 재가입 제외): 이 상품의 과거 가입 이력 변수가 없다 — customer.is_first_deposit(첫 거래)는 은행 첫 거래라 다른 개념이다. "
        "유일한 조건이 안 서므로 UNSUPPORTED (kb10 KBSSG-S2-R08-07 과 같은 자리). "
        "02 ② 청약우대 연 0.40%: 가입일에 주택청약종합저축 보유 — 상품 키가 없다(kb10 KBMY-S2-R08-08) → UNSUPPORTED. "
        "03 ③ 자동이체우대 연 0.20%: 계약기간(가입일 ~ 만기일) 중 자동이체가 있는 달이 6개월 이상 (월 1회만 인정 → count_distinct_months(AUTO_TRANSFER) >= 6). "
        "근사: 「하나은행 입출금통장을 통하여 이 적금에 자동이체로 적립」을 담지 못해 고객의 모든 자동이체(공과금 등)를 센다 — 더 인정하는 쪽(원칙 1). "
        "04 ④ 카드우대 연 0.20%: 가입일 ~ 가입 후 3개월이 되는 달의 말일 사이에 카드 결제실적이 있으면 (exists CARD_USAGE). "
        "근사: 「하나(현대)카드 체크카드 · 본인명의 하나은행 입출금통장 결제」로 좁히지 못했다 — 더 인정하는 쪽. "
        "05 ⑤ 아동수당우대 연 0.20%: 아동수당 수령 이벤트가 없다(PENSION_RECEIPT 는 연금, DEPOSIT 은 다른 개념) → UNSUPPORTED. "
        "※ 보호자계좌 수령 시 수급계좌 제공 요건은 ⑤ 의 매개변수라 05 에 함께 둔다. 「최대 연 0.80%」는 합산 상한이라 규칙이 아니다.", [
    un(f"{c}-01", "가입우대 연 0.20% (최초 가입 · 해지후 재가입 제외) — 이 상품 과거 가입 이력 변수 없음",
       span(c, "① 가입우대 : 이 예금을 최초 가입한 경우 연 0.20% (해지후 재가입하는 경우 제공하지 않음)")),
    un(f"{c}-02", "청약우대 연 0.40% — 주택청약종합저축 상품 키 없음",
       span(c, "② 청약우대 : 가입일(또는 재예치일)에 본인명의 주택청약종합저축을 보유한 경우 연 0.40%")),
    ok(f"{c}-03", "계약기간 중 6개월 이상 자동이체 적립 → 우대금리 연 0.20%p (만기해지)",
       span(c, "③ 자동이체우대 : 계약기간중", "연 0.20%(월 1 회만 인정)"),
       cdm("AUTO_TRANSFER", 6), add(0.2),
       let={"window": win(A("contract.start_date"), A("contract.maturity_date"))}, guard=MATURITY),
    ok(f"{c}-04", "가입 후 3개월이 되는 달 말일까지 체크카드 결제실적 → 우대금리 연 0.20%p (만기해지)",
       span(c, "④ 카드우대 : 가입후(또는 재예치후) 3개월이 되는 달의 말일까지", "결제 실적 보유한 경우 연 0.20%"),
       {"exists": {"event": "CARD_USAGE", "within": {"ref": "$window"}}}, add(0.2),
       let={"window": win(A("contract.start_date"), A("contract.start_date", offset_months=3, day="last"))},
       guard=MATURITY),
    un(f"{c}-05", "아동수당우대 연 0.20% (보호자계좌 수령 시 수급계좌 제공 요건 포함) — 아동수당 수령 이벤트 없음",
       span(c, "⑤ 아동수당우대 : 가입후(또는 재예치후) 만기 전전월말 기준", "1 회 이상 수령한 경우 연 0.20%")),
])

c = "HNDRM-S2-R12"
G[c] = ("rule 5개 · OK 1 · UNSUPPORTED 4. 01 가항 연 0.30%p: 「가입고객이 출생후 1년이내, 만7세, 만13세, 만16세가 되는 해당 계약기간별 1년간」→ customer.age 가 0·7·13·16 이면 RATE_ADD 0.3. "
        "근사(양방향 · 가장 불확실): 조문은 «그 나이가 되는 계약기간 1년»인데 customer.age 는 판별 기준일의 만 나이다 — 그 계약기간 중 생일 전 구간(아직 6·12·15세)은 놓치고(불리), "
        "생일이 지난 뒤 다음 계약기간에 걸친 구간은 더 준다(유리). 가입일 나이·계약기간별 나이 변수가 없어 이것이 표현 가능한 가장 가까운 꼴이다. "
        "「다항에 해당하면 다항만 적용」으로 가항이 빠지는 경우도 못 담았다(더 주는 쪽). "
        "02 나항(동일 기관·학교 등 단체 신규 10인 이상 · 가입후 1년 0.30%): 단체 신규 변수 없음 → UNSUPPORTED. "
        "03 다항(만 3세 이하 · 대리인 신규 시점에 (태아)사랑하나적금 보유 또는 보유 이력 · 가입후 1년 1.00% · 최초 1회): 상품 키·보유 이력·최초 1회 변수 없음 → UNSUPPORTED (나이 조건만 남기면 유일 조건이 아니라 다른 rule 이 된다). "
        "04 중복 규칙(다항 해당 시 다항만 · 가·나 중복 불가): rule 사이의 배타 조건 — 나·다가 표현 불가라 담을 수 없다 → UNSUPPORTED. 「가·나항 동일 계약기간 최대 연0.30%」는 합산 상한이라 규칙이 아니다. "
        "05 ② 희망대학입학축하금리(만기전 1년간 연 2.00% · 만14세까지 희망대학 등록): 희망대학 등록 여부 변수 없음 → UNSUPPORTED. "
        "중도해지 미적용은 이 조문에 없어 guard 를 걸지 않았다.", [
    ok(f"{c}-01", "출생후 1년이내·만7세·만13세·만16세가 되는 계약기간 → 특별금리 연 0.30%p",
       span(c, "가. 이예금가입고객이출생후1 년이내", "연0.30%"),
       {"in": [V("customer.age"), [0, 7, 13, 16]]}, add(0.3)),
    un(f"{c}-02", "나항 단체 신규 10인 이상 가입 시 가입후 1년간 연 0.30% — 단체 신규 변수 없음",
       span(c, "나. 이예금가입고객이동일기관", "(단체신규는동일영업점에서확인하고신규하는경우제공)")),
    un(f"{c}-03", "다항 만3세 이하 · (태아)사랑하나적금 보유(이력) 시 가입후 1년간 연 1.00% (최초 1회) — 상품 키·보유 이력 변수 없음",
       span(c, "다. 예금주가만3세이하이고", "(단, 최초1 회에한함)")),
    un(f"{c}-04", "중복 적용 규칙 (다항 해당 시 다항만 · 가·나 중복 불가) — rule 사이 배타 조건을 담을 수단 없음",
       span(c, "단, 다항에해당할경우다항의특별금리만(연1.00%) 적용되며", "(가항, 나항중복적용불가)")),
    un(f"{c}-05", "희망대학입학축하금리 만기전 1년간 연 2.00% (만14세까지 등록) — 희망대학 등록 변수 없음",
       span(c, "②희망대학입학축하금리: 만기전1 년간연2.00%(만14 세까지희망대학등록가능)")),
])

# ───────────────────────── HNWSH 나의 소원 적금 ─────────────────────────
c = "HNWSH-S2-R01"
q = span(c, "실명의 개인 (1인 1계좌까지만 가능)")
G[c] = ("rule 2개 · 전부 OK. 01: 「1인 1계좌까지만 가능」→ has_product 참이면 DISQUALIFY. 02: 「실명의 개인」에서 확실한 탈락은 법인뿐이라 CORPORATION 만 DISQUALIFY "
        "(kb10 KBGL-S2-R01 결정 — 개인사업자·임의단체·공동명의는 조문이 말하지 않아 넣지 않았다 · 덜 탈락시키는 쪽).", [
    ok(f"{c}-01", "이미 이 상품을 보유하면 가입 불가 (1인 1계좌)", q, {"==": [V("customer.has_product"), True]}, DQ),
    ok(f"{c}-02", "법인은 가입 불가 (실명의 개인)", q, {"in": [V("customer.holder_type"), ["CORPORATION"]]}, DQ),
])

c = "HNWSH-S2-R09"
q = span(c, "6개월이상 12개월이상 24개월이상", "연0.95%")
G[c] = ("rule 4개 · 전부 OK. 계약기간별 기본금리 표(6~12개월 미만 0.65 · 12~24 미만 0.75 · 24~36 미만 0.85 · 36개월 0.95)를 행마다 RATE_OVERRIDE 로 옮겼다 "
        "(경계: 이상 >=, 미만 <, 「36개월」은 == 36 · kb10 KBMER-S2-R07 꼴). 표가 가로로 깨져 있어 네 rule 이 같은 표 문자열을 인용한다. "
        "「실제 예금 가입일에 … 고시한 금리 적용 (’21.03.25 현재, 세전)」은 출처 안내라 rule 이 아니다.", [
    ok(f"{c}-01", "계약기간 6개월 이상 12개월 미만 기본금리 연 0.65%", q,
       {"and": [{">=": [V("contract.term_months"), 6]}, {"<": [V("contract.term_months"), 12]}]}, ovr(0.65)),
    ok(f"{c}-02", "계약기간 12개월 이상 24개월 미만 기본금리 연 0.75%", q,
       {"and": [{">=": [V("contract.term_months"), 12]}, {"<": [V("contract.term_months"), 24]}]}, ovr(0.75)),
    ok(f"{c}-03", "계약기간 24개월 이상 36개월 미만 기본금리 연 0.85%", q,
       {"and": [{">=": [V("contract.term_months"), 24]}, {"<": [V("contract.term_months"), 36]}]}, ovr(0.85)),
    ok(f"{c}-04", "계약기간 36개월 기본금리 연 0.95%", q, term_eq(36), ovr(0.95)),
])

c = "HNWSH-S2-R10"
G[c] = ("rule 6개 · 전부 UNSUPPORTED. 01 ① 목표 불입금액 달성 우대 0.2%: 신규 시 설정한 목표 불입금액 변수가 없다. "
        "02~05 ② 소비 재테크 자동 적립 우대 10·20·30·40회 → 0.1·0.2·0.3·0.4%: 「하나체크카드 사용에 따른 자동 적립 횟수」는 소비재테크 서비스가 만든 이 적금으로의 적립 건수라 "
        "카드 결제 횟수(CARD_USAGE)와 다른 개념이다(설정한 금액만큼 적립 · 미설정 결제는 안 센다) → 각 구간 UNSUPPORTED. 구간이 서로 다른 효과라 행마다 나눴다. "
        "06 ③ 추천인 우대(건당 0.1% · 계좌별 최대 0.2%): 추천인 번호 입력 변수가 없다. "
        "머리 「만기해지 시에 한하여」는 본체가 표현 불가라 따로 두지 않았고, 「최대 연 0.4%」는 합산 상한이라 규칙이 아니다. "
        "판정(표현불가)에 동의한다 — ② 를 CARD_USAGE 횟수로 옮기면 다른 개념을 세는 것이 된다.", [
    un(f"{c}-01", "목표 불입금액 달성 우대 연 0.2% — 목표 불입금액 변수 없음",
       span(c, ": 신규 시 설정한 목표 불입금액을 만기해지 시 달성한 경우 (연 0.2%) 우대금리 제공")),
    un(f"{c}-02", "소비 재테크 자동 적립 10회 이상 연 0.1% — 자동 적립 횟수 이벤트 없음",
       span(c, ": 하나체크카드 사용에 따른 자동 적립 횟수가 10회 이상이면 (연 0.1%)")),
    un(f"{c}-03", "소비 재테크 자동 적립 20회 이상 연 0.2% — 자동 적립 횟수 이벤트 없음", span(c, "20회 이상이면 (연 0.2%)")),
    un(f"{c}-04", "소비 재테크 자동 적립 30회 이상 연 0.3% — 자동 적립 횟수 이벤트 없음", span(c, "30회 이상이면 (연 0.3%)")),
    un(f"{c}-05", "소비 재테크 자동 적립 40회 이상 연 0.4% — 자동 적립 횟수 이벤트 없음", span(c, "40회 이상이면 (연 0.4%) 우대금리 제공")),
    un(f"{c}-06", "추천인 우대 건당 연 0.1% (계좌별 최대 0.2%) — 추천인 번호 입력 변수 없음",
       span(c, ": 나의 소원 적금 신규 시 제공되는 추천인 번호를", "최대 (연 0.2%)까지 가능")),
])

# ───────────────────────── 쓰기 ─────────────────────────
n_ok = n_un = 0
for cid, (note, rules) in sorted(G.items()):
    t = TRI[cid]
    assert t["verdict"] in ("규칙", "표현불가"), cid
    for r in rules:
        assert _n(r["source"]["quote"]) in _n(CL[cid]["text"]), (cid, r["rule_id"])
        n_ok += r["status"] == "OK"
        n_un += r["status"] == "UNSUPPORTED"
    if t["verdict"] == "규칙":
        assert any(r["status"] == "OK" for r in rules), cid
    else:
        assert all(r["status"] == "UNSUPPORTED" for r in rules), cid
    out = {"clause_id": cid, "label": CL[cid]["label"], "verdict": t["verdict"], "note": note, "rules": rules}
    (OUT / f"{cid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", "utf-8")
want = {i for i, x in TRI.items() if x["verdict"] != "없음"}
print("files", len(G), "missing", sorted(want - set(G)), "extra", sorted(set(G) - want), "OK", n_ok, "UN", n_un)
