#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "[wfgy] usage: $0 <TASK_DIR> -- <base command and args...>" 1>&2
  exit 2
fi
TASK_DIR="$1"; shift || true
if [[ "${1:-}" != "--" ]]; then
  echo "[wfgy] usage: $0 <TASK_DIR> -- <base command and args...>" 1>&2
  exit 2
fi
shift
BUDGET="${TBENCH_TASK_TIMEOUT:-300}"
PLAYBOOK="${WF_PLAYBOOK_PATH:-wfgy_playbooks.yaml}"
PYBIN="$(command -v python3 || command -v python || true)"
if [[ -z "${PYBIN}" ]]; then
  echo "[wfgy] python not found" 1>&2
  exit 2
fi
if [[ -n "${WF_PROMPT_FILE:-}" ]]; then
  "${PYBIN}" wfgy_semantic_firewall.py || true
fi
exec "${PYBIN}" wfgy_retry.py \
  --task-dir "${TASK_DIR}" \
  --playbook "${PLAYBOOK}" \
  --budget-sec "${BUDGET}" \
  -- "$@"
