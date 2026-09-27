# 运维与回滚

## 部署前提

生产环境必须设置 `APP_ENV=production`、`ALLOW_DEV_IDENTITY=false`，替换默认 JWT 密钥或配置 `JWKS_URL`，并将 `CORS_ALLOWED_ORIGINS` 限定为实际控制台域名。启用 agent01 时必须提供 Bearer Token 和知识库 ID，且 `KNOWLEDGE_FALLBACK_TO_SAMPLE=false`。

## 启动与检查

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8001/live
Invoke-RestMethod http://127.0.0.1:8001/ready
Invoke-WebRequest http://127.0.0.1:8001/metrics
```

`/live` 只判断进程是否存活；`/ready` 会访问数据库。API 容器启动时先运行 Alembic，再启动服务。Web 控制台由同一个 API 容器托管，因此打开 `http://127.0.0.1:8001/` 即可访问。

## 监控

Prometheus 抓取 `/metrics`。核心指标包括 HTTP 请求量与耗时、任务终态、工具成功率与重试、模型调用量、Token 和估算成本。指标标签不包含租户、用户、任务 ID 或请求文本，避免高基数和敏感数据暴露。

具有 operator、approver 或 admin 角色的用户可调用 `GET /api/v2/metrics/summary`，查看自己租户最近 24 小时的任务成功率、P95、工具错误、Token 和估算成本。

## 数据库升级

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py
.\.venv\Scripts\alembic.exe current
```

部署前备份数据库。当前发布支持向前升级；不自动执行破坏性降级。若应用回滚到上一版本，先回滚应用镜像并保留已经扩展的兼容字段。只有在恢复数据库备份后，才执行会删除列或表的 downgrade。

## 故障处理

- `/live` 正常而 `/ready` 失败：检查数据库连接、凭据和 Alembic head。
- agent01 返回 401 或 403：检查 Token 和知识库授权，不切换到样例数据。
- 模型 429 或超时：查看稳定错误类型、重试次数和 `llm_calls`，不要把密钥写入日志。
- SSE 断开：任务仍在服务端执行；从任务列表重新读取最终状态，避免重复提交。
- 发布后错误率上升：停止新流量，保留数据库，回滚应用镜像，再根据迁移兼容性决定是否恢复备份。
