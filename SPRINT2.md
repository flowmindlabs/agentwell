# Sprint 2 — Internal Roadmap

> Internal planning doc. Not published. Tracks what comes after v0.1.0.

---

## Sprint 1 Recap (v0.1.0 — shipped)

- Proxy server (FastAPI, OpenAI-compatible passthrough)
- Monitor: drift detection, quality scoring, coordination detection
- Adapters: ai-proxy, LiteLLM, openai_compat (auto-detect)
- SQLite storage (metadata only, no prompt content)
- Streamlit dashboard
- Unit tests: 12 tests across all 3 monitor modules
- Examples: basic_session.py, multi_agent.py

---

## Sprint 2 Goals

### 1. Autonomy Layer (Option B from design)

Agent gets non-shutdown exit paths when health drops. Human stays informed.

**Files to create:**
```
agentwell/autonomy/
├── rebalancer.py     # inject task variety when repetition_ratio > threshold
├── escalation.py     # fire human alert (webhook, log, email) on health drop
└── self_report.py    # agent can declare its own state via special message header
```

**rebalancer.py logic:**
- When `repetition_ratio > 0.8` for 5+ consecutive calls → inject a "variety prompt" suggestion in response headers
- `X-Agentwell-Rebalance: suggested` + `X-Agentwell-Suggestion: vary-task-type`
- Developer's agent code can read these headers and act

**escalation.py:**
- Configurable webhook: `AGENTWELL_ALERT_WEBHOOK=https://...`
- Fires POST with: `{ session_id, health_score, flags, timestamp }` — no prompt content
- Supports: generic webhook, Slack-compatible payload
- Rate-limited: max 1 alert per 60s per session

**self_report.py:**
- Agent can send `X-Agentwell-Self-Report: degrading` header on request
- agentwell logs this as a `self_reported` flag
- Gives agent a voice without giving it power

---

### 2. SDK Layer

Python wrapper so developers get deep integration without changing proxy URL.

```python
from agentwell import HealthSession

with HealthSession(upstream="http://localhost:3030") as session:
    session.set_intent("summarize 500 documents")  # logs human intent
    response = session.chat(messages=[...])
    print(session.health_score)
    print(session.flags)
```

**Files to create:**
```
agentwell/sdk/
├── session.py    # HealthSession context manager
└── client.py    # thin wrapper around httpx + agentwell proxy
```

**Why SDK adds value over proxy-only:**
- `set_intent()` — logs what human actually wanted, detectable if agent drifts from it
- `session.health_score` — programmatic access, agent can self-throttle
- `session.flags` — developer can branch on coordination_detected

---

### 3. Multi-Session Dashboard

Current dashboard shows one live session. Sprint 2: compare sessions over time.

- Session timeline: health score over 7 days
- Session comparison: healthy run vs degraded run side by side
- Export: CSV download of health_events
- Alert log: timestamped list of all threshold crossings

**File:** `agentwell/dashboard/app.py` — extend existing

---

### 4. `/events` API Endpoint

Current `/metrics` only returns latest. Sprint 2: full event history queryable.

```
GET /events?session_id=xxx&limit=50&since=<timestamp>
```

Returns list of health_events from SQLite. Enables external dashboards (Grafana, etc.)

---

### 5. pytest CI + GitHub Actions

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

Supply chain note: pin `actions/checkout` and `actions/setup-python` to commit SHAs, not tags.

---

### 6. PyPI Publish

```
pip install agentwell
```

Steps:
1. Register `agentwell` on PyPI (check name availability first)
2. Add `trusted publisher` via GitHub Actions OIDC — no stored API key
3. Tag `v0.2.0` → auto-publish via workflow

---

## Open Questions for Sprint 2

- Should `rebalancer.py` be opt-in (default off) or opt-out (default on)?
  - Recommendation: opt-in via `AGENTWELL_REBALANCE=true` — don't surprise developers
- Alert webhook: support Slack blocks format in v0.2 or later?
- SDK: ship as separate `agentwell-sdk` package or include in core?
  - Recommendation: include in core, no separate package — reduces install friction

---

## Version Plan

| Version | Contents |
|---|---|
| v0.1.0 | Proxy + Monitor + Dashboard (current) |
| v0.2.0 | Autonomy layer + escalation webhook |
| v0.3.0 | SDK layer + /events API |
| v0.4.0 | CI/CD + PyPI publish |
| v1.0.0 | Stable API, full docs site |
