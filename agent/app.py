from __future__ import annotations

# 文件用途：Streamlit UI 入口，负责页面状态、布局与交互逻辑。

from pathlib import Path

import streamlit as st
from streamlit_ace import st_ace

from src.formatting import format_profile, format_problem, format_review
from src.models import Session
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
    st.session_state.setdefault("leetcode_input", "two-sum")
    st.session_state.setdefault("loaded_problem_id", None)
    st.session_state.setdefault("last_review", None)
    st.session_state.setdefault("last_hint", None)
    st.session_state.setdefault("last_used_skills", [])
    st.session_state.setdefault("load_error", None)


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
        st.session_state.language = st.selectbox(
            "语言", ["Python", "JavaScript", "Java", "C++"], index=0
        )

        st.session_state.leetcode_input = st.text_input(
            "LeetCode URL 或 slug",
            st.session_state.leetcode_input,
            placeholder="https://leetcode.com/problems/two-sum/ 或 two-sum",
        )

        if st.button("获取题目并开始", type="primary"):
            try:
                problem = agent.fetch_problem_from_leetcode(st.session_state.leetcode_input)
                st.session_state.loaded_problem_id = problem.id
                st.session_state.session = agent.create_session(
                    st.session_state.user_id,
                    problem.id,
                    st.session_state.language,
                )
                st.session_state.last_review = None
                st.session_state.last_hint = None
                st.session_state.last_used_skills = []
                st.session_state.load_error = None
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
    code = st_ace(
        value=value,
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
    return code if code is not None else value


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
    """渲染思路、问题和阶段性代码输入区。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    st.subheader("输入思路或代码")
    input_type = st.radio("输入类型", ["thought", "question", "code"], horizontal=True)
    if input_type == "code":
        content = render_code_editor(
            "内容",
            session.current_code or "",
            f"training_code_{session.session_id}",
            360,
        )
    else:
        content = st.text_area(
            "内容",
            height=220,
            placeholder="写下你的解题思路或问题。",
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
        st.info(f"Level {hint['hint_level']}: {hint['hint']}")


def render_submission(agent: TrainingAgent, session: Session) -> None:
    """渲染最终代码提交与复盘结果。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    st.subheader("提交代码")
    default_code = session.current_code or ""
    code = render_code_editor(
        "最终代码",
        default_code,
        f"submission_code_{session.session_id}",
        520,
    )
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
        st.info("请在左侧输入 LeetCode 题目 URL 或 slug，然后点击“获取题目并开始”。")
        return

    left, right = st.columns([1.05, 0.95])
    with left:
        render_problem(agent, session)
        render_chat_history(session)

    with right:
        render_training_controls(agent, session)
        render_submission(agent, session)


if __name__ == "__main__":
    main()
