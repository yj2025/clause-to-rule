"""평가셋 v2 정답 검사 — `gold.py check` 와 같은 검사(스키마 · 카탈로그 · 실행 · 원문 인용)를 v2 조문에 돌린다.

    python eval_v2/tools/check_gold_v2.py DIR        # DIR/<조문 id>.json 전부
    python eval_v2/tools/check_gold_v2.py DIR ID     # 하나만

조문 원문은 `eval_v2/clauses.json`. `gold.py` 는 경로가 `data/gold` 로 박혀 있어 검사 함수만 빌려 쓴다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "work" / "M2-2"))
import validate  # noqa: E402

CLAUSES = {c["id"]: c for c in json.loads((HERE / "clauses.json").read_text("utf-8"))}


def check_one(path):
    g = json.loads(Path(path).read_text("utf-8"))
    cid = g.get("clause_id") or Path(path).stem
    rules = g.get("rules") or []
    errs = [] if cid in CLAUSES else [f"모르는 조문 id: {cid}"]
    errs += validate.check_schema({"rules": rules})
    for r in rules:
        errs += validate.check_catalog(r)
        errs += validate.check_executable(r)
        if cid in CLAUSES:
            errs += validate.check_quote(r, CLAUSES[cid]["text"])
    return cid, errs


def main(argv):
    d = Path(argv[0])
    files = [d / f"{argv[1]}.json"] if len(argv) > 1 else sorted(d.glob("*.json"))
    bad = 0
    for f in files:
        if f.name.startswith("_"):
            continue
        cid, errs = check_one(f)
        bad += bool(errs)
        print(f"  {cid:<15}{'실패 ' + str(len(errs)) if errs else '통과'}")
        for e in errs[:5]:
            print(f"      {e}")
    print(f"\n검증 실패 {bad} / {len([f for f in files if not f.name.startswith('_')])}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
