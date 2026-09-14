"""⑨ 근거 — 생성물의 숫자가 조문에 있나.

**왜 이 축이 필요한가.**

`KBYY-S1-P01` 은 숫자가 한 개도 없는 두 줄짜리 소개 문장이다. 그런데 v6 생성물은
우대금리 `0.5 %p` 와 면제횟수 `100` 을 만들어 냈고 **관문 다섯을 전부 통과했다.**
quote 는 원문 그대로라 ④ 가 통과하고, 이름은 카탈로그에 있어 ③ 이 통과하고,
실행되므로 ⑤ 가 통과한다.

①~⑤ 중 어느 것도 **값이 어디서 왔는지** 묻지 않는다. ⑥ 도 못 잡는다 —
gold 가 빈 배열인 조문에서는 창작 rule 이 어느 프로필에서도 발화하지 않으면
실행 결과가 빈 배열과 같기 때문이다.

은행 금리를 발명하는 것은 이 프로젝트에서 가장 비싼 오류다. 그걸 세는 축이 없었다.

**이 축은 기존 관문을 건드리지 않는다.** ①~⑤ 의 정의가 그대로라 v1 부터의
비교가 유지된다. 새로 세는 것뿐이다.

## 무엇을 분모로 두나 — rule 이 아니라 조문이다

처음에는 **수치 effect 를 낸 rule** 을 분모로 뒀다. 그 분모가 8~28개뿐이라
한둘이 바뀌면 10p 가 움직인다. 3회 반복으로 재 보니 1회 기준 불확실 구간이
v1 ±19.1p · v2 ±18.9p · **v7 ±46.5p** 였다. **라운드 비교에 못 쓴다.**
게다가 모델이 rule 을 몇 개 내느냐에 따라 분모가 같이 흔들려서,
"덜 만들면 비율이 좋아지는" 축이었다.

**조문 단위로 센다** — "이 조문에서 지어낸 수가 하나라도 있나".
분모가 코퍼스 조문 수로 고정된다. 같은 세 라운드에서 **전부 ±2.5p** 다.
1회차로도 판정된다.

rule 단위 비율은 참고로 같이 찍지만 **라운드 비교에는 쓰지 않는다.**

    python grounding.py results/results_v6.json
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

# 값이 반드시 조문에 있어야 하는 effect 키
CHECKED = {
    "RATE_ADD": "value", "RATE_SUBTRACT": "value",
    "RATE_OVERRIDE": "value", "PENALTY_RATE": "value",
    "LIMIT_AMOUNT": "value", "FEE_WAIVE": "value",
}

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text):
    """조문에 적힌 수. 쉼표와 한글 단위를 편다."""
    out = set()
    for m in _NUM.finditer(text.replace(",", "")):
        s = m.group(0)
        try:
            v = float(s)
        except ValueError:
            continue
        out.add(v)
        if v == int(v):
            out.add(float(int(v)))
    # 한글 수 단위 — "100만원" 은 1000000, "2천만원" 은 20000000 이다
    UNIT = {"천": 1_000, "만": 10_000, "억": 100_000_000}
    flat = text.replace(",", "")
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(천만|백만|천|만|억)", flat):
        n, u = float(m.group(1)), m.group(2)
        mult = {"천만": 10_000_000, "백만": 1_000_000}.get(u) or UNIT[u]
        out.add(n * mult)
    return out


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_rule(rule, clause_text, nums=None):
    """이 rule 의 값이 조문에 근거가 있나. 오류 문자열 목록을 낸다."""
    nums = numbers_in(clause_text) if nums is None else nums
    eff = rule.get("effect") or {}
    key = CHECKED.get(eff.get("type"))
    if key is None:
        return []
    v = eff.get(key)
    if not _is_num(v):
        return []                      # 문자열 값("UNLIMITED")은 이 축의 대상이 아니다
    if float(v) in nums:
        return []
    if float(v) == 0.0:
        # "불가" 를 한도 0 으로 옮긴 것일 수 있다. 보수적으로 봐준다.
        return []
    return [f"{eff['type']} 의 {key} {v} 가 조문에 없다. "
            f"조문의 수: {sorted(nums) if nums else '없음'}"]


def audit(recs, texts):
    rules = grounded = invented = 0
    by_clause = collections.Counter()
    examples = []
    seen_clauses, bad_clauses = set(), set()
    for x in recs:
        seen_clauses.add(x["clause_id"])
        text = texts.get(x["clause_id"], "")
        nums = numbers_in(text)
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict):
                continue
            errs = check_rule(r, text, nums)
            if CHECKED.get((r.get("effect") or {}).get("type")) is None:
                continue
            if not _is_num((r.get("effect") or {}).get("value")):
                continue
            rules += 1
            if errs:
                invented += 1
                bad_clauses.add(x["clause_id"])
                by_clause[x["clause_id"]] += 1
                if len(examples) < 8:
                    examples.append((x["clause_id"], r, errs[0]))
            else:
                grounded += 1
    n_clauses = len(seen_clauses)
    return {"checked": rules, "grounded": grounded, "invented": invented,
            # 라운드 비교에 쓰는 값 — 분모가 조문 수로 고정된다 (±2.5p)
            "clauses": n_clauses, "bad_clauses": len(bad_clauses),
            "rate": len(bad_clauses) / n_clauses * 100 if n_clauses else 0.0,
            # 참고용 — 분모가 흔들려 라운드 비교에 못 쓴다 (최대 ±46.5p)
            "rule_rate": invented / rules * 100 if rules else 0.0,
            "by_clause": by_clause, "examples": examples}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--clauses", default="data/corpus.json")
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in json.loads(Path(a.clauses).read_text("utf-8"))}
    r = audit(recs, texts)

    print(f"=== {Path(a.results).name} ===\n")
    print(f"⑨ 근거 없는 수 — 검사한 수치 effect {r['checked']}개 중 "
          f"**{r['invented']}개({r['rate']:.1f}%)가 조문에 없는 수다**\n")
    if r["by_clause"]:
        print(f"{'조문':<16}{'건수':>5}")
        print("-" * 24)
        for cid, n in r["by_clause"].most_common(12):
            print(f"{cid:<16}{n:>5}")
    print("\n실물")
    for cid, rule, err in r["examples"]:
        eff = rule.get("effect") or {}
        print(f"  [{cid}] {eff.get('type')} {eff.get('value')} {eff.get('unit') or ''}")
        print(f"      {err[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
