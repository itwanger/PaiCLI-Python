from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from paicli.config import PaiCliConfig

DangerLevel = Literal["safe", "medium", "high"]
ToolDecision = Literal["approve", "deny", "skip"]


@dataclass(slots=True)
class ToolResult:
    content: str
    is_error: bool = False
    display_summary: str | None = None
    tool_use_id: str | None = None


@dataclass(slots=True)
class ToolContext:
    cwd: str
    config: PaiCliConfig
    approval_callback: Callable[[dict[str, Any]], Awaitable[ToolDecision] | ToolDecision] | None = (
        None
    )
    skill_context_buffer: Any | None = None


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    is_read_only: bool = True
    is_concurrency_safe: bool = True
    danger_level: DangerLevel = "safe"
    requires_approval: bool = False
    timeout: float = 60.0
    required_keys: list[str] = field(default_factory=list)

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f'tool "{self.name}" input must be an object')
        for key in self.required_keys:
            if key not in payload:
                raise ValueError(f'tool "{self.name}" missing required input: {key}')
        return payload

    async def execute(self, payload: dict[str, Any], context: ToolContext) -> ToolResult:
        data = self.validate(payload)
        return await asyncio.wait_for(self.handler(data, context), timeout=self.timeout)


def object_schema(
    properties: dict[str, dict[str, Any]],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }
