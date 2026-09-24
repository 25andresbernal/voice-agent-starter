"""A scripted stand-in for the Realtime API, used by `voice-agent demo` and
by the test suite.

FakeRealtimeConnection implements the same RealtimeConnection protocol as
the real WebSocket client (realtime_client.py), so AgentLoop cannot tell
the difference: this is what lets the offline demo run the real agent loop,
the real tool registry, and the real transcript writer with no network
access and no API key.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

_EPOCH = datetime(2026, 9, 23, 15, 0, 0, tzinfo=timezone.utc)


@dataclass
class FakeRealtimeConnection:
    """Replays a fixed list of server events; records client events sent."""

    script: list[dict[str, Any]]
    sent: list[dict[str, Any]] = field(default_factory=list)
    _clock: datetime = field(default=_EPOCH)

    async def send(self, event: dict[str, Any]) -> None:
        self.sent.append(event)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for event in self.script:
            delay_ms = event.get("_sim_delay_ms", 0)
            self._clock = self._clock + timedelta(milliseconds=delay_ms)
            yield {k: v for k, v in event.items() if k != "_sim_delay_ms"}

    def now(self) -> datetime:
        return self._clock


def _user_item(text: str) -> dict[str, Any]:
    return {
        "type": "conversation.item.created",
        "item": {
            "role": "user",
            "content": [{"type": "input_audio", "transcript": text}],
        },
    }


def _assistant_transcript(text: str, delay_ms: int) -> dict[str, Any]:
    return {
        "type": "response.audio_transcript.done",
        "transcript": text,
        "_sim_delay_ms": delay_ms,
    }


def _function_call(call_id: str, name: str, arguments_json: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "call_id": call_id, "name": name},
        },
        {
            "type": "response.function_call_arguments.done",
            "call_id": call_id,
            "arguments": arguments_json,
            "_sim_delay_ms": 150,
        },
    ]


def build_demo_script() -> list[dict[str, Any]]:
    """A full, realistic inbound-call conversation for a fictional
    appointment-booking business. Industry-neutral, no real names.

    Exercises both tools end to end: a lookup followed by a booking, so the
    eval harness has something real to score.
    """
    script: list[dict[str, Any]] = []
    script.append(
        _assistant_transcript(
            "Thanks for calling Riverside Wellness Studio. How can I help you today?",
            delay_ms=0,
        )
    )
    script.append(_user_item("Hi, I'd like to book a massage for this Friday."))
    script.extend(
        _function_call(
            "call_lookup_1",
            "look_up_availability",
            '{"service": "massage", "date": "2026-09-25"}',
        )
    )
    script.append(
        _assistant_transcript(
            "I have openings Friday at ten a.m., one p.m., and three p.m. "
            "Which time works best for you?",
            delay_ms=400,
        )
    )
    script.append(_user_item("One p.m. works great. My name is Jordan."))
    script.extend(
        _function_call(
            "call_book_1",
            "book_appointment",
            '{"service": "massage", "date": "2026-09-25", "time": "13:00", '
            '"customer_name": "Jordan"}',
        )
    )
    script.append(
        _assistant_transcript(
            "You're all set for one p.m. on Friday, Jordan. You'll get a text "
            "confirmation shortly. Is there anything else I can help with?",
            delay_ms=350,
        )
    )
    script.append(_user_item("No, that's everything. Thank you!"))
    script.append(
        _assistant_transcript(
            "You're welcome. Thanks for calling Riverside Wellness Studio, have a great day.",
            delay_ms=300,
        )
    )
    return script
