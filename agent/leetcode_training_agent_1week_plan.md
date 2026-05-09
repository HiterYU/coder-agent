# LeetCode 训练 Agent 一周协作落地方案

## 1. 一周目标

在 7 天内完成一个可演示、可连续使用的 LeetCode 编程训练 Agent 原型。

本版本只追求跑通核心训练闭环：

1. 用户选择题目。
2. 用户阅读题目并输入思路或代码。
3. Agent 根据当前阶段给分级提示。
4. 用户提交代码。
5. 系统做基础评估和复盘。
6. 系统记录错误模式。
7. 系统基于错误推荐下一题。

本版本不追求完整 LeetCode 题库、不追求复杂在线判题、不追求多人系统、不追求复杂机器学习模型。

## 2. 最终交付物

一周结束时必须能交付：

1. 一个可运行的本地 Web UI 或 CLI。
2. 10-15 道精选题目数据。
3. 单题训练会话流程。
4. 分级提示能力。
5. 提交代码后的复盘能力。
6. 简单用户画像和错误模式记录。
7. 下一题推荐。
8. README 运行说明。
9. 一段 3-5 分钟演示流程。

推荐技术栈：

- 后端：Python + FastAPI
- 前端：Streamlit 或简单 Web UI
- 数据：SQLite + JSON seed 数据
- Agent：单 Orchestrator + 多个 prompt 模板

如果时间不足，优先选择 Streamlit，减少前后端联调成本。

## 3. MVP 范围

### 3.1 必做

| 模块 | 必做能力 |
|---|---|
| 题库 | 10-15 道题，结构化保存 |
| 会话 | 创建会话、记录消息、保存当前代码 |
| 提示 | Level 1-5 分级提示 |
| 复盘 | 对用户思路和代码生成复盘 |
| 错误记录 | 记录错误类型、题目、次数 |
| 用户画像 | 汇总强项、弱点、提示依赖 |
| 推荐 | 根据弱点推荐下一题 |
| UI | 能看题、输入内容、请求提示、提交代码、看复盘 |

### 3.2 暂不做

| 暂不做 | 原因 |
|---|---|
| 完整 LeetCode 同步 | 一周内成本过高 |
| 真实在线判题沙箱 | 安全和工程成本高 |
| 多用户登录系统 | 原型不需要 |
| 复杂前端编辑器 | 容易拖慢进度 |
| 自动机器学习画像 | 样本太少，规则更稳 |
| 多 Agent 并行系统 | MVP 阶段没有必要 |

## 4. 核心用户流程

### 4.1 首次进入

1. 用户输入用户 ID。
2. 用户选择训练目标：
   - 算法基础
   - 面试高频
   - 动态规划
   - 二叉树
   - 滑动窗口
   - 图论
3. 系统根据目标推荐第一题。

### 4.2 单题训练

1. 系统展示题目标题、难度、标签、描述、示例、约束。
2. 用户输入思路、伪代码、代码或问题。
3. 用户可以点击或输入“请求提示”。
4. Agent 根据当前阶段和已给提示等级返回提示。
5. 用户提交代码。
6. 系统生成复盘：
   - 解法是否正确。
   - 时间复杂度。
   - 空间复杂度。
   - 边界条件。
   - 主要错误。
   - 改进建议。
7. 系统更新用户画像。
8. 系统推荐下一题。

## 5. 系统架构

```text
用户
 │
 ▼
Streamlit UI 或 CLI
 │
 ▼
Training Orchestrator
 │
 ├── Problem Store
 ├── Session Manager
 ├── Hint Engine
 ├── Review Engine
 ├── Profile Engine
 └── Recommendation Engine
 │
 ▼
SQLite / JSON Files
```

一周内建议先实现为单体应用，模块用 Python 文件或 class 拆开，不需要微服务。

## 6. 推荐目录结构

```text
leetcode-agent/
  README.md
  requirements.txt
  app.py
  data/
    problems.json
    seed_user_profile.json
  src/
    models.py
    problem_store.py
    session_manager.py
    hint_engine.py
    review_engine.py
    profile_engine.py
    recommendation_engine.py
    llm_client.py
    storage.py
  prompts/
    hint.md
    review.md
    profile_update.md
    recommendation.md
  tests/
    test_hint_engine.py
    test_profile_engine.py
    test_recommendation_engine.py
```

如果使用 Streamlit，`app.py` 直接作为入口。

## 7. 数据结构

### 7.1 Problem

```json
{
  "id": "two-sum",
  "leetcode_id": 1,
  "title": "Two Sum",
  "difficulty": "Easy",
  "tags": ["Array", "Hash Table"],
  "description": "Given an array of integers nums and an integer target...",
  "examples": [
    {
      "input": "nums = [2,7,11,15], target = 9",
      "output": "[0,1]",
      "explanation": "nums[0] + nums[1] == 9"
    }
  ],
  "constraints": [
    "2 <= nums.length <= 10^4",
    "-10^9 <= nums[i] <= 10^9"
  ],
  "expected_approaches": [
    {
      "name": "hash_map",
      "time_complexity": "O(n)",
      "space_complexity": "O(n)",
      "summary": "Use a hash map to store previous values and their indices."
    }
  ],
  "common_mistakes": [
    {
      "type": "return_value_instead_of_index",
      "description": "返回了值而不是下标"
    },
    {
      "type": "reuse_same_element",
      "description": "同一个元素被使用了两次"
    }
  ],
  "similar_problem_ids": ["three-sum", "two-sum-ii"]
}
```

### 7.2 Session

```json
{
  "session_id": "s_001",
  "user_id": "u_001",
  "problem_id": "two-sum",
  "language": "Python",
  "status": "coding",
  "started_at": "2026-05-07T10:00:00Z",
  "updated_at": "2026-05-07T10:20:00Z",
  "current_stage": "implementation",
  "hints_given": [1, 2],
  "messages": [
    {
      "role": "user",
      "type": "thought",
      "content": "我想先暴力枚举两个数。",
      "created_at": "2026-05-07T10:03:00Z"
    }
  ],
  "current_code": "",
  "submission_ids": []
}
```

### 7.3 ReviewResult

```json
{
  "submission_id": "sub_001",
  "session_id": "s_001",
  "is_likely_correct": true,
  "passed_sample_tests": true,
  "time_complexity": "O(n)",
  "space_complexity": "O(n)",
  "mistakes": [
    {
      "type": "boundary_condition_missing",
      "topic": "array",
      "severity": "medium",
      "evidence": "代码没有显式考虑空数组或长度不足的情况。"
    }
  ],
  "feedback": "你的哈希表方向是对的，主要需要注意返回下标而不是数值。",
  "next_actions": [
    "补充重复元素测试",
    "解释为什么不能复用同一个元素"
  ]
}
```

### 7.4 UserProfile

```json
{
  "user_id": "u_001",
  "language": "Python",
  "goal": "interview",
  "solved_problem_ids": ["two-sum"],
  "strengths": [
    {
      "topic": "hash_table",
      "confidence": 0.7,
      "evidence_count": 2
    }
  ],
  "weaknesses": [
    {
      "topic": "sliding_window",
      "pattern": "window_shrink_condition_wrong",
      "confidence": 0.8,
      "evidence_count": 3,
      "last_seen_at": "2026-05-07T10:20:00Z"
    }
  ],
  "common_mistakes": [
    {
      "type": "boundary_condition_missing",
      "count": 4,
      "last_seen_at": "2026-05-07T10:20:00Z",
      "example_problem_ids": ["two-sum", "merge-intervals"]
    }
  ],
  "hint_stats": {
    "total_hints": 8,
    "average_hint_level": 2.25,
    "level_4_or_5_count": 1
  }
}
```

## 8. 会话状态机

```text
not_started
  ↓
reading
  ↓
thinking
  ↓
coding
  ↓
debugging
  ↓
submitted
  ↓
reviewed
  ↓
completed
```

状态定义：

| 状态 | 含义 | 进入条件 |
|---|---|---|
| not_started | 尚未开始 | 创建会话前 |
| reading | 正在读题 | 用户打开题目 |
| thinking | 正在想思路 | 用户输入思路或伪代码 |
| coding | 正在写代码 | 用户输入代码 |
| debugging | 正在修 bug | 用户提交报错或失败结果 |
| submitted | 已提交 | 用户提交最终代码 |
| reviewed | 已复盘 | Agent 生成复盘 |
| completed | 已完成 | 用户确认完成或进入下一题 |

MVP 不需要自动精确识别所有状态，可以通过用户动作和关键词粗略更新。

## 9. 提示策略

### 9.1 提示等级

| 等级 | 名称 | 内容边界 | 示例 |
|---|---|---|---|
| Level 1 | 轻提醒 | 只提醒题目条件或边界 | 注意输入里是否可能有重复元素。 |
| Level 2 | 方向提示 | 给出算法方向，不给关键公式 | 可以考虑用哈希表减少重复查找。 |
| Level 3 | 关键思路 | 给出核心关系或移动规则 | 遍历时检查 target - x 是否已经出现。 |
| Level 4 | 代码骨架 | 给出变量和主循环结构 | 维护 seen 字典，遍历 nums。 |
| Level 5 | 完整题解 | 给完整解法、复杂度和复盘 | 用户明确要求答案或多次失败后提供。 |

### 9.2 升级规则

满足任一条件时，提示等级可以上升一级：

1. 用户明确请求“再具体一点”。
2. 用户在同一级提示后再次卡住。
3. 用户连续两次提交仍存在同类错误。
4. 当前提示等级不足以解释用户的具体报错。

满足任一条件时，不主动升级：

1. 用户还没有表达明确卡点。
2. 用户正在独立推导。
3. 用户刚拿到上一个提示，还没有尝试。
4. 用户的错误只需要一个边界提醒。

### 9.3 主动提醒规则

只在以下情况主动提醒：

1. 用户历史高频错误和当前题目高度相关。
2. 用户当前代码已经出现明确风险。
3. 提醒可以不泄露核心答案。

主动提醒模板：

```text
我注意到这题和你之前出错的 {mistake_type} 有关。先别急着改代码，建议你确认一下：{check_question}
```

## 10. 错误分类

MVP 使用固定 taxonomy，方便统计和推荐。

| 类型 | 说明 | 常见题型 |
|---|---|---|
| problem_understanding_wrong | 题意理解错误 | 所有题型 |
| boundary_condition_missing | 漏边界条件 | 数组、链表、树 |
| index_out_of_range | 下标越界 | 数组、字符串 |
| wrong_loop_condition | 循环条件错误 | 双指针、二分 |
| wrong_state_definition | 状态定义错误 | 动态规划 |
| wrong_state_transition | 状态转移错误 | 动态规划 |
| recursion_base_case_missing | 递归终止条件错误 | 树、DFS |
| visited_handling_wrong | visited 处理错误 | 图、DFS、BFS |
| greedy_reasoning_weak | 贪心理由不充分 | 贪心 |
| complexity_too_high | 复杂度过高 | 所有题型 |
| return_format_wrong | 返回格式错误 | 所有题型 |

## 11. 推荐策略

### 11.1 题目打分

MVP 使用规则打分：

```text
score =
  weakness_match * 0.40 +
  difficulty_fit * 0.25 +
  not_recently_done * 0.15 +
  interview_value * 0.10 +
  prerequisite_fit * 0.10
```

字段解释：

| 字段 | 说明 |
|---|---|
| weakness_match | 是否命中用户薄弱 topic 或错误模式 |
| difficulty_fit | 难度是否适合当前水平 |
| not_recently_done | 是否不是刚做过的题 |
| interview_value | 是否属于高频或经典题 |
| prerequisite_fit | 是否具备前置知识 |

### 11.2 推荐理由模板

```text
推荐你下一题做 {problem_title}。
原因：你刚才在 {mistake_type} 上有一次明显失误，这题可以继续练习 {topic}，难度比上一题略高但不会跳太大。
```

## 12. API 设计

如果使用 FastAPI，建议实现这些接口：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /problems | 获取题目列表 |
| GET | /problems/{problem_id} | 获取题目详情 |
| POST | /sessions | 创建训练会话 |
| GET | /sessions/{session_id} | 获取会话 |
| POST | /sessions/{session_id}/message | 发送思路、问题或代码片段 |
| POST | /sessions/{session_id}/hint | 请求提示 |
| POST | /sessions/{session_id}/submit | 提交代码 |
| GET | /users/{user_id}/profile | 获取用户画像 |
| GET | /users/{user_id}/recommendations | 获取推荐题目 |

一周内如果使用 Streamlit，可以不暴露完整 API，但内部函数要按这些边界拆分，方便后续迁移。

## 13. Prompt 模板

### 13.1 Hint Prompt

```text
你是一个 LeetCode 编程训练教练。

目标：帮助用户继续独立解题，不要过早给出完整答案。

输入：
- 题目：{problem}
- 用户画像：{profile}
- 当前会话：{session}
- 已给提示等级：{hints_given}
- 目标提示等级：{hint_level}
- 用户最近输入：{latest_message}

要求：
1. 严格遵守目标提示等级。
2. Level 1-3 不给完整代码。
3. 优先用问题引导用户思考。
4. 如果发现用户历史高频错误，只给克制提醒。
5. 输出中文。

输出格式：
{
  "hint_level": 2,
  "hint": "...",
  "why_this_hint": "...",
  "reveals_solution": false
}
```

### 13.2 Review Prompt

```text
你是一个严谨的代码复盘教练。

输入：
- 题目：{problem}
- 用户代码：{code}
- 用户思路：{thoughts}
- 样例运行结果：{sample_test_result}
- 用户画像：{profile}

任务：
1. 判断代码是否大概率正确。
2. 分析时间复杂度和空间复杂度。
3. 找出具体错误，不要泛泛而谈。
4. 标注错误类型，必须从给定 taxonomy 中选择。
5. 给出下一步改进建议。
6. 不要羞辱用户，不要给无证据结论。

输出 JSON：
{
  "is_likely_correct": true,
  "time_complexity": "O(n)",
  "space_complexity": "O(n)",
  "mistakes": [],
  "feedback": "...",
  "next_actions": []
}
```

### 13.3 Profile Update Prompt

```text
你负责根据一次做题记录更新用户画像。

输入：
- 旧画像：{profile}
- 题目：{problem}
- 会话记录：{session}
- 复盘结果：{review_result}

要求：
1. 只根据证据更新画像。
2. 单次错误只能轻微增加 confidence。
3. 多次重复错误才形成 weakness。
4. 如果本次表现良好，可以增加 strength。
5. 输出完整的新画像 JSON。
```

## 14. 两人协作分工

### 成员 A：Agent 与训练逻辑

负责范围：

1. 题目数据结构。
2. 首批 10-15 道题整理。
3. 错误 taxonomy。
4. Hint Prompt。
5. Review Prompt。
6. Profile Update Prompt。
7. 推荐规则。
8. 复盘输出格式。

交付文件：

```text
data/problems.json
prompts/hint.md
prompts/review.md
prompts/profile_update.md
prompts/recommendation.md
src/hint_engine.py
src/review_engine.py
src/profile_engine.py
src/recommendation_engine.py
```

### 成员 B：工程与产品集成

负责范围：

1. 项目脚手架。
2. Streamlit 或 FastAPI 应用。
3. 数据读取和保存。
4. 会话管理。
5. LLM 调用封装。
6. UI 页面。
7. README。
8. 演示脚本。

交付文件：

```text
app.py
requirements.txt
README.md
src/models.py
src/storage.py
src/problem_store.py
src/session_manager.py
src/llm_client.py
```

### 共同决定

1. 最终题目列表。
2. 数据字段是否冻结。
3. 提示等级定义。
4. 复盘 JSON schema。
5. 演示路径。
6. 验收标准。

## 15. 接口契约

为了避免两人互相阻塞，先冻结这些函数签名。

```python
def list_problems(filters: dict | None = None) -> list[Problem]:
    ...

def get_problem(problem_id: str) -> Problem:
    ...

def create_session(user_id: str, problem_id: str, language: str) -> Session:
    ...

def add_message(session_id: str, role: str, message_type: str, content: str) -> Session:
    ...

def generate_hint(session: Session, problem: Problem, profile: UserProfile) -> dict:
    ...

def review_submission(session: Session, problem: Problem, profile: UserProfile, code: str) -> ReviewResult:
    ...

def update_profile(profile: UserProfile, session: Session, review: ReviewResult) -> UserProfile:
    ...

def recommend_next_problem(profile: UserProfile, solved_problem_ids: list[str]) -> list[Problem]:
    ...
```

成员 A 可以先写假实现或纯函数，成员 B 可以先用 mock 数据接 UI。两边每天合并一次。

## 16. 一周排期

### Day 1：定范围和搭骨架

目标：项目能启动，数据格式冻结。

任务：

| 人 | 任务 |
|---|---|
| A | 确定 10-15 道题列表，完成 Problem JSON schema |
| A | 完成错误 taxonomy 初版 |
| B | 创建项目结构、依赖、运行入口 |
| B | 完成 Problem Store 和本地存储框架 |
| 共同 | 冻结函数签名和 ReviewResult schema |

验收：

1. 应用能启动。
2. 能展示题目列表。
3. `data/problems.json` 至少有 3 道完整题。

### Day 2：单题会话

目标：用户能打开一道题并持续输入内容。

任务：

| 人 | 任务 |
|---|---|
| A | 完成 Hint Prompt v1 |
| A | 为 5 道题写 common_mistakes 和 expected_approaches |
| B | 实现 Session Manager |
| B | UI 支持选题、显示题目、输入思路或代码 |
| 共同 | 联调会话数据保存 |

验收：

1. 可以创建 session。
2. 用户消息可以保存。
3. 关闭重开后能看到历史记录。

### Day 3：分级提示

目标：Agent 能根据会话给 Level 1-5 提示。

任务：

| 人 | 任务 |
|---|---|
| A | 实现 `hint_engine.py` |
| A | 设计提示升级规则 |
| B | 接入 LLM client |
| B | UI 增加“请求提示”按钮或命令 |
| 共同 | 用 3 道题测试提示是否剧透过早 |

验收：

1. 请求提示后能返回内容。
2. 同一题能逐级提示。
3. Level 1-3 不直接给完整答案。

### Day 4：提交与复盘

目标：用户提交代码后能看到结构化复盘。

任务：

| 人 | 任务 |
|---|---|
| A | 完成 Review Prompt v1 |
| A | 实现 `review_engine.py` |
| B | UI 增加代码提交区域 |
| B | 保存 submission 和 review result |
| 共同 | 人工测试 5 个错误案例 |

验收：

1. 提交代码后生成复盘。
2. 复盘包含复杂度、错误类型和改进建议。
3. 错误类型来自 taxonomy。

### Day 5：画像和推荐

目标：做完题后能更新用户画像并推荐下一题。

任务：

| 人 | 任务 |
|---|---|
| A | 完成 Profile Update Prompt |
| A | 实现推荐规则 |
| B | 增加用户画像页面 |
| B | 增加下一题推荐展示 |
| 共同 | 测试连续做 3 题的数据流 |

验收：

1. 画像会记录常见错误。
2. 推荐题目能给出理由。
3. 已做过题目不会马上重复推荐。

### Day 6：打磨和补数据

目标：让演示流程稳定。

任务：

| 人 | 任务 |
|---|---|
| A | 补齐 10-15 道题数据 |
| A | 优化提示和复盘 prompt |
| B | 修 UI 和数据保存问题 |
| B | 补 README 和启动脚本 |
| 共同 | 完整走 2 次演示流程 |

验收：

1. 题库数量达到 10-15。
2. 演示流程不需要手动改数据。
3. README 能让别人跑起来。

### Day 7：验收和演示

目标：冻结版本，准备展示。

任务：

| 人 | 任务 |
|---|---|
| A | 准备演示题目和讲解点 |
| A | 检查 Agent 输出质量 |
| B | 修最后的阻塞 bug |
| B | 准备演示环境 |
| 共同 | 录制或现场演示 3-5 分钟 |

验收：

1. 新用户能完成一道题。
2. 用户能请求多级提示。
3. 用户提交代码后能收到复盘。
4. 系统能记录错误并更新画像。
5. 系统能推荐下一题并说明原因。

## 17. 每日协作机制

每天固定两次同步：

1. 开始前 10 分钟：
   - 昨天完成了什么。
   - 今天交付什么。
   - 当前阻塞是什么。
2. 结束前 15 分钟：
   - 合并当天代码。
   - 跑一遍主流程。
   - 更新任务表。

协作规则：

1. 每天至少合并一次主分支。
2. 不改对方负责文件，除非提前说清楚。
3. 先用 mock 打通流程，再替换真实 LLM。
4. schema 变更必须两人确认。
5. 每天结束必须保证应用可启动。

## 18. 任务看板

| 任务 | 负责人 | 优先级 | 状态 |
|---|---|---|---|
| 项目脚手架 | B | P0 | Todo |
| 题目 schema | A | P0 | Todo |
| 首批 3 道题 | A | P0 | Todo |
| Problem Store | B | P0 | Todo |
| Session Manager | B | P0 | Todo |
| Hint Prompt | A | P0 | Todo |
| Hint Engine | A | P0 | Todo |
| LLM Client | B | P0 | Todo |
| UI 选题页面 | B | P0 | Todo |
| UI 会话页面 | B | P0 | Todo |
| Review Prompt | A | P0 | Todo |
| Review Engine | A | P0 | Todo |
| Submission Storage | B | P0 | Todo |
| Profile Engine | A | P1 | Todo |
| Profile Page | B | P1 | Todo |
| Recommendation Engine | A | P1 | Todo |
| Recommendation UI | B | P1 | Todo |
| README | B | P1 | Todo |
| 演示脚本 | 共同 | P1 | Todo |

## 19. 验收标准

### 19.1 功能验收

必须通过：

1. 用户能看到题目列表。
2. 用户能进入某一道题。
3. 用户能输入思路和代码。
4. 用户能请求提示。
5. 提示能逐级变具体。
6. 用户能提交代码。
7. 系统能生成结构化复盘。
8. 系统能记录至少一种错误模式。
9. 系统能展示用户画像。
10. 系统能推荐下一题。

### 19.2 质量验收

必须满足：

1. Level 1-3 不直接泄露完整答案。
2. 复盘必须引用用户代码或思路中的具体证据。
3. 用户画像不能只因一次错误就下强结论。
4. 推荐必须有理由。
5. 应用从零启动不超过 3 个命令。

### 19.3 演示验收

演示流程：

1. 选择用户 ID。
2. 选择训练目标。
3. 系统推荐第一题。
4. 用户输入一个不完整思路。
5. 请求 Level 1 和 Level 2 提示。
6. 提交一段有边界问题的代码。
7. Agent 指出错误并复盘。
8. 系统更新画像。
9. 系统推荐下一题。

## 20. 风险和兜底

| 风险 | 表现 | 兜底方案 |
|---|---|---|
| LLM 接入不稳定 | 提示或复盘失败 | 使用 mock response 和本地模板 |
| 代码评估不准 | LLM 误判正确性 | 明确标注“大概率判断”，先做样例测试 |
| 题目数据整理慢 | 题库不足 | 降到 8-10 道经典题 |
| 前端拖慢进度 | 页面做不完 | 改用 Streamlit 或 CLI |
| 画像过度推断 | 一次错误就贴标签 | 加 confidence 和 evidence_count |
| 推荐不好解释 | 用户不知道为什么做下一题 | 强制输出推荐理由 |

## 21. 一周内不要做的事

1. 不要搭复杂权限系统。
2. 不要做完整在线判题平台。
3. 不要做复杂可视化图表。
4. 不要引入多个数据库。
5. 不要追求支持所有编程语言。
6. 不要做完整公司题库。
7. 不要过早拆成多个独立 Agent 服务。
8. 不要在题目数量上消耗太多时间。

## 22. 最小演示题库建议

建议优先准备这些类型，覆盖常见错误：

| 题目 | 类型 | 训练点 |
|---|---|---|
| Two Sum | Hash Table | 返回下标、不能复用元素 |
| Valid Parentheses | Stack | 栈空判断、匹配顺序 |
| Best Time to Buy and Sell Stock | Array | 最小值维护、一次交易 |
| Merge Intervals | Sorting | 区间边界、合并条件 |
| Binary Search | Binary Search | 左右边界、循环条件 |
| Linked List Cycle | Two Pointers | 快慢指针、空指针 |
| Maximum Subarray | DP | 状态定义、局部最优 |
| Climbing Stairs | DP | 初始化、转移关系 |
| Longest Substring Without Repeating Characters | Sliding Window | 左边界更新 |
| Number of Islands | DFS/BFS | visited、边界检查 |

## 23. README 必须包含

```text
# LeetCode Training Agent

## Setup
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

## Run
./.venv/bin/python3 -m streamlit run app.py

## Demo User
user_id: demo

## Features
- Problem selection
- Guided hints
- Submission review
- User profile
- Next problem recommendation

## Limitations
- This MVP does not provide full online judging.
- Review correctness is based on sample tests and LLM analysis.
```

## 24. 完成定义

这个项目一周内完成，不等于做成完整产品。完成定义是：

1. 外部用户能在本地跑起来。
2. 用户能完整做完一道题。
3. Agent 能提供递进提示。
4. Agent 能基于用户代码做具体复盘。
5. 系统能留下用户错误记录。
6. 下一题推荐和用户画像不是静态假数据。
7. 两人可以继续在这个基础上扩展，而不是推倒重来。

优先把“单题训练体验”做扎实。题库、沙箱、多用户、复杂推荐都可以后置。
