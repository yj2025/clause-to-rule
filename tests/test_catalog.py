import pytest

import catalog as C


def test_variable_count():
    """2026-09-15 customer.holder_type · account.last_transaction_date 로 19개.

    2026-09-20 실행기 범위 결정으로 contract.payout_request_date 를,
    상품 코드 체계로 customer.held_products · customer.held_categories 를 더해 22개다.
    **데이터 쪽 확인 전이다** — 지급청구일과 보유 상품 목록이 고객 데이터에 있는지 아직 안 물었다.
    """
    assert len(C.VARIABLES) == 22


def test_event_count():
    """v17 에서 WITHDRAWAL, 2026-09-15 NAME_CHANGE 를 더해 12개가 됐다."""
    assert len(C.EVENTS) == 12


def test_operator_count():
    assert len(C.OPERATORS) == 15   # 10-06 sum_events


def test_effect_count():
    """2026-09-15 SERVICE_PROVIDE · FEE_WAIVE_NO_CARRYOVER · DORMANT_CONTRIBUTION · RESTRICT 로 12개.

    2026-09-20 TAX_EXEMPT_ELIGIBLE · PRODUCT_SWITCH_TO · STATE_CHANGE 를 더해 15개다.
    """
    assert len(C.EFFECTS) == 15


def test_fee_count():
    assert len(C.FEES) == 6


@pytest.mark.parametrize("name", sorted(C.VARIABLES))
def test_every_variable_has_type_and_desc(name):
    assert C.VARIABLES[name]["type"] and C.VARIABLES[name]["desc"]


@pytest.mark.parametrize("name", sorted(C.EVENTS))
def test_every_event_has_a_description(name):
    assert C.EVENTS[name]


def test_operators_have_no_duplicates():
    assert len(set(C.OPERATORS)) == len(C.OPERATORS)


def test_comparisons_are_operators():
    assert set(C.COMPARISONS) <= set(C.OPERATORS)


def test_counters_are_operators():
    assert set(C.COUNTERS) <= set(C.OPERATORS)


def test_rate_effects_are_effects():
    assert set(C.RATE_EFFECTS) <= set(C.EFFECTS)


def test_unsupported_is_a_status_not_an_effect():
    assert "UNSUPPORTED" in C.STATUSES and "UNSUPPORTED" not in C.EFFECTS


@pytest.mark.parametrize("name", sorted(C.ENUM_VALUES))
def test_enum_variables_are_declared_enum(name):
    assert C.VARIABLES[name]["type"] == "enum"


def test_fee_waive_needs_a_target():
    assert "target" in C.EFFECTS["FEE_WAIVE"]


def test_disqualify_needs_nothing():
    assert C.EFFECTS["DISQUALIFY"] == ()


# ── 확장 대기 4건은 아직 없어야 한다 ────────────────────────────────────
@pytest.mark.parametrize("name", ["PRODUCT_SWITCH_EFFECT", "THRESHOLD_AMOUNT"])
def test_pending_effects_are_absent(name):
    assert name not in C.EFFECTS


@pytest.mark.parametrize("name", ["SEIZURE", "PROVISIONAL_SEIZURE"])
def test_pending_events_are_absent(name):
    """아직 합의 전인 것. 압류 계열은 `CATALOG_PROPOSAL.md` 7순위다."""
    assert name not in C.EVENTS


def test_withdrawal_pairs_with_deposit():
    """DEPOSIT 만 있으면 출금만 있던 계좌가 무거래로 판정된다 — 부호가 뒤집힌다."""
    assert "WITHDRAWAL" in C.EVENTS and "DEPOSIT" in C.EVENTS


def test_withdrawal_is_picked_for_transaction_clauses():
    _, ev = C.pick_candidates("1년 이상 입출금 거래가 없는 계좌")
    assert "WITHDRAWAL" in ev


# ── pick_candidates ─────────────────────────────────────────────────────
def test_pick_returns_two_lists():
    v, e = C.pick_candidates("카드 결제실적")
    assert isinstance(v, list) and isinstance(e, list)


def test_pick_finds_card_usage():
    _, e = C.pick_candidates("KB국민카드 결제실적이 있는 경우")
    assert "CARD_USAGE" in e


def test_pick_finds_salary_transfer():
    _, e = C.pick_candidates("급여이체가 발생한 월")
    assert "SALARY_TRANSFER" in e


def test_pick_finds_reserved_amount():
    v, _ = C.pick_candidates("저금통으로 설정된 금액")
    assert "account.reserved_amount" in v


def test_pick_is_empty_without_evidence():
    v, e = C.pick_candidates("xyz")
    assert v == [] and e == []


def test_pick_results_are_sorted():
    v, e = C.pick_candidates("급여이체 카드 결제실적 저금통 만기 해지")
    assert v == sorted(v) and e == sorted(e)


def test_pick_only_returns_known_names():
    v, e = C.pick_candidates("급여이체 카드 저금통 만기 해지 전환 연금 외환")
    assert set(v) <= set(C.VARIABLES) and set(e) <= set(C.EVENTS)


def test_pick_fees_finds_ebank():
    assert "EBANK_TRANSFER" in C.pick_fees("전자금융 이체수수료")


def test_pick_fees_is_empty_without_evidence():
    assert C.pick_fees("xyz") == []


@pytest.mark.parametrize("name,value,want", [
    ("contract.termination_type", "MATURITY", True),
    ("contract.termination_type", "취소", False),
    ("contract.channel", "MOBILE", True),
    ("contract.channel", "카카오", False),
    ("customer.age", 17, True),
])
def test_is_known_value(name, value, want):
    assert C.is_known_value(name, value) is want


# ── 자리 검사 (2026-09-16 · v24 회귀) ────────────────────────────────────
def test_every_enum_value_knows_its_slot():
    """카탈로그를 넓히면 새 이름이 자동으로 제자리를 갖는다.

    v24 회귀의 뿌리는 «이름이 카탈로그에 있으면 아무 자리나 통과» 였다.
    09-15 에 명의유형을 넣자 INDIVIDUAL 이 REQUIRE 의 value 로도 통과했다.
    """
    import catalog
    for name, vals in catalog.ENUM_VALUES.items():
        for v in vals:
            assert catalog.slot_of(v), f"{v} 의 자리를 카탈로그가 모른다"
    for fam in (catalog.RESTRICTIONS, catalog.SERVICES, catalog.FEES,
                catalog.EVENTS, catalog.VARIABLES):
        for v in fam:
            assert catalog.slot_of(v), f"{v} 의 자리를 카탈로그가 모른다"


def test_a_made_up_code_has_no_slot():
    import catalog
    assert catalog.slot_of("PLEDGE_NOT_ALLOWED") is None


# ── v58 · 「규칙이 아닌 문장」 블록의 방아쇠를 넓힌다 ──────────────────────
def test_non_binding_trigger_never_hits_a_clause_with_rules():
    """**이 시험이 v58 의 유일한 위험을 막는다.**

    제목만으로 가리면 `KBONE-S2-R12`(※ 「본인명의 계좌가 필요합니다」 · 정답
    rule 1개)와 `KBONE-S2-R03`(※ 「전환가능 · 제외」 · 정답이 기권 2개)이 같이
    걸린다. 코드 주석이 「계약해지방법은 일부러 뺐다」고 적어 둔 이유가 그것이다.
    ※ 줄의 요건 동사로 가른다.
    """
    import json
    import pathlib

    import catalog
    import gold
    root = pathlib.Path(__file__).resolve().parent.parent
    clauses = {c["id"]: c for c in json.loads(
        (root / "data" / "corpus.json").read_text("utf-8"))}
    bad = []
    for p in sorted((root / "data" / "gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        g = json.loads(p.read_text("utf-8"))
        if not (g.get("rules") or []):
            continue
        text = clauses.get(p.stem, {}).get("text", "")
        if catalog.wants_non_binding(text):
            bad.append(f"{p.stem}({gold.group_of(g)} · rule {len(g['rules'])}개)")
    assert not bad, "규칙이 있는 조문에 「규칙이 아니다」를 말하고 있다: " + ", ".join(bad)


def test_the_two_known_risks_are_filtered_out():
    import json
    import pathlib

    import catalog
    root = pathlib.Path(__file__).resolve().parent.parent
    clauses = {c["id"]: c for c in json.loads(
        (root / "data" / "corpus.json").read_text("utf-8"))}
    for cid in ("KBONE-S2-R12", "KBONE-S2-R03"):
        assert not catalog.wants_non_binding(clauses[cid]["text"]), cid


def test_the_five_new_targets_are_covered():
    """v54 가 재시도 쪽에서 못 고친 다섯이 이 문으로는 닿아야 한다."""
    import json
    import pathlib

    import catalog
    root = pathlib.Path(__file__).resolve().parent.parent
    clauses = {c["id"]: c for c in json.loads(
        (root / "data" / "corpus.json").read_text("utf-8"))}
    for cid in ("KBONE-S2-R04", "KBYY-S2-R03", "KBYY-S2-R06",
                "KBYY-S2-R10", "KBYY-S2-R15"):
        assert catalog.wants_non_binding(clauses[cid]["text"]), cid


def test_limit_block_hits_exactly_the_two_limit_clauses():
    """v66 — 「최대 N만원」 방아쇠는 정답이 LIMIT_AMOUNT 를 쓰는 두 조문에만 걸린다.

    넓히면 「5년 이내」(정답 DORMANT_CONTRIBUTION)가 같이 걸려 v39 의 이득을 깰 수 있다.
    """
    import json
    import pathlib

    import catalog
    root = pathlib.Path(__file__).resolve().parent.parent
    clauses = json.loads((root / "data" / "corpus.json").read_text("utf-8"))
    hit = sorted(c["id"] for c in clauses if catalog.wants_limit_block(c["text"]))
    assert hit == ["KBYY-S2-R07", "KBYY-S2-R23"]
    for cid in hit:
        g = json.loads((root / "data" / "gold" / f"{cid}.json").read_text("utf-8"))
        effs = {(r.get("effect") or {}).get("type") for r in g["rules"]}
        assert "LIMIT_AMOUNT" in effs, cid
    for cid in ("KBONE-S2-R17", "KBYY-S2-R20"):
        text = next(c["text"] for c in clauses if c["id"] == cid)
        assert not catalog.wants_limit_block(text), cid


# ── v101 · 명의 유형 값은 DB 의 CHECK 를 따른다 (2026-10-03) ───────────────────────
def test_holder_type_values_follow_the_db_check():
    import catalog as C
    import datacheck as D
    db = set(D.CHECKS["Customer_Defaults.customer_kind"])
    ours = set(C.ENUM_VALUES["customer.holder_type"])
    # JOINT(공동명의)만 DB 밖에 남긴다 — 사용자 결정 (10-03). 늘면 이 시험이 터진다
    assert ours - db == {"JOINT"} and db <= ours


def test_the_fewshot_uses_only_catalog_holder_values():
    import json
    import catalog as C
    from schema import FEWSHOT_HOLDER_OUTPUT
    text = json.dumps(FEWSHOT_HOLDER_OUTPUT)
    for v in ("UNREGISTERED_ASSOCIATION", "REGISTERED_ASSOCIATION"):
        assert f'"{v}"' not in text
    assert "ORGANIZATION" in text and "ORGANIZATION" in C.ENUM_VALUES["customer.holder_type"]


def test_values_inside_an_in_list_are_checked():
    from validate import check_catalog
    rule = {"condition": {"not": {"in": [{"var": "customer.holder_type"},
                                         ["INDIVIDUAL", "REGISTERED_ASSOCIATION"]]}},
            "effect": {"type": "DISQUALIFY"}}
    errs = check_catalog(rule)
    assert any("REGISTERED_ASSOCIATION" in e and "ORGANIZATION" in e for e in errs)
    rule["condition"]["not"]["in"][1] = ["INDIVIDUAL", "ORGANIZATION"]
    assert not any("값이 아님" in e for e in check_catalog(rule))


# ── v117 · 금리 표 블록 (2026-10-05) ────────────────────────────────────────────
def test_rate_table_block_fires_on_two_rates_only():
    import catalog as C
    from prompt import build_user_prompt
    table = "[우대이율]\n9건 이상 | 연1.5%\n6건 이상 | 연1.0%"
    assert C.wants_rate_table(table) and "[금리 표를 옮기는 법]" in build_user_prompt(table)
    assert not C.wants_rate_table("▪ 우대이율 : 연 1.9%p") and "[금리 표를 옮기는 법]" not in build_user_prompt("▪ 우대이율 : 연 1.9%p")


def test_rate_table_block_hits_one_corpus_clause():
    import json
    import catalog as C
    hits = [c["id"] for c in json.load(open("data/corpus.json")) if C.wants_rate_table(c["text"])]
    assert hits == ["KBYY-S2-R10"]
