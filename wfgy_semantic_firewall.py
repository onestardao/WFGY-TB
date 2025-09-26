from typing import Dict, List, Tuple

def _truncate(s: str, max_len: int) -> str:
    return s[:max_len] if max_len > 0 and len(s) > max_len else s

def _contains_any(s: str, pats: List[str]) -> bool:
    low = s.lower()
    return any(p and p.lower() in low for p in pats)

def _allow_symbol(c: str, allowed: List[str]) -> bool:
    return c.isalnum() or (c in allowed) or c.isspace()

def _strip_disallowed_chars(s: str, allowed: List[str]) -> str:
    return "".join(ch for ch in s if _allow_symbol(ch, allowed))

def gate(messages: List[Dict], family_params: Dict) -> Tuple[List[Dict], Dict]:
    fw = family_params.get("firewall", {})
    max_system_len = int(fw.get("max_system_len", 480))
    allow_symbols = list(fw.get("allow_symbols", [".",",",":",";","-","_","+","=","*","/","\\"]))
    banned_patterns = list(fw.get("banned_patterns", []))
    _ = list(fw.get("whitelist_tokens", []))

    logs = {"truncated": False, "stripped": False, "blocked": False}
    out = []
    for m in messages:
        role = m.get("role","user")
        content = str(m.get("content",""))
        if role != "system" and _contains_any(content, banned_patterns):
            logs["blocked"] = True
            content = _strip_disallowed_chars(content, allow_symbols)
            logs["stripped"] = True
        if role == "system" and len(content) > max_system_len:
            content = _truncate(content, max_system_len)
            logs["truncated"] = True
        cleaned = _strip_disallowed_chars(content, allow_symbols)
        if cleaned != content:
            logs["stripped"] = True
        out.append({"role": role, "content": cleaned})
    return out, logs
