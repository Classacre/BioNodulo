"""Shared FastAPI app-state dependency helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request

from bionodulo.collab.audit import AuditLogger
from bionodulo.collab.models import CollabStore
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.presence import PresenceManager
from bionodulo.collab.rate_limiter import RateLimiter
from bionodulo.collab.room_manager import RoomManager
from bionodulo.collab.templates import TemplateManager
from bionodulo.core.workspace import resolve_workspace_root
from bionodulo.manager.installer import DependencyInstaller


@dataclass(frozen=True)
class AppState:
    """Typed view over the mutable FastAPI ``app.state`` namespace."""

    state: Any

    @property
    def workspace_root(self) -> Path:
        return resolve_workspace_root()

    @property
    def settings(self) -> Any:
        return self.state.settings

    @property
    def settings_manager(self) -> Any:
        return self.state.settings_manager

    @property
    def collab_store(self) -> CollabStore:
        store = getattr(self.state, "collab_store", None)
        if store is None:
            db_path = self.workspace_root / "collab.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            store = CollabStore(str(db_path))
            self.state.collab_store = store
        return store

    @property
    def permission_checker(self) -> PermissionChecker:
        checker = getattr(self.state, "permission_checker", None)
        if checker is None:
            checker = PermissionChecker(
                store=self.collab_store,
                fallback_file=self.workspace_root / "permissions.json",
            )
            self.state.permission_checker = checker
        return checker

    @property
    def audit_logger(self) -> AuditLogger:
        audit = getattr(self.state, "audit_logger", None)
        if audit is None:
            db_path = self.workspace_root / "audit.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            audit = AuditLogger(str(db_path))
            self.state.audit_logger = audit
        return audit

    @property
    def template_manager(self) -> TemplateManager:
        manager = getattr(self.state, "template_manager", None)
        if manager is None:
            db_path = self.workspace_root / "collab.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            manager = TemplateManager(str(db_path))
            self.state.template_manager = manager
        return manager

    @property
    def room_manager(self) -> RoomManager:
        manager = getattr(self.state, "room_manager", None)
        if manager is None:
            manager = RoomManager()
            self.state.room_manager = manager
        return manager

    @property
    def rate_limiter(self) -> RateLimiter:
        limiter = getattr(self.state, "rate_limiter", None)
        if limiter is None:
            limiter = RateLimiter()
            self.state.rate_limiter = limiter
        return limiter

    @property
    def presence_manager(self) -> PresenceManager:
        manager = getattr(self.state, "presence_manager", None)
        if manager is None:
            manager = PresenceManager()
            self.state.presence_manager = manager
        return manager

    @property
    def dependency_installer(self) -> DependencyInstaller:
        installer = getattr(self.state, "dependency_installer", None)
        if installer is None:
            installer = DependencyInstaller()
            self.state.dependency_installer = installer
        return installer


def app_state(request: Request) -> AppState:
    """Return a typed app-state accessor for dependency injection."""
    return AppState(request.app.state)


def app_state_from_app(app: Any) -> AppState:
    """Return a typed app-state accessor from a FastAPI app object."""
    return AppState(app.state)


def setting_literal(request: Request, key: str, default: Any = None) -> Any:
    """Read frontend-style literal dotted settings keys."""
    try:
        settings = app_state(request).settings_manager.get_all()
    except Exception:
        settings = {}
    return settings.get(key, default)
