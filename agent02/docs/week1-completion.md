# 第一周作品集版完成报告

## 交付结论

第一周范围内的企业级 AI Agent 智能工作流平台 MVP 已完成。系统具备可运行的 API、LangGraph 工作流、多工具编排、人工审批、失败恢复、记忆、MCP 集成、结构化日志、自动化评测和容器化配置。

## 阶段完成情况

| 阶段 | 已完成内容 | 达标证据 |
|---|---|---|
| 第 1 天：骨架与契约 | FastAPI 项目、配置、健康检查、统一请求与响应模型、任务状态机 | 健康检查与 API 契约测试通过 |
| 第 2 天：Agent 闭环 | LangGraph 的 agent、tool、approval、finish 节点及条件路由 | 普通对话和工具调用链测试通过 |
| 第 3 天：工具体系 | 知识库、计算器、搜索、日历、任务创建、故障注入工具；超时、重试和结构化错误 | 工具单测、超时和重试测试通过 |
| 第 4 天：记忆与状态 | 短期状态、显式偏好长期记忆、检查点、任务查询 | 会话隔离、敏感信息不入长期记忆测试通过 |
| 第 5 天：审批与恢复 | 高风险任务暂停审批、批准/拒绝、失败后恢复、幂等任务创建 | 审批与故障恢复端到端测试通过 |
| 第 6 天：MCP 与可观测性 | MCP Server/Client、企业制度工具、JSON 日志、请求链路字段和敏感字段脱敏 | MCP 集成与日志安全测试通过 |
| 第 7 天：评测与交付 | 30 条评测集、五个固定演示、Docker/PostgreSQL 配置、使用和排障文档 | 自动评测、演示脚本和 Compose 配置检查通过 |

## 验收结果

- 自动化测试：32 项通过。
- 测试覆盖率：92%。
- 离线评测：30/30 用例通过，任务成功率 100%。
- 工具选择准确率：100%。
- 工具执行成功率：97.06%；该指标包含故障恢复用例中预期发生的一次失败调用。
- 五个固定演示：知识问答、多工具计算、多步骤日期规划、人工审批、失败恢复全部通过。
- HTTP 冒烟测试：健康检查与多工具请求通过。
- 依赖一致性检查：通过。
- Docker Compose 配置解析：通过。

## 实际启动验收

2026-09-04 已实际启动本地 API 并完成以下在线验证：

- `GET /api/v1/health` 返回 `status=ok`、`database=ok`。
- 差旅费用请求完成 `knowledge -> calculator` 工具链，结果为 2250 元。
- 高风险任务从 `WAITING_APPROVAL` 经批准进入 `COMPLETED`。
- 故障注入任务先进入 `FAILED`，再从检查点恢复为 `COMPLETED`，共执行两次尝试。

Docker Desktop 的残留运行时套接字问题已经修复。修复过程只改名备份了临时运行目录，没有删除镜像、卷或项目数据。原目录保存在：

- `C:\Users\26524\AppData\Local\Docker\run.codex-backup-20260904`
- `C:\Users\26524\AppData\Local\Docker\run.codex-backup-20260904-2`
- `C:\Users\26524\AppData\Local\docker-secrets-engine.codex-backup-20260904`

Docker 容器冷启动已经完成并通过以下验收：

- Docker Engine 29.7.2 正常运行。
- `postgres:17-alpine` 与 `agent02-api` 容器均为 `healthy`。
- 容器 API 的健康检查返回 `status=ok`、`database=ok`。
- 容器内多工具链执行 `knowledge -> calculator`，结果为 2250 元。
- 容器内人工审批从 `WAITING_APPROVAL` 进入 `COMPLETED`。
- 重启 API 容器后，任务仍能从 PostgreSQL 查询，证明持久化有效。
- 数据库验收记录为 2 条任务、3 条工具调用、13 个检查点。
- API 结构化日志包含请求、任务、会话、工具、耗时和脱敏后的 Token 字段。

由于当前网络无法连接 Docker Hub 的 Python 镜像鉴权服务，本次从 `mirror.gcr.io` 拉取了同一官方 Python 3.12 slim 镜像，摘要为 `sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`。Dockerfile 仍默认使用 `python:3.12-slim`，同时支持通过 `BASE_IMAGE` 构建参数覆盖镜像源。

## 下一阶段建议

第二周优先接入真实模型和 agent01 知识库服务，再补充登录鉴权、Web 管理界面、生产级 PostgreSQL 迁移、指标看板和部署流水线。
