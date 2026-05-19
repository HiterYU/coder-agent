from __future__ import annotations

# 文件用途：管理用户长期画像，并根据提示和复盘结果更新能力统计。

from pathlib import Path

from .models import (
    MistakePattern,
    Problem,
    ReviewResult,
    Session,
    Strength,
    TopicMistakeProfile,
    UserProfile,
    Weakness,
    utc_now,
)
from .runtime_repository import SqliteRuntimeRepository
from .storage import JsonStorage
from .taxonomy import normalize_topic


class ProfileEngine:
    """用户画像管理器。

    参数:
        runtime_dir: 运行时目录。
        legacy_runtime_dir: 保留兼容参数；旧 JSON 需通过迁移命令手动导入 SQLite。
        seed_profile_path: 种子画像文件路径。

    返回值:
        无。实例化后可读取、保存和更新用户画像。
    """

    def __init__(
        self,
        runtime_dir: str | Path,
        seed_profile_path: str | Path,
        legacy_runtime_dir: str | Path | None = None,
    ):
        """初始化用户画像管理器。

        参数:
            runtime_dir: 运行时目录。
            legacy_runtime_dir: 保留兼容参数；不再自动读取旧 JSON。
            seed_profile_path: 种子画像文件路径。

        返回值:
            无。
        """
        self.storage = SqliteRuntimeRepository(runtime_dir)
        self.seed_profile_path = Path(seed_profile_path)

    def get_profile(self, user_id: str) -> UserProfile:
        """读取或创建用户画像。

        参数:
            user_id: 用户 ID。

        返回值:
            UserProfile: 用户长期画像。
        """
        raw = self.storage.load_json(f"profiles/{user_id}.json", None)
        if raw is not None:
            return UserProfile.model_validate(raw)
        if self.seed_profile_path.exists():
            seed = JsonStorage(self.seed_profile_path.parent).load_json(self.seed_profile_path.name, {})
            seed["user_id"] = user_id
            return UserProfile.model_validate(seed)
        return UserProfile(user_id=user_id)

    def save_profile(self, profile: UserProfile) -> None:
        """保存用户画像。

        参数:
            profile: 用户画像。

        返回值:
            无。
        """
        self.storage.save_json(f"profiles/{profile.user_id}.json", profile.model_dump(mode="json"))

    def update_after_hint(self, profile: UserProfile, hint_level: int) -> UserProfile:
        """根据提示使用情况更新画像。

        参数:
            profile: 用户画像。
            hint_level: 本次提示等级。

        返回值:
            UserProfile: 更新后的用户画像。
        """
        old_total = profile.hint_stats.total_hints
        old_average = profile.hint_stats.average_hint_level
        new_total = old_total + 1
        profile.hint_stats.total_hints = new_total
        profile.hint_stats.average_hint_level = round(
            ((old_average * old_total) + hint_level) / new_total, 2
        )
        if hint_level >= 4:
            profile.hint_stats.level_4_or_5_count += 1
        self.save_profile(profile)
        return profile

    def update_after_review(
        self, profile: UserProfile, session: Session, problem: Problem, review: ReviewResult
    ) -> UserProfile:
        """根据提交复盘结果更新画像。

        参数:
            profile: 用户画像。
            session: 当前训练会话。
            problem: 当前题目。
            review: 复盘结果。

        返回值:
            UserProfile: 更新后的用户画像。
        """
        if review.is_likely_correct and problem.id not in profile.solved_problem_ids:
            profile.solved_problem_ids.append(problem.id)

        if review.is_likely_correct and not review.mistakes:
            for tag in problem.tags[:2]:
                self._upsert_strength(profile, normalize_topic(tag))

        for mistake in review.mistakes:
            self._upsert_mistake_pattern(profile, mistake.type, problem.id)
            self._upsert_weakness(profile, mistake.topic, mistake.type)
            self._upsert_topic_mistake(profile, mistake.topic, mistake.type, problem.id)

        self.save_profile(profile)
        return profile

    def _upsert_strength(self, profile: UserProfile, topic: str) -> None:
        for strength in profile.strengths:
            if strength.topic == topic:
                strength.evidence_count += 1
                strength.confidence = min(0.95, round(strength.confidence + 0.1, 2))
                return
        profile.strengths.append(Strength(topic=topic, confidence=0.35, evidence_count=1))

    def _upsert_mistake_pattern(self, profile: UserProfile, mistake_type: str, problem_id: str) -> None:
        for pattern in profile.common_mistakes:
            if pattern.type == mistake_type:
                pattern.count += 1
                pattern.last_seen_at = utc_now()
                if problem_id not in pattern.example_problem_ids:
                    pattern.example_problem_ids.append(problem_id)
                return
        profile.common_mistakes.append(
            MistakePattern(
                type=mistake_type,
                count=1,
                last_seen_at=utc_now(),
                example_problem_ids=[problem_id],
            )
        )

    def _upsert_weakness(self, profile: UserProfile, topic: str, mistake_type: str) -> None:
        for weakness in profile.weaknesses:
            if weakness.topic == topic and weakness.pattern == mistake_type:
                weakness.evidence_count += 1
                weakness.confidence = min(0.95, round(weakness.confidence + 0.15, 2))
                weakness.last_seen_at = utc_now()
                return
        profile.weaknesses.append(
            Weakness(
                topic=topic,
                pattern=mistake_type,
                confidence=0.35,
                evidence_count=1,
                last_seen_at=utc_now(),
            )
        )

    def _upsert_topic_mistake(
        self, profile: UserProfile, topic: str, mistake_type: str, problem_id: str
    ) -> None:
        for item in profile.topic_mistake_profiles:
            if item.topic == topic:
                item.total_mistakes += 1
                item.mistake_counts[mistake_type] = item.mistake_counts.get(mistake_type, 0) + 1
                item.last_seen_at = utc_now()
                if problem_id not in item.example_problem_ids:
                    item.example_problem_ids.append(problem_id)
                return
        profile.topic_mistake_profiles.append(
            TopicMistakeProfile(
                topic=topic,
                total_mistakes=1,
                mistake_counts={mistake_type: 1},
                example_problem_ids=[problem_id],
                last_seen_at=utc_now(),
            )
        )
