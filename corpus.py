"""여러 상품설명서를 한 코퍼스로 묶기.

노이즈 바닥이 ±2~4p 라서 그 아래는 측정이 안 된다. 조문을 늘리는 것이 답인데,
상품을 더하면 **같은 조문이 두 번 들어온다.** KB Young Youth 통장과 KB 국민ONE통장은
붙임의 KB생활 서비스 조문이 글자까지 같다.

같은 내용을 두 번 채점하면 그 조문의 몫이 두 배가 되고, 두 상품에서 같은 방향으로
움직이므로 **분산이 눌린다.** §6.2 의 참조표 중복과 정확히 같은 사고다.
그래서 코퍼스를 묶을 때 본문이 같은 조문은 하나만 남긴다.

    python corpus.py build data/clauses.json data/clauses_kbone.json -o data/corpus.json
"""

import argparse
import json
import sys
from pathlib import Path


def _norm(text):
    return "".join(text.split())


def merge(sets, dedup=True):
    """[[조문,...], ...] → 하나의 목록.

    반환: (조문 목록, 뺀 것 목록). 뺀 것은 (뺀 id, 남긴 id) 쌍이다.
    먼저 들어온 상품의 조문을 남긴다.
    """
    out, seen, dropped = [], {}, []
    for clauses in sets:
        for c in clauses:
            key = _norm(c["text"])
            if dedup and key in seen:
                dropped.append((c["id"], seen[key]))
                continue
            seen[key] = c["id"]
            out.append(c)
    return out, dropped


def product_of(clause_id):
    """조문 id 의 상품 앞머리."""
    return clause_id.split("-", 1)[0]


def summary(clauses):
    """상품별 조문 수와 길이."""
    by = {}
    for c in clauses:
        p = product_of(c["id"])
        by.setdefault(p, []).append(len(c["text"]))
    return {p: {"조문": len(v), "중앙": sorted(v)[len(v) // 2],
                "최소": min(v), "최대": max(v)} for p, v in sorted(by.items())}


def _main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--keep-duplicates", action="store_true")
    a = ap.parse_args(argv)

    sets = [json.loads(Path(f).read_text("utf-8")) for f in a.files]
    merged, dropped = merge(sets, dedup=not a.keep_duplicates)
    Path(a.out).write_text(json.dumps(merged, ensure_ascii=False, indent=1), "utf-8")

    total = sum(len(s) for s in sets)
    print(f"입력 {len(sets)}개 문서 · 조문 {total}개")
    print(f"중복 제거 {len(dropped)}개 → {len(merged)}개  →  {a.out}\n")
    for cid, kept in dropped:
        print(f"  뺌 {cid:<16} (같은 본문이 {kept} 에 있다)")
    print()
    print(f"{'상품':<8}{'조문':>6}{'중앙':>8}{'최소':>7}{'최대':>7}")
    for p, s in summary(merged).items():
        print(f"{p:<8}{s['조문']:>6}{s['중앙']:>8}{s['최소']:>7}{s['최대']:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
