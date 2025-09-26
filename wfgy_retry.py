import time, random
from typing import Callable, Dict, Tuple

def run_with_retry(
    work_fn: Callable[[], Tuple[str, dict]],
    collapse_fn: Callable[[str], bool],
    params: Dict,
) -> Tuple[str, dict]:
    max_attempts = int(params.get("max_attempts", 2))
    base = float(params.get("base_backoff_s", 1.2))
    jitter = float(params.get("jitter_s", 0.6))

    last_text, last_meta = "", {"attempts": 0, "collapsed": False}
    for attempt in range(1, max_attempts + 1):
        text, meta = work_fn()
        last_text, last_meta = text, meta or {}
        last_meta["attempts"] = attempt
        if not collapse_fn(text):
            return text, last_meta
        last_meta["collapsed"] = True
        time.sleep(base + random.uniform(0, jitter))
    return last_text, last_meta
