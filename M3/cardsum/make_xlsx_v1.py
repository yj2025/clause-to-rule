#!/usr/bin/env python3
"""runs/gstar/*.json → 카드요약 모델 비교 엑셀 (2026-10-15)."""
import json, sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.comments import Comment

ORDER = ["gemma31", "gemma26", "gemma12", "qwen", "exaone"]
NAMES = {"qwen": "Qwen3-8B", "exaone": "EXAONE 3.5 7.8B", "gemma12": "Gemma 4 12B",
         "gemma26": "Gemma 4 26B-A4B", "gemma31": "Gemma 4 31B"}
run_dir, units_path, out = sys.argv[1:4]
units = json.loads(Path(units_path).read_text(encoding="utf-8"))
runs = {k: json.loads((Path(run_dir) / f"{k}.json").read_text(encoding="utf-8")) for k in ORDER}
rows = {k: {r["id"]: r for r in v["rows"]} for k, v in runs.items()}

F = "Arial"; base = Font(name=F, size=10); bold = Font(name=F, size=10, bold=True)
hdr_fill = PatternFill("solid", fgColor="1F3864"); hdr_font = Font(name=F, size=10, bold=True, color="FFFFFF")
hu_fill = PatternFill("solid", fgColor="F2F2F2"); ng_fill = PatternFill("solid", fgColor="FDE9E7")
blue = Font(name=F, size=10, color="0000FF")
thin = Side(style="thin", color="D9D9D9"); box = Border(top=thin, bottom=thin, left=thin, right=thin)
wrap = Alignment(wrap_text=True, vertical="top")

def header(ws, r, vals, widths=None):
    for c, v in enumerate(vals, 1):
        x = ws.cell(r, c, v); x.font = hdr_font; x.fill = hdr_fill; x.alignment = Alignment(wrap_text=True, vertical="center"); x.border = box
    if widths:
        for c, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(1, c).column_letter].width = w

def body(ws, r, vals, font=base, fill=None):
    for c, v in enumerate(vals, 1):
        x = ws.cell(r, c, v); x.font = font; x.alignment = wrap; x.border = box
        if fill: x.fill = fill

def label(u):
    return f"{u['track']} 카드" if u["kind"] == "card" else f"약관 요약 · {u['name']}"

wb = Workbook()
# ---------- 전체결과 (긴 표, 요약 시트 수식이 참조) ----------
ws3 = wb.active; ws3.title = "전체결과"
cols = ["ID", "구분", "모델", "상태", "재시도", "제목", "요약(슬롯 채운 뒤)", "글자 수", "검사 실패 이유(모든 시도)", "참고 메모", "출력 토큰(시도별)", "생성 시간(초)", "근거 섹션"]
header(ws3, 1, cols, [6, 16, 16, 7, 7, 24, 60, 7, 40, 24, 11, 10, 34])
r = 2
for u in units["units"]:
    for k in ORDER:
        x = rows[k][u["id"]]; res = x["result"] or {}
        errs = "; ".join(e for a in x["attempts"] for e in a["errors"])
        vals = [u["id"], label(u), NAMES[k], x["status"], "예" if x["retried"] else "", res.get("title", ""),
                res.get("summary", "") if res else "(폐기) " + x["attempts"][-1]["raw"][:200], None, errs,
                "; ".join(x["attempts"][-1]["notes"]), "/".join(str(a["output_tokens"]) for a in x["attempts"]),
                round(sum(a["seconds"] for a in x["attempts"]), 1), " · ".join(x["summary_sections"])]
        body(ws3, r, vals, fill=ng_fill if x["status"] == "폐기" else None)
        ws3.cell(r, 8, f'=IF(D{r}="통과",LEN(G{r}),"")').font = base
        r += 1
last = r - 1
ws3.freeze_panes = "D2"; ws3.auto_filter.ref = f"A1:M{last}"

# ---------- 요약 ----------
ws = wb.create_sheet("요약", 0)
ws["A1"] = "카드 요약 모델 비교 · KB Global Star 적금 (2026-10-14 시험, 검수 전 초안)"; ws["A1"].font = Font(name=F, size=13, bold=True)
ws["A2"] = "원문: docs/1014_새작업/글로벌스타적금설명서(다국어).pdf 1~6쪽 · C안 «꼭 확인할 조건» 카드 10장 + «약관 요약» 5항목 = 모델당 15건"; ws["A2"].font = base
header(ws, 4, ["모델", "통과", "폐기", "통과율", "재시도", "생성 시간 합계(초)", "로드(초)", "GPU 최대(GB)", "양자화", "한 줄 평가"],
       [18, 7, 7, 8, 8, 12, 9, 10, 26, 60])
verdict = {"gemma31": "가장 나음. 재시도 0. 표 값 단위 누락·조사 오류 소수",
           "gemma26": "31B와 비슷. 해요체 1회 이탈, 중도해지 단정 약화",
           "gemma12": "형식은 지키나 슬롯을 엉뚱한 자리에 씀(I1·I4)",
           "qwen": "15건 모두 «~습니다»체, 슬롯 오배치·조건 혼동 많음",
           "exaone": "매번 코드펜스, 슬롯 규칙 위반 — 사용 어려움"}
for i, k in enumerate(ORDER):
    rr = 5 + i; v = runs[k]
    body(ws, rr, [NAMES[k]])
    rng = f"전체결과!$C$2:$C${last}"
    ws.cell(rr, 2, f'=COUNTIFS({rng},A{rr},전체결과!$D$2:$D${last},"통과")')
    ws.cell(rr, 3, f'=COUNTIFS({rng},A{rr},전체결과!$D$2:$D${last},"폐기")')
    ws.cell(rr, 4, f"=IF(B{rr}+C{rr}=0,0,B{rr}/(B{rr}+C{rr}))")
    ws.cell(rr, 5, f'=COUNTIFS({rng},A{rr},전체결과!$E$2:$E${last},"예")')
    ws.cell(rr, 6, f"=SUMIFS(전체결과!$L$2:$L${last},{rng},A{rr})")
    for c, val in [(7, v["load_seconds"]), (8, v["peak_gpu_gb"]), (9, v["quantization"]), (10, verdict[k])]:
        ws.cell(rr, c, val)
    for c in range(1, 11):
        x = ws.cell(rr, c); x.border = box; x.alignment = wrap
        x.font = blue if c in (7, 8) else base
    ws.cell(rr, 4).number_format = "0.0%"
ws.cell(5, 7).comment = Comment("로드 시간·GPU 최대는 runs/gstar/<모델>.json 실행 기록에서 옮긴 값(파란 글씨)", "M3")
n = 5 + len(ORDER) + 1
notes = ["설정: greedy · thinking 끔 · max_new_tokens 256 · 실패 시 1회 다시 쓰게 하고 또 실패하면 폐기",
         "검사: 슬롯 밖 숫자 · 없는 슬롯 · 단위 중복 · 길이(카드 110자·2문장, 항목 150자·3문장, 제목 20자) · 금지어(grade.py N09 목록)",
         "숫자는 모델이 {S1} 같은 슬롯으로만 쓰고 코드가 값을 채움. {C…} 계산값(첫 가입 최대금리 5.0%, 6개월 중도해지 0.6%)은 규칙 엔진이 계산",
         "주의: «통과»는 형식 검사 통과일 뿐. 슬롯을 의미상 틀린 자리에 쓴 오류는 검사로 못 잡음 → «검토메모» 시트 참고",
         "안전장치: 모델마다 memguard.sh (컨테이너 anon 22G·작업 14G·PSI 50%×5). 최대 anon 7.8G"]
for i, t in enumerate(notes):
    ws.cell(n + i, 1, t).font = base

# ---------- 비교 (넓은 표) ----------
ws2 = wb.create_sheet("비교", 1)
h = ["ID", "구분", "출처", "C안 (사람)"] + [NAMES[k] for k in ORDER]
header(ws2, 1, h, [6, 16, 22, 38] + [38] * len(ORDER))
for i, u in enumerate(units["units"]):
    rr = 2 + i; hu = u["human"]
    vals = [u["id"], label(u), u["ref"], (hu.get("title", "") + "\n" if hu.get("title") else "") + hu["summary"]]
    for k in ORDER:
        x = rows[k][u["id"]]; res = x["result"]
        vals.append(((res.get("title", "") + "\n" if res.get("title") else "") + res["summary"]) if res else "(폐기)")
    body(ws2, rr, vals)
    ws2.cell(rr, 4).fill = hu_fill
    for j, k in enumerate(ORDER):
        if rows[k][u["id"]]["status"] == "폐기":
            ws2.cell(rr, 5 + j).fill = ng_fill
ws2.freeze_panes = "E2"

# ---------- 검토메모 ----------
ws4 = wb.create_sheet("검토메모", 2)
header(ws4, 1, ["모델", "ID", "문장(일부)", "문제", "유형"], [16, 6, 48, 52, 14])
memo = [
 ("gemma12", "I1", "매월 12개월부터 1일까지 1천원 이상 50만원 이하를", "슬롯을 엉뚱한 자리에 씀. 원문은 «매월 1일부터 마지막일까지 자유롭게»", "슬롯 오배치"),
 ("gemma12", "I4", "각각 6개월 이상 또는 1일 실적을 채우면", "«1일»은 실적 기간 시작일. 해외송금 3회 조건이 빠짐", "슬롯 오배치"),
 ("gemma26", "I1", "매월 12개월 동안 1일부터 마지막 날까지", "«매월 12개월 동안» 어색(계약기간 12개월과 섞임)", "슬롯 오배치"),
 ("qwen", "L1", "최저 6개월입니다", "최저금리 자리에 기간 슬롯을 씀. «1개월 이내»도 원문은 «1개월 미만»", "슬롯 오배치"),
 ("qwen", "L4", "3개월 초과 30% 이내는 기본금리 X 30%, 0.1 이하는 0.1% 적용", "구간이 뒤섞여 뜻이 틀림", "사실 오류"),
 ("qwen", "B1", "1영업일~3영업일 내 급여이체 50만원 이상, 또는 20만원 이상 카드결제 시", "급여 인정 기준을 카드결제 조건으로 잘못 연결", "사실 오류"),
 ("qwen", "R3", "만기일에는 자동 해지됩니다", "«KB스타뱅킹에서 가입한 계좌» 조건이 빠져 모든 계좌가 자동 해지되는 것처럼 읽힘", "조건 누락"),
 ("gemma12", "L2", "금리우대쿠폰의 우대금리가 적용되지 않아요", "우대금리(급여·카드·송금)도 중도해지 시 미적용인데 쿠폰만 말함", "조건 누락"),
 ("gemma26", "L2", "금리우대쿠폰의 우대금리를 받을 수 없으니", "위와 같음 — 우대금리 자체 미적용이 빠짐", "조건 누락"),
 ("gemma12", "R3", "만기일에 자동으로 해지되어 출금계좌로 입금돼요", "법적 지급제한 시 자동 해지 안 됨(예외)이 빠짐", "조건 누락"),
 ("gemma12", "I5", "중도해지하면 우대금리가 적용되지 않아요…", "만기후금리(3개월 초과 연 0.1%)가 빠짐", "조건 누락"),
 ("gemma31", "L1", "1개월 미만 유지 시 0.1의 금리를", "표 값에 단위 없음 → «연 0.1%»여야 함(슬롯 값에 단위가 없어서 생김)", "단위·조사"),
 ("gemma31", "L4", "3개월가 지나면 0.1가 적용돼요", "조사(«3개월이») · 단위(«연 0.1%») 오류", "단위·조사"),
 ("gemma26", "I3", "최대 금리는 연 5.0%이에요", "«5.0%예요»가 맞음 (31B 같은 문장도 동일)", "단위·조사"),
 ("gemma12", "L3", "중도해지로 처리될 수 있어요", "원문은 «중도해지로 처리»(단정). «될 수 있어요»로 약해짐 (26B L3·I5, 12B I5 동일)", "단정 약화"),
 ("gemma26", "B3", "제목: 비과세 혜택 적용 시 주의사항", "혜택 카드인데 제목이 주의사항 — 트랙과 안 맞음", "제목"),
 ("gemma26", "I5", "…적용되지 않으며, … 적용됩니다.", "해요체가 아님(검사에서는 참고 메모로만 표시)", "문체"),
]
for i, m in enumerate(memo):
    k, uid, s, p, t = m
    body(ws4, 2 + i, [NAMES[k], uid, s, p, t])
ws4.cell(2 + len(memo) + 1, 1, "검토: AI 가 문장을 읽고 원문과 대조해 적은 메모(사람 검수 전). 전수 검토가 아니라 눈에 띈 것 위주.").font = base
ws4.auto_filter.ref = f"A1:E{1 + len(memo)}"

for s in wb.worksheets:
    s.sheet_view.zoomScale = 100
from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)  # LibreOffice 없음 → 엑셀이 열 때 계산
wb.save(out); print("저장:", out)
