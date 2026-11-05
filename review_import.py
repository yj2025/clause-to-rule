"""검토 도구(아티팩트 DB)에 쌓인 사람 판정을 저장소로 옮긴다.

    python review_import.py DUMP_DIR            # 무엇이 바뀔지만 보여 준다
    python review_import.py DUMP_DIR --apply    # 정답 파일 · 대응표에 쓴다

DUMP_DIR 은 아티팩트 DB 세 컬렉션을 문서 하나당 JSON 파일로 내려받은 곳이다
(`DUMP_DIR/reviews/*.json` · `lex/*.json` · `lexgroups/*.json`).

옮기는 규칙은 이렇다.

  정답 조문   승인 → `reviewed: true`. 수정 · 반려 → `reviewed` 는 그대로 두고
              `human_review` 에 판정 · 의견 · 틀렸다고 표시한 rule 을 남긴다 (고칠 일)
  대응표      맞음 → `reviewed: true`. 틀림 · 모르겠음 → `human_review` 만 남긴다
  어휘 없음   맞음 → 묶음 전부 `reviewed: true`. 일부 틀림 → 표시 안 한 것만 `reviewed: true`,
              표시한 것은 `human_review`. 틀림 → 전부 `human_review`

**판정한 뒤 대응표가 바뀌었으면 옮기지 않는다.** 검토 도구는 판정할 때 본 판정 내용을
같이 저장한다. 지금 대응표와 다르면 "다시 봐야 함" 으로 따로 센다.
"""

import argparse
import json
from pathlib import Path

import review_data
import semconv

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "data" / "gold"

_META = ("why", "by", "reviewed", "source", "human_review")


def _docs(dump, coll):
    d = Path(dump) / coll
    out = {}
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        raw = json.loads(p.read_text("utf-8"))
        out[p.stem] = raw.get("data", raw)
    return out


def _stamp(r):
    return {"verdict": r.get("verdict"), "comment": r.get("comment", ""),
            "by": r.get("by", ""), "at": r.get("at", "")}


def plan_gold(reviews):
    changes = []
    for p in sorted(GOLD.glob("K*.json")):
        g = json.loads(p.read_text("utf-8"))
        r = reviews.get(g["clause_id"])
        if not r or not r.get("verdict"):
            continue
        hr = {**_stamp(r), "wrong_rules": sorted(k for k, v in (r.get("flags") or {}).items() if v)}
        changes.append((p, g, r["verdict"] == "승인", hr))
    return changes


def plan_lex(lexrev, grouprev, lex):
    by_id, groups = {}, {}
    for kind, table in lex.items():
        for key, e in table.items():
            by_id[review_data.entry_id(kind, key)] = (kind, key)
            if "gap" in e:
                gid = review_data.group_id(e.get("layer", "VOCAB"), e["gap"])
                groups.setdefault(gid, []).append((kind, key))

    ok, note, stale, unknown = [], [], [], []
    for eid, r in lexrev.items():
        if not r.get("verdict"):
            continue
        if eid not in by_id:
            unknown.append(eid)
            continue
        kind, key = by_id[eid]
        now = {k: v for k, v in lex[kind][key].items() if k not in _META}
        if r.get("entry") and json.loads(r["entry"]) != now:
            stale.append((kind, key))
            continue
        (ok if r["verdict"] == "맞음" else note).append((kind, key, _stamp(r)))

    for gid, r in grouprev.items():
        v = r.get("verdict")
        if not v:
            continue
        if gid not in groups:
            unknown.append(gid)
            continue
        flagged = {k for k, x in (r.get("flags") or {}).items() if x}
        for kind, key in groups[gid]:
            eid = review_data.entry_id(kind, key)
            if v == "맞음" or (v == "일부 틀림" and eid not in flagged):
                ok.append((kind, key, _stamp(r)))
            else:
                note.append((kind, key, {**_stamp(r), "flagged": eid in flagged}))
    return ok, note, stale, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    lex = json.loads(semconv.LEXICON_PATH.read_text("utf-8"))
    gold = plan_gold(_docs(a.dump, "reviews"))
    ok, note, stale, unknown = plan_lex(_docs(a.dump, "lex"), _docs(a.dump, "lexgroups"), lex)

    print(f"정답: 승인 {sum(1 for _, _, x, _ in gold if x)} · 고칠 일 {sum(1 for _, _, x, _ in gold if not x)}")
    for _, g, approved, hr in gold:
        if not approved:
            print(f"  {g['clause_id']} {hr['verdict']} {hr['wrong_rules']} {hr['comment'][:80]}")
    print(f"대응표: 맞음 {len(ok)} · 고칠 일 {len(note)} · 판정 뒤 대응표가 바뀜 {len(stale)} · 모르는 id {len(unknown)}")
    for kind, key, hr in note[:40]:
        print(f"  [{kind}] {key[:50]} → {hr['verdict']} {hr['comment'][:60]}")

    if not a.apply:
        print("\n--apply 를 붙이면 쓴다.")
        return
    for p, g, approved, hr in gold:
        if approved:
            g["reviewed"] = True
            # 검토 완료 조문은 `review` 에 검토자를 남긴다 — tests/test_goldaudit.py 가 본다 (2026-11-05)
            g["review"] = {"by": hr["by"], "at": hr["at"][:10], "verdict": "승인", "note": hr["comment"]}
        g["human_review"] = hr
        p.write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n", "utf-8")
    for kind, key, hr in ok:
        lex[kind][key]["reviewed"] = True
        lex[kind][key]["human_review"] = hr
    for kind, key, hr in note:
        lex[kind][key]["human_review"] = hr
    semconv.LEXICON_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print("썼다.")


if __name__ == "__main__":
    main()
