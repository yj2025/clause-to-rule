#!/usr/bin/env bash
set -u
export HF_HOME=/workspace/personal_workplace_CHO/.hf_cache HF_HUB_DISABLE_PROGRESS_BARS=1 TQDM_DISABLE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/workspace/.venv/bin/python
NEW=/workspace/personal_workplace_CHO/model/M2-2
OLD=<107e548 worktree>
for i in 1 2 3 4; do
  for tag in old new; do
    d=$NEW; [ $tag = old ] && d=$OLD
    (cd $d && $PY run_local_v2.py --out results/r23check/r23_${tag}_$i.json --clauses data/corpus.json --runs 1 --temperature 0.1 --max-new-tokens 3072 --no-retry --only KBYY-S2-R23) > results/r23check/r23_${tag}_$i.log 2>&1
    echo "$(date -u +%H:%M:%S) $tag $i 종료코드 $?"
  done
done
echo 끝
