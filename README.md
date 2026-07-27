# PitWall Agent

面向 Formula 1 的可解释 AI Agent。系统通过单 Agent、多工具架构整合实时赛况、新闻、FIA 规则 RAG、策略分析与多轮会话，重点展示 Agent 质量评测、证据引用、故障降级和可观测性，而不只是调用一次大模型。

## 已实现能力

- LangGraph 运行图：意图识别、计划生成、工具执行、回答格式化。
- 五类工具：赛况、新闻、FIA 规则、策略分析、通用问答。
- 规则 RAG：keyword/BM25、pgvector、RRF hybrid fusion、rerank、引用和无证据保护。
- 会话记忆：内存或 Redis backend，支持历史加载、压缩摘要和长期偏好。
- 工程能力：FastAPI、Next.js、Alembic、Docker Compose、结构化日志、Prometheus 指标和分层 CI。
- 可解释前端：展示 intent、tool、action、confidence、latency、citation 和 retrieved chunks。

## 质量基线

| 评测 | 数据集 | 当前结果 |
|---|---:|---:|
| Agent intent/tool/action/answer/evidence | 56 cases | 100% |
| Offline RAG Recall@1 / Recall@5 | 39 positive cases | 89.74% / 94.87% |
| Offline RAG MRR / 条款命中率 | 39 positive cases | 0.9231 / 94.87% |
| 域外强证据拒绝率 | 3 negative cases | 100% |
| 核心 Python 模块覆盖率 | unit + integration | 81.75% |

完整结果见 [Agent baseline](docs/evals/agent-baseline.md)、[clause-level RAG baseline](docs/evals/rag-clause-keyword.md) 和 [RAG ablation protocol](docs/evals/rag-ablation.md)。这些是确定性离线门禁；真实 LLM 的输出质量仍会受到模型提供商和提示版本影响。

## 架构

```text
Next.js UI
  -> FastAPI chat/SSE API
  -> ChatService + Redis session memory
  -> LangGraph runtime
  -> Planner -> ToolDispatcher -> ResponseFormatter
  -> Race / News / Regulation RAG / Strategy / General tools
  -> PostgreSQL + pgvector / Redis / external F1 sources / LLM
```

关键取舍：当前采用单 Agent 多工具，而不是多 Agent。这样能让路由、工具参数、fallback、引用和失败状态保持可测试、可追踪，适合当前五个明确领域。

## 一键启动

前置条件：Docker Desktop，建议至少 8 GB 可用内存。首次构建会安装 sentence-transformers，耗时取决于网络与机器性能。

```bash
docker compose up --build
```

启动后访问：

- Web UI: `http://localhost:3000`
- OpenAPI: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`
- Prometheus metrics: `http://localhost:8000/metrics`

Backend 启动时会自动执行 `alembic upgrade head`。已有 pre-Alembic 本地数据库会被初始迁移接管，不会重建已有业务表。

如需真实模型回答，在 `.env` 中配置：

```env
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

未配置 key 时，路由与多数工具仍可运行；生成环节会使用保守 fallback。

## 本地开发

```bash
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm ci
npm run dev
```

如果只想离线使用法规 JSON 而不连接 pgvector，可设置：

```env
REGULATION_PREFER_DATABASE=false
REGULATION_VECTOR_RETRIEVAL_ENABLED=false
```

## 质量门禁

```bash
uv run ruff check .
uv run pyright
uv run pytest -m "unit or integration" --cov
uv run pytest -m eval
uv run python scripts/run_agent_eval.py
uv run python scripts/run_rag_eval.py --mode keyword
cd frontend && npm run build
docker compose config --quiet
```

测试会强制关闭真实数据库、embedding 和 LLM 调用。真实外部服务验证应通过独立 smoke test 运行，避免 CI 因网络或费用波动失去确定性。

## 可观测性

每个请求带 `X-Request-Id`，日志记录请求、Agent、工具、RAG 和 LLM 阶段。`/metrics` 暴露：

- HTTP 请求量、状态码和延迟
- 工具调用量、结果和延迟
- LLM 调用结果和延迟
- RAG 检索结果和延迟

指标使用路由模板和有限枚举标签，避免 session ID 等高基数字段污染 Prometheus。

## 已知限制

- `/api/chat/stream` 当前在完整回答生成后按文本切片发送 SSE，不是底层 LLM token streaming。
- 离线 RAG 基线衡量条款和 chunk 检索，不等价于人工事实正确性评分或端到端回答正确率。
- Docker Compose 面向单机作品集演示，不包含高可用、用户认证或多租户。
- 外部 F1 API/RSS 不可用时会回退本地 seed，响应中的 `source` 会暴露数据来源。

产品、架构和面试讲解材料位于 [docs](docs/README.md)。
