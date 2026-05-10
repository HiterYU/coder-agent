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
MESSAGE_TYPE_LABELS = {
    "thought": "思路",
    "question": "问题",
    "code": "代码",
    "hint": "提示",
    "review": "复盘",
    "note": "备注",
}
SESSION_STATUS_LABELS = {
    "reading": "读题",
    "thinking": "思考",
    "coding": "编码",
    "debugging": "调试",
    "submitted": "已提交",
    "reviewed": "已复盘",
    "completed": "已完成",
}
SIDEBAR_DIALOG_MESSAGE_TYPES = {"thought", "question", "hint"}


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


def directory_problem_option_label(problem: dict) -> str:
    """生成 LeetCode 目录题目选项展示文案。

    参数:
        problem: LeetCode 目录缓存中的题目摘要。

    返回值:
        str: 包含题号、标题、难度和标签的展示文案。
    """
    leetcode_id = f"{problem.get('leetcode_id')}. " if problem.get("leetcode_id") else ""
    title = problem.get("title_cn") or problem.get("title") or problem.get("id")
    tags = [
        tag.get("name_translated") or tag.get("name") or tag.get("slug")
        for tag in problem.get("tags", [])[:3]
    ]
    tag_text = " / ".join(tag for tag in tags if tag) or "未标注"
    paid_text = " · 付费" if problem.get("paid_only") else ""
    return f"{leetcode_id}{title} · {tag_text}{paid_text}"


def difficulty_display(difficulty: str | None) -> str:
    """生成难度展示文案。

    参数:
        difficulty: 题目难度。

    返回值:
        str: 中英文组合的难度展示文案。
    """
    normalized = normalize_difficulty(difficulty)
    labels = {
        "Easy": "Easy / 简单",
        "Medium": "Medium / 中等",
        "Hard": "Hard / 困难",
    }
    return labels.get(normalized, normalized or "Unknown")


def normalize_difficulty(difficulty: str | None) -> str:
    """标准化题目难度。

    参数:
        difficulty: 题目难度。

    返回值:
        str: Easy、Medium、Hard 或原值。
    """
    value = str(difficulty or "").strip()
    difficulty_map = {
        "EASY": "Easy",
        "Easy": "Easy",
        "简单": "Easy",
        "MEDIUM": "Medium",
        "Medium": "Medium",
        "中等": "Medium",
        "HARD": "Hard",
        "Hard": "Hard",
        "困难": "Hard",
    }
    return difficulty_map.get(value, value)


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


def message_type_label(message_type: str) -> str:
    """获取会话消息类型的中文展示名称。

    参数:
        message_type: 会话消息类型。

    返回值:
        str: 中文展示名称，未知类型返回原值。
    """
    return MESSAGE_TYPE_LABELS.get(message_type, message_type)


def session_status_label(session: Session) -> str:
    """获取训练会话状态的中文展示名称。

    参数:
        session: 当前训练会话。

    返回值:
        str: 中文状态名称，未知状态返回原值。
    """
    status = getattr(session.status, "value", str(session.status))
    return SESSION_STATUS_LABELS.get(status, status)


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
    languages = ["Python", "JavaScript", "Java", "C++"]
    language_index = languages.index(st.session_state.language)
    st.session_state.language = st.selectbox("语言", languages, index=language_index)
    st.caption("选题统一在主区域“题库”页面完成。")
    if st.button("打开题库", use_container_width=True):
        st.session_state.active_page = "bank"
        st.rerun()

    st.divider()
    st.subheader("LeetCode 抓题")
    st.caption(
        "输入 leetcode.cn / leetcode.com 题目 URL 或 titleSlug。"
        "抓到后会缓存到 .runtime/problems，并立即开始这道题。"
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
            "选中某一道题并抓详情后，才会写入 .runtime/problems。"
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
            ["全部", "Easy", "Medium", "Hard"],
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


def render_problem_bank_page(agent: TrainingAgent) -> None:
    """渲染题库页面。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    st.title("题库")
    local_problems = agent.list_problems()
    cached_problem_ids = {problem.id for problem in local_problems}
    directory_cache = agent.get_cached_leetcode_directory()
    directory_items = directory_cache.get("items", [])

    st.caption(
        f"本地题目缓存 {len(local_problems)} 题 · "
        f"LeetCode 目录索引 {len(directory_items)} 题"
    )
    directory_tab, local_tab = st.tabs(["LeetCode 目录索引", "本地题目缓存"])

    with directory_tab:
        render_leetcode_directory_bank(agent, directory_cache, cached_problem_ids)
    with local_tab:
        render_local_problem_bank(agent, local_problems)


def render_leetcode_directory_bank(
    agent: TrainingAgent,
    directory_cache: dict,
    cached_problem_ids: set[str],
) -> None:
    """渲染 LeetCode 目录索引题库。

    参数:
        agent: 训练 Agent 实例。
        directory_cache: 最近一次缓存的 LeetCode 目录摘要。
        cached_problem_ids: 已缓存详情的题目 ID 集合。

    返回值:
        无。
    """
    directory_items = directory_cache.get("items", [])
    if not directory_items:
        st.info("还没有目录索引。请先在左侧“题目”页签里点击“抓目录索引”。")
        return

    col1, col2, col3 = st.columns([1.4, 0.8, 0.8])
    with col1:
        st.session_state.bank_directory_search = st.text_input(
            "搜索目录",
            st.session_state.bank_directory_search,
            placeholder="题号、标题、slug 或标签",
        )
    with col2:
        directory_difficulty = st.selectbox(
            "难度",
            ["全部", "Easy", "Medium", "Hard"],
            key="bank_directory_difficulty",
        )
    with col3:
        only_uncached = st.checkbox("只看未缓存", value=False)

    filtered_items = filter_directory_items(
        directory_items,
        st.session_state.bank_directory_search,
        "" if directory_difficulty == "全部" else directory_difficulty,
        only_uncached,
        cached_problem_ids,
    )
    st.caption(
        f"目录来源: {directory_cache.get('category_slug', 'unknown')} · "
        f"扫描 {directory_cache.get('scanned', 0)} 题 · "
        f"当前匹配 {len(filtered_items)} 题"
    )

    if not filtered_items:
        st.warning("没有匹配的目录题目。")
        return

    display_count = min(len(filtered_items), 50)
    st.caption(f"显示前 {display_count} 题。缩小搜索条件可以定位更多结果。")
    for index, item in enumerate(filtered_items[:display_count]):
        render_directory_problem_row(agent, item, cached_problem_ids, index)


def render_local_problem_bank(agent: TrainingAgent, problems: list[Problem]) -> None:
    """渲染本地缓存题库。

    参数:
        agent: 训练 Agent 实例。
        problems: 本地缓存和内置题目列表。

    返回值:
        无。
    """
    if not problems:
        st.info("本地还没有题目。可以先从 LeetCode 目录里选择一题抓详情。")
        return

    col1, col2 = st.columns([1.4, 0.8])
    with col1:
        st.session_state.bank_local_search = st.text_input(
            "搜索本地缓存",
            st.session_state.bank_local_search,
            placeholder="题号、标题、slug 或标签",
        )
    with col2:
        local_difficulty = st.selectbox(
            "难度",
            ["全部", "Easy", "Medium", "Hard"],
            key="bank_local_difficulty",
        )

    filtered_problems = filter_local_problems(
        problems,
        st.session_state.bank_local_search,
        "" if local_difficulty == "全部" else local_difficulty,
    )
    st.caption(f"当前匹配 {len(filtered_problems)} 题")
    for index, problem in enumerate(filtered_problems[:50]):
        render_local_problem_row(agent, problem, index)


def filter_directory_items(
    items: list[dict],
    query: str,
    difficulty: str,
    only_uncached: bool,
    cached_problem_ids: set[str],
) -> list[dict]:
    """过滤 LeetCode 目录题目。

    参数:
        items: 目录题目摘要列表。
        query: 搜索关键词。
        difficulty: 可选难度过滤。
        only_uncached: 是否只看未缓存详情的题目。
        cached_problem_ids: 已缓存详情的题目 ID 集合。

    返回值:
        list[dict]: 过滤后的目录题目摘要列表。
    """
    normalized_query = query.strip().lower()
    filtered = []
    for item in items:
        problem_id = str(item.get("id") or "")
        if difficulty and normalize_difficulty(item.get("difficulty")) != difficulty:
            continue
        if only_uncached and problem_id in cached_problem_ids:
            continue
        if normalized_query and normalized_query not in directory_item_search_text(item):
            continue
        filtered.append(item)
    return filtered


def filter_local_problems(problems: list[Problem], query: str, difficulty: str) -> list[Problem]:
    """过滤本地题目列表。

    参数:
        problems: 本地题目列表。
        query: 搜索关键词。
        difficulty: 可选难度过滤。

    返回值:
        list[Problem]: 过滤后的本地题目列表。
    """
    normalized_query = query.strip().lower()
    filtered = []
    for problem in problems:
        if difficulty and problem.difficulty != difficulty:
            continue
        if normalized_query and normalized_query not in local_problem_search_text(problem):
            continue
        filtered.append(problem)
    return filtered


def render_directory_problem_row(
    agent: TrainingAgent,
    item: dict,
    cached_problem_ids: set[str],
    index: int,
) -> None:
    """渲染 LeetCode 目录题目行。

    参数:
        agent: 训练 Agent 实例。
        item: 目录题目摘要。
        cached_problem_ids: 已缓存详情的题目 ID 集合。
        index: 当前行序号，用于生成组件 key。

    返回值:
        无。
    """
    problem_id = str(item.get("id") or "")
    is_cached = problem_id in cached_problem_ids
    with st.container(border=True):
        title_col, difficulty_col, meta_col, action_col = st.columns([2.1, 0.75, 1, 0.9])
        with title_col:
            st.markdown(f"**{directory_problem_option_label(item)}**")
            st.caption(problem_id)
        with difficulty_col:
            st.markdown(f"**{difficulty_display(item.get('difficulty'))}**")
        with meta_col:
            cache_text = "已缓存详情" if is_cached else "仅目录索引"
            ac_rate = item.get("ac_rate")
            ac_rate_text = f" · 通过率 {ac_rate:.1f}%" if isinstance(ac_rate, (int, float)) else ""
            st.caption(f"{cache_text}{ac_rate_text}")
        with action_col:
            if st.button(
                "进入做题",
                key=f"directory_problem_{problem_id}_{index}",
                use_container_width=True,
            ):
                start_directory_problem(agent, problem_id, is_cached)


def render_local_problem_row(agent: TrainingAgent, problem: Problem, index: int) -> None:
    """渲染本地题目行。

    参数:
        agent: 训练 Agent 实例。
        problem: 本地题目。
        index: 当前行序号，用于生成组件 key。

    返回值:
        无。
    """
    with st.container(border=True):
        title_col, difficulty_col, meta_col, action_col = st.columns([2.1, 0.75, 1, 0.9])
        with title_col:
            leetcode_prefix = f"{problem.leetcode_id}. " if problem.leetcode_id else ""
            st.markdown(f"**{leetcode_prefix}{problem.title}**")
            st.caption(problem.id)
        with difficulty_col:
            st.markdown(f"**{difficulty_display(problem.difficulty)}**")
        with meta_col:
            tag_text = " / ".join(problem.tags[:3]) if problem.tags else "未标注"
            st.caption(f"已缓存详情 · {tag_text}")
        with action_col:
            if st.button(
                "开始",
                key=f"local_problem_{problem.id}_{index}",
                use_container_width=True,
            ):
                start_problem_session(agent, problem.id)
                st.session_state.active_page = "practice"
                st.rerun()


def start_directory_problem(agent: TrainingAgent, problem_id: str, is_cached: bool) -> None:
    """从目录题目进入做题页，必要时先抓详情并缓存。

    参数:
        agent: 训练 Agent 实例。
        problem_id: LeetCode titleSlug。
        is_cached: 题目详情是否已经在本地缓存。

    返回值:
        无。
    """
    if is_cached:
        start_problem_session(agent, problem_id)
    else:
        problem = agent.fetch_problem_from_leetcode(
            f"https://leetcode.cn/problems/{problem_id}/"
        )
        start_problem_session(agent, problem.id)
        st.session_state.last_import_message = (
            f"已缓存 {problem.leetcode_id or problem.id}. {problem.title}"
        )
    st.session_state.active_page = "practice"
    st.rerun()


def directory_item_search_text(item: dict) -> str:
    """生成 LeetCode 目录题目搜索文本。

    参数:
        item: 目录题目摘要。

    返回值:
        str: 小写搜索文本。
    """
    parts = [
        str(item.get("leetcode_id") or ""),
        str(item.get("id") or ""),
        str(item.get("title") or ""),
        str(item.get("title_cn") or ""),
        normalize_difficulty(item.get("difficulty")),
    ]
    for tag in item.get("tags", []):
        parts.extend(
            [
                str(tag.get("name") or ""),
                str(tag.get("name_translated") or ""),
                str(tag.get("slug") or ""),
            ]
        )
    return " ".join(parts).lower()


def local_problem_search_text(problem: Problem) -> str:
    """生成本地题目搜索文本。

    参数:
        problem: 本地题目。

    返回值:
        str: 小写搜索文本。
    """
    parts = [
        problem.id,
        str(problem.leetcode_id or ""),
        problem.title,
        problem.difficulty,
        " ".join(problem.tags),
        problem.description,
    ]
    return " ".join(parts).lower()


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

    render_workspace_header(agent, session)
    left, right = st.columns([0.95, 1.05])
    with left:
        with st.container(border=True):
            render_problem(agent, session)

    with right:
        with st.container(border=True):
            render_submission(agent, session)


if __name__ == "__main__":
    main()
