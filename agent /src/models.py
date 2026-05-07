from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


if not hasattr(BaseModel, "model_validate"):
    BaseModel.model_validate = classmethod(lambda cls, value: cls.parse_obj(value))

if not hasattr(BaseModel, "model_dump"):
    def _model_dump(self, mode: str = "python", **kwargs):
        if mode == "json":
            return json.loads(self.json())
        return self.dict(**kwargs)

    BaseModel.model_dump = _model_dump

if not hasattr(BaseModel, "model_dump_json"):
    def _model_dump_json(self, indent: int | None = None, **kwargs):
        return self.json(ensure_ascii=False, indent=indent, **kwargs)

    BaseModel.model_dump_json = _model_dump_json


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
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


class ReviewResult(BaseModel):
    submission_id: str = Field(default_factory=lambda: new_id("sub"))
    session_id: str
    is_likely_correct: bool
    passed_sample_tests: bool = False
    time_complexity: str = "Unknown"
    space_complexity: str = "Unknown"
    mistakes: list[Mistake] = Field(default_factory=list)
    feedback: str
    next_actions: list[str] = Field(default_factory=list)
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
