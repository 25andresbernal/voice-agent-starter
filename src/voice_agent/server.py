"""FastAPI webhook server for inbound calls.

Flow (see realtime_client.py for the exact request/response shapes):

  Twilio trunk -> INVITE -> sip.api.openai.com
  OpenAI -> POST /webhook/openai-realtime  { type: "realtime.call.incoming", data: {...} }
  this server -> POST /v1/realtime/calls/{call_id}/accept
  this server -> open wss://api.openai.com/v1/realtime?call_id={call_id}
  AgentLoop consumes events on that socket until the call ends.

Run with `voice-agent serve`. Requires OPENAI_API_KEY and OPENAI_PROJECT_ID;
see .env.example. A public URL (e.g. an ngrok tunnel) is required so OpenAI
can reach the webhook -- see the README Quick start for real mode.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, Response

from .agent_loop import AgentLoop
from .config import Settings
from .realtime_client import (
    RealtimeWebSocketConnection,
    accept_call,
    build_session_config,
)
from .tools import ToolRegistry, build_default_registry
from .transcript import TranscriptWriter

logger = logging.getLogger("voice_agent.server")

DEFAULT_INSTRUCTIONS = (
    "You are a friendly phone agent for a small appointments business. Keep "
    "turns short -- one idea and at most one question at a time. Confirm "
    "details back to the caller before booking. Never end the call until "
    "the caller confirms they are done."
)


@dataclass
class IncomingCall:
    call_id: str
    sip_headers: dict[str, str]


def parse_incoming_webhook(payload: dict[str, Any]) -> IncomingCall | None:
    """Pure parsing of a realtime.call.incoming webhook body.

    Returns None for any other event type so the route can 200 and ignore
    events this server does not act on yet.
    """
    if payload.get("type") != "realtime.call.incoming":
        return None
    data = payload.get("data", {})
    call_id = data.get("call_id", "")
    headers = {h.get("name", ""): h.get("value", "") for h in data.get("sip_headers", [])}
    return IncomingCall(call_id=call_id, sip_headers=headers)


def create_app(
    settings: Settings | None = None, registry: ToolRegistry | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    registry = registry or build_default_registry()

    app = FastAPI(title="voice-agent-starter")
    app.state.settings = settings
    app.state.registry = registry

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook/openai-realtime")
    async def openai_realtime_webhook(request: Request) -> Response:
        payload = await request.json()
        incoming = parse_incoming_webhook(payload)
        if incoming is None:
            return Response(status_code=200)

        session_config = build_session_config(
            model=settings.realtime_model,
            voice=settings.realtime_voice,
            instructions=DEFAULT_INSTRUCTIONS,
            tool_defs=registry.to_openai_tool_defs(),
        )
        resp = await accept_call(incoming.call_id, session_config, api_key=settings.openai_api_key)
        if resp.status_code >= 300:
            logger.error("accept_call failed for %s: %s", incoming.call_id, resp.text)
            return Response(status_code=200)

        asyncio.create_task(_handle_call(incoming.call_id, settings, registry))
        return Response(status_code=200)

    return app


async def _handle_call(call_id: str, settings: Settings, registry: ToolRegistry) -> None:
    transcript = TranscriptWriter(call_id=call_id)
    async with RealtimeWebSocketConnection(call_id=call_id, api_key=settings.openai_api_key) as conn:
        loop = AgentLoop(connection=conn, registry=registry, transcript=transcript)
        try:
            await loop.run()
        except Exception:  # noqa: BLE001
            logger.exception("agent loop crashed for call %s", call_id)
