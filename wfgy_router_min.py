import os, json, time, yaml, re
from typing import Dict, List
from wfgy_semantic_firewall import gate
from wfgy_dt_guard import detect_collapse, enforce
from wfgy_retry import run_with_retry

def _load_playbooks(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _match_family(task_name: str, play: Dict) -> str:
    name = (task_name or "").lower()
    for fam, keys in (play.get("aliases") or {}).items():
        for k in keys or []:
            if k in name:
                return fam
    return "general"

def _strip_wrappers(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```[a-zA-Z0-9]*\n", "", s)
    s = re.sub(r"```\s*$", "", s)
    s = re.sub(r"^(output:|answer:)\s*", "", s, flags=re.I)
    s = s.strip().strip('"').strip("'").strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def _is_simple_text_task(task_name: str) -> bool:
    return any(k in (task_name or "").lower() for k in ["hello-world", "simple-answer", "exact-print"])

def _force_strict_format(text: str, formatter: str) -> str:
    t = text.strip()
    if formatter == "json":
        if not t.startswith("{") and not t.startswith("["):
            return t
        t = t.replace("\n", "").replace("\r", "")
        return t
    if formatter == "number":
        m = re.search(r"[-+]?[0-9]*\.?[0-9]+", t)
        return m.group(0) if m else t
    if formatter == "yesno":
        low = t.lower()
        if "yes" in low and "no" not in low:
            return "yes"
        if "no" in low and "yes" not in low:
            return "no"
        return t
    if formatter == "line":
        return t.splitlines()[0] if t else t
    if "\n" in t and len(t) > 160:
        return t.splitlines()[0]
    return t

def _system_only_output(formatter: str) -> str:
    if formatter == "json":
        return "Only output the final JSON. No notes. No code. No markdown."
    if formatter == "number":
        return "Only output the final numeric value. No words. No units if not requested."
    if formatter == "yesno":
        return "Only output 'yes' or 'no'. No other text."
    if formatter == "line":
        return "Only output the final line. No extra lines."
    return "Only output the final answer. No extra words."

def route(task_name: str, user_prompt: str, messages: List[Dict] = None) -> Dict:
    play_path = os.getenv("WFGY_PLAYBOOK", "wfgy_playbooks.yaml")
    dry_run = int(os.getenv("WFGY_DRY_RUN", "1")) == 1
    data = _load_playbooks(play_path)
    family = _match_family(task_name, data)
    fam_params = data.get("families", {}).get(family, data.get("families", {}).get("general", {}))

    if fam_params.get("prescan", {}).get("enabled", False):
        s = min(int(os.getenv("WFGY_PRESCAN_MAX_S", "5")), int(fam_params["prescan"].get("seconds", 3)))
        time.sleep(max(0, s))

    strict_cfg = fam_params.get("strict_output", {})
    formatter = strict_cfg.get("formatter", "auto")
    want_strict = bool(strict_cfg.get("enabled", False) or _is_simple_text_task(task_name))

    system_directives = []
    if want_strict:
        system_directives.append(_system_only_output(formatter))

    msgs = messages[:] if messages else []
    if system_directives:
        msgs = [{"role":"system","content":" ".join(system_directives)}] + msgs
    msgs += [{"role":"user","content": user_prompt}]

    msgs, fw_logs = gate(msgs, fam_params)

    def once_attempt():
        if dry_run:
            text = f"[dry-run:{family}] " + user_prompt.strip().splitlines()[0][:120]
            return text, {"dry_run": True, "family": family, "fw": fw_logs}
        raise RuntimeError("Real model call not wired. Set WFGY_DRY_RUN=1 for smoke test.")

    def collapse_fn(txt: str) -> bool:
        return detect_collapse(txt or "", fam_params)

    text, meta = run_with_retry(once_attempt, collapse_fn, fam_params.get("retry", {}))

    text = enforce(text, fam_params)
    text = _strip_wrappers(text)
    if want_strict:
        text = _force_strict_format(text, formatter)

    if fam_params.get("micro_ab", {}).get("enabled", False):
        meta["micro_ab"] = "enabled"

    # simple eval label
    low = text.lower()
    if any(k in low for k in ["maybe","not sure","uncertain"]):
        label = "uncertain"
    elif len(text.split()) < 3:
        label = "best-unique"
    else:
        label = "multiple" if " or " in low else "reasonable"
    meta["eval_label"] = label

    return {"family": family, "text": text, "meta": meta}

if __name__ == "__main__":
    out1 = route("hello-world", "print exactly: OK")
    out2 = route("raman-fitting", "compute best-fit a for y=a*x")
    print(json.dumps({"smoke_1": out1, "smoke_2": out2}, ensure_ascii=False, indent=2))
