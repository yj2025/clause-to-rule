"""1차 출력을 **다시 채점**한다 — 재시도 지문에 붙는 처방은 이걸로 선측정한다.

2026-09-23 · v46 에서 틀렸다. 재시도 지문에 조건부 블록을 붙이는 처방을
설계하면서 **최종(best) 시도의 오류로 「닿는 조문」을 셌다.** 8개로 나왔다.
실제로는 **27개**다 — 재시도 지문은 **1차 시도의 오류**로 만들어지는데,
1차에 지어냈다가 재시도로 고친 조문은 최종 오류에 안 남기 때문이다.

레코드에 `raw_first` 가 있으니 다시 채점하면 1차 오류를 되살릴 수 있다.

    python firsterr.py v41 v43 v44 v45 --match 카탈로그에 없는

**지문(1차)에 붙는 처방은 코퍼스로 세면 된다.** 이 도구는 **재시도에 붙는
처방** 전용이다.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import validate as V


def _texts():
    return {c["id"]: c.get("text", "")
            for c in json.loads(Path("data/corpus.json").read_text("utf-8"))}


def first_errors(rec, texts):
    """1차 출력을 지금 검증기로 다시 채점한다. 못 읽으면 None."""
    raw = rec.get("raw_first") or ""
    try:
        out = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            out = json.loads(m.group(0))
        except Exception:
            return None
    try:
        return V.score_record(out, texts.get(rec["clause_id"], ""))["errors"] or []
    except Exception:
        return None


def clauses_hit(tags, needles):
    """needles 중 하나라도 1차 오류에 있는 조문 → {조문: 회수}."""
    texts = _texts()
    hit = collections.Counter()
    bad = 0
    for t in tags:
        for x in json.loads(Path(f"results/results_{t}.json").read_text("utf-8")):
            es = first_errors(x, texts)
            if es is None:
                bad += 1
                continue
            if any(any(n in str(e) for n in needles) for e in es):
                hit[x["clause_id"]] += 1
    return hit, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("rounds", nargs="+")
    ap.add_argument("--match", nargs="+", required=True,
                    help="1차 오류에서 찾을 문구")
    a = ap.parse_args(argv)
    hit, bad = clauses_hit(a.rounds, a.match)
    print(f"=== 1차 오류에 {a.match} 가 있는 조문 ===\n")
    print(f"  라운드 {', '.join(a.rounds)} · 1차를 못 읽은 건 {bad}")
    print(f"  **닿는 조문 {len(hit)}개**\n")
    for c, n in sorted(hit.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {c:<16} {n}/{len(a.rounds)}회")
    return 0


if __name__ == "__main__":
    sys.exit(main())
