# PitWall Agent 秋招交付说明

## 五分钟演示

1. 打开 Chat，提问 `下一站比赛是什么时候？`，展示 route、tool 和权威数据 source。
2. 提问 `谁赢得了比赛`，展示比赛结果 + 数据来源标签。
3. 提问 `What does B5.6.4 require?`，观察真实 token stream，并打开 Evidence 面板。
4. 打开 RAG Lab，运行同一问题，切换 keyword、vector、hybrid 和 final，展示精确条款提升、breadcrumb 和 score components。
5. 提问 `What is the alien pit lane rule?`，展示 `insufficient_evidence` 和零引用。
6. 断网再问一次比赛结果，展示缓存兜底 + "数据源：…缓存"标注（若可行）。
7. 打开 Grafana，展示 HTTP、RAG、LLM、stream outcome、TTFT 和 active corpus 指标。
8. 展示 CI 与 keyword/vector/hybrid 三份评测报告 + QA judge 报告。
9. 时间允许时用 `uvx mcp dev` 演示 MCP 工具被外部客户端调用。

## 面试主线

- 为什么使用单 Agent、多工具：领域边界稳定，路由、参数、fallback 和引用契约可确定性测试。
- 为什么重建法规语料：逐页字符切片破坏跨页条款并产生伪条款号；结构化 JSON 才是权威中间产物。
- 为什么 hybrid 有 keyword guardrail：法规术语和条款号的 lexical 信号强；向量消融证明纯 dense 召回弱（R@5 66.7%），Section 感知 + 交叉编码器重排提升到 73.7%，但单检索器仍无法到 100%，因此 keyword 兜底是必要设计。
- 如何实现真实流式：token callback 穿过 LLM、领域服务、工具和 LangGraph，由 ChatService producer thread 推送 SSE；完成前不持久化 assistant turn。
- 如何证明回答质量：LLM-as-judge 端到端评测（忠实度/有用性/决策正确率），`response_format=json_object` + 重试保证结构化。
- 如何实现生态互操作：MCP server 暴露 10 个工具，复用领域服务，单一事实来源。
- 如何保证数据可信：实时 → Redis last-good 缓存 → 本地种子三级回退，回答标注来源，不拿假数据冒充。
- 如何证明工程质量：60 条 RAG golden set、59 条 Agent eval、QA judge、后端测试、Playwright 双视口、Prometheus/Grafana 和可重复压测。

## 必须主动说明

- Keyword Recall@5 已是 100%，因此 hybrid 不可能再提升 3 个百分点；验收调整为 Recall@5 不回退，并单独报告 MRR/Recall@1。
- Raw vector 是消融证据，不应隐藏；`docs/evals/rag-vector-ablation.md` 记录诊断（正确条款余弦排位 22-67）与改进（73.7%）以及负结果（重排池 30 < 15），说明领域检索不能只依赖 embedding 相似度。
- LLM-as-judge 是带噪声的近似指标（rejection 阈值 0.85），不是金标准；确定性指标（状态准确率、引用一致性）作为 CI 主门禁。
- 本项目不声称高可用、认证、多租户或 FIA 专家级事实审核。
- 部署为本地单机 Compose 拓扑，刻意不做公网部署/CD。
