"""조문 분할 — 규칙 기반. 결정론적이다.

LLM 은 태스크 1(조문 → 조건식)에만 쓴다. 전처리는 전부 코드다.

이 상품설명서의 조문은 **표의 한 행**이다. 왼쪽 칸이 라벨, 오른쪽 칸이 본문이다.
라벨이 괄호로 시작하거나 "이어짐" 이 붙은 행은 앞 행의 계속이므로 합친다.

참조표(`###` 로 시작하는 별도 표)는 그것을 가리키는 조문 안에 **인라인**한다.
표를 따로 조문으로 떼면 같은 내용이 두 번 채점되고, 그게 §6.2 의 참조표 중복이다.
111 레코드 중 21건이 중복이었고, 그 오염이 있는 회귀를 지우고 없는 개선을 만들었다.
`inline_refs=False` 로 부르면 옛 오염본(`-T##` 조문)이 나온다 — 비교용이다.

긴 조문 분할(`row_budget`)은 기본값이 꺼져 있다. 분할이 풀려던 문제(잘림)는
FEE_WAIVE 가 이미 풀었고, 남은 이득은 측정 오차와 구분되지 않는다 (§6.5).
"""

import re
from pathlib import Path

_PAGE = re.compile(r"^-+\s*page\s+(\d+)\s*-+$", re.I)
_SEC = re.compile(r"^##\s+(\d+|붙임)\s*(.*)$")
_SUB = re.compile(r"^###\s+(.+)$")
_ROW = re.compile(r"^\|(.*)\|$")
_SEP = re.compile(r"^[\s|:-]+$")
_BULLET = re.compile(r"^[▪□■]\s*(.*)$")
_CONT = re.compile(r"^\(|이어짐|산출근거")

_BOILERPLATE = (
    "「금융소비자 보호에 관한 법률", "예금자보호법", "이 설명서는",
    "본 설명서는", "설명내용을 제대로", "통장 미발행",
)

_CATEGORY = (
    ("rate",        ("금리", "이율", "이자계산", "이자 지급")),
    ("tax",         ("세제", "과세", "비과세")),
    ("benefit",     ("면제", "우대", "서비스", "저금통", "제휴", "쿠폰")),
    ("eligibility", ("가입대상", "신규금액", "상품유형", "상 품 명", "상품특징",
                     "전환", "제공기간", "제공조건")),
    ("restriction", ("제한", "불가", "중지", "압류", "이용제한", "질권", "양도")),
    ("admin",       ("거래방법", "해지", "통지", "책임", "열람", "휴면", "보호")),
)


def _norm(s):
    return re.sub(r"\s+", "", s)


def _cells(line):
    m = _ROW.match(line.strip())
    return [c.strip() for c in m.group(1).split("|")] if m else None


def _category(label, text):
    for name, words in _CATEGORY:
        if any(w in label for w in words):
            return name
    for name, words in _CATEGORY:
        if any(w in text for w in words):
            return name
    return "other"


def _clause_text(label, body):
    body = body.replace("<br>", "\n").strip()
    return f"[{label}]\n{body}" if body else f"[{label}]"


def _parse(path):
    """문서 → (조문 후보, 참조표).

    본표와 참조표를 가르는 기준은 **머리글 행**이다. 절이 시작된 뒤 처음 나오는
    머리글이 그 절의 본표이고, 같은 머리글이 다시 나오면 참조표 구간이 끝난 것이다.
    머리글은 바로 다음 줄이 `| --- |` 인 행으로 알아본다.

    참조표는 **제목을 부른 조문 중 가장 가까운 앞 조문**에 붙는다. 아무도 부르지
    않으면 바로 앞 조문에 붙인다. 같은 제목의 표가 세 번 나와도 섞이지 않는다.
    """
    page, section, sub = 1, 0, None
    main_header = None
    tables, blocks, bullets = [], [], []

    def flush_bullets():
        if bullets:
            blocks.append({"label": "상품 개요", "body": "\n".join(bullets),
                           "page": page, "section": section, "kind": "P"})
            bullets.clear()

    lines = Path(path).read_text("utf-8").splitlines()
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        m = _PAGE.match(line.strip())
        if m:
            page = int(m.group(1))
            continue
        m = _SEC.match(line)
        if m:
            flush_bullets()
            tag = m.group(1)
            section = 5 if tag == "붙임" else int(tag)
            sub, main_header = None, None
            continue
        m = _SUB.match(line)
        if m:
            flush_bullets()
            sub = {"title": m.group(1).strip(), "rows": [], "page": page,
                   "after": len(blocks) - 1}
            tables.append(sub)
            continue

        cells = _cells(line)
        if cells is not None:
            if _SEP.match(line):
                continue
            is_header = (i + 1 < len(lines) and _SEP.match(lines[i + 1].strip()))
            if is_header:
                norm = tuple(_norm(c) for c in cells)
                if main_header is None and sub is None:
                    main_header = norm
                elif norm == main_header:
                    sub = None                    # 본표로 돌아왔다
                elif sub is not None:
                    sub["rows"].append(cells)     # 참조표는 머리글도 본문이다
                continue
            if sub is not None:
                sub["rows"].append(cells)
                continue
            if len(cells) < 2:
                continue
            label, body = cells[0].replace("<br>", " ").strip(), cells[1]
            if _CONT.match(label) and blocks:
                blocks[-1]["body"] += "<br>" + body      # 앞 행의 계속
                continue
            blocks.append({"label": label, "body": body, "page": page,
                           "section": section, "kind": "R"})
            continue

        m = _BULLET.match(line.strip())
        if m and section <= 1:
            bullets.append(m.group(1))
    flush_bullets()
    return blocks, tables


def _table_text(tb):
    """표를 조문 본문에 붙일 형태로. 셀 안의 <br> 도 줄바꿈이다."""
    return "\n".join(" | ".join(c for c in row).replace("<br>", "\n")
                     for row in tb["rows"])


def build(path, row_budget=None, inline_refs=True, prefix="KBYY"):
    """문서 → 조문 목록. prefix 는 조문 id 앞머리다 (상품마다 다르게 준다)."""
    blocks, tables = _parse(path)
    texts = [_clause_text(b["label"], b["body"]) for b in blocks]
    attached = {}
    for tb in tables:
        key = _norm(tb["title"])
        owner = tb["after"]
        for i in range(tb["after"], -1, -1):
            if key in _norm(texts[i]):
                owner = i
                break
        attached.setdefault(owner, []).append(tb)

    out, n = [], {}
    for idx, b in enumerate(blocks):
        text = texts[idx]
        mine = attached.get(idx, [])
        refs = [t["title"] for t in mine]
        if inline_refs:
            for t in mine:
                text += f"\n\n[참조표: {t['title']}]\n{_table_text(t)}"
        key = (b["section"], b["kind"])
        n[key] = n.get(key, 0) + 1
        out.append({"id": f"{prefix}-S{b['section']}-{b['kind']}{n[key]:02d}",
                    "label": b["label"], "category": _category(b["label"], text),
                    "text": text.rstrip(), "page": b["page"],
                    "refs": refs if inline_refs else []})

    if not inline_refs:                       # 옛 오염본 — 표를 따로 조문으로 뗀다
        for i, tb in enumerate(tables, 1):
            out.append({"id": f"{prefix}-S2-T{i:02d}", "label": tb["title"],
                        "category": "benefit", "page": tb["page"], "refs": [],
                        "text": f"[{tb['title']}]\n{_table_text(tb)}"})
    if row_budget:
        out = _split_long(out, row_budget)
    return out


def _split_long(clauses, row_budget):
    """표 행이 예산을 넘으면 조문을 a/b/c 로 쪼갠다. 기본값은 꺼져 있다."""
    out = []
    for c in clauses:
        lines = c["text"].splitlines()
        rows = [l for l in lines if l.count("|") >= 1]
        if len(rows) <= row_budget:
            out.append(c)
            continue
        head = [l for l in lines if l.count("|") < 1]
        for i in range(0, len(rows), row_budget):
            out.append({**c, "id": c["id"] + "abcdefgh"[i // row_budget],
                        "text": "\n".join(head + rows[i:i + row_budget])})
    return out


def select(clauses, skip="boilerplate"):
    """조건식으로 옮길 것이 없는 정형문구를 뺀다."""
    if skip != "boilerplate":
        return list(clauses)
    return [c for c in clauses if not any(w in c["text"] for w in _BOILERPLATE)]
