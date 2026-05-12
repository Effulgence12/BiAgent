# API Key 使用说明

## 是否必须填写 API Key？

不强制。项目不填 API Key 也能运行：DataAnalyst、Visualizer、DecisionMaker 都有本地确定性逻辑，可用于课堂演示、数据校验和调试。

如果希望让 Agent 调用千问/Qwen 大模型润色建议并支持 WebSocket 流式输出，请在 `.env` 或 shell 环境变量中填写：

```bash
ENABLE_LLM=1
QWEN_API_KEY=你的key
# 或使用官方文档常见变量名：DASHSCOPE_API_KEY=你的key
QWEN_MODEL=qwen3.6-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

> 安全提醒：不要把真实 key 写入 Git；不要截图或公开分享 `.env`。

## Qwen 调用方式

项目使用 Qwen Cloud / DashScope 的 OpenAI-compatible Chat Completions 接口：

- Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- Chat path：`/chat/completions`
- Header：`Authorization: Bearer <QWEN_API_KEY 或 DASHSCOPE_API_KEY>`
- 默认模型：`qwen3.6-plus`
- 流式：请求体设置 `stream=true` 与 `stream_options={"include_usage": true}`

为了节省 token，项目只在 `ENABLE_LLM=1` 时调用 Qwen，并且只发送数据摘要和前三行样例给 DecisionMaker，不发送完整结果表。

## 多个智能体用同一个 Key 还是不同 Key？

默认建议使用同一个 Key。多个智能体是同一个应用内的不同角色，主要通过不同 Prompt、状态和工具权限区分职责，而不是通过不同 API Key 区分。

只有以下场景才建议拆分多个 Key：

1. 不同成员需要分摊额度或成本。
2. 不同 Agent 使用不同模型供应商。
3. 需要对 SQL 生成、决策建议等调用分别审计、限流或计费。
4. 生产环境需要安全隔离。

本课程项目阶段推荐先使用单个 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY` 跑通全链路。
