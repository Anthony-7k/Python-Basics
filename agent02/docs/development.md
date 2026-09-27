# 开发环境与质量门禁

## 环境模式

| `APP_ENV` | 自动建表 | 用途 |
| --- | --- | --- |
| `development` | 是 | 本地开发 |
| `test` | 是 | 自动化测试 |
| `integration` | 否 | 集成验证，必须先迁移 |
| `production` | 否 | 发布环境，必须先迁移 |

未知的环境名称会在启动时被拒绝。配置摘要和日志不得包含 API Key、Bearer Token 或数据库密码。

## 本地质量检查

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing --cov-fail-under=90 -q
.\.venv\Scripts\python.exe -m eval.run_eval --dataset eval/datasets/week2.json --output eval/results/week2.json
pnpm --dir web install --frozen-lockfile
pnpm --dir web run build
docker compose config --quiet
# 使用旧版 Compose 时：docker-compose config -q
```

CI 对每次提交执行相同检查，并验证前端生产构建和空数据库迁移。失败测试、覆盖率低于 90%、迁移失败、前端构建失败或确定性评测失败都会阻止合并。

## 健康检查

- `GET /live` 只验证 API 进程存活，不访问外部依赖。
- `GET /ready` 验证数据库连接；依赖不可用时返回 503。
- `GET /api/v1/health` 保留为第一周兼容端点。
