# M3 개인화 요약 프롬프트 테스트 키트

T1~T4 테스트 입력을 Qwen2.5-7B-Instruct에 넣어 출력을 만들고(run_m3.py), 그 출력을 자동 채점(grade.py)한다.

## 구성
- `prompts/` — system 프롬프트 (v0.3 포함. 새 버전은 여기에 파일만 추가)
- `testcases/T1~T4.json` — 가상 상품 테스트 입력 (적금 / 정기예금 / 입출금 / 엣지)
- `expectations.json` — 케이스별 정답 단언. 팀 결정이 바뀌면 여기만 고치면 됨
- `run_m3.py` — 모델 실행 (greedy 고정, fp16, sdpa — V100 기준)
- `grade.py` — 채점, 여러 버전 비교표 생성
- `samples/` — 채점기 동작 확인용 예시 출력 (simulated: 손으로 쓴 정상 출력 / broken: 일부러 망가뜨린 출력)

## 실행
```bash
# 1) 모델 실행 (GPU 서버에서). 케이스당 출력이 runs/v0.3/T1.out.txt ... 로 저장됨
python run_m3.py --system prompts/personalized_summary_v0.3.system.txt \
  --cases testcases --model <Qwen2.5-7B-Instruct 경로> --out runs/v0.3

# 2) 채점 (GPU 불필요)
python grade.py --cases testcases --expect expectations.json --outputs runs/v0.3

# 3) 프롬프트를 고친 뒤 비교
python run_m3.py --system prompts/<새 버전>.txt --cases testcases --model <경로> --out runs/v0.4
python grade.py --cases testcases --expect expectations.json --outputs runs/v0.3 runs/v0.4 --report compare.md
```
채점기만 먼저 확인하려면:
`python grade.py --cases testcases --expect expectations.json --outputs samples/simulated samples/broken`

### run_m3.py 옵션
- `--no-reminder` — user 끝의 "JSON 하나만 출력" 리마인더를 뺌 (리마인더 효과 A/B 비교용)
- `--sample --repeat 5` — 샘플링으로 케이스당 5번 실행 (출력이 얼마나 흔들리는지 확인용. 기본은 greedy 1회)
- `--only T1 T3` — 일부 케이스만
- `--max-new-tokens` — 기본 2560. `run_meta.json`의 `hit_max_new_tokens`가 true면 출력이 잘린 것

## 결과 읽는 법
- **필수** — 점수에 반영. 프롬프트 규칙 그대로의 기준 (근거 fact_id, 판정 state 일치, 수치·%p·경계어 보존, 금지어, must_include 등)
- **기획** — 의사결정표 의도 (가입 불가를 혜택보다 먼저, 최고금리보다 기본금리 먼저, 분량 8문장 이하 등). v0.3 규칙에는 없어서 실패가 예상됨. 프롬프트를 고친 뒤 통과하는지 보는 용도
- **참고** — 팀 결정 전 기준 (state 안내 문구 고정 여부, purpose와 무관한 Fact를 빼야 하는지). 점수 제외
- 결과: `grade_report.md`(요약, 버전 비교, 실패 목록) + `grade_results.csv`(전체 검사 결과)

## 한계
- T1~T4와 판정 결과는 가상 데이터다. 실제 KB 상품 + 2-4 단계 실제 출력으로 만든 케이스를 추가해야 최종 평가가 된다. `testcases/`에 JSON을 넣고 `expectations.json`에 같은 이름의 키로 단언을 추가하면 된다 (단언이 없어도 공통 검사 24개는 돌아감).
- 자동 채점은 형식·수치·판정 일치만 본다. 문장이 자연스러운지, 뜻이 미묘하게 바뀌었는지는 사람이 실패 목록과 출력을 같이 보며 확인해야 한다.
- 금액 표기(500000 / 500,000원 / 50만원)는 현재 따로 정규화하지 않는다. 팀이 동치 기준을 정하면 `grade.py`의 `norm()`에 추가.
