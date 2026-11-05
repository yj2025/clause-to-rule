#!/usr/bin/env python3
"""runs/<이름>/*.json → 카드요약 모델 비교 엑셀 (2026-10-15 v2: 상품설명서 5종 · 모델링 가능여부 시트).

    python make_xlsx.py runs/v2 units review_v2.json "<docs 경로>/카드요약_모델비교.xlsx"

review_v2.json: {"verdict": {모델키: 한 줄 평가}, "memo": [[모델키, 상품키, ID, 문장 일부, 문제, 유형], ...], "memo_note": "..."}
v1(글로벌스타 1건) 엑셀은 make_xlsx_v1.py.
"""
import json
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.workbook.properties import CalcProperties

ORDER = ["gemma31", "gemma26", "gemma12", "qwen", "exaone"]
NAMES = {"qwen": "Qwen3-8B", "exaone": "EXAONE 3.5 7.8B", "gemma12": "Gemma 4 12B",
         "gemma26": "Gemma 4 26B-A4B", "gemma31": "Gemma 4 31B"}
PORDER = ["gstar", "kbstar_term", "mine", "byul2", "general"]

run_dir, units_dir, review_path, out = sys.argv[1:5]
products = {p: json.loads((Path(units_dir) / f"{p}.json").read_text(encoding="utf-8")) for p in PORDER}
runs = {k: json.loads((Path(run_dir) / f"{k}.json").read_text(encoding="utf-8"))
        for k in ORDER if (Path(run_dir) / f"{k}.json").exists()}
rows = {k: {(r["product"], r["id"]): r for r in v["rows"]} for k, v in runs.items()}
review = json.loads(Path(review_path).read_text(encoding="utf-8")) if Path(review_path).exists() else {}

F = "Arial"
base = Font(name=F, size=10)
blue = Font(name=F, size=10, color="0000FF")
hdr_fill = PatternFill("solid", fgColor="1F3864")
hdr_font = Font(name=F, size=10, bold=True, color="FFFFFF")
sub_fill = PatternFill("solid", fgColor="D9E1F2")
hu_fill = PatternFill("solid", fgColor="F2F2F2")
ng_fill = PatternFill("solid", fgColor="FDE9E7")
ok_fill = PatternFill("solid", fgColor="E2EFDA")
thin = Side(style="thin", color="D9D9D9")
box = Border(top=thin, bottom=thin, left=thin, right=thin)
wrap = Alignment(wrap_text=True, vertical="top")


def header(ws, r, vals, widths=None):
    for c, v in enumerate(vals, 1):
        x = ws.cell(r, c, v)
        x.font, x.fill, x.border = hdr_font, hdr_fill, box
        x.alignment = Alignment(wrap_text=True, vertical="center")
    for c, w in enumerate(widths or [], 1):
        ws.column_dimensions[ws.cell(1, c).column_letter].width = w


def body(ws, r, vals, font=base, fill=None):
    for c, v in enumerate(vals, 1):
        x = ws.cell(r, c, v)
        x.font, x.alignment, x.border = font, wrap, box
        if fill:
            x.fill = fill


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(name=F, size=13, bold=True)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = base


def label(u):
    return f"{u['track']} 카드" if u["kind"] == "card" else f"약관 요약 · {u['name']}"


wb = Workbook()

# ---------- 전체결과 (긴 표, 요약 시트 수식이 참조) ----------
ws5 = wb.active
ws5.title = "전체결과"
cols = ["상품", "ID", "구분", "모델", "상태", "재시도", "제목", "요약(슬롯 채운 뒤)", "글자 수", "검사 실패 이유(모든 시도)",
        "참고 메모", "출력 토큰(시도별)", "생성 시간(초)", "근거 섹션"]
header(ws5, 1, cols, [16, 6, 16, 16, 7, 7, 24, 60, 7, 40, 24, 11, 10, 34])
r = 2
for p in PORDER:
    for u in products[p]["units"]:
        for k in runs:
            x = rows[k].get((p, u["id"]))
            if not x:
                continue
            res = x["result"] or {}
            vals = [products[p]["product"], u["id"], label(u), NAMES[k], x["status"], "예" if x["retried"] else "",
                    res.get("title", ""),
                    res.get("summary", "") if res else "(폐기) " + x["attempts"][-1]["raw"][:200], None,
                    "; ".join(e for a in x["attempts"] for e in a["errors"]),
                    "; ".join(x["attempts"][-1]["notes"]),
                    "/".join(str(a["output_tokens"]) for a in x["attempts"]),
                    round(sum(a["seconds"] for a in x["attempts"]), 1), " · ".join(x["summary_sections"])]
            body(ws5, r, vals, fill=ng_fill if x["status"] == "폐기" else None)
            ws5.cell(r, 9, f'=IF(E{r}="통과",LEN(H{r}),"")').font = base
            r += 1
last = r - 1
ws5.freeze_panes = "E2"
ws5.auto_filter.ref = f"A1:N{last}"


def R(col):
    return f"전체결과!${col}$2:${col}${last}"


# ---------- 요약 ----------
ws = wb.create_sheet("요약", 0)
n_units = sum(len(products[p]["units"]) for p in PORDER)
n_cards = sum(u["kind"] == "card" for p in PORDER for u in products[p]["units"])
title(ws, "카드 요약 모델 비교 v2 · 상품설명서 5종 (2026-10-15, 검수 전 초안)",
      f"상품 5종 · 모델당 {n_units}건(«꼭 확인할 조건» 카드 {n_cards}장 + «약관 요약» {n_units - n_cards}항목) · 원문: docs/1014_새작업/*.pdf")
header(ws, 4, ["모델", "통과", "폐기", "통과율", "재시도", "검토메모 건수", "생성 시간 합계(초)", "건당 평균(초)", "로드(초)",
               "GPU 최대(GB)", "양자화", "한 줄 평가"], [18, 7, 7, 8, 8, 10, 12, 10, 9, 10, 24, 58])
for i, k in enumerate(runs):
    rr = 5 + i
    v = runs[k]
    body(ws, rr, [NAMES[k]])
    m = R("D")
    ws.cell(rr, 2, f'=COUNTIFS({m},A{rr},{R("E")},"통과")')
    ws.cell(rr, 3, f'=COUNTIFS({m},A{rr},{R("E")},"폐기")')
    ws.cell(rr, 4, f"=IF(B{rr}+C{rr}=0,0,B{rr}/(B{rr}+C{rr}))")
    ws.cell(rr, 5, f'=COUNTIFS({m},A{rr},{R("F")},"예")')
    ws.cell(rr, 6, f"=COUNTIFS(검토메모!$A$2:$A$500,A{rr})")
    ws.cell(rr, 7, f"=SUMIFS({R('M')},{m},A{rr})")
    ws.cell(rr, 8, f"=IF(B{rr}+C{rr}=0,0,G{rr}/(B{rr}+C{rr}))")
    for c, val in [(9, v["load_seconds"]), (10, v["peak_gpu_gb"]), (11, v["quantization"]),
                   (12, review.get("verdict", {}).get(k, ""))]:
        ws.cell(rr, c, val)
    for c in range(1, 13):
        x = ws.cell(rr, c)
        x.border, x.alignment = box, wrap
        x.font = blue if c in (9, 10) else base
    ws.cell(rr, 4).number_format = "0.0%"
    ws.cell(rr, 8).number_format = "0.0"
ws.cell(5, 9).comment = Comment("로드 시간·GPU 최대는 runs/v2/<모델>.json 실행 기록에서 옮긴 값(파란 글씨)", "M3")

r0 = 5 + len(runs) + 2
ws.cell(r0, 1, "상품별 통과 수").font = Font(name=F, size=11, bold=True)
header(ws, r0 + 1, ["상품", "건수"] + [NAMES[k] for k in runs])
for j, p in enumerate(PORDER):
    rr = r0 + 2 + j
    body(ws, rr, [products[p]["product"], len(products[p]["units"])] + [None] * len(runs))
    for i, k in enumerate(runs):
        x = ws.cell(rr, 3 + i, f'=COUNTIFS({R("A")},$A{rr},{R("D")},"{NAMES[k]}",{R("E")},"통과")')
        x.border, x.font = box, base

r1 = r0 + 2 + len(PORDER) + 1
notes = [
    "설정: greedy · thinking 끔 · max_new_tokens 256 · 실패 시 1회 다시 쓰게 하고 또 실패하면 폐기",
    "검사: 슬롯 밖 숫자 · 없는 슬롯 · 단위 중복 · 길이(카드 110자·2문장, 항목 150자·3문장, 제목 20자) · 금지어(grade.py N09)",
    "v2 보완(10-15): 표 값에 단위를 붙여 슬롯화(«연 0.1%») · 슬롯 뒤 조사 코드 보정 · 목록 번호·상품명 속 숫자 제외 · "
    "«원문이 단정하면 단정형»·«조건·예외 빠뜨리지 않기»·«카드 종류에 맞는 제목» 규칙 추가",
    "계산값({C…})은 규칙 엔진이 계산: 처음 가입 최대금리(글로벌스타), 12개월 계약 6개월 뒤 중도해지 금리(적금·정기예금)",
    "주의: «통과»는 형식 검사 통과일 뿐. 내용 오류는 «검토메모» 시트 참고(AI 검토, 사람 검수 전)",
    "근거 원문은 AI 가 PDF에서 C안 카드 기준으로 손으로 잘라 넣음(model/M3/cardsum/units/*.json). 실제 서비스는 DB·섹션 분류가 대신해야 함",
    "안전장치: 모델마다 memguard.sh (컨테이너 anon 22G·작업 14G·PSI 50%×5)",
    "다음 개선(검토에서 나온 것): ① 단위 중복 검사에 월·세·매·가지·개, 슬롯 앞 «연» 추가(«11월월», «연 연 2.0%») "
    "② 해요체를 참고 메모 → 실패로 올리거나 «~습니다»→«~어요» 후처리 ③ 내용이 많은 카드(우대금리·쿠폰)는 길이 한도를 따로 "
    "④ 슬롯 오배치는 검사로 못 잡음 → 사람 검수 유지, 섹션과 무관한 슬롯 줄이기",
]
for i, t in enumerate(notes):
    ws.cell(r1 + i, 1, t).font = base

# ---------- 비교 (넓은 표) ----------
ws2 = wb.create_sheet("비교", 1)
header(ws2, 1, ["상품", "ID", "구분", "출처", "C안 (사람, 글로벌스타만)"] + [NAMES[k] for k in runs],
       [14, 6, 16, 22, 34] + [36] * len(runs))
rr = 2
for p in PORDER:
    for u in products[p]["units"]:
        hu = u.get("human") or {}
        vals = [products[p]["product"], u["id"], label(u), u["ref"],
                ((hu.get("title", "") + "\n") if hu.get("title") else "") + hu.get("summary", "")]
        for k in runs:
            x = rows[k].get((p, u["id"]))
            res = x and x["result"]
            vals.append((((res.get("title", "") + "\n") if res.get("title") else "") + res["summary"]) if res else "(폐기)")
        body(ws2, rr, vals)
        ws2.cell(rr, 5).fill = hu_fill
        for j, k in enumerate(runs):
            x = rows[k].get((p, u["id"]))
            if x and x["status"] == "폐기":
                ws2.cell(rr, 6 + j).fill = ng_fill
        rr += 1
ws2.freeze_panes = "F2"
ws2.auto_filter.ref = f"A1:{ws2.cell(1, 5 + len(runs)).column_letter}{rr - 1}"

# ---------- 검토메모 ----------
ws3 = wb.create_sheet("검토메모", 2)
header(ws3, 1, ["모델", "상품", "ID", "문장(일부)", "문제", "유형"], [16, 14, 6, 46, 52, 14])
memo = review.get("memo", [])
pname = {p: products[p]["product"] for p in PORDER}
for i, (k, p, uid, s, prob, kind) in enumerate(memo):
    body(ws3, 2 + i, [NAMES[k], pname[p], uid, s, prob, kind])
ws3.cell(3 + len(memo), 1, review.get("memo_note", "")).font = base
ws3.auto_filter.ref = f"A1:F{max(2, 1 + len(memo))}"
ws3.freeze_panes = "A2"

# ---------- 모델링 가능여부 ----------
ws4 = wb.create_sheet("모델링 가능여부", 3)
title(ws4, "모델링(파인튜닝) 가능 여부 · 이 서버 기준 (2026-10-15)",
      "환경: Tesla V100-SXM2 32GB (bf16 미지원 → fp16) · 컨테이너 RAM 28GiB(넘으면 SSH 까지 멈춤) · CPU 4코어 · "
      "peft 0.20 / bitsandbytes 0.49 / transformers 5.18 설치됨 (trl 없음, 없어도 됨)")
header(ws4, 4, ["모델", "구조", "추론(이 작업)", "추론 GPU 최대(GB)", "QLoRA 파인튜닝", "근거·위험", "권장 용도"],
       [18, 16, 12, 12, 14, 64, 34])
feas = [
    ("gemma31", "dense 31B", "가능",
     "NF4 4비트 가중치만 약 19GB. 학습용 여유 약 13GB → 짧은 입력(이 작업 ~1.5k 토큰)·배치 1·그래디언트 체크포인팅이면 될 수도 있으나 "
     "느리고 GPU 메모리 초과 위험. 로딩 때 디스크 캐시 압박 큼(가중치 59GB)", "빠듯함", "지금처럼 프롬프트로 초안 생성(교사 모델)"),
    ("gemma26", "MoE 26B(활성 4B)", "가능",
     "전문가 가중치가 nn.Parameter 라 bitsandbytes 4비트가 안 먹어 직접 만든 NF4 로더로 올림 → 표준 LoRA(peft)가 전문가 층을 지원하지 않음. "
     "어텐션 층만 LoRA 는 이론상 가능하나 검증 안 됨", "사실상 어려움", "추론만"),
    ("gemma12", "dense 12B", "가능",
     "NF4 약 8GB → LoRA·옵티마이저·활성값을 넣어도 32GB 안에 여유. 팀에서 QLoRA 해 본 적 있음(M2 clause-to-rule results/sys_qlora_paired.json, Dev50)",
     "가능", "파인튜닝 1순위 후보(31B 결과를 배우는 학생 모델)"),
    ("qwen", "dense 8B", "가능", "NF4 약 6GB → 무난. 다만 이번 작업에서 해요체·슬롯 규칙을 못 지켜 기본기가 약함", "가능", "비교·기준선"),
    ("exaone", "dense 7.8B", "가능",
     "가중치가 fp32 30GB 라 로딩 때 디스크 캐시 압박(10-14 안전장치에 한 번 걸림). 원격 코드를 transformers 5.18 에 맞게 고친 사본 필요",
     "가능(번거로움)", "권장 안 함"),
]
for i, (k, arch, inf, why, ft, use) in enumerate(feas):
    gpu = runs[k]["peak_gpu_gb"] if k in runs else ""
    body(ws4, 5 + i, [NAMES[k], arch, inf, gpu, ft, why, use])
    ws4.cell(5 + i, 4).font = blue
    ws4.cell(5 + i, 5).fill = ok_fill if ft.startswith("가능") else (ng_fill if "어려움" in ft else sub_fill)
r2 = 5 + len(feas) + 1
blocks = [
    ("결론", [
        "지금은 파인튜닝보다 «31B 프롬프트 + 코드 검사·보정 + 사람 검수»가 맞음.",
        "이유 1) 학습 데이터가 없음 — 사람이 검수한 정답 문장은 C안 15건(상품 1개)뿐. 최소 수백 쌍 필요.",
        "이유 2) 31B 의 남은 오류는 대부분 단위·조사처럼 코드로 고칠 수 있는 것 — 학습으로 고칠 문제가 아님(v2 에서 코드 보정 넣음).",
        "이유 3) 31B 는 학습 없이도 형식 규칙을 거의 다 지킴. 프롬프트·검사로 올릴 여지가 아직 남아 있음.",
    ]),
    ("파인튜닝이 의미 있어지는 시점 · 순서", [
        "1. 31B 로 상품 여러 개의 카드·요약 초안 생성 (지금 파이프라인 그대로)",
        "2. 사람 검수 → 고친 문장을 정답으로 저장 (서비스 흐름의 «사람 검수 후 summaries 저장»이 곧 학습 데이터)",
        "3. 정답이 수백 쌍 모이면 Gemma 4 12B 를 QLoRA 로 학습(31B → 12B 증류). 입력 = 근거 섹션 + 슬롯, 출력 = 검수된 문장",
        "4. 같은 검사(슬롯 밖 숫자·길이·금지어) + 검토메모 기준으로 31B 와 비교해 따라오면 12B 로 교체 → 속도·GPU 절반 이하",
    ]),
    ("학습 시 주의", [
        "컨테이너 RAM 28GiB: 학습 스크립트도 memguard.sh 로 띄울 것(로딩·데이터 준비 중 RAM 초과 시 SSH 불통).",
        "V100 은 bf16 미지원 → fp16 + 손실 스케일링. FlashAttention-2 미지원(sdpa).",
        "숫자는 학습 데이터에서도 슬롯 표기로 둬야 함(모델이 숫자를 외워 쓰지 않게).",
    ]),
]
for head, lines in blocks:
    ws4.cell(r2, 1, head).font = Font(name=F, size=11, bold=True)
    r2 += 1
    for t in lines:
        ws4.cell(r2, 1, t).font = base
        r2 += 1
    r2 += 1

wb.calculation = CalcProperties(fullCalcOnLoad=True)  # LibreOffice 없음 → 엑셀이 열 때 계산
wb.save(out)
print("저장:", out, "· 전체결과", last - 1, "행")
