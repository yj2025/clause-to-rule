import json
R="규칙";N="없음";U="표현불가"
J=[
("HNSAL-S1-P01",N,"high","상품명·특징 소개뿐이고 고객에 따라 갈리는 조건→효과가 없다.",[]),
("HNSAL-S2-R01",R,"high","실명의 개인·개인사업자 외 명의(holder_type)와 1인1계좌(has_product)는 DISQUALIFY 로 옮길 수 있다. 연금/주거래하나월복리적금 중복가입 불가는 하나은행 상품이 PRODUCTS 에 없어 UNSUPPORTED.",["DISQUALIFY"]),
("HNSAL-S2-R04",U,"high","만기일시지급·중도해지/만기후 단리 계산은 이자 지급 방식·계산법이라 카탈로그로 표현할 수단이 없다(kb10 이자지급방법 관례와 같음).",[]),
("HNSAL-S2-R06",R,"medium","가입금액 1만원 미만·300만원 초과면 가입 불가를 contract.amount 비교 DISQUALIFY 로 옮길 수 있다(kb10 가입금액 관례). 청년응원 특별금리 등록 시 150만원 한도는 등록 여부 변수가 없어 UNSUPPORTED. 적금의 '가입금액'이 월 납입액 뜻이면 표현불가로 갈 여지가 있다.",["DISQUALIFY"]),
("HNSAL-S2-R07",U,"low","분기당 적립한도는 '분기' 기간 단위의 한도를 담을 effect/변수가 없고, 청년응원 특별금리 적용기간 150만원 한도도 등록 상태 변수가 없다. 조건 없는 LIMIT_AMOUNT 로 근사하면 규칙으로 볼 수도 있다.",[]),
("HNSAL-S2-R08",R,"high","가입기간 1·2·3년별 기본금리 표를 contract.term_months 조건의 RATE_OVERRIDE 로 옮길 수 있다(kb10 계약기간별 기본이율표 관례).",["RATE_OVERRIDE"]),
("HNSAL-S2-R09",R,"high","급여하나우대(계약기간 1/2 이상 월 50만원 이상 급여입금 → 연0.90%)는 SALARY_TRANSFER count_distinct_months·min_amount 로, 온라인채널 가입(연0.10%)은 contract.channel 로 RATE_ADD 가능하며 중도해지 시 미적용은 guard. 재예치 기간 한정·급여일 등록 인정기준 일부는 UNSUPPORTED.",["RATE_ADD"]),
("HNSAL-S2-R10",R,"high","만35세 이하·1년제·6개월 이상 급여입금·하나카드 월30만원 이상 결제 시 연1.30% 는 customer.age·term_months·SALARY_TRANSFER·CARD_USAGE 로 RATE_ADD 가능. 고객별 1회 한정·하나머니 충전 제외는 UNSUPPORTED.",["RATE_ADD"]),
("HNSAL-S2-R11",U,"high","쿠폰 금리값이 문서 밖(쿠폰함)에 있고 쿠폰 보유 변수도 없어 표현 불가(kb10 금리우대쿠폰 관례).",[]),
("HNSAL-S2-R12",R,"medium","중도해지 1개월 미만 0.10%·1~3개월 0.15%·3~6개월 0.20% 는 termination_type EARLY 와 경과기간 조건의 RATE_OVERRIDE 로 옮길 수 있다. 6개월 이상 '기본금리×차등율×경과율' 식은 UNSUPPORTED. 입금건별 경과기간이라 근사인 점에서 medium.",["RATE_OVERRIDE"]),
("HNSAL-S2-R13",U,"high","만기후 금리는 지급 당시 정기적금 기본금리의 ½·¼ 로, 문서 밖 금리에 비율을 곱하는 식이라 표현 불가.",[]),
("HNSAL-S2-R14",U,"high","월복리 이자계산 산식 설명으로 판별 범위 밖 이자 산출이라 표현 불가.",[]),
("HNSAL-S2-R25",N,"high","'해당사항 없음' — 옮길 조건·효과가 없다.",[]),
("HNDRM-S1-P01",N,"high","상품 소개문으로 조건→효과가 없다.",[]),
("HNDRM-S2-R01",R,"high","만 18세 초과면 가입 불가(customer.age), 1인1계좌(has_product)를 DISQUALIFY 로 옮길 수 있다.",["DISQUALIFY"]),
("HNDRM-S2-R02",N,"high","상품유형 '적립식예금' 은 고정 사실로 판단할 조건이 없다.",[]),
("HNDRM-S2-R09",N,"low","예금주명 인자는 통장 표기 편의 안내로 금리·수수료·자격·제한에 해당하지 않는다. '글자수에 따라 미제공' 을 조건으로 보면 표현불가일 수 있다.",[]),
("HNDRM-S2-R10",N,"medium","가입기간이 1년 하나뿐이라 연 2.70% 단일 기본금리를 고시하는 서술이고 고객별로 갈리지 않는다(kb10 단일 기본이율 관례). 1년 조건 RATE_OVERRIDE 로 적을 여지는 있다.",[]),
("HNDRM-S2-R11",R,"high","자동이체 6회 이상(AUTO_TRANSFER count) 연0.20%, 가입 후 3개월 내 체크카드 결제(CARD_USAGE exists) 연0.20%, 최초가입(is_first_deposit 근사) 연0.20% 는 RATE_ADD 가능하고 중도해지 미적용은 guard. 주택청약 보유(하나은행 상품 키 없음)·아동수당 수령(이벤트 없음)은 UNSUPPORTED.",["RATE_ADD"]),
("HNDRM-S2-R12",R,"medium","가항(출생 후 1년 이내·만7·13·16세가 되는 계약기간 연0.30%)은 customer.age 조건 RATE_ADD 로 근사 가능하다. 나항 단체 10인 신규·다항 (태아)사랑하나적금 보유·희망대학 입학축하금리는 변수/상품 키가 없어 UNSUPPORTED. '해당 나이가 되는 계약기간' 판정이 근사라 medium.",["RATE_ADD"]),
("HNDRM-S2-R13",R,"medium","HNSAL 과 같은 중도해지 구간표: 6개월 미만 세 구간은 EARLY 해지·경과기간 조건 RATE_OVERRIDE, 6개월 이상 차등율×경과율 식은 UNSUPPORTED.",["RATE_OVERRIDE"]),
("HNDRM-S2-R14",U,"high","만기후 금리가 지급 당시 정기적금 기본금리의 ½·¼ 라 문서 밖 값×비율로 표현 불가.",[]),
("HNDRM-S2-R15",U,"high","이자계산 산식 설명으로 표현 불가.",[]),
("HNDRM-S2-R24",N,"high","'해당사항없음' — 옮길 것이 없다.",[]),
("HNWSH-S1-P01",N,"high","상품 소개문으로 조건→효과가 없다.",[]),
("HNWSH-S2-R01",R,"high","실명의 개인 외 명의 가입 불가(holder_type)와 1인1계좌(has_product)를 DISQUALIFY 로 옮길 수 있다(kb10 KBNR 관례).",["DISQUALIFY"]),
("HNWSH-S2-R03",N,"high","상품유형 '자유적립식' 은 고정 사실로 판단할 조건이 없다.",[]),
("HNWSH-S2-R06",N,"medium","자동 적립을 원하면 서비스를 신청하고 신청 당일 사용분부터 다음 영업일에 적립된다는 절차 안내로, 금리·수수료·자격·제한 효과가 없다.",[]),
("HNWSH-S2-R09",R,"high","6~12·12~24·24~36·36개월 구간별 기본금리 표를 contract.term_months 조건 RATE_OVERRIDE 로 옮길 수 있다.",["RATE_OVERRIDE"]),
("HNWSH-S2-R10",U,"low","목표 불입금액 달성(목표액 변수 없음), 체크카드 자동적립 횟수(소비재테크 자동적립 이벤트 없음), 추천인 번호 입력(변수 없음) 모두 카탈로그에 수단이 없다. 자동적립을 AUTO_TRANSFER 횟수로 근사하면 규칙으로 볼 여지가 있다.",[]),
("HNWSH-S2-R11",U,"low","서비스 신청자 한정·1일 적립 1천~10만원·잔액부족 시 재처리 불가·월 적립한도 제외 등 조건은 있으나 서비스 신청 상태·일별 자동적립을 담을 변수/이벤트가 없다. 대부분 서비스 동작 설명이라 없음으로 볼 여지도 있다.",[]),
("HNWSH-S2-R12",R,"medium","중도해지 6개월 미만 세 구간(0.1/0.15/0.2%)은 EARLY 해지·경과기간 조건 RATE_OVERRIDE 로 가능, 6개월 이상 차등률×경과율 식은 UNSUPPORTED.",["RATE_OVERRIDE"]),
("HNWSH-S2-R13",U,"high","만기후 금리가 지급 당시 상호부금 기본금리의 1/2·1/4 라 표현 불가.",[]),
("HNWSH-S2-R14",U,"high","이자계산식 설명으로 표현 불가.",[]),
("HNWSH-S2-R23",N,"high","'해당 없음' — 옮길 것이 없다.",[]),
]
ids=[c["id"] for c in json.load(open(r"C:\HuggingFace_demo\eval_v2\clauses.json",encoding="utf-8"))]
assert [j[0] for j in J]==ids, "id mismatch"
out=[{"id":i,"verdict":v,"confidence":c,"reason":r,"effects":e} for i,v,c,r,e in J]
p=r"C:\HuggingFace_demo\eval_v2\judges\judge_opus.json"
open(p,"w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=1))
d=json.load(open(p,encoding="utf-8")); print(len(d))
from collections import Counter; print(Counter(x["verdict"] for x in d)); print([x["id"] for x in d if x["confidence"]=="low"])
