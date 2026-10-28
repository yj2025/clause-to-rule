"""7단계 · 조합 분석 — 이미 있는 kb10 출력만으로 (2026-10-27, NEXT_PLAN 7단계). GPU 없음.

    python lora/combine.py | tee lora/logs/combine.log

재료 (kb10 105 = dev 22 + test 83, 전부 P1 을 채점 때 얹은 꼴):
    e1     lora/results/dev_e1.json + test_e1.json
    gemma  lora/results/kb10_gemma31.json
    base   showcase/results_kb10v127b.json   (순정 Qwen3-8B, v127b)

1) 오라클 상한 — 조문마다 {빈 출력 · e1 · gemma · base} 중 ⑥ 이 가장 높은 것을 골랐을 때. 동점이면 앞 순서(빈 출력 먼저).
   정답을 보고 고르므로 상한일 뿐이다. 오라클 «e1 · 빈만» 도 같이 낸다 — e1 이 기권해야 할 때 기권만 잘했으면 얼마인지.
2) 실제 조합 (효과 키 = score_split.eff_keys 의 (effect.type, target 또는 value)):
    교집합   e1 의 OK rule 중 gemma 가 같은 효과 키를 낸 것만
    합집합   e1 OK rule + gemma OK rule 중 e1 에 없는 효과 키 (같은 키는 e1 쪽 하나)
    이어받기 e1 이 OK rule 을 내면 e1, 아니면 gemma
   조합은 OK rule 만 다룬다 — UNSUPPORTED rule 은 effect 가 없어 ⑥ 에 안 걸린다 (아래 «검사» 줄이 확인한다).
조합 결과는 러너 출력 꼴로 `lora/results/combo_*.json` 에 남긴다 (모델 출력 조각뿐, 정답 없음).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score_split as S  # noqa: E402  (ROOT 로 chdir)

SRC = {"e1": ["lora/results/dev_e1.json", "lora/results/test_e1.json"],
       "gemma": ["lora/results/kb10_gemma31.json"],
       "base": ["showcase/results_kb10v127b.json"]}


def load(paths):
    out = {}
    for p in paths:
        for r in json.load(open(p)):
            if "clause_id" in r and "error" not in r:
                out[r["clause_id"]] = S.rules_of(r, True)
    return out


def key1(rule):
    return next(iter(S.eff_keys([rule])), None)


def combos(e1, gm):
    inter, union, relay = {}, {}, {}
    for i in e1:
        a, b = S.ok_rules(e1[i]), S.ok_rules(gm.get(i, []))
        kb = {key1(r) for r in b}
        ka = {key1(r) for r in a}
        inter[i] = [r for r in a if key1(r) in kb]
        union[i] = a + [r for r in b if key1(r) not in ka]
        relay[i] = a if a else b
    return {"교집합": inter, "합집합": union, "이어받기": relay}


def oracle(cands, ids):
    out, pick = {}, {}
    for i in ids:
        best = max(cands, key=lambda n: (S.clause_six(i, cands[n][i]), -list(cands).index(n)))
        out[i], pick[i] = cands[best][i], best
    return out, pick


def line(name, v):
    print(f"  {name:22}{v['n']:>4}{v['six']:>7}{v['six_empty']:>7}{v['six_has']:>7}{v['rec']:>7}{v['prec']:>7}"
          f"   {v['hit']:>3}/{v['n_gold']:>3}/{v['n_out']:>3}   {v['out_rule']:>3}")


def main():
    runs = {n: load(p) for n, p in SRC.items()}
    ids_all = sorted(runs["e1"])
    assert all(set(ids_all) <= set(r) for r in runs.values()), "출처마다 105조문이어야 한다"

    # 검사 — OK rule 만 남겨도 ⑥ 이 같은가 (UNSUPPORTED 가 ⑥ 에 안 걸린다는 가정)
    diff = sum(abs(S.clause_six(i, runs[n][i]) - S.clause_six(i, S.ok_rules(runs[n][i]))) > 1e-6
               for n in runs for i in ids_all)
    print(f"검사: OK rule 만 남겼을 때 ⑥ 이 달라진 조문 {diff} (0 이어야 조합이 공정)")

    cands = {"빈 출력": {i: [] for i in ids_all}, "e1": runs["e1"], "gemma": runs["gemma"], "base": runs["base"]}
    combo = combos(runs["e1"], runs["gemma"])
    for name, outs in combo.items():
        recs = [{"clause_id": i, "output": {"rules": outs[i]}, "final": {k: True for k in S.E.GATES},
                 "combo": name} for i in ids_all]
        Path(f"lora/results/combo_{ {'교집합': 'inter', '합집합': 'union', '이어받기': 'relay'}[name] }.json"
             .replace(" ", "")).write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")

    for split in ("dev", "test", "all"):
        ids = ids_all if split == "all" else S.E.split_ids(split)
        o4, pick = oracle(cands, ids)
        o2, _ = oracle({k: cands[k] for k in ("빈 출력", "e1")}, ids)
        rows = {**{k: S.evaluate(v, ids) for k, v in cands.items()},
                **{k: S.evaluate(v, ids) for k, v in combo.items()},
                "오라클 (빈·e1)": S.evaluate(o2, ids), "오라클 (넷)": S.evaluate(o4, ids)}
        n_has = rows["빈 출력"]["n_has"]
        print(f"\n[{split}] {len(ids)}조문 · 정답 rule {n_has} · 정답 빈 {len(ids) - n_has}   (전부 P1 얹음)")
        print(f"  {'':22}{'n':>4}{'⑥':>7}{'⑥빈':>7}{'⑥rule':>7}{'재현':>7}{'정밀':>7}   맞춤/정답/출력  rule낸조문")
        for k, v in rows.items():
            line(k, v)
        from collections import Counter
        print("  오라클 (넷) 고른 출처: " + " · ".join(f"{k} {v}" for k, v in Counter(pick.values()).most_common()))
        has = [i for i in ids if S.ok_rules(S.kb10six.DRAFT[i]["rules"])]
        print("  그중 정답 rule 조문: " + " · ".join(f"{k} {v}" for k, v in Counter(pick[i] for i in has).most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
