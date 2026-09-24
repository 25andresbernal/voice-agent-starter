from fastapi.testclient import TestClient

from voice_agent.config import Settings
from voice_agent.server import create_app, parse_incoming_webhook


def test_parse_incoming_webhook_extracts_call_id_and_headers():
    payload = {
        "object": "event",
        "id": "evt_1",
        "type": "realtime.call.incoming",
        "data": {
            "call_id": "call_abc",
            "sip_headers": [
                {"name": "From", "value": "sip:+15555550123@sip.example.com"},
                {"name": "To", "value": "sip:+15555550199@sip.example.com"},
            ],
        },
    }
    incoming = parse_incoming_webhook(payload)
    assert incoming is not None
    assert incoming.call_id == "call_abc"
    assert incoming.sip_headers["From"] == "sip:+15555550123@sip.example.com"


def test_parse_incoming_webhook_ignores_other_event_types():
    assert parse_incoming_webhook({"type": "some.other.event", "data": {}}) is None


def test_health_endpoint():
    settings = Settings(openai_api_key="sk-test", openai_project_id="proj_abc")
    app = create_app(settings=settings)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_ignores_non_incoming_events_without_calling_openai():
    settings = Settings(openai_api_key="sk-test", openai_project_id="proj_abc")
    app = create_app(settings=settings)
    client = TestClient(app)
    resp = client.post("/webhook/openai-realtime", json={"type": "something.else", "data": {}})
    assert resp.status_code == 200
