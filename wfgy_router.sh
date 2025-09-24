#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source ./wfgy_env.sh

pkill -f "python.*wfgy_retry.py" >/dev/null 2>&1 || true

nohup python3 -u wfgy_retry.py       >>"$WFGY_PROXY_LOG_FILE" 2>&1 &

echo "[wfgy-router] started (pid=$!) → port $WFGY_ROUTER_PORT"
sleep 0.3
echo "[wfgy-router] tail -n 100 -f $WFGY_PROXY_LOG_FILE"
