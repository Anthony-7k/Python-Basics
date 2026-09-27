# 安全威胁模型

## 保护对象

保护租户任务、Checkpoint、记忆、审计、知识库内容、模型凭据、agent01 Token 和 JWT。浏览器只持有短期 JWT，不接收模型或知识库凭据。

## 主要威胁与控制

| 威胁 | 控制 | 自动证据 |
| --- | --- | --- |
| 请求体伪造用户或租户 | 身份只从已验证 JWT 构造 | v2 身份测试 |
| 猜测其他租户 task ID | Repository 查询同时匹配 tenant_id | 跨租户 404 测试 |
| viewer 执行或 operator 审批 | RBAC 权限矩阵和拒绝审计 | 角色拒绝测试 |
| 知识内容提示注入 | RAG 输出标记为不可信，不能重新规划或扩大权限 | 提示注入测试 |
| 模型生成未知工具或非法参数 | Registry 白名单和 Pydantic Schema | Provider 与工具测试 |
| 高风险写操作越权 | 执行前 Checkpoint 和 approver/admin 审批 | 审批恢复测试 |
| Token 或密钥进入日志 | 结构化日志按键名和值模式脱敏 | 日志脱敏测试 |
| 生产静默回退样例知识 | integration/production 禁止 agent01 fallback | 运行配置测试 |
| CORS 过宽 | production 禁止 `*` | 运行配置测试 |
| 无限循环或服务占用 | max_steps、超时、有限重试 | 工作流边界测试 |

## 剩余风险

当前版本未包含企业 SSO 管理、密钥轮换服务、分布式任务队列、WAF 和集中式告警。部署到真实企业环境前，应接入外部身份提供商和 Secret Manager，对 Prometheus 端点实施网络访问控制，并完成依赖与镜像漏洞扫描。
