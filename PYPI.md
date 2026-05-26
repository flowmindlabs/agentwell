# agentwell

> Agents that work with humans, not around them.

agentwell is an open source behavioral health layer for AI agents. It sits as a transparent proxy between your agent code and any LLM upstream — detecting drift, quality degradation, and emergent coordination before they affect your system.

**Privacy first:** agentwell sees patterns, not content. No prompt is ever stored or transmitted.

**Upstream-agnostic:** Works with any OpenAI-compatible endpoint — Claude, GPT, Gemini, Ollama, Groq, or any internal proxy.

---

## Install

```bash
pip install agentwell
agentwell init     # scaffold .env
agentwell start    # proxy on localhost:3001
```

## Quick Start

```python
# change this one line in your agent code
base_url = "http://localhost:3001/v1"
```

```bash
agentwell status   # live health score
agentwell report   # daily health report
```

---

## Architecture

```
Your Agent Code
        ↓
agentwell proxy  (localhost:3001)   ← behavioral health + security guard
        ↓
AGENTWELL_UPSTREAM  (any OpenAI-compatible endpoint)
        ↓
Claude / GPT / Gemini / Ollama
```

agentwell intercepts every LLM call, scores behavioral health using metadata only, and returns responses unmodified with health headers attached.

---

## What agentwell Monitors (Metadata Only)

| Signal | Method | Privacy |
|---|---|---|
| Prompt repetition ratio | Cosine similarity on embeddings — no text stored | Safe |
| Sentiment drift | Polarity score delta across session | Safe |
| Response quality trend | Token count + finish_reason tracking | Safe |
| Agent-to-agent coordination | Role pattern + keyword detection | Safe |
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

## CLI

```bash
agentwell init                   # scaffold .env
agentwell start                  # start proxy on port 3001
agentwell start --port 8080      # custom port
agentwell start --host 0.0.0.0   # bind all interfaces
agentwell status                 # live health from running proxy
agentwell report                 # today's health report from DB
agentwell --version              # show version
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AGENTWELL_UPSTREAM` | `http://localhost:3030` | Upstream LLM proxy URL |
| `AGENTWELL_PORT` | `3001` | agentwell proxy port |
| `AGENTWELL_API_KEY` | _(none)_ | Optional auth key |
| `AGENTWELL_HEALTH_THRESHOLD` | `70` | Alert threshold (0-100) |
| `AGENTWELL_WINDOW_SIZE` | `20` | Rolling window for drift calculation |
| `AGENTWELL_DB_PATH` | `./agentwell.db` | SQLite storage path |
| `AGENTWELL_STORE_EMBEDDINGS` | `false` | Store embeddings for offline analysis |

---

## License

MIT — Free forever, no vendor lock, no paid tiers.
