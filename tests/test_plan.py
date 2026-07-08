from __future__ import annotations

import asyncio
from typing import Any

from paicli.agent import PlanExecuteAgent
from paicli.config import load_config
from paicli.plan import ExecutionPlan, Planner, Task, TaskType
from paicli.tools import ToolRegistry, get_builtin_tools


def test_execution_plan_exposes_dag_batches():
    plan = ExecutionPlan(id="plan_1", goal="demo")
    task_1 = Task("task_1", "read a", TaskType.FILE_READ)
    task_2 = Task("task_2", "read b", TaskType.FILE_READ)
    task_3 = Task("task_3", "summarize", TaskType.ANALYSIS, ["task_1", "task_2"])

    plan.add_task(task_1)
    plan.add_task(task_2)
    plan.add_task(task_3)

    assert plan.execution_order() == ["task_1", "task_2", "task_3"]
    assert plan.execution_batches() == [[task_1, task_2], [task_3]]
    assert plan.executable_tasks() == [task_1, task_2]
    task_1.mark_completed("done")
    assert plan.executable_tasks() == [task_2]


def test_planner_parses_tasks_and_dependencies():
    planner = Planner(FakeClient())

    plan = planner.parse_plan(
        "demo",
        """
        ```json
        {
          "summary": "demo plan",
          "tasks": [
            {"id": "a", "description": "A", "type": "COMMAND", "dependencies": []},
            {"id": "b", "description": "B", "type": "VERIFICATION", "dependencies": ["a"]}
          ]
        }
        ```
        """,
    )

    assert plan.summary == "demo plan"
    assert plan.get_task("task_2").dependencies == ["task_1"]
    assert plan.get_task("task_2").type == TaskType.VERIFICATION


def test_plan_execute_runs_independent_tasks_in_parallel(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    client = ParallelPlanClient()
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    config = load_config(project_root=tmp_path)
    config.policy.hitl_mode = "never"
    agent = PlanExecuteAgent(
        llm_client=client,
        tool_registry=registry,
        config=config,
        cwd=str(tmp_path),
    )

    async def run():
        text = ""
        async for event in agent.run("先做 A 和 B，然后汇总"):
            if event.get("type") == "text_delta":
                text += str(event.get("text") or "")
            elif event.get("type") == "error":
                raise event["error"]
        return text

    result = asyncio.run(run())

    assert "Completed [task_1]" in result
    assert "Completed [task_2]" in result
    assert client.peak_concurrency == 2


class FakeClient:
    model_name = "fake-model"
    provider_name = "fake-provider"
    max_context_window = 1000

    async def chat(self, messages, tools, *, system_prompt):  # noqa: ARG002
        yield {"type": "text_delta", "text": "{}"}
        yield {"type": "message_end", "stop_reason": "end_turn"}


class ParallelPlanClient(FakeClient):
    def __init__(self):
        self.current_concurrency = 0
        self.peak_concurrency = 0
        self.ready = asyncio.Event()

    async def chat(self, messages, tools, *, system_prompt):  # noqa: ARG002
        body = _message_text(messages[-1].content)
        if "Please create an execution plan" in body:
            yield {
                "type": "text_delta",
                "text": (
                    '{"summary":"parallel","tasks":['
                    '{"id":"a","description":"Task A","type":"ANALYSIS","dependencies":[]},'
                    '{"id":"b","description":"Task B","type":"ANALYSIS","dependencies":[]}'
                    "]}"
                ),
            }
            yield {"type": "message_end", "stop_reason": "end_turn"}
            return

        if "Task A" in body or "Task B" in body:
            self.current_concurrency += 1
            self.peak_concurrency = max(self.peak_concurrency, self.current_concurrency)
            if self.current_concurrency == 2:
                self.ready.set()
            await asyncio.wait_for(self.ready.wait(), timeout=2)
            self.current_concurrency -= 1
            text = "result for A" if "Task A" in body else "result for B"
            yield {"type": "text_delta", "text": text}
            yield {"type": "message_end", "stop_reason": "end_turn"}
            return

        yield {"type": "text_delta", "text": "fallback"}
        yield {"type": "message_end", "stop_reason": "end_turn"}


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content)
