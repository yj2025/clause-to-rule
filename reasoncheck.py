"""빈 배열의 이유(`no_rule_reason`)를 잰다 (2026-10-06 · v125).

    python reasoncheck.py results/results_v125.json
    python reasoncheck.py showcase/results_kb10v125a.json --gold showcase/gold_draft

정답이 빈 배열인 조문(코퍼스 12 · kb10 36)만 센다. ⑥ 은 그대로 두고 따로 센다 —
⑥ 은 «옳게 기권»과 «아무것도 못 냄»을 못 가른다.
"""
import argparse
import collections
import json
from pathlib import Path


def check(results, gold_dir):
    gold = {p.stem: json.loads(p.read_text("utf-8")) for p in Path(gold_dir).glob("K*.json")}
    rows = []
    for x in json.loads(Path(results).read_text("utf-8")):
        g = gold.get(x["clause_id"])
        if not g or g.get("rules"):
            continue
        out = x.get("output") if isinstance(x.get("output"), dict) else {}
        rules = out.get("rules")
        rows.append({"clause_id": x["clause_id"], "want": g.get("no_rule_reason"),
                     "empty": rules == [], "got": out.get("no_rule_reason")})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--gold", default="data/gold")
    a = ap.parse_args(argv)
    for r in a.results:
        rows = check(r, a.gold)
        n = len(rows)
        empty = [x for x in rows if x["empty"]]
        same = [x for x in empty if x["got"] == x["want"]]
        print(f"{Path(r).name}: 정답 빈 배열 {n} · 빈 배열로 냄 {len(empty)} · 이유 적음 "
              f"{sum(1 for x in empty if x['got'])} · 이유 맞음 {len(same)}")
        print("   갈래별 맞음:", dict(collections.Counter(x["want"] for x in same)),
              "/ 정답:", dict(collections.Counter(x["want"] for x in rows)))


if __name__ == "__main__":
    main()
