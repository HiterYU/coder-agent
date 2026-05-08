from __future__ import annotations

# 文件用途：将题目、复盘和用户画像格式化为 Streamlit 可渲染文本。

from .models import Problem, ReviewResult, UserProfile
from .taxonomy import MISTAKE_TAXONOMY


def format_problem(problem: Problem) -> str:
    """格式化题目详情。

    参数:
        problem: 题目数据。

    返回值:
        str: Markdown 格式的题目详情。
    """
    examples = "\n\n".join(
        f"Input: {example.input}\nOutput: {example.output}\n{example.explanation}"
        for example in problem.examples
    )
    constraints = "\n".join(f"- {item}" for item in problem.constraints)
    return (
        f"### {problem.title}\n\n"
        f"Difficulty: {problem.difficulty}\n\n"
        f"Tags: {', '.join(problem.tags)}\n\n"
        f"{problem.description}\n\n"
        f"#### Examples\n\n{examples}\n\n"
        f"#### Constraints\n\n{constraints}"
    )


def format_review(review: ReviewResult) -> str:
    """格式化复盘结果。

    参数:
        review: 结构化复盘结果。

    返回值:
        str: Markdown 格式的复盘内容。
    """
    mistakes = "\n".join(
        f"- {MISTAKE_TAXONOMY.get(mistake.type, mistake.type)} / {mistake.severity}: {mistake.evidence}"
        for mistake in review.mistakes
    )
    next_actions = "\n".join(f"- {item}" for item in review.next_actions)
    if not mistakes:
        mistakes = "- 暂未发现明确错误。"
    if not next_actions:
        next_actions = "- 用更多样例继续验证。"
    sample_results = "\n".join(
        (
            f"- 样例 {item.index}: {'通过' if item.passed else '失败'}"
            f"；期望 {item.expected}；实际 {item.actual or '无'}"
            f"{f'；错误 {item.error}' if item.error else ''}"
        )
        for item in review.sample_test_results
    )
    if not sample_results:
        sample_results = "- 未运行可执行样例。"
    used_skills = ", ".join(review.used_skills) if review.used_skills else "未加载额外 skill"
    return (
        f"**使用 Skill**: {used_skills}\n\n"
        f"**大概率正确**: {'是' if review.is_likely_correct else '否'}\n\n"
        f"**样例测试**: {'通过' if review.passed_sample_tests else '未通过或未运行'}\n\n"
        f"**样例结果**:\n{sample_results}\n\n"
        f"**时间复杂度**: {review.time_complexity}\n\n"
        f"**空间复杂度**: {review.space_complexity}\n\n"
        f"**反馈**: {review.feedback}\n\n"
        f"**错误记录**:\n{mistakes}\n\n"
        f"**下一步**:\n{next_actions}"
    )


def format_profile(profile: UserProfile) -> str:
    """格式化用户失误画像。

    参数:
        profile: 用户画像。

    返回值:
        str: 文本格式的用户画像摘要。
    """
    topic_profiles = []
    for item in sorted(
        profile.topic_mistake_profiles, key=lambda value: value.total_mistakes, reverse=True
    ):
        mistake_text = ", ".join(
            f"{mistake_type}={count}"
            for mistake_type, count in sorted(
                item.mistake_counts.items(), key=lambda value: value[1], reverse=True
            )
        )
        examples = ", ".join(item.example_problem_ids[:4])
        topic_profiles.append(
            f"- {item.topic}: total={item.total_mistakes}; {mistake_text}; examples={examples}"
        )

    mistakes = "\n".join(
        f"- {item.type}: {item.count} 次，样例题 {', '.join(item.example_problem_ids)}"
        for item in profile.common_mistakes
    )
    return (
        f"语言: {profile.language}\n\n"
        f"目标: {profile.goal}\n\n"
        f"已解决: {len(profile.solved_problem_ids)} 题\n\n"
        f"提示统计: total={profile.hint_stats.total_hints}, "
        f"avg_level={profile.hint_stats.average_hint_level}\n\n"
        f"不同题型失误画像:\n{chr(10).join(topic_profiles) or '- 暂无'}\n\n"
        f"常见错误:\n{mistakes or '- 暂无'}"
    )
