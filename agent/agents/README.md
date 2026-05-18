# Agent 指令目录

本目录按 Claude Code subagents 的组织方式维护项目内子代理。每个子代理是一个独立 Markdown 文件，文件名即代码调用时使用的 `agent_name`。

```text
agents/
  hint.md
  review.md
  _template.md
```

## 文件格式

每个 Agent 文件必须包含 YAML front matter：

```markdown
---
name: hint
description: 在用户解 LeetCode 题卡住、请求提示、澄清题意或需要下一步检查方向时使用。
tools:
  - get_problem
  - search_problem_cache
---

# Hint Agent

这里写角色、职责、边界和工具使用规则。
```

字段约定：

- `name`：Agent 名称，需和 `LlmClient.complete_text(...)` 或 `complete_json(...)` 的 `agent_name` 一致。
- `description`：说明何时使用该 Agent。
- `tools`：声明该 Agent 允许使用的工具；真实工具权限仍由 `src/tools/default_tools.py` 控制。

## Skill 目录

通用或专门技能放在同级 `../skills/<skill-name>/SKILL.md`：

```text
skills/
  leetcode-leveled-hint/
    SKILL.md
  leetcode-code-review/
    SKILL.md
```

`SKILL.md` 必须带 YAML front matter。启动时只读取元数据并常驻内存，用户问题命中相似判断后才加载全文。

加载顺序固定为：

1. `agents/<agent_name>.md`
2. 命中的 `skills/<skill-name>/SKILL.md` 正文
3. 代码中本次 LLM 调用的任务指令

如需新增 Agent，复制 `_template.md`，并在代码调用 `LlmClient.complete_text(...)` 或 `complete_json(...)` 时传入对应 `agent_name`。
