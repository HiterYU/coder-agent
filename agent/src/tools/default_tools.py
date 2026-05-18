from __future__ import annotations

# 文件用途：注册 LeetCode 训练场景默认可用的本地工具。

from pathlib import Path
from typing import Any

from ..code_templates import get_python_function_signature, infer_method_name
from ..leetcode_client import LeetCodeClient
from ..models import Problem
from ..problem_store import ProblemStore
from ..submission_runner import PythonSubmissionRunner, SubmissionRunResult
from .registry import ToolContext, ToolDefinition, ToolRegistry


def build_default_tool_registry(project_dir) -> ToolRegistry:
    """创建默认工具注册表。

    参数:
        project_dir: 项目根目录。

    返回值:
        ToolRegistry: 已注册默认工具的工具注册表。
    """
    registry = ToolRegistry(ToolContext(project_dir=Path(project_dir)))
    registry.register(
        ToolDefinition(
            name="get_problem",
            description="从本地题库或运行时缓存读取指定 LeetCode 题目的结构化信息。",
            parameters={
                "type": "object",
                "properties": {
                    "problem_id": {
                        "type": "string",
                        "description": "题目 ID 或 LeetCode slug，例如 two-sum。",
                    }
                },
                "required": ["problem_id"],
                "additionalProperties": False,
            },
            handler=_get_problem,
            agent_names={"hint", "review"},
        )
    )
    registry.register(
        ToolDefinition(
            name="search_problem_cache",
            description="按关键词、难度或标签搜索本地题库和运行时缓存中的题目。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "关键词，可匹配题目 ID、标题、标签或描述。",
                    },
                    "difficulty": {
                        "type": "string",
                        "description": "可选难度：Easy、Medium 或 Hard。",
                    },
                    "tag": {
                        "type": "string",
                        "description": "可选标签，例如 Array、Hash Table、Dynamic Programming。",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回多少道题，默认 5，最大 20。",
                    },
                },
                "additionalProperties": False,
            },
            handler=_search_problem_cache,
            agent_names={"hint", "review"},
        )
    )
    registry.register(
        ToolDefinition(
            name="fetch_leetcode_problem",
            description="从 LeetCode GraphQL 拉取题目并写入运行时缓存；支持 leetcode.com 和 leetcode.cn。",
            parameters={
                "type": "object",
                "properties": {
                    "url_or_slug": {
                        "type": "string",
                        "description": "LeetCode 题目 URL 或 slug，例如 https://leetcode.cn/problems/two-sum/。",
                    }
                },
                "required": ["url_or_slug"],
                "additionalProperties": False,
            },
            handler=_fetch_leetcode_problem,
            agent_names={"hint", "review"},
        )
    )
    registry.register(
        ToolDefinition(
            name="search_leetcode_problem_list",
            description="在线搜索 LeetCode 中国站题目列表，用于按题号、标题、slug 或标签查找题目；不会写入本地缓存。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "关键词，可匹配题号、英文标题、中文标题、slug 或标签。",
                    },
                    "difficulty": {
                        "type": "string",
                        "description": "可选难度：Easy、Medium 或 Hard。",
                    },
                    "tag": {
                        "type": "string",
                        "description": "可选标签，可匹配英文标签、中文标签或 tag slug。",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回多少道题，默认 10，最大 50。",
                    },
                    "scan_limit": {
                        "type": "integer",
                        "description": "最多在线扫描多少道题，默认 500，最大 3000。",
                    },
                },
                "additionalProperties": False,
            },
            handler=_search_leetcode_problem_list,
            agent_names={"hint", "review"},
        )
    )
    registry.register(
        ToolDefinition(
            name="run_python_examples",
            description="用当前项目的样例执行器运行 Python 提交代码或函数体，并返回样例结果；不是 LeetCode 在线判题。",
            parameters={
                "type": "object",
                "properties": {
                    "problem_id": {
                        "type": "string",
                        "description": "题目 ID 或 LeetCode slug，例如 two-sum。",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python 提交代码；可以是完整 Solution，也可以只包含函数体。",
                    },
                    "language": {
                        "type": "string",
                        "description": "提交语言，当前只有 Python 会实际执行。",
                    },
                },
                "required": ["problem_id", "code"],
                "additionalProperties": False,
            },
            handler=_run_python_examples,
            agent_names={"review"},
        )
    )
    return registry


def _get_problem(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    problem_id = _read_required_string(arguments, "problem_id")
    problem = _problem_store(context).get_problem(problem_id)
    return _problem_to_tool_dict(problem)


def _search_problem_cache(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip().lower()
    difficulty = str(arguments.get("difficulty") or "").strip()
    tag = str(arguments.get("tag") or "").strip()
    limit = min(max(int(arguments.get("limit") or 5), 1), 20)

    problems = _problem_store(context).list_problems()
    if difficulty:
        problems = [problem for problem in problems if problem.difficulty == difficulty]
    if tag:
        problems = [problem for problem in problems if tag in problem.tags]
    if query:
        problems = [
            problem
            for problem in problems
            if query in _problem_search_text(problem)
        ]

    return {
        "count": len(problems),
        "problems": [
            {
                "id": problem.id,
                "leetcode_id": problem.leetcode_id,
                "title": problem.title,
                "difficulty": problem.difficulty,
                "tags": problem.tags,
                "function_signature": problem.function_signature,
                "resolved_function_signature": get_python_function_signature(problem),
                "resolved_function_name": problem.function_name or infer_method_name(problem.id),
            }
            for problem in problems[:limit]
        ],
    }


def _fetch_leetcode_problem(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    url_or_slug = _read_required_string(arguments, "url_or_slug")
    problem = LeetCodeClient().fetch_problem(url_or_slug)
    stored_problem = _problem_store(context).upsert_problem(problem)
    return _problem_to_tool_dict(stored_problem)


def _search_leetcode_problem_list(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip().lower()
    difficulty = str(arguments.get("difficulty") or "").strip()
    tag = str(arguments.get("tag") or "").strip().lower()
    limit = min(max(int(arguments.get("limit") or 10), 1), 50)
    scan_limit = min(max(int(arguments.get("scan_limit") or 500), limit), 3000)

    problems = LeetCodeClient(prefer_cn=True).fetch_problem_list(limit=scan_limit)
    matched = []
    for problem in problems:
        if difficulty and problem.get("difficulty") != difficulty:
            continue
        if tag and tag not in _leetcode_list_problem_tags_text(problem):
            continue
        if query and query not in _leetcode_list_problem_search_text(problem):
            continue
        matched.append(_leetcode_list_problem_to_tool_dict(problem))

    return {
        "scanned": len(problems),
        "count": len(matched),
        "problems": matched[:limit],
    }


def _run_python_examples(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    problem_id = _read_required_string(arguments, "problem_id")
    code = _read_required_string(arguments, "code")
    language = str(arguments.get("language") or "Python")

    problem = _problem_store(context).get_problem(problem_id)
    result = PythonSubmissionRunner().run_examples(problem, code, language)
    return _run_result_to_tool_dict(result)


def _problem_store(context: ToolContext) -> ProblemStore:
    return ProblemStore(
        context.data_dir,
        context.runtime_dir,
        legacy_runtime_dir=context.legacy_runtime_dir,
    )


def _problem_to_tool_dict(problem: Problem) -> dict[str, Any]:
    data = problem.model_dump(mode="json")
    data["resolved_function_signature"] = get_python_function_signature(problem)
    data["resolved_function_name"] = problem.function_name or infer_method_name(problem.id)
    description = str(data.get("description") or "")
    if len(description) > 6000:
        data["description"] = f"{description[:6000]}\n...[truncated]"
    return data


def _problem_search_text(problem: Problem) -> str:
    parts = [
        problem.id,
        str(problem.leetcode_id or ""),
        problem.title,
        problem.difficulty,
        " ".join(problem.tags),
        problem.description,
    ]
    return " ".join(parts).lower()


def _leetcode_list_problem_to_tool_dict(problem: dict[str, Any]) -> dict[str, Any]:
    tags = [
        {
            "name": item.get("name", ""),
            "name_translated": item.get("nameTranslated", ""),
            "slug": item.get("slug", ""),
        }
        for item in problem.get("topicTags") or []
    ]
    return {
        "leetcode_id": problem.get("frontendQuestionId"),
        "id": problem.get("titleSlug"),
        "title": problem.get("title"),
        "title_cn": problem.get("titleCn"),
        "difficulty": problem.get("difficulty"),
        "paid_only": problem.get("paidOnly", False),
        "ac_rate": problem.get("acRate"),
        "tags": tags,
    }


def _leetcode_list_problem_search_text(problem: dict[str, Any]) -> str:
    parts = [
        str(problem.get("frontendQuestionId") or ""),
        str(problem.get("title") or ""),
        str(problem.get("titleCn") or ""),
        str(problem.get("titleSlug") or ""),
        _leetcode_list_problem_tags_text(problem),
    ]
    return " ".join(parts).lower()


def _leetcode_list_problem_tags_text(problem: dict[str, Any]) -> str:
    parts = []
    for item in problem.get("topicTags") or []:
        parts.extend(
            [
                str(item.get("name") or ""),
                str(item.get("nameTranslated") or ""),
                str(item.get("slug") or ""),
            ]
        )
    return " ".join(parts).lower()


def _run_result_to_tool_dict(result: SubmissionRunResult) -> dict[str, Any]:
    return {
        "ran": result.ran,
        "passed": result.passed,
        "skipped_reason": result.skipped_reason,
        "results": [
            {
                "index": item.index,
                "passed": item.passed,
                "input": item.input_text,
                "expected": item.expected_text,
                "actual": item.actual,
                "error": item.error,
            }
            for item in result.results
        ],
    }


def _read_required_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少必填参数: {key}")
    return value.strip()
