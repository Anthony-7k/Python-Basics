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

### 4. 测试

```bash
uv run pytest -p no:cacheprovider
```

### 5. Day16 检索模式与评测

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
