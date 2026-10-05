#!/usr/bin/env bash
# 2026-10-05 v119 — kb10 두 판 뒤 코퍼스 한 판
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v119a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v119b
./run_round.sh v119
echo "$(date '+%F %T') v119 체인 끝"
