from __future__ import annotations

# 文件用途：渲染侧边栏训练面板，包括题目设置、训练对话和状态展示。

import streamlit as st

from src.formatting import format_profile
from src.models import Session
from src.training_agent import TrainingAgent

from .constants import DIFFICULTY_FILTER_OPTIONS, SIDEBAR_DIALOG_MESSAGE_TYPES, SUPPORTED_LANGUAGES
from .formatters import message_type_label, session_status_label
from .llm_status import render_llm_status, render_used_skills
from .state import start_problem_session


def render_sidebar(agent: TrainingAgent, session: Session | None) -> None:
    """渲染侧边栏训练设置、提示对话和状态信息。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话；未加载题目时为 None。

    返回值:
        无。
    """
    with st.sidebar:
        st.header("训练面板")
        page_options = {"做题": "practice", "题库": "bank"}
        if st.session_state.active_page not in page_options.values():
            st.session_state.active_page = "practice"
        current_page_label = next(
            label
            for label, page in page_options.items()
            if page == st.session_state.active_page
        )
        selected_page_label = st.radio(
            "页面",
            list(page_options),
            index=list(page_options).index(current_page_label),
            horizontal=True,
        )
        st.session_state.active_page = page_options[selected_page_label]
        setup_tab, dialog_tab, status_tab = st.tabs(["题目", "对话", "状态"])
        with setup_tab:
            render_problem_setup(agent)
        with dialog_tab:
            render_training_dialog(agent, session)
        with status_tab:
            render_status_panel(agent)


def render_problem_setup(agent: TrainingAgent) -> None:
    """渲染侧边栏题目与语言设置。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    st.subheader("题目设置")
    st.session_state.user_id = st.text_input("用户 ID", st.session_state.user_id)
    language_index = SUPPORTED_LANGUAGES.index(st.session_state.language)
    st.session_state.language = st.selectbox("语言", SUPPORTED_LANGUAGES, index=language_index)
    st.caption("选题统一在主区域“题库”页面完成。")
    if st.button("打开题库", use_container_width=True):
        st.session_state.active_page = "bank"
        st.rerun()

    st.divider()
    st.subheader("LeetCode 抓题")
    st.caption(
        "输入 leetcode.cn / leetcode.com 题目 URL 或 titleSlug。"
        "抓到后会缓存到 projects/agent.db，并立即开始这道题。"
    )
    st.session_state.leetcode_input = st.text_input(
        "题目 URL 或 titleSlug",
        st.session_state.leetcode_input,
        placeholder="https://leetcode.cn/problems/two-sum/ 或 two-sum",
    )

    if st.button("抓题并开始", use_container_width=True):
        try:
            problem = agent.fetch_problem_from_leetcode(st.session_state.leetcode_input)
            start_problem_session(agent, problem.id)
            st.session_state.last_import_message = (
                f"已缓存 {problem.leetcode_id or problem.id}. {problem.title}"
            )
            st.rerun()
        except Exception as exc:
            st.session_state.load_error = str(exc)

    if st.session_state.last_import_message:
        st.success(st.session_state.last_import_message)

    with st.expander("抓目录索引"):
        st.caption(
            "只缓存 LeetCode 中国站题目目录摘要，不抓题面详情。"
            "选中某一道题并抓详情后，才会写入 projects/agent.db。"
        )
        directory_limit = st.number_input(
            "最多索引题数",
            min_value=1,
            max_value=3000,
            value=20,
            step=10,
        )
        directory_difficulty = st.selectbox(
            "抓取难度",
            DIFFICULTY_FILTER_OPTIONS,
        )
        include_paid = st.checkbox("包含付费题", value=False)
        if st.button("抓目录索引", use_container_width=True):
            try:
                result = agent.fetch_problem_directory_from_leetcode(
                    limit=int(directory_limit),
                    include_paid=include_paid,
                    difficulty="" if directory_difficulty == "全部" else directory_difficulty,
                )
                st.session_state.last_directory_import_result = result
                st.session_state.last_import_message = (
                    f"目录索引已缓存：扫描 {result['scanned']} 题，记录 {result['selected']} 题。"
                )
                st.session_state.active_page = "bank"
                st.rerun()
            except Exception as exc:
                st.session_state.load_error = str(exc)

        directory_cache = st.session_state.last_directory_import_result
        if not directory_cache:
            directory_cache = agent.get_cached_leetcode_directory()
        directory_items = directory_cache.get("items", [])
        if directory_items:
            st.caption(
                f"当前目录索引: 扫描 {directory_cache['scanned']} 题，"
                f"记录 {directory_cache['selected']} 题。"
            )
            if st.button("去题库选题", use_container_width=True):
                st.session_state.active_page = "bank"
                st.rerun()

    with st.expander("抓题内容说明"):
        st.markdown(
            "- 单题抓取：题号、标题、难度、标签、题面、样例、约束、Python 模板和函数签名。\n"
            "- 不抓提交记录、个人通过状态、官方题解或评论。\n"
            "- 目录索引只保存题号、标题、slug、难度、通过率和标签；不会缓存题面详情。\n"
            "- 真正写入题目详情缓存的是你输入或从目录选中并点击抓详情的那一道题。"
        )


def render_training_dialog(agent: TrainingAgent, session: Session | None) -> None:
    """渲染侧边栏思路、问题和提示对话面板。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话；未加载题目时为 None。

    返回值:
        无。
    """
    st.subheader("训练对话")
    if session is None:
        st.info("开始一道题后，可以在这里记录思路、提问并获取提示。")
        return

    st.caption(
        f"{session_status_label(session)} · {session.language} · "
        f"已请求 {len(session.hints_given)} 次提示"
    )
    hint_messages = [
        message
        for message in session.messages
        if message.type in SIDEBAR_DIALOG_MESSAGE_TYPES
    ]
    with st.container(height=360, border=True):
        if not hint_messages:
            st.caption("记录思路，提出问题，或直接请求下一条递进提示。")
        for message in hint_messages[-12:]:
            with st.chat_message(message.role):
                st.caption(message_type_label(message.type))
                st.markdown(message.content)

    with st.form(f"hint_dialog_form_{session.session_id}", clear_on_submit=True):
        input_type = st.radio(
            "输入类型",
            ["thought", "question"],
            horizontal=True,
            format_func=message_type_label,
            key=f"sidebar_dialog_type_{session.session_id}",
        )
        dialog_content = st.text_area(
            "内容",
            height=96,
            placeholder="写思路会保存到对话；写问题会同时生成一条提示回复。",
        )
        send_message = st.form_submit_button(
            "发送",
            type="primary",
            use_container_width=True,
        )

    if send_message:
        if not dialog_content.strip():
            st.warning("请输入思路或问题。")
            return
        if input_type == "question":
            request_hint(agent, session, dialog_content.strip())
        else:
            session = agent.add_user_message(session, "thought", dialog_content.strip())
            st.session_state.session = session
        st.rerun()

    if st.button(
        "直接请求下一条提示",
        use_container_width=True,
        key=f"next_hint_{session.session_id}",
    ):
        request_hint(agent, session)
        st.rerun()

    if st.session_state.last_hint:
        hint = st.session_state.last_hint
        request_count = hint.get("hint_request_count", len(session.hints_given))
        st.caption(f"最近提示: 第 {request_count} 次 · Level {hint['hint_level']}")
        render_used_skills(hint.get("used_skills", []))


def request_hint(
    agent: TrainingAgent,
    session: Session,
    user_question: str | None = None,
) -> None:
    """按需追加追问并生成下一条提示。

    参数:
        agent: 训练 Agent 实例。
        session: 当前训练会话。
        user_question: 用户在提示对话中的追问；为空时只生成下一条提示。

    返回值:
        无。
    """
    if user_question:
        session = agent.add_user_message(session, "question", user_question)
    session, profile, hint = agent.generate_hint(session)
    st.session_state.session = session
    st.session_state.last_hint = hint
    st.session_state.last_used_skills = hint.get("used_skills", [])


def render_status_panel(agent: TrainingAgent) -> None:
    """渲染侧边栏 LLM 状态和用户画像。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    render_llm_status(agent)
    st.divider()
    profile = agent.get_profile(st.session_state.user_id)
    st.subheader("失误画像")
    st.text(format_profile(profile))
