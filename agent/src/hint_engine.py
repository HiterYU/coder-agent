from __future__ import annotations

from .llm_client import LlmClient
from .models import Problem, Session, UserProfile
from .taxonomy import normalize_topic


class HintEngine:
    def __init__(self, llm_client: LlmClient | None = None):
        self.llm = llm_client or LlmClient()

    def generate_hint(self, session: Session, problem: Problem, profile: UserProfile) -> dict:
        hint_level = self._next_hint_level(session)
        llm_hint = self._generate_llm_hint(session, problem, profile, hint_level)
        if llm_hint:
            return llm_hint

        hint = self._fallback_hint(problem, profile, hint_level)
        return {
            "hint_level": hint_level,
            "hint": hint,
            "why_this_hint": "根据当前提示等级、题目标签和用户历史错误生成。",
            "reveals_solution": hint_level >= 5,
        }

    def _next_hint_level(self, session: Session) -> int:
        if not session.hints_given:
            return 1
        return min(max(session.hints_given) + 1, 5)

    def _generate_llm_hint(
        self, session: Session, problem: Problem, profile: UserProfile, hint_level: int
    ) -> dict | None:
        if not self.llm.available:
            return None
        latest_message = session.messages[-1].content if session.messages else ""
        system = "你是一个 LeetCode 编程训练教练。你帮助用户独立解题，不要过早泄露答案。只输出 JSON。"
        user = f"""
题目:
{problem.model_dump_json(indent=2)}

用户画像:
{profile.model_dump_json(indent=2)}

当前会话:
{session.model_dump_json(indent=2)}

用户最近输入:
{latest_message}

目标提示等级: {hint_level}

要求:
1. Level 1-3 不给完整代码。
2. Level 4 可以给代码骨架。
3. Level 5 才能给完整题解。
4. 输出中文。

JSON 格式:
{{
  "hint_level": {hint_level},
  "hint": "...",
  "why_this_hint": "...",
  "reveals_solution": false
}}
"""
        data = self.llm.complete_json(system, user)
        if not data or "hint" not in data:
            return None
        data["hint_level"] = hint_level
        data.setdefault("why_this_hint", "LLM 根据会话上下文生成。")
        data.setdefault("reveals_solution", hint_level >= 5)
        return data

    def _fallback_hint(self, problem: Problem, profile: UserProfile, hint_level: int) -> str:
        primary_tag = problem.tags[0] if problem.tags else "题目"
        primary_topic = normalize_topic(primary_tag)
        approach = problem.expected_approaches[0] if problem.expected_approaches else None
        mistake = problem.common_mistakes[0] if problem.common_mistakes else None
        profile_warning = self._profile_warning(problem, profile)

        if hint_level == 1:
            if mistake:
                return f"先检查一个容易忽略的点：{mistake.description}。不要急着写完整代码，先确认题意边界。"
            return f"先把输入规模、边界条件和返回格式确认清楚。这题的主要标签是 {primary_tag}。"

        if hint_level == 2:
            direction = approach.summary if approach else f"从 {primary_tag} 的经典解法方向思考。"
            return f"{profile_warning}这题可以先考虑这个方向：{direction}"

        if hint_level == 3:
            if approach:
                return f"关键是定义好中间状态或维护量。当前推荐思路是 {approach.name}：{approach.summary}"
            return f"把每一步要维护的不变量写出来，尤其注意 {primary_topic} 相关的边界变化。"

        if hint_level == 4:
            return (
                "可以先写代码骨架：初始化必要变量，遍历输入，在循环里更新状态，最后返回结果。"
                "重点是每次更新前后都确认不变量是否仍然成立。"
            )

        if approach:
            return (
                f"完整方向：使用 {approach.name}。{approach.summary} "
                f"时间复杂度 {approach.time_complexity}，空间复杂度 {approach.space_complexity}。"
            )
        return "可以请求完整题解，但建议先把你的思路和当前代码贴出来，我会按代码中的具体问题复盘。"

    def _profile_warning(self, problem: Problem, profile: UserProfile) -> str:
        problem_topics = {normalize_topic(tag) for tag in problem.tags}
        for weakness in profile.weaknesses:
            if weakness.topic in problem_topics and weakness.confidence >= 0.5:
                return f"你之前在 {weakness.pattern} 上出现过几次问题，建议这次先主动检查。"
        return ""
