"""Async comment CRUD operations for collaborative workflows."""

from __future__ import annotations

import asyncio

from bionodulo.collab.models import CollabStore, Comment


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
    """Insert a new comment using the shared SQLAlchemy store."""
    comment = Comment(
        workflow_id=workflow_id,
        node_id=node_id,
        user_id=user_id,
        user_name=user_name,
        user_color=user_color,
        content=content,
        parent_id=parent_id,
    )
    return store.add_comment(comment)


class CommentManager:
    """Async manager for comment CRUD with threaded replies."""

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
        """Create a new comment or reply."""
        if parent_id is not None:
            parent = await asyncio.to_thread(self.store.get_comment, parent_id)
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
        """Get all comments for a workflow with replies nested."""
        return await asyncio.to_thread(self.store.list_comments, workflow_id)

    async def list_for_node(self, workflow_id: str, node_id: str) -> list[Comment]:
        """Get comments for a specific node with replies nested."""
        return await asyncio.to_thread(self.store.list_comments, workflow_id, node_id)

    async def update(self, comment_id: str, content: str) -> Comment | None:
        """Edit a comment's content."""
        return await asyncio.to_thread(self.store.update_comment, comment_id, content)

    async def resolve(self, comment_id: str) -> bool:
        """Mark a comment as resolved."""
        return await asyncio.to_thread(self._resolve_bool, comment_id, True)

    async def unresolve(self, comment_id: str) -> bool:
        """Mark a comment as unresolved."""
        return await asyncio.to_thread(self._resolve_bool, comment_id, False)

    async def delete(self, comment_id: str) -> bool:
        """Delete a comment and all its replies."""
        return await asyncio.to_thread(self.store.delete_comment, comment_id)

    async def get(self, comment_id: str) -> Comment | None:
        """Get a single comment by ID."""
        return await asyncio.to_thread(self.store.get_comment, comment_id)

    def _resolve_bool(self, comment_id: str, resolved: bool) -> bool:
        comment = (
            self.store.resolve_comment(comment_id)
            if resolved
            else self.store.unresolve_comment(comment_id)
        )
        return comment is not None
