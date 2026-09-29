"""KB 상품 10개의 상품설명서를 DB 에서 조문으로 뜬다 — 쇼케이스용 (2026-09-29).

라운드 코퍼스(`data/corpus.json`)와 **섞지 않는다.** 정답이 없는 상품이라 채점을 못 하고,
섞으면 라운드끼리 못 견준다. 결과는 `showcase/` 안에만 둔다.

원문은 `.txt` 가 아니라 DB `Detail_Sections` 의 `항목` 이다. 거기서는 셀 안 줄바꿈이
공백으로 뭉개져 있으므로 ▪ ※ ➢ 주N) 앞에서 다시 끊는다. 모양을 `doc_split` 과 맞춘다:

  * 섹션 1 의 항목들 → 조문 하나 (`S1-P01`, 「상품 개요」)
  * `a | b` 행만 있는 항목은 **참조표**다 → 제목을 언급한 앞 조문에 인라인한다
    (못 찾으면 바로 앞 조문). 따로 떼면 §6.2 의 참조표 중복이 된다
  * 정형문구는 `doc_split.select` 로 뺀다

    python showcase/build_clauses.py            → showcase/clauses.json
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import doc_split  # noqa: E402

DB = "file:/workspace/database/schema/financedb.db?mode=ro"

# (id 앞머리, 상품명, 분류) — 입출금 3 · 적금 4 · 정기예금 3
PRODUCTS = [
    ("KBGL",  "KB골든라이프연금우대통장",      "입출금"),
    ("KBSSG", "쓱머니KB통장",                  "입출금"),
    ("KBNR",  "KB나라사랑우대통장",            "입출금"),
    ("KBSME", "KB 중소기업재직자 우대저축",    "적금"),
    ("KBMER", "KB가맹점우대적금",              "적금"),
    ("KBMY",  "KB내맘대로적금",                "적금"),
    ("KBHAP", "KB국민행복적금",                "적금"),
    ("KBSUP", "국민수퍼정기예금(개인)",        "정기예금"),
    ("KBSTR", "KB Star 정기예금",              "정기예금"),
    ("KBGEN", "일반정기예금",                  "정기예금"),
]

_BREAK = re.compile(r"\s+(?=[▪※➢]|주\d\)|\([가-하]\)\s|- [가-힣 ]+:)")


def _body(text):
    """뭉개진 줄바꿈을 표지 앞에서 되살린다."""
    return "\n".join(_BREAK.sub("\n", line).strip() for line in text.splitlines())


def _is_table(lines):
    return len(lines) > 0 and not lines[0].startswith("▪") and \
        any(" | " in l for l in lines)


def _sections(conn, name):
    row = conn.execute(
        """select v.version_id, v.effective_date, v.document_url, d.document_name
           from Products p join Relations r on r.product_id = p.product_id
           join Documents d on d.document_id = r.document_id
           join Document_Versions v on v.document_id = d.document_id and v.is_current = 1
           where p.product_name = ? and d.document_type = 'PRODUCT_DESCRIPTION'""",
        (name,)).fetchone()
    if row is None:
        raise SystemExit(f"상품설명서가 없다: {name}")
    secs = conn.execute(
        """select section_path, full_text from Detail_Sections
           where version_id = ? and section_level = '항목' order by section_id""",
        (row[0],)).fetchall()
    return row, secs


def build_one(conn, prefix, name):
    meta, secs = _sections(conn, name)
    overview, blocks = [], []          # blocks: [sec, label, body, [표...]]
    for path, full in secs:
        sec = int(re.match(r"섹션(\d+)", path).group(1))
        label, _, rest = full.partition("\n")
        label = " ".join(label.split())
        lines = [l.strip() for l in rest.splitlines() if l.strip()]
        if sec == 1:
            overview.append(f"{label} : {' '.join(lines)}")
        elif _is_table(lines) and blocks:
            key = doc_split._norm(label)
            owner = next((b for b in reversed(blocks)
                          if key in doc_split._norm(b[2])), blocks[-1])
            owner[3].append((label, "\n".join(lines)))
        else:
            blocks.append([sec, label, _body(rest), []])

    out = []
    if overview:
        text = "[상품 개요]\n" + "\n".join(overview)
        out.append({"id": f"{prefix}-S1-P01", "label": "상품 개요",
                    "category": doc_split._category("상품 개요", text),
                    "text": text, "page": None, "refs": []})
    n = {}
    for sec, label, body, tables in blocks:
        text = doc_split._clause_text(label, body)
        for title, rows in tables:
            text += f"\n\n[참조표: {title}]\n{rows}"
        n[sec] = n.get(sec, 0) + 1
        out.append({"id": f"{prefix}-S{sec}-R{n[sec]:02d}", "label": label,
                    "category": doc_split._category(label, text),
                    "text": text.rstrip(), "page": None,
                    "refs": [t for t, _ in tables]})
    return meta, out


def main():
    conn = sqlite3.connect(DB, uri=True)
    clauses, index = [], []
    for prefix, name, kind in PRODUCTS:
        meta, cl = build_one(conn, prefix, name)
        kept = doc_split.select(cl)
        clauses += kept
        index.append({"prefix": prefix, "product": name, "kind": kind,
                      "document": meta[3], "effective_date": meta[1],
                      "url": meta[2], "clauses_all": len(cl), "clauses": len(kept)})
        print(f"{prefix:6} {kind:4} {name:22} 조문 {len(cl):3} → {len(kept):3}")
    (HERE / "clauses.json").write_text(
        json.dumps(clauses, ensure_ascii=False, indent=1), "utf-8")
    (HERE / "products.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    print(f"합계 {len(clauses)}조문 → showcase/clauses.json")


if __name__ == "__main__":
    main()
