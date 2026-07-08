from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class TaskType(StrEnum):
    PLANNING = "PLANNING"
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    COMMAND = "COMMAND"
    ANALYSIS = "ANALYSIS"
    VERIFICATION = "VERIFICATION"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Task:
    id: str
    description: str
    type: TaskType = TaskType.ANALYSIS
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    def add_dependency(self, task_id: str) -> None:
        if task_id not in self.dependencies:
            self.dependencies.append(task_id)

    def add_dependent(self, task_id: str) -> None:
        if task_id not in self.dependents:
            self.dependents.append(task_id)

    def mark_started(self) -> None:
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()

    def mark_completed(self, result: str) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.end_time = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.end_time = time.time()

    def mark_skipped(self) -> None:
        self.status = TaskStatus.SKIPPED
        self.end_time = time.time()

    def is_executable(self, all_tasks: dict[str, Task]) -> bool:
        if self.status != TaskStatus.PENDING:
            return False
        return all(
            dep_id in all_tasks and all_tasks[dep_id].status == TaskStatus.COMPLETED
            for dep_id in self.dependencies
        )


@dataclass(slots=True)
class ExecutionPlan:
    id: str
    goal: str
    tasks: dict[str, Task] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.CREATED
    summary: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    _execution_order: list[str] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
        for dep_id in task.dependencies:
            dep = self.tasks.get(dep_id)
            if dep:
                dep.add_dependent(task.id)
        for existing in self.tasks.values():
            if task.id in existing.dependencies:
                task.add_dependent(existing.id)
        self._execution_order.clear()

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def all_tasks(self) -> list[Task]:
        return list(self.tasks.values())

    def root_tasks(self) -> list[Task]:
        return [task for task in self.tasks.values() if not task.dependencies]

    def executable_tasks(self) -> list[Task]:
        return [task for task in self.tasks.values() if task.is_executable(self.tasks)]

    def compute_execution_order(self) -> bool:
        order: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(task: Task) -> bool:
            if task.id in visiting:
                return False
            if task.id in visited:
                return True
            visiting.add(task.id)
            for dep_id in task.dependencies:
                dep = self.tasks.get(dep_id)
                if dep and not visit(dep):
                    return False
            visiting.remove(task.id)
            visited.add(task.id)
            order.append(task.id)
            return True

        for task in self.tasks.values():
            if task.id not in visited and not visit(task):
                return False
        self._execution_order = order
        return True

    def execution_order(self) -> list[str]:
        if not self._execution_order:
            self.compute_execution_order()
        return list(self._execution_order)

    def execution_batches(self) -> list[list[Task]]:
        remaining = set(self.tasks)
        completed: set[str] = set()
        batches: list[list[Task]] = []
        while remaining:
            batch_ids = [
                task_id
                for task_id in self.execution_order()
                if task_id in remaining
                and all(dep_id in completed for dep_id in self.tasks[task_id].dependencies)
            ]
            if not batch_ids:
                break
            batch = [self.tasks[task_id] for task_id in batch_ids]
            batches.append(batch)
            completed.update(batch_ids)
            remaining.difference_update(batch_ids)
        return batches

    def progress(self) -> float:
        if not self.tasks:
            return 1.0
        completed = sum(1 for task in self.tasks.values() if task.status == TaskStatus.COMPLETED)
        return completed / len(self.tasks)

    def is_all_completed(self) -> bool:
        return all(task.status == TaskStatus.COMPLETED for task in self.tasks.values())

    def has_failed(self) -> bool:
        return any(task.status == TaskStatus.FAILED for task in self.tasks.values())

    def mark_started(self) -> None:
        self.status = PlanStatus.RUNNING
        self.start_time = time.time()

    def mark_completed(self) -> None:
        self.status = PlanStatus.COMPLETED
        self.end_time = time.time()

    def mark_failed(self) -> None:
        self.status = PlanStatus.FAILED
        self.end_time = time.time()

    def summarize(self) -> str:
        batches = self.execution_batches()
        first_batch = ", ".join(task.id for task in batches[0]) if batches else "none"
        final_batch = ", ".join(task.id for task in batches[-1]) if batches else "none"
        return (
            f"Plan {self.id}: {self.summary or self.goal}\n"
            f"Tasks: {len(self.tasks)} | Parallel batches: {len(batches)} | "
            f"Executable now: {len(self.executable_tasks())}\n"
            f"First batch: {first_batch}\n"
            f"Final convergence: {final_batch}"
        )
