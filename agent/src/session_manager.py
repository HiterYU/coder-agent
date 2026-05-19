from __future__ import annotations

# 文件用途：管理训练会话的创建、读取、消息追加和状态更新。

from pathlib import Path

from .models import Message, Session, SessionStatus, utc_now
from .runtime_repository import SqliteRuntimeRepository


class SessionManager:
    """训练会话管理器。

    参数:
        runtime_dir: 运行时目录。
        legacy_runtime_dir: 保留兼容参数；旧 JSON 需通过迁移命令手动导入 SQLite。

    返回值:
        无。实例化后可创建、读取和更新会话。
    """

    def __init__(self, runtime_dir: str | Path, legacy_runtime_dir: str | Path | None = None):
        """初始化训练会话管理器。

        参数:
            runtime_dir: 运行时目录。
            legacy_runtime_dir: 保留兼容参数；不再自动读取旧 JSON。

        返回值:
            无。
        """
        self.storage = SqliteRuntimeRepository(runtime_dir)

    def create_session(self, user_id: str, problem_id: str, language: str = "Python") -> Session:
        """创建训练会话。

        参数:
            user_id: 用户 ID。
            problem_id: 题目 ID。
            language: 当前练习语言。

        返回值:
            Session: 新建并已保存的会话。
        """
        session = Session(user_id=user_id, problem_id=problem_id, language=language)
        self.save_session(session)
        return session

    def get_session(self, session_id: str) -> Session:
        """读取训练会话。

        参数:
            session_id: 会话 ID。

        返回值:
            Session: SQLite 中保存的会话。
        """
        raw = self.storage.load_json(f"sessions/{session_id}.json", None)
        if raw is None:
            raise KeyError(f"Session not found: {session_id}")
        return Session.model_validate(raw)

    def save_session(self, session: Session) -> None:
        """保存训练会话。

        参数:
            session: 训练会话对象。

        返回值:
            无。
        """
        session.updated_at = utc_now()
        self.storage.save_json(f"sessions/{session.session_id}.json", session.model_dump(mode="json"))

    def add_message(self, session: Session, role: str, message_type: str, content: str) -> Session:
        """追加会话消息并更新阶段。

        参数:
            session: 当前训练会话。
            role: 消息角色。
            message_type: 消息类型。
            content: 消息内容。

        返回值:
            Session: 更新后的训练会话。
        """
        session.messages.append(Message(role=role, type=message_type, content=content))
        if role == "user":
            session.current_stage = self._infer_stage(message_type, content)
            session.status = self._status_for_stage(session.current_stage)
            if message_type == "code":
                session.current_code = content
        self.save_session(session)
        return session

    def mark_hint_given(self, session: Session, hint_level: int, hint: str) -> Session:
        """记录一次提示。

        参数:
            session: 当前训练会话。
            hint_level: 提示等级。
            hint: 提示内容。

        返回值:
            Session: 更新后的训练会话。
        """
        session.hints_given.append(hint_level)
        session.messages.append(Message(role="assistant", type="hint", content=hint))
        self.save_session(session)
        return session

    def mark_reviewed(self, session: Session, submission_id: str, review_text: str) -> Session:
        """记录提交复盘结果。

        参数:
            session: 当前训练会话。
            submission_id: 提交 ID。
            review_text: 复盘反馈文本。

        返回值:
            Session: 更新后的训练会话。
        """
        session.status = SessionStatus.REVIEWED
        session.current_stage = "reviewed"
        session.submission_ids.append(submission_id)
        session.messages.append(Message(role="assistant", type="review", content=review_text))
        self.save_session(session)
        return session

    def _infer_stage(self, message_type: str, content: str) -> str:
        normalized = content.lower()
        if message_type == "code" or "def " in normalized or "class " in normalized:
            return "implementation"
        if "error" in normalized or "报错" in normalized or "失败" in normalized:
            return "debugging"
        if message_type == "thought":
            return "thinking"
        return "reading"

    def _status_for_stage(self, stage: str) -> SessionStatus:
        if stage == "implementation":
            return SessionStatus.CODING
        if stage == "debugging":
            return SessionStatus.DEBUGGING
        if stage == "thinking":
            return SessionStatus.THINKING
        return SessionStatus.READING
