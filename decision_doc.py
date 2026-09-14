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

    d.p("아래 **두 가지**를 정해 주시면 나머지 조문은 그 기준으로 일관되게 "
        "적용하겠습니다. 뒤에 **구조 질문 셋**이 더 있습니다 — "
        "판단이 아니라 「이것을 시스템 어디에 둘까」의 문제입니다.", color=INK)

    d.ln(1)
    d.set_font("nk", "B", 11)
    d.set_text_color(*INK)
    d.cell(TW, 7, "먼저, 이미 정해진 것")
    d.ln(8)
    d.p("2026-09-14 에 조문 여섯 개를 직접 보시고 원칙 둘을 정하셨습니다. "
        "나머지 조문에 그대로 적용하고 있습니다.")
    d.p("**하나. 거래·해지 경로는 규칙이 아니라 절차입니다.** "
        "「영업점 또는 스타뱅킹으로 해지 가능」은 어디서 할 수 있는지 알려 주는 "
        "안내이고 고객을 가르는 조건이 아닙니다. "
        "해지 경로 변수는 **어휘 확장 후보에서 뺐습니다** — 넓혀도 여기서 "
        "나올 규칙이 없습니다.", indent=6)
    d.p("**둘. 효과의 값에 자유 문자열을 쓰지 않습니다.** "
        "정답 초안이 「본인명의의 입출금이자유로운예금 계좌」라는 한국어 문장을 "
        "값으로 넣고 있었습니다. 실행기가 읽을 수 없는 값입니다. "
        "그 규칙은 「옮길 수 없음」으로 바꿨고, **검사 기준도 "
        "「실행기가 읽을 수 있나」로 고쳤습니다** — 길이도 언어도 "
        "대소문자도 상관없습니다.", indent=6)
    d.p("둘째 결정으로 형식 검사 하나가 엄해졌습니다. 카탈로그 준수율이 "
        "과거 라운드에서 최대 6.5%p 내려갑니다. **모델이 나빠진 것이 아니라 "
        "검사를 엄하게 만든 것입니다.**", indent=6, color=INK)

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
    d.q(2, "다른 개념으로 옮긴 것은 어떻게 볼까요")
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

    # ── 구조 질문 셋 ──────────────────────────────────────
    d.add_page()
    d.h1("구조 질문 셋", "원칙으로는 안 가려집니다. 「이것을 어디에 둘까」의 문제입니다.")
    d.p("나머지 35조문을 정해진 원칙으로 훑었더니 어긋나는 것이 없었습니다. "
        "다만 아래 셋은 원칙의 문제가 아니라 **설계 결정**이라 남겨 두었습니다. "
        "지금 정하지 않으면 나중에 바꿀 때 채점기와 정답을 같이 고쳐야 합니다.")

    d.q(3, "조문의 범위를 어디까지 볼까요")
    d.case("해당 사례 — 자료열람요구권", [
        ("조문", "은행은 법령·제3자의 이익 침해 등의 사유가 있는 경우 "
                 "자료 열람을 제한하거나 거절할 수 있습니다"),
        ("모양", "조건이 있고 효과가 있습니다 — 형식만 보면 규칙입니다"),
        ("지금", "빈 배열. 금리·수수료·가입자격·한도 어디에도 안 닿습니다"),
    ])
    d.options([
        ("가", "**예금 조건만 다룹니다.** 금리·수수료·자격·한도에 닿지 않으면 "
               "옮길 대상이 아닙니다. 지금 상태입니다.", OK),
        ("나", "**약관의 모든 규칙을 다룹니다.** 열람 제한도 규칙이므로 "
               "「옮길 수 없음」입니다. 어휘를 훨씬 많이 넓혀야 합니다.", MUTED),
    ])

    d.q(4, "기본금리를 상품 설정에 둘까요, 규칙으로 둘까요")
    d.case("해당 사례 — 기본금리 조문 둘", [
        ("조문", "▪ 연 0.1% (KB Young Youth) · ▪ 연 0.10% (KB국민ONE)"),
        ("지금", "상품 설정 파일의 base_rate 0.1 로 두고 조문은 빈 배열"),
        ("이유", "해석기가 최종 금리를 계산할 때 출발값으로 깔아 줍니다"),
    ])
    d.options([
        ("가", "**상품 설정에 둡니다.** 지금 상태입니다. 조문마다 같은 값을 "
               "되풀이하지 않아도 됩니다.", OK),
        ("나", "**규칙으로 둡니다.** 조문에 적힌 것은 조문에서 나와야 한다면 "
               "이쪽입니다. 대신 조건 없이 항상 적용되는 규칙이 생깁니다.", MUTED),
    ])

    d.q(5, "금리 상한을 어디에 둘까요")
    d.case("해당 사례 — 최종금리 범위", [
        ("조문", "▪ 최저 연 0.1% ~ 최고 연 2.0%  ※ 최고금리는 기본금리와 "
                 "특별금리를 합한 금리"),
        ("지금", "합산 설정(aggregation)의 상한으로 두고 조문은 빈 배열"),
        ("이유", "기본 0.1 + 특별 1.9 = 2.0 을 서술한 문장이지 새 제약이 아닙니다"),
    ])
    d.options([
        ("가", "**합산 설정에 둡니다.** 지금 상태입니다.", OK),
        ("나", "**규칙으로 둡니다.** 조건 없이 항상 참인 규칙이 되는데, "
               "그 형태는 지표 하나가 결함으로 셉니다.", MUTED),
    ])

    # ── 왜 중요한가 ───────────────────────────────────────
    d.add_page()
    d.h1("이 결정이 무엇을 바꾸나요")

    d.p("**1번이 가장 큽니다.** 지금 정답은 46조문 중 **32조문**에 "
        "「옮길 수 없음」 규칙을 두고 있습니다 (규칙 수로는 56개). "
        "1번을 「나」로 바꾸면 그 수가 늘고, 어휘를 더 넓혀야 합니다. "
        "「가」를 유지하면 지금 우선순위가 그대로 섭니다.", color=INK)

    d.p("**모든 지표가 이 기준 위에서 계산됩니다.** 조문의 뜻을 재는 지표 "
        "여섯 개가 정답 데이터를 기준으로 삼습니다. 기준이 바뀌면 "
        "과거 라운드를 전부 다시 채점합니다 — 결과 파일을 보관하고 있어 "
        "GPU 없이 하루면 됩니다.")

    d.p("**정답 46조문 중 6조문만 사람 검토를 마쳤습니다.** 나머지 40조문은 "
        "제가 만든 초안입니다. 제가 초안을 쓰고 제가 승인하면 검증이 아닙니다. "
        "기계로 확인할 수 있는 것은 전부 확인했고 실제 오류를 넷 고쳤습니다 — "
        "그중 하나는 정답이 모델에게 벌점을 주는 바로 그 일을 하고 있던 "
        "것이었습니다. 남은 것은 위 두 가지 같은 **판단**입니다.")

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
