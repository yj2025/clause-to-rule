"""⑥ 을 둘로 나누고 효과 단위 재현율 · 정밀도를 더한다 — GPU 없이 이미 있는 결과로 (2026-10-26).

    python lora/score_split.py                         ← 기본 묶음 (빈 출력 · v127a/b · e1~e3 · 있으면 선생)
    python lora/score_split.py --runs lora/results/x.json --split test

⑥ 은 빈 출력에 유리하다 — 정답에 OK rule 이 없는 조문이 대부분이고, 놓친 rule 은 거의 안 벌준다.
그래서 «정답 빈»(OK rule 없음) / «정답 rule»(OK rule 있음) 조문 평균을 따로 낸다.
효과 단위: 정답 OK rule 의 (effect.type, target 또는 value) 를 출력 OK rule 이 몇 개 맞췄나 (다중집합, split 안 합산).
P1 은 채점 때 얹는다 — 관문 다섯을 다 못 넘은 비어 있지 않은 출력을 빈 배열로 (run_local_v2.drop_gate_failed 와 같은 규칙).
출력은 숫자 표뿐이다 — 정답 내용은 찍지 않는다.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_adapter as E  # noqa: E402  (ROOT 로 chdir · showcase 경로를 잡아 준다)
import kb10six  # noqa: E402
from scoring import score  # noqa: E402

DEFAULT = {"dev": ["showcase/results_kb10v127a.json", "showcase/results_kb10v127b.json",
                   "lora/results/dev_e1.json", "lora/results/dev_e2.json", "lora/results/dev_e3.json",
                   "lora/results/kb10_gemma31.json"],
           "test": ["showcase/results_kb10v127a.json", "showcase/results_kb10v127b.json",
                    "lora/results/test_e1.json", "lora/results/kb10_gemma31.json"]}


def ok_rules(rules):
    return [r for r in rules or [] if isinstance(r, dict) and r.get("status") == "OK"]


def eff_keys(rules):
    keys = Counter()
    for r in ok_rules(rules):
        e = r.get("effect") if isinstance(r.get("effect"), dict) else {}
        keys[(json.dumps(e.get("type")), json.dumps(e.get("target") if "target" in e else e.get("value"),
                                                    ensure_ascii=False, sort_keys=True))] += 1
    return keys


def rules_of(rec, p1):
    rules = (rec.get("output") or {}).get("rules")
    rules = rules if isinstance(rules, list) else []
    if p1 and rules and not all((rec.get("final") or {}).get(k) for k in E.GATES):
        return []
    return rules


def clause_six(cid, rules):
    return score(kb10six.DRAFT[cid]["rules"] or [], rules, "SUM", kb10six.P,
                 kb10six.BASE_RATE[cid.split("-")[0]])["rate"] * 100


def evaluate(outs, ids):
    """outs: {조문: 출력 rules}. ids 중 outs 에 있는 것만 잰다."""
    got = [i for i in ids if i in outs]
    six = {i: clause_six(i, outs[i]) for i in got}
    has = [i for i in got if ok_rules(kb10six.DRAFT[i]["rules"])]
    emp = [i for i in got if i not in has]
    hit = n_gold = n_out = 0
    for i in got:
        g, o = eff_keys(kb10six.DRAFT[i]["rules"]), eff_keys(outs[i])
        hit += sum((g & o).values())
        n_gold += sum(g.values())
        n_out += sum(o.values())
    avg = lambda xs: round(sum(six[i] for i in xs) / len(xs), 1) if xs else float("nan")  # noqa: E731
    return {"n": len(got), "n_has": len(has), "six": avg(got), "six_empty": avg(emp), "six_has": avg(has),
            "rec": round(100 * hit / n_gold, 1) if n_gold else float("nan"),
            "prec": round(100 * hit / n_out, 1) if n_out else float("nan"),
            "hit": hit, "n_gold": n_gold, "n_out": n_out,
            "out_rule": sum(bool(ok_rules(outs[i])) for i in got)}


def report(split, paths):
    ids = E.split_ids(split)
    rows = {"빈 출력": evaluate({i: [] for i in ids}, ids)}
    for p in paths:
        if not Path(p).exists():
            continue
        recs = {r["clause_id"]: r for r in json.load(open(p)) if "clause_id" in r and "error" not in r}
        for p1 in (False, True):
            rows[f"{Path(p).stem.replace('results_', '')} {'P1' if p1 else 'P0'}"] = evaluate(
                {i: rules_of(r, p1) for i, r in recs.items()}, ids)
    n_has = rows["빈 출력"]["n_has"]
    print(f"\n[{split}] {len(ids)}조문 · 정답 rule {n_has} · 정답 빈 {len(ids) - n_has}")
    print(f"  {'':22}{'n':>4}{'⑥':>7}{'⑥빈':>7}{'⑥rule':>7}{'재현':>7}{'정밀':>7}   맞춤/정답/출력  rule낸조문")
    for k, v in rows.items():
        print(f"  {k:22}{v['n']:>4}{v['six']:>7}{v['six_empty']:>7}{v['six_has']:>7}{v['rec']:>7}{v['prec']:>7}"
              f"   {v['hit']:>3}/{v['n_gold']:>3}/{v['n_out']:>3}   {v['out_rule']:>3}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"])
    ap.add_argument("--runs", nargs="*")
    ap.add_argument("--json", help="표를 json 으로도 남긴다 (숫자만)")
    a = ap.parse_args(argv)
    out = {}
    for split in [a.split] if a.split else ["dev", "test"]:
        out[split] = report(split, a.runs if a.runs is not None else DEFAULT[split])
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
