# results/ 안내

라운드 하나가 결과 파일 하나다. `results_v<n>.json` 이 그 라운드의 기록이고
**덮어쓰지 않는다** — 문서에 적힌 수치가 이 파일에서 나왔기 때문이다.
채점을 고친 뒤 옛 라운드를 견줄 때는 파일을 고치지 말고
`python tools/report.py results/results_v28.json --rescore` 를 쓴다.

## 이름이 특이한 것들

| 파일 | 무엇인가 |
|---|---|
| `results_base3.json` | 기준선 3회차. 프롬프트를 손대기 전의 출발점 |
| `results_base3_partial.json` | 기준선이 18조문에서 한 번 끊겼던 기록. `docs/NOISE.md` 가 분모 18을 설명하며 인용한다 |
| `results_v23.PARTIAL-8.json` | v23 이 남의 GPU 작업 때문에 8조문에서 끊긴 기록. `docs/EXPERIMENTS.md` 가 인용한다 |
| `results_v27.PARTIAL-11.json` | v27 이 11조문에서 OOM 으로 끊겨 **폐기된** 라운드. 최종본이 없다 |
| `results_kbyy_v3.PARTIAL-20clauses.json` | v3 을 KBYY 만으로 먼저 돌려 본 것. 최종본에 없는 레코드가 40건 있다 |
| `results_v23x3.json` | v23 을 3회차로 다시 돌린 것 |

2026-09-21 에 `results_base3_rest.json` 과 `results_v23_rest.json` 을 지웠다 —
최종본에 **완전히 포함**되어 있고 문서 어디서도 안 부르는 병합 찌꺼기였다.

## 라운드 파일이 아닌 것

| 파일 | 무엇인가 |
|---|---|
| `blind43_*.jsonl` · `blind43_score*.json` | 팀원 모델을 이 저장소 정답으로 채점한 것 |
| `semconv_gold315.json` | 팀원 의미 규칙 315레코드를 실행 규칙으로 변환한 결과 |
| `semselect_dev50.json` · `sys_qlora_paired.json` · `dev_size.json` | 변환기·체크포인트 비교용 중간 산출물 |
