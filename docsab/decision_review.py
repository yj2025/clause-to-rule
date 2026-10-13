"""정보배치 의사결정표 × 상품 원문 매칭 검토 페이지 (2026-10-13).

    python3 docsab/decision_review.py "KB 중소기업재직자 우대저축"   → docs/정보배치_원문매칭_<상품>.html

docs/예금요약_서비스_정보배치_의사결정표.xlsx 의 «기획_배치결정표» 49개 정보 항목마다 그 상품의 원문 조항을 붙인다.
- 항목 이름이 팀 요약입력 key 이름과 같으면 그 key 의 주 · 참고 · 공통 조항 (key 매칭)
- 아니면 상품 조항 · 공통약관에서 낱말로 찾는다 (낱말 검색 — 자동이라 확인 필요)
보류 항목은 결정 · 프롬프트 입력 · 메모를 빈칸으로 두고 검토자가 채운다(브라우저 저장 · CSV/JSON 내려받기).
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

DOCS = Path("/workspace/personal_workplace_CHO/docs")
XLSX = DOCS / "예금요약_서비스_정보배치_의사결정표.xlsx"
SRC = DOCS / "요약입력_상품별.json"
TEMPLATE = Path(__file__).parent / "decision_review_template.html"

# key 가 없는 15개 항목 — 낱말 검색 (조항 제목 + 본문)
KW = {
    "서비스 상태": r"혁신금융|서비스 종료|판매 ?중단|판매 ?종료",
    "저축·납입 방법": r"저축방법|납입방법|자유적립|정액적립|월 ?저축",
    "추가입금·추가납입": r"추가 ?입금|추가 ?납입|추가 ?저축",
    "판매한도·모집한도·조기종료": r"판매한도|모집한도|한도 ?소진|조기 ?종료",
    "이자 계산·결산 방식": r"이자 ?계산|결산|원가일|평균잔액",
    "만기 후 이율·처리": r"만기 ?후|만기후",
    "특별중도해지": r"특별 ?중도 ?해지",
    "가입·거래 채널": r"거래방법|가입방법|가입 ?채널|인터넷뱅킹|스타뱅킹|비대면 ?(가입|채널)|(영업점|지점)(에서|을 통해|,)",   # «영업점에 게시한 금리»는 빼려고 좁힘
    "연결·연계·출금계좌": r"연결계좌|연계계좌|출금계좌|입금계좌|모계좌",
    "자동이체·자동납부": r"자동이체|자동납부",
    "금융소비자 권리·분쟁·자료열람": r"분쟁|자료열람|민원|청약철회|위법계약",
    "예금자보호": r"예금자 ?보호|예금보험",
    "휴면예금·출연": r"휴면|출연|서민금융",
    "압류·가압류·상계·지급제한": r"압류|가압류|상계|지급 ?제한|지급정지",
    "통장·증서 발급": r"통장 ?발급|증서|통장 ?교부|무통장",
}


def load_items():
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)   # 서식이 깨져 있어 read_only 로만 열린다
    rows = [r for r in wb["기획_배치결정표"].iter_rows(values_only=True) if any(v not in (None, "") for v in r)]
    hdr = rows[2]
    return [{k: ("" if v is None else str(v)) for k, v in zip(hdr, r)} for r in rows[3:]]


def sec_view(s, role, how):
    return {"id": s["section_id"], "doc": s["doc_type"], "where": f"{s.get('document', '')} {s.get('path', '')}".strip(),
            "title": s.get("title") or "", "text": s["text"].strip(), "role": role, "how": how}


def main(product):
    packet = next(p for p in json.loads(SRC.read_text("utf-8"))["packets"] if p["product_name"] == product)
    secs = {s["section_id"]: s for s in packet["sections"] + packet.get("common_sections", [])}
    by_name = {k["name"]: k for k in packet["keys"]}
    missing = {(m["name"] if isinstance(m, dict) else m) for m in packet.get("missing_keys", [])}
    used = set()
    out = []
    for it in load_items():
        name = it["정보 항목"]
        matched, how = [], "없음"
        if name in by_name:
            k = by_name[name]
            for role, ids in (("주", k["primary_section_ids"]), ("참고", k["reference_section_ids"]), ("공통", k.get("common_section_ids", []))):
                for i in ids:
                    if i in secs:
                        matched.append(sec_view(secs[i], role, "key")); used.add(i)
            how = "key 매칭" if matched else "key 있음 · 원문 없음"
        elif name in KW:
            pat = re.compile(KW[name])
            for s in secs.values():
                if pat.search((s.get("title") or "") + " " + s["text"]):
                    matched.append(sec_view(s, "검색", "keyword"))
            how = "낱말 검색" if matched else "없음"
        if name in missing and not matched:
            how = "팀 요약입력: 원문 없음"
        order = {"특약": 0, "상품설명서": 1, "동의서": 2, "공통약관": 3}
        matched.sort(key=lambda m: (order.get(m["doc"], 9), m["id"]))
        out.append({
            "area": it["영역"], "name": name, "meaning": it["무엇을 뜻하는지"],
            "first_out": it["최초 출력 추천"], "first_how": it["최초 출력에서의 표현 방식"],
            "ask": it["추가 질문 추천"], "ask_when": it["질문이 필요한 상황"], "detail": it["상세보기"],
            "reason": it["추천 이유"], "basis": it["밀접한 참고 근거"],
            "decision": it["팀 최종 결정"], "prompt": it["프론트 제외한 내용 프롬프트 입력"],
            "how": how, "sections": matched,
        })
    unused = [sec_view(s, "-", "-") for s in packet["sections"] if s["section_id"] not in used
              and not any(m["id"] == s["section_id"] for o in out for m in o["sections"])]
    data = {"product": product, "category": packet.get("product_category"), "url": packet.get("product_url"),
            "items": out, "unused": unused,
            "source": {"xlsx": XLSX.name, "packets": SRC.name}}
    html = TEMPLATE.read_text("utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    safe = re.sub(r"[^\w가-힣]+", "", product)
    path = DOCS / f"정보배치_원문매칭_{safe}.html"
    path.write_text(html, "utf-8")
    hold = [o for o in out if o["decision"] == "보류"]
    print(f"{product}: 항목 {len(out)} · 원문 붙음 {sum(1 for o in out if o['sections'])} "
          f"(key {sum(o['how'] == 'key 매칭' for o in out)} · 낱말 {sum(o['how'] == '낱말 검색' for o in out)}) · "
          f"보류 {len(hold)} 중 원문 {sum(1 for o in hold if o['sections'])} · 어느 항목에도 안 붙은 조항 {len(unused)} → {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "KB 중소기업재직자 우대저축")
