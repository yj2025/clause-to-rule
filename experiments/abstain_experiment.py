"""«rule 을 낼지 말지» 를 출력의 일치로 가르면 빈 출력을 넘는가 — 기권 판단 시험 (2026-11-05). GPU 없음.

    python experiments/abstain_experiment.py

정답을 보지 않는 신호만 쓴다. 모든 출력에 P1(관문 탈락 → 빈 배열)을 먼저 건다.

    자기 일치   같은 코드를 여러 번 돌린 출력에서, 효과 키(effect.type · target/value)가 k 번 이상 나온 rule 만 낸다.
                k 는 결과를 보기 전에 정했다 — **주 기준은 과반**, 만장일치 · 2회 이상은 참고.
                kb10: v121~v127 a·b 여덟 판 · 코퍼스: v121~v127 네 판.
    모델 간 일치 e1 과 Gemma 4 31B 가 같은 효과 키를 낸 rule 만 (10-27 combine.py 의 «교집합» 과 같은 규칙).
                새 평가셋 v2 에는 같은 모델을 여러 번 돌린 출력이 없어 이것으로 본다.

⑥ 은 조문마다 재서 평균한다. 「낸 조문」 은 OK rule 을 하나라도 낸 조문 수다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]
import collections
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lora"))

import gate_experiment as X  # noqa: E402  (데이터 묶음 · 채점 함수를 같이 쓴다)
import score_split as S  # noqa: E402


def key(rule):
    return next(iter(S.eff_keys([rule])), None)


def consensus(runs, cid, k):
    """여러 판에서 효과 키가 k 판 이상에 나온 OK rule 만. rule 은 그 키를 처음 낸 판의 것을 쓴다."""
    seen, first = collections.Counter(), {}
    for run in runs:
        keys = set()
        for r in S.ok_rules(run.get(cid, [])):
            kk = key(r)
            if kk is not None and kk not in keys:
                keys.add(kk)
                first.setdefault(kk, r)
        seen.update(keys)
    return [first[kk] for kk, n in seen.items() if n >= k]


def agree(a, b):
    """a 의 OK rule 중 b 가 같은 효과 키를 낸 것만."""
    kb = {key(r) for r in S.ok_rules(b)}
    return [r for r in S.ok_rules(a) if key(r) in kb]


def avg(ids, six, outs):
    return statistics.mean(six(c, outs.get(c, [])) for c in ids)


def emitted(ids, outs):
    return sum(bool(S.ok_rules(outs.get(c, []))) for c in ids)


def self_consistency(name, ids, six, runs):
    n = len(runs)
    empty = avg(ids, six, {})
    each = [avg(ids, six, r) for r in runs]
    print(f"\n== {name} · {n}판 · 빈 출력 ⑥ {empty:.1f}")
    print(f"   {'':34}{'⑥':>7}{'빈 출력 대비':>11}{'낸 조문':>8}")
    print(f"   {'P1 한 판씩 (평균)':34}{statistics.mean(each):7.1f}{statistics.mean(each) - empty:+11.1f}"
          f"{statistics.mean(emitted(ids, r) for r in runs):8.1f}")
    for label, k in ((f"2판 이상 (참고)", 2), (f"과반 {n // 2 + 1}/{n} 이상 ← 주 기준", n // 2 + 1),
                     (f"만장일치 {n}/{n} (참고)", n)):
        outs = {c: consensus(runs, c, k) for c in ids}
        v = avg(ids, six, outs)
        print(f"   {label:34}{v:7.1f}{v - empty:+11.1f}{emitted(ids, outs):8d}")


def cross_model(name, ids, six, a, b, la, lb):
    empty = avg(ids, six, {})
    print(f"\n== {name} · 빈 출력 ⑥ {empty:.1f}")
    print(f"   {'':34}{'⑥':>7}{'빈 출력 대비':>11}{'낸 조문':>8}")
    for label, outs in ((f"{la} 단독", a), (f"{lb} 단독", b),
                        (f"{la} ∩ {lb} (일치한 것만)", {c: agree(a.get(c, []), b.get(c, [])) for c in ids})):
        v = avg(ids, six, outs)
        print(f"   {label:34}{v:7.1f}{v - empty:+11.1f}{emitted(ids, outs):8d}")


def main():
    name, ids, texts, six, paths = X.corpus()
    self_consistency(name, ids, six, X.runs_of([p for p in paths if p.exists()]))
    name, ids, texts, six, paths = X.kb10()
    self_consistency(name, ids, six, X.runs_of([p for p in paths if p.exists()]))
    # kb10 · 모델 간 — 10-27 combine.py 와 같은 재료
    e1 = {**X.runs_of([ROOT / "lora/results/dev_e1.json"])[0], **X.runs_of([ROOT / "lora/results/test_e1.json"])[0]}
    gm = X.runs_of([ROOT / "lora/results/kb10_gemma31.json"])[0]
    cross_model("kb10 105 · 모델 간", ids, six, e1, gm, "e1", "Gemma")
    name, ids, texts, six, paths = X.v2()
    e1, base = (X.runs_of([p])[0] for p in paths)
    gm = X.runs_of([ROOT / "lora/results/v2_gemma31.json"])[0]
    cross_model(name.replace("(e1 · 순정)", "· 모델 간"), ids, six, e1, gm, "e1", "Gemma")
    cross_model(name.replace("(e1 · 순정)", "· 모델 간"), ids, six, base, gm, "순정", "Gemma")


if __name__ == "__main__":
    main()
