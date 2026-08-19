# PitWall Agent 5 分钟演示手册

## 演示前检查

```bash
docker compose up --build
```

打开 `http://localhost:3000`、`http://localhost:8000/health/ready` 和 `http://localhost:8000/metrics`。如果 Docker 镜像源不可用，可按 README 的本地开发方式启动，并设置法规文件检索模式。

> 注意：改过代码后要 `docker compose up -d --build backend` 重建镜像，否则演示的是旧代码（端口 8000 被旧容器占用时最常见）。

## 演示流程

### 1. 多工具路由

依次提问：

- `下一场比赛是什么时候？`
- `车手积分榜前 3 名是谁？`
- `今天有什么 F1 新闻？`

展示回答下方 trace 中的 intent、tool、action、source 和 latency，说明 Planner 只负责计划，外部访问封装在工具内。

### 2. 比赛结果能力

提问：`谁赢得了比赛` 或 `上一场比赛谁赢了`

展示 get_race_results 返回冠军、领奖台，以及回答末尾的数据来源标签（`数据源：Jolpica API`）。说明结果信号路由（谁赢/赢得/夺冠）有 golden eval 覆盖。

### 3. 有证据的规则回答

提问：`What is an unsafe release from the pit lane?`

展开 citation 和 retrieved chunks，展示文档、Section、article、page、score components 与 evidence strength。强调回答只使用检索证据，引用由结构化 chunk 生成，不让模型自行编造来源。

### 4. 拒绝编造

提问：`What is the alien pit lane rule?`

展示 `insufficient_evidence`、低 confidence、零 citation，说明无证据状态是显式回答契约，并有 golden eval 防止回归。

### 5. 数据降级与来源透明（新增亮点）

断网（或临时停掉外部 API）后再问一次比赛结果：

- 若 Redis 有 last-good 缓存 → 回答标注"数据源：Jolpica API 缓存 · 缓存时间 …"
- 若无缓存 → 标注"本地示例数据，仅演示用"

说明系统在上游故障时不拿假数据冒充真实数据，对来源完全透明。

### 6. 多轮记忆

先问：`车队积分榜前 5 名是谁？`，再问：`第 4 名呢？`

展示 session history 和 memory trace，说明系统只对追问继承上下文，显式的新主体查询不会被旧上下文污染。长时记忆后端为 PostgreSQL（user_id 维度画像），重启容器不丢"你记得我"。

### 7. MCP 互操作（2026 亮点）

```bash
uv run python -m app.mcp
uvx mcp dev app/mcp/pitwall_server.py   # 或 Claude Desktop 配置
```

展示 `tools/list` 返回 10 个工具、`tools/call` 调用 `race_driver_standings` / `regulation_ask`，说明标准协议互操作 + 单一事实来源（复用领域服务）。

### 8. 工程证据

打开 `/metrics`，展示 HTTP、tool、LLM 和 RAG 指标；随后展示 CI 与 `docs/evals` 中的基线结果（keyword/hybrid 100%、vector 消融 73.7%、QA judge 忠实度 ~4.8）。

## 面试主线

### 为什么是单 Agent 多工具

当前领域边界明确，单 Agent 可以减少自治组件之间的状态同步，让路由、参数、fallback 和引用契约都能做确定性测试。新增能力通过工具扩展，不需要修改运行图主流程。

### 如何证明 RAG 有效

Agent golden cases 衡量路由和回答契约；60 条独立 RAG 数据集衡量 Section Recall、Clause Recall@1/5、MRR 和域外强证据拒绝率。离线 keyword 门禁保持确定性，vector/hybrid 使用同一标注集和 active corpus 在手动 integration job 中做消融。向量消融报告说明为什么纯向量弱（正确条款余弦排位 22-67）、hybrid 为何必要。

### 如何证明回答质量

端到端 QA eval：offline（确定性状态准确率/引用一致性，进 CI）+ online（LLM-as-judge 打忠实度/有用性/决策正确率）。judge 用 `response_format=json_object` + 重试保证结构化输出。

### 如何处理外部依赖故障

HTTP 和 LLM 调用有明确超时；赛况数据走"实时 → Redis last-good 缓存 → 本地种子"三级回退并在回答标注来源；readiness 区分依赖故障；日志和 Prometheus 指标用于定位失败阶段。

## 必须主动说明的限制

- regulation/general 的 SSE 使用底层模型 token streaming；赛况等确定性回答在 trace 中标记为 `buffered`。当前为 producer 线程实现，async 流是已知扩展点。
- 当前评测不能替代领域专家对每条 FIA 结论的人工审核。
- Compose 是单机演示拓扑，不代表已经实现高可用、认证和多租户。
