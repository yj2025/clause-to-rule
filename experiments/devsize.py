"""다음 pilot 의 Dev 는 몇 문항이어야 체크포인트 차이를 가르나.

    python experiments/devsize.py        # → results/dev_size.json + 표 출력

`experiments/ckpt_paired.py` 가 보인 것 — Dev50 으로는 e2 와 e3 를 못 가른다. 그러면 얼마면 되나.
유의수준 0.05 (양측), 검정력 0.8 을 기준으로 잡는다.

**0/1 지표 (semantic_exact · status_correct).** 짝지은 비교는 정확 McNemar 다.
필요한 문항 수는 차이 Δ 만이 아니라 **한쪽만 맞히는 문항 비율 p_disc** 에 달렸다.
검정력을 정확히 계산한다 — 불일치 문항 수 D ~ Bin(N, p_disc), 그중 새 체크포인트 쪽
B ~ Bin(D, q), q = (p_disc + Δ) / (2 · p_disc). 이 pilot 은 개선이 전부 한 방향이라
p_disc = Δ 였다 (e1→e2 정확 일치 0 : 4). 체크포인트가 성숙하면 양쪽으로 갈린다.
그래서 p_disc = Δ · r, r = 1 · 2 · 4 를 본다.

**부분점수 지표 (*_f1).** 문항별 차이의 표준편차 σ 로 정규근사
N = ((z₀.₉₇₅ + z₀.₈) · σ / Δ)². σ 는 **e2 → e3** 에서 잰다 — 다음 pilot 이 가를
것은 성숙한 체크포인트끼리라서다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binom, norm

import ckpt_paired as C

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "dev_size.json"

ALPHA = 0.05
POWER = 0.8
DELTAS = (0.02, 0.05, 0.10)
RATIOS = (1, 2, 4)
GRADED = ("form_f1", "effect_f1", "operator_f1")
N_MAX = 20000


def mcnemar_power(n, delta, p_disc, alpha=ALPHA):
    """정확 McNemar(양측, p < alpha 에서 기각)의 검정력."""
    if not 0 < delta <= p_disc <= 1:
        raise ValueError(f"0 < Δ ≤ p_disc ≤ 1 이어야 한다: Δ={delta}, p_disc={p_disc}")
    q = (p_disc + delta) / (2 * p_disc)
    d = np.arange(1, n + 1)
    # 불일치 d 개에서 기각되는 가장 큰 소수 쪽 개수 lo: 2·F(lo; d, ½) < alpha
    lo = binom.ppf(alpha / 2, d, 0.5).astype(int)
    lo = np.where(2 * binom.cdf(lo, d, 0.5) < alpha, lo, lo - 1)
    reject = np.where(lo >= 0, binom.cdf(lo, d, q) + binom.cdf(lo, d, 1 - q), 0.0)
    return float(np.sum(binom.pmf(d, n, p_disc) * reject))


def mcnemar_n(delta, p_disc, power=POWER, alpha=ALPHA, n_max=N_MAX):
    """검정력이 **처음** power 이상이 되는 N. 정확검정은 톱니라 그 뒤로 잠깐 내려갈 수 있다."""
    lo = 1
    while lo * 2 <= n_max and mcnemar_power(lo * 2, delta, p_disc, alpha) < power:
        lo *= 2
    # 두 배씩 건너뛰면 톱니의 앞 교차를 놓칠 수 있다 — 아래 끝에서부터 한 칸씩 훑는다
    for n in range(max(1, lo // 2), n_max + 1):
        if mcnemar_power(n, delta, p_disc, alpha) >= power:
            return n
    return None


def normal_n(sigma, delta, power=POWER, alpha=ALPHA):
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil((z * sigma / delta) ** 2)


def main():
    data, shas = C.load()
    orders = sorted(data["base"])

    binary = []
    for delta in DELTAS:
        for r in RATIOS:
            p = delta * r
            binary.append({"delta": delta, "ratio": r, "p_disc": p,
                           "n": mcnemar_n(delta, p),
                           "power_at_50": mcnemar_power(50, delta, p)})

    sigma = {}
    for m in GRADED:
        diffs = [float(data["e3"][o][m]) - float(data["e2"][o][m]) for o in orders]
        mean = sum(diffs) / len(diffs)
        sigma[m] = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (len(diffs) - 1))
    graded = [{"metric": m, "sigma_e2_e3": sigma[m], "delta": delta,
               "n": normal_n(sigma[m], delta)}
              for m in GRADED for delta in DELTAS]

    observed = {}
    for a, b in C.PAIRS:
        only_a = sum(1 for o in orders if data[a][o]["semantic_exact"] and not data[b][o]["semantic_exact"])
        only_b = sum(1 for o in orders if data[b][o]["semantic_exact"] and not data[a][o]["semantic_exact"])
        observed[f"{a}→{b}"] = {"only_a": only_a, "only_b": only_b,
                                "p_disc": (only_a + only_b) / len(orders)}

    result = {"alpha": ALPHA, "power": POWER, "sources_sha256": shas,
              "observed_semantic_exact_discordance": observed,
              "binary_mcnemar": binary, "graded_normal": graded}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")

    print(f"α={ALPHA} 양측 · 검정력 {POWER}\n")
    print("정확 일치 불일치 (관측):",
          " · ".join(f"{k} {v['only_a']}:{v['only_b']}" for k, v in observed.items()))
    print("\n## 0/1 지표 — 정확 McNemar")
    print("   Δ     p_disc (=Δ·r)   필요 N   지금 N=50 의 검정력")
    for x in binary:
        n = x["n"] if x["n"] is not None else f">{N_MAX}"
        print(f"  {x['delta']:4.0%}   {x['p_disc']:5.0%} (r={x['ratio']})   {n:>6}   {x['power_at_50']:5.1%}")
    print("\n## 부분점수 지표 — 정규근사, σ 는 e2→e3")
    for m in GRADED:
        row = " · ".join(f"Δ {x['delta']:.0%} → {x['n']}" for x in graded if x["metric"] == m)
        print(f"  {m:12} σ={sigma[m]:.3f}   {row}")
    print(f"\n→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
