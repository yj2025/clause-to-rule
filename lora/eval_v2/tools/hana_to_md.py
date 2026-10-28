"""하나은행 요약 상품설명서 PDF → `doc_split.py` 가 읽는 마크다운 (2026-10-27, 평가셋 v2).

KB 상품설명서 txt 와 같은 꼴로 만든다:

    ----- page N -----
    ## 1 상품 개요            ← 본문의 «• 상 품 명 : …» 글머리표를 «▪» 로
    ## 2 거래 조건
    | 구 분 | 내 용 |
    | --- | --- |
    | 라벨 | 본문<br>본문 |

* 1쪽은 **요약본**이라 뺀다 — 2~5쪽 본문과 같은 내용이 두 번 들어간다.
* 본표만 쓴다. 칸 안에 끼어 있는 작은 표(우대항목 · 중도해지금리 표 …)는 왼쪽 끝에서 시작하지 않으므로
  (x0 가 본표보다 40pt 넘게 오른쪽) 버린다 — 그 글자는 이미 본표 칸 안에 들어 있다.
* 라벨이 빈 행은 앞 행의 계속이다 (쪽을 넘어가는 칸).
* 4칸 행(라벨 | 본문 | 라벨 | 본문)은 두 행으로 나눈다.
* «용 어 | 설 명» 부록 표는 뺀다. 3절 유의사항 글머리표는 KB 와 같이 조문으로 쓰지 않는다.

    python eval_v2/tools/hana_to_md.py eval_v2/docs/X.pdf eval_v2/md/X.md
"""
import re
import sys
from pathlib import Path

import pdfplumber


def _clean(s):
    s = (s or "").strip()
    return re.sub(r"\s*\n\s*", "<br>", s).replace("|", "/")


def _label(s):
    """칸 라벨 한 줄로. «가 입 대 상» 처럼 글자마다 띄운 것은 붙이고, PDF 의 «¶»(가운뎃점 자리)는 «·» 로."""
    words = re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip().replace("¶", "·").split(" ")
    n = 0
    while n < len(words) and re.fullmatch(r"[가-힣]", words[n]):
        n += 1
    if n >= 3:                                    # 앞머리 한 글자씩 띄운 부분만 붙인다
        words = ["".join(words[:n])] + words[n:]
    return " ".join(words).replace(" · ", "·")


def main_rows(page):
    tables = page.find_tables()
    if not tables:
        return []
    left = min(t.bbox[0] for t in tables)
    rows = []
    for t in sorted(tables, key=lambda t: t.bbox[1]):
        if t.bbox[0] > left + 40:
            continue
        data = t.extract()
        if _label(data[0][0]).replace(" ", "") in ("용어",):
            continue
        for r in data:
            cells = [c for c in r]
            if _label(cells[0]).replace(" ", "") == "구분":
                continue
            if len(cells) == 4 and _label(cells[2]):
                rows.append((_label(cells[0]), _clean(cells[1])))
                rows.append((_label(cells[2]), _clean(cells[3])))
            else:
                rows.append((_label(cells[0]), _clean("\n".join(c for c in cells[1:] if c))))
    return rows


def overview(text):
    """2쪽의 «1. 상품 개요» ~ «2. 거래 조건» 사이 글머리표."""
    m = re.search(r"\n1\.?\s*상품[^\n]*\n(.*?)\n2\.?\s*거래", text, re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line[:1] in ("•", "￭", "■"):
            out.append(line[1:].strip())
        elif out and line:
            out[-1] += " " + line
    return out


def convert(pdf_path):
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        title = re.search(r"『\s*(.+?)\s*』", pdf.pages[1].extract_text() or "")
        lines.append(f"# 「{title.group(1) if title else Path(pdf_path).stem}」 상품설명서\n")
        rows_all = []
        for i, page in enumerate(pdf.pages[1:], 2):
            if i == 2:
                lines += ["----- page 2 -----", "", "## 1 상품명 및 특징", ""]
                lines += [f"▪ {b}" for b in overview(page.extract_text() or "")]
                lines += ["", "## 2 거래 조건", "", "| 구 분 | 내 용 |", "| --- | --- |"]
            for label, body in main_rows(page):
                if not label and rows_all:
                    rows_all[-1][1] += "<br>" + body
                elif label:
                    rows_all.append([label, body, i])
        page = 2
        for label, body, p in rows_all:
            if p != page:
                lines += [f"----- page {p} -----"]
                page = p
            lines.append(f"| {label} | {body} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(convert(src), "utf-8")
    print(dst)
