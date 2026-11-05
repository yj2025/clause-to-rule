"""금리 rule 을 코드로 기권시키면 ⑥ 이 «빈 출력» 을 넘는가 — 후처리 시험 (2026-11-05). GPU 없음.

    python gate_experiment.py

모델 출력은 그대로 두고 rule 을 걸러 다시 채점만 한다. 걸러 내는 규칙은 **원문과 출력만 본다**(정답을 안 본다).

    G0  거르지 않음
    G1  원문에 금리(%) 참조표가 있는 조문의 금리 rule 을 뺀다          ← «표 조문은 기권»
    G2  금리 rule 을 전부 뺀다                                            ← 상한선 확인용
    G3  금리 값이 원문에 그 숫자로 안 나오는 금리 rule 을 뺀다             ← «근거 없는 금리는 기권»
    G4  카탈로그에 없는 effect 를 뺀다 (REINVEST · ALLOW_* 처럼 지어낸 이름)
    G5  G3 + G4

세 묶음에서 잰다. kb10 에서 손실을 보고 규칙을 골랐으니 kb10 수치는 낙관적이다 —
**코퍼스(43)와 새 평가셋 v2(35, 학습 · 처방에 한 번도 안 씀)가 확인용이다.**
모든 출력에 P1(관문 탈락 → 빈 배열)을 먼저 건다 — 10단계 후보와 같은 조건.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lora"))
sys.path.insert(0, str(ROOT / "showcase"))

import catalog  # noqa: E402
import gold as G  # noqa: E402
import score_split as S  # noqa: E402
from scoring import score  # noqa: E402

RATE = {"RATE_ADD", "RATE_SUBTRACT", "RATE_OVERRIDE", "PENALTY_RATE"}


def rate_table(text):
    i = text.find("[참조표")
    return i >= 0 and bool(re.search(r"\d+(\.\d+)?\s*%", text[i:]))


def _nums(v):
    """effect value 에 든 수들. 수가 아니면 빈 목록."""
    if isinstance(v, bool):
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    if isinstance(v, dict):
        return [x for y in v.values() for x in _nums(y)]
    if isinstance(v, list):
        return [x for y in v for x in _nums(y)]
    return []


def grounded(rule, text):
    """금리 값의 수가 원문에 «수 + %» 로 나오는가. 값이 없으면 근거 없음으로 본다."""
    found = {float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)}
    ns = _nums((rule.get("effect") or {}).get("value"))
    return bool(ns) and all(any(abs(n - f) < 1e-9 for f in found) for n in ns)


def is_rate(r):
    return isinstance(r, dict) and r.get("status") == "OK" and (r.get("effect") or {}).get("type") in RATE


def invented(r):
    t = (r.get("effect") or {}).get("type") if isinstance(r, dict) else None
    return isinstance(r, dict) and r.get("status") == "OK" and t is not None and t not in catalog.EFFECTS


GATES = {
    "G0 거르지 않음": lambda rs, t: rs,
    "G1 금리표 조문의 금리 rule 기권": lambda rs, t: [r for r in rs if not (rate_table(t) and is_rate(r))],
    "G2 금리 rule 전부 기권": lambda rs, t: [r for r in rs if not is_rate(r)],
    "G3 근거 없는 금리 기권": lambda rs, t: [r for r in rs if not (is_rate(r) and not grounded(r, t))],
    "G4 지어낸 effect 기권": lambda rs, t: [r for r in rs if not invented(r)],
    "G5 G3 + G4": lambda rs, t: [r for r in rs if not invented(r) and not (is_rate(r) and not grounded(r, t))],
}


def runs_of(paths):
    """파일마다 {조문: P1 건 rules}."""
    out = []
    for p in paths:
        recs = [r for r in json.loads(Path(p).read_text("utf-8")) if "clause_id" in r and "error" not in r]
        if recs and "run" in recs[0]:
            for k in sorted({r["run"] for r in recs}):
                out.append({r["clause_id"]: S.rules_of(r, True) for r in recs if r["run"] == k})
        else:
            out.append({r["clause_id"]: S.rules_of(r, True) for r in recs})
    return out


def corpus():
    gold = {p.stem: json.loads(p.read_text("utf-8")) for p in sorted((ROOT / "data/gold").glob("K*.json"))}
    prod = json.loads((ROOT / "data/gold/_product.json").read_text("utf-8"))
    P = G.profiles()
    six = lambda c, rs: score(gold[c].get("rules") or [], rs, prod["aggregation"], P, prod["base_rate"])["rate"] * 100  # noqa: E731
    texts = {c["id"]: c["text"] for c in json.loads((ROOT / "data/corpus.json").read_text("utf-8"))}
    paths = [ROOT / f"results/results_v{v}.json" for v in (121, 123, 125, 127)]
    return "코퍼스 43 (새 정답 · ONE통장 안내 셋 제외)", list(gold), texts, six, paths


def kb10():
    texts = {c["id"]: c["text"] for c in json.loads((ROOT / "showcase/clauses_key.json").read_text("utf-8"))}
    ids = sorted(S.kb10six.DRAFT)
    paths = [ROOT / f"showcase/results_kb10v{v}{s}.json" for v in (121, 123, 125, 127) for s in "ab"]
    return "kb10 105 (정답 초안)", ids, texts, S.clause_six, paths


def v2():
    ids = [c["id"] for c in json.loads((ROOT / "data/gold_v2/_clauses.json").read_text("utf-8"))]
    texts = {c["id"]: c["text"] for c in json.loads((ROOT / "data/gold_v2/_clauses.json").read_text("utf-8"))}
    S.kb10six.DRAFT.update({i: json.loads((ROOT / f"data/gold_v2/{i}.json").read_text("utf-8")) for i in ids})
    S.kb10six.BASE_RATE.update({"HNSAL": 2.95, "HNDRM": 2.70, "HNWSH": 0.75})
    paths = [ROOT / "lora/results/v2_e1.json", ROOT / "lora/results/v2_base.json"]
    return "새 평가셋 v2 35 (e1 · 순정)", ids, texts, S.clause_six, paths


def main():
    for name, ids, texts, six, paths in (corpus(), kb10(), v2()):
        runs = runs_of([p for p in paths if p.exists()])
        empty = statistics.mean(six(c, []) for c in ids)
        print(f"\n== {name} · 회차 {len(runs)} · 빈 출력 ⑥ {empty:.1f}")
        print(f"   {'':30}{'⑥ 평균':>8}{'빈 출력 대비':>10}{'회차별':>8}")
        for g, f in GATES.items():
            vals = [statistics.mean(six(c, f(run.get(c, []), texts[c])) for c in ids) for run in runs]
            m = statistics.mean(vals)
            print(f"   {g:30}{m:8.1f}{m - empty:+10.1f}   " + " ".join(f"{v:.1f}" for v in vals))


if __name__ == "__main__":
    main()
