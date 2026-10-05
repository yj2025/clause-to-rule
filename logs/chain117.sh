#!/usr/bin/env bash
# 2026-10-05 v117 — kb10 두 판 뒤 코퍼스 두 판
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v117a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v117b
for v in v117 v118; do ./run_round.sh $v; done
echo "$(date '+%F %T') v117 체인 끝"
