from __future__ import annotations

import asyncio
import json
from pathlib import Path

from paicli.bootstrap import build_tool_registry
from paicli.config import load_config
from paicli.mcp.config import load_mcp_server_specs

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "parallel-search" / "mcp.json"


def test_parallel_example_loads_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
    config_dir = tmp_path / ".paicli"
    config_dir.mkdir()
    (config_dir / "mcp.json").write_bytes(EXAMPLE.read_bytes())

    spec = load_mcp_server_specs(tmp_path)["parallel-search"]
    assert spec.type == "streamable_http"
    assert spec.url == "https://search.parallel.ai/mcp"
    assert spec.headers == {"User-Agent": "PaiCLI-Python/0.1.0"}
    assert spec.enabled
    assert spec.timeout == 30
    assert spec.env == {}


def test_parallel_example_disabled_keeps_builtin_search(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_dir = tmp_path / ".paicli"
    config_dir.mkdir()
    data = json.loads(EXAMPLE.read_text())
    data["mcpServers"]["parallel-search"]["enabled"] = False
    (config_dir / "mcp.json").write_text(json.dumps(data))
    config = load_config(project_root=tmp_path)

    registry, manager = asyncio.run(build_tool_registry(config=config, cwd=str(tmp_path)))
    assert "web_search" in registry.list_names()
    assert not any(name.startswith("mcp__parallel-search__") for name in registry.list_names())
    assert manager is not None
    assert not manager.last_errors
    assert config.llm.provider == "deepseek"
