"""팀원 QLoRA 체크포인트끼리 Dev50 점수 차이가 우연을 넘나 — 짝지은 비교.

    python ckpt_paired.py        # → results/sys_qlora_paired.json + 요약 출력

팀원 평가는 `do_sample=False` 라 같은 체크포인트를 다시 돌려도 답이 같다. 그래서
`noise.py` 처럼 반복 실행으로 흔들림을 잴 수 없다. 흔들림은 **Dev 가 50문항뿐**인 데서
온다 — 같은 모델이라도 다른 50문항을 뽑았으면 점수가 달랐을 것이다.

그래서 이미 나온 문항별 점수(CSV)로 **같은 문항끼리 짝지어** 본다.

* 0/1 지표(semantic_exact · status_correct · json_parse): 한쪽만 맞힌 문항 수로
  **정확 McNemar**. 둘 다 맞히거나 둘 다 틀린 문항은 차이에 대해 말해 주는 것이 없다.
* 부분점수 지표(*_f1 · grounding_rate): 문항별 차이의 **부호 뒤집기 순열검정**.
* 둘 다 문항 부트스트랩으로 **평균 차이의 95% 구간**을 낸다.

팀원 점수 파일의 값이 CSV 문항 평균과 같은지 먼저 확인한다 — 다르면 멈춘다.
팀원 폴더는 **읽기만 한다.** `blind50_LOCKED` 는 열지 않는다.
"""

import csv
import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "sys_qlora_paired.json"

SYS = Path("/workspace/personal_workplace_SYS/experiment_code")
RUN = SYS / "qwen35_9b_part2_1_qlora_pilot_v1_1"
DEV = SYS / "gold_build400_dev50_gold_compact_v1_1.jsonl"
MODELS = {
    "base": RUN / "base_dev50_predictions.csv",
    "e1": RUN / "checkpoint_evals" / "epoch1_dev50_predictions.csv",
    "e2": RUN / "checkpoint_evals" / "epoch2_dev50_predictions.csv",
    "e3": RUN / "checkpoint_evals" / "epoch3_dev50_predictions.csv",
}
PAIRS = (("base", "e1"), ("e1", "e2"), ("e2", "e3"), ("base", "e3"))

BINARY = ("semantic_exact", "status_correct", "json_parse")
GRADED = ("form_f1", "effect_f1", "operator_f1", "group_op_f1",
          "unresolved_type_f1", "grounding_rate")
SCORE_KEY = {"json_parse": "json_parse_rate"}

SEED = 20260917
N_BOOT = 10000
N_PERM = 20000


# ── 통계 ────────────────────────────────────────────────────────────────
def mcnemar_exact(only_a, only_b):
    """양측 정확 McNemar. 한쪽만 맞힌 문항 수 둘을 받는다."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def min_discordant_for(alpha=0.05):
    """한쪽만 맞힌 문항이 전부 한 방향일 때 p < alpha 가 되는 최소 개수."""
    n = 1
    while mcnemar_exact(0, n) >= alpha:
        n += 1
    return n


def sign_flip_p(diffs, n_perm=N_PERM, rng=None):
    """짝지은 차이 평균이 0 인가 — 부호 뒤집기 순열검정 (양측, +1 보정)."""
    rng = rng or random.Random(SEED)
    d = [x for x in diffs if x != 0]
    if not d:
        return 1.0
    obs = abs(sum(d))
    hit = 0
    for _ in range(n_perm):
        s = sum(x if rng.random() < 0.5 else -x for x in d)
        if abs(s) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (n_perm + 1)


def boot_ci(diffs, n_boot=N_BOOT, rng=None):
    """문항 부트스트랩 — 평균 차이의 95% 구간 (백분위)."""
    rng = rng or random.Random(SEED)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]


# ── 읽기 ────────────────────────────────────────────────────────────────
def _val(row, metric):
    if metric == "json_parse":
        return row["json_parse_ok"] == "True"
    v = row[metric]
    return v == "True" if v in ("True", "False") else float(v)


def load(models=MODELS):
    """{모델: {sample_order: {지표: 값, ...}}}. 점수 파일과 CSV 평균이 다르면 멈춘다."""
    out, shas = {}, {}
    for tag, path in models.items():
        raw = path.read_bytes()
        shas[path.name if tag == "base" else f"{path.parent.name}/{path.name}"] = \
            hashlib.sha256(raw).hexdigest()
        rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
        per = {}
        for r in rows:
            per[int(r["sample_order"])] = {
                **{m: _val(r, m) for m in BINARY + GRADED},
                "gold_status": r["gold_status"], "pred_status": r["pred_status"],
                "document_name": r["document_name"], "failure_family": r["failure_family"]}
        scores = json.loads(path.with_name(path.name.replace("predictions.csv", "scores.json"))
                            .read_text("utf-8"))
        for m in BINARY + GRADED:
            mean = sum(float(v[m]) for v in per.values()) / len(per)
            want = scores[SCORE_KEY.get(m, m)]
            if abs(mean - want) > 1e-9:
                raise SystemExit(f"{tag} {m}: CSV 평균 {mean} ≠ 점수 파일 {want}")
        out[tag] = per
    keys = {t: set(v) for t, v in out.items()}
    if len({frozenset(k) for k in keys.values()}) != 1:
        raise SystemExit(f"모델마다 문항이 다르다: { {t: len(k) for t, k in keys.items()} }")
    return out, shas


# ── 비교 ────────────────────────────────────────────────────────────────
def compare(a, b, metric, orders):
    xa = [float(a[o][metric]) for o in orders]
    xb = [float(b[o][metric]) for o in orders]
    diffs = [y - x for x, y in zip(xa, xb)]
    lo, hi = boot_ci(diffs, rng=random.Random(SEED))
    res = {"a": sum(xa) / len(xa), "b": sum(xb) / len(xb),
           "diff": sum(diffs) / len(diffs), "ci95": [lo, hi]}
    if metric in BINARY:
        only_a = [o for o in orders if a[o][metric] and not b[o][metric]]
        only_b = [o for o in orders if b[o][metric] and not a[o][metric]]
        res.update(test="mcnemar_exact", only_a=len(only_a), only_b=len(only_b),
                   p=mcnemar_exact(len(only_a), len(only_b)),
                   only_a_items=only_a, only_b_items=only_b)
    else:
        res.update(test="sign_flip", up=sum(d > 0 for d in diffs), down=sum(d < 0 for d in diffs),
                   p=sign_flip_p(diffs, rng=random.Random(SEED)))
    return res


def run(data, orders=None):
    orders = sorted(orders or data["base"])
    return {f"{a}→{b}": {m: compare(data[a], data[b], m, orders) for m in BINARY + GRADED}
            for a, b in PAIRS}


def main():
    data, shas = load()
    orders = sorted(data["base"])
    rules = [o for o in orders if data["base"][o]["gold_status"] == "RULES_FOUND"]
    result = {
        "what": "팀원 QLoRA pilot v1.1 Dev50 — 체크포인트 짝지은 비교",
        "sources_sha256": shas,
        "dev_sha256": hashlib.sha256(DEV.read_bytes()).hexdigest(),
        "n": len(orders),
        "min_one_sided_discordant_for_p05": min_discordant_for(),
        "seed": SEED, "n_boot": N_BOOT, "n_perm": N_PERM,
        "all": run(data, orders),
        "rules_found_only": {"n": len(rules), **run(data, rules)},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")

    print(f"Dev {len(orders)}문항 · 한쪽만 맞힌 문항이 전부 한 방향이어도 "
          f"{result['min_one_sided_discordant_for_p05']}개는 돼야 p<0.05")
    for scope, block, n in (("전체", result["all"], len(orders)),
                            ("RULES_FOUND 만", result["rules_found_only"], len(rules))):
        print(f"\n## {scope} (n={n})")
        for pair in (f"{a}→{b}" for a, b in PAIRS):
            print(f"  {pair}")
            for m, r in block[pair].items():
                extra = (f"한쪽만 {r['only_a']}:{r['only_b']}" if r["test"] == "mcnemar_exact"
                         else f"오름 {r['up']} · 내림 {r['down']}")
                flag = "*" if r["p"] < 0.05 else " "
                print(f"   {flag} {m:19} {r['a']:.3f}→{r['b']:.3f}  차 {r['diff']:+.3f} "
                      f"[{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]  p={r['p']:.3f}  {extra}")
    print(f"\n→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
