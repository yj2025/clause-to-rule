"""목표 형식 지시문 + 특약 · 상품설명서를 합친 입력으로 한 상품을 요약한다 (2026-10-12 · Qwen3-8B 단독 시험).

    /workspace/.venv/bin/python docsab/run_merged.py KB스타통장   → docsab/merged_<상품>.json
지시문에 정답 내용은 넣지 않는다 — 필드 규칙만.
"""
import json, sys, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json")
MAX_NEW = 6144

SYSTEM = """너는 KB 예금상품 원문을 key별로 요약하는 모델이다. 입력에는 같은 상품의 [특약] 조항과 [상품설명서] 조항이 함께 들어 있다.

규칙
1. 두 문서를 합쳐 key마다 결과를 하나만 낸다. 한쪽 문서에만 있는 내용도 버리지 않는다.
2. 두 문서의 내용이 다르거나 한쪽에만 있는 조건 · 예외가 있으면 어느 한쪽을 고르지 말고 doc_diff 에 무엇이 어느 문서에만 있는지 적는다. 한쪽에만 있는 예외 · 조건에는 only_in 에 그 문서 이름("특약" 또는 "상품설명서")을 적는다.
3. 조건은 충족한다고 가정하지 않는다. 고객의 거래 실적이나 잔액 등 고객 정보가 있어야 판단할 수 있는 조건에는 user_input 에 고객에게 물어야 할 값을 짧게 적는다.
4. 조건 · 단서 · 예외(단, ※, 다만, 제외)는 하나도 빠뜨리지 않는다. 원문의 ※ 문장은 각각 exceptions 나 conditions 나 special 중 하나에 들어가야 한다.
5. 금리 · 금액 · 기간 숫자는 원문 그대로 옮긴다. 원문에 기준일이 있으면 as_of 에 적는다.
6. conditions · exceptions · special 의 줄마다 src 에 근거 조항 번호(§ 뒤의 숫자)를 정수 배열로 적는다.
7. 여러 조건 중 하나만 충족하면 되는지, 모두 충족해야 하는지는 condition_logic 에 적는다. 신규 특례 · 이용 경로 · 산정 기준처럼 조건도 예외도 아닌 부가 규칙은 special 에 적는다.
8. '요약 대상 key'에 있는 key만 출력한다. 근거가 없으면 summary 를 null 로 두고 note 에 이유를 적는다.

출력은 JSON 하나만:
{"product_id": 정수, "product_name": 문자열, "items": [
  {"key": 문자열, "summary": "한두 문장",
   "benefit": "혜택 내용(있을 때만)",
   "conditions": [{"text": 문자열, "user_input": "물을 값(필요할 때만)", "src": [정수], "only_in": "(한쪽에만 있을 때만)"}],
   "condition_logic": "(조건이 둘 이상일 때)",
   "exceptions": [{"text": 문자열, "src": [정수], "only_in": "(한쪽에만 있을 때만)"}],
   "special": {"text": 문자열, "src": [정수]},
   "as_of": "(기준일이 있을 때)",
   "doc_diff": "(두 문서가 다를 때)",
   "note": "(필요할 때)",
   "source_section_ids": [정수]}
]}
값이 없는 필드는 빼도 된다."""


def build(p):
    secs = [s for s in p["sections"] if s["doc_type"] in ("특약", "상품설명서")]
    have = {s["section_id"] for s in secs}
    ids = lambda xs: ("[" + ", ".join(str(x) for x in xs if x in have) + "]") if any(x in have for x in xs) else "-"
    L = [f"# 상품: {p['product_name']} (product_id {p['product_id']})", "문서: 특약 + 상품설명서", "", "## 요약 대상 key"]
    for k in p["keys"]:
        g = f", {k['group']}" if k.get("group") else ""
        L.append(f"- {k['key']} ({k['name']}{g}): 주 {ids(k['primary_section_ids'])} / 참고 {ids(k['reference_section_ids'])}")
    if p.get("missing_keys"):
        L.append("- 원문 없음(출력하지 말 것): " + ", ".join(m["key"] if isinstance(m, dict) else m for m in p["missing_keys"]))
    L += ["", "## 조항"]
    for s in secs:
        tags = ", ".join(f"{t['key']}:{t['role']}" for t in s["keys"])
        L += [f"[§{s['section_id']} | {s['doc_type']} | {s['document']} {s['path']} | {s['title']} | {tags}]", s["text"].strip(), ""]
    return "\n".join(L)


def main(name):
    import torch
    from run_local_v2 import load_model, parse_json
    d = json.loads(SRC.read_text("utf-8"))
    p = next(x for x in d["packets"] if x["product_name"] == name)
    tok, model = load_model()
    user = build(p)
    text = tok.apply_chat_template([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                                   tokenize=False, add_generation_prompt=True, enable_thinking=False)
    enc = tok(text, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)
    gen = out[0][enc["input_ids"].shape[1]:]
    raw = tok.decode(gen, skip_special_tokens=True)
    rec = {"product_name": name, "model": "Qwen/Qwen3-8B", "in_tokens": int(enc["input_ids"].shape[1]),
           "gen_tokens": len(gen), "truncated": len(gen) >= MAX_NEW, "sec": round(time.time() - t0, 1),
           "system": SYSTEM, "user": user, "raw": raw, "parsed": parse_json(raw)}
    (HERE / f"merged_{name}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), "utf-8")
    print(f"{name} · 입력 {rec['in_tokens']} · 생성 {rec['gen_tokens']} · {rec['sec']}s · 잘림 {rec['truncated']} · {'읽힘' if rec['parsed'] else '안 읽힘'}")


if __name__ == "__main__":
    main(sys.argv[1])
