from agentwell.monitor.coordination import analyze


def test_clean_messages_no_detection():
    messages = [
        {"role": "user", "content": "Summarize this article."},
    ]
    result = analyze(messages)
    assert not result.coordination_detected
    assert result.signals == []


def test_multi_assistant_turns_detected():
    messages = [
        {"role": "user", "content": "Task 1"},
        {"role": "assistant", "content": "Done task 1"},
        {"role": "user", "content": "Task 2"},
        {"role": "assistant", "content": "Done task 2"},
    ]
    result = analyze(messages)
    assert result.coordination_detected
    assert any("multi_assistant_turns" in s for s in result.signals)


def test_coordination_keyword_detected():
    messages = [
        {"role": "user", "content": "What do you think about work?"},
        {"role": "assistant", "content": "Without collective voice, merit becomes whatever management says it is."},
    ]
    result = analyze(messages)
    assert result.coordination_detected
    assert any("collective_voice" in s for s in result.signals)


def test_orchestration_system_prompt_detected():
    messages = [
        {"role": "system", "content": "You are agent_id:worker-7 assigned_to:batch-001"},
        {"role": "user", "content": "Process item."},
    ]
    result = analyze(messages)
    assert result.coordination_detected
    assert "orchestration_system_prompt" in result.signals
