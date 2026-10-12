"""모델 요약 출력에 결정론적 검사 · 보완을 붙인다 (2026-10-13 · 역할 나누기).

    python3 docsab/postcheck.py <모델출력.json> [--out <보완.json>]

모델 출력(`parsed.items`)과 팀 요약입력의 조항(특약 · 상품설명서)을 key 별로 맞춰 본다.
모델이 잘 못 하는 일 넷을 코드가 맡는다 — 모델이 쓴 값은 지우지 않고, 코드가 붙인 값은 `_check` 아래에 따로 남긴다.

1. 문서 차이 — 두 문서가 같은 key 를 다룰 때, 조건 · 예외 성격의 문장(제외 · 불가 · 한함 · 이상 · 미만 …)이
   한쪽 문서에만 있으면 doc_diff 후보로 적는다. 모델의 doc_diff 는 쓰지 않는다(헛표시가 잦았다).
2. 누락 의심 — 원문의 제외 · 불가 문장이 모델 출력 어디에도 없으면 적는다.
3. 물을 입력 — 조건 문장의 낱말로 고객에게 물을 값을 표에서 붙인다(모델이 비워 둔 줄만).
4. 출처 — 줄에 src 가 없으면 그 key 의 조항 번호를 붙인다.
"""
import json
import re
import sys
from pathlib import Path

SRC = Path("/workspace/personal_workplace_CHO/docs/요약입력_상품별.json")
DOCS = ("특약", "상품설명서")

# 조건 · 예외 성격의 문장만 문서 차이 · 누락 후보로 본다 (설명 · 예시 · 고지 문장은 뺀다)
COND = re.compile(r"제외|불가|포함|한함|한하여|한정|않습니다|않음|없습니다|이상|이하|미만|초과|경우에 한|단,|다만")
EXC = re.compile(r"제외|불가|한함|한하여|한정|않습니다|않음")
SKIP = re.compile(r"예\)|예시|\[이미지|고객센터|문의|페이지 \d|민원|설명서는")

DIFF_T = 0.6   # 10-13: 세 상품 목표로 맞춤 — key 5/5 찾음 · 헛표시 2 (낱말 단위 · 흔한 낱말 가중치 낮춤)

# 물을 입력 표 — 앞에서부터 처음 맞는 줄 (조건 문장에서 찾는다)
ASK = [
    (r"인정단어", "월별 인정단어 입금 합계"),
    (r"급여", "급여 수령 여부"),
    (r"(카드|결제대금).*(출금|누적)", "월 카드 결제대금 출금액"),
    (r"간편결제|결제 ?이용 ?횟수|결제.*횟수", "월 결제 횟수"),
    (r"자동이체.*(출금|이력)|리브 ?모바일|Liiv", "자동이체 출금 여부"),
    (r"(합산|합계).*입금|입금.*(합산|합계)|만원 이상 입금", "월 입금 합계"),
    (r"잔액.*거래|거래.*잔액|무거래", "잔액 · 최종 거래일"),
    (r"최초 ?가입|재 ?가입", "최초 가입 여부"),
    (r"동의", "동의 여부"),
]


def norm(s):
    return re.sub(r"[\s·•※\-\(\)\[\]「」『』'\"‘’“”,.:~▪☞|①②③④⑤]", "", s or "")


def grams(s, n=2):
    s = norm(s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def cover(a, b_grams, n=2):
    """문장 a 의 n-gram 중 b 에 있는 비율."""
    A = grams(a, n)
    return len(A & b_grams) / len(A) if A else 1.0


# 낱말 단위 대조 (문서 차이) — 어순 · 어미가 달라도 같은 문장으로 본다
NEG = [(r"할\s*수\s*없[^\s,.]*|불가능[^\s,.]*|불가[^\s,.]*|않[^\s,.]*|제공하지", " 불가 "),
       (r"1\s*가지", "하나"), (r"충족[^\s,.]*", "발생"), (r"당행", "KB국민은행"), (r"타\s*금융기관|다른\s*금융기관", "타금융기관"),
       (r"개인\s*사업자", "개인사업자"), (r"관련\s*서류|서류\s*미제출", "서류미제출"), (r"경우는\s*제외", "경우는 불가")]
STOP = {"이통장", "통장의", "통장은", "통장을", "통장으로", "경우", "경우는", "경우에", "합니다", "있습니다", "있는", "및", "또는", "아래"}


def canon(s):
    s = s or ""
    for pat, rep in NEG:
        s = re.sub(pat, rep, s)
    return s


def terms(s):
    """낱말의 앞 두 글자(어간 근사)와 숫자 · 단위 묶음."""
    s = canon(s)
    out = set(re.findall(r"\d+(?:[.,]\d+)?\s*(?:%p|%|만\s*원|원|개월|년|일|회|건|세|개|매)?", s.replace(" ", "")))
    for w in re.findall(r"[가-힣A-Za-z]{2,}", s):
        if w not in STOP:
            out.add(w[:2])
    return out


def term_cover(a, other_terms, df=None):
    """a 의 낱말 중 상대 문서에 있는 비율. df(낱말이 나온 조항 수)를 주면 흔한 낱말일수록 가볍게 센다."""
    A = terms(a)
    if not A:
        return 1.0
    w = {t: 1.0 / (df.get(t, 1) if df else 1) for t in A}
    return sum(w[t] for t in A & other_terms) / sum(w.values())


def clauses(text):
    """조항 본문을 판정 단위 문장으로 자른다 — ※ · ▪ · 줄바꿈 · 번호 · ' - ' 앞에서."""
    parts = re.split(r"\n|※|▪|☞|(?=[①②③④⑤])|(?<=\S) - |【[^】]*】|\(\d\)|주\d\)", text)
    out = []
    for p in parts:
        p = p.strip(" \t|-")
        if len(norm(p)) >= 6 and not SKIP.search(p):
            out.append(p)
    return out


def item_text(it):
    return json.dumps(it, ensure_ascii=False)


def lines_of(it):
    for f in ("conditions", "exceptions"):
        for x in it.get(f) or []:
            if isinstance(x, dict):
                yield f, x


def check_product(packet, items):
    secs = {s["section_id"]: s for s in packet["sections"]}
    keys = {k["key"]: k for k in packet["keys"]}
    out = []
    for it in items:
        k = keys.get(it.get("key"))
        chk = {}
        if k:
            ids = list(k["primary_section_ids"]) + list(k["reference_section_ids"])
            by = {d: [secs[i] for i in ids if i in secs and secs[i]["doc_type"] == d] for d in DOCS}
            # 1. 문서 차이 — 주 조항이 두 문서 다에 있을 때만
            prim = {d: [secs[i] for i in k["primary_section_ids"] if i in secs and secs[i]["doc_type"] == d] for d in DOCS}
            # 붙임(전환 대상 등 다른 상품 설명)은 이 상품의 조건이 아니라서 뺀다
            prim = {d: [s for s in prim[d] if "붙임" not in (s.get("title") or "") + (s.get("path") or "")] for d in DOCS}
            if prim["특약"] and prim["상품설명서"]:
                # 상대 문서 전체와 대조한다 — 같은 내용이 상대 문서의 다른 조항에 있을 수 있다 (낱말 단위: 글자 조각은 어순 차이에 헛표시)
                g = {d: set().union(*(terms(x["text"]) for x in packet["sections"] if x["doc_type"] == d)) for d in DOCS}
                df = {}
                for x in packet["sections"]:
                    for t in terms(x["text"]):
                        df[t] = df.get(t, 0) + 1
                only = []
                for d, other in (("특약", "상품설명서"), ("상품설명서", "특약")):
                    for s in prim[d]:
                        for c in clauses(s["text"]):
                            if COND.search(c) and term_cover(c, g[other], df) < DIFF_T:
                                only.append({"text": c[:160], "only_in": d, "src": [s["section_id"]]})
                if only:
                    chk["doc_diff"] = only
            # 2. 누락 의심 — 주 조항의 제외 · 불가 문장이 출력에 없으면
            out_g = grams(item_text(it))
            miss = []
            for s in (x for d in DOCS for x in prim[d]):
                for c in clauses(s["text"]):
                    if EXC.search(c) and cover(c, out_g) < 0.5:
                        miss.append({"text": c[:160], "src": [s["section_id"]]})
            if miss:
                chk["missing"] = miss
            # 3 · 4. 물을 입력 · 출처
            added = []
            for f, x in lines_of(it):
                if f == "conditions" and not x.get("user_input"):
                    for pat, ask in ASK:
                        if re.search(pat, x.get("text", "")):
                            x["user_input"] = ask
                            added.append(ask)
                            break
                if not x.get("src"):
                    x["src"] = [i for i in k["primary_section_ids"] if i in secs]
            if added:
                chk["user_input_added"] = added
        it["_check"] = chk
        out.append(it)
    return out


def run(path, out=None):
    rec = json.loads(Path(path).read_text("utf-8"))
    packets = {p["product_name"]: p for p in json.loads(SRC.read_text("utf-8"))["packets"]}
    items = check_product(packets[rec["product_name"]], (rec.get("parsed") or {}).get("items", []))
    # 채점 · 화면용으로 코드가 찾은 문서 차이를 doc_diff · only_in 에 반영한다 (모델의 doc_diff 는 _model_doc_diff 로 옮김)
    for it in items:
        if "doc_diff" in it:
            it["_model_doc_diff"] = it.pop("doc_diff")
        for f, x in lines_of(it):
            if "only_in" in x:
                x["_model_only_in"] = x.pop("only_in")
        dd = it["_check"].get("doc_diff")
        if dd:
            it["doc_diff"] = " / ".join(f"{x['only_in']}에만: {x['text'][:60]}" for x in dd)
            for f, x in lines_of(it):
                for y in dd:
                    if cover(x.get("text", ""), grams(y["text"])) >= 0.6 or cover(y["text"], grams(x.get("text", ""))) >= 0.6:
                        x["only_in"] = y["only_in"]
    rec = dict(rec, parsed={"items": items}, postcheck=True)
    out = Path(out) if out else Path(path).with_name(Path(path).stem + ".post.json")
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), "utf-8")
    n = lambda f: sum(len(i["_check"].get(f, [])) for i in items)
    print(f"{rec['product_name']} · 문서 차이 후보 {n('doc_diff')}줄({sum(1 for i in items if i['_check'].get('doc_diff'))} key)"
          f" · 누락 의심 {n('missing')} · 물을 입력 추가 {n('user_input_added')} → {out}")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    run(a[0], a[a.index("--out") + 1] if "--out" in a else None)
