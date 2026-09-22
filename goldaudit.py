"""골드 초안을 기계로 따져 본다 — 사람 판단이 필요한 것만 남기려고.

`gold.py check` 는 ③④⑤ 를 본다 (인용문이 원문에 있나 · 이름이 카탈로그에 있나 ·
실행되나). 46조문 전부 통과한다. 여기서는 **그것이 못 보는 것**을 본다.

1. **걸림돌 주장이 지금도 사실인가.** 초안이 "출금 이벤트 없음" 이라 적었는데
   v17 에서 카탈로그에 넣었다면 그 주장은 낡았다. 낡은 주장 하나가
   확장 순위를 통째로 틀리게 만든다.

2. **빠뜨린 줄이 없나.** 조문에 규칙이 될 만한 줄인데 어느 rule 도 인용하지
   않았다면 초안이 놓쳤을 수 있다. ⑫ 의 '과소' 는 모델만 재지 초안은 안 잰다.

3. **초안이 헛조건을 담고 있나.** 정답에 언제나 참인 조건이 있으면
   ⑥ 이 그것을 정답으로 가르친다.

4. **UNSUPPORTED 인데 조건이 붙어 있나.** 관례는 `{}` 다. 다만
   **조건은 되는데 effect 만 없는 경우**에는 일부러 남긴다 — `DECISIONS.md` 참고.
   지금 둘 있고 둘 다 의도한 것이다.

셋 다 **기계로 끝난다.** 사람이 볼 것은 "이 줄이 정말 규칙인가" 같은
해석뿐이고, 이 도구가 그 목록을 좁혀 준다.

    python goldaudit.py
    python goldaudit.py --missed        # 빠뜨린 줄만
"""

import argparse
import json
import re
import sys
from pathlib import Path

import catalog
import vacuous as V

GOLD_DIR = Path("data/gold")

# 초안이 "없다" 고 주장한 것 → 카탈로그에서 그 주장을 깨뜨릴 이름
# 여기 적힌 이름이 카탈로그에 생기면 그 주장은 낡은 것이다.
CLAIMS = [
    ("출금 이벤트",   lambda: "WITHDRAWAL" in catalog.EVENTS),
    ("명의변경",     lambda: any("NAME" in k or "명의" in v
                                for k, v in catalog.EVENTS.items())),
    ("압류 계열 이벤트", lambda: any("SEIZ" in k or "압류" in v
                                 for k, v in catalog.EVENTS.items())),
    ("상품 전환 effect", lambda: any("SWITCH" in k or "TRANSFER" in k
                                  for k in catalog.EFFECTS)),
    ("최종거래일",    lambda: any("last" in k or "final" in k
                               for k in catalog.VARIABLES)),
    ("명의 유형 변수", lambda: any("holder" in k or "entity" in k
                                for k in catalog.VARIABLES)),
    ("적용 기준 금액", lambda: any("basis" in k or "BASIS" in k
                                for k in list(catalog.VARIABLES) + list(catalog.EFFECTS))),
    ("서비스 제공 effect", lambda: "SERVICE_PROVIDE" in catalog.EFFECTS),
    ("이월 금지 effect", lambda: "FEE_WAIVE_NO_CARRYOVER" in catalog.EFFECTS),
    ("출연 effect", lambda: "DORMANT_CONTRIBUTION" in catalog.EFFECTS),
    ("'거래 금지' effect", lambda: "RESTRICT" in catalog.EFFECTS),
    ("납부 경로 속성", lambda: "route" in catalog.EVENT_ATTRIBUTES.get("AUTO_TRANSFER", {})),
    ("계약 구분 속성", lambda: "source" in catalog.EVENT_ATTRIBUTES.get("SALARY_TRANSFER", {})),
]

# 규칙이 될 만한 줄인가 — 조판 기호와 말투로 거른다
# 2026-09-22 — `※` · `➢` · `☞` 를 빠뜨리고 있었다. **`※` 가 27줄이다.**
# 그냥 많은 게 아니라 **정답에서 실제로 규칙이 되는 줄**이다 — 인터넷뱅킹 해지
# 요건(`KBONE-S2-R12`)도, 실적 무관 면제(`KBYY-S2-R12`)도 전부 `※` 로 시작한다.
# 그 줄들을 한 번도 대조하지 않은 채 「빠뜨린 줄 13개」라고 적고 있었다.
# `[제목]` 은 조판 머리라 규칙이 아니므로 그대로 뺀다.
BULLET = re.compile(r"^\s*(▪|▶|➢|☞|※|·|-|\(?[가-힣]\)|\([0-9]+\)|[0-9]+\.)\s*")
RULEISH = re.compile(
    r"면제|우대|금리|불가|제한|해지|가입|지급|이자|대상|조건|한도|자격|중지|"
    r"제외|적용|부과|감면|산정")
# 안내문 — 규칙이 아니다
NOTICEY = re.compile(
    r"참고|안내|문의|홈페이지|고객센터|상담|바랍니다|참조|예시는|자세한 (내용|사항)")


def _gold():
    out = {}
    for p in sorted(GOLD_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        d = json.loads(p.read_text("utf-8"))
        out[d["clause_id"]] = d
    return out


def _corpus():
    return {x["id"]: x for x in
            json.loads(Path("data/corpus.json").read_text("utf-8"))}


def stale_claims(gold):
    """낡은 걸림돌 주장. 카탈로그에 생겼는데 아직 '없다' 고 적힌 것."""
    live = {name for name, probe in CLAIMS if probe()}
    hits = []
    for cid, d in gold.items():
        for r in d.get("rules") or []:
            if r.get("status") != "UNSUPPORTED":
                continue
            lab = r.get("label", "")
            for name in live:
                if name in lab:
                    hits.append((cid, r.get("rule_id"), name, lab))
    return hits, live


def missed_lines(gold, corpus):
    """규칙이 될 만한데 어느 rule 도 **인용하지 않은** 줄.

    2026-09-22 — 이름이 「빠뜨린 줄」이라 오해를 부른다. 이 검사가 보는 것은
    **인용(quote)** 이고, 조건식에 그 뜻이 담겼는지는 안 본다. 실물로 물렸다 —
    `KBYY-S2-R12` 의 「면제기간: 이번 달 11일부터」가 걸렸는데, 정답을 열어 보니
    조건식에 `{"day": 11}` 로 이미 들어 있었다. 인용이 수수료 행에 붙어 있었을 뿐이다.
    `KBYY-S5-R02` 의 「카드결제분 제외」도 `where.route` 에 이미 담겨 있었다.

    그래서 조문에 **규칙이 하나라도 있는지**를 같이 돌려준다. 규칙이 0개인 조문은
    그 줄이 정말 안 담긴 것이고, 규칙이 있으면 **조건식을 열어 봐야** 안다.
    """
    out = []
    for cid, d in gold.items():
        text = (corpus.get(cid) or {}).get("text", "")
        quoted = " ".join((r.get("source") or {}).get("quote", "")
                          for r in d.get("rules") or [])
        for raw in text.splitlines():
            line = raw.strip()
            if len(line) < 12 or not BULLET.match(line):
                continue
            if not RULEISH.search(line) or NOTICEY.search(line):
                continue
            core = BULLET.sub("", line)[:18]
            if core and core in quoted:
                continue
            out.append((cid, line, len(d.get("rules") or []), bool(d.get("reviewed"))))
    # 규칙이 0개인 조문을 먼저 — 사람이 볼 값이 가장 큰 자리다
    out.sort(key=lambda x: (x[2] != 0, x[0]))
    return out


def gold_vacuity(gold):
    out = []
    for cid, d in gold.items():
        for r in d.get("rules") or []:
            if not isinstance(r, dict):
                continue
            for kind, why in V.check_rule(r):
                if kind == "헛조건":
                    out.append((cid, r.get("rule_id"), why))
    return out


def unsupported_with_condition(gold):
    out = []
    for cid, d in gold.items():
        for r in d.get("rules") or []:
            if r.get("status") == "UNSUPPORTED" and (r.get("condition") or {}):
                out.append((cid, r.get("rule_id")))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--missed", action="store_true")
    a = ap.parse_args(argv)
    gold, corpus = _gold(), _corpus()

    missed = missed_lines(gold, corpus)
    if a.missed:
        shown = None
        for cid, line, n, rev in missed:
            if (n == 0) != shown:
                shown = (n == 0)
                print("\n── 규칙이 하나도 없는 조문 — 그 줄이 정말 안 담겼다 ──"
                      if shown else
                      "\n── 규칙은 있다 — 인용만 안 붙었는지 조건식을 열어 봐야 안다 ──")
            mark = "검토✓" if rev else "초안 "
            print(f"{cid:<16}{mark} rule{n:>2}  {line[:74]}")
        print(f"\n{len(missed)}줄 · {len({c for c, _, _, _ in missed})}조문")
        return 0

    print(f"골드 {len(gold)}조문 · "
          f"rule {sum(len(d.get('rules') or []) for d in gold.values())}개\n")

    stale, live = stale_claims(gold)
    print(f"■ 낡은 걸림돌 주장 — 카탈로그에 생겼는데 '없다' 고 적힌 것")
    print(f"  지금 카탈로그에 있는 것: {', '.join(sorted(live)) or '없음'}")
    if stale:
        for cid, rid, name, lab in stale:
            print(f"  ✗ {cid:<16} {rid:<20} '{name}' 를 없다고 적었다")
            print(f"      {lab[:76]}")
    else:
        print("  낡은 주장 없음")

    vac = gold_vacuity(gold)
    print(f"\n■ 초안이 담은 헛조건")
    if vac:
        for cid, rid, why in vac:
            print(f"  ✗ {cid:<16} {rid:<20} {why[:60]}")
    else:
        print("  없음")

    uwc = unsupported_with_condition(gold)
    print(f"\n■ UNSUPPORTED 인데 조건이 붙은 rule (의도한 것 — DECISIONS.md)")
    if uwc:
        for cid, rid in uwc:
            print(f"  · {cid:<16} {rid}   조건은 되는데 effect 가 없다")
    else:
        print("  없음")

    zero = [m for m in missed if m[2] == 0]
    print(f"\n■ 어느 rule 도 **인용하지 않은** 줄 — {len(missed)}줄 / "
          f"{len({c for c, _, _, _ in missed})}조문")
    print(f"  그중 **규칙이 하나도 없는 조문** {len(zero)}줄 / "
          f"{len({c for c, _, _, _ in zero})}조문 — 여기가 사람이 볼 자리다.")
    print("  나머지는 규칙이 있다. 인용만 안 붙었을 수 있으니 조건식을 열어 봐야 안다")
    print("  `--missed` 로 전부 본다 — 규칙이 없는 조문부터 찍는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
