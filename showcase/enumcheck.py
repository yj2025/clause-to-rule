"""v101 판정 보조 — 저장된 결과를 **지금 검증기로 다시 채점**해 ③ · 관문 다섯 · DB 밖 명의 유형 · 지어낸 해지 유형을 센다.

    python showcase/enumcheck.py results/results_v90.json ... showcase/results_kb10v100a.json ...

③ 의 채점 계약이 v101 에서 바뀌었다(`in` 목록 안 값도 본다). 저장된 `final` 은 옛 계약이라 견줄 때는 이것으로 다시 잰다.
"""
import json
import sys

sys.path.insert(0, ".")
import validate as V  # noqa: E402

DB = {"INDIVIDUAL", "SOLE_PROPRIETOR", "CORPORATION", "ORGANIZATION", "JOINT"}
G = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
TEXT = {}
for f in ("data/corpus.json", "showcase/clauses.json"):
    TEXT.update({c["id"]: c["text"] for c in json.load(open(f))})


def enum_values(node, var):
    out = []
    if isinstance(node, dict):
        for op, a in node.items():
            if op in ("in", "==", "!=") and isinstance(a, list) and len(a) == 2 and a[0] == {"var": var}:
                out += a[1] if isinstance(a[1], list) else [a[1]]
            out += enum_values(a, var)
    elif isinstance(node, list):
        for x in node:
            out += enum_values(x, var)
    return out


print(f"{'':28}{'③':>5}{'관문5':>6}  DB 밖 명의 유형 (조문)          지어낸 해지 유형 (조문)")
for path in sys.argv[1:]:
    recs = json.load(open(path))
    marks = [V.score_record(x.get("output"), TEXT[x["clause_id"]]) for x in recs]
    bad_h, bad_t = set(), set()
    for x in recs:
        conds = [r.get("condition") for r in (x.get("output") or {}).get("rules") or [] if isinstance(r, dict)]
        if any(v not in DB for c in conds for v in enum_values(c, "customer.holder_type") if isinstance(v, str)):
            bad_h.add(x["clause_id"])
        if any(v not in V.catalog.ENUM_VALUES["contract.termination_type"]
               for c in conds for v in enum_values(c, "contract.termination_type") if isinstance(v, str)):
            bad_t.add(x["clause_id"])
    print(f"{path.split('/')[-1][8:-5]:28}{sum(m['catalog_ok'] for m in marks):>5}"
          f"{sum(all(m[g] for g in G) for m in marks):>6}  {len(bad_h)} {sorted(bad_h)}   {len(bad_t)} {sorted(bad_t)}")
