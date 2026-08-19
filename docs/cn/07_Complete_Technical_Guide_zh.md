# PitWall Agent 完全技术指南

> 面向对象：项目的"所有者"（哪怕一行代码都没写过）。
> 目标：读完这份文档，你能从头到尾讲清楚这个项目的每一个文件、每一条数据流、每一个设计决策，并回答面试中的任何深挖问题。
> 阅读方法：按顺序读第一遍建立全局观；面试前重点复习第三、四、七部分；写简历时参考第八部分。

---

# 目录

- **第一部分 · 入门**
  - 1. 这个项目是什么
  - 2. 技术栈全景
  - 3. 快速启动（本地开发全流程）
  - 4. 项目目录结构全景
- **第二部分 · 请求全链路（先建立整体认知）**
  - 5. 一次最简单的对话发生了什么
  - 6. 一次规则问答发生了什么（RAG 路径）
  - 7. 一次多步复合问答发生了什么（Agent 路径）
- **第三部分 · 后端逐模块详解**
  - 8. 应用入口：app/main.py 与中间件
  - 9. API 层：全部 29 个端点
  - 10. Schema 层：全部 Pydantic 模型
  - 11. 服务层：ChatService / MemoryService / QAService / NewsService / RaceService / StrategyService
  - 12. 数据访问层：NewsRepository / RuleRepository
  - 13. 数据库：表结构、迁移、pgvector
- **第四部分 · Agent 核心深度（面试主战场）**
  - 14. 意图路由 IntentRouter
  - 15. 规划器 Planner（多步任务分解）
  - 16. 工具调度器 ToolDispatcher（$ref 数据传递）
  - 17. LangGraph 运行时 RuntimeGraph（节点、状态、路由）
  - 18. 反思器 Reflector（ReAct 正向推理循环）
  - 19. 回答格式化 ResponseFormatter（多步汇总）
  - 20. ToolCallingModelAdapter（LangGraph 内原生工具规划）
  - 21. AgentService（上下文拼装、协议开关、流式）
- **第五部分 · RAG 与知识库**
  - 22. 法规数据管线：PDF → 结构化解析 → chunking → embedding → pgvector
  - 23. 检索链路：查询改写、向量/关键词/混合检索、RRF、重排、护栏
  - 24. 消融实验与质量数字
- **第六部分 · 记忆与多轮对话**
  - 25. 会话历史（SessionService、Redis、TTL）
  - 26. 上下文压缩与长期记忆（MemoryService）
- **第七部分 · 评测与质量体系**
  - 27. 四层评测体系总览
  - 28. 每个评测脚本的指标与门禁
  - 29. 测试组织（tests/ 目录）
- **第八部分 · 前端**
  - 30. 页面与路由
  - 31. 组件详解
  - 32. API 封装与 SSE 流式处理
  - 33. 样式方案与响应式
- **第九部分 · 部署、CI 与运维**
  - 34. Docker Compose 拓扑
  - 35. Dockerfile 多阶段构建
  - 36. CI 流水线（7 个 job）
  - 37. 监控：Prometheus 指标与 Grafana
  - 38. 结构化日志与 MCP
- **第十部分 · 面试速查**
  - 39. 高频追问与回答要点
  - 40. 常见深挖问题的标准答案
- **附录**
  - A. 配置项全表（.env.example 逐项解释）
  - B. API 端点全表
  - C. 数据库表全表
  - D. 工具 action 全表
  - E. 评测案例规模与字段
  - F. Prometheus 指标全表

---

# 第一部分 · 入门

## 1. 这个项目是什么

**一句话**：PitWall Agent 是一个以 F1（一级方程式赛车）为垂直场景的 AI 问答助手，它把"聊天机器人"、"知识库问答（RAG）"、"实时数据工具"和"自主 Agent"四件事做在了一个工程里。

**一个比喻**：想象你面前有一堵"车队墙（pit wall）"——F1 比赛时车队工程师待的地方，那里能看到一切数据、规则、新闻，并快速决策。这个项目就是把那堵墙做成 AI：你问它"红旗规则是什么"它翻规则书回答你，你问"维斯塔潘积分多少"它去实时数据源拉给你，你问"诺里斯最近的新闻违反了什么规则"它会自己拆成"先查新闻→再查规则"两步去做。

**功能清单**（面试开场介绍用）：

| 能力 | 说明 |
| --- | --- |
| 多轮聊天 | 会话历史、上下文压缩、长期记忆（Redis 可选） |
| FIA 规则问答 | 基于 2026 F1 规则 PDF 的 RAG，带条款级引用 |
| 新闻 | 双 RSS 源摄取（formula1.com + motorsport.com）、搜索、洞察、规则联动分析 |
| 赛况数据 | 实时赛历/积分榜（Jolpica/Ergast API），进程内缓存 + Redis last-good 降级 |
| 策略分析 | 基于规则+新闻上下文的进站/轮胎策略建议 |
| Agent 能力 | 意图识别、多步任务分解（2-4 步依赖链）、ReAct 正向推理循环（失败/证据不足自动重规划）、原生 function calling 共存路径 |
| 可观测性 | 结构化 JSON 日志、16 个 Prometheus 指标、Grafana 看板、trace 面板 |
| 质量体系 | 四层评测：单元测试（327+）、Agent golden eval（66 条）、RAG eval（60 条）、QA judge |

**这个项目在面试中的定位**：它不是一个"demo"，而是一个有完整工程闭环（测试、评测、CI、监控、文档、部署）的 AI 应用。面试官看重的三件事它都有：**工程规范、RAG 深度（带消融实验）、Agent 设计（多步规划 + 反思循环）**。

## 2. 技术栈全景

### 2.1 后端

| 技术 | 版本/说明 | 用途 |
| --- | --- | --- |
| Python | 3.12 | 主语言 |
| FastAPI | — | Web 框架（异步、自动 OpenAPI 文档） |
| LangGraph | ≥1.2.7 | Agent 编排图（intent → plan → execute → judge 循环） |
| SQLAlchemy 2.x | — | ORM（psycopg3 驱动） |
| PostgreSQL 17 + pgvector | pgvector/pgvector:pg17 | 主数据库 + 向量检索（1024 维 embedding） |
| Alembic | — | 数据库迁移 |
| Redis 7 | redis:7-alpine | 会话存储（可选）、长期记忆（可选）、last-good 数据缓存 |
| OpenAI SDK | — | LLM 调用（DeepSeek 兼容端点），含原生 function calling |
| sentence-transformers | BAAI/bge-m3 + bge-reranker-v2-m3 | 嵌入模型与重排模型 |
| PyMuPDF / pypdf | — | PDF 解析（法规数据摄取） |
| feedparser + BeautifulSoup | — | RSS 新闻摄取 |
| MCP (Model Context Protocol) | mcp>=1.9 | 以 MCP server 形式暴露工具（`/mcp` 挂载） |
| Prometheus 客户端 | — | 指标采集 |
| pytest / ruff / pyright | — | 测试 / lint / 类型检查 |

### 2.2 前端

| 技术 | 版本 | 用途 |
| --- | --- | --- |
| Next.js 16 | App Router + Turbopack | 框架 |
| React 19 | — | UI |
| TypeScript 5.9 | strict 模式 | 类型 |
| react-markdown + remark-gfm | — | 消息 Markdown 渲染 |
| lucide-react | — | 图标 |
| 手写 CSS 变量 | globals.css，赛车红 #d7182a | 样式（Tailwind 装了但没用） |
| vitest / Playwright | — | 单元测试 / E2E 测试 |

### 2.3 基础设施

| 组件 | 说明 |
| --- | --- |
| Docker Compose | postgres + redis + backend + frontend + prometheus + grafana（后两个在 observability profile 下） |
| GitHub Actions | 唯一 workflow `ci.yml`，7 个 job |
| Prometheus + Grafana | 监控（Grafana 匿名登录，端口 3001） |

### 2.4 为什么是这个组合（面试可能会问）

- **LangGraph 而不是手写 while 循环**：图结构让"节点可测"（每个节点是纯函数，输入输出都是显式 state），也为将来加子图/多 Agent 留结构。这正是后来升级多步计划时没有推翻重来的原因。
- **pgvector 而不是向量数据库**：规则问答需要"条款 + 向量 + 元数据过滤"在一起查，pgvector 让向量和业务数据在同一事务里，省一套基础设施；对 6198 个 chunk 的规模完全够用。
- **手写 CSS 而不是 Tailwind/组件库**：UI 只有两个页面，手写更可控；全局 CSS 变量让主题统一。
- **模块级单例而不是 FastAPI Depends 注入**：服务之间相互依赖，模块级单例（`chat_service = ChatService()`）代码更直白；代价是测试时要用构造注入（`ChatService(agent_service=...)`）替换依赖——这也是项目里 stub 测试特别多的原因。

## 3. 快速启动（本地开发全流程）

```powershell
# 0. 前置：安装 Python 3.12、uv、Docker Desktop
# 1. 安装依赖
uv sync

# 2. 启动基础设施（Postgres+pgvector 和 Redis）
docker compose up -d postgres redis

# 3. 初始化数据库（建表）
uv run python scripts/init_pgvector_db.py        # 等价于 alembic upgrade head

# 4. （可选）导入法规语料到数据库
#    如果不想导入，系统会自动回退读取 data/regulations/processed/chunks.json
uv run python scripts/import_regulation_chunks.py --input data/regulations/processed/chunks.json

# 5. 配置 .env（从 .env.example 复制，填入 LLM_API_KEY）
#    LLM_API_KEY=sk-xxx   # DeepSeek 或兼容 OpenAI 的 key

# 6. 启动后端（开发模式，热重载）
uv run uvicorn app.main:app --reload

# 7. 启动前端（另一个终端）
cd frontend
npm install
npm run dev          # http://localhost:3000

# 8. 验证
# 后端健康检查：http://localhost:8000/health
# OpenAPI 文档：http://localhost:8000/docs
# 前端：http://localhost:3000
```

**关键提示**：
- `uv sync` 用的是 `pyproject.toml` + `uv.lock`（锁文件），保证依赖可复现。
- 后端启动时若 `NEWS_INGEST_ON_STARTUP=true`，会用后台线程抓一次 RSS 新闻（默认 15 条），失败不阻塞启动。
- 数据库迁移在 `Dockerfile` 里是容器启动命令的一部分（`alembic upgrade head && uvicorn ...`），本地开发需手动跑一次 `init_pgvector_db.py`。
- 不配 LLM key 项目也能跑：所有依赖 LLM 的环节（规划、判断、回答生成）都有确定性 fallback。

## 4. 项目目录结构全景

```
PitWall-Agent/
├── app/                          # 后端主代码（Python 包）
│   ├── main.py                   # FastAPI 入口：中间件、路由注册、MCP 挂载
│   ├── agents/                   # ★ Agent 核心
│   │   ├── intent_router.py      # 意图识别（关键词 + LLM 双路径）
│   │   ├── planner.py            # 规划器（多步任务分解）
│   │   ├── runtime_graph.py      # LangGraph 运行时（AgentState + 节点 + 路由）
│   │   ├── reflector.py          # 反思器（ReAct 裁判）
│   │   ├── tool_dispatcher.py    # 工具调度（build_plan / execute_plan / $ref 插值）
│   │   ├── response_formatter.py # 回答格式化（每种 intent 的输出模板）
│   │   └── function_calling.py   # 原生 tool calling schema 与单次模型适配器
│   ├── api/                      # 路由层（薄，只做参数解析和响应）
│   │   ├── router.py             # 根路由 + 健康检查 + /metrics
│   │   ├── chat.py               # 聊天（普通 + SSE 流式）+ 会话管理
│   │   ├── agent.py              # 低层 Agent 调试端点（deprecated）
│   │   ├── news.py               # 新闻 CRUD + 搜索 + 洞察 + 规则联动
│   │   ├── race.py               # 赛历/积分榜
│   │   ├── rules.py              # 规则问答 + 检索调试 + 语料状态
│   │   └── strategy.py           # 策略分析
│   ├── config/
│   │   └── settings.py           # pydantic-settings 全部配置（80+ 项）
│   ├── core/
│   │   ├── logging.py            # 结构化 JSON 日志
│   │   ├── metrics.py            # Prometheus 指标（16 个）
│   │   ├── request_context.py    # request_id 的 ContextVar
│   │   └── mcp_server.py         # MCP server（把工具暴露给 MCP 客户端）
│   ├── db/
│   │   ├── engine.py             # SQLAlchemy engine / SessionLocal
│   │   ├── models.py             # 三张 ORM 模型
│   │   └── init_db.py            # 跑 alembic upgrade
│   ├── middleware/
│   │   ├── request_context.py    # 注入 request_id
│   │   └── access_log.py         # 访问日志 + HTTP 指标
│   ├── repositories/
│   │   ├── news_repository.py    # 新闻 CRUD + ILIKE 搜索
│   │   └── rule_repository.py    # ★ RAG 数据层（向量/关键词/混合检索，约 1180 行）
│   ├── schemas/                  # 全部 Pydantic 模型（chat/agent/rules/news/race/strategy/chunk/rag/pdf/regulation_document）
│   ├── services/
│   │   ├── agent_service.py      # ★ Agent 编排入口（协议开关、上下文、fallback）
│   │   ├── chat_service.py       # ★ 会话编排（历史、记忆、流式事件协议）
│   │   ├── memory_service.py     # 长期记忆（偏好标记 + 语义召回）
│   │   ├── session_service.py    # 会话存取 + 压缩（SessionStoreFactory）
│   │   ├── context_compaction_service.py  # LLM 摘要压缩
│   │   ├── qa_service.py         # ★ RAG 问答（分类、检索、生成、证据判定）
│   │   ├── knowledge_service.py  # 语料管理（active corpus、摄取入口）
│   │   ├── query_rewriter.py     # 查询改写（仅中文触发 LLM）
│   │   ├── general_answer_service.py  # 开放问题兜底 + 实时数据护栏
│   │   ├── news_service.py / news_ingestion_service.py / news_insight_service.py / news_rule_analysis_service.py
│   │   ├── race_service.py / race_data_provider.py / static_race_data.py
│   │   ├── strategy.py           # StrategyAnalysisService
│   │   ├── regulation_ingestion_service.py / regulation_parser.py / chunker.py / pdf_reader.py / text_cleaner.py
│   │   ├── embedding_service.py  # BGE-M3 嵌入
│   │   ├── reranker.py           # 交叉编码器重排
│   │   ├── data_cache.py         # Redis last-good 缓存
│   │   ├── http_retry.py         # 带重试的上游请求
│   │   ├── qa_grounding.py       # 确定性落地校验（无 LLM）
│   │   └── llm/
│   │       ├── client.py         # LLMClient（chat / stream_chat / chat_tools）
│   │       ├── judge.py          # LLM-as-judge（在线评测）
│   │       └── prompts.py / schemas.py  # 遗留模板（未被引用）
│   ├── tools/                    # 领域工具（Tool 协议：invoke(**kwargs) -> ToolResult）
│   │   ├── base.py               # ToolResult 数据类 + Tool 协议
│   │   ├── news_tool.py / race_tool.py / regulation_tool.py / strategy_tool.py / general_tool.py
│   └── middleware/...            # （见上）
├── tests/                        # 后端测试（pytest，327+ 用例）
│   ├── agents/                   # Agent 核心单测（planner/react_loop/runtime_graph/reflector/formatter/dispatcher/intent/function_calling）
│   ├── api/                      # 端点测试
│   ├── services/                 # 服务层测试（chat/agent/memory/session/qa/news/race/...）
│   ├── repositories/             # 数据层测试
│   ├── rag/                      # 检索测试
│   ├── tools/                    # 工具测试
│   ├── evals/                    # 评测 harness（agent golden / rag / qa）
│   ├── mcp/                      # MCP 测试
│   └── infrastructure/           # 需要真实 Postgres/Redis 的测试
├── scripts/                      # 运维/评测脚本（12 个）
│   ├── init_pgvector_db.py       # 初始化数据库
│   ├── build_regulation_chunks.py# 法规 PDF → 结构化语料 + embedding + 入库激活
│   ├── import_regulation_chunks.py / embed_regulation_chunks.py / resize_regulation_embedding_column.py
│   ├── run_agent_eval.py         # Agent golden 评测
│   ├── run_rag_eval.py           # RAG 检索评测（keyword/vector/hybrid）
│   ├── run_qa_eval.py            # QA 评测（offline 确定性 / online LLM judge）
│   ├── benchmark_api.py          # 压测
│   ├── ingest_formula1_news.py / refresh_news.py / import_news_articles.py
│   └── smoke_test_llm.py         # LLM 连通性
├── migrations/                   # Alembic 迁移（2 个：initial_schema、clause_aware_corpus）
├── data/
│   ├── regulations/
│   │   ├── raw/                  # 6 个 FIA 2026 规则 PDF（源资产，不入 Docker 镜像）
│   │   └── processed/            # chunks.json（6198 chunks）、corpus_manifest.json、structured/
│   └── evals/                    # agent_cases.jsonl(66)、qa_cases.jsonl(21)、rag_cases.jsonl(60)
├── docs/                         # 中文文档（00-06）+ evals 基线 + rfcs
├── frontend/                     # Next.js 前端
│   ├── app/                      # layout.tsx、page.tsx（聊天）、rag/page.tsx（RAG Lab）
│   ├── components/               # message-bubble、evidence-panel、session-list、workspace-nav
│   ├── services/api.ts           # API 封装 + SSE 解析
│   ├── types/chat.ts             # 全部前端类型
│   ├── lib/chat-utils.ts         # 引用提取工具
│   ├── e2e/                      # Playwright E2E
│   └── Dockerfile / next.config.ts / vitest.config.mts / playwright.config.ts
├── ops/                          # prometheus.yml + grafana provisioning + dashboard
├── docker-compose.yml
├── Dockerfile                    # 后端多阶段构建
├── pyproject.toml                # 依赖 + pytest markers + coverage 门禁
├── alembic.ini
└── .env.example                  # 58 行配置模板
```

**记忆方法（面试时画目录树）**：从入口往内数——`main.py`（挂路由）→ `api/`（端点）→ `services/`（业务）→ `repositories/`（数据）→ `db/`（表）；旁边一支 `agents/`（编排）+ `tools/`（工具）；对面一支 `frontend/`；脚下 `scripts/` + `tests/` + `ops/`。

---

# 第二部分 · 请求全链路（先建立整体认知）

> 这一部分不讲代码细节，只讲"一条消息进来后，系统里发生了什么"。
> 先把这三条链路在脑子里走通，后面每个模块的细节才有地方安放。

## 5. 一次最简单的对话发生了什么

场景：你在前端输入框敲了"你好"并按回车。

**第 0 步：浏览器侧（frontend/app/page.tsx）**
1. `sendMessage("你好")` 被调用：本地**乐观追加**一条用户消息到聊天区（不等后端响应，先显示出来），创建一个 `AbortController`（用于"停止生成"按钮），然后调用 `services/api.ts` 的 `streamChatMessage`。
2. `streamChatMessage` 向后端 `POST /api/chat/stream` 发请求，body 是 `{"message": "你好", "session_id": null}`（新会话）。它拿到响应后开始 `ReadableStream` 循环读字节，把 SSE 事件逐条解析出来（`parseSseEvent`），通过 `onEvent` 回调交给页面。

**第 1 步：后端入口（app/api/chat.py + app/main.py）**
3. 请求穿过中间件链：`CORSMiddleware`（跨域）→ `RequestContextMiddleware`（生成 `request_id`，写入 ContextVar 和响应头）→ `AccessLogMiddleware`（计时、记 HTTP 指标和访问日志）。
4. 路由 `POST /api/chat/stream` 收到请求，调用 `chat_service.stream_chat(message, session_id)`。注意：`chat_service` 是模块级单例（`chat_service = ChatService()`），整个进程只有一个。

**第 2 步：会话与记忆（app/services/chat_service.py、session_service.py、memory_service.py）**
5. `stream_chat` 先发一个 SSE 事件 `session_started`（带 `session_id`：因为没有传 session_id，`SessionStore` 会新建一个）。
6. 取"上一轮意图"作为 fallback：新会话没有历史，`fallback_intent=None`。
7. `memory_service.build_context(session, message)` 组装记忆上下文——新会话就是空上下文。
8. 把用户消息写入会话历史（`append_user_message`），并发 `status("thinking")`、`status("routing")` 等阶段事件给前端。

**第 3 步：Agent 处理（app/services/agent_service.py + app/agents/）**
9. `agent_service.stream_query(message, fallback_intent=None, conversation_context="")` 被放进一个 **daemon 工作线程** 里跑（这样才能让 SSE 主循环一边收 token 一边转发）。
10. 线程内：`LLMQueryPlanner.plan("你好")` 判断意图 → "你好"没有关键词命中任何业务意图，启发式路由到 `general`（通用问答）→ `ToolDispatcher` 构建计划：调用 `general_tool` 的 `answer` 动作。
11. `GeneralAnswerService.answer("你好")` 检查护栏关键词（"你好"不在"需要实时数据"的黑名单里）→ 调用 LLM（DeepSeek）生成回答，或者用内置问候语兜底。回答逐 token 通过 `on_token` 回调塞进 `queue.Queue`。
12. 主循环从队列取 token，发 `message_delta` SSE 事件（前端每收到一个就把打字机文本追加一段）。

**第 4 步：收尾**
13. LLM 生成完毕 → `message_completed` 事件（带完整 `ChatResponse`：最终回答、历史、会话摘要）。
14. 前端收到后：用服务端返回的 `history` **整体替换**本地历史（以服务端为准），清空流式状态，刷新会话列表。
15. 后端收尾：把 assistant 回答追加进历史 → `compact_session`（检查是否需要压缩）→ `memory_service.record_interaction`（提取长期记忆）→ 记流式指标（`STREAM_DURATION`、`STREAM_TTFT`）。

**这条链路你该记住的 5 个关键点**：
- 前端先乐观显示用户消息，再靠 SSE 事件流做打字机效果；
- 历史记录、记忆、意图 fallback 都在 `ChatService` 层完成，`AgentService` 只负责"单次问答"；
- LLM 在**工作线程**里跑，主循环只做队列转发，保证流式不阻塞；
- 如果全程一个 token 都没有（比如工具直接给了答案），后端会把最终答案按 **24 字符** 切块、每 15ms 发一块，模拟打字机（buffered 模式）；
- `request_id` 从中间件一路贯穿日志，方便排查一次请求的完整链路。

## 6. 一次规则问答发生了什么（RAG 路径）

场景：你问"什么是封闭区（parc ferme）？"

这条链路的核心在 `app/services/qa_service.py`（`RegulationQAService.ask`）+ `app/repositories/rule_repository.py`（检索管线）。

**前置知识：规则语料从哪来？**
6 个 FIA 2026 规则 PDF（Section A-F）经过 `scripts/build_regulation_chunks.py` 管线变成 6198 个结构化 chunk（每条条款、每个表格、每篇索引块），每个 chunk 配 1024 维 embedding（BGE-M3），存进 PostgreSQL 的 `regulation_chunks` 表。运行时若数据库里没有语料，`RuleRepository` 会自动回退读 `data/regulations/processed/chunks.json` 文件。

**问答流程**（`RegulationQAService.ask`）：
1. **查询分类**（`_classify_query`）：用关键词判断问题类型——`fact_lookup`（问具体条款，如"B5.6.4 要求什么"）、`section_overview`（问某个 Section 整体）、`document_overview`（问整份文档）。不同类型走不同的检索策略。
2. **检索**（`rule_repository.search_relevant_chunks(question, top_k=3)`）——这是全项目最复杂的函数，详见第 23 节，先记结论：
   - 查询改写（仅含中文时用 LLM 改写，英文走确定性路径）；
   - 双路召回：pgvector 余弦相似度（向量路）+ BM25 关键词打分（关键词路）；
   - **RRF（Reciprocal Rank Fusion）** 融合两路候选；
   - 两轮重排：启发式（精确条款 +30 分、短语命中加分）→ 交叉编码器 bge-reranker（模型重排）→ 关键词护栏（若关键词路第一名得分极高，整体改用关键词结果）；
   - 对命中的 chunk 做**相邻条款扩展**（同一个 clause 的相邻 part 一起带上，保证上下文完整）。
3. **生成**（`_generate_answer`）：把检索到的 chunk 作为上下文，LLM `temperature=0` 生成回答，同时输出 `Citation` 列表（引用哪份文档、哪一节、哪一条）。
4. **证据判定**：根据检索得分和引用一致性，给回答打 `answer_status`：
   - `answered`：证据强（最终分 ≥ 阈值且短语命中或关键词分达标）；
   - `partial_evidence`：证据弱（分数在 1-8 之间）——回答会标注"信息有限"；
   - `insufficient_evidence`：检索不到可靠条款——LLM 会明确拒绝回答。
5. 返回 `RuleAskResponse`：`answer` + `citations` + `retrieved_chunks` + `answer_status` + `confidence` + `evidence_count` + `source_mode` + `query_type`。

**前端能看到什么**：聊天页的 Evidence 面板显示引用条款和检索片段；RAG Lab 页面（`/rag`）能逐步查看 keyword/vector/hybrid 每个阶段的候选。

**为什么这套设计值得讲**（面试点）：检索不是"embedding 相似度 top-k"一把梭，而是 双路召回 + RRF 融合 + 关键词护栏 + 重排 + 证据判定 的完整管线；并且**不达标的证据宁可拒绝回答**（`insufficient_evidence`），不编造——这是 RAG 应用最该有的严谨性。

## 7. 一次多步复合问答发生了什么（Agent 路径）

场景：你问"诺里斯最近的新闻，他违反了哪条规则？"

这个问题需要两步：先搜新闻，再拿新闻内容去查规则。这是一个典型的**多步任务分解**场景。

**第 1 步：意图识别（app/agents/intent_router.py）**
- 启发式路由扫描消息关键词："新闻"命中 news 意图，"规则"命中 regulation 意图。意图路由返回 `news`（新闻优先级更高）。

**第 2 步：规划（app/agents/planner.py）**
- `LLMQueryPlanner.plan()` 先构建"启发式计划"（单步：新闻搜索）。然后检查 `_has_multi_intent_signal`：消息同时含"新闻"和"规则"关键词 → 复合信号 → **强制走 LLM 规划**，并放大 token 预算（160 → 320）。
- LLM 返回多步计划 JSON：
  ```json
  {
    "steps": [
      {"intent": "news", "tool_name": "news_tool", "action": "search",
       "params": {"query": "诺里斯", "limit": 5}, "output_key": "news_hit"},
      {"intent": "regulation", "tool_name": "regulation_tool", "action": "ask",
       "params": {"question": "$ref:news_hit.articles.0.title"}, "output_key": "rule_check"}
    ]
  }
  ```
  注意第二步的 `question` 是 `$ref:news_hit.articles.0.title`——一个**步骤间引用**：运行时会把第一步搜索结果的第一个文章标题替换进来。
- `_parse_and_normalize` 校验每一步：intent/action 必须在白名单内（防 LLM 幻觉出工具名）、参数规范化、`output_key` 去重。校验不过就整体回退启发式单步计划。

**第 3 步：执行（app/agents/runtime_graph.py，LangGraph）**
- LangGraph 图的状态 `AgentState` 里带着 `plan_steps`（步骤队列）、`step_index`（当前步）、`step_outputs`（各步输出）。
- 节点依次执行：`classify_intent → plan_tool → execute_tool → judge_result →（循环或）format_response`。
- 第一步执行新闻搜索，结果存入 `step_outputs["news_hit"]`；
- `judge_result` 发现还有剩余步骤且当前成功 → 返回 `continue_plan`（不消耗修复轮次预算）→ 回到 `plan_tool` 推进到第二步；
- 第二步执行前做 `$ref` 插值：`interpolate_params` 把 `$ref:news_hit.articles.0.title` 解析成真实标题（支持 dict 路径和列表索引）→ 调用规则工具。

**第 4 步：格式化（app/agents/response_formatter.py）**
- 多步执行后，`result` 里带 `step_results`（每步的输出摘要）。formatter 把前置步骤摘要（相关新闻标题）+ 最终回答（规则结论）拼成一段完整回答："相关新闻：Norris penalised in China GP…\n\n根据 FIA 规则…"。

**第 5 步：失败怎么办（ReAct 循环）**
- 如果第二步规则查询返回 `insufficient_evidence`（证据不足），`reflector.judge` 会被触发：把**结构化 observation**（answer_status、证据数、命中条款）给 LLM，LLM 决定 finish 或给出 `next_plan`（比如换个问法重查规则）→ 回到 `plan_tool` 替换剩余计划继续执行。
- 整个循环受 `max_steps` 限制（默认 5，`AGENT_REACT_MAX_STEPS` 可调）；**无 LLM key 时走确定性路径**：证据不足直接给出"信息有限"的回答，不循环、不挂起。

**为什么这套设计值得讲**（面试点）：Agent 不是"带工具的聊天机器人"——它有 任务分解（多步依赖链 + $ref 数据传递）、观察-再推理（judge 在失败/证据不足时重规划）、可评测（66 条 golden cases 断言工具序列）三层能力，且单步场景自动退化为确定性路径。

---

# 第三部分 · 后端逐模块详解

> 现在开始"事无巨细"。建议对照源码阅读本节。

## 8. 应用入口：app/main.py 与中间件

`app/main.py` 全文件只有 47 行，但它是理解整个后端装配方式的钥匙：

```python
configure_logging()                       # ① 模块级：logging.basicConfig(level=..., format="%(message)s")
app = FastAPI(title="PitWall Agent", version="0.1.0", description=..., lifespan=lifespan)
app.add_middleware(AccessLogMiddleware)   # ② 先注册（后执行）
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CORSMiddleware, ...)   # 后注册（先执行）
app.include_router(router)                # ③ 挂载全部业务路由
mcp_server = PitWallServer()              # ④ MCP server
app.mount("/mcp", mcp_server.streamable_http_app())
```

**逐项解释**：

### 8.1 lifespan（启动生命周期）
唯一动作：当 `settings.news_ingest_on_startup=True`（默认 true）时，启动一个 **daemon 线程** `_ingest_news_on_startup()` 去抓 RSS 新闻（`NewsIngestionService().ingest(limit=settings.news_ingest_startup_limit)`，默认 15 条）。成功/失败都记结构化日志，**异常被吞掉不阻断启动**——启动抓新闻是可选的锦上添花，不能让它拖垮服务。

注意：**没有**数据库连接初始化（SQLAlchemy engine 是惰性的，第一次查询才连）、**没有** Redis ping（Redis 只在 readiness 检查或创建 RedisSessionStore 时连接）。

### 8.2 中间件执行顺序（面试易错点）
Starlette 中间件"后注册先执行"，所以实际请求链路是：

```
CORSMiddleware → RequestContextMiddleware → AccessLogMiddleware → 路由
```

- **CORSMiddleware**：`settings.resolved_cors_allow_origins` 是逗号分隔字符串切成的 list。特殊处理：如果配置里含 `"*"`，则 `allow_origins=["*"], allow_credentials=False`（浏览器规范：`*` 和 credentials 不能共存）；否则 `allow_origins=列表, allow_credentials=True`。methods/headers 都是 `["*"]`。
- **RequestContextMiddleware**（`app/middleware/request_context.py`）：`request_id = 请求头 X-Request-Id 或 uuid4().hex` → 写入 `request.state.request_id` + `ContextVar`（`app/core/request_context.py` 的 `set_request_id`，`get_request_id()` 供全局读取）→ `try: call_next finally: clear_request_id()` → 响应头回写 `X-Request-Id`。
- **AccessLogMiddleware**（`app/middleware/access_log.py`，继承 `BaseHTTPMiddleware`）：`perf_counter` 计时 → Prometheus 指标 `HTTP_REQUESTS.labels(method, route, status)` + `HTTP_DURATION.labels(method, route)`（route 标签来自 `request.scope["route"].path`，取不到退化为 `request.url.path`）→ 结构化日志 `log_structured("http_request", method, path, status_code, duration_ms, request_id, origin, ...)` → **异常时记 500 指标和日志后 re-raise**（不吞异常，交给 Starlette 默认错误处理）。

### 8.3 两个"没有"（同样重要）
- **没有** `app/deps.py`，**没有** FastAPI `Depends()` 依赖注入——服务全部是模块级单例（`chat_service = ChatService()`）。`app/db/engine.py` 里定义了 `get_db_session()` 生成器但**没有任何调用者**（业务 DB 访问都在 service/repository 内部 `SessionLocal()`）。
- **没有**异常处理器、**没有**静态文件挂载（唯一 mount 是 `/mcp`）。业务 404/503 由各路由抛 `HTTPException`。

### 8.4 结构化日志（app/core/logging.py）
`log_structured(logger, event, **fields)` 输出单行 JSON：`{"timestamp"(UTC ISO), "level", "event", "request_id"(来自 ContextVar), **fields}`，`json.dumps(ensure_ascii=False, default=str)`。全项目统一用这个，日志可被任何 JSON 采集器（ELK/Loki）直接消费。

### 8.5 指标（app/core/metrics.py）
全部 16 个 Prometheus 指标（详见附录 F），归类：HTTP（2）、工具（2）、LLM（2）、RAG（2）、流式（3）、语料（2 Gauge）、上游（3）。命名规范：`pitwall_<领域>_<类型>_total` / `pitwall_<领域>_duration_seconds`。

## 9. API 层：全部 29 个端点

路由组织：`app/api/router.py` 创建根 `APIRouter()` 并 include 六个子 router（rules/news/race/strategy/agent/chat）。下面按文件列出全部端点。

### 9.1 根路由（app/api/router.py）

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/` | GET | `{"name": "PitWall Agent"}` |
| `/health` | GET | 完整健康检查（见下），恒 200 |
| `/health/live` | GET | liveness，恒 `{"status": "ok"}` |
| `/health/ready` | GET | readiness，状态非 ok 时返回 **503** |
| `/metrics` | GET | Prometheus 文本格式（`include_in_schema=False`，不进 OpenAPI） |

**`_health_payload()` 五项检查**（`/health` 和 `/health/ready` 共用）：
- `database`：`SessionLocal()` 里 `SELECT 1`，异常 → degraded；
- `redis`：仅当 `session_backend == "redis"` 才真的 `ping()`，否则 `not_configured`（所以 memory 模式下 /health 不报 redis 问题）；
- `llm`：只检查配置是否齐全（key + base_url + model），**不真的调 LLM**；
- `rag`：联表统计 active corpus 的 `chunk_count` / `embedding_count`，并顺手更新 Gauge 指标；
- `news`：`count(news_articles)`。
总状态：全部 ∈ {ok, configured, not_configured} → `"ok"`，否则 `"degraded"`。

### 9.2 聊天（app/api/chat.py，prefix=/api/chat）★ 核心

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/chat` | POST | 普通对话（非流式） |
| `/api/chat/stream` | POST | **SSE 流式对话** |
| `/api/chat/sessions` | GET | 列会话（`limit` 1-100 默认 20） |
| `/api/chat/{session_id}` | GET | 会话元数据（无 → 404） |
| `/api/chat/{session_id}` | DELETE | 删除会话 |
| `/api/chat/{session_id}/history` | GET | 会话历史 |

每个聊天端点还在响应头写 `X-PitWall-Endpoint-Mode: primary` 和 `X-PitWall-Endpoint-Note`（标记主路径，便于排障）。

**SSE 流式实现细节**（面试爱问）：
- 用 `StreamingResponse(media_type="text/event-stream")`（不是 sse-starlette 的 EventSourceResponse），头含 `Cache-Control: no-cache`、`Connection: keep-alive`；
- 帧格式：`event: {event}\ndata: {json}\n\n`（标准 SSE，双换行结尾）；
- **没有心跳帧**——长连接可靠性依赖代理层 keep-alive；
- 事件协议（service 层 `stream_chat` 产出）：`session_started` → `status(message=thinking)` → `status(routing)` → `status(retrieving)` → `status(generating)` → `message_delta`×N（token 流）→ `message_completed`（完整 ChatResponse）；异常 → `error`；
- 工作线程 + `queue.Queue` + `threading.Event` 实现 token 中转；客户端断开时 `StreamCancelled` 异常中断线程；
- **buffered 模式**：若全程零 token（工具直接给答案），把最终答案按 **24 字符**切块、每块间隔 `stream_buffered_chunk_delay_ms`（默认 15ms）逐块发，模拟打字机；
- 指标：`STREAM_REQUESTS.labels(success|error|cancelled, token|buffered)`、`STREAM_TTFT`、`STREAM_DURATION`。

### 9.3 低层 Agent（app/api/agent.py，prefix=/api/agent）

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/agent/query` | POST | **deprecated=True**：单次低层 Agent 查询（调试用），`AgentQueryRequest{message}` → `AgentQueryResponse` |

没有异常处理（错误直接 500），响应头 `X-PitWall-Endpoint-Mode: debug`。用途：curl 调试 Agent 而不用走聊天链路。

### 9.4 新闻（app/api/news.py，prefix=/api/news）

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/news` | GET | 最新文章（limit 1-100 默认 20） |
| `/api/news/search` | GET | 搜索（`q` 必填、limit 1-50 默认 10） |
| `/api/news/refresh` | POST | 手动触发 RSS 摄取（limit 1-100 默认 20）→ `{ingested_count, articles}` |
| `/api/news/{article_id}` | GET | 单篇详情（无 → 404） |
| `/api/news/{article_id}/insights` | GET | LLM 洞察分析 |
| `/api/news/{article_id}/rules-analysis` | GET | 规则联动分析（top_k 1-10 默认 3） |

### 9.5 赛况（app/api/race.py，prefix=/api/race）

全部走 `race_service`，数据来自 Jolpica/Ergast API，默认赛季 `current`：

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/race/schedule` | GET | 赛季赛历 |
| `/api/race/next` | GET | 下一场（无 upcoming → 404） |
| `/api/race/previous` | GET | 上一场 |
| `/api/race/standings/drivers` | GET | 车手积分榜 |
| `/api/race/standings/constructors` | GET | 车队积分榜 |

每个端点都有可选 query 参数 `season`。

### 9.6 规则（app/api/rules.py，prefix=/api/rules）

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/rules/ask` | POST | RAG 问答（`RuleAskRequest{question}`） |
| `/api/rules/retrieve/debug` | POST | **检索链路调试**（返回每个阶段候选，RAG Lab 页面就用它） |
| `/api/rules/corpus/active` | GET | 当前激活语料（无 → **503** "No active regulation corpus is available."） |

### 9.7 策略（app/api/strategy.py，prefix=/api/strategy）

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/strategy/analyze` | POST | 策略分析（`StrategyAnalysisRequest` → `StrategyAnalysisResponse`：recommendation/confidence/facts/analysis/assumptions/cautions） |

### 9.8 MCP

`app/main.py` 里 `app.mount("/mcp", ...)`——把工具层以 MCP streamable HTTP transport 暴露（`POST/GET /mcp/*`）。这是给支持 MCP 的客户端（如 Claude Desktop）用的，与 REST 端点并存。

## 10. Schema 层：全部 Pydantic 模型

Pydantic v2。按文件：

### 10.1 app/schemas/chat.py（会话与聊天）
- `ConversationTurn`：`role("user"|"assistant")`、`message`、`created_at`、可选 `intent`/`tool_name`（assistant 消息的元数据）
- `ChatSessionSummary`：`session_id`、`title`（默认 "New conversation"，1-80 字符）、`turn_count`（≥0）、`last_intent`?、`updated_at`
- `ChatRequest`：`message`（必填 ≥1 字符）、`session_id`?（≥1）
- `ChatResponse`：`session_id` + `response: AgentQueryResponse` + `history: list[ConversationTurn]` + `session: ChatSessionSummary`
- `ChatHistoryResponse` / `ChatSessionListResponse` / `ChatSessionDeleteResponse`（`{session_id, deleted}`）

### 10.2 app/schemas/agent.py
- `AgentQueryRequest`：`message`
- `AgentQueryResponse`：`intent`、`tool_name`、`success`、`final_answer`、`result: dict`、`error?`、`trace: dict` —— **trace 是前端证据面板的数据源**（intent/tool_name/action/answer_status/evidence_count/citations/retrieved_chunks/plan/steps/judge_outcomes...）

### 10.3 app/schemas/rules.py（RAG 相关，字段最丰富）
- `RuleAskRequest`：`question`（≥1）
- `RetrievalDebugRequest`：继承 RuleAskRequest + `top_k`（1-20 默认 5）
- `ActiveCorpusResponse`：`corpus_version`、`parser_version`、`embedding_model`?、`status`、`chunk_count`、`embedding_count`、`created_at`、`validation: dict`
- `Citation`：`document_title` + 可选 `article`/`section`/`page`/`excerpt`
- `RetrievedChunk`（15+ 字段）：`chunk_id`、`content`、`score`?、`document_title`?、`article`?、`section`?、`page`?、`page_start`?、`page_end`?、`heading_path`、`clause_id`?、`article_title`?、`chunk_type`（clause/table/article_overview）、`corpus_version`?、`document_key`?、`breadcrumb`、`part_ordinal`、`score_components: dict[str,float]`
- `RuleAskResponse`：`answer`、`citations`、`retrieved_chunks`、`answer_status`（answered/partial_evidence/insufficient_evidence）、`confidence`、`evidence_count`、`source_mode`、`query_type`
- `RetrievalDebugResponse`：`question`、`normalized_question`、`rewritten_queries`、`retrieval_queries`、`extracted_phrases`、`expanded_keywords`、`preferred_sections`、`vector_candidates`、`keyword_candidates`、`hybrid_candidates`、`retrieved_chunks`

### 10.4 app/schemas/news.py
- `NewsArticleCreate`（摄取用）：`source_name`(1-64)、`source_article_id`?、`title`(1-512)、`summary`?、`content`?、`article_url`、`author`?、`published_at`?、`tags`、`raw_payload`?
- `NewsArticleRead`（13 字段，含 `from_record`/`to_create_model` 类方法）
- `NewsRefreshResponse`、`NewsEntity`、`NewsInsightResponse`（category/summary/key_points/entities/rule_relevance）、`RuleTopicMatch`、`NewsRuleAnalysisResponse`（matched_topics/suggested_questions/related_chunks/analysis_summary）

### 10.5 其他
- `race.py`：`SessionInfo`、`RaceWeekend`、`DriverStandingEntry`、`ConstructorStandingEntry`、`RaceResultEntry`/`RaceResult`
- `strategy.py`：`StrategyAnalysisRequest`（question + race_context/regulation_context/news_context）、`StrategyAnalysisResponse`（recommendation/confidence/facts/analysis/assumptions/cautions）
- `chunk.py`：`RegulationChunk`（内部检索模型，23 字段含 chunk_type/content_hash/embedding_text/part_ordinal）
- `rag.py`：`RegulationDocumentIngestionResult`、`RegulationIngestionSummary`
- `pdf.py`：PDF 解析中间产物（PdfTextBlock/Line/Table/Page）
- `regulation_document.py`：`RegulationClause`/`RegulationArticle`/`RegulationDocument`/`CorpusValidation`/`CorpusManifest`

## 11. 服务层：业务逻辑的核心

### 11.1 ChatService（app/services/chat_service.py）——会话编排中枢

构造：`ChatService(agent_service=None, session_service=None, context_builder=None, memory_service=None)`，不传就各自 new 一个（模块级单例 `chat_service = ChatService()`）。

**`handle_chat(message, session_id=None)` 完整流程**（普通对话）：
1. `session_service.get_or_create_session(session_id)`——没有就新建；
2. `get_history(session_id)` + `get_last_intent(session_id)`——**上一轮意图作为本轮 fallback**（例如上轮问规则，这轮问"那罚多少？"，意图延续规则）；
3. `memory_service.build_context(session, current_message)`——组装记忆上下文（摘要 + 长期记忆 + 最近几轮 + 当前消息，按 token 预算裁剪）；
4. `append_user_message(...)`——用户消息先入库；
5. `agent_service.handle_query(message, fallback_intent=..., conversation_context=...)`——核心问答；
6. `append_agent_response(...)` → `compact_session(...)`（触发压缩检查）→ `_refresh_memory_context`（回填摘要）→ `_with_memory_trace`（把记忆的 trace 注入 response.trace，前端可看）；
7. `memory_service.record_interaction(...)`（提取长期记忆）；
8. 返回 `ChatResponse`。

**`stream_chat(...)` 的 SSE 事件协议**见 9.2 节。核心机制：daemon 线程 `pitwall-chat-stream` 跑 `agent_service.stream_query(message, on_token=...)`，`on_token` 回调把 token 塞进 `queue.Queue`；主生成器 `messages.get()` 阻塞消费。取消时工作线程抛 `StreamCancelled`。**零 token 时退化为 buffered 模式**（24 字符分块 + 15ms 间隔）。

### 11.2 SessionService（app/services/session_service.py）——会话存取与压缩

- `SessionStoreFactory.create()` 按 `settings.session_backend` 选择：`memory` → `InMemorySessionStore`（进程内 dict）；`redis` → `RedisSessionStore`（`Redis.from_url`，**启动即 ping 校验，失败抛 ConnectionError**）；其他值抛 `ValueError`。**没有 postgres 会话后端**。
- Redis 键设计：会话数据 + 历史轮次，TTL = `session_ttl_seconds`（默认 86400；.env.example 示例 604800 = 7 天）。
- `compact_session`：历史轮数超 `session_history_max_turns`（20）或 token 超 `memory_compaction_token_threshold`（1600）时触发压缩。

### 11.3 MemoryService（app/services/memory_service.py）——长期记忆

- 开关：`memory_long_term_enabled`（默认 true）、后端 `memory_long_term_backend`（postgres/memory/redis）、TTL 30 天、语义召回 `top_k=3`、`memory_vector_retrieval_enabled`。
- `build_context(session, message)`：把 最近 N 轮（`memory_recent_turns=4`）+ 长期记忆摘要 + 当前消息 组装成一个"渲染上下文"字符串，受 `memory_context_token_budget`（1200）预算约束。
- `record_interaction(...)`：从对话里提取**偏好标记**（比如用户是哪个车队的粉丝），写入长期记忆存储（默认 PostgreSQL 按 user_id + memory_key 持久化：preference/history 增量追加、constraint/fact 覆盖更新）。
- 记忆的"召回"支持向量相似度（语义检索，复用 embedding 服务）。

### 11.4 ContextCompactionService（app/services/context_compaction_service.py）——上下文压缩

会话变长后，用 LLM 把旧对话压缩成结构化 JSON 摘要（预算 `memory_summary_token_budget=260`）。**LLM 失败时走确定性回退**（截断保留最近轮次），保证压缩永不失败。

### 11.5 RegulationQAService（app/services/qa_service.py）——RAG 问答 ★

`ask(request)` 流程（前面第 6 节讲过，这里补充内部细节）：
1. `_classify_query(question)` → `fact_lookup` / `section_overview` / `document_overview`；
2. 按类型检索：`get_section_chunks(section, limit=6)`（每个 article 取一个代表 chunk，优先匹配 `[A-F]\d+(\.\d+)?` 格式的条款）/ `get_document_overview_chunks(limit_per_section=1)`（Section A-F 各取 1 个）/ `retrieve_regulation_chunks`（走完整混合检索）；
3. 证据强度判定 → `_generate_answer`（LLM temperature=0，带引用）/ `_build_partial_evidence_answer`（证据弱，回答会明说"信息有限"）/ 概览回答；
4. 组装 `RuleAskResponse`，`source_mode` 区分 `regulation_rag` / `regulation_overview`。

`debug_retrieval(request)`：调 `knowledge_service.debug_regulation_retrieval`，返回全链路候选（vector/keyword/hybrid/final）——RAG Lab 页面的数据源。

### 11.6 KnowledgeService（app/services/knowledge_service.py）——语料管理

- `get_active_corpus()`：查 `regulation_corpora` 表 active 的语料 + chunk 统计；
- `ingest_regulations(...)`：摄取管线入口（build 脚本调用）；
- `debug_regulation_retrieval(...)`：转发到 RuleRepository。

### 11.7 QueryRewriter（app/services/query_rewriter.py）——查询改写

`rewrite(question)`：**仅当问题含 CJK 字符时调用 LLM**（中文提问太口语化，直接检索效果差），把口语问题改写成规范的检索问法；英文问题走确定性路径（不花 LLM 钱）。token 预算 180、超时 4s，失败返回原问题。

### 11.8 GeneralAnswerService（app/services/general_answer_service.py）——开放问题兜底

`answer(question)`：
1. **护栏检查** `_requires_authoritative_tool`：27 个关键词命中（latest/today/now/current/standings/schedule/calendar/next race/news/regulation/2026/最新/今天/积分/赛程/下一站/规则...）→ 拒绝回答："这个问题需要实时或权威资料支持…"，`answer_status=insufficient_evidence`，`source_mode=general_guardrail`——**防止 LLM 编造实时数据**；
2. 否则 `LLMClient().chat(temperature=0.3)` 正常回答；
3. 空答案/异常 → `_build_fallback_answer`（问候语特殊回复 + 通用引导），`mode=fallback`。

### 11.9 NewsService 家族

- **NewsService**：薄包装（list/search/get/insights/rules-analysis）。`search_articles` 先做**中文别名展开**（`_expand_query_aliases`：把"维斯塔潘"展开成 "Max Verstappen"，遍历洞察服务的 DRIVER/TEAM/CIRCUIT_ALIASES 别名表）再入库 ILIKE 搜索——解决"中文问、英文数据"的匹配问题。
- **NewsIngestionService**：`ingest(limit)` 从 `[MotorsportRSSSource, Formula1RSSSource]` 抓 RSS → `NewsRepository.upsert_article` 去重入库。**只吃 RSS 元数据**（标题/摘要/链接/时间），不抓正文。
- **NewsInsightService**（纯规则，无 LLM）：20 组车手别名、17 组车队别名、15 组赛道别名、6 类文章分类（driver_market/race_weekend/technical/team_operations/commercial/race_control）、直接规则术语 13 个、间接 7 个。`analyze(article)`：分类 → 实体提取 → 关键点（句子切分取前 3）→ 摘要 → 规则相关性判定（direct/possible/none + 中文理由）。
- **NewsRuleAnalysisService**（新闻→规则联动）：6 个预置主题（red_flag/safety_car/unsafe_release/parc_ferme/stewards_penalty/technical_compliance），每个带预置英文检索问题。`analyze(article, top_k=3)`：主题匹配 → 生成建议问题（命中主题用预置，否则按标题生成，去重限 4 条）→ 对前 3 条问题各调 `rule_repository.search_relevant_chunks` 合并去重 → 中文总结。

### 11.10 RaceService 家族

- **RaceService** → **JolpicaRaceDataProvider**（`race_data_provider.py`）：三级降级——① 进程内缓存（TTL 300s）→ ② Jolpica/Ergast API（`api.jolpi.ca/ergast/f1`）→ ③ Redis `last_good:*` 缓存（`data_cache.py`）→ ④ **静态种子数据**（`static_race_data.py`，上次成功数据的 JSON 快照）。
- **DataCache**（last-good 缓存）：键前缀 `last_good:`，`SET EX=ttl`（86400s）。设计意图：上游挂了返回最近一次成功数据，**而不是伪造样例**——这是生产级降级思维，面试可以讲。
- **http_retry.get_with_retry**：最多 `upstream_get_max_retries+1` 次尝试，仅 429/500/502/503/504 可重试，指数退避（`backoff * 2**attempt`），记 `UPSTREAM_*` 指标（provider 维度）。

### 11.11 StrategyAnalysisService（app/services/strategy.py）

`analyze(question, race_context, regulation_context, news_context)`：把赛况、规则、新闻三类上下文 + 问题拼成 prompt 给 LLM，输出 `StrategyAnalysisResponse`（recommendation/confidence/facts/analysis/assumptions/cautions）。**事实与假设分离**（facts vs assumptions）——LLM 建议的严谨表达。

### 11.12 LLM 相关（app/services/llm/）

- **client.py**：`LLMClient(model=...)`，方法 `chat(messages, temperature, max_tokens, timeout, response_format)`（返回 str）、`stream_chat(...)`（返回 token 迭代器）、`chat_tools(messages, tools, ...)`（返回完整 `ChatCompletionMessage`，含 tool_calls，function calling 路径用）。所有方法都记 `LLM_CALLS`/`LLM_DURATION` 指标和结构化日志。`settings.llm_api_key` 同时兼容 `LLM_API_KEY` / `DEEPSEEK_API_KEY` 两个环境变量名。
- **judge.py**：`LLMJudge`（LLM-as-judge，在线 QA 评测用）。`judge(question, answer, evidence_texts, ...)` 输出 `AnswerVerdict`（groundedness_score 1-5 / helpfulness_score 1-5 / rejection_correct / violations / reasoning）。解析失败自动带修复指令重试，连续 3 次失败抛 `LLMJudgeParseError`。
- **prompts.py / schemas.py**：遗留模板（`SYSTEM_PROMPT`、`StrategyAdvice`），**未被任何代码引用**——文档里如实说明，避免你面试时被问住。

### 11.13 qa_grounding.py——确定性落地校验（无 LLM）

- `tokenize`：CJK 二元组 + ASCII 词（≥3 字符）；
- `evidence_supported_fraction(answer, evidence_texts, min_overlap_ratio=0.2)`：回答中可分析句子与证据 token 重叠率 ≥0.2 的比例——**衡量回答是否真的有证据支撑**；
- `citations_consistent(citations, chunks)`：每条引用必须匹配至少一个检索 chunk（条款级匹配，都缺条款时标题互含）。
这是 QA 离线评测的基石，也是"引用一致性 100%"数字的来源。

## 12. 数据访问层：两个 Repository

### 12.1 NewsRepository（app/repositories/news_repository.py）

| 方法 | 逻辑 |
| --- | --- |
| `upsert_article(article)` | 先按 `(source_name, source_article_id)` 查，再按 `article_url` 查；无则 INSERT；有则更新 title，按非 None 更新 summary/content/author/published_at/tags/raw_payload，**重置 is_deleted=False**（软删除复活） |
| `list_recent_articles(limit)` | `is_deleted=False`，`published_at DESC NULLS LAST, id DESC` |
| `get_article_by_id(id)` | 按主键查 |
| `search_articles(query, limit)` | query 分词取前 4 个词，`title/summary/content ILIKE '%term%'` OR 组合 |
| `list_articles_for_backfill(...)` | 按 source 过滤、可选 content 为空、id DESC |

### 12.2 RuleRepository（app/repositories/rule_repository.py）★ RAG 数据层（约 1180 行）

**关键常量**：`VECTOR_CANDIDATE_LIMIT=40`、`KEYWORD_CANDIDATE_LIMIT=40`、`HYBRID_CANDIDATE_LIMIT=50`、`MIN_RERANK_SCORE=8`（强证据阈值）、`PARTIAL_RERANK_SCORE=1`（弱证据阈值）、`MIN_KEYWORD_EVIDENCE_SCORE=6`、`KEYWORD_GUARDRAIL_SCORE=20`、`RRF_K=60`；`QUERY_STOP_WORDS`（20 个）、`QUERY_SYNONYMS`（中文→英文，如"红旗"→"red flag"）、`SECTION_KEYWORDS`（Section A-F 关键词表）。

**公开方法**：
- `search_relevant_chunks(question, top_k=3)`：`debug_retrieval` 后调 `expand_clause_context` 补相邻条款；
- `search(question, mode="keyword|vector|hybrid", top_k=5)`：评测用稳定入口；
- `get_active_corpus()`：SQL 联表统计；
- `get_section_chunks(section_code, limit=6)`：Section 概览用；
- `get_document_overview_chunks(limit_per_section=1)`：整文档概览用；
- `debug_retrieval(question, top_k)`：完整可解释管线（第 23 节细讲）。

**数据加载策略**：`_load_chunks` 优先 `_load_chunks_from_database`（active corpus 全部 chunks），失败/无库回退 `_load_chunks_from_file`（`data/regulations/processed/chunks.json`）。全部进程内缓存（`_cached_chunks` 等 6 个缓存结构）。

## 13. 数据库：表结构、迁移、pgvector

### 13.1 连接配置（app/db/engine.py）

```python
engine = create_engine(settings.sqlalchemy_database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```
`sqlalchemy_database_url` = `postgresql+psycopg://{user}:{password}@{host}:{port}/{db}`（psycopg3 驱动；`database_url` 配置项可整体覆盖）。无显式 pool 参数（psycopg3 默认池）。

### 13.2 三张表（app/db/models.py）

**regulation_chunks**（法规语料分块，核心检索对象）：
| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | Integer PK | 自增 |
| chunk_id | VARCHAR(255) 唯一索引 | 如 `fia-2026-section-a:A1.1.1:clause:p01` |
| document_title / section_code / article | VARCHAR，索引 | 元数据（A-F 各 Section） |
| page | Integer | 页码 |
| content | Text | 条款正文 |
| embedding | Vector(1024) | BGE-M3 向量（可空——未嵌入的 chunk） |
| metadata | JSON | page_start/page_end/heading_path/part_ordinal/source_path |
| corpus_version | VARCHAR(128) 索引 | 语料版本（默认 legacy） |
| document_key / clause_id / chunk_type / content_hash / article_title / embedding_text | 见迁移 0002 | 结构化语料字段 |

**regulation_corpora**（语料版本管理）：
| 列 | 说明 |
| --- | --- |
| corpus_version | VARCHAR(128) 主键 |
| parser_version / embedding_model | 解析器与嵌入模型版本 |
| source_hashes / build_parameters / validation | JSON（源文件哈希、构建参数、校验结果） |
| status | building/validated/failed/active |
| active | Boolean 索引（一次只有一个 active） |

**news_articles**（新闻）：
| 列 | 说明 |
| --- | --- |
| id PK / source_name 索引 / source_article_id | 唯一约束 `uq_news_source_article_id(source_name, source_article_id)` |
| title 索引 / summary / content / article_url（唯一）/ author / published_at 索引 | 内容字段 |
| tags / raw_payload | JSON |
| fetched_at / is_deleted | 摄取时间 / 软删除 |

### 13.3 迁移（migrations/，Alembic）

- `env.py`：运行时用 `settings.sqlalchemy_database_url` 覆盖 `alembic.ini` 里的默认连接串；`compare_type=True`（迁移可感知列类型变化）。
- **0001_initial_schema**：`CREATE EXTENSION IF NOT EXISTS vector`；建 regulation_chunks + news_articles（兼容 pre-Alembic 老库：news_articles 已存在则只 ALTER source_article_id 为 VARCHAR(255)）。
- **0002_clause_aware_corpus**：给 regulation_chunks 加 8 列（corpus_version/document_key/clause_id/chunk_type/content_hash/article_title/embedding_text）+ 建索引；新建 regulation_corpora 表；有 legacy chunks 时插入 legacy 语料记录。
- 本地初始化：`python scripts/init_pgvector_db.py`；Docker 里是启动命令 `alembic upgrade head`。

### 13.4 pgvector 用法

- 列类型 `Vector(1024)`（SQLAlchemy 的 pgvector 方言）；
- 查询：`embedding.cosine_distance(question_embedding)` + `order_by(distance)` + `limit(pool_size)`；
- 相似度 = `max(1.0 - distance, 0.0)`；
- 只在 active corpus 的 chunk 上检索（`.where(embedding.is_not(None), active.is_(True))`）。

---

# 第四部分 · Agent 核心深度（面试主战场）

> 这一部分是整个项目最值得讲的部分。每个文件、每个设计决策、每个边界情况都要能讲清楚。
> 建议一边读一边打开 `app/agents/` 的源码对照。

## 14. 意图路由 IntentRouter（app/agents/intent_router.py）

**职责**：把用户消息归类到 5 个意图之一：`news` / `race` / `regulation` / `strategy` / `general`。

**核心逻辑**：
- `route(message, fallback_intent=None)`：先扫关键词表（中文优先），命中即返回对应意图；`general` 是兜底。
- **意图优先级**：news 关键词优先（"新闻/资讯/headline"），其次 race（"积分/积分榜/车手/车队/赛程/下一站/standings"）、regulation（"规则/条例/违规/rule"）、strategy（"策略/进站/pit stop"）。
- `looks_like_follow_up(message)`：检测"那/然后/如果是"这类承接词 → 是追问，配合上一轮 fallback 意图使用。
- `route_news_article(message)` 类方法：检测 "article 42" / "新闻 42" 模式（数字）→ 定位到具体新闻文章（而不是泛泛搜索）。

**设计要点**：意图路由是"廉价先行"的——先用关键词快速定意图（零成本、确定性），只有拿不准的（general）才升级到 LLM。这就是"双路径"思想的起点。

## 15. 规划器 Planner（app/agents/planner.py）

**职责**：把用户消息变成一个可执行的工具计划（单步或多步）。

**核心数据结构**（多步升级后）：

```python
tool_plan = {
    "intent": "news",        # 顶层字段 = 第一步（向后兼容）
    "tool_name": "news_tool",
    "action": "search",
    "params": {"query": "诺里斯", "limit": 5},
    "steps": [                # ★ 统一结构：所有计划都有 steps，单步时长度 1
        {"intent": "news", "tool_name": "news_tool", "action": "search",
         "params": {"query": "诺里斯", "limit": 5}, "output_key": "news_hit"},
        {"intent": "regulation", "tool_name": "regulation_tool", "action": "ask",
         "params": {"question": "$ref:news_hit.articles.0.title"}, "output_key": "rule_check"},
    ],
}
```

**`plan(message, fallback_intent=None)` 的完整流程**：
1. `intent_router.route(message, fallback_intent)` 得到启发式意图；
2. `_build_heuristic_plan(intent, message)`——纯规则构建单步计划：news 分 list_recent（没具体话题）/search（有话题）/get_article（有 "article N"）；race 分赛历/积分榜/比赛结果；regulation/strategy/general 都是 ask/analyze/answer + question=原消息；
3. `_with_steps(...)` 把单步计划包装成 `steps` 长度 1 的统一结构；
4. `_should_use_llm_planner(message, heuristic_intent)` 决定是否升级 LLM：
   - 配置 `llm_planner_enabled=false` 且无注入 client → 不升级；
   - 意图是 general 且不是闲聊（`_is_casual_general_message`：你好/谢谢/再见等）、不是追问 → 升级；
   - **意图非 general 但命中复合信号**（`_has_multi_intent_signal`：同时含"新闻"和"规则/策略/积分"等）→ 也升级（多步分解）；
5. LLM 路径：`_build_messages` 构造 prompt（system 说明支持的 intent/action 白名单 + steps 格式说明）→ `LLMClient.chat(temperature=0, max_tokens=planner 预算)` → `_parse_and_normalize` 解析校验；
6. **校验与 fallback**：LLM 返回的 JSON 若 intent/action 不在白名单、params 不合法、steps 为空或含非法步骤 → 抛 ValueError → **整体回退启发式计划**（永远有兜底）。

**`_parse_and_normalize` 的多步解析细节**：
- 有 `steps` 数组且非空 → 逐步骤校验（intent 在 `_SUPPORTED_ACTIONS`、action 在对应白名单）；
- 每步参数规范化 `_normalize_step_params`：regulation/strategy/general 注入 `question=消息`（**已有值不覆盖**，所以 `$ref` 引用能保留）；news 的 list_recent 补 `limit=5`；get_article/get_insights/get_rules_analysis 要求整数 `article_id`（**`$ref:` 开头的引用在规划期跳过校验**，运行时才解析）；
- `output_key` 非空且不重复，否则自动生成 `step_{i}`；
- 顶层 `intent/tool_name/action/params` 取第一步——向后兼容所有旧调用方。

**多意图信号检测**（`_has_multi_intent_signal`）：news_hit（news/新闻/资讯/围场）∧（regulation_hit ∨ strategy_hit ∨ race_hit）。命中时 `_planner_max_tokens` 返回 `llm_planner_multi_max_tokens`（320，单步是 160）——多步 JSON 需要更大输出空间。

**面试要点**："为什么 planner 不用 function calling？"→ 见第 20 节的双路径论证；"LLM 乱输出工具名怎么办？"→ 白名单校验 + 启发式回退，两条防线。

## 16. 工具调度器 ToolDispatcher（app/agents/tool_dispatcher.py）

**职责**：把"计划"变成"工具调用"，并管理工具结果。

**核心方法**：
- `build_plan(intent, message)`：启发式计划构建（与 planner 的 `_build_heuristic_plan` 同源逻辑，供无 planner 场景直接使用）；
- `execute_plan(plan, on_token=None) -> ToolResult`：按 `tool_name` 找到工具实例，`invoke(**params)`（`on_token` 透传给支持流式的工具，如 regulation/general 的 LLM 生成）；**全部异常捕获**，返回 `ToolResult(tool_name, success=False, error=...)`——工具层永不向上抛异常；
- `execute_plan_steps(steps, on_token=None) -> list[ToolResult]`：多步执行器——按序执行、`$ref` 插值、**任一步失败即停**；
- **模块级函数** `interpolate_params(params, step_outputs)` / `resolve_ref(ref, step_outputs)`：`$ref:<output_key>.<field_path>` 解析，支持 dict 路径与**列表索引**（`articles.0.title`），找不到返回 None。

**工具注册**：`ToolDispatcher.__init__(news_tool, race_tool, regulation_tool, strategy_tool, general_tool)` 五个位置参数（可注入 stub）。每个工具实现 `Tool` 协议（`name` + `description` + `invoke(**kwargs) -> ToolResult`）。

**execute_plan 的兜底细节**：dispatch 用 if/elif 链按 tool_name 分发；`_on_unknown_tool` 返回失败结果；每个工具调用都记 `TOOL_CALLS.labels(tool, action, outcome)` + `TOOL_DURATION` 指标和结构化日志。

## 17. LangGraph 运行时 RuntimeGraph（app/agents/runtime_graph.py）

**职责**：整个 Agent 循环的编排者。图结构：

```
classify_intent → plan_tool → execute_tool → judge_result ──→ format_response（结束）
                      ↑                          │
                      └──── next_plan 非空 ──────┘
```

**AgentState（TypedDict）**：`message / fallback_intent / intent / tool_plan / plan_steps / step_index / step_outputs / tool_name / success / result / error / final_answer / trace / judgement / judge_reasons / steps（累加） / step_count / max_steps`。

**四个节点的职责**：
1. **classify_intent**：调 `planner.plan`；异常时 fallback 为 general 单步（绝不 500）；初始化 `plan_steps`（`tool_plan["steps"]` 或单步包装）、`step_index=0`、`step_outputs={}`；
2. **plan_tool**：三分支——① `next_plan` 是 `{"_continue": True}`（多步继续）→ `step_index += 1`，保留计划；② `next_plan` 是裁判修复计划 → **替换整个剩余计划**（保留 step_outputs 供 $ref 引用）；③ 首次进入 → 用 state 里的计划；
3. **execute_tool**：取 `plan_steps[step_index]` → `interpolate_params` 解析 $ref → `execute_plan` → 结果存入 `step_outputs[output_key]` → 追加 trace 记录（step 编号 = `max(step_count, step_index+1)`，兼顾修复轮次与计划内步骤）；
4. **judge_result**：判定优先级——**a)** 还有剩余步骤且成功 → `continue_plan`（不消耗修复预算）；**b)** `step_count >= max_steps` → `max_steps_reached`；**c)** reflector 未启用 → `judge_disabled`；**d)** 失败 ∨ 结果不完整（`_result_needs_more_info`）∨ (general 成功且配置开启) → 调 `reflector.judge`；**e)** 否则 `no_judge_needed`。

**路由**（`_route_after_judge`）：judgement.finish=False 且 next_plan 非空 → plan_tool；否则 format_response。

**`_result_needs_more_info`（正向推理触发条件，按 intent 区分）**：
- regulation：`answer_status == "insufficient_evidence"` 或 fallback 模式无答案；
- news：**只有 list_recent/search 动作**检查空文章；get_article/get_insights/get_rules_analysis 有结构化 payload 即视为完整（避免误判强制重规划）；
- race：没有任何数据字段（standings/schedule/race/race_result/season 全空）才触发。

**run() 入口**：`graph.invoke({...})` 获取最终 state → 组 `AgentQueryResponse`（intent/tool_name 取最后执行步骤，与 fallback 路径语义统一）。

**trace 字段**（前端证据面板数据源）：intent/tool_name/action/params/success/error/answer_status/confidence/evidence_count/source_mode/query_type/citations/retrieved_chunks/**plan**（计划序列）/steps（执行序列）/judge_outcomes（每次 judge 的原因）。

**checkpointer**：构造参数支持（`Checkpointer`），用于将来会话持久化；当前未启用。

## 18. 反思器 Reflector（app/agents/reflector.py）

**职责**：观察工具结果，决定"结束还是继续"（ReAct 的"反思"环节）。

**`judge(message, intent, tool_plan, tool_result, step_count, max_steps) -> judgement`**：
- `enabled` 属性：`agent_judge_enabled and (llm_api_key 存在 or 注入 llm_client)`；
- 调 `_build_messages` 构造 prompt → `LLMClient.chat(temperature=0, max_tokens=160, response_format=json_object)` → `_parse_judgement` 解析（剥代码围栏、正则抓 JSON、校验 finish 是 bool）；
- 解析失败/异常 → `{"finish": True, "reason": "judge_error", "next_plan": None}`（降级结束，不挂起）。

**结构化 observation（多步升级的关键）**：`app/agents/tool_observation.py` 是 tool-calling planner 与 Judge 共用的确定性摘要器。它保留 `answer_status/confidence/evidence_count/source_mode/query_type`、答案字段、最多 5 条 citation/evidence 元数据，以及新闻、赛事、策略的关键条目；失败结果保留 `success/error/empty`。每条 observation 是合法 JSON 且固定不超过 2400 字符，不新增 LLM 调用。完整 payload 继续存在 Agent state、response、trace 和 evidence panel 中。

**prompt 要点**：白名单重申（`news_tool:list_recent|get_article|...`）；指导"工具失败→给修正计划（get_article 失败回退 list_recent）"、"insufficient_evidence→换查询词重问"、"结果已答→finish"；禁止发明工具名。

**judgement 契约**：`{"finish": bool, "reason": str, "next_plan": {tool_name, action, params} | None}`。

## 19. 回答格式化 ResponseFormatter（app/agents/response_formatter.py）

**职责**：把工具结果变成最终的中文/英文回答。

**build(message, intent, tool_name, success, result, error)**：
- 失败 → 直接返回 error 文案；
- **多步汇总**：result 带 `step_results` 且多于 1 步 → 先把前置步骤摘要（`_summarize_step_payload`：新闻标题列表/文章摘要/洞察摘要）拼在前面，再拼最终步骤的主回答；
- 单步 → 按 intent 分派到 `_build_main_answer`。

**各 intent 的格式化**：
- news：article → "标题：摘要"；insights → 摘要+关键点前 3；rules_analysis → 分析摘要；articles 列表 → `_format_news_list`（新闻列表模板，含时间）；
- race：`_build_race_answer`——按消息提取关注对象（车手/车队/比赛），**只回答被问到的那条**（比如问维斯塔潘就只输出他的积分），未指定则列全部；含"第 N 名 / 效力于 X / 积 N 分"模板；
- regulation：`response.answer`；
- strategy：recommendation + 置信度（"置信度：high/medium/low"）+ 关键事实 + 假设/注意事项；
- general：`response.answer`。

**formatter 不接触 LLM**——它是纯模板逻辑，所有回答都来自工具结果，因此可单测（tests/agents/test_response_formatter.py 有 14 个用例：赛历/比赛/积分榜/特定车手定位/新闻洞察/来源披露等）。

## 20. ToolCallingModelAdapter（app/agents/function_calling.py）——LangGraph 内原生工具规划

**为什么存在**：回答面试题"为什么不用原生 function calling？"的最好方式就是真的实现一条（RFC-008）。两条路径共享同一 ToolDispatcher 和领域服务，不复制业务逻辑。

**工具 schema**：`build_tool_functions()` 把 14 个动作映射为 OpenAI function schema（name=动作名，description 标注 `[tool_name]` 和 intent，parameters 定义必填项如 `question`/`article_id`）。

**调用循环（run(message)）**：
```
messages = [system, user]
for step in 1..max_steps:
    reply = llm.chat_tools(messages, tools)   # tool_choice="auto"
    if reply.tool_calls:
        messages += [assistant(tool_calls)]    # 原样回灌（含 id/type/function）
        for tc in reply.tool_calls[:5]:        # 支持单轮多工具并行（上限 5）
            result = dispatcher.execute_plan(action, params)
            messages += [tool(tool_call_id, payload[:2000])]
        continue
    return reply.content                        # 无工具调用 → 最终回答
```

**接入方式**：`AGENT_PLANNER_MODE=tool_calling` 时，LangGraph 的 `model` 节点进行一次携带 tools 的模型调用；异常在同一张图内切换到 `structured`。trace 统一带 `runtime: "langgraph"` 和 `planner_mode`。

**对比结论（RFC-008 核心）**：structured 确定性、离线可测、进 CI；tool_calling 灵活（LLM 自主选工具、可并行）、需 LLM key、模型间不可复现。tool_calling 每轮只回灌有界 observation；旧批次滚动压缩为 `Previous tool observations`，当前 assistant/tool 批次仍保持 OpenAI-compatible 顺序。两者共享同一 LangGraph runtime，生产默认 tool_calling。

## 21. AgentService（app/services/agent_service.py）——编排入口

**构造**：`AgentService(planner, tool_dispatcher, reflector, response_formatter, runtime=None, logger)`。默认 self._build_runtime() 组装完整 LangGraph runtime（LangGraph 导入失败时 runtime=None → 走 fallback 路径）。

**handle_query(message, fallback_intent=None, conversation_context=None, on_token=None) 流程**：
1. `_build_effective_message`：把 conversation_context（记忆渲染上下文）拼进消息（`[Previous conversation]\n...\n[Current question]...` 模板）——让 LLM 感知多轮；
2. **规划开关**：`agent_planner_mode` 选择 `tool_calling|structured`，所有请求均调用 `LangGraphAgentRuntime.run(...)`；
3. runtime 存在 → `runtime.run(message, fallback_intent, on_token)`；
4. **fallback 路径**（无 LangGraph）：planner.plan → `execute_plan_steps`（多步支持）→ formatter.build → 组 `AgentQueryResponse`（**trace 同样含 plan/steps**，与 runtime 路径行为一致）；
5. `_with_latency_trace`：把 `latency_ms_by_stage`（agent_total/stream_total）写进 trace；
6. 结构化日志 `agent_query_completed`（intent/tool_name/success/error_type）。

**stream_query(message, ...)**：带 on_token 的版本，内部同 handle_query（LLM 生成时逐 token 回调）。

**为什么 fallback 路径要保留多步能力**：LangGraph 是第三方依赖，万一版本不兼容导入失败，系统仍要完整工作（多步 + $ref 都支持），这是工程冗余意识的体现。

---

# 第五部分 · RAG 与知识库

> 规则问答是项目里 RAG 做得最扎实的部分：数据管线（PDF→向量）、检索管线（双路召回→融合→重排）、证据判定、消融实验，一整套都有。这部分是"检索工程师"面试题的弹药库。

## 22. 法规数据管线：PDF → 结构化解析 → chunking → embedding → pgvector

### 22.1 源数据

`data/regulations/raw/` 下 6 个 FIA 2026 F1 规则 PDF（2026-06-25 版，Section A-F）：
- A 通用条款（Iss03，972KB）、B 运动（Iss07，1.17MB）、C 技术（Iss19，4.43MB）、D 财务-车队（Iss07，762KB）、E 财务-PU 制造商（Iss06，886KB）、F 运营（Iss09，452KB）。

### 22.2 管线五步（scripts/build_regulation_chunks.py → RegulationIngestionService）

**① 读取（RegulationPdfReader，app/services/pdf_reader.py）**
- 优先 PyMuPDF：`get_text("blocks")` + `get_text("dict")` 提取**带坐标的行**（含粗体/字号信息），`page.find_tables()` 抽表格；
- 页眉/页脚过滤：按 18%/86% 高度阈值 + 跨页重复文本检测（`_repeat_key` 把数字归一为 `#` 再比对）+ 噪音词（©2026/Issue/页码）；
- 失败回退 pypdf 纯文本读取。

**② 结构化解析（RegulationStructureParser，app/services/regulation_parser.py）**
- 版本 `clause-tree-v1`；标题必须含 "Section [A-F]" 否则报错；
- 行级解析：跳过目录页（`_is_contents_page`：CONTENTS:/CONVENTION: 或索引密度 ≥18%）、APPENDIX 切换 scope、`{letter}\d+(\.\d+)*` 加粗标题行开启新条款（跳过 "2026 Formula 1:" 开头的伪标题）、正文行归入段落/列表项、表格挂到当前条款；
- 输出 `RegulationDocument`（文档 → Article → Clause 的树，含段落/列表项/表格）。

**③ Chunking（RegulationChunker，app/services/chunker.py）**
- `chunk_structure(document, max_chars=1600)`：逐 article 逐 clause——
  - **正文单元** `[clause_id+标题, *段落, *列表项]` 经 `_split_units` 切分，超长单元 `_split_long_unit` 按语义标点（`; : , 空格` 与引号定义）断点切 → 每个 part 一个 `clause` 类型 chunk；
  - **表格**按 Markdown 行渲染、按行分组 → `table` 类型 chunk；
  - 每篇文章生成一个 `article_overview` 索引块（条款摘要列表）→ 让"Section 概览"类问题有落点；
- **chunk_id 格式**：`{title_slug}:{corpus_version}:{scope_id}:{clause_id}:{chunk_type}:p{part:02d}`（同 clause 多次出现加 `:o02` 序号）；
- `embedding_text = breadcrumb + "\n\n" + content`（breadcrumb 如 `Section A > A1 > A1.1.1`——**把层级信息编进向量**，这是 clause-aware 的关键 trick）；
- `content_hash = SHA-256(content)`。

**④ 校验（_validate）**
- 条款缺失率：clause/table 类型无 clause_id 占比 ≥2% 报错；
- 伪页眉检测：无点号 clause_id 且内容含 "2026 Formula 1:" 或 "©2026"；
- 页码范围、chunk_id 重复、**结构化正文覆盖率 ≥98%**（structured 字符数 / 全部字符数）；
- 校验不过**不允许激活**（status 保持 validated/failed）。

**⑤ Embedding + 入库（SqlAlchemyRegulationChunkStore）**
- `build_embedding_service()`：BGE-M3（`BAAI/bge-m3`），1024 维，batch_size=8，device=cpu；
- `stage_corpus`：单事务——删同版本 chunks/corpus → 激活时先 `UPDATE ... SET active=false WHERE active`（**原子切换，一次只有一个 active 语料**）→ 插 corpus 记录 → 逐条插 chunk；
- manifest（corpus_manifest.json）记录 source_hashes（6 个 PDF 的 SHA-256）、chunk_max_chars、embedding_model、parser_version。

### 22.3 产物

- `chunks.json`：**6198 个 chunk**（4.28MB），每条含 20 个字段（chunk_id/document_title/section_code/article/page_number/page_start/page_end/heading_path/chunk_index/content/source_path/corpus_version/document_key/article_title/clause_id/chunk_type/content_hash/embedding_text/part_ordinal）；
- `corpus_manifest.json`：corpus_version `fia-2026-20260625`、status active、validation valid（clause_missing_rate 0.0、body_coverage_rate 1.0）；
- `structured/fia-2026-section-{a..f}.json` + `.md`（评审用）。

**面试讲法**："我的语料不是'把 PDF 每 500 字切一段'，而是按 FIA 文档本身的条款树切——每条 clause 是一个 chunk，段落太长按语义标点切 part，同 clause 的相邻 part 检索时可以自动补齐（expand_clause_context）。chunk 里嵌了 breadcrumb 层级信息，所以'封闭区'这种概念能命中 A 部分的结构条款。整条管线带校验：正文覆盖率必须 ≥98% 才能激活。"

## 23. 检索链路：查询改写、双路召回、RRF、重排、护栏

`RuleRepository.debug_retrieval(question, top_k)` 是完整管线，分 7 步：

**① 规范化与改写**
- `_normalize_question`：规整 "section X" 大小写 + 追加同义词（"红旗"→"red flag"）；
- `QueryRewriter.rewrite`：仅含 CJK 时调 LLM 改写（token 180、超时 4s、失败返回原问题）；`_deduplicate_queries` 去重。

**② 短语与关键词提取**
- `_extract_phrases`：12 个硬编码短语（parc ferme / unsafe release / red flag...），短语命中加分权重高；
- `_expand_keywords`：分词 + 近义词典扩展 + 去停用词（20 个）。

**③ 段落/条款定位**
- `_match_preferred_sections`：正则 "section a-f" + 条款前缀 + `SECTION_KEYWORDS`（每节的领域词表）；
- `_extract_exact_clause_ids`：正则 `\b[A-F]\d+(\.\d+)+\b`——**用户直接问 B5.6.4 时，精确条款号优先**。

**④ 双路召回**
- **向量路** `_search_by_vector_queries`：`embed_query` 生成查询向量 → pgvector cosine_distance → `limit(pool_size)`（`max(top_k*8, 80)`）→ 相似度 `max(1.0-distance, 0.0)`；每路取 `max(top_k, 40)` 再合并去重；
- **关键词路** `_search_by_keywords`：倒排索引候选 + 精确条款 +30 → **BM25**（k1=1.5、b=0.75、avgdl=180、IDF 来自语料统计）+ 启发式 `_score_chunk`（短语 +10、关键词 +1、article 命中 +3、overview 类型 -4、preferred section +8）。

**⑤ RRF 融合**
`_fuse_candidates`：`score = (vector_rrf + keyword_rrf) * 100 + min(keyword_score, 20)`，K=60——两路排名取倒数融合，弱化单一检索器的偏差。

**⑥ 两轮重排 + 护栏**
- `_rerank_chunks`（启发式）：exact clause +30、hybrid 分截断 25、`evidence_strength` 判定（final ≥8 且短语命中 >0 或 keyword ≥6 → 强证据）；
- `_apply_keyword_guardrail`：**若关键词路第一名 ≥20 分，整体替换为关键词结果**（标 `keyword_guardrail: 1.0`）——防止向量相似但语义无关的噪声；
- `_apply_model_rerank`：交叉编码器 bge-reranker-v2-m3 对候选打分（覆盖 score，保留 `rerank_heuristic`/`rerank_model` 组件）；模型不可用时原样返回。

**⑦ 精确条款强化 + 相邻扩展**
- `_boost_exact_vector_results`：命中精确条款的 chunk 分数强制 `max(score, 100)`，标 `exact_clause: 1.0`；
- `expand_clause_context(hits, max_neighbors=1)`：同 document_key+clause_id 且 `|part_ordinal 差|=1` 的相邻 part 追加进结果（不改排名）——保证引用上下文完整。

**RAG 指标**：`RAG_RETRIEVALS.labels(query_type, outcome)` + `RAG_DURATION`。

**面试讲法**："检索是双路召回：向量抓语义、BM25 抓术语，RRF 融合后过两道闸——关键词护栏（防止向量'看着像但不对'）和重排（先启发式后交叉编码器）。用户明确给条款号（B5.6.4）时精确匹配直接 +100 分压制一切。证据强度不够就返回 insufficient_evidence，宁可拒答不编造。"

## 24. 消融实验与质量数字

**为什么做消融**：证明"混合检索的每一步都有用"，而不是玄学调参。README 质量基线：

| 检索器 | Clause Recall@5 | MRR | 说明 |
| --- | --- | --- | --- |
| 纯向量（基线） | 66.7% | 0.504 | 只靠 embedding 相似度 |
| 纯向量 + Section 感知 + 重排 | 73.7% | 0.574 | clause-aware chunking + bge-reranker |
| Keyword-only | 100% | 79.65% | 术语匹配在条文场景极强 |
| **Adaptive hybrid** | **100%** | ~78% | 关键词护栏兜底 + 向量补语义 |

- 无答案问题强证据拒绝率 **100%**；
- **为什么纯向量到不了 100%**（文档里如实记录）：抽象问法 vs 具体条文时，正确条款的余弦排位常落 22-67 名——"红旗"的语义向量离具体条文远。所以混合检索 + 护栏是必须的，这也说明"别迷信 embedding"。
- 评测数据 `data/evals/rag_cases.jsonl`：**60 条**，覆盖精确条款、跨页、表格、同义改写、跨 Section 干扰、无答案问题六类。

**QA 质量**：
- offline（无 LLM）：状态准确率 100%、引用一致性 100%（基于 qa_grounding 的确定性校验）；
- online（LLM-as-judge）：忠实度均值 ~4.8/5、拒绝/回答决策正确率 ~90%。

---

# 第六部分 · 记忆与多轮对话

> 聊天机器人最容易翻车的三个点：上下文爆掉、跨轮忘事、追问跑偏。这个项目用三层机制解决：会话历史（持久化）、上下文压缩（防爆）、长期记忆（跨会话）。

## 25. 会话历史（SessionService + Redis）

### 25.1 存储后端（SessionStoreFactory）

`settings.session_backend` 二选一（**没有 postgres 后端**）：
- `memory`（默认）：`InMemorySessionStore`，进程内 dict。重启即丢，适合开发；
- `redis`：`RedisSessionStore`，`Redis.from_url(resolved_redis_url)`，**创建时 ping 校验，失败抛 ConnectionError**（快速失败而不是静默降级）。生产/演示用 `.env` 配 `SESSION_BACKEND=redis`。

### 25.2 键与 TTL

- 会话数据键带 `session_id`，TTL = `session_ttl_seconds`（默认 86400 = 1 天；.env.example 示例 604800 = 7 天）；
- 历史最多 `session_history_max_turns`（20 轮），超过触发压缩（见下节）。

### 25.3 会话生命周期（get_or_create_session）

`session_id` 由前端传入或服务端新建（uuid4 hex）。会话摘要（title/turn_count/last_intent/updated_at）每次交互后更新；`last_intent` 就是下一轮追问的 fallback 意图来源。

## 26. 上下文压缩与长期记忆（MemoryService）

### 26.1 三层上下文拼装（memory_service.build_context）

每次问答前，把三类内容拼成 `conversation_context` 传给 Agent：
1. **会话摘要**（compacted summary）：旧轮次被压缩后的摘要（token 预算 `memory_summary_token_budget=260`）；
2. **长期记忆**：跨会话提取的用户偏好（如"喜欢迈凯伦"），语义召回 top 3 条；
3. **最近 N 轮**（`memory_recent_turns=4`）原文。
整体受 `memory_context_token_budget`（1200）预算约束，超出按优先级裁剪（最近优先）。

### 26.2 压缩触发与执行（ContextCompactionService）

- 触发条件：历史轮数 > 20 或累计 token > `memory_compaction_token_threshold`（1600）；
- 执行：LLM 把旧对话压成**结构化 JSON 摘要**（保持关键事实/用户偏好/未完成事项）；
- **确定性回退**：LLM 失败时截断保留最近轮次——压缩永不失败、永不阻塞。

### 26.3 长期记忆（memory_long_term_*）

- 开关 `memory_long_term_enabled`（默认 true）、后端 `memory_long_term_backend`（postgres/memory/redis）、TTL 30 天；
- `record_interaction(user_message, assistant_message)`：从对话中提取**偏好标记**（规则匹配 + 别名表），写入长期存储（默认 PostgreSQL 按 user_id + memory_key 持久化；preference/history 增量追加、constraint/fact 覆盖更新）；
- 召回：`memory_vector_retrieval_enabled` 开启时支持向量相似度语义召回（复用 embedding 服务）。

### 26.4 记忆的 trace

每次问答后，`_with_memory_trace` 把记忆的 trace（命中的长期记忆、压缩统计）注入 response.trace——前端证据面板下方能看到记忆来源，**可观测的记忆**是加分设计。

---

# 第七部分 · 评测与质量体系

> 面试官最关心"你怎么证明它好用"。答案是四层评测，每一层都有数字。这是项目区别于 demo 的核心证据。

## 27. 四层评测体系总览

| 层 | 工具 | 内容 | 关键数字 |
| --- | --- | --- | --- |
| 1. 单元/集成测试 | pytest | 全部后端逻辑（327+ 用例） | coverage ≥80%（CI 门禁） |
| 2. Agent golden eval | scripts/run_agent_eval.py | 66 条用例，六项指标 | 全部 100% |
| 3. RAG 检索 eval | scripts/run_rag_eval.py | 60 条，keyword/vector/hybrid 三模式 | hybrid 100%、MRR ~78% |
| 4. QA eval | scripts/run_qa_eval.py | 21 条，offline 确定性 + online LLM judge | offline 100%；online 忠实度 ~4.8/5 |

**设计原则**：**离线评测全部确定性**（无 LLM key 也能跑、结果可复现）——online 评测才用 LLM-as-judge，且不作为 CI 门禁（依赖模型）。

## 28. 每个评测脚本的指标与门禁

### 28.1 run_agent_eval.py（Agent golden）

- 用例：`data/evals/agent_cases.jsonl`，66 条（含 6 条多步依赖链）；
- 每条的断言字段：`expected_intent` / `expected_tool` / `expected_action` / `must_include[]` / `must_not_include[]` / `expected_answer_status` / **`expected_steps[]`（多步工具序列）** / `expected_plan_len`；
- 汇总六项指标：intent/tool/action/answer/evidence/**step_sequence** 准确率 + p50/p95 延迟；
- `--planner-mode structured|tool_calling`：统一 runtime 下的 planner 对比（tool_calling 需 LLM key）；
- 任一失败 returncode 1 → CI 门禁；
- harness 在 `tests/evals/test_agent_quality_eval.py`（HeuristicPlanner + EvalToolDispatcher，不依赖 LLM）。

### 28.2 run_rag_eval.py（检索）

- `--mode keyword|vector|hybrid`（默认 keyword，top_k=5）；
- 指标：recall@1/@5、section_recall@5、clause_recall@1/@5、MRR、clause_hit_rate、strong_evidence_rejection_rate；
- `--baseline-git-ref` 生成新旧对比报告（消融实验就是这么做的）；
- CI 门禁示例（hybrid）：section_recall@5 ≥0.98、clause_recall@5 ≥0.975、MRR ≥0.75、拒绝率 1.0。

### 28.3 run_qa_eval.py（回答质量）

- offline：注入 `DeterministicQueryRewriter`（不调 LLM）+ `FailingLLMClient`（强制确定性 fallback）→ 断言 answer_status 准确率、引用一致性、证据支撑比例（qa_grounding）；
- online：LLMJudge 评 groundedness/helpfulness/rejection_correct（1-5 分）；
- CI 门禁（offline）：状态准确率 ≥0.95、引用一致性 1.0。

### 28.4 其他

- `benchmark_api.py`：压测（live/ready/retrieval/stream 四模式，stream 统计 TTFT），可设 `--max-p95-ms` 门禁；
- 前端 vitest（2 个测试文件）+ Playwright E2E（桌面 + 移动双视口，mock API + 手工 SSE）。

## 29. 测试组织（tests/ 目录）

```
tests/
├── agents/        # Agent 核心单测：test_planner（15）、test_react_loop（18）、
│                  # test_runtime_graph、test_reflector、test_response_formatter（10+）、
│                  # test_tool_dispatcher、test_intent_router、test_function_calling、test_strategy_integration
├── api/           # 端点测试（chat 流式、rules、news、race、health）
├── services/      # chat_service、agent_service、memory、session、qa、news、race、logging...
├── repositories/  # news_repository、rule_repository
├── rag/           # 检索测试（chunker、parser、混合检索）
├── tools/         # 各工具测试
├── evals/         # 评测 harness：test_agent_quality_eval（66 条）、test_run_agent_eval、
│                  # test_rag_eval、test_qa_eval
├── mcp/           # MCP 工具暴露测试
└── infrastructure/# 需要真实 Postgres/Redis（RUN_INFRA_TESTS=1 才跑）
```

**pytest markers**（pyproject.toml）：`unit` / `integration` / `eval` / `infrastructure`。CI 里 `pytest -m "unit or integration"` 先跑带 coverage 门禁的，再单独跑 `-m eval`。

---

# 第八部分 · 前端

## 30. 页面与路由

Next.js 16 App Router。只有两个页面：

| 路由 | 文件 | 功能 |
| --- | --- | --- |
| `/` | frontend/app/page.tsx | 聊天工作台（核心页） |
| `/rag` | frontend/app/rag/page.tsx | RAG Lab 检索实验页 |
| `/_not-found` | Next 默认 | — |

根布局 `app/layout.tsx`：`<html lang="zh-CN">`、导入 globals.css、metadata（title "PitWall Agent"）。**没有任何 Provider**（无状态管理库，全靠 useState + props）。

### 30.1 聊天页的状态设计（page.tsx）

**useState**：`sessions`（会话列表）、`activeSessionId`、`history`（ConversationTurn[]）、`draft`（输入框）、`streamingAssistant: {text, sessionId?} | null`（流式中间态）、`completedResponse`、`errorMessage`、`statusMessage`（顶部指示灯文字）、`sidebarOpen`/`evidenceOpen`（移动端抽屉）、`lastMessage`（重试用）。

**useRef**：`abortRef`（AbortController，Stop 按钮用）、`messageEndRef`（滚动锚点）。

**useEffect**：
- 挂载时 `refreshSessions(true)`（只跑一次）；
- `[history, streamingAssistant]` 变化时滚动到底部——**流式自动滚动**的实现。

**sendMessage 的核心流程**（面试可讲）：
1. 创建 `AbortController` 存 ref；
2. 乐观追加用户消息到 history（立即显示）；
3. `setStreamingAssistant({text: ""})` + `setStatusMessage("Connecting")`；
4. 调 `streamChatMessage({message, session_id}, onEvent, signal)`；
5. 事件分发：`session_started` → 记录 sessionId；`status` → 更新状态灯（thinking/routing/retrieving/generating）；`message_delta` → 追加流式文本（打字机）；`message_completed` → **用后端返回的 history 整体替换本地**、清流式状态、刷新会话列表；`error` → 抛出；
6. catch：`AbortError` → "Generation stopped"（用户点 Stop）；其他 → errorMessage；
7. 重试按钮：出错且 `lastMessage` 存在时出现，重新发送。

### 30.2 RAG Lab（/rag）

检索调试页：corpus 状态（版本/chunk 数/覆盖率）→ 问题输入 + Top K 下拉（3-20）→ Retrieve → **4 个 stage tab**（final/keyword/vector/hybrid）切换查看各检索阶段的候选——直接把 `debug_retrieval` 的响应可视化。默认问题 "What does B5.6.4 require?"。

## 31. 组件详解

| 组件 | 文件 | 职责 |
| --- | --- | --- |
| MessageBubble | message-bubble.tsx | 消息气泡：角色徽章（You/PitWall）、intent/tool_name 元数据、**LIVE 标签**（流式中）、react-markdown + GFM 渲染、typing-indicator（首 token 前 "Working..."） |
| EvidencePanel | evidence-panel.tsx | 证据面板（服务端组件，无状态）：trace-summary 2×2（Status/Evidence/Latency/Stream）、Metadata chips、**AgentSteps**（plan 序列 + steps 执行序列 + judge 决策）、Citations（截断 260 字符）、Retrieved chunks（前 5 条） |
| SessionList | session-list.tsx | 会话侧栏：新建按钮、标题/turn_count/last_intent/时间、删除按钮（hover 变红） |
| WorkspaceNav | workspace-nav.tsx | 顶部导航：PW 红块品牌、Chat / RAG Lab 激活态（usePathname） |

## 32. API 封装与 SSE 流式处理（frontend/services/api.ts）

**API_BASE_URL**：`process.env.NEXT_PUBLIC_API_BASE_URL`（构建期注入，默认 `http://127.0.0.1:8000`），尾斜杠剥除。

| 函数 | 端点 | 说明 |
| --- | --- | --- |
| `listSessions()` | GET /api/chat/sessions?limit=50 | `cache: "no-store"` |
| `getChatHistory(id)` | GET /api/chat/{id}/history | |
| `deleteSession(id)` | DELETE /api/chat/{id} | |
| `sendChatMessage(payload)` | POST /api/chat | **未在页面使用**（备用） |
| `streamChatMessage(payload, onEvent, signal?)` | POST /api/chat/stream | SSE 流式（见下） |
| `getActiveCorpus()` | GET /api/rules/corpus/active | RAG 页 |
| `debugRuleRetrieval(question, topK)` | POST /api/rules/retrieve/debug | RAG 页 |
| `parseSseEvent(rawEvent)` | — | 解析单个 SSE 块（有单测） |

**SSE 解析细节**（面试可讲）：`fetch` → `response.body.getReader()` → `TextDecoder.decode({stream: true})`（**避免多字节字符截断**）→ `buffer.split("\n\n")`（SSE 事件空行分隔）→ 残块留待下轮 → `parseSseEvent` 找 `event:` 行 + 所有 `data:` 行（多行 data 用 `\n` 连接）→ `JSON.parse`。

## 33. 样式方案与响应式

- **纯手写 CSS**（globals.css，212 行）：`--accent: #d7182a`（赛车红）、`--bg #f4f5f7`、`--text #17191c` 等 CSS 变量；Tailwind 装了但没用（无 tailwind.config、无 `@import "tailwindcss"`）；
- 布局：`app-frame`（100dvh）→ `workspace-nav`（58px 黑底红边）→ `chat-shell`（grid 278px + 1fr）→ `chat-grid`（1fr + 360px 证据列）；
- 用户气泡深色右对齐（#292d33）、助手气泡浅灰；
- **响应式断点**：1080px 证据列收窄 310px；820px 起移动端——侧栏变 fixed 抽屉（translateX 滑入，180ms transition）、证据面板变底部抽屉、mobile-only 按钮；430px 单列化；
- 聊天内容区 `max(24px, calc((100% - 820px)/2))` 居中——宽屏下正文不拉太宽，保持可读性。

---

# 第九部分 · 部署、CI 与运维

## 34. Docker Compose 拓扑

| 服务 | 镜像 | 端口 | 关键点 |
| --- | --- | --- | --- |
| postgres | pgvector/pgvector:pg17 | 5432 | 命名卷 postgres_data；healthcheck pg_isready；restart unless-stopped |
| redis | redis:7-alpine | 6379 | 命名卷 redis_data；healthcheck redis-cli ping |
| backend | 根 Dockerfile 构建 | 8000 | env 覆盖（DATABASE_URL 指向 postgres 服务名、SESSION_BACKEND=redis、HF 模型缓存 /models）；卷挂载 `./.hf-models:/models`；depends_on 用 `condition: service_healthy` |
| frontend | frontend/Dockerfile 构建 | 3000 | build arg NEXT_PUBLIC_API_BASE_URL |
| prometheus | prom/prometheus:v3.5.0 | 9090 | **profile: observability**（默认不起） |
| grafana | grafana/grafana:12.1.0 | 3001 | 匿名 Viewer 登录；provisioning + dashboards 只读挂载 |

**启动命令**：`docker compose up -d`（基础四件套）；`docker compose --profile observability up -d`（加监控）。
**Windows 注意**：`.tmp/docker-compose.pg5433.yml` 是 override 片段（`!override []` 去掉 5432 端口映射）——用于 5432 被 Windows Hyper-V 保留段占用时。

## 35. Dockerfile 多阶段构建

**后端**（根 Dockerfile，python:3.12-slim）：
- uv 二进制从 `ghcr.io/astral-sh/uv:0.8.15` COPY 过来；
- `uv sync --frozen --no-dev --no-install-project`（锁文件安装）；
- 拷贝 `alembic.ini` + `migrations/` + `app/` + `scripts/` + `data/regulations/processed/`（**只拷 processed，不拷 raw PDF**——镜像小且源资产不入库）；
- 启动：`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`。

**前端**（frontend/Dockerfile，node:22-alpine 三阶段）：`npm ci` → `npm run build`（standalone 产物）→ runtime 只拷 `.next/standalone` + `.next/static`，`node server.js`。

## 36. CI 流水线（.github/workflows/ci.yml，7 个 job）

触发：push（main/master）+ 所有 PR + workflow_dispatch。

| job | 内容 | 备注 |
| --- | --- | --- |
| backend-quality | uv sync + ruff + pyright | 快速门禁 |
| backend-tests | pytest unit/integration（coverage ≥80%）→ pytest eval → run_agent_eval → run_rag_eval（keyword 门禁）→ run_qa_eval（offline 门禁） | 全套离线评测 |
| compose-config | `docker compose config --quiet` | 配置合法性 |
| backend-infrastructure | 起真 pgvector+redis，alembic upgrade + pytest -m infrastructure | 需要 RUN_INFRA_TESTS=1 |
| hybrid-eval | 重建语料 + vector/hybrid 检索评测 | **仅 workflow_dispatch**（要 CPU 嵌入） |
| qa-eval | online LLM judge | **仅 workflow_dispatch**（要 LLM key，secrets） |
| frontend | npm ci → lint（--max-warnings=0）→ tsc --noEmit → vitest → Playwright E2E（双视口） | |

**亮点**：离线评测全部进 CI 且带阈值门禁；烧钱的（hybrid 嵌入、LLM judge）留手动触发——CI 设计有成本意识。

## 37. 监控：Prometheus 指标与 Grafana

**指标暴露**：`/metrics`（Prometheus 文本格式）。16 个指标（附录 F 全表）：HTTP、工具、LLM、RAG、流式、语料 Gauge、上游请求，全部带 labels（route/status/tool/action/model/outcome/query_type/provider/mode...）。

**Grafana 看板**（ops/grafana/dashboards/pitwall-overview.json，8 面板）：
1. Active corpus chunks / embeddings（Gauge）
2. HTTP error rate（`sum(rate(...{status=~"5.."}[5m]))/...`）
3. Stream P95 TTFT（histogram_quantile）
4. HTTP requests 时序（按 route/status）
5. Stream outcomes（按 outcome/mode）
6. RAG P95 latency（按 query_type）
7. LLM P95 latency（按 model）

refresh 5s，uid `pitwall-overview`，Prometheus scrape_interval 5s。

## 38. 结构化日志与 MCP

- **日志**：`log_structured` 单行 JSON（timestamp UTC/level/event/request_id/字段）。event 命名风格 `领域_动作_结果`（如 `agent_query_completed`、`llm_tools_request_completed`）。排查一次请求 = 按 request_id grep。
- **MCP**：`/mcp` 挂载 streamable HTTP transport，把工具层暴露给 MCP 客户端（Claude Desktop 等）。`app/core/mcp_server.py` 用官方 mcp SDK 实现（RFC-007 有文档）。与 REST 并存，同一工具层。

---

# 第十部分 · 面试速查

## 39. 高频追问与回答要点（一句话版）

| 面试官问 | 你的回答要点 |
| --- | --- |
| 介绍你的项目 | 30 秒版：F1 场景 AI 问答助手，四件事——聊天（多轮记忆）、规则 RAG（条款级引用）、实时数据工具（新闻/赛况）、自主 Agent（多步规划 + ReAct 反思），配四层评测与完整工程闭环 |
| 你的 Agent 和带工具的聊天机器人有什么区别？ | 三层：任务分解（2-4 步依赖链 + $ref 数据传递）、观察-再推理（judge 在失败/证据不足/结果不完整时重规划）、可评测（66 条 golden 断言工具序列，step_sequence 100%） |
| 为什么不用原生 function calling？ | 两种 planner 都在 LangGraph 内实现（RFC-008）：structured 保确定性/离线可测，tool_calling 保灵活性/可并行；共享工具、Judge、预算与 trace，模型异常图内回退 |
| RAG 检索为什么用混合而不是纯向量？ | 消融数据：纯向量 66.7%→73.7%（加 clause-aware + 重排）仍达不到 100%，关键词 BM25 在条文术语场景 100%；RRF 融合 + 关键词护栏兜底；抽象问法 vs 具体条文时向量排位会掉到 22-67 名 |
| 检索结果不可信怎么办？ | 证据判定：强证据（≥8 分）→ answered；弱证据 → partial_evidence（明说信息有限）；无证据 → insufficient_evidence 拒绝回答。引用一致性离线评测 100% |
| 上下文太长怎么办？ | 三层：最近 4 轮原文 + LLM 摘要压缩（1600 token 阈值触发，失败确定性回退）+ 长期记忆语义召回；总预算 1200 token 裁剪 |
| 流式怎么实现的？ | 后端：工作线程跑 LLM + queue.Queue 中转 + SSE 帧（event/data 双换行）；零 token 时 24 字符分块模拟打字机；前端：ReadableStream + TextDecoder（防多字节截断）+ 按 \n\n 分帧 |
| 多步计划会不会死循环/失控？ | max_steps 可配（默认 5）；计划内步骤不消耗修复预算；judge 白名单校验；无 LLM key 走确定性路径 |
| 怎么证明工程质量？ | 327+ 测试 coverage≥80%、66 条 Agent eval 六指标 100%、60 条 RAG eval、21 条 QA eval、CI 七 job 全门禁、16 个监控指标 + Grafana、压测脚本 |
| 数据库表设计？ | 三张表：regulation_chunks（含 Vector(1024)）、regulation_corpora（版本管理，一次一个 active）、news_articles（唯一约束去重）；Alembic 两个迁移 |

## 40. 常见深挖问题的标准答案（详细版）

**Q：多步计划的步骤间数据是怎么传递的？**
A：Planner 输出的每一步有 `output_key`，执行器按序执行并把结果存进 `step_outputs[output_key]`。后一步的 params 可以写 `$ref:<output_key>.<字段路径>`，执行前 `interpolate_params` 做解析——支持 dict 路径和列表索引（如 `$ref:news_hit.articles.0.title`）。这样 LLM 不用把中间结果完整塞进上下文，传递是结构化的、可追踪的。

**Q：judge 为什么不在每一步都触发？触发条件是什么？**
A：judge 触发条件是"有理由怀疑当前结果不够"：① 工具失败；② regulation 证据不足（answer_status=insufficient_evidence 或 fallback 无答案）；③ news/race 结果不完整（空文章/无数据字段）；④ general 成功且配置开启。多步计划执行到成功步骤时直接 continue，不进 judge——计划内的步骤不需要反思，只有异常情况才反思，省 token 且行为可预测。

**Q：LangGraph 相比手写循环好在哪？**
A：① 节点是纯函数，state 显式，每个节点可独立单测；② 图结构让"路由"可视化（judge → plan_tool 循环一眼可见）；③ 为将来加子图/多 Agent 留了结构（Send API、subgraph）；④ 有官方 checkpoint 机制（当前未启用，但接口在）。

**Q：为什么 RuleRepository 要回退读 JSON 文件？**
A：向量检索依赖数据库里有 active corpus 和 embedding。新环境没跑摄取脚本时，回退读 `chunks.json`（6198 条，含全部字段）让规则问答仍能工作（只是没有向量路，走关键词路）。进程内 6 个缓存结构避免重复 IO。这是"渐进式能力降级"：没有向量 → 关键词也能答；没有数据库 → 文件也能答。

**Q：新闻搜索怎么处理中文？**
A：双保险——① 数据侧：RSS 摄取时标题/摘要原样入库；② 查询侧：`NewsService.search_articles` 先做别名展开（`_expand_query_aliases`），把"维斯塔潘"展开为 "Max Verstappen"（20 组车手/17 组车队/15 组赛道别名表），再入库 ILIKE 搜索。洞察服务的实体提取也用同一张别名表。

**Q：赛况数据源挂了怎么办？**
A：四级降级：进程内缓存（TTL 300s）→ Jolpica API（带重试：429/5xx 指数退避）→ Redis last-good 缓存（86400s，上游挂了用上次成功数据）→ 静态种子数据（JSON 快照）。设计原则：**用最近的真实数据降级，绝不伪造样例**。

**Q：评测为什么分 offline/online？**
A：offline 用确定性组件（FailingLLMClient、DeterministicQueryRewriter）跑完整个管线，结果可复现、零成本、进 CI 门禁；online 用 LLM-as-judge 评主观质量（忠实度/有用性），依赖模型、成本高，只手动触发。两级互补：offline 保底不回归，online 看真实体验。

**Q：如果用户问"下一站什么时候"，Agent 怎么走？**
A：意图路由命中 race → planner 构建 get_next_race 单步计划 → race_tool → RaceService 四级降级取数据 → formatter 的 `_build_race_answer` 按消息提取关注对象输出。如果上游全挂且无缓存，工具返回失败 → judge 触发 → reflector 无 LLM 时直接结束并返回"实时数据暂不可用"的确定性文案。

**Q：为什么 formatter 不用 LLM 生成？**
A：回答格式是产品契约（引用、置信度、结构），LLM 自由发挥会破坏一致性且不可测。formatter 是纯模板逻辑，从工具的结构化结果生成回答，10+ 单测覆盖每个 intent——这也是"回答质量可评测"的前提。

## 附录

## 附录 A：配置项全表（.env.example 逐项解释）

### LLM
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| LLM_API_KEY | 空 | 兼容 DEEPSEEK_API_KEY |
| LLM_BASE_URL | https://api.deepseek.com | OpenAI 兼容端点 |
| LLM_MODEL | deepseek-v4-flash | 主模型 |
| LLM_TIMEOUT_SECONDS | 20 | 超时 |
| LLM_MAX_RETRIES | 1 | 重试次数 |
| LLM_MAX_TOKENS | 700 | 回答 token 上限 |

### Planner（Agent 规划）
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| LLM_PLANNER_ENABLED | true | 规划器开关 |
| LLM_PLANNER_MAX_TOKENS | 160 | 单步规划预算 |
| LLM_PLANNER_MULTI_MAX_TOKENS | 320 | 多步分解预算（复合信号触发） |
| LLM_PLANNER_TIMEOUT_SECONDS | 4 | 规划超时 |

### Agent
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| AGENT_REACT_MAX_STEPS | 5 | ReAct 修复循环轮次（计划内步骤不受限） |
| AGENT_PLANNER_MODE | tool_calling | tool_calling（原生工具规划）\| structured（结构化确定性规划） |
| AGENT_JUDGE_ENABLED | true | 裁判开关 |
| AGENT_JUDGE_ON_SUCCESS_GENERAL | true | general 成功也判 |
| AGENT_JUDGE_MAX_TOKENS | 160 | 裁判 token |
| AGENT_JUDGE_TIMEOUT_SECONDS | 4 | 裁判超时 |

### RAG
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| QUERY_REWRITE_MAX_TOKENS / TIMEOUT | 180 / 4 | 查询改写（仅中文触发 LLM） |
| REGULATION_PREFER_DATABASE | true | 优先读库内 chunks |
| REGULATION_VECTOR_RETRIEVAL_ENABLED | false（settings 默认 true） | 向量检索开关——**注意 .env.example 与 settings 默认值不同**，演示默认关向量（省模型），CI hybrid job 显式开 |
| REGULATION_RERANK_ENABLED / MODEL / MAX_CANDIDATES / BATCH_SIZE | true / bge-reranker-v2-m3 / 15 / 8 | 重排 |
| REGULATION_EMBEDDING_QUERY_INSTRUCTION | 空 | 查询指令前缀 |

### 上游与缓存
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| RACE_REQUEST_TIMEOUT_SECONDS | 3 | Jolpica 超时 |
| RACE_CACHE_TTL_SECONDS | 300 | 进程内赛况缓存 |
| UPSTREAM_GET_MAX_RETRIES / BACKOFF | 2 / 0.2 | 上游重试 |
| DATA_CACHE_ENABLED / TTL | true / 86400 | Redis last-good |

### 新闻
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| FORMULA1_FEED_URL / MOTORSPORT_FEED_URL | 官方 RSS 地址 | 双源 |
| NEWS_INGEST_ON_STARTUP / LIMIT | true / 15 | 启动后台抓取 |
| NEWS_REQUEST_TIMEOUT_SECONDS | 10 | RSS 超时 |

### 会话与记忆
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| SESSION_BACKEND | memory（settings）/ redis（示例） | 会话后端 |
| REDIS_URL | redis://localhost:6379/0 | |
| SESSION_TTL_SECONDS | 86400（示例 604800=7 天） | 会话 TTL |
| SESSION_HISTORY_MAX_TURNS | 20 | 压缩触发轮数 |
| MEMORY_RECENT_TURNS | 4 | 上下文保留最近轮 |
| MEMORY_CONTEXT_TOKEN_BUDGET | 1200 | 渲染上下文预算 |
| MEMORY_SUMMARY_TOKEN_BUDGET | 260 | 摘要预算 |
| MEMORY_COMPACTION_TOKEN_THRESHOLD | 1600 | 压缩触发阈值 |
| MEMORY_COMPRESSION_ENABLED | true | LLM 压缩开关 |
| MEMORY_LONG_TERM_ENABLED / BACKEND / TTL / TOP_K | true / memory / 2592000 / 3 | 长期记忆 |
| MEMORY_VECTOR_RETRIEVAL_ENABLED | true | 记忆语义召回 |

### Postgres / 嵌入
| 变量 | 默认 | 说明 |
| --- | --- | --- |
| POSTGRES_HOST/PORT/DB/USER/PASSWORD | localhost/5432/pitwall/pitwall/pitwall | |
| DATABASE_URL | 空 | 直接覆盖连接串 |
| REGULATION_EMBEDDING_MODEL / DIM / BATCH / DEVICE | bge-m3 / 1024 / 8 / cpu | 嵌入 |
| HF_TOKEN | 空 | HuggingFace 下载模型 |

## 附录 B：API 端点全表（29 + MCP）

见第 9 节完整表格。速记：`/health(/live|/ready)`、`/metrics`、`/api/chat(+/stream|/sessions|/{id}(+/history))`、`/api/agent/query`、`/api/news(+/search|/refresh|/{id}(+/insights|/rules-analysis))`、`/api/race(schedule|next|previous|standings/drivers|standings/constructors)`、`/api/rules(ask|retrieve/debug|corpus/active)`、`/api/strategy/analyze`、`/mcp/*`。

## 附录 C：数据库表全表

见第 13 节。速记：三张表——`regulation_chunks`（检索对象，含 Vector(1024)）、`regulation_corpora`（版本管理，active 唯一）、`news_articles`（新闻，唯一约束防重）。

## 附录 D：工具 action 全表（5 工具 14 动作）

| 工具 | 动作 | 参数 | 说明 |
| --- | --- | --- | --- |
| news_tool | list_recent | limit | 最新新闻 |
| news_tool | search | query, limit | 搜索新闻 |
| news_tool | get_article | article_id | 单篇详情 |
| news_tool | get_insights | article_id | LLM 洞察 |
| news_tool | get_rules_analysis | article_id | 规则联动 |
| race_tool | list_schedule | — | 赛历 |
| race_tool | get_next_race / get_previous_race | — | 上/下一场 |
| race_tool | get_race_results | — | 比赛结果 |
| race_tool | get_driver_standings / get_constructor_standings | — | 积分榜 |
| regulation_tool | ask | question | 规则 RAG 问答 |
| strategy_tool | analyze | question | 策略分析 |
| general_tool | answer | question | 通用问答 |

## 附录 E：评测案例规模与字段

| 文件 | 条数 | 字段 | 覆盖 |
| --- | --- | --- | --- |
| agent_cases.jsonl | 66 | name/messages/expected_intent/expected_tool/expected_action/must_include/must_not_include/expected_answer_status/expected_steps/expected_plan_len | 5 意图 + 6 条多步链（中英） |
| rag_cases.jsonl | 60 | name/question/expected_sections/expected_articles/language | 精确条款/跨页/表格/同义改写/跨 Section 干扰/无答案 |
| qa_cases.jsonl | 21 | name/question/expected_answer_status/language | 状态判定 + 引用 |

## 附录 F：Prometheus 指标全表（16 个）

| 指标 | 类型 | labels |
| --- | --- | --- |
| pitwall_http_requests_total | Counter | method, route, status |
| pitwall_http_request_duration_seconds | Histogram | method, route |
| pitwall_tool_calls_total | Counter | tool, action, outcome |
| pitwall_tool_duration_seconds | Histogram | tool, action |
| pitwall_llm_calls_total | Counter | model, outcome |
| pitwall_llm_duration_seconds | Histogram | model |
| pitwall_rag_retrievals_total | Counter | query_type, outcome |
| pitwall_rag_retrieval_duration_seconds | Histogram | query_type |
| pitwall_stream_requests_total | Counter | outcome, mode |
| pitwall_stream_time_to_first_token_seconds | Histogram | — |
| pitwall_stream_duration_seconds | Histogram | mode |
| pitwall_active_corpus_chunks | Gauge | — |
| pitwall_active_corpus_embeddings | Gauge | — |
| pitwall_upstream_requests_total | Counter | provider, outcome |
| pitwall_upstream_retries_total | Counter | provider |
| pitwall_upstream_request_duration_seconds | Histogram | provider |

---

> **文档结束语**：这份文档把项目从外到内讲了一遍。面试前建议做三件事：① 通读第二、四、五部分（链路、Agent、RAG）；② 打开源码对照第十部分把每个问答用自己的话讲一遍；③ 亲手跑一次 `uv run pytest`、`uv run python scripts/run_agent_eval.py`、`docker compose up -d`，让数字变成自己的经验。祝你秋招顺利。




