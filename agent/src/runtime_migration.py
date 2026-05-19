from __future__ import annotations

# 文件用途：提供旧版运行时 JSON 数据迁移到 SQLite 的手动迁移逻辑。

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime_repository import SqliteRuntimeRepository


RUNTIME_SECTIONS = (
    "problems",
    "sessions",
    "profiles",
    "reviews",
    "leetcode_directories",
)


@dataclass
class MigrationSummary:
    """运行时迁移结果摘要。

    参数:
        imported: 各分区成功导入数量。
        skipped: 各分区因已存在而跳过数量。
        errors: 读取旧 JSON 时遇到的错误说明。
        sources: 实际扫描过的旧运行时目录。

    返回值:
        无。实例保存本次迁移统计。
    """

    # 各分区成功写入 SQLite 的数量。
    imported: dict[str, int] = field(default_factory=dict)
    # 各分区因 SQLite 已存在记录而跳过的数量。
    skipped: dict[str, int] = field(default_factory=dict)
    # 旧 JSON 读取或解析错误列表。
    errors: list[str] = field(default_factory=list)
    # 本次扫描过的旧运行时目录。
    sources: list[str] = field(default_factory=list)

    def mark_imported(self, section: str) -> None:
        """记录一次导入。

        参数:
            section: 运行时分区名称。

        返回值:
            无。
        """
        self.imported[section] = self.imported.get(section, 0) + 1

    def mark_skipped(self, section: str) -> None:
        """记录一次跳过。

        参数:
            section: 运行时分区名称。

        返回值:
            无。
        """
        self.skipped[section] = self.skipped.get(section, 0) + 1

    def total_imported(self) -> int:
        """统计导入总数。

        参数:
            无。

        返回值:
            int: 所有分区导入记录数量。
        """
        return sum(self.imported.values())


def migrate_project_runtime(project_dir: str | Path, overwrite: bool = False) -> MigrationSummary:
    """把项目旧 JSON 运行时数据迁移到 SQLite。

    参数:
        project_dir: `agent/` 项目目录。
        overwrite: SQLite 中已有同 ID 记录时是否覆盖。

    返回值:
        MigrationSummary: 本次迁移统计摘要。
    """
    project_dir = Path(project_dir)
    repository = SqliteRuntimeRepository(project_dir / "projects")
    summary = MigrationSummary()

    for source_dir in _legacy_source_dirs(project_dir):
        if not source_dir.exists():
            continue
        summary.sources.append(str(source_dir))
        for record in _iter_legacy_records(source_dir, summary):
            _migrate_record(repository, record, overwrite, summary)

    return summary


def _legacy_source_dirs(project_dir: Path) -> list[Path]:
    return [
        project_dir / "projects",
        project_dir / ".runtime",
    ]


def _iter_legacy_records(
    source_dir: Path,
    summary: MigrationSummary,
) -> list[tuple[str, str, Any]]:
    records: list[tuple[str, str, Any]] = []
    records.extend(_iter_runtime_file_records(source_dir, summary))
    records.extend(_iter_small_file_records(source_dir, summary))
    return records


def _iter_runtime_file_records(
    source_dir: Path,
    summary: MigrationSummary,
) -> list[tuple[str, str, Any]]:
    runtime_path = source_dir / "runtime.json"
    if not runtime_path.exists():
        return []

    raw = _load_json_file(runtime_path, summary)
    if not isinstance(raw, dict):
        return []

    records: list[tuple[str, str, Any]] = []
    for section in RUNTIME_SECTIONS:
        section_data = raw.get(section)
        if not isinstance(section_data, dict):
            continue
        for item_id, payload in section_data.items():
            records.append((section, str(item_id), payload))
    return records


def _iter_small_file_records(
    source_dir: Path,
    summary: MigrationSummary,
) -> list[tuple[str, str, Any]]:
    records: list[tuple[str, str, Any]] = []
    for section in RUNTIME_SECTIONS:
        section_dir = source_dir / section
        if not section_dir.exists() or not section_dir.is_dir():
            continue
        for path in sorted(section_dir.glob("*.json")):
            payload = _load_json_file(path, summary)
            if payload is None:
                continue
            records.append((section, path.stem, payload))
    return records


def _load_json_file(path: Path, summary: MigrationSummary) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        summary.errors.append(f"{path}: {type(exc).__name__}: {exc}")
        return None


def _migrate_record(
    repository: SqliteRuntimeRepository,
    record: tuple[str, str, Any],
    overwrite: bool,
    summary: MigrationSummary,
) -> None:
    section, item_id, payload = record
    relative_path = f"{section}/{item_id}.json"
    exists = repository.load_json(relative_path, None) is not None
    if exists and not overwrite:
        summary.mark_skipped(section)
        return
    repository.save_json(relative_path, payload)
    summary.mark_imported(section)
