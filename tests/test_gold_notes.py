"""정답의 **설명(note)이 규칙과 어긋나면** 검토하는 사람이 잘못 읽는다.

2026-09-24 에 일곱 파일이 그랬다. note 는 「UNSUPPORTED 1개」라고 하는데
규칙은 `RESTRICT` · `SERVICE_PROVIDE` 를 쓴다 — **어휘가 넓어지면서 정답이
바뀌었는데 설명을 안 고친 것**이다. 35조문이 사람 검토를 기다리고 있고,
검토하는 사람이 읽는 것이 바로 이 note 다.

설명을 지우지 않고 **표시를 붙였다** (되돌린 라운드도 이유와 함께 남기는 것과
같은 방식). 이 시험은 **새로 어긋나는 것**을 잡는다.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARK = "※ 2026-09-24"


def _golds():
    for p in sorted((ROOT / "data" / "gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        yield p, json.loads(p.read_text("utf-8"))


def test_note_unsupported_count_matches_the_rules():
    bad = []
    for p, g in _golds():
        note = g.get("note") or ""
        if note.startswith(MARK):          # 이미 표시한 낡은 설명
            continue
        m = re.search(r"UNSUPPORTED\s*(\d+)\s*개", note)
        if not m:
            continue
        n = sum(1 for r in (g.get("rules") or []) if r.get("status") == "UNSUPPORTED")
        if int(m.group(1)) != n:
            bad.append(f"{p.stem}: note {m.group(1)}개 · 실제 {n}개")
    assert not bad, "설명과 규칙이 어긋난다 — 표시를 붙이거나 설명을 고칠 것:\n" + "\n".join(bad)


def test_the_stale_notes_are_marked_not_deleted():
    """낡은 설명을 **지우지 않았는지** 본다. 판단 근거는 남겨야 한다."""
    marked = [p.stem for p, g in _golds() if (g.get("note") or "").startswith(MARK)]
    assert len(marked) == 7, f"표시된 파일 {len(marked)}개 — 일곱이어야 한다"
    for p, g in _golds():
        if (g.get("note") or "").startswith(MARK):
            assert len(g["note"]) > 300, f"{p.stem}: 표시만 남고 설명이 지워졌다"
