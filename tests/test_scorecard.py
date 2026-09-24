from pathlib import Path

from evals.scorecard import score_file, score_transcript

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "transcripts"


def _metric(result, label):
    return next(m for m in result.metrics if m.label == label)


def test_good_call_scores_perfectly():
    result = score_file(EXAMPLES / "example-good-oil-change-booking.jsonl")
    assert result.overall_score == 100.0
    assert result.grade == "A"


def test_long_winded_agent_is_penalized_on_turn_length_only():
    result = score_file(EXAMPLES / "example-long-winded-agent.jsonl")
    assert _metric(result, "Assistant turn length").score < 100.0
    assert _metric(result, "No premature close").score == 100.0
    assert _metric(result, "One question per turn").score == 100.0


def test_multi_question_turn_is_penalized():
    result = score_file(EXAMPLES / "example-multi-question-turn.jsonl")
    assert _metric(result, "One question per turn").score < 100.0
    assert "1 of" in _metric(result, "One question per turn").detail


def test_premature_close_scores_zero_on_that_metric():
    result = score_file(EXAMPLES / "example-premature-close.jsonl")
    assert _metric(result, "No premature close").score == 0.0
    assert result.overall_score < 100.0


def test_tool_call_error_lowers_tool_correctness_only():
    result = score_file(EXAMPLES / "example-tool-call-error.jsonl")
    m = _metric(result, "Tool-call correctness")
    assert m.score == 50.0
    assert "1/2" in m.detail


def test_score_transcript_with_no_turns_is_well_defined():
    result = score_transcript([], transcript_path="empty")
    assert result.overall_score == 100.0


def test_score_transcript_handles_no_tool_calls():
    turns = [
        {
            "call_id": "x",
            "turn": 1,
            "speaker": "assistant",
            "text": "Hello, how can I help?",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "tool_call": None,
            "latency_ms": None,
        }
    ]
    result = score_transcript(turns)
    m = next(m for m in result.metrics if m.label == "Tool-call correctness")
    assert m.score == 100.0
    assert "no tool calls" in m.detail
