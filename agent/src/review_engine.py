from __future__ import annotations

# 文件用途：复盘用户提交代码，生成错误分析、复杂度判断和下一步建议。

from .llm_client import LlmClient
from .models import ExampleRunRecord, Mistake, Problem, ReviewResult, Session, UserProfile
from .submission_runner import PythonSubmissionRunner, SubmissionRunResult
from .taxonomy import MISTAKE_TAXONOMY, normalize_topic


class ReviewEngine:
    """代码复盘引擎。

    参数:
        llm_client: 可选 LLM 客户端；未传入时创建默认客户端。

    返回值:
        无。实例化后可通过 review_submission 复盘提交代码。
    """

    def __init__(self, llm_client: LlmClient | None = None):
        """初始化代码复盘引擎。

        参数:
            llm_client: 可选 LLM 客户端；未传入时创建默认客户端。

        返回值:
            无。
        """
        self.llm = llm_client or LlmClient()
        self.runner = PythonSubmissionRunner()

    def review_submission(
        self, session: Session, problem: Problem, profile: UserProfile, code: str
    ) -> ReviewResult:
        """复盘用户提交的代码。

        参数:
            session: 当前训练会话。
            problem: 当前题目。
            profile: 用户画像。
            code: 用户提交的代码。

        返回值:
            ReviewResult: 结构化复盘结果。
        """
        run_result = self.runner.run_examples(problem, code, session.language)
        llm_review = self._generate_llm_review(session, problem, profile, code, run_result)
        if llm_review:
            self._apply_run_result(llm_review, run_result)
            return llm_review
        return self._fallback_review(session, problem, code, run_result)

    def _generate_llm_review(
        self,
        session: Session,
        problem: Problem,
        profile: UserProfile,
        code: str,
        run_result: SubmissionRunResult,
    ) -> ReviewResult | None:
        if not self.llm.available:
            return None
        system = "你是一个严谨的 LeetCode 代码复盘教练。只输出 JSON，不要输出 Markdown。"
        user = f"""
题目:
{problem.model_dump_json(indent=2)}

用户画像:
{profile.model_dump_json(indent=2)}

会话:
{session.model_dump_json(indent=2)}

用户代码:
{code}

样例运行结果:
{self._format_run_result_for_prompt(run_result)}

错误类型 taxonomy:
{MISTAKE_TAXONOMY}

任务:
1. 判断代码是否大概率正确。
2. 分析时间复杂度和空间复杂度。
3. 找出具体错误，错误 type 必须从 taxonomy 中选择。
4. 复盘必须引用代码或思路中的证据。
5. 如果样例运行失败，passed_sample_tests 必须是 false，is_likely_correct 必须是 false。
6. 输出中文 JSON。

JSON 格式:
{{
  "is_likely_correct": true,
  "passed_sample_tests": false,
  "time_complexity": "O(n)",
  "space_complexity": "O(n)",
  "mistakes": [
    {{
      "type": "boundary_condition_missing",
      "topic": "array",
      "severity": "medium",
      "evidence": "..."
    }}
  ],
  "feedback": "...",
  "next_actions": ["..."]
}}
"""
        data = self.llm.complete_json(system, user, agent_name="review")
        if not data or "feedback" not in data:
            return None
        try:
            return ReviewResult(session_id=session.session_id, **data)
        except Exception:
            return None

    def _fallback_review(
        self, session: Session, problem: Problem, code: str, run_result: SubmissionRunResult
    ) -> ReviewResult:
        normalized = code.lower()
        mistakes = self._detect_mistakes(problem, normalized, code)
        mistakes.extend(self._mistakes_from_run_result(problem, run_result))
        approach = problem.expected_approaches[0] if problem.expected_approaches else None
        is_likely_correct = (
            len(mistakes) == 0
            and bool(code.strip())
            and (not run_result.ran or run_result.passed)
        )

        if approach:
            time_complexity = approach.time_complexity
            space_complexity = approach.space_complexity
        else:
            time_complexity = "需要进一步分析"
            space_complexity = "需要进一步分析"

        if is_likely_correct:
            feedback = (
                "从当前代码结构和样例执行结果看，你的解法大概率方向正确。"
                "这不是完整在线判题，建议继续补充边界用例验证。"
            )
            next_actions = ["补充边界用例", "口头解释时间复杂度和关键不变量"]
        elif run_result.ran and not run_result.passed:
            feedback = "当前代码没有通过题目样例，先修正样例暴露的错误，再做复杂度优化。"
            next_actions = [f"修正样例 {item.index}: {item.error or '实际输出与期望不一致'}" for item in run_result.results if not item.passed]
        elif run_result.skipped_reason:
            feedback = f"本次没有执行样例：{run_result.skipped_reason} 复盘将基于代码结构和规则分析。"
            next_actions = [f"检查：{mistake.evidence}" for mistake in mistakes] or ["补充可执行样例或切换到 Python 提交"]
        else:
            feedback = "这次提交里有几个需要优先检查的问题，先修正证据最明确的错误，再跑样例。"
            next_actions = [f"检查：{mistake.evidence}" for mistake in mistakes]

        return ReviewResult(
            session_id=session.session_id,
            is_likely_correct=is_likely_correct,
            passed_sample_tests=run_result.ran and run_result.passed,
            sample_test_results=self._to_example_run_records(run_result),
            time_complexity=time_complexity,
            space_complexity=space_complexity,
            mistakes=mistakes,
            feedback=feedback,
            next_actions=next_actions,
        )

    def _detect_mistakes(self, problem: Problem, normalized_code: str, raw_code: str) -> list[Mistake]:
        mistakes: list[Mistake] = []
        topic = normalize_topic(problem.tags[0]) if problem.tags else "general"

        if not raw_code.strip():
            return [
                Mistake(
                    type="problem_understanding_wrong",
                    topic=topic,
                    severity="high",
                    evidence="提交内容为空，无法判断解法。",
                )
            ]

        if "return" not in normalized_code:
            mistakes.append(
                Mistake(
                    type="return_format_wrong",
                    topic=topic,
                    severity="high",
                    evidence="代码中没有明显 return 语句，可能无法返回题目要求的结果。",
                )
            )

        if problem.id == "two-sum":
            if "dict" not in normalized_code and "{}" not in normalized_code and "map" not in normalized_code:
                mistakes.append(
                    Mistake(
                        type="complexity_too_high",
                        topic="hash_table",
                        severity="medium",
                        evidence="Two Sum 的高效解通常需要哈希表；当前代码没有明显哈希表结构。",
                    )
                )
            if "return [nums" in normalized_code or "return nums" in normalized_code:
                mistakes.append(
                    Mistake(
                        type="return_format_wrong",
                        topic="array",
                        severity="high",
                        evidence="题目要求返回下标，当前代码看起来可能返回了数值。",
                    )
                )

        if problem.id == "valid-parentheses":
            if "stack" not in normalized_code and "append" not in normalized_code:
                mistakes.append(
                    Mistake(
                        type="wrong_state_definition",
                        topic="stack",
                        severity="medium",
                        evidence="括号匹配通常需要栈；当前代码没有明显维护未匹配左括号。",
                    )
                )
            if "pop" in normalized_code and ("if" not in normalized_code or "not stack" not in normalized_code):
                mistakes.append(
                    Mistake(
                        type="boundary_condition_missing",
                        topic="stack",
                        severity="high",
                        evidence="使用 pop 前需要确认栈非空，否则遇到单独右括号会出错。",
                    )
                )

        if problem.id == "binary-search":
            if "while" in normalized_code and "left <= right" not in normalized_code and "left < right" not in normalized_code:
                mistakes.append(
                    Mistake(
                        type="wrong_loop_condition",
                        topic="binary_search",
                        severity="medium",
                        evidence="二分搜索需要明确循环条件，当前 while 条件不容易验证边界。",
                    )
                )

        if problem.id == "maximum-subarray":
            if "0" in normalized_code and "max" in normalized_code and "nums[0]" not in normalized_code:
                mistakes.append(
                    Mistake(
                        type="boundary_condition_missing",
                        topic="dynamic_programming",
                        severity="medium",
                        evidence="最大子数组如果用 0 初始化，可能在全负数输入下返回错误结果。",
                    )
                )

        if problem.id == "number-of-islands":
            if "visited" not in normalized_code and "grid[" not in normalized_code:
                mistakes.append(
                    Mistake(
                        type="visited_handling_wrong",
                        topic="graph_search",
                        severity="high",
                        evidence="岛屿数量需要标记已访问陆地，否则可能重复计数或无限递归。",
                    )
                )

        return mistakes

    def _apply_run_result(self, review: ReviewResult, run_result: SubmissionRunResult) -> None:
        review.sample_test_results = self._to_example_run_records(run_result)
        if run_result.ran:
            review.passed_sample_tests = run_result.passed
            if not run_result.passed:
                review.is_likely_correct = False
                existing_evidence = {mistake.evidence for mistake in review.mistakes}
                for mistake in self._mistakes_from_run_result(None, run_result):
                    if mistake.evidence not in existing_evidence:
                        review.mistakes.append(mistake)
        elif run_result.skipped_reason:
            review.passed_sample_tests = False

    def _mistakes_from_run_result(
        self, problem: Problem | None, run_result: SubmissionRunResult
    ) -> list[Mistake]:
        if not run_result.ran or run_result.passed:
            return []

        topic = normalize_topic(problem.tags[0]) if problem and problem.tags else "general"
        mistakes: list[Mistake] = []
        for item in run_result.results:
            if item.passed:
                continue
            if item.error:
                mistake_type = "index_out_of_range" if "IndexError" in item.error else "boundary_condition_missing"
                evidence = f"样例 {item.index} 运行失败：{item.error}"
            else:
                mistake_type = "return_format_wrong"
                evidence = f"样例 {item.index} 未通过：期望 {item.expected_text}，实际输出 {item.actual!r}"
            mistakes.append(
                Mistake(
                    type=mistake_type,
                    topic=topic,
                    severity="high",
                    evidence=evidence,
                )
            )
        return mistakes

    def _to_example_run_records(self, run_result: SubmissionRunResult) -> list[ExampleRunRecord]:
        return [
            ExampleRunRecord(
                index=item.index,
                passed=item.passed,
                input=item.input_text,
                expected=item.expected_text,
                actual=repr(item.actual),
                error=item.error,
            )
            for item in run_result.results
        ]

    def _format_run_result_for_prompt(self, run_result: SubmissionRunResult) -> str:
        if run_result.ran:
            records = self._to_example_run_records(run_result)
            return "\n".join(
                (
                    f"- 样例 {record.index}: {'通过' if record.passed else '失败'}; "
                    f"expected={record.expected}; actual={record.actual}; error={record.error}"
                )
                for record in records
            )
        if run_result.skipped_reason:
            return f"未执行：{run_result.skipped_reason}"
        return "未执行。"
