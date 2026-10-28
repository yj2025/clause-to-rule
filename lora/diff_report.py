"""제약 켜고 끈 결과 비교 — README 의 3 · 4단계 해석 근거 (2026-10-27). GPU 없음.

    python lora/diff_report.py | tee lora/logs/diff_report.log

A) kb10 test: e1 + P1 (test_e1, P1 은 채점 때 얹음) vs e1 + 제약 + P1 (test_e1_c) — ⑥ 이 갈린 조문과 그 까닭(관문 · P1).
B) 보류 풀: rule 을 낸 출력의 첫 탈락 관문, 제약 켜고 끌 때 최종 rule 유무 변화, 제약 하에 남은 catalog 실패 메시지.
출력은 조문 ID · 점수 · 개수 · 검증기 메시지뿐 — 정답 내용은 찍지 않는다 (정답은 «rule 있음/없음» 만).
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score_split as S  # noqa: E402  (ROOT 로 chdir)

GATES = S.E.GATES


def load(p):
    return {r["clause_id"]: r for r in json.load(open(p)) if "clause_id" in r}


def gates(r):
    return sum(bool((r.get("final") or {}).get(k)) for k in GATES)


def raw_rules(r):
    return (r.get("gate_dropped") or r.get("output") or {}).get("rules") or []


def part_a():
    print("A) kb10 test — e1 + P1 vs e1 + 제약 + P1")
    ids = S.E.split_ids("test")
    a, b = load("lora/results/test_e1.json"), load("lora/results/test_e1_c.json")
    win = lose = 0
    for i in ids:
        ra, rb = S.rules_of(a[i], True), S.rules_of(b[i], False)   # test_e1_c 는 러너에 P1 이 이미 있다
        sa, sb = S.clause_six(i, ra), S.clause_six(i, rb)
        if abs(sa - sb) < 1e-6:
            continue
        win += sb > sa
        lose += sb < sa
        da = bool(raw_rules(a[i])) and not ra                       # 끔: P1 이 버렸나
        db = b[i].get("gate_dropped") is not None
        print(f"  {i:16} 정답rule={'Y' if S.ok_rules(S.kb10six.DRAFT[i]['rules']) else 'N'}  ⑥ {sa:5.1f} → {sb:5.1f}"
              f"   끔: OK rule {len(S.ok_rules(ra))} · 관문 {gates(a[i])} · P1버림 {'Y' if da else 'N'}"
              f"  |  켬: OK rule {len(S.ok_rules(rb))} · 관문 {gates(b[i])} · P1버림 {'Y' if db else 'N'}")
    print(f"  갈린 조문 {win + lose} · 제약 쪽 이김 {win} · 짐 {lose}")


def part_b():
    print("\nB) 보류 풀 111")
    runs = {n: load(f"lora/results/pool_{n}.json") for n in ("base", "base_c", "e1", "e1_c")}
    for n, rs in runs.items():
        first = Counter()
        for r in rs.values():
            if raw_rules(r):
                f = r.get("final") or {}
                first[next((k for k in GATES if not f.get(k)), "다 통과")] += 1
        print(f"  {n:7} rule 낸 출력의 첫 탈락 관문: {dict(first)}")
    for off, on in (("base", "base_c"), ("e1", "e1_c")):
        c = Counter((bool((runs[off][k].get("output") or {}).get("rules")), bool((runs[on][k].get("output") or {}).get("rules")))
                    for k in runs[off])
        print(f"  {off} → {on} 최종 rule (끔, 켬): " + " · ".join(f"{x}{y}: {v}" for (x, y), v in sorted(c.items())))
    for n in ("base_c", "e1_c"):
        for r in runs[n].values():
            if raw_rules(r) and not (r.get("final") or {}).get("catalog_ok"):
                print(f"  {n} catalog 실패 {r['clause_id']}: {str(r.get('errors'))[:200]}")


if __name__ == "__main__":
    part_a()
    part_b()
