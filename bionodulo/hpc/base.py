"""
Abstract base for HPC backends.

Defines the interface that all HPC backends (SLURM, PBS, SGE, Local) must
implement, plus a shared job script generator.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HPCJob:
    """Represents a submitted HPC job.

    Attributes:
        job_id: The scheduler-assigned job identifier.
        status: Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, UNKNOWN).
        stdout: Path to the captured stdout file.
        stderr: Path to the captured stderr file.
        exit_code: Exit code of the job (None if still running).
        metadata: Additional scheduler-specific metadata.
    """

    job_id: str
    status: str = "PENDING"
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HPCBackend(abc.ABC):
    """Abstract base class for HPC job scheduling backends."""

    scheduler = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abc.abstractmethod
    async def submit_job(
        self,
        script_path: str | Path,
        *args: str,
        **kwargs: Any,
    ) -> HPCJob:
        """Submit a batch job script to the scheduler."""
        ...

    @abc.abstractmethod
    async def check_status(self, job: HPCJob) -> HPCJob:
        """Check and update the status of a submitted job."""
        ...

    @abc.abstractmethod
    async def cancel_job(self, job: HPCJob) -> HPCJob:
        """Cancel a running or pending job."""
        ...

    def generate_job_script(
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
        scheduler: str = "generic",
        nodes: int | None = None,
        account: str | None = None,
    ) -> str:
        """Generate a batch job script.

        Args:
            commands: List of shell commands to execute.
            job_name: Name of the job.
            output_dir: Directory for stdout/stderr files.
            walltime: Maximum wall time.
            cpus: Number of CPU cores.
            memory_mb: Memory in megabytes.
            queue: Queue/partition name.
            email: Email for job notifications.
            env_setup: Lines to add at the start of the script.
            modules: Modules to load.
            scheduler: Target scheduler type (slurm, pbs, sge, generic).
            nodes: Number of scheduler nodes to request.
            account: Scheduler account or project to charge.

        Returns:
            The job script content as a string.
        """
        output_dir = Path(output_dir)
        lines: list[str] = []

        if scheduler == "slurm":
            lines.extend(
                self._slurm_directives(
                    job_name,
                    output_dir,
                    walltime,
                    cpus,
                    memory_mb,
                    queue,
                    email,
                    nodes,
                    account,
                )
            )
        elif scheduler in ("pbs", "torque"):
            lines.extend(
                self._pbs_directives(
                    job_name,
                    output_dir,
                    walltime,
                    cpus,
                    memory_mb,
                    queue,
                    email,
                    nodes,
                    account,
                )
            )
        elif scheduler == "sge":
            lines.extend(
                self._sge_directives(
                    job_name,
                    output_dir,
                    walltime,
                    cpus,
                    memory_mb,
                    queue,
                    email,
                    nodes,
                    account,
                )
            )
        else:
            lines.append("#!/bin/bash")
            lines.append("# Job: " + job_name)

        lines.append("")
        if env_setup:
            lines.extend(env_setup)
            lines.append("")
        if modules:
            for mod in modules:
                lines.append("module load " + mod)
            lines.append("")
        lines.append('cd "' + str(output_dir.absolute()) + '"')
        lines.append("")
        for cmd in commands:
            lines.append(cmd)
        lines.append("")
        lines.append("# Job completed")
        return "\n".join(lines) + "\n"

    def _slurm_directives(
        self, job_name: str, output_dir: Path, walltime: str | None,
        cpus: int | None, memory_mb: int | None, queue: str | None, email: str | None,
        nodes: int | None, account: str | None,
    ) -> list[str]:
        lines = ["#!/bin/bash"]
        lines.append("#SBATCH --job-name=" + job_name)
        lines.append("#SBATCH --output=" + str(output_dir) + "/" + job_name + "_%j.out")
        lines.append("#SBATCH --error=" + str(output_dir) + "/" + job_name + "_%j.err")
        if queue:
            lines.append("#SBATCH --partition=" + queue)
        if walltime:
            lines.append("#SBATCH --time=" + walltime)
        if nodes:
            lines.append("#SBATCH --nodes=" + str(nodes))
        if cpus:
            lines.append("#SBATCH --cpus-per-task=" + str(cpus))
        if memory_mb:
            lines.append("#SBATCH --mem=" + str(memory_mb) + "M")
        if account:
            lines.append("#SBATCH --account=" + account)
        if email:
            lines.append("#SBATCH --mail-user=" + email)
            lines.append("#SBATCH --mail-type=END,FAIL")
        return lines

    def _pbs_directives(
        self, job_name: str, output_dir: Path, walltime: str | None,
        cpus: int | None, memory_mb: int | None, queue: str | None, email: str | None,
        nodes: int | None, account: str | None,
    ) -> list[str]:
        lines = ["#!/bin/bash"]
        lines.append("#PBS -N " + job_name)
        lines.append("#PBS -o " + str(output_dir) + "/" + job_name + ".out")
        lines.append("#PBS -e " + str(output_dir) + "/" + job_name + ".err")
        if queue:
            lines.append("#PBS -q " + queue)
        if walltime:
            lines.append("#PBS -l walltime=" + walltime)
        resource_parts = []
        if nodes:
            resource_parts.append("select=" + str(nodes))
        if cpus:
            resource_parts.append("ncpus=" + str(cpus))
        if memory_mb:
            resource_parts.append("mem=" + str(memory_mb) + "mb")
        if resource_parts:
            lines.append("#PBS -l " + ":".join(resource_parts))
        if account:
            lines.append("#PBS -A " + account)
        if email:
            lines.append("#PBS -M " + email)
            lines.append("#PBS -m ae")
        return lines

    def _sge_directives(
        self, job_name: str, output_dir: Path, walltime: str | None,
        cpus: int | None, memory_mb: int | None, queue: str | None, email: str | None,
        nodes: int | None, account: str | None,
    ) -> list[str]:
        if nodes not in (None, 1):
            raise ValueError("SGE backend does not support multi-node requests")
        lines = ["#!/bin/bash"]
        lines.append("#$ -N " + job_name)
        lines.append("#$ -o " + str(output_dir) + "/" + job_name + ".out")
        lines.append("#$ -e " + str(output_dir) + "/" + job_name + ".err")
        if queue:
            lines.append("#$ -q " + queue)
        if walltime:
            lines.append("#$ -l h_rt=" + walltime)
        if cpus:
            lines.append("#$ -pe smp " + str(cpus))
        if memory_mb:
            lines.append("#$ -l h_vmem=" + str(memory_mb) + "M")
        if account:
            lines.append("#$ -A " + account)
        if email:
            lines.append("#$ -M " + email)
            lines.append("#$ -m ae")
        return lines
