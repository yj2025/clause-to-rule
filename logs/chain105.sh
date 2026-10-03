#!/usr/bin/env bash
# 2026-10-03 v105 — 코퍼스 네 판 뒤 kb10 두 판
cd /workspace/personal_workplace_CHO/model/M2-2
for v in v105 v106 v107 v108; do ./run_round.sh $v; done
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v105a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v105b
echo "$(date '+%F %T') v105 체인 끝"
