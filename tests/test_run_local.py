import json

import pytest

import run_local_v2 as R


@pytest.mark.parametrize("raw,want", [
    ('{"rules": []}', {"rules": []}),
    ('```json\n{"rules": []}\n```', {"rules": []}),
    ('```\n{"rules": []}\n```', {"rules": []}),
    ('네, 결과입니다. {"rules": []} 이상입니다.', {"rules": []}),
    ('  \n {"rules": [{"rule_id": "R"}]}\n', {"rules": [{"rule_id": "R"}]}),
])
def test_parse_json_recovers(raw, want):
    assert R.parse_json(raw) == want


@pytest.mark.parametrize("raw", ["설명만 있음", "", "{", "}{", "{'rules': []}"])
def test_parse_json_gives_up_cleanly(raw):
    assert R.parse_json(raw) is None


def test_parse_json_takes_the_outermost_object():
    assert R.parse_json('{"rules": [{"a": {"b": 1}}]}') == {"rules": [{"a": {"b": 1}}]}


def test_gpu_mem_returns_three_numbers():
    got = R.gpu_mem()
    assert len(got) == 3 and all(isinstance(x, float) for x in got)


def test_gpu_mem_is_non_negative():
    assert all(x >= 0 for x in R.gpu_mem())


def test_marks_has_every_key():
    keys = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok", "empty", "n_rules")
    assert set(R._marks(None)) == set(keys)


def test_marks_of_none_is_all_false():
    assert not any(v for k, v in R._marks(None).items() if k != "n_rules")


def test_max_new_tokens_default():
    assert R.MAX_NEW_TOKENS == 3072
