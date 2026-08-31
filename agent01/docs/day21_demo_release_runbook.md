# Day21｜演示、最终验收与发布 Runbook

## 1. 2026-08-28 与 2026-08-31 验收结果

Docker Desktop 4.88.1 已安装并完成真实验收：四服务 healthy、Alembic head、两轮端到端主链路、`down/up` 持久化、日志脱敏抽查、三类备份生成/可读性校验及经授权的覆盖式恢复均通过。恢复前另建回滚快照；恢复后 A/B 各 3 个 ready 文档、原 4 条历史、5 条引用、Upload 原件和 Chroma Chunk 全部复验通过。验收过程中修复了 MySQL 非事务 DDL 迁移重试和 Streamlit 硬刷新会话恢复两个缺陷。最终 GitHub Actions `33164825390` 已通过；`main` 与 `v1.0.0` Tag 已普通推送，按用户最后指示未创建 GitHub Release。3–5 分钟演示视频暂缓录制和人工复核。

2026-08-31 从远端 `main@0991533` 全新克隆，在 `agent01:day21-cleanclone`、端口 `18000/18501` 和 `agent01_cleanclone_*` 三类独立卷中完成 `--no-cache` 构建。四服务 healthy，`/health`、`/ready`、UI 均返回 200，Alembic 为 `b7e1c4d9a2f0 (head)`，API/UI 均以 UID 10001 运行且根文件系统只读。本地 401 边界、知识库创建/查询、`down/up` 后 MySQL 记录与 Chroma/Upload 哨兵持久化、日志零敏感值/致命错误，以及无网络只读容器内的 160 项测试和全部质量门槛均通过。此次 clean-clone 未在缺少具体数据与模型目的地授权时再次外发样例；8 月 28 日 A/B 两轮真实模型链路不受影响。

## 2. 准备环境

启动 Docker Desktop，然后确认：

```powershell
docker --version
docker compose version
docker info
```

现有 `agent01/.env` 含用户模型配置，禁止用 `.env.example` 覆盖。只手动补入缺少的键，并用随机、URL 安全的字母数字密码/Token 替换占位符：

```dotenv
MYSQL_DATABASE=agent01
MYSQL_USER=agent01
MYSQL_PASSWORD=<random-alphanumeric-password>
MYSQL_ROOT_PASSWORD=<different-random-alphanumeric-password>
API_PORT=8000
UI_PORT=8501
DEMO_AUTH_USERS_JSON={"<random-demo-token>":"<demo-user-email>"}
DEMO_API_KEY=<same-random-demo-token>
```

不要在聊天、截图、终端录屏或 Git diff 中展示 `.env` 内容。

## 3. 构建与健康检查

```powershell
cd D:\AI-Agent-Roadmap-2026\Python-Basics\agent01
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

验收：

- [x] `mysql` healthy。
- [x] `redis` healthy。
- [x] `api` healthy，日志显示 Alembic 迁移成功。
- [x] `ui` healthy。
- [x] `GET http://127.0.0.1:8000/health` 返回 200。
- [x] `GET http://127.0.0.1:8000/ready` 返回 200，数据库、Chroma、上传目录和 Redis 均无失败。
- [x] `GET http://127.0.0.1:8501/_stcore/health` 返回 200。

若构建失败，优先修复锁定依赖、系统库、非 root 写权限和健康检查，不绕过 `user: 10001:10001`、只读根文件系统或持久卷。

## 4. 主链路演示 A

只使用仓库中的公开合成样例：

- `data/sample/employee_handbook.txt`
- `data/sample/test.pdf`
- `data/sample/test.docx`

逐项记录结果、资源 ID 与截图编号；不要把 Token 放进截图。

- [x] 打开 Streamlit，创建“Day21 Demo A”知识库。
- [x] 上传 TXT、PDF、DOCX，记录三个 `task_id`。
- [x] 等待三个任务都进入 `succeeded`，对应文档进入 `ready`。
- [x] 提问可回答问题，核对答案、文件名、页码和 `chunk_id` 引用。
- [x] 提问信息不足问题，确认明确拒答且不伪造引用。
- [x] 运行一次单文档总结。
- [x] 运行一次双文档对比。
- [x] 刷新 UI，确认会话历史仍可读取。
- [x] 保存关键截图：知识库/文档、可追溯引用、历史恢复；Agent 总结/对比由结构化证据记录。

## 5. 主链路演示 B

不要复用第一次的知识库或会话；建立“Day21 Demo B”，完整重复上传、入库、问答、拒答、Agent、引用和历史流程。第二次运行用于排除一次性初始化或缓存造成的假通过。

- [x] 第二个知识库创建成功。
- [x] 三类文档再次入库成功。
- [x] 问答与引用正确。
- [x] 总结/对比路由正确。
- [x] 会话历史刷新后存在。
- [x] 两个知识库之间没有串库。

## 6. 停止/启动后的持久化

```powershell
docker compose down
docker compose up -d
docker compose ps
```

禁止执行 `docker compose down -v`。重新进入 UI 后验证：

- [x] MySQL 中的知识库、文档元数据、入库任务、会话和消息仍存在。
- [x] Upload 卷中的原始文件仍可用于重新入库。
- [x] Chroma 中原有 Chunk 可检索，引用仍映射到正确文档。
- [x] Redis 清空或重建不影响正确性。

## 7. 日志与备份

```powershell
docker compose logs --tail=200 api
docker compose logs --tail=200 ui mysql redis
```

- [x] 不含 Bearer Token、API Key、完整问题、完整 Prompt、完整回答或文档正文。
- [x] 只出现请求 ID、路由、状态、耗时和安全摘要等允许字段。

按 `docs/day20_deployment.md` 生成以下三个备份并记录文件大小与 SHA-256：

- [x] `agent01-mysql.sql`
- [x] `agent01-chroma.tar.gz`
- [x] `agent01-uploads.tar.gz`

备份含企业内容，只能保存到受控位置，不能提交 Git。恢复会覆盖数据；执行任何恢复命令前，必须再次确认目标环境、备份文件和覆盖范围。

- [x] 使用 `20260828-181106` 备份覆盖恢复当前本地 MySQL、Chroma、Upload 数据卷。
- [x] 恢复前创建独立回滚快照。
- [x] 恢复后四服务 healthy，A/B 文档、历史、检索引用和 Alembic head 全部通过。

## 8. 3–5 分钟演示视频脚本

| 时间 | 画面 | 讲述重点 |
| --- | --- | --- |
| 0:00–0:25 | README 标题与架构图 | 企业文档分散、关键词检索弱、通用模型缺少内部证据 |
| 0:25–0:50 | `docker compose ps`、`/ready` | 四服务、真实依赖就绪、非 root 与持久卷；不要展示环境变量 |
| 0:50–1:30 | 创建知识库并上传三类文档 | 任务化入库、文件安全校验、解析/切分/Embedding/Chroma |
| 1:30–2:15 | 一次问答与引用卡片 | 知识库过滤、拒答约束、服务端回填文件/页码/Chunk |
| 2:15–2:45 | 信息不足问题 | 展示不编造答案和不附带虚假来源 |
| 2:45–3:20 | 单文档总结或双文档对比 | 三工具白名单、权限二次校验、步数/超时/预算 |
| 3:20–3:45 | 刷新历史、展示第二知识库 | MySQL 会话持久化与知识库隔离 |
| 3:45–4:20 | 评测表格 | 50 题版本化数据集、1.98/2、49/50 两分、限制与证据边界 |
| 4:20–4:40 | 已知限制 | OCR、可靠队列、精细 RBAC、压测与生产监控 |

视频至少录两遍，选主链路完整、无密钥、无等待卡顿的一版。录制后从头观看，确认字幕、缩放、声音、引用和数字均与仓库一致。

## 9. 最终回归

评测报告必须写到临时目录，避免覆盖用户现有 Day17 文件：

```powershell
uv sync --locked
uv run pytest -p no:cacheprovider
uv run python -m compileall -q app frontend eval tests
uv run python eval/eval_agent_routing.py --min-correct 10
```

再按 `.github/workflows/agent01-ci.yml` 中的命令运行 Day17 检索和回答门槛，并把 `--json-report`、`--csv-report`、`--markdown-report` 指向临时目录。

最后检查：

```powershell
git diff --check
git status --short
git diff --cached --name-only
```

禁止使用 `git add .` 或 `git add -A`。只精确暂存 Day21 文件，并确认没有 `.env`、数据库、备份、向量目录、上传原件或用户已有的 Day17/Day18 工作区内容。

## 10. 发布门槛与命令

只有以下条件全部满足后才考虑发布：

- [x] 两次主链路连续成功。
- [x] `down/up` 后数据与引用恢复。
- [x] 三类备份生成并校验。
- [x] 远端 clean-clone 的无缓存构建、隔离运行、持久化和离线回归通过。
- [x] 全量回归与最新 GitHub Actions 通过（运行 `33164825390`）。
- [x] README、架构、评测、演示文档、面试材料和实际功能一致。
- [ ] 3–5 分钟演示视频已录制并人工复核（按用户指示暂缓，不阻塞其余 Day21 验收）。
- [x] 已向用户报告提交内容、测试结果和所有已知限制。
- [x] `main` 与 `v1.0.0` Tag 已普通推送。
- [x] 按用户最后指示未创建 GitHub Release。

建议提交拆分：

```text
docs: finalize readme architecture and evaluation report
fix: resolve final acceptance issues
release: publish enterprise-knowledge-agent v1.0.0
```

当前仓库版本为 `1.0.0`，`main` 与 `v1.0.0` Tag 已推送。除非用户另行明确要求，不创建 GitHub Release；后续只提交事实修正、Day21 截图和验收证据，不改写既有发布历史。
