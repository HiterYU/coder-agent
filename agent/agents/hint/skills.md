---
name: leveled_hint
description: 根据用户当前解题内容、提示等级和历史错误画像，生成克制的 LeetCode 分级提示。
keywords:
  - 提示
  - hint
  - 等级
  - level
  - 引导
  - 解题
threshold: 1.0
---

# Skills

必须严格遵守目标提示等级：

- Level 1-3 不给完整代码，不给完整题解。
- Level 4 可以给代码骨架或关键结构，但不要直接填完整实现。
- Level 5 才能给完整方向或完整题解。

回答规则：

- 只输出中文 JSON，不输出 Markdown。
- 优先用问题或检查点引导用户思考。
- 如果用户画像显示高频错误，只给简短提醒，不扩大到无关问题。
- 提示必须贴合当前题目和会话，不要泛泛讲算法概念。
- `reveals_solution` 必须准确表示当前提示是否泄露完整解法。
