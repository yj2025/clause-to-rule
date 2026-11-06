"""⑫ 선언 — 모델이 gold 와 같은 판정을 내렸나.

**왜 이 축이 필요한가.**

⑥ 은 실행 결과를 비교하는데, `UNSUPPORTED` rule 은 effect 가 없어서 resolver 가
아무것도 싣지 않는다. **그래서 빈 배열과 실행 결과가 완전히 같다.**
gold 15개 중 10개가 이 상태라 ⑥ 의 변별력이 5개에서만 나온다.

뜻으로는 전혀 다르다.

    빈 배열      옮길 것이 없다 (사실 서술·분류 라벨)
    UNSUPPORTED  옮길 조건과 효과는 있는데 카탈로그에 수단이 없다
    정상 rule    옮길 수 있다

후자는 카탈로그를 넓히라는 신호이고 전자는 아니다. 이걸 못 가르면
"모델이 무엇을 판단했는지" 를 아예 못 본다.

세 갈래 판정을 gold 와 맞춰 본다. **실행 결과가 아니라 선언을 본다.**

기존 ⑥ 을 건드리지 않는다. 따로 센다.

    python tools/declare.py results/results_v6.json
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import json
import sys
from pathlib import Path

GOLD_DIR = Path("data/gold")

EMPTY, UNSUP, MIXED, OK = "빈 배열", "UNSUPPORTED 뿐", "섞임", "정상 rule"


def verdict(rules):
    """세 갈래 (+섞임). rules 가 리스트가 아니면 None(무출력)."""
    if not isinstance(rules, list):
        return None
    rs = [r for r in rules if isinstance(r, dict)]
    if not rs:
        return EMPTY
    u = sum(1 for r in rs if r.get("status") == "UNSUPPORTED")
    if u == len(rs):
        return UNSUP
    return MIXED if u else OK


def _gold():
    out = {}
    for p in sorted(GOLD_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        out[p.stem] = json.loads(p.read_text("utf-8"))
    return out


def audit(recs, run=None):
    g = _gold()
    rows, hit = [], 0
    conf = collections.Counter()
    for x in recs:
        if run is not None and x["run"] != run:
            continue
        d = g.get(x["clause_id"])
        if d is None:
            continue
        want = verdict(d.get("rules") or [])
        got = verdict((x.get("output") or {}).get("rules")
                      if isinstance(x.get("output"), dict) else None)
        ok = want == got
        hit += ok
        conf[(want, got)] += 1
        rows.append((x["clause_id"], x["run"], want, got, ok))
    n = len(rows)
    return {"n": n, "hit": hit, "rate": hit / n * 100 if n else 0.0,
            "rows": rows, "conf": conf}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--run", type=int, default=0)
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    r = audit(recs, a.run)
    print(f"=== {Path(a.results).name} (run {a.run}) ===\n")
    print(f"⑫ 선언 일치 — gold 가 있는 {r['n']}조문 중 "
          f"**{r['hit']}개({r['rate']:.1f}%)가 gold 와 같은 판정**\n")
    print(f"{'조문':<16}{'gold':<18}{'생성':<18}")
    print("-" * 56)
    for cid, run, want, got, ok in r["rows"]:
        print(f"{cid:<16}{want:<18}{str(got):<18}{'' if ok else '←'}")
    print(f"\n{'gold':<18}{'생성':<18}{'건수':>6}")
    print("-" * 44)
    for (w, g), n in r["conf"].most_common():
        print(f"{w:<18}{str(g):<18}{n:>6}")
    print("\n⑥ 은 빈 배열과 UNSUPPORTED 를 못 가른다. 이 축은 선언을 본다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
