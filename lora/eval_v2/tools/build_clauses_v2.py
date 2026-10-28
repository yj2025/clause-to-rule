"""평가셋 v2 조문 — `md/*.md` → `doc_split.build` → `select` → kb10 과 같은 거르기 (2026-10-27).

kb10(`showcase/clauses_key.json`)과 같은 방식이다: 정형문구는 `doc_split.select` 로 빼고,
분류가 rate · eligibility · benefit 인 조문만 남긴다 (`lora/code/build_pool.py` 의 KEY_CATS).

    python eval_v2/tools/build_clauses_v2.py      # → eval_v2/clauses.json · clauses_all.json
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "work" / "M2-2"))
import doc_split  # noqa: E402

DOCS = {"HNSAL": "하나_급여하나 월복리 적금.md",
        "HNDRM": "하나_(아이) 꿈하나 적금.md",
        "HNWSH": "하나_나의 소원 적금.md"}
KEY_CATS = {"rate", "eligibility", "benefit"}


def main():
    every, kept = [], []
    for prefix, name in DOCS.items():
        cl = doc_split.build(HERE / "md" / name, prefix=prefix)
        sel = doc_split.select(cl)
        every += cl
        kept += [c for c in sel if c["category"] in KEY_CATS]
    (HERE / "clauses_all.json").write_text(json.dumps(every, ensure_ascii=False, indent=1), "utf-8")
    (HERE / "clauses.json").write_text(json.dumps(kept, ensure_ascii=False, indent=1), "utf-8")
    print(f"전체 {len(every)} · 남김 {len(kept)}")
    for prefix in DOCS:
        mine = [c for c in kept if c["id"].startswith(prefix + "-")]
        print(f"  {prefix} {len(mine):2}  " + " · ".join(f"{k} {v}" for k, v in collections.Counter(c['category'] for c in mine).items()))
        for c in mine:
            print(f"      {c['id']:14} {c['category']:11} {c['label'][:30]}")


if __name__ == "__main__":
    main()
