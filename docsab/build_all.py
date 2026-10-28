"""전 상품 key 요약(Gemma 4 31B, OOM 이면 12B)에 후처리를 붙이고 상품별 상태를 모은다 → docsab/all_products.json (2026-10-13).

    python3 docsab/build_all.py

상품마다: 쓴 모델 · 입력/생성 토큰 · 시간 · JSON 여부 · key 채움 · 후처리(문서 차이 key · 누락 의심 · 물을 입력 추가).
정답이 있는 세 상품(KB스타통장 · 프리N · 별별통장2)은 앞서 돌린 결과를 쓰고 score_target 점수도 붙인다.
"""
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
EARLIER = {"KB스타통장": M3 / "results_kbstar_03_gemma31/gemma31_scored_input.json",
           "KB 프리N통장": M3 / "results_freen_01/gemma31_scored_input.json",
           "KB 별별통장2": M3 / "results_byul2_01/gemma31_scored_input.json"}


def records():
    packets = json.loads(P.SRC.read_text("utf-8"))["packets"]
    for p in packets:
        name, pid = p["product_name"], p["product_id"]
        if name in EARLIER:
            r = json.loads(EARLIER[name].read_text("utf-8"))
            yield p, dict(r, product_id=pid, source="10-12~13 개별 실행", model="google/gemma-4-31B-it"), EARLIER[name]
            continue
        main = M3 / "results_all_gemma31" / f"{pid}.json"
        fb = M3 / "results_all_gemma12_fallback" / f"{pid}.json"
        if not main.exists():
            yield p, None, None
            continue
        r = json.loads(main.read_text("utf-8"))
        if r.get("error") and fb.exists():
            r2 = json.loads(fb.read_text("utf-8"))
            r2["fallback_from"] = r.get("error")
            yield p, r2, fb
        else:
            yield p, r, main


def main():
    rows, screens = [], {}
    for p, r, path in records():
        name = p["product_name"]
        n_keys = len(p["keys"])
        row = {"product": name, "product_id": p["product_id"], "category": p.get("product_category"), "keys": n_keys}
        if r is None:
            row["status"] = "아직"
            rows.append(row)
            continue
        row.update(model=r.get("model", "").split("/")[-1], in_tokens=r.get("in_tokens"), gen_tokens=r.get("gen_tokens"),
                   sec=r.get("sec"), error=r.get("error"), fallback_from=r.get("fallback_from"), truncated=r.get("truncated"))
        if not r.get("parsed"):
            row["status"] = r.get("error") or "JSON 깨짐"
            rows.append(row)
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            post = P.run(str(path))
        items = json.loads(Path(post).read_text("utf-8"))["parsed"]["items"]
        row.update(status="완료", filled=sum(1 for i in items if i.get("summary")),
                   diff_keys=[i["key"] for i in items if i["_check"].get("doc_diff")],
                   missing=sum(len(i["_check"].get("missing", [])) for i in items),
                   ui_added=sum(len(i["_check"].get("user_input_added", [])) for i in items))
        if name in S.TARGETS:
            with contextlib.redirect_stdout(io.StringIO()):
                S.main(str(path))
            t = json.loads(Path(str(path).replace(".json", ".score.json")).read_text("utf-8"))["totals"]
            row["target_score"] = f"줄 {t['lines_hit']}/{t['lines']} · 문서 차이 {t['diff_hit']}/{t['diff_need']}"
        rows.append(row)
        screens[name] = {"names": {k["key"]: k["name"] for k in p["keys"]}, "items": items}
    done = [r for r in rows if r["status"] == "완료"]
    summary = {"total": len(rows), "done": len(done), "pending": sum(r["status"] == "아직" for r in rows),
               "failed": [r["product"] for r in rows if r["status"] not in ("완료", "아직")],
               "fallback": [r["product"] for r in rows if r.get("fallback_from")],
               "gen_hours": round(sum(r.get("sec") or 0 for r in rows) / 3600, 1)}
    (HERE / "all_products.json").write_text(json.dumps({"summary": summary, "rows": rows, "screens": screens},
                                                       ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
