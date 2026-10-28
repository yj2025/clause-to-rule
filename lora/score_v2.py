"""10단계 · 새 평가셋(gold_v2) 채점 — 후보 다섯을 한 번에 (2026-10-27). GPU 없음.

    python lora/score_v2.py --vote-ids              ← Gemma 투표가 필요한 조문 (정답 안 봄: e1 · Gemma 출력만)
    python lora/score_v2.py | tee lora/logs/score_v2.log   ← 채점 (모든 출력이 다 있어야 돈다)

후보는 `lora/final_candidates.md` 에 고정한 다섯. 채점은 kb10 과 같은 ⑥ · 정답 빈 / 정답 rule · 효과 재현 · 정밀 (`score_split.evaluate`).
정답은 `data/gold_v2/<id>.json` 의 rules, 기본금리는 `lora/eval_v2/SERVER.md` 의 상품별 값.
출력은 숫자 · 조문 id 뿐 — 정답 내용은 찍지 않는다. **한 번만 돌린다.** 결과로 설정을 고치지 않는다.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import combine as C  # noqa: E402  (ROOT 로 chdir)
import relay_vote as RV  # noqa: E402
import score_split as S  # noqa: E402
import vote as V  # noqa: E402

BASE_RATE = {"HNSAL": 2.95, "HNDRM": 2.70, "HNWSH": 0.75}
OUT = {"base": ["lora/results/v2_base.json"], "e1": ["lora/results/v2_e1.json"],
       "gemma": ["lora/results/v2_gemma31.json"]}
VOTE = ["lora/results/v2_vote_gemma31.json"]


def clause_ids():
    return [c["id"] for c in json.loads(Path("data/gold_v2/_clauses.json").read_text("utf-8"))]


def vote_ids():
    e1, gm = C.load(OUT["e1"]), C.load(OUT["gemma"])
    ids = clause_ids()
    assert set(ids) <= set(e1) and set(ids) <= set(gm), "e1 · Gemma 출력이 다 있어야 한다"
    return [i for i in ids if not S.ok_rules(e1[i]) and S.ok_rules(gm[i])]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vote-ids", action="store_true")
    a = ap.parse_args(argv)
    if a.vote_ids:
        print(",".join(vote_ids()))
        return 0

    ids = clause_ids()
    gold = {i: json.loads(Path(f"data/gold_v2/{i}.json").read_text("utf-8")) for i in ids}
    S.kb10six.DRAFT.update(gold)            # 접두어가 kb10 과 안 겹친다 (HN*)
    S.kb10six.BASE_RATE.update(BASE_RATE)
    runs = {n: C.load(p) for n, p in OUT.items()}
    for n, r in runs.items():
        assert set(ids) <= set(r), f"{n}: 조문 {len(set(ids) - set(r))}개 없음"
    smp = V.samples(VOTE)
    need = vote_ids()
    assert set(need) <= set(smp), f"Gemma 투표 표본 없는 조문: {sorted(set(need) - set(smp))}"

    cands = {"1 빈 출력": {i: [] for i in ids},
             "2 순정 + P1": runs["base"],
             "3 e1 + P1": runs["e1"],
             "4 이어받기": C.combos(runs["e1"], runs["gemma"])["이어받기"],
             f"5 이어받기 + 투표 k={RV.K}": RV.relay_vote(runs["e1"], runs["gemma"], smp, RV.K)}
    ref = {"(참고) Gemma + P1 단독": runs["gemma"]}
    rows = {n: S.evaluate({i: v[i] for i in ids}, ids) for n, v in {**cands, **ref}.items()}
    n_has = rows["1 빈 출력"]["n_has"]
    print(f"새 평가셋 gold_v2 · {len(ids)}조문 · 정답 rule {n_has} · 정답 빈 {len(ids) - n_has} · Gemma 투표 조문 {len(need)}")
    print(f"  {'':26}{'n':>4}{'⑥':>7}{'⑥빈':>7}{'⑥rule':>7}{'재현':>7}{'정밀':>7}   맞춤/정답/출력  rule낸조문")
    for n, v in rows.items():
        print(f"  {n:26}{v['n']:>4}{v['six']:>7}{v['six_empty']:>7}{v['six_has']:>7}{v['rec']:>7}{v['prec']:>7}"
              f"   {v['hit']:>3}/{v['n_gold']:>3}/{v['n_out']:>3}   {v['out_rule']:>3}")

    # 갈린 조문 — 후보끼리 ⑥ 이 다른 조문 수 (몇 조문 차이는 흔들림일 수 있다)
    six = {n: {i: S.clause_six(i, v[i]) for i in ids} for n, v in cands.items()}
    names = list(cands)
    print("\n갈린 조문 수 (⑥ 이 다른 조문 · 앞 후보가 이김 / 짐)")
    for x in range(len(names)):
        for y in range(x + 1, len(names)):
            a, b = six[names[x]], six[names[y]]
            w = sum(a[i] > b[i] + 1e-6 for i in ids)
            l = sum(b[i] > a[i] + 1e-6 for i in ids)
            print(f"  {names[x]:26} vs {names[y]:26} 갈림 {w + l:>2} · {w} / {l}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
