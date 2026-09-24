from voice_agent.tools import build_default_registry


def test_registry_lists_all_three_tools():
    registry = build_default_registry()
    assert set(registry.names()) == {
        "look_up_availability",
        "book_appointment",
        "transfer_to_human",
    }


def test_look_up_availability_returns_three_distinct_slots():
    registry = build_default_registry()
    result = registry.call("look_up_availability", {"service": "massage", "date": "2026-09-25"})
    assert "error" not in result
    assert len(result["available_times"]) == 3
    assert len(set(result["available_times"])) == 3


def test_look_up_availability_is_deterministic():
    registry = build_default_registry()
    a = registry.call("look_up_availability", {"service": "haircut", "date": "2026-10-01"})
    b = registry.call("look_up_availability", {"service": "haircut", "date": "2026-10-01"})
    assert a == b


def test_book_appointment_returns_confirmation():
    registry = build_default_registry()
    result = registry.call(
        "book_appointment",
        {
            "service": "massage",
            "date": "2026-09-25",
            "time": "13:00",
            "customer_name": "Alex",
        },
    )
    assert result["status"] == "confirmed"
    assert result["booking_id"].startswith("bk_")


def test_transfer_to_human():
    registry = build_default_registry()
    result = registry.call("transfer_to_human", {"reason": "angry customer"})
    assert result["status"] == "transfer_requested"


def test_missing_required_argument_is_an_error_not_an_exception():
    registry = build_default_registry()
    result = registry.call("book_appointment", {"service": "massage"})
    assert "error" in result
    assert "date" in result["error"]


def test_unknown_tool_is_an_error_not_an_exception():
    registry = build_default_registry()
    result = registry.call("delete_all_bookings", {})
    assert "error" in result


def test_openai_tool_defs_shape():
    registry = build_default_registry()
    defs = registry.to_openai_tool_defs()
    assert len(defs) == 3
    for d in defs:
        assert d["type"] == "function"
        assert "name" in d
        assert "description" in d
        assert d["parameters"]["type"] == "object"
