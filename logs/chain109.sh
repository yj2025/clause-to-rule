#!/usr/bin/env bash
# 2026-10-04 v109 — kb10 두 판 뒤 코퍼스 한 판
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v109a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v109b
./run_round.sh v109
echo "$(date '+%F %T') v109 체인 끝"
