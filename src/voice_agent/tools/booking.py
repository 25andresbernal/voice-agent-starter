"""book_appointment: confirms a slot and returns a booking id.

Same reasoning as availability.py: a deterministic fake so the offline demo
and tests are self-contained. Swap `book_appointment` for a real call to
your scheduling system's API; the JSON schema and the agent loop do not
need to change.
"""

from __future__ import annotations

import hashlib
from typing import Any

PARAMETERS = {
    "type": "object",
    "properties": {
        "service": {"type": "string", "description": "The service being booked."},
        "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
        "time": {"type": "string", "description": "Time in HH:MM 24-hour format."},
        "customer_name": {"type": "string", "description": "Name to book the appointment under."},
    },
    "required": ["service", "date", "time", "customer_name"],
}


def book_appointment(arguments: dict[str, Any]) -> dict[str, Any]:
    service = arguments["service"]
    date = arguments["date"]
    time = arguments["time"]
    customer_name = arguments["customer_name"]

    booking_id = (
        "bk_" + hashlib.sha256(f"{service}:{date}:{time}:{customer_name}".encode()).hexdigest()[:10]
    )

    return {
        "status": "confirmed",
        "booking_id": booking_id,
        "service": service,
        "date": date,
        "time": time,
        "customer_name": customer_name,
    }
