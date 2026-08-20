# Day15：Streamlit 前端与演示体验

日期：2026-08-20

## 1. 交付范围

Day15 新增 `frontend/`，页面始终通过 HTTP 调用 FastAPI：

```text
Streamlit 页面
  -> frontend/api_client.py
  -> FastAPI /api/v1/*
  -> 既有 Services / Repositories
```

前端没有导入数据库 Session、Chroma、Retriever、RAG Service 或 LLM Client。

已覆盖：

- 配置并检查 FastAPI 地址。
- 创建、选择和刷新知识库。
- 上传 PDF、DOCX、TXT，并查看入库任务状态。
- 重新加载文档列表，确认后重建索引或删除文档。
- 展示多轮聊天，按知识库保存独立的 `conversation_id` 和消息。
- 清空当前知识库会话，不影响其他知识库会话。
- 以可展开卡片显示来源、文件名、页码、证据片段和 Chunk ID。
- 显示缓存命中、检索耗时、总耗时和 Request ID。
- 将连接失败、超时、HTTP 错误和异常响应转换为可执行的中文提示。

## 2. 启动方式

先启动依赖与 API：

```powershell
wsl -d Ubuntu -- redis-cli ping
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端启动前端：

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
uv run streamlit run frontend/app.py
```

页面默认地址为 `http://localhost:8501`。

## 3. 状态与隔离设计

`frontend/state.py` 维护：

```text
selected_knowledge_base_id
conversation_id
messages
chat_sessions
ingestion_tasks
last_chat_meta
```

`chat_sessions` 和 `ingestion_tasks` 都以 `knowledge_base_id` 为键。切换知识库时，先保存旧知识库的会话，再恢复目标知识库自己的会话；目标知识库没有历史状态时使用空会话，绝不复用其他知识库的 `conversation_id`。

文档列表不依赖前端缓存，每次页面重载都会从 FastAPI 重新读取，因此刷新后仍能恢复服务端保存的文档状态。

## 4. 引用可读性修复

真实 UI 验收发现，旧入库链路把磁盘上传路径写入 Chroma 的 `source` 元数据，引用卡片会暴露完整路径和哈希文件名。

Day15 调整入库流程：后台任务把数据库中的原始 `document.file_name` 传给 Chunk 元数据。重新索引后，Chat 响应和前端卡片显示 `employee_handbook.txt`。前端仍会对意外的完整路径提取 basename，作为旧索引和异常数据的安全降级。

## 5. 自动化测试

新增测试覆盖：

- 知识库列表与文档上传响应解析。
- pending、running、succeeded、failed 入库状态。
- 首次 Chat 保存、后续 Chat 复用 `conversation_id`。
- 连接失败、请求超时、404、422 和异常响应格式。
- 知识库切换不会串用会话，切回时只恢复对应会话。
- 来源字段缺失、无页码和完整路径的安全显示。
- 入库 Chunk 使用原始上传文件名作为引用元数据。

最终全量回归：`108 passed, 1 warning`。warning 仍是既有的 Starlette/httpx TestClient 弃用提示。

## 6. 不依赖 Swagger 的人工验收

已通过 Streamlit 页面完成：

```text
创建 Day15 演示知识库
-> 上传公开员工手册示例并等待入库成功
-> 查看文档列表
-> 确认并提交重新索引
-> 刷新任务到 succeeded
-> 提问年假规则并展开来源
-> 继续追问并复用同一个 conversation_id
-> 重新加载页面后从 FastAPI 恢复文档列表
```

演示知识库使用仓库内的 `data/sample/employee_handbook.txt`，没有提交 `data/uploads/` 中的运行时文件。

## 7. 关键截图

- [聊天就绪与知识库选择](screenshots/day15/chat-ready.png)
- [多轮问答与展开引用](screenshots/day15/chat-citations.png)
- [文档列表、入库成功与确认操作](screenshots/day15/documents.png)

## 8. 已知环境说明

- WSL 内 `redis-cli ping` 返回 `PONG`，但 Windows 到 WSL Redis 的连接仍可能受本机代理/NAT 影响；缓存层会按既有设计安全降级，不阻断问答。
- 浏览器自动化环境未能取得原生文件选择器句柄，因此人工验收使用同一个 FastAPI 上传接口注入公开示例文件；上传请求、MIME、任务解析和错误态由前端 HTTP Client 自动化测试覆盖。
