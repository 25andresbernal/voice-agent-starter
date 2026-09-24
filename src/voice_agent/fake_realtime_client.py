"""A scripted stand-in for the Realtime API, used by `voice-agent demo` and
by the test suite.

FakeRealtimeConnection implements the same RealtimeConnection protocol as
the real WebSocket client (realtime_client.py), so AgentLoop cannot tell
the difference: this is what lets the offline demo run the real agent loop,
the real tool registry, and the real transcript writer with no network
access and no API key.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .tools.availability import look_up_availability

_EPOCH = datetime(2026, 9, 23, 15, 0, 0, tzinfo=timezone.utc)

# 24-hour "HH:MM" -> spoken form, for the fixed slot pool in tools/availability.py.
_SPOKEN_TIME = {
    "09:00": "nine a.m.",
    "10:00": "ten a.m.",
    "11:00": "eleven a.m.",
    "13:00": "one p.m.",
    "14:00": "two p.m.",
    "15:00": "three p.m.",
    "16:00": "four p.m.",
}


def _spoken_time(time_24h: str) -> str:
    return _SPOKEN_TIME.get(time_24h, time_24h)


def _spoken_list(times_24h: list[str]) -> str:
    words = [_spoken_time(t) for t in times_24h]
    if len(words) == 1:
        return words[0]
    if len(words) == 2:
        return f"{words[0]} and {words[1]}"
    return ", ".join(words[:-1]) + f", and {words[-1]}"


def _end_sentence(clause: str) -> str:
    """Add a sentence-ending period unless the clause already ends in one
    (e.g. because it ends in "a.m." or "p.m."), so composed sentences never
    get a doubled period."""
    return clause if clause.endswith((".", "!", "?")) else clause + "."


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

    The assistant's spoken lines are generated from the *actual* tool
    output (by calling the same deterministic tool function the agent loop
    will call later with identical arguments), not typed by hand, so the
    spoken slot list and the booked time can never drift out of sync with
    what the transcript's tool-call turns actually recorded.
    """
    service, date = "massage", "2026-09-25"
    availability = look_up_availability({"service": service, "date": date})
    available_times = availability["available_times"]
    chosen_time = available_times[-1]
    customer_name = "Jordan"

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
            json.dumps({"service": service, "date": date}),
        )
    )
    slots_clause = _end_sentence(f"I have openings Friday at {_spoken_list(available_times)}")
    script.append(
        _assistant_transcript(
            f"{slots_clause} Which time works best for you?",
            delay_ms=400,
        )
    )
    chosen_time_spoken = _spoken_time(chosen_time)
    chosen_time_clause = chosen_time_spoken[0].upper() + chosen_time_spoken[1:]
    script.append(_user_item(f"{chosen_time_clause} works great. My name is {customer_name}."))
    script.extend(
        _function_call(
            "call_book_1",
            "book_appointment",
            json.dumps(
                {
                    "service": service,
                    "date": date,
                    "time": chosen_time,
                    "customer_name": customer_name,
                }
            ),
        )
    )
    script.append(
        _assistant_transcript(
            f"You're all set for {_spoken_time(chosen_time)} on Friday, {customer_name}. "
            "You'll get a text confirmation shortly. Is there anything else I can help with?",
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
