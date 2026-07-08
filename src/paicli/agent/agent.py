from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from paicli.config import PaiCliConfig
from paicli.llm.base import LlmClient
from paicli.skill import SkillContextBuffer
from paicli.snapshot import SnapshotService
from paicli.tools.registry import ToolRegistry
from paicli.types import Message, QueryResult

from .query import query


class Agent:
    def __init__(
        self,
        *,
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        system_prompt: str,
        cwd: str,
        config: PaiCliConfig,
        approval_callback=None,
        max_turns: int = 20,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.cwd = cwd
        self.config = config
        self.approval_callback = approval_callback
        self.max_turns = max_turns
        self.history: list[Message] = []
        self.skill_context_buffer = SkillContextBuffer()

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = SnapshotService(self.cwd)
        with suppress(Exception):
            snapshot.create("pre-turn")
        try:
            async for event in query(
                llm_client=self.llm_client,
                tool_registry=self.tool_registry,
                system_prompt=self.system_prompt,
                user_message=message,
                history=self.history,
                cwd=self.cwd,
                config=self.config,
                approval_callback=self.approval_callback,
                skill_context_buffer=self.skill_context_buffer,
                max_turns=self.max_turns,
            ):
                if event.get("type") == "done":
                    self.history = list(event.get("messages") or [])
                yield event
        finally:
            with suppress(Exception):
                snapshot.create("post-turn")

    async def run_complete(self, message: str) -> QueryResult:
        text = ""
        tokens = 0
        turns = 0
        async for event in self.run(message):
            if event.get("type") == "text_delta":
                text += str(event.get("text") or "")
            elif event.get("type") == "error":
                raise event["error"]
            elif event.get("type") == "done":
                tokens = int(event.get("total_tokens") or 0)
                turns = int(event.get("total_turns") or 0)
        return QueryResult(text=text, total_tokens=tokens, turns=turns)

    def clear_history(self) -> None:
        self.history = []
        self.skill_context_buffer.clear()
