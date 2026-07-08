from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from paicli.config import PaiCliConfig
from paicli.image import parse_image_references
from paicli.llm.base import LlmClient
from paicli.tools.base import ToolContext
from paicli.tools.executor import ToolExecutor
from paicli.tools.registry import ToolRegistry
from paicli.types import Message


async def query(
    *,
    llm_client: LlmClient,
    tool_registry: ToolRegistry,
    system_prompt: str,
    user_message: str,
    history: list[Message] | None,
    cwd: str,
    config: PaiCliConfig,
    approval_callback=None,
    skill_context_buffer=None,
    max_turns: int = 20,
) -> AsyncIterator[dict[str, Any]]:
    user_message = _prepend_skill_context(user_message, skill_context_buffer)
    messages = [
        *(history or []),
        Message(role="user", content=parse_image_references(user_message, cwd)),
    ]
    tool_definitions = tool_registry.definitions()
    executor = ToolExecutor(tool_registry)
    context = ToolContext(
        cwd=cwd,
        config=config,
        approval_callback=approval_callback,
        skill_context_buffer=skill_context_buffer,
    )

    total_tokens = 0
    turn = 0

    while turn < max_turns:
        turn += 1
        text = ""
        thinking = ""
        stop_reason = "end_turn"
        usage_input = 0
        usage_output = 0
        tool_states: dict[int, dict[str, Any]] = {}

        async for event in llm_client.chat(messages, tool_definitions, system_prompt=system_prompt):
            event_type = event.get("type")
            if event_type == "text_delta":
                delta = str(event.get("text") or "")
                text += delta
                yield {"type": "text_delta", "text": delta}
            elif event_type == "thinking_delta":
                delta = str(event.get("thinking") or "")
                thinking += delta
                yield {"type": "thinking_delta", "thinking": delta}
            elif event_type == "tool_call_delta":
                _merge_tool_delta(tool_states, event["tool_call"])
            elif event_type == "message_end":
                stop_reason = str(event.get("stop_reason") or "end_turn")
            elif event_type == "usage":
                usage = event.get("usage") or {}
                usage_input += int(usage.get("input_tokens") or 0)
                usage_output += int(usage.get("output_tokens") or 0)
                yield {"type": "usage", "usage": usage}
            elif event_type == "error":
                yield {"type": "error", "error": event["error"]}
                return

        total_tokens += usage_input + usage_output
        tool_calls = _finalize_tool_calls(tool_states)
        assistant_message = Message(role="assistant", content=text, tool_calls=tool_calls)
        if thinking and text:
            assistant_message.content = text
        elif thinking:
            assistant_message.content = ""
        messages.append(assistant_message)
        yield {"type": "turn_complete", "turn": turn, "stop_reason": stop_reason}

        if stop_reason != "tool_use" and not tool_calls:
            break

        for call in tool_calls:
            name = call.get("function", {}).get("name", "unknown")
            yield {"type": "tool_call", "name": name, "input": _tool_input(call)}

        tool_results = await executor.execute_all(tool_calls, context)
        for result in tool_results:
            yield {
                "type": "tool_result",
                "name": _tool_name_by_id(tool_calls, result.tool_use_id or ""),
                "result": result.content,
                "is_error": result.is_error,
            }
            messages.append(
                Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_use_id,
                )
            )

    yield {
        "type": "done",
        "total_turns": turn,
        "total_tokens": total_tokens,
        "messages": messages,
    }


def _merge_tool_delta(tool_states: dict[int, dict[str, Any]], delta: dict[str, Any]) -> None:
    index = int(delta.get("index") or 0)
    state = tool_states.setdefault(
        index,
        {
            "id": delta.get("id") or f"tool_{index}",
            "type": "function",
            "function": {"name": "", "arguments": ""},
        },
    )
    if delta.get("id"):
        state["id"] = delta["id"]
    function = delta.get("function") or {}
    if function.get("name"):
        state["function"]["name"] = function["name"]
    if function.get("arguments"):
        state["function"]["arguments"] += function["arguments"]


def _finalize_tool_calls(tool_states: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    calls = []
    for index in sorted(tool_states):
        state = tool_states[index]
        if state["function"]["name"]:
            calls.append(state)
    return calls


def _tool_input(call: dict[str, Any]) -> dict[str, Any]:
    raw = call.get("function", {}).get("arguments") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _tool_name_by_id(calls: list[dict[str, Any]], tool_call_id: str) -> str:
    for call in calls:
        if call.get("id") == tool_call_id:
            return str(call.get("function", {}).get("name") or "unknown")
    return "unknown"


def _prepend_skill_context(user_message: str, skill_context_buffer) -> str:
    if not skill_context_buffer or skill_context_buffer.is_empty():
        return user_message
    drained = skill_context_buffer.drain()
    if not drained:
        return user_message
    return f"{drained}\n\n---\nUser request:\n{user_message}"
