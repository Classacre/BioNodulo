"""
Local execution fallback backend.

Runs jobs locally using Python subprocess.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCBackend, HPCJob

logger = logging.getLogger(__name__)


class LocalBackend(HPCBackend):
    """Local execution backend that runs jobs via subprocess."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.max_parallel = self.config.get("max_parallel", 4)
        self.semaphore = asyncio.Semaphore(self.max_parallel)
        self._running: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def submit_job(
        self,
        script_path: str | Path,
        *args: str,
        **kwargs: Any,
    ) -> HPCJob:
        """Execute a job script locally as an async subprocess."""
        script_path = Path(script_path)
        if not script_path.is_file():
            raise FileNotFoundError(f"Job script not found: {script_path}")

        job_id = f"local_{id(script_path)}_{asyncio.get_running_loop().time()}"
        output_dir = kwargs.get("cwd", script_path.parent)
        job_name = script_path.stem
        stdout_path = Path(output_dir) / (job_name + ".out")
        stderr_path = Path(output_dir) / (job_name + ".err")

        env = dict(os.environ)
        if kwargs.get("env"):
            env.update(kwargs["env"])

        job = HPCJob(
            job_id=job_id,
            status="PENDING",
            stdout=str(stdout_path),
            stderr=str(stderr_path),
        )

        task = asyncio.create_task(self._run_local(job, script_path, env, kwargs.get("cwd")))
        self._tasks[job_id] = task
        task.add_done_callback(lambda done_task: self._handle_job_done(job_id, done_task))
        return job

    def _handle_job_done(self, job_id: str, task: asyncio.Task[None]) -> None:
        self._tasks.pop(job_id, None)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Local HPC job %s failed unexpectedly", job_id)

    async def check_status(self, job: HPCJob) -> HPCJob:
        """Return the current status of a local job."""
        if job.job_id in self._running:
            proc = self._running[job.job_id]
            if proc.returncode is None:
                job.status = "RUNNING"
            elif proc.returncode == 0:
                job.status = "COMPLETED"
                job.exit_code = 0
            else:
                job.status = "FAILED"
                job.exit_code = proc.returncode
        return job

    async def cancel_job(self, job: HPCJob) -> HPCJob:
        """Kill a running local job."""
        if job.job_id in self._running:
            proc = self._running[job.job_id]
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            del self._running[job.job_id]
        task = self._tasks.get(job.job_id)
        if task is not None and not task.done():
            task.cancel()
        job.status = "CANCELLED"
        return job

    async def shutdown(self) -> None:
        """Cancel active local jobs and wait for their runner tasks."""
        tasks = list(self._tasks.values())
        for proc in self._running.values():
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._running.clear()
        self._tasks.clear()

    async def _run_local(
        self,
        job: HPCJob,
        script_path: Path,
        env: dict[str, str],
        cwd: str | Path | None,
    ) -> None:
        """Run a local job under the concurrency semaphore."""
        async with self.semaphore:
            job.status = "RUNNING"
            proc = await asyncio.create_subprocess_exec(
                "bash",
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd or script_path.parent,
            )
            self._running[job.job_id] = proc
            try:
                try:
                    stdout_data, stderr_data = await proc.communicate()
                except asyncio.CancelledError:
                    if proc.returncode is None:
                        proc.kill()
                        await proc.wait()
                    raise

                try:
                    with open(job.stdout, "wb") as fh:
                        fh.write(stdout_data)
                except OSError:
                    pass
                try:
                    with open(job.stderr, "wb") as fh:
                        fh.write(stderr_data)
                except OSError:
                    pass

                if proc.returncode == 0:
                    job.status = "COMPLETED"
                elif job.status != "CANCELLED":
                    job.status = "FAILED"
                job.exit_code = proc.returncode
            finally:
                self._running.pop(job.job_id, None)

    def generate_local_script(
        self,
        commands: list[str],
        job_name: str = "bionodulo_job",
        output_dir: str | Path = ".",
        env_setup: list[str] | None = None,
        modules: list[str] | None = None,
    ) -> str:
        """Generate a local job script (bash, no scheduler directives)."""
        lines: list[str] = ["#!/bin/bash", "# Local job: " + job_name, ""]
        if env_setup:
            lines.extend(env_setup)
            lines.append("")
        if modules:
            for mod in modules:
                lines.append("module load " + mod)
            lines.append("")
        lines.append('cd "' + str(Path(output_dir).absolute()) + '"')
        lines.append("")
        for cmd in commands:
            lines.append(cmd)
        lines.append("")
        lines.append("# Job completed")
        lines.append("")
        return "\n".join(lines)
