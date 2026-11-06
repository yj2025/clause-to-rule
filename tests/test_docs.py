"""문서가 서로를 가리키는 곳이 끊겨 있지 않은지.

2026-09-14 에 라운드 문서 22개를 `EXPERIMENTS.md` 하나로 합쳤다.
그때 `EXPERIMENT_v<n>.md` 를 가리키던 곳이 셋 남아 있었다.
"""

import re

import pytest

# 2026-09-28 에 METHOD.md 를 더했다 — 판정하는 법이 라운드 판정문 곳곳에 흩어져
# 있어서, 세션이 초기화되면 방법부터 다시 세워야 했다. 한 장으로 모았다.
#
# 2026-11-06 폴더 정리 — README 만 루트에 두고 나머지 일곱은 docs/ 로 옮겼다.
# (세션 설정 파일 CLAUDE.md 는 지웠다 — 읽는 문서가 아니다.)
DOCS = ("README.md", "docs/ROUNDS.md", "docs/EXPERIMENTS.md", "docs/NOISE.md",
        "docs/CATALOG_PROPOSAL.md", "docs/DECISIONS.md", "docs/STATUS.md", "docs/METHOD.md")

# 본문에서 `파일.md` 꼴로 부르는 것
_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py))`")


def test_the_doc_set_is_exactly_eight(root):
    got = sorted([p.name for p in root.glob("*.md")] + [f"docs/{p.name}" for p in (root / "docs").glob("*.md")])
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
        # 루트 기준 경로이거나, docs/ 안의 문서끼리 이름만으로 부른 것
        if not ((root / name).exists() or (root / "docs" / name).exists()):
            missing.append(name)
    assert not missing, f"{doc} 가 없는 파일을 가리킨다: {sorted(missing)}"


# ── 2026-09-23 · 라운드를 돌리는 길은 하나여야 한다 ──────────────────────
def test_run_round_is_the_only_entry_point(root):
    """이어 돌리기를 따로 두지 않는다.

    v33 이 12/46 에서 끊겼을 때 세션 임시 폴더에 워처를 따로 짰고, 라운드마다
    복사본이 늘었다. **세션이 바뀌면 사라지는 자리다.** 저장소 안의
    `run_round.sh` 하나로 합쳤다 — 끊기면 같은 명령을 다시 부르면 된다.
    """
    sh = (root / "run_round.sh").read_text("utf-8")
    assert "남은 부분결과를 거둔다" in sh, "끊긴 라운드를 잇는 부분이 없다"
    assert "flock" in sh, "두 개가 겹쳐 도는 것을 막는 자물쇠가 없다"
    assert "wait_gpu" in sh, "GPU 를 기다리는 부분이 없다"
    assert "--only" in sh, "안 된 조문만 도는 부분이 없다"
    assert not list(root.glob("*_resume.sh")), "이어 돌리기 스크립트가 따로 남아 있다"
