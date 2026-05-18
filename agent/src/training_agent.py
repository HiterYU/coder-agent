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
        self.runtime_dir = self.project_dir / "projects"
        self.legacy_runtime_dir = self.project_dir / ".runtime"
        RuntimeJsonStorage(
            self.runtime_dir, legacy_base_dir=self.legacy_runtime_dir
        ).compact_legacy_files()
        self.llm = LlmClient()
        self.leetcode_client = LeetCodeClient()
        self.problem_store = ProblemStore(
            self.data_dir, self.runtime_dir, legacy_runtime_dir=self.legacy_runtime_dir
        )
        self.session_manager = SessionManager(self.runtime_dir, self.legacy_runtime_dir)
        self.profile_engine = ProfileEngine(
            self.runtime_dir,
            self.data_dir / "seed_user_profile.json",
            legacy_runtime_dir=self.legacy_runtime_dir,
        )
        self.hint_engine = HintEngine(self.llm)
        self.review_engine = ReviewEngine(self.llm)

    def list_problems(self, filters: dict | None = None) -> list[Problem]:
        """列出本地和运行时缓存题目。

        参数:
            filters: 可选过滤条件，支持 difficulty 和 tag。

        返回值:
            list[Problem]: 符合条件的题目列表。
        """
        return self.problem_store.list_problems(filters)

    def get_problem(self, problem_id: str) -> Problem:
        """读取指定题目。

        参数:
            problem_id: 题目 ID。

        返回值:
            Problem: 题目详情。
        """
        return self.problem_store.get_problem(problem_id)

    def fetch_problem_from_leetcode(self, url_or_slug: str) -> Problem:
        """从 LeetCode 拉取题目并写入运行时缓存。

        参数:
            url_or_slug: LeetCode 题目 URL 或 slug。

        返回值:
            Problem: 拉取并转换后的题目详情。
        """
        problem = self.leetcode_client.fetch_problem(url_or_slug)
        return self.problem_store.upsert_problem(problem)

    def fetch_problem_directory_from_leetcode(
        self,
        limit: int | None = None,
        include_paid: bool = False,
        difficulty: str = "",
    ) -> dict:
        """从 LeetCode 中国站拉取题目目录摘要并写入运行时缓存。

        参数:
            limit: 最多抓取多少道题；为空时扫描配置中的目录可见题目。
            include_paid: 是否包含付费题。
            difficulty: 可选难度过滤，支持 Easy、Medium、Hard。

        返回值:
            dict: 包含目录摘要和扫描数量的缓存结果。
        """
        raw_items = []
        selected_items = []
        offset = 0
        page_size = self.leetcode_client.page_size
        filters = self._leetcode_directory_filters(difficulty)

        while True:
            data = self.leetcode_client.fetch_question_list_by_range(
                offset=offset,
                limit=page_size,
                filters=filters,
            )
            block = data.get("data", {}).get("problemsetQuestionList", {})
            batch = block.get("questions") or []
            raw_items.extend(batch)

            for item in batch:
                if not include_paid and item.get("paidOnly"):
                    continue
                item_difficulty = self._normalize_leetcode_directory_difficulty(
                    item.get("difficulty")
                )
                if difficulty and item_difficulty != difficulty:
                    continue
                selected_items.append(item)
                if limit is not None and len(selected_items) >= limit:
                    break

            if limit is not None and len(selected_items) >= limit:
                break
            if not block.get("hasMore") or not batch:
                break
            offset += page_size

        entries = [self._leetcode_directory_entry(item) for item in selected_items]
        storage = RuntimeJsonStorage(
            self.runtime_dir, legacy_base_dir=self.legacy_runtime_dir
        )
        storage.save_json(
            "leetcode_directories/latest.json",
            {
                "category_slug": self.leetcode_client.category_slug,
                "include_paid": include_paid,
                "difficulty": difficulty,
                "scanned": len(raw_items),
                "selected": len(entries),
                "items": entries,
            },
        )

        return {
            "scanned": len(raw_items),
            "selected": len(entries),
            "items": entries,
        }

    def _leetcode_directory_filters(self, difficulty: str) -> dict:
        """生成 LeetCode 中国站目录 GraphQL 过滤条件。

        参数:
            difficulty: 可选难度过滤，支持 Easy、Medium、Hard。

        返回值:
            dict: GraphQL QuestionListFilterInput。
        """
        if not difficulty:
            return {}
        return {"difficulty": difficulty.upper()}

    def _normalize_leetcode_directory_difficulty(self, difficulty: object) -> str:
        """标准化 LeetCode 目录题目难度。

        参数:
            difficulty: LeetCode 目录接口返回的难度值。

        返回值:
            str: Easy、Medium、Hard 或原始字符串。
        """
        value = str(difficulty or "").strip()
        difficulty_map = {
            "EASY": "Easy",
            "Easy": "Easy",
            "简单": "Easy",
            "MEDIUM": "Medium",
            "Medium": "Medium",
            "中等": "Medium",
            "HARD": "Hard",
            "Hard": "Hard",
            "困难": "Hard",
        }
        return difficulty_map.get(value, value)

    def get_cached_leetcode_directory(self) -> dict:
        """读取最近一次缓存的 LeetCode 题目目录摘要。

        参数:
            无。

        返回值:
            dict: 最近一次目录摘要缓存；不存在时返回空目录。
        """
        storage = RuntimeJsonStorage(
            self.runtime_dir, legacy_base_dir=self.legacy_runtime_dir
        )
        return storage.load_json(
            "leetcode_directories/latest.json",
            {
                "category_slug": self.leetcode_client.category_slug,
                "include_paid": False,
                "difficulty": "",
                "scanned": 0,
                "selected": 0,
                "items": [],
            },
        )

    def _leetcode_directory_entry(self, item: dict) -> dict:
        """把 LeetCode 中国站目录条目转换为本地缓存摘要。

        参数:
            item: LeetCode 中国站题目目录条目。

        返回值:
            dict: 本地目录缓存摘要。
        """
        tags = [
            {
                "name": tag.get("name", ""),
                "name_translated": tag.get("nameTranslated", ""),
                "slug": tag.get("slug", ""),
            }
            for tag in item.get("topicTags") or []
        ]
        return {
            "leetcode_id": item.get("frontendQuestionId"),
            "id": item.get("titleSlug"),
            "title": item.get("title"),
            "title_cn": item.get("titleCn"),
            "difficulty": self._normalize_leetcode_directory_difficulty(
                item.get("difficulty")
            ),
            "paid_only": item.get("paidOnly", False),
            "ac_rate": item.get("acRate"),
            "tags": tags,
        }

    def get_profile(self, user_id: str) -> UserProfile:
        """读取或创建用户画像。

        参数:
            user_id: 用户 ID。

        返回值:
            UserProfile: 用户长期画像。
        """
        profile = self.profile_engine.get_profile(user_id)
        self.profile_engine.save_profile(profile)
        return profile

    def create_session(self, user_id: str, problem_id: str, language: str = "Python") -> Session:
        """创建一道题的训练会话。

        参数:
            user_id: 用户 ID。
            problem_id: 题目 ID。
            language: 当前练习语言。

        返回值:
            Session: 新建训练会话。
        """
        self.get_profile(user_id)
        return self.session_manager.create_session(user_id, problem_id, language)

    def add_user_message(self, session: Session, message_type: str, content: str) -> Session:
        """向会话追加用户输入。

        参数:
            session: 当前训练会话。
            message_type: 输入类型，如 thought、question 或 code。
            content: 用户输入内容。

        返回值:
            Session: 更新后的训练会话。
        """
        return self.session_manager.add_message(session, "user", message_type, content)

    def generate_hint(self, session: Session) -> tuple[Session, UserProfile, dict]:
        """为当前会话生成下一次提示。

        参数:
            session: 当前训练会话。

        返回值:
            tuple[Session, UserProfile, dict]: 更新后的会话、画像和提示数据。
        """
        problem = self.problem_store.get_problem(session.problem_id)
        profile = self.profile_engine.get_profile(session.user_id)
        hint = self.hint_engine.generate_hint(session, problem, profile)
        hint["used_skills"] = self.llm.last_used_skills
        session = self.session_manager.mark_hint_given(session, hint["hint_level"], hint["hint"])
        profile = self.profile_engine.update_after_hint(profile, hint["hint_level"])
        return session, profile, hint

    def review_submission(self, session: Session, code: str) -> tuple[Session, UserProfile, ReviewResult]:
        """复盘用户提交代码。

        参数:
            session: 当前训练会话。
            code: 用户提交代码。

        返回值:
            tuple[Session, UserProfile, ReviewResult]: 更新后的会话、画像和复盘结果。
        """
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
        """保存复盘结果。

        参数:
            review: 本次提交的复盘结果。

        返回值:
            无。
        """
        self.profile_engine.storage.save_json(
            f"reviews/{review.submission_id}.json", review.model_dump(mode="json")
        )
