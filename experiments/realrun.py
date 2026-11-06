"""실행기를 **진짜 고객**에게 돌린다 — 합성 프로필이 아니라 `customerdb.db` 로.

⑥ 과 ⑩ 은 축을 조합해 만든 프로필 1024개로 잰다. 그것은 **조건의 정확도**를
재기 위한 것이고, 데이터가 늘 갖춰져 있다고 가정한다. 실제 데이터는 안 그렇다 —
2026-09-21 에 세어 보니 이벤트 12종을 받치는 테이블이 아예 없다 (`tools/datacheck.py`).

이 파일은 그 간극을 **눈으로 보게** 한다. 합성 프로필에서 MET/NOT_MET 이 나오던
rule 이 진짜 데이터에서는 UNKNOWN 이 된다. 그게 정상이다 — `resolver` 가 구간과
`needs_review` 로 받는다. 정상인지 **세어서** 말할 수 있게 하는 것이 목적이다.

**없다** 와 **모른다** 를 안 뭉갠다. DB 가 주지 않는 것은 `_provided` 에 안 넣는다.
빈 리스트로 뭉개면 실적 없는 고객과 데이터 없는 고객이 같은 답을 받는다.

DB 는 읽기 전용으로만 연다.

    python experiments/realrun.py                 고객마다 판별을 낸다
    python experiments/realrun.py --product KBYY  한 상품 조문만
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

import catalog
from engine import evaluate_rules
from resolver import resolve

CUSTOMER_DB = Path("/workspace/database/schema/customerdb.db")
GOLD_DIR = Path(__file__).resolve().parents[1] / "data" / "gold"

# DB 가 실제로 주는 것만 적는다. 여기 없는 것은 «모른다» 로 간다.
# `datacheck.BACKING` 이 근거다 — 거기가 바뀌면 여기도 바뀐다.
def provided_keys():
    """실행기에 «이건 준다» 고 선언할 이름 목록.

    `datacheck.BACKING` 이 유일한 근거다. 여기서 따로 적으면 둘이 갈라지고,
    그러면 «없다» 와 «모른다» 의 경계가 조용히 틀어진다.
    """
    import datacheck
    keys = [k for k, v in datacheck.BACKING.items() if v is not None]
    # 이벤트는 하나도 못 준다 — 거래 내역 테이블이 없다
    return keys


def _age(birth, on):
    """생년월일 → 만 나이. 생일이 안 지났으면 한 살 뺀다."""
    b = date.fromisoformat(birth)
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def customers():
    """DB 한 줄씩을 실행기 ctx 로 바꾼다."""
    today = date.today()
    with sqlite3.connect(f"file:{CUSTOMER_DB}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "select a.account_id, d.customer_kind, d.customer_birth "
            "  from Customer_Accounts a "
            "  left join Customer_Defaults d on d.account_id = a.account_id "
            " order by a.account_id").fetchall()
        subs = {}
        for s in c.execute("select * from Customer_Subscriptions"):
            subs.setdefault(s["account_id"], []).append(dict(s))

    by_id = {v["id"]: (k, v) for k, v in catalog.PRODUCTS.items()
             } if catalog.PRODUCTS and "id" in next(iter(catalog.PRODUCTS.values())) else {}
    out = []
    for r in rows:
        mine = subs.get(r["account_id"], [])
        held = [by_id[s["product_id"]][0] for s in mine if s["product_id"] in by_id]
        cats = sorted({by_id[s["product_id"]][1]["category"]
                       for s in mine if s["product_id"] in by_id})
        newest = mine[-1] if mine else {}
        ctx = {
            "customer": {
                "age": _age(r["customer_birth"], today) if r["customer_birth"] else None,
                "is_youth": (_age(r["customer_birth"], today) < 19
                             if r["customer_birth"] else None),
                "holder_type": r["customer_kind"],
                "has_product": bool(held),
                "held_products": held,
                "held_categories": cats,
            },
            "contract": {
                "start_date": newest.get("joined_date"),
                "maturity_date": newest.get("maturity_date"),
                "termination_date": newest.get("closed_date"),
                "reference_date": today.isoformat(),
                "amount": newest.get("joined_amount"),
                "monthly_amount": newest.get("monthly_amount"),
            },
            "account": {},
            "events": {},
            "_provided": provided_keys(),
        }
        out.append((r["account_id"], ctx, held))
    return out


def gold_rules(product=None):
    """정답에서 `OK` rule 만 모은다. `UNSUPPORTED` 는 애초에 안 돌린다.

    `product` 에 `"KBYY"` 처럼 조문 앞머리를 주면 그 상품만 고른다.
    """
    out = []
    for f in sorted(GOLD_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text("utf-8"))
        cid = d.get("clause_id")
        if product and not (cid or "").startswith(product):
            continue
        for r in (d.get("rules") or []):
            if r.get("status") == "OK":
                out.append(r)
    return out


def product_base_rate():
    """기준금리는 **고객이 아니라 상품**에 붙는다.

    2026-09-22 — 여기서 `ctx["contract"]["base_rate"]` 만 보고 있었다. 고객 DB 는
    그 값을 주지 않으므로 늘 0.0 이 되고, 최종 금리가 **누구에게나 0.00~0.00** 으로
    찍혔다. 조건식이나 실행기 탓이 아닌데 그렇게 보인다.

    상품설명서에서 읽은 값이 `data/gold/_product.json` 에 있다 (연 0.1%).
    계약이 값을 주면 그것을 쓰고, 없으면 상품 값으로 떨어진다.
    """
    f = GOLD_DIR / "_product.json"
    if not f.exists():
        return 0.0
    return float(json.loads(f.read_text("utf-8")).get("base_rate") or 0.0)


def main(argv=None):
    """고객마다 판별을 내고, UNKNOWN 이 몇이고 왜인지 찍는다."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--product", help="KBYY · KBONE 처럼 조문 앞머리")
    # 2026-09-22 — 옵션 없이 돌리면 **가입 자격 규칙까지 섞여** 이미 보유한 고객이
    # 「자격 없음」으로 나온다. 정답의 DISQUALIFY 8개는 전부 가입 자격이다
    # (1인 1계좌 · 연령 · 명의 유형). 두 질문은 다르다 —
    #   신규: 이 고객이 지금 가입할 수 있나
    #   보유: 이미 가진 고객의 우대금리가 얼마인가
    # 섞어 돌리면 뒤쪽 시나리오가 아예 안 보인다 (전부 기준금리 고정).
    ap.add_argument("--mode", choices=("신규", "보유"), default="신규",
                    help="신규=전부 · 보유=가입 자격(DISQUALIFY) 규칙을 뺀다")
    a = ap.parse_args(argv)

    if not CUSTOMER_DB.exists():
        raise SystemExit(f"고객 DB 가 없다: {CUSTOMER_DB}")
    rules = gold_rules(a.product)
    if a.mode == "보유":
        rules = [r for r in rules
                 if (r.get("effect") or {}).get("type") != "DISQUALIFY"]
    print(f"정답 rule {len(rules)}개 · 고객 {len(customers())}명 · "
          f"기준금리 연 {product_base_rate()}% (상품설명서) · 보기 «{a.mode}»\n")

    from collections import Counter
    total = Counter()
    for aid, ctx, held in customers():
        js = evaluate_rules(rules, ctx)
        cnt = Counter(j.value.name if hasattr(j.value, "name") else str(j.value)
                      for j in js)
        total.update(cnt)
        res = resolve(js, base_rate=ctx["contract"].get("base_rate")
                      or product_base_rate())
        print(f"계정 {aid:<4} {ctx['customer']['holder_type']:<16}"
              f"만 {ctx['customer']['age']}세 · 보유 {held or '없음'}")
        print(f"     판별 {dict(cnt)}")
        print(f"     결과 {res}")
    print(f"\n합계 {dict(total)}")
    n = sum(total.values())
    u = total.get("U", 0)
    print(f"UNKNOWN {u}/{n} = {u / n * 100:.0f}%  "
          "— 데이터가 없어서지 조건식이 틀려서가 아니다")


if __name__ == "__main__":
    main()
