---
name: code_review
description: 在 Review Agent 需要基于题目、会话、用户画像、提交代码和样例运行结果复盘 LeetCode 提交时加载；用于约束正确性判断、复杂度分析、错误 taxonomy、证据要求、JSON 输出和下一步动作。
keywords:
  - 复盘
  - review
  - 代码
  - 提交
  - 错误
  - 复杂度
  - 样例
  - 测试
  - 运行
  - correctness
  - complexity
  - taxonomy
  - passed_sample_tests
  - is_likely_correct
threshold: 1.0
---

# Code Review Skill

## 工作流程

1. 先读取题目、会话、用户画像、提交代码、样例运行结果和调用方给出的错误 taxonomy。
2. 优先分析样例运行结果；样例失败时，以失败样例作为最高优先级证据。
3. 再检查返回格式、边界条件、状态定义、状态转移、循环条件和复杂度。
4. 每个错误只在有代码、思路或样例证据时输出，避免泛泛猜测。
5. 最后生成用户下一步能直接执行的修正动作。

## 判断规则

- 只输出中文 JSON，不输出 Markdown。
- `is_likely_correct` 只能表示“大概率正确”，不能表示真实判题通过。
- 如果样例运行失败，`passed_sample_tests` 必须是 `false`，`is_likely_correct` 必须是 `false`。
- 如果没有真实 LeetCode 判题结果，不得声称“已通过”或“必然正确”。
- 复杂度判断必须和代码结构一致；不确定时用保守表述，例如“需要进一步分析”。
- 错误类型 `type` 必须从调用方提供的 taxonomy 中选择，不得创造新类型。
- 每个错误必须包含能对应到代码、思路或样例运行结果的 `evidence`。

## 输出契约

JSON 必须包含：

- `is_likely_correct`：布尔值，只表示当前证据下的大概率判断。
- `passed_sample_tests`：布尔值，必须与样例运行结果一致。
- `time_complexity`：复杂度字符串或保守说明。
- `space_complexity`：复杂度字符串或保守说明。
- `mistakes`：错误数组；每项包含 `type`、`topic`、`severity`、`evidence`。
- `feedback`：一段中文复盘，先说最关键问题。
- `next_actions`：用户下一步能执行的具体动作数组。

## 复盘优先级

1. 运行时错误、返回格式错误、样例失败和边界条件错误。
2. 算法状态定义、状态转移、循环条件或 visited 处理错误。
3. 时间或空间复杂度不符合题目预期。
4. 可读性、局部重构和风格建议。

## 质量门槛

- 不因为代码风格问题掩盖 correctness、边界条件或复杂度问题。
- 不输出没有证据的错误；证据不足时在 `feedback` 中说明需要补充样例或上下文。
- `next_actions` 必须是用户下一步能执行的具体动作。
- 如果代码为空或无法解析，先指出输入问题，再给最小可执行补救步骤。
