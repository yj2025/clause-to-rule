"""결함을 세는 축은 **골드에서 0 이 나와야 한다.**

골드는 정답이다. 정답을 생성물인 것처럼 축에 돌렸을 때 결함이 잡히면
그 축이 틀린 것이다 — 모델이 아니라.

2026-09-14 에 이 검사를 처음 돌렸더니 ⑪ 이 골드에서 **34번** 발동했다.
전부 한 모양이었다 — 수수료 면제 rule 이 면제 대상 표의 행을 인용하고
조건은 면제조건 줄에서 온다. 인용문은 **효과의 대상**을 가리키고
조건의 근거는 다른 줄에 있다. 그게 맞는 구조다.

⑪ 이 "인용문 하나가 조건과 효과를 둘 다 받쳐야 한다" 고 가정하고 있었다.
고치니 보고값이 15.2% → 0.0% 가 됐다. **거의 전부 오탐이었다.**

축을 새로 만들면 **반드시 골드에 먼저 돌려 본다.**
"""

import json

import pytest


@pytest.fixture
def as_records(root):
    import os
    os.chdir(root)
    out = []
    for p in sorted((root / "data/gold").glob("*.json")):
        if p.name.startswith("_"):
            continue
        d = json.loads(p.read_text("utf-8"))
        out.append({"clause_id": d["clause_id"], "run": 0,
                    "output": {"rules": d.get("rules") or []}})
    return out


@pytest.fixture
def texts(root):
    return {x["id"]: x["text"] for x in
            json.loads((root / "data/corpus.json").read_text("utf-8"))}


def test_grounding_finds_nothing_in_gold(as_records, texts):
    import grounding
    a = grounding.audit(as_records, texts)
    assert a["bad_clauses"] == 0, f"⑨ 가 골드를 잡는다: {a['by_clause']}"


def test_quote_support_finds_nothing_in_gold(as_records, texts):
    """⑪ 이 여기서 34건을 냈다. 수수료 면제의 인용문은 효과의 대상을 가리킨다."""
    import support
    bad = [(x["clause_id"], e) for x in as_records
           for r in x["output"]["rules"]
           for e in support.check_rule(r, texts.get(x["clause_id"], ""))]
    assert not bad, f"⑪ 이 골드를 잡는다 ({len(bad)}건): {bad[:2]}"


def test_invented_codes_finds_nothing_in_gold(as_records):
    import invent
    a = invent.audit(as_records)
    assert a["bad"] == 0, f"⑬ 이 골드를 잡는다"


def test_vacuity_finds_nothing_in_gold(as_records):
    import vacuous
    a = vacuous.audit(as_records)
    assert a["bad"] == 0, f"⑭ 가 골드를 잡는다"
    rest = [x for x in as_records if x["clause_id"] not in KNOWN_IDLE]
    assert vacuous.audit(rest)["idle"] == 0, f"⑭ 가 골드에서 미가동을 잡는다"


# **알고 두는 측정 구멍.** 2026-09-15 SERVICE_PROVIDE 로 옮긴 표의 "만 7세 –" 하한은
# 채점 프로필의 나이(17 · 19)로는 안 흔들린다. 헛조건은 아니다 — 반례 표본에 6세가 있다.
# 프로필 나이 축에 6 을 더해 봤더니 1024 → 1536 이 되고 기준선 ⑩ 이 75.0 → 66.7 로
# 움직였다. 확정한 판정선을 버려야 해서 되돌렸다. 대가는 ⑥ 이 이 하한을 빠뜨린
# 생성물을 못 가리는 것 하나다.
KNOWN_IDLE = {"KBYY-S3-R05": 2}


def test_known_idle_conditions_are_exactly_these(as_records):
    import vacuous
    for cid, n in KNOWN_IDLE.items():
        one = [x for x in as_records if x["clause_id"] == cid]
        assert vacuous.audit(one)["idle"] == n, cid


def test_no_unconditional_disqualify_in_gold(as_records):
    import compose
    assert compose.unconditional_disqualify(as_records) == []


def test_declaration_scores_gold_perfectly(as_records):
    """⑫ 는 골드 대 골드라 100% 여야 한다. 아니면 채점기가 틀린 것이다."""
    import declare
    assert declare.audit(as_records, run=0)["rate"] == 100.0
