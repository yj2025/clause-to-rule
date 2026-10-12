"""docsab/out.jsonl → docsab/summaries_10.md (상품별 · key별로 특약판 · 설명서판을 나란히)."""
import json
from pathlib import Path

HERE = Path(__file__).parent
rs = [json.loads(l) for l in (HERE / "out.jsonl").read_text("utf-8").splitlines()]
src = json.loads(Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json").read_text("utf-8"))
names = {p["product_name"]: {k["key"]: k["name"] for k in p["keys"]} for p in src["packets"]}
by = {}
for r in rs:
    by.setdefault(r["product_name"], {})[r["doc"]] = r


def block(i):
    if not i or not i.get("summary"):
        note = f" — {i['note']}" if i and i.get("note") else ""
        return [f"  - (근거 없음{note})"]
    out = [f"  - {i['summary']}"]
    for f, lab in (("conditions", "조건"), ("exceptions", "예외")):
        for x in i.get(f) or []:
            out.append(f"    - {lab}: {x}")
    if i.get("note"):
        out.append(f"    - note: {i['note']}")
    return out


L = ["# 특약 vs 상품설명서 — Qwen3-8B key 요약 (10상품)", "",
     "- 생성: 2026-10-12 · 모델 `Qwen/Qwen3-8B` · 생각 모드 끔 · 온도 0 · 최대 4096토큰",
     "- 입력: 팀 요약입력 `docs/요약입력_상품별.json` — 상품마다 **특약 조항만** / **상품설명서 조항만** 따로 넣음 (공통약관 제외)",
     "- 지시문: 팀 요약 지시문에서 «특약 우선» · «공통약관» 두 문장만 뺌",
     "- 원본 출력: `docsab/out.jsonl` · 비교 분류: `docsab/compare.json`", "",
     "## 목차", ""]
for n, name in enumerate(by, 1):
    L.append(f"{n}. {name}")
for n, (name, d) in enumerate(by.items(), 1):
    A = {i["key"]: i for i in (d["특약"]["parsed"] or {}).get("items", [])}
    B = {i["key"]: i for i in (d["상품설명서"]["parsed"] or {}).get("items", [])}
    L += ["", "---", "", f"## {n}. {name}", "",
          f"특약 조항 {d['특약']['n_sections']}개 · 상품설명서 조항 {d['상품설명서']['n_sections']}개", ""]
    for k in dict.fromkeys(list(B) + list(A)):
        L += [f"### {names.get(name, {}).get(k, k)} (`{k}`)", "", "- **특약**"] + block(A.get(k)) + \
             ["- **상품설명서**"] + block(B.get(k)) + [""]
(HERE / "summaries_10.md").write_text("\n".join(L), "utf-8")
print(len(L), "줄")
