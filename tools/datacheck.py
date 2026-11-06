"""실행기가 **지금 있는 고객 데이터로** 판정할 수 있는 조문이 몇 개인가.

2026-09-21 에 `customerdb.db` 를 찾았다. 여태 이 저장소는 상품·문서 DB
(`financedb.db`)만 보고 있었고, 「고객 데이터에 이 값이 있는가」 는 계속
«데이터 쪽 확인 필요» 로 밀려 있었다 (DECISIONS.md 질문 4).

카탈로그는 **조문이 말하는 것**을 담는다. 이 파일은 **데이터가 주는 것**을 담고,
둘을 맞대어 «판정 못 하는 조문» 을 센다. 카탈로그를 좁히지는 않는다 —
조문이 말하는데 데이터가 없는 것은 데이터 쪽이 메울 구멍이지 조문 탓이 아니다.

DB 는 **읽기 전용으로만** 연다. 이 저장소는 남의 DB 를 안 건드린다.
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import sqlite3
from pathlib import Path

DB = Path("/workspace/database/schema/customerdb.db")

# 변수 → 어느 칼럼이 받치나. None 이면 데이터가 없다.
#
# «파생» 은 칼럼 하나를 그대로 읽는 게 아니라 계산해서 얻는 것이다 —
# 나이는 생년월일에서, 가입기간은 가입일과 만기일에서 나온다.
BACKING = {
    "customer.age":                 ("Customer_Defaults.customer_birth", "파생"),
    "customer.is_youth":            ("Customer_Defaults.customer_birth", "파생"),
    "customer.holder_type":         ("Customer_Defaults.customer_kind", "직접"),
    "customer.has_product":         ("Customer_Subscriptions.product_id", "파생"),
    "customer.held_products":       ("Customer_Subscriptions.product_id", "파생"),
    "customer.held_categories":     ("Customer_Subscriptions.product_id", "조인"),
    "contract.start_date":          ("Customer_Subscriptions.joined_date", "직접"),
    "contract.maturity_date":       ("Customer_Subscriptions.maturity_date", "직접"),
    "contract.term_months":         ("Customer_Subscriptions.joined_date", "파생"),
    "contract.amount":              ("Customer_Subscriptions.joined_amount", "직접"),
    "contract.monthly_amount":      ("Customer_Subscriptions.monthly_amount", "직접"),
    "contract.termination_date":    ("Customer_Subscriptions.closed_date", "직접"),
    "contract.reference_date":      ("(실행 시점)", "파생"),
    # 아래는 받치는 칼럼이 없다
    "contract.termination_type":    None,   # subscription_status 는 중도/만기를 안 가른다
    "contract.channel":             None,
    "contract.switch_date":         None,
    "contract.base_rate":           None,   # 상품 DB 에도 금리 칼럼이 없다
    "account.balance":              None,
    "account.reserved_amount":      None,
    "account.last_transaction_date": None,  # last_login_at 은 로그인이지 거래가 아니다
    "contract.payout_request_date": None,
    "customer.is_first_deposit":    None,   # 가입 이력이 비면 첫 거래로 볼 수는 있으나 약하다
}

# 이벤트는 하나도 못 받친다 — **거래 내역 테이블 자체가 없다.**
EVENTS_BACKED = frozenset()

# DDL 의 CHECK 가 값의 주인이다. 여기 적은 것과 어긋나면 시험이 터진다.
CHECKS = {
    "Customer_Defaults.customer_kind":
        ("INDIVIDUAL", "SOLE_PROPRIETOR", "CORPORATION", "ORGANIZATION"),
    "Customer_Defaults.customer_nationality": ("DOMESTIC", "FOREIGN"),
    "Customer_Defaults.customer_residency": ("RESIDENT", "NON_RESIDENT"),
    "Customer_Subscriptions.subscription_status": ("ACTIVE", "MATURED", "CLOSED"),
    "Customer_Accounts.account_status": ("ACTIVE", "DORMANT", "WITHDRAWN"),
}


def db_enum(qualified):
    """DB 의 CHECK 제약에서 값 목록을 **읽어 온다.** 손으로 적은 것을 안 믿는다."""
    import re
    table, column = qualified.split(".")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        sql = c.execute("select sql from sqlite_master where name = ?",
                        (table,)).fetchone()
    if not sql:
        return None
    m = re.search(rf"`{column}`\s+in\s*\(([^)]*)\)", sql[0], re.S)
    return tuple(re.findall(r"'([^']+)'", m.group(1))) if m else None


def missing(names):
    """이름들 중 데이터가 없는 것만 돌려준다."""
    return sorted(n for n in names
                  if n in BACKING and BACKING[n] is None)


def names_needed(rule):
    """rule 하나가 필요로 하는 변수·이벤트 이름."""
    import json
    import re
    s = json.dumps(rule, ensure_ascii=False)
    got = set(re.findall(r'"var":\s*"([^"]+)"', s))
    ev = set(re.findall(r'"event":\s*"([^"]+)"', s))
    return got, ev


def audit_gold():
    """gold 조문마다 «지금 데이터로 판정 가능한가» 를 가른다.

    `UNSUPPORTED` rule 은 애초에 안 돌리므로 세지 않는다. rule 이 하나도 없는
    조문(빈 배열)은 **판정할 게 없어서** 가능으로 친다 — 기권이 정답이다.
    """
    import json
    out = {}
    for f in sorted(Path("data/gold").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        cid = d.get("clause_id")
        if not cid:
            continue
        bad_v, bad_e = set(), set()
        for r in (d.get("rules") or []):
            if r.get("status") != "OK":
                continue
            v, e = names_needed(r)
            bad_v |= set(missing(v))
            bad_e |= (e - EVENTS_BACKED)
        out[cid] = {"blocked_vars": sorted(bad_v), "blocked_events": sorted(bad_e)}
    return out


def report():
    """사람이 읽는 요약 — 지금 데이터로 몇 조문을 판정할 수 있나."""
    import catalog
    gold = audit_gold()
    ok = [c for c, x in gold.items()
          if not x["blocked_vars"] and not x["blocked_events"]]
    print(f"조문 {len(gold)}개 중 **지금 데이터로 판정 가능 {len(ok)}개** "
          f"= {len(ok) / len(gold) * 100:.0f}%\n")

    from collections import Counter
    cv, ce = Counter(), Counter()
    for x in gold.values():
        cv.update(x["blocked_vars"])
        ce.update(x["blocked_events"])
    if cv:
        print("막는 변수 (데이터에 없다)")
        for n, k in cv.most_common():
            print(f"  {n:<34}{k:>2}조문")
    if ce:
        print("\n막는 이벤트 (거래 내역 테이블이 없다)")
        for n, k in ce.most_common():
            print(f"  {n:<34}{k:>2}조문")

    print("\n카탈로그에 있는데 데이터가 없는 변수 "
          f"{len([k for k, v in BACKING.items() if v is None])}"
          f"/{len(catalog.VARIABLES)}")
    print("데이터에 있는데 카탈로그에 없는 것: "
          "customer_nationality · customer_residency")


if __name__ == "__main__":
    report()
