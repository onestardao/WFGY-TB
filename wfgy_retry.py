import os, time, json, random, logging, uuid, math
from typing import Callable, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
LOG = logging.getLogger("wfgy-retry")

def _env_int(name: str, dflt: int) -> int:
    try:
        return int(os.getenv(name, dflt))
    except Exception:
        return dflt

def _env_float(name: str, dflt: float) -> float:
    try:
        return float(os.getenv(name, dflt))
    except Exception:
        return dflt

RETRY_MAX = _env_int("WFGY_RETRY_MAX", 2)
BASE_DELAY_MS = _env_int("WFGY_RETRY_BASE_DELAY_MS", 250)
JITTER_MS = _env_int("WFGY_RETRY_JITTER_MS", 120)
REQUEST_TIMEOUT_S = _env_int("WFGY_REQUEST_TIMEOUT_S", 90)

COLLAPSE_THRESHOLD = _env_float("WFGY_COLLAPSE_THRESHOLD", 0.18)
EARLYSTOP_MIN_CHARS = _env_int("WFGY_EARLYSTOP_MIN_CHARS", 64)

def _entropy_ratio(text: str) -> float:
    if not text:
        return 0.0
    from collections import Counter
    c = Counter(text)
    n = sum(c.values())
    probs = [v / n for v in c.values()]
    h = -sum(p * math.log(p + 1e-12) for p in probs)
    denom = math.log(len(c) + 1e-12)
    return h / denom if denom > 0 else 0.0

def _collapsed(text: str) -> bool:
    if len(text) < EARLYSTOP_MIN_CHARS:
        return True
    return _entropy_ratio(text) < COLLAPSE_THRESHOLD

def _sleep_backoff(try_idx: int) -> None:
    delay_ms = min(BASE_DELAY_MS * (2 ** try_idx), 3000)
    jitter = random.randint(0, JITTER_MS)
    time.sleep((delay_ms + jitter) / 1000.0)

def send_with_retry(send_fn: Callable[[], Dict[str, Any]],
                    redact: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    req_id = str(uuid.uuid4())[:8]
    for t in range(RETRY_MAX + 1):
        t0 = time.time()
        try:
            resp = send_fn()
        except Exception as e:
            LOG.warning(json.dumps({
                "req": req_id, "try": t, "kind": "exception", "error": repr(e)
            }))
            resp = {"ok": False, "error": repr(e)}

        took = time.time() - t0
        if resp.get("ok") and isinstance(resp.get("text"), str):
            text = resp["text"]
            collapsed = _collapsed(text)
            LOG.info(json.dumps({
                "req": req_id, "try": t, "ok": True, "took_s": round(took, 3),
                "len": len(text), "collapsed": collapsed
            }))
            if collapsed and t < RETRY_MAX:
                _sleep_backoff(t)
                continue
            return resp

        LOG.warning(json.dumps({
            "req": req_id, "try": t, "ok": False, "took_s": round(took, 3),
            "error": resp.get("error", "unknown")
        }))
        if t < RETRY_MAX:
            _sleep_backoff(t)

    return {"ok": False, "error": "exhausted"}

if __name__ == "__main__":
    LOG.info("wfgy_retry loaded. This file provides send_with_retry().")
