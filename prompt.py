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
            f"[위 출력의 문제]\n{listed}\n\n"
            f"문제만 고쳐서 JSON 을 다시 낸다. 고칠 필요 없는 rule 은 그대로 둔다.\n\n[출력]")
