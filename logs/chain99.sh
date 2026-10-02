#!/usr/bin/env bash
# 2026-10-02 v99 — kb10 두 번(따로 띄운 프로세스) 뒤 코퍼스 한 번
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v99a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v99b
./run_round.sh v99
echo "$(date '+%F %T') v99 체인 끝"
