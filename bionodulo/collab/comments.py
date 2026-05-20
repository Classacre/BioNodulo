"""Comment CRUD operations with threaded replies for collaborative workflows.

Uses SQLite (via :class:`CollabStore`) for persistence. All public methods
are ``async`` and wrap blocking SQLite calls with :func:`asyncio.to_thread`.

Threading model
---------------
Comments support two-level threading: top-level comments (``parent_id``
is ``None``) and replies (``parent_id`` points to the parent comment).
The database enforces ``ON DELETE CASCADE`` for replies via the foreign
key constraint.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from bionodulo.collab.models import CollabStore, Comment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synchronous helper functions (run in thread pool)
# ---------------------------------------------------------------------------


def _create_comment_sync(
    store: CollabStore,
    workflow_id: str,
    node_id: str | None,
    user_id: str,
    user_name: str,
    user_color: str,
    content: str,
    parent_id: str | None,
) -> Comment:
    """Insert a new comment into the database."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    comment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO comments
        (id, workflow_id, node_id, user_id, user_name, user_color,
         content, parent_id, resolved, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            comment_id,
            workflow_id,
            node_id,
            user_id,
            user_name,
            user_color,
            content,
            parent_id,
            now,
            now,
        ),
    )
    conn.commit()

    return Comment(
        id=comment_id,
        workflow_id=workflow_id,
        node_id=node_id,
        user_id=user_id,
        user_name=user_name,
        user_color=user_color,
        content=content,
        parent_id=parent_id,
        resolved=False,
        created_at=now,
        updated_at=now,
        replies=[],
    )


def _fetch_comments_for_workflow_sync(
    store: CollabStore,
    workflow_id: str,
) -> list[Comment]:
    """Fetch all comments for a workflow, ordered by creation time."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    rows = conn.execute(
        """
        SELECT id, workflow_id, node_id, user_id, user_name, user_color,
               content, parent_id, resolved, created_at, updated_at
        FROM comments
        WHERE workflow_id = ?
        ORDER BY created_at ASC
        """,
        (workflow_id,),
    ).fetchall()
    return [_row_to_comment(row) for row in rows]


def _fetch_comments_for_node_sync(
    store: CollabStore,
    workflow_id: str,
    node_id: str,
) -> list[Comment]:
    """Fetch all comments for a specific node, ordered by creation time."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    rows = conn.execute(
        """
        SELECT id, workflow_id, node_id, user_id, user_name, user_color,
               content, parent_id, resolved, created_at, updated_at
        FROM comments
        WHERE workflow_id = ? AND node_id = ?
        ORDER BY created_at ASC
        """,
        (workflow_id, node_id),
    ).fetchall()
    return [_row_to_comment(row) for row in rows]


def _update_comment_sync(
    store: CollabStore,
    comment_id: str,
    content: str,
) -> Comment | None:
    """Update comment content. Returns the updated comment or None."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        "UPDATE comments SET content = ?, updated_at = ? WHERE id = ?",
        (content, now, comment_id),
    )
    if cursor.rowcount == 0:
        conn.rollback()
        return None
    conn.commit()

    row = conn.execute(
        """
        SELECT id, workflow_id, node_id, user_id, user_name, user_color,
               content, parent_id, resolved, created_at, updated_at
        FROM comments WHERE id = ?
        """,
        (comment_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_comment(row)


def _resolve_comment_sync(
    store: CollabStore,
    comment_id: str,
    resolved: bool,
) -> bool:
    """Mark a comment as resolved or unresolved."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    now = datetime.now(timezone.utc).isoformat()
    resolved_int = 1 if resolved else 0

    cursor = conn.execute(
        "UPDATE comments SET resolved = ?, updated_at = ? WHERE id = ?",
        (resolved_int, now, comment_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def _delete_comment_sync(
    store: CollabStore,
    comment_id: str,
) -> bool:
    """Delete a comment and all its replies.

    Replies are deleted first (via explicit query) to avoid relying on
    SQLite ``PRAGMA foreign_keys`` being enabled. The parent comment
    is deleted after all replies are removed.
    """
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    # Delete replies first
    conn.execute("DELETE FROM comments WHERE parent_id = ?", (comment_id,))
    # Delete the parent comment
    cursor = conn.execute(
        "DELETE FROM comments WHERE id = ?",
        (comment_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def _get_comment_sync(
    store: CollabStore,
    comment_id: str,
) -> Comment | None:
    """Get a single comment by ID."""
    store._ensure_phase3_tables()
    conn: sqlite3.Connection = store._conn()
    row = conn.execute(
        """
        SELECT id, workflow_id, node_id, user_id, user_name, user_color,
               content, parent_id, resolved, created_at, updated_at
        FROM comments WHERE id = ?
        """,
        (comment_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_comment(row)


def _row_to_comment(row: sqlite3.Row) -> Comment:
    """Convert a SQLite row to a :class:`Comment` dataclass."""
    return Comment(
        id=row["id"],
        workflow_id=row["workflow_id"],
        node_id=row["node_id"],
        user_id=row["user_id"],
        user_name=row["user_name"] or "",
        user_color=row["user_color"] or "",
        content=row["content"],
        parent_id=row["parent_id"],
        resolved=bool(row["resolved"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        replies=[],
    )


def _nest_replies(comments: list[Comment]) -> list[Comment]:
    """Nest reply comments under their parents.

    Returns a list of top-level comments with their ``replies`` lists
    populated. Comments that reference a missing parent are treated as
    top-level.
    """
    by_id: dict[str, Comment] = {}
    top_level: list[Comment] = []

    for c in comments:
        by_id[c.id] = c

    for c in comments:
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id].replies.append(c)
        else:
            top_level.append(c)

    return top_level


# ---------------------------------------------------------------------------
# Async CommentManager
# ---------------------------------------------------------------------------


class CommentManager:
    """Async manager for comment CRUD with threaded replies.

    Args:
        store: A :class:`CollabStore` instance for database access.
    """

    def __init__(self, store: CollabStore) -> None:
        self.store = store

    async def create(
        self,
        workflow_id: str,
        node_id: str | None,
        user_id: str,
        user_name: str,
        user_color: str,
        content: str,
        parent_id: str | None = None,
    ) -> Comment:
        """Create a new comment or reply.

        Args:
            workflow_id: The workflow being commented on.
            node_id: The specific node (``None`` = workflow-level comment).
            user_id: ID of the commenting user.
            user_name: Display name of the user.
            user_color: Hex color for the user's avatar.
            content: Comment text content.
            parent_id: ID of the parent comment for replies (``None`` for top-level).

        Returns:
            The newly created :class:`Comment`.

        Raises:
            ValueError: If the parent comment does not exist.
        """
        if parent_id is not None:
            parent = await asyncio.to_thread(_get_comment_sync, self.store, parent_id)
            if parent is None:
                raise ValueError(f"Parent comment {parent_id} not found")

        return await asyncio.to_thread(
            _create_comment_sync,
            self.store,
            workflow_id,
            node_id,
            user_id,
            user_name,
            user_color,
            content,
            parent_id,
        )

    async def list_for_workflow(self, workflow_id: str) -> list[Comment]:
        """Get all comments for a workflow with replies nested.

        Returns a list of top-level :class:`Comment` objects. Reply
        comments are attached to their parent's ``replies`` list.
        """
        comments = await asyncio.to_thread(
            _fetch_comments_for_workflow_sync, self.store, workflow_id
        )
        return _nest_replies(comments)

    async def list_for_node(self, workflow_id: str, node_id: str) -> list[Comment]:
        """Get comments for a specific node with replies nested.

        Returns a list of top-level :class:`Comment` objects that are
        associated with the given node. Reply comments are attached to
        their parent's ``replies`` list.
        """
        comments = await asyncio.to_thread(
            _fetch_comments_for_node_sync, self.store, workflow_id, node_id
        )
        return _nest_replies(comments)

    async def update(self, comment_id: str, content: str) -> Comment | None:
        """Edit a comment's content.

        Args:
            comment_id: The comment to update.
            content: New comment text.

        Returns:
            The updated :class:`Comment`, or ``None`` if not found.
        """
        return await asyncio.to_thread(
            _update_comment_sync, self.store, comment_id, content
        )

    async def resolve(self, comment_id: str) -> bool:
        """Mark a comment as resolved.

        Returns:
            ``True`` if the comment was found and updated.
        """
        return await asyncio.to_thread(
            _resolve_comment_sync, self.store, comment_id, True
        )

    async def unresolve(self, comment_id: str) -> bool:
        """Mark a comment as unresolved.

        Returns:
            ``True`` if the comment was found and updated.
        """
        return await asyncio.to_thread(
            _resolve_comment_sync, self.store, comment_id, False
        )

    async def delete(self, comment_id: str) -> bool:
        """Delete a comment and all its replies.

        The ``ON DELETE CASCADE`` foreign key ensures replies are also
        removed. Returns ``True`` if the comment was found and deleted.
        """
        return await asyncio.to_thread(_delete_comment_sync, self.store, comment_id)

    async def get(self, comment_id: str) -> Comment | None:
        """Get a single comment by ID.

        Returns:
            The :class:`Comment` if found, ``None`` otherwise.
        """
        return await asyncio.to_thread(_get_comment_sync, self.store, comment_id)
