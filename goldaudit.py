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
BULLET = re.compile(r"^\s*(▪|▶|·|-|\(?[가-힣]\)|\([0-9]+\)|[0-9]+\.)\s*")
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
    """규칙이 될 만한데 어느 rule 도 인용하지 않은 줄."""
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
            out.append((cid, line))
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
        for cid, line in missed:
            print(f"{cid:<16} {line[:88]}")
        print(f"\n{len(missed)}줄 · {len({c for c, _ in missed})}조문")
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

    print(f"\n■ 빠뜨렸을 수 있는 줄 — {len(missed)}줄 / "
          f"{len({c for c, _ in missed})}조문")
    print("  규칙이 될 만한 조판인데 어느 rule 도 인용하지 않았다.")
    print("  `--missed` 로 전부 본다. **여기만 사람 판단이 필요하다.**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
