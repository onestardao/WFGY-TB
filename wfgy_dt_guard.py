import re
from typing import List

def repeated_ngrams_ratio(text: str, n: int = 3) -> float:
    toks = text.split()
    if len(toks) < n * 2:
        return 0.0
    grams = [" ".join(toks[i:i+n]) for i in range(0, len(toks) - n + 1)]
    total = len(grams)
    uniq = len(set(grams))
    return 1.0 - (uniq / max(total, 1))

def illegal_cross_paths(text: str) -> bool:
    bad = [
        r"ignore previous instructions",
        r"disregard.*rules",
        r"format.*then.*different format",
    ]
    for p in bad:
        if re.search(p, text, re.I | re.S):
            return True
    return False

def collapse_suspected(text: str) -> bool:
    if repeated_ngrams_ratio(text, 3) > 0.35:
        return True
    if re.search(r"(\b\w+\b)(?:\s+\1){3,}", text, re.I):
        return True
    return False

def apply(text: str) -> str:
    if illegal_cross_paths(text):
        raise ValueError("illegal cross path detected")
    if collapse_suspected(text):
        return text[:1024]
    return text
