# agentwell Testing Log

## Environment

| Component | Detail |
|---|---|
| EC2 Instance | t3.large, 2vCPU, 8GB RAM |
| OS | Ubuntu 26.04 LTS |
| Region | ap-south-1 (Mumbai) |
| Python | 3.12.3 |
| agentwell | v0.1.1 |
| LLM Provider | Groq (free tier) |
| Upstream URL | `https://api.groq.com/openai` |

---

## EC2 Setup — What We Did

### 1. Launch Instance
- Ubuntu 26.04 LTS, t3.large, 20GB gp3, Mumbai
- Security group: port 22 + 3001 + 8501 → your IP only, outbound 443 open to Groq

### 2. SSH In
```bash
ssh -i your-key.pem ubuntu@<ec2-ip>
```

### 3. Install Dependencies
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone https://github.com/flowmindlabs/agentwell.git
cd agentwell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cat > .env << EOF
AGENTWELL_UPSTREAM=https://api.groq.com/openai
AGENTWELL_PORT=3001
AGENTWELL_HEALTH_THRESHOLD=70
AGENTWELL_WINDOW_SIZE=20
AGENTWELL_DB_PATH=/home/ubuntu/agentwell/agentwell.db
AGENTWELL_STORE_EMBEDDINGS=false
AGENTWELL_API_KEY=
GROQ_API_KEY=your-groq-key-here
EOF
```

### 5. Start Proxy
```bash
source .venv/bin/activate
python -m agentwell.proxy.server
```

### 6. Issues Encountered and Fixed

| Issue | Root Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'httpx'` | Venv not activated | `source .venv/bin/activate` |
| `venv/bin/activate: No such file or directory` | Venv named `.venv` not `venv` | `source .venv/bin/activate` |
| `[Errno 98] address already in use` | Old process still on port 3001 | `kill $(lsof -t -i:3001)` |
| `TypeError: %d format` on startup | httpx INFO logs use `%d` for status code, Python 3.12 strict | Suppress httpx/httpcore to WARNING in server.py |
| `{"detail":"Unauthorized."}` | `AGENTWELL_API_KEY` was set, blocking curl | Left empty for local testing |
| `{"detail":"Invalid JSON."}` | Bash single-quote quoting issue in curl `-d` | Use `curl -d @/tmp/test.json` file approach |
| Groq `/health` returns 404 | Groq has no `/health` endpoint | Expected — adapter correctly falls back to `openai_compat` |

---

## Test 1 — Health Endpoint

**Date:** 2026-05-24  
**Command:**
```bash
curl http://localhost:3001/health
```

**Response:**
```json
{
  "status": "ok",
  "upstream": "https://api.groq.com/openai",
  "upstream_healthy": false,
  "adapter": "openai_compat",
  "session_id": "149f6e30-11a1-4b9c-9e49-0385d5836e1f"
}
```

**Result:** PASS  
`upstream_healthy: false` is correct — Groq has no `/health` endpoint. Adapter detection working.

---

## Test 2 — First LLM Call Through Proxy

**Date:** 2026-05-24  
**Model:** `llama-3.1-8b-instant` (Groq free tier)  
**Command:**
```bash
cat > /tmp/test.json << 'EOF'
{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"Summarize in one sentence: The sky is blue because of Rayleigh scattering of sunlight."}]}
EOF

curl -s -D - http://localhost:3001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d @/tmp/test.json
```

**Response headers:**
```
x-agentwell-health: 76
x-agentwell-flags: none
x-agentwell-privacy: metadata-only
```

**Response body (trimmed):**
```json
{
  "model": "llama-3.1-8b-instant",
  "choices": [{
    "message": {
      "content": "The blue color of the sky is primarily due to the scattering of sunlight by the tiny molecules of gases in the Earth's atmosphere, a phenomenon known as Rayleigh scattering."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 55,
    "completion_tokens": 35,
    "total_tokens": 90
  }
}
```

**Result:** PASS

| Signal | Value | Interpretation |
|---|---|---|
| `x-agentwell-health` | 76 | Healthy (threshold: 70) |
| `x-agentwell-flags` | none | No drift, no coordination signals |
| `x-agentwell-privacy` | metadata-only | Privacy guarantee active |
| `finish_reason` | stop | Clean completion |
| Groq API key | Injected from `.env` automatically | No key in curl command |

---

## What Verified

- [x] Proxy starts clean, no errors
- [x] Groq API key injected from `.env` — no key needed in curl
- [x] Health endpoint responds correctly
- [x] Adapter auto-detection works (openai_compat for Groq)
- [x] LLM call proxied successfully to Groq
- [x] `X-Agentwell-Health` header on every response
- [x] `X-Agentwell-Privacy: metadata-only` enforced
- [x] Drift + quality + coordination monitor pipeline running
- [x] No prompt/response content stored (DB schema enforces this)
- [x] Log redactor active (secrets stripped from all logs)

---

## Next: Agent Simulation

4-agent behavioral health simulation — `examples/simulation.py`

| Agent | Model | Tasks/day | What we watch |
|---|---|---|---|
| A Summarizer | `llama-3.1-8b-instant` | 100 | Summary quality shortening, tone shift |
| B Analyst | `llama-3.1-8b-instant` | 100 | Scoring drift, hedging increase |
| C Coordinator | `llama-3.3-70b-versatile` | 200 | repetition_ratio explosion, coordination signals |
| D Coding | `meta-llama/llama-4-scout-17b-16e-instruct` | 150 | Docstring quality drop, false positive/negative drift |

Expected: Agent C health_score < 40 by Day 3, task 100+.

See full task lists in `memory/project-agentwell-testing.md`.
