from __future__ import annotations

# 文件用途：封装 Streamlit 代码编辑器与 Python 答题代码模板拼接。

import streamlit as st
from streamlit_ace import st_ace

from src.code_templates import (
    extract_python_body_code,
    get_python_function_signature,
    is_python_body_mode_available,
)
from src.models import Problem, Session

from .constants import EDITOR_LANGUAGE_MAP


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


def looks_like_python_solution_code(problem: Problem, code: str) -> bool:
    """判断代码是否已经包含可提交的 Python 结构。

    参数:
        problem: 当前题目。
        code: 当前编辑器或会话中的代码。

    返回值:
        bool: 包含 Solution 类或顶层函数定义时返回 True。
    """
    normalized = code.replace("\r\n", "\n")
    function_name = problem.function_name
    return (
        "class Solution" in normalized
        or bool(function_name and f"def {function_name}(" in normalized)
    )


def indent_python_body_code(code: str) -> str:
    """为函数体代码补齐 class 和 def 下的缩进。

    参数:
        code: 旧版函数体代码。

    返回值:
        str: 增加 8 个空格缩进后的函数体代码。
    """
    return "\n".join(
        f"        {line}" if line.strip() else ""
        for line in code.splitlines()
    )


def build_python_solution_code(problem: Problem, code: str) -> str:
    """构造包含类名、函数签名和函数体的 Python 编辑器初始代码。

    参数:
        problem: 当前题目。
        code: 会话中已有的完整代码或旧版函数体代码。

    返回值:
        str: 可直接放入代码编辑器的 Python 代码。
    """
    if code.strip() and looks_like_python_solution_code(problem, code):
        return code

    signature = get_python_function_signature(problem)
    body_code = extract_python_body_code(problem, code)
    if not body_code.strip():
        body_code = "pass"
    indented_body = indent_python_body_code(body_code)
    return f"class Solution:\n    {signature}\n{indented_body}"


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
        solution_code = build_python_solution_code(problem, session.current_code or "")
        return render_code_editor(
            "答题代码",
            solution_code,
            f"submission_code_{session.session_id}",
            height,
        )

    return render_code_editor(
        "最终代码",
        session.current_code or "",
        f"submission_code_{session.session_id}",
        height,
    )
