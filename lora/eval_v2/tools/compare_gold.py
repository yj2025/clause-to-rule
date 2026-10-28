"""정답 작성자 셋(judges/gold_<이름>/)의 조건식을 견준다 (2026-10-27).

두 가지로 본다.
  뜻     ⑥ 과 같은 실행 비교 (`scoring.score`) — 두 판을 서로 정답 · 생성물로 바꿔 양쪽 100 이면 같다.
         ⑥ 프로필(256)에 나이 30 · 40 과 가입기간 24 · 36 개월을 더해 1024 프로필로 돈다 —
         원래 축(나이 17/19 · 기간 6/12)으로는 «만 35세 이하» · «2년제» 조건이 안 갈린다.
  모양   OK rule 의 (효과 종류, 값, 단위, 대상) 다중집합 — 프로필이 못 건드리는 차이(카드 실적 금액 등)를 잡는다.

판정: 셋 다 뜻 · 모양 같음 → «일치» / 뜻만 같음 → «뜻 일치» / 그 밖 → «갈림».
표현불가 조문은 셋 다 OK rule 이 없으면 «일치» (UNSUPPORTED 개수 · 문구는 채점에 안 들어간다).

    python eval_v2/tools/compare_gold.py            # → judges/compare_gold.json + 표
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent / "work" / "M2-2"
sys.path.insert(0, str(REPO))
import gold  # noqa: E402
from scoring import score  # noqa: E402

NAMES = ["opus", "sonnet", "fable"]
# 상품별 1년제 기본금리 — 판들 사이 비교에만 쓴다 (양쪽에 같은 값)
BASE = {"HNSAL": 2.95, "HNDRM": 2.70, "HNWSH": 0.75}

gold.AXES["age"] = [17, 19, 30, 40]
gold.AXES["term"] = [6, 12, 24, 36]
PROFILES = gold.profiles()


def load(name, cid):
    p = HERE / "judges" / f"gold_{name}" / f"{cid}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def shape(rules):
    out = []
    for r in rules:
        if r.get("status") != "OK":
            continue
        e = r.get("effect") or {}
        out.append((e.get("type"), json.dumps(e.get("value"), ensure_ascii=False, sort_keys=True),
                    e.get("unit"), e.get("target") or e.get("fee") or e.get("service")))
    return sorted(out, key=str)


def main():
    triage = json.loads((HERE / "gold" / "_triage.json").read_text("utf-8"))["items"]
    report = []
    for it in triage:
        if it["verdict"] == "없음":
            continue
        cid = it["id"]
        G = {n: load(n, cid) for n in NAMES}
        missing = [n for n, g in G.items() if g is None]
        if missing:
            report.append({"id": cid, "verdict": it["verdict"], "result": "빠짐", "missing": missing})
            continue
        R = {n: G[n].get("rules") or [] for n in NAMES}
        base = BASE[cid.split("-")[0]]
        pairs = {}
        for a, b in itertools.combinations(NAMES, 2):
            s1 = score(R[a], R[b], "SUM", PROFILES, base)
            s2 = score(R[b], R[a], "SUM", PROFILES, base)
            pairs[f"{a}-{b}"] = {"same_meaning": s1["rate"] == 1 and s2["rate"] == 1,
                                 "rate": round(min(s1["rate"], s2["rate"]) * 100, 1),
                                 "mismatch": (s1["mismatch"] or s2["mismatch"])[:2]}
        shapes = {n: shape(R[n]) for n in NAMES}
        meaning = all(p["same_meaning"] for p in pairs.values())
        form = len({json.dumps(s) for s in shapes.values()}) == 1
        if it["verdict"] == "표현불가":
            result = "일치" if not any(shapes.values()) else "갈림"
        else:
            result = "일치" if meaning and form else "뜻 일치" if meaning else "갈림"
        report.append({"id": cid, "verdict": it["verdict"], "result": result, "pairs": pairs,
                       "shapes": shapes, "n_rules": {n: [len(R[n]), sum(r.get("status") == "OK" for r in R[n])] for n in NAMES}})
    (HERE / "judges" / "compare_gold.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), "utf-8")
    for x in report:
        line = f"  {x['id']:14} {x['verdict']:5} {x['result']:5}"
        if "pairs" in x:
            line += "  " + " · ".join(f"{k} {v['rate']}" for k, v in x["pairs"].items())
            line += "  rule(전체/OK) " + " ".join(f"{n}={v[0]}/{v[1]}" for n, v in x["n_rules"].items())
        print(line)
    from collections import Counter
    print("\n", dict(Counter(x["result"] for x in report)))


if __name__ == "__main__":
    main()
