from voice_agent.outbound import build_create_call_request, build_outbound_twiml


def test_build_outbound_twiml_bridges_into_sip_uri():
    twiml = build_outbound_twiml("sip:proj_123@sip.api.openai.com;transport=tls")
    assert "<Dial><Sip>sip:proj_123@sip.api.openai.com;transport=tls</Sip></Dial>" in twiml


def test_build_create_call_request_shape():
    req = build_create_call_request(
        account_sid="AC123",
        to_number="+15555550123",
        from_number="+15555550199",
        sip_uri="sip:proj_123@sip.api.openai.com;transport=tls",
    )
    assert req["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Calls.json"
    assert req["data"]["To"] == "+15555550123"
    assert req["data"]["From"] == "+15555550199"
    assert "proj_123" in req["data"]["Twiml"]
