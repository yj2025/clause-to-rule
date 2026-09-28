"""지문 — 태스크 1 의 시스템 프롬프트와 조문별 user 프롬프트.

세 가지를 지킨다. 전부 실측 근거가 있다.

1. **부정 예시는 모델이 이미 저지르는 실수에만 쓴다** (§9 2번).
   안 하던 실수를 미리 막으려고 이름을 부르면 오히려 가르친다 —
   `literal` 을 쓰지 말라고 적었더니 4건에서 10건으로 늘었다.
   그래서 이 파일은 금지어를 이름으로 부르지 않는다. §5 의 assert 가 그걸 지킨다.

2. **지시문만으로는 안 된다. 예시가 있어야 한다** (§9 10번).
   "표현할 수 없으면 생략하라" 는 처음부터 있었는데, 예시가 전부 rule 을
   내놓는 형태라 모델이 본 빈 배열이 하나도 없었다. 그래서 빈 배열 예시를 넣는다.

3. **카탈로그는 조문별로 추려 넣는다** (§9 2번과 같은 뿌리).
   전체를 넣으면 길어지고, 안 쓸 이름을 보여주면 그 이름을 쓴다.
"""

import json

import catalog
from schema import FEWSHOTS

SYSTEM_PROMPT = """너는 은행 상품설명서의 조문을 기계가 실행할 수 있는 조건식 JSON 으로 옮기는 도구다.

출력은 JSON 하나뿐이다. 설명, 머리말, 코드펜스를 붙이지 않는다.

형식
  {"rules": [ rule, ... ]}

rule 하나의 형태
  rule_id    문자열. 조문 id 에 일련번호를 붙인다
  status     "OK" 또는 "UNSUPPORTED"
  label      사람이 읽을 짧은 이름
  source     {"quote": 조문 원문에서 그대로 옮긴 근거 문장}
  let        (선택) 이름 → 기간 명세. 조건에서 {"ref": "$이름"} 으로 부른다
  guard      (선택) 이 rule 을 아예 적용하지 않을 조건
  condition  조건식. 없으면 {} 이고 항상 적용된다는 뜻이다
  effect     {"type": ..., 그 type 이 요구하는 키}

지켜야 할 것
1. quote 는 조문 원문에 있는 글자를 **그대로** 옮긴다. 요약하거나 바꿔 쓰지 않는다.
2. 아래 목록에 있는 이름만 쓴다. 새 이름을 지어내지 않는다.
3. 조건식의 키는 하나다. 여러 조건은 {"and": [ ... ]} 로 묶는다.
4. 금리 effect 의 value 에는 조문에 적힌 **숫자**를 넣는다.
5. 조문에 조건과 효과가 없으면 rules 를 **빈 배열**로 낸다.
   조건과 효과는 있는데 아래 목록으로 표현할 수단이 없으면
   status 를 "UNSUPPORTED" 로 하고 effect 도 그렇게 적는다.
   이 둘은 다르다. 전자는 옮길 것이 없는 경우, 후자는 옮길 수 없는 경우다.

수를 돌려주는 것들은 비교로 감싼다.
  {">=": [ {"count_distinct_months": {"event": ..., "within": ...}}, 6 ]}
"""


# 쓰는 법 한 줄. **실측으로 오용이 확인된 이름에만** 붙인다.
#
# 전부에 붙이면 프롬프트가 길어지고, 안 쓸 이름을 설명하면 그 이름을 쓰게 된다
# (§9 2번 — 안 하던 실수를 미리 막으려 이름을 부르면 오히려 가르친다).
#
# 예시 자리를 쓰지 않는 경로다. `pick_candidates` 가 조문별로 어휘를 추리므로
# **그 이름이 실린 조문에서만** 길어진다.
_USAGE = {
    # v17: 이름을 줬는데 "1년 이상 입출금 거래가 없는" 을
    #      contract.term_months(가입기간)로 옮겼다. 46조문에서 1번 썼다.
    "WITHDRAWAL":
        "무거래 판정은 DEPOSIT 과 WITHDRAWAL 을 둘 다 센다",
    # v14: 거래중지·지급정지·비과세를 전부 여기로 밀었다 (생성물의 17.8%).
    "DISQUALIFY":
        "예금 자격 자체가 없을 때다. 특정 거래만 금지하는 것이 아니다",
    # v8 진단: 코퍼스는 이 개념을 "보유" 라 부르지 않고 "1인 1계좌" 라 부른다.
    "customer.has_product":
        '조문의 "1인 1계좌" 가 이것이다',
}


def _usage(name, pad=30):
    """변수·이벤트 밑에 붙는 쓰임새 힌트 줄. 등록된 이름에만 붙는다.

    전부 적으면 지문이 길어지고 ⑦ 빈 배열이 무너진다 — 지문이 길수록
    «무언가 만들라» 는 압력이 는다 (v21·v22 에서 실측).
    """
    line = _USAGE.get(name)
    return [f"{'':<{pad}}{line}"] if line else []


def _catalog_block(text):
    """조문에 근거가 있는 어휘만 추린다. 근거가 없으면 전체를 준다."""
    vs, es = catalog.pick_candidates(text)
    fees = catalog.pick_fees(text)
    services = catalog.pick_services(text)
    vs = vs or sorted(catalog.VARIABLES)
    es = es or sorted(catalog.EVENTS)

    lines = ["[변수]"]
    for v in vs:
        m = catalog.VARIABLES[v]
        lines.append(f"  {v:<28}{m['type']:<6}{m['desc']}")
        lines += _usage(v, 36)
    lines.append("[이벤트]")
    for e in es:
        lines.append(f"  {e:<28}{catalog.EVENTS[e]}")
        lines += _usage(e, 30)
    lines.append("[연산자]")
    lines.append("  " + ", ".join(catalog.OPERATORS))
    lines.append("[effect]")
    for name, need in catalog.EFFECTS.items():
        lines.append(f"  {name:<16}{'필수 키: ' + ', '.join(need) if need else '추가 키 없음'}")
        lines += _usage(name, 18)
    if fees:
        lines.append("[면제 대상]")
        lines += [f"  {f:<28}{catalog.FEES[f]}" for f in fees]
    if services:
        lines.append("[제휴서비스 대상]")
        lines += [f"  {s:<28}{catalog.SERVICES[s]}" for s in services]
    # 2026-09-23 · v39. 막는 효과를 가른 것(v36)과 같은 일을 「바뀌는」 효과 셋에 한다.
    if catalog.wants_change_kinds(text):
        lines.append("[바뀌는 것처럼 보이는 효과 셋 — 뜻이 다르다]")
        lines.append(f"  {'STATE_CHANGE':<28}이 계좌의 **설정**이 바뀐다 (저금통 해제 등). 예금은 그대로 있다")
        lines.append(f"  {'DORMANT_CONTRIBUTION':<28}휴면예금으로 **출연**된다 — 예금이 이 계좌를 떠난다")
        lines.append(f"  {'SERVICE_PROVIDE':<28}**계좌 밖의 서비스**를 준다 (수강권 · 신문 등). 예금과 무관하다")
        lines.append("  무엇이 바뀌는지로 고른다 — 계좌의 설정인가, 돈의 주인인가, 계좌 밖의 것인가")

    restrictions = catalog.pick_restrictions(text)
    if restrictions:
        # 2026-09-22 · v36. **막는 효과가 둘인데 지문이 뜻을 안 말한다.**
        #
        # effect 표는 이름과 필수 키만 찍는다 — 「DISQUALIFY 추가 키 없음」 ·
        # 「RESTRICT 필수 키: target」. 변수와 이벤트에는 설명이 붙는데 effect 에는 없다.
        # 그래서 모델은 「질권설정 불가」에도 DISQUALIFY 를 쓴다. **라벨은 정확한데
        # 효과 종류만 틀린다** — 뜻을 못 알아들은 것이 아니라 고를 줄 모르는 것이다.
        #
        # 이 블록은 이미 붙고 있었고 target 이름도 보여 주고 있었다 (네 조문 전부).
        # **그런데도 DISQUALIFY 로 갔다.** 목록을 준 것과 차이를 말한 것은 다르다 —
        # v24 가 이름을 줬고 v33 이 차이를 말해서 먹혔다. 여기는 아직 차이를 말한 적이 없다.
        if catalog.wants_ban_block(text):
            lines.append("[막는 효과는 둘이고 뜻이 다르다]")
            lines.append(f"  {'DISQUALIFY':<28}예금 **자격**을 잃는다 — 이 예금의 우대가 전부 무효가 된다")
            lines.append(f"  {'RESTRICT':<28}그 **거래 하나**를 못 한다 — 금리도 자격도 그대로다")
            lines.append("  무엇을 못 하게 하는지 이름을 댈 수 있으면 RESTRICT 이고, "
                         "그 이름을 target 에 적는다")
        lines.append("[금지 대상 — RESTRICT 의 target]")
        lines += [f"  {r:<28}{catalog.RESTRICTIONS[r]}" for r in restrictions]
    # 2026-09-20 상품 코드 체계. 조문이 이름으로 부른 상품만 붙인다 — 74개를 다 붙이면
    # 지문이 길어지고 안 부른 상품을 쓰게 된다 (§9 2번).
    products = catalog.pick_products(text)
    if products:
        lines.append("[상품 키] PRODUCT_SWITCH_TO 의 target · customer.held_products 의 값")
        lines += [f"  {k:<28}{catalog.PRODUCTS[k]['name']}" for k in products]
    if any("저금통" in text for _ in (1,)) and "해제" in text:
        lines.append("[상태 변경 대상]")
        lines += [f"  {k:<28}{v}" for k, v in catalog.STATES.items()]
    # 2026-09-22 · v35. 규칙이 아닌 문장을 알아보게 한다. **기준을 주고 판단은 맡긴다** —
    # 「이 조문은 규칙이 아니다」라고 적으면 답을 흘리는 것이고, 다른 조문에 못 옮긴다.
    if catalog.wants_non_binding(text):
        lines.append('[규칙인가 아닌가] 규칙은 **고객에 따라 달라지는 효과**를 낸다 — '
                     '금리 · 수수료 · 한도 · 자격 · 제한. 절차나 창구를 알려 주는 문장, '
                     '「제한없음」처럼 아무도 걸리지 않는 문장, 고객의 권리나 은행의 재량을 '
                     '말하는 문장은 **규칙이 아니다.**')
        lines.append('  그런 조문이면 rules 를 빈 배열로 낸다: {"rules": []}')
        lines.append('  다만 그 문장에 **조건이 붙어 있으면** (「…인 경우에만 가능」 같은) '
                     '그것은 규칙이다')

    # 2026-09-21 · 어휘 확장 2차 1순위. 조문이 「n째 요일」을 말할 때만 붙인다 —
    # 나머지 조문의 지문은 한 글자도 안 는다. few-shot 자리를 안 먹는 것이 요점이다
    # (장면 하나가 ⑦ 을 10.9p 무너뜨린다 — v21·v22).
    if catalog.wants_recurring_date(text):
        lines.append('[돌아오는 날짜] 해마다 오는 날은 기준점에 month_of 와 n째 요일을 적는다 — '
                     '{"anchor": "contract.reference_date", "month_of": [6, 12], '
                     '"day": {"weekday": "FRI", "nth": 3}, "offset_days": 1}')
        lines.append(f"  {'month_of':<28}그 날이 오는 달 (1~12 목록)")
        lines.append(f"  {'day.weekday':<28}MON TUE WED THU FRI SAT SUN")
        lines.append(f"  {'day.nth':<28}몇째 그 요일인가 (1~5)")
        lines.append(f"  {'offset_days':<28}그날에서 며칠 뒤인가 (다음날이면 1)")
        # 2026-09-22 · v32 판정. 이 기준점을 `within`(창) 자리에 넣은 회차가 있었다 —
        # 둘 다 anchor 를 품어 닮았다. **창은 시작과 끝이 있다** 는 것을 같이 적는다
        lines.append('  기간을 세려면 창에 넣는다 — '
                     '{"within": {"month_range": {"from": {여기}, "to": {여기}}}}')
    attrs = [(e, catalog.EVENT_ATTRIBUTES[e]) for e in es if e in catalog.EVENT_ATTRIBUTES]
    if attrs or "건별" in text:
        lines.append('[이벤트 조건] exists · count_* 에 "where" 를 건다 — '
                     '{"exists": {"event": …, "within": …, "where": {"min_amount": 500000}}}')
        lines.append(f"  {'min_amount':<28}건별 금액 이상 (원)")
        for e, a in attrs:
            for name, vals in a.items():
                lines.append(f"  {e + '.' + name:<28}{', '.join(vals)}")
    for name, vals in catalog.ENUM_VALUES.items():
        if name in vs:
            lines.append(f"[{name} 의 값]")
            lines.append("  " + ", ".join(vals))
    return "\n".join(lines)


def _fewshot_block(indent=1):
    """예시는 **들여쓴 JSON** 으로 보여준다.

    한 줄로 압축해 보여주면 모델이 중괄호 깊이를 놓친다. 실측으로, 압축본에서는
    rule 객체를 일찍 닫고 형제 키를 이어 붙이는 형태가 나왔고 그게 ① 실패의
    대부분이었다. 들여쓰기가 깊이 단서가 된다.
    """
    out = []
    for i, (clause, output) in enumerate(FEWSHOTS, 1):
        body = json.dumps(output, ensure_ascii=False, indent=indent)
        out.append(f"[예시 {i} · 조문]\n{clause}\n[예시 {i} · 출력]\n{body}")
    return "\n\n".join(out)


def build_user_prompt(clause_text, clause_id=None, fewshot_indent=1):
    """조문 하나 → user 프롬프트."""
    head = f"[조문 id] {clause_id}\n" if clause_id else ""
    return (f"{_fewshot_block(fewshot_indent)}\n\n"
            f"[쓸 수 있는 이름]\n{_catalog_block(clause_text)}\n\n"
            f"{head}[조문]\n{clause_text}\n\n[출력]")


# v46 — **목록에 없는 이름이 필요할 때 기권을 쓰라고 잇는다.**
#
# 오류 메시지는 「쓸 수 있는 것: …」만 말한다. 그래서 모델은 목록에서 비슷한 것을
# 찾고, 없으면 또 지어낸다. 시도 셋을 다 쓰고도 못 고치는 조문이 넷이다
# (`KBONE-S2-R15` · `KBYY-S2-R09` · `KBYY-S2-R17` · `KBYY-S3-R05`).
#
# 지문에는 이미 둘 다 적혀 있다 — 2번(이름을 지어내지 않는다)과 5번(수단이 없으면
# UNSUPPORTED). **2번을 어길 때가 바로 5번의 경우**인데 그 연결이 없다.
#
# `UNSUPPORTED` 는 **이미 15~19조문이 쓰는 수단**이다. 그래서 이것은 「안 쓰던 것을
# 새로 쓰라」(v40 · 채택 거의 0)가 아니라 **「이미 쓰는 수단을 다른 자리에 쓰라」**
# (v41 · 채택)다. 가설의 세 번째 시험이다.
#
# **이름을 하나도 적지 않는다** — v34 가 메시지에 예시를 박아 실패했다.
# **오류 줄마다 붙이지 않는다** — 오류가 여덟 줄까지 들어가므로 한 번만 붙인다.
#
# v50 — **마지막 줄을 더했다.** v46 이 기권을 늘리면서 「기권인데 조건이 남은
# 조문」이 4~5 에서 7~9 로 늘었다. 조건을 남기면 그 안의 이름이 계속 관문에
# 걸린다 (`KBYY-S2-R09` 가 기권으로 바꾸고도 0점인 이유다). 정답의 기권 rule
# 28개 중 조건이 든 것은 둘뿐이고 effect 가 든 것은 하나도 없다.
#
# v54 — **마지막 두 줄을 더했다.** v46 이 기권을 가르치면서 「정답이 «빈 배열»인
# 조문에 기권 rule 을 다는 자리」가 3~4 에서 6 으로 늘었다 (네 라운드 내내 6).
# 「기본이율 적용」 · 「해지 방법」처럼 **규칙이 아니라 서술인 문장**들이다.
# 블록이 「기권하라」만 말하고 「애초에 옮길 것이 없으면 만들지 마라」를 안 했다.
_NO_NAME = ("카탈로그에 없는", "가 카탈로그에 없다",
            "상품 키가 아님", "금지 대상이 아님")


def _no_name_block(errors):
    """이름이 목록에 없다는 오류가 하나라도 있을 때만 붙는다."""
    if not any(any(k in str(e) for k in _NO_NAME) for e in errors):
        return ""
    return ("\n[목록에 없는 이름이 필요할 때]\n"
            "  비슷한 다른 이름으로 바꾸지 않는다. 조문이 부르는 것이 목록에 "
            "없으면\n"
            '  그 rule 의 status 를 "UNSUPPORTED" 로 낸다 (지켜야 할 것 5).\n'
            "  그 rule 에는 조건도 효과도 적지 않는다 — 옮길 수단이 없다고 "
            "밝히는 자리다.\n")


def build_retry_prompt(clause_text, bad_output, errors, clause_id=None,
                      fewshot_indent=1):
    """검증에 걸린 출력을 고쳐 달라는 프롬프트.

    오류 메시지는 프롬프트의 일부다. 메시지가 좋아지자 재시도 기여가
    +10.8p 에서 +36.0p 로 커졌고 생성 호출은 257 에서 211 회로 줄었다 (§6.3).

    **되돌려 주는 출력도 들여쓴다.** 압축본을 보여주면 모델이 중괄호 깊이를
    놓친다는 것은 `_fewshot_block` 에서 이미 쟀다. 재시도 프롬프트는 그 압축본을
    [출력] 바로 앞 — 모델이 생성 직전에 보는 가장 가까운 자리 — 에 놓는
    마지막 한 곳이었다. 예시는 들여쓰기로 보여주고 정작 흉내 낼 대상은 한 줄로
    준 셈이다.

    v2 실측: 재시도 94회 중 결과가 나빠진 8회가 **전부** 되돌려 준 JSON 의
    중첩깊이 8 이상 구간에 몰렸다 (깊이 8 미만 54회는 0건).
    """
    listed = "\n".join(f"  - {e}" for e in errors[:8])
    shown = json.dumps(bad_output, ensure_ascii=False, indent=fewshot_indent)
    return (f"{build_user_prompt(clause_text, clause_id, fewshot_indent)}\n"
            f"{shown}\n\n"
            f"[위 출력의 문제]\n{listed}\n"
            f"{_no_name_block(errors)}\n"
            f"문제만 고쳐서 JSON 을 다시 낸다. 고칠 필요 없는 rule 은 그대로 둔다.\n\n[출력]")
