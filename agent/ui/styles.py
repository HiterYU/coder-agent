from __future__ import annotations

# 文件用途：集中注入 Streamlit 全局样式。

import streamlit as st


def inject_ui_styles() -> None:
    """注入页面级样式，压缩顶部留白并优化侧边栏页签间距。

    参数:
        无。

    返回值:
        无。
    """
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 1360px;
            padding-top: 1.25rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] [data-baseweb="tab-list"] {
            gap: 0.25rem;
        }
        [data-testid="stSidebar"] [data-baseweb="tab"] {
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.65rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
