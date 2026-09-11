import re

import pytest

from doc_split import build, select

DOC = "data/KB Young Youth 통장 상품설명서.txt"


@pytest.fixture(scope="module")
def raw(root):
    return build(root / DOC)


@pytest.fixture(scope="module")
def picked(raw):
    return select(raw)


def test_splitting_is_deterministic(root, raw):
    assert [c["id"] for c in build(root / DOC)] == [c["id"] for c in raw]


def test_ids_are_unique(raw):
    assert len({c["id"] for c in raw}) == len(raw)


def test_ids_follow_the_pattern(raw):
    assert all(re.fullmatch(r"KBYY-S\d-[PRT]\d\d", c["id"]) for c in raw)


def test_every_clause_has_text(raw):
    assert all(c["text"].strip() for c in raw)


def test_every_clause_has_a_page(raw):
    assert all(isinstance(c["page"], int) and c["page"] >= 1 for c in raw)


def test_longest_clause_matches_the_record(picked):
    assert max(len(c["text"]) for c in picked) == 1546


def test_shortest_clause_matches_the_record(picked):
    assert min(len(c["text"]) for c in picked) == 11


def test_annex_is_section_five(picked):
    assert [c["id"] for c in picked if c["id"].startswith("KBYY-S5-")]


def test_no_clause_contains_another(picked):
    assert not [(a["id"], b["id"]) for a in picked for b in picked
                if a is not b and a["text"] in b["text"]]


def test_boilerplate_is_removed(raw, picked):
    assert len(picked) < len(raw)


def test_deposit_protection_notice_is_removed(picked):
    assert not any("예금자보호법" in c["text"] for c in picked)


def test_select_can_be_told_to_keep_everything(raw):
    assert len(select(raw, skip=None)) == len(raw)


# ── 노트북에 적힌 조문들이 그대로 나오는가 ──────────────────────────────
@pytest.mark.parametrize("cid,label", [
    ("KBYY-S2-R11", "저금통 기능"),
    ("KBYY-S2-R12", "수수료면제 서비스"),
    ("KBYY-S2-R16", "질권설정"),
    ("KBYY-S5-R02", "KB생활 서비스Ⅰ"),
    ("KBYY-S5-R03", "KB생활 서비스Ⅱ"),
])
def test_known_labels(picked, cid, label):
    assert next(c for c in picked if c["id"] == cid)["label"] == label


@pytest.mark.parametrize("cid,n", [
    ("KBYY-S2-R02", 13), ("KBYY-S2-R03", 27), ("KBYY-S2-R06", 84),
    ("KBYY-S2-R16", 11), ("KBYY-S3-R02", 29),
    ("KBYY-S5-R01", 263), ("KBYY-S5-R02", 510),
])
def test_known_lengths(picked, cid, n):
    assert len(next(c for c in picked if c["id"] == cid)["text"]) == n


@pytest.mark.parametrize("cid,cat", [
    ("KBYY-S2-R06", "rate"), ("KBYY-S2-R07", "rate"),
    ("KBYY-S2-R16", "restriction"), ("KBYY-S2-R12", "benefit"),
    ("KBYY-S2-R13", "tax"),
])
def test_known_categories(picked, cid, cat):
    assert next(c for c in picked if c["id"] == cid)["category"] == cat


# ── 참조표 ──────────────────────────────────────────────────────────────
def test_fee_clause_has_the_table_inlined(picked):
    c = next(x for x in picked if x["id"] == "KBYY-S2-R12")
    assert "참조표" in c["text"] and c["refs"]


def test_fee_table_rows_are_present(picked):
    # 6행짜리 면제횟수 표는 붙임의 KB생활 서비스Ⅱ 에 붙는다. §6.5 의 정답표가 그것이다.
    c = next(x for x in picked if x["id"] == "KBYY-S5-R03")
    assert "월 10회" in c["text"] and "월 5회" in c["text"]


def test_section2_fee_clause_gets_the_three_row_table(picked):
    c = next(x for x in picked if x["id"] == "KBYY-S2-R12")
    assert "전자금융" in c["text"] and "월 10회" not in c["text"]


@pytest.mark.parametrize("cid,refs", [
    ("KBYY-S5-R02", ["기본실적", "면제 대상 수수료 및 면제횟수"]),
    ("KBYY-S5-R03", ["추가실적", "면제 대상 수수료 및 면제횟수", "급여이체 실적 인정기준"]),
])
def test_annex_reference_tables(picked, cid, refs):
    assert next(c for c in picked if c["id"] == cid)["refs"] == refs


def test_same_title_tables_do_not_mix(picked):
    a = next(c for c in picked if c["id"] == "KBYY-S5-R02")["text"]
    b = next(c for c in picked if c["id"] == "KBYY-S5-R03")["text"]
    assert "월 10회" in b and "월 10회" not in a


def test_inlined_version_has_no_table_only_clauses(picked):
    assert not [c for c in picked if "-T" in c["id"]]


def test_dup_table_version_has_table_only_clauses(root):
    dirty = build(root / DOC, inline_refs=False)
    assert [c for c in dirty if "-T" in c["id"]]


def test_dup_table_version_is_larger(root, raw):
    assert len(build(root / DOC, inline_refs=False)) > len(raw)


# ── 긴 조문 분할 (기본 꺼짐) ────────────────────────────────────────────
def test_row_budget_is_off_by_default(root, raw):
    assert not [c for c in raw if c["id"].endswith(("a", "b", "c"))]


def test_row_budget_splits_when_asked(root):
    split = build(root / DOC, row_budget=2)
    assert [c for c in split if c["id"].endswith("b")]


def test_row_budget_keeps_short_clauses_whole(root):
    split = build(root / DOC, row_budget=2)
    assert any(c["id"] == "KBYY-S2-R16" for c in split)


def test_saved_clauses_match_the_splitter(root, picked):
    import json
    saved = json.loads((root / "data/clauses.json").read_text("utf-8"))
    assert [c["id"] for c in saved] == [c["id"] for c in picked]
