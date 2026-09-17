"""이 저장소의 조문을 팀원 Part 2-1 모델 입력(Section Packet)으로 옮긴다.

    python blind_packets.py            # data/blind43_packets.jsonl 을 쓴다
    python blind_packets.py --check    # 쓰지 않고 검사만 한다

팀원 모델은 `packet_text` 하나만 입력으로 받는다 (QLoRA 노트북 `user_prompt`).
상품설명서 항목은 이런 모양이다.

    [PARENT_HEADER]
    2 거래 조건

    [CURRENT]
    저금통 기능
    ▪ 계좌의 … 특별금리 제공 - 저금통 설정, 해제는 …

**모양이 맞는지는 겹치는 3조문으로 잰다.** 팀원 Train 에 같은 항목이 들어 있어서
이 코드가 만든 패킷이 팀원 패킷과 **글자까지 같아야** 한다. 그 3조문은 블라인드가
아니므로 내보내지 않는다 — 남는 것이 43조문이다.

**상품이 달라도 글이 같을 수 있다.** 세제 · 압류 · 휴면예금 같은 항목은 KB 상품설명서마다
거의 같은 문구라, 팀원 Train 의 **다른 상품** 패킷과 글자까지 닮는다. 그래서 조문마다
가장 닮은 팀원 패킷을 찾아 `novelty` 등급을 붙인다. 채점은 이 등급별로 따로 낸다 —
처음 보는 글에서의 성능과 외운 틀을 다시 쓰는 성능을 섞지 않는다.

| novelty | 뜻 |
|---|---|
| `SEEN_TRAIN` | Train 에 0.95 이상 — 글자 몇 개 다른 같은 문구 |
| `NEAR_TRAIN` | Train 에 0.80 이상 — 같은 틀의 변형 |
| `SEEN_DEV` | Train 엔 없고 Dev 에 0.80 이상 — 학습엔 안 썼지만 체크포인트 고르는 데 썼다 |
| `NEW` | 어디에도 0.80 미만 |

본문 줄바꿈은 공백으로 잇는다 (겹치는 셋이 그렇다). 표는 행마다 줄을 나눈다 —
팀원 상품설명서 148건 중 28건이 표 행을 줄로 남겼다. 이 저장소가 붙인
`[참조표: 제목]` 표시는 팀원 입력에 없는 꼴이라 제목 줄만 남긴다.

팀원 폴더는 **읽기만 한다.** `gold_build400_review_blind50_LOCKED_v1_1.csv` 는 열지 않는다.
"""

import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "data" / "corpus.json"
OUT = ROOT / "data" / "blind43_packets.jsonl"

SYS = Path("/workspace/personal_workplace_SYS/experiment_code")
TEAM = (SYS / "gold_build400_train_ready265_compact_v1_1.jsonl",
        SYS / "gold_build400_dev50_gold_compact_v1_1.jsonl")

DOCS = {
    "KBYY": "KB Young Youth 통장 상품설명서",
    "KBONE": "KB국민ONE통장 상품설명서",
}
# 원문 `##` 제목 그대로. 5 는 doc_split.py 가 `붙임` 에 준 번호다
SECTIONS = {
    ("KBYY", 1): "1 상품 개요 및 특징",
    ("KBYY", 2): "2 거래 조건",
    ("KBYY", 3): "3 연계·제휴서비스",
    ("KBYY", 5): "붙임 자동전환 상품 주요 혜택",
    ("KBONE", 1): "1 상품명 및 특징",
    ("KBONE", 2): "2 거래 조건",
}

# 팀원 Train 에 같은 항목이 있다 → 블라인드가 아니다
OVERLAP = {
    "KBYY-S2-R11": ("KB Young Youth 통장 상품설명서", "섹션2/항목12"),
    "KBYY-S3-R04": ("KB Young Youth 통장 상품설명서", "섹션3/항목3"),
    "KBONE-S2-R04": ("KB국민ONE통장 상품설명서", "섹션2/항목4"),
}

# difflib ratio. 0.95 는 "세법이 개정될 경우" ↔ "세법 개정 시" 정도 차이다
SEEN, NEAR = 0.95, 0.80

_TABLE = re.compile(r"^\[참조표: (.+)\]$")
_ID = re.compile(r"^(KBYY|KBONE)-S(\d)-[PR]\d\d$")


def _body_lines(text):
    """첫 줄 `[항목명]` 을 뗀 본문을 덩어리로 나눈다. 표 덩어리는 행을 지킨다."""
    lines = text.split("\n")[1:]
    blocks, cur, in_table = [], [], False
    for line in lines:
        m = _TABLE.match(line)
        if m:
            if cur:
                blocks.append((in_table, cur))
            cur, in_table = [m.group(1)], True
        elif not line.strip():
            if cur:
                blocks.append((in_table, cur))
            cur, in_table = [], False
        else:
            cur.append(line.strip())
    if cur:
        blocks.append((in_table, cur))
    return blocks


def packet_text(clause):
    m = _ID.match(clause["id"])
    if not m:
        raise ValueError(f"조문 번호 꼴이 아니다: {clause['id']}")
    doc, sec = m.group(1), int(m.group(2))
    header = SECTIONS[(doc, sec)]
    head_item = clause["id"].split("-")[2].startswith("P")
    out = []
    for is_table, lines in _body_lines(clause["text"]):
        # 섹션 머리 항목(상품명 · 상품특징)은 팀원도 줄을 나눈다
        out.extend(lines if is_table or head_item else [" ".join(lines)])
    body = "\n".join(out)
    if head_item:
        # 팀원은 섹션 제목을 [CURRENT] 첫 줄에 둔다
        return f"[CURRENT]\n{header}\n{body}"
    return f"[PARENT_HEADER]\n{header}\n\n[CURRENT]\n{clause['label']}\n{body}"


def load_team(paths=TEAM):
    rows, shas = [], {}
    for p in paths:
        raw = p.read_bytes()
        shas[p.name] = hashlib.sha256(raw).hexdigest()
        split = "dev" if "_dev" in p.name else "train"
        for line in raw.decode("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_split"] = split
                rows.append(r)
    return rows, shas


def nearest(text, team_rows):
    """가장 닮은 팀원 패킷. quick_ratio 로 거른 뒤 ratio 를 잰다."""
    best = (0.0, None)
    for r in team_rows:
        sm = difflib.SequenceMatcher(None, text, r["packet_text"], autojunk=False)
        if sm.real_quick_ratio() <= best[0] or sm.quick_ratio() <= best[0]:
            continue
        ratio = sm.ratio()
        if ratio > best[0]:
            best = (ratio, r)
    return best


def novelty(text, team_rows):
    """(등급, Train 최근접, Dev 최근접). 최근접은 (ratio, 행)."""
    tr = nearest(text, [r for r in team_rows if r["_split"] == "train"])
    dv = nearest(text, [r for r in team_rows if r["_split"] == "dev"])
    if tr[0] >= SEEN:
        grade = "SEEN_TRAIN"
    elif tr[0] >= NEAR:
        grade = "NEAR_TRAIN"
    elif dv[0] >= NEAR:
        grade = "SEEN_DEV"
    else:
        grade = "NEW"
    return grade, tr, dv


def _near(pair):
    ratio, r = pair
    return {"ratio": round(ratio, 3),
            "where": f"{r['document_name']} {r['section_path']}" if r else None,
            "gold_status": r["semantic_rule"]["status"] if r else None}


def build(corpus=None, team=None):
    corpus = corpus if corpus is not None else json.loads(CORPUS.read_text("utf-8"))
    team_rows, shas = team if team is not None else load_team()
    by_key = {(r["document_name"], r["section_path"]): r for r in team_rows}

    problems, packets = [], []
    for c in corpus:
        doc = DOCS[c["id"].split("-")[0]]
        text = packet_text(c)
        if c["id"] in OVERLAP:
            want = by_key.get(OVERLAP[c["id"]])
            if want is None:
                problems.append(f"{c['id']}: 팀원 쪽 짝 {OVERLAP[c['id']]} 가 없다")
            elif want["packet_text"] != text:
                problems.append(f"{c['id']}: 팀원 패킷과 글자가 다르다")
            continue
        grade, tr, dv = novelty(text, team_rows)
        packets.append({
            "sample_id": c["id"],
            "document_name": doc,
            "document_type": "PRODUCT_DESCRIPTION",
            "label": c["label"],
            "packet_text": text,
            "novelty": grade,
            "nearest_train": _near(tr),
            "nearest_dev": _near(dv),
        })
    meta = {
        "what": "이 저장소 46조문 중 팀원 Train 과 겹치는 3조문을 뺀 블라인드 입력",
        "excluded_overlap": sorted(OVERLAP),
        "same_product_in_team_train": sorted({
            f"{r['document_name']} {r['section_path']}" for r in team_rows
            if any(p in r["document_name"] for p in ("KB Young Youth 통장", "KB국민ONE통장"))
            and (r["document_name"], r["section_path"]) not in set(OVERLAP.values())}),
        "team_sources_sha256": shas,
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "novelty_cutoffs": {"seen": SEEN, "near": NEAR},
    }
    return packets, meta, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="쓰지 않고 검사만")
    args = ap.parse_args()

    packets, meta, problems = build()
    for p in problems:
        print("!!", p)
    lens = sorted(len(p["packet_text"]) for p in packets)
    print(f"패킷 {len(packets)}개 · 겹침 제외 {len(meta['excluded_overlap'])} · "
          f"길이 최소/중앙/최대 {lens[0]}/{lens[len(lens) // 2]}/{lens[-1]}자")
    for grade in ("SEEN_TRAIN", "NEAR_TRAIN", "SEEN_DEV", "NEW"):
        got = [p for p in packets if p["novelty"] == grade]
        print(f"{grade:10} {len(got):2}")
        for p in got:
            if grade == "NEW":
                continue
            n = p["nearest_dev"] if grade == "SEEN_DEV" else p["nearest_train"]
            print(f"   {n['ratio']:.2f}  {p['sample_id']:14} ↔ {n['where']}")
    print(f"같은 상품 다른 문서(팀원 Train): {len(meta['same_product_in_team_train'])}건")
    for s in meta["same_product_in_team_train"]:
        print("  ", s)
    if problems:
        raise SystemExit(1)
    if not args.check:
        with OUT.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
            for p in packets:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
