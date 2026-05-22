from __future__ import annotations

# 文件用途：验证分级提示引擎的本地兜底逻辑与 LLM 提示融合行为。

from dataclasses import dataclass
from typing import Any

from src.hint_engine import HintEngine
from src.models import (
    Approach,
    CommonMistake,
    Message,
    Problem,
    Session,
    UserProfile,
    Weakness,
)


@dataclass
class _StubLlm:
    """测试用 LLM 客户端桩。

    参数:
        available: 是否报告为可用。
        response: complete_json 的固定返回值。

    返回值:
        无。
    """

    available: bool = False
    response: dict[str, Any] | None = None
    captured_user: str = ""
    captured_system: str = ""

    def complete_json(
        self, system: str, user: str, agent_name: str | None = None
    ) -> dict[str, Any] | None:
        """模拟 LLM JSON 响应。"""
        self.captured_system = system
        self.captured_user = user
        return self.response


def _make_problem(**overrides: Any) -> Problem:
    base = {
        "id": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "description": "返回两数之和的下标。",
        "examples": [],
        "constraints": [],
        "expected_approaches": [
            Approach(
                name="哈希表",
                time_complexity="O(n)",
                space_complexity="O(n)",
                summary="一次遍历，用哈希表保存补数。",
            )
        ],
        "common_mistakes": [CommonMistake(type="boundary_condition_missing", description="忘记检查同一下标。")],
    }
    base.update(overrides)
    return Problem(**base)


def _make_session(hints_given: list[int] | None = None, messages: list[Message] | None = None) -> Session:
    return Session(
        user_id="demo",
        problem_id="two-sum",
        hints_given=hints_given or [],
        messages=messages or [],
    )


def test_hint_engine_starts_from_level_one() -> None:
    """首次请求时提示等级应为 Level 1。"""
    engine = HintEngine(llm_client=_StubLlm(available=False))
    result = engine.generate_hint(_make_session(), _make_problem(), UserProfile(user_id="demo"))

    assert result["hint_level"] == 1
    assert result["hint_request_count"] == 1
    assert result["reveals_solution"] is False
    assert "忘记检查同一下标" in result["hint"] or "Two Sum" in result["hint"] or "Array" in result["hint"]


def test_hint_engine_increments_level_each_request() -> None:
    """连续提示请求应按 Level 递增并在 5 处封顶。"""
    engine = HintEngine(llm_client=_StubLlm(available=False))
    problem = _make_problem()
    profile = UserProfile(user_id="demo")

    for expected_level in (1, 2, 3, 4, 5):
        session = _make_session(hints_given=list(range(1, expected_level)))
        result = engine.generate_hint(session, problem, profile)
        assert result["hint_level"] == expected_level

    capped = engine.generate_hint(_make_session(hints_given=[1, 2, 3, 4, 5]), problem, profile)
    assert capped["hint_level"] == 5


def test_hint_engine_marks_reveals_solution_at_level_five() -> None:
    """Level 5 提示应标记 reveals_solution=True。"""
    engine = HintEngine(llm_client=_StubLlm(available=False))
    result = engine.generate_hint(
        _make_session(hints_given=[1, 2, 3, 4]),
        _make_problem(),
        UserProfile(user_id="demo"),
    )
    assert result["hint_level"] == 5
    assert result["reveals_solution"] is True


def test_hint_engine_follow_up_after_five_requests_keeps_level_five() -> None:
    """超过 5 次请求后提示等级保持 5，但请求轮次继续递增。"""
    engine = HintEngine(llm_client=_StubLlm(available=False))
    session = _make_session(hints_given=[1, 2, 3, 4, 5, 5])
    result = engine.generate_hint(session, _make_problem(), UserProfile(user_id="demo"))

    assert result["hint_level"] == 5
    assert result["hint_request_count"] == 7
    assert "第 7 次提示" in result["hint"]


def test_hint_engine_profile_warning_includes_known_weakness() -> None:
    """命中历史薄弱点时 Level 2 提示应附带提醒。"""
    engine = HintEngine(llm_client=_StubLlm(available=False))
    profile = UserProfile(
        user_id="demo",
        weaknesses=[
            Weakness(
                topic="array",
                pattern="boundary_condition_missing",
                confidence=0.7,
                evidence_count=2,
            )
        ],
    )
    session = _make_session(hints_given=[1])
    result = engine.generate_hint(session, _make_problem(), profile)

    assert result["hint_level"] == 2
    assert "boundary_condition_missing" in result["hint"]


def test_hint_engine_uses_llm_response_when_available() -> None:
    """LLM 可用且返回有效 JSON 时，应直接返回并覆盖等级与轮次。"""
    stub = _StubLlm(
        available=True,
        response={
            "hint_level": 99,
            "hint_request_count": 99,
            "hint": "考虑哈希表存补数。",
            "why_this_hint": "来自 LLM。",
            "reveals_solution": False,
        },
    )
    engine = HintEngine(llm_client=stub)
    session = _make_session(hints_given=[1, 2], messages=[Message(role="user", type="question", content="卡在哪里？")])
    result = engine.generate_hint(session, _make_problem(), UserProfile(user_id="demo"))

    assert result["hint_level"] == 3
    assert result["hint_request_count"] == 3
    assert result["hint"] == "考虑哈希表存补数。"
    assert "卡在哪里？" in stub.captured_user


def test_hint_engine_falls_back_when_llm_response_missing_hint() -> None:
    """LLM 返回非法 JSON 时应回退到本地兜底。"""
    stub = _StubLlm(available=True, response={"why_this_hint": "缺 hint"})
    engine = HintEngine(llm_client=stub)
    result = engine.generate_hint(_make_session(), _make_problem(), UserProfile(user_id="demo"))

    assert result["hint_level"] == 1
    assert "why_this_hint" in result
    assert result["hint"] != "缺 hint"
