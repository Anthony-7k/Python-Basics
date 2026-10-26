# 第一、二周 AI 能力补齐记录

日期：2026-10-11。

## 已实现

- RapidOCR + ONNX Runtime CPU 识别真实中文图片；扫描 PDF 按缺少文本的页面触发 OCR，混合 PDF 保留有文本页面的原生解析。
- OCR 原图坐标转换成 PDF 页面坐标，保留识别置信度；单图最多 2000 万像素，PDF 最多 20 页。OCR 失败明确记录为失败，不静默回退到 Fake。
- 可插拔 Ollama 和云端兼容 Chat Completions 抽取。云端使用 HTTPS，密钥在配置中遮蔽；发送内容是文档文本块，不包含用户账号和租户数据。
- 模型返回严格结构，字段名与文档类型必须合法，原始值必须是所引用原文块的子串；拒绝不存在的证据、重复字段、无效金额日期及额外指令字段。金额比较、审批与租户权限仍由后端确定性逻辑负责。
- 模型服务失败有限重试，不使用 Fake 补成功。记录模型名、提示版本、耗时、Token 用量；未配置云端单价时费用为未知，不记为零。
- 抽取 API 增加 `processing_metadata`，可查看每页解析方法及提供方。需迁移至 `20261011_0007`。

## 运行

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ocr]"
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:OCR_BACKEND = "rapidocr"
.\.venv\Scripts\python.exe -m app.main
```

真实模型是显式配置，不会自动调用或收费。选择云端时，在被 Git 忽略的 `.env` 中配置：

```dotenv
OCR_BACKEND=rapidocr
EXTRACTION_BACKEND=cloud
CLOUD_MODEL_BASE_URL=<供应商提供的 HTTPS 兼容 API 基地址，不含 /chat/completions>
CLOUD_MODEL_NAME=<支持 JSON 输出的模型名称>
CLOUD_MODEL_API_KEY=<仅在本机填入>
```

DeepSeek 与阿里云百炼提供兼容接口，但服务地域、模型支持与实际地址以各自控制台为准。切换云端意味着文档文字离开本机，请使用虚构或经过授权的数据。当前没有配置真实密钥或发起云端调用。

本机 Ollama 可使用 `EXTRACTION_BACKEND=ollama`，配置 `OLLAMA_MODEL` 与 `OLLAMA_BASE_URL`。本机没有发现 Ollama 安装，模型推理尚未实测。

## 评测

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_document_ai.py --ocr rapidocr
.\.venv\Scripts\python.exe scripts/evaluate_review_rules.py
.\.venv\Scripts\python.exe -m pytest -q
```

`eval/golden.json` 是人工标注的 5 份虚构文档真值，不使用程序抽取结果生成答案。每份增加扫描、2 度倾斜和低分辨率变体，共 20 次测试；文件名不包含业务类型提示。字段精确匹配统计同时惩罚遗漏和额外字段，按输入类型分别计算准确率、Precision、Recall、耗时均值和最近秩 P95。失败样本进入分母；费用未知时保持空值。

`eval/results/document-ai.json` 保留每个样本的预期与实际字段、解析方法、失败类型和耗时。`eval/results/review-rules.json` 使用隔离数据库测试五类风险场景，统计风险 Precision、Recall、F1 和案件完全匹配率，不改动工作台数据。

## 未达到完整验收的部分

本轮实际验证：87 项自动化测试通过，后端总覆盖率 90.89%，前端类型检查和生产构建通过（仍有大包体积提示）。20 次文档合成测试均正确匹配人工标注字段，5 组确定性风险案例全部匹配。扫描图单份平均约 3.04 秒，该值包含首轮模型初始化，不能推广到其他设备。

本地工作台还创建了“真实 OCR 验收 三单扫描图”案件，编号 `a1541e2d-f7f8-40ca-a517-842a7536dcd0`。合同、采购单、发票分别抽取 5、3、5 个字段，均标记为真实 OCR，规则未发现风险；案件保留待人工核对状态，未自动批准。记录位于 `eval/results/live-ocr.json`。

前端抽取面板新增每页解析方式、模型名称、耗时与 Token 用量。模型分数明确提示不是校准后的正确概率，未知费用不显示为零。

这是一组小规模合成基线，各变体来自相同文档，彼此相关，不能代表真实业务准确率。仍需收集经过授权、脱敏、不同版式的独立文档，划分开发/测试集，再补多页、表格、缺失字段、模糊和严重旋转样本。已有五种业务风险场景与异常输出回归不替代真实评测。

云端模型仅通过模拟 HTTP 返回值验证协议、证据校验和失败路径，未完成真实模型质量、延迟及账单验收。OCR 端到端已使用真实模型运行；不同 GPU/CPU 和模型版本的速度不能直接比较。完整第二周目标仍需要云端配置和更广泛独立样本。

接口参考：

- https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/
- https://docs.ollama.com/api/chat
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions
