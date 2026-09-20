"""대응표(`data/semconv_lexicon.json`) 합치기와 검사.

    python semconv_lexicon.py merge out_a.json out_b.json …   # 초안들을 대응표에 합친다
    python semconv_lexicon.py check                           # 대응표만 검사한다

판정 하나하나가 형식에 맞는지, 조건식이 카탈로그 이름만 쓰고 실행되는지 본다.
**판정이 옳은지는 보지 않는다** — 그건 사람 검토의 몫이고, 검토 여부를
판정마다 `reviewed` 로 남긴다.
"""

import json
import sys
from pathlib import Path

import catalog
import semconv
import validate

_FORMS = {
    "cond": ({"dsl"}, {"not_rule"}),
    "constraint": ({"requirement", "violation"}, {"not_rule"}),
    "subject": ({"var", "unit"}, {"operand", "unit"}, {"requirement", "when", "violation"},
                {"not_rule"}),
    "member": ({"value"},),
    "target": ({"effect"}, {"not_rule"}),
    "scope": ({"ignore"}, {"and"}),
    "modifier": ({"and_not"}, {"ignore"}),
    "relation": ({"ignore"},),
}
_UNITS = ("won", "months", "days", "count", "age", "enum", "bool", "date")


def _probe(cond, let=None):
    r = {"rule_id": "LEX-01", "status": "OK", "source": {"quote": "x"},
         "condition": cond, "effect": {"type": "RATE_ADD", "value": 0.1, "unit": "%p"}}
    if let:
        r["let"] = let
    return validate.check_catalog(r) + validate.check_executable(r)


def check_entry(kind, key, e):
    """판정 하나 → 오류 목록."""
    if not isinstance(e, dict):
        return [f"{kind}[{key}]: 객체가 아니다"]
    if "gap" in e:
        errs = []
        # CONVERTER: 카탈로그 · DSL 에는 있는데 변환기의 칸 구조가 못 옮긴다 (2026-09-18 2차 검토)
        if e.get("layer", "VOCAB") not in ("VOCAB", "STRUCTURE", "SCOPE", "CONVERTER"):
            errs.append(f"{kind}[{key}]: gap 의 layer 가 아니다: {e.get('layer')}")
        if e.get("family") not in semconv.FAMILIES:
            errs.append(f"{kind}[{key}]: family 가 목록에 없다: {e.get('family')}")
        return errs
    keys = set(e) - {"gap", "layer", "family"}
    if not any(need <= keys for need in _FORMS[kind]):
        return [f"{kind}[{key}]: 형태가 아니다 — 필요한 키 {[sorted(f) for f in _FORMS[kind]]}, 온 키 {sorted(keys)}"]
    errs = []
    let = e.get("let")
    for part in ("dsl", "requirement", "and", "and_not"):
        if part in e:
            errs += [f"{kind}[{key}].{part}: {m}" for m in _probe(e[part], let)]
    if "operand" in e:
        errs += [f"{kind}[{key}].operand: {m}"
                 for m in _probe({">=": [e["operand"], 0]}, let)]
    if "var" in e:
        errs += [f"{kind}[{key}].var: {m}" for m in _probe({"==": [{"var": e["var"]}, 0]})]
    if "unit" in e and kind == "subject" and e["unit"] not in _UNITS:
        errs.append(f"{kind}[{key}]: unit 이 아니다: {e['unit']}")
    if e.get("violation") not in (None, "DISQUALIFY", "LIMIT_AMOUNT"):
        errs.append(f"{kind}[{key}]: violation 이 아니다: {e['violation']}")
    if kind == "target" and "effect" in e:
        eff = {k: e[k] for k in ("target", "unit", "renewable", "applies_to", "value") if k in e}
        eff["type"] = e["effect"]
        need = catalog.EFFECTS.get(e["effect"])
        if need is None:
            errs.append(f"{kind}[{key}]: 카탈로그에 없는 effect: {e['effect']}")
        else:
            r = {"rule_id": "LEX-01", "status": "OK", "source": {"quote": "x"},
                 "condition": {"==": [{"var": "customer.age"}, 0]}, "effect": eff}
            errs += [f"{kind}[{key}]: {m}" for m in validate.check_catalog(r)]
        if "::" not in key:
            errs.append(f"{kind}[{key}]: target 키는 '종류::표현' 이어야 한다")
    return errs


def check(data):
    errs = []
    for kind, table in data.items():
        if kind == "_meta":
            continue
        if kind not in _FORMS:
            errs.append(f"모르는 칸: {kind}")
            continue
        for key, e in table.items():
            errs += check_entry(kind, key, e)
    return errs


def merge(paths, into=semconv.LEXICON_PATH):
    p = Path(into)
    data = json.loads(p.read_text("utf-8")) if p.exists() else {}
    added, conflicts = 0, []
    for path in paths:
        draft = json.loads(Path(path).read_text("utf-8"))
        for kind, table in draft.items():
            for key, e in table.items():
                e = {**e, "by": e.get("by", "claude-draft"), "reviewed": e.get("reviewed", False)}
                cur = data.setdefault(kind, {}).get(key)
                if cur is not None and cur.get("reviewed"):
                    conflicts.append(f"{kind}[{key}]: 검토된 판정이 있어 초안을 버린다")
                    continue
                if cur is not None and {k: v for k, v in cur.items() if k not in ("why", "by", "reviewed")} \
                        != {k: v for k, v in e.items() if k not in ("why", "by", "reviewed")}:
                    conflicts.append(f"{kind}[{key}]: 초안끼리 다르다 — 뒤의 것을 쓴다 ({path})")
                data[kind][key] = e
                added += 1
    data = {k: dict(sorted(v.items())) for k, v in sorted(data.items())}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return added, conflicts


def main():
    cmd, *args = sys.argv[1:] or ["check"]
    if cmd == "merge":
        added, conflicts = merge(args)
        print(f"합침 {added}")
        for c in conflicts:
            print("  ", c)
    data = json.loads(Path(semconv.LEXICON_PATH).read_text("utf-8"))
    errs = check(data)
    print(f"판정 {sum(len(v) for v in data.values())} · 오류 {len(errs)}")
    for e in errs:
        print("  ", e)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
