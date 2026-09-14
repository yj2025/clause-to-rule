

def test_the_abstention_baseline_is_computed_and_printed(root):
    """아무것도 안 만드는 모델의 ⑥ 점수를 같이 찍어야 한다.

    이전 실험(30조문)에서 이 값이 92.6% 였고 일곱 라운드가 전부 그 아래였다 —
    **⑥ 은 뜻이 아니라 기권율을 재고 있었다.** 저장소가 날아가면서 이 검사가
    사라졌고 그 뒤 아홉 라운드를 기준선 없이 찍었다.

    46조문에서도 88.0% 다. 기권만으로 만점을 받는 조문이 37개다 —
    gold 가 빈 배열인 13개와, gold rule 이 전부 UNSUPPORTED 라
    실행 결과가 빈 배열과 같은 24개.
    """
    import os, json
    os.chdir(root)
    from pathlib import Path
    import gold, report
    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    rate, perfect = report.abstain_baseline(
        tpl, prod["aggregation"], gold.profiles(), prod["base_rate"])
    assert 80 < rate < 95, f"기준선이 {rate:.1f}% 다 — 예상 범위 밖"
    assert perfect > len(tpl) // 2, "기권만으로 만점인 조문이 절반을 넘는다"


def test_no_round_has_ever_beaten_the_abstention_baseline(root):
    """지금까지 어느 라운드도 기준선을 넘지 못했다. 넘으면 이 시험을 고칠 것.

    넘는 날이 오면 그것이 이 프로젝트의 첫 진짜 성과다.
    """
    import os, json, statistics
    os.chdir(root)
    from pathlib import Path
    import gold, report
    from scoring import score
    tpl = {p.stem: json.loads(p.read_text("utf-8"))
           for p in sorted(Path("data/gold").glob("*.json"))
           if not p.name.startswith("_")}
    prod = json.loads(Path("data/gold/_product.json").read_text("utf-8"))
    agg, base, P = prod["aggregation"], prod["base_rate"], gold.profiles()
    b, _ = report.abstain_baseline(tpl, agg, P, base)
    recs = [x for x in json.loads(
        Path("results/results_v22.json").read_text("utf-8")) if x["run"] == 0]
    ss = []
    for x in recs:
        g = tpl.get(x["clause_id"])
        if not g:
            continue
        got = (x.get("output") or {}).get("rules")
        ss.append(score(g.get("rules") or [],
                        got if isinstance(got, list) else [],
                        agg, P, base)["rate"] * 100)
    assert statistics.mean(ss) < b, "기준선을 넘었다 — 이 시험을 고치고 축하할 것"


def test_gate_swaps_are_not_called_damage(root):
    """관문을 맞바꾼 것과 총수가 줄어든 것을 갈라 센다.

    "결과를 망가뜨린 회차" 하나로 세던 것이 과장이었다. 기준선 7건을
    열어 보니 다섯은 관문 수가 같은 맞바꿈이고 둘은 오히려 늘었다(합계 +2).

    채택 규칙을 "관문을 하나라도 잃으면 안 받는다" 로 바꾸는 실험을
    저장된 결과로 돌려 봤더니 KBONE-S2-R20 에서 관문을 오히려 하나 잃는다.
    GPU 없이 확인하고 바꾸지 않기로 했다.
    """
    import os, json
    os.chdir(root)
    from pathlib import Path
    GATES = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")
    recs = json.loads(Path("results/results_base3.json").read_text("utf-8"))
    lost = [x for x in recs
            if any(x["first"][k] and not x["final"][k] for k in GATES)]
    n = lambda m: sum(1 for k in GATES if m[k])
    worse = [x for x in lost if n(x["final"]) < n(x["first"])]
    assert lost, "맞바꾼 회차가 있어야 이 시험이 의미가 있다"
    assert not worse, (
        "관문 총수가 줄어든 회차가 생겼다 — 채택 규칙이 깨진 것이다. "
        f"{[(x['clause_id'], x['run']) for x in worse]}")


def test_rescore_does_not_touch_the_file(root):
    """저장된 관문 표시는 **그때 잰 값**이고 기록이다.

    채점을 고칠 때마다 덮어쓰면 문서에 적힌 수치와 어긋난다.
    2026-09-14 에 실제로 한 번 덮어썼다가 되돌렸다.
    """
    import os, json, hashlib
    os.chdir(root)
    from pathlib import Path
    import report
    f = Path("results/results_base3.json")
    before = hashlib.sha256(f.read_bytes()).hexdigest()
    recs = json.loads(f.read_text("utf-8"))
    out = report.rescore(recs)
    assert hashlib.sha256(f.read_bytes()).hexdigest() == before, "파일이 바뀌었다"
    assert recs[0]["final"] is not out[0]["final"], "원본을 그대로 돌려주면 안 된다"
    assert len(out) == len(recs)


def test_rescore_changes_the_marks_when_the_schema_changed(root):
    """스키마를 풀었으므로 옛 라운드의 ② 가 오른다."""
    import os, json
    os.chdir(root)
    from pathlib import Path
    import report
    recs = json.loads(Path("results/results_base3.json").read_text("utf-8"))
    now = sum(1 for x in recs if x["final"]["schema_ok"])
    new = sum(1 for x in report.rescore(recs) if x["final"]["schema_ok"])
    assert new > now, "UNSUPPORTED 의 condition 을 풀었으니 올라야 한다"
