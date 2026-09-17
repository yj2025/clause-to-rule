"""블라인드 실행 · 채점 (`blind_run.py` · `blind_score.py`).

팀원 노트북을 실행해 프롬프트와 평가 함수를 가져오므로, 노트북이 없는 곳에서는 그 시험을 건너뛴다.
"""

import pytest

import blind_run
import blind_score as S


def test_packets_are_the_43_blind_clauses():
    ps = blind_run.load_packets()
    assert len(ps) == 43
    assert not {"KBONE-S2-R04", "KBYY-S2-R11", "KBYY-S3-R04"} & {p["sample_id"] for p in ps}


@pytest.mark.skipif(not blind_run.NOTEBOOK.exists(), reason="팀원 노트북 없음")
def test_prompt_comes_from_the_notebook_verbatim():
    system, user = blind_run.team_prompt()
    assert system.startswith("You are a financial-document Semantic Rule Structurer")
    assert user("X") == "Structure the following Section Packet into semantic_rule_v1.1 JSON.\n\nX"


@pytest.mark.skipif(not S.NOTEBOOK.exists(), reason="팀원 노트북 없음")
def test_team_evaluator_matches_notebook_behaviour():
    extract_json, grounding_rate = S.team_evaluator()
    assert extract_json('앞말 {"status": "NO_EXECUTABLE_RULE"} 뒷말')[0] == {"status": "NO_EXECUTABLE_RULE"}
    # 팀원 grounding_rate 는 `surface` 값만 본다 — evidence 문장은 세지 않는다
    sem = {"rule_units": [{"evidence": [{"text": "없는 말"}],
                           "body": {"left": {"surface": "가 나"}, "right": {"surface": "없는 말"}}}]}
    assert grounding_rate(sem, "가나다") == 0.5
    assert grounding_rate({"status": "NO_EXECUTABLE_RULE"}, "가나다") == 1.0


def test_resume_refuses_different_conditions():
    a = {"_meta": {"model": "m", "model_revision": "r", "adapter_sha256": "x",
                   "notebook_sha256": "n", "packets_sha256": "p", "generation": {"max_new_tokens": 6144}}}
    b = {"_meta": {**a["_meta"], "adapter_sha256": "y"}}
    assert blind_run._same_conditions(a, a)
    assert not blind_run._same_conditions(a, b)


def test_shape_requires_v11_status_and_forms():
    assert S.shape_ok({"status": "NO_EXECUTABLE_RULE"})
    assert S.shape_ok({"status": "RULES_FOUND",
                       "rule_units": [{"form": "CONSTRAINT", "body": {}}]})
    # 기반 모델이 실제로 낸 모양 — v1.1 이 아니다
    assert not S.shape_ok({"status": "RULES_FOUND",
                           "rule_units": [{"id": "RULE_001", "type": "CONSTRAINT"}]})
    assert not S.shape_ok({"status": "RULES_FOUND", "rules": [{"rule_type": "CONSTRAINT"}]})
    assert not S.shape_ok({"status": "FOUND"})
    assert not S.shape_ok(None)


def test_rules_found_that_are_all_not_a_rule_count_as_empty():
    # 기본금리 · 거래 경로만 낸 RULES_FOUND 는 이 저장소 원칙으로 빈 배열이다
    assert S.declared_empty({"status": "RULES_FOUND"}, {"outcome": "NOT_A_RULE"}) is True
    assert S.declared_empty({"status": "RULES_FOUND"}, {"outcome": "NONE_CONVERTED"}) is False
    assert S.declared_empty({"status": "NO_EXECUTABLE_RULE"}, None) is True
    assert S.declared_empty({"status": "UNRESOLVED"}, None) is None
    assert S.declared_empty(None, None) is None
