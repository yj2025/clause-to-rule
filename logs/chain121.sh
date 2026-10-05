#!/usr/bin/env bash
# 2026-10-06 v121 — kb10 두 판 뒤 코퍼스 한 판
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v121a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v121b
./run_round.sh v121
echo "$(date '+%F %T') v121 체인 끝"
