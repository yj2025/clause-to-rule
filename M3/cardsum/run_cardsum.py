#!/usr/bin/env python3
"""C안 «꼭 확인할 조건» 카드 · «약관 요약» 5항목의 한두 줄 요약을 모델로 만든다 (2026-10-14 시험).

    python run_cardsum.py --model qwen --units units/*.json --out runs/v2

규칙(팀 초안):
- 항목·카드마다 따로 호출하고, 그 항목의 근거 섹션만 입력한다. 넣은 섹션은 결과의 summary_sections 에 남긴다.
- 숫자는 슬롯으로: 원문의 금리·기간·금액·횟수·날짜를 코드가 뽑아 {S1}… 로 주고, 모델은 슬롯 표기로만 숫자를 쓴다.
- 계산값은 코드가: 처음 가입 시 최대 금리, 중도해지 예시는 규칙 엔진(compute_slots)이 계산해 {C1}… 로 준다.
- 자동 검사: 슬롯 밖 숫자 · 없는 슬롯 · 길이 · 문장 수 · 금지어. 실패하면 이유를 알려 1회 다시 쓰게 하고, 또 실패하면 폐기.
- 사람 검수 후 저장은 이 스크립트 밖(검수 전 초안만 만든다).
v2(10-15): 상품 여러 개 · 표의 단위 없는 값(«0.1», 단위: 연 %)에 «연 …%» 를 붙여 슬롯화 · 슬롯 뒤 조사를 코드가 보정
(«3개월가»→«3개월이») · 원문이 단정하면 단정형, 카드 종류에 맞는 제목을 쓰라는 규칙 추가.
모델은 compare_terms.py 와 같이 NF4 4비트 · greedy · thinking 끔. gemma26 만 m3eval/run_m3.py 의 전문가 NF4 로더를 쓴다.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HF = Path(os.environ.get("HF_HOME", "/workspace/personal_workplace_CHO/.hf_cache")) / "hub"


def snap(repo):
    return str(next((HF / f"models--{repo.replace('/', '--')}" / "snapshots").iterdir()))


MODELS = {
    "qwen": lambda: snap("Qwen/Qwen3-8B"),
    "exaone": lambda: str(HERE.parent / "exaone_local"),  # 10-12 transformers 5.18 용으로 고친 사본
    "gemma12": lambda: snap("google/gemma-4-12B-it"),
    "gemma26": lambda: snap("google/gemma-4-26B-A4B-it"),
    "gemma31": lambda: snap("google/gemma-4-31B-it"),
}

BANNED = r"항상|누구나|확실히|보장|추천|유리|가입하세요|비교|적합"  # m3eval/grade.py N09 와 같음
LIMITS = {"card": {"chars": 110, "sents": 2, "title": 20}, "item": {"chars": 150, "sents": 3}}

SYSTEM = """당신은 은행 상품설명서 원문을 소비자가 읽기 쉬운 한국어 문장으로 옮기는 작성자입니다.

규칙
1. 입력으로 받은 원문에 있는 내용만 씁니다. 원문에 없는 해석, 추천, 권유, 다른 상품과의 비교는 쓰지 않습니다.
2. 숫자(금리·기간·금액·횟수·날짜)는 직접 쓰지 말고 반드시 슬롯 표기로 씁니다. 예: {S1}, {C1}
   - 슬롯 목록에 없는 숫자는 쓰지 않습니다. 숫자가 필요 없는 문장이면 슬롯을 쓰지 않아도 됩니다.
   - 슬롯 값에 이미 단위(%, 개월, 원 등)가 붙어 있으면 단위를 다시 붙이지 않습니다.
   - {C…} 슬롯은 규칙에 따라 미리 계산해 둔 값입니다. 직접 계산하지 말고 필요하면 이 값을 씁니다.
3. 해요체로, 짧고 쉬운 말로 씁니다. 원문의 어려운 용어는 풀어 씁니다.
4. 원문이 단정하면(«…로 처리», «적용하지 않음») 단정형으로 씁니다. 원문에 «…수 있음»이 없으면 «…수 있어요»로 약하게 바꾸지 않습니다.
5. 조건·예외가 있으면 빠뜨리지 않습니다(예: 누가·언제만 해당하는지, 어떤 경우 제외되는지).
6. 정해진 JSON 하나만 출력합니다. 앞뒤에 다른 글이나 코드펜스를 쓰지 않습니다."""

CARD_TASK = """[할 일] 아래 원문 조항 하나로 «꼭 확인할 조건» 카드 한 장을 씁니다.
- title: 이 조건을 한눈에 알 수 있는 짧은 제목 ({title}자 이내). 상황(예: «…하면»)이나 핵심 내용으로.
  카드 종류에 맞게: «혜택» 카드 제목에 «주의»를 쓰지 않고, «손해» 카드 제목은 손해 상황이 드러나게.
- summary: 고객이 꼭 알아야 할 점을 1~{sents}문장, 슬롯 값을 채운 뒤 {chars}자 이내로.
- 카드 종류가 «손해»면 고객이 손해 볼 수 있는 점을, «혜택»이면 받을 수 있는 것과 조건을, «알아둘 것»이면 지켜야 할 규칙을 중심으로 씁니다.
출력 형식: {{"title": "…", "summary": "…"}}"""

ITEM_TASK = """[할 일] 상품 요약의 «{name}» 항목을 씁니다. 이 항목에서 다룰 내용: {goal}
- summary: 1~{sents}문장, 슬롯 값을 채운 뒤 {chars}자 이내로.
출력 형식: {{"summary": "…"}}"""

# 숫자 + 단위. 날짜 먼저. (주1) · (예시1) 같은 각주 번호는 슬롯으로 뽑지 않는다.
SLOT_RE = re.compile(
    r"\d{4}\.\d{1,2}\.\d{1,2}\.?"
    r"|\d+(?:,\s?\d+)+월"          # 2,5,8,11월
    r"|\d+/\d+"                     # 2/3
    r"|만\s?\d+세"
    r"|택\d"
    r"|(?:연\s?)?\d+(?:\.\d+)?\s?(?:%p|%|개월|영업일|백만원|만원|천원|억원|만좌|원|회|인|계좌|일|년|월|세|가지|개|매)?"
)


def extract_slots(text):
    slots, seen = [], set()
    for m in SLOT_RE.finditer(text):
        before = text[max(0, m.start() - 3):m.start()]
        if re.search(r"(주|예시)$", before):
            continue
        prev = text[m.start() - 1:m.start()] or " "
        if re.match(r"[가-힣A-Za-z]", prev) and prev not in "년월일" and not m.group(0).startswith(("택", "만")):
            continue  # «별별통장2» 같은 이름 속 숫자
        if text[m.start() - 1:m.start()] == "(" and text[m.end():m.end() + 1] == ")":
            continue  # «(1)입금쿠폰» 같은 번호
        line_head = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
        if not line_head.strip() and re.match(r"\d+\.\s", text[m.start():]):  # «1. 기본이율» 같은 목록 번호
            continue
        v = m.group(0).strip().rstrip(".")
        if re.fullmatch(r"\d+\.\d+", v) and "연 %" in text:  # 표 값(단위: 연 %)
            v = f"연 {v}%"
        if v in seen:
            continue
        seen.add(v)
        ctx = text[max(0, m.start() - 18):m.end() + 12].replace("\n", " ")
        slots.append({"id": f"S{len(slots) + 1}", "value": v, "context": ctx})
    return slots


def trunc2(x):  # 소수점 셋째 자리 이하 버림
    return int(x * 100 + 1e-9) / 100


def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if x != int(x) else f"{x:.1f}"


def compute_slots(names, p):
    """규칙 엔진: 원문 표의 값(params)으로 계산하는 값만. 모델은 계산하지 않는다."""
    out = []
    for n in names:
        if n == "first_join_max":
            v = p["max_rate"] - p["rejoin_bonus"]
            out.append(("처음 가입할 때 받을 수 있는 최대 금리(최고금리에서 재가입 우대를 뺌)", f"연 {fmt(v)}%"))
        elif n == "early_example_6m":
            months = 6
            ratio, floor = next((r, f) for lo, hi, r, f in p["early_table"] if lo <= months < hi)
            v = max(trunc2(p["base_rate"] * ratio * months / p["contract_months"]), floor)
            out.append((f"예시: {p['contract_months']}개월 계약에서 {months}개월 동안 넣어 둔 돈을 중도해지할 때 받는 금리"
                        f"(기본금리 연 {fmt(p['base_rate'])}% 기준, 규칙 엔진 계산)", f"연 {fmt(v)}%"))
            out.append(("위 예시의 넣어 둔 기간", f"{months}개월"))
            out.append(("만기까지 두면 받는 기본금리", f"연 {fmt(p['base_rate'])}%"))
        else:
            raise KeyError(n)
    return [{"id": f"C{i + 1}", "value": v, "context": label} for i, (label, v) in enumerate(out)]


def build_unit(u, by_id, params):
    if u.get("from_units"):
        parts = [by_id[k] for k in u["from_units"]]
        text = "\n\n".join(f"[{q['ref']}]\n{q['text']}" for q in parts)
        sections = [q["ref"] for q in parts]
        body = "\n".join(q["text"] for q in parts)  # 머리말(«3쪽» 등)은 슬롯에서 뺌
    else:
        text, sections = u["text"], [u["ref"]]
        body = text
    slots = extract_slots(body) + compute_slots(u.get("computed", []), params)
    lim = LIMITS[u["kind"]]
    task = (CARD_TASK.format(**lim) if u["kind"] == "card"
            else ITEM_TASK.format(name=u["name"], goal=u["goal"], **lim))
    head = f"카드 종류: {u['track']}\n" if u["kind"] == "card" else ""
    slot_lines = "\n".join(f"{s['id']} = {s['value']}    ← {s['context']}" for s in slots) or "(없음)"
    user = f"{task}\n\n{head}출처: {u['ref']}\n[원문]\n{text}\n\n[슬롯]\n{slot_lines}"
    return text, sections, slots, user


BATCHIM_DIGIT = set("013678")  # 영·일·삼·육·칠·팔 / 이·사·오·구는 받침 없음
UNIT_BATCHIM = {"%p": False, "%": False, "개월": "ㄹ", "영업일": "ㄹ", "일": "ㄹ", "원": True, "만원": True, "천원": True,
                "억원": True, "백만원": True, "만좌": False, "회": False, "인": True, "계좌": False, "년": True,
                "월": "ㄹ", "세": False, "가지": False, "개": False, "매": False, "택1": "ㄹ", "택2": False}
PAIRS = [("이에요", "예요"), ("으로", "로"), ("이", "가"), ("은", "는"), ("을", "를"), ("과", "와")]


def final_sound(v):
    """값을 읽을 때 마지막 음절의 받침: False(없음) · True(있음) · 'ㄹ'. 날짜 등 모르면 None."""
    for unit, b in sorted(UNIT_BATCHIM.items(), key=lambda x: -len(x[0])):
        if v.endswith(unit):
            return b
    if re.search(r"\d$", v) and not re.search(r"\d{4}\.\d", v):
        d = v[-1]
        return "ㄹ" if d in "178" else (d in BATCHIM_DIGIT)
    return None


def fix_particles(t, vals):
    """슬롯 바로 뒤 조사를 값의 받침에 맞춘다(«{S1}가» → 값이 «3개월»이면 «이»)."""
    def sub(m):
        sid, part = m.group(1), m.group(2)
        b = final_sound(vals.get(sid, ""))
        if b is None:
            return m.group(0)
        for with_b, without_b in PAIRS:
            if part in (with_b, without_b):
                if (with_b, without_b) == ("으로", "로"):
                    good = "로" if b in (False, "ㄹ") else "으로"
                else:
                    good = with_b if b else without_b
                return "{" + sid + "}" + good
        return m.group(0)
    return re.sub(r"\{([A-Z]\d+)\}(이에요|예요|으로|로|이|가|은|는|을|를|과|와)(?![가-힣])", sub, t)


def check(raw, u, slots, src, keep=()):
    """반환: (채운 결과 dict 또는 None, 실패 이유 목록, 참고 메모 목록)"""
    errs, notes = [], []
    s = raw.strip()
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None, ["JSON 을 찾지 못함"], notes
    if m.group(0) != s:
        notes.append("JSON 앞뒤에 다른 글·코드펜스")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return None, [f"JSON 파싱 실패: {e}"], notes
    keys = ["title", "summary"] if u["kind"] == "card" else ["summary"]
    if any(not isinstance(obj.get(k), str) or not obj[k].strip() for k in keys):
        return None, [f"필드 누락: {keys}"], notes
    vals = {x["id"]: x["value"] for x in slots}
    out = {}
    for k in keys:
        t = obj[k].strip()
        for sid in re.findall(r"\{([A-Z]\d+)\}", t):
            if sid not in vals:
                errs.append(f"{k}: 없는 슬롯 {{{sid}}}")
        for sid, unit in re.findall(r"\{([A-Z]\d+)\}\s?(%p|%|개월|영업일|만원|천원|원|회|일|년)", t):
            if sid in vals and not re.search(r"\d$", vals[sid]):
                errs.append(f"{k}: 단위가 붙은 슬롯 {{{sid}}}={vals[sid]} 뒤에 «{unit}» 를 또 붙임")
        if re.search(r"(니다|한다|이다)[.]?(\s|$)", t):
            notes.append(f"{k}: 해요체가 아닌 문장")
        bare = re.sub(r"\{[A-Z]\d+\}", "", t)
        for term in keep:  # 상품명 속 숫자(«별별통장2»)
            bare = bare.replace(term, "")
        digits = re.findall(r"\d[\d.,]*", bare)
        if digits:
            errs.append(f"{k}: 슬롯 밖 숫자 {digits}")
        fixed = fix_particles(t, vals)
        if fixed != t:
            notes.append(f"{k}: 조사 보정")
        out[k] = re.sub(r"\{([A-Z]\d+)\}", lambda mm: vals.get(mm.group(1), mm.group(0)), fixed)
    lim = LIMITS[u["kind"]]
    summ = out["summary"]
    n_sent = len([x for x in re.split(r"(?<=[.!?])\s+", summ) if x.strip()])
    if n_sent > lim["sents"]:
        errs.append(f"문장 수 {n_sent} > {lim['sents']}")
    if len(summ) > lim["chars"]:
        errs.append(f"길이 {len(summ)}자 > {lim['chars']}자")
    if u["kind"] == "card" and len(out["title"]) > lim["title"]:
        errs.append(f"제목 {len(out['title'])}자 > {lim['title']}자")
    bad = [w for k in keys for w in re.findall(BANNED, out[k]) if w not in src]
    if bad:
        errs.append(f"금지어 {bad}")
    return out, errs, notes


def load(key):
    import torch
    import transformers
    from transformers import AutoTokenizer, BitsAndBytesConfig
    path = MODELS[key]()
    tok = AutoTokenizer.from_pretrained(path, trust_remote_code=(key == "exaone"))
    if key == "gemma26":
        sys.path.insert(0, str(HERE.parent / "m3eval"))
        from run_m3 import load_experts_nf4
        return tok, load_experts_nf4(path).eval(), path, "전문가 NF4 · 나머지 fp16"
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    cls = (getattr(transformers, "AutoModelForMultimodalLM", None) if key.startswith("gemma") else None) \
        or transformers.AutoModelForCausalLM
    model = cls.from_pretrained(path, quantization_config=quant, dtype=torch.float16, device_map={"": 0},
                                attn_implementation="sdpa", trust_remote_code=(key == "exaone")).eval()
    return tok, model, path, "NF4 4비트(double quant) · fp16 연산"


def generate(tok, model, messages, max_new):
    import torch
    enc = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True,
                                  return_tensors="pt", enable_thinking=False).to(model.device)
    t0 = time.perf_counter()
    with torch.inference_mode():
        seq = model.generate(**enc, max_new_tokens=max_new, do_sample=False, temperature=None, top_p=None,
                             top_k=None, repetition_penalty=1.0)
    new = seq[0, enc["input_ids"].shape[1]:]
    text = tok.decode(new, skip_special_tokens=True)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return text, int(enc["input_ids"].shape[1]), int(new.shape[0]), time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--units", required=True, nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--max-new-tokens", type=int, default=256)
    a = ap.parse_args()

    import torch
    datas = [json.loads(Path(f).read_text(encoding="utf-8")) for f in a.units]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    tok, model, path, quant = load(a.model)
    load_s = time.perf_counter() - t0
    print(f"[{a.model}] 로드 {load_s:.0f}s · GPU {torch.cuda.memory_allocated() / 2**30:.1f}GB", flush=True)

    rows = []
    todo = [(d, u) for d in datas for u in d["units"] if not a.only or f"{d['key']}:{u['id']}" in a.only or u["id"] in a.only]
    for data, u in todo:
        by_id = {x["id"]: x for x in data["units"]}
        src, sections, slots, user = build_unit(u, by_id, data["params"])
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        attempts = []
        for n in range(2):
            raw, n_in, n_out, sec = generate(tok, model, msgs, a.max_new_tokens)
            filled, errs, notes = check(raw, u, slots, src, re.findall(r"\S*\d\S*", data["product"]))
            attempts.append({"raw": raw, "filled": filled, "errors": errs, "notes": notes,
                             "input_tokens": n_in, "output_tokens": n_out, "seconds": round(sec, 1),
                             "hit_max_new_tokens": n_out >= a.max_new_tokens})
            if filled and not errs:
                break
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "검사에서 걸렸습니다: " + "; ".join(errs)
                      + "\n규칙을 지켜 같은 형식의 JSON 하나만 다시 출력하세요."}]
        last = attempts[-1]
        ok = bool(last["filled"]) and not last["errors"]
        row = {"model": a.model, "product": data["key"], "product_name": data["product"], "id": u["id"], "kind": u["kind"], "track": u.get("track"), "name": u.get("name"),
               "status": "통과" if ok else "폐기", "retried": len(attempts) > 1,
               "result": last["filled"] if ok else None, "summary_sections": sections,
               "slots": slots, "human": u.get("human"), "attempts": attempts}
        rows.append(row)
        r = row["result"] or {}
        print(json.dumps({"id": f"{data['key']}:{u['id']}", "status": row["status"], "retried": row["retried"],
                          "out_tokens": [x["output_tokens"] for x in attempts],
                          "sec": round(sum(x["seconds"] for x in attempts), 1),
                          "text": (r.get("title", "") + " | " if r.get("title") else "") + r.get("summary", ""),
                          "errors": last["errors"]}, ensure_ascii=False), flush=True)

    (out_dir / f"{a.model}.json").write_text(json.dumps({
        "model": a.model, "path": path, "quantization": quant, "load_seconds": round(load_s),
        "settings": {"do_sample": False, "enable_thinking": False, "max_new_tokens": a.max_new_tokens,
                     "retries": 1, "limits": LIMITS},
        "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1),
        "system_prompt": SYSTEM, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    n_ok = sum(r["status"] == "통과" for r in rows)
    print(f"[{a.model}] 끝 · 통과 {n_ok}/{len(rows)} · 재시도 {sum(r['retried'] for r in rows)}", flush=True)


if __name__ == "__main__":
    main()
