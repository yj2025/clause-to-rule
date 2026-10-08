"""상품별로 조건식이 읽는 입력 필드 — 다음 단계가 «무엇을 물을지» 정할 때 쓴다 (2026-10-08).

    python fields.py                       # 정답 10상품 전부
    python fields.py KBNR KBSSG -o out.json
    python fields.py KBNR --results showcase/results_kb10v127a.json

조건식(condition · guard · let)에서 필드와 이벤트를 모아, 어디서 얻는 값인지 다섯 갈래로 나눈다.
갈래는 **10-08 사용자 결정**(기본 정보만 받고 거래 내역은 모으지 않는다)을 따른 것이다 —
서비스의 입력 화면이 바뀌면 `SOURCE` 를 고친다. 카탈로그에 필드를 더하면 시험이 여기를 고치라고 막는다.

rule 마다 «기본 정보만으로 판정이 끝나나»도 센다 — 거래 이벤트 · 계좌 상태를 읽는 rule 은 늘 조건부(UNKNOWN)로 남는다.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import catalog
import explain

# 어디서 얻는 값인가
AUTO = "AUTO"                  # 입력 없이 정해진다 (판정일 = 오늘 · 상품의 기본이율)
REGISTRATION = "REGISTRATION"  # 상품 등록 화면에서 받는다 (가입일 · 만기일 · 납입액 · 명의)
ASK = "ASK"                    # 기본 정보로 한 번 물으면 된다
TERMINATION = "TERMINATION"    # 해지할 때 생긴다 — 가입 중에는 늘 모른다
NOT_COLLECTED = "NOT_COLLECTED"  # 거래 내역 · 계좌 상태 — 모으지 않는다

SOURCE = {
    "contract.reference_date": AUTO, "contract.base_rate": AUTO,
    # 둘은 계산값이지만 입력이 있어야 나온다 — 기간은 가입일 · 만기일에서, 청년 여부는 나이에서
    "contract.term_months": REGISTRATION, "customer.is_youth": ASK,
    "contract.start_date": REGISTRATION, "contract.maturity_date": REGISTRATION,
    "contract.monthly_amount": REGISTRATION, "contract.amount": REGISTRATION, "customer.holder_type": REGISTRATION,
    "customer.age": ASK, "customer.has_product": ASK, "customer.held_products": ASK,
    "customer.held_categories": ASK, "customer.is_first_deposit": ASK, "contract.channel": ASK,
    "contract.termination_type": TERMINATION, "contract.termination_date": TERMINATION,
    "contract.payout_request_date": TERMINATION,
    "account.balance": NOT_COLLECTED, "account.reserved_amount": NOT_COLLECTED,
    "account.last_transaction_date": NOT_COLLECTED, "contract.switch_date": NOT_COLLECTED,
}


def source_of(name):
    return NOT_COLLECTED if name.startswith("events.") else SOURCE[name]


def desc_of(name):
    if name.startswith("events."):
        return catalog.EVENTS.get(name[len("events."):], name)
    return catalog.VARIABLES.get(name, {}).get("desc", name)


def product_fields(rules_by_clause):
    """{조문: rules} → 필드별 갈래 · 설명 · 쓰는 rule, 그리고 rule 을 «판정에 필요한 가장 먼 갈래»로 센 수."""
    fields = {}
    worst = collections.Counter()
    order = [AUTO, REGISTRATION, ASK, TERMINATION, NOT_COLLECTED]
    for cid, rules in rules_by_clause.items():
        for r in rules or []:
            if r.get("status") != "OK":
                continue
            used = explain.uses(r)
            for u in used:
                f = fields.setdefault(u, {"source": source_of(u), "desc": desc_of(u), "rules": []})
                f["rules"].append(r.get("rule_id"))
            worst[max((source_of(u) for u in used), key=order.index, default=AUTO)] += 1
    return ({k: fields[k] for k in sorted(fields, key=lambda k: (order.index(fields[k]["source"]), k))},
            {k: worst[k] for k in order})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("products", nargs="*", help="상품 접두어. 없으면 정답이 있는 10상품 전부")
    ap.add_argument("--results", help="정답 대신 이 결과 파일의 모델 출력을 쓴다")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    out = {}
    for p in a.products or list(explain.BASE_RATE):
        rules = explain.load_results(a.results, p) if a.results else explain.load_gold(p)
        f, n = product_fields(rules)
        out[p] = {"fields": f, "rules_by_hardest_source": n}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text, "utf-8")
    else:
        print(text)
    tot = collections.Counter()
    for v in out.values():
        tot.update(v["rules_by_hardest_source"])
    print("OK rule 을 판정에 필요한 가장 먼 갈래로 셈: " + " · ".join(f"{k} {tot[k]}" for k in
          (AUTO, REGISTRATION, ASK, TERMINATION, NOT_COLLECTED)), file=sys.stderr)


if __name__ == "__main__":
    main()
