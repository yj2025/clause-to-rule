"""카탈로그 확장을 팀에 묻는 문서.

    /workspace/.venv/bin/python make_catalog_decision.py

조판은 make_decision.py 와 같다. 폰트는 brief.py 머리말 참고.
숫자는 손으로 박는다 — 문서는 특정 시점의 사진이다.
"""

from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
OUT = HERE / "M2-2_카탈로그확장_결정요청.pdf"

INK = (26, 24, 22)
MUTED = (66, 62, 56)
FAINT = (104, 98, 90)
ACCENT = (32, 76, 110)
RULE = (214, 209, 202)
SUNK = (242, 240, 236)
OK = (43, 102, 60)
BAD = (154, 46, 36)

W, M = 210.0, 20.0
TW = W - 2 * M


class Doc(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(True, margin=20)
        self.add_font("nk", "", str(FONTS / "KR-Regular.ttf"))
        self.add_font("nk", "B", str(FONTS / "KR-Bold.ttf"))
        self.set_margins(M, 18, M)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-14)
        self.set_font("nk", "", 7.5)
        self.set_text_color(*FAINT)
        self.cell(TW, 5, f"카탈로그 확장 — 결정 요청 · {self.page_no()}", align="R")

    def h1(self, text, sub=None):
        self.set_font("nk", "B", 16)
        self.set_text_color(*INK)
        self.multi_cell(TW, 8, text, new_x="LMARGIN")
        if sub:
            self.set_font("nk", "", 9.5)
            self.set_text_color(*MUTED)
            self.multi_cell(TW, 5.4, sub, new_x="LMARGIN")
        self.ln(1.5)
        y = self.get_y()
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.7)
        self.line(M, y, M + 24, y)
        self.ln(4)

    def q(self, n, text):
        if self.get_y() > 224:
            self.add_page()
        self.ln(2)
        y = self.get_y()
        self.set_fill_color(*ACCENT)
        self.rect(M, y + 0.6, 7, 7, style="F")
        self.set_xy(M, y + 1.2)
        self.set_font("nk", "B", 8)
        self.set_text_color(255, 255, 255)
        self.cell(7, 6, str(n), align="C")
        self.set_xy(M + 11, y)
        self.set_font("nk", "B", 12.5)
        self.set_text_color(*INK)
        self.multi_cell(TW - 11, 6.6, text, new_x="LMARGIN")
        self.ln(1.5)

    def p(self, text, size=9.7, color=MUTED, indent=0):
        self.set_x(M + indent)
        self.set_font("nk", "", size)
        self.set_text_color(*color)
        self.multi_cell(TW - indent, 5.6, text, markdown=True, new_x="LMARGIN")
        self.ln(2)

    def case(self, label, lines, indent=11):
        need = 9 + len(lines) * 4.9
        if self.get_y() + need > 256:
            self.add_page()
        y0 = self.get_y()
        self.set_fill_color(*SUNK)
        self.rect(M + indent, y0, TW - indent, need, style="F")
        self.set_xy(M + indent + 4, y0 + 2.4)
        self.set_font("nk", "B", 7.6)
        self.set_text_color(*ACCENT)
        self.cell(TW - indent - 8, 4, label)
        self.set_font("nk", "", 8.6)
        yy = y0 + 7.2
        for k, v in lines:
            self.set_xy(M + indent + 4, yy)
            self.set_text_color(*FAINT)
            self.cell(17, 4.7, k)
            self.set_text_color(*INK)
            self.multi_cell(TW - indent - 25, 4.7, v, markdown=True, new_x="LMARGIN")
            yy = self.get_y()
        self.set_y(y0 + need + 3)

    def options(self, items):
        for tag, text, tone in items:
            self.set_x(M + 11)
            if self.get_y() > 260:
                self.add_page()
            self.set_x(M + 11)
            self.set_font("nk", "B", 9.4)
            self.set_text_color(*tone)
            self.cell(13, 5.4, tag)
            self.set_font("nk", "", 9.4)
            self.set_text_color(*MUTED)
            self.multi_cell(TW - 24, 5.4, text, markdown=True, new_x="LMARGIN")
            self.ln(1)
        self.ln(2)

    def table(self, head, rows, widths, aligns=None, hi=None):
        aligns = aligns or ["L"] * len(head)
        hi = hi or set()
        if self.get_y() + 8 + len(rows) * 6 > 256:
            self.add_page()
        self.set_font("nk", "B", 7.8)
        self.set_text_color(*FAINT)
        for t, w, a in zip(head, widths, aligns):
            self.cell(w, 6, t, align=a)
        self.ln(6)
        self.set_draw_color(*RULE)
        self.set_line_width(0.3)
        self.line(M, self.get_y(), M + sum(widths), self.get_y())
        self.ln(1.2)
        for i, row in enumerate(rows):
            bold = i in hi
            for j, (t, w, a) in enumerate(zip(row, widths, aligns)):
                self.set_font("nk", "B" if bold or j == 0 else "", 9.0)
                self.set_text_color(*(INK if bold else MUTED))
                self.cell(w, 6, t, align=a)
            self.ln(6)
            self.set_draw_color(238, 235, 230)
            self.line(M, self.get_y() - 0.6, M + sum(widths), self.get_y() - 0.6)
        self.ln(3)


def build():
    d = Doc()
    d.add_page()

    d.set_font("nk", "", 8.5)
    d.set_text_color(*ACCENT)
    d.cell(TW, 6, "MODEL 2 · 결정 요청")
    d.ln(9)
    d.h1("조건식에 쓸 어휘를 어디까지 넓힐까요",
         "약관 46조문 중 32조문이 「옮길 수 없음」입니다. 지문으로는 못 풉니다 — "
         "여섯 라운드로 확인했습니다. 무엇을 더할지 정해 주십시오.")

    d.p("지금 쓸 수 있는 어휘는 변수 17개, 이벤트 11개, 효과 8개입니다. "
        "못 옮기는 것은 대개 **효과** 쪽입니다 — 조건은 표현되는데 "
        "그래서 무엇을 하라는지를 담을 자리가 없습니다.")

    d.case("지금 무엇이 일어나는가 — 실물", [
        ("조문", "▪ 담보제공 불가능"),
        ("생성물", "조건 없음 · 효과 「예금 자격 상실」"),
        ("결과", "**모든 고객이 예금 자격을 잃습니다.**"),
        ("이유", "「특정 거래만 금지」를 담을 효과가 없어 가장 가까운 것으로 밀고, "
                 "담보제공을 가리킬 변수도 없어 조건을 못 붙입니다."),
    ], indent=0)
    d.p("이 모양이 여덟 라운드에서 **19회** 나왔고 그중 9회는 형식 검사 "
        "다섯 개를 전부 통과했습니다. 뜻만 정반대입니다.")

    # ── 1 ────────────────────────────────────────────────
    d.q(1, "어느 항목부터 넣을까요")
    d.p("「풀린다」를 **그 조문의 「옮길 수 없음」 규칙이 하나도 안 남는다**로 "
        "정의하고 다시 셌습니다. 한 조문이 두 가지를 동시에 요구하면 "
        "하나만 넣어서는 아무것도 안 풀립니다.", indent=11)
    d.table(
        ["넣는 항목", "누적 조문", "남는 조문"],
        [["제휴서비스 제공 효과", "4", "28"],
         ["＋ 면제 잔여횟수 이월", "6", "26"],
         ["＋ 명의 유형 변수", "8", "24"],
         ["＋ 최종거래일 변수", "10", "22"],
         ["＋ 거래유형별 금지 효과", "11", "21"],
         ["＋ 명의변경 이벤트", "14", "18"]],
        [78, 36, 36], ["L", "R", "R"], hi={3, 5})
    d.p("**다섯째와 여섯째를 같이 넣으면 3조문이 한꺼번에 열립니다.** "
        "거래중지·양도담보 계열이 그 둘을 함께 요구하기 때문입니다. "
        "묶음의 값이 항목의 합보다 큽니다.", indent=11)
    d.options([
        ("가", "**넷까지.** 10조문이 열립니다. 각 항목이 단독으로도 값을 냅니다.", OK),
        ("나", "**여섯까지.** 14조문이 열립니다. 다섯째·여섯째는 **같이** 넣어야 "
               "값이 납니다. 모든 고객을 탈락시키는 오류도 여기서 사라집니다.", OK),
        ("다", "**우선 하나만.** 제휴서비스 제공 효과입니다. 4조문이 열리고 "
               "io 명세가 가장 단순합니다. 시범으로 해 보고 나머지를 정합니다.", MUTED),
    ])

    d.p("항목별 실물은 다음 쪽에 있습니다.")

    # ── 항목별 근거 ──────────────────────────────────────
    d.add_page()
    d.h1("항목별로 무엇이 막혀 있나")
    for name, n, lines in [
        ("제휴서비스 제공 효과", "4조문", [
            ("조문", "NE능률 교육서비스 — 가입 고객에게 무료체험 제공 (고객별 1회)"),
            ("막힌 것", "금리도 수수료도 금액한도도 아닌 혜택을 담을 효과가 없음"),
            ("덧붙임", "제공기간·유의사항·이행책임 조문도 여기 딸려 있습니다"),
        ]),
        ("면제 잔여횟수 이월", "2조문", [
            ("조문", "수수료면제 잔여횟수는 이월되지 않습니다"),
            ("막힌 것", "잔여 횟수를 가리킬 변수도, 이월 금지 효과도 없음"),
        ]),
        ("명의 유형 변수", "2조문", [
            ("조문", "실명의 개인 ※ 개인사업자 및 서류미제출 임의단체, 공동명의 가입 불가"),
            ("막힌 것", "가입자가 개인인지 사업자인지 단체인지 가리킬 변수가 없음"),
        ]),
        ("최종거래일 변수", "2조문", [
            ("조문", "만기일 또는 최종거래일 이후 5년 이내 해지하지 않을 경우 휴면예금 출연"),
            ("막힌 것", "「마지막 거래가 언제였나」를 가리킬 변수가 없음"),
        ]),
        ("거래유형별 금지 효과", "1조문 · 묶으면 3", [
            ("조문", "담보제공 불가능 / 양도·상속에 의한 명의변경 불가능"),
            ("막힌 것", "특정 거래만 금지하는 효과가 없어 예금 자격 상실로 밀림"),
        ]),
        ("명의변경 이벤트", "0조문 · 묶으면 3", [
            ("조문", "무거래기간 산정: 입출금 거래 **또는 명의변경 거래** 최종 발생일"),
            ("막힌 것", "명의변경을 거래로 셀 수 없어 무거래 판정이 틀림"),
        ]),
    ]:
        if d.get_y() > 222:
            d.add_page()
        d.set_font("nk", "B", 10.5)
        d.set_text_color(*INK)
        d.cell(TW - 34, 6.5, name)
        d.set_font("nk", "", 8.4)
        d.set_text_color(*ACCENT)
        d.cell(34, 6.5, f"단독 {n}", align="R")
        d.ln(7)
        d.case("", lines, indent=0)

    # ── 2·3·4 ────────────────────────────────────────────
    d.add_page()
    d.h1("어휘 말고 형식도 정할 것이 셋 있습니다",
         "항목을 더하는 것과 별개로, 조건식이 표현할 수 있는 모양 자체를 넓히는 문제입니다.")

    d.q(2, "조건에 금액을 붙일 수 있게 할까요")
    d.case("막힌 것", [
        ("조문", "급여이체 | **건별 50만원 이상**의 급여이체 실적이 있는 경우"),
        ("지금", "급여이체가 있으면 (금액 조건을 못 붙임)"),
        ("범위", "급여이체 실적 인정기준 네 줄이 전부 여기 걸립니다"),
    ])
    d.options([
        ("가", "**건별 금액 조건을 넣습니다.** 「50만원 이상인 건이 있으면」을 "
               "표현할 수 있게 됩니다.", OK),
        ("나", "**넣지 않습니다.** 대신 그 조문들을 「옮길 수 없음」으로 둡니다.", MUTED),
    ])

    d.q(3, "이벤트에 속성을 붙일까요")
    d.case("막힌 것", [
        ("조문 A", "공과금이체 실적 — 아파트관리비·지로·CMS·펌뱅킹 자동납부 "
                   "(**카드결제분 제외**)"),
        ("조문 B", "급여이체 **계약에 의해** 입금되는 건만 인정"),
        ("지금", "자동이체가 있으면 / 급여이체가 있으면 (단서를 못 붙임)"),
    ])
    d.options([
        ("가", "**속성을 붙입니다.** 이벤트에 경로·계약 여부 같은 하위 구분을 둡니다. "
               "io 명세가 가장 크게 바뀌는 선택입니다.", OK),
        ("나", "**이벤트를 쪼갭니다.** 「계약에 의한 급여이체」를 별도 이벤트로 "
               "만듭니다. 명세는 단순하지만 이벤트 수가 늡니다.", MUTED),
        ("다", "**넣지 않습니다.** 인정기준 단서는 옮기지 않습니다.", MUTED),
    ])

    d.q(4, "누가 어느 범위까지 만들까요")
    d.p("어휘를 넓히면 **실행기와 해석기도 같이 고쳐야 합니다.** "
        "새 효과는 최종 금리 계산에 어떻게 들어갈지, 새 변수는 고객 데이터의 "
        "어느 필드에서 올지가 정해져야 합니다.", indent=11)
    d.options([
        ("가", "**io 명세를 먼저 합의하고 제가 구현합니다.** 이름과 필수 키, "
               "값의 범위만 정해 주시면 실행기·해석기·정답 데이터를 맞추겠습니다.", OK),
        ("나", "**데이터 쪽과 같이 정합니다.** 새 변수가 실제 고객 데이터에 "
               "있는지부터 확인이 필요하면 이쪽입니다.", MUTED),
    ])

    # ── 마무리 ───────────────────────────────────────────
    d.add_page()
    d.h1("정하기 전에 알아 두실 것")

    d.p("**정답 데이터 판정 기준이 먼저입니다.** 「옮길 수 있다」의 경계를 어디에 "
        "두느냐에 따라 위 우선순위가 바뀝니다. 그 문서를 따로 드렸습니다.", color=INK)

    d.p("**실제로 한 번 움직였습니다.** 9/14 에 조문 여섯 개를 검토하면서 "
        "「제공기간」이 제휴서비스 쪽으로 옮겨져 그 항목이 3조문에서 **4조문**이 "
        "됐습니다. 같은 검토에서 **해지 경로 변수는 후보에서 뺐습니다** — "
        "거래 경로는 규칙이 아니라 절차라고 정해졌기 때문입니다. "
        "나머지 40조문을 검토하면 순위가 더 움직일 수 있습니다.")

    d.p("**옛 우선순위는 틀렸습니다.** 이전 안건은 「그 항목을 언급한 조문 수」로 "
        "순위를 매기고 있었습니다. 출금 이벤트가 2순위였는데 실제로 넣어 보니 "
        "**푼 조문이 0개**였습니다 — 그 조문들이 다른 것도 같이 요구했기 "
        "때문입니다. 꼴찌였던 제휴서비스가 1등입니다.")

    d.p("**확장은 지문 문제도 같이 풉니다.** 예시를 하나 더한 라운드에서 "
        "규칙을 낸 회차만으로 정규화해 재면 카탈로그 준수가 12.9p 올랐습니다. "
        "쓸 수 있는 이름이 늘면 이름 쓰는 법 전반이 좋아집니다.")

    d.p("**모델은 병목이 아닙니다.** 형식 검사를 세 번 모두 못 넘은 26조문을 "
        "원인별로 가르면 카탈로그가 16조문, 채점기 결함이 7조문, "
        "모델이 못 하는 것이 3조문입니다.")

    d.ln(2)
    d.set_font("nk", "B", 11)
    d.set_text_color(*INK)
    d.cell(TW, 7, "결정 뒤에 제가 할 일")
    d.ln(9)
    d.p("정한 항목의 io 명세를 카탈로그에 넣고, 실행기와 해석기를 맞추고, "
        "정답 46조문에서 해당 규칙을 「옮길 수 없음」에서 정상으로 바꿉니다. "
        "그다음 라운드를 돌려 실제로 열리는지 확인합니다. "
        "항목 하나에 라운드 하나씩, 판정선은 이미 확정돼 있습니다.")

    d.ln(3)
    d.set_draw_color(*RULE)
    d.set_line_width(0.3)
    d.line(M, d.get_y(), M + TW, d.get_y())
    d.ln(3)
    d.set_font("nk", "", 8)
    d.set_text_color(*FAINT)
    d.multi_cell(TW, 4.8,
                 "근거 · model/M2-2/CATALOG_PROPOSAL.md · blockers.py (이 셈을 하는 도구)\n"
                 "정답 데이터의 각 판단과 이유는 data/gold/ 의 note 에 있습니다.")

    d.output(str(OUT))
    print(f"만들었습니다 → {OUT.name}  ({OUT.stat().st_size / 1024:.0f} KB, {d.page_no()}쪽)")


if __name__ == "__main__":
    build()
