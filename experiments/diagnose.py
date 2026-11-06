"""한 라운드의 실패를 처방 후보로 바꾸기 위한 브리핑.

라운드 사이에 이걸 읽고 **한 번에 한 가지** 처방을 고른다. 둘을 같이 넣으면
지표가 움직여도 어느 쪽이 먹었는지 못 가른다 (§9 12번).

    python experiments/diagnose.py results/results_v2.json
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import json
import sys
from pathlib import Path

import analyze
import validate as V

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
SYM = dict(zip(KEYS, "①②③④⑤"))


def _first_gate(x):
    """이 회차가 처음 걸린 관문."""
    for k in KEYS:
        if not x["final"][k]:
            return k
    return None


def brief(recs, texts, examples=2):
    n = len(recs)
    print(f"레코드 {n}건 · 조문 {len({x['clause_id'] for x in recs})}개\n")

    # 1. 어느 관문에서 처음 걸리나
    first = collections.Counter(_first_gate(x) for x in recs)
    print("처음 걸리는 관문 (그 뒤 관문은 이것 때문에 같이 실패한다)")
    print(f"{'관문':<20}{'건수':>6}{'몫':>8}")
    print("-" * 36)
    for k in KEYS:
        if first[k]:
            print(f"{SYM[k]} {k:<17}{first[k]:>6}{first[k] / n * 100:>7.1f}%")
    print(f"{'전부 통과':<20}{first[None]:>6}{first[None] / n * 100:>7.1f}%\n")

    # 2. 오류 메시지 묶음
    msgs = collections.Counter()
    for x in recs:
        for e in x.get("errors") or []:
            head = e.split(".")[0].split(":")[0].strip()
            if ": " in e:
                head = e.split(": ")[0] + ": " + e.split(": ")[1].split(".")[0][:34]
            msgs[head] += 1
    print("오류 메시지 (상위 12)")
    print(f"{'메시지':<62}{'건수':>6}")
    print("-" * 70)
    for m, c in msgs.most_common(12):
        print(f"{m[:60]:<62}{c:>6}")

    # 3. 틀린 형태
    f = analyze.forms(recs)
    if f:
        print("\n틀린 형태")
        for k, v in f.most_common():
            print(f"  {k:<40}{v:>5}")

    # 4. 한 번도 못 넘는 조문
    by = collections.defaultdict(list)
    for x in recs:
        by[x["clause_id"]].append(x)
    stuck = [(cid, rs) for cid, rs in by.items()
             if not any(all(x["final"][k] for k in KEYS) for x in rs)]
    print(f"\n한 번도 못 넘는 조문 {len(stuck)} / {len(by)}")
    for cid, rs in sorted(stuck)[:12]:
        g = _first_gate(rs[0])
        print(f"  {cid:<16}{SYM.get(g, '?')} {g or '':<14}자수 {len(texts.get(cid, '')):>5}")

    # 5. 실패 실물 — 처방을 고르려면 실제 출력을 봐야 한다
    print(f"\n실패 실물 (관문별 {examples}개)")
    for k in KEYS:
        got = [x for x in recs if _first_gate(x) == k][:examples]
        if not got:
            continue
        print(f"\n--- {SYM[k]} {k} ---")
        for x in got:
            raw = (x["raw_first"] or "").strip()
            print(f"[{x['clause_id']} run{x['run']}] 출력 {len(raw)}자 "
                  f"· 잘림 {x['truncated']} · 시도 {x['n_attempts']}")
            print(f"  {raw[:260]}")
            for e in (x.get("errors") or [])[:2]:
                print(f"  오류: {e[:150]}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--clauses", default="data/corpus.json")
    ap.add_argument("--examples", type=int, default=2)
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in json.loads(Path(a.clauses).read_text("utf-8"))}
    brief(recs, texts, a.examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
