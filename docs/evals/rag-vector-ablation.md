# Vector Retrieval Ablation

目标：诊断"纯向量（BGE-M3 dense）Clause Recall@5 只有 66.67%"的根因，并尝试改进。

评测集：`data/evals/rag_cases.jsonl`（60 条，正样本 57）。检索面：active corpus `fia-2026-20260625`（6198 chunks，pgvector）。指标口径与 `scripts/run_rag_eval.py --mode vector` 一致。

## 结果总览

| 配置 | Clause R@5 | Clause R@1 | MRR | Section R@5 |
| --- | ---: | ---: | ---: | ---: |
| 基线：纯 BGE-M3 dense cosine | 66.67% | 42.1% | 0.504 | 98.2% |
| + Section 感知检索（V1） | 68.4% | 43.9% | 0.527 | 100% |
| + 交叉编码器重排（V2，bge-reranker-v2-m3 重排 15 候选） | **73.7%** | 47.4% | 0.574 | 100% |
| 对照组：重排池扩到 30 候选 | 71.9% | — | 0.567 | 100% |
| 生产路径：keyword + hybrid（RRF + 重排） | 100% | 66.7% | 0.787 | 100% |

## 根因诊断

1. **正确条款的余弦排位很低（22~67 名）**。对 19 个基线失败案例做 top-80 余弦扫描，大部分正确条款排在 22-67 位，甚至 4 个在 top-80 之外。原因：查询是抽象问法（"How are regulatory breaches handled?"），而条款是法律条文原文，BGE-M3 对整段长条款求均值后，关键概念被稀释。
2. **跨 Section 混淆**。`applicable-regulations`（期望 Section A）命中 C1.2.1 等"applicable regulations"措辞相近的其它 Section 条款。
3. **同 Section 内近邻条款压过目标条款**。`skid-block` 期望 C3.6.2，但 C3.6.3（金属滑板）语义更近；`safety-car` 期望 B5.12.1，但 B5.13（Safety Car）更像。

## 改进实现

- **V1 Section 感知检索**（`rule_repository.py`）：`_search_by_vector` 扩大候选池、捕获 cosine 分数，并复用 keyword 路径已有的 `_match_preferred_sections`（"Section D"、"technical rules"、"sporting rules"、条款号等信号），对候选按 Section 偏好优先排序。补充了 Section B 关键词（track limits / impeding / sporting）。
- **V2 交叉编码器重排**：把向量候选（15 条）送入已有的 bge-reranker-v2-m3，用 query-chunk 成对相关性重新排序。该模型生产路径（hybrid）已在用，此处补齐"单检索器"侧的重排。

## 结论

- 纯 dense 向量在**法律条款检索**这类"抽象问题 vs 具体法条"场景天然偏弱，改进后 R@5 66.67% → 73.7%（+7pp）、MRR 0.504 → 0.574、Clause@1 42% → 47.4%，缩小了对 keyword 兜底的依赖，但无法靠单一检索器达到 100%。
- 重排候选池过大反而引入跨 Section 噪声（30 候选 < 15 候选），说明候选精炼比堆量更重要。
- **架构结论**：hybrid（keyword BM25 + dense + RRF 融合 + 交叉编码器重排）稳定 100% 是被评测数据证明的必要设计——legal 检索对词面信号高度敏感，稠密向量负责召回候选，词法信号负责精度兜底。

实现文件：`app/repositories/rule_repository.py`（`_search_by_vector` / `_search_by_vector_queries` / `search(mode="vector")` / `_apply_model_rerank(max_candidates)`）。
