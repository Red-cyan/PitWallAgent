# PitWall Agent 源码导读与工程实践

> 本文回答四个问题：项目用了什么技术、代码怎样工作、为什么这样设计、出现问题时怎样定位。
>
> **实现事实以当前代码、Alembic migration、测试和评测脚本为准。** 早期产品与架构文档保留了设计背景和演进目标，不代表每项设想都已经落地。

## 1. 项目解决什么问题

PitWall Agent 不是简单的“聊天页面加大模型”。它把 F1 问题分流给实时数据工具、法规 RAG 或通用模型，并要求事实回答可追踪、可评测、可降级：

- 赛况和新闻尽量来自外部数据源，不依赖模型记忆。
- FIA 法规必须检索原文；证据不足时拒绝武断回答。
- 路由、工具、检索、生成、会话和流式协议能独立测试。
- LLM、数据库或 Redis 不可用时明确降级，不伪造成功。

推荐阅读顺序：`app/api/chat.py` -> `app/services/chat_service.py` -> `app/services/agent_service.py` -> `app/agents/runtime_graph.py` -> `app/agents/planner.py` -> `app/agents/tool_dispatcher.py` -> `app/tools/`。法规链路再按 `regulation_parser.py` -> `chunker.py` -> `rule_repository.py` -> `qa_service.py` 阅读，最后看前端 `services/api.ts`、Chat 和 RAG Lab 页面。

## 2. 技术栈、选择理由与取舍

| 技术 | 项目用途 | 为什么这样选 | 代价或替代方案 |
| --- | --- | --- | --- |
| Python 3.12 | 后端、PDF 和评测脚本 | AI、PDF、Embedding 生态完整 | CPU 密集任务可进一步拆成任务队列 |
| FastAPI | REST、SSE、OpenAPI | Pydantic 整合好，接口契约清晰 | 当前 SSE 使用线程；高并发可改全异步 |
| Pydantic Settings | `.env` 和类型化配置 | 配置错误更早暴露 | 生产还需要 Secret Manager |
| LangGraph | Agent 状态图 | 节点、状态和失败路径可测试 | 当前小图也能用普通函数实现，多一层抽象 |
| OpenAI SDK / DeepSeek | 兼容接口和 token stream | 易替换兼容供应商 | 供应商兼容度、错误码和延迟仍不同 |
| SQLAlchemy / Alembic | ORM、事务、schema 迁移 | 数据模型和变更可复现 | 性能问题仍需理解实际 SQL |
| PostgreSQL / pgvector | corpus、新闻、向量 | 结构化字段和向量共库，支持事务激活 | 超大规模可考虑独立向量库 |
| Redis | session、TTL、最近会话索引 | 低延迟且适合短期状态 | 本地可用 memory；当前无集群保障 |
| PyMuPDF / pypdf | 坐标文本、表格和 fallback | 能利用 PDF 布局，pypdf 负责兜底 | 版式变化需要 parser fixture 回归 |
| sentence-transformers / BGE-M3 | 多语言 embedding | 适合中英文 FIA 问题 | 首次下载慢，CPU 推理慢，raw vector 仍偏弱 |
| Next.js 16 / React 19 / TypeScript | Chat 和 RAG Lab | 路由、类型、构建链成熟 | 当前状态局部，不需要 Redux |
| pytest / Ruff / Pyright | 行为、风格、类型门禁 | 分工明确且适合 CI | 静态检查不替代边界测试 |
| ESLint / Playwright | 前端静态和 E2E | 覆盖 Hook、桌面/移动交互 | 浏览器测试执行成本较高 |
| Prometheus / Grafana | 指标和仪表盘 | 行业通用，便于演示观测闭环 | 本地配置不是生产级 HA 监控 |

主线不是堆技术，而是划分责任：LLM 处理含糊语言和生成，Tool 提供事实，数据库保证版本和事务，评测证明检索质量。

## 3. 目录职责

```text
app/
  api/             HTTP 路由和协议转换
  agents/          LangGraph、Planner、ToolDispatcher
  tools/           Agent 能力的统一适配层
  services/        业务流程、PDF、外部数据、会话和问答
  repositories/    数据库和本地 corpus 查询
  schemas/         Pydantic 数据契约
  db/              SQLAlchemy engine、session、models
  core/            日志、指标、请求上下文
frontend/
  app/             Next.js Chat 和 RAG Lab 页面
  components/      消息、会话、证据和导航
  services/        API 请求和 SSE 解析
  e2e/             Playwright 场景
data/              PDF 源文件、生成语料、评测集
migrations/        Alembic 数据库变更
scripts/           构建、导入、评测、benchmark
tests/             与后端分层对应的 pytest
ops/               Prometheus / Grafana 配置
```

关键边界：API 不写业务规则，Tool 不直接承担复杂存储，Repository 不决定回答措辞。这样数据源、检索算法和 UI 可以分别演进。

## 4. 本地运行与配置

当前只要求本地运行，无需先处理 Docker。后端：

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

前端另开终端：

```powershell
cd frontend
npm install
npm run dev
```

默认前端 `http://localhost:3000`，后端 `http://127.0.0.1:8000`。不使用 Redis 时配置 `SESSION_BACKEND=memory`；不使用数据库向量检索时设置 `REGULATION_PREFER_DATABASE=false`、`REGULATION_VECTOR_RETRIEVAL_ENABLED=false`，系统仍可用本地 chunks 做 keyword 检索。

| 环境变量 | 含义与风险 |
| --- | --- |
| `LLM_API_KEY` | 兼容 `DEEPSEEK_API_KEY`；为空时通用生成明确降级 |
| `LLM_BASE_URL` / `LLM_MODEL` | 供应商地址和模型；协议或权限不符会失败 |
| `LLM_TIMEOUT_SECONDS` | 太短误杀慢响应，太长拖累用户体验 |
| `LLM_PLANNER_ENABLED` | 控制含糊问题是否调用模型 Planner |
| `REGULATION_EMBEDDING_MODEL` | 默认 `BAAI/bge-m3`，首次可能下载大模型 |
| `REGULATION_PREFER_DATABASE` | 是否优先查询数据库 active corpus |
| `REGULATION_VECTOR_RETRIEVAL_ENABLED` | 没有 embeddings 时不要开启 |
| `SESSION_BACKEND` / `REDIS_URL` | memory 重启丢失；Redis 需单独可达 |
| `DATABASE_URL` / `POSTGRES_*` | 完整 URL 优先；schema 必须匹配 Alembic |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器视角的后端地址，注意 CORS |

不要提交真实 `.env`。新增配置时同步更新 `settings.py` 和 `.env.example`。

## 5. 一次聊天请求的完整调用链

```text
Next.js
  -> POST /api/chat/stream
  -> ChatService.stream_chat
  -> AgentService.stream_query
  -> LangGraph runtime
  -> Planner -> ToolDispatcher -> Tool
  -> Service / Repository / 外部 API / LLM
  -> AgentResponse
  -> SSE message_delta + message_completed
  -> 前端消息与证据面板
```

`app/api/chat.py` 暴露同步聊天、SSE、会话列表、详情、删除和历史。API 只做校验与协议转换，不判断问题类别。

`ChatService` 获取 session、读取历史和 memory context，先保存 user turn，再执行 Agent；只有完整成功后才保存 assistant turn 和长期偏好。用户取消时保留问题便于重试，但不会把半句话当完整回答。

`runtime_graph.py` 将 plan、工具结果和最终回答放在显式 state 中。当前坚持单 Agent、多工具：业务边界用 Tool 已经足够，多 Agent 会增加模型成本和不可预测性。LangGraph 的价值是节点可测，也为将来的审核、重试节点保留结构。

## 6. Planner 和五类工具

Planner 采用“启发式优先，LLM 补充”。条款号、赛程、排名等高置信表达直接构造 plan；一般问题、短追问和含糊表达才调用 LLM Planner。模型只能返回支持的 `intent`、`action`、`params`，代码会解析 JSON、验证 intent/action 组合并重建参数。超时、非法 JSON 或不支持的动作都会回退到启发式计划。

这么做可以减少延迟和费用，阻止模型凭空调用工具，并保证供应商故障时核心功能仍可用。

| Tool | 责任 | 主要实现 |
| --- | --- | --- |
| `news_tool` | 最新新闻、搜索、新闻规则关联 | F1 RSS、news service/repository |
| `race_tool` | 赛程、赛果、车手和车队积分 | Jolpica/Ergast-compatible API、缓存 |
| `regulation_tool` | FIA 条款问答和引用 | `QAService` + `RuleRepository` |
| `strategy_tool` | 比赛策略分析 | 确定性业务 service |
| `general_tool` | 开放式 F1 问题 | LLM 与明确 fallback |

所有工具返回统一 `ToolResult`，Runtime 不需要知道每个数据源的内部细节。

## 7. SSE 与真实 token stream

| 事件 | 含义 |
| --- | --- |
| `session_started` | 尽快给前端 session ID、request ID |
| `status` | `thinking`、`routing`、`retrieving`、`generating` |
| `message_delta` | provider token 或缓冲文本片段 |
| `message_completed` | 完整回答、证据、trace 和 history |
| `error` | 清洗后的稳定错误 |

同步 SSE 生成器无法在一个线程里一边阻塞执行 Agent、一边 yield token。`ChatService.stream_chat` 因此用 producer 线程执行 Agent，用线程安全 `queue.Queue` 传 token、完成或异常。

Regulation 和 General 将 `on_token` 传到 `LLMClient`，供应商增量直接成为 `message_delta`，trace 标为 `stream_mode=token`。赛况等确定性回答没有 provider token，完成后分片输出，标为 `buffered`。协议相同，但指标不会把缓冲分片冒充真实 token。

前端手动解析 `ReadableStream`，因为原生 `EventSource` 不支持 POST。解析器保留未完成 buffer，空行才结束一个事件。`AbortController` 取消请求；后端取消传播到 token callback，且成功完成之前不持久化 assistant。错误响应不暴露密钥、prompt 或堆栈。

## 8. Session 与 Memory

`SessionService` 支持：

- `memory`：零依赖，适合测试和本地学习；进程重启即丢失，不能多实例共享。
- `redis`：session key 是 `pitwall:session:<session_id>`，最近会话 sorted set 是 `pitwall:sessions:index`，分值为更新时间。

Redis 写入带 TTL。index 可能短暂保留已过期 ID，读取列表时会过滤。历史超过 `MEMORY_COMPACTION_TOKEN_THRESHOLD` 后，早期 turn 合入 summary，近期原文保留；`MemoryService` 再按预算组合 summary、recent turns 和长期偏好。

这里使用近似 token 预算，并非供应商 tokenizer 的精确值。长期记忆也不应保存密钥或敏感信息。项目没有认证，所以 session ID 不能当严格授权凭证。

## 9. 法规 PDF 结构化解析

旧按页切片会导致跨页条款断裂、条款号缺失，以及页眉 `C132` 被误判为条款。检索算法无法修复解析阶段已经丢失的结构。

新链路：

```text
FIA PDF
  -> positioned text blocks + tables
  -> Document / Article / Clause / List / Table
  -> structured JSON（权威中间产物）
  -> review Markdown（人工审阅）
  -> clause-aware chunks -> embeddings
  -> staging validation -> active corpus
```

`regulation_parser.py` 使用 PyMuPDF 获取文本块、坐标和表格，按页面位置与跨页重复频率过滤页眉、页脚、版权、日期和页码。页面提取失败时才使用 pypdf fallback，因为它不能提供同等级布局。

条款候选除正则外，还必须符合当前 Section 前缀、合法层级和正文位置，所以顶部的 `C132 2026 Formula 1...` 不会建立 Clause。解析器维护跨页 clause state，并保存 `page_start/page_end`。

表格保留 headers、rows 和所属 clause。成本帽或 ATR 表格若压平为普通文本，年份、列和值的对应关系会丢失。结构化 JSON 是入库权威源；Markdown 只用于 review 和 Git diff，禁止反向解析入库。

本阶段没有 OCR。扫描 PDF 应校验失败，不能生成看似成功的空 corpus。

## 10. Clause-aware Chunking

`chunker.py` 默认以最低层编号 Clause 为检索单元，目标最大 1,600 字符：短条款保持整体；长条款优先按列表项、段落和语义标点拆分；表格按表头加行组拆分，每个 part 重复表头。同 clause 的 part 共享 `clause_id`，序号稳定。

| `chunk_type` | 内容与用途 |
| --- | --- |
| `clause` | 条款正文，是事实回答首选证据 |
| `table` | 表头和行组，用于数值对应关系 |
| `article_overview` | Article 标题和子条款索引，只服务宽泛概览 |

展示 `content` 保留原文；`embedding_text` 注入 Section、Article 和 breadcrumb。这样向量具有上下文，而引用不会出现人为注水文本。

ID 形式为：

```text
<document-slug>:<corpus-version>:<scope>:<clause>[:occurrence]:<chunk-type>:pNN
```

它由文档版本、条款路径、重复 occurrence 和 part ordinal 决定，不依赖页内随机号。相同输入应产生相同 ID。`content_hash` 是原始展示内容的 SHA-256。命中一个 part 后可补邻近 part 作为上下文，但不改变原始排名。

## 11. Manifest、校验和原子激活

`regulation_corpora` 记录 corpus version、parser version、PDF source hashes、chunk 参数、embedding model、status、active、validation 和时间。`regulation_chunks` 保存正文、向量、版本、clause、type、hash 和页码。

新 corpus 先写 staging，解析、校验、入库和 embedding 全部完成后，才在数据库事务中停用旧版本并激活新版本。构建失败不会影响旧 active corpus；旧版本保留用于回滚。

质量门禁：正文条款号缺失率低于 2%，伪页眉条款为 0，正文覆盖率至少 98%，页码范围合法，chunk ID 不重复。命令：

```powershell
uv run python scripts/build_regulation_chunks.py `
  --corpus-version fia-2026-YYYYMMDD `
  --emit-markdown `
  --activate
```

只检查可用 `--validate-only`。不要手改 manifest 强行激活失败语料，否则会破坏“active 一定完整”的不变量。

## 12. Keyword、Vector 与 Hybrid Retrieval

`RuleRepository` 的 candidate limits 分别是 vector 40、keyword 40、hybrid 50。

Keyword 组合 BM25、短语、条款号、Section、标题和字段信号，再 rerank。精确 `B5.14.2` 查询直接提升对应 `clause_id`；Section 过滤使用结构化字段。同分时按源 corpus 顺序排序，避免集合遍历顺序让评测抖动。

Vector 使用同一 BGE-M3 生成 1,024 维 query embedding，在 pgvector 中取相似项。它擅长同义表达，却可能混淆主题相近但法律约束不同的条款。当前 raw vector Clause Recall@5 为 66.67%，证明 embedding 并不自动优于词法检索。

Hybrid 使用 Reciprocal Rank Fusion：

```text
RRF score = sum(1 / (60 + rank))
```

之后执行结构化 rerank 和证据过滤。关键常量：`MIN_RERANK_SCORE=8`、`PARTIAL_RERANK_SCORE=1`、`MIN_KEYWORD_EVIDENCE_SCORE=6`。Keyword 第一名达到 `KEYWORD_GUARDRAIL_SCORE=20` 时，保护强词法结果，防止弱向量把精确条款挤出 Top 5。

当前 60 条评测中 keyword 和 adaptive hybrid Clause Recall@5 都是 100%。Hybrid 无法在已经饱和的 Recall 上再提升 3 个百分点，正确结论是做到无回退，同时保留同义改写能力；不能为了指标篡改报告。

## 13. QA Grounding

`QAService` 区分 `fact_lookup`、`section_overview` 和 `document_overview`。结果状态：

| 状态 | 含义 |
| --- | --- |
| `answered` | 强证据足够，基于引用作答 |
| `partial_evidence` | 有相关材料，但不足以确认结论 |
| `insufficient_evidence` | 没有可靠证据，明确拒绝 |

相关文本不等于足够证据。例如数值问题只命中 Article 概览时不能让 LLM 补数。引用保留文档、Clause、页码、chunk type、corpus version 和 breadcrumb；debug API 额外给出 score components，用于区分召回失败和排序失败。

## 14. MCP 集成

`app/mcp/` 用官方 `mcp` SDK（FastMCP）把三类核心能力暴露为标准 MCP 工具：法规 RAG（`regulation_ask`、`regulation_debug_retrieval`）、赛况（`race_schedule`、`race_next`、`race_previous`、`race_driver_standings`、`race_constructor_standings`、`race_results`）、新闻（`news_search`、`news_recent`）。

工具方法直接复用 `RegulationQAService` / `RaceService` / `NewsService`，与内部 Agent 工具同源，不复制业务逻辑；返回统一 `{success, ...}` 契约，证据不足沿用确定性拒绝语义。

- stdio：`uv run python -m app.mcp`，可被 Claude Desktop、`uvx mcp dev`（inspector）直接拉起。
- Streamable HTTP：`app.main` 挂载 `/mcp` 子应用，远程 client 指向 `http://localhost:8000/mcp`。
- 测试：`tests/mcp/test_pitwall_server.py` 断言工具注册集合与每个工具的出入参、错误路径。

设计细节见 `docs/rfcs/zh/RFC-007-MCP_zh.md`。

## 15. 前端

Chat 页面管理 session、history、流式草稿、状态、错误和选中证据。收到 delta 追加草稿，收到 completed 后用服务端完整对象替换，确保最终证据与 trace 一致。停止生成只取消当前请求，失败时保留手动重试入口。证据在桌面端为侧栏，移动端为 drawer。

RAG Lab 不是第二个聊天页，而是检索调试台：展示 active corpus、候选阶段、最终排名、chunk type、breadcrumb、页码和评分分量。排错顺序是检查精确条款识别、keyword/vector 召回、RRF、rerank/阈值、最终 corpus version。

当前没有 Redux/Zustand，因为跨页面共享状态很少。复杂缓存、权限或乐观更新出现后再引入更合理。

## 16. 数据模型和迁移

| 表 | 作用 |
| --- | --- |
| `regulation_chunks` | chunk、clause、type、page、content、embedding、corpus version |
| `regulation_corpora` | source hash、参数、状态、active 和 validation manifest |
| `news_articles` | 新闻来源、URL、正文、发布时间和原始 payload |

查询必须限定 active corpus，否则保留的旧版本会产生重复条款。`chunk_id` 唯一，常用结构化字段有索引。`20260727_0002_clause_aware_corpus.py` 增加 corpus 字段和 manifest 表；修改 ORM 后忘记升级 Alembic，会在真实数据库出现“column does not exist”，即使 mock 测试正常。

## 17. 可观测性

结构化日志记录 request ID、路由、工具、检索数量、结果和阶段耗时，但不应记录密钥。`/metrics` 暴露 HTTP、Tool、LLM、RAG、Stream、TTFT、总时长、active corpus 数量和上游重试等 Prometheus 指标。

分析 TTFT 时要结合 `stream_mode`，buffered 首片和真实 provider token 含义不同。`ops/` 的 Grafana 配置证明观测闭环，不代表生产告警、长期存储或高可用已经完成。

## 18. 测试和评测

四层质量保障：单元测试覆盖 Planner、Parser、Chunker 和排序；API/Repository 测试覆盖契约与证据；离线 golden cases 覆盖 Agent 和 60 条法规问题；Playwright 覆盖桌面/移动 Chat、停止、证据和 RAG Lab。

```powershell
uv run pytest
uv run ruff check .
uv run pyright
uv run python scripts/run_agent_eval.py
uv run python scripts/run_rag_eval.py --mode keyword

cd frontend
npm run lint
npm run build
npm run test:e2e
```

Keyword 是普通 PR 的确定性门禁；Vector/Hybrid 需要同一 BGE 模型、active corpus 和 pgvector，放在 integration job，避免普通 CI 下载大模型。当前基线为 200 passed、2 skipped；Keyword Recall@5 100%、Section Recall@5 100%、MRR 约 0.80；Hybrid Recall@5 100%；拒绝率 100%。以 `docs/evals/` 最新报告为准。

## 19. 常见问题与定位

| 现象 | 常见原因 | 定位与处理 |
| --- | --- | --- |
| 通用回答降级 | 缺少 key、模型无权限 | 检查 `.env` 和 LLM 日志；不要把 fallback 当真实模型 |
| 很久没有首 token | Provider、Planner 或检索慢 | 看 TTFT、stage latency、stream mode，分别调整超时 |
| 首次 vector 很慢 | BGE-M3 下载或 CPU 加载 | 检查 HF cache；可先关闭 vector 验证 keyword |
| Vector 无结果 | 无 embedding 或维度不符 | 看 active embedding 数与 1,024 维配置，统一模型重建 |
| 命中旧条款 | active 状态或过滤错误 | 看 manifest 与 debug corpus version，重新正确激活 |
| 会话重启丢失 | 使用 memory backend | 本地可接受；持久化时配置可达 Redis |
| Redis 不可用 | URL、密码、端口错误 | 临时切 memory，先验证业务；再单独排 Redis |
| 数据库缺列 | Alembic 未升级 | 检查 `alembic current/history`，执行 migration |
| 浏览器请求失败 | API base 或 CORS | 看 Network、`NEXT_PUBLIC_API_BASE_URL`、allowed origins |
| 新 PDF 覆盖率低 | FIA 布局变化 | 审阅 JSON/Markdown，加 fixture 后调整启发式 |
| 表格值错位 | table extraction 合并列 | 对照 headers/rows 与原 PDF，不能让 LLM 猜 |
| 出现 `C132` 假条款 | 页眉规则失效 | 看坐标和 false-header 门禁，补回归 fixture |
| 停止后保存半句 | 取消未传播或保存过早 | 检查 StreamCancelled，assistant 只在成功后 append |
| Keyword 好、Vector 差 | 模型不适配或短条款相似 | 看 RAG Lab 分量，保留 guardrail 并评估模型 |
| 本地与 DB 结果不同 | corpus/参数/模型不同 | 对比 manifest source hash 和 build parameters |

先判断问题属于浏览器协议、API、Agent、Tool、检索、数据还是模型。不要一看到错误答案就只改 prompt。

## 20. 已知边界和安全问题

- 没有认证、授权、多租户和 rate limit，不能直接暴露公网。
- session ID 不是可靠身份凭证。
- 本地/Compose 是作品集拓扑，不是高可用生产部署。
- 没有 OCR；图片型 PDF 无法解析。
- FIA 布局变化需要持续维护 parser fixtures。
- 法规回答不替代 FIA 官方解释和专业审核。
- Raw vector 较弱，hybrid 仍依赖 keyword guardrail。
- 外部新闻和赛况 API 可能限流、超时或改 schema。
- 真实 LLM 非确定，CI 不应对措辞做严格字符串断言。
- SSE producer 使用线程；高并发要评估线程、队列背压和取消传播。
- 日志与长期记忆尚未实现完整隐私和删除治理。

## 21. 面试表达与源码练习

推荐用问题、方案、取舍、数据来讲：

> 我把 F1 问答拆成确定性工具和法规 RAG。高置信问题用启发式路由，含糊问题才用 LLM Planner，并校验 action 后回退。法规 PDF 先解析成跨页 Clause 和 Table，再生成确定性 chunk；Keyword、BGE-M3 和 RRF 做混合检索，强词法证据用 guardrail 保护。Corpus 先 staging 校验，再事务切换 active version。回答区分 answered、partial 和 insufficient evidence，并通过 SSE 返回真实 token 与引用。

需要能解释：为什么没有多 Agent、为什么 JSON 而不是 Markdown 是权威源、为什么 raw vector 弱仍保留 hybrid、为什么取消后只保存 user turn。

建议亲手完成：

1. 给 Planner 增加一种 heuristic 并补单测。
2. 构造跨页 Clause，比较 structured JSON、Markdown 和 chunks。
3. 在 RAG Lab 对比精确条款与同义问题的评分。
4. 调高证据阈值，观察 answered 变为 partial。
5. 停止一次 token stream，检查 history 只有 user turn。
6. 修改 chunk 正文，验证 hash 改变而稳定 ID 不乱变。
7. 添加一个伪页眉 parser fixture，并让回归测试保护它。

高频追问：

**为什么不用纯 LLM 路由？** 明确问题可确定识别，纯 LLM 增加延迟、费用和失败面；模型应该解决含糊性。

**为什么不用纯向量？** 法规编号、术语和数字有强词法信号，raw vector 实测更弱；hybrid 让同义与精确匹配互补。

**如何防幻觉？** 不是只改 prompt，而是权威数据、结构化解析、证据门槛、拒答状态、引用和离线评测共同约束，且仍保留专家审核边界。

**为什么 active 切换要事务？** 构建和 embedding 可能部分失败；事务保证读请求只看到完整版本。

**LangGraph 必要吗？** 当前用函数也能做，但状态图让节点可测并方便扩展审核/重试；代价是抽象层，所以没有再拆多 Agent。

**生产化还缺什么？** 认证授权、rate limit、Secret 管理、异步任务、连接池/背压、隐私治理、告警与 SLO，之后才是多实例和独立向量库。

## 22. 文档冲突时以什么为准

优先级：测试验证过的当前代码 -> Alembic 与 API schema -> corpus manifest 和评测报告 -> 本导读与根 README -> 产品/历史架构/RFC 的设计意图。

发现冲突先用测试复现，再修改实现或文档。明确区分现状、目标和已知问题，比声称“生产级但没有边界”更可信。
