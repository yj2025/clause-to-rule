"""모델 출력(merged_<상품>.json)을 목표 결과물(target_kbstar.json)에 key별로 맞춰 본다.

    python3 docsab/score_target.py docsab/merged_KB스타통장.json [--target docsab/target_freen.json]
문장 일치는 정규화 후 글자 2-gram 겹침으로 본다(목표 문장 기준 0.5 이상이면 같은 줄). 기계 대조라 근사다.
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
norm = lambda s: re.sub(r"[\s·•※\-\(\)\[\]「」'\"‘’“”,.:~]", "", s or "")
def grams(s):
    s = norm(s); return {s[i:i+2] for i in range(len(s)-1)}
def sim(a, b):
    A, B = grams(a), grams(b)
    return len(A & B) / len(A) if A else 0.0

def lines(it):
    out = []
    for f in ("conditions", "exceptions"):
        for x in it.get(f) or []:
            x = x if isinstance(x, dict) else {"text": str(x)}
            out.append(x)
            for y in x.get("exceptions") or []:      # 조건 안에 예외를 넣은 출력(Gemma)도 센다
                out.append(y if isinstance(y, dict) else {"text": str(y)})
    sp = it.get("special")
    if isinstance(sp, dict): out.append(sp)
    elif isinstance(sp, str): out.append({"text": sp})
    return out

def best(t, cands):
    sc = [(sim(t["text"], c.get("text", "")), c) for c in cands]
    return max(sc, key=lambda x: x[0]) if sc else (0, None)

TARGETS = {"KB스타통장": "target_kbstar.json", "KB 프리N통장": "target_freen.json", "KB 별별통장2": "target_byul2.json"}


def main(path, target=None):
    rec = json.loads(Path(path).read_text("utf-8"))
    target = target or HERE / TARGETS[rec.get("product_name", "KB스타통장")]
    tgt = {i["key"]: i for i in json.loads(Path(target).read_text("utf-8"))["items"]}
    got = {i.get("key"): i for i in (rec["parsed"] or {}).get("items", [])}
    T = dict(filled=0, keys=len(tgt), lines=0, lines_hit=0, src_ok=0, ui_need=0, ui_hit=0,
             only_need=0, only_hit=0, only_false=0, diff_need=0, diff_hit=0, diff_false=0, asof_need=0, asof_hit=0)
    rows = []
    for k, t in tgt.items():
        g = got.get(k) or {}
        T["filled"] += bool(g.get("summary"))
        tl, gl = lines(t), lines(g)
        miss = []
        for x in tl:
            T["lines"] += 1
            s, m = best(x, gl)
            if s >= 0.5:
                T["lines_hit"] += 1
                ids = {int(re.sub(r"\D", "", str(v)) or -1) for v in (m.get("src") or [])}   # "§1153" 꼴도 받는다 (EXAONE)
                if ids & set(x["src"]): T["src_ok"] += 1
                if x.get("user_input"):
                    T["ui_need"] += 1; T["ui_hit"] += bool(m.get("user_input"))
                if x.get("only_in"):
                    T["only_need"] += 1; T["only_hit"] += m.get("only_in") == x["only_in"]
            else:
                miss.append(x["text"])
                if x.get("user_input"): T["ui_need"] += 1
                if x.get("only_in"): T["only_need"] += 1
        T["only_false"] += sum(1 for m in gl if m.get("only_in") and not any(x.get("only_in") and sim(x["text"], m.get("text", "")) >= 0.5 for x in tl))
        if t.get("doc_diff"): T["diff_need"] += 1; T["diff_hit"] += bool(g.get("doc_diff"))
        elif g.get("doc_diff"): T["diff_false"] += 1
        if t.get("as_of"): T["asof_need"] += 1; T["asof_hit"] += norm(t["as_of"]) in norm(json.dumps(g, ensure_ascii=False))
        rows.append({"key": k, "filled": bool(g.get("summary")), "target_lines": len(tl), "model_lines": len(gl),
                     "missed": miss, "doc_diff_model": g.get("doc_diff"), "doc_diff_target": t.get("doc_diff")})
    extra = [k for k in got if k not in tgt]
    print(f"key 채움 {T['filled']}/{T['keys']} · 목표에 없는 key {extra}")
    print(f"조건·예외·특례 줄 {T['lines_hit']}/{T['lines']} 맞음 · 그중 출처 맞음 {T['src_ok']}/{T['lines_hit']}")
    print(f"물을 입력(user_input) {T['ui_hit']}/{T['ui_need']} · 한쪽에만(only_in) {T['only_hit']}/{T['only_need']} (헛표시 {T['only_false']})")
    print(f"문서 차이(doc_diff) {T['diff_hit']}/{T['diff_need']} (헛표시 {T['diff_false']}) · 기준일 {T['asof_hit']}/{T['asof_need']}")
    for r in rows:
        if r["missed"] or not r["filled"] or r["doc_diff_model"]:
            print(f"- {r['key']}: 채움 {r['filled']} · 줄 {r['model_lines']}/{r['target_lines']}" + (f" · 빠짐 {r['missed']}" if r["missed"] else "")
                  + (f" · 모델 doc_diff: {r['doc_diff_model']}" if r["doc_diff_model"] else ""))
    out = Path(path).with_suffix(".score.json")
    out.write_text(json.dumps({"totals": T, "rows": rows, "extra_keys": extra}, ensure_ascii=False, indent=1), "utf-8")

if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[a.index("--target") + 1] if "--target" in a else None)
