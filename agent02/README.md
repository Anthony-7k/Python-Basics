# Enterprise AI Agent Workflow Platform

这是一个面向作品集展示的企业级 AI Agent 工作流平台 MVP。项目用 FastAPI 提供 API，以 LangGraph 显式编排 Agent、Tool、Approval 和 End 节点，并实现多工具、多步骤、Checkpoint、人工审批、受控记忆、MCP、结构化日志和可重复评测。

## 已实现能力

- OpenAI-compatible Function Calling Planner，以及无需 API Key 的确定性规则 Planner。
- Knowledge、Calculator、Search、Calendar、Task 五类工具；Knowledge Tool 可调用 `agent01` 的 `/api/v1/chat`，并保留来源。
- LangGraph StateGraph、Conditional Edge、最大步数和跨工具结果引用。
- PostgreSQL 或 SQLite 持久化任务、步骤、工具调用、Checkpoint 和 Memory。
- HIGH_RISK 写操作在执行前进入 `WAITING_APPROVAL`，支持批准、拒绝和修改参数后批准。
- v2 API 使用 JWT、RBAC、租户隔离和安全审计；请求体不能指定真实身份。
- 有上限的重试、超时、幂等写操作和 Checkpoint 恢复。
- 自建 Enterprise Tools MCP Server 与 stdio Client。
- React TypeScript Web 控制台、SSE 实时轨迹、历史任务和人工审批。
- FlowPilot 工作台：任务搜索与筛选、按工作区保存的会话草稿、表单式审批、失败恢复、结果复制和 Markdown 导出；权限与工作区信息来自已验证身份。
- Prometheus 指标、租户运行摘要、50 条第二周评测和五个固定 Demo。

## 本地启动

需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m app.main
```

默认配置使用本地 SQLite、规则 Planner 和样例知识库，因此无需 API Key 即可运行。Web 控制台为 `http://127.0.0.1:8001/`，Swagger 为 `http://127.0.0.1:8001/docs`。进程存活检查为 `GET /live`，数据库就绪检查为 `GET /ready`；`GET /api/v1/health` 继续作为第一周兼容端点。

集成和生产环境不在应用启动时自动建表，启动前必须运行：

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py
```

## Docker Compose 启动

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose 会启动 API 和 PostgreSQL，并在 API 启动前自动执行 Alembic 升级。不要把 `.env`、数据库密码或 Token 提交到 Git。

如果所在网络无法访问 Docker Hub 的 Python 镜像鉴权服务，可以保持默认 Dockerfile 不变，仅在本次构建时指定缓存镜像：

```powershell
docker-compose build --build-arg BASE_IMAGE=mirror.gcr.io/library/python:3.12-slim api
docker-compose up -d --no-build
```

## 复用 agent01 知识库

先启动相邻目录中的 `agent01`，然后配置：

```dotenv
KNOWLEDGE_BACKEND=agent01
AGENT01_BASE_URL=http://127.0.0.1:8000
AGENT01_BEARER_TOKEN=<agent01 DEMO_AUTH_USERS_JSON 中的 token>
AGENT01_KNOWLEDGE_BASE_ID=<已存在且当前用户有权访问的知识库 ID>
KNOWLEDGE_FALLBACK_TO_SAMPLE=false
```

Docker 内调用宿主机上的 `agent01` 时，使用 `http://host.docker.internal:8000`。Tool 返回的 RAG 内容统一标记为不可信数据，不能改变 Agent 的系统规则。

## 核心 API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/live` | 进程存活检查，不访问数据库 |
| GET | `/ready` | 数据库与必要依赖就绪检查 |
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/agent/chat` | 提交任务并运行 Agent |
| GET | `/api/v1/tasks/{task_id}?user_id=...` | 查询任务状态 |
| POST | `/api/v1/tasks/{task_id}/approve` | 批准或修改后批准 |
| POST | `/api/v1/tasks/{task_id}/reject` | 拒绝高风险操作 |
| POST | `/api/v1/tasks/{task_id}/resume` | 从最近 Checkpoint 恢复失败任务 |

v1 只在 `development` 和 `test` 环境启用，用于第一周回归。集成与生产使用经过身份认证的 v2 API，完整接口见 [API v2](docs/api-v2.md)。

示例请求：

```powershell
$body = @{
  message = "查询上海差旅标准并计算 3 天最高报销金额"
  user_id = "demo-user"
  session_id = "demo-session"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/v1/agent/chat -ContentType application/json -Body $body
```

## 测试 评测与 Demo

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m eval.run_eval --output eval/results/baseline.json
.\.venv\Scripts\python.exe -m eval.run_eval --dataset eval/datasets/week2.json --output eval/results/week2.json
pnpm --dir web install
pnpm --dir web run build
pnpm --dir web test
.\.venv\Scripts\python.exe scripts/week2_acceptance.py
.\.venv\Scripts\python.exe scripts/run_demos.py
```

评测值由运行脚本从逐条 Case 结果计算。规则 Planner 不产生 LLM usage，报告中的 `average_token_usage` 因此是 `null`，而不是伪造的 0。真实模型 20 条测试使用 `eval.run_live_eval`，只有配置真实 API Key 后才执行和出具报告。

## 项目结构

```text
app/
  agent/          LangGraph 工作流和 Planner
  tools/          Tool 接口、Registry、五类工具与 MCP Tool
  api.py          FastAPI 路由
  database.py     SQLAlchemy 数据模型
  repositories.py Checkpoint、任务与记忆持久化
  service.py      任务运行、审批、拒绝和恢复
  observability/  Prometheus 指标
web/              React TypeScript 控制台
eval/             评测数据集与运行器
scripts/          数据库初始化和五个 Demo
migrations/       Alembic 版本化数据库迁移
tests/            单元、集成、API、隔离、安全与 MCP 测试
docs/             架构、工作流、评测和排障说明
```

## 已知边界

- Search、Calendar 和 Task 使用可替换的本地适配器；尚未连接真实企业 SaaS。
- 当前版本没有企业 SSO 管理台、异步任务队列、Redis 集群和生产告警路由。
- development 与 test 保留自动建表；integration 与 production 强制使用 Alembic 迁移。
- OpenAI Planner 的表现与所选模型有关；自动化测试和基线评测固定使用规则 Planner。

更多设计说明见 [架构](docs/architecture.md)、[工作流](docs/agent-workflow.md)、[API v2](docs/api-v2.md)、[安全设计](docs/security.md)、[威胁模型](docs/threat-model.md)、[数据库迁移](docs/migrations.md)、[运维回滚](docs/operations.md)、[演示脚本](docs/demo-script.md)、[开发质量门禁](docs/development.md)、[评测](docs/evaluation.md)和[排障](docs/troubleshooting.md)。
