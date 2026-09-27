# Changelog

## 0.2.0 Week 2

- 引入 Alembic 唯一迁移路径、环境分级和就绪检查。
- 新增 JWT、RBAC、租户隔离、审计和 v2 API。
- 新增可替换模型 Provider、LLM 调用与估算成本记录、SSE 执行事件。
- 收紧 agent01 契约、来源模型、稳定错误和提示注入边界。
- 新增 React TypeScript 控制台、任务历史、轨迹和审批界面。
- 新增 Prometheus 指标、租户运行摘要、50 条评测和自动验收脚本。

已知限制：真实模型和真实 agent01 验收需要外部凭据；Search、Calendar 和 Task 仍是可替换的本地适配器；未实现分布式 Worker。
