# RFC-007：MCP 集成设计
**项目**：PitWall Agent
**RFC 编号**：RFC-007
**作者**：Red Cyan
**状态**：已通过
**创建日期**：2026-08-06
**最后更新**：2026-08-06

---

# 1. 摘要
本请求意见稿（RFC）明确 PitWall Agent 如何通过 Model Context Protocol（MCP）对外暴露能力。

MCP 是 Anthropic 于 2024 年底开源的模型上下文协议，已成为 AI 应用生态的互操作事实标准。本项目把「FIA 法规 RAG、实时赛况、新闻检索」三类核心能力封装为标准 MCP 工具，使任何支持 MCP 的客户端（Claude Desktop、`mcp inspector`、各类 Agent 框架、集成开发环境）都可以直接调用，无需定制 API 对接。

---

# 2. 背景与动机

## 2.1 现状
- 能力入口仅限 FastAPI `/api/*` 与内部 Agent 工具（`app/tools/`）。
- 外部 AI 客户端若要使用法规问答，需要单独开发 REST 客户端、处理认证与数据结构。

## 2.2 目标
- G1：以标准化协议暴露核心能力，降低第三方集成成本。
- G2：复用既有领域服务（`RegulationQAService` / `RaceService` / `NewsService`），保证单一事实来源，不复制业务逻辑。
- G3：工具行为与内部 Agent 工具保持一致（同样的回答格式、同样的证据结构、同样的拒绝语义）。
- G4：本地一键可跑、可被 `mcp inspector` 与 Claude Desktop 直接拉起，便于演示与调试。
- G5：可测试——工具注册、入参出参、错误路径全部有单元测试覆盖。

## 2.3 非目标
- 本 RFC 不含 MCP Client 方向（由 PitWall Agent 作为客户端调用外部 MCP 工具），留待后续迭代。
- 不做多租户认证与授权（当前为本地/局域网演示拓扑）。

---

# 3. 技术方案

## 3.1 依赖
选用官方 Python SDK `mcp`（`mcp>=1.9,<2`，当前锁定 1.29.0），使用其高层封装 **FastMCP**。

> 说明：mcp 2.x 移除了 FastMCP 模块，改用更低层的 MCPServer 绑定 API；本 RFC 锁定 1.x 以使用行业通用的 `@mcp.tool()` 声明式写法，代码可读性与可移植性更高。

## 3.2 模块结构
```text
app/mcp/
  __init__.py         # 导出 PitWallServer / build_server
  __main__.py         # uv run python -m app.mcp  (stdio 入口)
  pitwall_server.py   # PitWallServer：FastMCP 实例 + 10 个工具方法
```

## 3.3 工具清单
| 工具 | 复用服务 | 说明 |
| --- | --- | --- |
| `regulation_ask` | `RegulationQAService.ask` | 法规 RAG 问答，返回 answer/answer_status/citations/confidence |
| `regulation_debug_retrieval` | `RegulationQAService.debug_retrieval` | 检索链路调试（keyword/vector/hybrid/rerank 各阶段） |
| `race_schedule` | `RaceService.list_schedule` | 赛历 |
| `race_next` | `RaceService.get_next_race` | 下一场比赛 |
| `race_previous` | `RaceService.get_previous_race` | 上一场比赛 |
| `race_driver_standings` | `RaceService.list_driver_standings` | 车手积分榜 |
| `race_constructor_standings` | `RaceService.list_constructor_standings` | 车队积分榜 |
| `race_results` | `RaceService.get_race_results` | 最近已结束轮次或指定轮次的正赛结果 |
| `news_search` | `NewsService.search_articles` | 新闻关键词检索（支持中文别名） |
| `news_recent` | `NewsService.list_recent_articles` | 最近新闻 |

## 3.4 传输层
- **stdio**（默认）：`uv run python -m app.mcp`，适合本地、Claude Desktop、`mcp inspector` 拉起。
- **Streamable HTTP**：FastAPI 应用挂载 `/mcp` 子应用（`app.main` 中 `app.mount("/mcp", PitWallServer().streamable_http_app())`），支持远程/浏览器客户端。

## 3.5 返回契约
每个工具返回 JSON 序列化 dict，结构统一：
```json
{ "success": true, "...": "工具特有字段" }
{ "success": false, "error": "人类可读错误说明" }
```
- 法规问答的证据不足场景沿用既有确定性拒绝语义（`answer_status=insufficient_evidence`），不会把无证据答案包装成成功。
- 未找到比赛/文章等空结果返回 `success=false` 与明确 error，而非空壳成功。

## 3.6 一致性保障
工具方法即普通可测方法，`_register_tools` 将它们绑定到 FastMCP：
```python
for method in tool_methods:
    self.app.tool()(method)
```
测试直接调用方法本身，同时通过 `app.list_tools()` 断言注册集合，形成双保险。

---

# 4. 安全与边界
- 服务构造无网络/数据库副作用，`PitWallServer()` 可在 import 期安全实例化（与既有 `app/api/rules.py` 模块级构造一致）。
- 不引入新的外部依赖面：HTTP 出站复用既有 `http_retry` 与超时配置。
- 已知边界：当前无认证、无速率限制；若暴露到公网需在网关层补充。

---

# 5. 测试策略
`tests/mcp/test_pitwall_server.py`：
- 断言 10 个工具全部注册且名称集合精确匹配。
- 每个工具的 stub 服务出参结构断言（法规问答/拒绝语义/检索调试/赛历/结果/积分/新闻）。
- 错误路径：空 query 的 `news_search` 返回结构化错误。

运行时冒烟：`uv run python -m app.mcp` 通过官方 `ClientSession` 完成 initialize → list_tools → call_tool 全链路。

---

# 6. 使用方式

## 6.1 本地调试
```bash
uv run python -m app.mcp
uvx mcp dev app/mcp/pitwall_server.py   # mcp inspector 图形化调试
```

## 6.2 Claude Desktop
在配置中注册命令式 MCP server：
```json
{ "command": "uv", "args": ["run", "python", "-m", "app.mcp"] }
```

## 6.3 Streamable HTTP
```bash
docker compose up -d
# 任意 MCP client 指向 http://localhost:8000/mcp
```

---

# 7. 未来演进
- RFC-007.1：PitWall Agent 作为 MCP Client，把外部 MCP 工具动态注入 ToolDispatcher。
- RFC-007.2：OAuth 认证与租户隔离，支持公网暴露。
- RFC-007.3：工具级 metric 上报（复用 Prometheus 现有指标）。
