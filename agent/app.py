from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.formatting import format_profile, format_problem, format_review
from src.models import Session
from src.training_agent import TrainingAgent


PROJECT_DIR = Path(__file__).resolve().parent


@st.cache_resource
def get_agent() -> TrainingAgent:
    return TrainingAgent(PROJECT_DIR)


def init_state() -> None:
    st.session_state.setdefault("user_id", "demo")
    st.session_state.setdefault("language", "Python")
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("leetcode_input", "two-sum")
    st.session_state.setdefault("loaded_problem_id", None)
    st.session_state.setdefault("last_review", None)
    st.session_state.setdefault("last_hint", None)
    st.session_state.setdefault("load_error", None)


def render_sidebar(agent: TrainingAgent) -> None:
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
                st.session_state.load_error = None
                st.rerun()
            except Exception as exc:
                st.session_state.load_error = str(exc)

        st.divider()
        profile = agent.get_profile(st.session_state.user_id)
        st.subheader("失误画像")
        st.text(format_profile(profile))


def ensure_session(agent: TrainingAgent) -> Session:
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
    problem = agent.get_problem(session.problem_id)
    st.markdown(format_problem(problem))


def render_chat_history(session: Session) -> None:
    if not session.messages:
        return
    st.subheader("会话记录")
    for message in session.messages:
        with st.chat_message(message.role):
            st.markdown(f"**{message.type}**")
            st.write(message.content)


def render_training_controls(agent: TrainingAgent, session: Session) -> None:
    st.subheader("输入思路或代码")
    input_type = st.radio("输入类型", ["thought", "question", "code"], horizontal=True)
    content = st.text_area(
        "内容",
        height=180,
        placeholder="写下你的解题思路、问题，或者粘贴代码。",
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
            st.rerun()

    if st.session_state.last_hint:
        hint = st.session_state.last_hint
        st.info(f"Level {hint['hint_level']}: {hint['hint']}")


def render_submission(agent: TrainingAgent, session: Session) -> None:
    st.subheader("提交代码")
    default_code = session.current_code or ""
    code = st.text_area("最终代码", value=default_code, height=260)
    if st.button("提交并复盘", type="primary"):
        session, profile, review = agent.review_submission(session, code)
        st.session_state.session = session
        st.session_state.last_review = review
        st.rerun()

    if st.session_state.last_review:
        st.markdown(format_review(st.session_state.last_review))


def main() -> None:
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
