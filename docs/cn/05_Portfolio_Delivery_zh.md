# PitWall Agent 秋招交付说明

## 五分钟演示

1. 打开 Chat，提问 `下一站比赛是什么时候？`，展示 route、tool 和权威数据 source。
2. 提问 `What does B5.6.4 require?`，观察真实 token stream，并打开 Evidence 面板。
3. 打开 RAG Lab，运行同一问题，切换 keyword、vector、hybrid 和 final，展示精确条款提升、breadcrumb 和 score components。
4. 提问 `What is the alien pit lane rule?`，展示 `insufficient_evidence` 和零引用。
5. 打开 Grafana，展示 HTTP、RAG、LLM、stream outcome、TTFT 和 active corpus 指标。
6. 展示 CI 与 keyword/vector/hybrid 三份评测报告。

## 面试主线

- 为什么使用单 Agent、多工具：领域边界稳定，路由、参数、fallback 和引用契约可确定性测试。
- 为什么重建法规语料：逐页字符切片破坏跨页条款并产生伪条款号；结构化 JSON 才是权威中间产物。
- 为什么 hybrid 有 keyword guardrail：当前法规术语和条款号的 lexical 信号很强，raw vector 消融明显较差；自适应策略只在 keyword 弱时让向量主导。
- 如何实现真实流式：token callback 穿过 LLM、领域服务、工具和 LangGraph，由 ChatService producer thread 推送 SSE；完成前不持久化 assistant turn。
- 如何证明工程质量：60 条 RAG golden set、Agent eval、后端测试、Playwright 双视口、Prometheus/Grafana 和可重复压测。

## 必须主动说明

- Keyword Recall@5 已是 100%，因此 hybrid 不可能再提升 3 个百分点；验收调整为 Recall@5 不回退，并单独报告 MRR/Recall@1。
- Raw vector 结果作为消融证据，不应隐藏；它说明领域检索不能只依赖 embedding 相似度。
- 本项目不声称高可用、认证、多租户或 FIA 专家级事实审核。
