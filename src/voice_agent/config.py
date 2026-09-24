"""Environment-driven configuration.

Every field here maps 1:1 to a variable documented in .env.example. Nothing
in this module touches the network or raises on import: `demo` and `eval`
must work with none of these set. `validate_for_serve()` is the one place
that enforces what `serve` actually needs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = ""
    openai_project_id: str = ""
    openai_webhook_secret: str = ""
    realtime_model: str = "gpt-realtime"
    realtime_voice: str = "alloy"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    port: int = 8000
    public_base_url: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
            openai_webhook_secret=os.environ.get("OPENAI_WEBHOOK_SECRET", ""),
            realtime_model=os.environ.get("REALTIME_MODEL", "gpt-realtime"),
            realtime_voice=os.environ.get("REALTIME_VOICE", "alloy"),
            twilio_account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.environ.get("TWILIO_FROM_NUMBER", ""),
            port=int(os.environ.get("PORT", "8000")),
            public_base_url=os.environ.get("PUBLIC_BASE_URL", ""),
        )

    @property
    def sip_uri(self) -> str:
        """The SIP trunk origination target for this project.

        See https://platform.openai.com/docs/guides/realtime-sip
        """
        return f"sip:{self.openai_project_id}@sip.api.openai.com;transport=tls"

    def validate_for_serve(self) -> list[str]:
        """Return a list of human-readable problems; empty means ready to serve."""
        problems = []
        if not self.openai_api_key:
            problems.append("OPENAI_API_KEY is not set")
        if not self.openai_project_id:
            problems.append("OPENAI_PROJECT_ID is not set")
        return problems

    def validate_for_outbound_call(self) -> list[str]:
        problems = self.validate_for_serve()
        if not self.twilio_account_sid:
            problems.append("TWILIO_ACCOUNT_SID is not set")
        if not self.twilio_auth_token:
            problems.append("TWILIO_AUTH_TOKEN is not set")
        if not self.twilio_from_number:
            problems.append("TWILIO_FROM_NUMBER is not set")
        return problems
