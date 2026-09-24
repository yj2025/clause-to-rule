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


def _six(tag):
    """조문별 ⑥."""
    import gold
    from scoring import score
    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()
    out = {}
    for x in json.loads(Path(f"results/results_{tag}.json").read_text("utf-8")):
        g = tpl.get(x["clause_id"])
        if g is None:
            continue
        got = (x.get("output") or {}).get("rules")
        out[x["clause_id"]] = score(g.get("rules") or [],
                                    got if isinstance(got, list) else [],
                                    agg, P, base)["rate"] * 100
    return out


def final_hit(tags, needles):
    """**최종**(best) 오류에 아직 남아 있는 조문 — 재시도가 못 고친 자리."""
    out = set()
    for t in tags:
        for x in json.loads(Path(f"results/results_{t}.json").read_text("utf-8")):
            if any(any(n in str(e) for n in needles) for e in (x.get("errors") or [])):
                out.add(x["clause_id"])
    return out


def split(base_tags, needles, new_tags, least=3):
    """**닿는 쪽과 안 닿는 쪽을 갈라 ⑥ 을 견준다** (v37 이 쓴 방법).

    처방이 진짜로 먹었으면 닿는 쪽만 움직인다. 둘 다 움직이면 흔들림이다.
    """
    import statistics
    hit, _ = clauses_hit(base_tags, needles)
    HIT = {c for c, n in hit.items() if n >= least}
    S = {t: _six(t) for t in list(base_tags) + list(new_tags)}
    cs = sorted(S[base_tags[0]])
    inn = [c for c in cs if c in HIT]
    out = [c for c in cs if c not in HIT]
    print(f"\n닿는 조문 {len(inn)} · 안 닿는 조문 {len(out)} "
          f"({least}/{len(base_tags)}회 이상 닿으면 «닿는 쪽»)\n")
    print(f"{'':<12}" + "".join(f"{t:>8}" for t in base_tags)
          + f"{'폭':>13}" + "".join(f"{t:>8}" for t in new_tags))
    for name, group in (("닿는 쪽", inn), ("안 닿는 쪽", out)):
        vs = [statistics.mean([S[t][c] for c in group]) for t in base_tags]
        ns = [statistics.mean([S[t][c] for c in group]) for t in new_tags]
        print(f"{name:<12}" + "".join(f"{x:>8.1f}" for x in vs)
              + f"{min(vs):>6.1f}~{max(vs):<6.1f}"
              + "".join(f"{x:>8.1f}" for x in ns))
    for name, group in (("닿는 쪽", inn), ("안 닿는 쪽", out)):
        moved = []
        for c in group:
            vs = [S[t][c] for t in base_tags]
            for t in new_tags:
                if S[t][c] < min(vs) or S[t][c] > max(vs):
                    moved.append((c, vs, t, S[t][c]))
        print(f"\n{name} — 폭 밖으로 움직인 칸 {len(moved)}개")
        for c, vs, t, v in moved:
            print(f"  {c:<16}{t:>5}  " + " · ".join(f"{x:4.0f}" for x in vs)
                  + f" → {v:.0f}")
    # ── 닿는 쪽을 한 번 더 가른다 ────────────────────────────────────────
    #
    # **「재시도가 고친다」가 «옳게 고친다»는 뜻이 아니다.** 1차에 없는 이름을
    # 썼다가 재시도에서 **목록 안의 엉뚱한 이름**으로 바꾸는 길이 있다 (⑮).
    # 그래서 못 고치는 쪽과 스스로 고치는 쪽을 따로 본다.
    import statistics as _st
    stuck = sorted(set(inn) & final_hit(base_tags, needles))
    fixed = sorted(set(inn) - set(stuck))
    if stuck and fixed:
        print(f"\n닿는 쪽을 한 번 더 가르면 — 못 고치는 {len(stuck)} · "
              f"스스로 고치는 {len(fixed)}\n")
        print(f"{'':<18}" + "".join(f"{t:>8}" for t in base_tags)
              + f"{'폭':>13}" + "".join(f"{t:>8}" for t in new_tags))
        for name, group in (("못 고치는 쪽", stuck), ("스스로 고치는 쪽", fixed)):
            vs = [_st.mean([S[t][c] for c in group]) for t in base_tags]
            print(f"{name:<18}" + "".join(f"{x:>8.1f}" for x in vs)
                  + f"{min(vs):>6.1f}~{max(vs):<6.1f}"
                  + "".join(f"{_st.mean([S[t][c] for c in group]):>8.1f}"
                            for t in new_tags))

    print("\n※ 동전 조문은 이미 폭이 0~100 이라 «폭 밖»으로 안 나간다. "
          "평균 줄로 읽어야 한다.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("rounds", nargs="+")
    ap.add_argument("--match", nargs="+", required=True,
                    help="1차 오류에서 찾을 문구")
    ap.add_argument("--split", nargs="+", default=None,
                    help="이 라운드들을 닿는 쪽·안 닿는 쪽으로 갈라 ⑥ 을 견준다")
    a = ap.parse_args(argv)
    hit, bad = clauses_hit(a.rounds, a.match)
    print(f"=== 1차 오류에 {a.match} 가 있는 조문 ===\n")
    print(f"  라운드 {', '.join(a.rounds)} · 1차를 못 읽은 건 {bad}")
    print(f"  **닿는 조문 {len(hit)}개**\n")
    for c, n in sorted(hit.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {c:<16} {n}/{len(a.rounds)}회")
    if a.split:
        split(a.rounds, a.match, a.split)
    return 0


if __name__ == "__main__":
    sys.exit(main())
