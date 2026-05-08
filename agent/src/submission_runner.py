from __future__ import annotations

# 文件用途：执行用户提交的 Python 代码，并用题目样例做基础正确性验证。

import ast
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Example, Problem


PROBLEM_METHOD_MAP = {
    "two-sum": "twoSum",
    "valid-parentheses": "isValid",
    "best-time-to-buy-and-sell-stock": "maxProfit",
    "binary-search": "search",
    "maximum-subarray": "maxSubArray",
    "climbing-stairs": "climbStairs",
    "longest-substring-without-repeating-characters": "lengthOfLongestSubstring",
    "number-of-islands": "numIslands",
}


@dataclass(frozen=True)
class ExampleCase:
    """可执行样例用例。

    参数:
        index: 样例序号。
        arguments: 调用参数字典。
        expected: 期望输出。

    返回值:
        无。该类用于承载解析后的样例。
    """

    # 样例序号，从 1 开始。
    index: int
    # LeetCode 输入参数名和值。
    arguments: dict[str, Any]
    # 期望输出值。
    expected: Any


@dataclass(frozen=True)
class ExampleRunResult:
    """单个样例运行结果。

    参数:
        index: 样例序号。
        passed: 是否通过。
        input_text: 原始输入文本。
        expected_text: 原始期望输出文本。
        actual: 实际输出。
        error: 错误信息。

    返回值:
        无。该类用于展示和复盘样例执行结果。
    """

    # 样例序号，从 1 开始。
    index: int
    # 是否通过该样例。
    passed: bool = False
    # 原始输入文本。
    input_text: str = ""
    # 原始期望输出文本。
    expected_text: str = ""
    # 实际输出；运行失败或跳过时为 None。
    actual: Any = None
    # 错误信息；通过时为空。
    error: str = ""


@dataclass(frozen=True)
class SubmissionRunResult:
    """提交代码执行结果。

    参数:
        ran: 是否实际运行了用户代码。
        passed: 是否所有可执行样例通过。
        skipped_reason: 跳过执行的原因。
        results: 每个样例的执行结果。

    返回值:
        无。该类用于复盘阶段判断样例通过情况。
    """

    # 是否实际运行了用户代码。
    ran: bool = False
    # 所有可执行样例是否通过。
    passed: bool = False
    # 跳过执行的原因。
    skipped_reason: str = ""
    # 每个样例的执行结果。
    results: list[ExampleRunResult] = field(default_factory=list)


class PythonSubmissionRunner:
    """Python 提交执行器。

    参数:
        timeout_seconds: 子进程执行超时时间。

    返回值:
        无。实例化后可通过 run_examples 执行样例。
    """

    def __init__(self, timeout_seconds: int = 3):
        """初始化 Python 提交执行器。

        参数:
            timeout_seconds: 子进程执行超时时间。

        返回值:
            无。
        """
        self.timeout_seconds = timeout_seconds

    def run_examples(self, problem: Problem, code: str, language: str) -> SubmissionRunResult:
        """执行用户代码并验证题目样例。

        参数:
            problem: 当前题目。
            code: 用户提交代码。
            language: 用户选择的语言。

        返回值:
            SubmissionRunResult: 样例执行结果。
        """
        if language.lower() != "python":
            return SubmissionRunResult(skipped_reason="当前只支持运行 Python 提交。")
        if not code.strip():
            return SubmissionRunResult(skipped_reason="提交代码为空。")

        parsed_cases = self._parse_examples(problem.examples)
        if not parsed_cases:
            return SubmissionRunResult(skipped_reason="题目样例无法解析为可执行测试。")

        payload = {
            "code": code,
            "problem_id": problem.id,
            "method_name": self._infer_method_name(problem.id),
            "cases": [
                {"index": case.index, "arguments": case.arguments, "expected": case.expected}
                for case in parsed_cases
            ],
        }

        try:
            process = subprocess.run(
                [sys.executable, "-I", str(self._runner_script_path())],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SubmissionRunResult(
                ran=True,
                passed=False,
                skipped_reason="",
                results=[
                    ExampleRunResult(
                        index=case.index,
                        input_text=problem.examples[case.index - 1].input,
                        expected_text=problem.examples[case.index - 1].output,
                        error=f"执行超过 {self.timeout_seconds} 秒，可能存在死循环或复杂度过高。",
                    )
                    for case in parsed_cases
                ],
            )

        if process.returncode != 0:
            if process.returncode < 0:
                error = "执行被系统中断，可能是超时、死循环或内存使用过高。"
            else:
                error = (process.stderr or process.stdout or "执行失败。").strip()
            return SubmissionRunResult(
                ran=True,
                passed=False,
                results=[
                    ExampleRunResult(
                        index=case.index,
                        input_text=problem.examples[case.index - 1].input,
                        expected_text=problem.examples[case.index - 1].output,
                        error=error,
                    )
                    for case in parsed_cases
                ],
            )

        try:
            raw_results = json.loads(process.stdout)
        except json.JSONDecodeError:
            return SubmissionRunResult(
                ran=True,
                passed=False,
                results=[
                    ExampleRunResult(
                        index=case.index,
                        input_text=problem.examples[case.index - 1].input,
                        expected_text=problem.examples[case.index - 1].output,
                        error="执行结果不是合法 JSON。",
                    )
                    for case in parsed_cases
                ],
            )

        results = [
            self._to_example_run_result(problem.examples[item["index"] - 1], item)
            for item in raw_results
            if isinstance(item, dict) and isinstance(item.get("index"), int)
        ]
        return SubmissionRunResult(
            ran=True,
            passed=bool(results) and all(item.passed for item in results),
            results=results,
        )

    def _parse_examples(self, examples: list[Example]) -> list[ExampleCase]:
        cases: list[ExampleCase] = []
        for index, example in enumerate(examples, start=1):
            if not example.output.strip():
                continue
            arguments = _parse_input_arguments(example.input)
            expected = _parse_value(example.output)
            if not arguments or expected is _UNPARSEABLE:
                continue
            cases.append(ExampleCase(index=index, arguments=arguments, expected=expected))
        return cases

    def _infer_method_name(self, problem_id: str) -> str:
        if problem_id in PROBLEM_METHOD_MAP:
            return PROBLEM_METHOD_MAP[problem_id]
        words = [word for word in re.split(r"[^a-zA-Z0-9]+", problem_id) if word]
        if not words:
            return ""
        return words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])

    def _runner_script_path(self) -> Path:
        script = Path(tempfile.gettempdir()) / "leetcode_training_submission_runner.py"
        script.write_text(_RUNNER_SCRIPT, encoding="utf-8")
        return script

    def _to_example_run_result(self, example: Example, item: dict) -> ExampleRunResult:
        return ExampleRunResult(
            index=item["index"],
            passed=bool(item.get("passed")),
            input_text=example.input,
            expected_text=example.output,
            actual=item.get("actual"),
            error=str(item.get("error") or ""),
        )


class _Unparseable:
    pass


_UNPARSEABLE = _Unparseable()


def _parse_input_arguments(input_text: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    for name, value_text in _split_assignments(input_text):
        value = _parse_value(value_text)
        if value is _UNPARSEABLE:
            return {}
        arguments[name] = value
    return arguments


def _split_assignments(input_text: str) -> list[tuple[str, str]]:
    assignments: list[tuple[str, str]] = []
    position = 0
    pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=")

    while True:
        match = pattern.search(input_text, position)
        if not match:
            break
        next_match = pattern.search(input_text, match.end())
        end = next_match.start() if next_match else len(input_text)
        value = input_text[match.end() : end].strip().rstrip(",")
        assignments.append((match.group(1), value))
        position = end

    return assignments


def _parse_value(value_text: str) -> Any:
    value_text = value_text.strip()
    if not value_text:
        return _UNPARSEABLE

    normalized = re.sub(r"\btrue\b", "True", value_text, flags=re.IGNORECASE)
    normalized = re.sub(r"\bfalse\b", "False", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bnull\b", "None", normalized, flags=re.IGNORECASE)

    try:
        return ast.literal_eval(normalized)
    except (SyntaxError, ValueError):
        if re.fullmatch(r"-?\d+", value_text):
            return int(value_text)
        if re.fullmatch(r"-?\d+\.\d+", value_text):
            return float(value_text)
        return _UNPARSEABLE


_RUNNER_SCRIPT = r'''
from __future__ import annotations

import collections
import contextlib
import functools
import heapq
import io
import itertools
import json
import math
import resource
import sys
from typing import Dict, List, Optional, Set, Tuple


_ALLOWED_IMPORTS = {
    "collections": collections,
    "functools": functools,
    "heapq": heapq,
    "itertools": itertools,
    "math": math,
    "typing": sys.modules["typing"],
}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root_name = name.split(".", 1)[0]
    if level != 0 or root_name not in _ALLOWED_IMPORTS:
        raise ImportError(f"不允许导入模块: {name}")
    return __import__(name, globals, locals, fromlist, level)


_SAFE_BUILTINS = {
    "__import__": _safe_import,
    "__build_class__": __build_class__,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "chr": chr,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "ord": ord,
    "pow": pow,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "object": object,
    "print": print,
    "type": type,
    "zip": zip,
    "BaseException": BaseException,
    "Exception": Exception,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "TypeError": TypeError,
    "ValueError": ValueError,
}


def _apply_resource_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))


def _normalize(value):
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    return value


def _matches_expected(problem_id, arguments, actual, expected):
    normalized_actual = _normalize(actual)
    normalized_expected = _normalize(expected)
    if normalized_actual == normalized_expected:
        return True

    if problem_id == "two-sum" and isinstance(actual, (list, tuple)) and len(actual) == 2:
        nums = arguments.get("nums")
        target = arguments.get("target")
        if isinstance(nums, list) and isinstance(target, int):
            try:
                i, j = int(actual[0]), int(actual[1])
                return i != j and 0 <= i < len(nums) and 0 <= j < len(nums) and nums[i] + nums[j] == target
            except (TypeError, ValueError, IndexError):
                return False

    return False


def _find_callable(namespace, method_name):
    solution_cls = namespace.get("Solution")
    if isinstance(solution_cls, type):
        solution = solution_cls()
        if method_name and hasattr(solution, method_name):
            return getattr(solution, method_name)
        methods = [
            getattr(solution, name)
            for name in dir(solution)
            if not name.startswith("_") and callable(getattr(solution, name))
        ]
        if len(methods) == 1:
            return methods[0]

    if method_name and callable(namespace.get(method_name)):
        return namespace[method_name]

    functions = [
        value
        for name, value in namespace.items()
        if not name.startswith("_") and callable(value) and getattr(value, "__module__", "") == "__submission__"
    ]
    if len(functions) == 1:
        return functions[0]
    raise ValueError("没有找到可调用的 Solution 方法或唯一函数。")


def main():
    payload = json.loads(sys.stdin.read())
    problem_id = payload.get("problem_id", "")
    namespace = {
        "__name__": "__submission__",
        "__builtins__": _SAFE_BUILTINS,
        "List": List,
        "Dict": Dict,
        "Set": Set,
        "Tuple": Tuple,
        "Optional": Optional,
        "collections": collections,
        "Counter": collections.Counter,
        "defaultdict": collections.defaultdict,
        "deque": collections.deque,
        "heapq": heapq,
        "itertools": itertools,
        "functools": functools,
        "math": math,
    }
    _apply_resource_limits()
    debug_stdout = io.StringIO()
    with contextlib.redirect_stdout(debug_stdout):
        exec(payload["code"], namespace)
    target = _find_callable(namespace, payload.get("method_name", ""))
    results = []
    for case in payload["cases"]:
        arguments = case["arguments"]
        expected = case["expected"]
        try:
            with contextlib.redirect_stdout(debug_stdout):
                actual = target(**arguments)
            normalized_actual = _normalize(actual)
            normalized_expected = _normalize(expected)
            results.append(
                {
                    "index": case["index"],
                    "passed": _matches_expected(problem_id, arguments, actual, expected),
                    "actual": normalized_actual,
                    "expected": normalized_expected,
                    "error": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "index": case["index"],
                    "passed": False,
                    "actual": None,
                    "expected": expected,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''
