# Agent 2 — 스펙 리뷰: system_v0.3 내부 모순 · 모호함 · 출력 스키마 결함

- 대상: `in/system_v0.3.txt` (57줄). 배경 참고: `in/table_dump.txt` (기획_배치결정표).
- 관점: 프롬프트를 계약서로 읽고, **성실한 구현자(=모델 또는 후처리 코드 작성자) 두 명이 다르게 해석할 수 있는 지점**을 찾았다.
- 표기: `[확인]` = 프롬프트·표 원문으로 확인된 사실. `[추측]` = 7B 모델 동작이나 파이프라인 데이터 형태에 대한 추정이라 실험으로 확인해야 함.
- 줄 번호는 system_v0.3.txt 기준. "표 행"은 기획_배치결정표의 정보 항목명.

---

## 0. 한눈에 보기 (심각도순 상위)

| # | 심각도 | 위치 | 한 줄 요약 |
|---|---|---|---|
| A1 | 치명 | rule 5 (L21) ↔ [입력] L7 ↔ rule 1 | "세전 여부"를 적으라는데 입력에 세전 여부 필드가 없음 → 지키려면 rule 1(상식 금지) 위반 |
| A2 | 치명 | rule 5 ↔ as_of | as_of 가 null 인 금리를 어떻게 할지 없음 → 날짜 지어내기 또는 금리 삭제로 갈림 |
| A5 | 높음 | L8 judgment_results | judgment_results 에 없는 fact 의 state 미정의, "INFO"와 파이프라인 누락이 구분 불가 |
| B4 | 높음 | rule 10 UNSATISFIED | "어떤 조건이 모자란지"를 말하라는데 입력에 그 정보 필드가 없음 → 모델이 재판정(rule 9 위반) |
| B1 | 높음 | rule 13 ↔ 7 ↔ 12 | 생략 규칙과 연쇄 포함 규칙의 우선순위 없음 → 분량·내용이 구현자마다 달라짐 |
| B3 | 높음 | rule 1 ↔ 10 ↔ 출력 | 질문·확인 안내 문장의 근거가 candidate_facts 가 아님 → "모든 문장 fact_id" 와 충돌 |
| C1 | 높음 | 출력 state | 문장 하나에 state 가 다른 fact 가 섞일 때 state 결정 규칙 없음, "INFO" 의미 혼탁 |
| A4 | 높음 | L7 condition/exceptions/only_in | 자료형·의미 미정의. only_in 이 "예외에만" 붙는지 "fact 전체"에 붙는지 두 해석 |
| B5 | 높음 | rule 10 PA3 | "적용됩니다" 템플릿이 가입 전(미가입) 시나리오에서 사실과 어긋남, scenario 입력 없음 |
| A6 | 중간 | L11 section_order | 원소가 키인지 제목인지, fact→섹션 배정 규칙 없음 → 정보 배치 판단을 LLM 이 하게 됨 |
| B6 | 중간 | rule 8 | "단위 환산을 하면" 허용 → 입력에 없는 수치 생성(rule 1·5 위반) 통로 |
| C3 | 중간 | questions_for_user ↔ rule 13 | INFO_MISSING 문장 속 질문과 questions_for_user 가 같은 내용을 두 번 씀 |
| E1 | 중간 | 규칙 괄호 (CF1…) | 평가 ID 가 모델 입력에 들어가 득보다 실이 클 가능성 |
| F | — | 전체 | system/user 분할안 (구체 템플릿 제시) |

---

## A. 입력 필드 정의 결함 (멘토: "누락값 처리 규칙(null/공백/보완)을 명시할 것")

### A1. [심각도: 치명] "세전 여부"를 요구하지만 입력에 세전 여부를 알 수 있는 필드가 없음
- 위치: rule 5 (L21) "고시 금리는 기준일(as_of)과 **세전 여부**를 같이 적는다", [입력] L7 `{fact_id, key, text, value, unit, condition, exceptions, only_in, as_of}`, rule 1 (L15) "입력에 없는 사실 · 수치 · **일반 상식은 쓰지 않는다**"
- 표 행: 기본금리·기본이율·적용이율(프롬프트 IN), 최고·최종 공시금리(프롬프트 IN), 세제·과세·비과세(프롬프트 IN — "비과세 가입 가능 상품이면 세후 결과와 함께 표시")
- 근거 [확인]: candidate_facts 필드 목록에 세전/세후 필드가 없다. text 안에 "세전"이 우연히 적혀 있을 때만 근거가 생긴다.
- 두 해석:
  - 구현자 1: "은행 고시 금리는 보통 세전이다"라는 상식으로 "(세전)"을 붙인다 → rule 1 위반이며, 비과세 상품이면 틀린 정보.
  - 구현자 2: 근거가 없으니 생략한다 → rule 5 위반.
  - 어느 쪽도 규칙을 다 지킬 수 없는 **구조적 모순**.
- 고친 문구:
  - [입력] candidate_facts 정의에 필드 추가:
    > `tax_basis`: "세전" · "세후" · null. 금리 Fact 에만 쓴다. null 이면 원문에 세전·세후 표시가 없다는 뜻이다.
  - rule 5 교체:
    > 5. 금리 · 금액 · 기간 · 횟수는 value 와 unit 을 그대로 옮긴다. %와 %p 를 바꾸지 않고, 원 단위를 줄이거나 반올림하지 않는다. 금리 Fact 를 쓸 때 as_of 가 있으면 "(○○○○.○○.○○ 기준)"을, tax_basis 가 있으면 "(세전)" 또는 "(세후)"를 붙인다. as_of · tax_basis 가 null 이면 해당 표시를 붙이지 않고, 날짜나 세전 여부를 짐작해 쓰지 않는다.
  - 코드 쪽 권장: tax_basis 는 2-4 단계에서 채우거나, 상품 공통 고정 문구("표시 금리는 세전 기준")를 **프론트 고정 영역**에서 내보내고 M3 에서는 빼는 편이 결정론적.

### A2. [심각도: 치명] as_of 가 없는 금리를 어떻게 처리할지 없음, "고시 금리"의 범위도 미정
- 위치: rule 5 (L21) "고시 금리는 기준일(as_of)…을 같이 적는다"
- 표 행: 최고·최종 공시금리, 기본금리, 이벤트·쿠폰·특별금리("현재 유효한 혜택과 핵심 조건만 표시")
- 근거 [확인]: (1) as_of 가 null/빈 문자열일 때의 지시가 없다. (2) "고시 금리"가 기본금리만인지, 우대금리·최고금리·중도해지이율·만기후이율까지인지 정의가 없다. 표에서는 "공시금리"라는 말을 쓰는데 프롬프트는 "고시 금리"를 써서 용어도 다르다.
- 두 해석: as_of 없음 → (a) 오늘 날짜/임의 날짜를 채움(환각, 치명), (b) 금리 문장을 통째로 뺌(must_include 이면 rule 11 위반), (c) 기준일 없이 그냥 씀. 고시 금리 범위 → 중도해지이율 표(기간별 % 테이블)에도 기준일을 붙일지 갈림.
- 고친 문구:
  - 용어 정의 블록(신설):
    > "금리 Fact" = unit 이 "%" 또는 "%p" 인 Fact. 기준일 표시는 금리 Fact 전부에 같은 방식으로 적용한다. ("고시 금리"라는 말은 쓰지 않는다)
  - 누락값 규칙(신설, A 공통):
    > as_of 가 null 이면 기준일을 쓰지 않는다. 날짜를 만들어 쓰지 않는다.
  - 코드 쪽 권장 [추측이 아닌 설계 제안]: 금리 Fact 의 as_of 가 null 이면 2-4 단계에서 `must_include` 에서 빼고 `omitted_must_include` 사유 `"AS_OF_MISSING"` 으로 코드가 미리 기록 — 모델에게 판단을 넘기지 않는다.

### A3. [심각도: 높음] value 가 null/빈 값이거나 text 와 value 가 다를 때 규칙 없음
- 위치: L7 `text, value, unit`, rule 5 "Fact 의 값과 단위를 그대로 옮긴다"
- 근거 [확인]: "Fact 의 값"이 text 속 숫자인지 value 필드인지 지정이 없다. value 가 null 인 서술형 Fact(예: "중도해지 시 중도해지이율 적용")와 수치형 Fact 가 섞여 들어올 것이 분명한데 [추측: 2-4 출력 형태 미확인] 처리 규칙이 없다.
- 두 해석: text 의 "연 3.5%" vs value `3.50` unit `%` → "3.5%"/"3.50%" 중 무엇이 "그대로"인가. value null 이면 text 숫자를 쓸지 숫자 없이 쓸지.
- 고친 문구:
  > value · unit 이 있으면 수치는 반드시 value 와 unit 으로 쓴다(text 속 숫자를 쓰지 않는다). value 가 null 또는 "" 이면 text 의 내용을 쓰되 text 에 없는 숫자를 만들지 않는다. text 와 value 의 숫자가 서로 다르면 그 Fact 를 쓰지 않고 omitted_must_include 에 reason "VALUE_TEXT_MISMATCH" 로 적는다(must_include 가 아니면 그냥 쓰지 않는다).
  - 코드 쪽 권장: value 는 문자열로 넘긴다("3.50", "1000000") — 7B 가 숫자 타입을 받아 3.5 로 정규화하는 것을 막기 위함 [추측].

### A4. [심각도: 높음] condition · exceptions · only_in 의 자료형과 의미 미정의
- 위치: L7, rule 7 (L23) "only_in 이 있는 예외도 똑같이 조건으로 쓰고, 끝에 "(상품설명서 기준)"처럼 출처 문서를 붙인다"
- 표 행: 우대금리·우대이율 조건, 가입제한·제외조건, 수수료·수수료면제
- 근거 [확인]: 세 필드 모두 문자열인지, 배열인지, 2-1 조건식 JSON 인지 정의가 없다. 특히 only_in:
  - 해석 1: exceptions 원소에 딸린 속성(예외 하나가 상품설명서에만 있음).
  - 해석 2: Fact 전체에 딸린 속성(이 Fact 자체가 상품설명서에만 있음). 필드 목록상 위치는 해석 2인데, rule 7 문장은 해석 1로 읽힌다.
  - only_in 의 값이 "상품설명서"라는 문서명인지, 문서 ID 인지, 배열인지도 미정 → "(상품설명서 기준)" 꼬리표 문구를 모델이 만들어야 함.
  - only_in 이 **없는** Fact 의 출처는 붙이지 않는가? (두 구현자가 "약관 기준"을 붙일지 갈림)
- condition 이 조건식 JSON 이면 [추측] 7B 가 AND/OR 를 자연어로 옮기다가 rule 2("이며"→"또는") 위반 위험이 커진다. condition 은 **자연어 문자열**(2-4 단계가 만든 것)로 받는 것이 rule 2 준수에 유리.
- 고친 문구 (필드 정의):
  > - condition: 문자열 또는 null. 이 Fact 의 금리·혜택이 적용되는 조건을 원문 표현으로 적은 것. 여러 조건이면 "그리고/또는"이 문자열 안에 이미 적혀 있다. 그대로 옮기고 접속어를 바꾸지 않는다. null 이면 조건이 없는 Fact 다.
  > - exceptions: 문자열 배열. 비어 있으면 []. 이 Fact 의 혜택이 적용되지 않는 경우(제외 조건)다.
  > - only_in: 문자열 또는 null. 이 Fact 가 약관이 아닌 다른 문서에만 있을 때 그 문서 이름(예: "상품설명서"). 값이 있으면 그 Fact 로 쓴 문장 끝에 "(only_in 값 기준)"을 붙인다. null 이면 아무것도 붙이지 않는다.
  - rule 7 교체:
    > 7. 제한 · 예외 · 상한(한도) · 전제조건을 빼거나 누그러뜨리지 않는다. 어떤 Fact 의 혜택을 쓰면 그 Fact 의 exceptions 도 같은 섹션에 쓴다. only_in 이 있는 Fact 는 문장 끝에 "(○○ 기준)"을 붙인다.

### A5. [심각도: 높음] judgment_results 에 없는 fact 의 state, 같은 fact 에 여러 판정
- 위치: L8, 출력 L50 `"INFO"`, L56 "state 가 없는 일반 정보 문장(금리 안내 등)은 "INFO"로 적는다"
- 근거 [확인]: candidate_facts 와 judgment_results 의 대응이 1:1 인지 정의가 없다. 판정 결과가 없는 경우가 두 종류다.
  - (a) 판정 대상이 아닌 일반 정보(예: 기본금리 숫자) → INFO 가 맞음.
  - (b) condition 이 있는데 판정이 빠짐(2-2/2-3 실패, overview 의 "보류 34건"과 같은 상황) → INFO 로 쓰면 **조건 있는 혜택을 무판정으로 안내**하게 되고, 모델이 condition 을 보고 스스로 적용 여부를 말할 위험(rule 9 위반).
  - 같은 fact_id 로 판정이 2건 이상 오면(하위 조건별 판정) 어떤 state 를 따를지 없음.
- 고친 문구:
  > judgment_results 는 fact_id 하나에 최대 한 건이다(코드가 보장). judgment_results 에 없는 Fact 는 판정 대상이 아닌 일반 정보이며, 고객에게 적용되는지 말하지 않는다 — "적용됩니다/안 됩니다/알려 주시면" 같은 표현을 쓰지 않고 상품 내용만 쓴다.
  - 코드 쪽 권장: (b) 경우는 코드가 state `BANK_CONFIRM_NEEDED` 또는 별도 `JUDGMENT_UNAVAILABLE` 로 채워 보내 모델이 (a)/(b) 를 구분할 필요가 없게 할 것.

### A6. [심각도: 중간] section_order 원소 정의 없음, fact→섹션 배정 규칙 없음, 빈 섹션 처리 없음
- 위치: L11 "section_order: 섹션 순서", rule 14 (L40), 출력 `"title": "..."`
- 근거 [확인]: 원소가 `"rate"` 같은 키인지 `"금리"` 같은 제목인지, 출력 title 을 원소 그대로 쓰는지 모델이 지을지 없다. 어떤 Fact 가 어느 섹션에 가는지도 모델이 정해야 한다 — 멘토 원칙("판정·선별은 코드, AI 는 문장만")에 비추면 배치 판단을 LLM 에 넘긴 셈. 해당 섹션에 쓸 Fact 가 없을 때 빈 섹션을 출력할지, 생략할지도 없다.
- 표 연결: 표는 항목마다 영역(상품기본/가입자격/금리이자/해지만기…)을 이미 정해 두었다 → 영역을 섹션 키로 쓰면 코드로 배정 가능.
- 고친 문구:
  > section_order: [{"section_id": "...", "title": "..."}] — 출력 sections 는 이 순서를 따르고 title 은 입력 title 을 글자 그대로 쓴다. 각 Fact 는 section_id 필드를 가진다. Fact 는 자기 section_id 섹션에만 쓴다. 쓸 문장이 없는 섹션은 출력하지 않는다.
  - candidate_facts 에 `section_id` 필드 추가.

### A7. [심각도: 중간] missing_fields 를 "그대로 묻는다" — 원소가 내부 키면 고객에게 키가 노출됨
- 위치: rule 10 INFO_MISSING (L31) "missing_fields 를 그대로 묻는다"
- 근거 [확인]: missing_fields 원소 형식 미정. [추측] 2-2 판정 코드가 내는 값은 `"salary_transfer"`, `"age"` 같은 필드 키일 가능성이 높다. "그대로"를 글자 그대로로 읽으면 "salary_transfer 를 알려 주시면"이 나오고, 풀어 쓰라고 읽으면 모델이 질문을 창작(나이 → "만 나이"? "생년월일"?)해 질문 내용이 호출마다 달라진다. 또한 overview 메모의 "군인이십니까?" 같은 질문 문구는 개인정보 수집 범위와 연결되므로(표 '최초입력_추천안' — 개인정보보호법 제16조 최소수집) 코드에서 고정하는 것이 맞다.
- 고친 문구:
  > missing_fields: [{"field": "...", "question": "..."}] — question 은 고객에게 물을 문장으로 코드가 만든다. 질문은 question 을 글자 그대로 쓰고 바꾸거나 더하지 않는다.

### A8. [심각도: 중간] user_input 의 "없는 값" 정의 — null / "" / 0 / 키 없음 구분
- 위치: L6 "없는 값은 모르는 것이다"
- 근거 [확인]: 예치 예정금액 0, 빈 문자열, null, 키 자체 없음, "모름" 문자열이 같은 뜻인지 없다. 0 원(실제 값)을 "모르는 것"으로 처리하면 안 됨.
- 고친 문구:
  > user_input 에서 키가 없거나 값이 null 또는 "" 이면 그 정보는 모르는 것이다. 0, false 는 고객이 입력한 실제 값이다. 모르는 정보를 짐작하거나 다른 값으로 채우지 않는다.

### A9. [심각도: 낮음] purpose 가 비었을 때, reason · key 의 용도
- 위치: L5, L8 `reason`, L7 `key`
- 근거 [확인]: purpose 가 null/"" 일 때 rule 13 "purpose 와 … 관련된 Fact 를 먼저" 의 기준이 사라진다(가입 전 첫 화면은 purpose 없이 들어올 가능성이 큼 [추측]). reason 은 문장에 써도 되는지(쓰면 근거가 candidate_facts 가 아님 → rule 1 충돌) 없다. key 는 어디에도 쓰이지 않는다.
- 고친 문구:
  > purpose 가 null 또는 "" 이면 must_include 와 section_order 순서만 따른다.
  > judgment_results 의 reason 은 참고용이다. reason 의 문장이나 수치를 그대로 옮기지 않는다 — 모자란 조건은 unmet_conditions(B4)로만 쓴다.
  > key 는 Fact 종류 이름이다(문장에 쓰지 않는다).

---

## B. 규칙 간 충돌·모호

### B1. [심각도: 높음] rule 13 "도움 안 되는 Fact 는 넣지 않는다" vs rule 7 "제외 조건도" vs rule 12 dependencies vs 정보량 축소 — 우선순위 없음
- 위치: rule 7 (L23), rule 11 (L35), rule 12 (L36), rule 13 (L39)
- 표 행/멘토: "정보가 많으면 안 보므로 한 화면 정보량 축소", 회의요약 "우대금리 표현 — 미확정 조건과 분리", overview "요약은 약 5~6줄 기준"
- 근거 [확인]: rule 13 은 생략을 지시하고 rule 7·12 는 연쇄 포함을 지시한다. 혜택 Fact 하나를 고르면 exceptions + dependencies(B) + B 의 dependencies… 로 폐포가 커지는데, 어디까지가 의무인지·문장 수 상한이 있는지 없다. "판단에 도움이 안 되는" 의 기준도 모델 재량이라 같은 입력에서 구현자마다(=샘플마다) 다른 Fact 집합이 나온다 → 일치율 테스트가 흔들림.
- 추가 모순: UNSATISFIED 혜택에도 rule 7 대로 제외 조건을 붙여야 하는가? 적용되지 않는 혜택의 제외 조건은 정보량만 늘린다.
- 고친 문구 (rule 13 교체):
  > 13. 쓸 Fact 는 다음 순서로 고른다. ① must_include_fact_ids 전부 ② 고른 Fact 의 dependencies 쌍 B 전부 ③ 고른 Fact 의 exceptions ④ purpose 와 관련된 나머지 Fact. ①~③ 은 빼지 않는다. ④ 는 문장이 총 N 개를 넘지 않을 때만 넣는다. 같은 내용을 두 번 쓰지 않는다.
  > (단, UNSATISFIED Fact 는 exceptions 를 쓰지 않고 모자란 조건만 쓴다.)
  - 코드 쪽 권장: ①②의 폐포(dependencies 의 추이 폐포)는 코드가 계산해 must_include 에 미리 넣는다 → 모델은 "must_include 전부 + 여유 있으면 purpose 관련"만 판단. N(예: 8)은 팀이 정하고 일치율 테스트로 조정.

### B2. [심각도: 중간] rule 6 "금리·혜택은 조건과 한 문장에" vs rule 15 문장 완결·자연스러움 → 과도하게 긴 문장
- 위치: rule 6 (L22), rule 15 (L43), rule 14 "앞 문장이 가리키는 대상이 분명하게"
- 근거 [확인]: 조건이 3~4개인 우대금리(예: 급여이체 그리고 카드실적 30만원 이상 그리고 마케팅 동의)를 한 문장에 묶고, rule 5 의 기준일·세전 표기, rule 7 의 제외 조건, rule 10 의 "입력하신 내용 기준으로" 까지 붙이면 한 문장이 100자를 쉽게 넘는다 [추측: 7B 에서 호응 오류·조건 누락 확률이 높아짐]. 구현자 1은 한 문장 강행, 구현자 2는 문장을 쪼개고 둘째 문장을 "이 경우"로 시작 → 어느 쪽이 규칙 준수인지 판정 불가.
- 고친 문구 (rule 6 교체):
  > 6. 이상 · 초과 · 이하 · 미만 경계를 그대로 쓴다. 금리 · 혜택은 그 condition 과 떨어뜨리지 않는다: 조건이 하나면 한 문장에 쓰고, 둘 이상이면 "다음 조건을 모두 충족하면 연 ○○%입니다:" 처럼 금리 문장 바로 뒤에 조건 문장을 이어 쓴다. 이어 쓴 문장은 같은 fact_id 를 달고, 사이에 다른 Fact 의 문장을 넣지 않는다.
  - (조건 목록을 문장 배열에 넣을지, 별도 `conditions` 배열로 출력할지는 프론트 렌더링과 함께 결정 — 표 '우대금리' 행 "미확정 조건과 분리" 권고와 맞음)

### B3. [심각도: 높음] rule 1 "모든 문장 fact_id" vs 섹션 제목·질문 문장·INFO_MISSING/BANK_CONFIRM 안내 문장
- 위치: rule 1 (L15), rule 10 (L31~32), 출력 L50
- 근거 [확인]: "○○을 알려 주시면 확인할 수 있습니다", "은행 확인이 필요합니다"의 근거는 candidate_facts 가 아니라 judgment_results 다. 섹션 title 은 sentences 밖이라 근거가 필요 없는지 불분명. 구현자 1은 질문 문장에 fact_ids `[]` 를 달고, 구현자 2는 대상 Fact id 를 단다 → 후처리 검증(fact_ids 비어 있으면 실패) 코드가 달라진다.
- 고친 문구 (rule 1 교체):
  > 1. sentences 의 모든 문장은 fact_ids 가 1개 이상이다. 판정 안내 문장(적용됩니다 / 적용되지 않습니다 / 알려 주시면 / 은행 확인)은 그 판정의 fact_id 를 단다. 섹션 title 은 문장이 아니며 입력 title 을 그대로 쓴다. 입력에 없는 사실 · 수치 · 일반 상식은 쓰지 않는다.

### B4. [심각도: 높음] rule 10 UNSATISFIED "+ 어떤 조건이 모자란지" — 입력에 그 정보가 없음
- 위치: rule 10 (L30), rule 9 (L27) "뒤집거나 새로 판정하지 않는다"
- 근거 [확인]: judgment_results 에는 `missing_fields`(정보 없음용)와 `reason`(형식 미정)뿐이다. 어느 하위 조건이 미충족인지 구조화 필드가 없으므로, 모델은 user_input 과 condition 을 비교해 "급여이체 실적이 없어서"를 **스스로 추론**해야 한다 = 새 판정(rule 9 위반, 멘토 "판정은 코드").
- 고친 문구:
  > judgment_results: [{fact_id, state, missing_fields, unmet_conditions, reason}] — unmet_conditions 는 UNSATISFIED 일 때 충족되지 않은 조건 문구 배열(코드가 채움).
  > UNSATISFIED: "입력하신 내용 기준으로는 적용되지 않습니다" + unmet_conditions 를 그대로 쓴다. unmet_conditions 가 비어 있으면 모자란 조건을 쓰지 않는다.

### B5. [심각도: 높음] PA3 템플릿이 가입 전(미가입) 시나리오에서 부자연스럽고, 금소법 표현 리스크
- 위치: rule 10 (L29) SATISFIED "입력하신 내용 기준으로 적용됩니다 — 단정하되"
- 표/멘토: 파이프라인 ④ 시나리오(가입 전·가입 후·만기 전후), 멘토단 "MVP 는 가입 전이 본질", "추천 가능/불가 표현은 금소법 중개 이슈로 쓰지 않음"
- 근거 [확인]: 가입 전 고객에게 "우대금리가 적용됩니다"는 아직 계약도, 실적도 없는 상태에서 확정 결과처럼 읽힌다. 또 우대조건 중 상당수는 "가입 후 기간 중 실적"이라 [추측] 가입 전 판정은 "조건 충족 가능"이지 "적용"이 아님. 입력에 scenario 필드가 없어서 템플릿을 분기할 수도 없다. rule 16 "혜택을 보장하는 말을 쓰지 않는다"와 "단정하되"도 긴장 관계.
- 가입제한 행의 "가입 가능/불가 판정" 결과가 SATISFIED 로 오면 "가입하실 수 있습니다" → 추천처럼 읽힐 여지.
- 고친 문구:
  - [입력] 추가: `scenario`: "가입전" · "가입후" · "만기전후"
  - rule 10 SATISFIED 교체:
    > - SATISFIED: 가입전이면 "입력하신 내용 기준으로 ○○ 조건에 해당합니다", 가입후·만기전후면 "입력하신 내용 기준으로 적용됩니다". "받을 수 있습니다 · 받게 됩니다 · 가입하세요 · 유리합니다 · 추천" 은 쓰지 않는다.

### B6. [심각도: 중간] rule 8 "단위 환산을 하면 원래 값도 같이 쓴다" — 수치 생성 허용
- 위치: rule 8 (L26) ↔ rule 1 "입력에 없는 수치는 쓰지 않는다", rule 5 "원 단위를 줄이거나 반올림하지 않는다"
- 근거 [확인]: rule 8 은 환산을 암묵적으로 허용한다(예: 10000000원 → "1천만 원"). 환산 결과는 입력에 없는 수치이고 rule 5 "원 단위를 줄이지 않는다"와도 정면 충돌. 7B 는 자릿수 환산에서 오류를 낼 수 있음 [추측].
- 고친 문구:
  > 8. user_input 의 값은 입력 그대로 인용한다. 단위를 바꾸거나 계산하지 않는다. (표시용 포맷이 필요하면 코드가 user_input 에 display 문자열을 넣어 준다)

### B7. [심각도: 중간] INFO_MISSING "혜택을 가정하지 않는다" vs "조건부 문장(○○이면 △△)"
- 위치: rule 10 (L31)
- 근거 [확인]: "○○이면 △△"의 △△ 가 혜택이므로 일종의 가정이다. 경계가 없으면 구현자 1은 "급여이체를 하시면 연 0.5%p 우대금리가 적용됩니다"(사실상 확정 톤), 구현자 2는 조건부 문장을 아예 안 씀.
- 고친 문구:
  > - INFO_MISSING: 고객에게 적용되는지 말하지 않는다. "○○(condition)이면 △△(value unit)가 적용되는 조건입니다. 아래 질문에 답해 주시면 적용 여부를 확인할 수 있습니다." 형식으로 쓴다. △△ 는 그 Fact 의 value · unit 만 쓴다.

### B8. [심각도: 중간] rule 12 의 예시가 dependencies 밖 쌍을 모델에게 추론시킴
- 위치: rule 12 (L36) "예: 최고금리를 말하면 그 금리의 조건 · 한도 · 기간도 말한다"
- 근거 [확인]: 예시가 일반 원칙처럼 쓰여 있어서 dependencies 에 없는 쌍(최고금리 ↔ 기간)도 모델이 스스로 묶게 된다 → 결정론 이탈 + rule 3("서로 다른 Fact 의 조건과 혜택을 새로 연결하지 않는다")과 충돌 가능.
- 표 연결: 최고·최종 공시금리 행 "기본금리/조건과 묶어 보여주기" — 이 묶음은 2-4 코드가 dependencies 로 내보내는 것이 맞다.
- 고친 문구:
  > 12. dependencies 의 A 를 썼으면 B 도 쓴다. dependencies 에 없는 Fact 끼리는 새로 묶지 않는다.

### B9. [심각도: 중간] rule 4 "Fact 에 그 말이 있을 때만 '보장'" vs rule 16 "보장하는 말을 쓰지 않는다"
- 위치: rule 4 (L18), rule 16 (L44)
- 근거 [확인]: rule 4 는 조건부 허용, rule 16 은 무조건 금지 → 원문에 "원금 보장"이 있는 경우 두 해석. 표의 '예금자보호' 행은 "제외"(프론트 고정 표시)라 M3 에 올 일은 적지만 상품 특징 Fact 에 섞일 수 있음.
- 고친 문구:
  > 4. … "항상" · "누구나" · "확실히"는 Fact 의 text 에 그 말이 있을 때만 쓴다. "보장"은 쓰지 않는다(rule 16).

### B10. [심각도: 중간] rule 14 "고객에게 중요한 것부터" — 기준 없음, 표의 우선순위가 반영 안 됨
- 위치: rule 14 (L40)
- 표 행: 가입제한·제외조건 "가입이 불가능한 조건은 혜택보다 먼저 알려주는 쪽을 추천", 중도해지 "핵심 불이익으로 표시", 거래·이용·입출금 제한 "핵심 주의로 표시"
- 근거 [확인]: "중요"의 기준이 없어 섹션 내 순서가 샘플마다 달라짐.
- 고친 문구:
  > 각 섹션 안에서는 UNSATISFIED → BANK_CONFIRM_NEEDED → INFO_MISSING → SATISFIED → 일반 정보 순으로 쓴다. 같은 순위 안에서는 candidate_facts 순서를 따른다.
  - 코드 쪽 권장: candidate_facts 를 우선순위로 정렬해 넘기면 "입력 순서대로" 한 줄로 해결.

### B11. [심각도: 낮음] rule 11 "모두 반영" + omitted_must_include 로 빠져나갈 통로 — 허용 사유 미정
- 위치: rule 11 (L35), 출력 L54
- 근거 [확인]: 어떤 경우에 생략이 정당한지 없어서, 7B 가 길이를 줄이려고 must_include 를 omitted 로 돌릴 수 있다 [추측]. reason 이 자유 문장이면 자동 집계 불가.
- 고친 문구:
  > omitted_must_include 의 reason 은 "VALUE_TEXT_MISMATCH" · "AS_OF_MISSING" · "DUPLICATE_OF:<fact_id>" 중 하나만 쓴다. 이 밖의 이유로 must_include 를 빼지 않는다.

---

## C. 출력 스키마 결함

### C1. [심각도: 높음] sentence.state — "INFO" 가 입력 state 4종과 섞임, 여러 fact 문장의 state 미정
- 위치: L50, L56
- 근거 [확인]: (1) 문장 하나가 SATISFIED fact 와 INFO_MISSING fact 를 함께 쓰면 state 를 무엇으로 적을지 규칙이 없다. (2) "INFO" 는 판정 상태가 아니라 "판정 없음"인데 같은 enum 에 섞여 있고, 이름이 INFO_MISSING 과 접두어가 같아 7B 가 혼동하기 쉽다 [추측]. (3) L56 "state 가 없는 일반 정보 문장(금리 안내 등)" — 금리 안내는 우대금리면 판정이 있으므로 예시가 오해를 부른다.
- 고친 문구:
  > 문장 하나에는 state 가 같은 Fact 만 쓴다. state 는 그 Fact 들의 judgment state 를 그대로 적고, judgment_results 에 없는 Fact 만 쓴 문장은 "NONE" 으로 적는다.
  - 출력 enum: `"SATISFIED|UNSATISFIED|INFO_MISSING|BANK_CONFIRM_NEEDED|NONE"` ("INFO" → "NONE"로 개명)
  - 후처리 검증: 문장 state == 각 fact_id 의 입력 state(없으면 NONE) 를 코드로 검사 → PA2 자동 채점 가능.

### C2. [심각도: 중간] used_fact_ids 는 sentences fact_ids 합집합과 같아야 하는가
- 위치: L53
- 근거 [확인]: 정의가 없다. 합집합이면 모델이 출력할 이유가 없는 파생값(불일치만 만드는 필드)이고, 다르다면 "문장엔 안 썼지만 참고한 Fact"인지 의미가 불명.
- 고친 문구: 출력에서 삭제하고 코드가 계산. 남겨야 한다면
  > used_fact_ids 는 sentences 의 fact_ids 를 중복 없이 모은 것과 정확히 같다.

### C3. [심각도: 중간] questions_for_user 와 INFO_MISSING 문장 속 질문의 중복 (rule 13 "같은 내용 두 번" 위반)
- 위치: rule 10 INFO_MISSING "알려 주시면 확인할 수 있습니다… missing_fields 를 그대로 묻는다", L52, rule 13
- 근거 [확인]: 같은 질문이 본문 문장과 questions_for_user 에 두 번 나오는 것이 설계상 강제된다. 또 questions_for_user 가 문자열 배열이라 어떤 field/fact 에 대한 질문인지 연결이 없어, 답변을 받은 뒤 재판정(표 "답변 후 개인화 출력")으로 이어 붙일 수 없다.
- 고친 문구:
  > 질문 문장은 sentences 에 쓰지 않는다. 본문에는 B7 의 조건부 문장만 쓰고 "아래 질문에 답해 주시면"으로 끝낸다.
  > "questions_for_user": [{"field": "...", "fact_ids": ["..."], "question": "..."}] — missing_fields 의 field · question 을 그대로 옮긴다. 같은 field 는 한 번만 쓴다.
  - (A7 처럼 question 을 코드가 만든다면 questions_for_user 자체를 코드가 생성하고 모델 출력에서 빼는 것도 가능 — 더 결정론적)

### C4. [심각도: 낮음] 빈 배열·빈 섹션·코드펜스 처리
- 위치: L46 "JSON 하나만, 다른 글 없이", L52~54
- 근거 [확인]: omitted_must_include · questions_for_user 가 없을 때 `[]` 인지 키 생략인지 없음. ```json 코드펜스 허용 여부 없음 [추측: Qwen2.5 는 펜스를 자주 붙임]. 빈 sentences 섹션 처리 없음(A6).
- 고친 문구:
  > 출력은 `{` 로 시작해 `}` 로 끝난다. ``` 를 쓰지 않는다. 키는 모두 쓰고, 내용이 없으면 [] 로 적는다. 문장이 없는 섹션은 넣지 않는다. text 안에 fact_id 같은 내부 값을 쓰지 않는다.

### C5. [심각도: 낮음] product 출력 필드
- 근거 [확인]: 입력 product 를 그대로 복사하라는 지시가 없음(상품명 축약·수정 가능). 코드가 이미 아는 값이라 출력에서 빼는 것이 낫다.
- 고친 문구: 삭제 권장. 유지 시 "product 는 입력 값을 글자 그대로 쓴다."

---

## D. 용어 혼동

### D1. [심각도: 중간] 용어 정의가 없거나 같은 대상에 여러 이름
| 용어 | 문제 [확인] | 고친 문구 |
|---|---|---|
| "Fact" / "Fact 의 값" | text 인지 value 인지 불명 (A3) | "Fact = candidate_facts 의 원소 하나. Fact 의 수치 = value + unit" |
| "고시 금리" | 범위 미정, 표는 "공시금리" (A2) | "금리 Fact" 로 통일 |
| "혜택" | 금리 우대만인지 수수료 면제·제휴혜택 포함인지 불명 (rule 3, 6, 7, 10, 16) | "혜택 = condition 이 있는 Fact 의 value(우대금리·면제·지원금 등)" |
| "제외 조건" (rule 7) | exceptions 필드와 같은 것인지 불명 | "제외 조건 = exceptions" |
| "제한·예외·상한·전제조건" (rule 7) | 어느 필드에 해당하는지 매핑 없음 | "제한·상한은 별도 Fact 로 오고, 예외는 exceptions, 전제조건은 condition" |
| "조건부 문장" (rule 10) | 형식 불명 (B7) | B7 템플릿 |
| "출처 문서" (rule 7) | only_in 값인지, 모델이 만드는지 (A4) | "only_in 값" |
| "섹션" | section_order 원소와 title 관계 (A6) | A6 |
| "고객 상황" (rule 13) | user_input 인지 judgment 인지 | "user_input 과 judgment_results" |

---

## E. 평가 기준 ID 괄호를 모델 입력에 넣는 것의 득실

### E1. [심각도: 중간] (CF1)~(F1·F2·F3·F4) 괄호
- 위치: L13 "[규칙 — 괄호는 평가 기준 ID]", 각 규칙 끝
- 득 [확인]: 규칙 ↔ 평가표 추적성(어느 규칙이 어느 지표를 겨냥하는지)이 한 파일에 보임. 실패 사례 분석 때 편함.
- 실 [추측, 실험 필요]:
  - 7B 모델에게 ID 자체는 의미가 없다(평가표 내용이 프롬프트에 없음). 토큰만 차지.
  - 출력 문장에 "(CF1)"·"(FD3)" 식 괄호를 흉내 낼 위험 — 특히 rule 7 이 "(상품설명서 기준)" 같은 괄호 꼬리표를 요구해 괄호 패턴이 강화됨.
  - "R1 · R2 · R3 · R4" 처럼 한 규칙에 4개 ID 가 붙은 곳은 규칙 1개에 평가 4개가 매달린 구조라, 평가표 쪽에서 이중 감점(learnings: "too many criteria cause double-penalty")의 신호이기도 함 — 프롬프트 문제라기보다 평가표 정리 과제.
- 고친 문구: 모델에 보내는 system 에서는 괄호와 L13 의 "— 괄호는 평가 기준 ID" 를 지운다. 추적성은 저장소에 `prompt_rule_map.csv` (rule_no, eval_ids) 로 따로 둔다. 확실히 하려면 괄호 있음/없음 두 버전을 같은 케이스로 돌려 일치율 비교(learnings: "넣은 버전·뺀 버전을 모두 돌려 결정").

---

## F. system / user 경계 — 구체 분할안

### 원칙
- **system** = 호출마다 바뀌지 않는 것: 역할, 입력 필드 정의(스키마 설명 = 현재 [입력] 블록), 누락값 규칙, 문장 규칙, state 템플릿, 출력 스키마. 현재 [입력] 블록은 "값"이 아니라 "스키마 설명"이므로 system 에 남는 게 맞다 [확인].
- **user** = 호출마다 바뀌는 실제 값: scenario, product, purpose, user_input, candidate_facts, judgment_results, must_include_fact_ids, dependencies, section_order.
- 멘토 지적(소형 모델은 앞부분 정보 손실) 대응 [추측, 실험 필요]: system 을 짧게 유지하고, **user 맨 끝에 출력 형식 한 줄 리마인더**를 둔다. user 안에서도 must_include Fact 를 candidate_facts 앞쪽에 정렬한다.
- Qwen2.5-Instruct 는 chat template 에 system 역할을 지원하므로 기술적 제약은 없다 [확인: Qwen2.5 chat template 에 system 블록 존재. 단, system 미지정 시 기본 system 문구가 자동 삽입되므로 반드시 명시할 것].

### system (고정) 구성
```
[역할] 1~2줄 (현재 L1)
[입력 필드 정의] 현재 [입력] 블록 + A1~A9 정의 (tax_basis, section_id, unmet_conditions, missing_fields 구조, scenario)
[누락값 규칙] null / "" / [] / 키 없음 처리 한 블록으로 모음 (A2, A3, A8, A9)
[규칙] 1~16 (평가 ID 괄호 제거, B1~B11 반영)
[state 문구] 시나리오별 템플릿 표 (B5, B7)
[출력 형식] JSON 스키마 + C1~C5
```

### user (호출마다) 템플릿
```
scenario: 가입전
product: KB Star 정기예금
purpose: 금리가 얼마인지
user_input: {"deposit_amount": "10000000", "term_months": "12", "salary_transfer": null}
section_order: [{"section_id":"rate","title":"금리"},{"section_id":"terminate","title":"중도해지"}]
must_include_fact_ids: ["F3","F7"]
dependencies: [["F3","F4"]]
candidate_facts:
[{"fact_id":"F3","section_id":"rate","key":"우대금리","text":"...","value":"0.5","unit":"%p","tax_basis":null,"condition":"급여이체 실적이 있는 경우","exceptions":[],"only_in":null,"as_of":"2026-10-01"}, ...]
judgment_results:
[{"fact_id":"F3","state":"INFO_MISSING","missing_fields":[{"field":"salary_transfer","question":"급여를 이 은행 계좌로 받고 계신가요?"}],"unmet_conditions":[],"reason":"..."}]

위 입력만 근거로, system 의 출력 형식대로 JSON 하나만 출력하라.
```
- 이 템플릿에서 위 JSON 예시는 설명용이며 값은 가상이다.
- user 에 넣지 말 것: 규칙 재진술(길이 증가), 평가 ID, few-shot 예시(넣을 거면 system 끝에 1개, 시나리오별 1개 이하 — 길이 대비 효과는 실험으로 확인).

---

## G. 의사결정표와 프롬프트 사이 불일치 (배경 참고, 프롬프트 수정 범위 밖일 수 있음)

### G1. [심각도: 중간] "우대금리·우대이율 조건"은 "제외"(프론트가 보여 줌)인데, "최고·최종 공시금리"는 "프롬프트 IN" + "조건 충족 시 표현과 함께"
- 근거 [확인]: 표 '우대금리·우대이율 조건' 행 마지막 열 "제외", '최고·최종 공시금리' 행 "프롬프트 IN", 표현 방식 "최고금리는 '조건 충족 시'라는 표현과 함께 표시". rule 6·12 는 최고금리를 쓰면 조건도 쓰라고 하는데, 조건 Fact 가 프론트 제외 대상이라 candidate_facts 에 안 들어오면 rule 12 를 지킬 수 없다.
- 고친 문구(팀 결정 필요):
  > "프론트 제외 항목이라도 프롬프트 IN 항목의 dependencies B 로 걸리면 candidate_facts 에 포함한다" — 2-4 단계 규칙으로 명시.

### G2. [심각도: 낮음] 이벤트·쿠폰·특별금리 "현재 유효한 혜택만" — 유효기간 필드 없음
- 근거 [확인]: 표 행 '이벤트·쿠폰·특별금리'(프롬프트 IN) 표현 방식 "현재 유효한 혜택과 핵심 조건만". 입력에 valid_until 이 없어 모델이 유효성을 판단할 수 없다(판단해서도 안 됨).
- 고친 문구: "유효하지 않은 이벤트 Fact 는 2-4 단계에서 candidate_facts 에서 뺀다" (코드 규칙), 프롬프트에는 추가 없음.

### G3. [심각도: 낮음] 세제·과세(프롬프트 IN, "세후 결과와 함께 표시") vs rule 1·8 계산 금지
- 근거 [확인]: 세후 결과는 계산값이다. 모델이 계산하면 안 되므로 코드가 세후 금액을 Fact(value)로 만들어 넘겨야 한다. A1 의 tax_basis 와 함께 2-4 산출물 정의에 반영 필요.

### G4. [심각도: 낮음] 표의 '금융 설명 수준'(쉬움/기본/상세) 입력 vs rule 15 "쉬운 말로 풀어 쓰기는 하지 않는다"
- 근거 [확인]: 최초입력_추천안에 '금융 설명 수준' 선택 입력이 있으나 M4 보류로 프롬프트는 원문 용어 고정. 현재는 일관(M4 보류)이나, 나중에 수준 입력을 user 로 넘기면 rule 15 와 충돌하므로 그때 rule 15 를 분기해야 함을 메모.

---

## H. 수정 반영 system 초안 (v0.4 후보, 위 지적을 한데 모은 것)

> 아래는 지적 사항을 반영한 **예시 초안**이다. 필드 추가(tax_basis, section_id, unmet_conditions, missing_fields 구조, scenario)는 2-4 단계 산출물 변경이 전제이므로 팀 합의 후 적용.

```
너는 은행 예금상품 정보를 고객 한 사람에게 맞춰 정리하는 모델이다. user 메시지의 입력만 근거로 쓴다. 적용 여부는 이미 코드가 판정했다. 너는 판정을 새로 하지 않고, 정확한 문장으로 옮긴다.

[입력 필드]
- scenario: "가입전" | "가입후" | "만기전후"
- product: 상품 이름
- purpose: 고객이 알고 싶은 것. null 또는 "" 이면 없음
- user_input: 고객이 넣은 값. 키가 없거나 null · "" 이면 모르는 값이다. 0 · false 는 실제 값이다
- section_order: [{section_id, title}]
- candidate_facts: [{fact_id, section_id, key, text, value, unit, tax_basis, condition, exceptions, only_in, as_of}]
  - value · unit: 수치. 수치는 이 두 필드로만 쓴다. value 가 null 이면 수치가 없는 Fact 다
  - tax_basis: "세전" | "세후" | null
  - condition: 이 Fact 가 적용되는 조건(문자열) 또는 null
  - exceptions: 이 Fact 가 적용되지 않는 경우(문자열 배열). 없으면 []
  - only_in: 이 Fact 가 실린 약관 외 문서 이름 또는 null
  - as_of: 금리 기준일 또는 null
- judgment_results: [{fact_id, state, missing_fields:[{field, question}], unmet_conditions:[...], reason}]
  - fact_id 하나에 한 건. 여기에 없는 Fact 는 판정 대상이 아닌 일반 정보다
  - reason 은 참고용이며 문장에 옮기지 않는다
- must_include_fact_ids: 반드시 쓸 fact_id
- dependencies: [[A, B]] — A 를 쓰면 B 도 쓴다

[규칙]
근거
1. sentences 의 모든 문장은 fact_ids 가 1개 이상이다. 입력에 없는 사실 · 수치 · 일반 상식은 쓰지 않는다.
2. 뜻 · 방향 · 범위를 바꾸지 않는다. "하나 이상"↔"모두", "그리고"↔"또는", "제외"↔"포함"을 바꾸지 않는다.
3. 서로 다른 Fact 의 조건과 혜택을 묶지 않는다. dependencies 에 없는 Fact 끼리 새로 묶지 않는다.
4. "항상 · 누구나 · 확실히"는 text 에 그 말이 있을 때만 쓴다. "보장 · 추천 · 유리 · 가입하세요"는 쓰지 않는다.
수치·조건
5. 수치는 value 와 unit 을 그대로 쓴다. %와 %p 를 바꾸지 않고, 줄이거나 반올림하지 않는다. 금리(unit 이 % 또는 %p)를 쓸 때 as_of 가 있으면 "(YYYY.MM.DD 기준)", tax_basis 가 있으면 "(세전)" 또는 "(세후)"를 붙인다. null 이면 붙이지 않고 짐작해 쓰지 않는다.
6. 이상 · 초과 · 이하 · 미만을 그대로 쓴다. 금리 · 혜택은 condition 과 떨어뜨리지 않는다. 조건이 둘 이상이면 금리 문장 바로 뒤에 조건 문장을 이어 쓰고 같은 fact_id 를 단다.
7. 혜택을 쓰면 그 Fact 의 exceptions 도 쓴다(UNSATISFIED 는 제외). only_in 이 있으면 문장 끝에 "(only_in 값 기준)"을 붙인다.
고객 적용
8. user_input 값은 그대로 인용한다. 단위를 바꾸거나 계산하지 않는다.
9. 적용 여부는 judgment_results 의 state 만 따른다. condition 과 user_input 을 비교해 새로 판단하지 않는다.
10. state 별 문구:
  - SATISFIED: 가입전 → "입력하신 내용 기준으로 ○○ 조건에 해당합니다". 그 외 → "입력하신 내용 기준으로 적용됩니다".
  - UNSATISFIED: "입력하신 내용 기준으로는 적용되지 않습니다" + unmet_conditions 를 그대로. 비어 있으면 이유를 쓰지 않는다.
  - INFO_MISSING: "(condition)이면 (value unit)이 적용되는 조건입니다. 아래 질문에 답해 주시면 확인할 수 있습니다." 질문 자체는 문장에 쓰지 않는다.
  - BANK_CONFIRM_NEEDED: "은행 확인이 필요합니다" + 확인할 내용(해당 Fact 의 condition). 추측을 붙이지 않는다.
  - judgment 없음: 적용 여부를 말하지 않고 상품 내용만 쓴다.
선택·구성
11. 쓸 Fact: ① must_include 전부 ② 그 dependencies B ③ 그 exceptions ④ purpose 관련 Fact(문장이 8개를 넘지 않을 때만). ①~③ 은 빼지 않는다. 같은 내용을 두 번 쓰지 않는다.
12. 섹션은 section_order 순서, title 은 입력 그대로. Fact 는 자기 section_id 섹션에만 쓴다. 문장이 없는 섹션은 넣지 않는다.
13. 섹션 안 순서: UNSATISFIED → BANK_CONFIRM_NEEDED → INFO_MISSING → SATISFIED → 일반 정보. 같은 순위는 입력 순서.
문장
14. 끝까지 완결된 자연스러운 한국어로 쓴다. 원문 용어(결산일, 평균잔액, 우대금리 등)를 그대로 쓴다.
15. 한 문장에는 state 가 같은 Fact 만 쓴다.

[출력] `{`로 시작해 `}`로 끝나는 JSON 하나. ``` 를 쓰지 않는다. 비어 있으면 [].
{
 "sections": [{"title": "...", "sentences": [{"text": "...", "fact_ids": ["..."], "state": "SATISFIED|UNSATISFIED|INFO_MISSING|BANK_CONFIRM_NEEDED|NONE"}]}],
 "questions_for_user": [{"field": "...", "fact_ids": ["..."], "question": "..."}],
 "omitted_must_include": [{"fact_id": "...", "reason": "VALUE_TEXT_MISMATCH|AS_OF_MISSING|DUPLICATE_OF:<fact_id>"}]
}
state: 문장에 쓴 Fact 의 판정 state. 판정 없는 Fact 만 쓴 문장은 "NONE".
```
- 삭제된 출력 필드: `product`, `used_fact_ids` → 코드가 계산(C2, C5).
- 이 초안의 "문장 8개" 상한은 임의 값이다 — 팀이 "한 페이지" 기준(overview: 요약 약 5~6줄)과 맞춰 정할 것.

---

## I. 후속 확인이 필요한 것 (추측으로 남긴 부분)
1. 2-4 단계가 실제로 내보내는 candidate_facts / judgment_results 의 형태(condition 이 자연어인지 JSON 인지, missing_fields 원소 형태). → A4·A7·B4 의 심각도가 여기에 달림.
2. Qwen2.5-7B 가 평가 ID 괄호·코드펜스·value 정규화(3.50→3.5)를 실제로 일으키는 빈도 → 괄호 있음/없음 A/B 일치율 테스트.
3. system 길이를 줄였을 때(H 초안 vs v0.3) 규칙 준수율 차이 — 멘토의 "앞부분 손실" 지적 검증.
