from pathlib import Path

from voice_agent import cli
from voice_agent.transcript import TRANSCRIPTS_DIR

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "transcripts"


def test_demo_command_runs_offline_and_prints_scorecard(capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_PROJECT_ID", raising=False)

    exit_code = cli.main(["demo"])
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "Simulated call complete" in out
    assert "Call quality scorecard" in out
    assert "Overall score" in out


def test_demo_command_writes_a_transcript_file(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    before = set(TRANSCRIPTS_DIR.glob("demo-*.jsonl"))
    cli.main(["demo"])
    after = set(TRANSCRIPTS_DIR.glob("demo-*.jsonl"))
    new_files = after - before
    assert len(new_files) == 1


def test_eval_command_scores_an_example_transcript(capsys):
    path = str(EXAMPLES / "example-good-oil-change-booking.jsonl")
    exit_code = cli.main(["eval", path])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Overall score: 100.0/100 (A)" in out


def test_eval_command_llm_judge_falls_back_to_fake_judge_without_key(capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = str(EXAMPLES / "example-good-oil-change-booking.jsonl")
    exit_code = cli.main(["eval", path, "--llm-judge"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "LLM judge score" in out
    assert "FakeJudge" in out


def test_serve_command_fails_fast_without_keys(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_PROJECT_ID", raising=False)
    exit_code = cli.main(["serve"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "OPENAI_API_KEY" in err


def test_call_command_fails_fast_without_keys(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    exit_code = cli.main(["call", "--to", "+15555550123"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "TWILIO_ACCOUNT_SID" in err
