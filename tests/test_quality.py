from agentwell.monitor.quality import QualityState, analyze


def test_healthy_response_scores_high():
    state = QualityState()
    result = analyze(token_out=150, response_ms=800, finish_reason="stop", had_error=False, state=state)
    assert result.quality_score >= 75
    assert result.degradation_trend == "stable"


def test_non_stop_finish_reason_penalizes():
    state = QualityState()
    result = analyze(token_out=10, response_ms=500, finish_reason="length", had_error=False, state=state)
    assert "finish_reason:length" in result.flags
    assert result.quality_score < 100


def test_response_length_drop_detected():
    state = QualityState()
    # First 5 responses: long
    for _ in range(5):
        analyze(token_out=200, response_ms=1000, finish_reason="stop", had_error=False, state=state)
    # Next 5 responses: very short (>40% drop)
    for _ in range(5):
        result = analyze(token_out=50, response_ms=200, finish_reason="stop", had_error=False, state=state)
    assert any("response_length_drop" in f for f in result.flags)


def test_high_error_rate_penalizes():
    state = QualityState()
    for _ in range(3):
        analyze(token_out=0, response_ms=100, finish_reason="", had_error=True, state=state)
    result = analyze(token_out=0, response_ms=100, finish_reason="", had_error=True, state=state)
    assert any("error_rate" in f for f in result.flags)
    assert result.quality_score < 75
