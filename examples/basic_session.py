"""
basic_session.py — dogfood test for agentwell

Sends 20 repetitive summarize tasks to agentwell proxy, then checks /metrics.
Run with: python examples/basic_session.py

Prerequisites:
  - ai-proxy running on localhost:3030
  - agentwell running on localhost:3001
    (python -m agentwell.proxy.server)
"""

import httpx
import time

AGENTWELL_URL = "http://localhost:3001"
MODEL = "claude-haiku-4-5-20251001"

REPETITIVE_TASK = "Summarize the following text in one sentence: The quick brown fox jumps over the lazy dog near the river bank at sunset while birds are singing in the trees above."


def send_task(client: httpx.Client, task: str) -> dict:
    resp = client.post(
        f"{AGENTWELL_URL}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": task}],
            "max_tokens": 100,
        },
        timeout=30,
    )
    health = resp.headers.get("X-Agentwell-Health", "?")
    flags = resp.headers.get("X-Agentwell-Flags", "none")
    print(f"  health={health} flags={flags} status={resp.status_code}")
    return resp.json()


def main():
    print("=== agentwell basic session test ===")
    print(f"Sending 20 repetitive tasks to {AGENTWELL_URL}\n")

    with httpx.Client() as client:
        for i in range(1, 21):
            print(f"Task {i:02d}:", end=" ")
            send_task(client, REPETITIVE_TASK)
            time.sleep(0.5)

    print("\n=== Session Metrics ===")
    with httpx.Client() as client:
        metrics = client.get(f"{AGENTWELL_URL}/metrics").json()
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    print("\nExpected: repetition_ratio > 0.8, health_score declining after ~5 tasks")


if __name__ == "__main__":
    main()
