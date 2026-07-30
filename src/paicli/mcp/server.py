from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from paicli.config import load_config
from paicli.tools import ToolRegistry, get_builtin_tools
from paicli.tools.base import ToolContext


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    return registry


def _tool_list(registry: ToolRegistry) -> list[dict[str, Any]]:
    tools = []
    for definition in registry.definitions():
        fn = definition["function"]
        tools.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "inputSchema": fn["parameters"],
            }
        )
    return tools

def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": "2025-11-25",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "paicli", "version": "0.1.0"},
    }

async def _handle_request(request: dict[str, Any], cwd: str) -> dict[str, Any]:
    registry = _build_registry()
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if method in {"initialize", "notifications/initialized"}:
        return {"jsonrpc": "2.0", "id": request_id, "result": _initialize_result()}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_list(registry)}}
    if method == "tools/call":
        name = params.get("name")
        tool = registry.get(str(name))
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"message": f'Tool "{name}" not found'},
            }
        config = load_config(project_root=cwd)
        config.policy.hitl_mode = "never"
        result = await tool.execute(
            params.get("arguments") or {},
            ToolContext(cwd=cwd, config=config),
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": result.content}],
                "isError": result.is_error,
            },
        }
    return {"jsonrpc": "2.0", "id": request_id, "error": {"message": f"Unknown method: {method}"}}


async def serve_stdio(cwd: str | None = None) -> None:
    root = str(Path(cwd or ".").resolve())
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, input)
        try:
            request = json.loads(line)
            response = await _handle_request(request, root)
        except EOFError:
            break
        except Exception as exc:  # noqa: BLE001
            response = {"jsonrpc": "2.0", "error": {"message": str(exc)}}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def serve_http(port: int = 3000, cwd: str | None = None) -> None:
    root = str(Path(cwd or ".").resolve())

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            try:
                request = json.loads(raw)
                response = asyncio.run(_handle_request(request, root))
                status = 200
            except Exception as exc:  # noqa: BLE001
                response = {"jsonrpc": "2.0", "error": {"message": str(exc)}}
                status = 200
            body = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PaiCLI MCP server listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
