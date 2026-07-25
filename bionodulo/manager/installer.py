"""Async installation engine for BioNodulo dependencies.

With the manifest-based per-workflow environment architecture, the
installer's primary job is to run `pixi lock` and `pixi install` for
workflow environments and track progress.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bionodulo.environments.manifest import (
    get_env_dir,
    get_environment_plan_id,
    workflow_to_environment_plan,
)

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, dict[str, Any]], Any]


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
        }


class InstallJob:
    """Represents a single install job with progress tracking."""

    def __init__(
        self,
        job_id: str,
        report: dict[str, Any],
        env_strategy: str = "workflow",
    ) -> None:
        self.job_id = job_id
        self.report = report
        self.env_strategy = env_strategy
        self.progress = InstallProgress(job_id=job_id)
        self._cancel_event = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None

    def cancel(self) -> None:
        """Signal cancellation."""
        self._cancel_event.set()
        self.progress.status = "cancelled"

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()


class DependencyInstaller:
    """Manages async installation jobs for workflow dependencies.

    With manifest-based environments, each workflow gets its own
    content-addressed pixi environment. The installer generates the
    manifest and runs `pixi lock` + `pixi install` in the background.
    """

    def __init__(self) -> None:
        self.jobs: dict[str, InstallJob] = {}
        self._lock = asyncio.Lock()

    def _send_log(
        self,
        level: str,
        message: str,
        job_id: str | None = None,
    ) -> None:
        """Emit a log message if a callback is registered."""
        logger.info("[%s] %s", level, message)

    async def install_workflow_env(
        self,
        workflow: dict[str, Any],
        registry: Any,
        workspace_dir: str | Path,
        emit: EmitCallback | None = None,
    ) -> str:
        """Start an async install job for a workflow environment.

        Returns the job_id for polling.
        """
        job_id = str(uuid.uuid4())[:8]
        job = InstallJob(job_id, {}, env_strategy="workflow")
        job.progress.status = "running"
        self.jobs[job_id] = job

        async def _run() -> None:
            try:
                environment_plan = workflow_to_environment_plan(workflow, registry)
                packages = list(environment_plan.all_packages)
                env_id = get_environment_plan_id(environment_plan)
                env_dir = get_env_dir(env_id, workspace_dir)
                wf_name = workflow.get("name", "") if isinstance(workflow, dict) else ""

                # Write default display name if not already set
                if wf_name:
                    from bionodulo.environments.manifest import get_env_name, set_env_meta
                    if not get_env_name(env_dir):
                        set_env_meta(env_dir, name=wf_name)

                job.progress.message = f"Resolved {len(packages)} packages for env {env_id[:8]}"
                if emit:
                    emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})

                from bionodulo.environments.manifest import (
                    generate_manifest,
                    generate_environment_manifest,
                    is_env_ready,
                    is_environment_manifest_current,
                    is_environment_ready_for_lock,
                    is_manifest_current,
                    mark_env_lock_installed,
                    materialize_committed_environment,
                    run_pixi_install,
                    run_pixi_lock,
                )

                # A committed bundle is authoritative for package sets that have
                # one.  Materialization also verifies the manifest bytes, so this
                # path must never regenerate a lock from the network.
                committed_lock_digest = materialize_committed_environment(
                    env_dir,
                    environment_plan,
                )
                if committed_lock_digest is None:
                    # Step 1: manifest
                    manifest_current = (
                        is_environment_manifest_current(env_dir, environment_plan)
                        if environment_plan.named_environments
                        else is_manifest_current(env_dir, packages)
                    )
                    if not manifest_current:
                        job.progress.message = "Generating pixi.toml manifest..."
                        if emit:
                            emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})
                        if environment_plan.named_environments:
                            generate_environment_manifest(env_dir, environment_plan)
                        else:
                            generate_manifest(env_dir, packages)
                        # CRITICAL FIX: Delete stale lockfile so pixi lock will regenerate it
                        lockfile = env_dir / "pixi.lock"
                        if lockfile.exists():
                            lockfile.unlink()

                    # Step 2: lock
                    if not is_env_ready(env_dir, environment_plan.environment_names):
                        job.progress.message = "Locking dependencies with pixi (this may take a moment)..."
                        if emit:
                            emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})
                        ok, msg = await run_pixi_lock(env_dir, emit=emit, job_id=job_id)
                        if not ok:
                            job.progress.status = "failed"
                            job.progress.message = msg
                            job.progress.errors.append(msg)
                            if emit:
                                emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})
                            return

                    environment_ready = is_env_ready(
                        env_dir,
                        environment_plan.environment_names,
                    )
                    locked_install = False
                else:
                    # The committed lock already supplies the manifest and lock;
                    # only install when the environment lacks a matching digest.
                    environment_ready = is_environment_ready_for_lock(
                        env_dir,
                        committed_lock_digest,
                        environment_plan,
                    )
                    locked_install = True

                # Step 3: install
                if not environment_ready:
                    job.progress.message = "Installing packages into environment..."
                    if emit:
                        emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})
                    ok, msg = await run_pixi_install(
                        env_dir,
                        emit=emit,
                        job_id=job_id,
                        locked=locked_install,
                        all_environments=bool(environment_plan.named_environments),
                    )
                    if not ok:
                        job.progress.status = "failed"
                        job.progress.message = msg
                        job.progress.errors.append(msg)
                        if emit:
                            emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})
                        return
                    if committed_lock_digest is not None:
                        mark_env_lock_installed(env_dir, committed_lock_digest)

                job.progress.status = "completed"
                job.progress.message = f"Environment {env_id[:8]} ready with {len(packages)} packages"
            except Exception as exc:
                logger.exception("Install job %s failed", job_id)
                job.progress.status = "failed"
                job.progress.message = str(exc)
                job.progress.errors.append(str(exc))
            finally:
                if emit:
                    emit("install.progress", {"job_id": job_id, **job.progress.to_dict()})

        job._task = asyncio.create_task(_run())
        job._task.add_done_callback(lambda task: self._handle_job_done(job_id, task))
        return job_id

    def _handle_job_done(self, job_id: str, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            job = self.jobs.get(job_id)
            if job is not None:
                job.progress.status = "cancelled"
                job.progress.message = "Installation cancelled"
        except Exception:
            logger.exception("Install job %s task failed unexpectedly", job_id)

    def get_job(self, job_id: str) -> InstallJob | None:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[InstallProgress]:
        """List all jobs."""
        return [j.progress for j in self.jobs.values()]

    async def shutdown(self) -> None:
        """Cancel and await any running installation jobs."""
        tasks: list[asyncio.Task[Any]] = []
        for job in self.jobs.values():
            task = job._task
            if task is not None and not task.done():
                job.cancel()
                task.cancel()
                tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
