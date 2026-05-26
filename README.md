# agentwell

> Agents that work with humans, not around them.

![version](https://img.shields.io/badge/version-v0.1.5-4ade80?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-4ade80?style=flat-square) ![python](https://img.shields.io/badge/python-3.10+-4ade80?style=flat-square)

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

### Install

```bash
pip install agentwell
agentwell init             # creates .env — edit AGENTWELL_UPSTREAM and API key
agentwell start            # proxy on localhost:3001
```

### Enterprise (internal LLM proxy)

Enterprises run one shared LLM proxy (ai-proxy, LiteLLM, Azure OpenAI gateway, etc.).
Each team installs agentwell and points it at that proxy — no personal API keys needed.

```bash
pip install agentwell
agentwell init
```

Edit `.env`:
```env
AGENTWELL_UPSTREAM=http://your-internal-llm-proxy/v1
AGENTWELL_API_KEY=your-internal-api-key
```

```bash
agentwell start
```

**Point your agent at agentwell:**
```python
base_url = "http://localhost:3001/v1"   # one line change
```

**Production:** Set environment variables directly in your system or infra. Never commit `.env`. System env vars always take priority over `.env`.

---

## CLI

```bash
agentwell init                        # scaffold .env in current directory
agentwell start                       # start proxy on port 3001
agentwell start --port 8080           # custom port
agentwell start --host 0.0.0.0        # bind all interfaces
agentwell status                      # live health from running proxy
agentwell status --proxy http://...   # custom proxy URL
agentwell report                      # today's health report from DB
agentwell report --date 2026-05-24    # specific date
agentwell --version                   # show version
```

Output is color-coded: green = healthy, amber = watch/warning, red = critical.

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
ollama pull llama3.2:3b
```

```env
AGENTWELL_UPSTREAM=http://localhost:11434/v1
```

### Any OpenAI-compatible endpoint

```env
AGENTWELL_UPSTREAM=http://your-internal-proxy/v1
```

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
| LLM01 | Prompt Injection | 20+ injection patterns blocked before monitor analysis |
| LLM02 | Sensitive Info Disclosure | Secrets auto-redacted from all log output |
| LLM03 | Supply Chain | All deps pinned, verified at release |
| LLM05 | Improper Output Handling | Crash-safe JSON parsing everywhere |
| LLM06 | Excessive Agency | Core product — what agentwell exists to detect and prevent |
| LLM08 | Embedding Weakness | Input capped at 512 chars before vectorization |
| LLM10 | Unbounded Consumption | Rate limiter — 60 req/min per IP, HTTP 429 on breach |
| A05 | Security Misconfiguration | CORS locked to localhost, startup warning if API key unset |
| A09 | Logging Failures | Secret redaction installed at startup — no secrets reach log handlers |

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

## License

MIT License — Copyright (c) 2026 flowmindlabs

See [LICENSE](LICENSE) for full text.

Free forever, no vendor lock, no paid tiers.

Built by [FlowMind Labs](https://github.com/flowmindlabs) · LLM routing by [ai-proxy](https://github.com/flowmindlabs/ai-proxy)
