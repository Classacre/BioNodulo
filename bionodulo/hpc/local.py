"""
Local execution fallback backend.

Runs jobs locally using Python subprocess.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCBackend, HPCJob


class LocalBackend(HPCBackend):
    """Local execution backend that runs jobs via subprocess."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.max_parallel = self.config.get("max_parallel", 4)
        self.semaphore = asyncio.Semaphore(self.max_parallel)
        self._running: dict[str, asyncio.subprocess.Process] = {}

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

        job_id = f"local_{id(script_path)}_{asyncio.get_event_loop().time()}"
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

        asyncio.create_task(self._run_local(job, script_path, env, kwargs.get("cwd")))
        return job

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
        job.status = "CANCELLED"
        return job

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
            proc = await asyncio.create_subprocess_shell(
                f"bash {script_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd or script_path.parent,
            )
            self._running[job.job_id] = proc
            stdout_data, stderr_data = await proc.communicate()

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

            if job.job_id in self._running:
                del self._running[job.job_id]

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
