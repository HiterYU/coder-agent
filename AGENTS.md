# Repository Guidelines
<!-- 文件用途：说明本仓库的结构、开发命令、代码规范与协作流程。 -->

## Project Structure & Module Organization

本仓库主体位于 `agent/` 目录。根目录 `README.md` 是项目简介；`agent/README.md` 是主要说明文档。

- `agent/app.py`：Streamlit UI 入口，只放页面状态、布局与交互逻辑。
- `agent/src/`：核心 Python 模块，包含 `TrainingAgent`、LeetCode 拉取、提示、复盘、画像、存储等能力。
- `agent/data/`：内置题库与种子用户画像。
- `agent/prompts/`：LLM 提示词模板。
- `agent/.runtime/`：运行时生成的题目、会话、画像和复盘数据；不要提交。

## Build, Test, and Development Commands

所有 Python 命令使用 `python3`。

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

- `pip install -r requirements.txt`：安装 Streamlit、Pydantic、OpenAI、Requests 等依赖。
- `streamlit run app.py`：启动本地 Web 应用。
- 可选：设置 `OPENAI_API_KEY` 和 `OPENAI_MODEL` 启用 LLM；未设置时使用本地规则兜底。

## Coding Style & Naming Conventions

使用 Python 3、4 空格缩进、类型注解和清晰的小函数。模块、函数和变量使用 `snake_case`，类使用 `PascalCase`。每个文件需包含文件头注释，说明功能与用途；所有对外函数和类必须提供中文 docstring，说明作用、参数和返回值；关键字段需添加中文注释。UI 逻辑保留在 `app.py`，业务流程放入 `src/training_agent.py` 或对应能力模块。

## Testing Guidelines

当前仓库尚未建立正式测试目录。新增测试时建议使用 `pytest`，放在 `agent/tests/`，文件命名为 `test_*.py`。优先覆盖 `src/` 中的纯业务逻辑，例如题目缓存、会话状态更新、提示等级递增和复盘结果解析。运行示例：

```bash
cd agent
python3 -m pytest
```

## Commit & Pull Request Guidelines

现有 Git 历史提交格式不统一，后续提交必须使用中文类型前缀：`类型: 简洁说明`，例如 `新增: 增加会话管理测试`、`修复: 处理 LeetCode 请求失败兜底`。正文用多个要点说明关键改动。

Pull Request 需说明变更目的、主要文件、验证命令和结果；涉及 UI 变化时附截图；涉及配置或运行时目录时说明是否需要迁移或清理本地数据。

## Security & Configuration Tips

不要提交 `.venv/`、`.runtime/`、API Key 或个人 LeetCode 数据。通过环境变量配置 `OPENAI_API_KEY`、`OPENAI_MODEL`，不要写入源码或数据文件。
