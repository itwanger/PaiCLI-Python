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
- Plan-and-Execute 模式，使用独立 Planner 生成 DAG，并按依赖批次执行可并行任务
- Multi-Agent 协作模式，包含 Planner、Worker、Reviewer、依赖调度、并行 worker、review
  重试，以及可切换到独立 Plan-and-Execute 的子 Agent
- 内置文件、Shell、grep、glob、记忆、网页搜索、网页抓取、代码搜索等工具
- HITL 人工确认、命令/路径安全策略和 JSONL 审计日志
- MCP client，支持 stdio 和 Streamable HTTP MCP server
- Skill 系统，支持内置、用户级和项目级分层、输入 Top-K 匹配、`load_skill` 当前回合懒加载，
  以及经 HITL 确认的 `save_skill` 流程沉淀
- Chrome DevTools MCP 配置助手
- PaiCLI 自身也可以作为 MCP server 暴露内置工具
- Runtime API，支持有历史的 thread、turn、事件日志，以及带原子抢占、租约恢复、取消保护、
  项目隔离和 `react|plan|team` 模式的持久化后台任务
- 静态项目记忆 + SQLite 动态长期记忆，支持元数据、去重、TTL、容量治理和相关性召回
- 上下文预算与压缩：达到可用输入预算的 80% 后压缩旧轮次，保留近期消息和完整工具调用对
- 完整 usage、缓存命中/未命中 Token、reasoning Token 和可配置成本估算
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

选择运行模式并输出机器可读的 usage/cost：

```bash
uv run paicli --mode plan -p "先读取 README，再验证项目" --json
uv run paicli --mode team --worker-mode plan -p "并行审计核心模块" --json
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
- `ZAI_API_KEY`（GLM 官方推荐）
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
/memory stats
/memory delete <id>
/memory clear
/save <fact>
/config
/tools
/hitl default|auto
/policy
/audit [N]
/index [path]
/search <query>
/plan <task>
/team <task>
/team --plan <task>
/model
/model <model-id>
/model <provider> <model-id>
/usage
/skill
/skill list
/skill show <name>
/skill on <name>
/skill off <name>
/skill reload
/mcp
/task
/task add [--mode react|plan|team] <task>
/task cancel <task_id>
/task log <task_id>
/snapshot
/snapshot clean
/restore <snapshot-id-or-index>
```

`/model` 会打开交互式模型选择器：`Tab` 或左右方向键在 `Default`、`Custom`
之间切换，上下方向键选择模型，`Enter` 立即切换当前 Agent。`Custom` 中可以选择已保存的
BYOK 模型、创建新的 DeepSeek/GLM/OpenAI-compatible 配置，或按 `d` 删除配置。自定义配置
保存在权限为 `0600` 的 `~/.paicli/models.json`；建议填写 API Key 环境变量名，只有显式输入
API Key 时才会把密钥写入该文件。

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
- `search_memory`
- `load_skill`
- `save_skill`
- `search_code`
- `revert_turn`

写文件、执行命令、远程 MCP 写操作、恢复快照等危险动作，会经过 policy、HITL 和 audit 处理。
`save_skill` 也必须经过 HITL；模型可以提议沉淀，但不会静默改变后续行为。

交互模式下按 `Shift+Tab` 可在两种会话权限模式间切换：

- `Default`：使用启动时的 HITL、工作区路径和命令安全策略。
- `Auto (full access)`：当前会话内不再请求审批，并关闭路径与命令守卫；再次按
  `Shift+Tab` 会恢复启动时的默认策略。

## Skill 匹配与沉淀

Skill 按 `builtin -> user -> project` 加载，同名时后层覆盖前层：

- builtin：产品默认能力
- user：`~/.paicli/skills/*/SKILL.md`，跨项目复用
- project：`.paicli/skills/*/SKILL.md`，最贴近当前仓库并拥有最高优先级

每次用户输入先用 name、description、tags 做中英文词法/字符 n-gram Top-K 匹配，再把候选交给模型决定是否调用 `load_skill`。Skill 正文只在真正加载后进入当前 ReAct 的下一模型轮；每个并发子 Agent 都有独立 Skill 缓冲区，不会串线。

当一次成功流程具备稳定输入、明确步骤和可复用边界时，模型可以调用 `save_skill` 提议写入 project 或 user 层。该工具默认拒绝覆盖已有 Skill，并强制人工确认。

## 记忆、动态 Prompt 与上下文压缩

PaiCLI 把记忆分成三层：

- 短期记忆：当前 thread/session 的原始消息、工具调用和工具结果
- 静态长期记忆：`AGENTS.md`、`PAI.md`、`.paicli/PAI.md` 及自定义 prompt 文件；人工维护、可版本控制
- 动态长期记忆：按项目 scope 隔离的 SQLite 记录；包含 kind、source、importance、confidence、TTL、访问次数和内容哈希

动态记忆不会再无条件取“最近 8 条”。每个请求会按当前问题自动召回 Top-K，并把结果放进明确标注为 untrusted data 的动态 Prompt；模型觉得候选不足时，还可以调用 `search_memory` 深搜。写入端会拒绝空值/超长值，通过规范化哈希去重，并按项目容量淘汰低价值记录。

Prompt 分为可缓存的静态前缀和逐请求重建的动态后缀。静态前缀承载身份、规则和项目指令；动态后缀承载当前时间、cwd、模型、工具以及与当前问题相关的记忆。

可用输入预算按 `context_window - max_output_tokens - reserve_tokens` 计算。默认在该预算的 80% 触发压缩，压到 55% 左右，为后续输出、工具结果和无 tokenizer 估算误差留出空间。压缩摘要只属于短期会话，不会自动晋升为长期记忆。

## 模型、Token 与费用

默认 provider/model 是 `deepseek/deepseek-v4-flash`。DeepSeek V4 Flash/Pro 的内置 profile 使用 1M 上下文，并带有截至 2026-07-17 的官方每百万 Token 价格；价格会变化，因此可以用 `llm.context_window` 和 `llm.prices` 覆盖，未知 OpenAI-compatible 模型应显式配置。

流式请求开启 `stream_options.include_usage`，并解析 `choices=[]` 的 usage-only 块、cache hit/miss 和 reasoning Token。REPL 用 `/usage` 查看最近一次普通 ReAct，单次 CLI 用 `--json` 获取完整 usage/cost。成本以供应商返回的实际 Token 为准，不能只用“代码行数”精确推算。

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

可选的免费、免 Key 联网搜索配置见 [Parallel Search MCP 示例](examples/parallel-search/README.md)。
该示例使用已有的 Streamable HTTP client，不改变内置 DuckDuckGo 搜索或默认模型配置。

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
  -d '{"message":"后台总结这个仓库","mode":"plan"}'

curl -sS http://127.0.0.1:8080/v1/tasks \
  -H 'x-api-key: dev-key'
```

也可以只启动队列消费者，不暴露 HTTP：

```bash
uv run paicli worker --workers 2 --cwd .
```

任务队列按项目目录隔离；worker 使用 SQLite 原子事务领取任务，并通过 lease/heartbeat 恢复崩溃任务。运行中取消会阻止 worker 把迟到结果重新覆盖为 completed。

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

plan_result = engine.plan_complete("先读取 README，再总结项目结构")
team_result = engine.team_complete("让多个 Agent 并行检查核心模块")
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

Python 版覆盖了 Java / TypeScript 版本里公开、开放协议相关的主要 Agent CLI 能力，包括 CLI、REPL、ReAct、Plan-and-Execute、Multi-Agent、Skill、SDK、工具调用、MCP、Runtime API、记忆、快照、联网工具和图片输入。

Java 版本里还有一个私有的微信 iLink 通道。Python 仓库没有内置这个私有通道，因为它依赖账号、扫码登录和协议凭证，不应该用假实现冒充。

更详细的实现对齐情况见 [docs/parity.md](docs/parity.md)。

## License

MIT. See [LICENSE](LICENSE).
