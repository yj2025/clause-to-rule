"""개인화 요약 출력을 생성평가 통합기준 v0.3 의 «객관 Track»으로 검사한다 (2026-10-13).

    python3 docsab/score_personal.py <입력.json> <run_prompt 출력.json>

코드로 볼 수 있는 것만 본다 — 문장 자연스러움 · 중요도 같은 주관 Track 은 사람/LLM 몫이라 여기서 판정하지 않는다.
  CF1  문장마다 근거 fact_id 가 있고, 모두 candidate_facts 안에 있는가
  FD1  문장의 숫자(금액 · % · 날짜 · 개월 …)가 그 문장이 인용한 fact 나 user_input 에 있는가
  PA2  판정이 있는 fact 를 인용한 문장의 state 가 판정과 같은가
  PA3  INFO_MISSING 문장이 혜택을 단정하지 않는가 · BANK_CONFIRM_NEEDED 문장에 «확인»이 있는가
  CC1  must_include 가 모두 인용됐는가
  CC2  의존 쌍 (A 인용 → B 인용)
  F4/R4 같은 문장 반복
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/personal_workplace_CHO/model/M2-2")
from run_local_v2 import parse_json  # noqa: E402

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:%p|%|만\s*원|원|개월|년|월|일|회|개|매|세)?")
ASSERT = re.compile(r"(면제됩니다|적용됩니다|받을 수 있습니다|드립니다)(?!.*(?:면|경우|알려|확인))")
DENY = re.compile(r"적용되지 않습니다|면제되지 않습니다|받을 수 없습니다")   # INFO_MISSING 을 «안 된다»로 단정 (10-13 Qwen)


def nums(s):
    out = set()
    for m in NUM.findall(s or ""):
        m = re.sub(r"[\s,]", "", m)
        if re.fullmatch(r"\d", m):          # 한 자리 숫자만 있는 것(①의 1 등)은 뺀다
            continue
        out.add(m)
    return out


def main(inp_path, out_path):
    inp = json.loads(Path(inp_path).read_text("utf-8"))
    rec = json.loads(Path(out_path).read_text("utf-8"))
    o = parse_json(rec["output"])
    R = {"model": rec["model"], "gen_tokens": rec["output_tokens"], "sec": round(rec["generation_seconds"]), "parsed": bool(o)}
    if not o:
        print(json.dumps(R, ensure_ascii=False)); return R
    facts = {f["fact_id"]: f for f in inp["candidate_facts"]}
    judg = {j["fact_id"]: j for j in inp["judgment_results"]}
    user_nums = nums(json.dumps(inp["user_input"], ensure_ascii=False))
    sents = [s for sec in o.get("sections", []) for s in sec.get("sentences", []) if isinstance(s, dict)]
    cited = set()
    cf1_bad, fd1_bad, pa2_bad, pa3_bad = [], [], [], []
    for s in sents:
        ids = s.get("fact_ids") or []
        cited |= set(ids)
        unknown = [i for i in ids if i not in facts]
        if not ids or unknown:
            cf1_bad.append({"text": s.get("text", "")[:80], "unknown": unknown, "no_ids": not ids})
        src = nums(" ".join(json.dumps(facts[i], ensure_ascii=False) for i in ids if i in facts)) | user_nums
        extra = sorted(n for n in nums(s.get("text", "")) if n not in src and re.sub(r"[^\d.]", "", n) not in {re.sub(r"[^\d.]", "", x) for x in src})
        if extra:
            fd1_bad.append({"text": s.get("text", "")[:80], "numbers": extra})
        for i in ids:
            if i in judg and s.get("state") not in (judg[i]["state"], "INFO"):
                pa2_bad.append({"fact_id": i, "want": judg[i]["state"], "got": s.get("state"), "text": s.get("text", "")[:80]})
            if i in judg and s.get("state") == "INFO" and judg[i]["state"] != "SATISFIED":
                pa2_bad.append({"fact_id": i, "want": judg[i]["state"], "got": "INFO", "text": s.get("text", "")[:80]})
        st = s.get("state")
        if st == "INFO_MISSING" and (ASSERT.search(s.get("text", "")) or DENY.search(s.get("text", ""))):
            pa3_bad.append({"state": st, "text": s.get("text", "")[:80]})
        if st == "BANK_CONFIRM_NEEDED" and "확인" not in s.get("text", ""):
            pa3_bad.append({"state": st, "text": s.get("text", "")[:80]})
    must = inp["must_include_fact_ids"]
    cc1_miss = [m for m in must if m not in cited]
    cc2_bad = [d for d in inp["dependencies"] if d[0] in cited and d[1] not in cited]
    texts = [re.sub(r"\s", "", s.get("text", "")) for s in sents]
    dup = len(texts) - len(set(texts))
    judged_cited = [j for j in judg if j in cited]
    missing_fields = [m for j in inp["judgment_results"] for m in j.get("missing_fields", [])]
    q = " ".join(o.get("questions_for_user", []) or [])
    R.update({
        "sentences": len(sents),
        "CF1 근거 없는 문장": len(cf1_bad), "FD1 근거에 없는 숫자": len(fd1_bad),
        "PA2 판정 불일치": len(pa2_bad), "PA2 판정 fact 인용": f"{len(judged_cited)}/{len(judg)}",
        "PA3 표현 강도 오류": len(pa3_bad),
        "CC1 필수 누락": f"{len(cc1_miss)}/{len(must)}", "CC2 의존 누락": f"{len(cc2_bad)}/{len(inp['dependencies'])}",
        "물을 것 표시": f"{sum(1 for m in missing_fields if any(w in q for w in re.findall(r'[가-힣]{2,}', m)[:3]))}/{len(missing_fields)}",
        "반복 문장": dup,
        "detail": {"CF1": cf1_bad, "FD1": fd1_bad, "PA2": pa2_bad, "PA3": pa3_bad, "CC1": cc1_miss, "CC2": cc2_bad},
    })
    Path(out_path).with_suffix(".score.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: v for k, v in R.items() if k != "detail"}, ensure_ascii=False))
    return R


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
