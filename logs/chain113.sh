#!/usr/bin/env bash
# 2026-10-04 v113 — kb10 두 판 뒤 코퍼스 두 판
cd /workspace/personal_workplace_CHO/model/M2-2
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v113a
CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10v113b
for v in v113 v114; do ./run_round.sh $v; done
echo "$(date '+%F %T') v113 체인 끝"
