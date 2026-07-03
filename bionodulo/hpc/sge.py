"""
Sun Grid Engine (SGE) backend for HPC job scheduling.

Uses ``qsub``, ``qstat``, and ``qdel`` to manage jobs.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCBackend, HPCJob


class SGEBackend(HPCBackend):
    """Sun Grid Engine HPC backend implementation."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.queue = self.config.get("queue", "")
        self.pe = self.config.get("parallel_environment", "smp")
        self.default_walltime = self.config.get("default_walltime", "01:00:00")
        self.default_cpus = self.config.get("default_cpus", 1)
        self.default_memory_mb = self.config.get("default_memory_mb", 4096)

    async def _run(self, *args: str) -> tuple[int, str, str]:
        """Run an SGE CLI command WITHOUT a shell (no injection surface)."""
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
        """Accept SGE job IDs (+ array/step suffixes); reject shell syntax."""
        if not re.fullmatch(r"[A-Za-z0-9_.:+-]+", str(job_id)):
            raise ValueError(f"Invalid SGE job id: {job_id!r}")
        return str(job_id)

    @staticmethod
    def _validate_arg(value: str) -> str:
        """Validate a caller-supplied qsub arg (dependency / extra_args element).

        These flow from the /hpc/submit API body, so constrain them to safe
        characters and reject leading dashes that could smuggle extra options.
        """
        text = str(value)
        if not text or text.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_.,:+=/@-]+", text):
            raise ValueError(f"Invalid qsub argument: {value!r}")
        return text

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
            cmd_parts.extend(["-hold_jid", self._validate_job_id(kwargs["dependency"])])
        if kwargs.get("hold"):
            cmd_parts.append("-h")
        if kwargs.get("extra_args"):
            cmd_parts.extend(self._validate_arg(a) for a in kwargs["extra_args"])
        cmd_parts.append(str(script_path))

        returncode, stdout_text, stderr_text = await self._run(*cmd_parts)

        if returncode != 0:
            raise RuntimeError(f"qsub failed (exit {returncode}): {stderr_text}")

        match = re.search(r"Your job (\d+)", stdout_text)
        if not match:
            match = re.search(r"(\d+)", stdout_text.strip())
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
        returncode, _stdout, stderr_text = await self._run(
            "qdel", self._validate_job_id(job.job_id)
        )
        if returncode != 0:
            if "does not exist" not in stderr_text.lower():
                raise RuntimeError(f"qdel failed: {stderr_text}")
        job.status = "CANCELLED"
        return job

    async def _qstat_status(self, job_id: str) -> str | None:
        job_id = self._validate_job_id(job_id)
        _rc, stdout_text, stderr_text = await self._run("qstat", "-j", job_id)
        if "do not exist" in stderr_text.lower() or "following" in stderr_text.lower():
            return await self._qstat_history_status(job_id)
        for line in stdout_text.splitlines():
            match = re.search(r"job_state\s*:\s*(\w+)", line)
            if match:
                return self._sge_state_to_status(match.group(1))
        # Fall back to the summary listing, filtered in-process (no shell pipe).
        _rc2, stdout2, _err2 = await self._run("qstat")
        for line in stdout2.splitlines():
            if line.strip().startswith(job_id):
                parts = line.split()
                if len(parts) >= 5:
                    return self._sge_state_to_status(parts[4])
        return None

    async def _qstat_history_status(self, job_id: str) -> str | None:
        job_id = self._validate_job_id(job_id)
        _rc, stdout_text, _err = await self._run("qacct", "-j", job_id)
        if "error" in stdout_text.lower() or not stdout_text.strip():
            return "COMPLETED"
        for line in stdout_text.splitlines():
            match = re.search(r"exit_status\s+(-?\d+)", line)
            if match:
                exit_code = int(match.group(1))
                return "COMPLETED" if exit_code == 0 else "FAILED"
        return "COMPLETED"

    @staticmethod
    def _sge_state_to_status(state: str) -> str:
        state_map = {
            "q": "PENDING", "qw": "PENDING", "h": "PENDING", "hqw": "PENDING",
            "s": "PENDING", "t": "PENDING", "r": "RUNNING", "R": "RUNNING",
            "Eqw": "FAILED", "dr": "CANCELLED", "dt": "CANCELLED",
            "d": "CANCELLED", "z": "COMPLETED",
        }
        return state_map.get(state, "UNKNOWN")

    def generate_sge_script(
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
        """Generate an SGE batch job script."""
        return self.generate_job_script(
            commands=commands, job_name=job_name, output_dir=output_dir,
            walltime=walltime or self.default_walltime, cpus=cpus or self.default_cpus,
            memory_mb=memory_mb or self.default_memory_mb, queue=queue or self.queue,
            email=email, env_setup=env_setup, modules=modules, scheduler="sge",
        )
