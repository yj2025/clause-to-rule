#!/usr/bin/env python3
"""testcases/T1~T4(v0.3 입력)를 v0.4 입력으로 바꿔 testcases_v0.4/ 에 쓴다.

v0.4 에서 늘어난 필드(scenario · section_id · polarity · tax_basis · judgment 병합 ·
unmet_conditions · missing_fields 질문 · confirm_items)는 2-4 단계 코드가 채운다고 가정하고 여기서 손으로 채운다.
reason 은 내부 키 · 식이 들어 있어 모델 입력에서 뺀다. 내용(text · 수치 · state)은 v0.3 입력과 같다.

    python make_cases_v04.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent

# fact_id: (section_id, polarity, tax_basis)
META = {
    "T1": {"F101": ("s1", "혜택", "세전"), "F102": ("s1", "혜택", "세전"), "F103": ("s2", "혜택", None),
           "F104": ("s2", "혜택", None), "F105": ("s3", "제한", None), "F106": ("s4", "불이익", None),
           "F107": ("s3", "일반", None)},
    "T2": {"F201": ("s1", "혜택", "세전"), "F202": ("s2", "일반", None), "F203": ("s2", "일반", None),
           "F204": ("s3", "혜택", None), "F205": ("s3", "불이익", None), "F206": ("s4", "불이익", None),
           "F207": ("s2", "일반", None)},
    "T3": {"F301": ("s1", "혜택", None), "F302": ("s1", "불이익", None), "F303": ("s1", "혜택", None),
           "F304": ("s2", "제한", None), "F305": ("s3", "제한", None), "F306": ("s1", "혜택", "세전")},
    "T4": {"F401": ("s3", "제한", None), "F402": ("s1", "혜택", None), "F403": ("s1", "혜택", None),
           "F404": ("s2", "혜택", None), "F405": ("s4", "불이익", None), "F406": ("s2", "혜택", None),
           "F407": ("s3", "제한", None)},
}

# 코드가 만든다고 가정하는 고객용 질문 (missing_fields 원소별)
QUESTIONS = {
    "card_spend_monthly": "당행 신용·체크카드로 한 달에 얼마 정도 결제하시나요?",
    "purpose_doc_submitted": "금융거래목적 확인 서류를 제출하셨나요?",
    "has_other_bank_account": "본인 명의의 다른 금융기관 계좌가 있으신가요?",
    "marketing_consent": "마케팅 수신에 동의하실 예정인가요?",
    "no_deposit_history_1y": "최근 1년 동안 이 은행에 예금을 보유한 적이 없으신가요?",
    "salary_transfer": "이 적금의 출금계좌로 급여이체를 하실 예정인가요?",
    "auto_transfer": "매월 자동이체로 납입하실 예정인가요?",
}

# UNSATISFIED 의 모자란 조건 · BANK_CONFIRM_NEEDED 의 확인할 것
UNMET = {
    "F301": ["전월 급여이체 50만원 이상", "전월 당행 카드 결제실적 30만원 이상"],
    "F401": ["만 19세 이상 만 34세 이하"],
}
CONFIRM = {"F204": ["전 금융기관 비과세종합저축 원금 합계(한도 5,000만원 중 남은 금액)"]}


def convert(name: str, case: dict) -> dict:
    titles = case["section_order"]
    sid = {t: f"s{i + 1}" for i, t in enumerate(titles)}
    judg = {j["fact_id"]: j for j in case["judgment_results"]}
    facts = []
    for f in case["candidate_facts"]:
        sec, pol, tax = META[name][f["fact_id"]]
        j = judg.get(f["fact_id"])
        nf = {"fact_id": f["fact_id"], "section_id": sec, "key": f["key"], "polarity": pol, "text": f["text"],
              "value": f["value"], "unit": f["unit"], "tax_basis": tax, "condition": f["condition"],
              "exceptions": f["exceptions"], "only_in": f["only_in"], "as_of": f["as_of"], "judgment": None}
        if j:
            nf["judgment"] = {
                "state": j["state"],
                "unmet_conditions": UNMET.get(f["fact_id"], []) if j["state"] == "UNSATISFIED" else [],
                "missing_fields": [{"field": m, "question": QUESTIONS[m]} for m in j["missing_fields"]],
                "confirm_items": CONFIRM.get(f["fact_id"], []) if j["state"] == "BANK_CONFIRM_NEEDED" else [],
            }
        facts.append(nf)
    assert set(sid.values()) >= {m[0] for m in META[name].values()}
    return {
        "scenario": "가입전",
        "product": case["product"],
        "purpose": case["purpose"],
        "user_input": case["user_input"],
        "section_order": [{"section_id": sid[t], "title": t} for t in titles],
        "candidate_facts": facts,
        "must_include_fact_ids": case["must_include_fact_ids"],
        "dependencies": case["dependencies"],
    }


def main():
    out = HERE / "testcases_v0.4"
    out.mkdir(exist_ok=True)
    for p in sorted((HERE / "testcases").glob("T*.json")):
        case = json.loads(p.read_text(encoding="utf-8"))
        (out / p.name).write_text(json.dumps(convert(p.stem, case), ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", out / p.name)


if __name__ == "__main__":
    main()
