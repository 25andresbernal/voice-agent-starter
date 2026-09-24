"""Call-quality scorecard.

Scores a transcript JSONL file (the format written by
voice_agent.transcript.TranscriptWriter) against five heuristics a PM can
read and defend without an LLM in the loop:

  1. turn length      -- assistant turns should be short; phone callers
                          cannot hold a paragraph in their head.
  2. one question      -- at most one question per assistant turn, so the
     per turn            caller always knows what to answer.
  3. no premature close -- the agent should not say goodbye mid-conversation.
  4. tool-call          -- every tool call had its required arguments and
     correctness           did not return an error.
  5. response latency   -- how long the assistant took to respond after
                            each user turn.

Each heuristic produces a 0-100 sub-score; the overall score is their
unweighted average. The thresholds below are starting points for a phone
UX bar, not a scientific result -- tune them for your own product.

An optional LLM-judge rubric (evals/judge.py) can add a sixth, qualitative
score. It is off by default; see judge.py for why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CLOSING_PHRASES = [
    "have a great day",
    "have a good day",
    "have a wonderful day",
    "goodbye",
    "take care now",
    "bye now",
]

MAX_QUESTIONS_PER_TURN = 1
TURN_LENGTH_OK_WORDS = 40
TURN_LENGTH_ZERO_WORDS = 120
LATENCY_OK_MS = 1500
LATENCY_ZERO_MS = 5000


@dataclass
class MetricResult:
    label: str
    score: float  # 0-100
    detail: str


@dataclass
class ScorecardResult:
    transcript_path: str
    metrics: list[MetricResult] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        if not self.metrics:
            return 0.0
        return round(sum(m.score for m in self.metrics) / len(self.metrics), 1)

    @property
    def grade(self) -> str:
        s = self.overall_score
        if s >= 90:
            return "A"
        if s >= 80:
            return "B"
        if s >= 70:
            return "C"
        if s >= 60:
            return "D"
        return "F"


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _scale_down(value: float, ok_at: float, zero_at: float) -> float:
    """100 for value <= ok_at, linearly down to 0 at value >= zero_at."""
    if value <= ok_at:
        return 100.0
    if value >= zero_at:
        return 0.0
    return _clamp(100.0 * (zero_at - value) / (zero_at - ok_at))


def score_turn_length(turns: list[dict[str, Any]]) -> MetricResult:
    assistant_turns = [t for t in turns if t["speaker"] == "assistant" and t["text"]]
    if not assistant_turns:
        return MetricResult("Assistant turn length", 100.0, "no assistant turns")
    lengths = [len(t["text"].split()) for t in assistant_turns]
    avg = sum(lengths) / len(lengths)
    score = _scale_down(avg, TURN_LENGTH_OK_WORDS, TURN_LENGTH_ZERO_WORDS)
    return MetricResult(
        "Assistant turn length",
        round(score, 1),
        f"avg {avg:.1f} words/turn (target <= {TURN_LENGTH_OK_WORDS}), max {max(lengths)}",
    )


def score_one_question_per_turn(turns: list[dict[str, Any]]) -> MetricResult:
    assistant_turns = [t for t in turns if t["speaker"] == "assistant" and t["text"]]
    violations = [t for t in assistant_turns if t["text"].count("?") > MAX_QUESTIONS_PER_TURN]
    if not assistant_turns:
        return MetricResult("One question per turn", 100.0, "no assistant turns")
    score = _clamp(100.0 - 25.0 * len(violations))
    return MetricResult(
        "One question per turn",
        round(score, 1),
        f"{len(violations)} of {len(assistant_turns)} turns asked more than one question",
    )


def score_no_premature_close(turns: list[dict[str, Any]]) -> MetricResult:
    n = len(turns)
    flagged = []
    for i, t in enumerate(turns):
        if t["speaker"] != "assistant" or not t["text"]:
            continue
        text_lower = t["text"].lower()
        if any(phrase in text_lower for phrase in CLOSING_PHRASES):
            is_near_end = i >= n - 2
            if not is_near_end:
                flagged.append(t["turn"])
    score = 100.0 if not flagged else 0.0
    detail = (
        "no closing language before the caller was done"
        if not flagged
        else (f"closing language appeared early, at turn(s) {flagged}")
    )
    return MetricResult("No premature close", score, detail)


def score_tool_call_correctness(turns: list[dict[str, Any]]) -> MetricResult:
    tool_turns = [t for t in turns if t["speaker"] == "tool"]
    if not tool_turns:
        return MetricResult("Tool-call correctness", 100.0, "no tool calls in this transcript")
    ok = 0
    for t in tool_turns:
        result = (t.get("tool_call") or {}).get("result", {})
        if isinstance(result, dict) and "error" not in result:
            ok += 1
    score = 100.0 * ok / len(tool_turns)
    return MetricResult(
        "Tool-call correctness", round(score, 1), f"{ok}/{len(tool_turns)} tool calls succeeded"
    )


def score_response_latency(turns: list[dict[str, Any]]) -> MetricResult:
    latencies = [
        t["latency_ms"]
        for t in turns
        if t["speaker"] == "assistant" and t.get("latency_ms") is not None
    ]
    if not latencies:
        return MetricResult("Response latency", 100.0, "no measurable latency in this transcript")
    avg = sum(latencies) / len(latencies)
    score = _scale_down(avg, LATENCY_OK_MS, LATENCY_ZERO_MS)
    return MetricResult(
        "Response latency",
        round(score, 1),
        f"avg {avg:.0f} ms (target <= {LATENCY_OK_MS} ms), max {max(latencies)} ms",
    )


def score_transcript(turns: list[dict[str, Any]], transcript_path: str = "") -> ScorecardResult:
    result = ScorecardResult(transcript_path=transcript_path)
    result.metrics = [
        score_turn_length(turns),
        score_one_question_per_turn(turns),
        score_no_premature_close(turns),
        score_tool_call_correctness(turns),
        score_response_latency(turns),
    ]
    return result


def render_table(result: ScorecardResult) -> str:
    label_w = max(len(m.label) for m in result.metrics) + 2
    lines = [f"Call quality scorecard: {result.transcript_path}", "-" * 78]
    for m in result.metrics:
        lines.append(f"{m.label:<{label_w}} {m.score:>5.1f}  {m.detail}")
    lines.append("-" * 78)
    lines.append(f"Overall score: {result.overall_score}/100 ({result.grade})")
    return "\n".join(lines)


def score_file(path: str | Path) -> ScorecardResult:
    from voice_agent.transcript import load_transcript

    turns = load_transcript(path)
    return score_transcript(turns, transcript_path=str(path))
