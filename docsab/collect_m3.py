"""M3 compare_terms.py 결과 폴더 → 모델별 채점 입력(<모델>_scored_input.json) (2026-10-13).

    /workspace/.venv/bin/python docsab/collect_m3.py <결과폴더> <상품명>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run_local_v2 import parse_json  # noqa: E402


def main(folder, product):
    folder = Path(folder)
    for f in sorted(folder.glob("*.json")):
        if f.stem in ("manifest", "run_status") or "_scored_input" in f.stem or f.stem.endswith((".post", ".score")):
            continue
        r = json.loads(f.read_text("utf-8"))
        p = r["parts"][0]
        j = parse_json(p["summary"])
        out = folder / f"{f.stem}_scored_input.json"
        out.write_text(json.dumps({"product_name": product, "model": r["model"], "parsed": j,
                                   "in_tokens": p["input_tokens"], "gen_tokens": p["output_tokens"],
                                   "sec": round(p["generation_seconds"], 1), "truncated": p["hit_output_limit"]},
                                  ensure_ascii=False, indent=1), "utf-8")
        print(f"{f.stem}: 입력 {p['input_tokens']} · 생성 {p['output_tokens']} · {round(p['generation_seconds'])}초 · {'읽힘' if j else '안 읽힘'} → {out.name}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
