"""look_up_availability: a deterministic fake scheduling backend.

Real deployments would call out to a booking system here. This starter uses
a small deterministic generator so the demo and tests never need network
access or a database, while still behaving like a real lookup (same inputs
always produce the same slots).
"""

from __future__ import annotations

import hashlib
from typing import Any

PARAMETERS = {
    "type": "object",
    "properties": {
        "service": {
            "type": "string",
            "description": "The service being booked, e.g. 'massage' or 'consultation'.",
        },
        "date": {
            "type": "string",
            "description": "Requested date in YYYY-MM-DD format.",
        },
    },
    "required": ["service", "date"],
}

_SLOT_POOL = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"]


def look_up_availability(arguments: dict[str, Any]) -> dict[str, Any]:
    service = arguments["service"]
    date = arguments["date"]

    # Deterministic pseudo-random pick of 3 open slots for this
    # (service, date) pair, so repeated calls and tests are stable.
    seed = hashlib.sha256(f"{service}:{date}".encode()).hexdigest()
    offsets = sorted({int(seed[i : i + 2], 16) % len(_SLOT_POOL) for i in range(0, 6, 2)})
    slots = [_SLOT_POOL[i] for i in offsets] or [_SLOT_POOL[0]]

    return {
        "service": service,
        "date": date,
        "available_times": slots,
    }
