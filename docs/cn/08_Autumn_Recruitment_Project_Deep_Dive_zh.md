# PitWall Agent 秋招项目深挖（统一 LangGraph 运行时架构）

> 本文档基于重构后代码（commit `42fa3a5 统一 LangGraph 工具调用编排`、`4379b91 完善Agent循环耗尽后的强制总结`），逐层拆解"一个 Agent 从收到问题到给出回答"的完整链路，并给出面试高频追问的参考答案。
>
> 配套阅读：`07_Complete_Technical_Guide_zh.md`（逐模块实现细节）、`docs/rfcs/zh/RFC-008-Function-Calling_zh.md`（双 planner 模式的权衡设计）。

---

# 0. 这份文档怎么用

- **快速了解项目**：看第 1、3 节。
- **讲一次完整对话**：看第 4 节（九幕流程，背下来基本就能撑起 5 分钟项目陈述）。
- **应对追问**：第 5、6、7、10 节是"深挖弹药库"，每节都带面试官视角的问题。
- **现场演示**：第 12 节有可直接照做的 demo 脚本与预期结果。

---

# 1. 项目一句话与核心卖点

**PitWall Agent 是一个面向 Formula 1 的可解释 AI Agent 全栈项目**：单 Agent、多工具架构，整合实时赛况、新闻、FIA 法规 RAG、策略分析与多轮会话记忆，把"路由、工具调用、检索证据、流式生成、失败降级"全部暴露为**可测试的工程契约**。

四个最值得讲的点（对应简历四个 bullet）：

1. **统一 LangGraph 运行时**：结构化规划（deterministic JSON plan + ReAct 裁判）与原生 tool calling（LLM 自主选工具）两种模式跑在同一张状态图上，`AGENT_PLANNER_MODE` 一行切换，模型失败可在图内自动回退。
2. **ReAct 正向推理循环**：工具执行后由 LLM 裁判观察结果，失败/证据不足/结果不完整时给出修复计划重规划，循环有预算上限，耗尽后强制总结兜底。
3. **Clause-aware RAG**：FIA 法规 PDF 结构化解析 → 条款级切块 → hybrid 检索（BM25 + BGE-M3 + pgvector + RRF + 交叉编码器重排 + keyword guardrail），无答案强证据拒绝。
4. **工程可观测性**：SSE 真实流式、结构化日志、Prometheus 指标、trace 面板、Redis 多轮会话 + 语义记忆，66 条 golden cases 离线门禁。

---

# 2. 架构演进：为什么从"双路径"走向"统一运行时"

## 2.1 旧架构（≤ 8c20a12）的痛点

重构前有两条**相互独立**的路径：

```text
manual 路径：      LangGraphAgentRuntime（classify → plan → execute → judge）
function_calling 路径： FunctionCallingAgent（自持 while 循环，不接 LangGraph）
```

三个痛点：

1. **行为不一致**：两条路径各自维护循环、上限、trace 语义，同样的"循环耗尽"在 manual 下是 `judge` 兜底、在 function_calling 下是"未能生成回答"，契约分裂。
2. **回退是"逃逸"**：function_calling 失败要跳出循环，在 `AgentService` 层 try/except 切 manual——回退动作发生在**图外**，trace 里看不到原因。
3. **循环耗尽无产出**：LLM 在 3 轮里反复调工具却不给最终回答时，直接返回"未能生成回答"，用户体验断裂。

## 2.2 新架构的答案

```text
单一 LangGraphAgentRuntime
  ├─ planner_mode=structured   （结构化规划 + ReAct 裁判）
  └─ planner_mode=tool_calling （模型原生选工具，默认）
```

- 两张"路径"收敛成一张图上的两种**模式**，共享 `AgentState`、`judge`、`max_steps`、`trace`、会话上层契约（RFC-008 边界"两种模式共享 LangGraph state/Judge/步骤上限/trace"由此实现）。
- 模型调用失败**不再逃逸**，而是图内切换 `planner_mode=structured` 并记录 `planner_fallback="tool_calling_error:..."`。
- 新增 `forced_summary` 节点：循环耗尽后强制 LLM 总结，失败回退最近工具回答。

> **面试一句话版**："我把两条工具调用路径统一进了同一张 LangGraph 图——结构化规划与原生 tool calling 只是同一运行时的两种 planner 模式，共享状态、裁判、预算和 trace；模型失败在图内降级而不是逃逸到外部，循环耗尽有强制总结兜底。"

---

# 3. 新架构全景

## 3.1 一图流

```text
                           ┌─ structured ─→ structured_plan ─┐
START → initialize ───────┤                                  ├→ tool_batch → normalize_observation → judge
                           └─ tool_calling ─→ model ─────────┘                                      │
                                                                                                    │
    model 无工具调用 ─→ finalize ◀── judge ──┬─ tool_batch（继续执行/修复计划）                       │
    max_steps_reached ─→ forced_summary → finalize │
                                              ├─ structured_plan（修复计划重规划）
                                              ├─ model（tool_calling 观察后再推理）
                                              └─ finalize（完成）
```

（源码：`app/agents/runtime_graph.py:141 _build_graph`）

## 3.2 节点职责表

| 节点 | 职责 | 源码位置 |
|---|---|---|
| `initialize` | 组装 `[system, user]` messages，按 `planner_mode` 分流 | `runtime_graph.py:186` |
| `model` | **一次**原生 tool calling（`ToolCallingModelAdapter.invoke`）；异常→图内切 structured | `runtime_graph.py:212` |
| `structured_plan` | 结构化规划：`planner.plan` 出 JSON 计划（支持 `$ref` 数据传递），单步→统一 step 结构 | `runtime_graph.py:261` |
| `tool_batch` | 批量执行工具；tool_calling 模式单轮最多 5 个并行；非法参数不 dispatch、直接记失败 | `runtime_graph.py:306` |
| `normalize_observation` | 多工具结果合并 citations / retrieved_chunks / evidence_count | `runtime_graph.py:380` |
| `judge` | ReAct 裁判：失败 / 证据不足 / general 成功 → LLM 决定继续或终止 | `runtime_graph.py:405` |
| `forced_summary` | 循环耗尽强制总结；失败回退最近一次工具回答 | `runtime_graph.py:468` |
| `finalize` | 组装最终回答 + trace | `runtime_graph.py:481` |

## 3.3 AgentState：一张状态表两种模式

`AgentState`（`runtime_graph.py:28`）是贯穿全图的**可序列化状态**，关键字段：

| 字段 | 含义 |
|---|---|
| `planner_mode` / `requested_planner_mode` / `planner_fallback` | 实际模式 / 请求模式（trace 用） / 回退原因 |
| `messages` | 与 LLM 往返的完整对话（tool_calling 模式把它当"记忆"回灌） |
| `pending_tool_calls` / `current_batch_plans` | 模型发出的待执行调用 / 规范化后的执行计划 |
| `batch_results` / `step_outputs` | 本批执行结果 / 按 output_key 缓存（供 `$ref` 与结构化多步引用） |
| `step_count` / `max_steps` | 轮次计数 / 上限（`AGENT_REACT_MAX_STEPS=5`） |
| `max_steps_reached` / `finalization_mode` | 是否耗尽 / 最终回答来源（direct/forced_summary/tool_result_fallback/empty_fallback） |
| `judge_reasons` / `steps` | `Annotated[list, operator.add]`——跨节点**累加**（LangGraph 归约），保证 trace 完整 |

> 设计点：`judge_reasons` 与 `steps` 用 `operator.add` 归约，意味着每次节点更新都会追加而不是覆盖——多轮循环的历史在 trace 里全程可查（前端证据面板依赖这个）。

---

# 4. 默认路径 tool_calling 的完整对话流程（九幕）

> 以下为**默认配置**（`AGENT_PLANNER_MODE=tool_calling`）下，用户在网页输入一句话的完整链路。结合 `frontend → /api/chat/stream` 的 SSE 事件逐幕展开。

## 幕 0：前端请求与 SSE 建立

前端 `frontend/services/api.ts` 对 `POST /api/chat/stream` 发送 `{message, session_id}`，后端 `app/api/chat.py:39` 返回 `text/event-stream`。

## 幕 1：会话与记忆组装（`app/services/chat_service.py:95 stream_chat`）

1. `get_or_create_session`：按 `session_id` 从 Redis 取会话，否则新建。
2. yield 三个状态事件：`session_started → status(thinking) → status(routing)`（前端立刻有反馈）。
3. `get_last_intent`：取上一轮 assistant 的 intent 作为本轮意图兜底（支撑追问）。
4. `memory_service.build_context`：拼装注入上下文——会话摘要 + 长时记忆（语义召回）+ 最近 4 轮；超 token 预算按"保住最近轮次 > 摘要 > 长时记忆"裁剪。
5. 用户消息落库，yield `status(retrieving)`、`status(generating)`。
6. 启动后台线程跑 agent，主线程从 queue 取 token 流式转发。

## 幕 2：进入统一运行时（`app/services/agent_service.py:62`）

`AgentService._handle_query` 现在**只做一件事**：调 `runtime.run()`。旧的 `AGENT_TOOL_PROTOCOL` 分支已删除（`agent_service.py` 由 260 行瘦身到 144 行），`function_calling` 的循环逻辑整体下沉进 LangGraph。

## 幕 3：initialize（`runtime_graph.py:186`）

- 写 `messages = [system(SYSTEM_PROMPT), user(message)]`。
- 记录 `requested_planner_mode`、初始化 `pending_tool_calls/current_batch_plans/step_outputs` 等空容器。
- `step_count` 按模式置初值：tool_calling 从 **0**、structured 从 **1**（两种模式的预算语义不同，见第 7 节）。

## 幕 4：model——LLM 自主选工具（`runtime_graph.py:212`）

`ToolCallingModelAdapter.invoke(messages)` 一次调用返回 `ChatCompletionMessage`，三种结果：

| 模型返回 | 行为 |
|---|---|
| 有 `tool_calls`（≤5 个） | 逐个 `tool_call_to_plan` 规范化 → 写 `pending_tool_calls` + `current_batch_plans` → 路由到 `tool_batch` |
| 无 tool_calls、有 content | `model_content=content` → 路由到 `finalize`（直接回答） |
| 调用异常 | 图内降级：`planner_mode=structured`、`planner_fallback="tool_calling_error:..."`、`step_count=1` → 路由到 `structured_plan` |

**这是"LLM 负责选工具"的落点**：14 个动作以 OpenAI function schema 暴露（`function_calling.py:73 build_tool_functions`），工具名/描述/intent 标注齐全，LLM 自己决定调哪个、参数怎么填、是否并行。

## 幕 5：tool_batch——执行（`runtime_graph.py:306`）

- 逐个 plan 执行（`tool_dispatcher.execute_plan`）；tool_calling 模式**同一轮多个 tool_calls 并行执行**。
- 非法参数（JSON 解析失败 / 未知工具名）**不 dispatch**，直接生成 `invalid_tool_result` 记失败（`function_calling.py:172`）——校验与执行解耦，白名单约束在模型输出之后、工具执行之前。
- 结果写 `step_outputs`、`steps`（trace 记录），并回灌 `messages`：
  ```json
  {"role": "tool", "tool_call_id": "...", "content": "{\"success\": true, \"payload\": {...}, \"error\": null}"}
  ```
  （截断 4000 字符，`runtime_graph.py:358`）
- 流式 token 仅 structured 模式透传（`allow_tool_streaming = requested_planner_mode == "structured"`）——因为 tool_calling 下回答由最终模型生成，工具执行阶段不流式。

## 幕 6：normalize_observation（`runtime_graph.py:380`）

并行多工具时，把各结果的 `citations / retrieved_chunks / evidence_count` 合并进顶层 `result`，前端证据抽屉一次性展示。

## 幕 7：judge——裁判观察（`runtime_graph.py:405`）

判定链（详见第 7 节）：

1. 结构化多步还有剩余且成功 → `_continue`，不消耗预算；
2. `step_count >= max_steps` → `max_steps_reached` → `forced_summary`；
3. `_should_judge`（失败 / 结果不完整 / general 成功）→ `reflector.judge`（LLM 裁判）；
4. 否则 tool_calling 模式默认 `continue`（继续让模型观察再推理）、structured 模式 `no_judge_needed`。

## 幕 8：forced_summary / finalize（`runtime_graph.py:468, 481`）

- `max_steps_reached` → `forced_summary`：追加"不要调工具、只用已有结果回答、≤350 字"的 user 消息（`ToolCallingModelAdapter.summarize`）；失败回退 `last_tool_answer`（最近一个含明确回答字段的成功工具结果）。
- `finalize`：结构化模式走 `response_formatter.build`；tool_calling 模式用 `model_content` 或强制总结结果。最终 `on_token(final_answer)`（工具结果为非流式时一次性吐给前端，前端按 chunk 展示）。
- 组装 trace（`_build_trace`，`:530`）：`runtime / planner_mode / planner_fallback / judge_outcome / max_steps_reached / finalization_mode / intent / tool_name / steps / plan ...`。

## 幕 9：回写会话与记忆（`chat_service.py:207-215`）

append assistant 历史 → 触发上下文压缩检查 → 刷新记忆 trace → `memory_service.record_interaction`（提取偏好存长时记忆）→ yield `message_completed`（完整 ChatResponse）。

---

# 5. 两种 planner 模式深度对比

## 5.1 structured 模式（确定性底座）

```text
initialize → structured_plan（planner.plan 出 JSON 计划）→ tool_batch → judge
                                                                  ├→ _continue 走下一步（不耗预算）
                                                                  ├→ next_plan 修复计划（耗预算）
                                                                  └→ 完成 → finalize
```

- `LLMQueryPlanner.plan` 先启发式路由（`IntentRouter.route` + `ToolDispatcher.build_plan`），仅 general / 复合意图时调 LLM 出 JSON；失败静默回退启发式。
- 计划支持 **2-4 步依赖链**：`{steps: [{intent, action, params, output_key}]}`，后续步骤用 `$ref:<output_key>.<field_path>` 引用前序输出（`tool_dispatcher.py:16 interpolate_params`）。
- 多步计划的"计划内步骤"**不消耗** `max_steps` 预算，只有裁判修复轮次消耗（`runtime_graph.py:441-446`）——预算语义精确。

## 5.2 tool_calling 模式（LLM 自主编排，默认）

- 模型每轮自主决定：调哪些工具（≤5 并行）、参数、是否停止并回答。
- 工具结果回灌后**下一轮模型能看到全部历史**，支持"观察后再推理"。
- 预算：`step_count` 每执行一批工具 +1，达上限走强制总结。

## 5.3 对比表

| 维度 | structured | tool_calling |
|---|---|---|
| 规划确定性 | 高：JSON 计划 + 白名单校验，非法回退启发式 | 低：LLM 自主，行为随模型漂移 |
| 离线评测 | golden eval 全离线（66 cases） | 需 LLM key，模型间不可复现 |
| 多工具并行 | 需 planner 显式编排（依赖链串行） | 原生支持单轮多 tool_calls |
| 参数生成 | 规则 + LLM JSON，白名单约束 | LLM 自由生成，需 schema 约束 |
| 失败修复 | reflector 结构化 observation + next_plan | LLM 观察 tool 结果自行决定 |
| 成本/延迟 | 可预测（planner + judge 小 token） | 每轮全量上下文回灌，token 更高 |
| 跨域组合 | 需 planner 显式建模 | 天然支持（实测可跨 3 域自主编排） |
| 适用 | 生产稳定路径、离线 CI、无 key 演示 | 开放式多步、探索灵活性（默认） |

## 5.4 图内回退（面试重点）

```python
# runtime_graph.py:212-223 _model_node
except Exception as exc:
    return {
        "planner_mode": "structured",
        "planner_fallback": f"tool_calling_error:{exc.__class__.__name__}",
        "step_count": 1,
        ...
    }
```

模型失败 → **不中断执行**，同一张图内切到结构化规划，`trace.planner_fallback` 记录原因。对比旧架构的图外 try/except，这是"降级可观测"的关键差异。

> **面试一句话版**："我刻意把回退做成图内状态转移而不是外部异常捕获——`planner_fallback` 字段会出现在 trace 里，前端能看到'这次回答是模型失败后降级成的'，可观测性和可测性都比逃逸式回退好。"

---

# 6. 强制总结（forced_summary）：循环耗尽的兜底

**动机**（对应旧架构的真实痛点）：tool_calling 模式下，LLM 可能把轮次全花在调工具上，最终没产出回答，旧代码直接返回"未能生成回答"。

**新设计**（`runtime_graph.py:468 _forced_summary_node`）：

```text
max_steps_reached
  → ToolCallingModelAdapter.summarize(messages)   # 追加"不要调工具，只用已有结果回答"
  → 成功：final_answer = 总结，finalization_mode = "forced_summary"
  → 失败：回退 last_tool_answer，finalization_mode = "tool_result_fallback"
  → 都没有：finalization_mode = "empty_fallback"
```

- summarize 的提示词要点（`function_calling.py:111`）：**"Do not call any more tools. Using only the tool results above, answer the original user question now."** + 长度约束（≤350 中文字符 / 220 英文词）防止截断。
- `last_tool_answer` 在 `tool_batch` 中持续更新（`runtime_graph.py:339-341`，`_extract_tool_answer` 从 `response.answer/final_answer/summary/analysis` 提取）——即使总结失败，也有最近一次有实质内容的工具回答可用。

> 三个 `finalization_mode` 值本身就是测试断言点（`tests/agents/test_function_calling.py` 的 `test_function_calling_forces_summary_after_max_steps` 与 `test_function_calling_uses_tool_answer_when_forced_summary_fails`）。

---

# 7. ReAct 裁判（judge）：触发、决策、预算

## 7.1 触发条件（`runtime_graph.py:405 _judge_node`，按优先级）

| # | 条件 | 结果 |
|---|---|---|
| 1 | 结构化多步还有剩余步骤且当前成功 | `_continue`，**不耗预算** |
| 2 | `step_count >= max_steps` | `max_steps_reached` → forced_summary |
| 3 | `_should_judge`：失败 / 结果不完整 / general 成功（`agent_judge_on_success_general=true`） | 调 `reflector.judge`（LLM 裁判） |
| 4 | 其他成功 | tool_calling：`continue`（继续观察）；structured：`no_judge_needed` |

结果不完整信号（`_result_needs_more_info`，`:583`）：regulation `insufficient_evidence` / fallback 无答案；news 空文章列表（get_article/insights/rules_analysis 例外）；race 无任何数据字段。

## 7.2 裁判决策

`reflector.judge`（`app/agents/reflector.py:57`）把"问题 + 执行计划 + 工具结果摘要"喂给 LLM，返回 `{finish, reason, next_plan}`：

- `finish=true` → 格式化回答；
- `finish=false` + `next_plan` → 图内路由：`_continue` 走 structured_plan 下一步，否则 `current_batch_plans=[修复计划]` 直接回 tool_batch（tool_calling 模式下可回 model 让模型重新观察再推理）。

## 7.3 预算语义（两种模式刻意不同）

- tool_calling：`step_count` 从 0 起，**每批工具执行 +1**；
- structured：`step_count` 从 1 起，**只有裁判的修复轮次 +1**，planner 预定义的多步步骤不消耗。

> **面试点**："为什么两种模式预算语义不同？因为 tool_calling 每轮都是模型自主决策（每轮都可能是'浪费'），structured 的步骤是计划内确定性的（不该为确定性步骤买单），只有修复性重规划才消耗预算。"（`runtime_graph.py:409-446`）

---

# 8. 工具层与领域能力

所有工具实现 `Tool` Protocol（`app/tools/base.py`），返回统一 `ToolResult{tool_name, success, payload, error}`，由 `ToolDispatcher.execute_plan` 分发（`app/agents/tool_dispatcher.py:336`）：

| 工具 | 动作（14 个） | 数据源 | 流式 |
|---|---|---|---|
| `news_tool` | list_recent / search / get_article / get_insights / get_rules_analysis | Formula1.com + Motorsport.com RSS → Postgres | 否（确定性） |
| `race_tool` | list_schedule / get_next_race / get_previous_race / get_race_results / get_driver_standings / get_constructor_standings | Jolpica API + last-good Redis 缓存 + 本地 seed 兜底 | 否（确定性） |
| `regulation_tool` | ask | hybrid RAG（条款级语料） | 是（LLM token 直出） |
| `strategy_tool` | analyze | 自动富化上下文（赛况+规则 RAG+新闻）后 LLM 结构化输出 | 否 |
| `general_tool` | answer | LLM 开放问答，权威数据 guardrail | 是 |

确定性工具（news/race）走 `buffered` 回答模式，LLM 工具（regulation/general）走真实 token 流式——前端 SSE 消费层据此分两种展示路径（`chat_service.py:186` 的 `stream_mode: token | buffered`）。

---

# 9. 会话、记忆与 RAG（架构不变部分，简述）

- **会话**：`SessionService`（Redis `pitwall:session:*` + zset 索引，TTL 7 天）；`ContextCompactionService` 超 20 轮/token 阈值时把旧轮次 LLM 摘要成 `{topic, facts, preferences, open_loops, entities}`，失败确定性回退。
- **长时记忆**：`MemoryService` 从"记住/以后/偏好"等标记提取偏好 → BGE-M3 语义召回（失败词法回退）→ 注入上下文。
- **RAG 链路**：`qa_service.ask` 先 `_classify_query`（fact_lookup / section_overview / document_overview）→ `rule_repository.debug_retrieval`：QueryRewriter（LLM 中→英术语）→ 关键词 BM25 + 向量（pgvector cosine）并行召回 → RRF 融合 → 启发式重排（`evidence_strength`）→ keyword guardrail → bge-reranker-v2-m3 最终重排 → 无强证据 → `partial_evidence`/`insufficient_evidence` 拒绝。基准：Clause Recall@5 100%、无答案拒绝率 100%。

---

# 10. 可测试性：105 个测试与 golden eval

- **单元/集成**：`uv run pytest` → **105 passed**（`tests/agents/` 覆盖 runtime_graph / function_calling / react_loop / reflector / planner / dispatcher / intent_router / response_formatter）。
- 重构后新增的关键测试（`tests/agents/test_function_calling.py`）：
  - `test_function_calling_forces_summary_after_max_steps`：耗尽 → 强制总结，校验 summarize 提示词（"Do not call any more tools" + "350 Chinese characters"）；
  - `test_function_calling_uses_tool_answer_when_forced_summary_fails`：总结失败回退工具回答；
  - `test_tool_calling_model_error_falls_back_inside_langgraph`：模型异常 → 图内切 structured，断言 `planner_fallback=="tool_calling_error:RuntimeError"`；
  - `test_invalid_tool_arguments_are_recorded_without_dispatch`：非法参数不执行工具。
- **离线门禁**：`uv run python scripts/run_agent_eval.py --planner-mode structured`（66 条 golden cases，含 6 条多步链，断言 intent/tool/action/status/evidence/step_sequence）；`--planner-mode tool_calling` 需真实 LLM key，跑同一批 cases 对比。

> 面试点：**"为什么默认是 tool_calling 但 CI 门禁是 structured？"** ——因为 CI 要确定性、要无 key 可跑；tool_calling 的价值在语义灵活性，用真实 LLM 在发布流程里做对比评测，不作为硬门禁。智能增强、确定性兜底，两者不冲突。

---

# 11. 面试高频追问与参考答案

**Q1：工具选择到底是谁负责的？**
三层：规则层（`IntentRouter` + `ToolDispatcher.build_plan`）用关键词和领域白名单定域，零成本可离线测；LLM 层（`LLMQueryPlanner` 或 `ToolCallingModelAdapter`）在白名单内做语义选择与多步规划；裁判层（`ReActReflector`）执行后观察结果、证据不足就换计划重试。LLM 提议、规则约束、裁判复核。

**Q2：为什么默认 tool_calling 而不是 structured？**
因为默认场景是面向用户的真实对话，语义灵活性优先（实测"维修区超速怎么罚"LLM 能自主跨 regulation+news+general 三域取数）。structured 的价值在可测性与无 key 演示，通过 `AGENT_PLANNER_MODE` 一行切换；CI 门禁固定用 structured 保证确定性。

**Q3：tool_calling 模型失败怎么办？**
图内降级：`_model_node` 捕获异常 → `planner_mode=structured` + `planner_fallback` 写入 trace → 同一张图继续走结构化规划。对比旧架构图外 try/except，降级原因可观测。

**Q4：LLM 一直在调工具不给答案怎么办？**
`forced_summary`：达 `max_steps` 后追加"禁止再调工具、只用已有结果回答"的总结请求；总结失败回退最近一次有实质内容的工具回答；再不行 `empty_fallback`。三个 `finalization_mode` 都有测试锁定。

**Q5：裁判（judge）会不会造成死循环？**
不会。`max_steps`（默认 5）硬上限，达上限强制走 forced_summary→finalize；且结构化多步的确定性步骤不消耗预算、只有修复轮次消耗，预算语义精确。

**Q6：为什么流式 token 只在 structured 透传给工具？**
tool_calling 下回答由最终模型生成（工具执行阶段没有可流式的内容）；structured 下 regulation/general 工具内部直接流式（`_on_token` 贯穿到 `LLMClient.stream_chat`）。前端消费层用 `stream_mode` 区分真实流式与 buffered。

**Q7：这个项目是不是套壳调 API？**
不是。调优与工程在：Clause-aware RAG（PDF 结构化解析、条款级切块、hybrid 检索五段管线、强证据门禁）、统一 LangGraph 运行时的双 planner 模式与图内降级、ReAct 裁判与预算控制、Redis 会话压缩与语义记忆、可测试的 golden eval 门禁——这些都不是模型能力，是系统设计。

**Q8：两条 planner 模式共享什么、不共享什么？**
共享：LangGraph state、judge 节点、max_steps、trace 契约、ToolDispatcher 与全部领域服务、会话上层。不共享：规划方式（JSON 计划 vs 原生 tool_calls）、工具结果回灌格式（step_outputs vs tool role messages）、预算递增语义。

---

# 12. 现场演示脚本（带预期结果）

```bash
# 前置：docker compose up -d --build（或 up -d backend + 本地前端 dev server）
# 当前模式：tool_calling（默认）
```

| 演示 | 问题 | 预期（实测结果） |
|---|---|---|
| 流式法规问答 | `维修区超速会怎么处罚` | 真实 token 流式输出，引用 B1.6.3，trace 可见 steps 与 citations |
| LLM 自主编排（跨域） | `维修区超速会怎么处罚` | 实测 5 步：regulation ask×2 → general → news search → regulation ask，跨 3 域取数 |
| 无答案拒绝 | `外星人参加F1比赛会被处罚吗` | 诚实回答规则未禁非人类，不编造条款 |
| 知识型提问 | `维斯塔潘是谁` | general answer + 主动补拉实时积分（steps 含 race_tool） |
| 切结构化对照 | `AGENT_PLANNER_MODE=structured` 后重启 | 同一问题走 JSON 计划 + ReAct 裁判，trace 无 planner_fallback |

```bash
# 验证命令
curl http://localhost:8000/health/ready           # {"status":"ok"}
uv run pytest tests/agents/ -q                     # 105 passed
uv run python scripts/run_agent_eval.py --planner-mode structured   # 离线门禁
```

---

# 13. 已知边界与改进方向

- **tool_calling 成本**：每轮仍需模型推理，但不再回灌完整 tool payload。planner 与 Judge 共用 2400 字符上限的确定性结构化 observation；更早批次滚动压缩为同预算的 `Previous tool observations`，完整结果只保留在 state/response/trace/evidence 中。
- **tool 结果截断**：`messages` 回灌截断 4000 字符，长 payload 可能丢细节。
- **judge 依赖 LLM**：裁判输出 JSON 需足够 `max_tokens`（曾实测 160 截断导致 `judge_error`，本项目调至 512）；无 key 时 judge 自动禁用走确定性路径。
- **意图路由已知边界**：纯关键词路由下"维斯塔潘是谁"仍可能被 race 域抢答（`RACE_KEYWORDS` 含人名）；tool_calling 模式下 LLM 可纠正，structured 模式是已知 trade-off。
- **对比评测非 CI 门禁**：tool_calling 行为随模型漂移，需固定模型版本做基线。

---

# 附：与旧架构的迁移速查

| 旧（≤8c20a12） | 新（42fa3a5+） |
|---|---|
| `AGENT_TOOL_PROTOCOL=manual\|function_calling` | `AGENT_PLANNER_MODE=structured\|tool_calling`（默认 tool_calling） |
| `FunctionCallingAgent.run()` 独立循环 | `ToolCallingModelAdapter`（单次调用）+ LangGraph 编排 |
| `AgentService` 图外 try/except 回退 | `_model_node` 图内降级，`planner_fallback` 进 trace |
| 循环耗尽 → "未能生成回答" | `forced_summary` → summarize / tool_result_fallback / empty_fallback |
| 两套 trace 契约 | 统一：runtime / planner_mode / finalization_mode / max_steps_reached |
| eval `--protocol` | eval `--planner-mode` |
