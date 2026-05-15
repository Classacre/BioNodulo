"""HPC integration nodes for BioNodulo.

Provides nodes for submitting jobs to HPC clusters and checking their status.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class HPCSubmitJobNode(CommandNode):
    """Submit a job to an HPC cluster."""
    NODE_ID = "hpc_submit_job"
    DISPLAY_NAME = "HPC Submit Job"
    REQUIRED_CONDA_PACKAGES = []
    CATEGORY = "hpc"
    DESCRIPTION = "Submit a workflow job to a configured HPC cluster (SLURM, PBS, SGE)"
    SEARCH_ALIASES = ["hpc", "submit", "slurm", "pbs", "sge", "cluster", "batch"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("job_id",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "workflow_json": ("STRING", {"description": "Workflow definition JSON string", "multiline": True}),
                "scheduler": ("STRING", {"default": "slurm", "description": "slurm, pbs, sge, lsf"}),
            },
            "optional": {
                "partition": ("STRING", {"default": "", "description": "Queue/partition name"}),
                "nodes": ("INT", {"default": 1, "min": 1}),
                "cores": ("INT", {"default": 8, "min": 1}),
                "memory": ("STRING", {"default": "32G"}),
                "walltime": ("STRING", {"default": "24:00:00"}),
                "account": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple:
        """Override to submit via HPC adapter if available."""
        context = kwargs.get("context")
        if context and hasattr(context, "hpc_adapter"):
            adapter = context.hpc_adapter
            job_id = await adapter.submit(
                workflow=kwargs["workflow_json"],
                scheduler=kwargs.get("scheduler", "slurm"),
                partition=kwargs.get("partition"),
                nodes=kwargs.get("nodes", 1),
                cores=kwargs.get("cores", 8),
                memory=kwargs.get("memory", "32G"),
                walltime=kwargs.get("walltime", "24:00:00"),
                account=kwargs.get("account"),
            )
            return (job_id,)
        raise RuntimeError(
            "HPC submission failed: could not connect to any job scheduler. "
            "Please verify that you are on a cluster node with a supported "
            "scheduler (Slurm, PBS/Torque, SGE)."
        )


class HPCCheckStatusNode(CommandNode):
    """Check HPC job status."""
    NODE_ID = "hpc_check_status"
    DISPLAY_NAME = "HPC Check Status"
    CATEGORY = "hpc"
    DESCRIPTION = "Check the status of a submitted HPC job"
    SEARCH_ALIASES = ["hpc", "status", "check", "monitor", "job"]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("status", "details")
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "job_id": ("STRING", {"description": "HPC job ID"}),
                "scheduler": ("STRING", {"default": "slurm", "description": "slurm, pbs, sge, lsf"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple:
        """Override to check status via HPC adapter if available."""
        context = kwargs.get("context")
        if context and hasattr(context, "hpc_adapter"):
            adapter = context.hpc_adapter
            status = await adapter.status(
                job_id=kwargs["job_id"],
                scheduler=kwargs.get("scheduler", "slurm"),
            )
            return (status.get("state", "UNKNOWN"), str(status))
        return ("UNKNOWN", "{\"note\": \"No HPC adapter configured\"}")
