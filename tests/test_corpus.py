"""여러 상품을 묶을 때 같은 조문이 두 번 들어오는 것을 막는다.

같은 내용을 두 번 채점하면 그 조문의 몫이 두 배가 되고, 두 상품에서 같은 방향으로
움직이므로 분산이 눌린다. §6.2 의 참조표 중복과 같은 사고다.
"""

import json

import pytest

import corpus


def c(cid, text):
    return {"id": cid, "text": text, "label": "x", "category": "other",
            "page": 1, "refs": []}


def test_merge_keeps_everything_distinct():
    got, dropped = corpus.merge([[c("A-1", "가"), c("A-2", "나")]])
    assert len(got) == 2 and dropped == []


def test_merge_drops_identical_text():
    got, dropped = corpus.merge([[c("A-1", "같은 글")], [c("B-1", "같은 글")]])
    assert len(got) == 1 and dropped == [("B-1", "A-1")]


def test_merge_keeps_the_first_product():
    got, _ = corpus.merge([[c("A-1", "같은 글")], [c("B-1", "같은 글")]])
    assert got[0]["id"] == "A-1"


def test_merge_ignores_whitespace_differences():
    _, dropped = corpus.merge([[c("A-1", "같은 글")], [c("B-1", "같은  글\n")]])
    assert dropped


def test_merge_can_be_told_to_keep_duplicates():
    got, dropped = corpus.merge([[c("A-1", "같은 글")], [c("B-1", "같은 글")]],
                                dedup=False)
    assert len(got) == 2 and dropped == []


def test_merge_of_nothing_is_empty():
    assert corpus.merge([]) == ([], [])


def test_merge_dedups_within_one_product_too():
    got, dropped = corpus.merge([[c("A-1", "같은 글"), c("A-2", "같은 글")]])
    assert len(got) == 1 and dropped == [("A-2", "A-1")]


@pytest.mark.parametrize("cid,want", [
    ("KBYY-S2-R01", "KBYY"), ("KBONE-S2-R09", "KBONE"), ("X-1", "X")])
def test_product_of(cid, want):
    assert corpus.product_of(cid) == want


def test_summary_counts_per_product():
    s = corpus.summary([c("A-1", "가"), c("A-2", "나다"), c("B-1", "라")])
    assert s["A"]["조문"] == 2 and s["B"]["조문"] == 1


def test_summary_reports_extremes():
    s = corpus.summary([c("A-1", "가"), c("A-2", "나다라")])
    assert s["A"]["최소"] == 1 and s["A"]["최대"] == 3


# ── 실제 코퍼스 ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def built(root):
    return json.loads((root / "data/corpus.json").read_text("utf-8"))


def test_corpus_has_both_products(built):
    assert {corpus.product_of(x["id"]) for x in built} == {"KBYY", "KBONE"}


def test_corpus_ids_are_unique(built):
    assert len({x["id"] for x in built}) == len(built)


def test_corpus_texts_are_unique(built):
    assert len({corpus._norm(x["text"]) for x in built}) == len(built)


def test_corpus_is_larger_than_one_product(built, clauses):
    assert len(built) > len(clauses)


def test_corpus_dropped_the_shared_annex(built):
    # KB생활 서비스Ⅱ 는 두 상품에 글자까지 같다. 하나만 남아야 한다
    long = [x for x in built if len(x["text"]) == 1546]
    assert len(long) == 1


def test_corpus_clause_bodies_are_intact(built, clauses):
    by = {x["id"]: x["text"] for x in built}
    assert all(by[c["id"]] == c["text"] for c in clauses)
