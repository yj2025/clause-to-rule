"""팀 요약입력 v2 지시문의 규칙을 출력이 지키는지 검사한다 (2026-10-13).

    python3 docsab/score_v2.py <run_prompt 출력.json> <상품명>

v2 지시문(docs/요약입력_상품별_v2.json meta.instruction)의 규칙 중 코드로 볼 수 있는 것:
  형식     JSON 으로 읽히는가 · 출력 한도에서 잘렸는가
  범위     «요약 대상 key»만 냈는가 (원문 없음 key · 대상 밖 key 를 냈는가) · 대상 key 중 몇 개를 채웠는가
  최종금리 «우대금리 조건 있음»이면 final_rate 에 «우대 조건 충족 시»가 있는가 (조건 내용을 썼는지는 사람이 본다)
  특별중도해지  입력에 그 태그가 있으면 early_termination 에 특별중도해지 한 줄이 있는가
  질문 금지  사용자에게 묻거나 개인화한 문장이 있는가
  숫자     출력의 금액 · % · 기간 숫자가 그 상품 원문에 있는가
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/personal_workplace_CHO/model/M2-2")
from run_local_v2 import parse_json  # noqa: E402

SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별_v2.json")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:%p|%|만\s*원|천\s*원|원|개월|년|일|회|세|매|개)")
ASKY = re.compile(r"\?|알려\s*주|입력해\s*주|확인해\s*주시|선택해\s*주|고객님(?:의|께서)|귀하")


def norm_num(s):
    return re.sub(r"[\s,]", "", s)


def main(out_path, product):
    d = json.loads(SRC.read_text("utf-8"))
    p = next(x for x in d["packets"] if x["product_name"] == product)
    keys_in = set(d["meta"]["keys_in"])
    target = {k["key"] for k in p["keys"] if k["primary_section_ids"] or k["reference_section_ids"] or k.get("common_section_ids")}
    banned = {m["key"] if isinstance(m, dict) else m for m in p.get("missing_keys", [])}
    special = any(t["role"] == "특별중도해지" for s in p["sections"] for t in s["keys"])
    pref = "우대금리 조건 있음" in p.get("input_text", "") or "우대금리 조건 있음" in [json.loads(l) for l in open(str(SRC).replace(".json", ".jsonl"))
                                                                                 if json.loads(l)["product_name"] == product][0]["input"]
    src_nums = {norm_num(m) for s in p["sections"] + p.get("common_sections", []) for m in NUM.findall(s["text"])}
    rec = json.loads(Path(out_path).read_text("utf-8"))
    o = parse_json(rec["output"])
    R = {"model": rec["model"], "gen_tokens": rec["output_tokens"], "sec": round(rec["generation_seconds"]),
         "truncated": rec["output_tokens"] >= 6144, "parsed": bool(o)}
    if not o:
        print(json.dumps(R, ensure_ascii=False)); return R
    items = [i for i in o.get("items", []) if isinstance(i, dict)]
    out_keys = [i.get("key") for i in items]
    filled = {i.get("key") for i in items if i.get("summary")}
    text = lambda i: json.dumps({k: i.get(k) for k in ("summary", "conditions", "exceptions", "note")}, ensure_ascii=False)
    fr = next((i for i in items if i.get("key") == "final_rate"), None)
    et = next((i for i in items if i.get("key") == "early_termination"), None)
    # 표 머리에만 단위가 있는 원문(«(단위: 연 %) … 0.1»)이 있어 숫자만 같아도 인정한다
    src_bare = {re.sub(r"[^\d.]", "", n) for n in src_nums} | set(re.findall(r"\d+(?:\.\d+)?", " ".join(
        s["text"] for s in p["sections"] + p.get("common_sections", []))))
    bad_nums = sorted({n for i in items for n in map(norm_num, NUM.findall(text(i)))
                       if n not in src_nums and re.sub(r"[^\d.]", "", n) not in src_bare})
    asks = [(i.get("key"), m.group(0)) for i in items for m in [ASKY.search(text(i))] if m]
    R.update({
        "대상 key 채움": f"{len(filled & target)}/{len(target)}",
        "빠진 대상 key": sorted(target - filled),
        "원문 없음 key 출력": sorted(set(out_keys) & banned),
        "대상 밖 key 출력": sorted(set(out_keys) - target - banned),
        "keys_in 밖 key 출력": sorted(set(out_keys) - keys_in),
        "중복 key": sorted({k for k in out_keys if out_keys.count(k) > 1}),
        "최종금리 «우대 조건 충족 시»": (None if not pref else bool(fr and re.search(r"우대.{0,6}(조건|충족)", text(fr)))),
        "특별중도해지 한 줄": (None if not special else bool(et and "특별중도해지" in text(et))),
        "질문 · 개인화 문장": asks,
        "원문에 없는 숫자": bad_nums,
    })
    Path(out_path).with_suffix(".v2score.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(R, ensure_ascii=False))
    return R


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
