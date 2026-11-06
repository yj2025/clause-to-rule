"""발표용 결과물 — 검증된 것만 보여 주고 한계를 같이 적는다 (2026-09-29).

두 갈래로 모은다.

  1. **기존 두 상품** — 정답이 있다. v58~v61 · v66~v69 여덟 라운드(따로 띄운 프로세스)에서
     ⑥ 100% 가 **일곱 번 이상**인 조문만 낸다. 한 번 맞은 것은 안 낸다 (`METHOD.md` 3절)
  2. **새 상품** — 정답이 없다. `showcase/review.json` 에서 사람 대조로 ✅ 인 것만 낸다

**정답(`data/gold/`)은 싣지 않는다** — 블라인드 평가용이라 팀원에게 주지 않는다.
「정답과 일치한 라운드 수」만 적는다.

    python showcase/present.py      → showcase/out/presentation.md
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import gold  # noqa: E402
import pick_best  # noqa: E402
from scoring import score  # noqa: E402

ROUNDS = (58, 59, 60, 61, 66, 67, 68, 69)
MIN_HITS = 7
NAMES = {"KBYY": "KB Young Youth 통장", "KBONE": "KB국민ONE통장"}

# ⑥ 이 맞다고 해도 **사람이 원문과 정답을 대조해 틀린 것**. 합성 프로필의 「기본실적」 축은
# 카드결제 · 자동이체 · 출금을 **한꺼번에** 켠다(`gold._ctx`). 그래서 「카드결제만 있는 고객」이
# 프로필에 없고, 「카드 **또는** 공과금」을 「자동이체 → 세 가지 면제」로 적어도 ⑥ 이 100 이다
# (2026-09-29 대조).
SIXTH_BLIND = {
    "KBYY-S5-R02": "⑥ 은 여덟 번 중 일곱 번 맞다고 하지만 **뜻이 틀렸다.** 원문은 「카드결제 **또는** "
                   "공과금이체 → 세 가지 면제」인데, 모델은 자동이체가 있으면 세 가지를, 카드결제만 "
                   "있으면 한 가지만 면제한다. 신규 후 두 달의 무조건 면제도 빠졌다. 합성 프로필이 "
                   "카드결제와 자동이체를 늘 같이 켜서 ⑥ 이 이 차이를 못 본다.",
}


def _load(p):
    return json.loads(Path(p).read_text("utf-8"))


def stable_clauses():
    """[(조문, 맞은 라운드 수, 보여 줄 출력)] — 정답에 규칙이 있는 조문만 센다."""
    prod, tpl, P = gold._product(), gold._templates(), gold.profiles()
    corpus = {c["id"]: c for c in _load(ROOT / "data" / "corpus.json")}
    recs = {v: {r["clause_id"]: r for r in _load(ROOT / "results" / f"results_v{v}.json")}
            for v in ROUNDS}
    out, total = [], 0
    for cid, g in tpl.items():
        gr = g.get("rules") or []
        if not any(x.get("status") == "OK" for x in gr):
            continue
        total += 1
        hits, shown = 0, None
        for v in ROUNDS:
            r = recs[v].get(cid)
            rules = ((r or {}).get("output") or {}).get("rules") or []
            if score(gr, rules, prod["aggregation"], P, prod["base_rate"])["rate"] >= 0.999:
                hits += 1
                shown = (v, rules)                 # 맞은 라운드 중 가장 최근 것을 보인다
        if hits >= MIN_HITS:
            out.append((corpus[cid], hits, shown))
    out.sort(key=lambda x: x[0]["id"] in SIXTH_BLIND)     # ⑥ 사각지대는 뒤로
    return out, total


def new_product_best():
    review = _load(HERE / "review.json")
    clauses = {c["id"]: c for c in _load(HERE / "clauses_key.json")}
    recs = {r["clause_id"]: r for r in _load(HERE / "results_kb10.json")}
    prods = {p["prefix"]: p for p in _load(HERE / "products.json")}
    out = []
    for cid, rv in review.items():
        if rv.get("verdict") != "ok":
            continue
        c = clauses[cid]
        rules = (recs[cid].get("output") or {}).get("rules") or []
        base = pick_best._base_rate([x for x in clauses.values()
                                     if x["id"].startswith(cid.split("-")[0] + "-")])
        out.append((prods[cid.split("-")[0]], c, rules, rv["note"], base))
    return out


def _rules_block(rules):
    ok = [{k: r[k] for k in ("label", "condition", "effect") if k in r}
          for r in rules if r.get("status") == "OK"]
    return "```json\n" + json.dumps(ok, ensure_ascii=False, indent=1) + "\n```"


def _examples(rules, base):
    ex = pick_best.examples(rules, base)
    if not ex or not ex[0]["고객"]:
        return []
    keys = list(ex[0]["고객"])
    L = ["| " + " | ".join(f"`{k}`" for k in keys) + " | 최종 금리 | 자격 상실 | 그 밖의 효과 |",
         "|" + "---|" * (len(keys) + 3)]
    for e in ex:
        vals = [json.dumps(e["고객"][k], ensure_ascii=False) for k in keys]
        other = " · ".join(e["그밖의효과"])[:110] or "—"
        L.append("| " + " | ".join(vals) + f" | {e['최종금리']} | {e['자격상실']} | {other} |")
    return L


def render():
    stable, total = stable_clauses()
    good = [x for x in stable if x[0]["id"] not in SIXTH_BLIND]
    new = new_product_best()
    L = ["# 약관 조문 → 조건식 — 검증된 결과와 한계", "",
         "> Qwen3-8B · 온도 0.1 · 추론만 (학습 없음). 2026-09-29 기준.", "",
         "## 한 줄", "",
         f"**조건이 없는 선언은 안정적으로 옮긴다** — 정답이 있는 두 상품에서 규칙이 필요한 "
         f"{total}조문 중 {len(good)}조문을 여덟 번 중 {MIN_HITS}번 이상, 정답과 글자까지 같게 낸다 "
         "(비과세 · 질권 제한 · 서비스 제공 · 면제 이월 불가). **조건이 붙은 조문은 아직 안정적으로 "
         "못 옮긴다** — 여기서 한 조문(수수료 면제)은 지표가 맞다고 했지만 사람이 보니 틀렸고, "
         "금리 조문은 한 번도 안정적으로 맞지 않았다. 새 상품 8종에서는 계약기간별 기본이율표와 "
         "가입 자격 한 줄이 옮겨졌다.", "",
         "---", "", "## 1. 기존 두 상품 — 정답과 여러 번 일치한 조문", "",
         f"따로 띄운 여덟 라운드(v58~v61 · v66~v69)에서 **정답과 실행 결과가 일치한 라운드 수**다. "
         "한 번 맞은 것은 싣지 않는다 — 한 번 뽑은 값으로 세 번 틀린 판정을 냈다.", "",
         "| 상품 | 조문 | 일치 |", "|---|---|---:|"]
    L[-2] = "| 상품 | 조문 | ⑥ 일치 | 사람 대조 |"
    L[-1] = "|---|---|---:|---|"
    for c, hits, _ in stable:
        mark = "⚠ 틀림 (⑥ 사각지대)" if c["id"] in SIXTH_BLIND else "✅ 정답과 같다"
        L.append(f"| {NAMES.get(c['id'].split('-')[0], '')} | {c['label']} `{c['id']}` | "
                 f"{hits}/{len(ROUNDS)} | {mark} |")
    for c, hits, (v, rules) in stable:
        L += ["", f"### {c['label']} — {NAMES.get(c['id'].split('-')[0], '')} "
                  f"(`{c['id']}` · {hits}/{len(ROUNDS)})", "",
              ]
        if c["id"] in SIXTH_BLIND:
            L += [f"> ⚠ {SIXTH_BLIND[c['id']]}", ""]
        L += ["**원문**", "", "```", c["text"], "```", "",
              f"**모델이 낸 조건식** (v{v})", "", _rules_block(rules), ""]
        ex = _examples(rules, 0.1)
        if ex:
            L += ["**경계값 고객으로 돌리면** (합성 고객)", ""] + ex
    L += ["", "---", "", "## 2. 새 상품 — 사람이 원문과 대조한 것", "",
          "정답이 없는 상품이다. 105조문을 돌려 기계 검사를 넘은 18조문을 원문과 하나씩 "
          f"대조했고, **{len(new)}조문이 맞았다.**", ""]
    for p, c, rules, note, base in new:
        L += [f"### {c['label']} — {p['product']} ({p['kind']}) `{c['id']}`", "",
              f"> {note}", "", "**원문**", "", "```", c["text"], "```", "",
              "**모델이 낸 조건식**", "", _rules_block(rules), ""]
        ex = _examples(rules, base)
        if ex:
            L += ["**경계값 고객으로 돌리면** (합성 고객)", ""] + ex + [""]
    L += ["", "---", "", "## 3. 한계 — 숨기지 않는다", "",
          "* **금리 조문을 못 옮긴다.** 기존 상품의 특별금리(`KBYY-S2-R07`)는 여덟 번 다 틀렸다 — "
          "「최대 100만원까지」를 상한이 아니라 문턱으로 읽는다. v66 처방이 같은 계열의 다른 "
          "조문은 열었지만 이 조문은 못 열었다",
          f"* **안정적으로 맞히는 것은 {total}조문 중 {len(good)}조문이고, 전부 조건이 없는 선언이다.** "
          "나머지는 가끔 맞거나 한 번도 못 맞힌다",
          "* **지표(⑥)에 사각지대가 있다.** 합성 프로필이 카드결제 · 자동이체 · 출금을 늘 같이 켜서 "
          "「A **또는** B」와 「A 만」을 못 가린다. 수수료 면제 조문 하나가 그래서 맞은 것으로 "
          "잡혔다 — 프로필 축을 나눠야 한다",
          "* **다른 상품으로 일반화가 안 된다.** 새 상품 105조문 중 사람 대조를 넘은 것은 4조문"
          "(4%)이다. 원인은 셋이다 — 어휘에 없는 개념(중도해지·만기후이율의 경과기간과 비율식 · "
          "금리우대쿠폰 · 정보제공 동의, 12조문), 있는 어휘를 못 찾음(6조문), 관문은 넘었는데 "
          "뜻을 틀림(13조문 — 가입 자격을 거꾸로 적기, 없는 금리 지어내기)",
          "* **정답 46조문 중 35조문은 사람 검토 전이다.** 위 「일치」는 그 정답과의 일치다",
          "* 고객 예시는 **합성 고객**이다. 진짜 고객 DB 로 돌린 결과가 아니다", "",
          "## 4. 다음 방향", "",
          "1. **적금·예금 어휘를 넣는다** — 경과기간 · 비율식이 한 묶음으로 5조문을 막는다 "
          "(팀 결정 사항)",
          "2. **금리 조문은 금리 rule 과 한도 rule 을 따로 적게 한다** — `KBYY-S2-R07` 이 두 문장을 "
          "한 조건으로 묶는다",
          "3. **뜻을 뒤집는 실수를 검증기로 막는다** — 가입 자격 반전, 나이를 문자열과 비교. "
          "다만 지금 코퍼스에서는 표적이 너무 작아 잴 수 없다 — 코퍼스를 넓히는 것이 먼저다"]
    return "\n".join(L) + "\n"


def main():
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    (out / "presentation.md").write_text(render(), "utf-8")
    print(f"→ {out / 'presentation.md'}")


if __name__ == "__main__":
    main()
