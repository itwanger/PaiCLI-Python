# PaiCLI Python Parity

This file tracks the Python port against the existing Java and TypeScript implementations.

## Implemented

- CLI:
  - `paicli`
  - `paicli -p`
  - `--provider`
  - `--model`
  - `--plain`
  - `--cwd`
  - `paicli doctor`
  - `paicli serve --http --port <port>`
- REPL:
  - `/help`
  - `/clear`
  - `/context`
  - `/memory`
  - `/save`
  - `/config`
  - `/tools`
  - `/hitl`
  - `/policy`
  - `/audit`
  - `/index`
  - `/search`
  - `/plan`
  - `/team`
  - `/task`
  - `/snapshot`
  - `/restore`
  - `/skill`
  - `/mcp`
  - `/exit`
- Agent:
  - OpenAI-compatible streaming LLM client
  - DeepSeek default
  - ReAct loop with text/thinking/tool-call/tool-result/done events
  - Plan-and-Execute agent with Planner-generated DAG, dependency ordering, and parallel executable batches
  - Multi-Agent orchestrator with Planner, Worker, Reviewer, dependency scheduling, parallel workers, review approval parsing, and bounded retry
  - SDK entrypoint with ReAct, Plan-and-Execute, and Multi-Agent methods
  - pre/post side-history snapshots around Agent runs
- Configuration:
  - defaults
  - user config
  - project config
  - project `.env`
  - CLI overrides
  - process env
  - provider-specific keys such as `DEEPSEEK_API_KEY`, `GLM_API_KEY`, `STEP_API_KEY`, `KIMI_API_KEY`
- Tools:
  - `read_file`
  - `write_file`
  - `list_dir`
  - `glob` / `glob_files`
  - `grep` / `grep_code`
  - `bash` / `execute_command`
  - `web_search`
  - `web_fetch`
  - `save_memory`
  - `load_skill`
  - `search_code`
  - `revert_turn`
- Safety:
  - PathGuard
  - CommandGuard
  - HITL approval
  - JSONL AuditLog
- Memory:
  - SQLite long-term memory
  - project memory files `PAI.md`, `.paicli/PAI.md`, local variants
- Skills:
  - built-in/user/project skill layers
  - user/project `.paicli/skills/*/SKILL.md`
  - `~/.paicli/skills.json` disabled-state store
  - `load_skill` with one-shot SkillContextBuffer injection
  - `/skill list/show/on/off/reload`
- RAG:
  - SQLite local code index
  - `/index`
  - `/search`
  - `search_code`
- MCP:
  - official MCP Python SDK client
  - stdio MCP server connection
  - Streamable HTTP MCP server connection
  - dynamic `mcp__server__tool` registration
  - virtual resource tools
  - virtual prompt tools
  - `paicli mcp init-chrome`
  - `paicli mcp list`
  - PaiCLI MCP server over stdio/http for built-in tools
- Chrome DevTools MCP:
  - project/user config writer for `npx chrome-devtools-mcp@latest`
  - `--browser-url`
  - `--headless`
  - `--slim`
  - usage-statistics opt-out flag by default
- Runtime:
  - API key requirement
  - `POST /v1/threads`
  - `POST /v1/threads/{id}/turns`
  - `GET /v1/threads/{id}/events`
  - `POST /v1/tasks`
  - `GET /v1/tasks`
  - `GET /v1/tasks/{id}`
  - `POST /v1/tasks/{id}/cancel`
  - SQLite durable task queue
- Snapshot:
  - `pre-turn` / `post-turn`
  - `/snapshot`
  - `/restore`
  - `revert_turn`
- Image input:
  - `@image:path`
  - `@image:file:///path`
  - `@image:https://...`
  - local image resize/compress
  - transparent PNG white background handling
  - provider/model capability fallback
- Diagnostics:
  - Python syntax diagnostics after `write_file`

## Live Dependencies

These features need external credentials or platform state for live verification:

- Real LLM calls need API keys.
- Chrome DevTools MCP needs Node.js LTS, npm/npx, and Chrome.
- Runtime API turn execution needs a working LLM key.
- WeChat iLink needs private iLink credentials and scan-login state.

## Known Remaining Java-Only Area

The Java implementation has a WeChat iLink channel. Python does not ship that private channel yet because it requires iLink account credentials and protocol details that should not be faked. All public/open protocol surfaces from the TypeScript baseline and the main Java Agent CLI surfaces have corresponding Python implementations.

## Verification

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev python -m pytest
uv build
uv run paicli --help
uv run paicli doctor --cwd .
uv run paicli mcp serve --transport http --port 3999
```
