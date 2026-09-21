"""`data/products.json` 을 DB 스냅샷에서 만든다.

`catalog.py` 가 이 파일을 가리키고 있었는데 **실제로는 없었다** (2026-09-21 에 알았다).
스냅샷을 어떻게 떴는지가 코드로 남아 있지 않으면 다시 뜰 때 조용히 달라진다.

키는 **모델이 읽고 쓰는 이름**이다. 한 번 정한 키를 바꾸면 스키마 열거가 바뀌고
그 라운드는 앞 라운드와 못 견준다. 그래서 이 스크립트는 **키를 새로 짓지 않고**,
이미 있는 파일의 키를 그대로 이어받는다. 새 상품만 키를 짓는다.

    python products.py --check     지금 파일이 DB 와 맞는지만 본다 (안 고친다)
    python products.py --write     다시 뜬다
"""

import argparse
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

DB = Path("/workspace/database/schema/financedb.db")
OUT = Path(__file__).resolve().parent / "data" / "products.json"
BANK = "KB국민은행"


def _key(name):
    """상품 이름 → 모델이 쓰는 키. 공백만 밑줄로 바꾼다."""
    return "_".join(name.split())


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    """DB 에서 상품을 읽어 `{키: {...}}` 로 돌려준다. **읽기 전용으로만 연다.**"""
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        bank_id = c.execute("select bank_id from Banks where bank_name = ?",
                            (BANK,)).fetchone()
        if not bank_id:
            raise SystemExit(f"은행을 못 찾았다: {BANK}")
        rows = c.execute(
            "select product_id, product_name, product_code, product_category, "
            "       customer_scope "
            "  from Products where bank_id = ? order by product_name",
            (bank_id[0],)).fetchall()

    # 이미 있는 키를 이어받는다 — 키가 바뀌면 스키마 열거가 바뀐다
    old = {}
    if OUT.exists():
        old = {v.get("code"): k
               for k, v in json.loads(OUT.read_text("utf-8"))["products"].items()}

    out = {}
    for pid, name, code, category, scope in rows:
        key = old.get(code) or _key(name)
        out[key] = {"id": pid, "name": name, "code": code,
                    "category": category, "scope": scope}
    return out


def build():
    return {"_meta": {"source": str(DB), "db_sha256": _sha256(DB),
                      "bank": BANK, "at": date.today().isoformat(),
                      "n": None},
            "products": snapshot()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="파일을 다시 뜬다")
    a = ap.parse_args()

    doc = build()
    doc["_meta"]["n"] = len(doc["products"])
    now = doc["products"]
    have = json.loads(OUT.read_text("utf-8"))["products"] if OUT.exists() else {}

    added, gone = sorted(set(now) - set(have)), sorted(set(have) - set(now))
    changed = sorted(k for k in set(now) & set(have)
                     if {i: v for i, v in now[k].items() if i != "id"}
                     != {i: v for i, v in have[k].items() if i != "id"})
    print(f"DB {len(now)}개 · 파일 {len(have)}개")
    if added:
        print(f"  새로 생김 {len(added)}: {added[:8]}")
    if gone:
        print(f"  없어짐 {len(gone)}: {gone[:8]}")
    if changed:
        print(f"  내용 바뀜 {len(changed)}: {changed[:8]}")
    if not (added or gone or changed):
        print("  키도 내용도 그대로다")

    if a.write:
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                       "utf-8")
        print(f"\n썼다: {OUT}")
    else:
        print("\n(--write 없이는 안 고친다)")


if __name__ == "__main__":
    main()
