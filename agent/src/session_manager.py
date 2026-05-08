from __future__ import annotations

from pathlib import Path

from .models import Message, Session, SessionStatus, utc_now
from .storage import JsonStorage


class SessionManager:
    def __init__(self, runtime_dir: str | Path):
        self.storage = JsonStorage(runtime_dir)

    def create_session(self, user_id: str, problem_id: str, language: str = "Python") -> Session:
        session = Session(user_id=user_id, problem_id=problem_id, language=language)
        self.save_session(session)
        return session

    def get_session(self, session_id: str) -> Session:
        raw = self.storage.load_json(f"sessions/{session_id}.json", None)
        if raw is None:
            raise KeyError(f"Session not found: {session_id}")
        return Session.model_validate(raw)

    def save_session(self, session: Session) -> None:
        session.updated_at = utc_now()
        self.storage.save_json(f"sessions/{session.session_id}.json", session.model_dump(mode="json"))

    def add_message(self, session: Session, role: str, message_type: str, content: str) -> Session:
        session.messages.append(Message(role=role, type=message_type, content=content))
        if role == "user":
            session.current_stage = self._infer_stage(message_type, content)
            session.status = self._status_for_stage(session.current_stage)
            if message_type == "code":
                session.current_code = content
        self.save_session(session)
        return session

    def mark_hint_given(self, session: Session, hint_level: int, hint: str) -> Session:
        session.hints_given.append(hint_level)
        session.messages.append(Message(role="assistant", type="hint", content=hint))
        self.save_session(session)
        return session

    def mark_reviewed(self, session: Session, submission_id: str, review_text: str) -> Session:
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
