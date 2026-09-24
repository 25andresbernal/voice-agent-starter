from datetime import datetime, timezone

from voice_agent.transcript import ToolCall, TranscriptWriter, load_transcript


def test_write_and_load_round_trip(tmp_path):
    writer = TranscriptWriter(call_id="test-call-1", directory=tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    writer.write_turn("assistant", "Hello there.", now)
    writer.write_turn("user", "Hi.", now)
    writer.write_turn(
        "tool",
        "",
        now,
        tool_call=ToolCall(name="look_up_availability", arguments={"a": 1}, result={"b": 2}),
    )

    turns = load_transcript(writer.path)
    assert len(turns) == 3
    assert turns[0]["speaker"] == "assistant"
    assert turns[0]["turn"] == 1
    assert turns[1]["turn"] == 2
    assert turns[2]["tool_call"]["name"] == "look_up_availability"
    assert turns[2]["tool_call"]["result"] == {"b": 2}


def test_turn_numbers_increment_per_writer_instance(tmp_path):
    writer = TranscriptWriter(call_id="test-call-2", directory=tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for _ in range(5):
        writer.write_turn("user", "hi", now)
    turns = load_transcript(writer.path)
    assert [t["turn"] for t in turns] == [1, 2, 3, 4, 5]


def test_path_uses_call_id(tmp_path):
    writer = TranscriptWriter(call_id="abc123", directory=tmp_path)
    assert writer.path.name == "abc123.jsonl"
