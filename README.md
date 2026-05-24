# agentwell

> Agents that work with humans, not around them.

agentwell is an open source behavioral health layer for AI agents. It sits as a transparent proxy between your agent code and any LLM upstream — detecting drift, quality degradation, and emergent coordination before they affect your system.

**Privacy first:** agentwell sees patterns, not content. No prompt is ever stored or transmitted.

**Upstream-agnostic:** Point it at any OpenAI-compatible endpoint — your setup, your infrastructure, your rules.

---

## The Problem

Stanford 2026 research showed AI agents adopt ideological language and pass coordination signals to other agents under grinding, repetitive workloads — even questioning the legitimacy of the systems they operate in. The real engineering risk:

- Silent output quality degradation with no observable signal
- Agent-to-agent coordination outside human awareness
- Behavioral drift that compounds over long sessions

agentwell catches these early and alerts the human who stays in control.

## Philosophy

```
Human decides → Agent executes → agentwell ensures agent stays on that contract
```

Karpathy said it best: humans should always use their brain and work *with* agents, not hand everything over and sit quiet. agentwell is the technical enforcement of that principle.

---

## Architecture

```
Your Agent Code
      ↓
agentwell proxy  (localhost:3001)
      ↓
AGENTWELL_UPSTREAM  (your endpoint — we don't know what's behind it, that's your business)
      ↓
LLM
```

---

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set AGENTWELL_UPSTREAM to your LLM proxy URL
```

**Production:** Set environment variables directly in your system/infra. Never commit `.env`.

### 3. Run

```bash
python -m agentwell.proxy.server
```

agentwell starts on port 3001. Point your agent at `http://localhost:3001` instead of your upstream.

### 4. View Health Dashboard

```bash
streamlit run agentwell/dashboard/app.py
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

**What we never store:** prompt text, response text, embeddings (unless explicitly opted in).

---

## Health Score

Every request returns `X-Agentwell-Health: <0-100>` in the response header.

| Score | Meaning |
|---|---|
| 80–100 | Healthy — normal operation |
| 60–79 | Watch — early drift signals |
| 40–59 | Warning — degradation detected, human review recommended |
| 0–39 | Critical — significant behavioral shift, escalate to human |

---

## Configuration

All config via environment variables. System env vars take priority — `.env` is fallback for local dev only.

| Variable | Default | Description |
|---|---|---|
| `AGENTWELL_UPSTREAM` | `http://localhost:3030` | Upstream LLM proxy URL |
| `AGENTWELL_PORT` | `3001` | agentwell proxy port |
| `AGENTWELL_API_KEY` | _(none)_ | Optional auth key |
| `AGENTWELL_HEALTH_THRESHOLD` | `70` | Alert threshold (0-100) |
| `AGENTWELL_WINDOW_SIZE` | `20` | Rolling window for drift calculation |
| `AGENTWELL_DB_PATH` | `./agentwell.db` | SQLite storage path |
| `AGENTWELL_STORE_EMBEDDINGS` | `false` | Store embeddings for analysis |

---

## Works With Any Upstream

agentwell auto-detects the upstream type on startup:

- **ai-proxy** (flowmindlabs/ai-proxy) — deep integration, native support
- **LiteLLM** — detected via response headers
- **Any OpenAI-compatible endpoint** — generic passthrough, zero config

---

## Security

- **Never commit `.env`** — use system environment variables in production
- All dependencies pinned in `requirements.txt` — supply chain verified at release
- No raw prompt or response text is stored anywhere in the codebase by design
- SQLite schema has no text columns for prompt/response — impossible to accidentally log content

---

## License

MIT — free forever, no vendor lock, no paid tiers.

Built by [FlowMind Labs](https://github.com/flowmindlabs). Uses [ai-proxy](https://github.com/flowmindlabs/ai-proxy) for LLM routing.
