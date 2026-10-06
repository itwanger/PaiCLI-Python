# Parallel Search MCP

这个示例通过 PaiCLI 已有的 Streamable HTTP MCP client 添加可选的联网搜索和网页提取工具。
[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) 的匿名访问免费，
不需要 API Key；免费层有速率限制，搜索使用服务端管理的 Fast 模式。PaiCLI 的 LLM 调用仍需要
你自己的模型配置和 Key。

## 配置

在需要启用搜索的项目中创建 `.paicli/mcp.json`，将本目录 [mcp.json](mcp.json) 中的
`parallel-search` 条目合并到 `mcpServers` 中。如果项目还没有 MCP 配置，可在本仓库根目录执行：

```bash
mkdir -p .paicli
cp examples/parallel-search/mcp.json .paicli/mcp.json
```

已有配置时不要直接覆盖文件。项目级同名 server 会覆盖用户级配置；这个条目不含认证头，
因此使用匿名免费层。`User-Agent` 标识 PaiCLI client，`timeout` 设置 MCP 请求超时（秒）。

## 使用

```bash
uv run paicli mcp list
uv run paicli --plain -p "使用 parallel-search 搜索 Python asyncio TaskGroup 的官方文档，给出链接和要点"
```

工具发现后，远端工具注册为 `mcp__parallel-search__<tool-name>`。可以在交互模式中用 `/tools`
查看工具名，再要求 Agent 使用对应工具。结果经 PaiCLI 的工具执行器返回给 Agent，远端工具
的只读标注仍决定是否需要审批；单次非交互查询不会静默批准需要审批的工具。

配置不会替换内置的 DuckDuckGo `web_search`，也不会更改默认 LLM provider。
如需禁用，将条目中的 `enabled` 改为 `false`，然后重启 PaiCLI。删除该条目可能重新启用
用户级配置中的同名 server。

如果 `/tools` 中缺少远端工具，先用 `paicli mcp list` 检查配置，再检查网络连接。
遇到限流时，查看工具返回的错误和服务的免费层限制，稍后重试。
