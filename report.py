"""한 라운드의 지표를 한 장으로.

    python report.py results/results_v1.json [--baseline results/....json]

①~⑤ 는 검증기가, ⑦ 은 빈 배열 축이, ⑥ 은 gold 가 낸다. 셋을 따로 읽어야 한다 —
하나가 무너질 때 나머지가 같이 0 이 되면 어느 축이 움직였는지 못 읽는다.

군 평균만 보지 말 것. 조문 하나가 군 전체를 흔들 수 있다 (부록 A.2).
그래서 조문별 표를 같이 찍는다.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import analyze
import gold
import validate as V
from scoring import score

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
SYMS = "①②③④⑤"
SYM = dict(zip(KEYS, SYMS))
NAME = ("JSON 파싱", "스키마 적합", "카탈로그 준수", "quote 원문 일치", "실행 가능")


def _rate(recs, phase, key):
    return analyze.rate(recs, phase, key) if recs else 0.0


def unsupported_stats(recs):
    """⑧ — UNSUPPORTED 를 얼마나 쓰나.

    UNSUPPORTED rule 은 `condition` 이 {} 라 이름이 없고, 그래서 ③ 카탈로그 준수를
    **공짜로 통과한다.** UNSUPPORTED 를 늘리도록 가르치는 처방은 뜻이 좋아지지
    않아도 ③ 을 올릴 수 있다. 유실된 기록 §9 11번 — "새 탈출구를 열 때는 채점을
    먼저 막는다" — 가 그 자리다.

    ⑥ 도 UNSUPPORTED 와 빈 배열을 못 가른다(둘 다 실행 결과가 같다).
    그래서 이 축이 없으면 회피를 볼 방법이 아예 없다.

    반환: rule 단위 비율, 조문(레코드) 단위 분포
    """
    rules = unsup = 0
    kind = collections.Counter()
    for x in recs:
        rs = (x.get("output") or {}).get("rules")
        if not isinstance(rs, list):
            kind["무출력"] += 1
            continue
        rs = [r for r in rs if isinstance(r, dict)]
        u = sum(1 for r in rs if r.get("status") == "UNSUPPORTED")
        rules += len(rs)
        unsup += u
        if not rs:
            kind["빈 배열"] += 1
        elif u == len(rs):
            kind["UNSUPPORTED 뿐"] += 1
        elif u:
            kind["섞임"] += 1
        else:
            kind["OK 뿐"] += 1
    return {"rule": rules, "unsup": unsup,
            "rate": unsup / rules * 100 if rules else 0.0, "kind": kind}


def gate8(recs, base=None):
    a = unsupported_stats(recs)
    print(f"\n⑧ UNSUPPORTED 사용 (③ 을 회피로 딸 수 있는 경로다)")
    line = f"  rule 단위 {a['unsup']}/{a['rule']} = {a['rate']:.1f}%"
    if base:
        b = unsupported_stats(base)
        line += f"   (기준 {b['rate']:.1f}% · {a['rate'] - b['rate']:+.1f}p)"
    print(line)
    print(f"  레코드 단위 " + " · ".join(f"{k} {v}" for k, v in a["kind"].most_common()))
    if base:
        b = unsupported_stats(base)
        print(f"  기준        " + " · ".join(f"{k} {v}" for k, v in b["kind"].most_common()))


def gate9(recs, texts, base=None):
    """⑨ 근거 — 생성물의 수가 조문에 있나.

    **첫 회차로 맞춰 잰다.** 회차 수가 다른 라운드를 그냥 비교하면 틀린다.

    **분모는 조문이다.** rule 을 분모로 두면 1회 불확실 구간이 최대 ±46.5p 라
    라운드 비교에 못 쓰고, 모델이 rule 을 덜 내기만 해도 비율이 좋아진다.
    조문 단위는 ±2.5p 다 — NOISE.md 참고.
    """
    import grounding
    recs = [x for x in recs if x["run"] == 0]
    a = grounding.audit(recs, texts)
    if not a["checked"]:
        return
    print(f"\n⑨ 근거 없는 수 (은행 금리를 발명하는 것은 가장 비싼 오류다)")
    line = (f"  조문 {a['clauses']}개 중 지어낸 수가 있는 조문 "
            f"{a['bad_clauses']}개 = {a['rate']:.1f}%")
    if base:
        b = grounding.audit([x for x in base if x["run"] == 0], texts)
        line += f"   (기준 {b['rate']:.1f}% · {a['rate'] - b['rate']:+.1f}p)"
    print(line)
    print(f"  (참고 · 라운드 비교엔 안 쓴다) 수치 effect {a['checked']}개 중 "
          f"{a['invented']}개 = {a['rule_rate']:.1f}%")
    if a["by_clause"]:
        print("  " + " · ".join(f"{c} {n}" for c, n in a["by_clause"].most_common(6)))
    print("  ①~⑤ 는 값의 출처를 묻지 않는다. ⑥ 도 발화하지 않는 창작은 못 잡는다.")


def gate11(recs, texts):
    """⑪ 뒷받침 — 인용문이 rule 을 받치나. 하한이다."""
    import support
    a = support.audit(recs, texts)
    if not a["checked"]:
        return
    print(f"\n⑪ 인용문이 rule 을 안 받침 (**하한** — 기계로 확실한 것만 센다)")
    print(f"  인용문 있는 rule {a['checked']}개 중 {a['bad']}개 = {a['rate']:.1f}%")
    if a["kinds"]:
        print("  " + " · ".join(f"{k[:28]} {n}" for k, n in a["kinds"].most_common(3)))
    print("  ④ 는 인용문이 원문에 있는지만 본다. 사람이 읽으면 어긋남이 훨씬 많다.")


def gate12(recs):
    """⑫ 선언 — gold 와 같은 판정을 내렸나."""
    import declare
    a = declare.audit(recs, run=0)
    if not a["n"]:
        return
    print(f"\n⑫ 선언 일치 — gold {a['n']}조문 중 {a['hit']}개 = {a['rate']:.1f}%")
    over = sum(n for (w, g), n in a["conf"].items()
               if w in (declare.EMPTY, declare.UNSUP)
               and g in (declare.OK, declare.MIXED))
    under = sum(n for (w, g), n in a["conf"].items()
                if w in (declare.OK, declare.MIXED)
                and g in (declare.EMPTY, declare.UNSUP))
    print(f"  과생성(만들 것이 없는데 만듦) {over}건 · 과소(만들 수 있는데 포기) {under}건")
    print("  ⑥ 은 빈 배열과 UNSUPPORTED 를 못 가른다. 이 축은 선언을 본다.")


def with_rules(recs):
    """rule 을 하나라도 낸 회차만. 생성물이 이상해도 죽지 않는다."""
    out = []
    for x in recs:
        o = x.get("output")
        rs = o.get("rules") if isinstance(o, dict) else None
        if isinstance(rs, list) and rs:
            out.append(x)
    return out


def gates_on_rules(recs, base=None):
    """③④⑤ 를 **rule 이 있는 회차만으로** 다시 잰다.

    빈 배열은 검사할 이름도, 인용문도, 실행할 것도 없어서 ③④⑤ 가 자동 실패다.
    **gold 가 빈 배열인 조문에서 모델이 정답을 내도 벌점을 받는다** (v10 에서
    `KBYY-S2-R06` 과 `KBONE-S2-R04` 가 그랬다).

    그래서 ①~⑤ 는 **rule 을 많이 낼수록 유리한 축**이다. 과생성이 형식 지표를 올린다.
    이 갈래는 그 편향을 뺀 값이다. 부록 A.3 의 "무출력 제외 갈래" 와 같은 방식이다.

    **기존 ①~⑤ 를 바꾸지 않는다.** 나란히 찍는다.
    """
    R = with_rules(recs)
    if not R:
        return
    print(f"\n③④⑤ 를 rule 있는 회차만으로 ({len(R)}/{len(recs)}건)")
    print(f"{'지표':<22}{'전체':>9}{'rule 있는 것만':>14}{'차이':>8}")
    print("-" * 54)
    for i, k in enumerate(KEYS):
        if k in ("json_ok", "schema_ok"):
            continue
        a, b = _rate(recs, "final", k), _rate(R, "final", k)
        print(f"{SYMS[i]} {NAME[i]:<19}{a:>8.1f}%{b:>13.1f}%{b - a:>+7.1f}p")
    if base:
        B = with_rules(base)
        if B:
            print(f"\n{'':<22}{'기준':>9}{'이번':>14}{'변화':>8}")
            for i, k in enumerate(KEYS):
                if k in ("json_ok", "schema_ok"):
                    continue
                a, b = _rate(B, "final", k), _rate(R, "final", k)
                print(f"{SYMS[i]} {NAME[i]:<19}{a:>8.1f}%{b:>13.1f}%{b - a:>+7.1f}p")


def gate13(recs):
    """⑬ 지어낸 코드 — 카탈로그에 없는 개념을 문자열에 담았나."""
    import invent
    a = invent.audit([x for x in recs if x["run"] == 0])
    if not a["checked"]:
        return
    print(f"\n⑬ 지어낸 코드 — 문자열 값 {a['checked']}개 중 {a['bad']}개 = {a['rate']:.1f}%")
    if a["names"]:
        print("  " + " · ".join(f"{k} {v}" for k, v in a["names"].most_common(6)))
    print("  v12 부터 ③ 에 물린다. 그 전 라운드는 이 경로로 관문을 통과했다.")


def gate14(recs):
    """⑭ 헛조건 — 조건이 붙었는데 언제나 참인가."""
    import vacuous
    a = vacuous.audit([x for x in recs if x["run"] == 0])
    if not a["checked"]:
        return
    print(f"\n⑭ 헛조건 — 조건이 붙은 rule {a['checked']}개 중 "
          f"{a['bad']}개 = {a['rate']:.1f}% (어떤 문맥에서도 참)")
    print(f"   미가동 {a['idle']}개 = {a['idle_rate']:.1f}% — "
          f"프로필이 그 변수를 안 흔든 것이라 모델 탓이 아니다")
    if a["by_clause"]:
        print("  " + " · ".join(f"{c} {n}" for c, n in a["by_clause"].most_common(6)))
    print("  관문 다섯이 전부 통과시킨다. ⑫ 도 못 본다 — 판정은 맞기 때문이다.")


def gate10(recs):
    """⑩ 합성 — 조문을 **합쳐서** 한 고객의 금리를 낸다.

    ⑥ 은 조문을 고립시켜 재므로 합성할 때만 드러나는 파괴를 못 본다.
    그런데 이 축은 여태 `report.py` 에 없었다 — `compose.py` 를 따로 돌려야
    보였고, 그래서 **라운드 판정에서 한 번도 안 썼다.** 2026-09-14 에 넣는다.

    비율만 찍지 않는다. 값이 25.0 · 56.2 · 75.0 처럼 딱 떨어지는
    **불연속 계단**이라 평균으로 읽으면 오해한다. 어긋남의 **종류**와
    조건 없는 `DISQUALIFY` 개수를 같이 찍는다.
    """
    import compose
    try:
        r = compose.compare(recs, run=0)
    except Exception as e:
        print(f"\n⑩ 합성 — 잴 수 없다: {e}")
        return
    dq = rate_hi = rate_lo = 0
    for (ka, kb), n in r["diffs"].items():
        if ka[2] != kb[2]:
            dq += n
        elif (kb[0] or 0) > (ka[0] or 0) or (kb[1] or 0) > (ka[1] or 0):
            rate_hi += n
        elif (kb[0] or 0) < (ka[0] or 0) or (kb[1] or 0) < (ka[1] or 0):
            rate_lo += n
    print(f"\n⑩ 합성 — 조문 {r['clauses']}개를 합쳐 프로필 {r['total']}개에 돌린다")
    print(f"  일치 {r['rate']:.1f}%  (gold rule {r['gold_rules']} · 생성 {r['gen_rules']})")
    if r["total"] - r["match"]:
        print(f"  어긋남 {r['total'] - r['match']}개 — 자격 판정 {dq} · "
              f"금리가 높다 {rate_hi} · 낮다 {rate_lo}")
    u = compose.unconditional_disqualify(recs)
    if u:
        print(f"  **조건 없는 DISQUALIFY {len(u)}개** — 모든 고객이 탈락한다")
        for cid, rid, quote in u[:4]:
            print(f"    {cid:<16} {quote}")
    print("  비율은 불연속 계단이다. 평균으로 읽지 말고 종류를 본다.")


def _empty_rate(recs):
    n = sum(1 for x in recs
            if isinstance((x.get("output") or {}).get("rules"), list)
            and not x["output"]["rules"])
    return n / len(recs) * 100 if recs else 0.0


def gates(recs, texts, base=None):
    print(f"레코드 {len(recs)}건 · 조문 {len({x['clause_id'] for x in recs})}개 "
          f"· 회차 {max(x['run'] for x in recs) + 1}회\n")
    print(f"{'지표':<22}{'1차':>8}{'재시도후':>10}{'개선':>8}")
    print("-" * 50)
    for i, k in enumerate(KEYS):
        a, b = _rate(recs, "first", k), _rate(recs, "final", k)
        print(f"{SYMS[i]} {NAME[i]:<19}{a:>7.1f}%{b:>9.1f}%{b - a:>+7.1f}p")

    if base:
        # 같은 (조문, 회차) 만 비교한다. 코퍼스가 달라지면 그냥 비교하면 안 된다.
        key = lambda x: (x["clause_id"], x["run"])
        common = {key(x) for x in base} & {key(x) for x in recs}
        A = [x for x in base if key(x) in common]
        B = [x for x in recs if key(x) in common]
        print(f"\n기준 대비 (공통 {len(common)}건)")
        print(f"{'지표':<22}{'기준':>8}{'이번':>8}{'변화':>8}")
        print("-" * 50)
        for i, k in enumerate(KEYS):
            a, b = _rate(A, "final", k), _rate(B, "final", k)
            mark = "" if abs(b - a) >= 4.0 else "  (노이즈 안)"
            print(f"{SYMS[i]} {NAME[i]:<19}{a:>7.1f}%{b:>7.1f}%{b - a:>+7.1f}p{mark}")
        print(f"⑦ {'빈 배열':<19}{_empty_rate(A):>7.1f}%{_empty_rate(B):>7.1f}%"
              f"{_empty_rate(B) - _empty_rate(A):>+7.1f}p")
        print("\n노이즈 바닥은 ±2~4p 다 (§9). 그 안의 변화는 판정하지 않는다.")

    none = sum(1 for x in recs if not isinstance((x.get("output") or {}).get("rules"), list))
    print(f"⑦ 빈 배열 (별도 축)      {'':>7} {_empty_rate(recs):>8.1f}%")

    # 재시도가 관문을 잃은 회차. **둘로 갈라 센다.**
    #
    # 처음에는 "결과를 망가뜨린 회차" 하나로 셌는데 과장이었다.
    # 기준선 7건을 열어 보니 다섯은 관문 수가 같은 **맞바꿈**이고
    # 둘은 오히려 관문이 늘었다 (합계 +2). 채택 규칙을 "관문을 하나라도
    # 잃으면 안 받는다" 로 바꿔 보는 실험을 저장된 결과로 돌려 봤더니
    # KBONE-S2-R20 에서 관문을 오히려 하나 잃는다. **바꾸지 않는다.**
    lost = [x for x in recs
            if any(x["first"][k] and not x["final"][k] for k in KEYS)]
    n_of = lambda m: sum(1 for k in KEYS if m[k])
    worse = [x for x in lost if n_of(x["final"]) < n_of(x["first"])]
    swap = len(lost) - len(worse)
    tries = sum(x["n_attempts"] - 1 for x in recs)
    print(f"\n재시도 {tries}회 · 관문 총수가 줄어든 회차 {len(worse)}건"
          f" · 같은 수로 맞바꾼 회차 {swap}건", end="")
    if lost:
        by = collections.Counter(k for x in lost for k in KEYS
                                 if x["first"][k] and not x["final"][k])
        got = collections.Counter(k for x in lost for k in KEYS
                                  if x["final"][k] and not x["first"][k])
        print("  잃은 관문 " + " · ".join(f"{SYM[k]} {v}" for k, v in by.items())
              + "  ·  얻은 관문 " + " · ".join(f"{SYM[k]} {v}" for k, v in got.items()))
    else:
        print()

    # 몇 번째 시도가 채택됐나 (v6 부터)
    if any("n_best" in x for x in recs):
        c = collections.Counter(x.get("n_best", 1) for x in recs)
        helped = sum(v for k, v in c.items() if k > 1)
        print(f"채택된 시도 " + " · ".join(f"{k}번째 {v}" for k, v in sorted(c.items()))
              + f"   재시도가 이긴 회차 {helped}건")
    print(f"\n무출력 {none}건 · 생성 호출 {sum(x['n_attempts'] for x in recs)}회 "
          f"· 재시도 없이 통과 {sum(1 for x in recs if x['n_attempts'] == 1)}건 "
          f"· 잘림 {sum(bool(x.get('truncated')) for x in recs)}건")


def per_clause(recs, texts, worst=8):
    """조문별. 군 평균을 처방의 효과로 읽지 않기 위한 표다."""
    by = collections.defaultdict(list)
    for x in recs:
        by[x["clause_id"]].append(x)
    rows = []
    for cid, rs in by.items():
        ok = sum(1 for x in rs if all(x["final"][k] for k in KEYS))
        nr = [x["final"].get("n_rules", 0) for x in rs]
        tr = sum(bool(x.get("truncated")) for x in rs)
        none = sum(1 for x in rs
                   if not isinstance((x.get("output") or {}).get("rules"), list))
        rows.append((ok / len(rs), cid, len(rs), ok, nr, tr, none))
    rows.sort()
    print(f"\n조문별 — ①~⑤ 전부 통과한 회차 (낮은 순 {worst}개)")
    print(f"{'조문':<16}{'회차':>5}{'전부통과':>9}{'rule 수':>13}{'잘림':>6}{'무출력':>7}")
    print("-" * 60)
    for r, cid, n, ok, nr, tr, none in rows[:worst]:
        print(f"{cid:<16}{n:>5}{ok:>6}/{n:<3}{str(nr):>13}{tr:>6}{none:>7}")
    steady = sum(1 for r, *_ in rows if r == 1.0)
    print(f"\n항상 통과하는 조문 {steady} / {len(rows)} · "
          f"한 번도 못 넘는 조문 {sum(1 for r, *_ in rows if r == 0.0)}")

    # 잘림과 무출력이 한 조문에 몰리는지 — 부록 A.3 이 그 이야기다
    hot = [(cid, tr, none) for _, cid, _, _, _, tr, none in rows if tr or none]
    if hot:
        print(f"\n잘림·무출력이 난 조문 {len(hot)}개")
        for cid, tr, none in sorted(hot, key=lambda x: -(x[1] + x[2]))[:6]:
            print(f"  {cid:<16}잘림 {tr} · 무출력 {none}")


def abstain_baseline(tpl, agg, P, base):
    """**아무것도 안 만드는 모델의 ⑥ 점수.**

    이전 실험(~2026-09-09, 30조문)에서 이 값이 92.6% 였고 일곱 라운드가
    전부 그 아래였다. **⑥ 은 뜻이 아니라 기권율을 재고 있었다.**
    저장소가 날아가면서 이 검사가 같이 사라졌고, 그 뒤 아홉 라운드 동안
    ⑥ 을 기준선 없이 찍어 왔다. 2026-09-14 에 되살린다.

    46조문에서도 **88.0%** 다. 원인은 두 가지가 겹친다 —
    gold 가 빈 배열인 조문이 13개이고, 나머지 중 24개는 gold rule 이 전부
    UNSUPPORTED 라 **실행 결과가 빈 배열과 같다.** 합쳐서 37/46 조문이
    기권만 해도 만점을 준다.

    **⑥ 단독으로는 "옳게 기권했다" 와 "아무것도 못 냈다" 를 못 가른다.**
    그래서 ⑫(선언 일치)가 따로 있다. 둘을 같이 읽어야 한다.
    """
    ss = [score(g.get("rules") or [], [], agg, P, base)["rate"] * 100
          for g in tpl.values()]
    perfect = sum(1 for x in ss if x == 100)
    return (sum(ss) / len(ss) if ss else 0.0), perfect


def meaning(recs):
    """⑥ — 섞인 갈래와 무출력 제외 갈래를 같이 찍는다 (부록 A.3).

    **기준선을 같이 찍는다.** 안 찍으면 기권율을 성능으로 오독한다.
    """
    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    if not tpl:
        print("\n⑥ — gold 가 없다")
        return
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()

    by = collections.defaultdict(list)
    for x in recs:
        by[x["clause_id"]].append(x)

    b_rate, b_perfect = abstain_baseline(tpl, agg, P, base)
    print(f"\n⑥ 실행 결과 일치 — gold {len(tpl)}개 · 프로필 {len(P)}개")
    print(f"  **기준선 {b_rate:.1f}%** — 아무것도 안 만드는 모델의 점수다. "
          f"{b_perfect}/{len(tpl)}조문이 기권만으로 만점을 받는다.")
    print(f"  이 아래면 기권보다 못한 것이다. ⑫ 와 같이 읽어야 한다 — "
          f"⑥ 은 '옳게 기권' 과 '아무것도 못 냄' 을 못 가른다.")
    print(f"{'조문':<16}{'회차':>5}{'섞인갈래':>10}{'무출력제외':>12}{'검토':>6}")
    print("-" * 52)
    mixed, clean = {}, {}
    for cid, g in sorted(tpl.items()):
        rs = by.get(cid) or []
        if not rs:
            continue
        ms, cs = [], []
        for x in rs:
            got = (x.get("output") or {}).get("rules")
            s = score(g.get("rules") or [], got if isinstance(got, list) else [],
                      agg, P, base)["rate"]
            ms.append(s)
            if isinstance(got, list):
                cs.append(s)
        mixed[cid], clean[cid] = ms, cs
        c = f"{sum(cs) / len(cs) * 100:.1f}%" if cs else "무출력뿐"
        print(f"{cid:<16}{len(rs):>5}{sum(ms) / len(ms) * 100:>9.1f}%{c:>12}"
              f"{'✓' if g.get('reviewed') else '초안':>6}")
    print("-" * 52)
    print(f"{'전체 (조문 가중)':<16}{'':>5}{gold.clause_weighted(mixed) * 100:>9.1f}%"
          f"{gold.clause_weighted({k: v for k, v in clean.items() if v}) * 100:>11.1f}%")
    if not all(g.get("reviewed") for g in tpl.values()):
        print("\n⚠ 검토되지 않은 gold 가 있다. 이 ⑥ 은 기준선이 아니라 파이프라인 점검용이다.")


def forms(recs, baseline=None):
    tables = [("이번", analyze.forms(recs))]
    if baseline:
        tables.insert(0, ("기준", analyze.forms(baseline)))
    names = sorted({k for _, c in tables for k in c})
    if not names:
        print("\n틀린 형태 — 없음")
        return
    w = max(len(n) for n in names) + 2
    print(f"\n틀린 형태 (지표가 안 움직여도 이건 움직인다)")
    print(f"{'형태':<{w}}" + "".join(f"{n:>10}" for n, _ in tables))
    print("-" * (w + 10 * len(tables)))
    for name in names:
        print(f"{name:<{w}}" + "".join(f"{c.get(name, 0):>10}" for _, c in tables))
    print(f"{'합계':<{w}}" + "".join(f"{sum(c.values()):>10}" for _, c in tables))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--clauses", default="data/corpus.json")
    ap.add_argument("--baseline")
    a = ap.parse_args(argv)

    recs = json.loads(Path(a.results).read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in json.loads(Path(a.clauses).read_text("utf-8"))}
    base = json.loads(Path(a.baseline).read_text("utf-8")) if a.baseline else None

    print(f"=== {Path(a.results).name} ===\n")
    gates(recs, texts, base)
    per_clause(recs, texts)
    gates_on_rules(recs, base)
    gate8(recs, base)
    gate9(recs, texts, base)
    gate10(recs)
    gate11(recs, texts)
    gate12(recs)
    gate13(recs)
    gate14(recs)
    meaning(recs)
    forms(recs, base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
