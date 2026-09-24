"""Optional LLM-judge rubric.

The five scorecard.py heuristics are cheap, deterministic, and defensible
without an LLM in the loop -- that is deliberate, since a scorecard a PM
cannot explain is not trustworthy. This module adds an optional sixth,
qualitative score for teams that want it.

It is OFF by default (the `voice-agent eval` CLI only uses it when passed
--llm-judge) because it costs money, adds latency, and its numbers are not
reproducible run to run. Tests never call the real OpenAI API: they use
FakeJudge, a deterministic stand-in, which is also what a live run falls
back to if --llm-judge is passed without an OPENAI_API_KEY configured.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

RUBRIC_PROMPT = """You are grading one phone call transcript between an AI voice agent \
and a caller. Score the call from 0 to 10 on overall quality: did the agent sound \
natural, stay on topic, and resolve the caller's request without confusion or \
unnecessary repetition?

Respond with a JSON object only, of the form:
{{"score": <number 0-10>, "rationale": "<one paragraph, plain language>"}}

Transcript:
{transcript}
"""


@dataclass
class JudgeResult:
    score: float  # 0-10
    rationale: str


class Judge(Protocol):
    def score(self, turns: list[dict[str, Any]]) -> JudgeResult: ...


class FakeJudge:
    """Deterministic stand-in judge. No network access, no API key.

    Used by the test suite, and used automatically as a fallback when
    --llm-judge is requested but no OPENAI_API_KEY is configured, so an
    eval run never hangs or fails outright on a missing credential.
    """

    def score(self, turns: list[dict[str, Any]]) -> JudgeResult:
        assistant_turns = [t for t in turns if t["speaker"] == "assistant" and t["text"]]
        tool_turns = [t for t in turns if t["speaker"] == "tool"]

        base = 7.0
        if tool_turns:
            base += 1.0
        if len(assistant_turns) >= 3:
            base += 1.0
        score = min(base, 10.0)

        return JudgeResult(
            score=score,
            rationale=(
                "FakeJudge: a deterministic stand-in, not a real quality "
                "assessment. It rewards transcripts that use at least one "
                "tool call and have a multi-turn conversation. Configure "
                "OPENAI_API_KEY and pass --llm-judge for an actual "
                "LLM-graded score."
            ),
        )


class OpenAIJudge:
    """Real judge: one chat completion call, graded against RUBRIC_PROMPT."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    def score(self, turns: list[dict[str, Any]]) -> JudgeResult:
        import httpx

        transcript_text = "\n".join(
            f"{t['speaker']}: {t['text']}" for t in turns if t.get("text")
        )
        prompt = RUBRIC_PROMPT.format(transcript=transcript_text)

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return JudgeResult(score=float(data["score"]), rationale=str(data["rationale"]))


def get_judge(*, use_llm_judge: bool, api_key: str) -> Judge | None:
    """None means "do not run a judge" -- the default. Only returns a judge
    when the caller opted in with --llm-judge."""
    if not use_llm_judge:
        return None
    if api_key:
        return OpenAIJudge(api_key=api_key)
    return FakeJudge()
