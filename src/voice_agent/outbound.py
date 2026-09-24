"""Outbound calling: a thin wrapper, documented rather than fully built out.

Inbound is the fully implemented path in this starter (webhook -> accept ->
WebSocket -> agent loop). Outbound reuses the same trunk in the other
direction: Twilio places a call and immediately dials it into the same
OpenAI SIP endpoint, so the call arrives at OpenAI exactly as an inbound
call would and is handled by the same webhook and agent loop.

This module builds the TwiML and the Twilio REST request for that; it does
not add a second, parallel event-handling path.
"""

from __future__ import annotations

from typing import Any

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def build_outbound_twiml(sip_uri: str) -> str:
    """TwiML that bridges the new outbound call straight into the OpenAI
    Realtime SIP endpoint. Twilio requests this document once the callee
    answers.
    """
    return f'<Response><Dial><Sip>{sip_uri}</Sip></Dial></Response>'


def build_create_call_request(
    *,
    account_sid: str,
    to_number: str,
    from_number: str,
    sip_uri: str,
) -> dict[str, Any]:
    """The HTTP request Twilio's Calls API needs to place the call.

    Returned as a plain dict (url, auth, data) rather than issued directly,
    so this is unit-testable without network access. `voice_agent.cli`
    issues the actual POST with httpx when TWILIO_* credentials are present.
    """
    return {
        "url": f"{TWILIO_API_BASE}/Accounts/{account_sid}/Calls.json",
        "data": {
            "To": to_number,
            "From": from_number,
            "Twiml": build_outbound_twiml(sip_uri),
        },
    }
