"""앞 판의 결과에 v123 후처리(`grounding.abstain_ungrounded`)를 다시 건다 (2026-10-06).

    python postfilter.py results/results_v121.json results/results_v123.json --clauses data/corpus.json
    python postfilter.py showcase/results_kb10v121a.json showcase/results_kb10v123a.json --clauses showcase/clauses_key.json

후처리는 재시도 뒤 **고른 출력에만** 걸리므로, 같은 출력에 다시 걸면 러너가 낸 것과 같다 —
GPU 로 다시 돌리지 않는다. 관문 ①~⑤ 표시(`final`)는 고르기 전에 잰 값이라 그대로 둔다.
"""
import argparse
import json
from pathlib import Path

import grounding


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
        x["postfilter_from"] = Path(a.src).name
        n += bool(x["ungrounded"])
    Path(a.dst).write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    print(f"{a.dst}: 기권으로 바꾼 조문 {n}")


if __name__ == "__main__":
    main()
