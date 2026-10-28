# 서버에 넣는 법 (2026-10-27)

서버 M2-2 저장소 루트(`/workspace/personal_workplace_CHO/model/M2-lora`)에서:

    unzip eval_v2_to_server.zip -d /tmp/ev2
    mkdir -p data/gold_v2 && cp /tmp/ev2/eval_v2/gold/*.json data/gold_v2/
    cp /tmp/ev2/eval_v2/clauses.json data/gold_v2/_clauses.json
    cp -r /tmp/ev2/eval_v2 lora/eval_v2        # 출처 · 판정 기록 · 도구 (참고용)

- 정답 35개 + `_triage.json`. 조문 원문은 `_clauses.json` (조문 id 접두어 HNSAL · HNDRM · HNWSH).
- **봉인:** NEXT_PLAN 10단계 전에는 여기에 모델을 돌리지 않는다. 한 번만 쓴다. 서버 밖 · HF 로 내보내지 않는다.
- 채점은 kb10 과 같은 ⑥ (`gold.profiles()` · `scoring.score`, aggregation SUM). 상품별 1년제 기본금리: HNSAL 2.95 · HNDRM 2.70 · HNWSH 0.75.
- `tools/check_gold_v2.py` · `compare_gold.py` 는 로컬 경로(`../work/M2-2`) 기준이라 서버에서는 `sys.path` 줄만 저장소 루트로 고친다.
