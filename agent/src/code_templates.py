from __future__ import annotations

# 文件用途：解析 LeetCode Python 模板，并在函数体答题模式下生成可执行提交代码。

import ast
import re
import textwrap
from collections.abc import Iterable

from .models import Problem


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


def select_python_starter_code(code_snippets: list[dict]) -> str:
    """从 LeetCode 代码模板列表中选取 Python 模板。

    参数:
        code_snippets: LeetCode GraphQL 返回的 codeSnippets 列表。

    返回值:
        str: Python3 或 Python 模板代码；找不到时返回空字符串。
    """
    preferred_lang_slugs = ("python3", "python")
    for lang_slug in preferred_lang_slugs:
        for snippet in code_snippets:
            if snippet.get("langSlug") == lang_slug and snippet.get("code"):
                return str(snippet["code"]).strip("\n")
    return ""


def extract_python_function_metadata(starter_code: str) -> tuple[str, str]:
    """从 Python 模板中提取函数签名和函数名。

    参数:
        starter_code: LeetCode Python 初始代码模板。

    返回值:
        tuple[str, str]: 函数签名和函数名；无法提取时返回两个空字符串。
    """
    for line in starter_code.splitlines():
        stripped = line.strip()
        match = re.match(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*\)\s*(?:->\s*[^:]+)?\s*:", stripped)
        if match:
            return stripped, match.group(1)
    return "", ""


def infer_method_name(problem_id: str) -> str:
    """根据题目 ID 推断 LeetCode Python 方法名。

    参数:
        problem_id: 题目 slug 或本地题目 ID。

    返回值:
        str: 推断出的驼峰方法名；无法推断时返回空字符串。
    """
    if problem_id in PROBLEM_METHOD_MAP:
        return PROBLEM_METHOD_MAP[problem_id]
    words = [word for word in re.split(r"[^a-zA-Z0-9]+", problem_id) if word]
    if not words:
        return ""
    return words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])


def infer_argument_names_from_examples(problem: Problem) -> list[str]:
    """从题目样例输入中推断方法参数名。

    参数:
        problem: 当前题目。

    返回值:
        list[str]: 按样例出现顺序排列的参数名列表。
    """
    if not problem.examples:
        return []
    return _extract_assignment_names(problem.examples[0].input)


def get_python_function_signature(
    problem: Problem, argument_names: Iterable[str] | None = None
) -> str:
    """获取函数体答题模式使用的 Python 函数签名。

    参数:
        problem: 当前题目。
        argument_names: 可选参数名列表；题目没有 LeetCode 模板时用于兜底生成签名。

    返回值:
        str: 形如 `def twoSum(self, nums, target):` 的函数签名；无法生成时返回空字符串。
    """
    if problem.function_signature:
        return _ensure_signature_colon(problem.function_signature)

    method_name = problem.function_name or infer_method_name(problem.id)
    if not method_name:
        return ""

    names = [name for name in (argument_names or []) if name]
    if not names:
        names = infer_argument_names_from_examples(problem)
    arguments = ", ".join(["self", *names])
    return f"def {method_name}({arguments}):"


def is_python_body_mode_available(problem: Problem, language: str) -> bool:
    """判断当前会话是否可以使用 Python 函数体答题模式。

    参数:
        problem: 当前题目。
        language: 用户选择的编程语言。

    返回值:
        bool: 可以展示函数体编辑器时返回 True。
    """
    return language.lower() == "python" and bool(get_python_function_signature(problem))


def extract_python_body_code(problem: Problem, code: str) -> str:
    """从完整 Python 提交中提取函数体代码。

    参数:
        problem: 当前题目。
        code: 用户当前代码，可能是完整提交或函数体。

    返回值:
        str: 提取后的函数体；无法提取时返回原始代码。
    """
    if not code.strip():
        return ""

    function_name = problem.function_name or infer_method_name(problem.id)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    function_node = _find_solution_function(tree, function_name)
    if not function_node or not function_node.body:
        return code

    lines = code.splitlines()
    start_line = function_node.body[0].lineno
    end_line = function_node.end_lineno or start_line
    body = "\n".join(lines[start_line - 1 : end_line])
    body = textwrap.dedent(body).strip("\n")
    return "" if body.strip() == "pass" else body


def build_python_submission_code(
    problem: Problem, code: str, argument_names: Iterable[str] | None = None
) -> str:
    """把函数体代码包装成可执行的 LeetCode Python 提交。

    参数:
        problem: 当前题目。
        code: 用户输入的函数体或完整提交代码。
        argument_names: 可选参数名列表，用于生成兜底函数签名。

    返回值:
        str: 完整 Python 提交代码；如果用户已输入完整提交则原样返回。
    """
    function_name = problem.function_name or infer_method_name(problem.id)
    if looks_like_complete_python_submission(code, function_name):
        return code

    signature = get_python_function_signature(problem, argument_names)
    if not signature:
        return code

    return f"class Solution:\n    {signature}\n{_indent_python_body(code)}\n"


def looks_like_complete_python_submission(code: str, function_name: str = "") -> bool:
    """判断代码是否已经是完整 Python 提交。

    参数:
        code: 用户输入的代码。
        function_name: 当前题目期望的方法名。

    返回值:
        bool: 已包含 `Solution` 方法或目标顶层函数时返回 True。
    """
    if not code.strip():
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    if _find_solution_function(tree, function_name):
        return True
    top_level_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if function_name:
        return any(node.name == function_name for node in top_level_functions)
    return len(top_level_functions) == 1


def _extract_assignment_names(input_text: str) -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for match in pattern.finditer(input_text):
        names.append(match.group(1))
    return names


def _ensure_signature_colon(signature: str) -> str:
    stripped = signature.strip()
    return stripped if stripped.endswith(":") else f"{stripped}:"


def _find_solution_function(tree: ast.Module, function_name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Solution":
            methods = [item for item in node.body if isinstance(item, ast.FunctionDef)]
            if function_name:
                for method in methods:
                    if method.name == function_name:
                        return method
            public_methods = [method for method in methods if not method.name.startswith("_")]
            if len(public_methods) == 1:
                return public_methods[0]

    if function_name:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return node
    return None


def _indent_python_body(code: str, spaces: int = 8) -> str:
    body = textwrap.dedent(code).strip("\n")
    if not body.strip():
        return " " * spaces + "pass"

    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line.strip() else "" for line in body.splitlines())
