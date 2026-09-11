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


# ── 자기수정 루프가 결과를 망가뜨리지 않는다 ────────────────────────────
import run_local_v2 as R


def _m(**kw):
    base = dict(json_ok=False, schema_ok=False, catalog_ok=False,
                quote_ok=False, exec_ok=False)
    base.update(kw)
    return base


def test_score_of_counts_gates():
    assert R._score_of(_m(json_ok=True, schema_ok=True)) == 2


def test_score_of_none_is_zero():
    assert R._score_of(None) == 0


def test_score_of_all_gates():
    assert R._score_of(_m(**{k: True for k in R.GATES})) == 5


def test_gates_match_the_validator():
    from validate import score_record
    marks = score_record({"rules": []}, "조문")
    assert all(k in marks for k in R.GATES)


class _FakeTok:
    def apply_chat_template(self, conv, **kw):
        return "x"

    def __call__(self, text, **kw):
        return {"input_ids": [[0]]}


def _run_with(outputs, monkeypatch, clause_text="만 19세 미만"):
    """_generate 가 정해진 출력을 차례로 내도록 바꿔 끼운다."""
    seq = list(outputs)

    def fake(tok, model, user, temperature, max_new_tokens):
        return (seq.pop(0), False)

    monkeypatch.setattr(R, "_generate", fake)
    clause = {"id": "T-01", "text": clause_text}
    return R.run_clause(None, None, clause, runs=1)[0]


GOOD = ('{"rules": [{"rule_id": "R", "status": "OK", '
        '"source": {"quote": "만 19세 미만"}, '
        '"condition": {"<": [{"var": "customer.age"}, 19]}, '
        '"effect": {"type": "DISQUALIFY"}}]}')
BROKEN = '{"rules": [{"rule_id": "R"'          # 파싱 실패
WEAK = '{"rules": [{"rule_id": "R", "source": {"quote": "없는 문장"}, ' \
       '"condition": {}, "effect": {"type": "DISQUALIFY"}}]}'


def test_a_good_first_attempt_stops_the_loop(monkeypatch):
    r = _run_with([GOOD, BROKEN], monkeypatch)
    assert r["n_attempts"] == 1 and r["final"]["exec_ok"]


def test_a_worse_retry_is_not_accepted(monkeypatch):
    # 1차가 4관문, 재시도가 파싱 실패 — 1차를 낸다
    r = _run_with([WEAK, BROKEN, BROKEN], monkeypatch)
    assert r["final"]["json_ok"] is True
    assert r["n_best"] == 1


def test_a_better_retry_is_accepted(monkeypatch):
    r = _run_with([WEAK, GOOD], monkeypatch)
    assert r["final"]["quote_ok"] is True and r["n_best"] == 2


def test_a_tie_keeps_the_earlier_attempt(monkeypatch):
    # 같은 관문 수면 앞의 것을 쓴다 — 재시도가 포기 선언으로 갈아타는 것을 막는다
    r = _run_with([WEAK, WEAK, WEAK], monkeypatch)
    assert r["n_best"] == 1


def test_first_is_always_the_first_attempt(monkeypatch):
    r = _run_with([WEAK, GOOD], monkeypatch)
    assert r["first"]["quote_ok"] is False and r["final"]["quote_ok"] is True


def test_raw_first_and_last_are_both_kept(monkeypatch):
    r = _run_with([WEAK, GOOD], monkeypatch)
    assert r["raw_first"] == WEAK and r["raw_last"] == GOOD


def test_retry_can_never_lose_a_gate(monkeypatch):
    for seq in ([GOOD, BROKEN], [WEAK, BROKEN, BROKEN], [WEAK, WEAK, BROKEN]):
        r = _run_with(list(seq), monkeypatch)
        assert R._score_of(r["final"]) >= R._score_of(r["first"])
