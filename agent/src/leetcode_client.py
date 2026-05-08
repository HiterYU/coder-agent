from __future__ import annotations

import re
from html import unescape

import requests
from bs4 import BeautifulSoup

from .models import CommonMistake, Example, Problem


LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"


QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    titleSlug
    difficulty
    content
    exampleTestcases
    topicTags {
      name
    }
  }
}
"""


class LeetCodeClient:
    def fetch_problem(self, url_or_slug: str) -> Problem:
        slug = self.extract_slug(url_or_slug)
        response = requests.post(
            LEETCODE_GRAPHQL_URL,
            json={"query": QUESTION_QUERY, "variables": {"titleSlug": slug}},
            headers={
                "Content-Type": "application/json",
                "Referer": f"https://leetcode.com/problems/{slug}/",
                "User-Agent": "leetcode-training-agent/0.1",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        question = payload.get("data", {}).get("question")
        if not question:
            raise ValueError(f"LeetCode problem not found: {slug}")
        return self._to_problem(question)

    def extract_slug(self, url_or_slug: str) -> str:
        value = url_or_slug.strip()
        if not value:
            raise ValueError("请输入 LeetCode 题目 URL 或 slug。")
        match = re.search(r"leetcode\.com/problems/([^/?#]+)/?", value)
        if match:
            return match.group(1)
        return value.strip("/").split("/")[-1]

    def _to_problem(self, question: dict) -> Problem:
        content_html = question.get("content") or ""
        text = self._html_to_text(content_html)
        examples = self._extract_examples(text, question.get("exampleTestcases") or "")
        constraints = self._extract_constraints(text)
        tags = [item["name"] for item in question.get("topicTags", [])]
        description = self._strip_constraints(text)

        return Problem(
            id=question["titleSlug"],
            leetcode_id=int(question["questionId"]) if question.get("questionId") else None,
            title=question["title"],
            difficulty=question["difficulty"],
            tags=tags,
            description=description,
            examples=examples,
            constraints=constraints,
            expected_approaches=[],
            common_mistakes=self._default_mistakes(tags),
            similar_problem_ids=[],
            interview_value=0.5,
            prerequisites=[],
        )

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for code in soup.find_all("code"):
            code.string = code.get_text()
        text = soup.get_text("\n")
        lines = [unescape(line.strip()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _extract_examples(self, text: str, example_testcases: str) -> list[Example]:
        examples: list[Example] = []
        blocks = re.split(r"Example\s+\d+:", text)
        for block in blocks[1:]:
            input_match = re.search(r"Input:\s*(.+)", block)
            output_match = re.search(r"Output:\s*(.+)", block)
            explanation_match = re.search(r"Explanation:\s*(.+)", block)
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
            return [Example(input=example_testcases.strip(), output="", explanation="LeetCode sample testcases")]
        return []

    def _extract_constraints(self, text: str) -> list[str]:
        marker = "Constraints:"
        if marker not in text:
            return []
        constraints_text = text.split(marker, 1)[1]
        lines = []
        for line in constraints_text.splitlines():
            cleaned = line.strip(" -")
            if cleaned:
                lines.append(cleaned)
        return lines

    def _strip_constraints(self, text: str) -> str:
        if "Constraints:" in text:
            return text.split("Constraints:", 1)[0].strip()
        return text.strip()

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
