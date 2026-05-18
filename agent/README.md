# LeetCode Training Agent

一周 MVP 版本：一个主 Agent，内部包含实时取题、提示、复盘、失误画像几个能力模块。

## 功能

- 从本地题库下拉选择题目，支持按 LeetCode URL 或 slug 补充导入
- 单题训练会话
- 支持 Tab 缩进和语法高亮的代码编辑器
- Level 1-5 分级提示强度，超过 5 次后继续围绕最新上下文追问
- 提交代码后的结构化复盘
- Python 提交会运行题目样例，样例失败会直接标记为未通过
- Agent 指令和 Skill 按需加载
- 错误模式记录
- 按不同题型更新失误画像

## 安装

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

项目依赖统一安装在 `agent/.venv`。后续运行、测试和调试命令都使用项目虚拟环境；未激活 `.venv` 时，使用 `./.venv/bin/python3`，避免误用系统 Python。

## 运行

```bash
./.venv/bin/python3 -m streamlit run app.py
```

浏览器打开 Streamlit 给出的本地地址。

## 可选本地配置

没有 API key 也能运行，系统会使用本地规则兜底。

项目默认使用 Claude-style 的 `settings.json` 配置 LLM 和 LeetCode 抓题：

```json
{
  "openai": {
    "api_key": "your_api_key",
    "model": "gpt-5.5",
    "base_url": ""
  },
  "leetcode": {
    "csrftoken": "",
    "prefer_cn": true,
    "retry_count": 5,
    "timeout": 15,
    "category_slug": "all-code-essentials",
    "page_size": 50
  }
}
```

如果使用 OpenAI-compatible 代理或第三方兼容服务，填写自定义地址：

把 `openai.base_url` 改成自定义地址即可。

旧版 `config.toml` 仍兼容；当 `settings.json` 中某个字段为空时，会用 `config.toml` 中的同名字段补齐。不要提交 API Key，可把个人密钥放在本地忽略文件或环境变量中。

LLM 只会在 `openai.api_key` 非空时启用。LeetCode 抓题会读取 `leetcode` 配置，其中 `csrftoken` 可留空；需要中国站登录态时再填写。Streamlit 会缓存 `TrainingAgent`，所以修改配置后需要点击侧边栏“重新加载 LLM 配置”，或重启应用。

可以用下面命令检查当前是否启用：

```bash
./.venv/bin/python3 -c "from src.llm_client import LlmClient; c=LlmClient(); print(c.available, c.status_message)"
```

## Demo 用户

```text
user_id: demo
```

## 项目结构

```text
agent/
  app.py
  settings.json
  agents/
    hint.md
    review.md
    _template.md
  skills/
    leetcode-leveled-hint/
      SKILL.md
    leetcode-code-review/
      SKILL.md
  data/
    problems.json
    seed_user_profile.json
  src/
    agent_instructions.py
    training_agent.py
    leetcode_client.py
    hint_engine.py
    review_engine.py
    submission_runner.py
    profile_engine.py
    problem_store.py
    session_manager.py
    storage.py
    models.py
  projects/
    runtime.json
```

## 架构

```text
Streamlit UI
  ↓
TrainingAgent
  ├── LeetCodeClient
  ├── ProblemStore
  ├── HintEngine -> LlmClient -> agents/hint.md + skills/leetcode-leveled-hint/SKILL.md
  ├── ReviewEngine -> LlmClient -> agents/review.md + skills/leetcode-code-review/SKILL.md
  ├── ToolRegistry -> src/tools/
  ├── PythonSubmissionRunner
  ├── ProfileEngine
  ↓
JSON Runtime Storage -> projects/runtime.json
```

## Agent 指令与 Skills

LLM 调用会按 Agent 名称加载 `agents/<agent_name>.md` 和命中的 `skills/<skill-name>/SKILL.md`。

当前内置：

- `agents/hint.md`：分级提示 Agent。
- `agents/review.md`：代码复盘 Agent。
- `agents/_template.md`：新增 Agent 时复制使用的模板。
- `skills/leetcode-leveled-hint/SKILL.md`：提示强度控制 Skill。
- `skills/leetcode-code-review/SKILL.md`：代码复盘 Skill。

启动时只读取 `SKILL.md` 顶部 YAML 元数据并保存在内存中；每次用户问题进入对应 Agent 时，系统会用用户上下文和元数据做相似判断，命中后才加载 Skill 全文。UI 只显示“已使用 skill: ...”，不会打印全文。

加载顺序固定为 `agents/<agent_name>.md`、命中的 `skills/<skill-name>/SKILL.md` 正文、代码中的本次任务指令。新增 Agent 时，在 `agents/` 下创建同名 Markdown 文件，并在调用 `LlmClient.complete_text(...)` 或 `complete_json(...)` 时传入 `agent_name="文件名"`。

## LLM 工具调用

`LlmClient` 会按 Agent 名称暴露本地工具 schema。模型返回 function call 时，`ToolRegistry` 负责执行 `src/tools/` 中的本地 handler，并把工具结果回传给模型继续生成最终文本或 JSON。

当前默认工具：

- `get_problem`：读取本地题库或运行时缓存中的题目。
- `search_problem_cache`：按关键词、难度或标签搜索题目缓存。
- `fetch_leetcode_problem`：从 LeetCode GraphQL 拉取题目并写入运行时缓存。
- `run_python_examples`：运行 Python 样例执行器；只对 Review Agent 开放，结果不是 LeetCode 在线判题。

工具使用边界写在 `agents/hint.md`、`agents/review.md` 和对应 `SKILL.md` 中。UI 会在 LLM 参与生成后展示最近一次实际调用的工具名称。

## Python 样例执行

提交语言为 Python 时，`ReviewEngine` 会先通过 `PythonSubmissionRunner` 执行题目样例，再进入 LLM 或本地规则复盘。

执行策略：

- 子进程运行用户代码，避免卡住 Streamlit 主进程。
- 设置超时和内存限制，死循环或资源过高会标记为样例失败。
- 支持常见 LeetCode `Solution` 方法名，例如 `twoSum`、`isValid`、`maxProfit`、`search`。
- 允许常用算法模块，如 `collections`、`heapq`、`itertools`、`math`。
- 禁止导入 `os` 等非解题必要模块。

样例失败时，`passed_sample_tests` 会是 `false`，`is_likely_correct` 也会被强制设为 `false`。这不是完整在线判题，只代表当前题目样例执行结果和结构化复盘。

## Runtime 存储

运行时数据统一写入一个文件：

```text
projects/runtime.json
```

文件按分区和 id 组织：

```json
{
  "problems": {
    "two-sum": {}
  },
  "sessions": {
    "s_xxx": {}
  },
  "profiles": {
    "demo": {}
  },
  "reviews": {
    "sub_xxx": {}
  }
}
```

启动时会自动把旧版 `.runtime/runtime.json` 以及 `.runtime/problems/`、`.runtime/sessions/`、`.runtime/profiles/`、`.runtime/reviews/` 下的小 JSON 文件合并进 `projects/runtime.json`。之后不会再为每条会话或复盘创建单独 JSON 文件。

## 当前限制

- 不是完整在线判题系统。
- Python 复盘会先跑题目样例，但还不是完整隐藏用例判题。
- 非 Python 语言仍使用 LLM 或规则分析做“大概率判断”。
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

### 1. 用户选择或导入 LeetCode 题目

默认流程是在侧边栏从本地题库下拉选择题目，题目标题、难度和标签由 `ProblemStore.list_problems()` 从 `data/problems.json` 与 `projects/runtime.json` 汇总得到，用户不需要手动拼 slug。

如果本地题库里没有目标题，可以在“从 LeetCode URL 或 slug 导入”里输入题目 slug 或 URL：

```text
two-sum
https://leetcode.com/problems/two-sum/
```

导入调用链：

```text
app.py
  -> TrainingAgent.fetch_problem_from_leetcode()
    -> LeetCodeClient.fetch_problem()
      -> LeetCode GraphQL
      -> 转成 Problem
    -> ProblemStore.upsert_problem()
      -> 缓存到 projects/runtime.json 的 problems 分区
```

### 2. 用户开始一道题

```text
app.py
    -> TrainingAgent.create_session()
    -> ProfileEngine.get_profile()
    -> SessionManager.create_session()
    -> 保存到 projects/runtime.json 的 sessions 分区
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

`HintEngine` 会根据 `session.hints_given` 自动决定下一次提示强度。第一次是 Level 1，之后逐级增加，最高 Level 5。Level 1-5 表示泄题强度，不表示最多只能请求 5 次；第 6 次及以后会继续保持 Level 5，并根据用户最新输入、失败样例或代码细节继续追问式回答。

### 5. 用户提交代码

```text
app.py
  -> TrainingAgent.review_submission()
    -> ProblemStore.get_problem()
    -> ProfileEngine.get_profile()
    -> ReviewEngine.review_submission()
      -> Python 提交先运行样例
      -> 再优先调用 LLM
      -> 失败则使用本地规则检查常见错误
    -> ProfileEngine.update_after_review()
      -> 更新不同题型失误画像
    -> SessionManager.mark_reviewed()
    -> 保存 review 到 projects/runtime.json 的 reviews 分区
```

`ReviewEngine` 返回 `ReviewResult`，包括：

- 是否大概率正确
- 时间复杂度
- 空间复杂度
- 样例测试结果
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
| `src/code_templates.py` | 解析 LeetCode 函数签名和包装函数体提交 |
| `src/session_manager.py` | 创建、更新、保存会话 |
| `src/hint_engine.py` | 生成分级提示 |
| `src/review_engine.py` | 代码复盘和错误识别 |
| `src/submission_runner.py` | Python 提交样例执行器 |
| `src/tools/` | LLM 工具注册表和默认本地工具 |
| `src/agent_instructions.py` | Agent 指令和 Skill 渐进式加载 |
| `src/profile_engine.py` | 用户失误画像读取和更新 |
| `src/llm_client.py` | OpenAI API 封装 |
| `src/storage.py` | JSON 文件存储和 runtime 单文件存储 |
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
projects/runtime.json -> problems
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
projects/runtime.json -> sessions
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

Python 提交会先运行题目样例；非 Python 提交只做 LLM 或规则级分析。

### ProfileEngine

负责用户画像，重点是“不同题型的失误画像”。

保存位置：

```text
projects/runtime.json -> profiles
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
settings.json 有 openai.api_key -> 调 LLM
没有 key 或调用失败 -> 本地规则兜底
```

所以这个项目不依赖 API key 才能运行。

`src/llm_client.py` 只负责封装调用，不做业务判断。

## 本地数据如何保存

运行时数据都在 `projects/runtime.json` 中：

```text
projects/
  runtime.json
```

这让 MVP 不需要数据库，也避免为每个 session、review、profile 疯狂创建小 JSON。打开 `runtime.json` 就能看到按 id 组织的状态变化。

## 后续开发建议

优先顺序：

1. 强化 `review_engine.py` 的规则检查和样例外边界用例生成。
2. 给 `hint_engine.py` 增加更细的题型提示模板。
3. 给 `app.py` 增加更完整的运行状态展示。
4. 给 `profile_engine.py` 增加更细的题型画像统计。
5. 增加隐藏用例或自定义用例执行能力。
6. 数据量变大后再把 `projects/runtime.json` 换成 SQLite。
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
