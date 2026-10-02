#!/usr/bin/env bash
# 2026-10-01 kb10 대조 — 같은 날 지금 코드(fdd6af7 · v94 되돌린 뒤)와 09-29 코드(432b02e)를 연달아 돌린다.
# v94 체인과 겹치지 않게 v97 완주를 기다린다.
until grep -q 'v97 완주' /workspace/personal_workplace_CHO/model/M2-2/logs/chain94.log; do sleep 60; done
echo "$(date '+%F %T') v94 체인 끝 — kb10new 시작"
cd /workspace/personal_workplace_CHO/model/M2-2 && CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10new
echo "$(date '+%F %T') kb10new 끝 — kb10old 시작 (432b02e)"
cd /workspace/personal_workplace_CHO/model/M2-2-kb10old && CORPUS=showcase/clauses_key.json ./showcase/run_showcase.sh kb10old
echo "$(date '+%F %T') kb10 대조 둘 다 끝"
