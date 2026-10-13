"""docsab/out.jsonl · compare.json → docsab/summaries_10.html (웹 페이지로 보기)."""
import json
from pathlib import Path

HERE = Path(__file__).parent
rs = [json.loads(l) for l in (HERE / "out.jsonl").read_text("utf-8").splitlines()]
cmp_rows = json.loads((HERE / "compare.json").read_text("utf-8"))
src = json.loads(Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json").read_text("utf-8"))
names = {p["product_name"]: {k["key"]: k["name"] for k in p["keys"]} for p in src["packets"]}
cls = {(r["product"], r["key"]): r["class"] for r in cmp_rows}
# 원문 대조로 확인한 것 (10-12)
VERIFIED = {
    ("KB스타통장", "fee"): ["doc", "문서 차이 확인 — 오픈뱅킹 이체 · 결산이자 입금 제외는 상품설명서에만 있다"],
    ("KB스타통장", "eligibility_target"): ["doc", "문서 차이 확인 — «개인사업자 · 서류 미제출 임의단체 포함»은 상품설명서에만 있다"],
    ("KB 별별통장2", "partner_benefit"): ["noise", "모델 흔들림 — 두 원문 모두 «월 최대 5회 · 별 최대 월 15개». 특약판 요약이 숫자를 뭉갰다"],
    ("KB 프리N통장", "fee"): ["noise", "모델 흔들림 — 특약 원문에도 제외 조건 4개가 다 있는데 특약판 요약에서 빠졌다"],
}

def slim(i):
    if not i:
        return None
    return {k: i.get(k) for k in ("summary", "conditions", "exceptions", "note") if i.get(k)}

products = []
by = {}
for r in rs:
    by.setdefault(r["product_name"], {})[r["doc"]] = r
for name, d in by.items():
    A = {i["key"]: i for i in (d["특약"]["parsed"] or {}).get("items", [])}
    B = {i["key"]: i for i in (d["상품설명서"]["parsed"] or {}).get("items", [])}
    keys = []
    for k in dict.fromkeys(list(B) + list(A)):
        keys.append({"key": k, "name": names.get(name, {}).get(k, k), "class": cls.get((name, k), ""),
                     "a": slim(A.get(k)), "b": slim(B.get(k)), "verified": VERIFIED.get((name, k))})
    products.append({"name": name, "na": d["특약"]["n_sections"], "nb": d["상품설명서"]["n_sections"], "keys": keys})

data = json.dumps(products, ensure_ascii=False).replace("</", "<\\/")
mr = json.loads((HERE / "merged_KB스타통장.json").read_text("utf-8"))
sc = json.loads((HERE / "merged_KB스타통장.score.json").read_text("utf-8"))
qitems = mr["parsed"]["items"]
qlines = [x for i in qitems for f in ("conditions", "exceptions") for x in (i.get(f) or [])]
isblob = lambda t: t.count("※") + t.count("▪") + t.count("①") + t.count(" - ") >= 2 or len(t) > 150
qwen = json.dumps({"items": qitems, "score": sc["totals"], "nlines": len(qlines),
                   "blob": sum(isblob(x["text"]) for x in qlines),
                   "review": json.loads((HERE / "qwen_review.json").read_text("utf-8"))}, ensure_ascii=False).replace("</", "<\\/")
target = (HERE / "target_kbstar.json").read_text("utf-8").replace("</", "<\\/")
html = (HERE / "page_template.html").read_text("utf-8").replace("/*__DATA__*/[]", data).replace("/*__TARGET__*/null", target).replace("/*__QWEN__*/null", qwen).replace("/*__REVIEW__*/null", (HERE / "review_agent.json").read_text("utf-8").replace("</", "<\\/")).replace("/*__MULTI__*/null", (HERE / "multi_products.json").read_text("utf-8").replace("</", "<\\/") if (HERE / "multi_products.json").exists() else "null").replace("/*__MODELS__*/null", (HERE / "models_kbstar.json").read_text("utf-8").replace("</", "<\\/"))
(HERE / "summaries_10.html").write_text(html, "utf-8")
print("ok", len(html) // 1024, "KB")
