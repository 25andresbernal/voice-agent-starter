"""transfer_to_human: hands the call off instead of letting the model guess.

Real deployments would trigger a SIP REFER or a Twilio call-forward here.
This starter returns a structured intent the calling server can act on
(e.g. by ending the Realtime session and bridging the original SIP leg to
a human queue); wiring that up is deployment-specific and left to you.
"""

from __future__ import annotations

from typing import Any

PARAMETERS = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "description": "Short reason the call needs a human, e.g. 'angry customer' or "
            "'request outside policy'.",
        },
    },
    "required": ["reason"],
}


def transfer_to_human(arguments: dict[str, Any]) -> dict[str, Any]:
    reason = arguments["reason"]
    return {
        "status": "transfer_requested",
        "reason": reason,
        "note": "The calling server is responsible for bridging this call to a human queue.",
    }
