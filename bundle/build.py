"""key 묶음 입력 · key 단위 정답 · 조문 단위 출력을 key 로 모은 기준선 (2026-10-08 · v129 준비).

    python bundle/build.py      → bundle/bundles.json (러너 입력 · id/label/text) · bundle/gold_keys.json

묶음 하나 = 상품 하나의 key 하나. 그 key 가 «주»인 조항(특약 + 상품설명서)을 원문 그대로 이어 붙인다.
key 단위 정답 = 그 key 의 «주» 조항에 대응되는 우리 조문(bundle/clause_sections.json)의 정답 rule 을 모두 모은 것.
대응되는 정답 조문이 하나도 없는 key(특약에만 있는 key 등)는 채점하지 않는다 — 수를 같이 적는다.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json")
import sys
sys.path.insert(0, str(HERE))
from mapping import PRODUCTS  # noqa: E402


def gold_rules(cid):
    for base in (ROOT / "showcase/gold_draft", ROOT / "data/gold"):
        p = base / f"{cid}.json"
        if p.exists():
            return json.loads(p.read_text("utf-8")).get("rules") or []
    return None


def main():
    packets = {p["product_name"]: p for p in json.loads(SRC.read_text("utf-8"))["packets"]}
    cmap = json.loads((HERE / "clause_sections.json").read_text("utf-8"))["mapped"]
    by_section = {}
    for cid, m in cmap.items():
        by_section.setdefault(m["section_id"], []).append(cid)
    bundles, golds, skipped = [], {}, []
    for pre, name in PRODUCTS.items():
        p = packets[name]
        for k in p["keys"]:
            secs = [s for s in p["sections"] if s["section_id"] in set(k["primary_section_ids"])]
            if not secs:
                continue
            bid = f"{pre}-K-{k['key']}"
            parts = []
            for s in secs:
                where = f"{s['doc_type']} {s['path']}"
                parts.append(f"[{s['title'] or k['name']} — {where}]\n{s['text'].strip()}")
            text = f"[{k['name']}]\n" + "\n\n".join(parts)
            clauses = sorted({c for s in secs for c in by_section.get(s["section_id"], [])})
            rules = [r for c in clauses for r in (gold_rules(c) or [])]
            if not clauses:
                skipped.append(bid)
            bundles.append({"id": bid, "label": k["name"], "category": k["key"], "text": text,
                            "page": None, "refs": [], "sections": [s["section_id"] for s in secs],
                            "clauses": clauses})
            if clauses:
                golds[bid] = {"clauses": clauses, "rules": rules}
    (HERE / "bundles.json").write_text(json.dumps(bundles, ensure_ascii=False, indent=1), "utf-8")
    (HERE / "gold_keys.json").write_text(json.dumps(golds, ensure_ascii=False, indent=1), "utf-8")
    L = sorted(len(b["text"]) for b in bundles)
    print(f"묶음 {len(bundles)} · 채점하는 key {len(golds)} · 정답 조문이 없는 key {len(skipped)}")
    print(f"입력 길이(자) 중앙 {L[len(L)//2]} · 최대 {L[-1]} · 4천 넘는 것 {sum(x > 4000 for x in L)}")
    covered = {c for g in golds.values() for c in g["clauses"]}
    print(f"채점에 들어가는 우리 조문 {len(covered)} / 대응 {len(cmap)}")


if __name__ == "__main__":
    main()
