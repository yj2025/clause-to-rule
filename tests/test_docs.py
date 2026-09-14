"""문서가 서로를 가리키는 곳이 끊겨 있지 않은지.

2026-09-14 에 라운드 문서 22개를 `EXPERIMENTS.md` 하나로 합쳤다.
그때 `EXPERIMENT_v<n>.md` 를 가리키던 곳이 셋 남아 있었다.
"""

import re

import pytest

DOCS = ("README.md", "ROUNDS.md", "EXPERIMENTS.md", "NOISE.md",
        "CATALOG_PROPOSAL.md", "DECISIONS.md", "RECOVERY.md", "STATUS.md")

# 본문에서 `파일.md` 꼴로 부르는 것
_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py))`")


def test_the_doc_set_is_exactly_eight(root):
    got = sorted(p.name for p in root.glob("*.md"))
    assert got == sorted(DOCS), (
        f"문서가 늘거나 줄었다: {got}. 라운드마다 파일을 새로 만들지 않는다 — "
        "EXPERIMENTS.md 에 항목을 더한다")


@pytest.mark.parametrize("doc", DOCS)
def test_no_dangling_reference(root, doc):
    text = (root / doc).read_text("utf-8")
    missing = []
    for name in set(_REF.findall(text)):
        if "*" in name or name.startswith(".."):
            continue          # 글로브와 저장소 밖은 뺀다
        if not (root / name).exists():
            missing.append(name)
    assert not missing, f"{doc} 가 없는 파일을 가리킨다: {sorted(missing)}"
