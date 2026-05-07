from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow
from bionodulo.environments.conda import conda_available, conda_create_plan, conda_executable
from bionodulo.environments.containers import apptainer_available, apptainer_plan, docker_available, docker_plan
from bionodulo.manager.runtime_installer import (
    apptainer_runtime_plan,
    docker_runtime_plan,
    managed_micromamba_available,
    managed_micromamba_path,
    managed_micromamba_plan,
)


@dataclass(frozen=True, slots=True)
class NodePack:
    package_id: str
    display_name: str
    node_ids: tuple[str, ...]
    description: str
    source: str
    install_hint: str


BUILTIN_PACKS: tuple[NodePack, ...] = (
    NodePack(
        package_id="bionodulo-core-qc",
        display_name="BioNodulo Core QC",
        node_ids=("fastqc", "multiqc", "fastp"),
        description="Quality control and read preprocessing nodes shipped with BioNodulo.",
        source="builtin",
        install_hint="Already included with BioNodulo.",
    ),
    NodePack(
        package_id="bionodulo-core-alignment",
        display_name="BioNodulo Core Alignment",
        node_ids=("bwa_index", "bwa_mem", "samtools_sort", "samtools_index"),
        description="Alignment placeholders and command wrappers shipped with BioNodulo.",
        source="builtin",
        install_hint="Already included with BioNodulo.",
    ),
)

TOOL_INSTALL_HINTS = {
    "fastqc": "Install FastQC with conda/mamba, for example: mamba install -c bioconda fastqc",
    "fastp": "Install fastp with conda/mamba, for example: mamba install -c bioconda fastp",
    "multiqc": "Install MultiQC with conda/mamba, for example: mamba install -c bioconda multiqc",
    "bwa": "Install BWA with conda/mamba, for example: mamba install -c bioconda bwa",
    "samtools": "Install samtools with conda/mamba, for example: mamba install -c bioconda samtools",
}


def environment_status(registry: NodeRegistry, *, custom_nodes_dir: Path) -> dict[str, Any]:
    node_info = registry.object_info()
    required_tools = sorted({tool for meta in node_info.values() for tool in meta.get("required_executables", [])})
    tools = [
        {
            "name": tool,
            "available": shutil.which(tool) is not None,
            "path": shutil.which(tool),
            "install_hint": TOOL_INSTALL_HINTS.get(tool, f"Install {tool} and make sure it is on PATH."),
        }
        for tool in required_tools
    ]
    custom_packages = _custom_packages(custom_nodes_dir)
    managed_mamba = managed_micromamba_path()
    return {
        "python": sys.version.split()[0],
        "custom_nodes_dir": str(custom_nodes_dir),
        "registered_nodes": len(node_info),
        "import_warnings": list(registry.import_warnings),
        "tools": tools,
        "node_packs": [
            {
                "package_id": pack.package_id,
                "display_name": pack.display_name,
                "node_ids": list(pack.node_ids),
                "description": pack.description,
                "source": pack.source,
                "install_hint": pack.install_hint,
            }
            for pack in BUILTIN_PACKS
        ],
        "custom_packages": custom_packages,
        "runtimes": {
            "conda": {"available": conda_available(), "path": conda_executable(), "managed": managed_micromamba_available(), "managed_path": str(managed_mamba)},
            "docker": {"available": docker_available(), "path": shutil.which("docker")},
            "apptainer": {"available": apptainer_available(), "path": shutil.which("apptainer") or shutil.which("singularity")},
        },
        "manager": {
            "mode": "install-with-confirmation",
            "install_requires_confirmation": True,
            "security_note": "BioNodulo can detect missing node packs and tools and run generated install commands after explicit in-app confirmation.",
            "recommended_runtime": "conda",
            "recommended_setup": "Install BioNodulo-managed micromamba, then create a workflow-specific environment from the workflow JSON.",
        },
    }


def diagnose_workflow(workflow: Workflow, registry: NodeRegistry) -> dict[str, Any]:
    node_info = registry.object_info()
    missing_node_types = sorted({node.type for node in workflow.nodes if not registry.has(node.type)})
    used_node_types = sorted({node.type for node in workflow.nodes if registry.has(node.type)})
    required_tools = sorted({tool for node_type in used_node_types for tool in node_info[node_type].get("required_executables", [])})
    missing_tools = [
        {
            "name": tool,
            "available": shutil.which(tool) is not None,
            "path": shutil.which(tool),
            "install_hint": TOOL_INSTALL_HINTS.get(tool, f"Install {tool} and make sure it is on PATH."),
        }
        for tool in required_tools
        if shutil.which(tool) is None
    ]
    runtime_plans = _runtime_plans_for(workflow)
    install_plans = [_missing_node_plan(node_type) for node_type in missing_node_types]
    tool_plans = [_tool_install_plan(tool, workflow) for tool in missing_tools]
    environment_plan = environment_install_plan(workflow)
    all_plans = [*runtime_plans]
    if environment_plan:
        all_plans.append(environment_plan)
    all_plans.extend(install_plans)
    all_plans.extend(tool_plans)
    return {
        "missing_node_types": missing_node_types,
        "used_node_types": used_node_types,
        "missing_tools": missing_tools,
        "environment": workflow.environment.model_dump(),
        "environment_plan": environment_plan,
        "runtime_plans": runtime_plans,
        "install_plans": all_plans,
        "setup_required": bool(missing_node_types or missing_tools or runtime_plans),
        "setup_summary": _setup_summary(missing_node_types, missing_tools, runtime_plans),
        "safe_to_run_in_mock_mode": not missing_node_types,
    }


def environment_install_plan(workflow: Workflow) -> dict[str, Any] | None:
    spec = workflow.environment
    if spec.type == "conda":
        return conda_create_plan(spec)
    if spec.type == "docker":
        return docker_plan(spec)
    if spec.type == "apptainer":
        return apptainer_plan(spec)
    return None


def _missing_node_plan(node_type: str) -> dict[str, Any]:
    return {
        "kind": "custom_node",
        "target": node_type,
        "status": "unknown",
        "action": "search_or_install_custom_node",
        "command_hint": f"Search a BioNodulo node registry for a package that provides {node_type}.",
        "requires_confirmation": True,
    }


def _runtime_plans_for(workflow: Workflow) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    if workflow.environment.type == "conda" and not conda_available():
        plan = managed_micromamba_plan()
        if plan:
            plans.append(plan)
    if workflow.environment.type == "docker" and not docker_available():
        plan = docker_runtime_plan()
        if plan:
            plans.append(plan)
    if workflow.environment.type == "apptainer" and not apptainer_available():
        plan = apptainer_runtime_plan()
        if plan:
            plans.append(plan)
    return plans


def _setup_summary(missing_node_types: list[str], missing_tools: list[dict[str, Any]], runtime_plans: list[dict[str, Any]]) -> str:
    if not missing_node_types and not missing_tools and not runtime_plans:
        return "Workflow dependencies look ready for real execution."
    parts = []
    if runtime_plans:
        parts.append(f"{len(runtime_plans)} runtime setup step(s)")
    if missing_tools:
        parts.append(f"{len(missing_tools)} missing external tool(s)")
    if missing_node_types:
        parts.append(f"{len(missing_node_types)} missing node type(s)")
    return "Setup needed: " + ", ".join(parts) + "."


def _tool_install_plan(tool: dict[str, Any], workflow: Workflow) -> dict[str, Any]:
    spec = workflow.environment
    if spec.type == "conda":
        channels = [part for channel in spec.channels for part in ("-c", channel)]
        executable = conda_executable() or "mamba"
        return {
            "kind": "tool",
            "target": tool["name"],
            "status": "missing",
            "action": "install_external_tool",
            "command": [executable, "install", "-y", "-n", spec.name, *channels, tool["name"]],
            "command_hint": f"Install {tool['name']} into Conda environment {spec.name}.",
            "environment": spec.model_dump(),
            "requires_confirmation": True,
        }
    if spec.type == "docker":
        return {
            "kind": "tool",
            "target": tool["name"],
            "status": "missing",
            "action": "install_external_tool",
            "command": [],
            "command_hint": f"Use a Docker image that contains {tool['name']} or rebuild {spec.image or spec.name} with that tool installed.",
            "environment": spec.model_dump(),
            "requires_confirmation": True,
        }
    return {
        "kind": "tool",
        "target": tool["name"],
        "status": "missing",
        "action": "install_external_tool",
        "command": [],
        "command_hint": f"Use or build an Apptainer image that contains {tool['name']} for {spec.name}.",
        "environment": spec.model_dump(),
        "requires_confirmation": True,
    }


def _custom_packages(custom_nodes_dir: Path) -> list[dict[str, Any]]:
    if not custom_nodes_dir.exists():
        return []
    packages = []
    for path in sorted(custom_nodes_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.name.startswith("."):
            continue
        if path.is_dir():
            packages.append({"name": path.name, "type": "directory", "path": str(path)})
        elif path.suffix == ".py":
            packages.append({"name": path.name, "type": "python_file", "path": str(path)})
    return packages
