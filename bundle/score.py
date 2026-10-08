"""key 단위 ⑥ — 묶음 출력(또는 조문 출력을 key 로 모은 것)을 key 단위 정답과 견준다 (2026-10-08 · v129).

    python bundle/score.py --clause-runs showcase/results_kb10v127a.json results/results_v127.json   # 기준선
    python bundle/score.py --bundle-runs results/results_v129.json                                   # 묶음 판

같은 정답 · 같은 프로필(gold.profiles() 1,024)이다. 조문 하나가 여러 key 의 «주» 조항이면 정답도 출력도 그 key 마다 같이 들어간다.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "showcase"))
import gold  # noqa: E402
from kb10six import BASE_RATE  # noqa: E402
from scoring import score  # noqa: E402

BASE = {**BASE_RATE, **{k: json.loads((ROOT / "data/gold/_product.json").read_text("utf-8"))["base_rate"]
                        for k in ("KBONE", "KBYY")}}


def _rules(x):
    o = x.get("output") if isinstance(x.get("output"), dict) else {}
    return o.get("rules") if isinstance(o.get("rules"), list) else []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clause-runs", nargs="*", default=[])
    ap.add_argument("--bundle-runs", nargs="*", default=[])
    a = ap.parse_args(argv)
    G = json.loads((HERE / "gold_keys.json").read_text("utf-8"))
    P = gold.profiles()
    cols = {}
    if a.clause_runs:          # 조문 단위 판들을 하나로 합쳐 한 «판»으로 (kb10 판 + 코퍼스 판)
        recs = {}
        for f in a.clause_runs:
            recs.update({x["clause_id"]: x for x in json.loads(Path(f).read_text("utf-8"))})
        cols["조문 단위"] = {k: [r for c in g["clauses"] for r in (_rules(recs[c]) if c in recs else [])]
                         for k, g in G.items()}
    for f in a.bundle_runs:
        recs = {x["clause_id"]: x for x in json.loads(Path(f).read_text("utf-8"))}
        cols[Path(f).stem.split("results_")[-1]] = {k: _rules(recs[k]) for k in G if k in recs}
    print(f"key 단위 ⑥ — 채점 key {len(G)}")
    rows = {}
    for name, out in cols.items():
        rows[name] = {k: score(G[k]["rules"], out.get(k, []), "SUM", P, BASE[k.split("-")[0]])["rate"] * 100
                      for k in G if k in out}
    empty = {k: score(G[k]["rules"], [], "SUM", P, BASE[k.split("-")[0]])["rate"] * 100 for k in G}
    for name, r in rows.items():
        kb = [v for k, v in r.items() if k.split("-")[0] not in ("KBONE", "KBYY")]
        co = [v for k, v in r.items() if k.split("-")[0] in ("KBONE", "KBYY")]
        print(f"  {name:12} 전체 {sum(r.values())/len(r):5.1f} ({len(r)}) · kb10 {sum(kb)/max(1,len(kb)):5.1f} ({len(kb)}) · 코퍼스 {sum(co)/max(1,len(co)):5.1f} ({len(co)})")
    print(f"  {'빈 출력':12} 전체 {sum(empty.values())/len(empty):5.1f}")
    (HERE / "last_scores.json").write_text(json.dumps({"rows": rows, "empty": empty}, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
