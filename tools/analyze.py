"""결과 파일 읽기 — 비율과 틀린 형태 세기.

지표 하나로는 한 라운드에 넣은 변경 둘을 못 나눈다. 틀린 **형태**를 각각 세면
지표가 안 움직여도 어느 처방이 먹었는지 나온다 (§9 12번).

    python tools/analyze.py forms results/a.json results/b.json
"""
import sys, pathlib  # 저장소 루트 · tools · experiments 에서 모듈을 찾는다 (2026-11-06 폴더 정리)
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / d) for d in ("", "tools", "experiments")]

import collections
import json
import re
import sys
from pathlib import Path

KEYS = ("json_ok", "schema_ok", "catalog_ok", "quote_ok", "exec_ok")


def rate(records, phase, key):
    """records 의 phase("first"/"final") 에서 key 가 참인 비율(%)."""
    if not records:
        return 0.0
    return sum(bool(x[phase][key]) for x in records) / len(records) * 100


def load(path):
    return json.loads(Path(path).read_text("utf-8"))


# ── 틀린 형태 세기 ──────────────────────────────────────────────────────
def _walk(node, fn):
    if isinstance(node, dict):
        fn(node)
        for v in node.values():
            _walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            _walk(v, fn)


def forms(records):
    """생성물에서 틀린 형태를 센다. 지표가 제자리여도 이건 움직인다."""
    c = collections.Counter()
    for x in records:
        rules = (x.get("output") or {}).get("rules") or []
        for r in rules:
            if not isinstance(r, dict):
                continue
            bound = set(r.get("let") or {})

            def look(node, bound=bound):
                if set(node) == {"var"}:
                    return                      # 피연산자 자리의 var 는 정상
                for k, v in node.items():
                    if k == "ref" and str(v).lstrip("$") not in bound:
                        c["미바인딩 $ref"] += 1
                    if k in ("and", "or") and not isinstance(v, list):
                        c[f"{k} 에 배열 아닌 것"] += 1
                    if k in ("count_events", "count_distinct_months",
                             "count_consecutive_months") and set(v or {}) - {"event", "within", "where"}:
                        c["count_* 에 군더더기 키"] += 1

            for part in ("condition", "guard"):
                if part in r:
                    _walk(r[part], look)
            cond = r.get("condition")
            if isinstance(cond, dict) and set(cond) == {"var"}:
                c["var 단독 조건식"] += 1
            eff = r.get("effect") or {}
            if eff.get("type") in ("RATE_ADD", "RATE_SUBTRACT",
                                   "RATE_OVERRIDE", "PENALTY_RATE"):
                v = eff.get("value")
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    c["금리 value 가 수가 아님"] += 1
        for e in x.get("errors") or []:
            m = re.match(r"정의되지 않은 연산자: ([^.]+)", e)
            if m:
                c[f"지어낸 연산자 {m.group(1).strip()}"] += 1
    return c


def _main(argv):
    if len(argv) < 2 or argv[0] != "forms":
        print(__doc__)
        return 1
    tables = [(Path(p).name, forms(load(p))) for p in argv[1:]]
    names = sorted({k for _, c in tables for k in c})
    w = max((len(n) for n in names), default=10) + 2
    print(f"{'형태':<{w}}" + "".join(f"{n[:14]:>16}" for n, _ in tables))
    for name in names:
        print(f"{name:<{w}}" + "".join(f"{c.get(name, 0):>16}" for _, c in tables))
    print(f"\n{'합계':<{w}}" + "".join(f"{sum(c.values()):>16}" for _, c in tables))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
