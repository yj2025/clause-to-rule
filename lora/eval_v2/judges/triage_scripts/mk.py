import json
R,N,U="규칙","없음","표현불가"
rows=[
("HNSAL-S1-P01",N,"high","상품명·특징 소개만 있는 개요 문장으로 조건→효과가 없다.",[]),
("HNSAL-S2-R01",R,"medium","실명의 개인 또는 개인사업자만 1인 1계좌로 가입 가능, 그 외 명의는 가입 불가. 타 상품 중복가입 불가는 카탈로그 상품 키에 없으나 1인1계좌·명의유형은 DISQUALIFY로 표현 가능.",["DISQUALIFY"]),
("HNSAL-S2-R04",U,"medium","월복리/단리 이자 계산·지급 방식 서술로 카탈로그에 표현 수단이 없다(중도해지·만기후는 단리라는 계산방식 지정).",[]),
("HNSAL-S2-R06",U,"low","1만~300만원 범위는 신규금액 서술에 가깝고, 청년응원 특별금리 등록 시 150만원이라는 조건은 카탈로그에 없는 등록 상태라 표현 불가.",[]),
("HNSAL-S2-R07",U,"low","분기 적립한도 범위 서술이며, 청년응원 특별금리 적용기간의 한도 변경 조건은 카탈로그에 없는 상태라 표현 불가.",[]),
("HNSAL-S2-R08",R,"medium","계약기간(1·2·3년)별 기본금리 표로 contract.term_months 조건의 RATE_OVERRIDE로 표현 가능.",["RATE_OVERRIDE"]),
("HNSAL-S2-R09",R,"high","급여이체 실적 보유 시 연 0.90% 가산, 중도해지 시 미적용 등 RATE_ADD로 표현 가능. 재예치·온라인가입 항목은 일부만 불가하나 규칙 존재.",["RATE_ADD"]),
("HNSAL-S2-R10",R,"high","만35세 이하·1년제·급여입금 6개월·하나카드 월 30만원 이상 충족 시 연 1.30% 가산(RATE_ADD).",["RATE_ADD"]),
("HNSAL-S2-R11",U,"high","쿠폰의 우대금리 값이 문서 밖(하나원큐 쿠폰함)에 있어 값을 알 수 없다.",[]),
("HNSAL-S2-R12",R,"low","중도해지 시 경과기간별 고정금리(연0.10/0.15/0.20%)가 있어 RATE_OVERRIDE 가능하나 경과율 계산 행은 표현 불가. 혼합이면 규칙.",["RATE_OVERRIDE"]),
("HNSAL-S2-R13",U,"high","만기후 금리가 지급 당시 정기적금 기본금리의 1/2, 1/4로 외부 값에 의존한다.",[]),
("HNSAL-S2-R14",U,"high","월복리 이자 계산식으로 계산 공식이라 표현 수단이 없다.",[]),
("HNSAL-S2-R25",N,"high","해당사항 없음이라 옮길 내용이 없다.",[]),
("HNDRM-S1-P01",N,"high","상품 특징 소개 문장뿐이다.",[]),
("HNDRM-S2-R01",R,"high","만 18세 이하 실명 개인만 1인 1계좌 가입 가능, 나이 초과 시 DISQUALIFY.",["DISQUALIFY"]),
("HNDRM-S2-R02",N,"high","상품유형 명칭만 있고 조건·효과가 없다.",[]),
("HNDRM-S2-R09",N,"medium","상품명에 별칭을 인자하는 편의 서비스 안내로 고객 조건에 따른 금리·자격·제한 효과가 아니다.",[]),
("HNDRM-S2-R10",R,"low","1년 기본금리 연 2.70% 단일 값으로 term_months=12 RATE_OVERRIDE 가능하나 단순 고시 서술일 수도 있다.",["RATE_OVERRIDE"]),
("HNDRM-S2-R11",R,"high","최초가입, 자동이체 6회, 체크카드 실적 등 조건별 RATE_ADD. 청약·아동수당 등 일부 불가하나 규칙 존재.",["RATE_ADD"]),
("HNDRM-S2-R12",R,"medium","만 7·13·16세 등 연령·가입 조건에 따른 특별금리 RATE_ADD. 희망대학 등록 등 일부 불가하나 규칙 존재.",["RATE_ADD"]),
("HNDRM-S2-R13",R,"low","중도해지 경과기간별 고정금리 RATE_OVERRIDE 가능, 경과율 계산 행은 표현 불가. 혼합이면 규칙.",["RATE_OVERRIDE"]),
("HNDRM-S2-R14",U,"high","만기후 금리가 정기적금 기본금리의 1/2, 1/4로 외부 값에 의존한다.",[]),
("HNDRM-S2-R15",U,"high","이자 계산 공식이라 표현 수단이 없다.",[]),
("HNDRM-S2-R24",N,"high","해당사항 없음.",[]),
("HNWSH-S1-P01",N,"high","상품 특징 소개 문장뿐이다.",[]),
("HNWSH-S2-R01",R,"medium","실명 개인만 1인 1계좌 가입 가능(customer.has_product, holder_type 기반 DISQUALIFY).",["DISQUALIFY"]),
("HNWSH-S2-R03",N,"high","상품유형 명칭만 있다.",[]),
("HNWSH-S2-R06",N,"medium","자동적립을 원하면 서비스를 신청해야 한다는 절차 안내로 금리·자격·한도 효과가 없다.",[]),
("HNWSH-S2-R09",R,"medium","가입기간 구간별 기본금리 표로 term_months 조건의 RATE_OVERRIDE 가능.",["RATE_OVERRIDE"]),
("HNWSH-S2-R10",U,"low","목표 불입금액 달성, 체크카드 자동적립 횟수, 추천인 번호 입력은 모두 카탈로그에 변수·이벤트가 없다.",[]),
("HNWSH-S2-R11",N,"low","소비재테크 서비스의 개념·신청·적립 방식 절차 안내가 대부분이고 고객 조건에 따른 금리·자격 효과가 없다.",[]),
("HNWSH-S2-R12",R,"low","중도해지 경과기간별 고정금리 RATE_OVERRIDE 가능, 경과율 계산 행은 표현 불가. 혼합이면 규칙.",["RATE_OVERRIDE"]),
("HNWSH-S2-R13",U,"high","만기후 금리가 상호부금 기본금리의 1/2, 1/4로 외부 값에 의존한다.",[]),
("HNWSH-S2-R14",U,"high","이자 계산식이라 표현 수단이 없다.",[]),
("HNWSH-S2-R23",N,"high","해당 없음.",[]),
]
out=[dict(id=a,verdict=b,confidence=c,reason=d,effects=e) for a,b,c,d,e in rows]
p=r"C:\HuggingFace_demo\eval_v2\judges\judge_sonnet.json"
json.dump(out,open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
ids=[c["id"] for c in json.load(open(r"C:\HuggingFace_demo\eval_v2\clauses.json",encoding="utf-8"))]
chk=json.load(open(p,encoding="utf-8"))
assert [x["id"] for x in chk]==ids and len(chk)==35
from collections import Counter
print(Counter(x["verdict"] for x in chk)); print([x["id"] for x in chk if x["confidence"]=="low"])
