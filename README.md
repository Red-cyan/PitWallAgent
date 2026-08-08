# PitWall Agent

面向 Formula 1 的可解释 AI Agent 全栈项目。系统使用单 Agent、多工具架构整合实时赛况、新闻、FIA 法规 RAG、策略分析和 Redis 多轮会话，并把路由、检索证据、模型流式生成与失败降级暴露为可测试的工程契约。

## 核心能力

- LangGraph 运行图：意图识别、多步计划分解、按序工具执行、回答格式化；ReAct 裁判在失败、证据不足或结果不完整时触发重规划（正向推理循环）。
- 五类工具：赛况（赛历、下/上一站、车手/车队积分榜、比赛结果）、新闻（多源 RSS 聚合，启动自动摄入，中英别名检索）、法规、策略和通用 F1 问答。
- Clause-aware RAG：PDF 结构化解析、跨页条款、表格、确定性 chunk ID、active corpus 原子切换。
- Hybrid retrieval：keyword/BM25、BGE-M3、pgvector、RRF、交叉编码器重排（bge-reranker-v2-m3）、精确条款提升和 keyword guardrail。
- 真实 SSE：regulation/general 的 LLM token 直接输出；确定性回答显式标记为 `buffered`。
- 可恢复会话：Redis 历史、上下文压缩、长期偏好、语义记忆召回（BGE-M3 向量 + 词法回退）、停止生成和显式重试。
- MCP 互操作：法规 RAG、赛况、新闻能力以标准 MCP 工具暴露，支持 stdio（Claude Desktop / mcp inspector）与 Streamable HTTP（`/mcp`）两种传输。
- 全栈工作台：Chat、会话管理、证据抽屉，以及独立的 RAG Lab 检索分析页。
- 工程保障：Alembic、Docker Compose、Prometheus、Grafana、结构化日志、CI、Playwright 和离线评测。

## 当前质量基线

| 指标 | 结果 |
| --- | ---: |
| Agent intent/tool/action/evidence golden cases | 100% |
| Agent 多步计划 step sequence（66 cases，含 6 条多步依赖链） | 100% |
| Keyword Section Recall@5 | 100% |
| Keyword Clause Recall@5 | 100% |
| Keyword MRR | 79.65% |
| Vector-only Clause Recall@5 | 73.7%（Section 感知检索 + 交叉编码器重排，基线 66.7%） |
| Adaptive hybrid Clause Recall@5 | 100% |
| Adaptive hybrid MRR | ~78% |
| 无答案强证据拒绝率 | 100% |
| QA 回答状态准确率（offline 确定性） | 100% |
| QA 引用一致性（offline 确定性） | 100% |
| QA 回答忠实度（online LLM judge，均值） | ~4.8 / 5 |
| QA 拒绝/回答决策正确率（online） | ~90% |
| Active corpus | 6,198 chunks / 6,198 embeddings |

评测集包含 60 条精确条款、跨页、表格、同义改写、跨 Section 干扰和无答案问题。纯向量（BGE-M3 dense）在"抽象问法 vs 法律条文"场景下正确条款的余弦排位常落到 22-67 名，因此单检索器无法达到 100%——改进后的向量路径通过 Section 感知检索（复用查询的 Section 信号）和交叉编码器重排（bge-reranker-v2-m3）把 R@5 从 66.7% 提升到 73.7%、MRR 0.504→0.574，消融细节见 `docs/evals/rag-vector-ablation.md`。生产路径为 hybrid：keyword BM25 提供精度兜底、稠密向量召回候选、RRF 融合后由交叉编码器最终排序（`rerank_model` 分数进入 `score_components`），稳定 100%。Vector-only 评测在 CI 手动 workflow 的 `hybrid-eval` job 中与 keyword/hybrid 一起进门禁。评测在无 LLM key 下运行以保证确定性。

## 架构

```text
Next.js Chat / RAG Lab
  -> FastAPI chat + true SSE + retrieval debug API
  -> ChatService + Redis session memory
  -> LangGraph runtime
  -> Intent classify -> Multi-step Planner -> ToolDispatcher -> domain tools
  -> Judge (ReAct) 失败/证据不足 -> 重规划 -> 继续执行，直至完成
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

## 接入 MCP

核心能力以标准 MCP 工具暴露（法规 RAG、赛况、新闻，共 10 个工具）。

本地 stdio（Claude Desktop、`mcp inspector`）：

```bash
uv run python -m app.mcp
uvx mcp dev app/mcp/pitwall_server.py
```

Streamable HTTP（随 FastAPI 一起启动）：

```bash
docker compose up -d
# 任意 MCP client 指向 http://localhost:8000/mcp
```

工具清单与返回契约见 `docs/rfcs/zh/RFC-007-MCP_zh.md`。

## 数据来源与兜底策略

赛况数据来自 Jolpica/Ergast 实时 API，新闻来自 Formula1.com / Motorsport.com RSS。为保证上游故障时仍可演示且**不把示例数据冒充真实数据**：

- **last-good 缓存**：实时请求成功后把结果写入 Redis（`last_good:*`，默认 24h），上游失败时优先回退到最近一次真实数据，并在回答中标注"数据源：Jolpica API 缓存 · 缓存时间 …"。
- **本地示例数据**：仅在没有任何真实缓存时使用本地种子数据（`source=local_seed`），回答会明确标注"本地示例数据，仅演示用"。
- **实时数据**：正常返回时标注"数据源：Jolpica API"。

来源标签由 `app/agents/response_formatter.py` 统一追加，覆盖赛历、下一/上一站、车手/车队积分榜和比赛结果。

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
uv run python scripts/run_qa_eval.py --mode offline \
  --min-status-accuracy 0.95 \
  --min-citation-consistency 1.0
```

端到端回答质量评测（需配置 LLM key，评估结果也包含 LLM-as-judge 的忠实度/有用性/决策正确率）：

```bash
uv run python scripts/run_qa_eval.py --mode online \
  --min-status-accuracy 0.95 \
  --min-citation-consistency 1.0 \
  --min-groundedness-score 4.0 \
  --min-helpfulness-score 3.5 \
  --min-rejection-correct 0.9 \
  --json-output docs/evals/qa-online.json \
  --markdown-output docs/evals/qa-online.md
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
