#!/usr/bin/env bash
# 2026-10-02 v98 — kb10 두 번(따로 띄운 프로세스) 뒤 코퍼스 한 번
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v98a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v98b
./run_round.sh v98
echo "$(date '+%F %T') v98 체인 끝"
