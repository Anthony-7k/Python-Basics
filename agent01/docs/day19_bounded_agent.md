# Day19｜有限 Agent：检索、总结与对比

## 1. 为什么采用有限路由

Day19 的目标是让系统选择受控行动，而不是把稳定 RAG 改造成开放式循环。
当前 Agent 每次请求生成一个确定性工具调用；程序仍然控制工具白名单、资源
范围、授权、步数、超时和总预算。文档证据不会参与工具选择，因此文档中的
“调用 Shell”或“访问其他知识库”等文字只能作为不可信数据。

## 2. 契约与组件

- `AgentRequest`：一个知识库、用户指令和最多两个文档 ID。
- `ToolCall`：调用 ID、白名单工具名、静态选择理由和待校验参数。
- `ToolResult`：成功/失败状态、耗时、安全结果摘要、输出或结构化错误。
- `DeterministicAgentRouter`：识别普通问答、总结、对比和不支持的危险操作。
- `ToolRegistry`：只注册三个工具，并使用各自 Pydantic schema 验证参数。
- `BoundedAgentService`：执行步数、单工具超时、总预算、失败即停和轨迹日志。

三个工具：

1. `search_knowledge` 先校验知识库所有者，再复用现有 RAG 回答与来源结构。
2. `summarize_document` 校验知识库和目标文档，读取该文档的有限索引 Chunk。
3. `compare_documents` 对左右文档分别执行同样的文档与知识库校验，再进行对比。

## 3. 安全与可靠性边界

- 工具参数中的 `knowledge_base_id` 必须与请求允许范围完全一致。
- 工具执行时仍调用 `AccessControlService`/`DocumentService`，不信任路由结果。
- 未知工具、空参数、重复文档、跨库参数和未完成入库的文档返回结构化错误。
- 失败、超时或达到总预算后立即停止，不重试，不进入 ReAct 无限循环。
- 工具线程使用独立 SQLAlchemy Session，避免跨线程共享请求 Session。
- 总结/对比证据采用转义后的显式标签，系统 Prompt 声明证据不可信。
- 轨迹只允许调用元数据和安全摘要进入 JSON 日志，不记录指令、正文或模型输出。
- Agent API 使用现有 Bearer 身份，并以独立 `agent` scope 复用 Chat 次数限制。

## 4. 可重复验收

```bash
uv run pytest -p no:cacheprovider tests/test_agent_router.py \
  tests/test_agent_registry.py tests/test_agent_tools.py tests/test_agent_api.py
uv run python eval/eval_agent_routing.py --min-correct 10
```

路由数据集固定 12 个样例，并逐例报告失败；当前目标不是只打印一个准确率。
测试还覆盖白名单、参数 schema、跨知识库范围、两文档分别授权、超时、最大
步数、Prompt Injection 证据转义和日志不泄露原文。

## 5. 已知限制

- 当前路由是关键词与资源数量驱动，遇到复杂含混意图会要求调用方补充参数。
- 单工具超时会让请求线程停止等待，但底层同步 SDK 调用只能依靠自身超时结束；
  生产环境应使用可取消任务队列或异步客户端。
- 总结与对比只覆盖配置上限内的索引 Chunk，不等同于无限长度文档的完整摘要。
- 当前只支持同一知识库内的两文档对比，不支持跨知识库共享策略。
- 进程内 Agent 限流和线程执行器不适合多实例生产部署。
