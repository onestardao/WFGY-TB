#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"
if [ -f "./wfgy_env.sh" ]; then
  source ./wfgy_env.sh
fi
cmd="${1:-start}"
start() {
  echo "[wfgy] starting router (dry-run: ${WFGY_DRY_RUN:-1})"
  nohup python3 wfgy_router_min.py >/tmp/wfgy_router.log 2>&1 &
  echo $! > /tmp/wfgy_router.pid
  echo "[wfgy] pid $(cat /tmp/wfgy_router.pid)"
}
stop() {
  if [ -f /tmp/wfgy_router.pid ]; then
    pid=$(cat /tmp/wfgy_router.pid)
    if ps -p "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      sleep 1
    fi
    rm -f /tmp/wfgy_router.pid
  else
    pkill -f wfgy_router_min.py || true
  fi
  echo "[wfgy] stopped"
}
reload() { stop; start; }
case "$cmd" in
  start) start ;;
  stop) stop ;;
  restart) reload ;;
  reload) reload ;;
  *) echo "usage: $0 {start|stop|reload|restart}" ; exit 1 ;;
esac
