# Day20 Docker、可观测性与部署演练

## 1. 部署边界

Compose 启动四个服务：

| 服务 | 用途 | 宿主机端口 | 持久化 |
| --- | --- | --- | --- |
| `api` | FastAPI、迁移、RAG/Agent | `8000` | Chroma、上传文件 |
| `ui` | Streamlit Web UI | `8501` | 无，状态来自 API |
| `mysql` | 用户、知识库、文档元数据、会话和消息 | 不公开 | MySQL 数据目录 |
| `redis` | 可重建的检索缓存 | 不公开 | 无 |

镜像在构建阶段用 `uv.lock` 安装依赖，运行阶段使用 UID `10001` 的
`agent01` 用户。API/UI 根文件系统只读，只有临时目录和明确的数据卷可写。

## 2. 前置条件与配置

- Docker Engine 24+ 或 Docker Desktop。
- Docker Compose v2.24+。
- 建议至少 4 GB 可用内存、2 个 CPU 核心和 10 GB 磁盘。

在 `agent01` 目录复制环境变量示例：

```bash
cp .env.example .env
```

必须替换：

- `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`
- `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`
- `DEMO_AUTH_USERS_JSON` 和与其中 Token 相同的 `DEMO_API_KEY`
- `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`

MySQL 密码请使用足够长的随机字母和数字。Compose 会把它拼入 SQLAlchemy
连接 URL；若使用 `@`、`:`、`/` 等字符，必须先做 URL 编码。`.env`、企业原始
文档、数据库文件、上传目录和 Chroma 目录都不能提交到 Git 或复制进镜像。

可选端口：

```dotenv
API_PORT=8000
UI_PORT=8501
```

## 3. 一键启动与初始化

先做只读配置检查，再构建并启动：

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

MySQL 和 Redis 通过健康检查后，API 会自动运行 `alembic upgrade head`；API
就绪后才启动 UI。首次构建需要下载基础镜像和 Python 依赖。

检查探针：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8501/_stcore/health
```

`/health` 只证明 API 进程可响应。`/ready` 会检查数据库连接、Chroma、上传
目录写入和启用状态下的 Redis；任一必需依赖失败时返回 HTTP 503，响应只给出
失败组件，不返回连接串或异常详情。

## 4. 主链路演练

1. 打开 `http://127.0.0.1:8501`。
2. 创建知识库并记录其 ID。
3. 上传仓库内允许公开演示的合成 TXT/PDF/DOCX，等待入库状态为 `ready`。
4. 完成一次知识问答并检查引用。
5. 完成一次 Agent 总结或双文档对比。
6. 刷新会话，确认历史消息仍可读取。
7. 检查日志中只有请求 ID、路由、状态、耗时和脱敏 Agent 轨迹。

没有可访问的模型或 Embedding API 时，只能验证容器、迁移、健康检查和不调用
模型的管理接口。本项目没有内置模型 mock；部署层验证不能宣称为真实 RAG、
Agent 或模型质量验证。

## 5. 重启与持久化验收

普通停止不会删除命名卷：

```bash
docker compose down
docker compose up -d
docker compose ps
```

重新打开 UI，逐项确认：

- 知识库、文档元数据、会话和消息仍在（MySQL）。
- 已上传原文件仍可用于重新入库（上传卷）。
- 原有文档 Chunk 可检索且引用正常（Chroma 卷）。

`docker compose restart` 和 `docker compose down` 都保留命名卷。
`docker compose down -v` 会删除 MySQL、Chroma 和上传卷，属于数据删除操作，
只能在确认备份和明确需要重置环境时执行。

## 6. 备份

先建立本地备份目录：

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
```

MySQL 使用逻辑备份，密码只在容器内部展开：

```powershell
docker compose exec -T mysql sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' > backups/agent01-mysql.sql
```

为获得一致的 Chroma 和上传快照，短暂停止会写入它们的 API/UI，再归档命名卷：

```powershell
docker compose stop ui api
docker run --rm -v agent01_chroma_data:/data:ro -v "${PWD}/backups:/backup" alpine:3.22 tar -czf /backup/agent01-chroma.tar.gz -C /data .
docker run --rm -v agent01_upload_data:/data:ro -v "${PWD}/backups:/backup" alpine:3.22 tar -czf /backup/agent01-uploads.tar.gz -C /data .
docker compose start api ui
```

备份完成后检查三个文件大小，并将其保存到受控、加密、限制访问且有保留周期的
位置。这些备份包含会话、文档和可能的企业敏感内容，不能提交到 Git。MySQL
保存权限和业务关系；上传卷保存不可从数据库重建的源文件；Chroma 通常可由
上传原件重新入库重建，但重建需要模型、时间和正确的 Embedding 配置。

## 7. 恢复

恢复会覆盖当前业务数据。先停止 API/UI、确认目标环境并再次备份现状。创建空卷
后，用对应归档恢复 Chroma 和上传卷，再启动 MySQL 并导入 SQL：

```powershell
docker compose stop ui api
docker run --rm -v agent01_chroma_data:/data -v "${PWD}/backups:/backup:ro" alpine:3.22 sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* && tar -xzf /backup/agent01-chroma.tar.gz -C /data && chown -R 10001:10001 /data'
docker run --rm -v agent01_upload_data:/data -v "${PWD}/backups:/backup:ro" alpine:3.22 sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* && tar -xzf /backup/agent01-uploads.tar.gz -C /data && chown -R 10001:10001 /data'
Get-Content -Raw backups/agent01-mysql.sql | docker compose exec -T mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
docker compose start api ui
```

恢复后检查 `/ready`，再验证知识库、文档、会话、检索和引用。若源环境与目标环境
的 Embedding 模型或维度不同，不要继续使用旧 Chroma 数据，应保留上传文件和
MySQL 元数据并按受控流程重新入库。

## 8. 日志与故障排查

查看健康状态和最近日志：

```bash
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 ui mysql redis
```

Compose 使用 `local` 日志驱动并限制单文件大小和轮转数量。应用日志仍需检查不含
Bearer Token、API Key、完整问题、完整 Prompt、答案和文档正文。

常见问题：

- 端口占用：修改 `.env` 中的 `API_PORT` 或 `UI_PORT` 后重建服务。
- API 长时间不健康：查看 `docker compose logs api mysql redis`；确认 MySQL
  密码一致、迁移成功、Redis 可达、数据卷可写。
- UI 健康但页面报 API 错误：确认 `api` 为 healthy，并检查 `DEMO_API_KEY`
  与 `DEMO_AUTH_USERS_JSON` 中的 Token 一致。
- 模型网络失败：健康检查可以通过，但问答/入库仍可能失败；核对代理、DNS、
  Base URL、模型名和供应商限流。不要用健康通过替代模型链路验收。
- `permission denied`：不要把宿主机任意目录覆盖挂载到 `/app`；命名卷由镜像中
  的非 root 用户目录初始化。若手工迁移卷，恢复其 UID/GID `10001:10001`。
- 磁盘增长：检查三个命名卷和 Docker 日志；先备份，再按保留策略清理。

## 9. 关闭与验收记录

普通关闭：

```bash
docker compose down
```

验收记录至少包含 Compose 配置检查、镜像构建、四个服务健康状态、主链路结果、
重启后持久化结果、备份文件校验和脱敏日志抽查。不要执行 `down -v`，除非明确
决定删除全部持久数据。
