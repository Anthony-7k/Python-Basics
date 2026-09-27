# 第二周作品集演示脚本

演示时使用单独的演示租户和开发令牌，不展示 `.env`、JWT、模型密钥或 agent01 Token。完整演示约 8 分钟。

## 1 登录和租户边界

打开控制台，以 `demo-user`、`portfolio-demo` 登录，选择 operator 和 approver。说明真实生产环境由企业身份提供商签发 JWT，请求体不能伪造用户或租户。

## 2 知识问答和来源

提交“查询公司年假制度”。展示 `planning`、`tool_started`、`tool_finished`、`completed` 事件，打开任务详情并指出来源的标题和定位信息。若演示真实 agent01，先确认页面来源标记为 document，而不是 sample。

## 3 多工具任务

提交“查询上海差旅标准并计算 3 天最高报销金额”。展示 Knowledge 和 Calculator 的顺序、跨工具结果引用，以及最终 2250 元结果。

## 4 人工审批

提交“创建任务：周五前提交预算复盘”。任务在工具执行前进入 `WAITING_APPROVAL`。展示原始参数，批准后再读取最终状态；随后再演示一次拒绝。

## 5 故障与恢复

通过 API 或固定 Demo 触发 `failure demo`，展示有限重试、稳定错误类型和 Checkpoint 恢复。说明 SSE 断开不会重复执行任务。

## 6 安全和可观测性

用另一个租户访问已有 task ID，展示统一 404。打开指标摘要，展示最近 24 小时成功率、P95、工具错误和 Token；说明 Prometheus 标签不含租户和用户标识。

## 7 验收证据

展示自动化测试、50 条离线评测、Alembic 空库迁移和 Web 生产构建结果。真实模型与真实 agent01 的报告仅在配置有效凭据并实际执行后展示，不能用 Fake Provider 冒充。
