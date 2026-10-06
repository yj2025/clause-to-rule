"""KB스타통장 수수료 면제 — 지금 어휘로 쓴 정답을 경계값 사례 11개에 돌린다 (2026-10-06 · 수기 검토 시범).

    python showcase/pilot_kbstar/run_cases.py

어휘가 모자란 자리를 두 가지로 메워 본다 — 정답을 고르려는 것이 아니라 **어느 쪽으로 메워도 틀리는 사례**를 보려는 것이다.
  favorable — 원칙 1(고객에게 불리한 근사 금지)대로 «입금이 있으면» 실적 인정 (KBMER-S2-R08 · KBGL-S2-R09 전례)
  per_event — «건별 50만원 이상 입금»으로 근사 (where.min_amount)
  sum       — 10-06 에 넣은 sum_events 로 «합산 50만원 이상»을 그대로
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
import catalog  # noqa: E402
from engine import TV, evaluate_rules  # noqa: E402

FEES = {1: "EBANK_TRANSFER", 2: "AUTO_DEBIT", 3: "ATM_TRANSFER", 4: "ATM_WITHDRAW_AFTER_HOURS",
        5: "OTHER_BANK_ATM_WITHDRAW"}
WIN = {"window": {"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -1, "day": "first"},
                                  "to": {"anchor": "contract.reference_date", "offset_months": -1, "day": "last"}}},
       "window2": {"month_range": {"from": {"anchor": "contract.reference_date", "offset_months": -2, "day": "first"},
                                   "to": {"anchor": "contract.reference_date", "offset_months": -2, "day": "last"}}}}
NOT_CARD = ["APARTMENT_FEE", "GIRO", "CMS", "FIRM_BANKING"]   # X4 — 카드 출금 제외. 리브 모바일 납부처는 못 가린다


def perf(win, variant):
    dep = {"event": "DEPOSIT", "within": {"ref": win}}
    if variant == "per_event":
        dep["where"] = {"min_amount": 500000}
    if variant == "sum":          # 10-06 · sum_events — 입금 속성(X1~X3)은 아직 못 거른다
        first = {">=": [{"sum_events": dep}, 500000]}
    else:
        first = {"exists": dep}
    return {"or": [first,
                   {"exists": {"event": "AUTO_TRANSFER", "within": {"ref": win}, "where": {"route": NOT_CARD}}}]}


def gold(variant):
    rules = []
    for n, fee in FEES.items():
        rules.append({"rule_id": f"KBSTAR-FEE-{n}", "status": "OK", "let": WIN,
                      "condition": {"or": [
                          {"and": [{">=": [{"var": "contract.reference_date"},
                                           {"anchor": "contract.reference_date", "offset_months": 0, "day": 11}]},
                                   perf("$window", variant)]},
                          {"and": [{"<=": [{"var": "contract.reference_date"},
                                           {"anchor": "contract.reference_date", "offset_months": 0, "day": 10}]},
                                   perf("$window2", variant)]}]},
                      "effect": {"type": "FEE_WAIVE", "target": fee, "value": "UNLIMITED"}})
        rules.append({"rule_id": f"KBSTAR-FEE-{n}-NEW", "status": "OK",
                      "condition": {"<=": [{"var": "contract.reference_date"},
                                           {"anchor": "contract.start_date", "offset_months": 2, "day": 10}]},
                      "effect": {"type": "FEE_WAIVE", "target": fee, "value": "UNLIMITED"}})
    return rules


# 사례의 사실을 실행기 입력으로. 어휘에 없는 사실(본인 계좌 · 결산이자 · 리브 모바일 · 제휴 ATM)은 담을 곳이 없다 — 그대로 빠진다.
def ctx_of(case):
    start = "2026-08-20" if case["id"] in ("B8", "B9") else "2025-03-01"
    ev = {"DEPOSIT": [], "AUTO_TRANSFER": []}
    dep = {"B1": [299999, 200000], "B2": [300000, 200000], "B3": [300000, 300000], "B4": [490000, 30000],
           "B7": [300000, 200000], "B10": [300000, 200000]}.get(case["id"], [])
    ev["DEPOSIT"] = [{"date": f"2026-09-{10 + i}", "amount": a} for i, a in enumerate(dep)]
    if case["id"] == "B5":
        ev["AUTO_TRANSFER"] = [{"date": "2026-09-25", "amount": 33000, "route": "CMS"}]
    if case["id"] == "B6":
        ev["AUTO_TRANSFER"] = [{"date": "2026-09-25", "amount": 33000, "route": "CARD"}]
    provided = ["contract.start_date", "contract.reference_date"]
    if case["id"] != "B11":
        provided += [f"events.{k}" for k in catalog.EVENTS]
    return {"customer": {}, "account": {},
            "contract": {"start_date": start, "reference_date": case["reference_date"], "switch_date": None},
            "events": ev if case["id"] != "B11" else {}, "_provided": provided}


def outcome(rules, case):
    fee = FEES[case["fee"]]
    js = [j for j in evaluate_rules(rules, ctx_of(case)) if (j.effect or {}).get("target") == fee]
    vals = [j.value for j in js]
    if any(getattr(j, "error", None) for j in js):
        return "ERROR:" + next(j.error for j in js if getattr(j, "error", None))
    return "WAIVED" if TV.T in vals else ("UNKNOWN" if TV.U in vals else "NOT_WAIVED")


def main():
    cases = json.loads((HERE / "cases.json").read_text("utf-8"))["cases"]
    print(f"{'사례':5}{'사람(정답)':12}{'favorable':14}{'per_event':14}{'sum':14}")
    score = {"favorable": 0, "per_event": 0, "sum": 0}
    for c in cases:
        row = [c["id"], c["expected"]]
        for v in ("favorable", "per_event", "sum"):
            got = outcome(gold(v), c)
            score[v] += got == c["expected"]
            row.append(got + ("" if got == c["expected"] else " ✗"))
        print(f"{row[0]:5}{row[1]:12}{row[2]:14}{row[3]:14}{row[4]:14}")
    print("맞음", score, "/", len(cases))
    (HERE / "gold_current_vocab.json").write_text(
        json.dumps({v: gold(v) for v in ("favorable", "per_event", "sum")}, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
