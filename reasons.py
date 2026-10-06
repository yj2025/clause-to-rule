"""빈 배열의 이유를 조문 머리말로 정한다 (2026-10-06 · v127).

모델에게 `no_rule_reason` 을 내라고 하자(v125) 기권이 줄고 코퍼스 ⑦ 이 −4.3p 흔들렸다 — 예시 출력에 키 하나를 더한 것도
«예시 자리를 건드린» 것이었다. 그래서 이유는 모델이 아니라 **러너가 고른 출력에** 붙인다. 모델이 rules 를 빈 배열로 냈을 때만,
조문 머리말([상품 개요] · [상품유형] · [기본이율] …)로 넷 중 하나를 고른다. 지문 · 예시는 한 글자도 안 바뀐다.

머리말만 본다. 본문을 읽고 판단하는 것은 모델의 일이고, 여기는 «왜 비었나»를 사람이 읽을 수 있게 남기는 꼬리표다.
"""
import re

from schema import NO_RULE_REASONS

_HEAD = re.compile(r"^\s*\[([^\]]+)\]")

# 머리말에 이 말이 있으면 — 위에서부터 먼저 맞는 것
_RULES = (
    ("SUMMARY", ("상품 개요", "상품개요")),
    ("LABEL", ("상품유형",)),
    ("PRODUCT_SETTING", ("기본이율", "기본금리", "최종이율", "최종금리", "신규금액", "판매한도")),
)


def head_of(text):
    """조문의 첫 [머리말]. 없으면 빈 문자열."""
    m = _HEAD.match(text or "")
    return m.group(1) if m else ""


def classify(text):
    """조문 → 넷 중 하나. 머리말이 위 어디에도 안 맞으면 안내(NOTE_ONLY)다 —
    거래방법 · 해지방법 · 가입절차 · 통지 · 정의 · 표가 다른 조문에 있는 이율 조문."""
    head = head_of(text).replace(" ", "")
    for reason, words in _RULES:
        if any(w.replace(" ", "") in head for w in words):
            return reason
    return "NOTE_ONLY"


def tag_empty(output, clause_text):
    """(바꾼 출력, 붙인 이유 또는 None). rules 가 빈 배열일 때만 붙인다. 입력은 건드리지 않는다."""
    if not isinstance(output, dict) or output.get("rules") != []:
        return output, None
    reason = classify(clause_text)
    assert reason in NO_RULE_REASONS
    return {**output, "no_rule_reason": reason}, reason
