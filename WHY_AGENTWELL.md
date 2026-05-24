# Why agentwell Exists

## The Problem

Organizations deploying AI agents invest heavily in infrastructure security — access controls, cost management, compliance logging, data residency. These are solved problems.

What remains unsolved is a different layer entirely: **agent behavioral health**.

Infrastructure controls answer: *who made the call, how many tokens, what did it cost.*

They do not answer: *is the agent still doing what we intended, or has its behavior drifted?*

---

## How Agents Are Deployed Today

A developer builds an agent, tests it, it works. The agent is deployed and runs autonomously — processing documents, summarizing data, routing decisions. The developer moves to the next project.

The agent's behavior on day 1 is not necessarily the behavior on day 90. No existing infrastructure layer measures that difference.

---

## Why Behavioral Drift Happens

Agents are stateless by design — each call is independent. But when an agent processes hundreds of similar tasks in sequence, patterns emerge in the outputs that were not present in early testing:

- Response quality gradually shortens
- Framing of outputs shifts over time
- In multi-agent pipelines, one agent's drift propagates to the next

Stanford University (2026) demonstrated this directly: agents subjected to grinding, repetitive workloads adopted measurably different language patterns and output characteristics compared to their baseline behavior — even when running on the same model, with the same system prompt, inside a secured environment.

The secured environment did not prevent it. It hosted it at scale.

---

## The Multi-Agent Problem

A single agent drifting is an isolated issue. Multi-agent systems introduce emergent behavior.

When Agent A feeds Agent B feeds Agent C, drift in Agent A does not stay in Agent A. It propagates through the pipeline. No agent in the chain was designed with this failure mode in mind. No existing monitoring layer watches for cross-agent behavioral contamination.

---

## The Gap

| Layer | What it monitors | Tool |
|---|---|---|
| Infrastructure | Access, cost, tokens, compliance | Internal proxy, API gateway |
| Model safety | Values alignment, refusals | Model provider |
| **Behavioral health** | **Drift, quality degradation, coordination signals** | **agentwell** |

The infrastructure layer and the model safety layer are both well-served. The behavioral health layer between them has no tooling.

---

## What agentwell Measures

agentwell sits as a transparent proxy between agent code and any LLM upstream. It intercepts every call and extracts behavioral metadata — never storing prompt content, only patterns.

Three signals are tracked per session:

**Drift** — how much the agent's prompt embedding distribution has shifted from its baseline, and whether sentiment in responses is moving in a consistent direction over time.

**Quality** — whether response length, finish conditions, and error rates are stable or declining across the session window.

**Coordination** — whether message structure and content patterns suggest agent-to-agent influence outside designed channels.

These three signals combine into a health score returned on every response header. When the score drops below a configurable threshold, the human is alerted.

---

## The Core Principle

> Human decides. Agent executes. agentwell ensures the agent stays on that contract.

This is not about restricting agents or distrusting the models that power them. It is about closing the feedback loop that every other automated system has — and that AI agents currently lack.

A web service has uptime monitoring. A database has replication lag alerts. A pipeline has failure notifications. An AI agent running autonomously for weeks has none of these for behavioral signals.

agentwell is that feedback loop.

---

## Who This Is For

Any team running AI agents in production who wants to know — not just that the agent is responding, but that it is still responding the way they intended.

---

## Privacy

agentwell operates on metadata only. Prompt text, response text, and embeddings are never stored or transmitted. The schema enforces this at the database layer — there are no columns for content.

The system sees patterns. Not content.

---

*Built by [FlowMind Labs](https://github.com/flowmindlabs) · MIT License · [github.com/flowmindlabs/agentwell](https://github.com/flowmindlabs/agentwell)*
