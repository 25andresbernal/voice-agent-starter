"""Command-line entry point: `voice-agent demo|serve|eval|call`."""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import datetime, timezone

from .agent_loop import AgentLoop
from .config import Settings
from .fake_realtime_client import FakeRealtimeConnection, build_demo_script
from .tools import build_default_registry
from .transcript import TranscriptWriter, load_transcript


def _cmd_demo(args: argparse.Namespace) -> int:
    """Run a full simulated call through the real agent loop, no network,
    no API keys, and score the resulting transcript."""
    from evals.scorecard import render_table, score_file

    call_id = f"demo-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"
    registry = build_default_registry()
    connection = FakeRealtimeConnection(script=build_demo_script())
    transcript = TranscriptWriter(call_id=call_id)
    loop = AgentLoop(connection=connection, registry=registry, transcript=transcript)

    asyncio.run(loop.run())

    print(f"Simulated call complete. Transcript written to {transcript.path}\n")
    with transcript.path.open(encoding="utf-8") as f:
        print(f.read().rstrip())

    print()
    result = score_file(transcript.path)
    print(render_table(result))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from evals.judge import get_judge
    from evals.scorecard import render_table, score_file

    result = score_file(args.transcript)
    print(render_table(result))

    if args.llm_judge:
        settings = Settings.from_env()
        judge = get_judge(use_llm_judge=True, api_key=settings.openai_api_key)
        if judge is not None:
            turns = load_transcript(args.transcript)
            jr = judge.score(turns)
            print()
            print(f"LLM judge score: {jr.score}/10")
            print(f"Rationale: {jr.rationale}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    problems = settings.validate_for_serve()
    if problems:
        print("Cannot start server, missing configuration:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nSee .env.example.", file=sys.stderr)
        return 1

    import uvicorn

    from .server import create_app

    app = create_app(settings)
    print(f"Webhook server listening on 0.0.0.0:{settings.port}")
    print("Configure this URL (behind a public tunnel) as your OpenAI webhook endpoint:")
    print("  <public-url>/webhook/openai-realtime")
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
    return 0


def _cmd_call(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    problems = settings.validate_for_outbound_call()
    if problems:
        print("Cannot place outbound call, missing configuration:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nSee .env.example.", file=sys.stderr)
        return 1

    import httpx

    from .outbound import build_create_call_request

    req = build_create_call_request(
        account_sid=settings.twilio_account_sid,
        to_number=args.to,
        from_number=settings.twilio_from_number,
        sip_uri=settings.sip_uri,
    )
    resp = httpx.post(
        req["url"],
        data=req["data"],
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
    )
    print(f"Twilio responded {resp.status_code}")
    print(resp.text)
    return 0 if resp.status_code < 300 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run an offline simulated call (no keys, no network)")
    demo.set_defaults(func=_cmd_demo)

    ev = sub.add_parser("eval", help="score a transcript JSONL file")
    ev.add_argument("transcript", help="path to a transcript .jsonl file")
    ev.add_argument(
        "--llm-judge",
        action="store_true",
        help="also run the optional LLM-judge rubric (off by default)",
    )
    ev.set_defaults(func=_cmd_eval)

    serve = sub.add_parser("serve", help="start the inbound webhook server (needs API keys)")
    serve.set_defaults(func=_cmd_serve)

    call = sub.add_parser("call", help="place an outbound call (needs Twilio + OpenAI keys)")
    call.add_argument("--to", required=True, help="destination phone number, e.g. +15555550123")
    call.set_defaults(func=_cmd_call)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
