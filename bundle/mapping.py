"""우리 조문(상품설명서 한 조문) ↔ 요약입력 묶음의 조항(section_id) 대응 (2026-10-08).

    python bundle/mapping.py            → bundle/clause_sections.json

요약입력(`docs/요약입력_상품별.json`, Supabase 10-08 조회)에는 section_id 가 있고 우리 조문에는 없다.
본문 글자로 맞춘다 — 공백 · 기호를 지우고, 우리 조문 본문이 그 조항 본문에 들어 있거나(조항이 더 길다) 거꾸로이거나,
글자 겹침 비율이 0.8 이상이면 같은 조항으로 본다.
"""
import difflib
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json")
PRODUCTS = {"KBGL": "KB골든라이프연금우대통장", "KBSSG": "쓱머니KB통장", "KBNR": "KB나라사랑우대통장",
            "KBSME": "KB 중소기업재직자 우대저축", "KBMER": "KB가맹점우대적금", "KBMY": "KB내맘대로적금",
            "KBHAP": "KB국민행복적금", "KBSUP": "국민수퍼정기예금(개인)", "KBSTR": "KB Star 정기예금",
            "KBGEN": "일반정기예금", "KBONE": "KB국민ONE통장", "KBYY": "KB Young Youth 통장"}


def norm(s):
    return re.sub(r"[\s▪※·•\-\|\[\]()（）:：,\.「」『』“”\"']", "", s or "")


def body(text):
    return text.split("\n", 1)[1] if "\n" in text else text


def _title(label):
    return norm(re.sub(r"\(.*\)", "", label or ""))


def match(clause, sections):
    """조항 제목으로 먼저 찾고(같은 DB 에서 떴다), 같은 제목이 여럿이면 본문 겹침으로 고른다.
    제목이 안 맞으면 본문 겹침만으로 — 0.8 이상일 때만."""
    docs = [s for s in sections if s["doc_type"] == "상품설명서"]
    cb = norm(body(clause["text"]))
    lab = _title(clause.get("label") or clause["text"].split("\n", 1)[0].strip("[]"))

    def sim(s):
        sb = norm(s["text"])
        if cb and len(cb) > 15 and cb in sb:
            return 1.0
        return difflib.SequenceMatcher(None, cb[:600], sb[:600]).ratio()

    same = [s for s in docs if _title(s["title"]) == lab or norm(s["text"]).startswith(lab) and lab]
    if same:
        best = max(same, key=sim)
        return best, round(sim(best), 2)
    best = max(docs, key=sim, default=None)
    r = sim(best) if best else 0.0
    return (best, r) if r >= 0.8 else (None, r)


def main():
    packets = {p["product_name"]: p for p in json.loads(SRC.read_text("utf-8"))["packets"]}
    clauses = json.loads((ROOT / "data/corpus.json").read_text("utf-8")) + \
        json.loads((ROOT / "showcase/clauses_key.json").read_text("utf-8"))
    out, miss = {}, []
    for c in clauses:
        pre = c["id"].split("-")[0]
        p = packets.get(PRODUCTS.get(pre))
        if p is None:
            miss.append((c["id"], "상품 없음"))
            continue
        s, r = match(c, p["sections"])
        if s is None:
            miss.append((c["id"], round(r, 2)))
            continue
        out[c["id"]] = {"product": p["product_name"], "section_id": s["section_id"], "score": round(r, 2),
                        "keys": s["keys"]}
    (HERE / "clause_sections.json").write_text(json.dumps({"mapped": out, "missing": miss}, ensure_ascii=False, indent=1), "utf-8")
    print(f"대응 {len(out)} / {len(clauses)} · 못 맞춘 {len(miss)}")
    for m in miss:
        print("  ", m)


if __name__ == "__main__":
    main()
