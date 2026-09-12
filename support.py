"""⑪ 뒷받침 — 인용문이 그 rule 을 실제로 받치나.

**왜 이 축이 필요한가.**

④ `check_quote` 는 인용문이 조문 원문에 있는지만 본다 — 순수 부분문자열 검사다.
**그 인용문이 그 rule 을 뒷받침하는지는 아무도 안 본다.** 원문 아무 문장이나
붙여 넣으면 ④ 가 통과한다.

실물 (v6, `KBYY-S2-R11`):

    quote     "다른 예금 상품으로 전환하는 경우 저금통은 자동 해제됨"
    condition contract.channel == "BRANCH"
    effect    DISQUALIFY

인용문은 전환 이야기이고 조건은 채널 이야기다. ④ 는 통과한다.

완벽하게 재는 방법은 없다. 그건 뜻을 읽는 일이고 사람이나 gold 가 할 몫이다.
여기서는 **기계적으로 확실한 불일치만** 센다. 놓치는 것은 많고 잘못 잡는 것은 적게.

**이 축은 하한이다.** 사람이 v6 생성물을 눈으로 읽었을 때는 훨씬 많은 자리에서
인용문과 조건이 어긋났다 — 조건이 채널을 보는데 인용문은 상품 전환 이야기인
경우처럼, 기계로는 못 가리는 것이 많다. 여기 숫자가 낮다고 안심하면 안 된다.

세 가지를 본다.

1. **수치 불일치** — effect 에 수가 있는데 인용문에 그 수가 없다.
   조문 전체에는 있는데 인용문에 없으면, 그 인용문은 그 값의 근거가 아니다.
2. **이벤트 불일치** — 조건이 이벤트를 보는데 인용문에 그 이벤트의 단서가 없다.
3. **인용문이 조문 전체** — 조문을 통째로 인용하면 근거를 고른 것이 아니다.

**기존 ④ 를 건드리지 않는다.** 따로 센다.

    python support.py results/results_v6.json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import catalog
import grounding

# 이벤트가 조문에서 불릴 만한 말. catalog._HINTS 보다 좁게 — 확실한 것만.
_EVENT_WORDS = {
    "SALARY_TRANSFER": ("급여",),
    "AUTO_TRANSFER": ("자동이체", "공과금", "지로", "CMS"),
    "CARD_USAGE": ("카드",),
    "DEPOSIT": ("입금", "예치"),
    "PENSION_RECEIPT": ("연금",),
    "FX_TRANSACTION": ("외화", "환전", "외환"),
    "PRODUCT_SWITCH": ("전환",),
    "TERMINATION": ("해지",),
    "APP_LOGIN": ("로그인", "스타뱅킹", "앱"),
    "TRANSACTION_CORRECTION": ("정정",),
}


def _events_in(node, out=None):
    out = set() if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "event" and isinstance(v, str):
                out.add(v)
            _events_in(v, out)
    elif isinstance(node, list):
        for v in node:
            _events_in(v, out)
    return out


def _norm(s):
    return "".join(str(s).split())


def check_rule(rule, clause_text):
    """기계적으로 확실한 불일치만. 오류 문자열 목록."""
    q = (rule.get("source") or {}).get("quote") or ""
    if not q:
        return []
    errs = []

    # 1. 수치 — effect 의 수가 인용문에 없는데 조문 다른 데에는 있다
    eff = rule.get("effect") or {}
    key = grounding.CHECKED.get(eff.get("type"))
    v = eff.get(key) if key else None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) != 0.0:
        in_q = float(v) in grounding.numbers_in(q)
        in_c = float(v) in grounding.numbers_in(clause_text)
        if in_c and not in_q:
            errs.append(f"{eff['type']} 의 값 {v} 가 조문에는 있으나 "
                        f"인용문에는 없다 — 이 인용문은 그 값의 근거가 아니다")

    # 2. 이벤트 — 조건이 보는 이벤트의 단서가 인용문에 없다
    #
    # 참조표를 가리키는 인용문은 봐준다. "기본실적 중 하나 이상" 은 표가
    # 그것을 카드결제·공과금이체로 정의하므로 근거가 맞다.
    points_to_table = any(w in q for w in ("아래 표", "표 참조", "실적", "아래"))
    if not points_to_table:
        for ev in _events_in(rule.get("condition")) | _events_in(rule.get("guard")):
            words = _EVENT_WORDS.get(ev)
            if not words:
                continue
            if not any(w in q for w in words) and any(w in clause_text for w in words):
                errs.append(f"조건이 {ev} 를 보는데 인용문에 그 단서가 없다 "
                            f"(조문 다른 곳에는 있다)")

    # 3. 조문을 통째로 인용 — 짧은 조문은 봐준다.
    #    11자짜리 "[질권설정] ▪ 불가" 를 통째로 인용하는 것은 정상이다.
    if _norm(q) and _norm(q) == _norm(clause_text) and len(_norm(q)) > 60:
        errs.append("인용문이 조문 전체다 — 근거를 고른 것이 아니다")
    return errs


def audit(recs, texts):
    checked = bad = 0
    kinds = collections.Counter()
    by_clause = collections.Counter()
    examples = []
    for x in recs:
        text = texts.get(x["clause_id"], "")
        for r in (x.get("output") or {}).get("rules") or []:
            if not isinstance(r, dict) or not (r.get("source") or {}).get("quote"):
                continue
            checked += 1
            errs = check_rule(r, text)
            if errs:
                bad += 1
                by_clause[x["clause_id"]] += 1
                for e in errs:
                    kinds[e.split("—")[0].split("(")[0].strip()[:34]] += 1
                if len(examples) < 6:
                    examples.append((x["clause_id"], r, errs[0]))
    return {"checked": checked, "bad": bad,
            "rate": bad / checked * 100 if checked else 0.0,
            "kinds": kinds, "by_clause": by_clause, "examples": examples}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--clauses", default="data/corpus.json")
    a = ap.parse_args(argv)
    recs = json.loads(Path(a.results).read_text("utf-8"))
    texts = {c["id"]: c["text"] for c in json.loads(Path(a.clauses).read_text("utf-8"))}
    r = audit(recs, texts)
    print(f"=== {Path(a.results).name} ===\n")
    print(f"⑪ 인용문이 rule 을 안 받침 — 인용문 있는 rule {r['checked']}개 중 "
          f"**{r['bad']}개({r['rate']:.1f}%)**\n")
    for k, n in r["kinds"].most_common():
        print(f"  {n:>4}  {k}")
    if r["by_clause"]:
        print("\n  " + " · ".join(f"{c} {n}" for c, n in r["by_clause"].most_common(8)))
    print("\n실물")
    for cid, rule, err in r["examples"]:
        print(f"  [{cid}] quote {(rule.get('source') or {}).get('quote','')[:52]!r}")
        print(f"      {err[:104]}")
    print("\n④ 는 인용문이 원문에 있는지만 본다. 이 축은 그것이 근거인지를 본다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
