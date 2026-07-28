from __future__ import annotations

import asyncio
import os
from typing import Any

from paicli.memory import MemoryManager
from paicli.policy import CommandGuard
from paicli.rag import CodeIndex
from paicli.skill import SkillRegistry
from paicli.snapshot import SnapshotService
from paicli.tools import file_ops as fops
from paicli.tools.base import Tool, ToolContext, ToolResult, object_schema
from paicli.tools.file_ops import FileOpResult
from paicli.web import fetch_url, search_web
from paicli.web.search import tavily_search_web


def get_builtin_tools() -> list[Tool]:
    tools = [
        Tool(
            name="read_file",
            description="Read a text file from the current workspace.",
            parameters=object_schema(
                {
                    "path": {"type": "string", "description": "Path to read"},
                    "offset": {"type": "number", "description": "Start line, 1-based"},
                    "limit": {"type": "number", "description": "Maximum number of lines"},
                },
                ["path"],
            ),
            required_keys=["path"],
            handler=_read_file,
        ),
        Tool(
            name="write_file",
            description="Write a UTF-8 text file inside the current workspace.",
            parameters=object_schema(
                {
                    "path": {"type": "string", "description": "Path to write"},
                    "content": {"type": "string", "description": "File content"},
                    "append": {"type": "boolean", "description": "Append instead of overwrite"},
                },
                ["path", "content"],
            ),
            required_keys=["path", "content"],
            handler=_write_file,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
        ),
        Tool(
            name="edit_file",
            description=(
                "Make line-based edits to a text file. Each edit replaces exact line sequences "
                "with new content. Returns a git-style diff showing the changes made."
            ),
            parameters=object_schema(
                {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old_text": {
                        "type": "string",
                        "description": "Text to search for — must match exactly",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Text to replace with",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview changes without modifying the file",
                    },
                },
                ["path", "old_text", "new_text"],
            ),
            required_keys=["path", "old_text", "new_text"],
            handler=_edit_file,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
        ),
        Tool(
            name="list_dir",
            description="List entries in a directory inside the current workspace.",
            parameters=object_schema(
                {"path": {"type": "string", "description": "Directory path"}},
                ["path"],
            ),
            required_keys=["path"],
            handler=_list_dir,
        ),
        Tool(
            name="glob",
            description="Find files by glob pattern inside the current workspace.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "limit": {"type": "number", "description": "Maximum results"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=_glob_files,
        ),
        Tool(
            name="glob_files",
            description="Alias of glob. Find files by glob pattern inside the current workspace.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "limit": {"type": "number", "description": "Maximum results"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=_glob_files,
        ),
        Tool(
            name="grep",
            description="Search text in workspace files.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Regex or plain text pattern"},
                    "path": {"type": "string", "description": "Optional path to search"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=_grep,
        ),
        Tool(
            name="grep_code",
            description="Alias of grep. Search text in workspace files.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Regex or plain text pattern"},
                    "path": {"type": "string", "description": "Optional path to search"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=_grep,
        ),
        Tool(
            name="directory_tree",
            description=(
                "Get a recursive tree view of files and directories as indented text. "
                "Each entry shows the name and type. Files have no children, "
                "while directories always show their contents."
            ),
            parameters=object_schema(
                {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: workspace root)",
                    },
                    "max_depth": {
                        "type": "number",
                        "description": "Maximum recursion depth (default: 3)",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Directory names to exclude from the tree",
                    },
                },
            ),
            required_keys=[],
            handler=_directory_tree,
        ),
        Tool(
            name="get_file_info",
            description=(
                "Retrieve detailed metadata about a file or directory — size, "
                "modification time, permissions, and type."
            ),
            parameters=object_schema(
                {"path": {"type": "string", "description": "Path to inspect"}},
                ["path"],
            ),
            required_keys=["path"],
            handler=_get_file_info,
        ),
        Tool(
            name="bash",
            description="Execute a shell command in the current workspace.",
            parameters=object_schema(
                {
                    "command": {"type": "string", "description": "Shell command"},
                    "timeout": {"type": "number", "description": "Timeout seconds"},
                },
                ["command"],
            ),
            required_keys=["command"],
            handler=_bash,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
        Tool(
            name="execute_command",
            description="Alias of bash. Execute a shell command in the current workspace.",
            parameters=object_schema(
                {
                    "command": {"type": "string", "description": "Shell command"},
                    "timeout": {"type": "number", "description": "Timeout seconds"},
                },
                ["command"],
            ),
            required_keys=["command"],
            handler=_bash,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
        Tool(
            name="web_search",
            description=(
                "Search the web for current information. Returns titles, URLs, and snippets."
            ),
            parameters=object_schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "number", "description": "Maximum result count"},
                },
                ["query"],
            ),
            required_keys=["query"],
            handler=_web_search,
        ),
        Tool(
            name="web_fetch",
            description="Fetch a public HTTP/HTTPS page and return readable text.",
            parameters=object_schema(
                {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_length": {"type": "number", "description": "Maximum returned characters"},
                },
                ["url"],
            ),
            required_keys=["url"],
            handler=_web_fetch,
        ),
        Tool(
            name="save_memory",
            description=(
                "Save an explicit or durable fact to long-term project memory. Use only for stable "
                "preferences, project constraints, user corrections, or reusable decisions; never "
                "store secrets, temporary task state, raw logs, or uncertain claims."
            ),
            parameters=object_schema(
                {
                    "content": {"type": "string", "description": "Durable fact to remember"},
                    "kind": {
                        "type": "string",
                        "enum": ["fact", "preference", "constraint", "correction", "decision"],
                    },
                    "importance": {"type": "number", "description": "Score from 0 to 1"},
                    "confidence": {"type": "number", "description": "Score from 0 to 1"},
                    "expires_at": {
                        "type": "string",
                        "description": "Optional ISO-8601 expiry for time-sensitive memory",
                    },
                },
                ["content"],
            ),
            required_keys=["content"],
            handler=_save_memory,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
        ),
        Tool(
            name="search_memory",
            description=(
                "Search relevance-ranked long-term project memory when prior preferences, "
                "corrections, constraints, or decisions may matter."
            ),
            parameters=object_schema(
                {
                    "query": {"type": "string", "description": "What to recall"},
                    "limit": {"type": "number", "description": "Maximum results"},
                    "kinds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional memory kinds",
                    },
                },
                ["query"],
            ),
            required_keys=["query"],
            handler=_search_memory,
        ),
        Tool(
            name="load_skill",
            description="Load a named PaiCLI skill manual from user/project skill directories.",
            parameters=object_schema(
                {"name": {"type": "string", "description": "Skill name"}},
                ["name"],
            ),
            required_keys=["name"],
            handler=_load_skill,
        ),
        Tool(
            name="save_skill",
            description=(
                "Persist a reusable PaiCLI workflow as a project or user skill after user approval."
            ),
            parameters=object_schema(
                {
                    "name": {"type": "string", "description": "Lowercase skill slug"},
                    "description": {
                        "type": "string",
                        "description": "When this skill should be used",
                    },
                    "content": {"type": "string", "description": "Reusable skill instructions"},
                    "scope": {
                        "type": "string",
                        "enum": ["project", "user"],
                        "description": "Where to persist the skill",
                    },
                    "version": {"type": "string", "description": "Skill version"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Matching keywords",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Update an existing skill instead of failing",
                    },
                },
                ["name", "description", "content"],
            ),
            required_keys=["name", "description", "content"],
            handler=_save_skill,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
            requires_approval=True,
        ),
        Tool(
            name="search_code",
            description="Search the local code index for semantically relevant lines.",
            parameters=object_schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["query"],
            ),
            required_keys=["query"],
            handler=_search_code,
        ),
        Tool(
            name="revert_turn",
            description="Restore the workspace to a previous PaiCLI side-history snapshot.",
            parameters=object_schema(
                {"snapshot": {"type": "string", "description": "Snapshot id or 1-based index"}},
                ["snapshot"],
            ),
            required_keys=["snapshot"],
            handler=_revert_turn,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
    ]
    return tools


# ---------------------------------------------------------------------------
# Handler: file operations (thin wrappers over file_ops)
# ---------------------------------------------------------------------------


async def _read_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.read_file(
        context.cwd,
        str(payload["path"]),
        offset=int(payload.get("offset") or 1),
        limit=int(payload.get("limit") or 500),
        path_guard_enabled=context.config.policy.path_guard_enabled,
    )
    return _to_tool_result(result)


async def _write_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.write_file(
        context.cwd,
        str(payload["path"]),
        str(payload["content"]),
        append=bool(payload.get("append")),
        path_guard_enabled=context.config.policy.path_guard_enabled,
    )
    return _to_tool_result(result)


async def _edit_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.edit_file(
        context.cwd,
        str(payload["path"]),
        str(payload["old_text"]),
        str(payload["new_text"]),
        path_guard_enabled=context.config.policy.path_guard_enabled,
        dry_run=bool(payload.get("dry_run")),
    )
    return _to_tool_result(result)


async def _list_dir(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.list_directory(
        context.cwd,
        str(payload["path"]),
        path_guard_enabled=context.config.policy.path_guard_enabled,
    )
    return _to_tool_result(result)


async def _glob_files(payload: dict[str, Any], _context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.glob_files(
        _context.cwd,
        str(payload["pattern"]),
        limit=int(payload.get("limit") or 100),
    )
    return _to_tool_result(result)


async def _grep(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.grep(
        context.cwd,
        str(payload["pattern"]),
        path=str(payload.get("path") or "."),
        limit=int(payload.get("limit") or 100),
        use_regex=bool(payload.get("regex", True)),
        path_guard_enabled=context.config.policy.path_guard_enabled,
    )
    return _to_tool_result(result)


async def _directory_tree(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.directory_tree(
        context.cwd,
        str(payload.get("path", ".")),
        max_depth=int(payload.get("max_depth") or 3),
        path_guard_enabled=context.config.policy.path_guard_enabled,
        exclude_patterns=tuple(payload.get("exclude_patterns") or ()),
    )
    return _to_tool_result(result)


async def _get_file_info(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    result: FileOpResult = fops.get_file_info(
        context.cwd,
        str(payload["path"]),
        path_guard_enabled=context.config.policy.path_guard_enabled,
    )
    return _to_tool_result(result)


# ---------------------------------------------------------------------------
# Handler: bash
# ---------------------------------------------------------------------------


async def _bash(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    command = str(payload["command"])
    if context.config.policy.command_guard_enabled:
        CommandGuard(context.config.policy.command_blacklist).validate(command)
    timeout = float(payload.get("timeout") or context.config.tools.timeout)
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=context.cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return ToolResult(f"Command timed out after {timeout:.0f}s", is_error=True)
    output = (stdout + stderr).decode("utf-8", errors="replace")
    if len(output) > 20_000:
        output = output[:20_000] + "\n... [truncated]"
    return ToolResult(
        output or f"(exit {proc.returncode}, no output)",
        is_error=proc.returncode != 0,
    )


# ---------------------------------------------------------------------------
# Handler: web
# ---------------------------------------------------------------------------


async def _web_search(payload: dict[str, Any], _context: ToolContext) -> ToolResult:
    max_results = int(payload.get("max_results") or payload.get("maxResults") or 5)
    tavily_key = os.environ.get("TAVILY_API_KEY")
    try:
        if tavily_key:
            results = await tavily_search_web(
                str(payload["query"]), api_key=tavily_key, max_results=max_results
            )
        else:
            results = await search_web(str(payload["query"]), max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(f"Search error: {exc}", is_error=True)
    if not results:
        return ToolResult(f'No search results found for "{payload["query"]}".')
    content = "\n\n".join(
        f"{index}. {result.title}\n{result.url}\n{result.snippet}"
        for index, result in enumerate(results, start=1)
    )
    return ToolResult(content, display_summary=f"Search: {len(results)} results")


async def _web_fetch(payload: dict[str, Any], _context: ToolContext) -> ToolResult:
    max_length = int(payload.get("max_length") or payload.get("maxLength") or 10_000)
    try:
        content = await fetch_url(str(payload["url"]), max_length=max_length)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(f"Fetch error: {exc}", is_error=True)
    return ToolResult(content, display_summary=f"Fetched {payload['url']}")


# ---------------------------------------------------------------------------
# Handler: memory
# ---------------------------------------------------------------------------


async def _save_memory(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    if not context.config.features.memory or not context.config.memory.long_term_enabled:
        return ToolResult("Long-term memory is disabled.", is_error=True)
    manager = MemoryManager(
        context.config.memory.long_term_db_path,
        scope=context.cwd,
        max_entries=context.config.memory.max_long_term_entries,
        max_content_length=context.config.memory.max_memory_chars,
    )
    memory_id = manager.save(
        str(payload["content"]),
        kind=str(payload.get("kind") or "fact"),
        source="agent",
        importance=float(payload.get("importance", 0.5)),
        confidence=float(payload.get("confidence", 1.0)),
        expires_at=payload.get("expires_at"),
    )
    return ToolResult(f"Saved memory #{memory_id}")


async def _search_memory(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    if not context.config.features.memory or not context.config.memory.long_term_enabled:
        return ToolResult("Long-term memory is disabled.", is_error=True)
    raw_kinds = payload.get("kinds")
    if raw_kinds is not None and not isinstance(raw_kinds, list):
        return ToolResult("search_memory kinds must be an array of strings.", is_error=True)
    manager = MemoryManager(
        context.config.memory.long_term_db_path,
        scope=context.cwd,
        max_entries=context.config.memory.max_long_term_entries,
        max_content_length=context.config.memory.max_memory_chars,
    )
    rows = manager.recall(
        str(payload["query"]),
        limit=int(payload.get("limit") or context.config.memory.recall_limit),
        kinds=[str(kind) for kind in raw_kinds] if raw_kinds else None,
        min_score=context.config.memory.recall_min_score,
    )
    if not rows:
        return ToolResult("(no relevant long-term memory)")
    content = "\n".join(
        f"#{row.id} [{row.kind}, importance={row.importance:.2f}] {row.content}" for row in rows
    )
    return ToolResult(content, display_summary=f"Recalled {len(rows)} memories")


# Keep the original handler imports working for SDK users and existing tests.
save_memory = _save_memory
search_memory = _search_memory


# ---------------------------------------------------------------------------
# Handler: skill
# ---------------------------------------------------------------------------


async def _load_skill(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    if not context.config.features.skill:
        return ToolResult("Skills are disabled.", is_error=True)
    skill = SkillRegistry(context.cwd).load(str(payload["name"]))
    if not skill:
        return ToolResult(f'Skill "{payload["name"]}" not found or disabled.', is_error=True)
    content = skill.body or skill.content
    if len(content) > 5_000:
        content = content[:5_000] + "\n... [truncated; use /skill show for the full skill]"
    if context.skill_context_buffer:
        context.skill_context_buffer.push(skill.name, content)
        return ToolResult(
            f'Loaded skill "{skill.name}" instructions for the next model turn.',
            display_summary=f"Loaded skill {skill.name}",
        )
    return ToolResult(content, display_summary=f"Loaded skill {skill.name}")


async def _save_skill(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    if not context.config.features.skill:
        return ToolResult("Skills are disabled.", is_error=True)
    raw_tags = payload.get("tags") or []
    if not isinstance(raw_tags, list):
        return ToolResult("save_skill tags must be an array of strings.", is_error=True)
    tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    registry = SkillRegistry(context.cwd)
    scope = str(payload.get("scope") or "project")
    name = str(payload["name"])
    try:
        if bool(payload.get("overwrite")):
            skill = registry.update(
                name,
                description=str(payload["description"]),
                body=str(payload["content"]),
                scope=scope,
                version=str(payload.get("version") or "1.0.0"),
                tags=tags,
            )
        else:
            skill = registry.create(
                name,
                description=str(payload["description"]),
                body=str(payload["content"]),
                scope=scope,
                version=str(payload.get("version") or "1.0.0"),
                tags=tags,
            )
    except (OSError, ValueError) as exc:
        return ToolResult(f"save_skill failed: {exc}", is_error=True)
    return ToolResult(
        f'Saved skill "{skill.name}" in {scope} scope at {skill.path}.',
        display_summary=f"Saved skill {skill.name}",
    )


load_skill = _load_skill


# ---------------------------------------------------------------------------
# Handler: code search
# ---------------------------------------------------------------------------


async def _search_code(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    index = CodeIndex(context.cwd)
    results = index.search(str(payload["query"]), limit=int(payload.get("limit") or 20))
    if not results:
        return ToolResult("(no indexed matches; run /index first)")
    return ToolResult("\n".join(f"{item.path}:{item.line}: {item.snippet}" for item in results))


# ---------------------------------------------------------------------------
# Handler: snapshot revert
# ---------------------------------------------------------------------------


async def _revert_turn(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    record = SnapshotService(context.cwd).restore(str(payload["snapshot"]))
    return ToolResult(f"Restored snapshot {record.id}")


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------


def _to_tool_result(result: FileOpResult) -> ToolResult:
    """Convert a FileOpResult to a ToolResult."""
    return ToolResult(
        content=result.content,
        is_error=result.is_error,
        display_summary=result.display_summary,
    )
