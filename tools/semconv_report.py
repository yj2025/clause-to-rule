"""팀원 gold(semantic_rule v1.1) 전체를 변환기에 넣고 막힌 이유를 센다.

    python tools/semconv_report.py                     # 결과 + 요약 출력
    python tools/semconv_report.py --slots out.json    # 대응표에 판정이 없는 표현 목록

팀원 폴더는 **읽기만 한다.** 파일 해시를 결과에 적어 어느 판을 쟀는지 남긴다.
`gold_build400_review_blind50_LOCKED_v1_1.csv` 는 열지 않는다 — 팀원이 잠근 평가셋이다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import hashlib
import json
from pathlib import Path

import semconv

SYS = Path("/workspace/personal_workplace_SYS/experiment_code")
SPLITS = {
    "train": SYS / "gold_build400_train_ready265_compact_v1_1.jsonl",
    "dev": SYS / "gold_build400_dev50_gold_compact_v1_1.jsonl",
}
OUT = Path(__file__).resolve().parents[1] / "results" / "semconv_gold315.json"

# 이 저장소의 46조문과 같은 상품 — 따로 떼어 본다
OWN_PRODUCTS = ("KB Young Youth 통장", "KB국민ONE통장")


def load(splits=SPLITS):
    rows = []
    for name, path in splits.items():
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_split"], r["_sha256"] = name, sha
                rows.append(r)
    return rows


def run(rows, lex):
    out = []
    for r in rows:
        rid = f"{r['_split']}-{r['sample_order']}"
        res = semconv.convert_record(r["semantic_rule"], lex, rid)
        out.append({"id": rid, "split": r["_split"], "section_id": r["section_id"],
                    "document_name": r["document_name"], "section_path": r["section_path"],
                    **res})
    return out


def _primary(layers):
    return layers[0] if layers else None


def summarize(results):
    s = {"records": collections.Counter(), "units": collections.Counter(),
         "unit_primary_layer": collections.Counter(), "unit_any_layer": collections.Counter(),
         "vocab_only_units": 0, "effects": 0, "blocked_effects": 0,
         "gaps": collections.Counter(), "gap_docs": collections.defaultdict(set),
         "not_rule": collections.Counter(), "rules": 0}
    for rec in results:
        s["records"][rec["outcome"]] += 1
        for u in rec["units"]:
            s["units"][u["outcome"]] += 1
            s["effects"] += u["n_effects"]
            s["blocked_effects"] += u["n_blocked_effects"]
            s["rules"] += len(u["rules"])
            if u["layers"]:
                s["unit_primary_layer"][_primary(u["layers"])] += 1
                for layer in u["layers"]:
                    s["unit_any_layer"][layer] += 1
                if u["layers"] == ["VOCAB"]:
                    s["vocab_only_units"] += 1
            for b in u["blockers"]:
                key = (b["layer"], b["reason"])
                s["gaps"][key] += 1
                s["gap_docs"][key].add(rec["document_name"])
            for why in u["not_rule"]:
                s["not_rule"][why] += 1
    s["gap_docs"] = {k: len(v) for k, v in s["gap_docs"].items()}
    return s


def partition(results, only=None):
    """단위를 겹치지 않게 가른다. 앞 칸이 이긴다.

      NOT_A_RULE   이 저장소 원칙으로는 규칙이 아니다 (절차 · 상품 설정)
      CONVERTED    전부 옮겼다
      PARTIAL      일부 effect 만 옮겼다
      SOURCE       의미 규칙 스스로 미해결
      SCOPE        판별 범위 밖이 하나라도 있다
      STRUCTURE    DSL 구조가 없는 자리가 하나라도 있다
      CONVERTER    변환기 칸 구조 한계 — 카탈로그 · DSL 에는 있다. 변환기를 고치면 열린다
      VOCAB        어휘만 없다 — 카탈로그를 넓히면 열린다
    """
    part = collections.Counter()
    vocab_sets = collections.Counter()
    struct = collections.Counter()
    fam = collections.defaultdict(collections.Counter)
    for rec in results:
        if only and not only(rec):
            continue
        for u in rec["units"]:
            L = set(u["layers"])
            if u["outcome"] in ("NOT_A_RULE", "CONVERTED", "PARTIAL"):
                key = u["outcome"]
            elif "SOURCE" in L:
                key = "SOURCE"
            elif "SCOPE" in L:
                key = "SCOPE"
            elif "STRUCTURE" in L:
                key = "STRUCTURE"
                for b in u["blockers"]:
                    if b["layer"] == "STRUCTURE":
                        struct[b["reason"]] += 1
            elif "CONVERTER" in L:
                key = "CONVERTER"
            else:
                key = "VOCAB"
                vocab_sets[frozenset(b["reason"] for b in u["blockers"])] += 1
            part[key] += 1
            for b in u["blockers"]:
                fam[key][b["family"] or "-"] += 1
    single = collections.Counter()
    for reasons, n in vocab_sets.items():
        if len(reasons) == 1:
            single[next(iter(reasons))] += n
    return {"partition": part, "vocab_single": single,
            "vocab_multi": sum(n for r, n in vocab_sets.items() if len(r) > 1),
            "structure_reasons": struct, "families": fam}


def slots(results):
    """대응표에 판정이 없는 표현 → 칸 · 등장 수 · 예시 문맥."""
    inv = {}
    for rec in results:
        for u in rec["units"]:
            for b in u["blockers"]:
                if b["layer"] != "UNLABELED":
                    continue
                kind = b["reason"].split(" 칸")[0].replace("대응표 ", "")
                key = (kind, b["surface"])
                x = inv.setdefault(key, {"kind": kind, "surface": b["surface"], "count": 0,
                                         "slots": set(), "where": []})
                x["count"] += 1
                x["slots"].add(b["slot"])
                if len(x["where"]) < 3:
                    x["where"].append(f"{rec['id']} · {rec['document_name']} {rec['section_path']}")
    out = sorted(inv.values(), key=lambda x: (x["kind"], -x["count"], x["surface"]))
    for x in out:
        x["slots"] = sorted(x["slots"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lexicon", default=str(semconv.LEXICON_PATH))
    ap.add_argument("--slots", help="판정 없는 표현 목록을 여기에 쓴다")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    rows = load()
    lex = semconv.Lexicon.load(a.lexicon)
    results = run(rows, lex)
    s = summarize(results)

    meta = {"sources": {k: {"path": str(p), "sha256": next(r["_sha256"] for r in rows
                                                          if r["_split"] == k)}
                        for k, p in SPLITS.items()},
            "lexicon": a.lexicon, "n_records": len(rows)}
    Path(a.out).write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False,
                                      indent=1), "utf-8")
    if a.slots:
        Path(a.slots).write_text(json.dumps(slots(results), ensure_ascii=False, indent=1), "utf-8")

    print(f"레코드 {len(rows)}: {dict(s['records'])}")
    print(f"단위 {sum(s['units'].values())}: {dict(s['units'])}")
    print(f"effect {s['effects']} 중 막힘 {s['blocked_effects']} · 옮긴 규칙 {s['rules']}")
    print(f"막힌 단위의 첫째 층: {dict(s['unit_primary_layer'])}")
    print(f"층이 하나라도 걸린 단위: {dict(s['unit_any_layer'])}")
    print(f"어휘만 막힌 단위: {s['vocab_only_units']}")
    print("막힌 이유 상위:")
    for (layer, why), n in s["gaps"].most_common(25):
        print(f"  {n:4d} ({s['gap_docs'][(layer, why)]:3d}문서) {layer:10s} {why}")
    print("규칙이 아닌 것:", dict(s["not_rule"].most_common(10)))

    for name, only in (("전체", None),
                       ("이 저장소와 같은 상품", lambda r: any(p in r["document_name"]
                                                            for p in OWN_PRODUCTS))):
        p = partition(results, only)
        print(f"\n== 단위 가르기 · {name}: {dict(p['partition'])}")
        print(f"   어휘만 막힌 단위 중 개념 하나만 없는 것 {sum(p['vocab_single'].values())}, 둘 이상 {p['vocab_multi']}")
        for why, n in p["vocab_single"].most_common(15):
            print(f"   {n:3d}  {why}")
        print("   구조 이유:")
        for why, n in p["structure_reasons"].most_common(10):
            print(f"   {n:3d}  {why}")


if __name__ == "__main__":
    main()
