# Day21｜最终评测与验收证据

## 1. 结论

截至 2026-08-28，本地 Python 3.11.9 环境的 160 项测试、Python 编译检查、Day19 Agent 路由门槛、Day17 离线检索门槛和已保存真实响应的回答质量重放均通过。最终 Day21 提交对应的 GitHub Actions 运行 `33164581409` 已成功。

Docker Desktop 4.88.1 上的真实镜像构建、四服务健康、两次端到端主链路、`down/up` 持久化、日志脱敏抽查、三类备份生成/可读性校验及经授权的覆盖式恢复均通过。恢复前创建了独立回滚快照；恢复后 A/B 数据和引用复验通过。

## 2. 2026-08-28 最终离线回归

| 检查 | 结果 | 证据边界 |
| --- | ---: | --- |
| 全量 pytest | 160 passed | 临时 Chroma/Upload、SQLite、Redis 关闭；不调用外部模型 |
| compileall | 通过 | `app`、`frontend`、`eval`、`tests` |
| Agent 路由 | 12/12（100%） | 固定路由数据集，最低门槛 10/12 |
| Vector Recall@3 | 72.50% | 50 题、离线哈希向量，仅用于工程回归 |
| Vector MRR | 70.00% | 同上 |
| 信息不足准确率 | 80.00% | 同上；检索前置过滤，不等于回答拒答 |
| 回答平均分 | 1.98/2 | 对 50 条已保存真实模型响应进行确定性重放 |
| 事实覆盖 / 一致 | 100% / 100% | 保存响应重放 |
| 相关性 / 拒答 / 引用 | 100% / 100% / 100% | 保存响应重放 |

本地最终复跑使用项目 `.venv` 的 Python 3.11.9 和锁定依赖。构建期间将 `pyproject.toml`/`uv.lock` 的失效清华镜像源迁移到官方 PyPI，并以 `uv lock --check` 和容器内 `uv sync --locked` 验证锁文件一致性。

## 3. 真实容器主链路与持久化

| 项目 | Demo A | Demo B |
| --- | ---: | ---: |
| TXT/PDF/DOCX 入库 | 3/3 succeeded、3/3 ready | 3/3 succeeded、3/3 ready |
| 可回答问答 | 5 条引用，含文件名/页码/Chunk | 5 条引用，含文件名/页码/Chunk |
| 信息不足 | 0 条来源，明确拒答 | 0 条来源，明确拒答 |
| 单文档总结 | `summarize_document` succeeded | `summarize_document` succeeded |
| 双文档对比 | `compare_documents` succeeded | `compare_documents` succeeded |
| 历史 | 4 条消息 | 4 条消息 |
| 重启后检索 | 5 条引用，缓存未命中后重建正确 | 5 条引用，缓存未命中后重建正确 |

正式知识库 ID 为 `015cde6c-1046-4fd3-8929-0c6d476e1507` 与 `b4826f70-ebef-45b2-a31f-a57ecd6e0ca7`。`down/up` 后 Upload 卷保留 3 个去重原文件，两个知识库在 Chroma 中各保留 7 个 Chunk；MySQL 元数据、任务、会话和消息均保留。Streamlit 硬刷新会话恢复经过真实浏览器复验。

### 3.1 备份证据

| 文件 | 大小（bytes） | SHA-256 |
| --- | ---: | --- |
| `agent01-chroma.tar.gz` | 164598 | `6a1d3807c0e7a5bf1982936fe0e5bf826325c4d3cdb0c4c747b9443c581b031f` |
| `agent01-mysql.sql` | 21836 | `895b3b6e91b67ba448df1ea94a6221aaa76921a6c7bb3571fb429ed97f88a639` |
| `agent01-uploads.tar.gz` | 86502 | `8c8a000b8e3b90ef086cd2b502ed21a0cb9752a183ca58c680e77191d0c6195e` |

两个 tar 目录可读，MySQL dump 非空。使用该组备份覆盖恢复当前本地三个数据卷后，四服务重新 healthy；A/B 各 3 个文档、原 4 条历史、5 条引用、Upload=3、Chroma 各 7 Chunk 及 Alembic head 全部通过。

离线检索使用 `offline-hashed-token-v1`、Chunk 500/Overlap 50、Top-K 3、最大距离 1.6，50 题全量集。该百分比能证明回归门槛稳定，不能作为生产 Embedding 质量或简历中的模型效果结论。

## 4. 已保存的真实模型评测

真实运行日期为 2026-08-23，数据集为 `employee-handbook-rag-eval/day17-v1`，SHA-256 为 `be756ebc2a689f156e79879e71d6a1fc4539faa5403f884097450135d0da41bf`。共 50 题，其中 Dev 25、Holdout 25；40 题可回答，10 题信息不足。

### 4.1 检索

配置：`text-embedding-v4`，Chunk 500/Overlap 50，Top-K 3，最大距离 1.1，Redis 未参与。

| 模式 | Recall@3 | MRR | 信息不足准确率 | 平均耗时 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vector | 100.00% | 90.00% | 10.00% | 156.17 ms | 262.88 ms |
| Hybrid | 100.00% | 96.25% | 0.00% | 182.21 ms | 423.59 ms |
| Rerank | 100.00% | 97.50% | 0.00% | 180.06 ms | 311.11 ms |

解读：Hybrid/Rerank 改善了首个正确证据的排名，但在当前阈值下把信息不足题的空检索率降为 0%。因此“排序更好”不等于“端到端更可靠”，不能只看 Recall/MRR 选择默认模式。当前默认保留 Vector，并把检索拒答阈值校准列入 Roadmap。

### 4.2 回答与引用

配置：`deepseek-chat` + `text-embedding-v4`，Vector Top-K 5，最大距离 1.1，Prompt `rag-prompt-day14-v1`。报告是对已保存真实响应的重放，不代表今天外部模型服务仍保持同一状态。

| 指标 | 结果 |
| --- | ---: |
| 平均 0/1/2 分 | 1.98 |
| 2 分 / 1 分 / 0 分 | 49 / 1 / 0 |
| 事实覆盖率 | 100.00% |
| 事实一致率 | 100.00% |
| 回答相关率 | 100.00% |
| 拒答准确率 | 100.00% |
| 引用正确率 | 100.00% |
| 平均回答耗时 | 1272.29 ms |
| P95 回答耗时 | 1767.85 ms |

唯一未获 2 分的样例是 `d17-044`。评测使用确定性事实、拒答和来源规则，并保留人工 0/1/2 复核标准；当前未启用 LLM-as-judge。

## 5. CI 与可复现性

GitHub Actions `agent01-ci` 使用 Python 3.11 和 `uv.lock`，执行：

1. `docker compose config --quiet`。
2. 全量 pytest。
3. Python 编译检查。
4. Day19 路由门槛。
5. Day17 离线检索门槛。
6. 已保存真实回答的质量重放门槛。

CI 使用占位配置、内存 SQLite、禁用 Redis 缓存，并把评测输出写入 Runner 临时目录；它不读取 `.env`，也不调用真实 Embedding、LLM、MySQL 或 Redis。

## 6. 发布验收矩阵

| 级别 | 项目 | 状态 | 备注 |
| --- | --- | --- | --- |
| P0 | Docker Compose 配置展开 | 通过 | GitHub Actions 已验证 |
| P0 | 镜像真实构建、四服务 healthy | 通过 | Docker Desktop 4.88.1，四服务 healthy |
| P0 | Alembic 在容器 MySQL 完成迁移 | 通过 | `b7e1c4d9a2f0` head；迁移可重试 |
| P0 | 上传→入库→问答→引用→历史连续两次 | 通过 | A/B 两轮均通过，知识库隔离 |
| P0 | `down/up` 后 MySQL、Chroma、上传原件保留 | 通过 | 未使用 `-v`；重启后引用恢复 |
| P0 | 全量测试、编译、路由、质量门槛 | 通过 | 2026-08-28 本地复跑通过 |
| P1 | 日志无 Token、Prompt、正文和完整问答 | 通过 | 已知密钥与正文短语命中均为 0 |
| P1 | MySQL/Chroma/Upload 备份与恢复 | 通过 | SHA-256、可读性、回滚快照和覆盖恢复复验完成 |
| P1 | README、架构、评测、演示与面试材料一致 | 已整理 | 视频仍需在真实环境录制 |
| P1 | GitHub Actions 最新运行通过 | 通过 | 运行 `33164581409` |

## 7. 简历可引用与不可引用

可以引用：

- 50 题版本化合成评测集，Dev/Holdout 各 25 题。
- 已保存真实模型响应平均 1.98/2，49/50 获 2 分。
- 事实覆盖、一致、相关、拒答与引用正确率在该固定集上均为 100%。
- 160 项自动化测试、12/12 固定 Agent 路由样例。

必须带限定：以上模型质量数据只覆盖该版本化合成员工手册评测集、指定模型和参数，不代表开放域或生产流量。

不能作为生产质量结论：离线哈希向量的 72.50% Recall@3、70.00% MRR、80.00% 信息不足准确率，以及尚未执行的压测与生产监控结果。

## 8. 证据入口

- `docs/day17_evaluation_methodology.md`：数据集、评分与引用规则。
- `docs/day17_retrieval_quality_live.md`：真实 Embedding 检索报告。
- `docs/day17_answer_quality_live.md`：真实回答重放报告。
- `eval/results/day17_answer_responses_live.json`：带模型、Prompt、参数和样例的保存响应。
- `docs/day19_bounded_agent.md`：Agent 安全边界与 12 个路由样例。
- `docs/day20_deployment.md`：Compose、持久化、备份与恢复流程。
