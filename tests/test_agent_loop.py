import pytest

from voice_agent.agent_loop import AgentLoop
from voice_agent.fake_realtime_client import FakeRealtimeConnection, build_demo_script
from voice_agent.tools import build_default_registry
from voice_agent.transcript import TranscriptWriter, load_transcript


@pytest.mark.asyncio
async def test_agent_loop_runs_full_demo_script(tmp_path):
    connection = FakeRealtimeConnection(script=build_demo_script())
    registry = build_default_registry()
    transcript = TranscriptWriter(call_id="loop-test", directory=tmp_path)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    await loop.run()

    turns = load_transcript(transcript.path)
    speakers = [t["speaker"] for t in turns]

    assert speakers.count("assistant") == 4
    assert speakers.count("user") == 3
    assert speakers.count("tool") == 2


@pytest.mark.asyncio
async def test_agent_loop_invokes_real_tool_and_reports_result(tmp_path):
    connection = FakeRealtimeConnection(script=build_demo_script())
    registry = build_default_registry()
    transcript = TranscriptWriter(call_id="loop-test-2", directory=tmp_path)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    await loop.run()

    turns = load_transcript(transcript.path)
    tool_turns = [t for t in turns if t["speaker"] == "tool"]
    names = [t["tool_call"]["name"] for t in tool_turns]
    assert names == ["look_up_availability", "book_appointment"]
    for t in tool_turns:
        assert "error" not in t["tool_call"]["result"]


@pytest.mark.asyncio
async def test_agent_loop_sends_function_call_output_and_response_create(tmp_path):
    connection = FakeRealtimeConnection(script=build_demo_script())
    registry = build_default_registry()
    transcript = TranscriptWriter(call_id="loop-test-3", directory=tmp_path)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    await loop.run()

    sent_types = [e["type"] for e in connection.sent]
    assert sent_types.count("conversation.item.create") == 2
    assert sent_types.count("response.create") == 2

    first_output = connection.sent[0]
    assert first_output["item"]["type"] == "function_call_output"
    assert first_output["item"]["call_id"] == "call_lookup_1"


@pytest.mark.asyncio
async def test_agent_loop_records_latency_on_assistant_turns_after_user_turns(tmp_path):
    connection = FakeRealtimeConnection(script=build_demo_script())
    registry = build_default_registry()
    transcript = TranscriptWriter(call_id="loop-test-4", directory=tmp_path)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    await loop.run()

    turns = load_transcript(transcript.path)
    assistant_turns = [t for t in turns if t["speaker"] == "assistant"]
    # The opening greeting has no prior user turn, so it is latency_ms=None;
    # every assistant turn after that follows a user turn.
    assert assistant_turns[0]["latency_ms"] is None
    assert all(t["latency_ms"] is not None for t in assistant_turns[1:])
    assert all(t["latency_ms"] >= 0 for t in assistant_turns[1:])


@pytest.mark.asyncio
async def test_agent_loop_handles_unknown_tool_without_crashing(tmp_path):
    script = [
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "call_id": "call_x", "name": "does_not_exist"},
        },
        {
            "type": "response.function_call_arguments.done",
            "call_id": "call_x",
            "arguments": "{}",
        },
    ]
    connection = FakeRealtimeConnection(script=script)
    registry = build_default_registry()
    transcript = TranscriptWriter(call_id="loop-test-5", directory=tmp_path)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    await loop.run()

    turns = load_transcript(transcript.path)
    assert turns[0]["tool_call"]["result"] == {"error": "unknown tool: does_not_exist"}
