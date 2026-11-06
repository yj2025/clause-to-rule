"""판정선을 여러 **프로세스**의 결과에서 다시 계산한다.

`tools/noise.py` 는 값을 들고 있고, 이 파일은 그 값을 **어디서 얻었는지**를 재현한다.

    python tools/floors.py v41 v43 v44 v45

전제 — 넘긴 라운드들은 **지문이 같아야 한다** (처방이 같다). 다르면 멈춘다.
한 라운드 안에 회차가 여럿이면 회차마다 따로 센다. 다만 **같은 프로세스의
회차는 서로 닮으므로** 프로세스 수가 판정선의 신뢰를 정한다 (`NOISE.md`).
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import collections
import json
import statistics
import sys
from pathlib import Path

import declare
import gold
import invent
import vacuous
from scoring import score

# 46조문 중 하나가 뒤집히면 2.2p 다. **σ 가 0 이어도 그보다 가늘게 판정하지 않는다** —
# 네 프로세스에서 한 번도 안 흔들렸다는 것이 흔들릴 수 없다는 뜻은 아니다.
RESOLUTION = 100 / 46

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok", "empty")
SYM = dict(zip(KEYS, ["①", "②", "③", "④", "⑤", "⑦"]))
NAME = dict(zip(KEYS, ["JSON 파싱", "스키마 적합", "카탈로그 준수", "quote 일치",
                       "실행 가능", "빈 배열"]))


def load(tag):
    p = Path(f"results/results_{tag}.json")
    return json.loads(p.read_text("utf-8"))


def fingerprint(recs):
    return {json.dumps(x["prompt"], sort_keys=True) for x in recs}


def units(tags):
    """(이름, 레코드) 목록 — 라운드×회차 하나가 한 단위다."""
    out = []
    for t in tags:
        recs = load(t)
        for r in sorted({x["run"] for x in recs}):
            out.append((f"{t}#{r}" if len({x['run'] for x in recs}) > 1 else t,
                        [x for x in recs if x["run"] == r]))
    return out


def rate(recs, key, phase="final"):
    return sum(bool(x[phase][key]) for x in recs) / len(recs) * 100


def six(recs, tpl, agg, P, base):
    """조문별 ⑥ (0~100)."""
    out = {}
    for x in recs:
        g = tpl.get(x["clause_id"])
        if g is None:
            continue
        got = (x.get("output") or {}).get("rules")
        out.setdefault(x["clause_id"], []).append(
            score(g.get("rules") or [], got if isinstance(got, list) else [],
                  agg, P, base)["rate"] * 100)
    return {c: sum(v) / len(v) for c, v in out.items()}


def floor_of(vals, n=46):
    """판정선 = 2σ, 다만 조문 하나(=100/n p)보다 가늘게는 안 잡는다."""
    return round(max(2 * statistics.pstdev(vals), 100 / n), 1)


def line(label, vals, n=46, width=8):
    sd = statistics.pstdev(vals)
    f = floor_of(vals, n)
    mark = "*" if 2 * sd < 100 / n else " "
    return (f"{label:<18}" + "".join(f"{v:>{width}.1f}" for v in vals)
            + f"{sd:>8.2f}p{'±' + format(f, '.1f') + 'p':>9}{mark}")


def main(tags):
    U = units(tags)
    fps = set()
    for _, recs in U:
        fps |= fingerprint(recs)
    print(f"=== 판정선 재계산 — {len(U)}단위 · {len(tags)}프로세스 ===\n")
    print("  " + " · ".join(n for n, _ in U))
    if len(fps) != 1:
        print(f"\n✗ 지문이 {len(fps)}종이다. 처방이 다른 라운드는 섞을 수 없다.")
        return 1
    # 2026-09-24 — **지문 1종이 「같은 구성」을 보장하지 않는다.** v41~v45 와
    # v46~v49 는 재시도 지문이 다른데 해시가 같다. `retry` 키를 그 뒤에
    # 넣었으므로, 키가 없는 옛 라운드를 섞을 때는 사람이 확인해야 한다.
    if "retry" not in json.loads(next(iter(fps))):
        print("  ⚠ 지문에 `retry` 키가 없는 옛 라운드다 (2026-09-24 이전).")
        print("    **재시도 지문이 달라도 해시가 같다.** 섞기 전에 라운드가 "
              "같은 처방인지 사람이 확인할 것.")
    print(f"  지문 1종 — 처방이 같다\n")

    head = "".join(f"{n.split('#')[0][-3:] + ('#' + n.split('#')[1] if '#' in n else ''):>8}"
                   for n, _ in U)
    print(f"{'축':<18}{head}{'σ':>9}{'판정선':>9}")
    print("-" * (18 + 8 * len(U) + 18))
    floors = {}
    for k in KEYS:
        vals = [rate(r, k) for _, r in U]
        floors[SYM[k]] = floor_of(vals)
        print(line(f"{SYM[k]} {NAME[k]}", vals))

    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()
    per = [six(r, tpl, agg, P, base) for _, r in U]

    vals = [sum(d.values()) / len(d) for d in per]
    floors["⑥"] = floor_of(vals)
    print(line("⑥ 실행 결과", vals))

    # ⑫ 는 조문이 단위, ⑬⑭ 는 이름/rule 이 단위다 — 해상도 하한이 다르다.
    for sym, name, fn in (("⑫", "선언 일치", lambda r: declare.audit(r)),
                          ("⑬", "지어낸 이름", lambda r: invent.audit_names(r)),
                          ("⑭", "헛조건", lambda r: vacuous.audit(r))):
        a = [fn(r) for _, r in U]
        vals = [x["rate"] for x in a]
        nn = min(x.get("n") or x.get("checked") or 46 for x in a)
        floors[sym] = floor_of(vals, nn)
        print(line(f"{sym} {name}", vals, nn))

    print(f"\n⑥ 갈래별 — 정답의 모양마다 판정선이 다르다\n")
    print(f"{'갈래':<18}{head}{'σ':>9}{'판정선':>9}")
    print("-" * (18 + 8 * len(U) + 18))
    gmap = {c: gold.group_of(g) for c, g in tpl.items()}
    gfloors = {}
    for grp in ("A빈", "A기권", "M", "B"):
        cs = [c for c, g in gmap.items() if g == grp]
        vals = [sum(d[c] for c in cs if c in d) / len([c for c in cs if c in d])
                for d in per]
        gfloors[grp] = floor_of(vals, len(cs))
        print(line(f"{grp} ({len(cs)}조문)", vals, len(cs)))

    # ── 동전 — 단위마다 값이 갈리는 조문 ────────────────────────────────
    coins = []
    for c in sorted(tpl):
        vs = [d[c] for d in per if c in d]
        if len(vs) == len(per) and len(set(vs)) > 1:
            coins.append((c, gmap[c], vs))
    print(f"\n동전 — {len(per)}단위에서 값이 갈린 조문 {len(coins)}/{len(tpl)}\n")
    for c, g, vs in sorted(coins, key=lambda t: -statistics.pstdev(t[2])):
        print(f"  {c:<16}{g:>6}  " + " · ".join(f"{v:>5.1f}" for v in vs)
              + f"   σ {statistics.pstdev(vs):>5.1f}p")

    cset = {c for c, _, _ in coins}

    # ── 동전을 뺀 값에 판정선을 붙이면 **순환이다** ──────────────────────
    # 동전은 「이 표본에서 갈린 조문」으로 정의했다. 그것을 빼고 같은 표본으로
    # 흔들림을 재면 0 이 나올 수밖에 없다. 옛 `FLOOR_NO_COIN = 2.4` 가 그렇게
    # 나온 값이다. 대신 **반반으로 갈라** 앞 절반으로 동전을 뽑고 뒤 절반에서
    # 흔들림을 잰다 — 이건 순환이 아니다.
    half = len(per) // 2
    if half >= 2:
        a, b = per[:half], per[half:]
        ca = {c for c in tpl
              if len({d[c] for d in a if c in d}) > 1}
        vals = [sum(v for c, v in d.items() if c not in ca)
                / len([c for c in d if c not in ca]) for d in b]
        print(f"\n반반 확인 — 앞 {half}단위로 동전 {len(ca)}개를 뽑고 "
              f"뒤 {len(b)}단위에서 잰다")
        print(f"  뺀 뒤 ⑥ " + " · ".join(f"{v:.1f}" for v in vals)
              + f" · 폭 {max(vals) - min(vals):.1f}p")
        print(f"  같은 표본으로 빼고 재면 0 이 나온다 — **그 값은 쓰지 않는다**")

    print("\n── tools/noise.py 에 넣을 값 ──\n")
    print("FLOORS = " + json.dumps(floors, ensure_ascii=False))
    print("GROUP_FLOORS = " + json.dumps(gfloors, ensure_ascii=False))
    print("COINS = " + json.dumps(sorted(cset), ensure_ascii=False))
    print("\n※ * 표는 2σ 가 조문 하나(2.2p)보다 작아 그 값으로 올린 축이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
