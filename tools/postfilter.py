"""앞 판의 결과에 후처리를 다시 건다 — v123 `grounding.abstain_ungrounded` · v127 `reasons.tag_empty` (2026-10-06).

    python tools/postfilter.py results/results_v121.json results/results_v123.json --clauses data/corpus.json
    python tools/postfilter.py showcase/results_kb10v121a.json showcase/results_kb10v123a.json --clauses showcase/clauses_key.json

후처리는 재시도 뒤 **고른 출력에만** 걸리므로, 같은 출력에 다시 걸면 러너가 낸 것과 같다 —
GPU 로 다시 돌리지 않는다. 관문 ①~⑤ 표시(`final`)는 고르기 전에 잰 값이라 그대로 둔다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]
import argparse
import json
from pathlib import Path

import grounding
import reasons


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--clauses", required=True)
    a = ap.parse_args(argv)
    texts = {c["id"]: c["text"] for c in json.loads(Path(a.clauses).read_text("utf-8"))}
    recs = json.loads(Path(a.src).read_text("utf-8"))
    n = 0
    for x in recs:
        x["output"], x["ungrounded"] = grounding.abstain_ungrounded(x.get("output"), texts[x["clause_id"]])
        x["output"], _ = reasons.tag_empty(x["output"], texts[x["clause_id"]])   # v127
        x["postfilter_from"] = Path(a.src).name
        n += bool(x["ungrounded"])
    Path(a.dst).write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    print(f"{a.dst}: 기권으로 바꾼 조문 {n}")


if __name__ == "__main__":
    main()
