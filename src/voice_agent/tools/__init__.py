"""Default tool registry for the voice agent."""

from __future__ import annotations

from .availability import PARAMETERS as AVAILABILITY_PARAMETERS
from .availability import look_up_availability
from .booking import PARAMETERS as BOOKING_PARAMETERS
from .booking import book_appointment
from .registry import Tool, ToolRegistry
from .transfer import PARAMETERS as TRANSFER_PARAMETERS
from .transfer import transfer_to_human


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="look_up_availability",
            description="Look up open appointment times for a service on a given date.",
            parameters=AVAILABILITY_PARAMETERS,
            handler=look_up_availability,
        )
    )
    registry.register(
        Tool(
            name="book_appointment",
            description="Book an appointment for a customer at a specific date and time.",
            parameters=BOOKING_PARAMETERS,
            handler=book_appointment,
        )
    )
    registry.register(
        Tool(
            name="transfer_to_human",
            description="Request a transfer of the call to a human agent.",
            parameters=TRANSFER_PARAMETERS,
            handler=transfer_to_human,
        )
    )
    return registry


__all__ = ["ToolRegistry", "Tool", "build_default_registry"]
