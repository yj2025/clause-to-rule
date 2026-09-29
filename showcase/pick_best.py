"""쇼케이스 결과에서 상품별 best 조항을 골라 JSON · 마크다운으로 낸다 (2026-09-29).

**정답이 없다.** 새 상품 8개는 사람 검토 정답이 없어 ⑥(실행 결과 일치)을 못 잰다.
그래서 «맞다» 가 아니라 **«걸리는 결함이 없다»** 까지만 기계로 가린다.

  1. 관문 ①~⑤ 통과 · 빈 배열 아님 · 잘림 없음
  2. ⑭ 헛조건 없음 (`vacuous.check_rule`) — 관문 다섯이 통과시키는 실패
  3. ⑮ 뜻이 다른 변수 없음 (`mismatch.find`) — 역시 관문이 못 보는 실패

셋을 다 넘은 것 중에서 **사람이 원문과 대조한 것만** best 로 낸다.
대조 결과는 `showcase/review.json` 에 적는다 — {조문 id: {"verdict": "ok"|"fix"|"drop", "note": …}}.
review 가 없는 조문은 «후보» 로만 나간다.

고객 예시는 조건의 **경계값**으로 만든다. 비교 `var op 값` 마다 값 −1 · 값 · +1
(목록이면 안 · 밖)을 넣고 조합을 실행기에 돌린다. 합성 프로필이다 — 진짜 고객이 아니다.

    python showcase/pick_best.py showcase/results_kb10.json
    python showcase/pick_best.py results/results_v66.json --clauses data/corpus.json   (시험용)
"""

import argparse
import copy
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import mismatch  # noqa: E402
import vacuous  # noqa: E402
import validate  # noqa: E402
from engine import evaluate_rules  # noqa: E402
from resolver import resolve  # noqa: E402

GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
# 보여 줄 가치 순서 — 금리·혜택이 먼저, 정형 행정 조문이 뒤
CAT_ORDER = {"rate": 0, "benefit": 1, "eligibility": 2, "restriction": 3,
             "tax": 4, "admin": 5, "other": 6}
# 고객에게 보이는 effect. 이 밖의 것(`STATE_CHANGE` 등)은 금리·자격을 안 바꿔 보여 줄 것이
# 없다. 그리고 이 목록 안이라도 기계 검사만으로는 반쯤만 맞다 — v58~v61·v66·v67 에서
# «결함 없음 + 이 목록» 49건 중 ⑥ 100% 는 47% (2026-09-29 실측). 그래서 사람 대조가 필요하다.
MEANINGFUL = {"RATE_ADD", "RATE_OVERRIDE", "FEE_WAIVE", "FEE_WAIVE_NO_CARRYOVER",
              "LIMIT_AMOUNT", "DISQUALIFY", "SERVICE_PROVIDE", "RESTRICT",
              "DORMANT_CONTRIBUTION"}
CMP = ("<", "<=", ">", ">=", "==", "!=")


def _meaningful(rules):
    return any(r.get("status") == "OK" and (r.get("effect") or {}).get("type") in MEANINGFUL
               for r in rules)
MAX_CASES = 6


def _prefix(cid):
    return cid.split("-")[0]


def _base_rate(clauses):
    """상품의 기본이율 조문에서 «연 x%» 첫 값을 꺼낸다. 없으면 0."""
    for c in clauses:
        if "기본이율" in c["label"] or "기본금리" in c["label"]:
            m = re.search(r"연\s*([\d.]+)\s*%", c["text"])
            if m:
                return float(m.group(1))
    return 0.0


def check(rec, text):
    """[(종류, 설명)]. 비었으면 기계가 잡는 결함이 없다."""
    f = rec["final"]
    out = [("관문", g) for g in GATES if not f.get(g)]
    if f.get("empty"):
        out.append(("빈 배열", "rule 을 내지 않았다"))
    if rec.get("truncated"):
        out.append(("잘림", "출력이 잘렸다"))
    rules = (rec.get("output") or {}).get("rules") or []
    if rules and all(r.get("status") != "OK" for r in rules):
        out.append(("기권", "옮길 수 없음만 냈다"))
    for r in rules:
        if r.get("status") != "OK":
            continue
        out += [("⑭ " + k, f"{r.get('rule_id')}: {d}") for k, d in vacuous.check_rule(r)]
        for part in ("condition", "guard"):
            for m in mismatch.find(r.get(part)) or []:
                out.append(("⑮ 뜻이 다른 변수", f"{r.get('rule_id')}: {m}"))
    return out


# 기계적으로만 고치는 것 — **뜻을 건드리지 않는 누락**만. 금리 effect 의 `unit` 을 빠뜨린
# 조문이 kb10 에서 19건이었다(2026-09-29). 값은 조문에 적힌 대로이고 단위만 없다.
# 가산·감산은 %p, 덮어쓰기는 절대 금리라 % 다. 고친 뒤 **검증기를 다시 통과해야** 쓴다.
_UNIT = {"RATE_ADD": "%p", "RATE_SUBTRACT": "%p", "RATE_OVERRIDE": "%"}


def patch_units(rules):
    """(고친 rule 목록, [고친 자리 설명]). 고칠 것이 없으면 설명이 빈 목록이다."""
    out, notes = [], []
    for r in rules:
        e = r.get("effect")
        if r.get("status") == "OK" and isinstance(e, dict) \
                and e.get("type") in _UNIT and not e.get("unit"):
            r = copy.deepcopy(r)
            r["effect"]["unit"] = _UNIT[e["type"]]
            notes.append(f"{r.get('rule_id')}: effect.unit 없음 → \"{_UNIT[e['type']]}\" 를 채웠다")
        out.append(r)
    return out, notes


def widen(rec, text):
    """관문에서 떨어진 기록을 단위만 채워 다시 잰다. 다 통과하면 (고친 기록, 설명)."""
    rules = (rec.get("output") or {}).get("rules") or []
    fixed, notes = patch_units(rules)
    if not notes:
        return None
    marks = validate.score_record({"rules": fixed}, text)
    if not all(marks.get(g) for g in GATES):
        return None
    return {**rec, "final": marks, "output": {"rules": fixed}}, notes


# ── 경계값 고객 ─────────────────────────────────────────────────────────

def _leaves(node, out):
    if isinstance(node, dict):
        for op, args in node.items():
            if op in CMP + ("in",) and isinstance(args, list) and len(args) == 2:
                a, b = args
                if isinstance(a, dict) and "var" in a and not isinstance(b, dict):
                    out.append((a["var"], op, b))
                elif isinstance(b, dict) and "var" in b and op == "in" \
                        and isinstance(a, (str, int, float)):
                    out.append((b["var"], "has", a))
            if isinstance(args, list):
                for x in args:
                    _leaves(x, out)
            else:
                _leaves(args, out)
    elif isinstance(node, list):
        for x in node:
            _leaves(x, out)
    return out


def _values(op, lit):
    if op == "in" and isinstance(lit, list) and lit:
        return [lit[0], "(목록 밖의 값)"]
    if op == "has":
        return [[lit], []]
    if isinstance(lit, bool):
        return [lit, not lit]
    if isinstance(lit, (int, float)):
        step = 1 if isinstance(lit, int) and abs(lit) < 1000 else max(1, abs(lit) // 100)
        return sorted({lit - step, lit, lit + step})
    return [lit, "(목록 밖의 값)"]


def _set(ctx, name, v):
    cur = ctx
    parts = name.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = v


def examples(rules, base):
    leaves = []
    for r in rules:
        if r.get("status") == "OK":
            _leaves(r.get("condition"), leaves)
    per_var = {}
    for name, op, lit in leaves:
        vs = per_var.setdefault(name, [])
        for v in _values(op, lit):
            if v not in vs:
                vs.append(v)
    names = list(per_var)[:3]                  # 변수 셋까지만 — 표가 읽혀야 한다
    combos = list(itertools.product(*[per_var[n] for n in names])) if names else [()]
    limit = 16 if len(names) == 1 else MAX_CASES   # 변수 하나면 경계를 다 보인다
    if len(combos) > limit:                    # 고르게 솎는다
        step = len(combos) / limit
        combos = [combos[int(i * step)] for i in range(limit)]
    ok = [r for r in rules if r.get("status") == "OK"]
    out = []
    for combo in combos:
        ctx = {}
        for n, v in zip(names, combo):
            _set(ctx, n, copy.deepcopy(v))
        js = evaluate_rules(ok, ctx)
        res = resolve(js, base_rate=base)
        out.append({
            "고객": {n: v for n, v in zip(names, combo)},
            "판별": {j.rule_id: j.status for j in js},
            # 걸린 금리 rule 이 없으면 기본이율을 찍지 않는다 — 그 값은 이 조문이 낸 것이 아니다
            "최종금리": (f"연 {res.final_rate_min}% ~ {res.final_rate_max}%"
                        if res.applied or res.unknown or res.overridden_rules
                        else "— (이 조문으로 정해지지 않음)"),
            "자격상실": res.disqualified,
            "검토필요": res.needs_review,
            "그밖의효과": [json.dumps(e, ensure_ascii=False) if not isinstance(e, str) else e
                        for e in res.other_effects],
        })
    return out


def _load(path, empty):
    """없거나 빈 파일이면 `empty`. review.json 은 대조 전에는 없다."""
    try:
        return json.load(open(path, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return empty


# ── 내기 ────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--clauses", default=str(HERE / "clauses.json"))
    ap.add_argument("--products", default=str(HERE / "products.json"))
    ap.add_argument("--review", default=str(HERE / "review.json"))
    ap.add_argument("--top", type=int, default=3, help="상품당 best 몇 개")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--widen", action="store_true",
                    help="단위만 빠진 것을 채워 다시 재고, ⑭·⑮ 에만 걸린 것도 후보로 둔다")
    ap.add_argument("--list", action="store_true", help="대조할 후보만 찍고 끝낸다")
    a = ap.parse_args(argv)

    clauses = {c["id"]: c for c in json.load(open(a.clauses, encoding="utf-8"))}
    recs = [r for r in json.load(open(a.results, encoding="utf-8")) if r["run"] == 0]
    prods = _load(a.products, [])
    names = {p["prefix"]: p for p in prods}
    review = _load(a.review, {})

    by_prod = {}
    for r in recs:
        c = clauses.get(r["clause_id"])
        if c is None:
            continue
        flags, patches = check(r, c["text"]), []
        if a.widen and any(k == "관문" for k, _ in flags):
            w = widen(r, c["text"])
            if w:
                r, patches = w
                flags = check(r, c["text"])
        rules = (r.get("output") or {}).get("rules") or []
        by_prod.setdefault(_prefix(r["clause_id"]), []).append(
            {"clause": c, "rules": rules, "flags": flags, "patches": patches,
             "review": review.get(r["clause_id"])})

    report = []
    for pre, items in by_prod.items():
        pc = [x["clause"] for x in items]
        base = _base_rate(pc)
        soft = ("⑭", "⑮")          # --widen 일 때 후보로 두되 표시를 달고 나간다
        clean = [x for x in items if not x["flags"] or
                 (a.widen and all(k.startswith(soft) for k, _ in x["flags"]))]
        clean.sort(key=lambda x: (
            {"ok": 0, None: 1, "fix": 2}.get((x["review"] or {}).get("verdict"), 3),
            not _meaningful(x["rules"]),
            CAT_ORDER.get(x["clause"]["category"], 9),
            -sum(1 for rr in x["rules"] if rr.get("status") == "OK" and rr.get("condition")),
        ))
        clean = [x for x in clean if (x["review"] or {}).get("verdict") != "drop"]
        if a.list:
            for x in clean:
                if x["review"] is None:
                    print(x["clause"]["id"], "|", x["clause"]["label"][:30], "|",
                          sorted({k for k, _ in x["flags"]}), "| 고침", len(x["patches"]))
            continue
        best = [x for x in clean if x["review"]][:a.top]     # 대조한 것만 best 로 낸다
        for x in best:
            x["examples"] = examples(x["rules"], base)
        info = names.get(pre, {"prefix": pre, "product": pre, "kind": ""})
        report.append({**info, "base_rate": base, "n": len(items), "n_clean": len(clean),
                       "best": best,
                       "all": [{"id": x["clause"]["id"], "label": x["clause"]["label"],
                                "flags": x["flags"]} for x in items]})

    if a.list:
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "kb10_best.json").write_text(json.dumps(
        [{**p, "best": [{"clause_id": x["clause"]["id"], "label": x["clause"]["label"],
                         "category": x["clause"]["category"], "source_text": x["clause"]["text"],
                         "rules": x["rules"], "review": x["review"],
                         "patched": x["patches"],
                         "flags": [f"{k}: {d}" for k, d in x["flags"]],
                         "examples": x["examples"]} for x in p["best"]]}
         for p in report], ensure_ascii=False, indent=1), "utf-8")
    (out / "kb10_best.md").write_text(render(report, a.results), "utf-8")
    for p in report:
        print(f"{p['prefix']:6} {p['product']:24} 조문 {p['n']:3} · 결함 없음 {p['n_clean']:3} · best {len(p['best'])}")
    print(f"→ {out}/kb10_best.json · kb10_best.md")


def _fence(obj):
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=1) + "\n```"


def render(report, src):
    L = ["# KB 상품 10종 — 조항별 best 결과물", "",
         f"> 원자료 `{Path(src).name}` · 모델 Qwen3-8B · 온도 0.1 · 1회차.",
         "> **정답이 없는 상품이다.** 여기 «best» 는 «기계가 잡는 결함(관문 ①~⑤ · ⑭ 헛조건 · "
         "⑮ 뜻이 다른 변수)이 없고, 사람이 원문과 대조한 것» 이다. «정확도» 가 아니다.",
         "> 고객 예시는 조건의 경계값으로 만든 **합성 고객**이다.", "",
         "## 한눈에", "", "| 분류 | 상품 | 조문 | 대조 후 남은 후보 | best |", "|---|---|---:|---:|---:|"]
    for p in report:
        L.append(f"| {p.get('kind','')} | {p['product']} | {p['n']} | {p['n_clean']} | {len(p['best'])} |")
    notes = HERE / "notes.md"
    if notes.exists():
        L += ["", notes.read_text("utf-8").rstrip()]
    for p in report:
        L += ["", "---", "", f"## {p['product']}  ({p.get('kind','')})", "",
              f"기본이율 연 {p['base_rate']:.2f}% · 조문 {p['n']}개 중 결함 없음 {p['n_clean']}개"]
        if p.get("url"):
            L.append(f" · [원문]({p['url']})")
        for i, x in enumerate(p["best"], 1):
            c, rv = x["clause"], x["review"] or {}
            mark = {"ok": "✅ 대조 완료", "fix": "⚠ 대조 — 고칠 점 있음"}.get(rv.get("verdict"), "후보 (대조 전)")
            L += ["", f"### {i}. {c['label']}  `{c['id']}` — {mark}", ""]
            if rv.get("note"):
                L += [f"> {rv['note']}", ""]
            if x.get("patches"):
                L += ["**고친 자리** (모델 출력에서 뜻과 무관한 누락만 채웠다)", ""]
                L += [f"* {n}" for n in x["patches"]] + [""]
            if x.get("flags"):
                L += ["**기계 검사 표시** — " + " · ".join(sorted({k for k, _ in x["flags"]})), ""]
            L += ["**원문**", "", "```", c["text"], "```", "", "**조건식 (모델 출력)**", "",
                  _fence([r for r in x["rules"]]), ""]
            ex = x.get("examples") or []
            if ex and ex[0]["고객"]:
                keys = list(ex[0]["고객"])
                L += ["**경계값 고객으로 돌리면**", "",
                      "| " + " | ".join(f"`{k}`" for k in keys) + " | 최종 금리 | 자격 상실 | 그 밖의 효과 |",
                      "|" + "---|" * (len(keys) + 3)]
                for e in ex:
                    vals = [json.dumps(e["고객"][k], ensure_ascii=False) for k in keys]
                    other = " · ".join(e["그밖의효과"])[:120] or "—"
                    L.append("| " + " | ".join(vals) + f" | {e['최종금리']} | {e['자격상실']} | {other} |")
        L += ["", "<details><summary>전체 조문 점검표</summary>", "",
              "| 조문 | 라벨 | 걸린 것 |", "|---|---|---|"]
        for x in p["all"]:
            fl = " · ".join(sorted({k for k, _ in x["flags"]})) or "없음"
            L.append(f"| `{x['id']}` | {x['label'][:30]} | {fl} |")
        L += ["", "</details>"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
