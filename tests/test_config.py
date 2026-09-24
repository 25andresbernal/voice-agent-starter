from voice_agent.config import Settings


def test_defaults_are_empty_and_do_not_raise():
    settings = Settings()
    assert settings.openai_api_key == ""
    assert settings.realtime_model == "gpt-realtime"


def test_from_env_reads_variables(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj_abc")
    monkeypatch.setenv("PORT", "9001")
    settings = Settings.from_env()
    assert settings.openai_api_key == "sk-test"
    assert settings.openai_project_id == "proj_abc"
    assert settings.port == 9001


def test_sip_uri_uses_project_id():
    settings = Settings(openai_project_id="proj_abc")
    assert settings.sip_uri == "sip:proj_abc@sip.api.openai.com;transport=tls"


def test_validate_for_serve_flags_missing_keys():
    settings = Settings()
    problems = settings.validate_for_serve()
    assert any("OPENAI_API_KEY" in p for p in problems)
    assert any("OPENAI_PROJECT_ID" in p for p in problems)


def test_validate_for_serve_passes_when_configured():
    settings = Settings(openai_api_key="sk-test", openai_project_id="proj_abc")
    assert settings.validate_for_serve() == []


def test_validate_for_outbound_call_requires_twilio_too():
    settings = Settings(openai_api_key="sk-test", openai_project_id="proj_abc")
    problems = settings.validate_for_outbound_call()
    assert any("TWILIO_ACCOUNT_SID" in p for p in problems)
