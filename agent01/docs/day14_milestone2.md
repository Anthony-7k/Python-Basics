# Day 14｜Redis 缓存与里程碑二验收

日期：2026-08-19

## 1. 已完成的开发内容

- Redis 检索结果缓存使用 TTL，并以 JSON 保存可还原的数据结构。
- 缓存键包含知识库 ID、知识库版本、Embedding 模型、Top-K、距离阈值和规范化问题哈希。
- Redis GET/SET 异常会降级为 cache miss，不阻断 Chroma 检索与 RAG 回答。
- 文档首次索引成功、删除、重建请求和重建成功都会推进知识库版本。
- `POST /api/v1/chat` 返回 `cache_hit`、`cache_lookup_ms`、`retrieval_ms` 和 `latency_ms`。
- 新增可配置的检索距离阈值 `RAG_RETRIEVAL_MAX_DISTANCE`，默认值为 `1.1`。
- 全量自动化测试：`81 passed, 1 warning`。
- MySQL 迁移版本：`b7e1c4d9a2f0 (head)`。

## 2. Day14 遇到的开发困难与解决办法

### 2.1 本机没有 Redis，也没有 Docker

最初无法获得真实 Redis 冷、热性能数据。检查发现 Windows 的 6379 端口没有服务，同时本机没有可用的 Docker Desktop 或原生 Redis。

解决办法：

1. 启用 WSL2 并安装 Ubuntu。
2. 在 Ubuntu 中安装 `redis-server` 和 `redis-tools`。
3. 使用 `sudo service redis-server start` 启动服务。
4. 先用 `redis-cli ping` 确认返回 `PONG`，再从 Windows 项目的 Python Redis 客户端验证 `redis://localhost:6379/0` 可访问。

经验：测试跨系统依赖时，必须同时验证服务内部连通性和应用实际使用的连接地址，不能只看到 Linux 内的 `PONG` 就结束。

### 2.2 WSL Ubuntu 安装受到网络和代理影响

使用 `wsl --install --web-download -d Ubuntu` 时曾出现：

```text
Wsl/InstallDistro/WININET_E_CANNOT_CONNECT
```

系统还提示检测到 Windows 的 localhost 代理，但该代理没有镜像到 WSL NAT 模式。

解决办法：完成 WSL 组件安装并重启 Windows 后，改用：

```powershell
wsl --install -d Ubuntu
```

系统随后成功安装并初始化 Ubuntu。localhost 代理提示没有影响本次本地 Redis 访问，但如果以后需要 WSL 访问代理网络，应单独配置 WSL 网络或代理地址。

### 2.3 向量已经召回，但被距离阈值误过滤

首次 Swagger 问答返回“知识库中没有足够的信息”，容易误以为文档没有入库或 Redis 缓存异常。进一步检查发现：

- 文档状态为 `ready`。
- Chroma 能召回包含“每晚 880 元”的正确 chunk。
- 实际 distance 为 `1.0459201335906982`。
- 当时硬编码的 `max_distance` 为 `0.98`。

因此，正确结果在召回后被阈值过滤。

解决办法：把距离阈值改为配置项：

```text
RAG_RETRIEVAL_MAX_DISTANCE=1.1
```

同时保留 `max_distance` 作为缓存键的一部分。阈值变化后会自然生成新缓存键，不会继续命中旧阈值下缓存的空结果。

经验：排查“没有答案”时，应依次检查文档状态、向量召回原始结果、distance 和业务过滤条件，不能直接把问题归因于模型或缓存。

### 2.4 重建后第一次截图显示 cache hit，造成版本失效误判

知识库从 version `2` 重建到 version `4` 后，截图显示 `cache_hit=true`。这看起来像旧缓存跨版本命中。

只读检查 Redis 后发现当前键明确包含 version `4`：

```text
rag:retrieval:v1:{knowledge_base_id}:4:...
```

说明它命中的是 version `4` 下已经建立的新缓存，而不是 version `2` 的旧缓存；Swagger 很可能已经执行过一次相同请求，截图展示的是第二次热请求。

解决办法：再次重建使版本从 `4` 增至 `6`，然后只执行一次相同问题。结果为 `cache_hit=false`、`retrieval_ms=314.82`，证明版本隔离生效。

经验：手工验收缓存时要记录请求次数，并结合实际 Redis key 判断，不应只根据一个 `cache_hit` 字段推断失效逻辑有缺陷。

### 2.5 Swagger 参数前导空格导致 404

删除文档时第一次返回：

```json
{"detail": "Document not found"}
```

请求 URL 中的知识库 ID 前出现 `%20`：

```text
knowledge_base_id=%20e547...
```

`%20` 是前导空格，导致知识库 ID 不匹配。

解决办法：清空参数输入框并重新粘贴不带空格的 ID。修正后接口返回 `200` 和 `status=deleted`。

经验：Swagger 出现意外 404 时，应先检查 Request URL 中是否有 `%20`、换行或其他 URL 编码字符。

### 2.6 Redis 停止后缓存查询变慢，但主流程不能失败

停止 Redis 后，cache lookup 因连接超时增加到约 `409.06 ms`。如果没有降级保护，Redis 异常会使问答接口返回 500。

解决办法：缓存层捕获 Redis GET/SET 异常，将其视为 cache miss，继续执行 Chroma 检索。实测 Redis 连接被拒绝时，Chat 仍返回 HTTP `200`，`cache_hit=false`、`retrieval_ms=315.23`。

经验：缓存属于优化层而不是正确性依赖。连接与 socket 超时必须较短，并且所有缓存异常都应安全回退到实时检索。

## 3. 启动前检查

在项目目录执行：

```powershell
uv run alembic current
uv run pytest
```

推荐的本地开发配置：

```text
REDIS_URL=redis://localhost:6379/0
RAG_CACHE_ENABLED=true
RAG_CACHE_TTL_SECONDS=300
RAG_RETRIEVAL_MAX_DISTANCE=1.1
REDIS_CONNECT_TIMEOUT_SECONDS=0.2
REDIS_SOCKET_TIMEOUT_SECONDS=0.2
```

启动 Redis：

```bash
sudo service redis-server start
redis-cli ping
```

启动 API：

```powershell
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开 Swagger：`http://127.0.0.1:8000/docs`。

## 4. Swagger 端到端验收

### 4.1 创建知识库

调用 `POST /api/v1/knowledge-bases`，新知识库 version 为 `1`。

### 4.2 上传并完成索引

调用 `POST /api/v1/documents?knowledge_base_id={knowledge_base_id}`，再轮询 `GET /api/v1/ingestion/{task_id}` 直到 `succeeded`。首次索引成功后 version 增至 `2`。

### 4.3 冷、热请求性能

连续两次调用 `POST /api/v1/chat`，不传 `conversation_id`，使用完全相同的请求体。

| 请求 | cache_hit | cache_lookup_ms | retrieval_ms | latency_ms | 答案与来源完整 |
| --- | --- | ---: | ---: | ---: | --- |
| 第一次（冷） | false | 13.63 | 1236.60 | 4997.84 | 是，回答 880 元并返回 S1 |
| 第二次（热） | true | 0.94 | 0.00 | 3333.98 | 是，回答 880 元并返回 S1 |

`latency_ms` 还包含 LLM 生成和历史持久化，判断 Redis 是否有效应优先比较 `cache_hit` 与 `retrieval_ms`。

### 4.4 对话历史

调用 `GET /api/v1/conversations/{conversation_id}/messages`，确认用户问题、助手回答和来源摘要完整。

### 4.5 重建索引失效

调用 `POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reindex`。请求和任务成功分别推进一次 version。

实测：知识库 version 从 `2` 增至 `6`；version `6` 下首次相同问题请求为 `cache_hit=false`，`cache_lookup_ms=1.41`、`retrieval_ms=314.82`、`latency_ms=3719.63`。

### 4.6 删除失效

调用 `DELETE /api/v1/documents/{document_id}?knowledge_base_id={knowledge_base_id}`。

实测：

- version 从 `6` 增至 `7`。
- 默认文档列表返回空数组。
- `include_deleted=true` 时能看到 `status=deleted` 的记录。
- 再次提问为 `cache_hit=false`、`sources=[]`、`used_chunk_ids=[]`。
- 回答不再泄露已删除文档中的 880 元信息。

### 4.7 Redis 故障降级

停止 Redis：

```bash
sudo service redis-server stop
redis-cli ping
```

确认连接被拒绝后，使用未查询过的问题调用 Chat。实测 HTTP 仍返回 `200`，`cache_hit=false`、`cache_lookup_ms=409.06`、`retrieval_ms=315.23`、`latency_ms=1148.17`。

验收后恢复 Redis：

```bash
sudo service redis-server start
redis-cli ping
```

最终返回 `PONG`。

## 5. 完成记录

- [x] Redis 实例已启动并通过 PING。
- [x] 冷/热请求结果已填入性能表。
- [x] 上传 → 任务 → 问答 → 历史 → 重建 → 删除流程通过。
- [x] 文档变化后旧缓存不再命中。
- [x] Redis 停止后核心问答仍可用。
- [x] 演示截图已保存，未提交真实企业文档、密钥或缓存数据。
