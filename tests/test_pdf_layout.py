"""PDF 가 여백 안에 그려지는지.

2026-09-14 에 사용자가 "글자 오른쪽이 짤린다" 고 알려 줬다.
`multi_cell` 이 끝나면 x 가 **오른쪽 끝(190mm)에 남는다.** 그 자리에서
다음 `multi_cell(TW, ...)` 을 부르면 190 에서 시작해 360mm 까지 그린다 —
페이지는 210mm 라 앞부분만 보인다.

**글자 추출로는 안 잡힌다.** 내용은 다 들어 있고 위치만 틀리기 때문이다.
표 칸 폭, 상자 높이, 페이지 경계를 다 재 봤지만 전부 정상이었다.
좌표를 봐야 잡힌다.
"""

import subprocess
import sys
from pathlib import Path

import pytest

MM = 72 / 25.4
RIGHT = 192.0          # 오른쪽 여백 190mm + 여유
DOCS = ("brief.py", "decision_doc.py", "decision_catalog.py", "decision_scope.py")


def _fonts_ready(root):
    f = root / "fonts"
    return (f / "KR-Regular.ttf").exists() and (f / "KR-Bold.ttf").exists()


@pytest.mark.parametrize("script", DOCS)
def test_nothing_is_drawn_past_the_right_margin(root, script, tmp_path):
    if not _fonts_ready(root):
        pytest.skip("글꼴이 없다 — brief.py 머리말 참고")
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    out = subprocess.run([sys.executable, str(root / script)],
                         cwd=root, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-400:]
    pdf = next(root.glob("*.pdf"), None)
    assert pdf, "PDF 가 안 만들어졌다"
    over = []
    for i, page in enumerate(PdfReader(pdf).pages, 1):
        page.extract_text(visitor_text=lambda t, cm, tm, fn, sz:
                          over.append((i, round(tm[4] / MM, 1), t[:24]))
                          if t.strip() and tm[4] / MM > RIGHT else None)
    assert not over, f"{pdf.name} 에서 여백을 넘은 글자: {over[:3]}"


@pytest.mark.parametrize("script", DOCS)
def test_the_bold_font_is_a_real_truetype(root, script):
    """굵은 글꼴이 OTF(CFF) 면 추출에 널 문자가 끼고 뷰어가 깨뜨린다."""
    if not _fonts_ready(root):
        pytest.skip("글꼴이 없다")
    pytest.importorskip("fontTools")
    from fontTools.ttLib import TTFont
    for name in ("KR-Regular.ttf", "KR-Bold.ttf"):
        f = TTFont(root / "fonts" / name)
        assert f.sfntVersion == "\x00\x01\x00\x00", (
            f"{name} 이 TrueType 이 아니다 (sfnt={f.sfntVersion!r})")
