#!/usr/bin/env bash
# 2026-10-03 v101 — 코퍼스 네 판 뒤 kb10 두 판
cd /workspace/personal_workplace_CHO/model/M2-2
for v in v101 v102 v103 v104; do ./run_round.sh $v; done
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v101a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v101b
echo "$(date '+%F %T') v101 체인 끝"
