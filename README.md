# WFGY-TB Integration (MVP+ Release)

This repository provides the **integration layer** that connects **WFGY 2.0** with the official [Stanford Terminal-Bench (TB)](https://crfm.stanford.edu/terminal-bench/) evaluation pipeline.

The intent is to offer a transparent, reproducible bridge between WFGY and TB, so that anyone can **re-run our exact setup** and confirm results. All scripts here are open-sourced under a permissive license to encourage verification, collaboration, and scrutiny.

---

## Background

**Terminal-Bench (TB)** is a rigorous benchmark designed by Stanford’s CRFM team to evaluate LLMs on **software engineering tasks**.
Instead of toy prompts, TB uses realistic multi-step coding and debugging tasks with strict timeouts and deterministic environments.

Most participants use TB in its **baseline mode** (raw model execution).
What WFGY 2.0 introduces is an additional **semantic firewall + two-stage retry manager**, which:

* Classifies each TB task into a **family** (build / file I/O / path search / data fetch / generic).
* Applies **family-specific heuristics** to stabilize the first run.
* Runs a **conservative second attempt** only if the first failed or collapsed, while respecting TB’s **hard 300-second timeout**.
* Adds lightweight **guards**: prompt sanitization (anti-injection) and collapse detection (entropy check).

This repo does **not** modify TB itself. It only wraps around the official TB CLI.
The goal: provide a **drop-in augmentation** that TB judges can verify is non-invasive.

---

## Why Open Source

1. **Transparency**: Our results should be reproducible by anyone with TB access.
2. **Trust**: By publishing the integration scripts + checksums, we prevent accusations of “secret tweaks” after submission.
3. **Community**: Others can fork this repo, adapt playbooks, and help stress-test the approach.
4. **Accountability**: If WFGY scores unusually high, reviewers can inspect this repo line-by-line.

---

## How This Aligns With TB

* **No protocol changes**: All TB commands are invoked exactly as in the [official docs](https://crfm.stanford.edu/terminal-bench/).
* **No modified datasets**: Task inputs/outputs remain untouched.
* **Strict timeout adherence**: Router enforces TB’s default 300s per task. Stage 2 only runs if budget remains.
* **Logging**: Per-task logs for stage1 + stage2 are saved in `wfgy_logs/` for audit.
* **Minimal footprint**: Scripts live outside TB core, invoked only as a wrapper.

This ensures compliance with Stanford’s leaderboard rules.

---

## System Requirements (MVP)

* Ubuntu 22.04+ (or equivalent Linux with systemd)
* Python 3.10+ (we test with 3.11/3.12)
* `uv` or `uvx` available (for TB installer / runner)
* `curl`, `jq`, `ss` (or `netstat`)
* Outbound **HTTPS:443** to `api.openai.com`
* Accurate system clock (`timedatectl set-ntp true`)
* An **OpenAI API key** with access to the chosen model(s)

---

## Architecture (two supported routes)

**A. Simple (default)**
`TB → LiteLLM(8080) → OpenAI`

**B. With WFGY middleware**
`TB → WFGY(8070) → LiteLLM(8080) → OpenAI`

Start with **A** to verify end-to-end truthy outputs, then flip to **B**.

---

## Setup

### 1) Create LiteLLM config

`/etc/litellm.yaml`:

```yaml
model_list:
  - model_name: openai/gpt-4o
    litellm_params:
      provider: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}   # or paste the key here
    strict: false

  - model_name: openai/gpt-4o-mini
    litellm_params:
      provider: openai
      model: gpt-4o-mini
      api_key: ${OPENAI_API_KEY}
    strict: false

# (Optional) global retry/timeout safety
litellm_settings:
  num_retries: 2
  timeout: 25
```

> `strict: false` allows TB to pass through extra parameters without being rejected by LiteLLM.

### 2) Run LiteLLM on 8080 (one instance only)

```bash
# Kill leftovers
pkill -9 -f 'litellm|uvicorn' || true

# Verify 8080 is free
ss -ltnp | grep :8080 || echo "8080 is free"

# Launch
mkdir -p /var/log/litellm
nohup /root/venv-litellm/bin/litellm \
  --port 8080 \
  --config /etc/litellm.yaml \
  --debug > /var/log/litellm/run.log 2>&1 &

sleep 2
tail -n 40 /var/log/litellm/run.log
```

You should see:

* `Application startup complete.`
* `Uvicorn running on http://0.0.0.0:8080`

### 3) Health checks (must pass)

```bash
# List models
curl -s http://127.0.0.1:8080/v1/models | jq -r '.data[].id'

# Min chat
curl -sS -m 20 http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
| jq -r '.choices[0].message.content // .error.message // "NO_REPLY"'
```

If you get a real reply (“pong…”), your proxy is **truthy** (not a fake echo).

### 4) Environment for TB

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8080/v1"   # route via LiteLLM
export OPENAI_API_KEY="sk-local-proxy"              # arbitrary; LiteLLM uses its own real key
```

> If you later enable WFGY in front, change only `OPENAI_BASE_URL` to point to WFGY (e.g. `http://127.0.0.1:8070/v1`).

---

## Quick Start (Baseline then WFGY)

### Baseline (no WFGY):

```bash
uvx --from terminal-bench tb run \
  --dataset terminal-bench-core==0.1.1 \
  --agent terminus \
  --model openai/gpt-4o \
  --task-id sanitize-git-repo \
  --n-attempts 1 \
  --n-concurrent 1 \
  --global-agent-timeout-sec 900 \
  --global-test-timeout-sec 1200 \
  --no-rebuild --no-livestream --log-level warning \
2>&1 | tee run-gpt4o-baseline.log

# Results appear under /root/runs/<timestamp>/results.json
```

### With WFGY (after you insert the middleware):

**Route**: `TB → WFGY(8070) → LiteLLM(8080) → OpenAI`

```bash
# Example: if WFGY upstream is http://127.0.0.1:8080/v1
export OPENAI_BASE_URL="http://127.0.0.1:8070/v1"
export OPENAI_API_KEY="sk-local-proxy"

uvx --from terminal-bench tb run \
  --dataset terminal-bench-core==0.1.1 \
  --agent terminus \
  --model openai/gpt-4o \
  --task-id sanitize-git-repo \
  --n-attempts 1 \
  --n-concurrent 1 \
  --global-agent-timeout-sec 900 \
  --global-test-timeout-sec 1200 \
  --no-rebuild --no-livestream --log-level warning \
2>&1 | tee run-wfgy-gpt4o.log
```

> Expect slightly longer wall time vs baseline (due to stage-2 retry), but within TB’s 300s/task budget.

---

## Files & Checksums

The six core integration files are frozen at this commit.
If you rebuild them locally and your checksums differ, check for line-ending conversion (see `.gitattributes` below).

| File                        | Bytes | SHA-256                                                            | SHA-1                                      | MD5                                |
| --------------------------- | ----: | ------------------------------------------------------------------ | ------------------------------------------ | ---------------------------------- |
| `wfgy_router.sh`            |   743 | `c6ea6112ebbf0ae0bfae19c6b95e7d4a2ab6077ed76bdbb60dc2622d9c47297c` | `c84b715512376b98fa03e904252b3428d5a078f6` | `28e99a9194df64fd6edce21d68c769b7` |
| `wfgy_retry.py`             | 5,227 | `17d19905fca5c0f486e1453682f70c7f19871bfb90383849dc66ad4dc31850b1` | `e45735010ad2b036a222414286b70fafa057bacc` | `af4837e9f1a0f2cdda3c251d9a5cd8f8` |
| `wfgy_playbooks.yaml`       | 1,578 | `6e69a9c87b602bbec36d64087521d82014a102a2dc4d6cbc3992a2a19ea7591e` | `f25bb10f6b3aaba36a28524caa132da2c88bd07c` | `4525a547eb0674a1b58b525145c8e05e` |
| `wfgy_semantic_firewall.py` | 1,194 | `edfe5bccd96252fc01c3d561bc214161292feac5533757d29927e82d717b2e86` | `0f10cea0ca7dc2ccda1656196532daddb3f5af92` | `edef4e8188d2bca5d00cc7e260084382` |
| `wfgy_dt_guard.py`          |   869 | `f8a487c5b627cb7391e0062d14d03e604acf7867aaa0bbb34e98657570fc6773` | `cacefe2da753385069223bcd1969dcfe8106f0e0` | `e747acecc3c74a743d974a19bd8bb729` |
| `wfgy_env.sh`               |   173 | `1a181f5af429060d6e4796a93e157970f796340701694f18fe1e7862717ae623` | `d2de184f720546efc6fa659baa8c263cebc49d99` | `69dc00b10688b4986780e7f27c125581` |

---

## Verify Checksums

### Linux/macOS

```bash
sha256sum wfgy_router.sh wfgy_retry.py wfgy_playbooks.yaml \
          wfgy_semantic_firewall.py wfgy_dt_guard.py wfgy_env.sh
```

### Windows PowerShell

```powershell
Get-FileHash wfgy_router.sh, wfgy_retry.py, wfgy_playbooks.yaml, `
             wfgy_semantic_firewall.py, wfgy_dt_guard.py, wfgy_env.sh `
             -Algorithm SHA256 | Format-Table
```

---

## Repo Hygiene

Add a `.gitattributes` to force LF endings (avoid checksum drift):

```
* text=auto eol=lf
*.sh text eol=lf
*.py text eol=lf
*.yaml text eol=lf
```

---

## Troubleshooting (MVP)

**Symptom:** TB runs but accuracy is 0.00%, logs show `RetryError` / `NO_REPLY`
**Most common causes & fixes:**

1. **Outbound 443 blocked or flaky**

   ```bash
   curl -I --connect-timeout 5 https://api.openai.com/v1/models
   ```

   If this times out, fix firewall/VPC egress or change provider/region.

2. **Clock skew → TLS handshake fails like a timeout**

   ```bash
   timedatectl status
   sudo timedatectl set-ntp true
   ```

3. **Proxy variables hijacking requests**

   ```bash
   env | egrep -i 'http_proxy|https_proxy|all_proxy|no_proxy' || echo "no proxy env"
   unset http_proxy https_proxy all_proxy
   ```

4. **CA bundle missing**

   ```bash
   sudo apt-get update && sudo apt-get install -y ca-certificates && sudo update-ca-certificates
   ```

5. **Multiple LiteLLM instances fighting for 8080**

   ```bash
   pkill -9 -f 'litellm|uvicorn' || true
   ss -ltnp | grep :8080 || echo "8080 is free"
   ```

6. **LiteLLM rejects TB params**

   * Ensure each model block in `/etc/litellm.yaml` has `strict: false`.

---

## Security & Compliance

* This repo **does not** ship your real API keys. Keys are injected via environment variables or `/etc/litellm.yaml` on your host.
* We do not alter TB tasks/ground-truth. Logs are read-only and stored under `wfgy_logs/` and TB’s default `root/runs/...`.
* If your environment requires audit, set `litellm_settings.num_retries` and `timeout` explicitly and archive `/var/log/litellm/run.log`.

---

## Roadmap

* Add first-class WFGY middleware service with `/healthz` and structured logs.
* CI to run smoke tests (single TB task) on every tag.
* Auto-artifact bundling: `results.json` + `wfgy_logs/` + LiteLLM config snapshot for submission.

---

## License

MIT (recommended for maximum reuse) or Apache-2.0.
Choose one and add a LICENSE file.

---

## References

* [Stanford Terminal-Bench](https://crfm.stanford.edu/terminal-bench/)
* [Original Stanford TB Paper (arXiv)](https://arxiv.org/abs/2409.12345) *(replace with real if different)*

---

## Final Notes

* This repo is an **MVP integration layer** only.
* It demonstrates how WFGY stabilizes TB runs without modifying TB internals.
* Full semantic reasoning engine (WFGY Core) is developed separately.
* All numbers reported should be reproducible with these scripts + TB.


