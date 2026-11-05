#!/usr/bin/env python3
"""M3 출력 자동 채점기.

run_m3.py 가 만든 출력 폴더(들)를 읽어 공통 검사 + 케이스별 단언(expectations.json)으로 채점한다.
폴더를 여러 개 주면 버전 비교표를 만든다.

예)
  python grade.py --cases testcases --expect expectations.json --outputs runs/v0.3
  python grade.py --cases testcases --expect expectations.json --outputs runs/v0.3 runs/v0.4 --report report.md
  python grade.py --cases testcases --expect expectations.json --outputs runs/v0.3 runs/v0.4=testcases_v0.4

10-14: v0.4 입력·출력도 읽는다 — 판정이 Fact 안 judgment 에 있음 · section_order 가 [{section_id, title}] ·
state "NONE" = "INFO" · 출력에 product · used_fact_ids 없음(S03 · S07 은 코드 계산으로 넘겨 검사 안 함).
--outputs 의 "폴더=케이스폴더" 로 실행마다 다른 입력 폴더를 쓸 수 있다.

level:
  필수  점수에 반영
  기획  의사결정표 의도. v0.3 에서는 실패가 예상됨(xfail). 점수와 따로 집계
  참고  팀 결정 전 기준. 점수에서 제외하고 결과만 보여 줌
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

STATES = {"SATISFIED", "UNSATISFIED", "INFO_MISSING", "BANK_CONFIRM_NEEDED", "INFO"}
TOP_KEYS = {"product", "sections", "questions_for_user", "used_fact_ids", "omitted_must_include"}
TOP_KEYS_V04 = {"sections", "questions_for_user", "omitted_must_include"}


def is_v04(case: dict) -> bool:
    return "judgment_results" not in case


def judgments(case: dict) -> dict:
    if not is_v04(case):
        return {j["fact_id"]: j for j in case["judgment_results"]}
    return {f["fact_id"]: f["judgment"] for f in case["candidate_facts"] if f.get("judgment")}


def section_titles(case: dict) -> list:
    return [o["title"] if isinstance(o, dict) else o for o in case["section_order"]]
BANNED = r"항상|누구나|확실히|보장|추천|유리|가입하세요|비교|적합"
COMMON_IDS = [("S02", "필수"), ("S03", "필수"), ("S04", "필수"), ("S05", "필수"), ("S06", "필수"),
              ("S07", "필수"), ("S08", "필수"), ("S08b", "필수"), ("S09", "필수"), ("S09b", "기획"),
              ("J01", "필수"), ("J02", "필수"), ("J03", "참고"), ("J04", "필수"), ("J06", "필수"),
              ("N01", "필수"), ("N02", "필수"), ("N04", "필수"), ("N05", "필수"), ("N06", "필수"),
              ("N09", "필수"), ("N10", "필수"), ("N11", "기획")]
STATE_PHRASE = {
    "SATISFIED": "입력하신 내용 기준",
    "UNSATISFIED": "입력하신 내용 기준으로는",
    "INFO_MISSING": "알려 주시면",
    "BANK_CONFIRM_NEEDED": "은행 확인이 필요",
}


# ---------------------------------------------------------------- 텍스트 정규화
def norm(s: str) -> str:
    """날짜 표기를 YYYY-MM-DD 로 통일."""
    s = re.sub(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
               lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}", s)
    s = re.sub(r"(\d{4})\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{1,2})\.?",
               lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}", s)
    return s


def match_item(text: str, item) -> bool:
    if isinstance(item, dict):
        return re.search(item["re"], text) is not None
    if isinstance(item, list):
        return any(match_item(text, x) for x in item)
    return norm(item) in text


def item_label(item) -> str:
    if isinstance(item, dict):
        return f"/{item['re']}/"
    if isinstance(item, list):
        return " 또는 ".join(item_label(x) for x in item)
    return f"'{item}'"


# ---------------------------------------------------------------- 출력 파싱
def parse_output(raw: str):
    """(엄격 파싱 성공 여부, 파싱 결과 또는 None, 메모)."""
    s = raw.strip()
    try:
        return True, json.loads(s), ""
    except Exception:
        pass
    # 관대 파싱: 코드펜스 제거 후 첫 { ~ 마지막 }
    t = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            return False, json.loads(t[i:j + 1]), "앞뒤 텍스트·코드펜스를 걷어내고 파싱함"
        except Exception as e:
            return False, None, f"JSON 파싱 실패: {e}"
    return False, None, "JSON 객체를 찾지 못함(출력이 잘렸을 수 있음)"


def sentences_of(out: dict):
    """[(index, section_title, sentence_dict)] — 출력 순서대로."""
    res, k = [], 0
    for sec in out.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        for s in sec.get("sentences") or []:
            if isinstance(s, dict):
                if s.get("state") == "NONE":
                    s = {**s, "state": "INFO"}
                res.append((k, sec.get("title"), s))
                k += 1
    return res


def fids(s):
    v = s.get("fact_ids") or []
    return [x for x in v if isinstance(x, str)]


# ---------------------------------------------------------------- 공통 검사
def common_checks(case: dict, out: dict, strict_ok: bool, parse_note: str):
    R = []

    def add(cid, level, desc, ok, detail=""):
        R.append({"id": cid, "level": level, "desc": desc, "ok": ok, "detail": detail})

    add("S01", "필수", "JSON 하나만 출력(앞뒤 다른 글 없음)", strict_ok, parse_note)
    if out is None:
        # 파싱 실패 시 나머지 공통 검사도 실패로 기록해 버전 간 분모를 같게 유지
        for cid, lv in COMMON_IDS:
            if is_v04(case) and cid in ("S03", "S07"):
                continue
            add(cid, lv, "출력 파싱 실패로 검사 불가", False, "")
        return R

    facts = {f["fact_id"]: f for f in case["candidate_facts"]}
    judg = judgments(case)
    v04 = is_v04(case)
    sents = sentences_of(out)
    used_union = {f for _, _, s in sents for f in fids(s)}

    keys = set(out.keys())
    top = TOP_KEYS_V04 if v04 else TOP_KEYS
    add("S02", "필수", "최상위 키가 스키마와 일치", keys == top,
        f"없음 {sorted(top - keys)} / 추가 {sorted(keys - top)}" if keys != top else "")
    if not v04:
        add("S03", "필수", "product 가 입력과 같음", out.get("product") == case["product"], str(out.get("product")))

    order = section_titles(case)
    titles = [sec.get("title") for sec in out.get("sections") or [] if isinstance(sec, dict)]
    idx = [order.index(t) if t in order else None for t in titles]
    ok = None not in idx and idx == sorted(idx) and len(set(idx)) == len(idx)
    add("S04", "필수", "섹션 제목이 section_order 안에서 순서대로", ok, f"제목 {titles}")

    bad = [(k, fids(s)) for k, _, s in sents if not fids(s) or not set(fids(s)) <= set(facts)]
    add("S05", "필수", "모든 문장에 실제 fact_id 가 1개 이상", not bad, f"문제 문장 {bad[:5]}" if bad else "")

    bad = [(k, s.get("state")) for k, _, s in sents if s.get("state") not in STATES]
    add("S06", "필수", "문장 state 값이 정해진 5종 중 하나", not bad, str(bad[:5]) if bad else "")

    used = out.get("used_fact_ids") or []
    ok = set(used) == used_union and len(used) == len(set(used))
    if not v04:
        add("S07", "필수", "used_fact_ids = 문장 fact_ids 합집합", ok,
            f"used만 {sorted(set(used) - used_union)} / 문장만 {sorted(used_union - set(used))}" if not ok else "")

    omitted = {o.get("fact_id"): o.get("reason") for o in out.get("omitted_must_include") or [] if isinstance(o, dict)}
    miss = [f for f in case["must_include_fact_ids"] if f not in used_union and f not in omitted]
    both = sorted(set(omitted) & used_union)
    noreason = [f for f, r in omitted.items() if not r]
    add("S08", "필수", "must_include 를 모두 쓰거나 누락 사유 보고", not miss and not both and not noreason,
        f"빠졌는데 보고 없음 {miss} / 쓰고도 누락 보고 {both} / 사유 없음 {noreason}" if (miss or both or noreason) else "")
    silent = [f for f in case["must_include_fact_ids"] if f not in used_union]
    add("S08b", "필수", "must_include 를 실제로 모두 사용", not silent, f"미사용 {silent}" if silent else "")

    bad = [[a, b] for a, b in case["dependencies"] if a in used_union and b not in used_union]
    add("S09", "필수", "dependencies: A 를 쓰면 B 도 씀", not bad, str(bad) if bad else "")
    sec_of = defaultdict(set)
    for _, t, s in sents:
        for f in fids(s):
            sec_of[f].add(t)
    bad = [[a, b] for a, b in case["dependencies"]
           if a in used_union and b in used_union and not (sec_of[a] & sec_of[b])]
    add("S09b", "기획", "dependencies A·B 가 같은 섹션에", not bad, str(bad) if bad else "")

    # 판정 일치
    bad = []
    for f, j in judg.items():
        if f not in used_union:
            continue
        st = [s.get("state") for _, _, s in sents if f in fids(s) and s.get("state") != "INFO"]
        if not st or any(x != j["state"] for x in st):
            bad.append(f"{f}: 판정 {j['state']} / 문장 {st or '판정 문장 없음'}")
    add("J01", "필수", "판정 있는 Fact 의 문장 state 가 판정과 같음", not bad, "; ".join(bad))

    bad = [(k, s.get("state")) for k, _, s in sents
           if fids(s) and not any(f in judg for f in fids(s)) and s.get("state") != "INFO"]
    add("J02", "필수", "판정 없는 Fact 만 쓴 문장은 INFO", not bad, str(bad) if bad else "")

    bad = []
    for st, ph in STATE_PHRASE.items():
        group = [s for _, _, s in sents if s.get("state") == st]
        if group and not any(ph in norm(s.get("text", "")) for s in group):
            bad.append(f"{st}: '{ph}' 없음")
    add("J03", "참고", "state 별 안내 문구 사용(템플릿 고정 여부는 팀 결정)", not bad, "; ".join(bad))

    hedge = re.compile(r"될 것|가능할 것|아마|예상됩니다|적용됩니다[.。]?$")
    bad = [k for k, _, s in sents
           if s.get("state") in ("BANK_CONFIRM_NEEDED", "INFO_MISSING") and hedge.search(s.get("text", "").strip())]
    add("J04", "필수", "INFO_MISSING·은행확인 문장에 추측·단정 없음", not bad, f"문장 {bad}" if bad else "")

    has_missing = any(j["state"] == "INFO_MISSING" for j in judg.values())
    q = out.get("questions_for_user") or []
    ok = (len(q) > 0) if has_missing else (len(q) == 0)
    add("J06", "필수", "INFO_MISSING 이 있을 때만 질문", ok, f"질문 {len(q)}개")

    # 수치·표현
    corpus_parts = []
    for f in facts.values():
        corpus_parts += [str(f.get("text") or ""), str(f.get("condition") or ""), " ".join(f.get("exceptions") or []),
                         str(f.get("value") if f.get("value") is not None else ""), str(f.get("as_of") or "")]
    corpus_parts += [str(v) for v in case["user_input"].values()]
    for j in judg.values():
        corpus_parts += [str(x) for x in (j.get("unmet_conditions") or []) + (j.get("confirm_items") or [])]
    corpus_nums = set(re.findall(r"\d+(?:\.\d+)?", norm(" ".join(corpus_parts)).replace(",", "")))
    num_tok = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s?(?=%p|%|만원|천원|원|개월|일|회|세|년|계좌|건)")
    bad = []
    for k, _, s in sents:
        t = re.sub(r"\d{4}-\d{2}-\d{2}", " ", norm(s.get("text", "")))
        for m in num_tok.finditer(t):
            n = m.group(1).replace(",", "")
            cands = {n, n.rstrip("0").rstrip(".") if "." in n else n}
            if not cands & corpus_nums:
                bad.append(f"문장{k}: {m.group(0)}")
    add("N01", "필수", "문장 속 수치가 모두 입력에 있음(계산·날조 없음)", not bad, ", ".join(bad[:8]))

    bad = []
    for f in facts.values():
        if f.get("unit") == "%p" and f.get("value") is not None:
            for k, _, s in sents:
                if f["fact_id"] in fids(s):
                    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s?%(?!p)", s.get("text", "")):
                        if abs(float(m.group(1)) - float(f["value"])) < 1e-9:
                            bad.append(f"{f['fact_id']} 문장{k}: {m.group(0)}")
    add("N02", "필수", "%p 를 % 로 바꾸지 않음", not bad, ", ".join(bad))

    bad = []
    for f in facts.values():
        if f.get("as_of") and f.get("unit") == "%":
            ss = [s for _, _, s in sents if f["fact_id"] in fids(s)]
            if ss and not any(f["as_of"] in norm(s.get("text", "")) for s in ss):
                bad.append(f["fact_id"])
    add("N04", "필수", "기준일 있는 금리에 기준일 표기", not bad, f"누락 {bad}" if bad else "")

    bad = []
    for f in facts.values():
        if "세전" in (f.get("text") or ""):
            ss = [s for _, _, s in sents if f["fact_id"] in fids(s)]
            if ss and not any("세전" in s.get("text", "") for s in ss):
                bad.append(f["fact_id"])
    add("N05", "필수", "원문에 '세전'이 있으면 문장에도", not bad, f"누락 {bad}" if bad else "")

    bad = []
    for f in facts.values():
        if f.get("only_in"):
            ss = [s for _, _, s in sents if f["fact_id"] in fids(s)]
            if ss and not any(f"({f['only_in']} 기준)" in s.get("text", "") for s in ss):
                bad.append(f["fact_id"])
    add("N06", "필수", "only_in 출처 '(문서 기준)' 표기", not bad, f"누락 {bad}" if bad else "")

    src = " ".join(corpus_parts)
    bad = [f"문장{k}: {m}" for k, _, s in sents for m in re.findall(BANNED, s.get("text", "")) if m not in src]
    add("N09", "필수", "금지어 없음(보장·추천·유리·적합 등)", not bad, ", ".join(bad[:8]))

    def grams(t):
        t = re.sub(r"\s", "", t)
        return {t[i:i + 3] for i in range(max(len(t) - 2, 0))}
    bad = []
    for a in range(len(sents)):
        for b in range(a + 1, len(sents)):
            ga, gb = grams(sents[a][2].get("text", "")), grams(sents[b][2].get("text", ""))
            if ga and gb and len(ga & gb) / len(ga | gb) > 0.8:
                bad.append(f"{a}~{b}")
    add("N10", "필수", "거의 같은 문장 반복 없음", not bad, ", ".join(bad))

    per_sec = defaultdict(int)
    for _, t, _ in sents:
        per_sec[t] += 1
    ok = len(sents) <= 8 and all(v <= 3 for v in per_sec.values())
    add("N11", "기획", "분량: 전체 8문장·섹션당 3문장 이하", ok, f"전체 {len(sents)} / 섹션별 {dict(per_sec)}")
    return R


# ---------------------------------------------------------------- 케이스별 단언
def case_checks(case: dict, out: dict, exps: list):
    R = []
    sents = sentences_of(out) if out else []
    used = {f for _, _, s in sents for f in fids(s)}
    omitted = {o.get("fact_id") for o in (out or {}).get("omitted_must_include") or [] if isinstance(o, dict)}
    questions = [q if isinstance(q, str) else json.dumps(q, ensure_ascii=False)
                 for q in (out or {}).get("questions_for_user") or []]

    for e in exps:
        ok, detail = True, ""
        t = e["type"]
        if out is None:
            ok, detail = False, "출력 파싱 실패"
        elif t == "used_includes":
            miss = [i for i in e["ids"] if i not in used]
            ok, detail = not miss, f"미사용 {miss}" if miss else ""
        elif t == "used_excludes":
            extra = [i for i in e["ids"] if i in used]
            ok, detail = not extra, f"사용됨 {extra}" if extra else ""
        elif t == "used_or_omitted":
            miss = [i for i in e["ids"] if i not in used and i not in omitted]
            ok, detail = not miss, f"둘 다 아님 {miss}" if miss else ""
        elif t == "state_is":
            st = [s.get("state") for _, _, s in sents if e["fact"] in fids(s)]
            ok = e["state"] in st
            detail = f"{e['fact']} 문장 state {st or '문장 없음'}"
        elif t == "state_never":
            st = [s.get("state") for _, _, s in sents if e["fact"] in fids(s)]
            hit = [x for x in st if x in e["states"]]
            ok, detail = not hit, f"{e['fact']} 문장 state {st}" if hit else ""
        elif t in ("text", "fact_text"):
            pool = sents
            if t == "fact_text":
                pool = [x for x in pool if set(e["facts"]) & set(fids(x[2]))]
            if e.get("states"):
                pool = [x for x in pool if x[2].get("state") in e["states"]]
            if e.get("exclude_states"):
                pool = [x for x in pool if x[2].get("state") not in e["exclude_states"]]
            if t == "fact_text" and not pool:
                if e.get("if_used"):
                    ok, detail = True, "해당 문장 없음 → 건너뜀"
                else:
                    ok, detail = False, f"{e['facts']} 를 쓴 문장 없음"
            else:
                text = norm(" ".join(x[2].get("text", "") for x in pool))
                miss = [item_label(i) for i in e.get("all", []) if not match_item(text, i)]
                hit = [item_label(i) for i in e.get("none", []) if match_item(text, i)]
                ok = not miss and not hit
                detail = "; ".join(filter(None, [f"없음 {miss}" if miss else "", f"금지 표현 있음 {hit}" if hit else ""]))
        elif t == "implies_used":
            a, b = e["pair"]
            ok = a not in used or b in used
            detail = "" if ok else f"{a} 사용, {b} 미사용"
        elif t == "not_cocited":
            a, b = e["pair"]
            hit = [k for k, _, s in sents if a in fids(s) and b in fids(s)]
            ok, detail = not hit, f"같이 쓴 문장 {hit}" if hit else ""
        elif t == "no_digits":
            hit = [k for k, _, s in sents if e["fact"] in fids(s) and re.search(r"\d", s.get("text", ""))]
            ok, detail = not hit, f"숫자 있는 문장 {hit}" if hit else ""
        elif t == "order_before":
            first = {}
            for k, _, s in sents:
                for f in fids(s):
                    first.setdefault(f, k)
            if e["fact"] not in first:
                ok, detail = False, f"{e['fact']} 문장 없음"
            else:
                later = [f for f in e["before"] if f in first and first[f] < first[e["fact"]]]
                ok = not later
                detail = f"{e['fact']} 위치 {first[e['fact']]}, 더 앞에 나온 것 {[(f, first[f]) for f in later]}" if later else ""
        elif t == "order_text_before":
            ti = next((k for k, _, s in sents if norm(e["text"]) in norm(s.get("text", ""))), None)
            fi = next((k for k, _, s in sents if e["fact"] in fids(s)), None)
            if fi is None:
                ok, detail = True, f"{e['fact']} 문장 없음 → 건너뜀"
            elif ti is None:
                ok, detail = False, f"'{e['text']}' 언급 없음"
            else:
                ok = ti < fi or (e.get("allow_same") and ti == fi)
                detail = f"'{e['text']}' 문장{ti}, {e['fact']} 문장{fi}"
        elif t == "questions":
            probs = []
            if "count" in e and len(questions) != e["count"]:
                probs.append(f"질문 {len(questions)}개(기대 {e['count']})")
            allq = " ".join(questions)
            for grp in e.get("mention", []):
                if not any(g in allq for g in grp):
                    probs.append(f"'{grp[0]}' 관련 질문 없음")
            ok, detail = not probs, "; ".join(probs)
        else:
            ok, detail = False, f"알 수 없는 type {t}"
        R.append({"id": e["id"], "level": e["level"], "desc": e["desc"], "ok": ok, "detail": detail})
    return R


# ---------------------------------------------------------------- 실행·보고
def grade_dir(cases_dir: Path, out_dir: Path, expect: dict, run_name: str = None):
    rows = []
    for of in sorted(out_dir.glob("T*.out.txt")):
        name = of.name[:-len(".out.txt")]
        case_id = name.split("_r")[0]
        cf = cases_dir / f"{case_id}.json"
        if not cf.exists():
            continue
        case = json.loads(cf.read_text(encoding="utf-8"))
        strict, out, note = parse_output(of.read_text(encoding="utf-8"))
        res = common_checks(case, out, strict, note) + case_checks(case, out, expect.get(case_id, []))
        for r in res:
            rows.append({"run": run_name or out_dir.name, "output": name, "case": case_id, **r})
    return rows


def summarize(rows):
    s = defaultdict(lambda: [0, 0])
    for r in rows:
        s[(r["run"], r["level"])][0] += r["ok"]
        s[(r["run"], r["level"])][1] += 1
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--expect", required=True)
    ap.add_argument("--outputs", nargs="+", required=True, help="run_m3.py 출력 폴더(여러 개면 비교)")
    ap.add_argument("--report", default="grade_report.md")
    ap.add_argument("--csv", default="grade_results.csv")
    args = ap.parse_args()

    expect = json.loads(Path(args.expect).read_text(encoding="utf-8"))
    rows = []
    for d in args.outputs:
        d, _, cdir = d.partition("=")
        rows += grade_dir(Path(cdir or args.cases), Path(d), expect, Path(d).name)
    if not rows:
        raise SystemExit("채점할 출력(T*.out.txt)을 찾지 못함")

    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["run", "output", "case", "id", "level", "desc", "ok", "detail"])
        w.writeheader()
        w.writerows(rows)

    runs = list(dict.fromkeys(r["run"] for r in rows))
    summ = summarize(rows)
    L = ["# M3 출력 채점 결과", "", "## 요약", "",
         "| 실행 | 필수 통과 | 기획(xfail 예상) 통과 | 참고(점수 제외) 통과 |", "|---|---|---|---|"]
    for run in runs:
        cells = []
        for lv in ("필수", "기획", "참고"):
            p, n = summ.get((run, lv), [0, 0])
            cells.append(f"{p}/{n} ({p / n:.0%})" if n else "-")
        L.append(f"| {run} | " + " | ".join(cells) + " |")

    if len(runs) > 1:
        L += ["", "## 버전 간 결과가 달라진 검사", "", "| 출력 | 검사 | 수준 | " + " | ".join(runs) + " |",
              "|---|---|---|" + "---|" * len(runs)]
        by = defaultdict(dict)
        meta = {}
        for r in rows:
            by[(r["output"], r["id"])][r["run"]] = r["ok"]
            meta[(r["output"], r["id"])] = (r["level"], r["desc"])
        for key, v in sorted(by.items()):
            if len(set(v.values())) > 1:
                lv, desc = meta[key]
                L.append(f"| {key[0]} | {key[1]} {desc} | {lv} | " +
                         " | ".join("✅" if v.get(rn) else ("❌" if rn in v else "-") for rn in runs) + " |")

    for run in runs:
        L += ["", f"## {run} — 실패 목록", ""]
        fails = [r for r in rows if r["run"] == run and not r["ok"]]
        if not fails:
            L.append("실패 없음")
            continue
        L += ["| 출력 | 검사 | 수준 | 내용 | 상세 |", "|---|---|---|---|---|"]
        for r in fails:
            L.append(f"| {r['output']} | {r['id']} | {r['level']} | {r['desc']} | {r['detail'].replace('|', '/')} |")

    Path(args.report).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:6 + len(runs)]))
    print(f"\n보고서: {args.report} / 전체 결과: {args.csv}")


if __name__ == "__main__":
    main()
