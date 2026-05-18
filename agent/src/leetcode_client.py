from __future__ import annotations

# 文件用途：从 LeetCode 国际站或中国站 GraphQL 抓取题目，并转换为当前程序的 Problem 模型。

import re
import time
from html import unescape
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from .code_templates import extract_python_function_metadata, select_python_starter_code
from .config import load_leetcode_config, resolve_config_path
from .models import CommonMistake, Example, Problem


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = resolve_config_path(PROJECT_DIR)
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
LEETCODE_CN_GRAPHQL_URL = "https://leetcode.cn/graphql/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36"
)


QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    difficulty
    content
    exampleTestcases
    codeSnippets {
      lang
      langSlug
      code
    }
    topicTags {
      name
      slug
    }
  }
}
"""

CN_QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    translatedTitle
    titleSlug
    difficulty
    content
    translatedContent
    exampleTestcases
    codeSnippets {
      lang
      langSlug
      code
    }
    topicTags {
      name
      nameTranslated
      slug
    }
  }
}
"""

QUESTION_LIST_QUERY = """
query problemsetQuestionList(
  $categorySlug: String,
  $limit: Int,
  $skip: Int,
  $filters: QuestionListFilterInput
) {
  problemsetQuestionList(
    categorySlug: $categorySlug,
    limit: $limit,
    skip: $skip,
    filters: $filters
  ) {
    hasMore
    total
    questions {
      acRate
      difficulty
      freqBar
      frontendQuestionId
      isFavor
      paidOnly
      solutionNum
      status
      title
      titleCn
      titleSlug
      topicTags {
        name
        nameTranslated
        id
        slug
      }
    }
  }
}
"""


class LeetCodeClient:
    """LeetCode GraphQL 客户端。

    参数:
        csrftoken: LeetCode 中国站 csrftoken；为空时读取项目配置。
        prefer_cn: 是否优先使用 LeetCode 中国站；为空时读取项目配置。
        retry_count: 请求失败时的重试次数。
        timeout: HTTP 请求超时时间，单位秒。

    返回值:
        无。实例化后可抓取题目详情或中国站题目列表。
    """

    def __init__(
        self,
        csrftoken: str | None = None,
        prefer_cn: bool | None = None,
        retry_count: int | None = None,
        timeout: int | None = None,
        config_path: str | Path | None = None,
        category_slug: str | None = None,
        page_size: int | None = None,
    ):
        """初始化 LeetCode GraphQL 客户端。

        参数:
            csrftoken: LeetCode 中国站 csrftoken；为空时读取配置文件。
            prefer_cn: 是否优先请求中国站；为空时读取配置文件。
            retry_count: 请求失败时的重试次数。
            timeout: HTTP 请求超时时间，单位秒。
            config_path: 可选项目配置文件路径；默认读取 `agent/settings.json`，兼容 `agent/config.toml`。
            category_slug: 中国站题库列表分类 slug。
            page_size: 中国站题库列表分页大小。

        返回值:
            无。
        """
        config = load_leetcode_config(config_path or DEFAULT_CONFIG_PATH)
        self.csrftoken = csrftoken or config.csrftoken or ""
        self.prefer_cn = prefer_cn if prefer_cn is not None else config.prefer_cn
        self.retry_count = max(retry_count or config.retry_count, 1)
        self.timeout = timeout or config.timeout
        self.category_slug = category_slug or config.category_slug
        self.page_size = max(page_size or config.page_size, 1)

    def fetch_problem(self, url_or_slug: str) -> Problem:
        """抓取单题并转换为当前程序使用的 Problem 模型。

        参数:
            url_or_slug: LeetCode 题目 URL 或 slug，支持 leetcode.com 和 leetcode.cn。

        返回值:
            Problem: 标准化后的题目数据。
        """
        slug = self.extract_slug(url_or_slug)
        endpoints = self._candidate_question_endpoints(url_or_slug)
        last_error: Exception | None = None

        for endpoint in endpoints:
            try:
                question = self._fetch_question(slug, endpoint)
                return self._to_problem(question, prefer_translated=endpoint == LEETCODE_CN_GRAPHQL_URL)
            except Exception as exc:
                last_error = exc

        raise ValueError(f"LeetCode problem not found: {slug}; last_error={last_error}")

    def fetch_problem_list(
        self,
        limit: int | None = None,
        page_size: int | None = None,
        category_slug: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """分页抓取 LeetCode 中国站题目列表。

        参数:
            limit: 最多返回多少道题；为空时抓取全部可见题目。
            page_size: 每页请求数量。
            category_slug: 中国站题库分类 slug。
            filters: GraphQL 过滤条件。

        返回值:
            list[dict[str, Any]]: LeetCode 中国站返回的题目摘要列表。
        """
        problems: list[dict[str, Any]] = []
        offset = 0
        page_size = max(page_size or self.page_size, 1)
        category_slug = category_slug or self.category_slug

        while True:
            data = self.fetch_question_list_by_range(
                offset=offset,
                limit=page_size,
                category_slug=category_slug,
                filters=filters,
            )
            block = data.get("data", {}).get("problemsetQuestionList", {})
            batch = block.get("questions") or []
            problems.extend(batch)

            if limit is not None and len(problems) >= limit:
                return problems[:limit]
            if not block.get("hasMore") or not batch:
                return problems
            offset += page_size

    def fetch_question_list_by_range(
        self,
        offset: int,
        limit: int,
        category_slug: str = "all-code-essentials",
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """按分页范围抓取 LeetCode 中国站题目列表原始数据。

        参数:
            offset: 跳过的题目数量。
            limit: 本页请求数量。
            category_slug: 中国站题库分类 slug。
            filters: GraphQL 过滤条件。

        返回值:
            dict[str, Any]: GraphQL JSON 响应。
        """
        payload = {
            "query": QUESTION_LIST_QUERY,
            "variables": {
                "categorySlug": category_slug,
                "skip": offset,
                "limit": limit,
                "filters": filters or {},
            },
            "operationName": "problemsetQuestionList",
        }
        return self.request_cn(payload)

    def fetch_problem_content(self, title_slug: str) -> dict[str, str]:
        """抓取 LeetCode 中国站单题中英文 HTML 题面。

        参数:
            title_slug: 题目 slug，例如 two-sum。

        返回值:
            dict[str, str]: 包含 `cn` 和 `en` 两份 HTML 题面。
        """
        question = self._fetch_question(title_slug, LEETCODE_CN_GRAPHQL_URL)
        return {
            "cn": question.get("translatedContent") or "",
            "en": question.get("content") or "",
        }

    def request_cn(self, data: dict[str, Any]) -> dict[str, Any]:
        """向 LeetCode 中国站 GraphQL 发送请求。

        参数:
            data: GraphQL 请求体。

        返回值:
            dict[str, Any]: GraphQL JSON 响应。
        """
        return self._post_graphql(LEETCODE_CN_GRAPHQL_URL, data)

    def extract_slug(self, url_or_slug: str) -> str:
        """从 LeetCode URL 或裸 slug 中提取题目 slug。

        参数:
            url_or_slug: LeetCode 题目 URL 或 slug。

        返回值:
            str: 题目 slug。
        """
        value = url_or_slug.strip()
        if not value:
            raise ValueError("请输入 LeetCode 题目 URL 或 slug。")

        match = re.search(r"leetcode\.(?:com|cn)/problems/([^/?#]+)/?", value)
        if match:
            return match.group(1)
        return value.strip("/").split("/")[-1]

    def _candidate_question_endpoints(self, url_or_slug: str) -> list[str]:
        prefer_cn = self.prefer_cn or "leetcode.cn" in url_or_slug.lower()
        if prefer_cn:
            return [LEETCODE_CN_GRAPHQL_URL, LEETCODE_GRAPHQL_URL]
        return [LEETCODE_GRAPHQL_URL, LEETCODE_CN_GRAPHQL_URL]

    def _fetch_question(self, slug: str, endpoint: str) -> dict[str, Any]:
        query = CN_QUESTION_QUERY if endpoint == LEETCODE_CN_GRAPHQL_URL else QUESTION_QUERY
        payload = {
            "query": query,
            "variables": {"titleSlug": slug},
            "operationName": "questionData",
        }
        data = self._post_graphql(endpoint, payload, referer_slug=slug)
        question = data.get("data", {}).get("question")
        if not question:
            raise ValueError(f"LeetCode problem not found: {slug}")
        return question

    def _post_graphql(
        self,
        endpoint: str,
        payload: dict[str, Any],
        referer_slug: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if referer_slug:
            site = "leetcode.cn" if endpoint == LEETCODE_CN_GRAPHQL_URL else "leetcode.com"
            headers["Referer"] = f"https://{site}/problems/{referer_slug}/"
        if endpoint == LEETCODE_CN_GRAPHQL_URL and self.csrftoken:
            headers["Cookie"] = f"csrftoken={self.csrftoken};"
            headers["x-csrftoken"] = self.csrftoken

        response: requests.Response | None = None
        for trial in range(1, self.retry_count + 1):
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("errors") and not data.get("data"):
                    raise RuntimeError(f"LeetCode GraphQL error: {data['errors']}")
                return data
            if trial < self.retry_count:
                time.sleep(trial**2)

        status = response.status_code if response is not None else "unknown"
        body = response.text if response is not None else ""
        raise RuntimeError(f"Fail to fetch LeetCode data: status={status}, body={body[:500]}")

    def _to_problem(self, question: dict[str, Any], prefer_translated: bool = False) -> Problem:
        content_html = self._question_content_html(question, prefer_translated)
        text = self._html_to_text(content_html)
        examples = self._extract_examples(text, question.get("exampleTestcases") or "")
        constraints = self._extract_constraints(text)
        tags = self._extract_tags(question.get("topicTags") or [])
        starter_code = select_python_starter_code(question.get("codeSnippets") or [])
        function_signature, function_name = extract_python_function_metadata(starter_code)

        return Problem(
            id=str(question["titleSlug"]),
            leetcode_id=self._parse_leetcode_id(question),
            title=self._question_title(question, prefer_translated),
            difficulty=self._normalize_difficulty(question.get("difficulty")),
            tags=tags,
            description=self._strip_constraints(text),
            examples=examples,
            constraints=constraints,
            starter_code=starter_code,
            function_signature=function_signature,
            function_name=function_name,
            expected_approaches=[],
            common_mistakes=self._default_mistakes(tags),
            similar_problem_ids=[],
            interview_value=0.5,
            prerequisites=[],
        )

    def _question_content_html(self, question: dict[str, Any], prefer_translated: bool) -> str:
        if prefer_translated and question.get("translatedContent"):
            return str(question["translatedContent"])
        return str(question.get("content") or question.get("translatedContent") or "")

    def _question_title(self, question: dict[str, Any], prefer_translated: bool) -> str:
        if prefer_translated and question.get("translatedTitle"):
            return str(question["translatedTitle"])
        return str(question.get("title") or question.get("translatedTitle") or question["titleSlug"])

    def _parse_leetcode_id(self, question: dict[str, Any]) -> int | None:
        raw_id = (
            question.get("questionFrontendId")
            or question.get("frontendQuestionId")
            or question.get("questionId")
        )
        try:
            return int(str(raw_id))
        except (TypeError, ValueError):
            return None

    def _normalize_difficulty(self, difficulty: Any) -> str:
        value = str(difficulty or "Medium")
        difficulty_map = {
            "简单": "Easy",
            "中等": "Medium",
            "困难": "Hard",
        }
        normalized = difficulty_map.get(value, value)
        return normalized if normalized in {"Easy", "Medium", "Hard"} else "Medium"

    def _extract_tags(self, raw_tags: list[dict[str, Any]]) -> list[str]:
        tags: list[str] = []
        for item in raw_tags:
            tag = str(item.get("name") or item.get("nameTranslated") or "").strip()
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for code in soup.find_all("code"):
            code.string = code.get_text()
        text = soup.get_text("\n")
        lines = [unescape(line.strip()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _extract_examples(self, text: str, example_testcases: str) -> list[Example]:
        examples: list[Example] = []
        blocks = re.split(r"(?:Example|示例)\s*\d+\s*[:：]", text, flags=re.IGNORECASE)
        for block in blocks[1:]:
            input_match = re.search(r"(?:Input|输入)\s*[:：]\s*(.+)", block, re.IGNORECASE)
            output_match = re.search(r"(?:Output|输出)\s*[:：]\s*(.+)", block, re.IGNORECASE)
            explanation_match = re.search(
                r"(?:Explanation|解释)\s*[:：]\s*(.+)",
                block,
                re.IGNORECASE,
            )
            if input_match and output_match:
                examples.append(
                    Example(
                        input=input_match.group(1).strip(),
                        output=output_match.group(1).strip(),
                        explanation=explanation_match.group(1).strip()
                        if explanation_match
                        else "",
                    )
                )
        if examples:
            return examples
        if example_testcases:
            return [
                Example(
                    input=example_testcases.strip(),
                    output="",
                    explanation="LeetCode sample testcases",
                )
            ]
        return []

    def _extract_constraints(self, text: str) -> list[str]:
        constraints_text = self._text_after_first_marker(text, ["Constraints:", "提示：", "提示:"])
        if not constraints_text:
            return []

        lines = []
        for line in constraints_text.splitlines():
            cleaned = line.strip(" -")
            if cleaned:
                lines.append(cleaned)
        return lines

    def _strip_constraints(self, text: str) -> str:
        marker_index = self._first_marker_index(text, ["Constraints:", "提示：", "提示:"])
        if marker_index == -1:
            return text.strip()
        return text[:marker_index].strip()

    def _text_after_first_marker(self, text: str, markers: list[str]) -> str:
        marker_index = self._first_marker_index(text, markers)
        if marker_index == -1:
            return ""
        for marker in markers:
            if text.startswith(marker, marker_index):
                return text[marker_index + len(marker) :].strip()
        return ""

    def _first_marker_index(self, text: str, markers: list[str]) -> int:
        indexes = [text.find(marker) for marker in markers if marker in text]
        return min(indexes) if indexes else -1

    def _default_mistakes(self, tags: list[str]) -> list[CommonMistake]:
        mistakes = [
            CommonMistake(type="boundary_condition_missing", description="边界条件遗漏"),
            CommonMistake(type="return_format_wrong", description="返回格式和题目要求不一致"),
        ]
        if "Dynamic Programming" in tags:
            mistakes.append(CommonMistake(type="wrong_state_definition", description="DP 状态定义不清晰"))
        if "Binary Search" in tags:
            mistakes.append(CommonMistake(type="wrong_loop_condition", description="二分循环条件或边界更新错误"))
        if "Depth-First Search" in tags or "Breadth-First Search" in tags or "Graph" in tags:
            mistakes.append(CommonMistake(type="visited_handling_wrong", description="visited 或边界处理错误"))
        if "Sliding Window" in tags:
            mistakes.append(CommonMistake(type="wrong_loop_condition", description="滑动窗口收缩条件错误"))
        return mistakes


class LcCrawler:
    """兼容旧脚本命名的 LeetCode 中国站抓题工具。

    参数:
        csrftoken: LeetCode 中国站 csrftoken；建议通过环境变量传入。

    返回值:
        无。实例化后可抓题目列表、题面或当前程序的 Problem 对象。
    """

    def __init__(self, csrftoken: str = ""):
        """初始化中国站抓题工具。

        参数:
            csrftoken: LeetCode 中国站 csrftoken。

        返回值:
            无。
        """
        self.client = LeetCodeClient(csrftoken=csrftoken, prefer_cn=True)

    def fetch_problem_list(self, limit: int | None = None) -> list[dict[str, Any]]:
        """抓取 LeetCode 中国站题目列表。

        参数:
            limit: 最多返回多少道题；为空时抓取全部。

        返回值:
            list[dict[str, Any]]: 中国站题目摘要列表。
        """
        return self.client.fetch_problem_list(limit=limit)

    def fetch_question_list_by_range(self, offset: int, limit: int) -> dict[str, Any]:
        """按分页范围抓取 LeetCode 中国站题目列表原始数据。

        参数:
            offset: 跳过的题目数量。
            limit: 本页请求数量。

        返回值:
            dict[str, Any]: GraphQL JSON 响应。
        """
        return self.client.fetch_question_list_by_range(offset=offset, limit=limit)

    def fetch_problem_content(self, title_slug: str) -> dict[str, str]:
        """抓取单题中英文 HTML 题面。

        参数:
            title_slug: 题目 slug。

        返回值:
            dict[str, str]: 包含 `cn` 和 `en` 的 HTML 题面。
        """
        return self.client.fetch_problem_content(title_slug)

    def fetch_problem(self, title_slug: str) -> Problem:
        """抓取单题并转换为当前程序的 Problem 模型。

        参数:
            title_slug: 题目 slug。

        返回值:
            Problem: 当前程序使用的题目模型。
        """
        return self.client.fetch_problem(f"https://leetcode.cn/problems/{title_slug}/")

    def fetch_problems(self, limit: int | None = None) -> list[Problem]:
        """批量抓取题目列表对应的 Problem 模型。

        参数:
            limit: 最多抓取多少道题；为空时抓取全部可见题目。

        返回值:
            list[Problem]: 当前程序使用的题目模型列表。
        """
        problems = []
        for item in self.fetch_problem_list(limit=limit):
            problems.append(self.fetch_problem(str(item["titleSlug"])))
        return problems
