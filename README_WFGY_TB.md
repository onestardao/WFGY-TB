# WFGY TB Enhancements (root-level)
what this adds
1. task-family playbooks with conservative defaults
2. two-stage retry under a hard 300s budget
3. minimal semantic firewall and collapse guard
4. zero change to TB core. you pass your base command after `--`

quick start
```
source ./wfgy_env.sh

# example

./wfgy_router.sh ./tasks/my_task -- uvx --from terminal-bench==0.1.1 tb run --task ./tasks/my_task

# or

./wfgy_router.sh ./tasks/my_task -- tb client run --task ./tasks/my_task
```

notes
- stage2 only runs if stage1 failed or dt_guard flags collapse, and only if time remains.
- budget split: 72% + 20% + 8% safety.
- tune playbooks per family. no code changes needed.
