"""정답 · 모델 출력의 rule 을 사람이 읽는 한국어 규칙 서식(manual_rule_ko.v0.1)으로 내보낸다 (2026-10-07).

    python export_manual.py KBGL --gold showcase/gold_draft --clauses showcase/clauses_key.json -o out.json
    python export_manual.py KBGL --results showcase/results_kb10v127a.json --clauses showcase/clauses_key.json -o out.json

서식은 팀에서 쓰는 `docs/kb_*_rules.json` 을 따른다. 그 서식에 없는 두 칸을 더한다 —
  「실행」: 이 규칙을 실행기가 판정할 수 있나(OK) · 없나(UNSUPPORTED → 사유)
  「규칙 없는 조문」: 빈 배열로 둔 조문과 그 이유(no_rule_reason)
조건의 「항목」은 카탈로그 이름의 한국어 설명으로 적는다. 원문 문구를 다시 지어 쓰지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

import catalog
import reasons
from schema import NO_RULE_REASONS

CMP = {">=": "이상", ">": "초과", "<=": "이하", "<": "미만", "==": "같음", "!=": "다름", "in": "포함"}
KO = {"INDIVIDUAL": "개인", "SOLE_PROPRIETOR": "개인사업자", "CORPORATION": "법인", "ORGANIZATION": "임의단체",
      "JOINT": "공동명의", "APARTMENT_FEE": "아파트관리비", "GIRO": "지로", "CMS": "CMS", "FIRM_BANKING": "펌뱅킹",
      "CARD": "카드", "SALARY_CONTRACT": "급여이체 약정", "GENERAL_TRANSFER": "일반 이체", "MATURITY": "만기해지",
      "EARLY": "중도해지", "PARTIAL": "일부해지", "MID_TERM": "중도", "NONE": "해지 안 함", "BRANCH": "영업점",
      "ONLINE": "온라인", "INTERNET": "인터넷뱅킹", "MOBILE": "모바일", "ATM": "자동화기기", "CALL": "폰뱅킹",
      "IN": "전환해 들어옴", "OUT": "전환해 나감"}


def ko(v):
    if isinstance(v, list):
        return [KO.get(x, x) if isinstance(x, str) else x for x in v]
    return KO.get(v, v) if isinstance(v, str) else v


COUNT_WORD = {"count_events": "건수", "count_distinct_months": "실적이 있는 달 수",
              "count_consecutive_months": "연속한 달 수", "sum_events": "금액 합계(원)"}


def _anchor(a):
    if not isinstance(a, dict):
        return str(a)
    base = catalog.VARIABLES.get(a.get("anchor"), {}).get("desc", a.get("anchor"))
    s = base
    if a.get("offset_months"):
        s += f" {a['offset_months']:+d}개월"
    if a.get("offset_days"):
        s += f" {a['offset_days']:+d}일"
    d = a.get("day")
    if isinstance(d, int):
        s += f"의 {d}일"
    elif d == "first":
        s += "의 1일"
    elif d == "last":
        s += "의 말일"
    elif isinstance(d, dict):
        s += f"의 {d.get('nth')}째 {d.get('weekday')}"
    if a.get("month_of"):
        s += f" ({'·'.join(map(str, a['month_of']))}월)"
    return s


def _window(w, env):
    if isinstance(w, dict) and "ref" in w:
        w = env.get(str(w["ref"]).lstrip("$"), w)
    mr = (w or {}).get("month_range") if isinstance(w, dict) else None
    if not mr:
        return "전 기간"
    f, t = mr.get("from", {}), mr.get("to", {})
    if f.get("offset_months") == t.get("offset_months") == -1 and f.get("day") == "first" and t.get("day") == "last":
        return "전월(1일~말일)"
    return f"{_anchor(f)} ~ {_anchor(t)}"


def _event(spec, env):
    s = f"{_window(spec.get('within'), env)} {catalog.EVENTS.get(spec.get('event'), spec.get('event'))}"
    where = spec.get("where") or {}
    if "min_amount" in where:
        s += f"(건별 {where['min_amount']:,}원 이상)"
    for k, v in where.items():
        if k != "min_amount":
            s += f"({', '.join(map(str, ko(v))) if isinstance(v, list) else ko(v)})"
    return s


def _operand(x, env):
    if isinstance(x, dict) and "var" in x:
        return catalog.VARIABLES.get(x["var"], {}).get("desc", x["var"])
    if isinstance(x, dict) and "anchor" in x:
        return _anchor(x)
    if isinstance(x, dict) and len(x) == 1 and next(iter(x)) in COUNT_WORD:
        k = next(iter(x))
        return f"{_event(x[k], env)} {COUNT_WORD[k]}"
    return x


def cond(node, env):
    if not node:
        return {"항목": "모든 계좌", "비교": "항상", "값": None}
    try:
        return _cond(node, env)
    except Exception:            # 모델 출력의 깨진 조건 — 원래 JSON 을 그대로 보인다
        return {"해석 못 한 조건": json.dumps(node, ensure_ascii=False)}


def _cond(node, env):
    (op, arg), = node.items()
    if op == "and":
        return {"모두": [cond(c, env) for c in arg]}
    if op == "or":
        return {"하나 이상": [cond(c, env) for c in arg]}
    if op == "not":
        return {"아님": cond(arg, env)}
    if op == "exists":
        e = _event(arg, env)
        return {"항목": e if e.endswith("실적") else f"{e} 실적", "비교": "있음", "값": True}
    a, b = arg
    return {"항목": _operand(a, env), "비교": CMP.get(op, op), "값": ko(_operand(b, env))}


def result(eff):
    t = (eff or {}).get("type")
    v = eff.get("value") if eff else None
    if t in ("RATE_ADD", "RATE_SUBTRACT"):
        return {"동작": "가산" if t == "RATE_ADD" else "차감", "대상": "기본이율", "값": f"연 {v}%p"}
    if t == "RATE_OVERRIDE":
        return {"동작": "적용", "대상": "이율", "값": f"연 {v}%"}
    if t in ("FEE_WAIVE", "FEE_WAIVE_NO_CARRYOVER"):
        return {"동작": "수수료 면제", "대상": catalog.FEES.get(eff.get("target"), eff.get("target")),
                "한도": "제한없음" if v == "UNLIMITED" else f"{v}회"}
    if t == "DISQUALIFY":
        return {"동작": "가입 불가", "대상": "이 상품"}
    if t == "LIMIT_AMOUNT":
        return {"동작": "한도", "대상": eff.get("target", "금액"), "값": f"{v:,}원" if isinstance(v, (int, float)) else v}
    return {"동작": t, "대상": eff.get("target"), "값": v}


def category(rule, label):
    t = ((rule.get("effect") or {}).get("type")) or ""
    if t.startswith("RATE") or "이율" in label or "금리" in label:
        return "우대금리" if "우대" in label else "기본금리·이자"
    if t.startswith("FEE") or "수수료" in label:
        return "수수료·부가혜택"
    if t in ("DISQUALIFY", "REQUIRE") or "가입" in label:
        return "가입대상·자격"
    if "해지" in label or "만기" in label:
        return "중도해지·만기 후"
    return "기타"


def export(prefix, clauses, rules_by_clause, source):
    out_rules, empty, n = [], [], 0
    for c in clauses:
        if not c["id"].startswith(prefix + "-"):
            continue
        label = reasons.head_of(c["text"]) or c.get("label", "")
        rules = rules_by_clause.get(c["id"])
        if rules == []:
            empty.append({"조문": c["id"], "원문 위치": label,
                          "이유": NO_RULE_REASONS[reasons.classify(c["text"])]})
            continue
        for r in rules or []:
            n += 1
            ok = r.get("status") == "OK"
            env = r.get("let") or {}
            c_ = cond(r.get("condition"), env)
            if ok and r.get("guard"):
                c_ = {"모두": [cond(r["guard"], env), c_]}
            item = {"규칙 번호": f"R{n:03d}", "분류": category(r, label + r.get("label", "")),
                    "규칙 형태": "조건에 따른 결과", "조건": c_,
                    "결과": [result(r.get("effect"))] if ok and r.get("effect") else [],
                    "근거": [{"원문 위치": label, "원문": (r.get("source") or {}).get("quote", "")}],
                    "실행": {"가능": ok, "사유": None if ok else r.get("label", "")},
                    "출처 rule": r.get("rule_id")}
            if not ok:
                item["설명"] = r.get("label", "")
            out_rules.append(item)
    return {"서식 버전": "manual_rule_ko.v0.1+exec", "문서 정보": {"상품 조문 접두어": prefix, "만든 곳": source},
            "규칙": out_rules, "규칙 없는 조문": empty, "검수": {"상태": "검수 전", "검수자": None}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("--gold")
    ap.add_argument("--results")
    ap.add_argument("--clauses", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    clauses = json.loads(Path(a.clauses).read_text("utf-8"))
    if a.gold:
        rbc = {p.stem: json.loads(p.read_text("utf-8")).get("rules") or []
               for p in Path(a.gold).glob(f"{a.prefix}-*.json")}
        src = f"정답 {a.gold}"
    else:
        rbc = {}
        for x in json.loads(Path(a.results).read_text("utf-8")):
            o = x.get("output") if isinstance(x.get("output"), dict) else {}
            rbc[x["clause_id"]] = o.get("rules") if isinstance(o.get("rules"), list) else None
        src = f"모델 출력 {Path(a.results).name}"
    doc = export(a.prefix, clauses, rbc, src)
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2), "utf-8")
    print(f"{a.out}: 규칙 {len(doc['규칙'])} (실행 가능 {sum(r['실행']['가능'] for r in doc['규칙'])}) · 규칙 없는 조문 {len(doc['규칙 없는 조문'])}")


if __name__ == "__main__":
    main()
