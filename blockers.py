"""카탈로그 확장 하나가 조문 몇 개를 실제로 푸는가.

`CATALOG_PROPOSAL.md` 는 확장 항목의 우선순위를 **그 항목을 언급한 조문 수**로
매겼다. 그건 틀린 셈법이다. 한 조문의 UNSUPPORTED rule 이 두 가지를 동시에
요구하면, 하나만 넣어서는 **아무것도 안 풀린다.**

v17 이 출금 이벤트를 넣었다. 제안서에서 2순위였고 "8조문이 여기 걸린다" 고
적혀 있었다. 실제로 풀린 조문은 **0개**다 — 출금을 요구한 조문은 전부
명의변경·출금한도·발급기준일 같은 **다른 것도 같이** 요구했다.

여기서는 골드의 UNSUPPORTED rule 라벨에서 걸림돌을 뽑아
* 항목 하나가 **단독으로** 푸는 조문 수
* 욕심 알고리즘으로 고른 **묶음**이 푸는 조문 수
를 센다.

라벨의 "— X 없음" 꼴에 기대는 키워드 추출이다. 정확한 목록이 아니라
**우선순위를 뒤집는 데 쓰는 근사치**다. 실물은 `--list` 로 확인할 것.

    python blockers.py
    python blockers.py --list 상품전환
"""

import argparse
import collections
import json
import sys
from pathlib import Path

GOLD_DIR = Path("data/gold")

# 라벨에 나타나는 말 → 확장 항목 이름
KEYS = [
    ("상품전환",   ("상품 전환 effect", "전환 effect", "전환 차단 effect")),
    ("최종거래일", ("최종거래일",)),
    ("이자가산",   ("이자 가산 effect", "원금 가산")),
    ("기준금액",   ("적용 기준 금액",)),
    ("명의유형",   ("명의 유형 변수",)),
    ("계좌지정",   ("계좌 지정 여부",)),
    ("세제",       ("비과세", "세율 effect", "세제 effect")),
    ("거래금지",   ("'거래 금지' effect",)),
    ("압류",       ("압류 계열 이벤트",)),
    ("면제이월",   ("이월",)),
    ("차감",       ("차감 effect",)),
    ("가맹점대금",   ("가맹점대금 입금 이벤트",)),
    ("발급일",     ("발급일 변수", "발급기준일")),
    ("출금",       ("출금 이벤트",)),
    ("계좌종류",   ("계좌 종류 변수", "예금 종류 변수", "상품 기준 변수",
                  "예금과목(상품 종류) 변수", "예금과목 세부 구분")),
    # 2026-09-20 상품 코드 체계. 전환 effect 는 생겼고 «어느 상품이 전환 가능한가» 가 남았다
    ("전환기준",   ("상품별 전환 가능 기준",)),
    ("결산일",     ("결산일",)),
    ("기간표현",   ("기간 조건을 표현할 수단", "기간·")),
    ("이벤트속성", ("계약 구분 속성", "납부 경로 속성")),
    ("제휴서비스", ("제3자 서비스 제공 effect", "서비스 제공 effect")),
    ("명의변경",   ("명의변경",)),
    ("질권",       ("질권설정을 가리킬",)),
    ("법령개정",   ("법령 개정 조건",)),
    ("서비스변경", ("축소·변경 사건",)),
    # 2026-09-15 에 더했다. 이 키가 없어 휴면예금 두 조문을 "최종거래일 하나로 풀린다" 고
    # 셌다 — 라벨은 처음부터 "최종거래일 변수와 출연 effect 없음" 이었다.
    ("출연",       ("출연 effect",)),
    # 2026-09-20 실행기 범위 결정. 거래중지 두 조문이 편입시기(연 2회 · 특정 요일)로 막혔다.
    ("편입시기",   ("편입시기",)),
]


def blockers_of(label):
    """라벨 하나에서 걸림돌 이름들. 하나도 못 찾으면 빈 집합."""
    out = set()
    for name, words in KEYS:
        if any(w in label for w in words):
            out.add(name)
    return out


def load():
    """조문 → {rule_id: 걸림돌 집합}. UNSUPPORTED rule 만."""
    out = {}
    for p in sorted(GOLD_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        d = json.loads(p.read_text("utf-8"))
        rs = {r.get("rule_id") or str(i): blockers_of(r.get("label", ""))
              for i, r in enumerate(d.get("rules") or [])
              if r.get("status") == "UNSUPPORTED"}
        if rs:
            out[d["clause_id"]] = rs
    return out


def unlocked(clauses, have):
    """`have` 를 넣었을 때 UNSUPPORTED rule 이 하나도 안 남는 조문."""
    done = []
    for cid, rs in clauses.items():
        if all(b and b <= have for b in rs.values()):
            done.append(cid)
    return done


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", metavar="항목")
    ap.add_argument("--depth", type=int, default=4)
    a = ap.parse_args(argv)
    clauses = load()

    if a.list:
        for cid, rs in sorted(clauses.items()):
            for rid, b in rs.items():
                if a.list in b:
                    print(f"{cid:<16} {rid:<20} {' '.join(sorted(b))}")
        return 0

    names = sorted({n for rs in clauses.values() for b in rs.values() for n in b})
    unknown = sum(1 for rs in clauses.values() for b in rs.values() if not b)
    print(f"UNSUPPORTED 를 가진 조문 {len(clauses)}개 · "
          f"걸림돌을 못 읽은 rule {unknown}개\n")

    cnt = collections.Counter()
    for rs in clauses.values():
        for b in rs.values():
            for n in b:
                cnt[n] += 1
    print(f"{'항목':<12}{'걸린 rule':>10}{'단독으로 푸는 조문':>18}")
    print("-" * 42)
    for n, k in cnt.most_common():
        solo = unlocked(clauses, {n})
        print(f"{n:<12}{k:>10}{len(solo):>16}  {' '.join(solo)}")

    print("\n묶어서 넣으면 — 욕심 알고리즘")
    have, prev = set(), 0
    for step in range(a.depth):
        best, gain = None, 0
        for n in names:
            g = len(unlocked(clauses, have | {n}))
            if g > gain:
                best, gain = n, g
        if best is None or gain <= prev:
            break
        have.add(best)
        prev = gain
        print(f"  {step + 1}개째 +{best:<12} 누적 {gain}조문  "
              f"({' '.join(sorted(have))})")
    print("\n제안서의 '언급 조문 수' 로 순위를 매기면 안 된다 — "
          "걸림돌은 묶여서 온다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
