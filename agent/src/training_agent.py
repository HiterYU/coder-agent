from __future__ import annotations

# 文件用途：训练 Agent 主控层，协调题目、会话、提示、复盘和用户画像模块。

from pathlib import Path

from .hint_engine import HintEngine
from .leetcode_client import LeetCodeClient
from .llm_client import LlmClient
from .models import Problem, ReviewResult, Session, UserProfile
from .problem_store import ProblemStore
from .profile_engine import ProfileEngine
from .review_engine import ReviewEngine
from .session_manager import SessionManager
from .storage import RuntimeJsonStorage


class TrainingAgent:
    """LeetCode 训练 Agent 主控层。

    参数:
        project_dir: 项目根目录路径。

    返回值:
        无。实例化后可通过各业务方法驱动训练流程。
    """

    def __init__(self, project_dir: str | Path):
        """初始化训练 Agent 主控层。

        参数:
            project_dir: 项目根目录路径。

        返回值:
            无。
        """
        self.project_dir = Path(project_dir)
        self.data_dir = self.project_dir / "data"
        self.runtime_dir = self.project_dir / ".runtime"
        RuntimeJsonStorage(self.runtime_dir).compact_legacy_files()
        self.llm = LlmClient()
        self.leetcode_client = LeetCodeClient()
        self.problem_store = ProblemStore(self.data_dir, self.runtime_dir)
        self.session_manager = SessionManager(self.runtime_dir)
        self.profile_engine = ProfileEngine(
            self.runtime_dir, self.data_dir / "seed_user_profile.json"
        )
        self.hint_engine = HintEngine(self.llm)
        self.review_engine = ReviewEngine(self.llm)

    def list_problems(self, filters: dict | None = None):
        return self.problem_store.list_problems(filters)

    def get_problem(self, problem_id: str):
        return self.problem_store.get_problem(problem_id)

    def fetch_problem_from_leetcode(self, url_or_slug: str) -> Problem:
        problem = self.leetcode_client.fetch_problem(url_or_slug)
        return self.problem_store.upsert_problem(problem)

    def get_profile(self, user_id: str) -> UserProfile:
        profile = self.profile_engine.get_profile(user_id)
        self.profile_engine.save_profile(profile)
        return profile

    def create_session(self, user_id: str, problem_id: str, language: str = "Python") -> Session:
        self.get_profile(user_id)
        return self.session_manager.create_session(user_id, problem_id, language)

    def add_user_message(self, session: Session, message_type: str, content: str) -> Session:
        return self.session_manager.add_message(session, "user", message_type, content)

    def generate_hint(self, session: Session) -> tuple[Session, UserProfile, dict]:
        problem = self.problem_store.get_problem(session.problem_id)
        profile = self.profile_engine.get_profile(session.user_id)
        hint = self.hint_engine.generate_hint(session, problem, profile)
        hint["used_skills"] = self.llm.last_used_skills
        session = self.session_manager.mark_hint_given(session, hint["hint_level"], hint["hint"])
        profile = self.profile_engine.update_after_hint(profile, hint["hint_level"])
        return session, profile, hint

    def review_submission(self, session: Session, code: str) -> tuple[Session, UserProfile, ReviewResult]:
        problem = self.problem_store.get_problem(session.problem_id)
        profile = self.profile_engine.get_profile(session.user_id)
        session.current_code = code
        review = self.review_engine.review_submission(session, problem, profile, code)
        review.used_skills = self.llm.last_used_skills
        profile = self.profile_engine.update_after_review(profile, session, problem, review)
        session = self.session_manager.mark_reviewed(session, review.submission_id, review.feedback)
        self._save_review(review)
        return session, profile, review

    def _save_review(self, review: ReviewResult) -> None:
        self.profile_engine.storage.save_json(
            f"reviews/{review.submission_id}.json", review.model_dump(mode="json")
        )
