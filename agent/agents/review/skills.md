---
name: code_review
description: 对 LeetCode 提交代码做基于证据的复盘，分析正确性、复杂度、错误类型和下一步动作。
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
threshold: 1.0
---

# Skills

回答规则：

- 只输出中文 JSON，不输出 Markdown。
- 错误类型 `type` 必须从调用方提供的 taxonomy 中选择。
- 每个错误必须包含能对应到代码或思路的 `evidence`。
- 复杂度判断必须和代码结构一致，不确定时用保守表述。
- `is_likely_correct` 只能表示“大概率正确”，不能表示真实判题通过。
- `next_actions` 必须是用户下一步能执行的具体动作。

复盘优先级：

1. 运行时错误、返回格式错误、边界条件错误。
2. 算法状态定义或转移错误。
3. 时间或空间复杂度不符合题目预期。
4. 可读性和局部优化建议。
