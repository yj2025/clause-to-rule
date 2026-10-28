"""8단계 · 이어받기 + Gemma 투표 — 후보 5 (2026-10-27, 결과 보기 전에 규칙을 정함). GPU 없음.

    python lora/relay_vote.py | tee lora/logs/relay_vote.log

규칙 (`final_candidates.md` 에 고정, kb10 결과로 바꾸지 않는다):
    1) e1 + P1 이 OK rule 을 내면 e1 그대로.
    2) 아니면 Gemma 탐욕(온도 0) + P1 의 OK rule 을 본다. 없으면 빈 출력.
    3) 있으면 같은 조문을 Gemma 온도 0.7 로 5회 (회차마다 재시도 · 관문 · P1) 뽑아,
       탐욕 rule 중 효과 키가 5회 중 **3회 이상** 나온 것만 남긴다. 표본에서 새 rule 을 더하지는 않는다 (거르기만).
효과 키는 score_split.eff_keys 와 같다. 비교로 «이어받기»(7단계, 거르기 없음)와 k=1~5 를 같이 낸다 — k=3 이 정한 값이다.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import combine as C  # noqa: E402  (ROOT 로 chdir)
import score_split as S  # noqa: E402
import vote as V  # noqa: E402

K = 3
SAMPLES = ["lora/results/vote_kb10_gemma31.json"]


def relay_vote(e1, greedy, smp, k):
    """조문별 rule. smp 에 없는 조문은 Gemma 표본이 없는 것 — 그 자리에 Gemma 가 끼어들면 안 된다."""
    out = {}
    for i in e1:
        a, b = S.ok_rules(e1[i]), S.ok_rules(greedy.get(i, []))
        if a or not b:
            out[i] = a
            continue
        assert i in smp, f"{i}: Gemma 표본 없음"
        cnt = V.agreement(smp[i])
        out[i] = [r for r in b if cnt[V.key1(r)] >= k]
    return out


def main():
    e1, gm = C.load(C.SRC["e1"]), C.load(C.SRC["gemma"])
    smp = V.samples(SAMPLES)
    print(f"Gemma 표본 {len(smp)}조문 · 조문당 회차 {sorted({len(v) for v in smp.values()})} · 정한 k={K}")
    for i in sorted(smp):
        b = S.ok_rules(gm[i])
        cnt = V.agreement(smp[i])
        print(f"  {i:16} 탐욕 OK rule {len(b)} · 효과 키별 표본 회차 {[cnt[V.key1(r)] for r in b]}")
    ids_all = sorted(e1)
    rows_by = {"빈 출력": {i: [] for i in ids_all}, "e1": e1, "이어받기 (거르기 없음)": C.combos(e1, gm)["이어받기"]}
    for k in range(1, 6):
        rows_by[f"이어받기 + 투표 k={k}" + (" ←" if k == K else "")] = relay_vote(e1, gm, smp, k)
    for split in ("dev", "test", "all"):
        ids = ids_all if split == "all" else S.E.split_ids(split)
        rows = {n: S.evaluate(v, ids) for n, v in rows_by.items()}
        n_has = rows["빈 출력"]["n_has"]
        print(f"\n[{split}] {len(ids)}조문 · 정답 rule {n_has} · 정답 빈 {len(ids) - n_has}   (전부 P1 얹음, 참고 숫자)")
        print(f"  {'':22}{'n':>4}{'⑥':>7}{'⑥빈':>7}{'⑥rule':>7}{'재현':>7}{'정밀':>7}   맞춤/정답/출력  rule낸조문")
        for n, v in rows.items():
            C.line(n, v)
    recs = [{"clause_id": i, "output": {"rules": rows_by[f"이어받기 + 투표 k={K} ←"][i]},
             "final": {g: True for g in S.E.GATES}, "combo": f"relay_vote_k{K}"} for i in ids_all]
    Path(f"lora/results/combo_relay_vote_k{K}.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
