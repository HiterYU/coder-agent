from __future__ import annotations

# 文件用途：渲染题库页面，包括 LeetCode 目录索引和本地题目缓存。

import streamlit as st

from src.models import Problem
from src.training_agent import TrainingAgent

from ..constants import DIFFICULTY_FILTER_OPTIONS
from ..formatters import (
    difficulty_display,
    directory_item_search_text,
    directory_problem_option_label,
    local_problem_search_text,
    normalize_difficulty,
)
from ..state import start_problem_session


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
            DIFFICULTY_FILTER_OPTIONS,
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
            DIFFICULTY_FILTER_OPTIONS,
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
