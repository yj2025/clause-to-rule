"""v127 — 빈 배열의 이유를 조문 머리말로 (2026-10-06)."""
import json
from pathlib import Path

import reasons


def test_head_is_read_from_the_first_bracket():
    assert reasons.head_of("[기본이율 (2025.01.13기준)]\n▪ 연 0.10%") == "기본이율 (2025.01.13기준)"
    assert reasons.head_of("머리말 없음") == ""


def test_each_reason_from_its_head():
    assert reasons.classify("[상품 개요]\n상 품 명 : X") == "SUMMARY"
    assert reasons.classify("[상품유형]\n▪ 정기예금") == "LABEL"
    assert reasons.classify("[최종금리 (세금공제 전)]\n▪ 최저 연 0.1%") == "PRODUCT_SETTING"
    assert reasons.classify("[신규금액]\n▪ 제한없음") == "PRODUCT_SETTING"
    assert reasons.classify("[거래방법]\n▪ 신규 : 지점 방문") == "NOTE_ONLY"


def test_only_an_empty_array_gets_a_reason():
    out = {"rules": [{"rule_id": "R1"}]}
    assert reasons.tag_empty(out, "[상품유형]") == (out, None)
    assert reasons.tag_empty(None, "[상품유형]") == (None, None)
    new, why = reasons.tag_empty({"rules": []}, "[상품유형]\n▪ 정기예금")
    assert why == "LABEL" and new == {"rules": [], "no_rule_reason": "LABEL"}


def test_it_agrees_with_every_empty_gold():
    """정답 48조문(코퍼스 12 · kb10 36)과 같다 — 정답의 이유도 Claude 가 붙였으니 독립 검증은 아니다(회귀 방지용)."""
    texts = {c["id"]: c["text"] for c in json.loads(Path("data/corpus.json").read_text("utf-8"))}
    texts.update({c["id"]: c["text"] for c in json.loads(Path("showcase/clauses_key.json").read_text("utf-8"))})
    bad = []
    for p in [*Path("data/gold").glob("K*.json"), *Path("showcase/gold_draft").glob("K*.json")]:
        g = json.loads(p.read_text("utf-8"))
        if not g.get("rules") and reasons.classify(texts[g["clause_id"]]) != g["no_rule_reason"]:
            bad.append(g["clause_id"])
    assert bad == []
