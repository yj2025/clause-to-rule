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

## 두 가지를 갈라 센다 — 이걸 안 하면 수치가 부풀려진다

프로필 전부에서 참이라고 다 모델 잘못이 아니다. `contract.term_months` 는
프로필에서 12 로 **고정**이라 `>= 12` 가 자동으로 참이 된다. 이건 내 프로필의
구멍이지 모델의 헛조건이 아니다.

그래서 프로필에서 걸린 조건마다 **카탈로그 정의역 전체를 훑는 문맥 400개**
(`_free.sample()`) 에서 반례를 찾는다.

* 반례 있음 → **미가동**. 내 프로필이 그 변수를 안 흔든 것뿐이다.
  측정의 구멍이라 ⑥·⑩ 의 변별력은 실제로 떨어지지만, 모델 탓은 아니다.
* 반례 없음 → **헛조건**. 어떤 문맥에서도 참이다. 모델의 결함이다.

반례 판정은 거짓과 모름을 둘 다 센다 — 헛조건 쪽을 **적게** 잡는 방향이다.
실행 오류는 표본의 흠일 수 있어 반례로 치지 않는다.

첫 측정에서 이 둘을 안 갈랐더니 "조건의 15~30%가 장식" 이 나왔다.
가르고 나면 수치가 크게 줄어든다 — ROUNDS.md 참고.

    python vacuous.py results/results_v19.json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import _free
import gold
from engine import evaluate
from tv import TV

_FREE = None


def _free_ctxs():
    global _FREE
    if _FREE is None:
        _FREE = _free.sample()
    return _FREE


def has_counterexample(cond, env=None):
    """정의역 전체를 훑는 표본에서 참이 아닌 문맥이 하나라도 있나.

    거짓과 모름을 둘 다 반례로 친다 — 헛조건을 적게 잡는 쪽으로 기운다.
    실행 오류는 표본의 흠일 수 있어 반례로 치지 않는다.
    """
    for ctx in _free_ctxs():
        try:
            if evaluate(cond, ctx, dict(env or {})) is not TV.T:
                return True
        except Exception:
            continue
    return False


def classify(cond, env=None):
    """`"헛조건"` · `"미가동"` · `None`."""
    if not is_vacuous(cond, env):
        return None
    return "미가동" if has_counterexample(cond, env) else "헛조건"

_PROFILES = None


def _profiles():
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = [c for _, c in gold.profiles()]
    return _PROFILES


def is_vacuous(cond, env=None):
    """조건이 붙어 있는데 프로필 전부에서 참인가.

    빈 조건과 조건 없음은 False — 숨은 것만 센다.
    실행 불가는 False — 그건 ⑤ 가 잡는다.

    **`env` 에 rule 의 `let` 을 넘겨야 한다.** 안 넘기면 창을 쓰는 조건이
    전부 "미바인딩 참조" 로 실행 실패가 되어 검사에서 빠진다.
    창을 쓰는 형태가 이 코퍼스에서 가장 흔하다 — v19 에서 이 구멍 때문에
    표적 조문의 헛조건을 놓쳤다.
    """
    if not isinstance(cond, dict) or not cond:
        return False
    try:
        return all(evaluate(cond, ctx, dict(env or {})) is TV.T
                   for ctx in _profiles())
    except Exception:
        return False


def vacuous_branches(cond, env=None):
    """`and` 안에서 헛것인 갈래. 조건 전체가 헛것이 아니어도 갈래는 헛것일 수 있다.

    v19 의 거래중지가 그 모양이다 — 잔액 조건은 진짜인데
    `count >= 0` 갈래가 아무 일도 하지 않는다. 그 갈래를 빼도 결과가 같다.
    """
    if not isinstance(cond, dict) or list(cond) != ["and"]:
        return []
    arms = cond["and"]
    if not isinstance(arms, list):
        return []
    return [a for a in arms if is_vacuous(a, env)]


def check_rule(rule):
    """[(종류, 설명), ...]. 종류는 `"헛조건"` 또는 `"미가동"`."""
    out = []
    env = rule.get("let") or {}
    for part in ("condition", "guard"):
        c = rule.get(part)
        kind = classify(c, env)
        if kind:
            out.append((kind, f"{part} 전체가 언제나 참이다 — 조건이 없는 것과 같다"))
            continue
        for a in vacuous_branches(c, env):
            k = "미가동" if has_counterexample(a, env) else "헛조건"
            out.append((k, f"{part} 의 한 갈래가 언제나 참이다 — 빼도 결과가 같다: "
                           f"{json.dumps(a, ensure_ascii=False)[:70]}"))
    return out


def audit(recs):
    checked = bad = idle = 0
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
            found = check_rule(r)
            kinds = {k for k, _ in found}
            if "헛조건" in kinds:
                bad += 1
                by_clause[x["clause_id"]] += 1
                if len(examples) < 6:
                    examples.append((x["clause_id"], cond))
            elif "미가동" in kinds:
                idle += 1
    return {"checked": checked, "bad": bad, "idle": idle,
            "rate": bad / checked * 100 if checked else 0.0,
            "idle_rate": idle / checked * 100 if checked else 0.0,
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
          f"**{r['bad']}개({r['rate']:.1f}%)가 어떤 문맥에서도 참이다**")
    print(f"   그 밖에 {r['idle']}개({r['idle_rate']:.1f}%)는 미가동 — "
          f"내 프로필이 그 변수를 안 흔든 것이라 모델 탓이 아니다\n")
    if r["by_clause"]:
        print("  " + " · ".join(f"{c} {n}" for c, n in r["by_clause"].most_common(8)))
    print("\n실물")
    for cid, cond in r["examples"]:
        print(f"  [{cid}] {json.dumps(cond, ensure_ascii=False)[:110]}")
    print("\n관문 다섯이 전부 통과시킨다. ⑫ 도 못 본다 — 판정은 맞기 때문이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
