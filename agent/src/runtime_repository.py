from __future__ import annotations

# 文件用途：定义 SQLite 运行时数据库表、schema 初始化和统一读写仓库。

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Engine, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session as SqlSession
from sqlalchemy.orm import mapped_column, sessionmaker


SCHEMA_VERSION = "1"
DEFAULT_DATABASE_NAME = "agent.db"


class RuntimeBase(DeclarativeBase):
    """运行时数据库 declarative base。

    参数:
        无。

    返回值:
        无。SQLAlchemy 用该基类收集表定义。
    """


class RuntimeMetadataRecord(RuntimeBase):
    """运行时数据库元信息表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "runtime_metadata"

    # 元信息键，例如 schema_version。
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    # 元信息值，统一按字符串保存。
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # 记录更新时间，使用 UTC ISO 字符串。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class ProblemRecord(RuntimeBase):
    """题目运行时缓存表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "problems"

    # 题目 slug 或本地题目 ID，作为主键。
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    # LeetCode 题号，便于后续检索和调试。
    leetcode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 题目标题，便于直接查看数据库内容。
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    # 题目难度，取 Easy / Medium / Hard。
    difficulty: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # 完整 Problem JSON payload，保持和 Pydantic 模型兼容。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录更新时间，使用 UTC ISO 字符串。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class SessionRecord(RuntimeBase):
    """训练会话表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "sessions"

    # 会话 ID，来自 Session.session_id。
    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    # 用户 ID，用于按用户聚合会话。
    user_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # 题目 ID，用于追踪会话对应的题目。
    problem_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    # 会话状态，保存枚举值字符串。
    status: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    # 完整 Session JSON payload。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录更新时间，优先使用 payload.updated_at。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class ProfileRecord(RuntimeBase):
    """用户画像表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "profiles"

    # 用户 ID，来自 UserProfile.user_id。
    user_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    # 常用语言，便于直接查看画像摘要。
    language: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # 用户目标，例如 interview。
    goal: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    # 完整 UserProfile JSON payload。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录更新时间，使用 UTC ISO 字符串。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class ReviewRecord(RuntimeBase):
    """提交复盘结果表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "reviews"

    # 提交 ID，来自 ReviewResult.submission_id。
    submission_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    # 会话 ID，用于回溯本次复盘所属会话。
    session_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    # 是否大概率正确，SQLite 中按 0/1 存储。
    is_likely_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 完整 ReviewResult JSON payload。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录创建时间，优先使用 payload.created_at。
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class LeetCodeDirectoryRecord(RuntimeBase):
    """LeetCode 目录缓存表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "leetcode_directories"

    # 缓存键，当前使用 latest，保留扩展空间。
    cache_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    # LeetCode 目录分类 slug。
    category_slug: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # 本次扫描题目数量。
    scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 本次选中并缓存的目录条目数量。
    selected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 完整目录缓存 JSON payload。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录更新时间，使用 UTC ISO 字符串。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class RuntimeBlobRecord(RuntimeBase):
    """兜底运行时 JSON 片段表。

    参数:
        无。

    返回值:
        无。SQLAlchemy 根据字段定义创建表。
    """

    __tablename__ = "runtime_blobs"

    # 运行时相对路径，例如 custom/foo.json。
    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    # 完整 JSON payload。
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    # 记录更新时间，使用 UTC ISO 字符串。
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


def utc_now() -> str:
    """生成当前 UTC ISO 时间字符串。

    参数:
        无。

    返回值:
        str: 秒级 UTC ISO 时间。
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def runtime_database_path(base_dir: str | Path) -> Path:
    """计算运行时 SQLite 数据库路径。

    参数:
        base_dir: 运行时目录，通常是 `projects/`。

    返回值:
        Path: `agent.db` 的完整路径。
    """
    return Path(base_dir) / DEFAULT_DATABASE_NAME


def create_runtime_engine(database_path: str | Path) -> Engine:
    """创建 SQLite 运行时数据库引擎。

    参数:
        database_path: SQLite 数据库文件路径。

    返回值:
        Engine: SQLAlchemy 引擎实例。
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{path.resolve().as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )


def init_runtime_schema(engine: Engine) -> None:
    """初始化运行时数据库 schema。

    参数:
        engine: SQLAlchemy 引擎实例。

    返回值:
        无。
    """
    RuntimeBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with session_factory() as session:
        record = session.get(RuntimeMetadataRecord, "schema_version")
        changed = False
        if record is None:
            record = RuntimeMetadataRecord(
                key="schema_version",
                value=SCHEMA_VERSION,
                updated_at=utc_now(),
            )
            session.add(record)
            changed = True
        elif record.value != SCHEMA_VERSION:
            record.value = SCHEMA_VERSION
            record.updated_at = utc_now()
            changed = True
        if changed:
            session.commit()


class SqliteRuntimeRepository:
    """SQLite 运行时仓库。

    参数:
        base_dir: 运行时目录，数据库会保存为该目录下的 `agent.db`。

    返回值:
        无。实例化后可按旧相对路径接口读写运行时 JSON。
    """

    def __init__(self, base_dir: str | Path):
        """初始化 SQLite 运行时仓库。

        参数:
            base_dir: 运行时目录，通常是项目下的 `projects/`。

        返回值:
            无。
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = runtime_database_path(self.base_dir)
        self.engine = create_runtime_engine(self.database_path)
        init_runtime_schema(self.engine)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            future=True,
        )

    def load_json(self, relative_path: str, default: Any) -> Any:
        """读取运行时 JSON 数据。

        参数:
            relative_path: 兼容旧结构的相对路径，如 `sessions/s_xxx.json`。
            default: 数据不存在时返回的默认值。

        返回值:
            Any: SQLite 中的 JSON payload 或默认值。
        """
        section, item_id = self._split_relative_path(relative_path)
        with self._session_factory() as session:
            payload = self._load_known_payload(session, section, item_id)
            if payload is not _MissingPayload:
                return payload

            blob = session.get(RuntimeBlobRecord, relative_path)
            if blob is not None:
                return blob.payload

        return default

    def save_json(self, relative_path: str, data: Any) -> None:
        """保存运行时 JSON 数据。

        参数:
            relative_path: 兼容旧结构的相对路径，如 `profiles/demo.json`。
            data: 可 JSON 序列化的数据。

        返回值:
            无。
        """
        section, item_id = self._split_relative_path(relative_path)
        with self._session_factory() as session:
            saved = self._save_known_payload(session, section, item_id, data)
            if not saved:
                self._upsert_blob(session, relative_path, data)
            session.commit()

    def load_section(self, section: str) -> dict[str, Any]:
        """读取一个运行时分区。

        参数:
            section: 分区名，如 problems、sessions、profiles、reviews。

        返回值:
            dict[str, Any]: 按 id 组织的 JSON payload。
        """
        with self._session_factory() as session:
            if section == "problems":
                return {
                    record.id: record.payload
                    for record in session.scalars(select(ProblemRecord).order_by(ProblemRecord.id))
                }
            if section == "sessions":
                return {
                    record.session_id: record.payload
                    for record in session.scalars(
                        select(SessionRecord).order_by(SessionRecord.session_id)
                    )
                }
            if section == "profiles":
                return {
                    record.user_id: record.payload
                    for record in session.scalars(
                        select(ProfileRecord).order_by(ProfileRecord.user_id)
                    )
                }
            if section == "reviews":
                return {
                    record.submission_id: record.payload
                    for record in session.scalars(
                        select(ReviewRecord).order_by(ReviewRecord.submission_id)
                    )
                }
            if section == "leetcode_directories":
                return {
                    record.cache_key: record.payload
                    for record in session.scalars(
                        select(LeetCodeDirectoryRecord).order_by(
                            LeetCodeDirectoryRecord.cache_key
                        )
                    )
                }

            prefix = f"{section}/"
            suffix = ".json"
            return {
                Path(record.path).stem: record.payload
                for record in session.scalars(
                    select(RuntimeBlobRecord).order_by(RuntimeBlobRecord.path)
                )
                if record.path.startswith(prefix) and record.path.endswith(suffix)
            }

    def _split_relative_path(self, relative_path: str) -> tuple[str, str]:
        path = Path(relative_path)
        parts = path.parts
        if len(parts) == 2 and path.suffix == ".json":
            return parts[0], path.stem
        return "", ""

    def _load_known_payload(self, session: SqlSession, section: str, item_id: str) -> Any:
        if not section or not item_id:
            return _MissingPayload

        if section == "problems":
            record = session.get(ProblemRecord, item_id)
            return record.payload if record else _MissingPayload
        if section == "sessions":
            record = session.get(SessionRecord, item_id)
            return record.payload if record else _MissingPayload
        if section == "profiles":
            record = session.get(ProfileRecord, item_id)
            return record.payload if record else _MissingPayload
        if section == "reviews":
            record = session.get(ReviewRecord, item_id)
            return record.payload if record else _MissingPayload
        if section == "leetcode_directories":
            record = session.get(LeetCodeDirectoryRecord, item_id)
            return record.payload if record else _MissingPayload

        return _MissingPayload

    def _save_known_payload(
        self,
        session: SqlSession,
        section: str,
        item_id: str,
        data: Any,
    ) -> bool:
        if not section or not item_id:
            return False

        handlers: dict[str, Callable[[SqlSession, str, Any], None]] = {
            "problems": self._upsert_problem,
            "sessions": self._upsert_session,
            "profiles": self._upsert_profile,
            "reviews": self._upsert_review,
            "leetcode_directories": self._upsert_leetcode_directory,
        }
        handler = handlers.get(section)
        if not handler:
            return False
        handler(session, item_id, data)
        return True

    def _upsert_problem(self, session: SqlSession, item_id: str, data: Any) -> None:
        payload = _payload_dict(data)
        record = session.get(ProblemRecord, item_id)
        if record is None:
            record = ProblemRecord(id=item_id, payload=data, updated_at=utc_now())
            session.add(record)
        record.leetcode_id = _safe_int(payload.get("leetcode_id"))
        record.title = str(payload.get("title") or "")
        record.difficulty = str(payload.get("difficulty") or "")
        record.payload = data
        record.updated_at = utc_now()

    def _upsert_session(self, session: SqlSession, item_id: str, data: Any) -> None:
        payload = _payload_dict(data)
        record = session.get(SessionRecord, item_id)
        if record is None:
            record = SessionRecord(session_id=item_id, payload=data, updated_at=utc_now())
            session.add(record)
        record.user_id = str(payload.get("user_id") or "")
        record.problem_id = str(payload.get("problem_id") or "")
        record.status = str(payload.get("status") or "")
        record.payload = data
        record.updated_at = str(payload.get("updated_at") or utc_now())

    def _upsert_profile(self, session: SqlSession, item_id: str, data: Any) -> None:
        payload = _payload_dict(data)
        record = session.get(ProfileRecord, item_id)
        if record is None:
            record = ProfileRecord(user_id=item_id, payload=data, updated_at=utc_now())
            session.add(record)
        record.language = str(payload.get("language") or "")
        record.goal = str(payload.get("goal") or "")
        record.payload = data
        record.updated_at = utc_now()

    def _upsert_review(self, session: SqlSession, item_id: str, data: Any) -> None:
        payload = _payload_dict(data)
        record = session.get(ReviewRecord, item_id)
        if record is None:
            record = ReviewRecord(submission_id=item_id, payload=data, created_at=utc_now())
            session.add(record)
        record.session_id = str(payload.get("session_id") or "")
        record.is_likely_correct = 1 if payload.get("is_likely_correct") else 0
        record.payload = data
        record.created_at = str(payload.get("created_at") or utc_now())

    def _upsert_leetcode_directory(self, session: SqlSession, item_id: str, data: Any) -> None:
        payload = _payload_dict(data)
        record = session.get(LeetCodeDirectoryRecord, item_id)
        if record is None:
            record = LeetCodeDirectoryRecord(cache_key=item_id, payload=data, updated_at=utc_now())
            session.add(record)
        record.category_slug = str(payload.get("category_slug") or "")
        record.scanned = _safe_int(payload.get("scanned")) or 0
        record.selected = _safe_int(payload.get("selected")) or 0
        record.payload = data
        record.updated_at = utc_now()

    def _upsert_blob(self, session: SqlSession, path: str, data: Any) -> None:
        record = session.get(RuntimeBlobRecord, path)
        if record is None:
            record = RuntimeBlobRecord(path=path, payload=data, updated_at=utc_now())
            session.add(record)
        record.payload = data
        record.updated_at = utc_now()


class _MissingPayload:
    """内部缺失标记。

    参数:
        无。

    返回值:
        无。该类只用于区分 None payload 和未命中。
    """


def _payload_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    return {}


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
