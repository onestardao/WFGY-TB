#!/usr/bin/env python3
import argparse, os, sys, time, subprocess, json, pathlib, yaml, re
def load_playbook(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
def now_ms():
    import time as _t
    return int(_t.time() * 1000)
def run_with_timeout(cmd, env, timeout_sec, log_path):
    start = now_ms()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
    out_chunks = []
    try:
        out, _ = proc.communicate(timeout=timeout_sec)
        out_chunks.append(out or "")
    except subprocess.TimeoutExpired:
        proc.kill()
        out_chunks.append("\n[wfgy] timeout kill\n")
        return 124, "".join(out_chunks), now_ms() - start
    rc = proc.returncode
    out_s = "".join(out_chunks) + out
    pathlib.Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(out_s)
    return rc, out_s, now_ms() - start
def choose_family(task_dir, playbook):
    from glob import glob
    def match_any(filespecs):
        for spec in filespecs:
            if spec.startswith("*."):
                if glob(os.path.join(task_dir, spec)):
                    return True
            else:
                if os.path.exists(os.path.join(task_dir, spec)):
                    return True
        return False
    text = ""
    for name in ["README.md", "readme.md", "task.txt", "instructions.txt"]:
        fp = os.path.join(task_dir, name)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    text += "\n" + f.read()
            except:
                pass
    families = playbook.get("families", {})
    for fam, conf in families.items():
        det = conf.get("detect", {})
        any_of = det.get("any_of", [])
        hints = det.get("text_hint", [])
        ok_file = match_any(any_of) if any_of else False
        ok_hint = any(re.search(h, text, re.I) for h in hints) if hints else False
        if ok_file or ok_hint:
            return fam
    return "generic"
def format_cmd(base_cmd, args_append):
    return base_cmd + (args_append or [])
def main():
    ap = argparse.ArgumentParser(description="WFGY two-stage retry with time budgeting")
    ap.add_argument("--task-dir", required=True)
    ap.add_argument("--family", default=None)
    ap.add_argument("--playbook", default="wfgy_playbooks.yaml")
    ap.add_argument("--budget-sec", type=int, default=300)
    ap.add_argument("--log-dir", default="wfgy_logs")
    ap.add_argument("base_cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    if args.base_cmd and args.base_cmd[0] == "--":
        args.base_cmd = args.base_cmd[1:]
    if not args.base_cmd:
        print("[wfgy] error: base command missing after --", file=sys.stderr)
        return 2
    play = load_playbook(args.playbook)
    fam = args.family or choose_family(args.task_dir, play)
    conf = play["families"].get(fam, play["families"]["generic"])
    hard = min(args.budget_sec, play.get("budget", {}).get("hard_sec", 300))
    s1_ratio = play.get("budget", {}).get("stage1_ratio", 0.72)
    s2_ratio = play.get("budget", {}).get("stage2_ratio", 0.20)
    safety = play.get("budget", {}).get("safety_ratio", 0.08)
    s1_sec = int(hard * s1_ratio)
    s2_sec = int(hard * s2_ratio)
    safety_ms = int(hard * safety * 1000)
    log_root = os.path.join(args.log_dir, pathlib.Path(args.task_dir).name)
    pathlib.Path(log_root).mkdir(parents=True, exist_ok=True)
    base_cmd = args.base_cmd
    env_base = os.environ.copy()
    env_base["WF_TASK_DIR"] = os.path.abspath(args.task_dir)
    env_base["WF_FAMILY"] = fam
    env1 = env_base.copy()
    env1.update({k:str(v) for k,v in conf.get("stage1", {}).get("env", {}).items()})
    cmd1 = format_cmd(base_cmd, conf.get("stage1", {}).get("args_append", []))
    rc1, out1, dur1 = run_with_timeout(cmd1, env1, s1_sec, os.path.join(log_root, "stage1.log"))
    collapse = False
    try:
        p = subprocess.Popen([sys.executable, "wfgy_dt_guard.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        j, _ = p.communicate(input=out1, timeout=3)
        flag = json.loads(j)
        collapse = flag.get("collapse", False)
    except Exception:
        pass
    if rc1 == 0 and not collapse:
        print(json.dumps({"family": fam, "stage": 1, "rc": rc1, "ms": dur1}))
        return 0
    elapsed_ms = dur1
    remain_ms = hard*1000 - elapsed_ms - safety_ms
    if remain_ms <= 5000:
        print(json.dumps({"family": fam, "stage": 1, "rc": rc1, "ms": dur1, "note": "no time for stage2"}))
        return rc1 if rc1 != 0 else 0
    env2 = env_base.copy()
    env2.update({k:str(v) for k,v in conf.get("stage2", {}).get("env", {}).items()})
    cmd2 = format_cmd(base_cmd, conf.get("stage2", {}).get("args_append", []))
    rc2, out2, dur2 = run_with_timeout(cmd2, env2, int(remain_ms/1000), os.path.join(log_root, "stage2.log"))
    best_rc = rc2 if rc2 == 0 else rc1
    print(json.dumps({"family": fam, "stage": 2, "rc1": rc1, "rc2": rc2, "ms1": dur1, "ms2": dur2}))
    return 0 if best_rc == 0 else best_rc
if __name__ == "__main__":
    sys.exit(main())
