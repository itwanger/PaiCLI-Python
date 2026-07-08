from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from paicli.agent.query import query
from paicli.config import PaiCliConfig
from paicli.llm.base import LlmClient
from paicli.plan import ExecutionPlan, Planner, Task, TaskStatus
from paicli.prompt import PromptAssembler
from paicli.skill import SkillContextBuffer
from paicli.snapshot import SnapshotService
from paicli.tools.registry import ToolRegistry
from paicli.types import Message


@dataclass(slots=True)
class TaskRunResult:
    task: Task
    text: str
    tokens: int
    turns: int
    error: Exception | None = None


class PlanExecuteAgent:
    def __init__(
        self,
        *,
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        config: PaiCliConfig,
        cwd: str,
        approval_callback=None,
        planner: Planner | None = None,
        max_task_turns: int = 8,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config
        self.cwd = cwd
        self.approval_callback = approval_callback
        self.planner = planner or Planner(llm_client)
        self.max_task_turns = max_task_turns
        self.history: list[Message] = []
        self.skill_context_buffer = SkillContextBuffer()

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = SnapshotService(self.cwd)
        with suppress(Exception):
            snapshot.create("pre-turn")
        total_tokens = 0
        total_turns = 0
        final_text = ""
        try:
            yield {"type": "text_delta", "text": f"Planning task: {message}\n\n"}
            plan = await self.planner.create_plan(message)
            yield {"type": "text_delta", "text": plan.summarize() + "\n\n"}
            async for event in self._execute_plan(plan):
                if event.get("type") == "usage":
                    usage = event.get("usage") or {}
                    total_tokens += int(usage.get("input_tokens") or 0)
                    total_tokens += int(usage.get("output_tokens") or 0)
                elif event.get("type") == "plan_task_done":
                    total_turns += int(event.get("turns") or 0)
                    continue
                elif event.get("type") == "text_delta":
                    final_text += str(event.get("text") or "")
                yield event
            self.history = [
                Message(role="user", content=message),
                Message(role="assistant", content=final_text),
            ]
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "error": exc}
            return
        finally:
            with suppress(Exception):
                snapshot.create("post-turn")
        yield {
            "type": "done",
            "total_turns": total_turns,
            "total_tokens": total_tokens,
            "messages": self.history,
        }

    async def _execute_plan(self, plan: ExecutionPlan) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "text_delta", "text": "Executing plan...\n\n"}
        plan.mark_started()
        while True:
            executable = _executable_tasks_in_order(plan)
            if not executable:
                break
            if len(executable) == 1:
                result = await self._execute_task(plan, executable[0])
                async for event in self._apply_task_result(result):
                    yield event
                continue
            yield {
                "type": "text_delta",
                "text": (
                    f"Running parallel batch: {', '.join(task.id for task in executable)}\n\n"
                ),
            }
            results = await asyncio.gather(
                *(self._execute_task(plan, task) for task in executable),
                return_exceptions=False,
            )
            for result in results:
                async for event in self._apply_task_result(result):
                    yield event

        if plan.has_failed():
            plan.mark_failed()
            yield {"type": "text_delta", "text": "Plan partially completed with failed tasks.\n\n"}
        elif plan.is_all_completed():
            plan.mark_completed()
            yield {"type": "text_delta", "text": _build_plan_result(plan)}
        else:
            plan.mark_failed()
            yield {
                "type": "text_delta",
                "text": "Plan stalled because dependencies were not satisfied.\n\n",
            }

    async def _apply_task_result(self, result: TaskRunResult) -> AsyncIterator[dict[str, Any]]:
        if result.error:
            result.task.mark_failed(str(result.error))
            yield {"type": "text_delta", "text": f"Failed [{result.task.id}]: {result.error}\n\n"}
            return
        result.task.mark_completed(result.text)
        yield {
            "type": "text_delta",
            "text": f"Completed [{result.task.id}]: {_preview(result.text)}\n\n",
        }
        yield {
            "type": "usage",
            "usage": {"input_tokens": result.tokens, "output_tokens": 0},
        }
        yield {"type": "plan_task_done", "turns": result.turns, "tokens": result.tokens}

    async def _execute_task(self, plan: ExecutionPlan, task: Task) -> TaskRunResult:
        task.mark_started()
        text = ""
        tool_results: list[str] = []
        tokens = 0
        turns = 0
        try:
            async for event in query(
                llm_client=self.llm_client,
                tool_registry=self.tool_registry,
                system_prompt=self._task_system_prompt(task),
                user_message=_task_context(plan, task),
                history=[],
                cwd=self.cwd,
                config=self.config,
                approval_callback=self.approval_callback,
                skill_context_buffer=self.skill_context_buffer,
                max_turns=self.max_task_turns,
            ):
                if event.get("type") == "text_delta":
                    text += str(event.get("text") or "")
                elif event.get("type") == "tool_result":
                    content = str(event.get("result") or "")
                    if content:
                        tool_results.append(content)
                elif event.get("type") == "usage":
                    usage = event.get("usage") or {}
                    tokens += int(usage.get("input_tokens") or 0)
                    tokens += int(usage.get("output_tokens") or 0)
                elif event.get("type") == "done":
                    turns += int(event.get("total_turns") or 0)
                elif event.get("type") == "error":
                    raise event["error"]
            result_text = text.strip() or "\n".join(tool_results).strip()
            return TaskRunResult(task=task, text=result_text, tokens=tokens, turns=turns)
        except Exception as exc:  # noqa: BLE001
            return TaskRunResult(task=task, text="", tokens=tokens, turns=turns, error=exc)

    def _task_system_prompt(self, task: Task) -> str:
        base = PromptAssembler(
            config=self.config,
            cwd=self.cwd,
            tool_names=self.tool_registry.list_names(),
            model=self.llm_client.model_name,
            provider=self.llm_client.provider_name,
        ).build()
        return (
            base
            + "\n\nYou are executing one task inside a Plan-and-Execute DAG.\n"
            + f"Task id: {task.id}\nTask type: {task.type.value}\n"
            + "Complete this task concretely. Use tools when needed."
        )


def _executable_tasks_in_order(plan: ExecutionPlan) -> list[Task]:
    executable_ids = {task.id for task in plan.executable_tasks()}
    return [plan.tasks[task_id] for task_id in plan.execution_order() if task_id in executable_ids]


def _task_context(plan: ExecutionPlan, task: Task) -> str:
    lines = [
        f"Goal: {plan.goal}",
        f"Current task [{task.id}]: {task.description}",
        "",
        "Completed dependency results:",
    ]
    for dep_id in task.dependencies:
        dep = plan.get_task(dep_id)
        if dep and dep.status == TaskStatus.COMPLETED:
            lines.append(f"- [{dep.id}] {dep.description}: {_preview(dep.result, 800)}")
    return "\n".join(lines)


def _build_plan_result(plan: ExecutionPlan) -> str:
    lines = ["Plan execution completed.", "", "Task summary:"]
    for task in plan.all_tasks():
        lines.append(f"- [{task.id}] {task.status.value}: {task.description}")
        if task.result:
            lines.append(f"  Result: {_preview(task.result)}")
    return "\n".join(lines) + "\n"


def _preview(text: str, max_len: int = 160) -> str:
    value = (text or "").replace("\r\n", "\n").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."
