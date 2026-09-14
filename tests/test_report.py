

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
