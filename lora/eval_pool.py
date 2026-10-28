"""환각률 — 정답 없는 보류 풀에서 관문 통과율을 잰다 (2026-10-26, NEXT_PLAN 3단계).

풀은 증류 481조문 중 학습에 안 쓴 111개 (`data/holdout_pool.json` = pool − train ids: 관문 탈락 83 + 빈 비율 상한으로 뺀 28).
kb10 과 상품은 안 겹치지만 **학습 상품과는 겹친다** (같은 문서의 다른 조문). 관문 탈락 쪽은 Gemma 도 못 넘은 어려운 조문이다.

    python lora/eval_pool.py --out lora/results/pool_e1_c.json --adapter lora/adapters/r16/checkpoint-52 --constrain
    python lora/eval_pool.py --score lora/results/pool_*.json      ← 채점만 (GPU 없음, 정답 불필요)
    python lora/eval_pool.py --clauses data/gold_v2/_clauses.json --out lora/results/v2_e1.json --adapter ...   ← 10단계 (새 셋 한 번)

생성은 eval_adapter 와 같다 — `run_local_v2.run_clause` (재시도 · 후처리 · P1 그대로, temperature 기본값).
제약은 `run_local_v2.set_constrain` + `thin_schema.THIN`. xgrammar 는 PYTHONPATH 의 개인 폴더에서 온다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_adapter as E  # noqa: E402  (ROOT 로 chdir)

POOL = HERE / "data/holdout_pool.json"


def run(adapter, constrain, out, limit=None, base="Qwen/Qwen3-8B", samples=1, temperature=0.1, pool=POOL):
    import run_local_v2 as R
    clauses = json.loads(Path(pool).read_text("utf-8"))[:limit]
    outp = Path(out)
    recs = json.loads(outp.read_text("utf-8")) if outp.exists() else []
    done = {r["clause_id"] for r in recs}
    tok, model = R.load_model(base)
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter).eval()
    if constrain:
        import thin_schema
        R.set_constrain(tok, model, thin_schema.THIN)
    t0 = time.time()
    for i, c in enumerate([x for x in clauses if x["id"] not in done], 1):
        tc = time.time()
        got = R.run_clause(tok, model, c, runs=samples, temperature=temperature)
        for g in got:
            g.update(adapter=adapter, constrain=constrain, temperature=temperature,
                     seconds=round((time.time() - tc) / samples, 1))
        recs += got
        R._release()
        fin = got[0].get("final") or {}
        print(f"진행 {i} [{c['id']}] 관문{sum(bool(fin.get(k)) for k in E.GATES)} 시도{got[0]['n_attempts']} "
              f"{time.time() - tc:.0f}s ({time.time() - t0:.0f}s)", flush=True)
        outp.write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    print(f"완료 → {out}", flush=True)


def stats(path):
    recs = [r for r in json.load(open(path)) if "clause_id" in r]
    n = len(recs)
    fin = [r.get("final") or {} for r in recs]
    # 빈 출력이 아닌 것 = 모델이 낸 출력이 rule 을 담았던 것 (P1 로 버려진 것 포함)
    raw_rules = [bool(((r.get("gate_dropped") or r.get("output") or {}).get("rules"))) for r in recs]
    nonempty = sum(raw_rules)
    return {"n": n,
            "gates_all": sum(all(f.get(k) for k in E.GATES) for f in fin),
            "rule_out": nonempty,
            "rule_gates_all": sum(all(f.get(k) for k in E.GATES) for f, x in zip(fin, raw_rules) if x),
            "catalog_fail": sum(x and not f.get("catalog_ok") for f, x in zip(fin, raw_rules)),
            "p1_drop": sum(r.get("gate_dropped") is not None for r in recs),
            "empty_final": sum(not (r.get("output") or {}).get("rules") for r in recs),
            "sec": round(sum(r.get("seconds", 0) for r in recs) / max(n, 1), 1),
            "tries": round(sum(r.get("n_attempts", 0) for r in recs) / max(n, 1), 2)}


def score_report(paths):
    print(f"  {'':24}{'n':>4}{'rule낸':>7}{'그중관문다':>9}{'catalog실패':>10}{'P1버림':>7}{'최종빈':>7}{'시도':>6}{'초/조문':>8}")
    rows = {}
    for p in paths:
        s = rows[Path(p).stem] = stats(p)
        print(f"  {Path(p).stem:24}{s['n']:>4}{s['rule_out']:>7}{s['rule_gates_all']:>9}{s['catalog_fail']:>10}"
              f"{s['p1_drop']:>7}{s['empty_final']:>7}{s['tries']:>6}{s['sec']:>8}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter")
    ap.add_argument("--constrain", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--samples", type=int, default=1, help="8단계 투표 — 조문당 회차 수 (레코드가 회차마다 하나)")
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--clauses", default=str(POOL), help="조문 파일 (기본: 보류 풀)")
    ap.add_argument("--score", nargs="*")
    a = ap.parse_args(argv)
    if a.score is not None:
        score_report(a.score)
        return 0
    run(a.adapter, a.constrain, a.out, a.limit, samples=a.samples, temperature=a.temperature, pool=a.clauses)
    if a.samples == 1:
        score_report([a.out])
    return 0


if __name__ == "__main__":
    sys.exit(main())
