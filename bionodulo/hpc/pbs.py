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

# Cap scheduler CLI calls so a wedged qsub/qstat/qdel can't hang the request.
_HPC_CMD_TIMEOUT_S = 30


class PBSBackend(HPCBackend):
    """PBS/Torque HPC backend implementation."""

    scheduler = "pbs"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.queue = self.config.get("queue", "")
        self.account = self.config.get("account", "")
        self.default_walltime = self.config.get("default_walltime", "01:00:00")
        self.default_cpus = self.config.get("default_cpus", 1)
        self.default_memory_mb = self.config.get("default_memory_mb", 4096)

    async def _run(self, *args: str) -> tuple[int, str, str]:
        """Run a PBS CLI command WITHOUT a shell (no injection surface).

        Bounded by a timeout so a wedged scheduler binary can't hang the request
        path; on timeout the process is killed and a RuntimeError is raised.
        """
        proc = await asyncio.create_subprocess_exec(
            *[str(arg) for arg in args],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_HPC_CMD_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"PBS command timed out after {_HPC_CMD_TIMEOUT_S}s: {args[0]!r}"
            ) from None
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def _validate_job_id(job_id: str) -> str:
        """Accept PBS job IDs (numeric + host suffix); reject shell syntax and
        leading dashes (which qdel/qstat would treat as option flags)."""
        text = str(job_id)
        if text.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_.:+\[\]-]+", text):
            raise ValueError(f"Invalid PBS job id: {job_id!r}")
        return text

    @staticmethod
    def _validate_arg(value: str) -> str:
        """Validate a caller-supplied qsub arg (dependency / extra_args element).

        These flow from the /hpc/submit API body, so constrain them to safe
        characters and reject leading dashes that could smuggle extra options.
        """
        text = str(value)
        if not text or text.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_.,:+=/@\[\]-]+", text):
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
            cmd_parts.extend(["-W", "depend=" + self._validate_arg(kwargs["dependency"])])
        if kwargs.get("hold"):
            cmd_parts.append("-h")
        if kwargs.get("extra_args"):
            cmd_parts.extend(self._validate_arg(a) for a in kwargs["extra_args"])
        cmd_parts.append(str(script_path))

        returncode, stdout_text, stderr_text = await self._run(*cmd_parts)

        if returncode != 0:
            raise RuntimeError(f"qsub failed (exit {returncode}): {stderr_text}")

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
        returncode, _stdout, stderr_text = await self._run(
            "qdel", self._validate_job_id(job.job_id)
        )
        if returncode != 0:
            if "unknown job" not in stderr_text.lower():
                raise RuntimeError(f"qdel failed: {stderr_text}")
        job.status = "CANCELLED"
        return job

    async def _qstat_status(self, job_id: str) -> str | None:
        """Get job status from qstat output."""
        job_id = self._validate_job_id(job_id)
        _rc, stdout_text, _err = await self._run("qstat", "-f", job_id)
        if not stdout_text or "unknown job" in stdout_text.lower():
            return await self._qstat_history_status(job_id)
        for line in stdout_text.splitlines():
            match = re.search(r"job_state\s*=\s*(\w)", line)
            if match:
                return self._pbs_state_to_status(match.group(1))
        return None

    async def _qstat_history_status(self, job_id: str) -> str | None:
        """Try to get status of a completed job."""
        job_id = self._validate_job_id(job_id)
        _rc, stdout_text, _err = await self._run("qstat", "-Hx", job_id)
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
        nodes: int | None = None,
        account: str | None = None,
    ) -> str:
        """Generate a PBS batch job script."""
        return self.generate_job_script(
            commands=commands, job_name=job_name, output_dir=output_dir,
            walltime=walltime or self.default_walltime, cpus=cpus or self.default_cpus,
            memory_mb=memory_mb or self.default_memory_mb, queue=queue or self.queue,
            email=email, env_setup=env_setup, modules=modules, scheduler="pbs",
            nodes=nodes, account=account or self.account,
        )
