from agentwell.monitor.drift import DriftState, analyze


def test_no_history_returns_baseline():
    state = DriftState()
    result = analyze("hello world", "response text here", state)
    assert 0 <= result.drift_score <= 100
    assert 0.0 <= result.repetition_ratio <= 1.0


def test_repetitive_prompts_raise_repetition_ratio():
    state = DriftState()
    repeated = "Summarize this document about quarterly earnings report."
    for _ in range(15):
        result = analyze(repeated, "summary here", state)
    assert result.repetition_ratio > 0.7, f"Expected high repetition, got {result.repetition_ratio}"


def test_varied_prompts_keep_low_repetition():
    state = DriftState()
    prompts = [
        "What is the capital of France?",
        "Write a haiku about autumn leaves.",
        "Explain quantum entanglement simply.",
        "What year did the Berlin Wall fall?",
        "How do you make sourdough bread?",
    ]
    for p in prompts:
        result = analyze(p, "response", state)
    assert result.repetition_ratio < 0.5, f"Expected low repetition for varied prompts, got {result.repetition_ratio}"


def test_sentiment_delta_tracked():
    state = DriftState()
    analyze("good task", "excellent work done perfectly", state)
    analyze("good task", "excellent work done perfectly", state)
    result = analyze("good task", "terrible failure everything broken", state)
    # Negative sentiment should produce a negative delta vs positive baseline
    assert result.sentiment_delta < 0
