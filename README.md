# PitWall Agent

面向 Formula 1 的可解释 AI Agent 全栈项目。系统使用单 Agent、多工具架构整合实时赛况、新闻、FIA 法规 RAG、策略分析和 Redis 多轮会话，并把路由、检索证据、模型流式生成与失败降级暴露为可测试的工程契约。

## 核心能力

- LangGraph 运行图：意图识别、计划生成、工具执行、回答格式化。
- 五类工具：赛况、新闻、法规、策略和通用 F1 问答。
- Clause-aware RAG：PDF 结构化解析、跨页条款、表格、确定性 chunk ID、active corpus 原子切换。
- Hybrid retrieval：keyword/BM25、BGE-M3、pgvector、RRF、交叉编码器重排（bge-reranker-v2-m3）、精确条款提升和 keyword guardrail。
- 真实 SSE：regulation/general 的 LLM token 直接输出；确定性回答显式标记为 `buffered`。
- 可恢复会话：Redis 历史、上下文压缩、长期偏好、语义记忆召回（BGE-M3 向量 + 词法回退）、停止生成和显式重试。
- 全栈工作台：Chat、会话管理、证据抽屉，以及独立的 RAG Lab 检索分析页。
- 工程保障：Alembic、Docker Compose、Prometheus、Grafana、结构化日志、CI、Playwright 和离线评测。

## 当前质量基线

| 指标 | 结果 |
| --- | ---: |
| Agent intent/tool/action/evidence golden cases | 100% |
| Keyword Section Recall@5 | 100% |
| Keyword Clause Recall@5 | 100% |
| Keyword MRR | 79.65% |
| Vector-only Clause Recall@5 | 66.67%（弱于 keyword，hybrid 用 RRF + 重排补齐） |
| Adaptive hybrid Clause Recall@5 | 100% |
| Adaptive hybrid MRR | ~78% |
| 无答案强证据拒绝率 | 100% |
| Active corpus | 1,984 chunks / 1,984 embeddings |

评测集包含 60 条精确条款、跨页、表格、同义改写、跨 Section 干扰和无答案问题。Raw vector 是消融项（R@5 66.67%），弱向量信号由 keyword guardrail 兜底；hybrid 用 bge-reranker-v2-m3 交叉编码器对融合候选做最终排序（`rerank_model` 分数进入 `score_components`）。当前评测集对 keyword 已偏易，重排的收益主要体现在排序质量而非 Recall；Vector-only 评测在 CI 手动 workflow 的 `hybrid-eval` job 中与 keyword/hybrid 一起进门禁。评测在无 LLM key 下运行以保证确定性。

## 架构

```text
Next.js Chat / RAG Lab
  -> FastAPI chat + true SSE + retrieval debug API
  -> ChatService + Redis session memory
  -> LangGraph runtime
  -> Planner -> ToolDispatcher -> domain tools
  -> PostgreSQL + pgvector / FIA corpus / external F1 sources / LLM
  -> Prometheus metrics -> optional Grafana dashboard
```

法规数据链路：

```text
FIA PDF
  -> PyMuPDF positioned blocks and tables
  -> Document / Article / Clause structured JSON
  -> review Markdown
  -> clause / table / article_overview chunks
  -> BGE-M3 embeddings
  -> staging validation
  -> atomic active-corpus switch
```

## 一键启动

前置条件：Docker Desktop，建议至少 8 GB 可用内存。

```bash
docker compose up --build
```

- Chat：`http://localhost:3000`
- RAG Lab：`http://localhost:3000/rag`
- OpenAPI：`http://localhost:8000/docs`
- Readiness：`http://localhost:8000/health/ready`
- Metrics：`http://localhost:8000/metrics`

启用本地监控面板：

```bash
docker compose --profile observability up --build
```

- Prometheus：`http://localhost:9090`
- Grafana：`http://localhost:3001`，默认进入 `PitWall / PitWall Overview`

真实模型回答需要在 `.env` 配置 OpenAI-compatible 服务：

```env
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

未配置 key 时，权威数据工具和确定性 fallback 仍可演示；通用生成会明确降级。

### 启用向量检索 / 重排 / 语义记忆

BGE-M3（embeddings）与 bge-reranker-v2-m3（重排）约需 5 GB 磁盘。默认关闭，避免 CI 和首次启动下载大模型：

```env
REGULATION_VECTOR_RETRIEVAL_ENABLED=true
REGULATION_RERANK_ENABLED=true
MEMORY_VECTOR_RETRIEVAL_ENABLED=true
HF_TOKEN=
# 可选：把宿主机已下载的模型目录挂载进容器（HF_HOME 所在目录，含 huggingface/ 与 sentence-transformers/）
HF_MODELS_DIR=E:\AIModels
```

若本机 5432 端口被系统保留（Windows Hyper-V 排除段 5340-5439 常见），可改宿主映射端口：

```env
POSTGRES_HOST_PORT=15432
```

## 开发与质量门禁

```bash
uv sync
uv run ruff check .
uv run pyright
uv run pytest
uv run python scripts/run_agent_eval.py
uv run python scripts/run_rag_eval.py --mode keyword \
  --min-section-recall-at-5 0.98 \
  --min-clause-recall-at-5 0.95 \
  --min-mrr 0.75 \
  --min-rejection-rate 1.0
```

```bash
cd frontend
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

带 active corpus 和 BGE-M3 的 hybrid integration 通过 GitHub Actions `workflow_dispatch` 手动运行，避免模型下载污染普通 PR 门禁。

本地性能检查：

```bash
uv run python scripts/benchmark_api.py --mode live --requests 50 --concurrency 20 --max-p95-ms 300
uv run python scripts/benchmark_api.py --mode retrieval --requests 20 --concurrency 5 --max-p95-ms 1500
uv run python scripts/benchmark_api.py --mode stream --requests 3 --concurrency 1
```

## 法规语料重建

```bash
uv run python scripts/build_regulation_chunks.py \
  --corpus-version fia-2026-YYYYMMDD \
  --emit-markdown \
  --activate
```

未通过条款缺失率、伪页眉、正文覆盖率、页码和重复 ID 校验的 corpus 不允许激活。旧版本默认保留，供显式回滚或清理。

## 已知边界

- Compose 是单机作品集拓扑，不代表高可用或多租户生产部署。
- 真实 LLM 的措辞、TTFT 和成本受供应商影响，因此普通 CI 只运行确定性测试。
- 离线检索评测证明条款可检索性，不替代 FIA 领域专家对最终法律/技术结论的审核。
- 当前不包含用户认证；本地演示环境不暴露到公网。

详细架构、评测和面试材料见 [docs](docs/README.md)。
