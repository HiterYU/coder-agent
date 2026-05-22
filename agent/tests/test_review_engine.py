from __future__ import annotations

# 文件用途：验证代码复盘引擎的本地兜底、LLM 解析与样例运行结果整合。

from dataclasses import dataclass, field
from typing import Any

from src.models import Example, Problem, ReviewResult, Session, UserProfile
from src.review_engine import ReviewEngine
from src.submission_runner import ExampleRunResult, SubmissionRunResult


@dataclass
class _StubLlm:
    """测试用 LLM 客户端桩。"""

    available: bool = False
    response: dict[str, Any] | None = None
    captured_user: str = ""

    def complete_json(
        self, system: str, user: str, agent_name: str | None = None
    ) -> dict[str, Any] | None:
        self.captured_user = user
        return self.response


@dataclass
class _StubRunner:
    """测试用 PythonSubmissionRunner 桩。"""

    result: SubmissionRunResult = field(default_factory=SubmissionRunResult)
    last_call: tuple[Problem, str, str] | None = None

    def run_examples(self, problem: Problem, code: str, language: str) -> SubmissionRunResult:
        self.last_call = (problem, code, language)
        return self.result


def _make_problem(**overrides: Any) -> Problem:
    base = {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "description": "返回两数之和的下标。",
        "examples": [Example(input="nums = [2,7,11,15], target = 9", output="[0,1]")],
        "expected_approaches": [],
        "common_mistakes": [],
    }
    base.update(overrides)
    return Problem(**base)


def _make_session() -> Session:
    return Session(user_id="demo", problem_id="two-sum")


def _attach_runner(engine: ReviewEngine, runner: _StubRunner) -> None:
    engine.runner = runner  # type: ignore[assignment]


def test_review_engine_fallback_flags_empty_code() -> None:
    """空提交应在本地兜底标记为 problem_understanding_wrong。"""
    engine = ReviewEngine(llm_client=_StubLlm(available=False))
    _attach_runner(engine, _StubRunner(SubmissionRunResult(skipped_reason="提交代码为空。")))

    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), "")

    assert review.is_likely_correct is False
    assert any(item.type == "problem_understanding_wrong" for item in review.mistakes)
    assert review.passed_sample_tests is False


def test_review_engine_fallback_detects_two_sum_without_hash_table() -> None:
    """暴力解 Two Sum 时应提示复杂度过高与返回格式问题。"""
    engine = ReviewEngine(llm_client=_StubLlm(available=False))
    _attach_runner(engine, _StubRunner(SubmissionRunResult(skipped_reason="未运行")))
    code = "def two_sum(nums, target):\n    return [nums[0], nums[1]]"

    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), code)

    mistake_types = {item.type for item in review.mistakes}
    assert "complexity_too_high" in mistake_types
    assert "return_format_wrong" in mistake_types
    assert review.is_likely_correct is False


def test_review_engine_fallback_marks_correct_on_pass() -> None:
    """样例全部通过且无规则错误时，应标记为大概率正确。"""
    engine = ReviewEngine(llm_client=_StubLlm(available=False))
    success_run = SubmissionRunResult(
        ran=True,
        passed=True,
        results=[
            ExampleRunResult(
                index=1,
                passed=True,
                input_text="nums = [2,7,11,15], target = 9",
                expected_text="[0,1]",
                actual=[0, 1],
            )
        ],
    )
    _attach_runner(engine, _StubRunner(success_run))
    code = "class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        for i, n in enumerate(nums):\n            if target - n in seen:\n                return [seen[target - n], i]\n            seen[n] = i\n        return []\n"

    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), code)

    assert review.is_likely_correct is True
    assert review.passed_sample_tests is True
    assert review.sample_test_results[0].passed is True
    assert review.mistakes == []


def test_review_engine_fallback_records_failed_sample() -> None:
    """样例失败时应记录失败样例并标记不正确。"""
    engine = ReviewEngine(llm_client=_StubLlm(available=False))
    failed_run = SubmissionRunResult(
        ran=True,
        passed=False,
        results=[
            ExampleRunResult(
                index=1,
                passed=False,
                input_text="nums = [2,7,11,15], target = 9",
                expected_text="[0,1]",
                actual=[1, 2],
                error="",
            )
        ],
    )
    _attach_runner(engine, _StubRunner(failed_run))

    code = "class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        return [1, 2]\n"
    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), code)

    assert review.is_likely_correct is False
    assert review.passed_sample_tests is False
    assert any("样例 1" in action for action in review.next_actions)


def test_review_engine_uses_llm_review_when_available() -> None:
    """LLM 返回有效 JSON 时应解析并合并样例运行结果。"""
    stub = _StubLlm(
        available=True,
        response={
            "is_likely_correct": True,
            "passed_sample_tests": True,
            "time_complexity": "O(n)",
            "space_complexity": "O(n)",
            "mistakes": [],
            "feedback": "整体思路正确。",
            "next_actions": ["补充负数边界用例"],
        },
    )
    engine = ReviewEngine(llm_client=stub)
    success_run = SubmissionRunResult(
        ran=True,
        passed=True,
        results=[
            ExampleRunResult(
                index=1,
                passed=True,
                input_text="nums = [2,7,11,15], target = 9",
                expected_text="[0,1]",
                actual=[0, 1],
            )
        ],
    )
    _attach_runner(engine, _StubRunner(success_run))

    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), "code")

    assert isinstance(review, ReviewResult)
    assert review.feedback == "整体思路正确。"
    assert review.time_complexity == "O(n)"
    assert review.passed_sample_tests is True
    assert review.sample_test_results[0].passed is True


def test_review_engine_apply_run_result_overrides_llm_when_sample_fails() -> None:
    """LLM 判断通过但样例失败时，应被运行结果纠偏。"""
    stub = _StubLlm(
        available=True,
        response={
            "is_likely_correct": True,
            "passed_sample_tests": True,
            "time_complexity": "O(n)",
            "space_complexity": "O(n)",
            "mistakes": [],
            "feedback": "看起来正确",
            "next_actions": [],
        },
    )
    engine = ReviewEngine(llm_client=stub)
    failed_run = SubmissionRunResult(
        ran=True,
        passed=False,
        results=[
            ExampleRunResult(
                index=1,
                passed=False,
                input_text="nums = [2,7,11,15], target = 9",
                expected_text="[0,1]",
                actual=[2, 3],
                error="",
            )
        ],
    )
    _attach_runner(engine, _StubRunner(failed_run))

    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), "code")

    assert review.is_likely_correct is False
    assert review.passed_sample_tests is False
    assert any("样例 1" in mistake.evidence for mistake in review.mistakes)


def test_review_engine_falls_back_when_llm_response_invalid() -> None:
    """LLM 返回缺失 feedback 字段时应回退到本地兜底。"""
    stub = _StubLlm(available=True, response={"is_likely_correct": True})
    engine = ReviewEngine(llm_client=stub)
    _attach_runner(engine, _StubRunner(SubmissionRunResult(skipped_reason="未运行")))

    code = "class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        for i, n in enumerate(nums):\n            if target - n in seen:\n                return [seen[target - n], i]\n            seen[n] = i\n        return []\n"
    review = engine.review_submission(_make_session(), _make_problem(), UserProfile(user_id="demo"), code)

    assert review.feedback
    assert review.feedback != ""
