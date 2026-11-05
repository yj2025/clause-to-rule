"""kb10 의 ⑥ — `showcase/gold_draft/` 의 정답 초안이 있는 조문만 잰다 (2026-10-03).

    python showcase/kb10six.py showcase/results_kb10v101a.json showcase/results_kb10v101b.json ...

정답은 에이전트 초안을 사람이 검토한 것이다 (10-06 · 11-05 로 105조문 모두 검토 완료).
상품마다 기본금리가 다르다 — 접두어로 `BASE_RATE` 를 고른다. 합산 방식은 코퍼스와 같이 SUM.
프로필은 코퍼스와 같은 `gold.profiles()` 다 (명의 유형은 INDIVIDUAL 로 고정 — 그 축은 ⑥ 이 못 본다).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import gold  # noqa: E402
from scoring import score  # noqa: E402

# KBSME 는 kb10_best 의 2.0 이 아니라 조문 표(36개월 2.5%)를 따른다 — 2026-10-03 판단 (정답 초안 쟁점 3)
BASE_RATE = {"KBGL": 0.1, "KBSSG": 0.1, "KBNR": 0.1, "KBSME": 2.5, "KBMER": 1.95, "KBMY": 2.25,
             "KBHAP": 3.7, "KBSUP": 0.0, "KBSTR": 2.05, "KBGEN": 0.0}
DRAFT = {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(Path("showcase/gold_draft").glob("*.json"))}
P = gold.profiles()


def six(path):
    out = {}
    for x in json.load(open(path)):
        g = DRAFT.get(x["clause_id"])
        if g is None:
            continue
        got = (x.get("output") or {}).get("rules")
        out[x["clause_id"]] = score(g.get("rules") or [], got if isinstance(got, list) else [], "SUM", P,
                                    BASE_RATE[x["clause_id"].split("-")[0]])["rate"] * 100
    return out


if __name__ == "__main__":
    runs = {p.split("results_")[-1][:-5]: six(p) for p in sys.argv[1:]}
    ids = sorted(DRAFT)
    print(f"정답 초안 {len(ids)}조문 · 갈래: " + " · ".join(f"{k} {v}" for k, v in sorted(
        __import__("collections").Counter(gold.group_of(DRAFT[c]) for c in ids).items())))
    print(f"{'':16}" + "".join(f"{k[-6:]:>9}" for k in runs))
    for c in ids:
        print(f"{c:16}" + "".join(f"{r.get(c, float('nan')):9.1f}" for r in runs.values()))
    print(f"{'평균':16}" + "".join(f"{sum(r.values()) / max(1, len(r)):9.1f}" for r in runs.values()))
    print(f"{'빈 출력이면':16}" + "".join(
        f"{sum(score(DRAFT[c].get('rules') or [], [], 'SUM', P, BASE_RATE[c.split('-')[0]])['rate'] * 100 for c in ids) / len(ids):9.1f}"
        for _ in runs))
