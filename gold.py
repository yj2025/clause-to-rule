"""gold 라벨링 — 지표 ⑥ 의 정답.

실행기가 있으므로 **케이스별 정답(이 고객은 3.5%)을 만들 필요가 없다.**
조문당 조건식 하나만 쓰면 고객 프로필 조합은 도구가 만든다.

    python gold.py select   대상과 선정 근거
    python gold.py init     data/gold/ 에 템플릿 — 모델 출력이 초안으로 깔린다
    python gold.py status   손대지 않은 파일 표시
    python gold.py check    스키마·카탈로그·실행·원문 검증
    python gold.py score    지표 ⑥

30조문을 다 할 필요는 없다. 유형별로 15개면 방향이 보인다.
**①~⑤ 를 통과했지만 뜻이 의심스러운 것**을 일부러 넣는다. 실패한 것만
라벨링하면 "지표가 못 보는 실패" 를 영원히 못 본다.

`init` 이 모델 출력을 초안으로 깔아준다. 백지보다 빠르고, 무엇보다 모델이
어디서 틀렸는지 보면서 고치게 된다. 다만 그대로 두면 모델을 모델로 채점하는
꼴이라 `status` 가 손대지 않은 파일을 표시한다.
"""

import json
import sys
from pathlib import Path

import catalog
import validate
from scoring import score

GOLD_DIR = Path("data/gold")

# 코퍼스를 먼저 본다. 예전에는 KBYY 전용 파일만 봐서 **KBONE gold 는 ④ 검사가
# 통째로 건너뛰어졌다** — 인용문이 틀려도 "통과" 로 찍혔다.
CLAUSES = Path("data/corpus.json")
CLAUSES_FALLBACK = Path("data/clauses.json")

# ── 프로필 축 ───────────────────────────────────────────────────────────
# 축 8개 × 2값 = 256 프로필. 축을 늘리면 곱으로 늘어난다.
#
# 두 축이 이 상품의 핵심이다.
#   basic  기본실적 — 카드결제 · 공과금이체
#   extra  추가실적 — 급여이체 · 가맹점결제(입금) · 연금수령
# "기본실적 없이 추가실적만" 이 면제 불가라는 조문이 있으므로 둘을 따로 켠다.
#
# 이벤트 날짜는 **기준일의 전월**에 놓는다. 조문이 거의 다 "전월 중" 이라
# 다른 달에 놓으면 창 밖이라 전부 UNKNOWN 이 되고 ⑥ 의 변별력이 죽는다.
# 급여이체는 전월로 끝나는 6개월치를 넣어 개월 수 세기도 걸리게 한다.
AXES = {
    "age":         [17, 19],
    "balance":     [0, 1_000_000],
    # 이 상품에 이미 계좌가 있나. "1인 1계좌" 조항 셋이 이 축에서만 발동한다.
    # 없을 때는 항상 False 라 그 rule 들이 프로필 어디서도 안 걸렸고,
    # 정상 rule 인데 ⑥ 변별력이 0 이었다.
    "has_product": [False, True],
    "basic":       [0, 1],
    "channel":     ["BRANCH", "MOBILE"],
    "extra":       [0, 1],
    "reserved":    [0, 1_000_000],
    "termination": ["MATURITY", "EARLY"],
    # 가입기간. 생성물이 가장 자주 쓰는 고정 변수였다 — 참조 27개.
    # 12 로 고정돼 있어서 `term_months >= 12` 가 프로필 전부에서 참이었고,
    # ⑥ 이 맞는 기간 조건과 틀린 기간 조건을 구별하지 못했다.
    "term":        [6, 12],
    # 판별 기준일의 시대. 참조 20개.
    # "2023-04-11 이후 가입분" 같은 시행일 조건이 기준일 하나로는 안 흔들린다.
    # OLD 는 그 시행일 **이전**이다. 날짜 전부가 기준일을 따라 움직인다.
    "epoch":       ["NOW", "OLD"],
}

# 시대별 날짜. 전부 기준일에서 파생한다 — 하나만 바꾸면 창도 같이 움직인다.
EPOCHS = {
    "NOW": {"reference": "2026-09-11", "start": "2026-01-01",
            "maturity": "2026-12-01"},
    # 상품 시행일 2023-04-11 **이전**. 시행일 조건을 흔드는 유일한 축이다.
    "OLD": {"reference": "2023-02-20", "start": "2022-06-01",
            "maturity": "2023-06-01"},
}

REFERENCE_DATE = EPOCHS["NOW"]["reference"]      # 예전 이름 — 쓰는 곳이 있다
START_DATE = EPOCHS["NOW"]["start"]
MATURITY_DATE = EPOCHS["NOW"]["maturity"]
PREV_MONTH = "2026-08"


def _month_before(ym, k):
    """`"2026-08"` 에서 k 달 전. `"2026-03"`."""
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) - k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def _prev_month(date):
    """기준일의 전월."""
    return _month_before(date[:7], 1)


def _ctx(combo):
    era = EPOCHS[combo["epoch"]]
    prev = _prev_month(era["reference"])
    ev = {}
    if combo["basic"]:
        ev["CARD_USAGE"] = [{"date": f"{prev}-15", "amount": 30_000}]
        ev["AUTO_TRANSFER"] = [{"date": f"{prev}-20", "amount": 80_000}]
        # 출금. v17 에서 카탈로그에 WITHDRAWAL 을 넣으면서 프로필은 안 고쳤다.
        # 그래서 `WITHDRAWAL == 0` 이 **모든 프로필에서 참**이 됐고,
        # 무거래 판정을 올바르게 옮긴 rule 이 헛조건으로 잡혔다 (⑭).
        # 이벤트를 카탈로그에 더하면 프로필 축도 같이 봐야 한다.
        ev["WITHDRAWAL"] = [{"date": f"{prev}-18", "amount": 50_000}]
    if combo["extra"]:
        # 전월로 끝나는 6개월치 — 개월 수 세기와 "전월 중" 이 둘 다 걸린다
        ev["SALARY_TRANSFER"] = [
            {"date": f"{_month_before(prev, k)}-25", "amount": 2_000_000}
            for k in range(5, -1, -1)]
        ev["DEPOSIT"] = [{"date": f"{prev}-10", "amount": 500_000}]
        ev["PENSION_RECEIPT"] = [{"date": f"{prev}-25", "amount": 600_000}]

    # 모든 이벤트 종류를 "제공했다" 고 선언한다. 선언하지 않으면 "없다" 가 아니라
    # "모른다" 가 되어 판별이 전부 UNKNOWN 으로 뭉개진다 (§7.2 의 세 번째 줄).
    provided = [f"events.{k}" for k in catalog.EVENTS] + [
        "contract.start_date", "contract.maturity_date", "contract.reference_date",
        "contract.termination_type", "contract.channel", "contract.base_rate",
        "account.balance", "account.reserved_amount", "customer.age"]

    return {
        "customer": {"age": combo["age"], "is_youth": combo["age"] < 19,
                     "has_product": combo["has_product"], "is_first_deposit": False,
                     # 축이 아니라 고정이다 (2026-09-15). 축으로 두면 프로필이 2048 이 되어
                     # 확정한 판정선을 버려야 한다. 대가 — 명의 유형 rule 은 프로필에서
                     # 발동하지 않아 ⑥ 이 그 조건의 정확도를 못 가린다. 조건 없이 탈락시키는
                     # 오류는 여전히 잡힌다.
                     "holder_type": "INDIVIDUAL"},
        "account": {"balance": combo["balance"],
                    "reserved_amount": combo["reserved"]},
        "contract": {"base_rate": 0.1, "channel": combo["channel"],
                     "start_date": era["start"], "maturity_date": era["maturity"],
                     "reference_date": era["reference"], "switch_date": None,
                     "termination_date": None, "term_months": combo["term"],
                     "amount": combo["balance"], "monthly_amount": 0,
                     "termination_type": combo["termination"]},
        "events": ev,
        "_provided": provided,
    }


def profiles():
    """AXES 의 모든 조합. [(이름, ctx), ...]"""
    names = sorted(AXES)
    out, idx = [], [0] * len(names)
    while True:
        combo = {n: AXES[n][idx[i]] for i, n in enumerate(names)}
        label = " ".join(f"{n}={combo[n]}" for n in names)
        out.append((label, _ctx(combo)))
        for i in range(len(names) - 1, -1, -1):
            idx[i] += 1
            if idx[i] < len(AXES[names[i]]):
                break
            idx[i] = 0
            if i == 0:
                return out


# ── 라벨링 대상 ─────────────────────────────────────────────────────────
# 고른 기준: ①~⑤ 를 통과했지만 뜻이 의심스러운 것을 먼저 넣는다.
# 실패한 것만 라벨링하면 "지표가 못 보는 실패" 를 영원히 못 본다.
TARGETS = {
    # 앞 여섯은 노트북 §8.2 의 저장된 출력에 남아 있던 것을 그대로 되살렸다.
    "KBYY-S5-R02": "수수료 면제를 LIMIT_AMOUNT 0원 으로 적었는지 확인. ⑤ 통과했다",
    "KBYY-S5-R01": "수수료 면제 + rule 수 흔들림 [4,3,4]. 셋 중 무엇이 맞나",
    "KBYY-S2-R03": "27자 [상품유형] 라벨인데 rule 2개를 만들었다. 빈 배열이 정답 아닌가",
    "KBYY-S2-R02": "3회 모두 빈 배열. 정말 표현할 게 없는 조문인가",
    "KBYY-S2-R16": "3회 모두 빈 배열. 위와 같은 확인",
    "KBYY-S2-R06": "rule 수 [2,0,2]. 0개가 맞나 2개가 맞나",
    # 아래 아홉은 복원하며 고른 것이다. 기준은 같다.
    "KBYY-S5-R03": "1,546자. 잘림이 여기서 났고 분할 논의도 이 조문이다",
    "KBYY-S2-R12": "수수료면제 서비스. 면제횟수 표를 값까지 맞히나",
    "KBYY-S2-R11": "저금통 특별금리. 조건과 한도가 섞여 있어 rule 수가 흔들린다",
    "KBYY-S2-R07": "특별금리 연 1.9%. RATE_ADD 를 RATE_OVERRIDE 로 적으면 10bp 가 틀어진다",
    "KBYY-S2-R10": "최저 0.1 ~ 최고 2.0. 구간을 rule 로 적으려 들면 틀린다",
    "KBYY-S2-R01": "가입대상. 나이 경계(만 19세 미만)를 == 로 적는 실수가 잦다",
    "KBYY-S2-R04": "자동전환. 상품 전환 effect 가 카탈로그에 없다 — UNSUPPORTED 가 맞나",
    "KBYY-S2-R19": "거래중지. 잔액과 무거래기간의 3단 조건이다",
    "KBYY-S3-R02": "29자 정상 기준점. 이게 맞아야 나머지 비교가 의미 있다",
}


# ── 가중 ────────────────────────────────────────────────────────────────
def clause_weighted(per_clause):
    """{조문: [회차 점수, ...]} → 조문 단위 평균.

    회차 가중으로 세면 안 된다. 무출력 회차를 뺀 만큼 그 조문의 비중까지 줄어서,
    많이 잘리는 조문일수록 점수에 덜 반영되는 두 번째 인공물이 생긴다 (부록 A.5).
    조문 하나는 회차를 몇 개 남겼든 똑같이 한 몫이다.
    """
    means = [sum(v) / len(v) for v in per_clause.values() if v]
    return sum(means) / len(means) if means else 0.0


def run_weighted(per_clause):
    """비교용. 이 방식은 쓰지 않는다 — 왜 안 되는지는 위 문서와 테스트에 있다."""
    flat = [x for v in per_clause.values() for x in v]
    return sum(flat) / len(flat) if flat else 0.0


def drop_empty_runs(runs):
    """무출력 회차를 뺀다. output 이 아예 없는 회차는 빈 배열이 아니다.

    빈 배열로 흘려보내면 기권군에서 만점을 받는다 — 모델이 아무것도 못 내놓은
    것과 낼 것이 없다고 판단한 것이 같은 점수가 된다 (부록 A.3).
    """
    return [x for x in runs if isinstance((x.get("output") or {}).get("rules"), list)]


# ── 명령 ────────────────────────────────────────────────────────────────
def _clauses():
    p = CLAUSES if CLAUSES.exists() else CLAUSES_FALLBACK
    return {c["id"]: c for c in json.loads(p.read_text("utf-8"))}


def _product():
    return json.loads((GOLD_DIR / "_product.json").read_text("utf-8"))


def _templates():
    return {p.stem: json.loads(p.read_text("utf-8"))
            for p in sorted(GOLD_DIR.glob("*.json")) if not p.name.startswith("_")}


def cmd_select():
    cl = _clauses()
    print(f"대상 {len(TARGETS)}개 / 전체 {len(cl)}조문\n")
    print(f"{'조문':<15}{'분류':<13}{'자수':>5}  고른 이유")
    print("-" * 92)
    for cid, why in TARGETS.items():
        c = cl.get(cid)
        if c is None:
            print(f"{cid:<15}{'없음':<13}{'-':>5}  {why[:56]}")
            continue
        print(f"{cid:<15}{c['category']:<13}{len(c['text']):>5}  {why[:56]}")


def cmd_init(results=None):
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    cl = _clauses()
    draft = {}
    if results and Path(results).exists():
        for x in json.loads(Path(results).read_text("utf-8")):
            rs = (x.get("output") or {}).get("rules")
            if isinstance(rs, list) and x["clause_id"] not in draft:
                draft[x["clause_id"]] = rs
    made = 0
    for cid in TARGETS:
        p = GOLD_DIR / f"{cid}.json"
        if p.exists() or cid not in cl:
            continue
        p.write_text(json.dumps(
            {"clause_id": cid, "label": cl[cid]["label"], "reviewed": False,
             "note": "모델 출력이 초안이다. 고친 뒤 reviewed 를 true 로 바꾼다.",
             "rules": draft.get(cid, [])}, ensure_ascii=False, indent=1), "utf-8")
        made += 1
    print(f"템플릿 {made}개 생성 · 초안 깔린 것 {sum(1 for c in TARGETS if draft.get(c))}개")


def verdict(rules):
    """세 갈래 중 무엇인가 — 빈 배열 / UNSUPPORTED 뿐 / rule 있음."""
    if not rules:
        return "빈 배열"
    if all(r.get("status") == "UNSUPPORTED" for r in rules):
        return "UNSUPPORTED 뿐"
    if any(r.get("status") == "UNSUPPORTED" for r in rules):
        return "일부 UNSUPPORTED"
    return "정상 rule"


def outcome_neutral(rules):
    """실행 결과가 빈 배열과 같은가.

    UNSUPPORTED rule 은 effect 가 없어 resolver 가 아무것도 싣지 않는다.
    그런 gold 는 모델이 빈 배열을 내도 ⑥ 만점을 준다 — ⑥ 의 변별력이 0 이다.

    **프로필 전부로 봐야 한다.** 하나만 보면 그 프로필에서 조건이 안 걸린 조문까지
    변별력 없음으로 나온다. 조건이 걸리는 프로필이 하나라도 있으면 변별력은 있다.
    """
    from scoring import outcome
    prod = json.loads((GOLD_DIR / "_product.json").read_text("utf-8"))
    agg, base = prod["aggregation"], prod["base_rate"]
    for _, ctx in profiles():
        if outcome(rules, ctx, agg, base) != outcome([], ctx, agg, base):
            return False
    return True


def cmd_status():
    tpl = _templates()
    done = [k for k, v in tpl.items() if v.get("reviewed")]
    print(f"템플릿 {len(tpl)}개 · 검토완료 {len(done)}개\n")
    print(f"{'조문':<16}{'rule':>5}{'판정':<18}{'⑥ 변별':<10}{'검토'}")
    print("-" * 62)
    neutral = 0
    for cid, v in sorted(tpl.items()):
        rs = v.get("rules") or []
        n = outcome_neutral(rs)
        neutral += n
        print(f"{cid:<16}{len(rs):>5}  {verdict(rs):<17}{'없음' if n else '있음':<11}"
              f"{'✓' if v.get('reviewed') else '초안'}")
    print("-" * 62)
    print(f"\n⑥ 으로 가릴 수 없는 gold {neutral} / {len(tpl)}개.")
    print("빈 배열과 UNSUPPORTED 는 실행 결과가 같다. 이 조문들에서는 모델이")
    print("아무것도 내지 않아도 만점이므로, ⑥ 의 변별력은 나머지 조문에서만 나온다.")


def cmd_check():
    cl, tpl, bad = _clauses(), _templates(), 0
    skipped = []
    for cid, v in sorted(tpl.items()):
        errs = validate.check_schema({"rules": v.get("rules") or []})
        if cid not in cl:
            skipped.append(cid)          # 조문을 못 찾으면 ④ 를 못 잰다. 숨기지 않는다
        for r in v.get("rules") or []:
            errs += validate.check_catalog(r)
            errs += validate.check_executable(r)
            if cid in cl:
                errs += validate.check_quote(r, cl[cid]["text"])
        bad += bool(errs)
        print(f"  {cid:<15}{'실패 ' + str(len(errs)) if errs else '통과'}")
        for e in errs[:3]:
            print(f"      {e}")
    print(f"\n검증 실패 {bad} / {len(tpl)}")
    if skipped:
        print(f"⚠ 조문 원문을 못 찾아 ④ 를 건너뛴 gold {len(skipped)}개: "
              f"{', '.join(skipped)}")
    return bad


def cmd_score(results):
    prod, tpl, P = _product(), _templates(), profiles()
    agg, base = prod["aggregation"], prod["base_rate"]
    recs = json.loads(Path(results).read_text("utf-8"))

    by = {}
    for x in recs:
        by.setdefault(x["clause_id"], []).append(x)

    print(f"프로필 {len(P)}개 · gold {len(tpl)}개\n")
    print(f"{'조문':<15}{'회차':>5}{'⑥ 섞인갈래':>12}{'⑥ 무출력제외':>14}")
    print("-" * 48)

    tot_mixed, tot_clean, n_clean = 0.0, 0.0, 0
    for cid, g in sorted(tpl.items()):
        runs = by.get(cid) or []
        if not runs:
            continue
        mixed, clean = [], []
        for x in runs:
            out = x.get("output")
            rs = (out or {}).get("rules")
            has_output = isinstance(rs, list)
            s = score(g.get("rules") or [], rs if has_output else [], agg, P, base)["rate"]
            mixed.append(s)
            if has_output:
                clean.append(s)
        m = sum(mixed) / len(mixed)
        c = sum(clean) / len(clean) if clean else None
        tot_mixed += m
        if c is not None:
            tot_clean += c
            n_clean += 1
        print(f"{cid:<15}{len(runs):>5}{m * 100:>11.1f}%"
              f"{('%.1f%%' % (c * 100)) if c is not None else '무출력뿐':>14}")

    n = len([1 for cid in tpl if by.get(cid)]) or 1
    print("-" * 48)
    print(f"{'전체':<15}{'':>5}{tot_mixed / n * 100:>11.1f}%"
          f"{tot_clean / (n_clean or 1) * 100:>13.1f}%")
    print("\n가중은 조문 단위다. 프로필 가중으로 세면 회차를 뺀 만큼 그 조문의")
    print("비중까지 줄어서, 많이 잘리는 조문일수록 점수에 덜 반영된다 (부록 A.5).")


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "select":
        cmd_select()
    elif cmd == "init":
        cmd_init(argv[1] if len(argv) > 1 else None)
    elif cmd == "status":
        cmd_status()
    elif cmd == "check":
        return cmd_check()
    elif cmd == "score":
        if len(argv) < 2:
            print("사용법: python gold.py score <results.json>")
            return 1
        cmd_score(argv[1])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
