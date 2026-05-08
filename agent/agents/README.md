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

```markdown
---
name: code_review
description: 对 LeetCode 提交代码做基于证据的复盘。
keywords:
  - 复盘
  - 代码
  - 复杂度
threshold: 1.0
---

# Skills

这里写完整 skill 规则。
```

加载顺序固定为：

1. `agent.md`
2. 命中的 `skills.md` 全文
3. 代码中本次 LLM 调用的任务指令

兼容说明：加载器也会识别 `skills.m`，但优先使用 `skills.md`。

如需新增 Agent，在代码调用 `LlmClient.complete_text(...)` 或 `complete_json(...)` 时传入 `agent_name="your_agent"`，并在这里创建同名目录。
