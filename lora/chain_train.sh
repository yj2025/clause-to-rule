#!/bin/bash
# 증류가 끝나면 → SFT 데이터 → QLoRA 학습 (2026-10-22). 학습은 memguard 아래에서 돈다.
#   setsid nohup lora/chain_train.sh >/dev/null 2>&1 &
cd "$(dirname "$0")/.." || exit 1
LOG=lora/logs/chain_train.log
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') [chain] $*" >> "$LOG"; }
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/workspace/.venv/bin/python

say "증류 끝 기다림"
while kill -0 "${DISTILL_PID:?}" 2>/dev/null; do sleep 60; done
if ! grep -q "^완료 " lora/logs/distill.log; then say "증류가 완료 줄 없이 끝남 — 멈춤"; exit 1; fi
say "증류 끝 → SFT 데이터"
$PY lora/make_sft.py --distill lora/data/distill_gemma31.json >> "$LOG" 2>&1 || { say "make_sft 실패"; exit 1; }

# GPU 가 비기를 기다린다 (남이 쓰고 있으면 24GB 여유가 날 때까지)
while [ "$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)" -lt 24000 ]; do sleep 120; done
say "학습 시작"
../M3/logs/memguard.sh lora/logs/train_r16.log $PY lora/train_lora.py --out lora/adapters/r16 --epochs 3
say "학습 끝 (종료코드 $?)"
