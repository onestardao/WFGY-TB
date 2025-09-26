from typing import Dict

def _ngram_repeat_ratio(text: str, n: int) -> float:
    text = text.strip()
    if n <= 0 or len(text) < n:
        return 0.0
    counts = {}
    total = 0
    for i in range(len(text) - n + 1):
        g = text[i:i+n]
        counts[g] = counts.get(g,0) + 1
        total += 1
    if total == 0:
        return 0.0
    return max(counts.values()) / total

def detect_collapse(text: str, family_params: Dict) -> bool:
    cfg = family_params.get("dt_guard", {})
    n = int(cfg.get("ngram_n", 5))
    limit = float(cfg.get("max_repeat_ratio", 0.2))
    return _ngram_repeat_ratio(text, n) >= limit

def enforce(text: str, family_params: Dict) -> str:
    cfg = family_params.get("dt_guard", {})
    max_len = int(cfg.get("truncate_after", 768))
    return text[:max_len] if max_len > 0 and len(text) > max_len else text
