from __future__ import annotations

# 文件用途：渲染做题主区，包括题目展示、答题代码编辑与提交复盘。

import streamlit as st

from src.formatting import format_problem, format_review
from src.models import Session
from src.training_agent import TrainingAgent

from ..code_editor import render_solution_code_editor
from ..formatters import session_status_label
from ..llm_status import render_llm_call_status


def render_workspace_header(agent: TrainingAgent, session: Session) -> None:
    """渲染主工作区标题和当前会话摘要。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    problem = agent.get_problem(session.problem_id)
    leetcode_prefix = f"{problem.leetcode_id}. " if problem.leetcode_id else ""
    tags = " / ".join(problem.tags[:3]) if problem.tags else "未标注"
    st.title("LeetCode Training Agent")
    st.caption(
        f"当前题目: {leetcode_prefix}{problem.title} · {problem.difficulty} · "
        f"{tags} · {session.language} · {session_status_label(session)} · "
        f"提示 {len(session.hints_given)} 次"
    )


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


def render_practice_page(agent: TrainingAgent, session: Session) -> None:
    """渲染做题页面整体布局。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。

    返回值:
        无。
    """
    render_workspace_header(agent, session)
    left, right = st.columns([0.95, 1.05])
    with left:
        with st.container(border=True):
            render_problem(agent, session)
    with right:
        with st.container(border=True):
            render_submission(agent, session)
