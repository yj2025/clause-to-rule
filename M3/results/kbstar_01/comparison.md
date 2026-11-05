# 금융상품 약관 요약 비교

모든 모델에 같은 원문 구간과 지시문을 사용했습니다.
분할 실행이면 각 구간의 요약을 비교합니다. 통합 요약은 생성하지 않습니다.

## google/gemma-4-12B-it

### 원문 구간 1

```json
{
  "product_id": 9,
  "product_name": "KB스타통장",
  "items": [
    {
      "key": "product_name",
      "summary": "KB스타통장",
      "source_section_ids": [3151]
    },
    {
      "key": "product_type",
      "summary": "보통예금, 저축예금",
      "source_section_ids": [1151, 3156]
    },
    {
      "key": "product_feature",
      "summary": "‘소득이 있는 누구나’ 혜택을 받을 수 있는 통장",
      "source_section_ids": [3152]
    },
    {
      "key": "eligibility_target",
      "summary": "금융실명거래 및 비밀보장에 관한 법률에 따라 실명이 확인된 개인",
      "conditions": [
        {
          "text": "1인 당 1개의 통장만 개설할 수 있습니다.",
          "src": [1150]
        },
        {
          "text": "실명의 개인(1 인 1 계좌)",
          "src": [3154]
        }
      ],
      "exceptions": [
        {
          "text": "개인사업자 및 관련서류 미제출 임의단체 포함",
          "src": [3154],
          "only_in": "상품설명서"
        },
        {
          "text": "공동명의 가입 불가",
          "src": [3154],
          "only_in": "상품설명서"
        }
      ],
      "source_section_ids": [1150, 3154]
    },
    {
      "key": "eligibility_restriction",
      "summary": "공동명의 가입 불가",
      "exceptions": [
        {
          "text": "개인사업자 및 관련서류 미제출 임의단체 포함",
          "src": [3154],
          "only_in": "상품설명서"
        },
        {
          "text": "공동명의 가입 불가",
          "src": [3154],
          "only_in": "상품설명서"
        }
      ],
      "source_section_ids": [3154]
    },
    {
      "key": "account_limit",
      "summary": "1인 1계좌만 가입 가능",
      "exceptions": [
        {
          "text": "공동명의로 가입할 수 없습니다.",
          "src": [3174],
          "only_in": "상품설명서"
        }
      ],
      "source_section_ids": [3174]
    },
    {
      "key": "deposit_amount",
      "summary": "제한없음",
      "source_section_ids": [3155]
    },
    {
      "key": "base_rate",
      "summary": "연 0.10% (2025.12.05. 기준, 세금공제 전)",
      "conditions": [
        {
          "text": "결산일 현재 영업점에 고시한 예금과목별 기본이율 적용",
          "src": [3157]
        }
      ],
      "as_of": "2025.12.05.",
      "source_section_ids": [3157]
    },
    {
      "key": "interest_payment",
      "summary": "보통예금은 매년 6, 12월 둘째 금요일, 저축예금은 매년 2, 5, 8, 11월 둘째 금요일에 결산하여 다음날 원금에 가산",
      "exceptions": [
        {
          "text": "예금의 이자는 최종거래일로부터 5년이 경과한 날부터는 이자를 원금에 더하지 않고, 계좌해지 또는 추가 입출금 거래 발생일에 일괄 계산하여 지급할 수 있습니다.",
          "src": [3158]
        }
      ],
      "source_section_ids": [3158]
    },
    {
      "key": "termination_method",
      "summary": "영업점, 개인인터넷뱅킹, KB 스타뱅킹을 통해 해지 가능",
      "conditions": [
        {
          "text": "개인인터넷뱅킹, KB 스타뱅뱅킹을 통한 해지 시 해지잔액을 입금할 수 있는 본인명의의 입출금이자유로운예금 계좌가 필요합니다.",
          "src": [3166]
        }
      ],
      "source_section_ids": [3166]
    },
    {
      "key": "tax",
      "summary": "비과세종합저축으로 가입가능",
      "conditions": [
        {
          "text": "관련세법이 개정될 경우 세율이 변경되거나 세금이 부과될 수 있음",
          "src": [3164]
        }
      ],
      "source_section_ids": [3164]
    },
    {
      "key": "transaction_restriction",
      "summary": "잔액 및 거래 기간에 따라 입출금, 잔액조회, 이관 등의 거래 제한",
      "conditions": [
        {
          "text": "예금잔액이 10,000원 미만이며, 1년이상 입출금거래가 없는 계좌",
          "src": [3170]
        },
        {
          "text": "예금잔액이 10,000원 이상 50,000원 미만이며, 2년이상 입출금거래가 없는 계좌",
          "src": [3170]
        },
        {
          "text": "예금잔액이 50,000원 이상 100,000원 미만이며, 3년이상 입출금거래가 없는 계좌",
          "src": [3170]
        },
        {
          "text": "무거래기간 산정기준 : 입출금 거래 또는 명의변경 거래 최종 발생일로 부터 산정",
          "src": [3170]
        },
        {
          "text": "편입시기 : 연2회(매년 6월, 12월 셋째 금요일 기준으로 익일인 토요일에 편입)",
          "src": [3170]
        },
        {
          "text": "거래를 다시 시작하고자 하는 경우에는 본인 확인 및 금융거래 목적을 확인 한 후 가능",
          "src": [3170]
        }
      ],
      "source_section_ids": [3170]
    },
    {
      "key": "fee",
      "summary": "특정 조건 충족 시 인터넷/폰/모바일뱅킹 타행 이체수수료, 납부자 자동이체 수수료, 자동화기기 타행 이체/시간외 출금수수료, 타행 자동화기기 출금수수료 면제",
      "benefit": "수수료 면제",
      "conditions": [
        {
          "text": "전월(1일~말일) 중 합산 50만원 이상 입금 이력이 있는 경우",
          "exceptions": [
            {
              "text": "당행 본인 명의 계좌에서 이체된 건 및 본인의 주민등록번호로 입금된 건 제외",
              "src": [1153]
            }
          ],
          "src": [1153]
        },
        {
          "text": "KB 리브 모바일(KB Liiv M) 자동이체 출금 이력이 있는 경우",
          "exceptions": [
            {
              "text": "체크카드 및 신용카드를 통해 출금된 건 제외",
              "src": [1153]
            }
          ],
          "src": [1153]
        },
        {
          "text": "전월(1일~말일) 중 아래 실적 중 1가지 이상 충족한 경우",
          "src": [3160]
        },
        {
          "text": "합산 50만원 이상 입금 이력이 있는 경우",
          "exceptions": [
            {
              "text": "당행 본인 명의 계좌에서 이체된 건 및 본인의 주민등록번호로 입금된 건 제외",
              "src": [3160]
            },
            {
              "text": "당행 오픈뱅킹을 통해 타금융기관에서 이체된 건 제외",
              "src": [3160]
            },
            {
              "text": "결산이자 입금 건 제외",
              "src": [3160]
            }
          ],
          "src": [3160]
        },
        {
          "text": "KB 리브 모바일(KB Liiv M) 자동이체 출금 이력이 있는 경우",
          "exceptions": [
            {
              "text": "체크카드 및 신용카드를 통해 출금된 건 제외",
              "src": [3160]
            }
          ],
          "src": [3160]
        }
      ],
      "condition_logic": "하나만 충족",
      "exceptions": [
        {
          "text": "이번달 11일 ~ 다음달 10일",
          "src": [1154]
        },
        {
          "text": "이 통장의 신규(또는 전환)일부터 다음 다음 달 10일까지는 은행 거래실적에 관계없이 면제",
          "src": [1154]
        },
        {
          "text": "다른은행 자동화기기의 경우 제휴 ATM 및 VAN사(효성·나이스·한네트 등) 자동화기기 제외",
          "src": [1156],
          "only_in": "상품설명서"
        }
      ],
      "special": {
        "text": "면제 횟수: 제한없음",
        "src": [1155]
      },
      "source_section_ids": [1153, 1154, 1155, 1156, 3160]
    },
    {
      "key": "assignment_collateral",
      "summary": "양도 가능, 담보제공 불가능",
      "source_section_ids": [3167, 3168]
    },
    {
      "key": "partner_benefit",
      "summary": "인컴박스 서비스: 다양한 출처의 불규칙한 입금 거래를 한 눈에 확인할 수 있는 입금관리 서비스",
      "conditions": [
        {
          "text": "인컴박스별로 입금 적요(보낸 사람)을 키워드로 설정 (박스 별 키워드는 3개까지 설정 가능)",
          "src": [3161]
        },
        {
          "text": "계좌별 인컴박스는 3개까지 설정 가능.",
          "src": [3161]
        }
      ],
      "special": {
        "text": "이용 경로 : KB스타뱅킹 앱 > 전체계좌조회 > KB스타통장 계좌 하단 [인컴박스]",
        "src": [3161]
      },
      "source_section_ids": [3161]
    },
    {
      "key": "transaction_restriction",
      "summary": "피해의심 거래계좌 및 사기이용 계좌로 이용될 경우 이체, 송금지연, 지급정지 등의 금융거래 제한조치 가능",
      "source_section_ids": [3174]
    }
  ]
}
```

## Qwen/Qwen3-8B

### 원문 구간 1

{
  "product_id": 9,
  "product_name": "KB스타통장",
  "items": [
    {
      "key": "product_type",
      "summary": "보통예금, 저축예금으로 가입 가능",
      "benefit": "입출금 자유로운 예금",
      "conditions": [
        {
          "text": "1인 1계좌로 가입 가능",
          "user_input": "개인 여부",
          "src": [1150, 3154],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "동일 예금과목 상품 전환 가능",
        "src": [3156]
      },
      "as_of": "2025.12.05",
      "doc_diff": "특약과 상품설명서 모두 포함",
      "note": "상품유형은 보통예금, 저축예금으로 구성됨"
    },
    {
      "key": "product_feature",
      "summary": "소득이 있는 누구나 혜택을 받을 수 있는 통장",
      "benefit": "소득이 있는 고객 대상 혜택",
      "conditions": [],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "소득이 있는 고객 대상 혜택",
        "src": [3152]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "상품특징은 소득이 있는 고객 대상 혜택"
    },
    {
      "key": "eligibility_target",
      "summary": "실명의 개인(1인 1계좌)",
      "benefit": "개인 및 개인사업자 포함",
      "conditions": [
        {
          "text": "실명의 개인(1인 1계좌)",
          "user_input": "개인 여부",
          "src": [1150, 3154],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "개인사업자 및 관련서류 미제출 임의단체 포함",
        "src": [3154]
      },
      "as_of": "",
      "doc_diff": "특약과 상품설명서 모두 포함",
      "note": "가입대상은 실명의 개인(1인 1계좌)"
    },
    {
      "key": "eligibility_restriction",
      "summary": "1인 1계좌, 공동명의 불가",
      "benefit": "공동명의 가입 불가",
      "conditions": [
        {
          "text": "1인 1계좌로 가입 가능",
          "user_input": "개인 여부",
          "src": [1150, 3154],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [
        {
          "text": "피해의심 거래계좌 및 사기이용 계좌로 이용될 경우 거래 제한",
          "src": [3174],
          "only_in": "상품설명서"
        }
      ],
      "special": {
        "text": "1인 1계좌로 가입 가능",
        "src": [3154]
      },
      "as_of": "",
      "doc_diff": "특약과 상품설명서 모두 포함",
      "note": "가입제한사항은 1인 1계좌, 공동명의 불가"
    },
    {
      "key": "account_limit",
      "summary": "1인 1계좌로 가입 가능",
      "benefit": "공동명의 가입 불가",
      "conditions": [
        {
          "text": "1인 1계좌로 가입 가능",
          "user_input": "개인 여부",
          "src": [1150, 3154],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "1인 1계좌로 가입 가능",
        "src": [3154]
      },
      "as_of": "",
      "doc_diff": "특약과 상품설명서 모두 포함",
      "note": "계좌수 제한은 1인 1계좌로 가입 가능"
    },
    {
      "key": "deposit_amount",
      "summary": "신규금액 제한 없음",
      "benefit": "최소 입금금액 없음",
      "conditions": [],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "신규금액 제한 없음",
        "src": [3155]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "신규금액은 제한 없음"
    },
    {
      "key": "base_rate",
      "summary": "기본이율 연 0.10%",
      "benefit": "연 0.10% 기본이율 적용",
      "conditions": [],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "기본이율은 결산일 현재 영업점에 고시한 예금과목별 기본이율 적용",
        "src": [3157]
      },
      "as_of": "2025.12.05",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "기본이율은 연 0.10%로 적용"
    },
    {
      "key": "interest_payment",
      "summary": "이자지급시기 및 방식",
      "benefit": "매년 특정 시점에 이자가 결산됨",
      "conditions": [
        {
          "text": "보통예금: 매년 6, 12월 둘째 금요일 결산",
          "user_input": "",
          "src": [3158],
          "only_in": "상품설명서"
        },
        {
          "text": "저축예금: 매년 2, 5, 8, 11월 둘째 금요일 결산",
          "user_input": "",
          "src": [3158],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [
        {
          "text": "최종거래일로부터 5년이 경과한 날부터는 이자를 원금에 더하지 않고, 계좌해지 또는 추가 입출금 거래 발생일에 일괄 계산하여 지급",
          "src": [3158],
          "only_in": "상품설명서"
        }
      ],
      "special": {
        "text": "이자지급시기 및 방식",
        "src": [3158]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "이자지급시기는 예금과목에 따라 달라짐"
    },
    {
      "key": "termination_method",
      "summary": "계약해지 방법",
      "benefit": "영업점, 개인인터넷뱅킹, KB 스타뱅킹을 통해 해지 가능",
      "conditions": [
        {
          "text": "해지잔액을 입금할 수 있는 본인명의의 입출금이자유로운예금 계좌가 필요",
          "user_input": "계좌 여부",
          "src": [3166],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "해지 방법은 영업점, 개인인터넷뱅킹, KB 스타뱅킹을 통해 가능",
        "src": [3166]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "계약해지 방법은 영업점, 개인인터넷뱅킹, KB 스타뱅킹을 통해 가능"
    },
    {
      "key": "tax",
      "summary": "세제관련",
      "benefit": "비과세종합저축으로 가입 가능",
      "conditions": [],
      "condition_logic": "모두 충족",
      "exceptions": [
        {
          "text": "관련세법이 개정될 경우 세율이 변경되거나 세금이 부과될 수 있음",
          "src": [3164],
          "only_in": "상품설명서"
        }
      ],
      "special": {
        "text": "비과세종합저축으로 가입 가능",
        "src": [3164]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "세제관련은 비과세종합저축으로 가입 가능"
    },
    {
      "key": "transaction_restriction",
      "summary": "거래중지 조건",
      "benefit": "무거래 계좌에 대해 거래 제한",
      "conditions": [
        {
          "text": "예금잔액이 10,000원 미만이며, 1년 이상 입출금거래가 없는 계좌",
          "user_input": "잔액 및 거래 기록",
          "src": [3170],
          "only_in": "상품설명서"
        },
        {
          "text": "예금잔액이 10,000원 이상 50,000원 미만이며, 2년 이상 입출금거래가 없는 계좌",
          "user_input": "잔액 및 거래 기록",
          "src": [3170],
          "only_in": "상품설명서"
        },
        {
          "text": "예금잔액이 50,000원 이상 100,000원 미만이며, 3년 이상 입출금거래가 없는 계좌",
          "user_input": "잔액 및 거래 기록",
          "src": [3170],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "무거래기간 산정기준: 입출금 거래 또는 명의변경 거래 최종 발생일로 부터 산정",
        "src": [3170]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "거래중지 조건은 잔액 및 거래 기록에 따라 달라짐"
    },
    {
      "key": "fee",
      "summary": "수수료면제 혜택",
      "benefit": "이체수수료, 자동이체수수료 면제",
      "conditions": [
        {
          "text": "전월(1일~말일) 중 이 통장에서 아래 실적 중 하나 이상 발생된 경우",
          "user_input": "실적 확인",
          "src": [1153, 3160],
          "only_in": "특약, 상품설명서"
        },
        {
          "text": "이 통장의 신규(또는 전환)일부터 다음 다음 달 10일까지는 은행 거래실적에 관계없이 면제",
          "user_input": "신규일 확인",
          "src": [1154, 3160],
          "only_in": "특약, 상품설명서"
        },
        {
          "text": "수수료 면제 횟수: 제한없음",
          "user_input": "",
          "src": [1155, 3160],
          "only_in": "특약, 상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [
        {
          "text": "당행 본인 명의 계좌에서 이체된 건 및 본인의 주민등록번호로 입금된 건 제외",
          "src": [1153, 3160],
          "only_in": "특약, 상품설명서"
        },
        {
          "text": "체크카드 및 신용카드를 통해 출금된 건 제외",
          "src": [1153, 3160],
          "only_in": "특약, 상품설명서"
        },
        {
          "text": "결산이자 입금 건 제외",
          "src": [3160],
          "only_in": "상품설명서"
        }
      ],
      "special": {
        "text": "수수료 면제 대상: 이체수수료, 자동이체수수료 등",
        "src": [1153, 1155, 1156, 3160]
      },
      "as_of": "",
      "doc_diff": "특약과 상품설명서 모두 포함",
      "note": "수수료면제 혜택은 실적 및 신규일에 따라 달라짐"
    },
    {
      "key": "assignment_collateral",
      "summary": "양도 및 담보제공",
      "benefit": "양도 가능, 담보제공 불가능",
      "conditions": [
        {
          "text": "질권설정 불가",
          "user_input": "",
          "src": [3167],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "양도 가능, 담보제공 불가능",
        "src": [3168]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "양도 가능, 담보제공 불가능"
    },
    {
      "key": "partner_benefit",
      "summary": "인컴박스 서비스",
      "benefit": "입금 관리 서비스 제공",
      "conditions": [
        {
          "text": "인컴박스별로 입금 적요(보낸 사람)를 키워드로 설정",
          "user_input": "키워드 설정 여부",
          "src": [3161],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "인컴박스 서비스 이용 경로: KB스타뱅킹 앱",
        "src": [3161]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "인컴박스 서비스는 입금 관리 서비스 제공"
    },
    {
      "key": "product_conversion",
      "summary": "상품·계좌 전환",
      "benefit": "동일 예금과목 상품 전환 가능",
      "conditions": [
        {
          "text": "개별상품에서 정한 기준에 의해 전환신규가 불가한 상품은 제외",
          "user_input": "전환 가능 여부",
          "src": [3156],
          "only_in": "상품설명서"
        }
      ],
      "condition_logic": "모두 충족",
      "exceptions": [],
      "special": {
        "text": "동일 예금과목 상품 전환 가능",
        "src": [3156]
      },
      "as_of": "",
      "doc_diff": "상품설명서에만 포함됨",
      "note": "상품·계좌 전환은 동일 예금과목 상품 전환 가능"
    }
  ]
}
