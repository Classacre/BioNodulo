"""
PBS/Torque backend for HPC job scheduling.

Uses ``qsub``, ``qstat``, and ``qdel`` to manage jobs.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCBackend, HPCJob


class PBSBackend(HPCBackend):
    """PBS/Torque HPC backend implementation."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.queue = self.config.get("queue", "")
        self.default_walltime = self.config.get("default_walltime", "01:00:00")
        self.default_cpus = self.config.get("default_cpus", 1)
        self.default_memory_mb = self.config.get("default_memory_mb", 4096)

    async def submit_job(
        self,
        script_path: str | Path,
        *args: str,
        **kwargs: Any,
    ) -> HPCJob:
        """Submit a batch script via ``qsub``."""
        script_path = Path(script_path)
        if not script_path.is_file():
            raise FileNotFoundError(f"Job script not found: {script_path}")

        cmd_parts = ["qsub"]
        if kwargs.get("dependency"):
            cmd_parts.extend(["-W", 'depend=' + kwargs["dependency"]])
        if kwargs.get("hold"):
            cmd_parts.append("-h")
        if kwargs.get("extra_args"):
            cmd_parts.extend(kwargs["extra_args"])
        cmd_parts.append(str(script_path))
        cmd = " ".join(cmd_parts)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            raise RuntimeError(f"qsub failed (exit {proc.returncode}): {stderr_text}")

        match = re.search(r"(\d+(?:\.\S+)?)", stdout_text)
        if not match:
            raise RuntimeError(f"Could not parse job ID from qsub output: {stdout_text}")

        job_id = match.group(1)
        output_dir = script_path.parent
        job_name = script_path.stem

        return HPCJob(
            job_id=job_id,
            status="PENDING",
            stdout=str(output_dir / (job_name + ".out")),
            stderr=str(output_dir / (job_name + ".err")),
        )

    async def check_status(self, job: HPCJob) -> HPCJob:
        """Check job status via ``qstat``."""
        status = await self._qstat_status(job.job_id)
        if status:
            job.status = status
        return job

    async def cancel_job(self, job: HPCJob) -> HPCJob:
        """Cancel a job via ``qdel``."""
        proc = await asyncio.create_subprocess_shell(
            f"qdel {job.job_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if "unknown job" not in stderr_text.lower():
                raise RuntimeError(f"qdel failed: {stderr_text}")
        job.status = "CANCELLED"
        return job

    async def _qstat_status(self, job_id: str) -> str | None:
        """Get job status from qstat output."""
        proc = await asyncio.create_subprocess_shell(
            f'qstat -f {job_id}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        if not stdout_text or "unknown job" in stdout_text.lower():
            return await self._qstat_history_status(job_id)
        for line in stdout_text.splitlines():
            match = re.search(r"job_state\s*=\s*(\w)", line)
            if match:
                return self._pbs_state_to_status(match.group(1))
        return None

    async def _qstat_history_status(self, job_id: str) -> str | None:
        """Try to get status of a completed job."""
        proc = await asyncio.create_subprocess_shell(
            f'qstat -Hx {job_id}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        for line in stdout_text.splitlines():
            match = re.search(r"job_state\s*=\s*(\w)", line)
            if match:
                return self._pbs_state_to_status(match.group(1))
        return "COMPLETED"

    @staticmethod
    def _pbs_state_to_status(state: str) -> str:
        state_map = {
            "Q": "PENDING", "H": "PENDING", "T": "PENDING",
            "W": "PENDING", "R": "RUNNING", "E": "RUNNING",
            "C": "COMPLETED", "F": "FAILED", "S": "SUSPENDED", "U": "UNKNOWN",
        }
        return state_map.get(state.upper(), "UNKNOWN")

    def generate_pbs_script(
        self,
        commands: list[str],
        job_name: str = "bionodulo_job",
        output_dir: str | Path = ".",
        walltime: str | None = None,
        cpus: int | None = None,
        memory_mb: int | None = None,
        queue: str | None = None,
        email: str | None = None,
        env_setup: list[str] | None = None,
        modules: list[str] | None = None,
    ) -> str:
        """Generate a PBS batch job script."""
        return self.generate_job_script(
            commands=commands, job_name=job_name, output_dir=output_dir,
            walltime=walltime or self.default_walltime, cpus=cpus or self.default_cpus,
            memory_mb=memory_mb or self.default_memory_mb, queue=queue or self.queue,
            email=email, env_setup=env_setup, modules=modules, scheduler="pbs",
        )
