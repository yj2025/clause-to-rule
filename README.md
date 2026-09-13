# M2-2 — 약관 조문을 실행 가능한 조건식으로

은행 상품설명서의 조문을 기계가 실행할 수 있는 **조건식 JSON** 으로 바꾸고,
그 조건식으로 고객별 최종 적용금리를 계산한다.

```
약관 조문  ──▶  조건식 JSON  ──▶  개별 판별  ──▶  최종 적용금리
           태스크1          태스크2        태스크3
           (LLM)            (순수 코드)     (순수 코드)
```

**LLM 은 태스크 1 에만 쓴다.** 전처리(조문 분할)와 판별(3치 논리 실행기)은
전부 결정론적 코드다.

## 먼저 읽을 것

| 무엇이 궁금한가 | 어디를 볼까 |
|---|---|
| 이 저장소가 왜 여기 있나 | `RECOVERY.md` |
| 지금까지 무엇을 알아냈나 | **`ROUNDS.md`** ← 여기서 시작 |
| 한 라운드의 가설과 판정 | `EXPERIMENT_v<n>.md` |
| 이 변화가 노이즈인가 | **`NOISE.md`** |
| 팀이 정해야 할 것 | **`CATALOG_PROPOSAL.md`** |
| 원래 프로젝트의 서술 | `../model-2/qwen3-8B.ipynb` |

## 30초 요약

2026-09-11 컨테이너 재시작으로 원본 저장소가 통째로 사라졌다.
노트북에 저장된 출력과 살아남은 생성물을 근거로 다시 세웠고(`RECOVERY.md`),
그 위에서 라운드를 v1 부터 다시 돌리고 있다.

**형식은 크게 좋아졌고 뜻은 그렇지 않다.**

| | v1 | v7 | v14 |
|---|---:|---:|---:|
| ① JSON 파싱 | 76.1% | 99.3% | — |
| ⑤ 실행 가능 | 47.8% | 70.3% | — |
| ⑨ 근거 없는 수 | 33.3% | 53.6% | — |
| **⑫ 선언 일치** (gold 46) | — | — | **47.8%** |

형식 관문이 +23p 오르는 동안 **숫자를 지어내는 비율도 +20p 늘었다.**
"전부 통과 22 → 30" 은 프로젝트 진척이 아니라 JSON 문법 준수율이고,
**그 준수율조차 rule 을 더 많이 낸 덕이 상당 부분이다** (v11).

**형식 축에서 편향과 무관하게 남는 것은 ① 과 ④ 뿐이다.**
진전은 뜻 축(⑨⑩⑫⑬)으로만 판정한다.

## 지표

형식을 재는 것과 뜻을 재는 것을 갈라 둔다. **섞어 읽으면 안 된다.**

### 형식 (①~⑤, ⑦)

| | 무엇 | 어디 |
|---|---|---|
| ① | JSON 파싱 | `validate.score_record` |
| ② | 스키마 적합 | `schema.SCHEMA` |
| ③ | 카탈로그 준수 | `validate.check_catalog` |
| ④ | quote 가 원문에 있나 | `validate.check_quote` |
| ⑤ | 실행 가능 | `validate.check_executable` |
| ⑦ | 빈 배열 (별도 축) | `report.py` |

### 뜻 (⑥, ⑧~⑫)

| | 무엇 | 어디 |
|---|---|---|
| ⑥ | 실행 결과가 gold 와 같나 (조문 단위) | `scoring.py` |
| ⑧ | UNSUPPORTED 를 얼마나 쓰나 (회피 감시) | `report.unsupported_stats` |
| ⑨ | 생성물의 수가 조문에 있나 | `grounding.py` |
| ⑩ | 조문을 **합쳐** 낸 금리가 gold 와 같나 | `compose.py` |
| ⑪ | 인용문이 그 rule 을 받치나 (**하한**) | `support.py` |
| ⑫ | 빈 배열/UNSUPPORTED/정상 판정이 맞나 | `declare.py` |
| ⑬ | 카탈로그에 없는 개념을 문자열에 담나 | `invent.py` |
| ⑭ | 조건이 붙었는데 언제나 참인가 | `vacuous.py` |

**⑥ 만으로는 부족하다.** UNSUPPORTED 와 빈 배열을 못 가르고, 조문을 고립시켜
재므로 합성할 때만 드러나는 파괴를 못 본다. 그래서 축을 더 세웠다.

## 돌리는 법

```bash
export M2_REPO_ROOT=/workspace/personal_workplace_CHO/model/M2-2
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache

./run_round.sh v10 1        # 탐색 (1회차, 약 40분)
./run_round.sh v10 3        # 확인 (3회차, 약 2시간)

python report.py results/results_v10.json --baseline results/results_v9.json
python judge.py  results/results_v10.json results/results_v9.json --watch <조문id>...
python diagnose.py results/results_v10.json     # 다음 처방을 고르기 위한 브리핑
python noise.py  results/results_v10.json       # 그 라운드의 판정선
```

테스트: `/workspace/.venv/bin/python -m pytest tests/ -q`

## 라운드 규칙

1. **한 번에 하나만 바꾼다.** 둘을 같이 넣으면 어느 쪽이 먹었는지 못 가린다
2. **가설과 되돌림 선을 결과 전에 적는다.** 숫자를 보고 고르면 무엇이든 설명된다
3. **판정선은 축마다 다르다.** `NOISE.md` 에 실측값이 있다 —
   ⑫ 는 ±2.1p, ⑨ 는 **±23.5p** 다. 하나의 값을 모든 축에 쓰면 안 된다
4. **조문별로 풀기 전에는 군 평균을 처방의 효과로 읽지 않는다**
5. **탈출구를 열기 전에 그것을 세는 축을 먼저 세운다**

## 아직 못 한 것

- **gold 30개 전부 미검토** (`reviewed: false`). 이것 없이는 ⑥⑩⑫ 를 기준선으로 못 쓴다
- **카탈로그 확장.** gold 46조문에 표현 불가 rule 이 **53개, 30조문**에 있다.
  코퍼스의 3분의 2가 부분적으로든 전부든 옮길 수 없다.
  **지문으로는 못 푼다** — v15 에서 막았더니 다른 도구로 샜다.
  우선순위와 근거는 `CATALOG_PROPOSAL.md` 에 있다
- **뜻을 겨냥한 처방이 이제 시작이다.** v2~v6 은 전부 조판과 선택 규칙이었다
