from __future__ import annotations

# 文件用途：Streamlit UI 入口，负责页面状态、布局与交互逻辑。

from pathlib import Path

import streamlit as st
from streamlit_ace import st_ace

from src.code_templates import (
    extract_python_body_code,
    get_python_function_signature,
    is_python_body_mode_available,
)
from src.formatting import format_profile, format_problem, format_review
from src.models import Problem, Session
from src.training_agent import TrainingAgent


PROJECT_DIR = Path(__file__).resolve().parent
EDITOR_LANGUAGE_MAP = {
    "Python": "python",
    "JavaScript": "javascript",
    "Java": "java",
    "C++": "c_cpp",
}


@st.cache_resource
def get_agent() -> TrainingAgent:
    """获取缓存后的训练 Agent。

    参数:
        无。

    返回值:
        TrainingAgent: 当前项目目录对应的训练 Agent 实例。
    """
    return TrainingAgent(PROJECT_DIR)


def init_state() -> None:
    """初始化 Streamlit 页面状态。

    参数:
        无。

    返回值:
        无。
    """
    st.session_state.setdefault("user_id", "demo")
    st.session_state.setdefault("language", "Python")
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("selected_problem_id", None)
    st.session_state.setdefault("leetcode_input", "two-sum")
    st.session_state.setdefault("loaded_problem_id", None)
    st.session_state.setdefault("last_review", None)
    st.session_state.setdefault("last_hint", None)
    st.session_state.setdefault("last_used_skills", [])
    st.session_state.setdefault("load_error", None)


def problem_option_label(problem: Problem) -> str:
    """生成题目下拉选项展示文案。

    参数:
        problem: 题目数据。

    返回值:
        str: 包含题号、标题、难度和标签的展示文案。
    """
    leetcode_prefix = f"{problem.leetcode_id}. " if problem.leetcode_id else ""
    tags = " / ".join(problem.tags[:3]) if problem.tags else "未标注"
    return f"{leetcode_prefix}{problem.title} ({problem.difficulty}) · {tags}"


def reset_training_outputs() -> None:
    """清空上一题的提示、复盘和错误状态。

    参数:
        无。

    返回值:
        无。
    """
    st.session_state.last_review = None
    st.session_state.last_hint = None
    st.session_state.last_used_skills = []
    st.session_state.load_error = None


def start_problem_session(agent: TrainingAgent, problem_id: str) -> None:
    """基于本地题目创建新的训练会话。

    参数:
        agent: 训练 Agent 实例。
        problem_id: 本地题库中的题目 ID。

    返回值:
        无。
    """
    problem = agent.get_problem(problem_id)
    st.session_state.loaded_problem_id = problem.id
    st.session_state.selected_problem_id = problem.id
    st.session_state.session = agent.create_session(
        st.session_state.user_id,
        problem.id,
        st.session_state.language,
    )
    reset_training_outputs()


def render_sidebar(agent: TrainingAgent) -> None:
    """渲染侧边栏训练设置。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    with st.sidebar:
        st.header("训练设置")
        st.session_state.user_id = st.text_input("用户 ID", st.session_state.user_id)
        languages = ["Python", "JavaScript", "Java", "C++"]
        language_index = languages.index(st.session_state.language)
        st.session_state.language = st.selectbox(
            "语言", languages, index=language_index
        )

        problems = agent.list_problems()
        problem_by_id = {problem.id: problem for problem in problems}
        problem_ids = [problem.id for problem in problems]
        if problem_ids:
            if st.session_state.selected_problem_id not in problem_by_id:
                st.session_state.selected_problem_id = problem_ids[0]
            selected_index = problem_ids.index(st.session_state.selected_problem_id)
            st.session_state.selected_problem_id = st.selectbox(
                "本地题库",
                problem_ids,
                index=selected_index,
                format_func=lambda problem_id: problem_option_label(problem_by_id[problem_id]),
            )
            if st.button("开始这道题", type="primary"):
                start_problem_session(agent, st.session_state.selected_problem_id)
                st.rerun()
        else:
            st.warning("本地题库为空，请先导入题目。")

        with st.expander("从 LeetCode URL 或 slug 导入"):
            st.session_state.leetcode_input = st.text_input(
                "LeetCode URL 或 slug",
                st.session_state.leetcode_input,
                placeholder="https://leetcode.com/problems/two-sum/ 或 two-sum",
            )

            if st.button("导入并开始"):
                try:
                    problem = agent.fetch_problem_from_leetcode(st.session_state.leetcode_input)
                    start_problem_session(agent, problem.id)
                    st.rerun()
                except Exception as exc:
                    st.session_state.load_error = str(exc)

        st.divider()
        render_llm_status(agent)

        st.divider()
        profile = agent.get_profile(st.session_state.user_id)
        st.subheader("失误画像")
        st.text(format_profile(profile))


def ensure_session(agent: TrainingAgent) -> Session | None:
    """确保当前页面拥有训练会话。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        Session | None: 当前训练会话；未加载题目时返回 None。
    """
    session = st.session_state.session
    loaded_problem_id = st.session_state.loaded_problem_id
    if session is None and loaded_problem_id:
        session = agent.create_session(
            st.session_state.user_id,
            loaded_problem_id,
            st.session_state.language,
        )
        st.session_state.session = session
    return session


def render_problem(agent: TrainingAgent, session: Session) -> None:
    """渲染当前题目信息。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    problem = agent.get_problem(session.problem_id)
    st.markdown(format_problem(problem))


def render_chat_history(session: Session) -> None:
    """渲染会话历史记录。

    参数:
        session: 当前训练会话。

    返回值:
        无。
    """
    if not session.messages:
        return
    st.subheader("会话记录")
    for message in session.messages:
        with st.chat_message(message.role):
            st.markdown(f"**{message.type}**")
            st.write(message.content)


def render_code_editor(label: str, value: str, key: str, height: int) -> str:
    """渲染支持语法高亮和 Tab 缩进的代码编辑器。

    参数:
        label: 编辑器标题。
        value: 编辑器初始代码内容。
        key: Streamlit 组件唯一标识。
        height: 编辑器高度，单位为像素。

    返回值:
        str: 用户当前输入的代码。
    """
    st.caption(label)
    language = EDITOR_LANGUAGE_MAP.get(st.session_state.language, "python")
    content_key = f"{key}_content"
    seed_key = f"{key}_seed"
    if content_key not in st.session_state:
        st.session_state[content_key] = value
    elif st.session_state.get(seed_key) != value and not st.session_state[content_key].strip():
        st.session_state[content_key] = value
    st.session_state[seed_key] = value

    code = st_ace(
        value=st.session_state[content_key],
        language=language,
        theme="github",
        key=key,
        height=height,
        font_size=14,
        tab_size=4,
        show_gutter=True,
        show_print_margin=False,
        wrap=False,
        auto_update=True,
        placeholder="在这里输入代码。",
    )
    if code is not None:
        st.session_state[content_key] = code
    return st.session_state[content_key]


def render_solution_code_editor(problem: Problem, session: Session, height: int) -> str:
    """渲染答题代码编辑器。

    参数:
        problem: 当前题目。
        session: 当前训练会话。
        height: 编辑器高度，单位为像素。

    返回值:
        str: 用户当前输入的函数体或完整代码。
    """
    if is_python_body_mode_available(problem, session.language):
        signature = get_python_function_signature(problem)
        st.caption("函数签名")
        st.code(f"class Solution:\n    {signature}", language="python")
        body_code = extract_python_body_code(problem, session.current_code or "")
        return render_code_editor(
            "函数体",
            body_code,
            f"submission_body_{session.session_id}",
            height,
        )

    return render_code_editor(
        "最终代码",
        session.current_code or "",
        f"submission_code_{session.session_id}",
        height,
    )


def render_llm_status(agent: TrainingAgent) -> None:
    """渲染 LLM 配置和调用状态。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    st.subheader("LLM 状态")
    if agent.llm.available:
        st.success(agent.llm.status_message)
    else:
        st.warning(agent.llm.status_message)

    st.caption(f"配置文件: {agent.llm.config_path}")
    if agent.llm.base_url:
        st.caption(f"Base URL: {agent.llm.base_url}")
    if agent.llm.last_error:
        st.caption(f"最近错误: {agent.llm.last_error}")

    if st.button("重新加载 LLM 配置"):
        get_agent.clear()
        st.rerun()


def render_training_controls(agent: TrainingAgent, session: Session) -> None:
    """渲染思路、问题输入区。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    st.subheader("输入思路或问题")
    input_type = st.radio(
        "输入类型",
        ["thought", "question"],
        horizontal=True,
        key=f"training_input_type_{session.session_id}",
    )
    content = st.text_area(
        "内容",
        height=180,
        placeholder="写下你的解题思路或问题。",
        key=f"training_text_{session.session_id}",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存输入"):
            if content.strip():
                session = agent.add_user_message(session, input_type, content.strip())
                st.session_state.session = session
                st.rerun()
            else:
                st.warning("请输入内容。")

    with col2:
        if st.button("请求提示"):
            session, profile, hint = agent.generate_hint(session)
            st.session_state.session = session
            st.session_state.last_hint = hint
            st.session_state.last_used_skills = hint.get("used_skills", [])
            st.rerun()

    if st.session_state.last_hint:
        hint = st.session_state.last_hint
        render_used_skills(hint.get("used_skills", []))
        render_llm_call_status(agent)
        request_count = hint.get("hint_request_count", len(session.hints_given))
        st.info(f"第 {request_count} 次提示 · Level {hint['hint_level']}: {hint['hint']}")


def render_submission(agent: TrainingAgent, session: Session) -> None:
    """渲染最终代码提交与复盘结果。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    problem = agent.get_problem(session.problem_id)
    st.subheader("答题代码")
    code = render_solution_code_editor(problem, session, 440)
    session.current_code = code
    st.session_state.session = session
    if st.button("提交并复盘", type="primary"):
        session, profile, review = agent.review_submission(session, code)
        st.session_state.session = session
        st.session_state.last_review = review
        st.session_state.last_used_skills = review.used_skills
        st.rerun()

    if st.session_state.last_review:
        render_llm_call_status(agent)
        st.markdown(format_review(st.session_state.last_review))


def render_used_skills(used_skills: list[str]) -> None:
    """渲染本次 LLM 调用实际使用的 Skill 名称。

    参数:
        used_skills: 已加载的 Skill 名称列表。

    返回值:
        无。
    """
    if used_skills:
        st.caption(f"已使用 skill: {', '.join(used_skills)}")
    else:
        st.caption("未加载额外 skill")


def render_llm_call_status(agent: TrainingAgent) -> None:
    """渲染最近一次 LLM 调用状态。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    if agent.llm.last_error:
        st.caption(f"LLM 未使用或调用失败: {agent.llm.last_error}")
    elif agent.llm.available:
        st.caption("LLM 已参与本次生成。")
    if agent.llm.last_used_tools:
        st.caption(f"已调用工具: {', '.join(agent.llm.last_used_tools)}")


def main() -> None:
    """运行 Streamlit 应用主流程。

    参数:
        无。

    返回值:
        无。
    """
    st.set_page_config(page_title="LeetCode Training Agent", layout="wide")
    init_state()
    agent = get_agent()
    render_sidebar(agent)

    st.title("LeetCode Training Agent")
    if st.session_state.load_error:
        st.error(st.session_state.load_error)

    session = ensure_session(agent)
    if session is None:
        st.info("请在左侧从本地题库选择一道题，然后点击“开始这道题”。")
        return

    left, right = st.columns([1.05, 0.95])
    with left:
        render_problem(agent, session)
        render_chat_history(session)

    with right:
        render_submission(agent, session)
        render_training_controls(agent, session)


if __name__ == "__main__":
    main()
