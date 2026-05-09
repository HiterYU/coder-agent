from __future__ import annotations

# 文件用途：根据题目、会话和用户画像生成分级提示。

from .llm_client import LlmClient
from .models import Problem, Session, UserProfile
from .taxonomy import normalize_topic


class HintEngine:
    """分级提示生成引擎。

    参数:
        llm_client: 可选 LLM 客户端；未传入时创建默认客户端。

    返回值:
        无。实例化后可通过 generate_hint 生成提示。
    """

    def __init__(self, llm_client: LlmClient | None = None):
        """初始化分级提示生成引擎。

        参数:
            llm_client: 可选 LLM 客户端；未传入时创建默认客户端。

        返回值:
            无。
        """
        self.llm = llm_client or LlmClient()

    def generate_hint(self, session: Session, problem: Problem, profile: UserProfile) -> dict:
        """生成下一次提示。

        参数:
            session: 当前训练会话。
            problem: 当前题目。
            profile: 用户画像。

        返回值:
            dict: 包含提示强度、请求轮次、提示内容、生成原因和是否泄露答案的字典。
        """
        hint_request_count = len(session.hints_given) + 1
        hint_level = self._next_hint_level(session)
        llm_hint = self._generate_llm_hint(
            session, problem, profile, hint_level, hint_request_count
        )
        if llm_hint:
            return llm_hint

        hint = self._fallback_hint(problem, profile, hint_level, hint_request_count)
        return {
            "hint_level": hint_level,
            "hint_request_count": hint_request_count,
            "hint": hint,
            "why_this_hint": "根据当前提示等级、题目标签和用户历史错误生成。",
            "reveals_solution": hint_level >= 5,
        }

    def _next_hint_level(self, session: Session) -> int:
        """计算下一次提示的泄题强度等级。

        参数:
            session: 当前训练会话。

        返回值:
            int: 1 到 5 之间的提示强度；超过 5 次请求后继续停留在 5。
        """
        if not session.hints_given:
            return 1
        return min(max(session.hints_given) + 1, 5)

    def _generate_llm_hint(
        self,
        session: Session,
        problem: Problem,
        profile: UserProfile,
        hint_level: int,
        hint_request_count: int,
    ) -> dict | None:
        """调用 LLM 生成提示。

        参数:
            session: 当前训练会话。
            problem: 当前题目。
            profile: 用户画像。
            hint_level: 本次提示强度，范围为 1 到 5。
            hint_request_count: 当前会话中的提示请求轮次，可大于 5。

        返回值:
            dict | None: LLM 生成的提示数据；调用失败或不可用时返回 None。
        """
        if not self.llm.available:
            return None
        latest_message = session.messages[-1].content if session.messages else ""
        system = "你是一个 LeetCode 编程训练教练。你帮助用户独立解题，并能持续回答多轮追问。只输出 JSON。"
        follow_up_rule = (
            "这是第 6 次或更多提示请求，提示强度仍按 Level 5 处理，但不要简单重复完整题解；"
            "请优先根据用户最近输入解释具体卡点、调试错误、边界用例或代码细节。"
            if hint_request_count > 5
            else "这是前 5 次递进提示，请严格控制泄题程度。"
        )
        user = f"""
题目:
{problem.model_dump_json(indent=2)}

用户画像:
{profile.model_dump_json(indent=2)}

当前会话:
{session.model_dump_json(indent=2)}

用户最近输入:
{latest_message}

提示请求轮次: {hint_request_count}
目标提示强度: Level {hint_level}

要求:
1. Level 1-3 不给完整代码。
2. Level 4 可以给代码骨架。
3. Level 5 才能给完整题解。
4. 输出中文。
5. {follow_up_rule}

JSON 格式:
{{
  "hint_level": {hint_level},
  "hint_request_count": {hint_request_count},
  "hint": "...",
  "why_this_hint": "...",
  "reveals_solution": false
}}
"""
        data = self.llm.complete_json(system, user, agent_name="hint")
        if not data or "hint" not in data:
            return None
        data["hint_level"] = hint_level
        data["hint_request_count"] = hint_request_count
        data.setdefault("why_this_hint", "LLM 根据会话上下文生成。")
        data.setdefault("reveals_solution", hint_level >= 5)
        return data

    def _fallback_hint(
        self, problem: Problem, profile: UserProfile, hint_level: int, hint_request_count: int
    ) -> str:
        """生成本地兜底提示。

        参数:
            problem: 当前题目。
            profile: 用户画像。
            hint_level: 本次提示强度，范围为 1 到 5。
            hint_request_count: 当前会话中的提示请求轮次，可大于 5。

        返回值:
            str: 中文提示文本。
        """
        primary_tag = problem.tags[0] if problem.tags else "题目"
        primary_topic = normalize_topic(primary_tag)
        approach = problem.expected_approaches[0] if problem.expected_approaches else None
        mistake = problem.common_mistakes[0] if problem.common_mistakes else None
        profile_warning = self._profile_warning(problem, profile)

        if hint_request_count > 5:
            if approach:
                return (
                    f"这是第 {hint_request_count} 次提示，我会继续围绕具体卡点展开。"
                    f"当前题推荐方向仍是 {approach.name}：{approach.summary} "
                    "如果你的代码还没通过，优先贴出失败输入、实际输出和你认为应该维护的不变量。"
                )
            return (
                f"这是第 {hint_request_count} 次提示，可以继续追问具体卡点。"
                "建议把当前代码、失败样例或你不确定的条件贴出来，我会按上下文继续拆解。"
            )

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
        """生成与用户画像相关的提醒。

        参数:
            problem: 当前题目。
            profile: 用户画像。

        返回值:
            str: 命中历史薄弱点时返回提醒文本，否则返回空字符串。
        """
        problem_topics = {normalize_topic(tag) for tag in problem.tags}
        for weakness in profile.weaknesses:
            if weakness.topic in problem_topics and weakness.confidence >= 0.5:
                return f"你之前在 {weakness.pattern} 上出现过几次问题，建议这次先主动检查。"
        return ""
