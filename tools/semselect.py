"""대응표에 글자 그대로 없는 표현 → 이미 판정된 같은 표현을 골라 판정을 재사용한다.

    python tools/semselect.py          # 팀원 Dev50 모델 출력으로 잰다 → results/semselect_dev50.json

`semconv.Lexicon` 은 원문 표현을 **공백만 접어 글자 그대로** 찾는다. 대응표는 팀원
**gold** 의 표현으로 만들었는데, 모델은 같은 문장을 조금 다르게 잘라 온다 —
`단, ` 을 붙이거나, 따옴표를 바꾸거나, 앞뒤를 더 잡는다. 그러면 뜻이 같아도
`UNLABELED` 로 막힌다 (epoch3 Dev50 에서 171 곳).

이 모듈은 **판정을 새로 짓지 않는다.** 대응표에 이미 있는 표현 중 같은 것으로 볼 수
있는 표현을 골라 그 판정을 그대로 쓴다. 그래서 나오는 조건식은 전부
`tools/semconv_lexicon.py check` 를 이미 통과한 것이다. 고르는 규칙은 결정론이다.

  canon    정규화한 글이 같다 — NFKC · 앞머리 표지(단, ※ ▪ - ① 1.) · 따옴표 · 공백 · 끝 문장부호
  contain  한쪽이 다른 쪽을 품고, 짧은 쪽이 긴 쪽의 CONTAIN 이상
  fuzzy    글자 2-gram Dice 가 FUZZY 이상

어느 단계든 **수가 다르면 잇지 않는다** ("20만원 이상" ↔ "30만원 이상").
target 칸은 effect 종류(`PROHIBIT::` …)가 같아야 한다 — 종류가 다르면 뜻이 다르다.
가장 높은 단계의 후보들이 **서로 다른 판정**을 가리키면 고르지 않는다 (AMBIGUOUS).

**기본은 canon 만 쓴다.** contain · fuzzy 는 한정어 하나를 못 가린다 — Dev50 에서
"실명의 개인 및 개인사업자" → "실명의 개인사업자", "압류, 가압류등" → "압류, 가압류,
질권설정 등", "중도해지일 전일까지" → "해지일 전일까지" 로 이었다. 틀린 판정은
채점을 더럽히므로 막힌 채로 두는 편이 낫다. 비교용으로 `LOOSE` 를 남긴다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import collections
import csv
import json
import re
import unicodedata
from pathlib import Path

import semconv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "semselect_dev50.json"

CONTAIN = 0.6
FUZZY = 0.8

# 판정의 뜻이 아닌 칸 — 같은 판정인지 볼 때 뺀다
_META = {"why", "by", "reviewed", "source", "claude_review", "human_review", "gold_informed"}

_LEAD = re.compile(r"^(?:단\s*,|※|▪|∙|·|•|-|➢|☞|[①-⑳]|\(\d+\)|\d+\s*[.)]|\[\d+\])\s*")
_QUOTES = str.maketrans({c: "" for c in "‘’“”\"'「」『』《》<>"})
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _strip_lead(s):
    prev = None
    while prev != s:
        prev, s = s, _LEAD.sub("", s.strip())
    return s


def _body(s):
    """앞머리 표지를 뗀 글. ① 은 NFKC 에서 1 이 되므로 정규화 앞뒤로 두 번 뗀다."""
    s = _strip_lead(str(s or "").translate(_QUOTES))
    return _strip_lead(unicodedata.normalize("NFKC", s).translate(_QUOTES))


def canon(s):
    s = re.sub(r"[\s.。,;:]+$", "", _body(s))
    return re.sub(r"\s+", "", s)


def numbers(s):
    return sorted(n.replace(",", "") for n in _NUM.findall(_body(s)))


def _bigrams(s):
    return collections.Counter(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else collections.Counter([s])


def dice(a, b):
    ba, bb = _bigrams(a), _bigrams(b)
    tot = sum(ba.values()) + sum(bb.values())
    return 2 * sum((ba & bb).values()) / tot if tot else 1.0


def signature(entry):
    return json.dumps({k: v for k, v in entry.items() if k not in _META},
                      ensure_ascii=False, sort_keys=True)


def _split(kind, key):
    if kind == "target" and "::" in key:
        t, s = key.split("::", 1)
        return t, s
    return None, key


STRICT = ("canon",)
LOOSE = ("canon", "contain", "fuzzy")


def match(kind, surface, keys, tiers=LOOSE):
    """(단계, [후보 키]) — `tiers` 안에서 가장 높은 단계의 후보만. 없으면 (None, [])."""
    t, s = _split(kind, semconv._norm(surface))
    cs, ns = canon(s), numbers(s)
    found = {"canon": [], "contain": [], "fuzzy": []}
    for key in keys:
        kt, ks = _split(kind, key)
        if kt != t or numbers(ks) != ns:
            continue
        ck = canon(ks)
        if not ck or not cs:
            continue
        if ck == cs:
            found["canon"].append(key)
        elif (ck in cs or cs in ck) and min(len(ck), len(cs)) / max(len(ck), len(cs)) >= CONTAIN:
            found["contain"].append(key)
        elif dice(ck, cs) >= FUZZY:
            found["fuzzy"].append(key)
    for name in ("canon", "contain", "fuzzy"):
        if name in tiers and found[name]:
            return name, found[name]
    return None, []


class SelectingLexicon(semconv.Lexicon):
    """글자 그대로 없으면 같은 표현을 골라 그 판정을 돌려준다. 고른 기록을 `log` 에 남긴다.

    `hide` 에 든 (칸, 키) 는 없는 것으로 친다 — 처음 보는 조문을 흉내 낼 때 쓴다.
    """

    def __init__(self, base, hide=(), tiers=STRICT):
        self.table = base.table
        self.hide = set(hide)
        self.tiers = tuple(tiers)
        self.log = []

    def _visible(self, kind):
        return [k for k in self.table[kind] if (kind, k) not in self.hide]

    def get(self, kind, surface):
        key = semconv._norm(surface)
        if key in self.table[kind] and (kind, key) not in self.hide:
            self.log.append({"kind": kind, "surface": key, "tier": "exact", "chosen": key})
            return self.table[kind][key]
        if not self.tiers:
            self.log.append({"kind": kind, "surface": key, "tier": "none", "chosen": None})
            return None
        tier, cands = match(kind, key, self._visible(kind), self.tiers)
        sigs = {signature(self.table[kind][c]) for c in cands}
        if tier is None:
            rec = {"tier": "none", "chosen": None}
        elif len(sigs) > 1:
            rec = {"tier": "ambiguous", "chosen": None, "candidates": cands[:5]}
        else:
            rec = {"tier": tier, "chosen": cands[0], "n_candidates": len(cands)}
        self.log.append({"kind": kind, "surface": key, **rec})
        return self.table[kind][rec["chosen"]] if rec["chosen"] else None


# ── Dev50 로 재기 ──────────────────────────────────────────────────────
class _Recording(semconv.Lexicon):
    """gold 를 옮기며 어떤 (칸, 키) 를 찾았는지 적는다."""

    def __init__(self, base):
        self.table = base.table
        self.seen = set()

    def get(self, kind, surface):
        key = semconv._norm(surface)
        if key in self.table[kind]:
            self.seen.add((kind, key))
        return self.table[kind].get(key)


def keys_used(sem, base):
    rec = _Recording(base)
    semconv.convert_record(sem, rec, "K")
    return rec.seen


def _rules(res):
    return sorted(json.dumps({"condition": r.get("condition"), "effect": r.get("effect")},
                             ensure_ascii=False, sort_keys=True)
                  for u in res["units"] for r in u["rules"])


def _layers(res):
    c = collections.Counter(b["layer"] for b in res["blockers"])
    for u in res["units"]:
        c.update(b["layer"] for b in u["blockers"])
    return c


def safe_convert(sem, lex):
    """형식이 깨진 모델 출력에서 변환기가 죽으면 막힌 것으로 센다."""
    if not isinstance(sem, dict):
        return None, "JSON 객체가 아니다"
    try:
        return semconv.convert_record(sem, lex, "P"), None
    except (AttributeError, TypeError, KeyError, ValueError) as e:
        return None, f"변환기 예외 {type(e).__name__}: {e}"


def evaluate(pred_rows, gold_rows, base, all_gold):
    """pred_rows: {order: raw_output}, gold_rows: {order: semantic_rule}, all_gold: 315건 전체."""
    use = {i: keys_used(r["semantic_rule"], base) for i, r in enumerate(all_gold)}
    count = collections.Counter(k for s in use.values() for k in s)
    idx = {r["sample_order"]: i for i, r in enumerate(all_gold) if "sample_order" in r}

    per, tiers, verdict = [], collections.Counter(), collections.Counter()
    for order, raw in sorted(pred_rows.items()):
        gold = gold_rows[order]
        own = use[idx[order]]
        hide = {k for k in own if count[k] == 1}          # 이 문항에만 나오는 표현
        g = semconv.convert_record(gold, base, "G")
        try:
            sem = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            per.append({"order": order, "error": "JSON 파싱 실패"})
            continue
        row = {"order": order, "gold_rules": len(_rules(g))}
        for mode, lex in (("literal", base),
                          ("literal_hidden", SelectingLexicon(base, hide, tiers=())),
                          ("select_hidden", SelectingLexicon(base, hide)),
                          ("loose_hidden", SelectingLexicon(base, hide, tiers=LOOSE))):
            res, err = safe_convert(sem, lex)
            if err:
                row["error"] = err
                break
            pr, gr = _rules(res), _rules(g)
            row[mode] = {"rules": len(pr), "rules_equal_gold": len(set(pr) & set(gr)),
                         "layers": dict(_layers(res))}
            if mode in ("select_hidden", "loose_hidden"):
                for x in lex.log:
                    tiers[(mode, x["tier"])] += 1
                    if x["tier"] in ("canon", "contain", "fuzzy"):
                        # 옳게 골랐나 — 같은 문항 gold 에서 이 표현에 대응하는 키의 판정과 같은가
                        mine = [k for (kd, k) in own if kd == x["kind"]]
                        otier, ocands = match(x["kind"], x["surface"], mine)
                        if not ocands:
                            verdict[(mode, x["tier"], "gold_has_no_counterpart")] += 1
                        else:
                            want = {signature(base.table[x["kind"]][c]) for c in ocands}
                            got = signature(base.table[x["kind"]][x["chosen"]])
                            verdict[(mode, x["tier"], "same" if got in want else "different")] += 1
                row[f"log_{mode}"] = lex.log
        per.append(row)
    return per, tiers, verdict


def main():
    import ckpt_paired as C
    import semconv_report as R

    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["e2", "e3"])
    args = ap.parse_args()

    base = semconv.Lexicon.load()
    all_gold = R.load()
    gold_rows = {r["sample_order"]: r["semantic_rule"] for r in all_gold if r["_split"] == "dev"}
    out = {"thresholds": {"contain": CONTAIN, "fuzzy": FUZZY}, "models": {}}
    for tag in args.models:
        rows = csv.DictReader(C.MODELS[tag].read_text("utf-8-sig").splitlines())
        pred = {int(r["sample_order"]): r["raw_output"] for r in rows}
        per, tiers, verdict = evaluate(pred, gold_rows, base, all_gold)
        tot = collections.defaultdict(collections.Counter)
        for row in per:
            for mode in ("literal", "literal_hidden", "select_hidden", "loose_hidden"):
                if mode in row:
                    tot[mode]["rules"] += row[mode]["rules"]
                    tot[mode]["rules_equal_gold"] += row[mode]["rules_equal_gold"]
                    tot[mode].update({f"blk_{k}": v for k, v in row[mode]["layers"].items()})
        gold_rules = sum(r.get("gold_rules", 0) for r in per)
        errors = collections.Counter(r["error"].split(":")[0] for r in per if "error" in r)
        out["models"][tag] = {"gold_rules": gold_rules, "errors": dict(errors),
                              "totals": {k: dict(v) for k, v in tot.items()},
                              "select_tiers": {f"{a}/{b}": v for (a, b), v in tiers.items()},
                              "select_correct": {"/".join(k): v for k, v in verdict.items()},
                              "records": per}
        print(f"\n## {tag}  (gold 로 옮긴 규칙 {gold_rules} · 변환 못 한 문항 {dict(errors)})")
        for mode, name in (("literal", "글자 그대로 (지금)"),
                           ("literal_hidden", "글자 그대로 · 이 문항 표현 숨김"),
                           ("select_hidden", "고르기(canon) · 숨김"),
                           ("loose_hidden", "고르기(느슨) · 숨김")):
            t = tot[mode]
            print(f"  {name:28} 규칙 {t['rules']:3} · gold 와 같은 규칙 {t['rules_equal_gold']:3} · "
                  f"UNLABELED {t['blk_UNLABELED']:3} · VOCAB {t['blk_VOCAB']:3} · "
                  f"STRUCTURE {t['blk_STRUCTURE']:3} · SCOPE {t['blk_SCOPE']:3}")
        print(f"  찾기 단계: { {f'{a}/{b}': v for (a, b), v in sorted(tiers.items())} }")
        print(f"  고른 것의 판정 (같은 문항 gold 대응 키와 비교): "
              f"{ {'/'.join(k): v for k, v in sorted(verdict.items())} }")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
