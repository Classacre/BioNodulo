"""SQLAlchemy-backed models for collaborative editing metadata."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    delete,
    or_,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import Index, UniqueConstraint

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses (public store contract)
# ---------------------------------------------------------------------------


@dataclass
class WorkflowShare:
    """Represents a workflow sharing invitation / permission grant."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    role: str = "viewer"  # owner | editor | viewer | commenter
    invited_by: str = ""
    invited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accepted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "role": self.role,
            "invited_by": self.invited_by,
            "invited_at": self.invited_at,
            "accepted_at": self.accepted_at,
        }


@dataclass
class CollabRoom:
    """Represents an active collaboration room session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active_users: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "active_users": self.active_users,
        }


@dataclass
class CollabAuditLogEntry:
    """Represents a single audit log entry for compliance tracking."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    action: str = ""
    target_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    performed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "payload": self.payload,
            "performed_at": self.performed_at,
        }


@dataclass
class Comment:
    """Represents a comment or reply on a workflow or node."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    node_id: str | None = None
    user_id: str = ""
    user_name: str = ""
    user_color: str = ""
    content: str = ""
    parent_id: str | None = None
    resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    replies: list[Comment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_color": self.user_color,
            "content": self.content,
            "parent_id": self.parent_id,
            "resolved": self.resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "replies": [reply.to_dict() for reply in self.replies],
        }


@dataclass
class WorkflowVersion:
    """Represents a saved snapshot of a workflow document state."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    user_name: str = ""
    snapshot: dict[str, Any] | bytes = field(default_factory=dict)
    name: str | None = None
    auto_save: bool = True
    node_count: int = 0
    edge_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "auto_save": self.auto_save,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "created_at": self.created_at,
        }


@dataclass
class WorkflowTemplate:
    """Represents a shareable workflow template."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    user_id: str = ""
    title: str = ""
    description: str = ""
    tags: str = ""
    snapshot: dict[str, Any] | bytes = field(default_factory=dict)
    is_public: bool = False
    fork_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "is_public": self.is_public,
            "fork_count": self.fork_count,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# SQLAlchemy ORM rows
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class WorkflowShareRow(Base):
    __tablename__ = "workflow_shares"
    __table_args__ = (
        CheckConstraint("role IN ('owner','editor','viewer','commenter')", name="ck_share_role"),
        UniqueConstraint("workflow_id", "user_id", name="uq_workflow_share_user"),
        Index("idx_shares_workflow", "workflow_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    invited_by: Mapped[str | None] = mapped_column(String)
    invited_at: Mapped[str] = mapped_column(String, nullable=False)
    accepted_at: Mapped[str | None] = mapped_column(String)


class CollabRoomRow(Base):
    __tablename__ = "collab_rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    last_activity_at: Mapped[str] = mapped_column(String, nullable=False)
    active_users: Mapped[int] = mapped_column(Integer, default=0)


class CollabAuditLogRow(Base):
    __tablename__ = "collab_audit_log"
    __table_args__ = (Index("idx_audit_workflow", "workflow_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String)
    payload: Mapped[str | None] = mapped_column(Text)
    performed_at: Mapped[str] = mapped_column(String, nullable=False)


class CommentRow(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("idx_comments_workflow", "workflow_id"),
        Index("idx_comments_node", "node_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    user_name: Mapped[str] = mapped_column(String, nullable=False)
    user_color: Mapped[str | None] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class WorkflowVersionRow(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        Index("idx_versions_workflow", "workflow_id"),
        Index("idx_versions_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    user_name: Mapped[str | None] = mapped_column(String)
    snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    auto_save: Mapped[bool] = mapped_column(Boolean, default=True)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class WorkflowTemplateRow(Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (Index("idx_templates_public", "is_public"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


# ---------------------------------------------------------------------------
# SQLAlchemy-backed store
# ---------------------------------------------------------------------------


class CollabStore:
    """Store collaboration metadata through SQLAlchemy.

    SQLite remains the default deployment backend, but raw SQL has been
    replaced with a proper ORM/session boundary so the schema can be managed by
    Alembic and evolved without duplicating query strings around the codebase.
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = str(db_path)
        self.engine = self._create_engine(self.db_path)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            future=True,
        )
        Base.metadata.create_all(self.engine)

    @staticmethod
    def _create_engine(db_path: str) -> Engine:
        if db_path == ":memory:":
            return create_engine(
                "sqlite+pysqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                future=True,
            )
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(
            f"sqlite+pysqlite:///{path.as_posix()}",
            connect_args={"check_same_thread": False},
            future=True,
        )

    def _session(self) -> Session:
        return self._session_factory()

    # ------------------------------------------------------------------
    # Workflow shares
    # ------------------------------------------------------------------

    def add_share(self, share: WorkflowShare) -> WorkflowShare:
        with self._session() as session:
            row = session.scalar(
                select(WorkflowShareRow).where(
                    WorkflowShareRow.workflow_id == share.workflow_id,
                    WorkflowShareRow.user_id == share.user_id,
                )
            )
            if row is None:
                row = WorkflowShareRow(id=share.id)
                session.add(row)
            else:
                row.id = share.id
            row.workflow_id = share.workflow_id
            row.user_id = share.user_id
            row.role = share.role
            row.invited_by = share.invited_by
            row.invited_at = share.invited_at
            row.accepted_at = share.accepted_at
            session.commit()
        return share

    def list_shares(self, workflow_id: str) -> list[WorkflowShare]:
        with self._session() as session:
            rows = session.scalars(
                select(WorkflowShareRow).where(WorkflowShareRow.workflow_id == workflow_id)
            ).all()
            return [self._row_to_share(row) for row in rows]

    def list_workflow_ids_for_user(self, user_id: str) -> list[str]:
        with self._session() as session:
            rows = session.scalars(
                select(WorkflowShareRow.workflow_id).where(WorkflowShareRow.user_id == user_id)
            ).all()
            return [str(workflow_id) for workflow_id in rows]

    def get_share(self, share_id: str) -> WorkflowShare | None:
        with self._session() as session:
            row = session.get(WorkflowShareRow, share_id)
            return self._row_to_share(row) if row else None

    def delete_share(self, share_id: str) -> bool:
        with self._session() as session:
            row = session.get(WorkflowShareRow, share_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def get_user_role(self, workflow_id: str, user_id: str) -> str | None:
        with self._session() as session:
            return session.scalar(
                select(WorkflowShareRow.role).where(
                    WorkflowShareRow.workflow_id == workflow_id,
                    WorkflowShareRow.user_id == user_id,
                )
            )

    # ------------------------------------------------------------------
    # Collab rooms
    # ------------------------------------------------------------------

    def upsert_room(self, room: CollabRoom) -> CollabRoom:
        with self._session() as session:
            row = session.scalar(
                select(CollabRoomRow).where(CollabRoomRow.workflow_id == room.workflow_id)
            )
            if row is None:
                row = CollabRoomRow(
                    id=room.id,
                    workflow_id=room.workflow_id,
                    created_at=room.created_at,
                )
                session.add(row)
            row.last_activity_at = room.last_activity_at
            row.active_users = room.active_users
            session.commit()
        return room

    def get_room(self, workflow_id: str) -> CollabRoom | None:
        with self._session() as session:
            row = session.scalar(
                select(CollabRoomRow).where(CollabRoomRow.workflow_id == workflow_id)
            )
            return self._row_to_room(row) if row else None

    def delete_room(self, workflow_id: str) -> bool:
        with self._session() as session:
            result = session.execute(
                delete(CollabRoomRow).where(CollabRoomRow.workflow_id == workflow_id)
            )
            session.commit()
            return (result.rowcount or 0) > 0

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def add_audit_entry(self, entry: CollabAuditLogEntry) -> CollabAuditLogEntry:
        with self._session() as session:
            session.add(
                CollabAuditLogRow(
                    id=entry.id,
                    workflow_id=entry.workflow_id,
                    user_id=entry.user_id,
                    action=entry.action,
                    target_type=entry.target_type,
                    target_id=entry.target_id,
                    payload=json.dumps(entry.payload),
                    performed_at=entry.performed_at,
                )
            )
            session.commit()
        return entry

    def list_audit_entries(self, workflow_id: str, limit: int = 100) -> list[CollabAuditLogEntry]:
        with self._session() as session:
            rows = session.scalars(
                select(CollabAuditLogRow)
                .where(CollabAuditLogRow.workflow_id == workflow_id)
                .order_by(CollabAuditLogRow.performed_at.desc())
                .limit(limit)
            ).all()
            return [self._row_to_audit(row) for row in rows]

    # ------------------------------------------------------------------
    # Phase 3 table management
    # ------------------------------------------------------------------

    def _ensure_phase3_tables(self) -> None:
        """Compatibility no-op; SQLAlchemy creates all metadata tables."""
        Base.metadata.create_all(self.engine)

    # ---- Comments ----

    def add_comment(self, comment: Comment) -> Comment:
        if not comment.created_at:
            comment.created_at = datetime.now(timezone.utc).isoformat()
        if not comment.updated_at:
            comment.updated_at = comment.created_at
        with self._session() as session:
            session.add(
                CommentRow(
                    id=comment.id,
                    workflow_id=comment.workflow_id,
                    node_id=comment.node_id,
                    user_id=comment.user_id,
                    user_name=comment.user_name,
                    user_color=comment.user_color,
                    content=comment.content,
                    parent_id=comment.parent_id,
                    resolved=comment.resolved,
                    created_at=comment.created_at,
                    updated_at=comment.updated_at,
                )
            )
            session.commit()
        return comment

    def get_comment(self, comment_id: str) -> Comment | None:
        with self._session() as session:
            row = session.get(CommentRow, comment_id)
            return self._row_to_comment(row) if row else None

    def list_comments(self, workflow_id: str, node_id: str | None = None) -> list[Comment]:
        with self._session() as session:
            stmt = (
                select(CommentRow)
                .where(CommentRow.workflow_id == workflow_id)
                .order_by(CommentRow.created_at.asc())
            )
            if node_id is not None:
                parent_ids = select(CommentRow.id).where(
                    CommentRow.workflow_id == workflow_id,
                    CommentRow.node_id == node_id,
                )
                stmt = stmt.where(
                    or_(
                        CommentRow.node_id == node_id,
                        CommentRow.parent_id.in_(parent_ids),
                    )
                )
            rows = session.scalars(stmt).all()
            return self._nest_comments([self._row_to_comment(row) for row in rows])

    def list_comments_for_workflow(self, workflow_id: str) -> list[Comment]:
        return self.list_comments(workflow_id)

    def list_comments_for_node(self, workflow_id: str, node_id: str) -> list[Comment]:
        return self.list_comments(workflow_id, node_id=node_id)

    def update_comment(self, comment_id: str, content: str) -> Comment | None:
        with self._session() as session:
            row = session.get(CommentRow, comment_id)
            if row is None:
                return None
            row.content = content
            row.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()
        return self.get_comment(comment_id)

    def resolve_comment(self, comment_id: str) -> Comment | None:
        return self._set_comment_resolved(comment_id, True)

    def unresolve_comment(self, comment_id: str) -> Comment | None:
        return self._set_comment_resolved(comment_id, False)

    def _set_comment_resolved(self, comment_id: str, resolved: bool) -> Comment | None:
        with self._session() as session:
            row = session.get(CommentRow, comment_id)
            if row is None:
                return None
            row.resolved = resolved
            row.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()
        return self.get_comment(comment_id)

    def delete_comment(self, comment_id: str) -> bool:
        with self._session() as session:
            child_result = session.execute(
                delete(CommentRow).where(CommentRow.parent_id == comment_id)
            )
            own_result = session.execute(delete(CommentRow).where(CommentRow.id == comment_id))
            session.commit()
            return ((child_result.rowcount or 0) + (own_result.rowcount or 0)) > 0

    # ---- Versions ----

    def add_version(self, version: WorkflowVersion) -> WorkflowVersion:
        snapshot = self._encode_snapshot(version.snapshot)
        if isinstance(version.snapshot, dict):
            version.node_count = version.node_count or len(version.snapshot.get("nodes", {}))
            version.edge_count = version.edge_count or len(version.snapshot.get("edges", {}))
        with self._session() as session:
            session.add(
                WorkflowVersionRow(
                    id=version.id,
                    workflow_id=version.workflow_id,
                    user_id=version.user_id,
                    user_name=version.user_name,
                    snapshot=snapshot,
                    name=version.name,
                    auto_save=version.auto_save,
                    node_count=version.node_count,
                    edge_count=version.edge_count,
                    created_at=version.created_at,
                )
            )
            session.commit()
        return version

    def get_version(self, version_id: str) -> WorkflowVersion | None:
        with self._session() as session:
            row = session.get(WorkflowVersionRow, version_id)
            return self._row_to_version(row) if row else None

    def list_versions(self, workflow_id: str, limit: int = 50) -> list[WorkflowVersion]:
        with self._session() as session:
            rows = session.scalars(
                select(WorkflowVersionRow)
                .where(WorkflowVersionRow.workflow_id == workflow_id)
                .order_by(WorkflowVersionRow.created_at.desc())
                .limit(limit)
            ).all()
            return [self._row_to_version(row) for row in rows]

    def delete_version(self, version_id: str) -> bool:
        with self._session() as session:
            result = session.execute(
                delete(WorkflowVersionRow).where(WorkflowVersionRow.id == version_id)
            )
            session.commit()
            return (result.rowcount or 0) > 0

    # ---- Templates ----

    def add_template(self, template: WorkflowTemplate) -> WorkflowTemplate:
        with self._session() as session:
            session.add(
                WorkflowTemplateRow(
                    id=template.id,
                    workflow_id=template.workflow_id,
                    user_id=template.user_id,
                    title=template.title,
                    description=template.description,
                    tags=template.tags,
                    snapshot=self._encode_snapshot(template.snapshot),
                    is_public=template.is_public,
                    fork_count=template.fork_count,
                    created_at=template.created_at,
                )
            )
            session.commit()
        return template

    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        with self._session() as session:
            row = session.get(WorkflowTemplateRow, template_id)
            return self._row_to_template(row) if row else None

    def list_public_templates(
        self,
        search: str | None = None,
        tags: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowTemplate]:
        with self._session() as session:
            stmt = select(WorkflowTemplateRow).where(WorkflowTemplateRow.is_public.is_(True))
            if search:
                like = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        WorkflowTemplateRow.title.like(like),
                        WorkflowTemplateRow.description.like(like),
                    )
                )
            if tags:
                stmt = stmt.where(WorkflowTemplateRow.tags.like(f"%{tags}%"))
            rows = session.scalars(
                stmt.order_by(WorkflowTemplateRow.created_at.desc()).limit(limit).offset(offset)
            ).all()
            return [self._row_to_template(row) for row in rows]

    def list_user_templates(self, user_id: str, limit: int = 50) -> list[WorkflowTemplate]:
        with self._session() as session:
            rows = session.scalars(
                select(WorkflowTemplateRow)
                .where(WorkflowTemplateRow.user_id == user_id)
                .order_by(WorkflowTemplateRow.created_at.desc())
                .limit(limit)
            ).all()
            return [self._row_to_template(row) for row in rows]

    def delete_template(self, template_id: str, user_id: str | None = None) -> bool:
        with self._session() as session:
            stmt = delete(WorkflowTemplateRow).where(WorkflowTemplateRow.id == template_id)
            if user_id is not None:
                stmt = stmt.where(WorkflowTemplateRow.user_id == user_id)
            result = session.execute(stmt)
            session.commit()
            return (result.rowcount or 0) > 0

    def increment_template_forks(self, template_id: str) -> None:
        with self._session() as session:
            row = session.get(WorkflowTemplateRow, template_id)
            if row is not None:
                row.fork_count = (row.fork_count or 0) + 1
                session.commit()

    @staticmethod
    def _row_to_share(row: WorkflowShareRow) -> WorkflowShare:
        return WorkflowShare(
            id=row.id,
            workflow_id=row.workflow_id,
            user_id=row.user_id,
            role=row.role,
            invited_by=row.invited_by or "",
            invited_at=row.invited_at,
            accepted_at=row.accepted_at,
        )

    @staticmethod
    def _row_to_room(row: CollabRoomRow) -> CollabRoom:
        return CollabRoom(
            id=row.id,
            workflow_id=row.workflow_id,
            created_at=row.created_at,
            last_activity_at=row.last_activity_at,
            active_users=row.active_users or 0,
        )

    @staticmethod
    def _row_to_audit(row: CollabAuditLogRow) -> CollabAuditLogEntry:
        try:
            payload = json.loads(row.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        return CollabAuditLogEntry(
            id=row.id,
            workflow_id=row.workflow_id,
            user_id=row.user_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            payload=payload,
            performed_at=row.performed_at,
        )

    @staticmethod
    def _row_to_comment(row: CommentRow) -> Comment:
        return Comment(
            id=row.id,
            workflow_id=row.workflow_id,
            node_id=row.node_id,
            user_id=row.user_id,
            user_name=row.user_name or "",
            user_color=row.user_color or "",
            content=row.content,
            parent_id=row.parent_id,
            resolved=bool(row.resolved),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _nest_comments(comments: list[Comment]) -> list[Comment]:
        by_id = {comment.id: comment for comment in comments}
        roots: list[Comment] = []
        for comment in comments:
            comment.replies = []
        for comment in comments:
            if comment.parent_id and comment.parent_id in by_id:
                by_id[comment.parent_id].replies.append(comment)
            else:
                roots.append(comment)
        return roots

    @staticmethod
    def _encode_snapshot(snapshot: dict[str, Any] | bytes) -> bytes:
        if isinstance(snapshot, bytes):
            return snapshot
        return json.dumps(snapshot).encode("utf-8")

    @staticmethod
    def _decode_snapshot(snapshot: Any) -> dict[str, Any] | bytes:
        if snapshot is None:
            return {}
        if isinstance(snapshot, memoryview):
            snapshot = snapshot.tobytes()
        if isinstance(snapshot, bytes):
            try:
                return json.loads(snapshot.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return snapshot
        if isinstance(snapshot, str):
            try:
                return json.loads(snapshot)
            except json.JSONDecodeError:
                return snapshot.encode("utf-8")
        if isinstance(snapshot, dict):
            return snapshot
        return {}

    def _row_to_version(self, row: WorkflowVersionRow) -> WorkflowVersion:
        return WorkflowVersion(
            id=row.id,
            workflow_id=row.workflow_id,
            user_id=row.user_id,
            user_name=row.user_name or "",
            snapshot=self._decode_snapshot(row.snapshot),
            name=row.name,
            auto_save=bool(row.auto_save),
            node_count=row.node_count or 0,
            edge_count=row.edge_count or 0,
            created_at=row.created_at,
        )

    def _row_to_template(self, row: WorkflowTemplateRow) -> WorkflowTemplate:
        return WorkflowTemplate(
            id=row.id,
            workflow_id=row.workflow_id or "",
            user_id=row.user_id,
            title=row.title,
            description=row.description or "",
            tags=row.tags or "",
            snapshot=self._decode_snapshot(row.snapshot),
            is_public=bool(row.is_public),
            fork_count=row.fork_count or 0,
            created_at=row.created_at,
        )

    def close(self) -> None:
        self.engine.dispose()
