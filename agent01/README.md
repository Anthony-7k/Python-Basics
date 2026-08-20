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
