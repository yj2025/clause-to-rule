"""kb10 에서 모델이 «빈 출력» 보다 점수를 잃는 조문과, 그 조문에 낸 effect (2026-11-05).

    python showcase/kb10loss.py showcase/results_kb10v127a.json showcase/results_kb10v127b.json

정답 초안 기준. 조문마다 (모델 ⑥ − 빈 출력 ⑥) 를 내고, 잃는 조문에 모델이 낸 effect 종류와
원문에 금리 표(%) 가 있는지를 붙인다. 표 조문을 코드로 기권시킬지 정하기 전에 손실이 어디서
오는지 보려는 것이다.
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "showcase")
import kb10six as K  # noqa: E402
from scoring import score  # noqa: E402

TEXT = {c["id"]: c["text"] for c in json.loads(Path("showcase/clauses_key.json").read_text("utf-8"))}


def rate_table(text):
    """원문에 금리(%)가 든 참조표가 있는가."""
    i = text.find("[참조표")
    return i >= 0 and bool(re.search(r"\d+(\.\d+)?\s*%", text[i:]))


def empty_six(cid):
    return score(K.DRAFT[cid].get("rules") or [], [], "SUM", K.P, K.BASE_RATE[cid.split("-")[0]])["rate"] * 100


def main(paths):
    empty = {c: empty_six(c) for c in K.DRAFT}
    loss = collections.defaultdict(list)
    effs = collections.defaultdict(collections.Counter)
    for p in paths:
        six = K.six(p)
        for x in json.load(open(p)):
            c = x["clause_id"]
            if c not in six:
                continue
            loss[c].append(six[c] - empty[c])
            for r in (x.get("output") or {}).get("rules") or []:
                if isinstance(r, dict) and r.get("status") == "OK":
                    effs[c][(r.get("effect") or {}).get("type")] += 1
    rows = sorted(((sum(v) / len(v), c) for c, v in loss.items()), key=lambda t: t[0])
    total = sum(d for d, _ in rows) / len(rows)
    print(f"조문 {len(rows)} · 모델 − 빈 출력 평균 {total:+.1f}p (음수 = 빈 출력보다 못함)")
    lost = [(d, c) for d, c in rows if d < 0]
    print(f"잃는 조문 {len(lost)} · 잃는 양 합 {sum(d for d, _ in lost) / len(rows):+.1f}p · "
          f"그중 금리 표 조문 {sum(rate_table(TEXT[c]) for _, c in lost)}")
    for d, c in lost:
        e = ", ".join(f"{k}×{n}" for k, n in effs[c].most_common())
        print(f"  {d:+7.1f}  {c:15} {'표' if rate_table(TEXT[c]) else '  '}  {e}")
    gained = [(d, c) for d, c in rows if d > 0]
    print(f"얻는 조문 {len(gained)} · 얻는 양 합 {sum(d for d, _ in gained) / len(rows):+.1f}p")


if __name__ == "__main__":
    main(sys.argv[1:])
