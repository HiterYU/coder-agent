# 文件用途：定义训练 Agent 的核心领域模型与运行时数据结构。
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    """生成当前 UTC 时间的 ISO 字符串。

    参数：
        无。

    返回：
        去除微秒后的 UTC ISO 时间字符串。
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    """生成带业务前缀的短随机 ID。

    参数：
        prefix: ID 前缀，用于区分会话、提交等业务实体。

    返回：
        形如 `{prefix}_xxxxxxxxxxxx` 的短 ID。
    """
    return f"{prefix}_{uuid4().hex[:12]}"


class SessionStatus(str, Enum):
    READING = "reading"
    THINKING = "thinking"
    CODING = "coding"
    DEBUGGING = "debugging"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    COMPLETED = "completed"


class Example(BaseModel):
    input: str
    output: str
    explanation: str = ""


class Approach(BaseModel):
    name: str
    time_complexity: str
    space_complexity: str
    summary: str


class CommonMistake(BaseModel):
    type: str
    description: str


class Problem(BaseModel):
    id: str
    leetcode_id: int | None = None
    title: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    tags: list[str]
    description: str
    examples: list[Example] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    # LeetCode 返回的 Python 初始代码模板，用于还原函数签名。
    starter_code: str = ""
    # Python 函数签名，例如 `def twoSum(self, nums: List[int], target: int) -> List[int]:`。
    function_signature: str = ""
    # Python 方法名，例如 `twoSum`。
    function_name: str = ""
    expected_approaches: list[Approach] = Field(default_factory=list)
    common_mistakes: list[CommonMistake] = Field(default_factory=list)
    similar_problem_ids: list[str] = Field(default_factory=list)
    interview_value: float = 0.5
    prerequisites: list[str] = Field(default_factory=list)


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    type: Literal["thought", "question", "code", "hint", "review", "note"]
    content: str
    created_at: str = Field(default_factory=utc_now)


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: new_id("s"))
    user_id: str
    problem_id: str
    language: str = "Python"
    status: SessionStatus = SessionStatus.READING
    started_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    current_stage: str = "reading"
    hints_given: list[int] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    current_code: str = ""
    submission_ids: list[str] = Field(default_factory=list)


class Mistake(BaseModel):
    type: str
    topic: str = "general"
    severity: Literal["low", "medium", "high"] = "medium"
    evidence: str


class ExampleRunRecord(BaseModel):
    index: int
    passed: bool = False
    input: str = ""
    expected: str = ""
    actual: str = ""
    error: str = ""


class ReviewResult(BaseModel):
    submission_id: str = Field(default_factory=lambda: new_id("sub"))
    session_id: str
    is_likely_correct: bool
    passed_sample_tests: bool = False
    sample_test_results: list[ExampleRunRecord] = Field(default_factory=list)
    time_complexity: str = "Unknown"
    space_complexity: str = "Unknown"
    mistakes: list[Mistake] = Field(default_factory=list)
    feedback: str
    next_actions: list[str] = Field(default_factory=list)
    # 本次复盘实际加载的 Skill 名称，只用于展示和审计，不参与判断。
    used_skills: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)


class Strength(BaseModel):
    topic: str
    confidence: float = 0.3
    evidence_count: int = 1


class Weakness(BaseModel):
    topic: str
    pattern: str
    confidence: float = 0.3
    evidence_count: int = 1
    last_seen_at: str = Field(default_factory=utc_now)


class MistakePattern(BaseModel):
    type: str
    count: int = 1
    last_seen_at: str = Field(default_factory=utc_now)
    example_problem_ids: list[str] = Field(default_factory=list)


class TopicMistakeProfile(BaseModel):
    topic: str
    total_mistakes: int = 0
    mistake_counts: dict[str, int] = Field(default_factory=dict)
    example_problem_ids: list[str] = Field(default_factory=list)
    last_seen_at: str = Field(default_factory=utc_now)


class HintStats(BaseModel):
    total_hints: int = 0
    average_hint_level: float = 0
    level_4_or_5_count: int = 0


class UserProfile(BaseModel):
    user_id: str
    language: str = "Python"
    goal: str = "interview"
    solved_problem_ids: list[str] = Field(default_factory=list)
    strengths: list[Strength] = Field(default_factory=list)
    weaknesses: list[Weakness] = Field(default_factory=list)
    common_mistakes: list[MistakePattern] = Field(default_factory=list)
    topic_mistake_profiles: list[TopicMistakeProfile] = Field(default_factory=list)
    hint_stats: HintStats = Field(default_factory=HintStats)
