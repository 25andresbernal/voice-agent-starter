"""Tool registry.

A tool is a plain Python callable plus the JSON schema that describes it to
the Realtime API. The registry is the single source of truth used in three
places: the session config sent to OpenAI's accept-call API, the agent loop
that dispatches `function_call` events, and the eval harness that checks
tool-call correctness against the same schemas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema, object type
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    @property
    def required_parameters(self) -> list[str]:
        return list(self.parameters.get("required", []))

    def to_openai_tool_def(self) -> dict[str, Any]:
        """The shape the Realtime API expects in session.tools."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def to_openai_tool_defs(self) -> list[dict[str, Any]]:
        return [t.to_openai_tool_def() for t in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool by name, returning its result dict.

        Never raises for a missing tool or a handler exception: both are
        turned into a `{"error": ...}` result so the agent loop can hand it
        back to the model as a normal function_call_output rather than
        crashing the call.
        """
        tool = self.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}
        missing = [p for p in tool.required_parameters if p not in arguments]
        if missing:
            return {"error": f"missing required arguments: {', '.join(missing)}"}
        try:
            return tool.handler(arguments)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            return {"error": f"tool handler raised: {exc}"}
