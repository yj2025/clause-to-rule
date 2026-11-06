"""두 라운드를 조문별로 대조한다.

군 평균은 조문 하나가 흔들 수 있다 (부록 A.2). 처방이 먹었는지는 **어느 조문이
어느 관문에서 풀렸고 어느 조문이 새로 막혔는지** 로 판정한다.

    python tools/judge.py results/results_v3.json results/results_v2.json
    python tools/judge.py results/results_v3.json results/results_v2.json --watch KBYY-S3-R02 KBYY-S2-R20

`--watch` 에 사전 등록한 조문을 주면 그것만 따로 찍는다. 결과를 보고 나서
판정 대상을 고르면 무엇이든 설명이 되므로, 대상은 라운드 전에 정해 둔다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import json
import sys
from pathlib import Path

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
SYM = dict(zip(KEYS, "①②③④⑤"))


def first_gate(rec):
    for k in KEYS:
        if not rec["final"][k]:
            return k
    return None


def by_clause_run(recs):
    return {(x["clause_id"], x["run"]): x for x in recs}


def judge(new, old, watch=()):
    A, B = by_clause_run(old), by_clause_run(new)
    common = sorted(set(A) & set(B))
    print(f"공통 (조문, 회차) {len(common)}건 "
          f"· 기준 {len(A)}건 · 이번 {len(B)}건\n")

    fixed, broke, moved = [], [], []
    for key in common:
        a, b = first_gate(A[key]), first_gate(B[key])
        if a == b:
            continue
        if a is not None and b is None:
            fixed.append((key, a))
        elif a is None and b is not None:
            broke.append((key, b))
        else:
            moved.append((key, a, b))

    print(f"풀린 회차 {len(fixed)} · 새로 막힌 회차 {len(broke)} · "
          f"걸리는 관문이 바뀐 회차 {len(moved)}\n")

    if fixed:
        print("풀렸다 (전부 통과로)")
        for (cid, run), a in sorted(fixed):
            print(f"  {cid:<16}run{run}  {SYM[a]} {a} 에서 막혀 있었다")
    if broke:
        print("\n새로 막혔다")
        for (cid, run), b in sorted(broke):
            print(f"  {cid:<16}run{run}  이제 {SYM[b]} {b} 에서 막힌다")
    if moved:
        print("\n걸리는 관문이 바뀌었다")
        for (cid, run), a, b in sorted(moved):
            print(f"  {cid:<16}run{run}  {SYM[a]} {a} → {SYM[b]} {b}")

    # 재시도 회귀 — 1차는 통과했는데 최종이 실패
    def regress(recs):
        return {k for k, x in recs.items()
                if any(x["first"][g] and not x["final"][g] for g in KEYS)}

    ra, rb = regress(A), regress(B)
    print(f"\n재시도가 관문을 잃은 회차 (맞바꿈 포함)  기준 {len(ra)} → 이번 {len(rb)}")
    healed = sorted(k for k in ra & set(common) if k not in rb)
    added = sorted(k for k in rb & set(common) if k not in ra)
    for cid, run in healed:
        print(f"  회복 {cid} run{run}")
    for cid, run in added:
        print(f"  새 회귀 {cid} run{run}")

    if watch:
        print(f"\n사전 등록한 조문 {len(watch)}개")
        print(f"{'조문':<16}{'기준':<18}{'이번':<18}{'판정'}")
        print("-" * 66)
        for cid in watch:
            ks = [k for k in common if k[0] == cid]
            if not ks:
                print(f"{cid:<16}{'없음':<18}{'없음':<18}—")
                continue
            a = collections.Counter(first_gate(A[k]) for k in ks)
            b = collections.Counter(first_gate(B[k]) for k in ks)
            fa = f"{sum(1 for k in ks if first_gate(A[k]) is None)}/{len(ks)} 통과"
            fb = f"{sum(1 for k in ks if first_gate(B[k]) is None)}/{len(ks)} 통과"
            pa = sum(1 for k in ks if first_gate(A[k]) is None)
            pb = sum(1 for k in ks if first_gate(B[k]) is None)
            verdict = "좋아짐" if pb > pa else ("나빠짐" if pb < pa else "그대로")
            print(f"{cid:<16}{fa:<18}{fb:<18}{verdict}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("old")
    ap.add_argument("--watch", nargs="*", default=[])
    a = ap.parse_args(argv)
    judge(json.loads(Path(a.new).read_text("utf-8")),
          json.loads(Path(a.old).read_text("utf-8")), a.watch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
