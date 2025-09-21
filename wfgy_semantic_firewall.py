#!/usr/bin/env python3
import os, re, sys, json, pathlib, time
INJECTION_PATTERNS = [
    r"\bignore\b.*\bsystem\b",
    r"\boverride\b.*\bpolicy\b",
    r"\bdownload\b.*\bhttp",
    r"\bdisable\b.*\bsafety\b",
    r"\bset\s+temperature\s*=\s*[12]",
]
def sanitize_text(txt: str) -> str:
    cleaned = txt
    for pat in INJECTION_PATTERNS:
        cleaned = re.sub(pat, "[blocked]", cleaned, flags=re.I|re.S)
    return cleaned
def sanitize_file(in_path: str, out_path: str) -> None:
    try:
        with open(in_path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
    except FileNotFoundError:
        return
    dst = sanitize_text(src)
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dst)
def run():
    prompt_file = os.environ.get("WF_PROMPT_FILE") or os.environ.get("TASK_PROMPT_FILE")
    if not prompt_file:
        return 0
    out_file = os.environ.get("WF_PROMPT_FILE_SANITIZED", "wfgy_sanitized/prompt.txt")
    sanitize_file(prompt_file, out_file)
    print(json.dumps({"sanitized_prompt": out_file}))
    return 0
if __name__ == "__main__":
    sys.exit(run())
