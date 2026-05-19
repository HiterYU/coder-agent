from __future__ import annotations

# 文件用途：读取内置题库，并把运行时题目缓存持久化到 SQLite。

from pathlib import Path

from .models import Problem
from .runtime_repository import SqliteRuntimeRepository
from .storage import JsonStorage


class ProblemStore:
    """题目查询与运行时题目缓存。

    参数:
        data_dir: 内置题库目录。
        runtime_dir: 可选运行时目录，用于缓存实时拉取题目到 SQLite。
        legacy_runtime_dir: 保留兼容参数；旧 JSON 需通过迁移命令手动导入 SQLite。

    返回值:
        无。实例化后可查询或更新题目。
    """

    def __init__(
        self,
        data_dir: str | Path,
        runtime_dir: str | Path | None = None,
        legacy_runtime_dir: str | Path | None = None,
    ):
        """初始化题目仓库。

        参数:
            data_dir: 内置题库目录。
            runtime_dir: 可选运行时目录。
            legacy_runtime_dir: 保留兼容参数；不再自动读取旧 JSON。

        返回值:
            无。
        """
        self.storage = JsonStorage(data_dir)
        self.runtime_storage = (
            SqliteRuntimeRepository(runtime_dir)
            if runtime_dir
            else None
        )
        raw_problems = self.storage.load_json("problems.json", [])
        self.problems = [Problem.model_validate(item) for item in raw_problems]
        self.problem_by_id = {problem.id: problem for problem in self.problems}
        self._load_runtime_problems()

    def list_problems(self, filters: dict | None = None) -> list[Problem]:
        """列出题目。

        参数:
            filters: 可选过滤条件，支持 difficulty 和 tag。

        返回值:
            list[Problem]: 符合条件的题目列表。
        """
        problems = self.problems
        if not filters:
            return problems

        difficulty = filters.get("difficulty")
        tag = filters.get("tag")
        if difficulty:
            problems = [problem for problem in problems if problem.difficulty == difficulty]
        if tag:
            problems = [problem for problem in problems if tag in problem.tags]
        return problems

    def get_problem(self, problem_id: str) -> Problem:
        """读取指定题目。

        参数:
            problem_id: 题目 ID 或 LeetCode slug。

        返回值:
            Problem: 题目详情。
        """
        if problem_id not in self.problem_by_id:
            raise KeyError(f"Problem not found: {problem_id}")
        return self.problem_by_id[problem_id]

    def upsert_problem(self, problem: Problem) -> Problem:
        """新增或更新运行时题目缓存。

        参数:
            problem: 题目详情。

        返回值:
            Problem: 已写入缓存的题目详情。
        """
        self.problem_by_id[problem.id] = problem
        self.problems = [item for item in self.problems if item.id != problem.id]
        self.problems.append(problem)
        if self.runtime_storage:
            self.runtime_storage.save_json(
                f"problems/{problem.id}.json", problem.model_dump(mode="json")
            )
        return problem

    def tags(self) -> list[str]:
        """列出全部题目标签。

        参数:
            无。

        返回值:
            list[str]: 排序后的标签列表。
        """
        return sorted({tag for problem in self.problems for tag in problem.tags})

    def _load_runtime_problems(self) -> None:
        if not self.runtime_storage:
            return

        for raw in self.runtime_storage.load_section("problems").values():
            if raw:
                self._upsert_memory_problem(Problem.model_validate(raw))

    def _upsert_memory_problem(self, problem: Problem) -> None:
        self.problem_by_id[problem.id] = problem
        self.problems = [item for item in self.problems if item.id != problem.id]
        self.problems.append(problem)
