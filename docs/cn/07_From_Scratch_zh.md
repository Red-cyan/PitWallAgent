# 从零学透 PitWall Agent（完整学习指南）

> 本指南假设你对这个项目**一无所知**，带你从"它到底在干嘛"开始，一层一层读懂全部代码。建议边读边打开对应文件对照，读一节、验证一节。

---

## 0. 这份文档怎么用

- 全篇按**教学顺序**组织：概念 → 架构 → 请求旅程 → 代码地图 → 逐个机制 → 算法 → 数据 → 动手。
- 每个重要知识点都标注了**对应文件路径**，请打开文件对照着读。
- 每章末尾有「自检」，答不上来就回看上一章。
- 全程约 3-5 小时可以通读一遍；之后按「第 10 章：常见修改任务」动手改几个小功能巩固。

---

## 1. 这个项目到底做什么？（大白话版）

**一句话**：一个能回答 Formula 1（F1 赛车）问题的 AI 助手。

你问它"上一场比赛谁赢了""维修区超速是什么规则""现在车队积分榜第几名"，它给出**带出处**的回答——每句话都能追溯到检索到的官方规则条款或实时数据。

**它和普通聊天机器人最大的区别**：它不会凭空编造，而是**先检索、再回答、附证据**（RAG），并且能调用**外部工具**（查赛历、积分榜、新闻）而不是只靠模型记忆。

**这个项目包含四样东西**：

| 组件 | 作用 | 类比 |
| --- | --- | --- |
| FastAPI 后端 | 提供 HTTP 接口，接收问题、返回回答（含流式） | 饭店后厨的传菜口 |
| LangGraph Agent | 决定"这个问题该用哪个工具、要不要重试" | 后厨调度主管 |
| RAG 检索 | 从 FIA 官方规则 PDF 里找相关条款当证据 | 厨师查菜谱 |
| Next.js 前端 | 聊天界面 + 调试/证据面板 | 餐厅大堂 |

项目里还有一套**评测系统**，用几百条预先标注好的问题自动打分，保证改代码不会把效果改坏——这是很多 AI 项目没有的。

---

## 2. 你需要的最小前置知识

下面每个概念先用一句人话解释，后面用到时会再展开。**现在看不懂没关系**，先有个印象。

| 概念 | 一句话解释 |
| --- | --- |
| LLM（大语言模型） | 像 DeepSeek 这样的模型，输入一段文字，输出一段文字。项目通过 OpenAI 兼容接口调用。 |
| Prompt | 发给 LLM 的指令文本（"你是 F1 规则助手，只依据片段回答……"）。 |
| Token | LLM 处理文本的最小单位（大概一个词或半个汉字）。 |
| RAG | 检索增强生成：先把文档切块存起来，回答前先搜索相关内容，把内容塞给 LLM，让它"看着资料回答"。防幻觉的核心手段。 |
| Agent / 工具调用 | 让 LLM 不只是"说话"，还能"做事"：系统准备了一批工具（查赛程、查积分榜…），Agent 决定调哪个。 |
| ReAct | "思考-行动-观察"循环：想一下该干嘛 → 调工具 → 看结果 → 决定是否继续。 |
| HTTP / API | 前后端通信的方式：前端发一个 HTTP 请求，后端返回数据。 |
| SSE 流式 | 后端把回答"一个字一个字"地推给前端，用户能实时看到打字效果。 |
| FastAPI | Python 的 Web 框架，用来写 HTTP 接口。 |
| LangGraph | 用"图"的方式编排 Agent 流程的框架（节点 + 连线 + 条件分支）。 |
| Next.js | 前端 React 框架，渲染聊天页面。 |
| PostgreSQL | 关系数据库，存规则块、新闻。带 pgvector 扩展还能存向量。 |
| Redis | 内存数据库，存会话、长时记忆、缓存。 |
| pgvector | Postgres 的向量检索扩展，用来做"找相似文本"。 |
| Pydantic | Python 的"数据结构定义 + 校验"库，项目里所有请求/响应都用它定义。 |
| Alembic | 数据库表结构版本管理（迁移）。 |
| Docker Compose | 一条命令把后端/数据库/前端全部跑起来。 |

---

## 3. 全局架构图

```text
浏览器（Next.js Chat / RAG Lab）       任意 MCP 客户端（Claude 等）
        │   HTTP + SSE                        │   MCP 协议
        ▼                                     ▼
┌───────────────────────────────────────────────────────────┐
│                    FastAPI 后端 (app.main)                 │
│  /api/chat  /api/rules  /api/race  /api/news ...  /mcp     │
│  中间件：AccessLog · RequestContext · CORS                 │
├───────────────────────────────────────────────────────────┤
│  ChatService（会话 + 流式）                                │
│    └─ AgentService                                        │
│         └─ LangGraphAgentRuntime（ReAct 循环图）           │
│              ├─ IntentRouter（判断意图）                   │
│              ├─ Planner（选工具+动作）                     │
│              ├─ ToolDispatcher（执行工具）                 │
│              │    ├─ RegulationTool ─ RAG 问答             │
│              │    ├─ RaceTool ────── 实时赛况              │
│              │    ├─ NewsTool ────── 新闻                  │
│              │    ├─ StrategyTool ── 策略                  │
│              │    └─ GeneralTool ── 通用 LLM 回答          │
│              └─ Reflector（失败时决定重试/换工具）          │
├───────────────────────────────────────────────────────────┤
│  领域服务：QAService · RaceService · NewsService · ...     │
│  RAG：RuleRepository（BM25 + 向量 + RRF + 重排）           │
│  MCP：PitWallServer（复用上面的服务）                      │
├───────────────────────────────────────────────────────────┤
│  数据：PostgreSQL(pgvector) · Redis · 本地法规语料 · 外部API│
│  观测：Prometheus metrics · JSON 日志 · Grafana            │
└───────────────────────────────────────────────────────────┘
```

**关键思想**：所有 HTTP 请求最终都汇入同一条 Agent 管线；MCP 是同一管线对外部客户端的"平行出口"；领域服务（RAG、赛况、新闻）被 Agent 和 MCP **共用**，保证行为一致。

---

## 4. 一次对话的完整旅程（从浏览器到答案）

以你在网页输入 `上一场比赛谁赢了` 为例，逐步看代码：

### 第 0 步：前端发起请求
- 前端 `frontend/app/page.tsx`（聊天页）→ 调用 `frontend/services/api.ts` 的 `streamChatMessage()` → 向后端 `POST http://127.0.0.1:8000/api/chat/stream` 发起 **SSE 流式请求**（带 `Content-Type: application/json`，body 是 `{message: "上一场比赛谁赢了"}`）。

### 第 1 步：后端入口
- `uvicorn` 把请求交给 `app/main.py` 里的 FastAPI 应用。
- 三个中间件依次处理：`RequestContextMiddleware`（分配 `request_id`）→ `AccessLogMiddleware`（记日志）→ `CORSMiddleware`（跨域）。
- 路由 `/api/chat/stream` 定义在 `app/api/chat.py` 的 `stream_chat()`。

### 第 2 步：ChatService 组装会话
- `stream_chat()` 调用 `app/services/chat_service.py` 的 `ChatService.stream_chat()`：
  1. 取/建会话（`session_service.get_or_create_session`）；
  2. 读取上一轮的意图作为 `fallback_intent`；
  3. 构建记忆上下文（`memory_service.build_context`）；
  4. 开一个**工作线程**跑 Agent，主线程边收 token 边通过 SSE 推给前端。

### 第 3 步：AgentService → LangGraph
- `app/services/agent_service.py` 的 `stream_query()` 调用 `LangGraphAgentRuntime.run()`（`app/agents/runtime_graph.py`）。
- 图开始执行：`classify_intent → plan_tool → execute_tool → judge_result → format_response`。

### 第 4 步：判断意图 + 选工具
- `IntentRouter.route()`（`app/agents/intent_router.py`）：用关键词/中文别名判断这是 `race`（赛况）意图。
- `Planner`（`app/agents/planner.py`）→ `ToolDispatcher.build_plan()`（`app/agents/tool_dispatcher.py`）：发现"谁赢/赢得"这类**结果信号**，决定 `race_tool / get_race_results`。

### 第 5 步：执行工具
- `ToolDispatcher.execute_plan()` 调用 `app/tools/race_tool.py` 的 `RaceTool.invoke(action="get_race_results")`。
- 工具再调用 `app/services/race_service.py` → `app/services/race_provider.py`（访问 Jolpica 实时 API，失败则走 last-good 缓存/本地种子），拿到比赛结果。

### 第 6 步：判断是否需要重试（ReAct）
- `Reflector`（`app/agents/reflector.py`）：工具成功且已回答 → 直接结束；工具失败 → 让 LLM 决定重试计划。

### 第 7 步：格式化回答
- `ResponseFormatter.build()`（`app/agents/response_formatter.py`）：把结构化结果转成中文句子，并**追加数据来源标签**（`数据源：Jolpica API`）。

### 第 8 步：流式返回 + 记录
- token 通过回调穿过工具→服务→LangGraph，由 ChatService 推给前端展示打字效果；同时写入 trace（意图、工具、动作、来源、耗时）供前端"证据面板"展示。

> **自检**：说出"上一场比赛谁赢了"从浏览器到回答经过了哪 6 个主要文件。

---

## 5. 代码地图：每个目录干什么

### 5.1 后端 `app/`（按职责）

| 目录/文件 | 作用 | 关键文件 |
| --- | --- | --- |
| `app/main.py` | 应用入口：装配中间件、挂路由、挂 `/mcp`、启动时后台摄入新闻 | 全局第一个读 |
| `app/api/` | **HTTP 层**：薄处理器，只负责"接请求→调服务→返响应"，不含业务逻辑 | `chat.py`（聊天/流式）、`rules.py`（规则问答）、`race.py`、`news.py`、`strategy.py`、`router.py`（聚合+健康检查+metrics） |
| `app/agents/` | **Agent 编排**：判断意图、选工具、执行、失败重试、格式化回答 | `runtime_graph.py`（核心图）、`intent_router.py`、`planner.py`、`tool_dispatcher.py`、`reflector.py`、`response_formatter.py` |
| `app/tools/` | **五个工具**，Agent 实际执行的"能力单元" | `race_tool.py`、`news_tool.py`、`regulation_tool.py`、`strategy_tool.py`、`general_tool.py`、`base.py`（统一返回结构 `ToolResult`） |
| `app/services/` | **领域业务**：所有真正干活的逻辑 | `chat_service.py`（会话+流式）、`agent_service.py`、`qa_service.py`（规则问答）、`race_service.py`+`race_provider.py`（赛况）、`news_*.py`（新闻）、`memory_service.py`（记忆）、`session_service.py`、`data_cache.py`（last-good 缓存）、`llm/client.py`（LLM 封装） |
| `app/repositories/` | **数据访问层**：SQL 查询、检索算法 | `rule_repository.py`（**RAG 检索核心，1187 行**）、`news_repository.py` |
| `app/rag/` | RAG 基础设施：embedding（向量化）、rerank（重排）、query 改写 | `embedding/bge_service.py`、`rerank/cross_encoder_service.py`、`retrieval/query_rewriter.py` |
| `app/schemas/` | **Pydantic 数据结构**：请求/响应/内部对象定义 | `rules.py`（规则问答相关）、`race.py`、`news.py`、`chat.py`、`agent.py`、`chunk.py` |
| `app/core/` | 横切设施：日志、Prometheus 指标、request_id | `logging.py`、`metrics.py` |
| `app/db/` | 数据库连接与 ORM 模型 | `engine.py`、`models.py` |
| `app/config/` | 配置（从 `.env` 读取） | `settings.py` |
| `app/middleware/` | 请求中间件 | `access_log.py`、`request_context.py` |
| `app/mcp/` | **MCP server**：把能力暴露成标准工具 | `pitwall_server.py`、`__main__.py` |

### 5.2 前端 `frontend/`

| 目录 | 作用 |
| --- | --- |
| `app/page.tsx` | 聊天主页（会话侧栏 + 消息 + 证据面板 + 流式渲染） |
| `app/rag/page.tsx` | RAG Lab：可视化检索各阶段（keyword/vector/hybrid/final） |
| `components/` | `message-bubble.tsx`（消息气泡）、`evidence-panel.tsx`（证据抽屉）、`session-list.tsx`（会话列表）、`workspace-nav.tsx`（导航） |
| `services/api.ts` | 所有后端 API 调用 + SSE 解析 |
| `lib/chat-utils.ts` | 抽取引用的工具函数 |
| `types/chat.ts` | TypeScript 类型（与后端 schema 对应） |

### 5.3 脚本与数据

| 目录/文件 | 作用 |
| --- | --- |
| `scripts/run_agent_eval.py` | 跑 Agent 评测（59 条 golden 用例） |
| `scripts/run_rag_eval.py` | 跑 RAG 检索评测（60 条，keyword/vector/hybrid 三模式） |
| `scripts/run_qa_eval.py` | 跑端到端回答质量评测（LLM judge） |
| `scripts/build_regulation_chunks.py` | 从 FIA PDF 构建法规语料（解析→切块→向量化→激活） |
| `scripts/refresh_news.py` / `ingest_formula1_news.py` | 新闻摄入 |
| `scripts/benchmark_api.py` | 接口压测 |
| `data/regulations/raw/` | 6 份 FIA 官方规则 PDF（**只读源资产**） |
| `data/regulations/processed/` | 构建产物：chunks.json、manifest、结构化 JSON/MD |
| `data/evals/*.jsonl` | 三套评测集（agent/rag/qa 用例） |
| `tests/` | 全部测试（单元/接口/评测/基础设施） |
| `migrations/` | 数据库表结构变更（Alembic） |
| `ops/` | Prometheus 与 Grafana 配置 |
| `.github/workflows/ci.yml` | CI 流水线（lint、测试、评测门禁） |

> **自检**：后端的分层（api→agents→services→repositories→db）分别管什么？想改检索算法改哪个文件？

---

## 6. 核心机制逐个讲透

### 6.1 意图路由 `app/agents/intent_router.py`

**做什么**：判断用户问题属于哪一类——`news`（新闻）/ `race`（赛况）/ `regulation`（规则）/ `strategy`（策略）/ `general`（通用）。

**怎么做的**：纯关键词/中文别名匹配。`RACE_KEYWORDS` 里有"比赛、积分榜、下一站、上一场、谁赢…"，`REGULATION_KEYWORDS` 里有"规则、红旗、安全车、罚时…"。按优先级依次检查：regulation → strategy → news → race → general。

**为什么不直接用 LLM 判断**：关键词判断**快、稳、可测**（59 条 golden 用例保证不误判），而 LLM 慢且不稳定。项目只在"明显是通用闲聊"时（`general`）才让 LLM planner 上场——这是"确定性兜底 + LLM 处理歧义"的混合设计。

### 6.2 Agent 运行图 `app/agents/runtime_graph.py`（本项目的心脏）

LangGraph 把流程画成一张图，节点是函数，边决定流向：

```text
START → classify_intent → plan_tool → execute_tool → judge_result
                                                      │
                     finish 或无需判断 ──────────────→ format_response → END
                     需要重试（judge 给出 next_plan）→ 回到 plan_tool（循环，最多 3 步）
```

- **`classify_intent`**：调用 `Planner.plan()` 得出 `{intent, tool_name, action, params}`。
- **`plan_tool`**：如果反射器给了 `next_plan`，用它覆盖原计划（重试/换方案）。
- **`execute_tool`**：`ToolDispatcher.execute_plan()` 真正调用工具。
- **`judge_result`**：`Reflector.judge()` 决定是结束还是重规划。
- **`format_response`**：`ResponseFormatter.build()` 生成最终中文回答 + trace。

**关键点**：
- 用 `MemorySaver` 做检查点（支持中断恢复，虽然目前单次调用不依赖）。
- `on_token` 通过 `threading.local` 传递，让工具执行时能把 LLM 的 token 逐字回调出去（用于流式）。
- 失败修复能力：工具执行失败时，反射器（LLM）根据错误给出修复计划，实现 ReAct 闭环。

### 6.3 工具与调度 `app/tools/` + `app/agents/tool_dispatcher.py`

**工具 = 能力单元**。每个工具返回统一的 `ToolResult(tool_name, success, payload, error)`（`app/tools/base.py`）。

| 工具 | 动作 | 背后服务 |
| --- | --- | --- |
| `race_tool` | list_schedule / next / previous / driver_standings / constructor_standings / race_results | `RaceService` |
| `news_tool` | list_recent / search / get_article / get_insights / get_rules_analysis | `NewsService` |
| `regulation_tool` | ask / debug_retrieval | `RegulationQAService` |
| `strategy_tool` | analyze | `StrategyAnalysisService` |
| `general_tool` | answer | `GeneralAnswerService` |

`ToolDispatcher` 负责两件事：**根据意图+消息选具体动作**（`build_plan`，大量关键词启发式）和**执行**（`execute_plan`，分发到对应工具，并记录 Prometheus 指标）。

### 6.4 RAG 检索管线 `app/repositories/rule_repository.py`（另一个心脏）

一条规则问题进来后，检索分几步（可对应 RAG Lab 界面看到每一阶段）：

```text
用户问题
  → _normalize_question（规范术语，如 Section A 统一格式、加同义词）
  → query_rewriter.rewrite（可选的查询改写，生成额外检索问法）
  → 关键词检索 _search_by_keywords：BM25 + 短语命中 + 条款号 + Section 偏好
  → 向量检索 _search_by_vector：BGE-M3 编码问题 → pgvector 余弦相似度（带 Section 感知）
  → 融合 _fuse_candidates：Reciprocal Rank Fusion（RRF）合并两个列表
  → 重排 _apply_model_rerank：bge-reranker-v2-m3 交叉编码器对候选再打分
  → 关键词兜底 _apply_keyword_guardrail：关键词强命中时优先
  → 返回 top-k chunks（每个带 score_components 可解释分数）
```

**为什么这么复杂**：评测证明纯向量（余弦相似度）对"抽象问题 vs 法律条文"召回差（R@5 只有 66.7%），词法信号（BM25、条款号）在这个领域更强，所以必须"向量召回 + 词法兜底 + 重排精排"。详见 `docs/evals/rag-vector-ablation.md`。

### 6.5 规则问答 `app/services/qa_service.py`

检索到片段后，`RegulationQAService.ask()` 决定怎么回答：

1. **判断问题类型**：`fact_lookup`（具体事实）/ `section_overview`（某个 Section 概览）/ `document_overview`（整本规则概览）——概览类不再走普通 top-k，而是聚合代表性条款。
2. **证据强度判断**：`_has_strong_evidence()`——只有"强证据"才让 LLM 生成确定回答。
3. **三种回答路径**：
   - 有强证据 → 把片段塞给 LLM 生成**带引用的回答**（prompt 强制"只依据片段、不编造"）；
   - 证据弱 → 给**保守的部分回答**（partial_evidence）；
   - 无证据 → **确定性拒绝**（`insufficient_evidence`），不编规则。
4. 引用（citation）由检索到的结构化 chunk 生成（文档名、条款、页码），**不让模型自编来源**。

### 6.6 会话与记忆 `chat_service.py` + `session_service.py` + `memory_service.py`

- **会话**（SessionService）：`session_id` 关联历史消息。默认存内存，`SESSION_BACKEND=redis` 时存 Redis，支持过期 TTL。
- **上下文压缩**（`context_compaction.py`）：历史太长时，让 LLM 把旧对话总结成"主题/事实/偏好/待办/实体"结构化摘要，省 token。
- **长时记忆**（`memory_service.py`）：跨会话记住用户偏好（如"我喜欢红牛"），存 Redis（`MEMORY_LONG_TERM_BACKEND=redis`），召回时先用 BGE-M3 向量相似、失败回退词法。

### 6.7 新闻与赛况 `news_service.py` / `race_service.py`

- **新闻**：`NewsIngestionService` 定时从 Formula1.com / Motorsport.com 的 RSS 拉取，`NewsRepository` 去重入库（按 source_article_id 唯一）。`NewsInsightService` 做确定性分类和实体抽取（车手/车队/赛道中文别名）。
- **赛况**：`JolpicaRaceDataProvider` 请求外部 API；成功写 Redis last-good 缓存；失败读缓存（标注时间）；都没了用本地种子数据（明确标注"仅演示用"）。回答末尾的**来源标签**由 formatter 统一追加，保证数据透明。

### 6.8 MCP `app/mcp/pitwall_server.py`

MCP = Model Context Protocol，让任意 AI 客户端（Claude Desktop、mcp inspector 等）通过标准协议调用你的能力。项目把 10 个工具（法规问答、赛况、新闻）用 FastMCP 暴露：

- stdio 传输：`uv run python -m app.mcp`（本地拉起）；
- Streamable HTTP：FastAPI 挂载 `/mcp`（远程连）。
- **设计精髓**：工具方法直接复用 `RegulationQAService` / `RaceService` / `NewsService`，不复制逻辑——内部 Agent 和外部客户端行为一致。

### 6.9 评测体系 `data/evals/` + `scripts/`

| 评测 | 文件 | 测什么 |
| --- | --- | --- |
| Agent golden | `agent_cases.jsonl`（59 条） | 意图/工具/动作/回答/证据是否对 |
| RAG | `rag_cases.jsonl`（60 条） | 检索是否召回正确条款（Recall/MRR/拒答率） |
| QA | `qa_cases.jsonl`（21 条） | 回答本身质量（状态准确率、引用一致、LLM judge 忠实度） |

三个脚本 `run_agent_eval.py` / `run_rag_eval.py` / `run_qa_eval.py` 读取用例、跑系统、对比期望值、输出报告并返回退出码（不达标 CI 红）。**这是"改代码不怕改坏"的保障**。

> **自检**：回答一条规则问题，检索管线走了哪几步？无证据时会怎样？

---

## 7. 关键算法用大白话讲

| 算法/概念 | 大白话 | 出现位置 |
| --- | --- | --- |
| **BM25** | 关键词打分：一个词在文档里出现得越多、在整个语料里越稀有，分越高。适合精确匹配"维修区超速"。 | `rule_repository._score_chunk_bm25` |
| **余弦相似度** | 把文本编码成向量，算两个向量夹角的接近程度（越接近 1 越相似）。适合"同义表达"。 | `rule_repository._search_by_vector` |
| **RRF 融合** | 把两个排序列表按"排名倒数"合并：`1/(k+rank)`，不依赖两个分数量纲是否可比。 | `rule_repository._fuse_candidates` |
| **交叉编码器重排** | 双编码器（向量检索）先粗召回 40 条，再用一个更聪明的模型把"问题-每条候选"成对比较精排。 | `app/rag/rerank/cross_encoder_service.py` |
| **证据强度** | 检索片段是否真的是规则原文（含"精确条款命中"等信号），决定回答是确定还是保守。 | `rule_repository`（score_components.evidence_strength） |
| **Token 流式** | LLM 逐字生成，回调把每个 token 立刻推给前端。 | `chat_service.stream_chat` |
| **LLM-as-judge** | 用一个 LLM 给另一个 LLM 的回答打分（忠实度/有用性/是否该拒答），强制 JSON 输出保证可解析。 | `app/services/llm/judge.py` |
| **last-good 缓存** | 上游 API 成功后把结果存 Redis，失败时回退到"最近一次成功的数据"，保证演示不断、且标注来源。 | `app/services/data_cache.py` |

---

## 8. 数据模型 `app/db/models.py`

| 表 | 存什么 | 关键列 |
| --- | --- | --- |
| `regulation_chunks` | 规则检索的基本单元（一条条款/表格/概览块） | `chunk_id`（确定性唯一）、`content`、`embedding`(vector1024)、`article`、`clause_id`、`section_code`、`corpus_version`、`chunk_type` |
| `regulation_corpora` | 语料版本与激活状态（同一套数据可多版本切换） | `corpus_version`、`active`、`embedding_model`、`validation` |
| `news_articles` | 新闻文章 | `source_article_id`（去重）、`title`、`article_url`、`published_at` |

**corpus 版本切换的意义**：规则 PDF 更新后构建新版本语料，校验通过才"原子激活"，旧版本保留可回滚。查询永远只查 `active=True` 的语料，避免重复条款。

---

## 9. 怎么运行、怎么调试

### 一键运行（推荐演示用）
```bash
docker compose up --build        # 后端+前端+Postgres+Redis 全起来
# Chat: http://localhost:3000
# API 文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health/ready
```
带监控面板：`docker compose --profile observability up --build`（Grafana 在 `localhost:3001`）。

### 本地开发运行（改代码用）
```bash
uv sync                         # 装依赖
docker compose up -d postgres redis   # 只起数据库
uv run alembic upgrade head     # 建表
uv run uvicorn app.main:app --reload  # 后端（改代码自动重启）
cd frontend && npm install && npm run dev  # 前端
```

### 调试三板斧
1. **看日志**：后端输出 JSON 结构化日志，含 `event`、`request_id`、各阶段耗时。改 `app_log_level=DEBUG` 看更细。
2. **看接口**：`http://localhost:8000/docs` 是 OpenAPI 交互文档，能直接试每个接口。
3. **看检索细节**：RAG Lab 页面（`/rag`）能看 keyword/vector/hybrid 每一阶段召回什么、分数多少。

### 跑评测（改完必跑）
```bash
uv run ruff check .             # 代码风格
uv run pyright                  # 类型检查
uv run pytest -m "not infrastructure"   # 测试（数据库相关用 -m infrastructure）
uv run python scripts/run_agent_eval.py
uv run python scripts/run_rag_eval.py --mode keyword
uv run python scripts/run_qa_eval.py --mode offline
```

---

## 10. 常见修改任务（想去改什么，改哪里）

| 你想做 | 改哪个文件 | 说明 |
| --- | --- | --- |
| 新增一个意图（如"天气"） | `intent_router.py`（加关键词）+ `tool_dispatcher.py`（加动作）+ `tools/`（新工具）+ `runtime_graph`/`reflector` 白名单 | 工具、意图、反射器三处白名单要保持一致 |
| 改规则检索效果 | `app/repositories/rule_repository.py` + 跑 `run_rag_eval.py` 验证 | 加/改关键词、Section 信号、融合权重 |
| 改问答 prompt/回答风格 | `app/services/qa_service.py` 的 `_build_messages` | 规则回答的系统提示词在这里 |
| 新增一个工具 | 建 `tools/xxx_tool.py` + `tool_dispatcher.py` 注册 + schema | 参考 `race_tool.py` 的写法 |
| 改前端界面 | `frontend/app/page.tsx` / `components/` | 聊天页、证据面板 |
| 加一个 API 接口 | `app/api/` 新 router + `app/schemas/` 定义 + `router.py` 挂载 | 参考 `race.py` |
| 改评测用例 | `data/evals/*.jsonl` | 加用例后注意同步 `tests/evals/` 里的数量断言 |
| 换 LLM | `.env` 改 `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | OpenAI 兼容即可 |
| 换 embedding/重排模型 | `settings.py` 的 `regulation_embedding_model` / `regulation_rerank_model` | 换模型需重新向量化语料 |

---

## 11. 术语表（速查）

- **Agent**：能自主决定"调什么工具、要不要重试"的系统。
- **Intent（意图）**：用户问题属于哪类（race/news/regulation…）。
- **Tool（工具）**：Agent 能调用的能力单元，统一返回 `ToolResult`。
- **Action（动作）**：一个工具下的具体操作（如 race_tool 的 get_race_results）。
- **RAG / Hybrid Retrieval**：混合检索（词法+向量）再重排。
- **Chunk（块）**：语料切成的检索单元，一个块是一个条款或表格。
- **Evidence / Citation**：检索到的证据块 / 回答中的引用。
- **ReAct**：思考→行动→观察的循环。
- **Reflector（反射器）**：决定 ReAct 是否继续的"裁判"。
- **Trace**：一次请求的完整决策记录（intent/tool/action/耗时），前端证据面板展示。
- **answer_status**：回答契约：`answered` / `partial_evidence` / `insufficient_evidence`。
- **corpus_version / active**：语料版本号 / 是否激活。
- **SSE**：Server-Sent Events，服务端推流。
- **last-good 缓存**：上游失败时回退的"最近成功数据"。
- **MCP**：AI 应用互操作标准协议。

---

## 12. 学习自检清单（通关才算懂）

读完并动手后，你应该能回答：

1. [ ] 用一句话说明项目是干什么的，和普通聊天机器人差在哪。
2. [ ] 画出后端分层（api → agents → services → repositories → db），各层职责。
3. [ ] 完整讲出"上一场比赛谁赢了"从浏览器到回答经过的文件链。
4. [ ] 说出 LangGraph 图有哪几个节点、ReAct 循环什么时候触发。
5. [ ] 说出 RAG 检索的五步管线，以及为什么不能用纯向量。
6. [ ] 说出三种 answer_status 分别什么时候出现。
7. [ ] 说出会话、上下文压缩、长时记忆分别在哪个服务、存哪里。
8. [ ] 说出三套评测各测什么、怎么跑。
9. [ ] 说出 MCP 复用了哪些服务、怎么启动。
10. [ ] 能自己新增一个最简单的工具并让它被路由到。

---

## 附：推荐阅读顺序

1. 本文档第 1-3 章（概念+架构）
2. 第 4 章完整请求旅程（对照文件）
3. 第 6 章逐个机制（对照文件）
4. 第 7-8 章算法与数据
5. 第 9 章跑起来 + 第 10 章动手改一个小功能
6. 面试前读 `docs/cn/03_Interview_Guide_zh.md`（高频追问 + 话术）
