"""증류용 조문 풀 — kb10 · 코퍼스 상품을 뺀 나머지 상품설명서를 조문으로 뜬다 (2026-10-20).

`showcase/build_clauses.py` 와 같은 방식(섹션1 → 상품 개요 · 참조표 인라인 · 정형문구 제외)인데,
원문을 옛 sqlite 가 아니라 **원문 스냅샷 jsonl**(`key_mapping_check/snapshot/`, SYS 09-30 스냅샷에서 고객 테이블 빼고
복사)에서 읽는다. 평가 상품(kb10 · KBONE · KBYY)과 **문서를 같이 쓰는 상품도 뺀다** — 같은 문서가 학습에 들어가면 새는 것이다.

    python lora/build_pool.py            → lora/data/pool.json · lora/data/pool_products.json
"""

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "showcase"))
import doc_split  # noqa: E402
from build_clauses import PRODUCTS as KB10, _body, _is_table  # noqa: E402

SNAP = Path("/workspace/personal_workplace_CHO/key_mapping_check/snapshot")
EVAL_NAMES = {n for _, n, _ in KB10} | {"KB국민ONE통장", "KB Young Youth 통장"}
KEY_CATS = {"rate", "eligibility", "benefit"}      # clauses_key.json 과 같은 거르기


def jl(name):
    return [json.loads(line) for line in open(SNAP / f"{name}.jsonl", encoding="utf-8")]


def build_one(prefix, secs):
    """build_clauses.build_one 과 같은 모양. secs = [(section_path, full_text)]"""
    overview, blocks = [], []
    for path, full in secs:
        sec = int(re.match(r"섹션(\d+)", path).group(1))
        label, _, rest = full.partition("\n")
        label = " ".join(label.split())
        lines = [l.strip() for l in rest.splitlines() if l.strip()]
        if sec == 1:
            overview.append(f"{label} : {' '.join(lines)}")
        elif _is_table(lines) and blocks:
            key = doc_split._norm(label)
            owner = next((b for b in reversed(blocks) if key in doc_split._norm(b[2])), blocks[-1])
            owner[3].append((label, "\n".join(lines)))
        else:
            blocks.append([sec, label, _body(rest), []])
    out = []
    if overview:
        text = "[상품 개요]\n" + "\n".join(overview)
        out.append({"id": f"{prefix}-S1-P01", "label": "상품 개요",
                    "category": doc_split._category("상품 개요", text), "text": text, "page": None, "refs": []})
    n = {}
    for sec, label, body, tables in blocks:
        text = doc_split._clause_text(label, body)
        for title, rows in tables:
            text += f"\n\n[참조표: {title}]\n{rows}"
        n[sec] = n.get(sec, 0) + 1
        out.append({"id": f"{prefix}-S{sec}-R{n[sec]:02d}", "label": label,
                    "category": doc_split._category(label, text), "text": text.rstrip(),
                    "page": None, "refs": [t for t, _ in tables]})
    return out


def main():
    prods = {p["product_id"]: p for p in jl("products")}
    docs = {d["document_id"]: d for d in jl("documents")}
    vers = {v["document_id"]: v for v in jl("document_versions") if v["is_current"]}
    by_doc = collections.defaultdict(list)
    for r in jl("relations"):
        if docs[r["document_id"]]["document_type"] == "PRODUCT_DESCRIPTION":
            by_doc[r["document_id"]].append(prods[r["product_id"]]["product_name"])
    secs = collections.defaultdict(list)
    for s in jl("detail_sections"):
        if s["section_level"] == "항목":
            secs[s["version_id"]].append(s)

    pool, index = [], []
    for i, (doc_id, names) in enumerate(sorted(by_doc.items()), 1):
        if EVAL_NAMES & set(names):
            print(f"평가 상품과 같은 문서 — 뺌: {names}")
            continue
        v = vers[doc_id]
        rows = sorted(secs[v["version_id"]], key=lambda s: s["section_id"])
        prefix = f"P{doc_id:03d}"
        cl = build_one(prefix, [(s["section_path"], s["full_text"]) for s in rows])
        kept = [c for c in doc_split.select(cl) if c["category"] in KEY_CATS]
        for c in kept:
            c["product"] = names[0]
        pool += kept
        index.append({"prefix": prefix, "document_id": doc_id, "products": names,
                      "document": docs[doc_id]["document_name"], "clauses_all": len(cl), "clauses_key": len(kept)})
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    (out / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=1), "utf-8")
    (out / "pool_products.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    print(f"문서 {len(index)} · 조문 {len(pool)} · 분류 {collections.Counter(c['category'] for c in pool)}")


if __name__ == "__main__":
    main()
