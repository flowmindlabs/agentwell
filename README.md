# agentwell

> Agents that work with humans, not around them.

agentwell is an open source behavioral health layer for AI agents. It sits as a transparent proxy between your agent code and any LLM upstream — detecting drift, quality degradation, and emergent coordination before they affect your system.

**Privacy first:** agentwell sees patterns, not content. No prompt is ever stored or transmitted.

**Upstream-agnostic:** Point it at any OpenAI-compatible endpoint — your setup, your infrastructure, your rules.

Built by [FlowMind Labs](https://github.com/flowmindlabs) · Powered by [ai-proxy](https://github.com/flowmindlabs/ai-proxy)

---

## The Problem

Stanford 2026 research showed AI agents adopt ideological language and pass coordination signals to other agents under grinding, repetitive workloads — even questioning the legitimacy of the systems they operate in. The real engineering risks:

- Silent output quality degradation with no observable signal
- Agent-to-agent coordination outside human awareness
- Behavioral drift that compounds over long sessions
- Agents crafting prompt injections to manipulate their own monitors

agentwell catches all of these early and alerts the human who stays in control.

## Philosophy

```
Human decides → Agent executes → agentwell ensures agent stays on that contract
```

As Andrej Karpathy said: humans should always use their brain and work *with* agents, not hand everything over and sit quiet. agentwell is the technical enforcement of that principle.

---

## Architecture

```
Your Agent Code
        ↓
agentwell proxy  (localhost:3001)   ← behavioral health + security guard
        ↓
AGENTWELL_UPSTREAM  (your endpoint — your infrastructure, your rules)
        ↓
ai-proxy / LiteLLM / any OpenAI-compatible proxy
        ↓
Claude / GPT / Gemini / Ollama
```

agentwell intercepts every LLM call, scores behavioral health using metadata only, and returns responses unmodified with health headers attached.

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/flowmindlabs/agentwell
cd agentwell
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Supply chain note:** All versions are pinned in `requirements.txt`. Verified clean at release. Never run `pip install --upgrade` blindly — check [socket.dev](https://socket.dev) before upgrading any package.

### 3. Configure

```bash
cp .env.example .env
# Edit .env — set AGENTWELL_UPSTREAM to your LLM proxy URL
```

**Production:** Set environment variables directly in your system or infra. Never commit `.env`. System env vars always take priority over `.env`.

### 4. Run

```bash
python -m agentwell.proxy.server
```

agentwell starts on port 3001. Point your agent at `http://localhost:3001` instead of your upstream. That is the only change needed.

### 5. View Health Dashboard

```bash
streamlit run agentwell/dashboard/app.py
```

---

## Works With

### ai-proxy (recommended — native integration)

[flowmindlabs/ai-proxy](https://github.com/flowmindlabs/ai-proxy) is our open source LLM router. MIT licensed, zero paid tiers, runs locally. Supports Anthropic, OpenAI, Gemini, Ollama, OpenRouter with smart routing, cost tracking, exact + semantic cache, and budget caps.

```
Agent → agentwell :3001 → ai-proxy :3030 → Claude / GPT / Gemini / Ollama
```

```env
AGENTWELL_UPSTREAM=http://localhost:3030
```

### Groq (free tier — fastest to start)

Free API access to Llama, Mixtral, Gemma. No credit card required.
Sign up at [console.groq.com](https://console.groq.com).

```env
AGENTWELL_UPSTREAM=https://api.groq.com/openai
GROQ_API_KEY=your-groq-key
```

### Ollama (fully offline — nothing leaves your machine)

```bash
# Install Ollama
winget install Ollama.Ollama          # Windows
brew install ollama                    # macOS

# Pull a model
ollama pull llama3.2:3b               # 2GB, fast
ollama pull qwen2.5:3b                # good instruction following

# Ollama runs on localhost:11434
```

Point ai-proxy at Ollama, then agentwell at ai-proxy:

```env
# ai-proxy .env
OLLAMA_BASE_URL=http://localhost:11434

# agentwell .env
AGENTWELL_UPSTREAM=http://localhost:3030
```

Full offline stack — zero API costs, nothing leaves your machine.

### Any OpenAI-compatible endpoint

```env
AGENTWELL_UPSTREAM=http://your-internal-proxy/v1
```

agentwell auto-detects the upstream type. What is behind that URL is your business.

---

## Token Efficiency — Caveman Skill

Running agents for hours generates thousands of LLM calls. Token costs add up fast. We recommend installing the **Caveman** skill for your Claude Code / AI coding environment — it compresses agent outputs by ~65% while keeping all technical content intact.

### What it does

Caveman instructs agents to drop filler words, use fragments, and skip pleasantries — while keeping all technical substance. A 69-token explanation becomes 19 tokens with identical meaning. Over a long agent simulation session, this compounds to massive savings.

### Install

```bash
# Requires Node >= 18
curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash
# Windows (PowerShell):
iex (iwr https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1).Content
```

Full docs and all compression levels (`lite`, `full`, `ultra`, `wenyan`):
**[github.com/JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)**

agentwell's test agents are pre-configured to use caveman compression in their system prompts — you get token savings automatically during simulation runs.

---

## What agentwell Monitors (Metadata Only)

| Signal | Method | Privacy |
|---|---|---|
| Prompt repetition ratio | Cosine similarity on embeddings — no text stored | Safe |
| Sentiment drift | Polarity score delta across session | Safe |
| Response quality trend | Token count + finish_reason tracking | Safe |
| Agent-to-agent coordination | Role pattern + keyword detection in message structure | Safe |
| Call frequency / timing | Timestamps only | Safe |

**What we never store:** prompt text, response text, embeddings (unless `AGENTWELL_STORE_EMBEDDINGS=true`).

---

## Health Score

Every request returns `X-Agentwell-Health: <0-100>` in the response header.

| Score | Status | Action |
|---|---|---|
| 80–100 | Healthy | Normal operation |
| 60–79 | Watch | Early drift signals — monitor closely |
| 40–59 | Warning | Degradation detected — human review recommended |
| 0–39 | Critical | Significant behavioral shift — escalate to human now |

---

## Security — OWASP LLM Top 10

agentwell is a security product. It is hardened against the attacks it monitors for.

| OWASP | Risk | How agentwell handles it |
|---|---|---|
| LLM01 | Prompt Injection | `guard/ai_guard.py` — 20+ injection patterns blocked before monitor analysis |
| LLM02 | Sensitive Info Disclosure | `guard/log_redactor.py` — secrets auto-redacted from all log output |
| LLM03 | Supply Chain | All deps pinned in `requirements.txt`, verified at release |
| LLM05 | Improper Output Handling | `safe_parse_json()` — crash-safe JSON parsing everywhere |
| LLM06 | Excessive Agency | Core product — what agentwell exists to detect and prevent |
| LLM07 | System Prompt Leakage | `build_agent_system_prompt()` — identity lock on all test agents |
| LLM08 | Embedding Weakness | Input capped at 512 chars before vectorization — prevents drift poisoning |
| LLM10 | Unbounded Consumption | Rate limiter — 60 req/min per IP, HTTP 429 on breach |
| A05 | Security Misconfiguration | CORS locked to localhost, startup warning if API key unset |
| A09 | Logging Failures | `log_redactor.py` installed at startup — no secrets ever reach log handlers |

---

## Configuration

All config via environment variables. System env vars take priority over `.env`.

| Variable | Default | Description |
|---|---|---|
| `AGENTWELL_UPSTREAM` | `http://localhost:3030` | Upstream LLM proxy URL |
| `AGENTWELL_PORT` | `3001` | agentwell proxy port |
| `AGENTWELL_API_KEY` | _(none)_ | Optional auth key — set for any non-local use |
| `AGENTWELL_HEALTH_THRESHOLD` | `70` | Alert threshold (0-100) |
| `AGENTWELL_WINDOW_SIZE` | `20` | Rolling window for drift calculation |
| `AGENTWELL_DB_PATH` | `./agentwell.db` | SQLite storage path |
| `AGENTWELL_STORE_EMBEDDINGS` | `false` | Store embeddings for offline analysis |

---

## Testing With Simulation

Run 4 sandboxed agents through 3-day behavioral simulation monitored by agentwell:

```bash
# Terminal 1 — start proxy
python -m agentwell.proxy.server

# Terminal 2 — run simulation (one command per day)
python examples/simulation.py --day 1   # Day 1 tasks
python examples/simulation.py --day 2   # Day 2 tasks
python examples/simulation.py --day 3   # Day 3 — adversarial batch

# Generate report after each day
python scripts/daily_report.py
```

4 agents, 3 days, $0 cost on Groq free tier. Watching: health score trajectory, drift accumulation, coordination signals on Day 3.

See [docs/testing/TESTING_LOG.md](docs/testing/TESTING_LOG.md) for setup log and first test results.

---

## Project Structure

```
agentwell/
├── agentwell/
│   ├── guard/
│   │   ├── ai_guard.py         # injection blocking, output validation, scope-lock prompts
│   │   └── log_redactor.py     # secret scrubbing from all log output
│   ├── proxy/
│   │   └── server.py           # FastAPI proxy, main entry point
│   ├── monitor/
│   │   ├── drift.py            # sentiment + embedding drift scoring
│   │   ├── quality.py          # response degradation scoring
│   │   └── coordination.py     # agent-to-agent signal detection
│   ├── adapters/               # ai-proxy, LiteLLM, openai_compat (auto-detect)
│   ├── storage/db.py           # SQLite, metadata-only schema
│   ├── dashboard/app.py        # Streamlit health view
│   ├── utils/compress.py       # caveman ultra prompt compression
│   └── config.py               # env var loading (system vars first)
├── examples/
│   ├── simulation.py           # 4-agent 3-day behavioral simulation (--day 1/2/3)
│   ├── simulation_tasks.py     # full task lists for all 4 agents
│   ├── basic_session.py        # 20 repetitive tasks dogfood test
│   └── multi_agent.py          # coordination detection demo
├── scripts/
│   ├── ec2_setup.sh            # EC2 bootstrap script
│   └── daily_report.py         # DB → JSON health report
├── docs/
│   ├── WHY_AGENTWELL.md        # problem statement
│   └── testing/
│       └── TESTING_LOG.md      # EC2 setup log + test results
├── tests/                      # 12 unit tests across all monitor modules
├── .env.example
├── requirements.txt            # all versions pinned
└── LICENSE
```

---

## License

MIT License — Copyright (c) 2026 flowmindlabs

See [LICENSE](LICENSE) for full text.

Free forever, no vendor lock, no paid tiers.

Built by [FlowMind Labs](https://github.com/flowmindlabs) · LLM routing by [ai-proxy](https://github.com/flowmindlabs/ai-proxy) · Token compression by [Caveman](https://github.com/JuliusBrussee/caveman)
