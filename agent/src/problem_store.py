from __future__ import annotations

from pathlib import Path

from .models import Problem
from .storage import JsonStorage, RuntimeJsonStorage


class ProblemStore:
    """题目查询与运行时题目缓存。

    参数:
        data_dir: 内置题库目录。
        runtime_dir: 可选运行时目录，用于缓存实时拉取题目。

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
            legacy_runtime_dir: 可选旧版运行时目录。

        返回值:
            无。
        """
        self.storage = JsonStorage(data_dir)
        self.runtime_storage = (
            RuntimeJsonStorage(runtime_dir, legacy_base_dir=legacy_runtime_dir)
            if runtime_dir
            else None
        )
        raw_problems = self.storage.load_json("problems.json", [])
        self.problems = [Problem.model_validate(item) for item in raw_problems]
        self.problem_by_id = {problem.id: problem for problem in self.problems}
        self._load_runtime_problems()

    def list_problems(self, filters: dict | None = None) -> list[Problem]:
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
        if problem_id not in self.problem_by_id:
            raise KeyError(f"Problem not found: {problem_id}")
        return self.problem_by_id[problem_id]

    def upsert_problem(self, problem: Problem) -> Problem:
        self.problem_by_id[problem.id] = problem
        self.problems = [item for item in self.problems if item.id != problem.id]
        self.problems.append(problem)
        if self.runtime_storage:
            self.runtime_storage.save_json(
                f"problems/{problem.id}.json", problem.model_dump(mode="json")
            )
        return problem

    def tags(self) -> list[str]:
        return sorted({tag for problem in self.problems for tag in problem.tags})

    def _load_runtime_problems(self) -> None:
        if not self.runtime_storage:
            return

        for raw in self.runtime_storage.load_section("problems").values():
            if raw:
                self._upsert_memory_problem(Problem.model_validate(raw))

        problems_dir = self.runtime_storage.base_dir / "problems"
        if not problems_dir.exists():
            return
        for path in problems_dir.glob("*.json"):
            raw = self.runtime_storage.load_json(f"problems/{path.name}", None)
            if raw:
                self._upsert_memory_problem(Problem.model_validate(raw))

    def _upsert_memory_problem(self, problem: Problem) -> None:
        self.problem_by_id[problem.id] = problem
        self.problems = [item for item in self.problems if item.id != problem.id]
        self.problems.append(problem)
