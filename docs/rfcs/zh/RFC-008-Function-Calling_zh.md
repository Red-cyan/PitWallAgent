# RFC-008：双工具调用协议（manual 规划 vs 原生 function calling）
**项目**：PitWall Agent
**RFC 编号**：RFC-008
**作者**：Red Cyan
**状态**：已通过
**创建日期**：2026-08-08
**最后更新**：2026-08-08

---

# 1. 摘要

本 RFC 说明 PitWall Agent 为何同时保留两条工具调用路径，并给出各自的适用场景、权衡与评测方法：

- **manual 路径**（默认）：`LLMQueryPlanner`（LLM + 启发式双路径）输出 JSON 计划，`ToolDispatcher` 按序执行，`ReActReflector` 在失败/证据不足/结果不完整时重规划。确定性、可离线测试、可逐节点断言。
- **function_calling 路径**：全部 14 个工具动作暴露为 OpenAI-compatible function schema，由 LLM 原生 tool calling 自主决定调用顺序与参数（支持单轮多工具并行、多轮观察再推理）。

两条路径共享同一 `ToolDispatcher` 与领域服务，不复制业务逻辑。

---

# 2. 背景与动机

## 2.1 现状

- manual 路径把"规划"显式建模为 JSON 计划（`{steps: [...]}`），可离线 golden eval 断言工具序列（`expected_steps`）、依赖注入（`$ref`）、重规划行为。
- 面试与生产中最常被问到的对比问题是：**"为什么不用原生 function calling？"** 本 RFC 用可运行的对照实现回答这个问题，而不是停留在口头论证。

## 2.2 目标

- G1：证明两条路径都能跑通同一组 golden cases，量化差异。
- G2：手动路径保持确定性、零 LLM 依赖，进 CI 门禁。
- G3：function_calling 路径验证 LLM 自主工具选择的灵活性（并行调用、自适应参数）。
- G4：文档化"什么时候用哪条路径"的决策规则。

---

# 3. 设计

## 3.1 配置开关

```env
AGENT_PLANNER_MODE=tool_calling   # tool_calling | structured
```

- `structured`：LangGraph 内执行结构化 planner、dispatcher 和 judge。
- `tool_calling`：LangGraph 内执行单次原生工具规划节点；模型失败时在同一张图内回退 `structured`。

## 3.2 工具 schema（`app/agents/function_calling.py`）

`build_tool_functions()` 把 14 个动作映射为 OpenAI function：

```json
{
  "type": "function",
  "function": {
    "name": "ask",
    "description": "[regulation_tool] Answer a question grounded in the FIA regulations (intent: regulation)",
    "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}
  }
}
```

动作名全局唯一（`list_recent`/`search`/`get_article`/...），每个动作描述标注所属工具与 intent，便于 LLM 选择。

## 3.3 调用循环（`LangGraphAgentRuntime`）

```
messages = [system, user]
for step in 1..max_steps:
    reply = llm.chat_tools(messages, tools)          # tool_choice=auto
    if reply.tool_calls:
        messages += [assistant(tool_calls)]          # 原样回灌
        for tc in reply.tool_calls:                  # 支持单轮并行
            result = dispatcher.execute_plan(action, params)
            messages += [tool(tool_call_id, result.payload)]
        continue
    return reply.content                             # 无工具调用 -> 最终回答
```

- 工具结果以 `tool` role 回灌，长度截断 2000 字符（与 reflector observation 同一策略）。
- 每轮可并行多个 tool_calls；多轮循环受 `AGENT_REACT_MAX_STEPS` 限制。达到上限时追加一次不携带 tools 的强制总结请求；若总结失败，则回退到最近一个包含明确回答字段的成功工具结果。
- `LLMClient.chat_tools` 复用同一 OpenAI client 与 metrics/logle。

---

# 4. 权衡对比

| 维度 | structured | tool_calling（默认） |
| --- | --- | --- |
| 规划确定性 | 高：JSON 计划 + 白名单校验，非法计划回退启发式 | 低：LLM 自主，行为随模型变化 |
| 离线评测 | golden eval 全离线（66 cases 六指标 100%） | 需 LLM key，模型间不可复现 |
| 多工具并行 | 需 planner 显式编排（依赖链串行） | 原生支持单轮多 tool_calls |
| 参数生成 | 规则 + LLM JSON，白名单约束 | LLM 自由生成，需 schema 约束 |
| 失败修复 | reflector 结构化 observation + next_plan | LLM 观察 tool 结果自行决定 |
| 成本/延迟 | 可预测（planner + judge 小 token） | 每轮全量上下文回灌，token 更高 |
| 可观测性 | trace 暴露 plan/steps/judge_outcomes | trace 暴露 tool_calls 序列 |
| 适用 | 生产稳定路径、离线演示、CI 门禁 | 探索复杂多步问题、验证灵活性 |

## 4.1 决策规则

- 默认与生产：**manual**——可测、可回滚、行为可预测。
- 需要 LLM 自主编排（如"帮我把诺里斯的新闻整理成规则对照报告"这类开放式多步任务）或验证最新模型能力时：**function_calling**。
- 两条路径共用工具层与领域服务，切换成本只有一行配置。

---

# 5. 评测方法

- `scripts/run_agent_eval.py --planner-mode structured`：离线确定性门禁（默认）。
- `scripts/run_agent_eval.py --planner-mode tool_calling --json-output docs/evals/tool-calling.json`：通过统一 LangGraph runtime 跑同一 66 条 golden cases（需 `LLM_API_KEY`）。
- 对比关注点：同一问题下 function_calling 是否产生等价或更优的工具序列；并行 tool_calls 是否降低轮次；失败场景是否被 LLM 自主修复。

---

# 6. 已知边界

- 两种 planner mode 共享 LangGraph state、Judge、步骤上限、trace 和会话上层契约。
- function_calling 的 tool 结果截断可能丢失长 payload 细节，后续可接入与 reflector 相同的结构化摘要。
- 对比评测结果依赖所选 LLM 与版本，不作为 CI 门禁。
