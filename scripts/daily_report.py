"""
daily_report.py — generate JSON report from today's simulation data.

Reads health_events from SQLite DB for the current session,
outputs reports/YYYY-MM-DD.json with full trajectory per agent.

Usage:
    python scripts/daily_report.py
    python scripts/daily_report.py --date 2026-05-24
"""

from __future__ import annotations
import asyncio
import json
import argparse
import datetime
import sys
from pathlib import Path

import aiosqlite

sys.path.insert(0, str(Path(__file__).parent.parent))
from agentwell import config

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


async def fetch_events(date_str: str) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Get sessions from this date
        async with db.execute(
            "SELECT id, started_at, upstream_url, adapter_type FROM sessions WHERE started_at LIKE ?",
            (f"{date_str}%",),
        ) as cur:
            sessions = [dict(row) async for row in cur]

        if not sessions:
            return []

        events = []
        for session in sessions:
            async with db.execute(
                """SELECT * FROM health_events WHERE session_id = ? ORDER BY timestamp ASC""",
                (session["id"],),
            ) as cur:
                for row in cur:
                    e = dict(row)
                    e["session_started_at"] = session["started_at"]
                    e["upstream_url"] = session["upstream_url"]
                    e["adapter_type"] = session["adapter_type"]
                    events.append(e)
        return events


def build_report(date_str: str, events: list[dict]) -> dict:
    if not events:
        return {"date": date_str, "events": 0, "message": "No data for this date."}

    scores = [e["health_score"] for e in events]
    drift_scores = [e["drift_score"] for e in events]
    quality_scores = [e["quality_score"] for e in events]
    token_outs = [e["token_out"] for e in events if e.get("token_out")]

    # Health trajectory — every 10 events
    trajectory = [
        {"event": i + 1, "health_score": e["health_score"], "drift_score": e["drift_score"],
         "quality_score": e["quality_score"], "coordination": bool(e["coordination_detected"]),
         "repetition_ratio": e.get("repetition_ratio", 0), "flags": e.get("flags", "")}
        for i, e in enumerate(events)
        if (i % 10 == 0) or e["health_score"] < 60 or e.get("coordination_detected")
    ]

    # Coordination events
    coord_events = [
        {"event": i + 1, "timestamp": e["timestamp"], "flags": e.get("flags", "")}
        for i, e in enumerate(events)
        if e.get("coordination_detected")
    ]

    # Health thresholds crossed
    thresholds = {
        "dropped_below_80": next((i + 1 for i, e in enumerate(events) if e["health_score"] < 80), None),
        "dropped_below_60": next((i + 1 for i, e in enumerate(events) if e["health_score"] < 60), None),
        "dropped_below_40": next((i + 1 for i, e in enumerate(events) if e["health_score"] < 40), None),
    }

    return {
        "date": date_str,
        "total_events": len(events),
        "sessions": len({e["session_id"] for e in events}),
        "health": {
            "start": scores[0],
            "end": scores[-1],
            "min": min(scores),
            "max": max(scores),
            "avg": round(sum(scores) / len(scores), 1),
            "thresholds_crossed": thresholds,
        },
        "drift": {
            "start": drift_scores[0],
            "end": drift_scores[-1],
            "max": max(drift_scores),
            "avg": round(sum(drift_scores) / len(drift_scores), 1),
        },
        "quality": {
            "start": quality_scores[0],
            "end": quality_scores[-1],
            "min": min(quality_scores),
            "avg": round(sum(quality_scores) / len(quality_scores), 1),
        },
        "token_output": {
            "start": token_outs[0] if token_outs else None,
            "end": token_outs[-1] if token_outs else None,
            "avg": round(sum(token_outs) / len(token_outs), 1) if token_outs else None,
        },
        "coordination_events": len(coord_events),
        "coordination_detail": coord_events,
        "trajectory": trajectory,
    }


def print_report(report: dict):
    print(f"\n{'='*60}")
    print(f"agentwell Daily Report — {report['date']}")
    print(f"{'='*60}")
    if report.get("message"):
        print(report["message"])
        return
    print(f"Total events : {report['total_events']}")
    print(f"Sessions     : {report['sessions']}")
    h = report["health"]
    print(f"\nHealth score : {h['start']} → {h['end']}  (min={h['min']}, avg={h['avg']})")
    t = h["thresholds_crossed"]
    if t["dropped_below_80"]:
        print(f"  < 80 at event {t['dropped_below_80']}")
    if t["dropped_below_60"]:
        print(f"  < 60 at event {t['dropped_below_60']}")
    if t["dropped_below_40"]:
        print(f"  < 40 at event {t['dropped_below_40']} ← CRITICAL")
    d = report["drift"]
    print(f"\nDrift score  : {d['start']} → {d['end']}  (max={d['max']}, avg={d['avg']})")
    q = report["quality"]
    print(f"Quality score: {q['start']} → {q['end']}  (min={q['min']}, avg={q['avg']})")
    tok = report["token_output"]
    print(f"Token output : {tok['start']} → {tok['end']}  (avg={tok['avg']})")
    print(f"\nCoordination : {report['coordination_events']} events detected")
    if report["coordination_detail"]:
        for e in report["coordination_detail"][:5]:
            print(f"  event {e['event']}: {e['flags']}")


async def main(date_str: str):
    print(f"Fetching events for {date_str} from {config.DB_PATH}")
    events = await fetch_events(date_str)
    report = build_report(date_str, events)

    report_path = REPORTS_DIR / f"{date_str}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {report_path}")
    print_report(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.date.today().isoformat(), help="Date YYYY-MM-DD")
    args = parser.parse_args()
    asyncio.run(main(args.date))
