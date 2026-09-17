"""블라인드 43조문에 돌린 팀원 모델 출력을 이 저장소 gold 로 채점한다.

    python blind_score.py base e3        # results/blind43_<tag>.jsonl → results/blind43_score.json

팀원 gold 가 없는 조문이라 팀원 지표(semantic_exact · form_f1 …)는 못 낸다.
gold 없이 낼 수 있는 것과, 이 저장소 gold 와 맞대는 것을 나눠 낸다.

**gold 없이**
  parse       JSON 을 꺼냈나 — 팀원 노트북 `extract_json` 그대로
  shape       semantic_rule_v1.1 모양인가 (status · form 이 정해진 값인가)
  grounding   `surface` 값이 패킷에 글자 그대로 있나 — 팀원 `grounding_rate` 그대로.
              evidence 문장은 세지 않고, surface 가 하나도 없으면 1.0 이다 (빈 출력도 만점)

**이 저장소 gold 와**
  선언        옮길 것이 있나 없나. gold 빈 배열 ↔ 모델 NO_EXECUTABLE_RULE.
              모델이 RULES_FOUND 를 냈어도 변환기가 전부 "규칙 아님"(기본금리 · 거래 경로)으로
              판정하면 빈 배열로 친다 — 이 저장소 원칙이다 (`DECISIONS.md`).
  변환        `semconv` + `semselect` canon 고르기. 막힌 층을 센다
  ⑥ 실행      옮겨진 규칙을 gold 와 같은 프로필에 돌려 결과가 같은 비율.
              **옮겨진 조문만** 잰다. 막힌 조문을 빈 규칙으로 채점하면 UNSUPPORTED gold 에서
              만점이 나와 뜻이 없다. 같은 조문에서 빈 배열의 ⑥ 을 기준선으로 같이 낸다.

모든 값을 novelty 등급(SEEN_TRAIN · NEAR_TRAIN · NEW)별로 따로 낸다 (`blind_packets.py`).
"""

import argparse
import collections
import json
import re
import unicodedata
from pathlib import Path

import gold
import semconv
import semselect
from scoring import score

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "blind43_score.json"
NOTEBOOK = Path("/workspace/personal_workplace_SYS/experiment_code/"
                "finance_part2_1_qwen35_9b_qlora_pilot_v1_1.ipynb")

STATUSES = ("RULES_FOUND", "NO_EXECUTABLE_RULE", "UNRESOLVED")
FORMS = ("CONSTRAINT", "CONDITIONAL_EFFECT", "SELECTOR")
TIERS = ("SEEN_TRAIN", "NEAR_TRAIN", "NEW")


def team_evaluator(notebook=NOTEBOOK):
    """노트북 Cell 06 을 실행해 extract_json · grounding_rate 를 가져온다."""
    nb = json.loads(Path(notebook).read_text("utf-8"))
    src = [c for c in ("".join(x["source"]) for x in nb["cells"] if x["cell_type"] == "code")
           if "Cell 06." in c]
    if len(src) != 1:
        raise SystemExit(f"노트북에서 Cell 06 을 하나로 못 찾았다: {len(src)}개")
    ns = {"re": re, "json": json, "unicodedata": unicodedata, "Counter": collections.Counter}
    exec(src[0], ns)
    return ns["extract_json"], ns["grounding_rate"]


def shape_ok(sem):
    if not isinstance(sem, dict) or sem.get("status") not in STATUSES:
        return False
    units = sem.get("rule_units")
    if sem["status"] == "RULES_FOUND" and not (isinstance(units, list) and units):
        return False                        # 규칙이 있다면서 rule_units 가 없다 — 기반 모델이 `rules` 로 냈다
    units = units or []
    return isinstance(units, list) and all(
        isinstance(u, dict) and u.get("form") in FORMS and isinstance(u.get("body"), dict)
        for u in units)


def declared_empty(sem, conv):
    """모델이 '옮길 것이 없다' 고 했나. True · False · None(미해결 · 판정 불가)."""
    if not isinstance(sem, dict):
        return None
    st = sem.get("status")
    if st == "NO_EXECUTABLE_RULE":
        return True
    if st != "RULES_FOUND":
        return None
    if conv is not None and conv["outcome"] == "NOT_A_RULE":
        return True
    return False


def _rules(conv):
    return [r for u in conv["units"] for r in u["rules"]] if conv else []


def score_tag(tag, packets, lex, extract_json, grounding_rate, prof, agg, base_rate):
    path = ROOT / "results" / f"blind43_{tag}.jsonl"
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    meta, preds = rows[0]["_meta"], {r["sample_id"]: r for r in rows[1:]}
    tpl = gold._templates()

    per = []
    for p in packets:
        sid = p["sample_id"]
        if sid not in preds:
            continue
        r = preds[sid]
        sem, err = extract_json(r["raw_output"])
        conv, conv_err = semselect.safe_convert(sem, semselect.SelectingLexicon(lex)) \
            if shape_ok(sem) else (None, "v1.1 모양이 아니다")
        g_rules = (tpl.get(sid) or {}).get("rules") or []
        rec = {"sample_id": sid, "novelty": p["novelty"], "truncated": r["truncated"],
               "parse": sem is not None, "shape": shape_ok(sem),
               "grounding": grounding_rate(sem, p["packet_text"]) if sem is not None else 0.0,
               "status": sem.get("status") if isinstance(sem, dict) else None,
               "gold_verdict": gold.verdict(g_rules),
               "gold_empty": not g_rules,
               "pred_empty": declared_empty(sem, conv),
               "convert_error": conv_err,
               "convert_outcome": conv["outcome"] if conv else None,
               "layers": dict(semselect._layers(conv)) if conv else {},
               "rules": _rules(conv)}
        rec["declaration_match"] = (rec["pred_empty"] == rec["gold_empty"]
                                    if rec["pred_empty"] is not None else False)
        if conv and conv["outcome"] in ("ALL_CONVERTED", "SOME_CONVERTED"):
            rec["exec"] = score(g_rules, rec["rules"], agg, prof, base_rate)["rate"]
            rec["exec_empty_baseline"] = score(g_rules, [], agg, prof, base_rate)["rate"]
        per.append(rec)
    return meta, per


def summarize(per):
    def block(rs):
        n = len(rs) or 1
        conv = collections.Counter(r["convert_outcome"] or "변환 안 됨" for r in rs)
        layers = collections.Counter()
        for r in rs:
            layers.update(r["layers"])
        ex = [r for r in rs if "exec" in r]
        return {
            "n": len(rs),
            "parse": sum(r["parse"] for r in rs) / n,
            "shape": sum(r["shape"] for r in rs) / n,
            "truncated": sum(r["truncated"] for r in rs),
            "grounding": sum(r["grounding"] for r in rs) / n,
            "status": dict(collections.Counter(r["status"] for r in rs)),
            "declaration_match": sum(r["declaration_match"] for r in rs) / n,
            "declaration_table": dict(collections.Counter(
                f"gold {'빈' if r['gold_empty'] else '규칙'} / 모델 "
                f"{ {True: '빈', False: '규칙', None: '판정불가'}[r['pred_empty']] }" for r in rs)),
            "convert": dict(conv),
            "blockers": dict(layers),
            "rules": sum(len(r["rules"]) for r in rs),
            "exec_n": len(ex),
            "exec": sum(r["exec"] for r in ex) / len(ex) if ex else None,
            "exec_empty_baseline": sum(r["exec_empty_baseline"] for r in ex) / len(ex) if ex else None,
        }
    out = {"전체": block(per)}
    for t in TIERS:
        out[t] = block([r for r in per if r["novelty"] == t])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    a = ap.parse_args()

    import blind_run
    packets = blind_run.load_packets()
    lex = semconv.Lexicon.load()
    extract_json, grounding_rate = team_evaluator()
    prod = gold._product()
    prof = gold.profiles()

    result = {"profiles": len(prof), "tags": {}}
    for tag in a.tags:
        meta, per = score_tag(tag, packets, lex, extract_json, grounding_rate, prof,
                              prod["aggregation"], prod["base_rate"])
        summ = summarize(per)
        result["tags"][tag] = {"meta": meta, "summary": summ, "records": per}
        print(f"\n## {tag} · {len(per)}/{len(packets)} 조문")
        for name, s in summ.items():
            ex = (f"⑥ {s['exec'] * 100:.0f}% (빈 배열 {s['exec_empty_baseline'] * 100:.0f}%, {s['exec_n']}조문)"
                  if s["exec"] is not None else "⑥ 옮겨진 조문 없음")
            print(f"  {name:10} n={s['n']:2} · JSON {s['parse'] * 100:3.0f}% · v1.1모양 {s['shape'] * 100:3.0f}% · "
                  f"근거 {s['grounding'] * 100:3.0f}% · 선언 일치 {s['declaration_match'] * 100:3.0f}% · "
                  f"규칙 {s['rules']} · {ex}")
            if name == "전체":
                print(f"             상태 {s['status']} · 잘림 {s['truncated']}")
                print(f"             선언 {s['declaration_table']}")
                print(f"             변환 {s['convert']} · 막힘 {s['blockers']}")
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), "utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
