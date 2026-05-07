# LeetCode Training Agent

一周 MVP 版本：一个主 Agent，内部包含实时取题、提示、复盘、失误画像几个能力模块。

## 功能

- 输入 LeetCode URL 或 slug 实时获取题目
- 单题训练会话
- Level 1-5 分级提示
- 提交代码后的结构化复盘
- 错误模式记录
- 按不同题型更新失误画像

## 安装

```bash
cd /home/donghui/jingqi/agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

浏览器打开 Streamlit 给出的本地地址。

## 可选 LLM 配置

没有 API key 也能运行，系统会使用本地规则兜底。

如果要使用 OpenAI API：

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_MODEL="gpt-4.1-mini"
streamlit run app.py
```

## Demo 用户

```text
user_id: demo
```

## 项目结构

```text
agent/
  app.py
  data/
    problems.json
    seed_user_profile.json
  src/
    training_agent.py
    leetcode_client.py
    hint_engine.py
    review_engine.py
    profile_engine.py
    problem_store.py
    session_manager.py
    storage.py
    models.py
  .runtime/
    problems/
    sessions/
    profiles/
    reviews/
```

## 架构

```text
Streamlit UI
  ↓
TrainingAgent
  ├── LeetCodeClient
  ├── ProblemStore
  ├── HintEngine
  ├── ReviewEngine
  ├── ProfileEngine
  ↓
JSON Runtime Storage
```

## 当前限制

- 不是完整在线判题系统。
- 复盘正确性是 LLM 或规则分析的“大概率判断”。
- 依赖 LeetCode GraphQL 可访问。
- 多用户只用 user_id 区分，没有登录系统。

## 代码如何配合

当前代码采用一个主控层加多个能力模块的结构：

```text
app.py
  -> TrainingAgent
      -> LeetCodeClient
      -> ProblemStore
      -> SessionManager
      -> HintEngine
      -> ReviewEngine
      -> ProfileEngine
      -> JsonStorage
```

`app.py` 是 Streamlit UI 入口。它只负责页面展示和按钮交互，不直接写复杂业务逻辑。

`TrainingAgent` 是主控层，位置在 `src/training_agent.py`。它负责协调其他模块，把用户的一次操作转成完整业务流程。

## 一次完整训练流程

### 1. 用户输入 LeetCode 题目

用户可以输入题目 slug：

```text
two-sum
```

也可以输入题目 URL：

```text
https://leetcode.com/problems/two-sum/
```

调用链：

```text
app.py
  -> TrainingAgent.fetch_problem_from_leetcode()
    -> LeetCodeClient.fetch_problem()
      -> LeetCode GraphQL
      -> 转成 Problem
    -> ProblemStore.upsert_problem()
      -> 缓存到 .runtime/problems/{problem_id}.json
```

### 2. 用户开始一道题

```text
app.py
  -> TrainingAgent.create_session()
    -> ProfileEngine.get_profile()
    -> SessionManager.create_session()
    -> 保存到 .runtime/sessions/{session_id}.json
```

这里会创建一个 `Session`，记录用户 ID、题目 ID、语言、开始时间、当前状态和后续消息。

### 3. 用户输入思路或代码

```text
app.py
  -> TrainingAgent.add_user_message()
    -> SessionManager.add_message()
    -> 更新 session.messages
    -> 推断 current_stage
    -> 保存 session
```

如果输入类型是 `code`，系统会把内容同步到 `session.current_code`。

### 4. 用户请求提示

```text
app.py
  -> TrainingAgent.generate_hint()
    -> ProblemStore.get_problem()
    -> ProfileEngine.get_profile()
    -> HintEngine.generate_hint()
      -> 优先调用 LLM
      -> 失败则使用本地规则兜底
    -> SessionManager.mark_hint_given()
    -> ProfileEngine.update_after_hint()
```

`HintEngine` 会根据 `session.hints_given` 自动决定下一个提示等级。第一次是 Level 1，之后逐级增加，最高 Level 5。

### 5. 用户提交代码

```text
app.py
  -> TrainingAgent.review_submission()
    -> ProblemStore.get_problem()
    -> ProfileEngine.get_profile()
    -> ReviewEngine.review_submission()
      -> 优先调用 LLM
      -> 失败则使用本地规则检查常见错误
    -> ProfileEngine.update_after_review()
      -> 更新不同题型失误画像
    -> SessionManager.mark_reviewed()
    -> 保存 review 到 .runtime/reviews/
```

`ReviewEngine` 返回 `ReviewResult`，包括：

- 是否大概率正确
- 时间复杂度
- 空间复杂度
- 错误类型
- 具体证据
- 复盘反馈
- 下一步建议

## 主要文件说明

| 文件 | 作用 |
|---|---|
| `app.py` | Streamlit 页面入口 |
| `src/training_agent.py` | 主控协调器 |
| `src/leetcode_client.py` | 从 LeetCode 实时获取题目 |
| `src/models.py` | 所有核心数据模型 |
| `src/problem_store.py` | 查询题目和缓存实时题目 |
| `src/session_manager.py` | 创建、更新、保存会话 |
| `src/hint_engine.py` | 生成分级提示 |
| `src/review_engine.py` | 代码复盘和错误识别 |
| `src/profile_engine.py` | 用户失误画像读取和更新 |
| `src/llm_client.py` | OpenAI API 封装 |
| `src/storage.py` | JSON 文件存储 |
| `src/taxonomy.py` | 固定错误类型 |
| `src/formatting.py` | 页面展示格式化 |
| `data/problems.json` | 本地兜底题库 |
| `data/seed_user_profile.json` | 初始用户画像 |

## 核心数据模型

核心模型都在 `src/models.py`。

| 模型 | 含义 |
|---|---|
| `Problem` | 一道题的结构化数据 |
| `Session` | 用户一次做题会话 |
| `Message` | 会话里的用户或助手消息 |
| `ReviewResult` | 一次代码提交后的复盘结果 |
| `Mistake` | 具体错误及证据 |
| `TopicMistakeProfile` | 某类题型下的失误统计 |
| `UserProfile` | 用户长期画像 |

其他模块之间尽量传这些模型，而不是随意传 dict。

## 模块边界

### LeetCodeClient

负责从 LeetCode 实时获取题目。

输入：

```python
fetch_problem("two-sum")
fetch_problem("https://leetcode.com/problems/two-sum/")
```

输出：

```python
Problem
```

它会把 LeetCode GraphQL 返回的数据转成系统内部的 `Problem`。

### ProblemStore

负责题目查询和缓存。

启动时读取：

```text
data/problems.json
.runtime/problems/*.json
```

实时抓到题目后调用：

```python
upsert_problem(problem)
```

常用查询：

```python
list_problems(filters=None)
get_problem(problem_id)
tags()
```

后续如果换数据库，优先改这个模块。

### SessionManager

负责会话状态，不负责提示和复盘。

保存位置：

```text
.runtime/sessions/
```

### HintEngine

负责提示内容。

输入：

- `Session`
- `Problem`
- `UserProfile`

输出：

```python
{
  "hint_level": 1,
  "hint": "...",
  "why_this_hint": "...",
  "reveals_solution": false
}
```

### ReviewEngine

负责代码复盘。

输入：

- `Session`
- `Problem`
- `UserProfile`
- `code`

输出：

- `ReviewResult`

当前不是完整在线判题，只做 LLM 或规则级分析。

### ProfileEngine

负责用户画像，重点是“不同题型的失误画像”。

保存位置：

```text
.runtime/profiles/
```

它会根据提示使用情况和复盘结果更新：

- 全局常见错误
- 按题型统计的错误分布
- 提示依赖程度

示例：

```json
{
  "topic": "dynamic_programming",
  "total_mistakes": 3,
  "mistake_counts": {
    "wrong_state_definition": 2,
    "boundary_condition_missing": 1
  },
  "example_problem_ids": ["maximum-subarray", "climbing-stairs"]
}
```

## LLM 和本地规则的关系

`HintEngine` 和 `ReviewEngine` 都是同一套策略：

```text
有 OPENAI_API_KEY -> 调 LLM
没有 key 或调用失败 -> 本地规则兜底
```

所以这个项目不依赖 API key 才能运行。

`src/llm_client.py` 只负责封装调用，不做业务判断。

## 本地数据如何保存

运行时数据都在 `.runtime/` 下：

```text
.runtime/
  problems/
    two-sum.json
  sessions/
    s_xxx.json
  profiles/
    demo.json
  reviews/
    sub_xxx.json
```

这让 MVP 不需要数据库，也方便调试。打开 JSON 文件就能看到状态变化。

## 后续开发建议

优先顺序：

1. 强化 `review_engine.py` 的规则检查。
2. 给 `hint_engine.py` 增加更细的题型提示模板。
3. 给 `app.py` 增加更好的代码输入体验。
4. 给 `profile_engine.py` 增加更细的题型画像统计。
5. 增加样例测试执行能力。
6. 把 `.runtime/` 从 JSON 换成 SQLite。
7. 流程稳定后再考虑 LangGraph。

不建议现在就做：

- 下一题推荐
- 完整在线判题平台
- 多 Agent 编排
- 复杂登录系统
- 完整 LeetCode 爬虫
- 向量数据库

当前重点是把这条链路做稳：

```text
实时题目获取 -> 用户行为证据 -> 分级提示 -> 代码复盘 -> 不同题型失误画像
```
