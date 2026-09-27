# 身份、租户与权限

第二周 v2 API 只接受 `Authorization: Bearer <JWT>` 身份。服务端从已验证令牌生成 `UserContext`，请求体中的 `user_id`、`tenant_id` 等伪造字段不会改变真实身份。

## JWT 必需声明

- `iss`：必须等于 `JWT_ISSUER`。
- `aud`：必须包含 `JWT_AUDIENCE`。
- `sub`：用户或服务主体。
- `tenant_id`：企业租户边界。
- `roles`：`viewer`、`operator`、`approver`、`admin` 的数组。
- `exp`：令牌过期时间。
- `jti`：建议提供，用于审计关联。

开发和集成环境可以启用 `POST /api/v2/auth/dev-token`。生产环境必须设置 `ALLOW_DEV_IDENTITY=false`，并替换开发密钥；推荐使用 `RS256` 与 `JWT_PUBLIC_KEY` 或 `JWKS_URL`。

## 权限矩阵

| 操作 | viewer | operator | approver | admin |
| --- | --- | --- | --- | --- |
| 查看本租户任务 | 允许 | 允许 | 允许 | 允许 |
| 创建任务 | 拒绝 | 允许 | 拒绝 | 允许 |
| 恢复失败任务 | 拒绝 | 允许 | 拒绝 | 允许 |
| 批准或拒绝高风险操作 | 拒绝 | 拒绝 | 允许 | 允许 |
| 查看审计事件 | 拒绝 | 拒绝 | 拒绝 | 允许 |
| 查看运行摘要 | 拒绝 | 允许 | 允许 | 允许 |

所有任务、步骤、工具调用、检查点和记忆记录都保存 `tenant_id`。v2 Repository 查询必须传入租户条件；跨租户任务查询返回 404，避免资源枚举。

## 审计

任务创建、读取、批准、拒绝、恢复以及权限拒绝会保存主体、租户、动作、资源、结果和 `request_id`。审计元数据不得保存完整 JWT、密码、API Key 或知识库 Token。
