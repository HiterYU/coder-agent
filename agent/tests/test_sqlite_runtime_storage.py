from __future__ import annotations

# 文件用途：回归验证 SQLite 运行时仓库、旧 JSON 迁移和主控层持久化链路。

import json
import sqlite3
from pathlib import Path

from src.runtime_migration import migrate_project_runtime
from src.runtime_repository import SqliteRuntimeRepository
from src.training_agent import TrainingAgent


def test_sqlite_runtime_repository_initializes_schema_and_core_sections(tmp_path: Path) -> None:
    """验证 SQLite 仓库会初始化 schema 并保存核心运行时分区。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    repository = SqliteRuntimeRepository(tmp_path / "projects")

    repository.save_json("problems/two-sum.json", _problem_payload("two-sum"))
    repository.save_json(
        "sessions/s_1.json",
        {
            "session_id": "s_1",
            "user_id": "demo",
            "problem_id": "two-sum",
            "language": "Python",
            "status": "reading",
            "updated_at": "2026-05-19T00:00:00+00:00",
        },
    )
    repository.save_json(
        "profiles/demo.json",
        {
            "user_id": "demo",
            "language": "Python",
            "goal": "interview",
            "solved_problem_ids": [],
        },
    )
    repository.save_json(
        "reviews/sub_1.json",
        {
            "submission_id": "sub_1",
            "session_id": "s_1",
            "is_likely_correct": True,
            "feedback": "通过样例。",
            "created_at": "2026-05-19T00:00:00+00:00",
        },
    )
    repository.save_json(
        "leetcode_directories/latest.json",
        {
            "category_slug": "all-code-essentials",
            "scanned": 2,
            "selected": 1,
            "items": [{"id": "two-sum"}],
        },
    )

    assert repository.database_path.name == "agent.db"
    assert repository.load_json("problems/two-sum.json", {})["title"] == "Two Sum"
    assert repository.load_section("sessions")["s_1"]["problem_id"] == "two-sum"
    assert repository.load_json("leetcode_directories/latest.json", {})["selected"] == 1

    with sqlite3.connect(repository.database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }
        assert {
            "runtime_metadata",
            "problems",
            "sessions",
            "profiles",
            "reviews",
            "leetcode_directories",
        }.issubset(table_names)
        problem_count = connection.execute("select count(*) from problems").fetchone()[0]
        assert problem_count == 1


def test_migrate_project_runtime_imports_legacy_json_without_overwriting(tmp_path: Path) -> None:
    """验证旧 JSON 可以手动迁移到 SQLite，默认不覆盖已有记录。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    project_dir = tmp_path / "agent"
    projects_dir = project_dir / "projects"
    legacy_dir = project_dir / ".runtime"
    projects_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)

    _write_json(
        projects_dir / "runtime.json",
        {
            "problems": {"two-sum": _problem_payload("two-sum")},
            "leetcode_directories": {
                "latest": {
                    "category_slug": "all-code-essentials",
                    "scanned": 10,
                    "selected": 1,
                    "items": [{"id": "two-sum"}],
                }
            },
        },
    )
    (legacy_dir / "profiles").mkdir()
    _write_json(
        legacy_dir / "profiles" / "demo.json",
        {
            "user_id": "demo",
            "language": "Python",
            "goal": "legacy",
            "solved_problem_ids": [],
        },
    )
    (projects_dir / "sessions").mkdir()
    _write_json(
        projects_dir / "sessions" / "s_1.json",
        {
            "session_id": "s_1",
            "user_id": "demo",
            "problem_id": "two-sum",
            "language": "Python",
            "status": "reading",
            "updated_at": "2026-05-19T00:00:00+00:00",
        },
    )

    summary = migrate_project_runtime(project_dir)
    repository = SqliteRuntimeRepository(projects_dir)

    assert summary.imported["problems"] == 1
    assert summary.imported["sessions"] == 1
    assert summary.imported["profiles"] == 1
    assert repository.load_json("problems/two-sum.json", {})["id"] == "two-sum"
    assert repository.load_json("profiles/demo.json", {})["goal"] == "legacy"

    repository.save_json(
        "profiles/demo.json",
        {
            "user_id": "demo",
            "language": "Python",
            "goal": "newer",
            "solved_problem_ids": [],
        },
    )
    second_summary = migrate_project_runtime(project_dir)
    assert second_summary.skipped["profiles"] == 1
    assert repository.load_json("profiles/demo.json", {})["goal"] == "newer"

    migrate_project_runtime(project_dir, overwrite=True)
    assert repository.load_json("profiles/demo.json", {})["goal"] == "legacy"


def test_training_agent_persists_sessions_profiles_and_directory_to_agent_db(
    tmp_path: Path,
) -> None:
    """验证 TrainingAgent 主链路写入 SQLite agent.db。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    project_dir = tmp_path / "agent"
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True)
    (project_dir / "projects").mkdir()
    _write_json(data_dir / "problems.json", [_problem_payload("two-sum")])
    _write_json(
        data_dir / "seed_user_profile.json",
        {
            "language": "Python",
            "goal": "interview",
            "solved_problem_ids": [],
        },
    )

    agent = TrainingAgent(project_dir)
    session = agent.create_session("demo", "two-sum")
    agent.add_user_message(session, "thought", "先用哈希表记录补数。")

    repository = SqliteRuntimeRepository(project_dir / "projects")
    saved_session = repository.load_json(f"sessions/{session.session_id}.json", {})
    saved_profile = repository.load_json("profiles/demo.json", {})

    assert (project_dir / "projects" / "agent.db").exists()
    assert saved_session["messages"][0]["content"] == "先用哈希表记录补数。"
    assert saved_profile["user_id"] == "demo"

    directory_payload = {
        "category_slug": "all-code-essentials",
        "include_paid": False,
        "difficulty": "",
        "scanned": 1,
        "selected": 1,
        "items": [{"id": "two-sum"}],
    }
    repository.save_json("leetcode_directories/latest.json", directory_payload)
    assert agent.get_cached_leetcode_directory()["items"][0]["id"] == "two-sum"


def _problem_payload(problem_id: str) -> dict:
    return {
        "id": problem_id,
        "leetcode_id": 1,
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "description": "Return indices of two numbers.",
        "examples": [],
        "constraints": [],
        "starter_code": "",
        "function_signature": "",
        "function_name": "",
        "expected_approaches": [],
        "common_mistakes": [],
        "similar_problem_ids": [],
        "interview_value": 0.5,
        "prerequisites": [],
    }


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
