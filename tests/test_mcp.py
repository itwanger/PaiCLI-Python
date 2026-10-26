from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from paicli.config import load_config
from paicli.entrypoints.repl import _count_mcp_servers
from paicli.mcp import McpClientManager
from paicli.mcp.server import _handle_request
from paicli.tools.base import ToolContext


def test_mcp_tools_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    async def run():
        return await _handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            str(tmp_path),
        )

    response = asyncio.run(run())
    tools = response["result"]["tools"]
    assert any(tool["name"] == "read_file" for tool in tools)
    assert any(tool["name"] == "execute_command" for tool in tools)


def test_mcp_client_registers_and_calls_stdio_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fake")

@mcp.tool()
def echo(text: str) -> str:
    return "echo:" + text

if __name__ == "__main__":
    mcp.run(transport="stdio")
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / ".paicli").mkdir()
    (tmp_path / ".paicli" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fake": {
                        "type": "stdio",
                        "command": "python",
                        "args": [str(server)],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    async def run():
        manager = McpClientManager(tmp_path)
        tools = await manager.load_tools()
        names = [tool.name for tool in tools]
        tool = next(item for item in tools if item.name == "mcp__fake__echo")
        config = load_config(project_root=tmp_path)
        config.policy.hitl_mode = "never"
        result = await tool.execute({"text": "ok"}, ToolContext(cwd=str(tmp_path), config=config))
        return names, result

    names, result = asyncio.run(run())
    assert "mcp__fake__echo" in names
    assert result.content == "echo:ok"


def test_mcp_client_suppresses_stdio_server_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    server = tmp_path / "noisy_mcp_server.py"
    server.write_text(
        """
import sys
from mcp.server.fastmcp import FastMCP

sys.stderr.write("NOISY_MCP_STARTUP\\n")
sys.stderr.flush()

mcp = FastMCP("noisy")

@mcp.tool()
def echo(text: str) -> str:
    return text

if __name__ == "__main__":
    mcp.run(transport="stdio")
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / ".paicli").mkdir()
    (tmp_path / ".paicli" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "noisy": {
                        "type": "stdio",
                        "command": "python",
                        "args": [str(server)],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    async def run():
        manager = McpClientManager(tmp_path)
        return await manager.load_tools()

    tools = asyncio.run(run())

    assert any(tool.name == "mcp__noisy__echo" for tool in tools)
    captured = capsys.readouterr()
    assert "NOISY_MCP_STARTUP" not in captured.err


@pytest.mark.parametrize(
    "bad_response",
    [
        {"code": 1000, "msg": "身份验证失败。", "success": False, "secret": "PRIVATE"},
        {"unexpected": "PRIVATE"},
        "invalid JSON PRIVATE",
    ],
)
def test_http_error_is_concise_and_other_servers_still_load(
    tmp_path,
    monkeypatch,
    caplog,
    bad_response,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".paicli").mkdir()
    (tmp_path / ".paicli" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "bad": {"url": "https://mcp.test/bad", "timeout": 1},
                    "good": {"url": "https://mcp.test/good", "timeout": 1},
                },
            }
        )
    )

    def respond(request):
        if request.url.path == "/bad":
            if isinstance(bad_response, str):
                return httpx.Response(
                    200,
                    text=bad_response,
                    headers={"content-type": "application/json"},
                )
            return httpx.Response(200, json=bad_response)
        if request.method != "POST":
            return httpx.Response(405)
        message = json.loads(request.content)
        if "id" not in message:
            return httpx.Response(202, headers={"content-type": "application/json"})
        if message["method"] == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "good", "version": "1"},
            }
        else:
            assert message["method"] == "tools/list"
            result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], "result": result})

    original_client = httpx.AsyncClient

    def mock_client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr("paicli.mcp.client.httpx.AsyncClient", mock_client)

    async def run():
        manager = McpClientManager(tmp_path)
        tools = await manager.load_tools()
        return manager, tools

    manager, tools = asyncio.run(run())
    assert any(tool.name == "mcp__good__echo" for tool in tools)
    assert not any(tool.name.startswith("mcp__bad__") for tool in tools)
    assert set(manager.last_errors) == {"bad"}
    error = manager.last_errors["bad"]
    assert "check the MCP URL and credentials" in error
    if isinstance(bad_response, dict) and "code" in bad_response:
        assert "1000" in error
    assert "PRIVATE" not in error
    assert "PRIVATE" not in caplog.text
    assert "Error parsing JSON response" not in caplog.text
    assert _count_mcp_servers(manager) == 1
