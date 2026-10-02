"""kb10 대조 — python kb10cmp.py <결과.json> ... (M2-2 루트에서)"""
import json, re, sys
sys.path.insert(0, ".")
import validate as V
C = {c["id"]: c["text"] for c in json.load(open("showcase/clauses.json"))}
rev = json.load(open("showcase/review.json"))
ONE = re.compile(r"1\s*인\s*1\s*계좌")
G = ["json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok"]
runs = {p.split("results_")[-1][:-5]: {x["clause_id"]: x for x in json.load(open(p))} for p in sys.argv[1:]}
print(f"{'':24}" + "".join(f"{k:>12}" for k in runs))
def row(name, f):
    print(f"{name:24}" + "".join(f"{f(R):>12}" for R in runs.values()))
for g in G:
    row(g, lambda R, g=g: sum(x["final"][g] for x in R.values()))
row("관문 다섯 다", lambda R: sum(all(x["final"][g] for g in G) for x in R.values()))
row("빈 배열", lambda R: sum(bool(x["final"].get("empty")) for x in R.values()))
def abst(x):
    rs = (x.get("output") or {}).get("rules") or []
    return bool(rs) and all(isinstance(r, dict) and r.get("status") == "UNSUPPORTED" for r in rs)
row("통째로 기권", lambda R: sum(abst(x) for x in R.values()))
row("OK rule 수", lambda R: sum(sum(1 for r in (x.get("output") or {}).get("rules") or [] if isinstance(r, dict) and r.get("status") == "OK") for x in R.values()))
row("뜻 오류 (뽑힌 출력)", lambda R: sum(bool(V.semantic_errors(x.get("output"), C[c])) for c, x in R.items()))
row("평균 시도 수", lambda R: f"{sum(x['n_attempts'] for x in R.values())/len(R):.2f}")
row("1인1계좌 has_product", lambda R: f"{sum('has_product' in json.dumps(x.get('output')) for c, x in R.items() if ONE.search(C[c]))}/{sum(bool(ONE.search(C[c])) for c in R)}")
print("\n대조 18조문 — 뽑힌 출력이 09-29 와 글자까지 같은가 / 관문 다섯")
base = list(runs)[0]
for c, v in rev.items():
    cells = []
    for k, R in runs.items():
        same = json.dumps(R[c].get("output"), sort_keys=True) == json.dumps(runs[base][c].get("output"), sort_keys=True)
        cells.append(f"{'=' if same else '≠'}{'✓' if all(R[c]['final'][g] for g in G) else '✗'}")
    print(f"  {c:16} {v['verdict']:5} " + "  ".join(cells))
print("\n관문 다섯이 갈린 조문")
for c in runs[base]:
    s = [all(R[c]["final"][g] for g in G) for R in runs.values() if c in R]
    if len(set(s)) > 1:
        print(f"  {c:16} " + " ".join('✓' if b else '✗' for b in s))
