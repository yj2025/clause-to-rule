"""M2 저장소(clause-to-rule)에서 run_batch.py 가 쓰던 함수 셋을 옮겨 온 사본 (2026-11-05).

- build      ← docsab/run_merged.py   상품 하나의 특약 · 상품설명서 조항을 요약 입력 글로 만든다
- parse_json ← run_local_v2.py        모델 출력에서 JSON 본문을 읽는다 (_json_body 포함)

원본: https://github.com/yj2025/clause-to-rule (cyj/lora). 내용은 고치지 않았다.
"""
import json
from pathlib import Path

# 팀 요약 입력 (상품별 key · 조항 묶음). run_batch.py --src 로 바꿀 수 있다.
SRC = Path(__file__).resolve().parent.parent.parent / "docs" / "요약입력_상품별.json"


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


def _json_body(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if len(s.split("```")) > 1 else s
        s = s[s.index("\n") + 1:] if "\n" in s else s
    i, j = s.find("{"), s.rfind("}")
    return None if i < 0 or j < i else s[i:j + 1]


def parse_json(raw):
    """코드펜스와 앞뒤 군더더기를 걷어내고 JSON 을 읽는다. 실패하면 None."""
    body = _json_body(raw)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None
