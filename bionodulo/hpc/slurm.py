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

    async def _run_slurm_command(self, *args: str) -> tuple[int, str, str]:
        """Run a SLURM CLI command without invoking a shell."""
        proc = await asyncio.create_subprocess_exec(
            *[str(arg) for arg in args],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def _validate_job_id(job_id: str) -> str:
        """Accept SLURM job IDs and array/step suffixes, reject shell syntax."""
        if not re.fullmatch(r"[A-Za-z0-9_.:+-]+", str(job_id)):
            raise ValueError(f"Invalid SLURM job id: {job_id!r}")
        return str(job_id)

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

        returncode, stdout_text, stderr_text = await self._run_slurm_command(*cmd_parts)
        if returncode != 0:
            raise RuntimeError(f"sbatch failed (exit {returncode}): {stderr_text}")

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
        returncode, _stdout_text, stderr_text = await self._run_slurm_command(
            "scancel",
            self._validate_job_id(job.job_id),
        )
        if returncode != 0:
            if "already completing" not in stderr_text.lower():
                raise RuntimeError(f"scancel failed: {stderr_text}")
        job.status = "CANCELLED"
        return job

    async def _squeue_status(self, job_id: str) -> str | None:
        """Get job status from squeue output."""
        returncode, stdout_text, _stderr_text = await self._run_slurm_command(
            "squeue",
            "--job",
            self._validate_job_id(job_id),
            "--format=%.18i %.2t",
            "--noheader",
        )
        if returncode != 0:
            return None
        stdout_text = stdout_text.strip()
        if not stdout_text:
            return None
        parts = stdout_text.split()
        if len(parts) >= 2:
            return self._slurm_state_to_status(parts[1])
        return None

    async def _sacct_status(self, job_id: str) -> str | None:
        """Get job status from sacct output."""
        returncode, stdout_text, _stderr_text = await self._run_slurm_command(
            "sacct",
            "--job",
            self._validate_job_id(job_id),
            "--format=State",
            "--noheader",
            "--parsable2",
        )
        if returncode != 0:
            return None
        stdout_text = stdout_text.strip()
        if not stdout_text:
            return None
        first_line = stdout_text.splitlines()[0].strip()
        return self._slurm_state_to_status(first_line)

    async def _sacct_exit_code(self, job_id: str) -> int | None:
        """Get exit code from sacct."""
        returncode, stdout_text, _stderr_text = await self._run_slurm_command(
            "sacct",
            "--job",
            self._validate_job_id(job_id),
            "--format=ExitCode",
            "--noheader",
            "--parsable2",
        )
        if returncode != 0:
            return None
        stdout_text = stdout_text.strip()
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
