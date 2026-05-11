# API Key 使用说明

## 是否必须填写 API Key？

项目可以先不填 API Key 运行：当前 DataAnalyst、Visualizer、DecisionMaker 都有本地确定性逻辑，用于课堂演示、数据校验和调试。

如果希望让 Agent 真正调用大语言模型生成更自然的 SQL、解释和建议，请在 `.env` 中填写：

```bash
DEEPSEEK_API_KEY=你的key
DEEPSEEK_MODEL=deepseek-chat
```

## 多个智能体用同一个 Key 还是不同 Key？

默认建议使用同一个 Key。多个智能体是同一个应用内的不同角色，主要通过不同 Prompt、状态和工具权限区分职责，而不是通过不同 API Key 区分。

只有以下场景才建议拆分多个 Key：

1. 不同成员需要分摊额度或成本。
2. 不同 Agent 使用不同模型供应商。
3. 需要对 SQL 生成、决策建议等调用分别审计、限流或计费。
4. 生产环境需要安全隔离。

本课程项目阶段推荐先使用单个 `DEEPSEEK_API_KEY` 跑通全链路。
