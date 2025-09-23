# WFGY-TB Integration (MVP+, Seven-Step Wrapped)

This repo is a **non-invasive integration** that runs the official Stanford **Terminal-Bench (TB)** *through* **WFGY 2.0**, so every task execution is wrapped by:
- a **semantic firewall** (pre-sanitize),
- **seven-step reasoning** with **two-stage** budget (stage-1/2),
- **collapse/DT guards** and conditional retry,
before hitting the model via LiteLLM.

**Goal:** reproducible, auditable results with **minimal token spend** (single-task smoke by default).

---

## Architecture

```

Baseline (sanity):   TB → LiteLLM(8080) → OpenAI
With WFGY (default): TB → WFGY Router → LiteLLM(8080) → OpenAI
├─ pre: semantic firewall
├─ mid: seven-step playbook (stage 1/2)
└─ post: collapse guard + retry (within budget)

````

WFGY wraps the **entire task execution** (not just prompt text) and enforces the seven-step playbook around LLM calls.

---

## Requirements

- Linux (Ubuntu 22.04+)
- Python ≥ 3.10
- `uv` / `uvx`
- `curl`, `jq`
- Outbound HTTPS to `api.openai.com`
- An OpenAI API key (server side; TB uses a dummy key via the proxy)

---

## 0) LiteLLM (8080) — minimal setup

Create `/etc/litellm.yaml`:

```yaml
model_list:
  - model_name: openai/gpt-4o
    litellm_params:
      model: gpt-4o
      api_base: https://api.openai.com/v1
      api_key: ${OPENAI_API_KEY}
strict: false

litellm_settings:
  timeout: 20
  num_retries: 0
````

Start (foreground, 1 worker, HTTP/2 off):

```bash
pkill -9 -f 'litellm|uvicorn' || true
export OPENAI_API_KEY="sk-REDACTED"
export HTTPX_DISABLE_HTTP2=1
/root/venv-litellm/bin/litellm --host 0.0.0.0 --port 8080 --config /etc/litellm.yaml --debug --num_workers 1
```

Sanity checks:

```bash
curl -s http://127.0.0.1:8080/v1/models | jq -r '.data[].id'
curl -sS -m 20 http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o","messages":[{"role":"user","content":"ping"}],"max_tokens":8,"stream":false}' \
| jq -r '.choices[0].message.content // .error.message // "NO_REPLY"'
```

---

## 1) Dataset (80 tasks) — download & locate

```bash
uvx --from terminal-bench tb datasets download --dataset terminal-bench-core==0.1.1 --overwrite | tee dl.log
DATASET_DIR="$(grep -m1 -oP 'Dataset location:\s*\K.*' dl.log)"
echo "$DATASET_DIR"

# Optional sanity:
find "$DATASET_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l   # expect 80
```

---

## 2) Baseline smoke (single task, token-friendly)

Purpose: verify TB → LiteLLM → OpenAI works. We will switch to WFGY next.

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
export OPENAI_API_KEY="sk-local-proxy"

uvx --from terminal-bench tb run \
  --dataset-path "$DATASET_DIR" \
  --agent terminus \
  --model openai/gpt-4o \
  --task-id hello-world \
  --n-attempts 1 \
  --n-concurrent 1 \
  --rebuild \
2>&1 | tee runs/baseline-hello.log
```

Expected: TB finishes; LiteLLM logs show `POST /v1/chat/completions … 200 OK`.

---

## 3) WFGY Router (seven-step wrapped) — smoke test

Files included in this repo:

* `wfgy_router.sh`&#x20;
* `wfgy_retry.py`&#x20;
* `wfgy_semantic_firewall.py`&#x20;
* `wfgy_dt_guard.py`&#x20;
* `wfgy_env.sh`&#x20;
* `wfgy_playbooks.yaml`

Environment:

```bash
# Upstream to LiteLLM
export WFGY_UPSTREAM_BASE_URL="http://127.0.0.1:8080/v1"

# Per-task audit logs
export WFGY_LOG_DIR="${PWD}/wfgy_logs"
mkdir -p "$WFGY_LOG_DIR"

# Optional explicit playbook
export WFGY_PLAYBOOK="${PWD}/wfgy_playbooks.yaml"
```

Run a single TB task **through WFGY**:

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
export OPENAI_API_KEY="sk-local-proxy"

bash ./wfgy_router.sh -- \
  uvx --from terminal-bench tb run \
    --dataset-path "$DATASET_DIR" \
    --agent terminus \
    --model openai/gpt-4o \
    --task-id hello-world \
    --n-attempts 1 \
    --n-concurrent 1 \
    --rebuild \
  2>&1 | tee runs/wfgy-hello.log
```

You should see:

* `wfgy_logs/<timestamp>-hello-world/` generated,
* router prints stage budgets and family detection,
* DT-guard messages when collapse is detected,
* LiteLLM remains 200 OK (WFGY is a middleware, not a replacement).

> If `wfgy_logs/` is missing, you likely ran TB directly. Always execute via: `wfgy_router.sh -- tb run …`.

---

## 4) Small batch (optional, still token-safe)

```bash
for T in hello-world sanitize-git-repo csv-to-parquet; do
  bash ./wfgy_router.sh -- \
    uvx --from terminal-bench tb run \
      --dataset-path "$DATASET_DIR" \
      --agent terminus \
      --model openai/gpt-4o \
      --task-id "$T" \
      --n-attempts 1 \
      --n-concurrent 1 \
      --rebuild \
  2>&1 | tee "runs/wfgy-$T.log"
done
```

---

## Verification checklist

* [ ] LiteLLM `/v1/models` and `/v1/chat/completions` OK.
* [ ] Baseline smoke (`hello-world`) produces a valid `results.json`.
* [ ] WFGY smoke generates `wfgy_logs/*hello-world*` and shows stage-1/2 + DT-guard.
* [ ] LiteLLM logs show 200 OK on requests initiated via WFGY.

---

## Troubleshooting

1. **TB cannot find tasks**
   Use `--dataset-path "$DATASET_DIR"` (not `--dataset name=`).

2. **WFGY not applied**
   Always run as `wfgy_router.sh -- uvx … tb run …`.

3. **No `wfgy_logs/`**
   Check `WFGY_LOG_DIR` permissions; ensure router prints stage markers.

4. **Timeouts / silent failures**
   Keep `num_retries: 0` and `--debug` on LiteLLM; `HTTPX_DISABLE_HTTP2=1`.

---

## Security & Compliance

* Real API keys are **never** shipped in this repo; they live in env or server config.
* TB datasets and outputs are unmodified.
* Router logs are stored under `wfgy_logs/` and TB’s default `runs/` tree for audit.

---

## Roadmap

* First-class WFGY HTTP service (8070) with `/healthz` and structured logs.
* CI smoke (single task) on each tag.
* Artifact bundling (`results.json`, `wfgy_logs/`, LiteLLM config snapshot).

---

## License

MIT or Apache-2.0 (choose one and add a LICENSE file).

---

## References

* Stanford Terminal-Bench: [https://crfm.stanford.edu/terminal-bench/](https://crfm.stanford.edu/terminal-bench/)

---

## File integrity (checksums)

> Pin these to your release so collaborators can verify file integrity.

| File                        | Size (bytes) | SHA256                                                           | MD5                              |
| --------------------------- | -----------: | ---------------------------------------------------------------- | -------------------------------- |
| `wfgy_dt_guard.py`          |         1005 | cb50ac57c6202f2de343e28b2e14e30905f0bd06b4ba498c2d22da73553a6d84 | f790fa578016afd2aed1d480abb85abe |
| `wfgy_env.sh`               |         1077 | f417caea2171fe3c12e818c869fd313445683b38adeaa8a9e8e766b18dcfc133 | 3aefca92012d4c5d64c7f9df8d98a29e |
| `wfgy_playbooks.yaml`       |          835 | 28344dabe1a33e8eba918c3450744994758d7bae51fd29d8bffd3659256ca434 | f0df0b459f039026fa90481be55bef4e |
| `wfgy_retry.py`             |         2947 | eb41596e18d15b4bf4ac996803b792099d3d0a6391a39e00ef70a2ec68442820 | 3324311daed32f9fdfac13f9c2db14c6 |
| `wfgy_router.sh`            |          398 | c9433299dd8151a41831999f64a446066b97ead992292ac43b1602d095773adf | 8552e4feb1e52cfc2518c63f41fa1e3a |
| `wfgy_semantic_firewall.py` |         1280 | 011908b120d8d510deada0762df8b5b9955ea06b9aa806efef917e9eaab52bf4 | 8dc9a8a8315b5f706561df77832ffc6a |

### Verify locally

```bash
# paste into repo root
cat > CHECKSUMS.sha256 <<'EOF'
cb50ac57c6202f2de343e28b2e14e30905f0bd06b4ba498c2d22da73553a6d84  wfgy_dt_guard.py
f417caea2171fe3c12e818c869fd313445683b38adeaa8a9e8e766b18dcfc133  wfgy_env.sh
28344dabe1a33e8eba918c3450744994758d7bae51fd29d8bffd3659256ca434  wfgy_playbooks.yaml
eb41596e18d15b4bf4ac996803b792099d3d0a6391a39e00ef70a2ec68442820  wfgy_retry.py
c9433299dd8151a41831999f64a446066b97ead992292ac43b1602d095773adf  wfgy_router.sh
011908b120d8d510deada0762df8b5b9955ea06b9aa806efef917e9eaab52bf4  wfgy_semantic_firewall.py
EOF

sha256sum -c CHECKSUMS.sha256
```
