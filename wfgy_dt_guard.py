#!/usr/bin/env python3
import sys, os, re, json
def entropy(s: str) -> float:
    if not s:
        return 0.0
    from math import log2
    p = {}
    for ch in s:
        p[ch] = p.get(ch, 0) + 1
    n = len(s)
    return -sum((c/n)*log2(c/n) for c in p.values())
def detect_collapse(output: str) -> dict:
    flags = []
    if not output.strip():
        flags.append("empty")
    if len(output) < 64 and "error" in output.lower():
        flags.append("short_error")
    if re.search(r"(repeat(ed)?\s+line\s*){3,}", output, re.I):
        flags.append("repeat")
    if entropy(output) < 2.0 and len(output) > 256:
        flags.append("low_entropy")
    return {"collapse": bool(flags), "reasons": flags}
def main():
    data = sys.stdin.read()
    res = detect_collapse(data)
    print(json.dumps(res))
    return 0
if __name__ == "__main__":
    sys.exit(main())

# WFGY PATCH MARKER


# === WFGY micro-upgrade: soft question/disclaimer detector (safe override) ===
try:
    QUESTIONY_TOKENS = ["?", "clarify", "can you", "should I", "do you want", "as a language model", "i cannot", "i can't", "i am unable"]
    def _wfgy_questiony_or_disclaimer(text: str) -> bool:
        low = (text or "").lower()
        return any(tok in low for tok in QUESTIONY_TOKENS)
    if 'apply_guard' in globals():
        _orig_apply_guard = apply_guard
        def apply_guard(text: str) -> str:
            if _wfgy_questiony_or_disclaimer(text):
                return text
            return _orig_apply_guard(text)
except Exception:
    pass
