# Agent01 - LLM Client Demo


## 项目介绍

这是一个基于 Python 的大模型调用测试项目。

第一阶段目标：

- 搭建可复现的 Python 开发环境
- 使用环境变量管理模型配置
- 调用 OpenAI-compatible API
- 实现命令行输入问题并获取模型回复


## 环境要求

- Python 3.11+
- uv
- OpenAI-compatible API


## 项目启动


### 1. 安装依赖

```bash
uv sync
```

### 2. 启动后端

先在 `.env` 配置演示用户。JSON 的 key 是 Bearer Token，value 是用户邮箱；
请使用随机 Token，示例占位符不能用于共享或生产环境：

```bash
DEMO_AUTH_USERS_JSON={"replace-with-random-demo-token":"local-user@agent01.local"}
DEMO_API_KEY=replace-with-random-demo-token
```

除 `/health`、`/ready` 外，所有 `/api/v1/**` 接口都要求：

```text
Authorization: Bearer <token>
```

`DEMO_API_KEY` 供 Streamlit HTTP 客户端发送同一凭证，不会由后端用作用户
映射。不要把真实 Token、模型密钥或 `.env` 提交到 Git。

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. 启动 Day15 Streamlit 前端

另开一个终端：

```bash
uv run streamlit run frontend/app.py
```

前端默认连接 `http://127.0.0.1:8000`。需要连接其他地址时，可在页面左侧修改，或设置：

```bash
API_BASE_URL=http://127.0.0.1:8000
```

Streamlit 只通过 FastAPI HTTP 接口访问知识库、文档、入库任务、聊天和会话历史，不直接连接 MySQL、Chroma、Redis 或模型服务。

### 4. Day18 安全、权限与可靠性

请求 Token 解析为明确用户邮箱，并随 FastAPI 依赖注入知识库、文档和会话
服务。服务层的统一授权组件校验 `knowledge_base_id` 所有者；文档、入库任务、
会话历史和 Chat 都复用该校验。其他用户猜中资源 ID 时也只得到 404，以减少
资源枚举信息。

上传和 Chat 使用按用户、按入口隔离的进程内固定窗口限流：

```bash
RATE_LIMIT_WINDOW_SECONDS=60
UPLOAD_RATE_LIMIT_REQUESTS=10
CHAT_RATE_LIMIT_REQUESTS=30
```

超限返回 429、`Retry-After` 和 `X-Request-ID`。该实现只适合单进程演示：
多 worker、多实例或重启后状态不共享；生产环境应在网关、Redis 或专用限流
服务中统一执行，并增加并发、请求体和成本预算限制。

应用日志使用 JSON 字段白名单，只保留 `request_id`、路由、方法、状态码、
耗时和不可逆 `actor_id` 等元数据。日志不记录 Authorization、API Key、完整
问题/回答、Prompt、文档正文或上传二进制；已配置密钥和常见凭证格式会再次
脱敏。第三方库与基础设施日志仍需独立审计。

RAG Prompt 把 `<knowledge_base_evidence>` 明确标记为不可信数据，禁止文档
修改角色、系统规则、认证、授权或知识库范围。程序侧授权、检索过滤、来源
编号约束和注入回归共同形成分层缓解，但 Prompt Injection 无法被完全消除。

完整威胁、信任边界和生产差距见
`docs/day18_security_threat_model.md`。

### 5. 测试

```bash
uv run pytest -p no:cacheprovider
```

### 6. Day16 检索模式与评测

默认仍使用纯向量检索。可在 `.env` 中切换：

```bash
RAG_RETRIEVAL_MODE=vector  # vector | hybrid | rerank
```

- `vector`：保持原有 Chroma 向量检索和距离过滤行为。
- `hybrid`：从同一知识库的 Chroma Chunk 计算轻量 BM25，并通过 RRF
  与向量候选融合。
- `rerank`：在融合候选上应用本地 `lexical-v1` 词法重排；它不是外部
  cross-encoder，不增加模型费用，但只能强化词面匹配。

运行固定的 13 问检索评测（评测时不经过 Redis 缓存）：

```bash
uv run python eval/eval_retrieval.py
```

结果写入 `eval/results/day16_retrieval_eval.json` 和
`docs/day16_retrieval_quality.md`。关键词分支当前会扫描指定知识库的全部
Chunk，适合本项目 V1 数据量；知识库扩大后应换成持久化稀疏索引。

运行 25 问压力集，生成真实向量失败目录并对比三种模式：

```bash
uv run python eval/eval_retrieval.py \
  --dataset eval/datasets/day16_failure_cases.json \
  --live-embedding \
  --output eval/results/day16_failure_catalog.json \
  --report docs/day16_failure_catalog.md
```

该压力集用于暴露排序失败和信息不足误命中，不作为默认模式的唯一选择依据。
主质量集和压力集应结合阅读。Rerank 的结果还会记录
`rerank_candidate_count`，用于确认重排前实际候选规模。

默认命令使用完全离线的哈希向量，只用于稳定回归和验证融合逻辑，不代表
生产 Embedding 质量。明确确认公开样例可以发送到 `.env` 配置的外部
Embedding 服务后，再运行真实质量评测：

```bash
uv run python eval/eval_retrieval.py --live-embedding
```

### 7. Day17 版本化 RAG 评测

Day17 固定集位于 `eval/datasets/day17_rag_eval_v1.json`，包含 50 题并按
25 个 Dev / 25 个 Holdout 分离。先运行完全离线的检索工程基线：

```bash
uv run python eval/eval_retrieval.py
```

命令同时输出 JSON、CSV 和 Markdown，并计算 Recall@K、MRR、信息不足
准确率、平均延迟和 P95。离线哈希向量不能作为生产质量结论。确认合成员工
手册可以发送到配置的外部 Embedding 服务后，再运行真实评测：

```bash
uv run python eval/eval_retrieval.py --live-embedding --split holdout
```

可用门槛让失败返回非零状态，例如：

```bash
uv run python eval/eval_retrieval.py \
  --modes vector \
  --min-recall-at-k 0.70 \
  --min-mrr 0.65 \
  --min-no-answer-accuracy 0.70
```

回答评测支持实时运行和保存响应重放。实时模式会调用 `.env` 配置的
Embedding 与 LLM，只应对仓库中的合成手册执行：

```bash
uv run python eval/eval_answer.py --live --split holdout --mode vector
```

生成的 `eval/results/day17_answer_eval.json` 本身可以作为无网络重放输入：

```bash
uv run python eval/eval_answer.py \
  --responses-json eval/results/day17_answer_eval.json \
  --min-average-score 1.60 \
  --min-fact-coverage 0.80 \
  --min-fact-consistency 0.90 \
  --min-answer-relevance 0.90 \
  --min-refusal-accuracy 0.70 \
  --min-citation-correctness 0.80
```

完整的 0/1/2 人工评分与独立引用规则见
`docs/day17_evaluation_methodology.md`。CI 运行 10 个无网络核心样本，避免把
模型或网络波动写成确定性单元测试。

### 8. GitHub Actions 离线回归

仓库根目录的 `.github/workflows/agent01-ci.yml` 会在 `main` 分支的
`agent01/**` 发生 Push 或 Pull Request 时自动运行，也支持手动触发。
工作流使用 Python 3.11 和锁定依赖，执行：

- 完整 pytest（包括 10 个 Day17 核心样本与 Day18 安全回归）。
- Python 编译检查。
- Day17 离线 Vector 检索质量门槛。
- 已保存真实响应的回答质量重放门槛。

CI 只使用占位配置，不读取 `.env`，不会调用真实 Embedding、LLM、MySQL
或 Redis。任何测试或门槛失败都会让工作流返回非零状态并在 GitHub 标红。
