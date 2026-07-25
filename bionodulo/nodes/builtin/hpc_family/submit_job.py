"""Fail-closed HPC workflow submission node."""
from __future__ import annotations

from typing import Any

from .adapter import (
    HPCAdapterNode,
    SUPPORTED_SCHEDULERS,
    require_adapter,
    scheduler_name,
    validate_memory,
    validate_positive_int,
    validate_safe_value,
    validate_scheduler,
    validate_walltime,
    validate_workflow_json,
)


class HPCSubmitJobNode(HPCAdapterNode):
    """Submit a serialized workflow through a configured HPC adapter."""

    NODE_ID = "hpc_submit_job"
    DISPLAY_NAME = "HPC Submit Job"
    DESCRIPTION = "Submit a workflow to a configured Slurm, PBS, or SGE adapter."
    SEARCH_ALIASES = ["hpc", "submit", "slurm", "pbs", "sge", "cluster", "batch"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("job_id",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "workflow_json": (
                    "STRING",
                    {"description": "Serialized BioNodulo workflow JSON object", "multiline": True},
                ),
                "scheduler": (list(SUPPORTED_SCHEDULERS), {"default": "slurm"}),
            },
            "optional": {
                "partition": ("STRING", {"default": "", "description": "Queue or partition name"}),
                "nodes": ("INT", {"default": 1, "min": 1}),
                "cores": ("INT", {"default": 8, "min": 1}),
                "memory": ("STRING", {"default": "32G"}),
                "walltime": ("STRING", {"default": "24:00:00"}),
                "account": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validations = (
            validate_workflow_json(inputs.get("workflow_json")),
            validate_scheduler(inputs.get("scheduler", "slurm")),
            validate_positive_int(inputs.get("nodes", 1), "nodes"),
            validate_positive_int(inputs.get("cores", 8), "cores"),
            validate_memory(inputs.get("memory", "32G")),
            validate_walltime(inputs.get("walltime", "24:00:00")),
            validate_safe_value(inputs.get("partition", ""), "partition"),
            validate_safe_value(inputs.get("account", ""), "account"),
        )
        return next((item for item in validations if item is not True), True)

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        adapter = require_adapter(context, "submit")
        job_id = await adapter.submit(
            workflow=kwargs["workflow_json"],
            scheduler=scheduler_name(kwargs.get("scheduler")),
            partition=str(kwargs.get("partition", "") or ""),
            nodes=int(kwargs.get("nodes", 1)),
            cores=int(kwargs.get("cores", 8)),
            memory=str(kwargs.get("memory", "32G")),
            walltime=str(kwargs.get("walltime", "24:00:00")),
            account=str(kwargs.get("account", "") or ""),
        )
        if not str(job_id or "").strip():
            raise RuntimeError("HPC submit adapter returned an empty job ID")
        return (str(job_id),)
