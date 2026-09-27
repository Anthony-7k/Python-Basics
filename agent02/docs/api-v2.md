# API v2

除开发令牌端点外，以下接口都要求 Bearer JWT。

| 方法 | 路径 | 权限 |
| --- | --- | --- |
| POST | `/api/v2/auth/dev-token` | 仅启用开发身份的非生产环境 |
| POST | `/api/v2/agent/chat` | `task:create` |
| POST | `/api/v2/agent/chat/stream` | `task:create` |
| GET | `/api/v2/tasks` | `task:read` |
| GET | `/api/v2/tasks/{task_id}` | `task:read` |
| POST | `/api/v2/tasks/{task_id}/approve` | `task:approve` |
| POST | `/api/v2/tasks/{task_id}/reject` | `task:approve` |
| POST | `/api/v2/tasks/{task_id}/resume` | `task:resume` |
| GET | `/api/v2/audit-events` | `audit:read` |
| GET | `/api/v2/metrics/summary` | `metrics:read` |

开发环境示例：

```powershell
$token = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v2/auth/dev-token `
  -ContentType application/json `
  -Body '{"subject":"demo-user","tenant_id":"portfolio-demo","roles":["operator"]}'

$headers = @{ Authorization = "Bearer $($token.access_token)" }
$body = @{ message = "查询公司年假制度"; session_id = "demo-session" } |
  ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v2/agent/chat `
  -Headers $headers -ContentType application/json -Body $body
```

v2 请求体只包含业务参数。`request_id` 和 `task_id` 由服务端生成，用户与租户来自 JWT。

流式接口使用标准 SSE，按运行情况发送 `task_created`、`planning`、`tool_started`、`tool_finished`、`approval_required`、`completed` 或 `failed`。每个事件的 `data` 都是 JSON；客户端断开后应通过任务查询接口恢复状态，不应自动重复提交。
