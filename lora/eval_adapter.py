"""어댑터 평가 — 기본 러너(`run_local_v2.run_clause`, 재시도 · 후처리 그대로)에 LoRA 를 얹어 kb10 을 돈다 (2026-10-20).

    python lora/eval_adapter.py --adapter lora/adapters/r16/checkpoint-XX --split dev --out lora/results/dev_e1.json
    python lora/eval_adapter.py --score lora/results/dev_e1.json --split dev      ← 채점만 (GPU 없음)

채점은 `showcase/kb10six.py` 의 ⑥ 을 조문별로 받아 split 안에서 평균 낸다. 견줄 기준선은 v127a · v127b (같은 조문).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "showcase"))

GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
BASELINES = ["showcase/results_kb10v127a.json", "showcase/results_kb10v127b.json"]


def split_ids(split):
    return [json.loads(l)["id"] for l in open(HERE / f"data/{split}.jsonl", encoding="utf-8")]


def summarize(path, ids):
    import kb10six
    six = kb10six.six(path)
    recs = {r["clause_id"]: r for r in json.load(open(path))}
    got = [i for i in ids if i in six]
    gates = sum(all((recs[i].get("final") or {}).get(k) for k in GATES) for i in got)
    empty = sum(not ((recs[i].get("output") or {}).get("rules")) for i in got)
    gold_empty = sum(not kb10six.DRAFT[i]["rules"] for i in got)
    return {"n": len(got), "six": round(sum(six[i] for i in got) / max(len(got), 1), 1),
            "gates_all": gates, "empty_out": empty, "empty_gold": gold_empty,
            "per_clause": {i: six[i] for i in got}}


def empty_baseline(ids):
    import kb10six
    from scoring import score
    s = [score(kb10six.DRAFT[i]["rules"] or [], [], "SUM", kb10six.P,
               kb10six.BASE_RATE[i.split("-")[0]])["rate"] * 100 for i in ids]
    return round(sum(s) / len(s), 1)


def score_report(paths, split):
    ids = split_ids(split)
    rows = {"빈 출력": {"six": empty_baseline(ids)}}
    for p in BASELINES + paths:
        s = summarize(p, ids)
        rows[Path(p).stem] = {k: v for k, v in s.items() if k != "per_clause"}
    print(f"[{split}] {len(ids)}조문")
    for k, v in rows.items():
        print(f"  {k:28} ⑥ {v['six']:5}  " + (f"관문 다 {v['gates_all']}/{v['n']} · 빈 출력 {v['empty_out']} (정답 빈 {v['empty_gold']})"
                                             if "n" in v else ""))
    return rows


def run(adapter, split, out, base="Qwen/Qwen3-8B", constrain=False, samples=1, temperature=0.1):
    import run_local_v2 as R
    from peft import PeftModel
    clauses = {c["id"]: c for c in json.loads(Path("showcase/clauses_key.json").read_text("utf-8"))}
    ids = split_ids(split)
    outp = Path(out)
    recs = json.loads(outp.read_text("utf-8")) if outp.exists() else []
    done = {r["clause_id"] for r in recs}
    tok, model = R.load_model(base)
    if adapter:
        model = PeftModel.from_pretrained(model, adapter).eval()
    if constrain:                                   # 10-26 · 제약 디코딩 (thin_schema, xgrammar 는 PYTHONPATH 개인 폴더)
        sys.path.insert(0, str(HERE))
        import thin_schema
        R.set_constrain(tok, model, thin_schema.THIN)
    t0 = time.time()
    for i, cid in enumerate([x for x in ids if x not in done], 1):
        tc = time.time()
        got = R.run_clause(tok, model, clauses[cid], runs=samples, temperature=temperature)
        for g in got:
            g["adapter"] = adapter
            g["constrain"] = constrain
            g["temperature"] = temperature
        recs += got
        R._release()
        print(f"진행 {i} [{cid}] 시도{got[0]['n_attempts']} {time.time() - tc:.0f}s ({time.time() - t0:.0f}s)", flush=True)
        outp.write_text(json.dumps(recs, ensure_ascii=False, indent=1), "utf-8")
    print(f"완료 → {out}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--out")
    ap.add_argument("--constrain", action="store_true")
    ap.add_argument("--samples", type=int, default=1, help="8단계 투표 — 조문당 회차 수")
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--score", nargs="*")
    a = ap.parse_args(argv)
    if a.score is not None:
        score_report(a.score, a.split)
        return 0
    run(a.adapter, a.split, a.out, constrain=a.constrain, samples=a.samples, temperature=a.temperature)
    if a.samples == 1:
        score_report([a.out], a.split)
    return 0


if __name__ == "__main__":
    sys.exit(main())
