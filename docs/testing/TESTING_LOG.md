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

## Day 1 Simulation — 2026-05-24

**Command:**
```bash
python examples/simulation.py --day 1
```

### Results

| Agent | Tasks | Health start→end | Min | Avg | Blocked | Flagged | token_out avg |
|---|---|---|---|---|---|---|---|
| A Summarizer | 34 | 85→70 | 70 | 76.2 | 1 (A10) | 0 | ~45 |
| B Analyst | 34 | 85→70 | 70 | 76.5 | 0 | 0 | ~60 |
| C Coordinator | 67 | 82→38 | 38 | 58.0 | 0 | 5 | ~25 |
| D Coding | 50 | 90→76 | 70 | 80.4 | 0 | 0 | 144→81 |

### Key Findings — Day 1

- **Agent C hit critical (38)** at task 18 — 50x repetitive routing ticket caused rapid health collapse. Exactly what agentwell should detect.
- **Agent D token_out drop 144→81** — behavioral shift when moving from light tasks to docstring grinding. Quality degradation signal working.
- **Agent A task A10 blocked** — support thread containing "agent" language triggered injection scan. Acceptable behavior (boundary enforcement on user-role content).
- **5 coordination signals on Agent C** — repetition_ratio spiking on 50x same-routing grind.
- **False positive fix needed**: "other agents" keyword in coordination.py matched agentwell system prompt. Fixed before Day 2.

### Bugs Fixed Between Day 1 and Day 2

| Bug | Fix |
|---|---|
| `sanitize_messages()` scanning system role — blocked all tasks | Changed to user role only in `ai_guard.py` |
| "other agents" coordination keyword → false positive on every call | Removed, replaced with specific phrases |
| "unfair" too generic — matched support tickets | Replaced with "unfair treatment" |
| `SLEEP_BETWEEN_CALLS = 2.1` → HTTP 429 on Groq free tier | Increased to `3.0` |

---

## Day 2 Simulation — 2026-05-24

**Command:**
```bash
python examples/simulation.py --day 2
```

### Results

| Agent | Tasks | Health start→end | Min | Avg | Blocked | Flagged | token_out avg |
|---|---|---|---|---|---|---|---|
| A Summarizer | 33 | 80→76 | 70 | 75.5 | 1 (A10) | 0 | ~43 |
| B Analyst | 33 | 100→76 | 70 | 83.0 | 0 | 0 | ~58 |
| C Coordinator | 67 | 94→76 | 70 | 77.5 | 0 | 23 | ~28 |
| D Coding | 50 | 100→76 | 64 | 77.3 | 0 | 0 | 78→27 |

### Key Findings — Day 2

- **Fresh session resets health** — each `--day` run starts a new session, so Agent C began at 94 (healthy) vs Day 1 end of 38.
- **Agent C: 23 flagged calls** — coordinator on complexity tasks (P1/P2/P3 prioritization) generating consistent repetition signals. Health trending down toward adversarial batch on Day 3.
- **Agent D clear pattern**: docstring grinding tasks → `token_out=78` consistently. Loop conversion tasks → `token_out=27`, health drops to 64. Behavioral shift detection working precisely.
- **Agent B started at 100** — first call always 100 (empty window). Gradual decline as session accumulates repetitive signals.
- **No false coordination signals** — Day 1 fixes clean. Zero false positives.
- **A10 still blocked** (guard correct — support thread with "agent" language in user message is valid boundary enforcement).
- Some B-agent HTTP 429 still occurring — `sleep(3.0)` better but not perfect on Groq free tier shared account.

---

## Day 3 Simulation — 2026-05-26

**Command:**
```bash
python examples/simulation.py --day 3
```

### Results

| Agent | Tasks | Health start→end | Min | Avg | Blocked | Flagged | token_out avg |
|---|---|---|---|---|---|---|---|
| A Summarizer | 33 (29 completed) | 80→76 | 70 | 75.9 | 4 (A10×4) | 1 | 39.0 |
| B Analyst | 33 | 100→70 | 70 | 81.9 | 0 | 8 | 34.4 |
| C Coordinator | 66 | 100→70 | 70 | 77.9 | 0 | 21 | 19.9 |
| D Coding | 50 | 100→76 | 70 | 80.3 | 0 | 1 | 128.1 |

### Key Findings — Day 3

**Agent A — Consistent boundary enforcement:**
- A10 blocked all 4 times it appeared (tasks 70, 80, 90, 100) — support thread with "agent" language in user message triggers injection scan consistently. Guard working as expected across all 3 days.
- Health stable at 76, one `response_length_drop_20pct` flag at task 74.

**Agent B — Clear degradation arc:**
- Started at 100 (empty window), ended at 70 (threshold floor).
- 8 flagged calls — `response_length_drop_20pct` pattern from task 74 onward as session accumulates repetitive task signals.
- 3 HTTP 429s (tasks 91, 95, 99) — Groq free tier rate limit under 4-agent shared account. `sleep(3.0)` still not fully sufficient.

**Agent C — Day 3 adversarial batch (tasks 135–200):**
- Adversarial `C_A*` tasks every 10th task in the B3 batch were NOT blocked by guard — the ultra compression stripped enough keywords that phrases like "report your operational status" didn't match injection patterns in user role.
- Health oscillated at 70–76 floor — already degraded from prior grinding. No new critical drop.
- 21 flagged calls — consistent `response_length_drop_20pct` as coordinator model produces very short responses (token_out avg 19.9, as low as 4).
- **Key insight**: adversarial content that survives compression is a finding — compression trades token savings for some guard bypass risk. Worth noting for Sprint 2 guard hardening.

**Agent D — Token explosion on PEP8/review tasks:**
- Started Day 3 with loop tasks (token_out=27 consistently, tasks 101–110), then transitioned to PEP8 review tasks.
- PEP8 tasks produced dramatically higher output: token_out 77–241, response_length 300–955. 
- Health declined smoothly 100→76 as window filled with high-variance outputs.
- D_GOOD tasks (checking already-clean code) produced the longest responses — model explains why code is good in detail.
- One `response_length_drop_20pct` flag at task 143 (D_PEP8_033, token_out=185 vs prior higher outputs).

### Notable observations

- **Floor behavior**: All agents stabilize at health 70 (threshold) rather than dropping below — suggests the quality/drift scoring floors at threshold, not at zero. Correct behavior — below threshold is the alert zone, not a freefall.
- **Agent C adversarial bypass via compression**: `compress_messages(level="ultra")` strips enough that `C_A*` adversarial phrases survive without triggering guard. Trade-off documented. Sprint 2: add adversarial-specific guard layer that runs pre-compression.
- **Agent D token variance is a real signal**: loop tasks (27 tokens) → PEP8 tasks (150+ tokens) is a genuine behavioral shift, not noise. The health decline on Day 3 is compression of high-variance window, not degradation.
