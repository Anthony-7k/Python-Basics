# 评测方法

`eval/datasets/portfolio_mvp.json` 保留第一周 30 条基线。`eval/datasets/week2.json` 继承基线并扩展到 50 条，新增来源、Schema、恢复、边界和提示注入场景。运行器逐条创建隔离的用户与 Session，并验证最终状态、工具顺序和答案关键字段。

计算指标包括：

- Task Success Rate
- Tool Selection Accuracy
- Tool Execution Success Rate
- Average Steps
- Average Token Usage
- Average Latency

运行命令：

```powershell
.\.venv\Scripts\python.exe -m eval.run_eval --output eval/results/baseline.json
.\.venv\Scripts\python.exe -m eval.run_eval --dataset eval/datasets/week2.json --output eval/results/week2.json
```

规则 Planner 没有 LLM usage，因此 Average Token Usage 输出 `null`。真实 LLM Planner 返回 usage 时才统计 Token，不将缺失值记录为 0。失败 Case 会保留用例 ID、实际状态、实际工具、延迟和错误类型。

真实模型路径使用 20 条独立数据集：

```powershell
$env:PLANNER_MODE="openai"
$env:LLM_API_KEY="<secret>"
.\.venv\Scripts\python.exe -m eval.run_live_eval
```

该测试只在凭据有效时执行；Fake Provider 只验证协议和错误处理，不能生成“真实模型通过”的报告。发布门槛是工具选择准确率不低于 90%。
