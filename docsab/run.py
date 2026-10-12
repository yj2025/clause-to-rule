"""특약만 · 상품설명서만 넣고 같은 요약 지시로 key 요약을 뽑는다 (2026-10-12 · 기준 문서 질문).

    /workspace/.venv/bin/python docsab/run.py            → docsab/out.jsonl (한 줄 = 상품 하나의 한 판)

입력은 팀 요약입력(docs/요약입력_상품별.json). 상품마다 A = 특약 조항만, B = 상품설명서 조항만.
요약 대상 key 목록은 두 판이 같다(그 문서에 근거가 없으면 summary null 이 나와야 한다). 공통약관은 둘 다 뺀다.
지시문은 팀 것에서 «특약 우선» · «공통약관» 두 문장만 뺀다. Qwen3-8B · 생각 끔 · 온도 0. 끊기면 다시 띄우면 된 것은 건너뛴다.
"""
import json, sys, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json")
OUT = HERE / "out.jsonl"
MAX_NEW = 4096
FIRST = ["KB스타통장", "KB 별별통장2", "KB 프리N통장", "쓱머니KB통장", "KB Young Youth 통장", "KB스타적금Ⅲ",
         "KB국민프리미엄적금 (정액적립식)", "KB 장기간부 도약적금", "KB사학연금평생안심통장", "KB맑은하늘적금",
         "KB내맘대로적금", "KB가맹점우대적금", "KB골든라이프연금우대통장", "KB나라사랑우대통장"]


def system_prompt(team):
    for s in ("특약과 상품설명서가 다르면 특약을 우선하고 차이를 note에 적는다. ",
              "[공통약관]은 상품 문서에 해당 key 내용이 없을 때만 쓴다. "):
        assert s in team, s
        team = team.replace(s, "")
    return team


def build_input(p, doc):
    secs = [s for s in p["sections"] if s["doc_type"] == doc]
    have = {s["section_id"] for s in secs}
    ids = lambda xs: "[" + ", ".join(map(str, [x for x in xs if x in have])) + "]" if any(x in have for x in xs) else "-"
    lines = [f"# 상품: {p['product_name']} (product_id {p['product_id']})",
             f"문서: {doc}만", "", "## 요약 대상 key"]
    for k in p["keys"]:
        g = f", {k['group']}" if k.get("group") else ""
        lines.append(f"- {k['key']} ({k['name']}{g}): 주 {ids(k['primary_section_ids'])} / 참고 {ids(k['reference_section_ids'])}")
    if p.get("missing_keys"):
        mk = [m if isinstance(m, str) else m.get("key") for m in p["missing_keys"]]
        lines.append("- 원문 없음(출력하지 말 것): " + ", ".join(mk))
    lines += ["", "## 조항"]
    for s in secs:
        tags = ", ".join(f"{t['key']}:{t['role']}" for t in s["keys"])
        lines.append(f"[§{s['section_id']} | {s['doc_type']} | {s['document']} {s['path']} | {s['title']} | {tags}]")
        lines.append(s["text"].strip())
        lines.append("")
    return "\n".join(lines), len(secs)


def main():
    import torch
    from run_local_v2 import load_model, _free_cache, parse_json
    d = json.loads(SRC.read_text("utf-8"))
    system = system_prompt(d["meta"]["instruction"])
    packets = [p for p in d["packets"] if {s["doc_type"] for s in p["sections"]} >= {"특약", "상품설명서"}]
    rank = {n: i for i, n in enumerate(FIRST)}
    packets.sort(key=lambda p: rank.get(p["product_name"], len(FIRST)))
    done = set()
    if OUT.exists():
        done = {(r["product_name"], r["doc"]) for r in map(json.loads, OUT.read_text("utf-8").splitlines())}
    tok, model = load_model()
    print(f"상품 {len(packets)} · 이미 된 판 {len(done)}", flush=True)
    for i, p in enumerate(packets):
        for doc in ("특약", "상품설명서"):
            if (p["product_name"], doc) in done:
                continue
            user, nsec = build_input(p, doc)
            conv = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            text = tok.apply_chat_template(conv, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            enc = tok(text, return_tensors="pt").to(model.device)
            t0, raw, err = time.time(), None, None
            try:
                with torch.no_grad():
                    out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)
                gen = out[0][enc["input_ids"].shape[1]:]
                raw, ngen = tok.decode(gen, skip_special_tokens=True), len(gen)
            except Exception as e:          # OOM 이면 그 판만 비우고 다음으로
                err, ngen = type(e).__name__, 0
                _free_cache()
            rec = {"product_name": p["product_name"], "product_id": p["product_id"], "doc": doc,
                   "n_sections": nsec, "in_tokens": int(enc["input_ids"].shape[1]), "gen_tokens": ngen,
                   "truncated": ngen >= MAX_NEW, "error": err, "sec": round(time.time() - t0, 1),
                   "parsed": parse_json(raw) if raw else None, "raw": raw}
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{i+1}/{len(packets)}] {p['product_name']} · {doc} · 조항 {nsec} · 입력 {rec['in_tokens']} · 생성 {ngen}"
                  f" · {rec['sec']}s · {'읽힘' if rec['parsed'] else '안 읽힘'}{' · ' + err if err else ''}", flush=True)
    print("docsab 끝", flush=True)


if __name__ == "__main__":
    main()
