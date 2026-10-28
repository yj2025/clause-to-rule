"""얇은 스키마 검사 — 지어낸 이름은 막고 정상 출력은 받는가 (2026-10-26 시험을 10-27 재현용 스크립트로 옮김). GPU 없음.

    PYTHONPATH=/workspace/personal_workplace_CHO/pylib python lora/probe_thin_schema.py | tee lora/logs/probe_thin_schema.log

1) 수락: 관문 다섯을 다 넘고 rule 이 있는 출력이 문법을 통과하나 — v127a · v127b · Gemma 증류 · 정답 초안(개수만 센다).
   원래 `schema.SCHEMA` 도 같이 잰다 (비교용).
2) 거부: v127a/b 의 수락된 출력에서 이름 하나를 카탈로그 밖 이름으로 바꾸면 거부하나 — 바꾼 값은 test 에서 실제로 나온 환각.
3) 거부된 정상 출력이 키 순서만 맞추면 수락되나.
출력은 개수뿐이다 — 정답 내용은 찍지 않는다.
"""

import copy
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lora"))
import schema  # noqa: E402
import thin_schema  # noqa: E402
import xgrammar as xgr  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
RULE_ORDER = ["rule_id", "status", "label", "source", "let", "guard", "condition", "effect"]
EFFECT_ORDER = ["type", "target", "value", "unit", "renewable", "applies_to"]
MUTATIONS = {   # test 에서 실제로 나온 환각 이름 (HANDOFF §6.3)
    "var": ("var", "customer.is_ssg_member", lambda d: "var" in d),
    "effect.type": ("type", "BOGUS_EFFECT", lambda d: "type" in d and "rule_id" not in d and "event" not in d),
    "target": ("target", "BRANCH", lambda d: "target" in d),
    "event": ("event", "ACTIVITY_ACCOUNT", lambda d: "event" in d),
}


def load_sources():
    src = {}
    for p in ["showcase/results_kb10v127a.json", "showcase/results_kb10v127b.json", "lora/data/distill_gemma31.json"]:
        src[Path(p).stem] = [r["output"] for r in json.load(open(ROOT / p))
                             if all((r.get("final") or {}).get(k) for k in GATES) and (r.get("output") or {}).get("rules")]
    gold = [json.load(open(p)) for p in sorted(glob.glob(str(ROOT / "showcase/gold_draft/*.json")))]
    src["gold_draft"] = [{"rules": g["rules"]} for g in gold if g.get("rules")]
    return src


def canon(o):
    rules = []
    for r in o["rules"]:
        r = {k: r[k] for k in sorted(r, key=lambda k: RULE_ORDER.index(k) if k in RULE_ORDER else 99)}
        if isinstance(r.get("effect"), dict):
            e = r["effect"]
            r["effect"] = {k: e[k] for k in sorted(e, key=lambda k: EFFECT_ORDER.index(k) if k in EFFECT_ORDER else 99)}
        rules.append(r)
    return {**o, "rules": rules}


def walk(o, f):
    if isinstance(o, dict):
        f(o)
        for v in list(o.values()):
            walk(v, f)
    elif isinstance(o, list):
        for v in o:
            walk(v, f)


def main():
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
    info = xgr.TokenizerInfo.from_huggingface(tok)
    comp = xgr.GrammarCompiler(info)
    grammars = {name: comp.compile_json_schema(json.dumps(s), strict_mode=False, any_whitespace=True)
                for name, s in (("원래 SCHEMA", schema.SCHEMA), ("얇은 THIN", thin_schema.THIN))}

    def accepts(g, obj):
        m = xgr.GrammarMatcher(g)
        return m.accept_string(json.dumps(obj, ensure_ascii=False, indent=1)) and m.accept_token(info.stop_token_ids[0])

    print(f"xgrammar {__import__('importlib.metadata').metadata.version('xgrammar')}")
    src = load_sources()

    print("\n1) 수락 — 관문 다 통과 · rule 있는 출력")
    for gname, g in grammars.items():
        tot = acc = 0
        for k, outs in src.items():
            a = sum(accepts(g, o) for o in outs)
            print(f"  [{gname}] {k:24} {a}/{len(outs)}")
            tot += len(outs)
            acc += a
        print(f"  [{gname}] 합계 {acc}/{tot} = {100 * acc / tot:.1f}%")

    print("\n2) 거부 — v127a/b 수락 출력에 환각 이름 하나씩")
    good = [o for k in ("results_kb10v127a", "results_kb10v127b") for o in src[k] if accepts(grammars["얇은 THIN"], o)]
    print(f"  바탕 출력 {len(good)}")
    for gname, g in grammars.items():
        tot = rej = 0
        for name, (key, bad, where) in MUTATIONS.items():
            n = r = 0
            for o in good:
                o2 = copy.deepcopy(o)
                before = json.dumps(o2)
                walk(o2, lambda d: d.__setitem__(key, bad) if where(d) else None)
                if json.dumps(o2) == before:
                    continue
                n += 1
                r += not accepts(g, o2)
            print(f"  [{gname}] {name:12} 바꾼 출력 {n} · 거부 {r}")
            tot += n
            rej += r
        print(f"  [{gname}] 합계 거부 {rej}/{tot}")

    print("\n3) 얇은 스키마가 거부한 정상 출력 — 키 순서만 맞추면?")
    for k, outs in src.items():
        bad = [o for o in outs if not accepts(grammars["얇은 THIN"], o)]
        if bad:
            print(f"  {k:24} 거부 {len(bad)} → 순서 맞추면 수락 {sum(accepts(grammars['얇은 THIN'], canon(o)) for o in bad)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
