"""⑭ 헛조건 — 조건이 붙어 있는데 언제나 참인가.

**왜 이 축이 필요한가.**

v19 에서 거래중지 조문이 이렇게 나왔다.

    {"and": [{"<":  [account.balance, 10000]},
             {">=": [count_events(WITHDRAWAL, $window), 0]}]}

**`count >= 0` 은 항상 참이다.** 조문은 "1년 이상 거래가 **없는** 계좌" 인데
생성물은 사실상 잔액 조건만으로 거래를 제한한다 —
잔액이 1만원 미만인 **모든 정상 계좌**가 걸린다.

**관문 다섯이 전부 통과시킨다.** 실행되고, 이름도 카탈로그에 있고, 인용문도 원문이다.
뜻만 정반대다. ⑫ 도 못 본다 — 판정(정상 rule)은 맞기 때문이다.

같은 모양을 v6 감사에서도 봤다 — `termination_type in [enum 5개 전부]`.
그때는 축이 없어 세지 못했다.

## 어떻게 재나

패턴을 하나씩 찾지 않는다. **프로필 256개 전부에서 참인 조건**을 센다.
실행기를 그대로 쓰므로 `count >= 0` 이든 enum 전체 나열이든 같이 걸린다.

빈 조건 `{}` 은 **세지 않는다.** "항상 적용" 이라는 뜻을 분명히 밝힌 것이라
숨은 헛조건과 다르다.

## 한계 — 프로필 축이 고정한 값도 걸린다

`contract.term_months` 는 프로필에서 12 로 고정이다. 그래서 `>= 12` 가
"프로필 전부에서 참" 으로 잡힌다. **진짜 헛조건은 아니다.**

축이 없는 변수를 쓰는 조건은 이 축이 과하게 잡는다. 다만 **⑥·⑩ 이 그 조건을
변별하지 못하는 것은 사실이므로**, 채점 관점에서는 헛조건과 같다.
프로필 축을 넓히면 줄어든다.

실물을 열어 확인할 것. `by_clause` 와 `examples` 가 그래서 있다.

    python vacuous.py results/results_v19.json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import gold
from engine import evaluate
from tv import TV

_PROFILES = None


def _profiles():
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = [c for _, c in gold.profiles()]
    return _PROFILES


def is_vacuous(cond):
    """조건이 붙어 있는데 프로필 전부에서 참인가.

    빈 조건과 조건 없음은 False — 숨은 것만 센다.
    실행 불가는 False — 그건 ⑤ 가 잡는다.
    """
    if not isinstance(cond, dict) or not cond:
        return False
    try:
        return all(evaluate(cond, ctx) is TV.T for ctx in _profiles())
    except Exception:
        return False


def vacuous_branches(cond):
    """`and` 안에서 헛것인 갈래. 조건 전체가 헛것이 아니어도 갈래는 헛것일 수 있다.

    v19 의 거래중지가 그 모양이다 — 잔액 조건은 진짜인데
    `count >= 0` 갈래가 아무 일도 하지 않는다. 그 갈래를 빼도 결과가 같다.
    """
    if not isinstance(cond, dict) or list(cond) != ["and"]:
        return []
    arms = cond["and"]
    if not isinstance(arms, list):
        return []
    return [a for a in arms if is_vacuous(a)]


def check_rule(rule):
    out = []
    for part in ("condition", "guard"):
        c = rule.get(part)
        if is_vacuous(c):
            out.append(f"{part} 이 프로필 전부에서 참이다 — 조건이 없는 것과 같다")
            continue
        for a in vacuous_branches(c):
            out.append(f"{part} 의 한 갈래가 언제나 참이다 — 빼도 결과가 같다: "
                       f"{json.dumps(a, ensure_ascii=False)[:70]}")
    return out


def audit(recs):
    checked = bad = 0
    by_clause = collections.Counter()
    examples = []
    for x in recs:
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict):
                continue
            cond = r.get("condition")
            if not isinstance(cond, dict) or not cond:
                continue
            checked += 1
            if check_rule(r):
                bad += 1
                by_clause[x["clause_id"]] += 1
                if len(examples) < 6:
                    examples.append((x["clause_id"], cond))
    return {"checked": checked, "bad": bad,
            "rate": bad / checked * 100 if checked else 0.0,
            "by_clause": by_clause, "examples": examples}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--run", type=int, default=0)
    a = ap.parse_args(argv)
    recs = [x for x in json.loads(Path(a.results).read_text("utf-8"))
            if x["run"] == a.run]
    r = audit(recs)
    print(f"=== {Path(a.results).name} (run {a.run}) ===\n")
    print(f"⑭ 헛조건 — 조건이 붙은 rule {r['checked']}개 중 "
          f"**{r['bad']}개({r['rate']:.1f}%)가 언제나 참이다**\n")
    if r["by_clause"]:
        print("  " + " · ".join(f"{c} {n}" for c, n in r["by_clause"].most_common(8)))
    print("\n실물")
    for cid, cond in r["examples"]:
        print(f"  [{cid}] {json.dumps(cond, ensure_ascii=False)[:110]}")
    print("\n관문 다섯이 전부 통과시킨다. ⑫ 도 못 본다 — 판정은 맞기 때문이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
