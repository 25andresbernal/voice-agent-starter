"""JSONL call transcripts.

One line per turn. A turn is one of: assistant speech, user speech, a tool
call (with its arguments and result), or a system note (call start/end).
This is the on-disk contract the eval harness in evals/scorecard.py reads,
so keep it stable and documented here.

Schema per line:
    call_id     str   stable id for the whole call
    turn        int   1-indexed, increases by one per line
    speaker     str   "assistant" | "user" | "tool" | "system"
    text        str   spoken/displayed text for this turn ("" for pure tool turns)
    timestamp   str   ISO-8601 UTC timestamp
    tool_call   dict | null   present only for speaker == "tool":
                    {"name": str, "arguments": dict, "result": dict}
    latency_ms  int | null    for "assistant" turns, time since the prior
                    "user" turn ended. Null when there is no prior user turn
                    to measure from (e.g. the opening greeting).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

Speaker = Literal["assistant", "user", "tool", "system"]

TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "transcripts"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class Turn:
    call_id: str
    turn: int
    speaker: Speaker
    text: str
    timestamp: str
    tool_call: ToolCall | None = None
    latency_ms: int | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class TranscriptWriter:
    """Appends turns to transcripts/<call_id>.jsonl as a call progresses."""

    call_id: str
    directory: Path = field(default_factory=lambda: TRANSCRIPTS_DIR)
    _next_turn: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.directory / f"{self.call_id}.jsonl"

    def write_turn(
        self,
        speaker: Speaker,
        text: str,
        timestamp: datetime,
        tool_call: ToolCall | None = None,
        latency_ms: int | None = None,
    ) -> Turn:
        turn = Turn(
            call_id=self.call_id,
            turn=self._next_turn,
            speaker=speaker,
            text=text,
            timestamp=timestamp.isoformat(),
            tool_call=tool_call,
            latency_ms=latency_ms,
        )
        self._next_turn += 1
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_json(), ensure_ascii=False) + "\n")
        return turn


def load_transcript(path: str | Path) -> list[dict[str, Any]]:
    """Read a transcript JSONL file into a list of turn dicts."""
    turns: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            turns.append(json.loads(line))
    return turns
