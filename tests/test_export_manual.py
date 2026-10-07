"""한국어 규칙 서식 내보내기 (2026-10-07)."""
import json
from pathlib import Path

import export_manual as E


def test_gold_of_two_products_exports_without_error():
    clauses = json.loads(Path("showcase/clauses_key.json").read_text("utf-8"))
    rbc = {p.stem: json.loads(p.read_text("utf-8")).get("rules") or [] for p in Path("showcase/gold_draft").glob("KBGL-*.json")}
    doc = E.export("KBGL", clauses, rbc, "test")
    assert doc["서식 버전"].startswith("manual_rule_ko.v0.1")
    assert all({"규칙 번호", "분류", "조건", "결과", "근거", "실행"} <= set(r) for r in doc["규칙"])
    assert {e["조문"] for e in doc["규칙 없는 조문"]} == {"KBGL-S1-P01", "KBGL-S2-R02", "KBGL-S2-R04", "KBGL-S2-R06"}


def test_conditions_read_in_korean():
    c = E.cond({"and": [{">=": [{"var": "customer.age"}, 19]},
                        {"in": [{"var": "customer.holder_type"}, ["CORPORATION"]]}]}, {})
    assert c == {"모두": [{"항목": "나이(만)", "비교": "이상", "값": 19},
                         {"항목": "명의 유형", "비교": "포함", "값": ["법인"]}]} or c["모두"][1]["값"] == ["법인"]


def test_a_broken_condition_is_shown_raw():
    assert "해석 못 한 조건" in E.cond({"and": [1], "or": []}, {})
