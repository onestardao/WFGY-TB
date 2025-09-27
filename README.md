# WFGY-TB Integration (MVP+, Seven-Step Wrapped, gpt-5)

This repo gives a non-invasive way to run Stanford **Terminal-Bench** through **WFGY Core 2.0**.  
Every LLM call is guarded by a **semantic firewall**, then routed through the **7-step reasoning chain**, then checked by **DT guards** with conditional retry.  
We keep TB unchanged. We only wrap the model call.

**Why this works**  
WFGY Core is a compact math layer. It measures semantic drift `ΔS`, watches state `λ_observe`, and applies a chain of modules: **BBMC**, **Coupler**, **BBPF**, **BBAM**, **BBCR**, with **Drunk Transformer** gates (**WRI, WAI, WAY, WDT, WTF**).  
These modules limit collapse, keep attention diverse, and block illegal cross-paths. Result is higher stability and fewer off-by-one mistakes.  
Read the core ideas here: [WFGY Core 2.0](https://github.com/onestardao/WFGY/blob/main/core/README.md)

---

## 📌 Status

The reproducible scripts and result files are **not yet uploaded**.  
We are actively updating, and the full package (logs, configs, reproduction guide) will be published once the official Terminal-Bench leaderboard results are out.  
Stay tuned for the public release — all contents will be open-sourced here under the same license.

---

## Architecture

```

Baseline:         TB → LiteLLM(8080) → OpenAI
With WFGY:        TB → WFGY Router → LiteLLM(8080) → OpenAI
pre:  semantic firewall
mid:  7-step reasoning (stage1/2 budgets)
post: DT guard + conditional retry

````

WFGY wraps the whole task execution. Not only the prompt text.

---

## Requirements

- Ubuntu 22.04 or newer
- Python 3.10 or newer
- `uv` or `uvx`
- Docker engine for TB tasks
- OpenAI key that can use `gpt-5`
- Outbound HTTPS to `api.openai.com`

---

## 0) LiteLLM on port 8080

Create `/etc/litellm.yaml`:

```yaml
model_list:
  - model_name: openai/gpt-5
    litellm_params:
      model: gpt-5
      api_base: https://api.openai.com/v1
      api_key: ${OPENAI_API_KEY}

litellm_settings:
  timeout: 20
  num_retries: 0
strict: false
````

Start it:

```bash
pkill -9 -f 'litellm|uvicorn' || true
export OPENAI_API_KEY="sk-REDACTED"
export HTTPX_DISABLE_HTTP2=1
litellm --host 0.0.0.0 --port 8080 --config /etc/litellm.yaml --debug --num_workers 1
```

Sanity:

```bash
curl -s http://127.0.0.1:8080/v1/models | jq -r '.data[].id'
```

---

## 1) Dataset

Use either dataset path or the `-d` flag. The examples below use the path.

```bash
uvx --from terminal-bench tb datasets download --dataset terminal-bench-core==0.1.1 --overwrite | tee dl.log
DATASET_DIR="$(grep -m1 -oP 'Dataset location:\s*\K.*' dl.log)"
echo "$DATASET_DIR"
find "$DATASET_DIR" -name "*.yaml" | wc -l
```

---

## 2) Baseline sanity with gpt-5

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
export OPENAI_API_KEY="sk-local-proxy"

uvx --from terminal-bench tb run \
  --dataset-path "$DATASET_DIR" \
  --agent terminus \
  --model openai/gpt-5 \
  --task-id hello-world \
  --n-attempts 1 \
  --n-concurrent 1 \
  --rebuild \
2>&1 | tee runs/baseline-hello.log
```

You should see a `runs/.../results.json` when it finishes.

---

## 3) WFGY router smoke

Environment:

```bash
export WFGY_UPSTREAM_BASE_URL="http://127.0.0.1:8080/v1"
export WFGY_LOG_DIR="${PWD}/wfgy_logs"
export WFGY_PLAYBOOK="${PWD}/wfgy_playbooks.yaml"
mkdir -p "$WFGY_LOG_DIR"
chmod +x ./wfgy_router.sh
```

Run one task through WFGY:

```bash
bash ./wfgy_router.sh -- \
  uvx --from terminal-bench tb run \
    --dataset-path "$DATASET_DIR" \
    --agent terminus \
    --model openai/gpt-5 \
    --task-id hello-world \
    --n-attempts 1 \
    --n-concurrent 1 \
    --rebuild \
2>&1 | tee runs/wfgy-hello.log
```

Expected: router prints stage budgets and DT guard messages. `wfgy_logs/...` directory appears.

---

## 4) Small batch

```bash
for T in hello-world sanitize-git-repo csv-to-parquet; do
  bash ./wfgy_router.sh -- \
    uvx --from terminal-bench tb run \
      --dataset-path "$DATASET_DIR" \
      --agent terminus \
      --model openai/gpt-5 \
      --task-id "$T" \
      --n-attempts 1 \
      --n-concurrent 1 \
      --rebuild \
  2>&1 | tee "runs/wfgy-$T.log"
done
```

---

## 5) Full run for leaderboard

Follow TB rules. Use `terminus` and the official core dataset.

```bash
uvx --from terminal-bench tb run \
  --dataset-path "$DATASET_DIR" \
  --agent terminus \
  --model openai/gpt-5 \
  --n-tasks 182 \
  --n-attempts 1 \
  --n-concurrent 1 \
2>&1 | tee runs/core011-gpt5.log
```

Keep the `results.json` and the log.

---

## Verification list

* LiteLLM returns models and chat completions locally
* Baseline hello-world produces a results file
* WFGY smoke prints stage markers and writes to `wfgy_logs`
* TB logs show progress like `Running tasks (x/...)`

---

## Troubleshooting

**Only 80 tasks available**
You likely ran without `--dataset-path` or wrong path. Re-download and pass the path.

**Stuck at starting harness**
Check Docker is active. Rebuild a single task with `--rebuild`.

**RetryError or timeouts**
Check the key can call gpt-5. Keep `--n-concurrent 1`. Do not set a custom `LITELLM_API_BASE` unless you know what you are doing.

**Disconnected SSH**
Always run long jobs inside tmux. Reattach with `tmux attach -t tbench` if you used a session.

---

## Why WFGY helps on TB

* The firewall removes junk patterns and forces strict output modes when required by the task family
* Seven-step chain reduces drift and keeps plan structure stable across the command sequence
* DT guard catches collapse and retries inside budget rather than returning garbage
  Together they turn many near-misses into clean passes with small token cost.

Read the math and the design notes here: [WFGY Core 2.0](https://github.com/onestardao/WFGY/blob/main/core/README.md)

---

## Replace files then restart

Upload or copy the seven files to the repo root. Set the router executable bit.

```bash
chmod +x wfgy_router.sh
# restart litellm if you changed its config
pkill -9 -f 'litellm|uvicorn' || true
litellm --host 0.0.0.0 --port 8080 --config /etc/litellm.yaml --debug --num_workers 1 &
```

---

## Downloads

All links point to the repo root.

| File                        | Link                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `wfgy_router.sh`            | [./wfgy_router.sh](./wfgy_router.sh)                       |
| `wfgy_router_min.py`        | [./wfgy_router_min.py](./wfgy_router_min.py)               |
| `wfgy_semantic_firewall.py` | [./wfgy_semantic_firewall.py](./wfgy_semantic_firewall.py) |
| `wfgy_dt_guard.py`          | [./wfgy_dt_guard.py](./wfgy_dt_guard.py)                   |
| `wfgy_retry.py`             | [./wfgy_retry.py](./wfgy_retry.py)                         |
| `wfgy_env.sh`               | [./wfgy_env.sh](./wfgy_env.sh)                             |
| `wfgy_playbooks.yaml`       | [./wfgy_playbooks.yaml](./wfgy_playbooks.yaml)             |

---

## File integrity

Six files below match the signed build. `wfgy_router_min.py` depends on your final commit; fill it after computing.

| File                        | Size (bytes) | SHA256                                                           | MD5                              |
| --------------------------- | -----------: | ---------------------------------------------------------------- | -------------------------------- |
| `wfgy_dt_guard.py`          |         1005 | cb50ac57c6202f2de343e28b2e14e30905f0bd06b4ba498c2d22da73553a6d84 | f790fa578016afd2aed1d480abb85abe |
| `wfgy_env.sh`               |         1077 | f417caea2171fe3c12e818c869fd313445683b38adeaa8a9e8e766b18dcfc133 | 3aefca92012d4c5d64c7f9df8d98a29e |
| `wfgy_playbooks.yaml`       |          835 | 28344dabe1a33e8eba918c3450744994758d7bae51fd29d8bffd3659256ca434 | f0df0b459f039026fa90481be55bef4e |
| `wfgy_retry.py`             |         2947 | eb41596e18d15b4bf4ac996803b792099d3d0a6391a39e00ef70a2ec68442820 | 3324311daed32f9fdfac13f9c2db14c6 |
| `wfgy_router.sh`            |          398 | c9433299dd8151a41831999f64a446066b97ead992292ac43b1602d095773adf | 8552e4feb1e52cfc2518c63f41fa1e3a |
| `wfgy_semantic_firewall.py` |         1455 | 1a9d545c75c808d59dab5fc26f3860fe8c2aeedf4d65ff87eea41cd30e31d523 | 312f494d3f4ee5275a862421bd07f0d3 |
| `wfgy_router_min.py`        |      **TBD** | **TBD**                                                          | **TBD**                          |

### Compute and verify

```bash
python - << 'PY'
import hashlib, os
files = [
  "wfgy_router.sh",
  "wfgy_router_min.py",
  "wfgy_semantic_firewall.py",
  "wfgy_dt_guard.py",
  "wfgy_retry.py",
  "wfgy_env.sh",
  "wfgy_playbooks.yaml",
]
def h(p, algo):
    m = hashlib.new(algo)
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""): m.update(ch)
    return m.hexdigest()
print("| File | Size (bytes) | SHA256 | MD5 |")
print("| --- | ---: | --- | --- |")
for f in files:
    size = os.path.getsize(f)
    print(f"| `{f}` | {size} | {h(f,'sha256')} | {h(f,'md5')} |")
with open("CHECKSUMS.sha256","w") as w:
    for f in files: w.write(f"{h(f,'sha256')}  {f}\n")
PY

sha256sum -c CHECKSUMS.sha256
```

---

## References

* Terminal-Bench overview: [https://crfm.stanford.edu/terminal-bench/](https://crfm.stanford.edu/terminal-bench/)
* WFGY Core 2.0: [https://github.com/onestardao/WFGY/blob/main/core/README.md](https://github.com/onestardao/WFGY/blob/main/core/README.md)


