# PitWall Agent 秋招面试指南

## 项目定位

PitWall Agent 是一个面向 Formula 1 的垂直 AI Agent。它不是通用聊天机器人，而是围绕 F1 赛历、积分榜、FIA 规则、新闻和策略分析构建的可演示工程系统。

核心目标是：路由可解释、工具选择可追踪、规则回答有证据、质量可以用 eval 测出来。

## 架构主线

```text
User
  -> Next.js Chat UI
  -> FastAPI Chat API
  -> ChatService
  -> AgentService
  -> Planner
  -> Tool Dispatcher
  -> Race / News / Regulation RAG / Strategy / General tools
  -> PostgreSQL + pgvector / Redis / local regulation chunks / external F1 sources
```

面试中可以按这条链路讲一次完整请求：用户提问后，Planner 判断 intent，Tool Dispatcher 选择工具，工具返回结构化 payload，Response Formatter 生成最终回答，trace/citation 面板展示决策和证据。

## RAG 流程

规则问答的数据链路：

```text
FIA PDF
  -> chunking
  -> metadata extraction
  -> embedding
  -> keyword retrieval
  -> vector retrieval
  -> RRF hybrid fusion
  -> rerank
  -> grounded answer + citation
```

现在额外加入了 overview retrieval：

- `fact_lookup`：维修区超速、危险驾驶、unsafe release 等具体事实问题，继续走 hybrid retrieval。
- `section_overview`：`SectionA讲了什么内容`、`技术规则大概讲什么` 这类问题，按指定 Section 聚合代表性 chunk。
- `document_overview`：`F1的大体规则是什么样的`、`2026 FIA规则分几部分` 这类问题，按 Section A-F 总览。

这样可以避免普通 top-k similarity 用几个随机片段硬答概览问题。

## 为什么暂时不用 LangChain

当前项目优先级是可控、可测、可解释。Planner、Tool Dispatcher、RAG repository、Response Formatter 都是本地清晰模块，便于定位问题和写单元测试。

暂不引入 LangChain 的原因：

- 当前工具数量有限，本地编排足够清晰。
- 需要精细控制 trace、fallback、citation 和 answer_status。
- 面试项目更需要展示工程边界和问题闭环，而不是堆框架。
- LangGraph 已经承担运行图编排，暂时没有必要再叠加 LangChain 抽象。

## 已解决的问题

- 路由误判：用 golden eval 覆盖 race/news/regulation/strategy/general。
- 多轮上下文污染：车队积分榜后追问车手第 4 名，不继承车队上下文。
- 积分榜排名错误：formatter 支持按位置、主体、top N 输出。
- RAG 无证据幻觉：无证据时返回 `insufficient_evidence`，不编规则。
- 概览问题答不准：新增 section/document overview path。
- 演示不可观测：前端最后一条 assistant 消息增加折叠 trace/citation 面板。

## 如何启动

后端：

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

规则数据重建：

```bash
uv run python scripts/build_regulation_chunks.py
uv run python scripts/import_regulation_chunks.py
uv run python scripts/embed_regulation_chunks.py
```

质量评估：

```bash
uv run python scripts/run_agent_eval.py
uv run pytest
uv run ruff check .
uv run pyright
cd frontend && npm run build
```

## 演示问题

- `车队积分榜前5名都是谁`
- `车手积分榜第4名是哪位`
- `维修区超速是什么`
- `危险驾驶是什么`
- `SectionA讲了什么内容`
- `F1的大体规则是什么样的`
- `alien pit lane rule`

演示时重点打开最后一条回答的“调试 / 证据”面板，展示 intent、tool、action、answer_status、evidence_count、latency、citation 和 retrieved chunks。
