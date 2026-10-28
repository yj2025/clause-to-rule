"""8단계 · 자기 일관성 투표 — 조문당 N 회 표본에서 k 회 이상 나온 효과 키의 rule 만 남긴다 (2026-10-27). GPU 없음.

    python lora/vote.py --pool lora/results/vote_pool_e1.json                    ← 8-1 정답 없이 일치 분포
    python lora/vote.py --kb10 lora/results/vote_dev_e1.json lora/results/vote_test_e1.json   ← 8-2 k 별 채점 (참고 숫자)

표본은 `eval_pool.py` · `eval_adapter.py` 의 `--samples N --temperature T` — 회차마다 재시도 · 관문 · P1 을 그대로 거친 레코드다.
투표: 회차마다 OK rule 의 효과 키(score_split.eff_keys 와 같은 (effect.type, target 또는 value)) 집합을 만들고,
키마다 몇 회차에 나왔는지 센다. k 회 이상인 키만 남기고, 그 키의 rule 은 **처음 나온 회차의 것**을 쓴다.
UNSUPPORTED rule 은 ⑥ 에 안 걸려서 버린다 (combine.py 의 검사 참고).
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score_split as S  # noqa: E402  (ROOT 로 chdir)


def samples(paths):
    """{조문: [회차별 rules (P1 얹음)]} — 회차 순서는 레코드의 run 순."""
    by = defaultdict(list)
    for p in paths:
        for r in json.load(open(p)):
            if "clause_id" in r and "error" not in r:
                by[r["clause_id"]].append((r.get("run", 0), S.rules_of(r, True)))
    return {i: [rules for _, rules in sorted(v, key=lambda x: x[0])] for i, v in by.items()}


def key1(rule):
    return next(iter(S.eff_keys([rule])), None)


def vote(runs, k):
    count, first = Counter(), {}
    for rules in runs:
        seen = set()
        for r in S.ok_rules(rules):
            kk = key1(r)
            if kk in seen:
                continue
            seen.add(kk)
            count[kk] += 1
            first.setdefault(kk, r)
    return [first[kk] for kk in first if count[kk] >= k]


def agreement(runs):
    """조문의 효과 키마다 나온 회차 수."""
    c = Counter()
    for rules in runs:
        for kk in {key1(r) for r in S.ok_rules(rules)}:
            c[kk] += 1
    return c


def pool_report(paths):
    smp = samples(paths)
    n = len(smp)
    N = Counter(len(v) for v in smp.values())
    print(f"보류 풀 {n}조문 · 조문당 회차 {dict(N)}")
    keys = [c for v in smp.values() for c in agreement(v).values()]
    print("효과 키가 나온 회차 수 분포 (키 단위): " + " · ".join(f"{m}회 {keys.count(m)}" for m in range(1, max(N) + 1)))
    first_rule = sum(bool(S.ok_rules(v[0])) for v in smp.values())
    any_rule = sum(any(S.ok_rules(r) for r in v) for v in smp.values())
    print(f"첫 회차만: OK rule 낸 조문 {first_rule}/{n} · 다섯 회차 중 한 번이라도: {any_rule}/{n}")
    print(f"  {'k':>3}{'rule 남은 조문':>14}{'남은 rule':>10}{'기권 조문':>10}")
    for k in range(1, max(N) + 1):
        kept = {i: vote(v, k) for i, v in smp.items()}
        nz = sum(bool(x) for x in kept.values())
        print(f"  {k:>3}{nz:>14}{sum(len(x) for x in kept.values()):>10}{n - nz:>10}")


def kb10_report(paths):
    smp = samples(paths)
    N = max(len(v) for v in smp.values())
    print(f"kb10 표본 {len(smp)}조문 · 조문당 최대 회차 {N}")
    for split in ("dev", "test", "all"):
        ids = [i for i in (S.E.split_ids("dev") + S.E.split_ids("test") if split == "all" else S.E.split_ids(split))
               if i in smp]
        if not ids:
            continue
        rows = {"빈 출력": S.evaluate({i: [] for i in ids}, ids),
                "첫 회차 (T 그대로)": S.evaluate({i: S.ok_rules(smp[i][0]) for i in ids}, ids)}
        for k in range(1, N + 1):
            rows[f"투표 k={k}"] = S.evaluate({i: vote(smp[i], k) for i in ids}, ids)
        n_has = rows["빈 출력"]["n_has"]
        print(f"\n[{split}] {len(ids)}조문 · 정답 rule {n_has} · 정답 빈 {len(ids) - n_has}   (회차마다 P1 얹음)")
        print(f"  {'':22}{'n':>4}{'⑥':>7}{'⑥빈':>7}{'⑥rule':>7}{'재현':>7}{'정밀':>7}   맞춤/정답/출력  rule낸조문")
        for name, v in rows.items():
            print(f"  {name:22}{v['n']:>4}{v['six']:>7}{v['six_empty']:>7}{v['six_has']:>7}{v['rec']:>7}{v['prec']:>7}"
                  f"   {v['hit']:>3}/{v['n_gold']:>3}/{v['n_out']:>3}   {v['out_rule']:>3}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", nargs="*")
    ap.add_argument("--kb10", nargs="*")
    a = ap.parse_args(argv)
    if a.pool:
        pool_report(a.pool)
    if a.kb10:
        kb10_report(a.kb10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
