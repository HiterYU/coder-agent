from __future__ import annotations

# 文件用途：验证用户画像引擎在提示、复盘后正确更新统计与薄弱点。

from pathlib import Path

from src.models import Mistake, Problem, ReviewResult, Session, UserProfile
from src.profile_engine import ProfileEngine


def _make_engine(tmp_path: Path) -> ProfileEngine:
    runtime_dir = tmp_path / "projects"
    seed_path = tmp_path / "seed.json"
    return ProfileEngine(runtime_dir=runtime_dir, seed_profile_path=seed_path)


def _make_problem() -> Problem:
    return Problem(
        id="two-sum",
        title="Two Sum",
        difficulty="Easy",
        tags=["Array", "Hash Table"],
        description="返回两数之和的下标。",
    )


def _make_session() -> Session:
    return Session(user_id="demo", problem_id="two-sum")


def _make_review(is_correct: bool, mistakes: list[Mistake] | None = None) -> ReviewResult:
    return ReviewResult(
        session_id="s_demo",
        is_likely_correct=is_correct,
        feedback="测试。",
        mistakes=mistakes or [],
    )


def test_profile_engine_creates_empty_profile_when_no_seed(tmp_path: Path) -> None:
    """没有种子文件且数据库为空时应返回最小用户画像。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")

    assert isinstance(profile, UserProfile)
    assert profile.user_id == "demo"
    assert profile.solved_problem_ids == []
    assert profile.hint_stats.total_hints == 0


def test_profile_engine_loads_seed_profile_when_available(tmp_path: Path) -> None:
    """缺少持久化画像时应回退到 seed 文件，并覆盖 user_id。"""
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        '{"language": "Python", "goal": "growth", "solved_problem_ids": ["climbing-stairs"]}',
        encoding="utf-8",
    )
    engine = ProfileEngine(runtime_dir=tmp_path / "projects", seed_profile_path=seed_path)

    profile = engine.get_profile("alice")

    assert profile.user_id == "alice"
    assert profile.goal == "growth"
    assert profile.solved_problem_ids == ["climbing-stairs"]


def test_profile_engine_persists_save_and_reload(tmp_path: Path) -> None:
    """save_profile 写入后再次 get_profile 应读取已保存数据。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")
    profile.goal = "interview-prep"
    profile.solved_problem_ids.append("two-sum")
    engine.save_profile(profile)

    reloaded = engine.get_profile("demo")
    assert reloaded.goal == "interview-prep"
    assert reloaded.solved_problem_ids == ["two-sum"]


def test_profile_engine_update_after_hint_tracks_average(tmp_path: Path) -> None:
    """update_after_hint 应正确累加并刷新均值与高级提示计数。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")
    engine.update_after_hint(profile, 2)
    engine.update_after_hint(profile, 4)
    engine.update_after_hint(profile, 5)

    refreshed = engine.get_profile("demo")
    assert refreshed.hint_stats.total_hints == 3
    assert refreshed.hint_stats.level_4_or_5_count == 2
    # (2 + 4 + 5) / 3 = 3.67
    assert refreshed.hint_stats.average_hint_level == 3.67


def test_profile_engine_update_after_review_adds_strength(tmp_path: Path) -> None:
    """正确解题且无错误时应为题目主要 topic 累计 strength。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")
    review = _make_review(is_correct=True)

    engine.update_after_review(profile, _make_session(), _make_problem(), review)

    refreshed = engine.get_profile("demo")
    assert "two-sum" in refreshed.solved_problem_ids
    strength_topics = {strength.topic for strength in refreshed.strengths}
    assert "array" in strength_topics


def test_profile_engine_update_after_review_records_mistake_patterns(tmp_path: Path) -> None:
    """复盘错误应同时落入 weaknesses、common_mistakes 和 topic_mistake_profiles。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")
    mistakes = [
        Mistake(type="boundary_condition_missing", topic="array", severity="medium", evidence="忽略空数组"),
    ]
    review = _make_review(is_correct=False, mistakes=mistakes)

    engine.update_after_review(profile, _make_session(), _make_problem(), review)
    engine.update_after_review(profile, _make_session(), _make_problem(), review)

    refreshed = engine.get_profile("demo")
    assert refreshed.solved_problem_ids == []
    assert refreshed.common_mistakes[0].type == "boundary_condition_missing"
    assert refreshed.common_mistakes[0].count == 2
    weakness = refreshed.weaknesses[0]
    assert weakness.topic == "array"
    assert weakness.pattern == "boundary_condition_missing"
    assert weakness.evidence_count == 2
    topic_profile = refreshed.topic_mistake_profiles[0]
    assert topic_profile.topic == "array"
    assert topic_profile.total_mistakes == 2
    assert topic_profile.mistake_counts == {"boundary_condition_missing": 2}


def test_profile_engine_update_after_review_does_not_duplicate_solved_problem(tmp_path: Path) -> None:
    """重复正确解同一道题不应在 solved 列表中重复出现。"""
    engine = _make_engine(tmp_path)
    profile = engine.get_profile("demo")
    review = _make_review(is_correct=True)

    engine.update_after_review(profile, _make_session(), _make_problem(), review)
    engine.update_after_review(profile, _make_session(), _make_problem(), review)

    refreshed = engine.get_profile("demo")
    assert refreshed.solved_problem_ids.count("two-sum") == 1
    strength = next(item for item in refreshed.strengths if item.topic == "array")
    assert strength.evidence_count == 2
