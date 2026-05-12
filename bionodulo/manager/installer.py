"""Async installation engine for BioNodulo dependencies.

Executes install plans for missing nodes, executables, and Python packages
with progress tracking and cancellation support.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.manager.custom_nodes import install_git, _install_requirements

logger = logging.getLogger(__name__)


@dataclass
class InstallProgress:
    """Progress update for an install job."""

    job_id: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    total_steps: int = 0
    completed_steps: int = 0
    current_step: str = ""
    message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
            "message": self.message,
            "errors": self.errors,
            "percent": (
                int(self.completed_steps / self.total_steps * 100)
                if self.total_steps > 0
                else 0
            ),
        }


class InstallJob:
    """An asynchronous install job with progress tracking."""

    _jobs: dict[str, "InstallJob"] = {}
    _lock = threading.Lock()

    def __init__(self, job_id: str, plan: dict[str, Any], custom_nodes_dir: Path):
        self.job_id = job_id
        self.plan = plan
        self.custom_nodes_dir = custom_nodes_dir
        self.progress = InstallProgress(job_id=job_id)
        self._cancelled = False
        self._task: asyncio.Task[Any] | None = None

    @classmethod
    def create(cls, plan: dict[str, Any], custom_nodes_dir: Path) -> "InstallJob":
        import uuid

        job_id = f"install_{uuid.uuid4().hex[:8]}"
        job = cls(job_id, plan, custom_nodes_dir)
        with cls._lock:
            cls._jobs[job_id] = job
        return job

    @classmethod
    def get(cls, job_id: str) -> "InstallJob" | None:
        with cls._lock:
            return cls._jobs.get(job_id)

    @classmethod
    def cleanup(cls, job_id: str) -> None:
        with cls._lock:
            cls._jobs.pop(job_id, None)

    def cancel(self) -> None:
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()

    def is_cancelled(self) -> bool:
        return self._cancelled

    async def run(self) -> InstallProgress:
        """Execute the install plan asynchronously."""
        self._task = asyncio.current_task()
        self.progress.status = "running"

        missing_nodes = self.plan.get("missing_nodes", [])
        missing_executables = self.plan.get("missing_executables", [])
        missing_packages = self.plan.get("missing_packages", [])

        self.progress.total_steps = (
            len(missing_nodes) + len(missing_executables) + len(missing_packages)
        )

        try:
            # 1. Install missing custom nodes
            for node in missing_nodes:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    return self.progress

                git_url = node.get("git_url", "")
                if not git_url:
                    self.progress.errors.append(
                        f"Cannot install {node['node_type']}: no git URL"
                    )
                    self.progress.completed_steps += 1
                    continue

                self.progress.current_step = f"Installing {node['node_type']}"
                repo_name = Path(git_url).stem
                dest = self.custom_nodes_dir / repo_name

                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    None,
                    lambda: install_git(
                        url=git_url,
                        install_dir=dest,
                        branch=node.get("git_commit", "") or "main",
                        overwrite=True,
                    ),
                )
                if success:
                    self.progress.message = f"Installed {node['node_type']}"
                else:
                    self.progress.errors.append(
                        f"Failed to install {node['node_type']} from {git_url}"
                    )
                self.progress.completed_steps += 1

            # 2. Install missing executables via micromamba
            for exe in missing_executables:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    return self.progress

                pkg = exe.get("conda_package") or exe["name"]
                self.progress.current_step = f"Installing {pkg}"

                success = await self._install_conda_package(pkg)
                if success:
                    self.progress.message = f"Installed {pkg}"
                else:
                    self.progress.errors.append(f"Failed to install {pkg}")
                self.progress.completed_steps += 1

            # 3. Install missing Python packages
            for pkg in missing_packages:
                if self._cancelled:
                    self.progress.status = "cancelled"
                    return self.progress

                pkg_name = pkg["name"]
                self.progress.current_step = f"Installing Python package {pkg_name}"

                success = await self._install_pip_package(pkg_name)
                if success:
                    self.progress.message = f"Installed {pkg_name}"
                else:
                    self.progress.errors.append(f"Failed to install {pkg_name}")
                self.progress.completed_steps += 1

            self.progress.status = "completed" if not self.progress.errors else "failed"
            if self.progress.errors:
                self.progress.message = (
                    f"Completed with {len(self.progress.errors)} error(s)"
                )
            else:
                self.progress.message = "All dependencies installed"

        except asyncio.CancelledError:
            self.progress.status = "cancelled"
            raise
        except Exception as exc:
            logger.exception("Install job failed")
            self.progress.status = "failed"
            self.progress.errors.append(str(exc))

        return self.progress

    async def _install_conda_package(self, package: str) -> bool:
        """Install a package via micromamba/conda."""
        try:
            mamba = shutil.which("micromamba") or shutil.which("mamba") or shutil.which("conda")
            if not mamba:
                logger.error("No conda executable found")
                return False

            cmd = [mamba, "install", "-y", "-c", "bioconda", "-c", "conda-forge", package]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            logger.error("conda install failed: %s", stderr.decode())
            return False
        except Exception as exc:
            logger.error("Failed to install %s: %s", package, exc)
            return False

    async def _install_pip_package(self, package: str) -> bool:
        """Install a package via pip."""
        try:
            pip = sys.executable
            cmd = [pip, "-m", "pip", "install", package]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            logger.error("pip install failed: %s", stderr.decode())
            return False
        except Exception as exc:
            logger.error("Failed to install %s: %s", package, exc)
            return False
