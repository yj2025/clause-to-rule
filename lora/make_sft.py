"""SFT 데이터 — 증류 라벨(관문 통과분) + 코퍼스 정답 → train, kb10 정답 → dev · test (2026-10-20).

나누기는 **상품 단위**다. kb10 은 학습에 넣지 않는다.

  * train : 증류 풀(kb10 · 코퍼스와 문서가 겹치는 상품 제외) 중 관문 다섯을 다 넘고 뜻 오류 0 · 잘림 없음
            + 코퍼스 정답 46 (KBONE · KBYY)
  * dev   : kb10 중 KBNR · KBHAP · KBGEN 정답 (22조문) — 체크포인트 고르기
  * test  : kb10 나머지 7상품 정답 (83조문) — 끝에 한 번만

입력은 기본 러너와 같다(SYSTEM_PROMPT + build_user_prompt) — 학습한 모델을 `run_local_v2.run_clause` 의
재시도 루프에 그대로 넣기 위해서다. 목표는 {"rules": [...]} 만 (v125 교훈: 출력 키를 늘리면 흔들린다).

    python lora/make_sft.py --distill lora/data/distill_gemma31.json
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from prompt import SYSTEM_PROMPT, build_user_prompt  # noqa: E402

DEV_PREFIX = ("KBNR", "KBHAP", "KBGEN")
GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")


def sample(cid, text, rules):
    return {"id": cid, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(text, cid)},
        {"role": "assistant", "content": json.dumps({"rules": rules}, ensure_ascii=False)}]}


def passed(r):
    """관문 다섯 · 뜻 오류 0 · 잘림 없음. 빈 배열은 검증기가 catalog 이하 관문을 끄므로 json · schema 만 본다."""
    f = r.get("final") or {}
    if r.get("truncated") or r.get("output") is None or r.get("semantic_errors"):
        return False
    if f.get("empty"):
        return bool(f.get("json_ok") and f.get("schema_ok"))
    return all(f.get(k) for k in GATES)


def renumber(cid, rules):
    """증류 라벨의 rule_id 를 정답 관례(R-<조문>-NN)로 맞춘다."""
    return [{**r, "rule_id": f"R-{cid}-{i:02d}"} for i, r in enumerate(rules, 1)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--distill", nargs="+", required=True)
    ap.add_argument("--max-empty-share", type=float, default=0.35,
                    help="증류 라벨 중 빈 배열 비율 상한 — 넘으면 빈 것을 덜어 낸다 (기권만 배우지 않게)")
    a = ap.parse_args(argv)

    pool = {c["id"]: c for c in json.loads((HERE / "data/pool.json").read_text("utf-8"))}
    stat = collections.Counter()
    silver, empty = [], []
    for f in a.distill:
        for r in json.loads(Path(f).read_text("utf-8")):
            stat["증류 전체"] += 1
            if not passed(r):
                stat["관문 탈락"] += 1
                continue
            rules = renumber(r["clause_id"], r["output"].get("rules") or [])
            s = sample(r["clause_id"], pool[r["clause_id"]]["text"], rules)
            (silver if rules else empty).append(s)
    random.seed(0)
    random.shuffle(empty)
    cap = int(a.max_empty_share / (1 - a.max_empty_share) * len(silver))
    stat["증류 통과 · rule 있음"] = len(silver)
    stat["증류 통과 · 빈 배열"] = len(empty)
    empty = empty[:cap]
    stat["빈 배열 남김"] = len(empty)

    corpus = {c["id"]: c for c in json.loads((ROOT / "data/corpus.json").read_text("utf-8"))}
    gold_corpus = [sample(cid, c["text"], json.loads((ROOT / f"data/gold/{cid}.json").read_text("utf-8"))["rules"])
                   for cid, c in corpus.items()]
    kb10 = {c["id"]: c for c in json.loads((ROOT / "showcase/clauses_key.json").read_text("utf-8"))}
    dev, test = [], []
    for cid, c in kb10.items():
        g = json.loads((ROOT / f"showcase/gold_draft/{cid}.json").read_text("utf-8"))
        (dev if cid.startswith(DEV_PREFIX) else test).append(sample(cid, c["text"], g["rules"]))

    train = silver + empty + gold_corpus
    random.shuffle(train)
    out = HERE / "data"
    for name, rows in (("train", train), ("dev", dev), ("test", test)):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for s in rows:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    stat.update({"train": len(train), "dev": len(dev), "test": len(test), "코퍼스 정답": len(gold_corpus)})
    (out / "sft_stats.json").write_text(json.dumps(stat, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(stat, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
