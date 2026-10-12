"""docsab/out.jsonl 의 특약판 · 설명서판을 key 별로 견준다.

    python3 docsab/compare.py            → 표 · docsab/compare.json
"""
import json, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
NUM = re.compile(r'\d+(?:[.,]\d+)?\s*(?:%p|%|만\s*원|천\s*원|원|개월|년|일|회|건|세)')


def nums(i):
    t = json.dumps({k: i.get(k) for k in ("summary", "conditions", "exceptions")}, ensure_ascii=False)
    return {re.sub(r'[\s,]', '', m) for m in NUM.findall(t)}


def filled(i):
    return bool(i and i.get("summary"))


def main():
    rs = [json.loads(l) for l in (HERE / "out.jsonl").read_text("utf-8").splitlines()]
    by = {}
    for r in rs:
        by.setdefault(r["product_name"], {})[r["doc"]] = r
    stat, exc, rows, bad = Counter(), Counter(), [], []
    for name, d in by.items():
        if len(d) < 2:
            continue
        if not all(d[x]["parsed"] for x in d):
            bad.append(name); continue
        A = {i["key"]: i for i in d["특약"]["parsed"].get("items", [])}
        B = {i["key"]: i for i in d["상품설명서"]["parsed"].get("items", [])}
        for k in dict.fromkeys(list(A) + list(B)):
            a, b = A.get(k), B.get(k)
            fa, fb = filled(a), filled(b)
            if not fa and not fb:
                c = "둘 다 비움"
            elif fa and not fb:
                c = "특약만 채움"
            elif fb and not fa:
                c = "설명서만 채움"
            else:
                na, nb = nums(a), nums(b)
                ea, eb = len(a.get("exceptions") or []), len(b.get("exceptions") or [])
                if na - nb and nb - na:
                    c = "둘 다 · 숫자 서로 다름"
                elif nb - na:
                    c = "둘 다 · 설명서에 숫자 더"
                elif na - nb:
                    c = "둘 다 · 특약에 숫자 더"
                elif ea != eb:
                    c = "둘 다 · 숫자 같고 예외 수 다름"
                else:
                    c = "둘 다 · 숫자 · 예외 수 같음"
            stat[c] += 1
            if fa and fb:
                ea, eb = len(a.get("exceptions") or []), len(b.get("exceptions") or [])
                exc["둘 다 채운 key"] += 1
                exc["예외 설명서가 더 많음" if eb > ea else "예외 특약이 더 많음" if ea > eb else "예외 수 같음"] += 1
            rows.append({"product": name, "key": k, "class": c,
                         "특약": a, "상품설명서": b})
    print(f"비교한 상품 {len(set(r['product'] for r in rows))} · 안 읽혀 뺀 상품 {bad}")
    tot = sum(stat.values())
    for c, n in stat.most_common():
        print(f"{n:5d}  {100*n/tot:5.1f}%  {c}")
    print("  예외(exceptions) 개수 —", dict(exc))
    (HERE / "compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
