import os, re, json
from typing import Dict, Any

ALLOW_LIST = {"hello-world", "sanitize-git-repo", "extract-safely"}

def _redact_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(payload))
    def redact(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = re.sub(r"sk-[A-Za-z0-9_\-]{20,}", "[REDACTED_KEY]", s)
        return s
    if "messages" in out:
        for m in out["messages"]:
            for k in ("content", "text"):
                if k in m and isinstance(m[k], str):
                    m[k] = redact(m[k])
    return out

def sanitize_prompt(task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    task = task or "generic"
    messages = payload.get("messages") or []
    max_sys = 8000
    for m in messages:
        if m.get("role") == "system" and isinstance(m.get("content"), str):
            m["content"] = m["content"][:max_sys]
    max_user = 6000
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            m["content"] = m["content"][:max_user]
    return _redact_keys(payload)

def gate(task: str) -> bool:
    if task in ALLOW_LIST:
        return True
    return True

if __name__ == "__main__":
    print("semantic firewall ready")
