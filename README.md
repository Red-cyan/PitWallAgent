# PitWall Agent

PitWall Agent 是一个面向 Formula 1 信息检索与规则问答的 AI Agent 项目。它把 FastAPI、Next.js、LangGraph、RAG、pgvector、Redis 和外部 F1 数据源整合到一个可演示的工程系统中，目标是回答赛程、积分榜、FIA 规则、新闻和策略类问题，并在需要事实依据时优先检索外部数据。

## 核心能力

- 对话式 F1 助手：支持多轮会话、会话列表、历史加载和删除。
- Agent 工具编排：根据用户意图调度新闻、赛事、规则、策略和通用问答工具。
- FIA 规则 RAG：从 FIA 2026 规则 PDF 切分 chunks，优先使用 Postgres + pgvector 检索，失败时退回本地 chunks 与关键词重排。
- 实时/准实时数据：赛事数据来自 Jolpica / Ergast-compatible API，新闻来自 Formula1 RSS；外部服务不可用时有本地 seed 降级。
- 可观测性：结构化日志、请求 ID、工具 trace、健康诊断接口。

## 架构

```text
Next.js UI
  -> FastAPI API
  -> ChatService / AgentService
  -> LangGraph runtime
  -> ToolDispatcher
  -> News / Race / Regulation / Strategy / General tools
  -> PostgreSQL + pgvector, Redis, Jolpica API, Formula1 RSS, LLM provider
```

当前向量存储使用 `pgvector/pgvector:pg17`，不是 Milvus。历史文档中如果出现 Milvus，应以当前代码和 `docker-compose.yml` 为准。

## 快速启动

```bash
uv sync
docker compose up -d
uv run python scripts/init_pgvector_db.py
uv run python scripts/import_regulation_chunks.py
uv run uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认前端访问 `http://localhost:3000`，后端访问 `http://127.0.0.1:8000`。

## 配置

复制 `.env.example` 为 `.env` 后按需填写：

```env
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

SESSION_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=604800
```

没有配置 LLM key 时，系统会使用启发式规划和部分 fallback 回答；规则问答会尽量基于检索证据返回保守结果。

## 常用演示问题

- `下一场比赛是哪个？`
- `车手积分榜第一名是谁？`
- `constructor standings`
- `parc ferme 是什么规则？`
- `unsafe release 怎么处罚？`
- `今天 F1 有什么新闻？`
- `安全车下 Ferrari 要不要进站？`
- `刚才那条规则和处罚有什么关系？`

## 质量门禁

```bash
uv run ruff check .
uv run pyright
uv run pytest
uv run python scripts/run_agent_eval.py
cd frontend && npm run build
```

当前目标是后端 lint、类型检查、pytest、Agent eval 和前端 build 全部通过。`pytest` 覆盖 API、服务、工具、Agent runtime、RAG 检索、日志和 golden eval case；`scripts/run_agent_eval.py` 从 `data/evals/agent_cases.jsonl` 读取同一批样例并输出 intent/tool/action/answer/evidence/latency 指标。

## 当前优化重点

- Agent 质量评估：`data/evals/agent_cases.jsonl` 是 pytest golden test 和独立 eval script 的共同数据源。
- RAG overview：规则问答会区分 `fact_lookup`、`section_overview`、`document_overview`，用于回答 `SectionA讲了什么内容`、`F1的大体规则是什么样的` 等概览问题。
- 前端可观测性：最后一条 assistant 回答带默认折叠的“调试 / 证据”面板，展示 intent、tool、action、answer status、confidence、evidence、latency、citations 和 retrieved chunks。
- 面试材料：中文讲解见 `docs/cn/03_Interview_Guide_zh.md`。

## 诊断接口

- `GET /health`：返回数据库、Redis、LLM、RAG chunks、新闻表的诊断状态。
- `GET /api/agent/query`：低层 Agent 调试接口。
- `POST /api/chat`：主对话接口。
- `POST /api/chat/stream`：SSE 输出接口。当前实现是完整生成后分片输出，不是底层 LLM token streaming。

## 工程取舍

- 单 Agent + 多工具：降低调试复杂度，适合 MVP 和面试讲解。
- pgvector 而非独立向量库：减少本地部署成本，便于作品集复现。
- 检索优先、生成其次：规则类问题必须基于证据；证据不足时应明确拒绝编造。
- 降级优先：外部 API 不可用时保留基本演示能力，但响应中会通过 `source` 字段暴露数据来源。
