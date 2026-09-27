# 运行排障

## 应用无法启动

确认使用 Python 3.11 或更高版本，并已执行 `pip install -e ".[dev]"`。如果 `PLANNER_MODE=openai`，必须配置 `LLM_API_KEY`。如果 `KNOWLEDGE_BACKEND=agent01` 且关闭样例回退，必须同时配置 Token 和 Knowledge Base ID。

## agent01 无法连接

先确认 `agent01` 的 `GET /api/v1/health` 可用，再检查 Bearer Token 和知识库权限。宿主机运行 agent01、Docker 运行本项目时，Base URL 通常应使用 `http://host.docker.internal:8000`。

## 任务停在 WAITING_APPROVAL

这是 HIGH_RISK 写操作的预期状态。调用 `/approve` 或 `/reject`。`approve` 可以携带 `modified_payload`，但新参数仍必须通过 Task Tool schema。

## 故障恢复失败

只有 `FAILED` 或 `TIMEOUT` 任务可以调用 `/resume`。检查数据库中是否存在最近 Checkpoint，并确认恢复使用同一 `user_id`。副作用工具必须依赖幂等键，避免恢复时重复写入。
