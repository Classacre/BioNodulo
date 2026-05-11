"""
SLURM backend for HPC job scheduling.

Uses ``sbatch``, ``squeue``, ``scancel``, and ``sacct`` to manage jobs.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCBackend, HPCJob


class SLURMBackend(HPCBackend):
    """SLURM HPC backend implementation."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.partition = self.config.get("partition", "")
        self.account = self.config.get("account", "")
        self.default_walltime = self.config.get("default_walltime", "01:00:00")
        self.default_cpus = self.config.get("default_cpus", 1)
        self.default_memory_mb = self.config.get("default_memory_mb", 4096)

    async def submit_job(
        self,
        script_path: str | Path,
        *args: str,
        **kwargs: Any,
    ) -> HPCJob:
        """Submit a batch script via ``sbatch``."""
        script_path = Path(script_path)
        if not script_path.is_file():
            raise FileNotFoundError(f"Job script not found: {script_path}")

        cmd_parts = ["sbatch"]
        if self.partition:
            cmd_parts.extend(["--partition", self.partition])
        if self.account:
            cmd_parts.extend(["--account", self.account])
        if kwargs.get("dependency"):
            cmd_parts.extend(["--dependency", kwargs["dependency"]])
        if kwargs.get("hold"):
            cmd_parts.append("--hold")
        if kwargs.get("array"):
            cmd_parts.extend(["--array", kwargs["array"]])
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
            raise RuntimeError(f"sbatch failed (exit {proc.returncode}): {stderr_text}")

        match = re.search(r"Submitted batch job (\d+)", stdout_text)
        if not match:
            raise RuntimeError(f"Could not parse job ID from sbatch output: {stdout_text}")

        job_id = match.group(1)
        output_dir = script_path.parent
        job_name = script_path.stem

        return HPCJob(
            job_id=job_id,
            status="PENDING",
            stdout=str(output_dir / (job_name + "_" + job_id + ".out")),
            stderr=str(output_dir / (job_name + "_" + job_id + ".err")),
        )

    async def check_status(self, job: HPCJob) -> HPCJob:
        """Check job status via ``squeue`` or ``sacct``."""
        status = await self._squeue_status(job.job_id)
        if status is None:
            status = await self._sacct_status(job.job_id)
        if status:
            job.status = status
            if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"):
                exit_code = await self._sacct_exit_code(job.job_id)
                if exit_code is not None:
                    job.exit_code = exit_code
        return job

    async def cancel_job(self, job: HPCJob) -> HPCJob:
        """Cancel a job via ``scancel``."""
        proc = await asyncio.create_subprocess_shell(
            f"scancel {job.job_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if "already completing" not in stderr_text.lower():
                raise RuntimeError(f"scancel failed: {stderr_text}")
        job.status = "CANCELLED"
        return job

    async def _squeue_status(self, job_id: str) -> str | None:
        """Get job status from squeue output."""
        proc = await asyncio.create_subprocess_shell(
            f'squeue --job {job_id} --format="%.18i %.2t" --noheader',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        if not stdout_text:
            return None
        parts = stdout_text.split()
        if len(parts) >= 2:
            return self._slurm_state_to_status(parts[1])
        return None

    async def _sacct_status(self, job_id: str) -> str | None:
        """Get job status from sacct output."""
        proc = await asyncio.create_subprocess_shell(
            f'sacct --job {job_id} --format=State --noheader --parsable2',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        if not stdout_text:
            return None
        first_line = stdout_text.splitlines()[0].strip()
        return self._slurm_state_to_status(first_line)

    async def _sacct_exit_code(self, job_id: str) -> int | None:
        """Get exit code from sacct."""
        proc = await asyncio.create_subprocess_shell(
            f'sacct --job {job_id} --format=ExitCode --noheader --parsable2',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        if not stdout_text:
            return None
        first_line = stdout_text.splitlines()[0].strip()
        if ":" in first_line:
            try:
                return int(first_line.split(":")[0])
            except ValueError:
                return None
        try:
            return int(first_line)
        except ValueError:
            return None

    @staticmethod
    def _slurm_state_to_status(state: str) -> str:
        state_map = {
            "PENDING": "PENDING", "PD": "PENDING",
            "RUNNING": "RUNNING", "R": "RUNNING",
            "SUSPENDED": "SUSPENDED", "S": "SUSPENDED",
            "COMPLETED": "COMPLETED", "CD": "COMPLETED",
            "FAILED": "FAILED", "F": "FAILED",
            "CANCELLED": "CANCELLED", "CA": "CANCELLED",
            "TIMEOUT": "TIMEOUT", "TO": "TIMEOUT",
            "NODE_FAIL": "FAILED", "NF": "FAILED",
            "PREEMPTED": "CANCELLED", "PR": "CANCELLED",
            "OUT_OF_MEMORY": "FAILED", "OOM": "FAILED",
        }
        return state_map.get(state.upper(), "UNKNOWN")

    def generate_slurm_script(
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
        """Generate a SLURM batch job script."""
        return self.generate_job_script(
            commands=commands,
            job_name=job_name,
            output_dir=output_dir,
            walltime=walltime or self.default_walltime,
            cpus=cpus or self.default_cpus,
            memory_mb=memory_mb or self.default_memory_mb,
            queue=queue or self.partition,
            email=email,
            env_setup=env_setup,
            modules=modules,
            scheduler="slurm",
        )
