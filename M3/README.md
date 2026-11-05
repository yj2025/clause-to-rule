# M3 — 약관 · 상품설명서 요약 모델 시험 (2026-09 ~ 10)

무엇을 시험했고 결과가 어디 있는지. 실행법은 아래 «금융상품 약관 요약 비교 실행» 절부터.
GPU 실행은 전부 `logs/chain_*.sh` → `logs/memguard.sh`.

| 시험 | 날짜 | 코드 | 결과 | 결론 (자세한 것은 M2 저장소 [clause-to-rule](https://github.com/yj2025/clause-to-rule) 의 `docsab/` · 엑셀) |
|---|---|---|---|---|
| Upstage Solar API 연결 · 요약 | 09-02 | `history/solar_api_test_20260902.ipynb` | 노트북 출력 | 첫 시험. 키는 `.env` |
| KB스타통장 key 요약 — 요약입력 조항 · 원문 전체 | 10-12 | `compare_terms.py` · `logs/chain_kbstar*.sh` · `chain2.sh` | `results/kbstar_01` · `kbstar_02_exaone` · `kbstar_full_01` · `kbstar_full_02_qwen` | Gemma 12B 15/16 key · Qwen 4비트 흔들림 · EXAONE 예외 뭉갬. 문서 차이 · 물을 입력은 다 못 함 |
| 같은 입력 Gemma 4 31B | 10-13 | `logs/chain31.sh` | `results/kbstar_03_gemma31` · `kbstar_full_03_gemma31` | 목표에 가장 가까움 |
| 프리N · 별별통장2 | 10-13 | `logs/chain_more.sh` | `results/freen_01` · `byul2_01` | 31B 가장 나음 |
| 개인화 요약 프롬프트 v0.3 | 10-13 | `run_prompt.py` · `logs/chain_personal.sh` | `results/personal_01` | 31B 최상 |
| 팀 v2 입력 샘플 | 10-13 | `logs/chain_v2_sample.sh` | `results/v2_sample` | 31B 13/14 · 12B 10/14 |
| 전 상품 (55) Gemma 31B | 10-13~14 | `run_batch.py` · `logs/chain_all.sh` | `results/all_gemma31` | 상품별 결과는 이 폴더. M2 쪽에서 한 파일로 모았던 `all_products.json` 은 남아 있지 않다 |
| 생성평가 v0.3 · v0.4 (외부 평가 키트) | 10-14 | `m3eval/` · `logs/chain_m3eval_*.sh` | `m3eval/runs/` | 12B: T1~T3 v0.3 96% · v0.4 92% |
| 카드 «꼭 확인할 조건» 요약 | 10-14~15 | `cardsum/` · `logs/chain_cardsum_*.sh` | `cardsum/runs/` | 상품 5종 72건 통과: 31B 69 · 26B 65 · 12B 63 · Qwen 55 · EXAONE 28 |

- `exaone_local/modeling_exaone.py` — EXAONE 3.5 원격 코드를 transformers 5.18 에 맞게 고친 사본. 가중치 링크는 10-20 캐시 삭제로 깨져 10-28 에 지웠다 (다시 쓰려면 모델을 받고 링크를 다시 건다).
- 10-28 정리: 결과 폴더 `results_*` 를 `results/` 아래로 모으고 접두어를 뗐다 (스크립트 경로도 고침).
- 11-05 정리 — M3 혼자 돌도록 했다 (M2 로컬 폴더는 지우고 [clause-to-rule](https://github.com/yj2025/clause-to-rule) 로 옮김):
  - `m2_inputs.py` — `run_batch.py` 가 M2 에서 불러 쓰던 `build`(docsab/run_merged.py) · `parse_json`(run_local_v2.py) 를 그대로 옮긴 사본. 58개 상품에서 원본과 같은 입력을 만드는 것을 확인함.
  - `prompts/example_kbstar_user.txt` — `logs/chain_personal.sh` 가 쓰던 사용자 입력 예시(M2 docsab/prompts 에서 옮김). 시스템 프롬프트는 같은 파일인 `m3eval/prompts/personalized_summary_v0.3.system.txt` 를 쓴다.
  - `logs/chain_*.sh` 는 스크립트 위치 기준으로 `cd` 한다. 서버 경로는 기본값으로만 남기고 환경변수로 바꿀 수 있다 — `PY`(파이썬, 기본 `/workspace/.venv/bin/python`) · `HF_HOME`(모델 캐시, 기본 `/workspace/personal_workplace_CHO/.hf_cache`). `cardsum/run_cardsum.py` 도 `HF_HOME` 을 따른다.
  - `run_batch.py --src` — 팀 요약 입력 json 경로 (기본 `../../docs/요약입력_상품별.json`, 저장소 밖에 있음).
  - 지움: `m3eval/*.orig` 백업 2개, `m3eval/review/testcases/`(`m3eval/testcases/` 와 같은 사본).
- 모델 캐시(`HF_HOME`)에는 11-05 기준 Gemma 4 31B · Qwen3-8B 만 있다. 12B · 26B · EXAONE 시험을 다시 돌리려면 모델을 다시 받는다.

---

# 금융상품 약관 요약 비교 실행

Gemma 4 12B IT와 EXAONE 3.5 7.8B Instruct를 하나의 CUDA GPU에서 순차 실행합니다.
동일 UTF-8 약관과 동일 system/user 지시문을 사용하고 모델별 공식 채팅 템플릿을 적용합니다.
두 모델 모두 NF4 4비트, greedy decoding, 비추론 모드, 입력 4096/출력 1536 토큰이 기본입니다.
EXAONE은 추론 모드 전환 기능이 없으며 enable_thinking 인자는 템플릿에서 무시됩니다.
이 코드는 추론 비교용입니다. 파인튜닝 코드는 포함하지 않습니다.

## 환경 설치

Python 3.11 또는 3.12와 NVIDIA CUDA GPU를 권장합니다. Linux/WSL2 환경을 우선 권장합니다.
GPU 번호는 nvidia-smi로 확인하세요. 기존 Qwen 서버를 포함한 GPU 작업을 먼저 종료하세요.
모델 다운로드용 인터넷, 충분한 디스크 공간, Hugging Face 접근 권한이 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# 예시 CUDA 12.8 wheel. 드라이버에 맞는 명령은 https://pytorch.org/get-started/locally/ 확인.
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt
```

Windows PowerShell에서는 활성화 명령만 `.\.venv\Scripts\Activate.ps1`로 바꾸세요.
Gemma 4 12B 설정 파일은 Transformers 5.10.0.dev0를 명시하므로 기존 4.x/초기 5.x를 가정하지 않습니다.
설치 시 최신 Git main을 사용하고, 성공한 실행의 패키지 버전과 모델 commit은 JSON에 기록합니다.
Git main은 변동하므로 성공 환경은 `python -m pip freeze > environment.lock.txt`로 보관하세요.
AutoModelForMultimodalLM/gemma4_unified 오류가 나면 해당 아키텍처 지원 버전을 확인하세요.
설치된 모델을 다른 Gemma 버전으로 자동 대체하지 않습니다.

모델 접근 인증이 필요한 경우:

```bash
hf auth login
```

EXAONE의 trust_remote_code=True는 모델 저장소의 Python 코드를 실행합니다.
공식 저장소 코드를 검토하고, 반복 실험 시 모델·코드 revision을 고정하는 것을 권장합니다.

## 실행

약관은 UTF-8 `terms.txt`로 준비하세요. PDF 자체는 지원하지 않습니다.
표, 각주, 별표, 예외조항을 포함해 텍스트 추출 결과를 먼저 확인하세요.

```bash
python compare_terms.py --terms terms.txt --out results_01
```

현재 Qwen에서 사용한 프롬프트를 동일하게 적용하려면:

```bash
python compare_terms.py --terms terms.txt --prompt prompt.txt --out results_02
```

입력이 길면 기본적으로 두 모델 실행 전에 중단합니다. 원문을 몰래 자르지 않습니다.
같은 원문 구간으로 나누어 비교하려면:

```bash
python compare_terms.py --terms terms.txt --prompt prompt.txt --allow-chunks --out results_03
```

양쪽 토크나이저에서 모두 입력 한도에 맞는 공통 구간을 생성합니다.
단락/줄바꿈을 우선하지만 긴 한 줄은 문자 경계로 나뉠 수 있습니다.
구간 사이 참조조항은 단독 요약에서 놓칠 수 있으므로 각 구간과 원문을 함께 검토하세요.
분할 결과는 구간별 요약이며 전체 문서 통합 요약이 아닙니다. 자동 재요약은 하지 않습니다.

전체 약관이 조금 길고 GPU 여유가 있으면 입력 한도를 늘릴 수 있습니다:

```bash
python compare_terms.py --terms terms.txt --max-input-tokens 8192 --out results_04
```

토크나이저만 다운로드하여 공통 입력을 미리 확인하려면 `--prepare-only`를 추가하세요.
준비 결과가 있는 디렉터리를 재사용하지 않고 새 --out 경로로 실행하세요.
Qwen3-8B도 같은 조건으로 새로 실행하려면 `--models gemma exaone qwen`을 추가하세요.
기존 Qwen 출력과 비교할 때는 프롬프트뿐 아니라 입력, 양자화, 생성 설정 차이도 기록하세요.

## GPU 30GB 제한의 의미

기본 메모리 예산은 십진 28GB, 지정 가능한 최대값은 30GB입니다.
실제 카드 용량과 예산 중 작은 값에서 2GB를 빼 PyTorch allocator 상한을 설정합니다.
모든 가중치는 선택 GPU 한 장에 로드하며 CPU offload나 다중 GPU 우회는 사용하지 않습니다.
한 모델의 프로세스가 종료된 뒤 다음 모델을 시작하므로 모델 두 개가 동시에 GPU에 올라가지 않습니다.
드라이버·CUDA context·bitsandbytes 외부 할당 등 PyTorch 밖의 메모리는 이 상한의 통제 대상이 아닙니다.
따라서 전체 nvidia-smi 사용량이 반드시 예산 아래라는 하드웨어 수준 보장은 아닙니다.
전체 GPU 사용량은 nvidia-smi로 확인하세요. JSON의 peak_reserved_gb는 PyTorch 예약 메모리입니다.
실제 24GB 카드에서도 실행을 시도하지만 입력 길이와 소프트웨어에 따라 OOM이 날 수 있습니다.
OOM이면 먼저 입력 2048, 출력 1024로 줄이고 --allow-chunks를 사용해 새 결과 폴더로 재실행하세요.
자동으로 모델별 다른 입력 길이로 재시도하지 않아 비교 조건을 유지합니다.

## 저장 파일

- manifest.json: 원문 구간, 원문·프롬프트 SHA256, 모델별 토큰 수
- prompt.txt: 실제 공통 지시문
- gemma.json / exaone.json: 요약, 원본 출력, 토큰 수, 모델 commit, 패키지 버전, 메모리, 시간
- comparison.md: 모델별 구간 요약을 읽고 비교하는 보고서
- metrics.csv: 구간별 입력/출력 토큰, 생성 시간, 처리량, 최대 PyTorch 메모리
- run_status.json: 실패 모델 목록. 종료 코드 1이면 일부 또는 전체 실패

첫 실행의 로딩 시간은 다운로드를 포함합니다. 생성 시간도 warm-up 없는 관측값이므로 엄밀한 속도 벤치마크가 아닙니다.
출력 한도 도달 여부를 기록합니다. 한도 도달 시 동일한 출력 한도를 올려 두 모델을 다시 비교하세요.
greedy decoding은 동일 환경 내 변동을 줄이지만 다른 GPU/패키지에서 완전한 재현성을 보장하지 않습니다.
Gemma 공식 권장 sampling 대신 모델 간 공통 greedy 조건을 쓰는 실험입니다.
manifest.json에는 원문이 포함됩니다. 데이터 보관 정책에 맞게 결과 폴더를 관리하세요.

평가는 숫자·기간 정확성, 예외/단서 누락, 근거 없는 생성, 근거 조항 일치, 가독성 순으로 수행하세요.
자동 점수나 승자를 만들지 않습니다. 비교 표에서 시간보다 원문 충실도를 먼저 검토하세요.

## 라이선스와 출처

EXAONE 3.5는 연구 목적 사용을 허용하지만 모델 및 출력물의 상업적 사용은 별도 라이선스가 필요합니다.
발표 시 모델명·버전 출처를 표시하세요.

- https://huggingface.co/google/gemma-4-12B-it
- https://huggingface.co/google/gemma-4-12B-it/raw/main/config.json
- https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
- https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct/raw/main/LICENSE
- https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes

이 제공 환경에서는 CUDA 모델을 다운로드/실행하지 않았습니다. 구문, CLI, 공통 분할 로직만 검증했습니다.
