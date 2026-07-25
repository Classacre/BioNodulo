"""Validation helpers for the BioNodulo HPC adapter protocol."""
from __future__ import annotations

import json
import re
import shlex
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from bionodulo.hpc.base import HPCJob
from bionodulo.nodes.base import BaseNode


SUPPORTED_SCHEDULERS = ("slurm", "pbs", "sge")
HPC_STATES = {
    "PENDING",
    "RUNNING",
    "SUSPENDED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "UNKNOWN",
}
_SAFE_SCHEDULER_VALUE = re.compile(r"[A-Za-z0-9_.:+-]*")
_SAFE_JOB_ID = re.compile(r"[A-Za-z0-9_.:+\[\]-]+")
_MEMORY = re.compile(r"[1-9]\d*(?:\.\d+)?[KMGT](?:i?B)?", re.IGNORECASE)
_MEMORY_PARTS = re.compile(r"([1-9]\d*(?:\.\d+)?)([KMGT])(?:i?B)?", re.IGNORECASE)
_WALLTIME = re.compile(r"(\d+):(\d{2}):(\d{2})")


def scheduler_name(value: Any) -> str:
    return str(value or "slurm").strip().lower()


def _backend_scheduler(backend: Any) -> str:
    identity = str(getattr(backend, "scheduler", "") or "").strip().lower()
    if not identity:
        raise RuntimeError("Configured HPC backend does not declare a scheduler identity")
    return "pbs" if identity == "torque" else identity


def _require_matching_backend(backend: Any, requested: Any) -> str:
    requested_name = scheduler_name(requested)
    configured_name = _backend_scheduler(backend)
    if configured_name != requested_name:
        raise RuntimeError(
            f"HPC scheduler mismatch: node requested {requested_name!r}, "
            f"but configured backend is {configured_name!r}"
        )
    return requested_name


def validate_scheduler(value: Any) -> bool | str:
    scheduler = scheduler_name(value)
    if scheduler not in SUPPORTED_SCHEDULERS:
        return f"scheduler must be one of: {', '.join(SUPPORTED_SCHEDULERS)}"
    return True


def validate_positive_int(value: Any, field: str) -> bool | str:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return f"{field} must be an integer"
    if parsed < 1:
        return f"{field} must be at least 1"
    return True


def validate_safe_value(value: Any, field: str) -> bool | str:
    text = str(value or "")
    if text.startswith("-") or _SAFE_SCHEDULER_VALUE.fullmatch(text) is None:
        return f"{field} contains unsupported scheduler characters"
    return True


def validate_memory(value: Any) -> bool | str:
    if _MEMORY.fullmatch(str(value or "").strip()) is None:
        return "memory must use a positive scheduler size such as 4096M or 32G"
    return True


def validate_walltime(value: Any) -> bool | str:
    match = _WALLTIME.fullmatch(str(value or "").strip())
    if match is None or int(match.group(2)) >= 60 or int(match.group(3)) >= 60:
        return "walltime must use HH:MM:SS with minutes and seconds below 60"
    return True


def validate_workflow_json(value: Any) -> bool | str:
    text = str(value or "").strip()
    if not text:
        return "workflow_json is required"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"workflow_json must be valid JSON: {exc.msg}"
    if not isinstance(payload, dict):
        return "workflow_json must encode a JSON object"
    return True


def validate_job_id(value: Any) -> bool | str:
    text = str(value or "").strip()
    if not text:
        return "job_id is required"
    if text.startswith("-") or _SAFE_JOB_ID.fullmatch(text) is None:
        return "job_id contains unsupported scheduler characters"
    return True


def _memory_mb(value: Any) -> int:
    match = _MEMORY_PARTS.fullmatch(str(value or "").strip())
    if match is None:
        raise ValueError("memory must use a positive scheduler size such as 4096M or 32G")
    amount = float(match.group(1))
    factor = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}[match.group(2).upper()]
    return max(1, int(amount * factor))


class HPCBackendAdapter:
    """Bridge the workflow-node protocol to the repository's HPCBackend API."""

    def __init__(self, backend: Any, context: Any) -> None:
        self.backend = backend
        self.context = context

    async def submit(self, **kwargs: Any) -> str:
        scheduler = _require_matching_backend(self.backend, kwargs.get("scheduler"))
        output_dir = Path(self.context.node_dir) / "hpc_submission"
        output_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = output_dir / "workflow.json"
        result_path = output_dir / "result.json"
        workspace_path = output_dir / "workspace"
        workflow_payload = json.loads(str(kwargs["workflow"]))
        workflow_path.write_text(json.dumps(workflow_payload, indent=2, sort_keys=True), encoding="utf-8")

        run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{self.context.run_id}-{self.context.node_id}").strip("-")
        command = shlex.join(
            [
                sys.executable,
                "-m",
                "bionodulo.execution.hpc_job_runner",
                "--workflow",
                str(workflow_path),
                "--result",
                str(result_path),
                "--workspace",
                str(workspace_path),
                "--run-id",
                run_id or "bionodulo-hpc-job",
            ]
        )
        generator = getattr(self.backend, "generate_job_script", None)
        if not callable(generator):
            raise RuntimeError(
                "Configured HPC backend cannot generate a resource-aware job script"
            )
        account = str(kwargs.get("account", "") or "") or str(
            getattr(self.backend, "account", "") or ""
        )
        script_text = generator(
            commands=[command],
            job_name=run_id or "bionodulo_hpc_job",
            output_dir=output_dir,
            walltime=str(kwargs.get("walltime", "24:00:00")),
            cpus=int(kwargs.get("cores", 8)),
            memory_mb=_memory_mb(kwargs.get("memory", "32G")),
            queue=str(kwargs.get("partition", "") or "") or None,
            scheduler=scheduler,
            nodes=int(kwargs.get("nodes", 1)),
            account=account or None,
        )
        script_path = output_dir / "workflow_job.sh"
        script_path.write_text(script_text, encoding="utf-8")
        script_path.chmod(0o700)

        job = await self.backend.submit_job(script_path)
        job_id = getattr(job, "job_id", job)
        if not str(job_id or "").strip():
            raise RuntimeError("HPC backend returned an empty job ID")
        return str(job_id).strip()

    async def status(self, **kwargs: Any) -> dict[str, Any]:
        _require_matching_backend(self.backend, kwargs.get("scheduler"))
        checked = await self.backend.check_status(HPCJob(job_id=str(kwargs["job_id"]).strip()))
        if is_dataclass(checked):
            details = asdict(checked)
        elif isinstance(checked, dict):
            details = dict(checked)
        else:
            raise RuntimeError("HPC backend check_status must return HPCJob or a mapping")
        state = details.pop("status", details.get("state", "UNKNOWN"))
        details["state"] = str(state or "UNKNOWN")
        return details


def require_adapter(context: Any, method: str) -> Any:
    adapter = getattr(context, "hpc_adapter", None) if context is not None else None
    if adapter is not None and callable(getattr(adapter, method, None)):
        return adapter
    backend = getattr(context, "hpc_backend", None) if context is not None else None
    backend_method = "submit_job" if method == "submit" else "check_status"
    if backend is not None and callable(getattr(backend, backend_method, None)):
        return HPCBackendAdapter(backend, context)
    raise RuntimeError(
        f"HPC {method} requires a configured context.hpc_adapter.{method}() or "
        f"context.hpc_backend.{backend_method}()"
    )


class HPCAdapterNode(BaseNode):
    """Common metadata for the internal HPC orchestration protocol."""

    CATEGORY = "hpc"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = "09c1316eabc70cdf1804fece6966a1847002b896"
    DOCUMENTATION_URL = (
        "https://github.com/Classacre/BioNodulo/tree/09c1316eabc70cdf1804fece6966a1847002b896/"
        "bionodulo/hpc"
    )
