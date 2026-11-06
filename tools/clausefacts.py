"""조문 단위 사실 — **비율이 아니라 이것으로 라운드를 판정한다.**

2026-09-23 저녁에 세운 규칙이다 (`EXPERIMENTS.md` v43·v44·v45 판정).
⑥ 의 판정선이 ±6.7p 인데 지금까지 어떤 처방도 그만큼 못 올렸다. 비율로 읽으면
흔들림의 윗쪽 끝을 뽑고 「올랐다」고 적게 된다 — v39 를 그렇게 틀렸다.

대신 **조문 단위의 이진 사실**을 센다. v36(`RESTRICT` 5→10) · v39
(`DORMANT_CONTRIBUTION` 0→2) · v41(`event.*` 2→1)이 판정선이 바뀌어도 버틴 이유다.

    python tools/clausefacts.py v46 --against v41 v43 v44 v45

견주는 값은 **여러 프로세스의 폭**이다. 한 라운드와 한 라운드를 견주지 않는다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import json
import sys
from pathlib import Path

import gold
import invent
import mismatch
from scoring import score


def load(tag):
    return json.loads(Path(f"results/results_{tag}.json").read_text("utf-8"))


def _gold_groups():
    out = {}
    for p in sorted(Path("data/gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        out[p.stem] = gold.group_of(json.loads(p.read_text("utf-8")))
    return out


_GOLD = _gold_groups()


def _eff(rule):
    e = rule.get("effect") if isinstance(rule, dict) else None
    if isinstance(e, dict):
        e = e.get("type")
    return e if isinstance(e, str) else None


def _rules(x):
    return [r for r in ((x.get("output") or {}).get("rules") or [])
            if isinstance(r, dict)]


def facts(recs, run=0):
    """한 회차에서 조문 단위 사실을 전부 뽑는다. 값은 **조문 id 집합**이다."""
    recs = [x for x in recs if x.get("run") == run]
    out = collections.defaultdict(set)
    for x in recs:
        cid = x["clause_id"]
        rs = _rules(x)
        for r in rs:
            e = _eff(r)
            if e:
                out[f"effect:{e}"].add(cid)
            if r.get("status") == "UNSUPPORTED":
                out["기권(UNSUPPORTED)"].add(cid)
                # 지문 5번은 「effect 도 그렇게 적는다」고 하는데 스키마·검증기·
                # 정답은 **effect 를 빼라**고 한다 (정답의 기권 rule 28개 전부
                # effect 가 없다). 2026-09-23 에 찾았다. 기권을 시키는 처방이
                # 이 모순에 걸릴 수 있어 따로 센다.
                if "effect" in r:
                    out["기권인데 effect 를 달았다"].add(cid)
                # **기권할 때는 조건도 비운다.** 정답의 기권 rule 28개 중 조건이
                # 든 것은 둘뿐이다. 조건을 남기면 거기 적힌 이름이 계속 관문에
                # 걸린다 — `KBYY-S2-R09` 가 기권으로 바꾸고도 0점인 이유다.
                if r.get("condition"):
                    out["기권인데 조건이 남았다"].add(cid)
                # **이것이 「도망」의 진짜 지표다.** v46 의 되돌리는 선을
                # 「기권한 조문 수」로 그었는데, 그 수는 **옳은 기권과 틀린
                # 기권을 못 가른다.** 15~19 → 24 로 걸렸지만 실제로 손해가 난
                # 자리는 없었다 (2026-09-23 · v46 판정). 정답이 «규칙» 인데
                # 기권한 것만 센다.
                if _GOLD.get(cid) in ("B", "M"):
                    out["정답이 규칙인데 기권했다"].add(cid)
            if _GOLD.get(cid) == "A빈" and r.get("status") == "UNSUPPORTED":
                out["정답이 빈 배열인데 기권했다"].add(cid)
        if not rs:
            out["빈 배열"].add(cid)
        if invent.audit_names([x])["bad"]:
            out["지어낸 이름"].add(cid)
        if mismatch.audit([x], run=run)["bad"]:
            out["타입 안 맞는 비교"].add(cid)
    return out


def six(recs, run=0):
    """조문별 ⑥ (0~100)."""
    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()
    out = {}
    for x in recs:
        if x.get("run") != run:
            continue
        g = tpl.get(x["clause_id"])
        if g is None:
            continue
        got = (x.get("output") or {}).get("rules")
        out[x["clause_id"]] = score(g.get("rules") or [],
                                    got if isinstance(got, list) else [],
                                    agg, P, base)["rate"] * 100
    return out


def _units(tags):
    out = []
    for t in tags:
        recs = load(t)
        for r in sorted({x["run"] for x in recs}):
            out.append((f"{t}#{r}" if len({x['run'] for x in recs}) > 1 else t,
                        recs, r))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("round")
    ap.add_argument("--against", nargs="+", required=True,
                    help="견주는 프로세스들 (여럿이어야 한다)")
    ap.add_argument("--clauses", nargs="*", default=[],
                    help="따로 볼 조문 (표적 · 되돌리는 선)")
    a = ap.parse_args(argv)

    base = [(n, facts(r, k), six(r, k)) for n, r, k in _units(a.against)]
    new_recs = load(a.round)
    new = [(f"{a.round}#{k}" if len({x['run'] for x in new_recs}) > 1 else a.round,
            facts(new_recs, k), six(new_recs, k))
           for k in sorted({x["run"] for x in new_recs})]

    if len(base) < 2:
        print("✗ 견주는 프로세스가 둘 미만이다. 한 값과 한 값을 견주지 않는다.")
        return 1

    keys = sorted({k for _, f, _ in base + new for k in f})
    print(f"=== 조문 단위 사실 — {a.round} vs {len(base)}프로세스 ===\n")
    head = "".join(f"{n[-6:]:>8}" for n, _, _ in base)
    print(f"{'사실 (조문 수)':<26}{head}{'폭':>9}  {a.round:>8}  판정")
    print("-" * (26 + 8 * len(base) + 22))
    for k in keys:
        vs = [len(f.get(k, ())) for _, f, _ in base]
        lo, hi = min(vs), max(vs)
        for n, f, _ in new:
            v = len(f.get(k, ()))
            if lo <= v <= hi:
                mark = "그대로"
            elif abs(v - (hi if v > hi else lo)) == 1:
                # 처방 없는 라운드끼리도 이만큼은 흔들린다 (아래 자기 검사)
                mark = "하나 — **판정 안 함**"
            else:
                mark = "**늘었다**" if v > hi else "**줄었다**"
            print(f"{k:<26}" + "".join(f"{x:>8}" for x in vs)
                  + f"{lo:>4}~{hi:<4}{v:>10}  {mark}")

    # ── 자기 검사 — 견주는 프로세스끼리는 얼마나 흔들리나 ────────────────
    #
    # **이걸 안 찍으면 조문 수도 비율과 같은 함정에 빠진다.** 하나를 빼고
    # 나머지의 폭과 견주면, 처방이 없는데도 줄이 밖으로 나간다.
    n_out = []
    for i, (_, fi, _) in enumerate(base):
        rest = [f for j, (_, f, _) in enumerate(base) if j != i]
        c = 0
        for k in keys:
            ws = [len(f.get(k, ())) for f in rest]
            v = len(fi.get(k, ()))
            if v < min(ws) or v > max(ws):
                c += 1
        n_out.append(c)
    print(f"\n자기 검사 — 견주는 프로세스 하나를 빼고 나머지의 폭과 견주면 "
          f"{'·'.join(map(str, n_out))}줄이 밖으로 나간다 ({len(keys)}줄 중 "
          f"평균 {sum(n_out) / len(n_out):.1f}).")
    print("**처방이 없어도 이만큼 나간다.** 겨냥하지 않은 줄이 하나 움직인 것은 "
          "판정하지 않는다 — 사전 등록한 본 축만 읽는다.")

    if a.clauses:
        print(f"\n조문별 ⑥ — 따로 보는 {len(a.clauses)}개\n")
        print(f"{'조문':<18}{head}{'':>4}{a.round:>10}")
        for c in a.clauses:
            vs = [s.get(c) for _, _, s in base]
            nv = [s.get(c) for _, _, s in new]
            print(f"{c:<18}" + "".join(f"{(f'{v:.0f}' if v is not None else '-'):>8}"
                                       for v in vs)
                  + "    " + "".join(f"{(f'{v:.0f}' if v is not None else '-'):>8}"
                                     for v in nv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
