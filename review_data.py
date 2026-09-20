"""검토 도구(아티팩트)에 실을 데이터를 만든다.

    python review_data.py OUT_DIR     # OUT_DIR/gold-data.js · lex-data.js

두 가지를 사람이 검토한다.

  정답 조문   `data/gold/` 46조문. `reviewed: true` 인 11조문은 "검토 완료" 로 싣는다
  대응표      `data/semconv_lexicon.json` 판정 776개.
              규칙을 만들거나 없애는 판정(옮김 · 규칙 아님 · 무시)은 **하나씩** 싣고,
              "어휘 없음"(gap)은 틀려도 잘못된 규칙을 만들지 않으므로 **이유별로 묶어** 싣는다.

판정마다 원문 근거를 붙인다 — 그 표현이 나온 팀원 gold 단위의 evidence, 블라인드
43조문에서 나온 표현이면 e3 출력 단위의 evidence. 검토 결과는 아티팩트 DB 에 쌓이고
`review_import.py` 가 저장소로 옮긴다. 아티팩트 DB 문서 id 는 한글을 못 쓰므로
판정 키의 해시(`entry_id`)를 쓴다.
"""

import hashlib
import json
import sys
from pathlib import Path

import catalog
import semconv
import semconv_report as R
import semselect

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "data" / "gold"

_HARM = {"DISQUALIFY", "RESTRICT", "PENALTY_RATE", "RATE_SUBTRACT", "DORMANT_CONTRIBUTION",
         "FEE_WAIVE_NO_CARRYOVER"}


def entry_id(kind, key):
    return hashlib.sha1(f"{kind}\x1f{key}".encode()).hexdigest()[:16]


def group_id(layer, reason):
    return "g" + hashlib.sha1(f"{layer}\x1f{reason}".encode()).hexdigest()[:15]


# ── 정답 조문 ───────────────────────────────────────────────────────────
def gold_data():
    clauses = {c["id"]: c for f in ("clauses.json", "clauses_kbone.json")
               for c in json.loads((ROOT / "data" / f).read_text("utf-8"))}
    out = []
    for p in sorted(GOLD.glob("K*.json")):
        g = json.loads(p.read_text("utf-8"))
        c = clauses.get(g["clause_id"], {})
        rules = []
        for r in g["rules"]:
            eff = r.get("effect")
            rules.append({
                "id": r.get("rule_id"), "status": r.get("status"), "label": r.get("label"),
                "quote": (r.get("source") or {}).get("quote"),
                "condition": r.get("condition"), "effect": eff, "let": r.get("let"),
                "dir": (None if not eff else "불이익" if eff.get("type") in _HARM else "혜택")})
        pa = g.get("principles_applied") or {}
        out.append({
            "id": g["clause_id"], "label": g.get("label") or c.get("label"),
            "page": c.get("page"), "text": c.get("text", ""),
            "reviewed": bool(g.get("reviewed")),
            "verdict": ("빈 배열" if not rules else
                        "UNSUPPORTED 뿐" if all(r["status"] == "UNSUPPORTED" for r in rules) else
                        "일부 UNSUPPORTED" if any(r["status"] == "UNSUPPORTED" for r in rules) else
                        "정상 rule"),
            "rules": rules, "note": g.get("note", ""),
            "decision": g.get("provisional_decision"),
            "principles": pa.get("basis") or [],
        })
    return out


# ── 대응표 ──────────────────────────────────────────────────────────────
def _units_with_keys(sem, lex):
    """semantic_rule 의 단위마다 그 단위가 찾은 (칸, 키)."""
    out = []
    for u in sem.get("rule_units") or []:
        rec = semselect._Recording(lex)
        try:
            semconv.convert_unit(u, rec, "K")
        except (AttributeError, TypeError, KeyError, ValueError):
            continue
        ev = [" ".join(str(e.get("text", "")).split())[:320]
              for e in (u.get("evidence") or []) if isinstance(e, dict)][:3]
        out.append((rec.seen, ev))
    return out


def contexts(lex, per_key=2):
    """(칸, 키) → 원문 근거 몇 개와 등장 수."""
    ctx, count = {}, {}

    def add(keys, where, ev):
        for k in keys:
            count[k] = count.get(k, 0) + 1
            lst = ctx.setdefault(k, [])
            if len(lst) < per_key and ev:
                lst.append({"where": where, "evidence": ev})

    for r in R.load():
        for keys, ev in _units_with_keys(r["semantic_rule"], lex):
            add(keys, f"팀원 gold · {r['document_name']} {r['section_path']}", ev)

    e3 = ROOT / "results" / "blind43_e3.jsonl"
    if e3.exists():
        for line in e3.read_text("utf-8").splitlines()[1:]:
            r = json.loads(line)
            try:
                sem = json.loads(r["raw_output"])
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(sem, dict):
                for keys, ev in _units_with_keys(sem, lex):
                    add(keys, f"블라인드 e3 출력 · {r['sample_id']}", ev)
    return ctx, count


def _kind_of(e):
    for k in ("gap", "not_rule", "ignore"):
        if k in e:
            return k
    return "mapped"


def lex_data():
    raw = json.loads(semconv.LEXICON_PATH.read_text("utf-8"))
    lex = semconv.Lexicon.load()
    ctx, count = contexts(lex)
    items, groups = [], {}
    for kind, table in raw.items():
        for key, e in table.items():
            k = (kind, semconv._norm(key))
            judged = {x: v for x, v in e.items() if x not in ("why", "by", "reviewed", "source")}
            row = {"id": entry_id(kind, key), "kind": kind, "key": key, "type": _kind_of(e),
                   "entry": judged, "why": e.get("why", ""), "source": e.get("source"),
                   "count": count.get(k, 0), "ctx": ctx.get(k, [])}
            if row["type"] == "gap":
                gid = group_id(e.get("layer", "VOCAB"), e["gap"])
                g = groups.setdefault(gid, {"id": gid, "layer": e.get("layer", "VOCAB"),
                                            "reason": e["gap"], "family": e.get("family"),
                                            "members": []})
                g["members"].append(row)
            else:
                items.append(row)
    items.sort(key=lambda x: ({"mapped": 0, "not_rule": 1, "ignore": 2}[x["type"]], -x["count"]))
    gl = sorted(groups.values(), key=lambda g: -sum(m["count"] or 1 for m in g["members"]))
    for g in gl:
        g["members"].sort(key=lambda m: -m["count"])
    return {"items": items, "groups": gl,
            "catalog": {"vars": {k: v["desc"] for k, v in catalog.VARIABLES.items()},
                        "events": catalog.EVENTS, "fees": catalog.FEES,
                        "services": catalog.SERVICES, "restrictions": catalog.RESTRICTIONS}}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    g, lx = gold_data(), lex_data()
    (out / "gold-data.js").write_text(
        "window.GOLD_DATA = " + json.dumps(g, ensure_ascii=False) + ";\n", "utf-8")
    (out / "lex-data.js").write_text(
        "window.LEX_DATA = " + json.dumps(lx, ensure_ascii=False) + ";\n", "utf-8")
    todo = sum(1 for c in g if not c["reviewed"])
    print(f"정답 {len(g)}조문 (검토 전 {todo}) · 대응표 개별 {len(lx['items'])} · "
          f"어휘 없음 묶음 {len(lx['groups'])} ({sum(len(x['members']) for x in lx['groups'])}개)")
    print(f"근거 없는 개별 판정 {sum(1 for x in lx['items'] if not x['ctx'])}")


if __name__ == "__main__":
    main()
