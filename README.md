# PaiCLI Python

PaiCLI Python 是一个运行在终端里的 AI Agent CLI，面向真实项目开发场景：读写文件、搜索代码、执行命令、联网检索、调用 MCP 工具、保存记忆、生成快照、恢复现场，并通过 Runtime API 对外提供线程、turn、事件和后台任务能力。

![](https://cdn.paicoding.com/stutymore/best-city-ai-agent-jd-20260708142704.png)

这个仓库是 PaiCLI 的 Python 版本。它不是一个空壳 Demo，而是按真实 CLI 产品来做：核心路径有测试覆盖，也经过本地 smoke 和真实终端运行验证。

## 配套教程路线

如果你是为了学习 Agent 工程、准备简历或准备面试，可以先看这条教程路线：

[PaiCLI 学习路线：手搓一个 Java 版 Claude Code](https://paicoding.com/paicli-learning-path)

这篇路线不是单纯教你“从第一行源码看到最后一行”，而是按真实学习和求职路径来组织：

- 先把 PaiCLI 在本地跑起来，直观看到 ReAct、工具调用、Plan 模式和联网搜索是怎么工作的
- 再把项目能力拆成可以写进简历的模块，比如 ReAct、Plan-and-Execute、Memory、RAG、MCP、HITL、多模态和 Runtime API
- 然后围绕简历里写到的模块去深挖源码，并同步准备对应的 Agent 面试题
- 最后通过 debug、改 bug、加工具、整理踩坑笔记，把项目真正变成自己的工程经验

教程目录覆盖实战篇、简历篇和面试篇，适合作为学习 PaiCLI Java 版和理解本 Python 版设计取舍的路线图。

![](https://cdn.paicoding.com/stutymore/paicli-python-launch-20260708161001.png)

## 功能特性

- 交互式终端 Agent，基于 Rich 和 prompt-toolkit 渲染
- 单次 prompt 模式，适合脚本、管道和自动化调用
- OpenAI-compatible 流式 LLM 客户端，默认面向 DeepSeek 配置
- 支持 `DEEPSEEK_API_KEY` 等 provider-specific API Key
- ReAct 工具调用循环，支持 thinking、tool call、tool result、final output 和 usage 事件
- 内置文件、Shell、grep、glob、记忆、网页搜索、网页抓取、代码搜索等工具
- HITL 人工确认、命令/路径安全策略和 JSONL 审计日志
- MCP client，支持 stdio 和 Streamable HTTP MCP server
- Chrome DevTools MCP 配置助手
- PaiCLI 自身也可以作为 MCP server 暴露内置工具
- Runtime API，支持线程、turn、事件日志和持久化后台任务
- SQLite 长期记忆和本地代码索引
- Agent run 前后自动创建快照，支持恢复现场
- 支持本地图片和远程图片输入，并根据模型能力自动降级

## 环境要求

- Python 3.11 或更新版本
- [uv](https://docs.astral.sh/uv/)
- 可选：`rg`，用于更快的本地搜索
- 可选：Chrome DevTools MCP 需要 Node.js 20.19.0 LTS 或更新版本、npm/npx 和 Chrome

## 快速开始

```bash
git clone https://github.com/itwanger/PaiCLI-Python.git
cd PaiCLI-Python
uv sync --extra dev
uv run paicli --help
```

启动交互模式：

```bash
uv run paicli
```

单次查询：

```bash
uv run paicli -p "帮我总结这个项目"
```

检查当前环境：

```bash
uv run paicli doctor --cwd .
```

## 配置

PaiCLI 的配置优先级如下：

1. 内置默认配置
2. `~/.paicli/config.json`
3. 项目级 `.paicli/config.json`
4. 项目级 `.env`
5. CLI 参数
6. 当前进程环境变量

可以像 Java 项目一样，把 DeepSeek Key 写到项目 `.env` 里：

```dotenv
PAICLI_PROVIDER=deepseek
PAICLI_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=your_key_here
```

也可以使用 PaiCLI 通用 Key：

```dotenv
PAICLI_PROVIDER=deepseek
PAICLI_MODEL=deepseek-v4-flash
PAICLI_API_KEY=your_key_here
```

当前支持的 provider-specific API Key 包括：

- `DEEPSEEK_API_KEY`
- `GLM_API_KEY`
- `STEP_API_KEY`
- `KIMI_API_KEY`

通过命令行临时覆盖 provider 和 model：

```bash
uv run paicli --provider deepseek --model deepseek-v4-flash
```

连接本地 OpenAI-compatible 服务：

```bash
PAICLI_PROVIDER=openai-compatible \
PAICLI_BASE_URL=http://127.0.0.1:11434/v1 \
PAICLI_MODEL=qwen2.5-coder \
uv run paicli -p "解释这个仓库"
```

## 交互命令

进入 `uv run paicli` 后，可以使用这些 slash commands：

```text
/help
/exit
/clear
/context
/memory
/memory search <query>
/memory clear
/save <fact>
/config
/tools
/hitl on|off|always|auto|never
/policy
/audit [N]
/index [path]
/search <query>
/plan <task>
/team <task>
/model
/skill
/skill show <name>
/mcp
/task
/task add <task>
/task cancel <task_id>
/task log <task_id>
/snapshot
/snapshot clean
/restore <snapshot-id-or-index>
```

## 内置工具

PaiCLI 内置了一组 Agent 可以调用的本地工具和联网工具：

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

写文件、执行命令、远程 MCP 写操作、恢复快照等危险动作，会经过 policy、HITL 和 audit 处理。

## 联网工具

`web_search` 使用 DuckDuckGo HTML 搜索，返回标题、URL 和摘要。

`web_fetch` 可以抓取公开 HTTP/HTTPS 页面，并做基础正文提取。它会拒绝 `file://`、loopback、私有网络和内网地址，降低 SSRF 风险。

如果需要登录态、浏览器状态或 JS 渲染页面，建议使用 Chrome DevTools MCP。

## MCP

PaiCLI 可以连接 MCP server，并把远端工具动态注册为：

```text
mcp__<server-name>__<tool-name>
```

初始化项目级 Chrome DevTools MCP 配置：

```bash
uv run paicli mcp init-chrome --scope project
```

它会写入 `.paicli/mcp.json`，内容类似：

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "chrome-devtools-mcp@latest",
        "--no-usage-statistics"
      ]
    }
  }
}
```

连接已有 remote-debugging Chrome：

```bash
uv run paicli mcp init-chrome \
  --scope project \
  --browser-url http://127.0.0.1:9222
```

查看已配置的 MCP server：

```bash
uv run paicli mcp list
```

把 PaiCLI 自身作为 MCP server 暴露：

```bash
uv run paicli mcp serve --transport stdio
uv run paicli mcp serve --transport http --port 3000
```

HTTP smoke：

```bash
curl -sS -X POST http://127.0.0.1:3000 \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Chrome DevTools MCP 会把浏览器页面和 DevTools 状态暴露给 Agent。不要随意把包含个人账号、敏感数据或生产后台的 Chrome 会话授权给 Agent。

## Runtime API

PaiCLI 内置轻量 Runtime API，适合外部系统接入线程、turn、事件和后台任务。

启动服务：

```bash
PAICLI_RUNTIME_API_KEY=dev-key \
uv run paicli serve --http --port 8080
```

创建线程：

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/threads \
  -H 'x-api-key: dev-key'
```

发送 turn：

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/threads/<thread_id>/turns \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-key' \
  -d '{"message":"总结这个项目"}'
```

读取事件：

```bash
curl -sS http://127.0.0.1:8080/v1/threads/<thread_id>/events \
  -H 'x-api-key: dev-key'
```

创建并查看后台任务：

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/tasks \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-key' \
  -d '{"message":"后台总结这个仓库"}'

curl -sS http://127.0.0.1:8080/v1/tasks \
  -H 'x-api-key: dev-key'
```

## 图片输入

PaiCLI 支持在 prompt 里引用图片：

```text
分析这张截图 @image:./screenshots/page.png
```

也支持绝对路径和远程图片：

```text
解释这张图 @image:/Users/me/Desktop/diagram.png
看看这个图片 @image:https://example.com/image.png
```

本地图片会自动压缩、缩放，并在需要时把透明底铺成白底，再转为 data URL。如果当前 provider/model 不支持多模态输入，PaiCLI 会自动降级为文本元信息，不会把不支持的图片 payload 发给模型。

## 快照

每次 Agent run 都会尽力创建项目快照：

- `pre-turn`
- `post-turn`

快照保存在 `~/.paicli/snapshots/`，不会写入项目 `.git`。

REPL 中可以使用：

```text
/snapshot
/restore 1
/snapshot clean
```

## SDK

```python
from paicli.sdk import create_default_engine

engine = create_default_engine(cwd=".")
result = engine.ask_complete("解释这个项目")
print(result.text)
```

## 开发

安装开发依赖：

```bash
uv sync --extra dev
```

运行检查：

```bash
uv run python -m ruff check .
uv run python -m ruff format --check .
uv run python -m pytest
uv build
```

常用 smoke：

```bash
uv run paicli --version
uv run paicli --help
uv run paicli doctor --cwd .
uv run paicli --plain -p hello
```

## 和 Java / TypeScript 版本的关系

Python 版覆盖了 Java / TypeScript 版本里公开、开放协议相关的主要 Agent CLI 能力，包括 CLI、REPL、工具调用、MCP、Runtime API、记忆、快照、联网工具和图片输入。

Java 版本里还有一个私有的微信 iLink 通道。Python 仓库没有内置这个私有通道，因为它依赖账号、扫码登录和协议凭证，不应该用假实现冒充。

更详细的实现对齐情况见 [docs/parity.md](docs/parity.md)。

## License

MIT. See [LICENSE](LICENSE).
