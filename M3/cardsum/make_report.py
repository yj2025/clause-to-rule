#!/usr/bin/env python3
"""runs/<이름>/*.json → 모델별 카드·약관요약 비교 HTML (2026-10-14).

    python make_report.py runs/gstar units_gstar.json "<docs 경로>/카드요약_모델비교_글로벌스타.html"
"""
import html
import json
import sys
from pathlib import Path

ORDER = ["qwen", "exaone", "gemma12", "gemma26", "gemma31"]
NAMES = {"qwen": "Qwen3-8B", "exaone": "EXAONE 3.5 7.8B", "gemma12": "Gemma 4 12B",
         "gemma26": "Gemma 4 26B-A4B", "gemma31": "Gemma 4 31B"}
E = html.escape


def main(run_dir, units_path, out_path):
    units = json.loads(Path(units_path).read_text(encoding="utf-8"))
    runs = {}
    for k in ORDER:
        p = Path(run_dir) / f"{k}.json"
        if p.exists():
            runs[k] = json.loads(p.read_text(encoding="utf-8"))
    rows = {k: {r["id"]: r for r in v["rows"]} for k, v in runs.items()}

    head = "".join(
        f"<tr><td>{E(NAMES[k])}</td><td>{sum(r['status'] == '통과' for r in v['rows'])}/{len(v['rows'])}</td>"
        f"<td>{sum(r['retried'] for r in v['rows'])}</td>"
        f"<td>{sum(len(r['attempts'][-1]['notes']) > 0 for r in v['rows'] if r['status'] == '통과')}</td>"
        f"<td>{v['load_seconds']}s</td>"
        f"<td>{sum(a['seconds'] for r in v['rows'] for a in r['attempts']):.0f}s</td>"
        f"<td>{max(a['output_tokens'] for r in v['rows'] for a in r['attempts'])}</td>"
        f"<td>{v['peak_gpu_gb']}GB</td><td>{E(v['quantization'])}</td></tr>"
        for k, v in runs.items())

    cards = []
    for u in units["units"]:
        label = (f"<span class='tag t-{E(u['track'])}'>{E(u['track'])}</span>" if u["kind"] == "card"
                 else f"<span class='tag t-item'>약관 요약</span> <b>{E(u['name'])}</b>")
        hu = u.get("human", {})
        human = (f"<b>{E(hu['title'])}</b><br>" if hu.get("title") else "") + E(hu.get("summary", ""))
        lines = [f"<tr class='human'><td>C안 (사람)</td><td>{human}</td><td></td></tr>"]
        for k in runs:
            r = rows[k].get(u["id"])
            if not r:
                continue
            last = r["attempts"][-1]
            if r["status"] == "통과":
                res = r["result"]
                body = (f"<b>{E(res['title'])}</b><br>" if res.get("title") else "") + E(res["summary"])
            else:
                body = f"<span class='muted'>폐기 · 마지막 출력:</span> <code>{E(last['raw'][:300])}</code>"
            info = [r["status"]] + (["재시도"] if r["retried"] else [])
            meta = (f"<span class='st {'ok' if r['status'] == '통과' else 'ng'}'>{' · '.join(info)}</span>"
                    + "".join(f"<div class='err'>{E(x)}</div>" for a in r["attempts"] for x in a["errors"])
                    + "".join(f"<div class='note'>{E(x)}</div>" for x in last["notes"])
                    + f"<div class='muted'>출력 {'/'.join(str(a['output_tokens']) for a in r['attempts'])} 토큰</div>")
            lines.append(f"<tr><td>{E(NAMES[k])}</td><td>{body}</td><td>{meta}</td></tr>")
        r0 = next((rows[k][u["id"]] for k in runs if u["id"] in rows[k]), None)
        src = u.get("text") or "\n\n".join(next(x for x in units["units"] if x["id"] == i)["text"]
                                           for i in u.get("from_units", []))
        slots = ", ".join(f"{s['id']}={s['value']}" for s in (r0["slots"] if r0 else []))
        cards.append(
            f"<section><h3>{E(u['id'])} {label}</h3><div class='ref'>{E(u['ref'])}</div>"
            f"<table class='cmp'>{''.join(lines)}</table>"
            f"<details><summary>모델에 넣은 원문 · 슬롯</summary><pre>{E(src)}</pre>"
            f"<div class='muted'>슬롯: {E(slots)}</div></details></section>")

    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>카드 요약 모델 비교</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--card:#fff;--ok:#15803d;--ng:#b91c1c;--hu:#f5f5f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#44403c;--card:#292524;--ok:#4ade80;--ng:#f87171;--hu:#312e2b}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Noto Sans KR",sans-serif;margin:0;padding:24px 16px;max-width:1100px;margin:auto}}
h1{{font-size:22px;margin:0 0 4px}} .muted{{color:var(--muted);font-size:13px}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}}
.sum td,.sum th{{font-size:14px}} section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:16px 0}}
h3{{margin:0;font-size:16px}} .ref{{color:var(--muted);font-size:13px;margin-bottom:6px}}
.cmp td:first-child{{width:130px;color:var(--muted);font-size:13px}} .cmp td:last-child{{width:230px;font-size:13px}}
tr.human td{{background:var(--hu)}} .tag{{font-size:12px;padding:1px 8px;border-radius:99px;border:1px solid var(--line)}}
.st.ok{{color:var(--ok);font-weight:600}} .st.ng{{color:var(--ng);font-weight:600}} .err{{color:var(--ng)}} .note{{color:var(--muted)}}
pre{{white-space:pre-wrap;font-size:13px;background:var(--hu);padding:10px;border-radius:6px}} code{{font-size:12px;word-break:break-all}}
.wrap{{overflow-x:auto}}
</style></head><body>
<h1>카드 요약 모델 비교 · {E(units['product'])}</h1>
<div class="muted">2026-10-14 시험 · 검수 전 초안 · 원문: {E(units['source'])}</div>
<p class="muted">규칙: 항목·카드마다 근거 섹션만 넣어 따로 호출 · 숫자는 슬롯 표기로만(코드가 채움) · 계산값(C 슬롯)은 규칙 엔진이 계산 ·
슬롯 밖 숫자/없는 슬롯/단위 중복/길이(카드 110자·2문장, 항목 150자·3문장)/금지어 검사 → 실패 시 1회 다시 쓰게 하고 또 실패하면 폐기. greedy · thinking 끔.</p>
<div class="wrap"><table class="sum"><tr><th>모델</th><th>통과</th><th>재시도</th><th>참고 메모</th><th>로드</th><th>생성 합계</th><th>최대 출력 토큰</th><th>GPU 최대</th><th>양자화</th></tr>{head}</table></div>
{''.join(cards)}
</body></html>"""
    Path(out_path).write_text(page, encoding="utf-8")
    print("저장:", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:4])
