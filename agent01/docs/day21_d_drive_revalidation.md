# Day21：D 盘重装环境复验（2026-09-03）

## 结论与边界

本机 Docker Desktop 4.89.0 / Engine 29.7.2 已恢复运行，程序与主要 Docker 数据位于 D 盘。当前源码成功构建，API、UI、MySQL、Redis 四服务健康；两轮真实模型主链路及停止/重启后的数据保留验证通过。

首轮是重装后的本地技术复验；随后用户完整关机再开机，另完成下文记录的 Windows 冷启动验收。两者均不是新一次全新克隆验收或生产安全认证。3–5 分钟演示视频、人工口述按用户最新要求暂缓验收；不能据此宣布这些交付项已完成。此前架构、评测、面试材料、发布 Tag 与 clean-clone 记录保留，参见原 runbook。本次未 commit、push、重新打 Tag 或创建 Release。

## 安装、数据与磁盘

| 项目 | 本次核验结果 |
| --- | --- |
| Docker Desktop 安装目录 | `D:\dev\DockerHost\Desktop` |
| Docker 主数据盘 | `D:\dev\DockerHost\Data\disk\docker_data.vhdx` |
| 应用源码 | `D:\AI-Agent-Roadmap-2026\Python-Basics\agent01` |
| 项目数据卷 | `agent01_mysql_data`、`agent01_chroma_data`、`agent01_upload_data` |
| VHDX 文件逻辑长度 | 约 6.83 GiB，不能等同于可回收空间 |
| C / D 盘当前可用空间 | 约 11.83 / 64.63 GiB（即时读数，后续会变化） |

这里统计的是磁盘空间，不是运行内存。C 盘仍保留 Docker 配置、运行日志和回滚备份；“主程序/数据在 D 盘”不代表 C 盘零占用。本次未再次清理卷、旧备份或整个虚拟磁盘。

## 本次修复与可回退记录

1. D 盘二进制已安装，但当前用户卸载登记仍指向旧 C 盘路径，导致启动时找不到 backend。先导出原登记，再将 Docker Desktop 安装目录、卸载命令、图标和版本登记修正到已核验的 D 盘 4.89.0 二进制。未修改防火墙、安全软件或凭据。
2. 遗留运行时 socket 导致 backend 启动失败。确认 Engine 未运行后，仅重命名准确定位的运行时目录，保留回滚副本；没有删除数据库、上传文件或 VHDX。原“安全启动”脚本保留。
3. Docker Hub 授权端点需要 Windows 构建客户端的进程代理。通过本机 `http://127.0.0.1:7890` 验证后，以进程级 `HTTP_PROXY` / `HTTPS_PROXY` 构建成功。原 Dockerfile 及 `# syntax=docker/dockerfile:1.7` 未改动。

登记备份保存在本机私有验收目录的 `docker-install-record-before-20260903.reg`。回滚登记会重新指向旧 C 盘路径，不能在保留 D 盘安装时随意导入。

本次保留的精确运行时备份包括：

- `%LOCALAPPDATA%\Docker\run-stale-verified-20260903-0922`
- `%LOCALAPPDATA%\docker-secrets-engine-stale-verified-20260903-0922`
- 原安全启动脚本创建的带 `stale-safe-launch-20260903-091917` 时间戳的运行时备份。

`BUILDKIT_SYNTAX=dockerfile.v0` 在本机被当作待拉取镜像，不是可用的绕过方案；不要重试该建议。新启动脚本在 `finally` 中精确恢复原有进程环境变量，包括恢复“原本不存在”的变量状态；不改用户或系统全局代理。

## 本次验收结果

| 验收项 | 结果与限制 |
| --- | --- |
| 构建 | Compose 校验与真实镜像构建通过；启动脚本再次缓存构建通过 |
| 四服务 | API / UI / MySQL / Redis 均 healthy |
| 迁移 | Alembic `b7e1c4d9a2f0 (head)` |
| 容器约束 | API / UI 为 `10001:10001`，只读根文件系统，drop ALL，no-new-privileges |
| HTTP | `/health`、`/ready`、UI health 均 200；无凭据访问知识库 API 为 401 |
| 自动测试 | 已构建镜像内 160 passed；离线、临时容器，不挂载真实 `.env` 或业务卷 |
| 语法检查 | 114 个 Python 文件通过编译检查 |
| 路由门槛 | 12/12 |
| 检索门槛 | 离线 hashed-vector：Recall@3 72.5%，MRR 70%，NoAnswer 80% |
| 答案质量门槛 | 历史已保存真实回答的 replay：均分 1.98，五项质量比例均 100%；不是今天新跑完整 50 问真实模型评测 |
| A / B 两轮真实模型 | 各上传 TXT / PDF / DOCX；各 3 个 ready 文档；可回答问题返回报销 30 天及来源，证据不足问题拒答且无来源 |
| 工具、历史与隔离 | 总结、对比、会话 4 条历史、知识库来源隔离通过；重复问题命中缓存 |
| 重启持久化 | `compose stop` 后 `up --no-build --pull never -d --wait`；A/B 各 3 文档、原 4 历史均保留，重问各 5 条有效引用 |
| 网页 | 实际打开 Streamlit，检查连接显示正常，文档管理页 3 个样例均“可用” |
| 日志抽查 | 今日四容器日志 412 行未匹配配置中的密钥/密码值，无 Python traceback / FATAL 标记；不是全面渗透测试 |

只有仓库自带合成 `employee_handbook.txt`、`test.pdf`、`test.docx` 与测试问题在用户明确允许后发送至已配置 DeepSeek 和阿里云模型接口，产生少量 API 用量。未使用个人或企业真实文档。两轮测试数据保留在本机，便于复核。

镜像名称沿用 Compose 的 `agent01:day20`，不是功能退回 Day20；应用源码版本为 1.0.0。实际验收构建 config digest 为 `sha256:fc37fe971d6f12aefae68ef5a9989320a5bee05e8c011012799643324bcd8fb9`。后续缓存构建因 provenance 可产生不同 manifest-list digest，不能只凭该差异判断代码改变。

## 启动与使用

1. 打开原 Docker Desktop“安全启动”快捷方式，等待 Engine 运行。若只需查看程序，不必重新构建。
2. 在项目目录运行：

```powershell
Set-Location 'D:\AI-Agent-Roadmap-2026\Python-Basics\agent01'
.\scripts\Start-Day21.ps1 -SkipBuild
```

代码改变或首次构建时，确保代理监听对应端口，再运行：

```powershell
.\scripts\Start-Day21.ps1 -ProxyUrl 'http://127.0.0.1:7890'
```

脚本不会启动/更改代理软件，也不会更改系统 PowerShell 执行策略。没有该代理时不要照填这个地址；可连外网的环境可省略参数。构建失败会停止流程，不会继续假装启动成功。

网页：<http://127.0.0.1:8501>；API 文档：<http://127.0.0.1:8000/docs>。Compose 现有 8000/8501 端口映射绑定所有主机接口，而 Streamlit 使用演示凭据，不能视为公网生产认证。不要配置端口转发或将演示页面公开；本次没有扩大防火墙或公网访问权限。

## 可追溯证据

以下证据保存在本机私有验收目录 `day21-evidence-20260903`，未提交仓库；仓库内只记录可公开的结论、方法与证据边界。

- `pytest.xml`：160 项测试结果。
- `retrieval.json/.csv/.md`、`answer.json/.csv/.md`：离线检索及历史答案 replay。
- `live.json`：A/B 两轮真实模型、语义检查、缓存及重启后持久化结果。
- `final_checks.json`：HTTP 状态与不含密钥的日志抽查统计。
- `cold_boot.json`：09:51 Windows 启动后的四服务、原文档/会话、原文件哈希与本地向量查询证据。

这些是本机证据，未上传远端。历史文件未覆盖，Day17 / Day18 用户未提交修改未动。README、此记录和 Windows 启动脚本是本次项目交付修改。

## Windows 冷启动验收补充（2026-09-03 10:02，UTC+8）

结论：**通过**。用户确认执行完整关机再开机；系统 `LastBootUpTime` 为 `2026-09-03 09:51:36.5 +08:00`，Kernel-Boot 事件 27 同时记录引导类型 `0x0`，晚于关机前两轮真实模型验收。

- 开机后 Docker 未自动运行，不作为失败条件。本轮验证的是通过既有入口正常启动，不要求开机自启。
- 09:57:55 调用现有 `Start-DockerDesktopSafe.ps1`，09:58:04 启动 D 盘 Docker；Engine 29.7.2 成功就绪，实际 Desktop/backend 进程位于 D 盘，无需本轮修复登记或改配置。
- 安全启动脚本仅把旧运行时目录重命名为 `run-stale-safe-launch-20260903-095804-abf4a8d4` 和 `docker-secrets-engine-stale-safe-launch-20260903-095804-3220ba0f`，原件保留为备份；未删除镜像、业务卷或 VHDX。
- 使用 `Start-Day21.ps1 -SkipBuild` 启动原容器，API、UI、MySQL、Redis 全部 healthy，Alembic 仍为 `b7e1c4d9a2f0 (head)`。没有重新构建、拉取镜像或重建数据卷。
- 对照关机前 `live.json` 的原始 ID：A/B 两知识库各 3 个 ready 文档、各 4 条原会话消息，原答复中的 30 天事实与各 5 条引用保留，引用归属核验通过。
- A/B 各 7 个 Chroma Chunk 仍在。复用已保存向量执行本地索引查询通过；没有向外部服务发送文本或调用 Embedding/LLM。这不是一轮新的真实模型生成测试。
- 两知识库涉及的 TXT/PDF/DOCX 原上传文件逐一 SHA-256 校验通过（内容相同的样例由存储去重，并非 6 份不同物理文件）。
- `/health`、`/ready` 与 UI health 正常，无凭据知识库访问仍为 401；实际网页显示 API 连接正常，A 知识库 3 个样例均“可用”。
- Docker Desktop 4.89.0 的安装登记仍在 `D:\dev\DockerHost\Desktop`；主 VHDX 仍在 `D:\dev\DockerHost\Data\disk\docker_data.vhdx`。

本机私有验收脚本 `day21_cold_boot_verify.py` 将结果另存为 `cold_boot.json`，未覆盖关机前的 `live.json`。此次模型调用次数为 0，未重复执行 160 项全量回归；沿用本日关机前的回归结果。

## 暂缓 / 未重复执行

- 演示视频录制、从头人工复核、3 分钟口述与追问训练：用户明确要求先不验收，保持暂缓，不视为已完成。
- 修复后的 Windows 冷启动：已完成上述本次验收；不代表已证明任意未来升级后的启动行为。
- 备份覆盖恢复与全新 clone：此前有独立记录，本次没有再次执行破坏性恢复或新 clone。
- C 盘旧备份进一步清理：未执行，仍需要逐项确认。
