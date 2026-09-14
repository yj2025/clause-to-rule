"""정답 판정 기준을 팀에 묻는 문서.

    /workspace/.venv/bin/python make_decision.py

폰트는 brief.py 머리말 참고. 숫자는 손으로 박는다.
"""

from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
OUT = HERE / "M2-2_정답판정기준_결정요청.pdf"

INK = (26, 24, 22)
MUTED = (92, 88, 82)
FAINT = (139, 133, 125)
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
        self.add_font("nk", "", str(FONTS / "NotoSansKR-VF.ttf"))
        self.add_font("nk", "B", str(FONTS / "NotoSansKR-Bold.ttf"))
        self.set_margins(M, 18, M)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-14)
        self.set_font("nk", "", 7.5)
        self.set_text_color(*FAINT)
        self.cell(TW, 5, f"정답 판정 기준 — 결정 요청 · {self.page_no()}", align="R")

    def h1(self, text, sub=None):
        self.set_font("nk", "B", 16)
        self.set_text_color(*INK)
        self.multi_cell(TW, 8, text)
        if sub:
            self.set_font("nk", "", 9.5)
            self.set_text_color(*MUTED)
            self.multi_cell(TW, 5.4, sub)
        self.ln(1.5)
        y = self.get_y()
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.7)
        self.line(M, y, M + 24, y)
        self.ln(4)

    def q(self, n, text):
        if self.get_y() > 226:
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
        self.multi_cell(TW - 11, 6.6, text)
        self.ln(1.5)

    def p(self, text, size=9.7, color=MUTED, indent=0):
        self.set_x(M + indent)
        self.set_font("nk", "", size)
        self.set_text_color(*color)
        self.multi_cell(TW - indent, 5.6, text, markdown=True)
        self.ln(2)

    def case(self, label, lines):
        need = 9 + len(lines) * 4.9
        if self.get_y() + need > 258:
            self.add_page()
        y0 = self.get_y()
        h = need
        self.set_fill_color(*SUNK)
        self.rect(M + 11, y0, TW - 11, h, style="F")
        self.set_xy(M + 15, y0 + 2.4)
        self.set_font("nk", "B", 7.6)
        self.set_text_color(*ACCENT)
        self.cell(TW - 19, 4, label)
        self.set_font("nk", "", 8.6)
        yy = y0 + 7.2
        for k, v in lines:
            self.set_xy(M + 15, yy)
            self.set_text_color(*FAINT)
            self.cell(16, 4.7, k)
            self.set_text_color(*INK)
            self.multi_cell(TW - 35, 4.7, v, markdown=True)
            yy = self.get_y()
        self.set_y(y0 + h + 3)

    def options(self, items):
        for tag, text, tone in items:
            if self.get_y() > 262:
                self.add_page()
            self.set_x(M + 11)
            self.set_font("nk", "B", 9.4)
            self.set_text_color(*tone)
            self.cell(13, 5.4, tag)
            self.set_font("nk", "", 9.4)
            self.set_text_color(*MUTED)
            self.multi_cell(TW - 24, 5.4, text, markdown=True)
            self.ln(1)
        self.ln(2)


def build():
    d = Doc()
    d.add_page()

    d.set_font("nk", "", 8.5)
    d.set_text_color(*ACCENT)
    d.cell(TW, 6, "MODEL 2 · 결정 요청")
    d.ln(9)
    d.h1("정답 데이터를 어떤 기준으로 판정할까요",
         "약관 46조문의 정답을 만들 때, 「옮길 수 있다」와 「옮길 수 없다」의 "
         "경계를 어디에 둘지 정해 주십시오.")

    d.p("조문을 조건식으로 옮기다 보면 **절반만 옮겨지는 경우**가 대부분입니다. "
        "그때 옮겨지는 절반만 쓸지, 아니면 「옮길 수 없음」으로 선언할지를 "
        "가르는 기준이 필요합니다. 지금은 제가 임시로 정해 두었고 "
        "**그 기준 위에서 모든 지표가 계산됩니다.** 기준이 바뀌면 "
        "카탈로그 확장 우선순위도 같이 바뀝니다.")

    d.p("아래 세 가지만 정해 주시면 나머지 46조문은 그 기준으로 일관되게 "
        "적용하겠습니다. 회의 한 번이면 됩니다.", color=INK)

    # ── 1 ────────────────────────────────────────────────
    d.q(1, "근사를 어디까지 허용할까요")
    d.p("지금 임시 기준은 **「오차가 고객에게 유리하면 허용, 불리하면 금지」** 입니다.",
        indent=11)
    d.case("허용한 사례 — 수수료 면제", [
        ("조문", "급여이체 | 건별 50만원 이상의 급여이체 실적이 있는 경우"),
        ("옮긴 것", "급여이체가 있으면 (금액 조건은 빠짐)"),
        ("효과", "수수료 면제"),
        ("결과", "50만원 미만 이체도 면제를 받습니다. 은행이 손해를 봅니다."),
    ])
    d.case("금지한 사례 — 거래중지", [
        ("조문", "잔액 1만원 미만이며 1년 이상 입출금 거래가 없는 계좌"),
        ("옮긴 것", "잔액 1만원 미만 (무거래 요건은 빠짐)"),
        ("효과", "거래 제한"),
        ("결과", "잔액이 적은 모든 정상 계좌가 막힙니다. 고객이 손해를 봅니다."),
    ])
    d.options([
        ("가", "**지금 기준을 유지합니다.** 방향으로 가릅니다. "
               "옮길 수 있는 것이 많아지고 카탈로그 확장 부담이 줍니다.", OK),
        ("나", "**방향과 무관하게 정확해야 합니다.** 조문의 모든 요건을 "
               "옮길 수 없으면 「옮길 수 없음」입니다. 규제 보고나 감사 대응이 "
               "목적이면 이쪽입니다. 대신 표현 불가가 크게 늘고 "
               "카탈로그를 더 넓혀야 합니다.", BAD),
    ])

    # ── 2 ────────────────────────────────────────────────
    d.q(2, "「무엇이 필요하다」는 요건을 불이익으로 볼까요")
    d.p("지금은 불이익으로 보고 **조건이 완전해야** 한다고 두었습니다.", indent=11)
    d.case("해당 사례 — 계약해지방법", [
        ("조문", "인터넷뱅킹·스타뱅킹으로 해지할 때 본인명의 입출금 계좌가 필요합니다"),
        ("옮긴 것", "채널이 인터넷 또는 모바일이면 → 계좌 보유 요구"),
        ("물음", "이건 고객에게 불이익인가요, 아니면 절차 안내인가요?"),
    ])
    d.options([
        ("가", "**불이익입니다.** 요건을 못 갖추면 해지를 못 하니 실질적 제약입니다. "
               "조건이 완전해야 하고, 불완전하면 「옮길 수 없음」입니다.", OK),
        ("나", "**절차 안내입니다.** 금리나 수수료를 바꾸지 않으므로 "
               "근사를 허용해도 됩니다.", MUTED),
    ])

    # ── 3 ────────────────────────────────────────────────
    d.q(3, "다른 개념으로 옮긴 것은 어떻게 볼까요")
    d.p("1번 기준은 **빠뜨린 것**을 다룹니다. 그런데 **다른 것으로 바꿔 옮긴** "
        "경우는 다루지 못합니다. 이건 방향의 문제가 아닙니다.", indent=11)
    d.case("해당 사례 — 가맹점결제 실적", [
        ("조문", "KB국민은행이 지급한 카드 가맹점대금 입금실적이 있는 경우"),
        ("뜻", "가맹점 사업자가 카드 대금을 **받는** 것"),
        ("옮긴 것", "입금이 있으면 (일반 입금)"),
        ("문제", "주체와 성격이 다릅니다. 월급 입금도 가맹점결제로 셉니다."),
    ])
    d.options([
        ("가", "**허용하지 않습니다.** 딱 맞는 이름이 없으면 「옮길 수 없음」입니다. "
               "정확하지만 표현 불가가 늘어납니다.", OK),
        ("나", "**주석을 달고 허용합니다.** 근사한 곳을 정답에 기록하고 "
               "넘어갑니다. 지금 상태입니다.", MUTED),
        ("다", "**사안마다 봅니다.** 기준을 세우지 않고 검토 때 판단합니다. "
               "46조문을 사람이 다 봐야 합니다.", MUTED),
    ])

    # ── 왜 중요한가 ───────────────────────────────────────
    d.add_page()
    d.h1("이 결정이 무엇을 바꾸나요")

    d.p("**1번이 가장 큽니다.** 지금 정답은 46조문 중 30조문에 "
        "「옮길 수 없음」 규칙을 두고 있습니다. 1번을 「나」로 바꾸면 "
        "그 수가 늘고, 카탈로그를 더 넓혀야 합니다. 「가」를 유지하면 "
        "지금 우선순위가 그대로 섭니다.", color=INK)

    d.p("**모든 지표가 이 기준 위에서 계산됩니다.** 조문의 뜻을 재는 지표 "
        "여섯 개가 정답 데이터를 기준으로 삼습니다. 기준이 바뀌면 "
        "과거 라운드를 전부 다시 채점합니다 — 결과 파일을 보관하고 있어 "
        "GPU 없이 하루면 됩니다.")

    d.p("**정답 46조문은 제가 만든 초안이고 사람 검토 전입니다.** "
        "제가 초안을 쓰고 제가 승인하면 검증이 아닙니다. "
        "기계로 확인할 수 있는 것은 전부 확인했고 실제 오류 셋을 고쳤습니다. "
        "남은 것은 위 세 가지 같은 **판단**입니다.")

    d.ln(2)
    d.set_font("nk", "B", 11)
    d.set_text_color(*INK)
    d.cell(TW, 7, "결정 뒤에 제가 할 일")
    d.ln(9)
    d.p("정한 기준을 글로 적고 46조문에 일관되게 적용합니다. "
        "바뀐 판정으로 과거 라운드를 전부 다시 채점하고, "
        "카탈로그 확장 우선순위를 다시 계산합니다. "
        "그 뒤에 확장 항목을 정하는 회의를 한 번 더 하면 됩니다.")

    d.ln(3)
    d.set_draw_color(*RULE)
    d.set_line_width(0.3)
    d.line(M, d.get_y(), M + TW, d.get_y())
    d.ln(3)
    d.set_font("nk", "", 8)
    d.set_text_color(*FAINT)
    d.multi_cell(TW, 4.8,
                 "근거 · model/M2-2/DECISIONS.md (지금 기준과 그 적용) · "
                 "data/gold/ (정답 46조문, 각 판단의 이유가 note 에 있음)\n"
                 "조문별 검토 도구와 카탈로그 확장 안건은 따로 있습니다.")

    d.output(str(OUT))
    print(f"만들었습니다 → {OUT.name}  ({OUT.stat().st_size / 1024:.0f} KB, {d.page_no()}쪽)")


if __name__ == "__main__":
    build()
