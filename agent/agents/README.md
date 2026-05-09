# Agent 指令目录

每个子目录对应一个可被 LLM 调用加载的 Agent。

目录约定：

```text
agents/
  hint/
    agent.md
    skills.md
  review/
    agent.md
    skills.md
  your_agent/
    agent.md
    skills.md
```

`skills.md` 必须带 YAML front matter。启动时只读取这些元数据并常驻内存，用户问题命中相似判断后才加载全文。
`description` 要写清楚触发场景、输入上下文和该 Skill 要约束的工作流；正文保持短而具体，只放 Agent 执行本任务必须遵守的流程、输出契约、质量门槛和兜底策略。

```markdown
---
name: code_review
description: 在 Review Agent 需要基于题目、会话、用户画像、提交代码和样例运行结果复盘 LeetCode 提交时加载；用于约束正确性判断、复杂度分析、错误 taxonomy、证据要求、JSON 输出和下一步动作。
keywords:
  - 复盘
  - 代码
  - 复杂度
  - taxonomy
threshold: 1.0
---

# Code Review Skill

## 工作流程

1. 先读取题目、会话、用户画像、提交代码和样例运行结果。
2. 优先分析样例失败、返回格式、边界条件和复杂度。
3. 每个错误都必须给出代码、思路或样例证据。

## 输出契约

- 只输出中文 JSON，不输出 Markdown。
- 错误类型必须从调用方提供的 taxonomy 中选择。
- 不得声称通过真实 LeetCode 判题，除非输入明确提供判题结果。
```

加载顺序固定为：

1. `agent.md`
2. 命中的 `skills.md` 全文
3. 代码中本次 LLM 调用的任务指令

兼容说明：加载器也会识别 `skills.m`，但优先使用 `skills.md`。

如需新增 Agent，在代码调用 `LlmClient.complete_text(...)` 或 `complete_json(...)` 时传入 `agent_name="your_agent"`，并在这里创建同名目录。
