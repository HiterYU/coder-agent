from __future__ import annotations

# 文件用途：验证 LeetCode 客户端纯逻辑（slug 提取、HTML 解析、tag 处理等）。

from pathlib import Path

import pytest

from src.leetcode_client import LeetCodeClient


@pytest.fixture
def client(tmp_path: Path) -> LeetCodeClient:
    config_path = tmp_path / "settings.json"
    config_path.write_text("{}", encoding="utf-8")
    return LeetCodeClient(config_path=config_path)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://leetcode.com/problems/two-sum/", "two-sum"),
        ("https://leetcode.cn/problems/valid-parentheses/description", "valid-parentheses"),
        ("two-sum", "two-sum"),
        ("/problems/binary-search/", "binary-search"),
    ],
)
def test_extract_slug_handles_url_and_slug(client: LeetCodeClient, raw: str, expected: str) -> None:
    """extract_slug 应支持 leetcode.com、leetcode.cn URL 和裸 slug。"""
    assert client.extract_slug(raw) == expected


def test_extract_slug_raises_on_empty(client: LeetCodeClient) -> None:
    """空字符串应抛出 ValueError 提示用户输入。"""
    with pytest.raises(ValueError):
        client.extract_slug("   ")


def test_html_to_text_strips_html_and_unescapes(client: LeetCodeClient) -> None:
    """_html_to_text 应去除标签并还原 HTML 实体。"""
    html = "<p>Hello&nbsp;<code>world</code></p><p>&amp;</p>"
    text = client._html_to_text(html)

    assert "Hello" in text
    assert "world" in text
    assert "&amp;" not in text
    assert "<" not in text and ">" not in text


def test_extract_examples_parses_input_and_output(client: LeetCodeClient) -> None:
    """_extract_examples 应识别 Example 块并解析 Input/Output/Explanation。"""
    text = (
        "Example 1:\n"
        "Input: nums = [2,7,11,15], target = 9\n"
        "Output: [0,1]\n"
        "Explanation: nums[0] + nums[1] == 9\n"
        "Example 2:\n"
        "Input: nums = [3,2,4], target = 6\n"
        "Output: [1,2]\n"
    )

    examples = client._extract_examples(text, "")
    assert len(examples) == 2
    assert examples[0].input.startswith("nums = [2,7,11,15]")
    assert examples[0].output == "[0,1]"
    assert "nums[0] + nums[1] == 9" in examples[0].explanation
    assert examples[1].output == "[1,2]"


def test_extract_examples_falls_back_to_example_testcases(client: LeetCodeClient) -> None:
    """正文无 Example 块时应使用 exampleTestcases 兜底。"""
    examples = client._extract_examples("没有可解析的样例", "[2,7,11,15]\n9")

    assert len(examples) == 1
    assert "[2,7,11,15]" in examples[0].input
    assert examples[0].explanation == "LeetCode sample testcases"


def test_extract_constraints_returns_clean_lines(client: LeetCodeClient) -> None:
    """_extract_constraints 应提取 Constraints 后的非空行并清理标记。"""
    text = (
        "Description ...\n"
        "Constraints:\n"
        "- 2 <= nums.length <= 1000\n"
        "- 0 <= nums[i] <= 1000000\n"
    )

    constraints = client._extract_constraints(text)
    assert constraints == [
        "2 <= nums.length <= 1000",
        "0 <= nums[i] <= 1000000",
    ]


def test_extract_constraints_supports_cn_marker(client: LeetCodeClient) -> None:
    """中文站约束标记 `提示：` 同样能识别。"""
    text = "题目描述...\n提示：\n- 1 <= n <= 100\n"

    constraints = client._extract_constraints(text)
    assert constraints == ["1 <= n <= 100"]


def test_extract_tags_deduplicates(client: LeetCodeClient) -> None:
    """_extract_tags 应保留顺序并去重。"""
    raw_tags = [
        {"name": "Array", "slug": "array"},
        {"name": "Hash Table", "slug": "hash-table"},
        {"name": "Array", "slug": "array"},
        {"name": "", "slug": ""},
    ]
    tags = client._extract_tags(raw_tags)
    assert tags == ["Array", "Hash Table"]


def test_extract_tags_falls_back_to_translated_name(client: LeetCodeClient) -> None:
    """name 为空时应使用 nameTranslated。"""
    raw_tags = [{"name": "", "nameTranslated": "数组", "slug": "array"}]
    assert client._extract_tags(raw_tags) == ["数组"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Easy", "Easy"),
        ("Medium", "Medium"),
        ("Hard", "Hard"),
        ("简单", "Easy"),
        ("中等", "Medium"),
        ("困难", "Hard"),
        ("unknown", "Medium"),
        (None, "Medium"),
    ],
)
def test_normalize_difficulty(client: LeetCodeClient, raw: str | None, expected: str) -> None:
    """中英文难度都应能映射到允许的取值。"""
    assert client._normalize_difficulty(raw) == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ({"questionFrontendId": "1"}, 1),
        ({"questionId": "42"}, 42),
        ({"frontendQuestionId": "  7 "}, 7),
        ({}, None),
        ({"questionFrontendId": "abc"}, None),
    ],
)
def test_parse_leetcode_id_handles_multiple_field_names(
    client: LeetCodeClient, question: dict, expected: int | None
) -> None:
    """题号字段优先 questionFrontendId，其次 frontendQuestionId/questionId。"""
    assert client._parse_leetcode_id(question) == expected


def test_default_mistakes_basic_set(client: LeetCodeClient) -> None:
    """无特殊 tag 时返回边界与返回格式两个基础错误。"""
    mistakes = client._default_mistakes([])
    types = {item.type for item in mistakes}
    assert {"boundary_condition_missing", "return_format_wrong"} <= types


def test_default_mistakes_adds_tag_specific_entries(client: LeetCodeClient) -> None:
    """命中 DP、二分、BFS/DFS 的题目应附加对应错误模式。"""
    dp_types = {item.type for item in client._default_mistakes(["Dynamic Programming"])}
    bs_types = {item.type for item in client._default_mistakes(["Binary Search"])}
    bfs_types = {item.type for item in client._default_mistakes(["Breadth-First Search"])}

    assert "wrong_state_definition" in dp_types
    assert "wrong_loop_condition" in bs_types
    assert "visited_handling_wrong" in bfs_types


def test_candidate_question_endpoints_respects_prefer_cn(tmp_path: Path) -> None:
    """prefer_cn=True 时应优先 cn 端点，slug 含 leetcode.cn 时同样优先。"""
    config_path = tmp_path / "settings.json"
    config_path.write_text("{}", encoding="utf-8")

    client = LeetCodeClient(config_path=config_path, prefer_cn=True)
    assert client._candidate_question_endpoints("two-sum")[0].endswith("leetcode.cn/graphql/")

    client = LeetCodeClient(config_path=config_path, prefer_cn=False)
    endpoints = client._candidate_question_endpoints("https://leetcode.cn/problems/two-sum/")
    assert endpoints[0].endswith("leetcode.cn/graphql/")

    endpoints = client._candidate_question_endpoints("https://leetcode.com/problems/two-sum/")
    assert endpoints[0] == "https://leetcode.com/graphql"


def test_fetch_problem_uses_stubbed_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_problem 应通过 GraphQL 桩端到端构造 Problem。"""
    config_path = tmp_path / "settings.json"
    config_path.write_text("{}", encoding="utf-8")
    client = LeetCodeClient(config_path=config_path, prefer_cn=False)

    sample_question = {
        "questionFrontendId": "1",
        "questionId": "1",
        "title": "Two Sum",
        "titleSlug": "two-sum",
        "difficulty": "Easy",
        "content": (
            "<p>Given an array of integers...</p>"
            "<p><strong>Example 1:</strong></p>"
            "<pre>Input: nums = [2,7,11,15], target = 9\n"
            "Output: [0,1]\n"
            "Explanation: Because nums[0] + nums[1] == 9.</pre>"
            "<p><strong>Constraints:</strong></p>"
            "<ul><li>2 &lt;= nums.length &lt;= 1000</li></ul>"
        ),
        "exampleTestcases": "[2,7,11,15]\n9",
        "codeSnippets": [
            {
                "lang": "Python3",
                "langSlug": "python3",
                "code": "class Solution:\n    def twoSum(self, nums, target):\n        pass\n",
            }
        ],
        "topicTags": [
            {"name": "Array", "slug": "array"},
            {"name": "Hash Table", "slug": "hash-table"},
        ],
    }

    def fake_post_graphql(self: LeetCodeClient, endpoint: str, payload: dict, referer_slug=None):
        return {"data": {"question": sample_question}}

    monkeypatch.setattr(LeetCodeClient, "_post_graphql", fake_post_graphql)

    problem = client.fetch_problem("https://leetcode.com/problems/two-sum/")

    assert problem.id == "two-sum"
    assert problem.leetcode_id == 1
    assert problem.title == "Two Sum"
    assert problem.difficulty == "Easy"
    assert "Array" in problem.tags and "Hash Table" in problem.tags
    assert problem.function_name == "twoSum"
    assert problem.starter_code.startswith("class Solution")
    assert problem.examples and problem.examples[0].output == "[0,1]"
    assert any("nums.length" in line for line in problem.constraints)
