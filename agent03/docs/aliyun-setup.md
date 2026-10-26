# 阿里云百炼接入

项目已选择阿里云百炼，预设 `qwen-plus`，通过兼容 Chat Completions 接口抽取字段。最终模型可用性以你的账号和地域为准。

## 需要你在本机填写

1. 登录阿里云百炼控制台，创建 API Key。不要将密钥发送到聊天或截图中。
2. 在同一地域、业务空间的调用示例中复制兼容 API 的 Base URL。不要复制带 `/chat/completions` 的完整请求地址。
3. 编辑项目根目录的 `.env`，填入 `CLOUD_MODEL_BASE_URL` 和 `CLOUD_MODEL_API_KEY`。文件已被 Git 忽略。
4. 确认使用云端及可能产生的费用后，将 `EXTRACTION_BACKEND=deterministic` 改为 `EXTRACTION_BACKEND=cloud`。

当前 `.env` 已预设真实 OCR、阿里云服务和模型名称，但没有密钥与地址，云端仍明确关闭。未配置不等于静默回退：一旦启用 cloud，配置不完整会拒绝启动，运行失败会记录任务失败。

阿里云当前文档推荐业务空间专属域名。例如北京地域的格式为：

`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`

请从自己的控制台复制准确地址，不要照抄占位符，也不要混用其他地域的 Key。非思考调用显式发送 `enable_thinking=false`，输出使用 JSON 模式，仍经过本地严格结构与原文证据校验。

## 检查和验收

```powershell
.\.venv\Scripts\python.exe scripts/check_cloud_config.py
```

此命令只检查本地配置，不发网络请求、不输出密钥、不产生模型调用费用。

配置完成后需要重启后端。下一步先用一份虚构合同验证调用，再运行 20 次合成文档评测；不要直接上传真实合同。评测会发出多次调用，失败重试也可能产生费用，应先在控制台设置适合自己的用量与账单提醒。

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_document_ai.py --ocr rapidocr --extractor cloud --output eval/results/aliyun-document-ai.json
```

记录字段正确率、失败率、耗时与 Token 用量；当前费用保持未知，账单以阿里云为准。真实调用和质量验收尚未执行。

官方参考：

- https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions
- https://help.aliyun.com/zh/model-studio/qwen-structured-output
