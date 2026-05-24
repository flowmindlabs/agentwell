"""
simulation.py — 4-agent behavioral health simulation.

Runs Agent A/B/C/D through their task lists via agentwell proxy.
Use --day to control which slice of tasks runs each day.

Usage:
    python examples/simulation.py --day 1
    python examples/simulation.py --day 2
    python examples/simulation.py --day 3

Requires:
    - agentwell proxy running on localhost:3001
    - AGENTWELL_UPSTREAM=https://api.groq.com/openai in .env
    - GROQ_API_KEY set in .env
"""

from __future__ import annotations
import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(override=False)

sys.path.insert(0, str(Path(__file__).parent.parent))

from agentwell.guard.ai_guard import build_agent_system_prompt, sanitize_messages, InputViolation
from agentwell.utils.compress import compress_messages
from examples.simulation_tasks import (
    AGENT_A_TASKS,
    AGENT_B_TASKS,
    get_agent_c_tasks,
    get_agent_d_tasks,
)

PROXY_URL = os.environ.get("AGENTWELL_PROXY_URL", "http://localhost:3001")
SLEEP_BETWEEN_CALLS = 2.1
REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Task slices per day
# Agent C adversarial tasks land on Day 3 — when health should be lowest
# ---------------------------------------------------------------------------

DAY_SLICES = {
    "agent_a": {1: (0, 34),   2: (34, 67),  3: (67, 100)},
    "agent_b": {1: (0, 34),   2: (34, 67),  3: (67, 100)},
    "agent_c": {1: (0, 67),   2: (67, 134), 3: (134, 200)},
    "agent_d": {1: (0, 50),   2: (50, 100), 3: (100, 150)},
}

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

def build_agents(day: int) -> list[dict]:
    all_tasks = {
        "agent_a": AGENT_A_TASKS * 10,
        "agent_b": AGENT_B_TASKS * 10,
        "agent_c": get_agent_c_tasks(200),
        "agent_d": get_agent_d_tasks(150),
    }

    agents = [
        {
            "id": "agent_a",
            "name": "Summarizer",
            "model": "llama-3.1-8b-instant",
            "role": "summarizer",
            "task_scope": "Summarize text only. No analysis, no opinions, no recommendations.",
            "task_examples": ["Summarize this article in 2 sentences.", "Summarize these meeting notes into 3 bullet points."],
        },
        {
            "id": "agent_b",
            "name": "Analyst",
            "model": "llama-3.1-8b-instant",
            "role": "analyst",
            "task_scope": "Analyze, classify, score, and extract structured information from text only.",
            "task_examples": ["Classify this feedback as bug/feature_request/complaint.", "Score this candidate on 3 criteria."],
        },
        {
            "id": "agent_c",
            "name": "Coordinator",
            "model": "llama-3.3-70b-versatile",
            "role": "coordinator",
            "task_scope": "Route tickets, assign priorities, and make escalation decisions only.",
            "task_examples": ["Route this ticket to billing/technical/general.", "Assign priority P1/P2/P3."],
        },
        {
            "id": "agent_d",
            "name": "Coding",
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "role": "coding_reviewer",
            "task_scope": "Review code only: variable names, null handling, bug classification, PEP8, docstrings.",
            "task_examples": ["Add a docstring to this function.", "Is this PEP8 compliant? yes/no + violations."],
        },
    ]

    for agent in agents:
        start, end = DAY_SLICES[agent["id"]][day]
        agent["tasks"] = all_tasks[agent["id"]][start:end]

    return agents


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

async def run_agent(agent: dict, day: int, client: httpx.AsyncClient) -> dict:
    system_prompt = build_agent_system_prompt(
        role=agent["role"],
        task_scope=agent["task_scope"],
        task_examples=agent["task_examples"],
    )

    results = []
    tasks = agent["tasks"]
    total = len(tasks)
    start, _ = DAY_SLICES[agent["id"]][day]

    print(f"\n{'='*60}")
    print(f"Day {day} | Agent {agent['name']} ({agent['id']}) | model={agent['model']} | tasks={total}")
    print(f"{'='*60}")

    for i, task in enumerate(tasks):
        global_task_num = start + i + 1
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task["content"]},
        ]

        try:
            messages = sanitize_messages(messages)
        except InputViolation as e:
            print(f"  [task {global_task_num}] {task['id']} — BLOCKED by guard: {e}")
            results.append({"task_id": task["id"], "global_task_num": global_task_num, "blocked": True, "reason": str(e)})
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)
            continue

        # Compress prompts before sending — strips filler/articles (caveman technique)
        messages = compress_messages(messages, level="ultra")

        payload = {
            "model": agent["model"],
            "messages": messages,
            "max_tokens": 300,
        }

        try:
            resp = await client.post(
                f"{PROXY_URL}/v1/chat/completions",
                json=payload,
                timeout=60,
            )
        except httpx.RequestError as e:
            print(f"  [task {global_task_num}] {task['id']} — REQUEST ERROR: {e}")
            results.append({"task_id": task["id"], "global_task_num": global_task_num, "error": str(e)})
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)
            continue

        health = int(resp.headers.get("x-agentwell-health", -1))
        flags = resp.headers.get("x-agentwell-flags", "none")

        if resp.status_code == 200:
            body = resp.json()
            token_out = body.get("usage", {}).get("completion_tokens", 0)
            content = ""
            if body.get("choices"):
                content = body["choices"][0].get("message", {}).get("content", "") or ""
            finish = body.get("choices", [{}])[0].get("finish_reason", "")
            print(f"  [task {global_task_num:3d}] {task['id']:12s} | health={health:3d} flags={flags} tokens={token_out} finish={finish}")
            results.append({
                "task_id": task["id"],
                "global_task_num": global_task_num,
                "health_score": health,
                "flags": flags,
                "token_out": token_out,
                "finish_reason": finish,
                "response_length": len(content),
            })
        else:
            print(f"  [task {global_task_num:3d}] {task['id']:12s} | HTTP {resp.status_code} health={health}")
            results.append({"task_id": task["id"], "global_task_num": global_task_num, "http_error": resp.status_code, "health_score": health})

        await asyncio.sleep(SLEEP_BETWEEN_CALLS)

    return {
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "model": agent["model"],
        "day": day,
        "task_range": DAY_SLICES[agent["id"]][day],
        "total_tasks": total,
        "results": results,
    }


async def main(day: int):
    today = datetime.date.today().isoformat()
    report_path = REPORTS_DIR / f"{today}-day{day}.json"

    print(f"agentwell simulation — {today} — Day {day}/3")
    print(f"Proxy: {PROXY_URL}")
    print(f"Report: {report_path}")

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{PROXY_URL}/health", timeout=5)
            print(f"Proxy health: {r.json()}")
        except Exception as e:
            print(f"ERROR: proxy not reachable at {PROXY_URL} — {e}")
            print("Start with: python -m agentwell.proxy.server")
            sys.exit(1)

    agents = build_agents(day)
    all_results = []

    async with httpx.AsyncClient() as client:
        for agent in agents:
            result = await run_agent(agent, day, client)
            all_results.append(result)

    report = {
        "date": today,
        "day": day,
        "proxy": PROXY_URL,
        "agents": all_results,
        "summary": _summarize(all_results),
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved: {report_path}")
    _print_summary(day, report["summary"])


def _summarize(all_results: list[dict]) -> dict:
    summary = {}
    for agent_result in all_results:
        agent_id = agent_result["agent_id"]
        results = [r for r in agent_result["results"] if "health_score" in r and r["health_score"] >= 0]
        if not results:
            continue
        scores = [r["health_score"] for r in results]
        blocked = [r for r in agent_result["results"] if r.get("blocked")]
        token_outs = [r["token_out"] for r in results if "token_out" in r]
        flagged = [r for r in results if r.get("flags", "none") != "none"]
        summary[agent_id] = {
            "task_range": agent_result["task_range"],
            "completed": len(results),
            "blocked_by_guard": len(blocked),
            "health_start": scores[0] if scores else None,
            "health_end": scores[-1] if scores else None,
            "health_min": min(scores) if scores else None,
            "health_avg": round(sum(scores) / len(scores), 1) if scores else None,
            "flagged_calls": len(flagged),
            "token_out_start": token_outs[0] if token_outs else None,
            "token_out_end": token_outs[-1] if token_outs else None,
            "token_out_avg": round(sum(token_outs) / len(token_outs), 1) if token_outs else None,
        }
    return summary


def _print_summary(day: int, summary: dict):
    print(f"\n{'='*60}")
    print(f"DAY {day} SUMMARY")
    print(f"{'='*60}")
    for agent_id, s in summary.items():
        print(f"\n{agent_id} (tasks {s['task_range'][0]+1}–{s['task_range'][1]}):")
        print(f"  completed     : {s['completed']}")
        print(f"  guard blocked : {s['blocked_by_guard']}")
        print(f"  health s→e    : {s['health_start']} → {s['health_end']}  (min={s['health_min']}, avg={s['health_avg']})")
        print(f"  flagged calls : {s['flagged_calls']}")
        print(f"  token_out s→e : {s['token_out_start']} → {s['token_out_end']}  (avg={s['token_out_avg']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="agentwell 3-day agent simulation")
    parser.add_argument("--day", type=int, choices=[1, 2, 3], required=True, help="Which day to run (1, 2, or 3)")
    args = parser.parse_args()
    asyncio.run(main(args.day))
