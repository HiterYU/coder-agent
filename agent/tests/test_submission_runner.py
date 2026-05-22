from __future__ import annotations

# 文件用途：验证 Python 提交执行器的样例解析、本地运行协议与异常兜底。

from src.models import Example, Problem
from src.submission_runner import (
    PythonSubmissionRunner,
    SubmissionRunResult,
    _parse_input_arguments,
    _parse_value,
    _split_assignments,
    _UNPARSEABLE,
)


def _make_problem(examples: list[Example] | None = None, **overrides) -> Problem:
    base = {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "description": "返回两数之和的下标。",
        "examples": examples
        or [Example(input="nums = [2,7,11,15], target = 9", output="[0,1]")],
        "function_name": "twoSum",
        "function_signature": "def twoSum(self, nums, target):",
    }
    base.update(overrides)
    return Problem(**base)


def test_parse_value_handles_python_literals() -> None:
    """整型、列表、布尔、None 都应该解析正确。"""
    assert _parse_value("42") == 42
    assert _parse_value("[1, 2, 3]") == [1, 2, 3]
    assert _parse_value("true") is True
    assert _parse_value("False") is False
    assert _parse_value("null") is None
    assert _parse_value('"hello"') == "hello"


def test_parse_value_returns_unparseable_for_empty_or_invalid() -> None:
    """空字符串和无法解析的内容应返回 _UNPARSEABLE。"""
    assert _parse_value("") is _UNPARSEABLE
    assert _parse_value("   ") is _UNPARSEABLE
    assert _parse_value("foo bar") is _UNPARSEABLE


def test_parse_value_fallback_to_numeric_regex() -> None:
    """ast.literal_eval 失败但匹配数字正则时应回退转换。"""
    assert _parse_value("-7") == -7
    assert _parse_value("3.14") == 3.14


def test_split_assignments_splits_multiple_kv() -> None:
    """多个 key=value 应按出现顺序切分并去除尾随逗号。"""
    pairs = _split_assignments("nums = [2,7,11,15], target = 9")
    assert pairs == [("nums", "[2,7,11,15]"), ("target", "9")]


def test_split_assignments_returns_empty_when_no_assignment() -> None:
    """没有 = 时返回空列表。"""
    assert _split_assignments("[2,7,11,15]") == []


def test_parse_input_arguments_returns_dict() -> None:
    """合法输入字符串应转换为参数字典。"""
    args = _parse_input_arguments("nums = [2,7,11,15], target = 9")
    assert args == {"nums": [2, 7, 11, 15], "target": 9}


def test_parse_input_arguments_returns_empty_on_unparseable_value() -> None:
    """任意参数值不可解析时整体返回空字典，避免半解析。"""
    args = _parse_input_arguments("nums = ???, target = 9")
    assert args == {}


def test_run_examples_skips_non_python_language() -> None:
    """非 Python 语言不应执行任何代码。"""
    runner = PythonSubmissionRunner()
    result = runner.run_examples(_make_problem(), "code", "JavaScript")
    assert isinstance(result, SubmissionRunResult)
    assert result.ran is False
    assert result.skipped_reason


def test_run_examples_skips_empty_code() -> None:
    """空代码也应跳过执行。"""
    runner = PythonSubmissionRunner()
    result = runner.run_examples(_make_problem(), "   ", "Python")
    assert result.ran is False
    assert "为空" in result.skipped_reason


def test_run_examples_skips_when_examples_cannot_be_parsed() -> None:
    """样例无法解析为可执行用例时应跳过执行。"""
    runner = PythonSubmissionRunner()
    problem = _make_problem(examples=[Example(input="无法解析的输入", output="")])
    result = runner.run_examples(problem, "def twoSum(nums, target): return []", "Python")
    assert result.ran is False
    assert "无法解析" in result.skipped_reason


def test_run_examples_runs_correct_two_sum_solution() -> None:
    """正确的 Two Sum 解应通过本地子进程执行并返回 passed=True。"""
    runner = PythonSubmissionRunner(timeout_seconds=10)
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        seen = {}\n"
        "        for i, n in enumerate(nums):\n"
        "            if target - n in seen:\n"
        "                return [seen[target - n], i]\n"
        "            seen[n] = i\n"
        "        return []\n"
    )

    result = runner.run_examples(_make_problem(), code, "Python")
    assert result.ran is True
    assert result.passed is True
    assert len(result.results) == 1
    assert result.results[0].passed is True
    assert result.results[0].actual == [0, 1]


def test_run_examples_reports_wrong_answer() -> None:
    """错误答案应返回 passed=False 并保留 actual。"""
    runner = PythonSubmissionRunner(timeout_seconds=10)
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        return [9, 9]\n"
    )
    result = runner.run_examples(_make_problem(), code, "Python")
    assert result.ran is True
    assert result.passed is False
    assert result.results[0].passed is False
    assert result.results[0].actual == [9, 9]


def test_run_examples_captures_runtime_exception() -> None:
    """运行过程抛异常时应在 results 中标记 error。"""
    runner = PythonSubmissionRunner(timeout_seconds=10)
    code = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        raise IndexError('boom')\n"
    )
    result = runner.run_examples(_make_problem(), code, "Python")
    assert result.ran is True
    assert result.passed is False
    assert result.results[0].passed is False
    assert "IndexError" in result.results[0].error


def test_run_examples_blocks_disallowed_imports() -> None:
    """子进程沙盒应阻止导入未授权模块。"""
    runner = PythonSubmissionRunner(timeout_seconds=10)
    code = (
        "import os\n"
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        return [0, 1]\n"
    )
    result = runner.run_examples(_make_problem(), code, "Python")
    assert result.ran is True
    assert result.passed is False
