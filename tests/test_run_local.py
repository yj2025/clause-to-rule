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
    assert R._score_of(_m(json_ok=True, schema_ok=True))[0] == 2


def test_score_of_none_is_zero():
    assert R._score_of(None)[0] == 0


def test_score_of_all_gates():
    assert R._score_of(_m(**{k: True for k in R.GATES}))[0] == 5


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
        assert R._score_of(r["final"])[0] >= R._score_of(r["first"])[0]


# ── v13: 관문 수가 같으면 오류가 적은 쪽 ────────────────────────────────
def test_score_is_a_pair():
    assert isinstance(R._score_of(_m(json_ok=True)), tuple)


def test_more_gates_beats_fewer_errors():
    a = R._score_of({**_m(json_ok=True, schema_ok=True), "errors": ["e"] * 9})
    b = R._score_of({**_m(json_ok=True), "errors": []})
    assert a > b


def test_fewer_errors_wins_a_gate_tie():
    """v12 에서 막혔던 자리 — 고쳤는데 관문 수가 같아 채택이 안 됐다."""
    a = R._score_of({**_m(json_ok=True), "errors": ["e", "e", "e"]})
    b = R._score_of({**_m(json_ok=True), "errors": ["e"]})
    assert b > a


def test_none_scores_lowest():
    assert R._score_of(None)[0] <= R._score_of(_m())[0]


def test_a_retry_that_only_reduces_errors_is_accepted(monkeypatch):
    # 관문 수는 같고 오류만 준 재시도가 채택된다
    WORSE = ('{"rules": [{"rule_id": "R", "source": {"quote": "없는 문장"}, '
             '"condition": {"nope": 1}, "effect": {"type": "GIVE_GIFT"}}]}')
    BETTER = ('{"rules": [{"rule_id": "R", "source": {"quote": "없는 문장"}, '
              '"condition": {}, "effect": {"type": "DISQUALIFY"}}]}')
    r = _run_with([WORSE, BETTER, BETTER], monkeypatch)
    assert r["n_best"] == 2


def test_a_swap_that_raises_the_total_is_accepted(monkeypatch):
    """관문을 하나 잃고 둘을 얻으면 채택된다 — 총수만 보장된다.

    v13 판정에서 "재시도 회귀가 구조적으로 0" 이라고 적은 것은 틀렸다.
    v16(3회차)에서 5건이 이 형태로 개별 관문을 잃었다.
    """
    a = _m(json_ok=True, schema_ok=True, quote_ok=True)          # 3관문
    b = _m(json_ok=True, schema_ok=True, catalog_ok=True, exec_ok=True)  # 4관문, quote 잃음
    assert R._score_of(b) > R._score_of(a)
    assert a["quote_ok"] and not b["quote_ok"]


def test_every_record_says_what_made_it():
    """결과 파일만 보고 어느 지문·예시·카탈로그로 돌렸는지 알 수 있어야 한다.

    v22 를 되돌린 뒤 '지금 지문이 v19 와 같나' 를 확인하려고 git 에서
    커밋을 찾아 파일을 풀어 대조해야 했다. 셋을 따로 세므로
    하나만 바뀌어도 어느 쪽인지 보인다.
    """
    import run_local_v2 as R
    fp = R.prompt_fingerprint()
    # vocab 은 2026-09-15 에 더했다 — 확장 여섯의 대상 목록·속성이 catalog 해시에 안 잡혔다
    # validator 는 2026-09-16 에 더했다 — 아래 시험이 이유다
    # retry 는 2026-09-24 에 더했다 — v46 이 재시도 지문을 바꿨는데 해시가 v41 과
    # 같았다. 처방 전후가 구별이 안 됐다 (`tests/test_fingerprint.py`)
    # triggers 는 2026-09-28 에 더했다 — 조건부 블록을 어느 조문에 붙일지 정하는
    # 방아쇠가 catalog.py 에 있는데 안 세고 있었다. v36↔v37 · v38↔v39 가
    # 구별되지 않았다. **이 시험은 키 목록만 보므로 구멍을 못 잡는다** —
    # 파일을 실제로 건드려 보는 것은 `tests/test_fingerprint.py` 다
    # runner 는 2026-09-30 에 더했다 — 재시도 루프(`run_clause`)가 이 파일에 있는데
    # 안 세고 있었다. 그 루프만 바꾸는 처방을 준비하다 봤다
    assert set(fp) == {"system", "fewshots", "n_fewshots", "catalog", "schema",
                       "vocab", "validator", "retry", "triggers", "runner"}
    assert fp["n_fewshots"] == 4
    assert all(isinstance(fp[k], str) and len(fp[k]) == 12
               for k in ("system", "fewshots", "catalog", "schema", "vocab",
                         "validator"))


def test_the_fingerprint_moves_when_the_validator_moves(tmp_path, monkeypatch):
    """**검증기도 출력을 바꾼다.** 스키마와 같은 이유다.

    검증기가 바뀌면 재시도에 되먹이는 오류 문구가 바뀌고, 그래서 생성물이
    바뀐다 — v24 에서 채택된 시도의 절반이 재시도 결과다.

    v25 에서 물릴 뻔했다. 지문·예시·카탈로그·스키마·어휘를 하나도 안 건드리고
    ③ 만 좁히는 라운드라, 이 키가 없으면 v24 와 해시가 **완전히 같아** 두 라운드를
    구별할 수 없다. v23 에서 스키마를 빠뜨려 똑같이 물렸던 자리다.
    """
    import run_local_v2 as R
    from pathlib import Path
    src = Path(R.__file__).parent / "validate.py"
    before = R.prompt_fingerprint()["validator"]
    original = src.read_text("utf-8")
    try:
        src.write_text(original + "\n# 한 줄 더\n", "utf-8")
        assert R.prompt_fingerprint()["validator"] != before
    finally:
        src.write_text(original, "utf-8")
    assert R.prompt_fingerprint()["validator"] == before


def test_the_fingerprint_moves_when_the_prompt_moves():
    import run_local_v2 as R
    import prompt
    a = R.prompt_fingerprint()
    old = prompt.SYSTEM_PROMPT
    try:
        prompt.SYSTEM_PROMPT = old + "\n한 줄 더"
        import importlib
        importlib.reload(R)
        b = R.prompt_fingerprint()
        assert a["system"] != b["system"]
        assert a["fewshots"] == b["fewshots"], "예시는 안 건드렸다"
    finally:
        prompt.SYSTEM_PROMPT = old
        import importlib
        importlib.reload(R)


def test_the_fingerprint_moves_when_the_schema_moves():
    """스키마는 ② 관문을 정의하므로 출력을 바꾼다.

    v23 에서 스키마에 제약을 더했는데 해시가 그대로라 기준선과 구별이
    안 됐다. 결과 파일만 보고 '같은 구성' 이라고 읽을 뻔했다.
    """
    import importlib
    import run_local_v2 as R
    import schema
    a = R.prompt_fingerprint()
    old = schema.SCHEMA
    try:
        schema.SCHEMA = dict(old, title="딴 것")
        importlib.reload(R)
        b = R.prompt_fingerprint()
        assert a["schema"] != b["schema"]
        assert a["system"] == b["system"], "지문은 안 건드렸다"
        assert a["fewshots"] == b["fewshots"], "예시는 안 건드렸다"
    finally:
        schema.SCHEMA = old
        importlib.reload(R)


# ── v70 · 관문을 다 넘어도 뜻 오류가 있으면 재시도한다 (2026-09-30) ──────────────
CAP_TEXT = "▪ 연 1.9% (최대 100만원까지)"
CAP_BAD = ('{"rules": [{"rule_id": "R", "status": "OK", '
           '"source": {"quote": "▪ 연 1.9% (최대 100만원까지)"}, '
           '"condition": {">=": [{"var": "account.reserved_amount"}, 1000000]}, '
           '"effect": {"type": "RATE_ADD", "value": 1.9, "unit": "%p"}}]}')
CAP_GOOD = ('{"rules": [{"rule_id": "R", "status": "OK", '
            '"source": {"quote": "▪ 연 1.9% (최대 100만원까지)"}, '
            '"condition": {">": [{"var": "account.reserved_amount"}, 0]}, '
            '"effect": {"type": "RATE_ADD", "value": 1.9, "unit": "%p"}}]}')


def test_a_cap_used_as_a_threshold_passes_every_gate():
    """**이 처방이 필요한 이유** — 관문 다섯이 이 모양을 통과시킨다."""
    import json

    from validate import score_record, semantic_errors
    m = score_record(json.loads(CAP_BAD), CAP_TEXT)
    assert all(m[k] for k in R.GATES)
    assert semantic_errors(json.loads(CAP_BAD), CAP_TEXT)


def test_a_semantic_error_triggers_a_retry_even_when_every_gate_passes(monkeypatch):
    r = _run_with([CAP_BAD, CAP_GOOD], monkeypatch, clause_text=CAP_TEXT)
    assert r["n_attempts"] == 2 and r["n_best"] == 2
    assert r["semantic_errors"] == []


def test_a_semantic_fix_that_loses_a_gate_is_not_taken(monkeypatch):
    # 뜻 오류는 없앴지만 인용이 틀려 관문을 잃은 재시도 — 1차를 낸다
    lost = CAP_GOOD.replace("▪ 연 1.9% (최대 100만원까지)", "없는 문장")
    r = _run_with([CAP_BAD, lost, lost], monkeypatch, clause_text=CAP_TEXT)
    assert r["n_best"] == 1 and r["semantic_errors"]


def test_no_semantic_error_without_a_cap_in_the_clause(monkeypatch):
    r = _run_with([GOOD, BROKEN], monkeypatch)
    assert r["n_attempts"] == 1 and r["semantic_errors"] == []


def test_the_semantic_check_is_silent_on_the_gold(root):
    """새 검사는 정답에서 0 이어야 한다 (`METHOD.md` 6절)."""
    import json

    from validate import semantic_errors
    texts = {c["id"]: c["text"] for c in
             json.loads((root / "data" / "corpus.json").read_text("utf-8"))}
    hits = []
    for p in sorted((root / "data" / "gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        hits += semantic_errors(json.loads(p.read_text("utf-8")), texts[p.stem])
    assert hits == []


# ── v74 · 조건을 단 LIMIT_AMOUNT 를 짚는다 (2026-09-30) ──────────────────────────
LIM_TEXT = "적용한도 : 저금통 금액 설정은 최대 100만원(1만원 단위)까지 가능"
LIM_BAD = ('{"rules": [{"rule_id": "R", "status": "OK", '
           '"source": {"quote": "적용한도 : 저금통 금액 설정은 최대 100만원(1만원 단위)까지 가능"}, '
           '"condition": {">": [{"var": "account.reserved_amount"}, 1000000]}, '
           '"effect": {"type": "LIMIT_AMOUNT", "value": 1000000}}]}')
LIM_GOOD = LIM_BAD.replace('{">": [{"var": "account.reserved_amount"}, 1000000]}', '{}')


def test_a_conditioned_limit_is_a_semantic_error():
    import json

    from validate import semantic_errors
    assert semantic_errors(json.loads(LIM_BAD), LIM_TEXT)
    assert semantic_errors(json.loads(LIM_GOOD), LIM_TEXT) == []


def test_a_conditioned_limit_is_caught_without_a_cap_in_the_text():
    """「최대 N만원」 방아쇠와 따로 선다 — 조문 글에 기대지 않는다."""
    import json

    from validate import semantic_errors
    assert semantic_errors(json.loads(LIM_BAD), "한도 문장")


def test_an_abstained_limit_is_left_alone():
    import json

    from validate import semantic_errors
    out = json.loads(LIM_BAD)
    out["rules"][0]["status"] = "UNSUPPORTED"
    assert semantic_errors(out, LIM_TEXT) == []


def test_a_conditioned_limit_triggers_a_retry(monkeypatch):
    r = _run_with([LIM_BAD, LIM_GOOD], monkeypatch, clause_text=LIM_TEXT)
    assert r["n_attempts"] == 2 and r["n_best"] == 2
    assert r["semantic_errors"] == []


# ── v78 · 한도 금액을 금리 조건의 위쪽 끝으로 쓴 것 (2026-09-30) ─────────────────
CAP_BELOW = CAP_BAD.replace('">="', '"<="')


def test_a_cap_used_as_an_upper_bound_on_the_rate_is_a_semantic_error():
    import json

    from validate import semantic_errors
    errs = semantic_errors(json.loads(CAP_BELOW), CAP_TEXT)
    assert errs and "> 0" in errs[0]
    assert semantic_errors(json.loads(CAP_GOOD), CAP_TEXT) == []


def test_the_v70_threshold_message_is_unchanged():
    """`>=` 쪽 문구는 v70 그대로 — 과거 라운드와 같은 말을 한다."""
    import json

    from validate import semantic_errors
    errs = semantic_errors(json.loads(CAP_BAD), CAP_TEXT)
    assert len(errs) == 1 and "이상인 고객만" in errs[0]


def test_an_upper_bound_on_a_disqualify_is_left_alone():
    import json

    from validate import semantic_errors
    out = json.loads(CAP_BELOW)
    out["rules"][0]["effect"] = {"type": "DISQUALIFY"}
    assert semantic_errors(out, CAP_TEXT) == []


# ── v82 · 「N년 이상 거래가 없는」을 거래가 있는 쪽으로 센 것 (2026-09-30) ─────────────
ABS_TEXT = "(가) 예금잔액이 10,000원 미만이며, 1년 이상 입출금 거래가 없는 계좌"
_WIN = '{"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -12}, "to": {"anchor": "contract.reference_date"}}}'
ABS_BAD = ('{"rules": [{"rule_id": "R", "status": "OK", "source": {"quote": "' + ABS_TEXT + '"}, '
           '"condition": {"and": [{"<": [{"var": "account.balance"}, 10000]}, '
           '{">=": [{"count_distinct_months": {"event": "WITHDRAWAL", "within": ' + _WIN + '}}, 12]}]}, '
           '"effect": {"type": "RESTRICT"}}]}')
ABS_GOOD = ('{"rules": [{"rule_id": "R", "status": "OK", "source": {"quote": "' + ABS_TEXT + '"}, '
            '"condition": {"and": [{"<": [{"var": "account.balance"}, 10000]}, '
            '{"not": {"exists": {"event": "DEPOSIT", "within": ' + _WIN + '}}}, '
            '{"not": {"exists": {"event": "WITHDRAWAL", "within": ' + _WIN + '}}}]}, '
            '"effect": {"type": "RESTRICT"}}]}')


def test_counting_transactions_for_an_absence_clause_is_a_semantic_error():
    import json

    from validate import semantic_errors
    assert semantic_errors(json.loads(ABS_BAD), ABS_TEXT)
    assert semantic_errors(json.loads(ABS_GOOD), ABS_TEXT) == []


def test_a_vacuous_count_is_caught_too():
    import json

    from validate import semantic_errors
    out = json.loads(ABS_BAD.replace('">="', '"<="'))
    assert semantic_errors(out, ABS_TEXT)


def test_a_zero_count_means_absence_and_is_left_alone():
    import json

    from validate import semantic_errors
    out = json.loads(ABS_BAD.replace('">="', '"=="').replace("}}, 12]", "}}, 0]"))
    assert semantic_errors(out, ABS_TEXT) == []


def test_the_absence_check_needs_the_clause_wording():
    import json

    from validate import semantic_errors
    assert semantic_errors(json.loads(ABS_BAD), "잔액이 1만원 미만인 계좌") == []
