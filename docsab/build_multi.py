"""상품 3개 × 모델 3개(31B · 12B · Qwen 4비트, 요약입력 조항)의 채점 · 후처리 전후 → docsab/multi_products.json (2026-10-13)."""
import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import postcheck as P  # noqa: E402
import score_target as S  # noqa: E402

M3 = HERE.parent.parent / "M3"
RUNS = [("KB스타통장", {"Gemma 4 31B": "results/kbstar_03_gemma31/gemma31", "Gemma 4 12B": "results/kbstar_01/gemma", "Qwen3-8B 4비트": "results/kbstar_01/qwen"}),
        ("KB 프리N통장", {"Gemma 4 31B": "results/freen_01/gemma31", "Gemma 4 12B": "results/freen_01/gemma", "Qwen3-8B 4비트": "results/freen_01/qwen"}),
        ("KB 별별통장2", {"Gemma 4 31B": "results/byul2_01/gemma31", "Gemma 4 12B": "results/byul2_01/gemma", "Qwen3-8B 4비트": "results/byul2_01/qwen"})]


def score(p):
    with contextlib.redirect_stdout(io.StringIO()):
        S.main(str(p))
    return json.loads(Path(str(p).replace(".json", ".score.json")).read_text("utf-8"))["totals"]


def main():
    review = json.loads((HERE / "multi_review.json").read_text("utf-8")) if (HERE / "multi_review.json").exists() else {}
    rows = []
    for prod, models in RUNS:
        for model, stem in models.items():
            p = M3 / f"{stem}_scored_input.json"
            if not p.exists():
                rows.append({"product": prod, "model": model, "missing": True, "review": review.get(f"{prod}|{model}", [])}); continue
            rec = json.loads(p.read_text("utf-8"))
            row = {"product": prod, "model": model, "parsed": bool(rec["parsed"]), "gen_tokens": rec["gen_tokens"], "sec": rec["sec"],
                   "review": review.get(f"{prod}|{model}", [])}
            if rec["parsed"]:
                row["before"] = score(p)
                with contextlib.redirect_stdout(io.StringIO()):
                    q = P.run(str(p))
                row["after"] = score(q)
                items = json.loads(Path(q).read_text("utf-8"))["parsed"]["items"]
                row["missing_flags"] = sum(len(i["_check"].get("missing", [])) for i in items)
                row["diff_found"] = [i["key"] for i in items if i["_check"].get("doc_diff")]
            rows.append(row)
    extra = json.loads((HERE / "multi_notes.json").read_text("utf-8")) if (HERE / "multi_notes.json").exists() else {}
    (HERE / "multi_products.json").write_text(json.dumps({"rows": rows, **extra}, ensure_ascii=False, indent=1), "utf-8")
    for r in rows:
        if r.get("before"):
            b, a = r["before"], r["after"]
            print(f"{r['product']:10s} {r['model']:14s} key {b['filled']}/{b['keys']} · 줄 {b['lines_hit']}/{b['lines']} · 차이 {b['diff_hit']}/{b['diff_need']}({b['diff_false']})→{a['diff_hit']}/{a['diff_need']}({a['diff_false']}) · 입력 {b['ui_hit']}→{a['ui_hit']}/{b['ui_need']} · 누락의심 {r['missing_flags']}")
        else:
            print(f"{r['product']:10s} {r['model']:14s} {'결과 없음' if r.get('missing') else 'JSON 깨짐'}")


if __name__ == "__main__":
    main()
