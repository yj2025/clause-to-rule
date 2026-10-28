#!/bin/bash
# NEXT_PLAN 8단계 (2026-10-27, 사용자 승인) — 이어받기 자리만 Gemma 투표. kb10 에서 e1 이 OK rule 을 안 냈고
# Gemma(탐욕) 가 OK rule 을 낸 15조문 × 온도 0.7 · 5회. P1 은 끈 채 (vote.py · relay_vote.py 가 채점 때 얹는다).
cd "$(dirname "$0")/.." || exit 1
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
IDS=KBGL-S2-R05,KBGL-S2-R06,KBMY-S1-P01,KBMY-S2-R01,KBMY-S2-R08,KBMY-S2-R16,KBNR-S2-R05,KBNR-S2-R06,KBNR-S2-R09,KBSME-S3-R02,KBSSG-S2-R01,KBSSG-S2-R06,KBSSG-S2-R10,KBSSG-S4-R01,KBSTR-S2-R07
../M3/logs/memguard.sh lora/logs/vote_kb10_gemma31.log /workspace/.venv/bin/python lora/distill.py \
  --clauses showcase/clauses_key.json --ids $IDS --samples 5 --temperature 0.7 --out lora/results/vote_kb10_gemma31.json
