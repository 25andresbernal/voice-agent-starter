"""Real Realtime API client: accepting SIP calls and streaming their events.

Implements the flow documented at
https://platform.openai.com/docs/guides/realtime-sip and
https://platform.openai.com/docs/guides/realtime-conversations
(fetched 2026-09-23):

1. Twilio's trunk origination URI points at
   sip:<project_id>@sip.api.openai.com;transport=tls. OpenAI receives the
   INVITE and POSTs a `realtime.call.incoming` webhook event to your
   configured endpoint with a `call_id` and the SIP headers.
2. Your server calls `POST /v1/realtime/calls/{call_id}/accept` with a
   session config (model, instructions, voice, tools) to answer the call,
   or `.../reject` to decline it.
3. Your server opens `wss://api.openai.com/v1/realtime?call_id={call_id}`
   to observe events on the now-live call and to send client events such
   as function_call_output and response.create.

This module does not use the OpenAI SDK so the wire format stays visible;
it is a thin httpx + websockets wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
import websockets

REALTIME_HTTP_BASE = "https://api.openai.com/v1/realtime"
REALTIME_WS_BASE = "wss://api.openai.com/v1/realtime"


def build_session_config(
    *,
    model: str,
    voice: str,
    instructions: str,
    tool_defs: list[dict[str, Any]],
) -> dict[str, Any]:
    """The payload for POST /v1/realtime/calls/{call_id}/accept."""
    return {
        "type": "realtime",
        "model": model,
        "instructions": instructions,
        "voice": voice,
        "tools": tool_defs,
    }


async def accept_call(
    call_id: str, session_config: dict[str, Any], *, api_key: str
) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.post(
            f"{REALTIME_HTTP_BASE}/calls/{call_id}/accept",
            headers={"Authorization": f"Bearer {api_key}"},
            json=session_config,
        )


async def reject_call(
    call_id: str, *, api_key: str, status_code: int = 603
) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.post(
            f"{REALTIME_HTTP_BASE}/calls/{call_id}/reject",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"status_code": status_code},
        )


@dataclass
class RealtimeWebSocketConnection:
    """Real implementation of the RealtimeConnection protocol used by
    AgentLoop, wrapping the call-monitoring WebSocket."""

    call_id: str
    api_key: str
    _ws: Any = None

    async def __aenter__(self) -> "RealtimeWebSocketConnection":
        self._ws = await websockets.connect(
            f"{REALTIME_WS_BASE}?call_id={self.call_id}",
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def send(self, event: dict[str, Any]) -> None:
        import json

        assert self._ws is not None, "connection not open; use 'async with'"
        await self._ws.send(json.dumps(event))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        import json

        assert self._ws is not None, "connection not open; use 'async with'"
        async for raw in self._ws:
            yield json.loads(raw)

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
