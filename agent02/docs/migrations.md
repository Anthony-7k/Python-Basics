# 数据库迁移

项目从第二周开始使用 Alembic 管理生产数据库结构。`development` 和 `test` 环境仍可自动建表，方便本地开发与单元测试；`integration` 和 `production` 启动时不会调用 `create_all`。

## 常用命令

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe history
```

`scripts/migrate.py` 会执行两种安全路径：

- 空数据库执行 `alembic upgrade head`。
- 第一周已经由 SQLAlchemy 建表、但没有 `alembic_version` 的数据库，先核对全部表和字段，再无损标记为当前基线。

如果旧数据库缺表或缺字段，脚本会停止并列出差异，不会尝试猜测或覆盖数据。

## 发布流程

1. 备份数据库并记录当前应用版本与 Alembic revision。
2. 在测试库执行升级和应用回归。
3. 在目标环境运行 `python scripts/migrate.py`。
4. 确认 `GET /ready` 返回 200 后再切换流量。

初始迁移支持在全新测试数据库上执行 `downgrade base` 和再次升级，用于验证结构可重建。已有业务数据的生产数据库不自动执行破坏性降级；回滚依赖升级前备份和上一版本应用镜像。
