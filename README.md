# WFGY-TB

Integration scripts and semantic firewall configs for running **WFGY 2.0** on the Stanford Terminal-Bench (TB).

## Files

- `wfgy_router.sh` – routing shell script for TB tasks
- `wfgy_retry.py` – retry manager for failed TB runs
- `wfgy_playbooks.yaml` – playbooks defining task strategies
- `wfgy_semantic_firewall.py` – semantic firewall guard module
- `wfgy_dt_guard.py` – Drunk Transformer safety guard
- `wfgy_env.sh` – environment setup for TB runs

## Usage (MVP)

This repository contains the integration layer between **WFGY 2.0** and the Stanford Terminal-Bench pipeline.  
It ensures:
- API calls are routed through the semantic firewall
- Failed runs can retry automatically
- All safeguards (DT Guard, Firewall) are enforced before submission

## Current Status

- API ✅  
- Pipeline ✅  
- WFGY 2.0 ✅  
- Problem: answers are not being written into `/app/solution.txt` (root cause under investigation)

## Next Steps

1. Fix write-to-file issue (solution not saved to `/app/solution.txt`).  
2. Run full benchmark on TB.  
3. Collect logs (asciinema + agent.cast).  
4. Prepare final submission.

---

MIT License (to be added if you want).
