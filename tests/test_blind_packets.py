"""이 저장소 조문 → 팀원 Part 2-1 입력 패킷 (`experiments/blind_packets.py`).

모양이 맞는지는 팀원 Train 에 같은 항목이 있는 3조문으로 잰다 — 글자까지 같아야 한다.
팀원 폴더가 없는 곳에서는 그 시험만 건너뛴다.
"""

import json

import pytest

import blind_packets as B

TEAM_READY = all(p.exists() for p in B.TEAM)
needs_team = pytest.mark.skipif(not TEAM_READY, reason="팀원 gold 파일이 없다")


@pytest.fixture(scope="module")
def corpus(root):
    return {c["id"]: c for c in json.loads((root / "data/corpus.json").read_text("utf-8"))}


@pytest.fixture(scope="module")
def written(root):
    lines = (root / "data/blind43_packets.jsonl").read_text("utf-8").splitlines()
    return json.loads(lines[0])["_meta"], [json.loads(l) for l in lines[1:]]


@needs_team
@pytest.mark.parametrize("cid", sorted(B.OVERLAP))
def test_overlapping_clause_matches_team_packet_to_the_letter(corpus, cid):
    rows, _ = B.load_team()
    want = next(r for r in rows if (r["document_name"], r["section_path"]) == B.OVERLAP[cid])
    assert B.packet_text(corpus[cid]) == want["packet_text"]


def test_written_set_is_corpus_minus_overlap(corpus, written):
    meta, packets = written
    ids = [p["sample_id"] for p in packets]
    assert len(ids) == len(set(ids)) == 43
    assert set(ids) == set(corpus) - set(B.OVERLAP)
    assert meta["excluded_overlap"] == sorted(B.OVERLAP)


def test_written_packets_are_what_the_code_builds_now(corpus, written):
    # 코퍼스나 변환을 바꾸고 파일을 다시 안 쓴 채 두지 않는다
    _, packets = written
    for p in packets:
        assert p["packet_text"] == B.packet_text(corpus[p["sample_id"]]), p["sample_id"]


def test_every_packet_carries_a_novelty_grade(written):
    _, packets = written
    assert {p["novelty"] for p in packets} <= {"SEEN_TRAIN", "NEAR_TRAIN", "SEEN_DEV", "NEW"}
    for p in packets:
        r = p["nearest_train"]["ratio"]
        if p["novelty"] == "SEEN_TRAIN":
            assert r >= B.SEEN
        elif p["novelty"] == "NEAR_TRAIN":
            assert B.NEAR <= r < B.SEEN
        else:
            assert r < B.NEAR


def test_prose_lines_are_joined_with_spaces():
    c = {"id": "KBONE-S2-R99", "label": "세제관련",
         "text": "[세제관련]\n▪ 비과세종합저축으로 가입가능\n※ 세법이 바뀌면 달라진다"}
    assert B.packet_text(c) == ("[PARENT_HEADER]\n2 거래 조건\n\n[CURRENT]\n세제관련\n"
                                "▪ 비과세종합저축으로 가입가능 ※ 세법이 바뀌면 달라진다")


def test_table_keeps_rows_and_drops_the_reference_marker():
    c = {"id": "KBYY-S2-R99", "label": "수수료면제 서비스",
         "text": "[수수료면제 서비스]\n▪ 면제조건: 카드 실적\n▪ 면제횟수 (아래 표 참조)\n\n"
                 "[참조표: 면제대상 수수료 및 면제횟수]\n면제대상 수수료 | 면제횟수\n이체수수료 | 제한 없음"}
    body = B.packet_text(c).split("[CURRENT]\n", 1)[1]
    assert body == ("수수료면제 서비스\n▪ 면제조건: 카드 실적 ▪ 면제횟수 (아래 표 참조)\n"
                    "면제대상 수수료 및 면제횟수\n면제대상 수수료 | 면제횟수\n이체수수료 | 제한 없음")
    assert "[참조표" not in body


def test_section_head_item_puts_section_title_in_current_and_keeps_lines(corpus):
    text = B.packet_text(corpus["KBONE-S1-P01"])
    assert text.startswith("[CURRENT]\n1 상품명 및 특징\n")
    assert "[PARENT_HEADER]" not in text
    assert len(text.split("\n")) == 4          # 태그 · 섹션 제목 · 상품명 · 상품특징


def test_unknown_clause_id_is_refused():
    with pytest.raises(ValueError):
        B.packet_text({"id": "KBYY-T01", "label": "x", "text": "[x]\ny"})
