from __future__ import annotations

# 文件用途：Streamlit UI 入口，仅负责整体路由与页面级状态。

import streamlit as st

from ui.pages.practice import render_practice_page
from ui.pages.problem_bank import render_problem_bank_page
from ui.sidebar import render_sidebar
from ui.state import ensure_session, get_agent, init_state
from ui.styles import inject_ui_styles


def main() -> None:
    """运行 Streamlit 应用主流程。

    参数:
        无。

    返回值:
        无。
    """
    st.set_page_config(page_title="LeetCode Training Agent", layout="wide")
    init_state()
    inject_ui_styles()
    agent = get_agent()
    session = ensure_session(agent)
    render_sidebar(agent, session)

    if st.session_state.load_error:
        st.error(st.session_state.load_error)

    if st.session_state.active_page == "bank":
        render_problem_bank_page(agent)
        return

    if session is None:
        st.title("LeetCode Training Agent")
        st.info("请切到“题库”页面选择一道题，或在左侧抓取 LeetCode 题目。")
        return

    render_practice_page(agent, session)


if __name__ == "__main__":
    main()
