"""The agent loop: the one piece of code that both `demo` and `serve` run.

This is the core design decision of this starter (see docs/design-notes.md):
the loop only knows about Realtime API server/client events, never about
Twilio, SIP, or WebSockets directly. It is handed a `RealtimeConnection` --
either a real WebSocket wrapper (realtime_client.py) or a scripted fake
(fake_realtime_client.py) -- and drives the same tool-calling and transcript
logic either way. That is what lets `voice-agent demo` exercise real
production code paths with zero network access.

Event names and shapes follow the OpenAI Realtime API as documented at
https://platform.openai.com/docs/guides/realtime-conversations and
https://platform.openai.com/docs/guides/realtime-sip (fetched 2026-09-23):

  response.output_item.added        -- a new item started; for function
                                        calls this carries call_id and name
                                        before arguments have streamed in
  response.function_call_arguments.delta  -- streamed argument JSON chunk
  response.function_call_arguments.done   -- full argument JSON string,
                                        keyed by call_id
  response.audio_transcript.done    -- assistant's spoken turn, as text
  conversation.item.created         -- includes user turns (with a
                                        transcript) when using input audio
                                        transcription
  response.done                     -- a model turn fully finished

Client events sent back:
  conversation.item.create (type function_call_output) -- tool result
  response.create                                        -- resume the model
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .tools import ToolRegistry
from .transcript import ToolCall, TranscriptWriter


class RealtimeConnection(Protocol):
    """What the agent loop needs from a Realtime API connection.

    Implemented for real by RealtimeWebSocketConnection (realtime_client.py)
    and for tests/demo by FakeRealtimeConnection (fake_realtime_client.py).
    """

    async def send(self, event: dict[str, Any]) -> None: ...

    def events(self) -> AsyncIterator[dict[str, Any]]: ...

    def now(self) -> datetime:
        """Current time for transcript timestamps.

        A real connection returns wall-clock time. A fake connection can
        return a fabricated, steadily advancing clock so demo transcripts
        show plausible (but deterministic) latency numbers without ever
        calling asyncio.sleep.
        """
        ...


@dataclass
class _PendingCall:
    name: str
    arguments_json: str = ""


@dataclass
class AgentLoop:
    """Consumes Realtime API events for one call, writes the transcript,
    and dispatches tool calls through a ToolRegistry."""

    connection: RealtimeConnection
    registry: ToolRegistry
    transcript: TranscriptWriter
    _pending_calls: dict[str, _PendingCall] = field(default_factory=dict)
    _last_user_turn_at: datetime | None = None

    async def run(self) -> None:
        async for event in self.connection.events():
            await self._handle_event(event)

    async def _handle_event(self, event: dict[str, Any]) -> None:
        etype = event.get("type")

        if etype == "conversation.item.created":
            await self._handle_item_created(event)
        elif etype == "response.output_item.added":
            self._handle_output_item_added(event)
        elif etype == "response.function_call_arguments.delta":
            self._handle_arguments_delta(event)
        elif etype == "response.function_call_arguments.done":
            await self._handle_arguments_done(event)
        elif etype == "response.audio_transcript.done":
            self._handle_assistant_transcript(event)
        # response.done, session.created, and other bookkeeping events are
        # intentionally ignored here; a production system would log them.

    async def _handle_item_created(self, event: dict[str, Any]) -> None:
        item = event.get("item", {})
        if item.get("role") != "user":
            return
        text = _extract_text(item)
        if not text:
            return
        now = self.connection.now()
        self._last_user_turn_at = now
        self.transcript.write_turn(speaker="user", text=text, timestamp=now)

    def _handle_output_item_added(self, event: dict[str, Any]) -> None:
        item = event.get("item", {})
        if item.get("type") != "function_call":
            return
        call_id = item.get("call_id")
        name = item.get("name")
        if call_id and name:
            self._pending_calls[call_id] = _PendingCall(name=name)

    def _handle_arguments_delta(self, event: dict[str, Any]) -> None:
        call_id = event.get("call_id")
        delta = event.get("delta", "")
        pending = self._pending_calls.get(call_id) if call_id else None
        if pending is not None:
            pending.arguments_json += delta

    async def _handle_arguments_done(self, event: dict[str, Any]) -> None:
        import json

        call_id = event.get("call_id")
        if not call_id:
            return
        pending = self._pending_calls.pop(call_id, None)
        # The done event carries the full arguments string regardless of
        # whether any delta events were seen, so prefer it when present.
        arguments_json = event.get("arguments") or (pending.arguments_json if pending else "")
        name = pending.name if pending else event.get("name", "unknown_tool")

        try:
            arguments = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            arguments = {}

        result = self.registry.call(name, arguments)

        now = self.connection.now()
        self.transcript.write_turn(
            speaker="tool",
            text="",
            timestamp=now,
            tool_call=ToolCall(name=name, arguments=arguments, result=result),
        )

        await self.connection.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                },
            }
        )
        await self.connection.send({"type": "response.create"})

    def _handle_assistant_transcript(self, event: dict[str, Any]) -> None:
        text = event.get("transcript", "")
        if not text:
            return
        now = self.connection.now()
        latency_ms = None
        if self._last_user_turn_at is not None:
            latency_ms = int((now - self._last_user_turn_at).total_seconds() * 1000)
        self.transcript.write_turn(
            speaker="assistant", text=text, timestamp=now, latency_ms=latency_ms
        )


def _extract_text(item: dict[str, Any]) -> str:
    """Pull the transcript text out of a conversation.item's content list.

    The Realtime API represents user speech as content parts with type
    "input_audio" (transcript field) or "input_text" (text field).
    """
    for part in item.get("content", []):
        if part.get("type") == "input_audio" and part.get("transcript"):
            return part["transcript"]
        if part.get("type") == "input_text" and part.get("text"):
            return part["text"]
    return ""
