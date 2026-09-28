"""문서에 박힌 수치가 **지금 값과 맞나**.

브리핑에서 두 번 겪었다 — **표는 갈고 본문에 옛 수치를 남겼다**
(2026-09-23 · 2026-09-25). 사람이 읽어서 잡았다. 자동으로 잡는다.

**전부를 검사하지 않는다.** 정규식으로 캐는 것은 깨지기 쉽다. 여기 있는 것은
**계산으로 확인할 수 있고 실제로 틀린 적이 있는** 것만이다. 새 수치를 문서에
박을 때 여기 한 줄 더하면 다음 사람이 낡은 값을 안 본다.
"""

import json
import re

import pytest

# (이름, 정규식, 지금 값을 내는 함수)
CHECKS = []


def _gold(root):
    return {p.stem: json.loads(p.read_text("utf-8"))
            for p in sorted((root / "data" / "gold").glob("*.json"))
            if not p.name.startswith("_")}


def test_clause_count_is_right(root):
    """「46조문」 — 조문이 늘거나 줄면 문서가 통째로 낡는다."""
    n = len(_gold(root))
    bad = []
    for doc in ("STATUS.md", "README.md", "METHOD.md"):
        text = (root / doc).read_text("utf-8")
        for m in re.finditer(r"(\d+)\s*조문", text):
            k = int(m.group(1))
            # 46 을 말하는 자리만 본다 — 갈래별 조문 수(12·9·4·21)는 다른 값이다
            if k in (44, 45, 46, 47, 48) and k != n:
                bad.append(f"{doc}: {m.group(0)}")
    assert not bad, f"조문 수는 {n} 인데 문서가 다르게 말한다: {bad}"


def test_reviewed_count_is_right(root):
    """「11조문 사람 검토 완료」 — 검토가 진행되면 이 값이 움직인다."""
    n = sum(1 for g in _gold(root).values() if g.get("reviewed"))
    text = (root / "STATUS.md").read_text("utf-8")
    m = re.search(r"\*\*(\d+)조문 사람 검토 완료\*\*", text)
    assert m, "STATUS.md 에서 검토 완료 수를 못 찾았다 — 문구가 바뀌면 이 시험도 고친다"
    assert int(m.group(1)) == n, f"검토 완료는 {n}조문인데 STATUS.md 는 {m.group(1)}조문이라 한다"


def test_abstain_baseline_is_right(root):
    """**기준선** — 어휘가 넓어지면 내려간다. 실제로 88.0 → 71.2 → 64.1 로 왔다.

    이 값이 틀리면 「기준선을 넘었나」라는 이 저장소의 본 질문이 통째로 틀린다.

    **「틀린 값을 찾는다」가 아니라 「지금 값이 들어 있나」로 본다.** 처음에는
    60 대 수치를 전부 훑었는데 ⑤ 63.6% 같은 다른 지표를 기준선으로 오해했고,
    줄 단위로 좁혀도 이력 수치(88.0 → 71.2 → 64.1)까지 잡았다. **문맥이 풍부한
    산문에서 «틀린 값»을 정규식으로 가리는 것은 과하다.** 기준선이 움직이면
    그것을 말하는 문서에 새 값이 없을 테니, 그것만 본다.
    """
    import statistics
    import sys
    sys.path.insert(0, str(root))
    import gold
    from scoring import score
    tpl = _gold(root)
    prod = json.loads((root / "data" / "gold" / "_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()
    now = statistics.mean(
        score(g.get("rules") or [], [], agg, P, base)["rate"] * 100
        for g in tpl.values())
    want = f"{now:.1f}"
    missing = [doc for doc in ("STATUS.md", "METHOD.md", "brief.py")
               if "기준선" in (root / doc).read_text("utf-8")
               and want not in (root / doc).read_text("utf-8")]
    assert not missing, (
        f"기준선이 {want}% 인데 그것을 말하는 문서에 그 값이 없다: {missing}. "
        "어휘가 바뀌면 기준선이 움직인다 — 문서를 같이 고친다")
