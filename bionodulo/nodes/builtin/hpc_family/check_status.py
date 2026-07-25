"""Fail-closed HPC job-status node."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .adapter import (
    HPCAdapterNode,
    HPC_STATES,
    SUPPORTED_SCHEDULERS,
    require_adapter,
    scheduler_name,
    validate_job_id,
    validate_scheduler,
)


class HPCCheckStatusNode(HPCAdapterNode):
    """Query a submitted job through a configured HPC adapter."""

    NODE_ID = "hpc_check_status"
    DISPLAY_NAME = "HPC Check Status"
    DESCRIPTION = "Check a Slurm, PBS, or SGE job through a configured HPC adapter."
    SEARCH_ALIASES = ["hpc", "status", "check", "monitor", "job", "slurm", "pbs", "sge"]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("status", "details")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "job_id": ("STRING", {"description": "Scheduler-assigned job ID"}),
                "scheduler": (list(SUPPORTED_SCHEDULERS), {"default": "slurm"}),
            },
            "optional": {},
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        job_validation = validate_job_id(inputs.get("job_id"))
        if job_validation is not True:
            return job_validation
        return validate_scheduler(inputs.get("scheduler", "slurm"))

    async def run(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        adapter = require_adapter(context, "status")
        result = await adapter.status(
            job_id=str(kwargs["job_id"]),
            scheduler=scheduler_name(kwargs.get("scheduler")),
        )
        if not isinstance(result, Mapping):
            raise RuntimeError("HPC status adapter must return a mapping")
        details = {str(key): value for key, value in result.items()}
        state = str(details.get("state", "")).strip().upper()
        if state not in HPC_STATES:
            raise RuntimeError("HPC status adapter returned a missing or unsupported state")
        details["state"] = state
        return (state, details)
