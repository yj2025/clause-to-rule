"""⑬ 지어낸 이름 — 카탈로그에 없는 개념을 이름 자리에 밀어 넣나.

**2026-09-20 에 정의를 넓혔다 (계약 변경 · 여섯 번째).** 전에는 `REQUIRE`/`DISQUALIFY` 의
**문자열 값**만 셌다. v28 에서 그 정의가 현상을 놓쳤다 — 카탈로그를 넓히자 모델이
**새로 준 effect 옆에** 이름을 지어냈다.

    STATE_CHANGE  INTEREST_CALCULATED     (없는 상태)
    RESTRICT      WITHDRAWAL              (없는 제한 대상)
    RESTRICT      PRODUCT_SWITCH          (없는 제한 대상)

`RESTRICT` 에 target 셋을 더 주자 **네 번째를 지어냈다.** 그런데 그 라운드의 ⑬ 은
«문자열 값 3개 중 3개» 였다 — 분모가 무너져 비교조차 안 됐다.

지금은 **이름 자리 전부**를 본다: effect 의 target · 자유 문자열 값 · 조건의 변수 ·
이벤트 · 앵커 · 이벤트 속성 값. 분모는 그 자리에 실제로 쓴 이름의 수다.

**자리마다 쓸 수 있는 이름이 다르다.** `WITHDRAWAL` 은 이벤트로는 카탈로그에 있지만
`RESTRICT` 의 target 은 아니다 — v28 이 실제로 낸 것이 그것이다. 카탈로그 어딘가에 있으면
봐주는 셈법은 이 현상을 놓친다. 그래서 **자리별 어휘**로 본다 (`SLOT_VOCAB`).
옛 값과 견주려면 `--value-only` 를 쓴다.

**관문(③)의 계약은 안 바꿨다.** `check_rule` 은 그대로다 — ⑬ 은 뜻을 재는 축이고
③ 은 관문이라, 한쪽을 넓히면서 다른 쪽을 같이 움직이면 무엇이 변했는지 못 읽는다.

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

# 문자열 값을 갖는 effect. **자유 문자열을 허용하지 않는다.**
#
# 2026-09-14 사람 검토에서 정해졌다. 정답 데이터가 `REQUIRE` 의 value 에
# "본인명의의 입출금이자유로운예금 계좌" 라는 한국어 문장을 넣고 있었는데,
# 카탈로그에 그 계좌 종류를 가리킬 코드가 없다. **모델에게 벌점을 주는
# 바로 그 일을 정답이 하고 있었다.** 그 rule 은 UNSUPPORTED 로 바꿨다.
FREE = ("REQUIRE", "DISQUALIFY")

# 대문자 코드형 — 지어낸 이름은 거의 이 모양이다
_CODE = re.compile(r"[A-Z][A-Z0-9_]{2,}")

# 카탈로그에 있는 이름은 지어낸 것이 아니다
def known():
    out = set(catalog.VARIABLES) | set(catalog.EVENTS) | set(catalog.EFFECTS)
    out |= set(catalog.FEES) | set(catalog.APPLIES_TO) | set(catalog.STATUSES)
    out |= set(catalog.SERVICES) | set(catalog.RESTRICTIONS)
    out |= set(catalog.STATES) | set(catalog.PRODUCTS)          # 2026-09-20
    for vals in catalog.ENUM_VALUES.values():
        out |= set(vals)
    for attrs in catalog.EVENT_ATTRIBUTES.values():
        for vals in attrs.values():
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
    if v.strip() in vocab:
        return []
    if not _CODE.fullmatch(v.strip()):
        return [f"{eff['type']} 의 value \"{v[:40]}\" 가 카탈로그 코드가 아니다. "
                f"자유 문자열은 쓰지 않는다 — 실행기가 읽을 수 없다. "
                f"표현 수단이 없으면 status 를 UNSUPPORTED 로 한다"]
    return [f"{eff['type']} 의 value \"{v}\" 는 카탈로그에 없는 코드다. "
            f"표현 수단이 없으면 status 를 UNSUPPORTED 로 한다"]


# ── 이름 자리 ───────────────────────────────────────────────────────────
_ATTR_KEYS = {"min_amount"}          # 값이 이름이 아니라 수인 자리


def slot_vocab():
    """자리 → 그 자리에 쓸 수 있는 이름. 자리를 틀리면 지어낸 것으로 센다."""
    targets = (set(catalog.FEES) | set(catalog.SERVICES) | set(catalog.RESTRICTIONS)
               | set(catalog.STATES) | set(catalog.PRODUCTS))
    attrs = {v for a in catalog.EVENT_ATTRIBUTES.values() for vals in a.values() for v in vals}
    return {"effect.target": targets,
            "effect.applies_to": set(catalog.APPLIES_TO),
            "effect.value": known(),
            "condition.var": set(catalog.VARIABLES),
            "condition.anchor": set(catalog.VARIABLES),
            "condition.event": set(catalog.EVENTS),
            "condition.where": attrs}


def names_of(rule):
    """rule 하나가 **이름 자리**에 쓴 이름들 → [(자리, 이름)]."""
    out = []
    eff = rule.get("effect") or {}
    if isinstance(eff.get("target"), str):
        out.append(("effect.target", eff["target"].strip()))
    if eff.get("type") in FREE and isinstance(eff.get("value"), str):
        v = eff["value"].strip()
        if _CODE.fullmatch(v):
            out.append(("effect.value", v))
    if isinstance(eff.get("applies_to"), str):
        out.append(("effect.applies_to", eff["applies_to"].strip()))

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("var", "anchor") and isinstance(v, str):
                    out.append((f"condition.{k}", v.strip()))
                elif k == "event" and isinstance(v, str):
                    out.append(("condition.event", v.strip()))
                elif k == "where" and isinstance(v, dict):
                    for a, want in v.items():
                        if a in _ATTR_KEYS:
                            continue
                        for x in (want if isinstance(want, list) else [want]):
                            if isinstance(x, str):
                                out.append(("condition.where", x.strip()))
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk({k: rule.get(k) for k in ("condition", "guard", "let")})
    return out


def audit_names(recs, vocab=None):
    """이름 자리에 쓴 이름 중 **그 자리의 카탈로그에 없는 것.** ⑬ 의 지금 정의다."""
    vocab = slot_vocab() if vocab is None else vocab
    checked = bad = 0
    names = collections.Counter()
    slots = collections.Counter()
    by_clause = collections.Counter()
    for x in recs:
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict):
                continue
            for slot, name in names_of(r):
                checked += 1
                if name not in vocab.get(slot, set()):
                    bad += 1
                    names[name] += 1
                    slots[slot] += 1
                    by_clause[x["clause_id"]] += 1
    return {"checked": checked, "bad": bad,
            "rate": bad / checked * 100 if checked else 0.0,
            "names": names, "slots": slots, "by_clause": by_clause}


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
    ap.add_argument("--value-only", action="store_true",
                    help="2026-09-20 이전 정의 — REQUIRE/DISQUALIFY 의 문자열 값만 센다")
    a = ap.parse_args(argv)
    recs = [x for x in json.loads(Path(a.results).read_text("utf-8"))
            if x["run"] == a.run]
    r = audit(recs) if a.value_only else audit_names(recs)
    what = "문자열 값" if a.value_only else "이름 자리"
    print(f"=== {Path(a.results).name} (run {a.run}) ===\n")
    print(f"⑬ 지어낸 이름 — {what} {r['checked']}개 중 "
          f"**{r['bad']}개({r['rate']:.1f}%)가 카탈로그에 없다**\n")
    if r.get("slots"):
        print("  자리별: " + " · ".join(f"{k} {v}" for k, v in r["slots"].most_common()))
    if r["names"]:
        print("  " + " · ".join(f"{k} {v}" for k, v in r["names"].most_common(12)))
    if r["by_clause"]:
        print("\n  조문별: " + " · ".join(f"{c} {n}"
                                        for c, n in r["by_clause"].most_common(8)))
    print("\n관문 다섯은 이것을 전부 통과시킨다. ③ 은 condition 안의 이름만 본다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
