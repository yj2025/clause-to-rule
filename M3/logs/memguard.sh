#!/bin/bash
# 10-14 · 메모리 안전장치. 명령을 새 프로세스 그룹으로 띄우고, 컨테이너가 위험해지면 그룹째 끈다.
# 파드 한도 28GiB 를 넘기면 sshd 까지 멈춰 SSH 가 막힘(10-14 26B 로딩 때 실제로 일어남).
# 쓰기: memguard.sh <로그파일> <명령...>   한도는 환경변수로 바꿀 수 있음
LOG=$1; shift
ANON_MAX_GB=${ANON_MAX_GB:-22}   # 컨테이너 전체 anon 메모리 (팀원 몫 포함, 한도 28GiB)
JOB_MAX_GB=${JOB_MAX_GB:-14}     # 이 작업 프로세스들의 RssAnon 합
PSI_MAX=${PSI_MAX:-30}           # /proc/pressure/memory full avg10 (%)
PSI_HITS=${PSI_HITS:-3}          # 이만큼 연속(2초 간격)이면 끔
say(){ echo "$(TZ=Asia/Seoul date '+%F %T') [memguard] $*" >> "$LOG"; }
setsid "$@" >> "$LOG" 2>&1 &
PG=$!
say "시작 pgid=$PG · 한도: 전체 anon ${ANON_MAX_GB}G, 작업 ${JOB_MAX_GB}G, PSI full ${PSI_MAX}% x${PSI_HITS}"
hits=0; peak_all=0; peak_job=0
while kill -0 -- -$PG 2>/dev/null; do
  all=$(awk '$1=="anon"{printf "%.1f", $2/2^30}' /sys/fs/cgroup/memory.stat)
  job=$(for p in $(pgrep -g $PG); do awk '/^RssAnon/{print $2}' /proc/$p/status 2>/dev/null; done | awk '{s+=$1} END{printf "%.1f", s/2^20}')
  psi=$(awk '/^full/{split($2,a,"="); print a[2]}' /proc/pressure/memory)
  peak_all=$(awk -v a=$all -v b=$peak_all 'BEGIN{print (a>b)?a:b}')
  peak_job=$(awk -v a=$job -v b=$peak_job 'BEGIN{print (a>b)?a:b}')
  if awk -v p=$psi -v m=$PSI_MAX 'BEGIN{exit !(p>m)}'; then hits=$((hits+1)); else hits=0; fi
  why=""
  awk -v a=$all -v m=$ANON_MAX_GB 'BEGIN{exit !(a>m)}' && why="전체 anon ${all}G > ${ANON_MAX_GB}G"
  awk -v a=$job -v m=$JOB_MAX_GB 'BEGIN{exit !(a>m)}' && why="작업 anon ${job}G > ${JOB_MAX_GB}G"
  [ $hits -ge $PSI_HITS ] && why="메모리 정체 PSI full ${psi}% 가 ${hits}회 연속"
  if [ -n "$why" ]; then
    say "중단: $why → 프로세스 그룹 종료"
    kill -TERM -- -$PG 2>/dev/null; sleep 5; kill -KILL -- -$PG 2>/dev/null
    wait $PG 2>/dev/null; exit 137
  fi
  sleep 2
done
wait $PG; rc=$?
say "끝 (종료코드 $rc) · 최대 전체 anon ${peak_all}G, 최대 작업 anon ${peak_job}G"
exit $rc
