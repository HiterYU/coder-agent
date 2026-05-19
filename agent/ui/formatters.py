from __future__ import annotations

# 文件用途：UI 层的标签、难度、搜索文本等纯展示格式化函数。

from src.models import Problem, Session

from .constants import MESSAGE_TYPE_LABELS, SESSION_STATUS_LABELS


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
