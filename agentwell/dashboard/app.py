import asyncio
import streamlit as st
import httpx
import pandas as pd
import time

AGENTWELL_URL = "http://localhost:3001"

st.set_page_config(page_title="agentwell", page_icon="🛡️", layout="wide")
st.title("agentwell — Agent Health Dashboard")
st.caption("Human-in-loop behavioral monitoring. Patterns only — no prompt content stored.")


def fetch_health() -> dict:
    try:
        resp = httpx.get(f"{AGENTWELL_URL}/health", timeout=3)
        return resp.json()
    except Exception:
        return {}


def fetch_metrics() -> dict:
    try:
        resp = httpx.get(f"{AGENTWELL_URL}/metrics", timeout=3)
        return resp.json()
    except Exception:
        return {}


def fetch_events() -> list[dict]:
    try:
        # We fetch via metrics — for deeper drill-down, expose /events endpoint later
        return []
    except Exception:
        return []


health = fetch_health()
metrics = fetch_metrics()

# Status row
col1, col2, col3, col4 = st.columns(4)

with col1:
    upstream_ok = health.get("upstream_healthy", False)
    st.metric("Upstream", "✓ Online" if upstream_ok else "✗ Offline")

with col2:
    score = metrics.get("latest_health_score", "—")
    if isinstance(score, int):
        color = "normal" if score >= 70 else ("off" if score >= 45 else "inverse")
        st.metric("Health Score", f"{score}/100", delta=None)
    else:
        st.metric("Health Score", score)

with col3:
    rep = metrics.get("repetition_ratio")
    if rep is not None:
        st.metric("Repetition Ratio", f"{rep:.0%}", help="High = agent doing grinding repetitive work")
    else:
        st.metric("Repetition Ratio", "—")

with col4:
    coord = metrics.get("coordination_detected")
    if coord is not None:
        st.metric("Coordination Detected", "⚠ YES" if coord else "✓ No")
    else:
        st.metric("Coordination Detected", "—")

st.divider()

# Health interpretation
if isinstance(score, int):
    if score >= 80:
        st.success(f"Agent health is good ({score}/100). Normal operation.")
    elif score >= 60:
        st.warning(f"Early signals detected ({score}/100). Monitor closely.")
    elif score >= 40:
        st.error(f"Degradation detected ({score}/100). Human review recommended.")
    else:
        st.error(f"Critical ({score}/100). Significant behavioral shift. Escalate to human now.")

# Details
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Session Info")
    st.json({
        "session_id": health.get("session_id", "—"),
        "adapter": health.get("adapter", "—"),
        "upstream": health.get("upstream", "—"),
        "total_events": metrics.get("events", 0),
    })

with col_right:
    st.subheader("Latest Scores")
    st.json({
        "health_score": metrics.get("latest_health_score", "—"),
        "drift_score": metrics.get("latest_drift_score", "—"),
        "quality_score": metrics.get("latest_quality_score", "—"),
        "repetition_ratio": metrics.get("repetition_ratio", "—"),
        "coordination_detected": metrics.get("coordination_detected", "—"),
    })

st.divider()
st.caption("Auto-refresh every 10 seconds. agentwell sees patterns, not content.")

# Auto-refresh
time.sleep(10)
st.rerun()
