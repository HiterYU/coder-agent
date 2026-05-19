from __future__ import annotations

# 文件用途：集中处理 Streamlit 会话状态与训练 Agent 缓存。

import streamlit as st

from src.training_agent import TrainingAgent

from .constants import PROJECT_DIR


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
    st.session_state.setdefault("last_import_message", None)
    st.session_state.setdefault("last_directory_import_result", None)
    st.session_state.setdefault("active_page", "practice")
    st.session_state.setdefault("bank_directory_search", "")
    st.session_state.setdefault("bank_local_search", "")


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
    st.session_state.last_import_message = None
    st.session_state.last_directory_import_result = None


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


def ensure_session(agent: TrainingAgent):
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
