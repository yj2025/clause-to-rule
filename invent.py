"""⑬ 지어낸 코드 — 카탈로그에 없는 개념을 문자열에 담아 밀어 넣나.

**왜 이 축이 필요한가.**

스키마가 `REQUIRE` 와 `DISQUALIFY` 의 `value` 를 **자유 문자열**로 허용한다.
그래서 모델이 카탈로그에 없는 개념을 대문자 코드로 지어내 그 자리에 담는다.

    {"type": "REQUIRE",    "value": "PLEDGE_NOT_ALLOWED"}
    {"type": "REQUIRE",    "value": "PRODUCT_SWITCH"}
    {"type": "DISQUALIFY", "value": "TAXABLE"}

**관문 다섯이 전부 통과한다.** ③ 은 `condition` 안의 이름만 보고 effect 의
문자열 값은 안 본다. 실행기도 문자열을 그냥 들고만 있는다.

이것이 ⑫ 의 최대 오류 유형을 만든다 — gold 가 "표현 수단이 없다(UNSUPPORTED)"
라고 판정한 조문 6개에서 모델이 정상 rule 을 낸다. 수단이 없는데 **있는 척** 한다.

카탈로그를 넓히는 것이 답이 아니다. 넓혀도 그 밖의 개념을 또 지어낸다.
**탈출구를 막기 전에 그것을 세는 축부터 세운다** (§9 11번).

    python invent.py results/results_v10.json
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import catalog

# 자유 문자열을 허용하는 effect
FREE = ("REQUIRE", "DISQUALIFY")

# 대문자 코드형 — 지어낸 이름은 거의 이 모양이다
_CODE = re.compile(r"[A-Z][A-Z0-9_]{2,}")

# 카탈로그에 있는 이름은 지어낸 것이 아니다
def known():
    out = set(catalog.VARIABLES) | set(catalog.EVENTS) | set(catalog.EFFECTS)
    out |= set(catalog.FEES) | set(catalog.APPLIES_TO) | set(catalog.STATUSES)
    for vals in catalog.ENUM_VALUES.values():
        out |= set(vals)
    return out


def check_rule(rule, vocab=None):
    """effect 의 문자열 값이 지어낸 코드인가."""
    vocab = known() if vocab is None else vocab
    eff = rule.get("effect") or {}
    if eff.get("type") not in FREE:
        return []
    v = eff.get("value")
    if not isinstance(v, str):
        return []
    if not _CODE.fullmatch(v.strip()):
        return []                       # 한글 설명문 등은 이 축의 대상이 아니다
    if v.strip() in vocab:
        return []
    return [f"{eff['type']} 의 value \"{v}\" 는 카탈로그에 없는 코드다. "
            f"표현 수단이 없으면 status 를 UNSUPPORTED 로 한다"]


def audit(recs):
    vocab = known()
    checked = bad = 0
    names = collections.Counter()
    by_clause = collections.Counter()
    for x in recs:
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict):
                continue
            eff = r.get("effect") or {}
            if eff.get("type") not in FREE or not isinstance(eff.get("value"), str):
                continue
            checked += 1
            if check_rule(r, vocab):
                bad += 1
                names[eff["value"]] += 1
                by_clause[x["clause_id"]] += 1
    return {"checked": checked, "bad": bad,
            "rate": bad / checked * 100 if checked else 0.0,
            "names": names, "by_clause": by_clause}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--run", type=int, default=0)
    a = ap.parse_args(argv)
    recs = [x for x in json.loads(Path(a.results).read_text("utf-8"))
            if x["run"] == a.run]
    r = audit(recs)
    print(f"=== {Path(a.results).name} (run {a.run}) ===\n")
    print(f"⑬ 지어낸 코드 — REQUIRE/DISQUALIFY 의 문자열 값 {r['checked']}개 중 "
          f"**{r['bad']}개({r['rate']:.1f}%)가 카탈로그에 없다**\n")
    if r["names"]:
        print("  " + " · ".join(f"{k} {v}" for k, v in r["names"].most_common(12)))
    if r["by_clause"]:
        print("\n  조문별: " + " · ".join(f"{c} {n}"
                                        for c, n in r["by_clause"].most_common(8)))
    print("\n관문 다섯은 이것을 전부 통과시킨다. ③ 은 condition 안의 이름만 본다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
