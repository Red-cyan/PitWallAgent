# PitWall Agent 秋招面试指南

## 项目定位

PitWall Agent 是一个面向 Formula 1 的垂直 AI Agent。它不是通用聊天机器人，而是围绕 F1 赛历、积分榜、FIA 规则、新闻和策略分析构建的可演示工程系统。

核心目标是：路由可解释、工具选择可追踪、规则回答有证据、质量可以用 eval 测出来、能力可以通过标准协议（MCP）被外部复用。

## 一句话卖点（30 秒电梯陈述）

> 我构建了一个 F1 领域的 LLM Agent：用 LangGraph 做有状态工具编排，用 clause-aware 混合检索做带证据的规则问答，用离线评测 + LLM-as-judge 证明检索和回答质量，并通过 MCP 把能力暴露给任意 AI 客户端。它不是一个 demo 聊天机器人，而是一套"路由-工具-RAG-评测-可观测"闭环的工程系统。

## 架构主线

```text
User
  -> Next.js Chat UI / 任意 MCP Client
  -> FastAPI Chat API + /mcp (Streamable HTTP)
  -> ChatService
  -> AgentService
  -> LangGraph Runtime (ReAct 循环)
  -> Planner -> Tool Dispatcher -> Race / News / Regulation RAG / Strategy / General tools
  -> PostgreSQL + pgvector / Redis / local regulation chunks / external F1 sources
  -> Prometheus metrics / JSON logs / CI eval gates
```

面试中可以按这条链路讲一次完整请求：用户提问后，Planner 判断 intent，Tool Dispatcher 选择工具，工具返回结构化 payload，Response Formatter 生成最终回答，trace/citation 面板展示决策和证据。额外的 ReAct 循环在工具失败或 general 回答不足时，由反射器（reflector）决定是否重规划。

## RAG 流程

规则问答的数据链路：

```text
FIA PDF
  -> clause-aware chunking（跨页合并、表格、确定性 chunk id）
  -> BGE-M3 embedding
  -> keyword retrieval (BM25 + 短语 + 条款号 + Section)
  -> vector retrieval (dense cosine + Section 感知)
  -> RRF hybrid fusion
  -> bge-reranker-v2-m3 交叉编码器重排
  -> grounded answer + citation / insufficient_evidence
```

现在额外加入了 overview retrieval：

- `fact_lookup`：维修区超速、危险驾驶、unsafe release 等具体事实问题，继续走 hybrid retrieval。
- `section_overview`：`SectionA讲了什么内容`、`技术规则大概讲什么` 这类问题，按指定 Section 聚合代表性 chunk。
- `document_overview`：`F1的大体规则是什么样的`、`2026 FIA规则分几部分` 这类问题，按 Section A-F 总览。

这样可以避免普通 top-k similarity 用几个随机片段硬答概览问题。

### 向量检索消融（面试高频）

纯 BGE-M3 dense 向量 Clause R@5 只有 66.7%。诊断出的根因：

1. **正确条款的余弦排位常落到 22-67 名**——"抽象问法 vs 法律条文"下，长条款 embedding 求均值稀释关键概念；
2. **跨 Section 混淆**——"applicable regulations"措辞在多个 Section 都出现；
3. **同 Section 近邻条款压过目标**——skid-block 期望 C3.6.2 却命中 C3.6.3。

改进：Section 感知检索（复用查询的 Section 信号做偏好排序）+ 交叉编码器重排，R@5 提升到 73.7%、MRR 0.504→0.574。重要负结果：重排池从 15 扩到 30 反而降到 71.9%（跨 Section 噪声），说明**候选精炼比堆量更重要**。

结论：法律条款检索对词面信号高度敏感，hybrid（BM25 精度兜底 + 稠密召回 + RRF + 重排）稳定 100% 是被评测证明的必要设计。详见 `docs/evals/rag-vector-ablation.md`。

## 为什么暂时不用 LangChain

当前项目优先级是可控、可测、可解释。Planner、Tool Dispatcher、RAG repository、Response Formatter 都是本地清晰模块，便于定位问题和写单元测试。

暂不引入 LangChain 的原因：

- 当前工具数量有限，本地编排足够清晰。
- 需要精细控制 trace、fallback、citation 和 answer_status。
- 面试项目更需要展示工程边界和问题闭环，而不是堆框架。
- LangGraph 已经承担运行图编排，暂时没有必要再叠加 LangChain 抽象。

## MCP 集成（2026 JD 高频关键词）

把法规 RAG、赛况、新闻三类能力暴露为标准 MCP 工具（10 个），任何 MCP 客户端（Claude Desktop、mcp inspector、Agent 框架）都能直接调用：

- **stdio**：`uv run python -m app.mcp`，可被 `uvx mcp dev` / Claude Desktop 拉起。
- **Streamable HTTP**：FastAPI 挂载 `/mcp`，远程 client 指向 `http://localhost:8000/mcp`。
- **单一事实来源**：工具方法直接复用 `RegulationQAService` / `RaceService` / `NewsService`，与内部 Agent 同源，不复制业务逻辑。
- **返回契约统一**：`{"success": true, ...}` / `{"success": false, "error": ...}`，证据不足沿用确定性拒绝语义。
- 技术决策：锁定 `mcp>=1.9,<2`（2.x 移除了 FastMCP 模块，改用更低层的 MCPServer；1.x 的 `@mcp.tool()` 是行业通用声明式写法）。

设计细节见 `docs/rfcs/zh/RFC-007-MCP_zh.md`。

## 评测体系（四层质量证明）

| 层 | 对象 | 指标 |
| --- | --- | --- |
| 单元/API/仓库测试 | 路由、证据、工具契约 | 303 tests，coverage ≥80% |
| Agent golden eval | 意图/工具/动作/回答/证据 | 59 cases 100% |
| RAG eval | Section/Clause Recall@1/5、MRR、拒答率 | keyword/hybrid 100%，vector 73.7%（消融） |
| 端到端回答质量 eval | LLM 生成答案本身 | offline（确定性）+ online（LLM-as-judge 忠实度/有用性/决策正确率） |

**LLM-as-judge**（`app/services/llm/judge.py`）：对真实 LLM 生成的回答打分——groundedness（忠实度 1-5）、helpfulness、rejection_correct；`response_format=json_object` 强制 JSON 输出 + 空响应/解析重试（最多 6 次）。基线：状态准确率 100%、忠实度均值 ~4.8、决策正确率 ~90%。offline 模式禁用 LLM 与重排、走确定性 fallback，因此能进普通 CI 门禁。

## 数据可信与来源披露

赛况数据来自 Jolpica 实时 API。为了在上游故障时仍可演示、且**不把示例数据冒充真实数据**：

- **last-good 缓存**：实时请求成功写 Redis（24h），失败优先回退最近真实数据，回答标注"数据源：Jolpica API 缓存 · 缓存时间 …"。
- **本地示例**：没有任何缓存时使用种子数据，明确标注"本地示例数据，仅演示用"。
- 回答末尾统一追加来源标签，覆盖赛历/积分榜/比赛结果。

这是面试可以主动讲的诚信设计：**系统在数据降级时对用户透明**。

## 已解决的问题

- 路由误判：用 golden eval 覆盖 race/news/regulation/strategy/general。
- `谁赢得了比赛` 被误路由到赛历：结果信号 tokens 覆盖"谁赢/赢得/夺冠"等措辞，agent eval 新增 3 条比赛结果用例。
- 裸车队名（`法拉利`）被误路由到赛历：team tokens → get_constructor_standings。
- 多轮上下文污染：车队积分榜后追问车手第 4 名，不继承车队上下文。
- 积分榜排名错误：formatter 支持按位置、主体、top N 输出。
- RAG 无证据幻觉：无证据时返回 `insufficient_evidence`，不编规则。
- 概览问题答不准：新增 section/document overview path。
- 演示不可观测：前端最后一条 assistant 消息增加折叠 trace/citation 面板。
- 静态兜底数据伪装成真实数据：来源披露 + Redis last-good 缓存。
- 向量召回弱：Section 感知检索 + 交叉编码器重排，R@5 66.7%→73.7%。
- Docker 重启丢长期记忆：长时记忆后端切 Redis。
- 回答质量不可量化：LLM-as-judge 端到端评测闭环。

## 如何启动

后端：

```bash
uv sync
docker compose up -d
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

MCP 调试：

```bash
uv run python -m app.mcp
uvx mcp dev app/mcp/pitwall_server.py
```

规则数据重建：

```bash
uv run python scripts/build_regulation_chunks.py \
  --corpus-version fia-2026-YYYYMMDD \
  --emit-markdown \
  --activate
```

质量评估：

```bash
uv run python scripts/run_agent_eval.py
uv run python scripts/run_rag_eval.py --mode keyword
uv run python scripts/run_qa_eval.py --mode offline
uv run pytest
uv run ruff check .
uv run pyright
cd frontend && npm run build && npm run test:e2e
```

## 演示问题

- `车队积分榜前5名都是谁`
- `车手积分榜第4名是哪位`
- `维修区超速是什么`
- `危险驾驶是什么`
- `SectionA讲了什么内容`
- `F1的大体规则是什么样的`
- `谁赢得了比赛`（比赛结果能力）
- `上一场比赛谁赢了`（上一站结果 + 来源标签）
- `alien pit lane rule`（拒绝编造）

演示时重点打开最后一条回答的"调试 / 证据"面板，展示 intent、tool、action、answer_status、evidence_count、latency、citation、retrieved chunks 和数据来源标签。

## 高频追问 Q&A

### 1. 为什么用 LangGraph 不用 AutoGen / CrewAI？
LangGraph 是显式的图状态机：条件边、检查点、重试、循环都可见可测。AutoGen 面向多 Agent 对话、CrewAI 偏角色协作，都更适合科研/演示；我需要的是**可确定性测试的单 Agent 编排**，LangGraph 与我的 eval 门禁闭环最契合。

### 2. 这是 Agent 还是"规则路由 + 聊天"？
架构上是有状态 Agent：LangGraph 图（classify → plan → execute → judge → 循环），反射器在工具失败时给出修复计划。**路由层**用确定性启发式是为了可测和防回归（59 条 golden），**歧义问题**（general）会交给 LLM planner。这是"确定性兜底 + LLM 处理歧义"的混合设计，不是玩具路由。

### 3. 为什么 RAG 用混合检索而不是纯向量？
消融报告证明了答案：法律条款是"抽象问法 vs 具体法条"，纯 dense 向量正确条款的余弦排位常落到 22-67 名，R@5 只有 66.7%。词法信号（BM25、条款号、Section）在这个领域更强；hybrid 让"同义召回 + 精确匹配"互补到 100%。

### 4. RRF 和直接拼接分数有什么区别？
RRF 对两个排序列表按 `1/(k+rank)` 融合，不依赖各检索器分数尺度可比（cosine 和 BM25 量纲不同）。直接拼分数需要调权、且向量弱时会被压过。RRF 用排序位置而非分数，鲁棒。

### 5. 怎么防止幻觉？
三层：检索证据兜底（无证据→`insufficient_evidence` 确定性拒绝）；prompt 强约束（只依据片段回答、引用只能来自片段）；端到端 LLM-as-judge 评测忠实度（均值 ~4.8），并有拒答正确率的门禁。

### 6. 为什么 judge 用 LLM 而不是规则/指标？
忠实度是语义判断，规则（token 重叠）只能做弱信号；LLM-as-judge 能判断"这句话证据支不支持"。配套做了工程化：`response_format=json_object` 强制 JSON、空响应重试、解析失败不中断整个评测。确定性指标（citation 一致性、状态准确率）仍保留在 offline 门禁里做无 key 回归。

### 7. MCP 是什么？你项目里怎么用的？
MCP 是 AI 应用与外部工具/数据互操作的标准协议（"AI 的 USB-C"）。我把法规 RAG、赛况、新闻暴露成 10 个标准工具，支持 stdio（Claude Desktop / inspector）和 Streamable HTTP（`/mcp`），并且**复用领域服务不复制逻辑**，保证内部 Agent 和外部调用行为一致。

### 8. 数据源挂了怎么办？
Jolpica 挂了 → 读 Redis last-good 缓存（标注缓存时间）；缓存也没有 → 本地种子数据（明确标注"仅演示用"）。回答对来源完全透明，不拿假数据冒充。

### 9. 多轮对话上下文怎么管理的？
Redis 会话历史 + 上下文压缩（token 预算内总结）+ 长时记忆（Redis 持久化，语义召回 BGE-M3 + 词法回退）。显式新主体查询不会继承旧上下文（有 regression 用例）。

### 10. 评测集会不会是自说自话？
60 条 RAG 数据集独立于实现标注（跨页、表格、同义改写、跨 Section 干扰、无答案负例），且 keyword/vector/hybrid 三份报告可对同一数据集复现；Agent 59 条 golden 覆盖六类意图。评测在无 LLM key 下确定性运行，保证 CI 可复现。

### 11. SSE 怎么实现的？为什么这么实现？
regulation/general 的 LLM token 通过回调穿过领域服务、工具、LangGraph，由 ChatService 推给前端；确定性回答标记为 `buffered`。当前是 producer 线程 + queue 的实现（面试可主动说"这是已知的扩展点，下一步可换 async 流"）。

### 12. 部署了什么？
本地单机 Docker Compose 拓扑（postgres/pgvector、redis、backend、frontend、可选 Prometheus/Grafana）。刻意不做高可用/认证/多租户——作为作品集明确声明边界，而不是假装生产级。

### 13. 为什么选择 BGE-M3 / pgvector / bge-reranker？
BGE-M3 支持多语言（中英 FIA 语料）+ dense/sparse 多范式，本地可部署；pgvector 让向量和元数据同库，避免多系统；重排用 bge-reranker-v2-m3 交叉编码器，比双编码器对"问题-条款"更准。

### 14. 最大的失败或教训？
向量消融的负结果最有价值：我一度以为加大重排候选池能提升，实测 30 候选反而比 15 差（跨 Section 噪声），说明**检索要"精"而非"多"**。这种"用评测否定假设"的过程正是工程可信度的来源。
