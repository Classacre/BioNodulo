"""Workflow dependency resolution for BioNodulo.

Scans workflows for node types, executables, and Python packages,
then returns what is required and how to obtain it.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
)
from bionodulo.environments.manifest import (
    get_env_dir,
    get_environment_plan_id,
    is_env_ready,
    workflow_to_environment_plan,
)

logger = logging.getLogger(__name__)


def _is_declarative_cwl_class(node_class: Any) -> bool:
    """Return whether *node_class* is bound to the shared CWL runtime."""
    try:
        from bionodulo.nodes.declarative_cwl import DECLARATIVE_CWL_FACTORY

        spec = node_class.CONTRACT_SPEC
        return (
            spec.cwl_invocation is not None
            and spec.execution_factory == DECLARATIVE_CWL_FACTORY
        ) or (
            spec.cwl_reference is not None
            and spec.execution_factory == "bionodulo.nodes.cwl_reference_runtime:CwlReferenceNode"
        ) or (
            spec.cwl_oci is not None
            and spec.execution_factory == "bionodulo.nodes.cwl_oci_runtime:CwlOciNode"
        )
    except (AttributeError, ImportError):
        return False


def _verify_declarative_stdout_workspace(spec: Any, workspace_dir: str | Path) -> None:
    """Require the selected filesystem to support safe stdout publication."""
    from bionodulo.nodes.contract.artifacts import Cardinality
    from bionodulo.nodes.contract.outputs import (
        OutputSpec,
        StdoutCollector,
        collect_outputs,
    )

    if not any(isinstance(output.collector, StdoutCollector) for output in spec.outputs):
        return
    workspace = Path(workspace_dir).expanduser().absolute()
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".cwl-stdout-capability-", dir=workspace) as temporary:
            probe = OutputSpec(
                port_id="stdout_capability_probe",
                artifact_type="artifact.file",
                cardinality=Cardinality.ONE,
                collector=StdoutCollector(
                    relative_path="stdout-capability-probe.bin",
                    maximum_bytes=1,
                ),
            )
            collect_outputs(
                (probe,),
                temporary,
                stdout=b"x",
                stdout_truncated=False,
            )
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "selected workspace filesystem cannot safely publish declarative CWL stdout; "
            "use a writable native Linux filesystem workspace (for example under /tmp or /opt), "
            f"not a Windows-mounted path: {error}"
        ) from error


async def _verify_declarative_cwl_class(
    node_class: Any,
    workspace_dir: str | Path,
) -> str | None:
    """Verify one configured native CWL runtime without invoking the legacy solver.

    A ``None`` result means that the current host can execute the bound node
    through the exact executable in its configured prefix.  An error string is deliberately
    fail-closed and becomes a workflow resolution error.
    """
    try:
        if getattr(node_class.CONTRACT_SPEC, "cwl_oci", None) is not None:
            from bionodulo.nodes.cwl_oci_runtime import configured_oci_runtime, prove_oci_runtime

            spec = node_class.CONTRACT_SPEC
            metadata = getattr(node_class, "ENVIRONMENT", None)
            if not isinstance(metadata, dict) or metadata.get("type") != "declarative_oci":
                raise RuntimeError("bound OCI node is missing container environment metadata")
            if metadata.get("name") != spec.environment.environment_id:
                raise RuntimeError("bound OCI environment ID differs from contract")
            if metadata.get("digest") != spec.environment.environment_digest():
                raise RuntimeError("bound OCI environment digest differs from contract")
            prove_oci_runtime(spec.cwl_oci, configured_oci_runtime())
            _verify_declarative_stdout_workspace(spec, workspace_dir)
            return None
        if getattr(node_class.CONTRACT_SPEC, "cwl_reference", None) is not None:
            from bionodulo.nodes.cwl_reference_runtime import verify_reference_runtime
            spec = node_class.CONTRACT_SPEC
            metadata = getattr(node_class, "ENVIRONMENT", None)
            if not isinstance(metadata, dict) or metadata.get("type") != "declarative_cwl":
                raise RuntimeError("bound node is missing declarative CWL environment metadata")
            if metadata.get("name") != spec.environment.environment_id:
                raise RuntimeError("bound node environment ID does not match its contract")
            if metadata.get("digest") != spec.environment.environment_digest():
                raise RuntimeError("bound node environment digest does not match its contract")
            await verify_reference_runtime(spec, workspace_dir=workspace_dir)
            return None
        from bionodulo.execution.subprocess_runner import run_subprocess
        from bionodulo.nodes.declarative_cwl import (
            PROBE_TIMEOUT_SECONDS,
            _assert_supported_host,
            _environment_digest,
            _locked_executable,
            _probe_for,
            _sha256_file,
            _validate_bound_spec,
        )

        spec = _validate_bound_spec(node_class.CONTRACT_SPEC)
        declared_digest = _environment_digest(spec)
        environment = spec.environment
        assert environment is not None
        metadata = getattr(node_class, "ENVIRONMENT", None)
        if type(metadata) is not dict or metadata.get("type") != "declarative_cwl":
            raise RuntimeError("bound node is missing declarative CWL environment metadata")
        if metadata.get("name") != environment.environment_id:
            raise RuntimeError("bound node environment ID does not match its contract")
        if metadata.get("digest") != declared_digest:
            raise RuntimeError("bound node environment digest does not match its contract")

        _assert_supported_host(spec)
        _verify_declarative_stdout_workspace(spec, workspace_dir)
        probe = _probe_for(spec)
        if probe.fingerprint is None:
            raise RuntimeError("native declarative CWL probe has no executable fingerprint")
        executable = _locked_executable(spec, probe)
        actual_digest = _sha256_file(executable)
        if actual_digest != probe.fingerprint:
            raise RuntimeError(
                f"executable fingerprint mismatch: expected {probe.fingerprint}, got {actual_digest}"
            )
        result = await run_subprocess(
            [str(executable), *probe.version_arguments],
            cwd=executable.parent,
            timeout=PROBE_TIMEOUT_SECONDS,
            node_id=str(getattr(node_class, "NODE_ID", "declarative-cwl-readiness")),
        )
        combined = "\n".join((str(result.get("stdout", "")), str(result.get("stderr", ""))))
        for line in combined.splitlines():
            if not line.startswith(probe.version_line_prefix):
                continue
            remainder = line[len(probe.version_line_prefix) :].strip()
            if remainder and remainder.split(maxsplit=1)[0] == probe.expected_version:
                return None
        raise RuntimeError(
            f"executable probe {probe.probe_id!r} did not report locked version "
            f"{probe.expected_version!r}"
        )
    except Exception as error:
        return str(error)


def build_node_manifest(
    workflow: dict[str, Any],
    registry: Any,
) -> dict[str, dict[str, Any]]:
    """Build a manifest of all node types used in a workflow.

    Captures metadata at save time so missing nodes can be resolved
    even if they are later uninstalled.
    """
    manifest: dict[str, dict[str, Any]] = {}
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = nodes.values()

    seen: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            node_type = node.get("type", "")
        else:
            node_type = getattr(node, "type", "")
        if not node_type or node_type in seen:
            continue
        seen.add(node_type)

        entry: dict[str, Any] = {"type": node_type}

        if registry is not None and hasattr(registry, "get"):
            node_class = registry.get(node_type)
            if node_class is not None:
                entry["display_name"] = getattr(node_class, "DISPLAY_NAME", node_type)
                entry["category"] = getattr(node_class, "CATEGORY", "")
                entry["version"] = getattr(node_class, "VERSION", "")
                if hasattr(node_class, "lifecycle_metadata"):
                    entry["lifecycle"] = node_class.lifecycle_metadata()
                if hasattr(node_class, "versioning_metadata"):
                    entry["versioning"] = node_class.versioning_metadata()
                entry["git_url"] = getattr(node_class, "GIT_URL", "")
                entry["git_commit"] = getattr(node_class, "GIT_COMMIT", "")
                entry["required_executables"] = getattr(
                    node_class, "REQUIRED_EXECUTABLES", []
                )
                entry["required_r_packages"] = getattr(
                    node_class, "REQUIRED_R_PACKAGES", []
                )
                entry["builtin"] = getattr(node_class, "__module__", "").startswith(
                    "bionodulo.nodes.builtin"
                )
                entry["python_class"] = (
                    f"{node_class.__module__}.{node_class.__name__}"
                )
            else:
                # Node not registered — try to get info from the node's stored node_info
                node_info = node.get("node_info", {}) if isinstance(node, dict) else {}
                if node_info:
                    entry["display_name"] = node_info.get("display_name", node_type)
                    entry["category"] = node_info.get("category", "")
                    entry["version"] = node_info.get("version", "")
                    entry["lifecycle"] = node_info.get("lifecycle", {})
                    entry["versioning"] = node_info.get("versioning", {})
                    entry["git_url"] = node_info.get("git_url", "")
                    entry["git_commit"] = node_info.get("git_commit", "")
                    package_info = node_info.get("custom_node_package", {})
                    if isinstance(package_info, dict):
                        entry["requirements"] = [
                            str(req)
                            for req in package_info.get("requirements", [])
                            if req
                        ]
                    entry["required_executables"] = node_info.get(
                        "required_executables", []
                    )
                    entry["required_r_packages"] = node_info.get(
                        "required_r_packages", []
                    )
                    entry["builtin"] = node_info.get("builtin", False)

        manifest[node_type] = entry

    return manifest


@dataclass
class MissingNode:
    """A custom node type that is not currently registered."""

    node_type: str
    git_url: str = ""
    git_commit: str = ""
    requirements: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class MissingExecutable:
    """An external tool executable that is not available."""

    name: str
    conda_package: str = ""
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class MissingPackage:
    """A Python package that needs installation."""

    name: str
    source: str = "pip"  # pip or conda
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class MissingRPackage:
    """An R package that needs installation."""

    name: str
    source: str = "cran"  # cran or bioconductor
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class ResolutionReport:
    """Complete resolution report for a workflow."""

    missing_nodes: list[MissingNode] = field(default_factory=list)
    missing_executables: list[MissingExecutable] = field(default_factory=list)
    missing_packages: list[MissingPackage] = field(default_factory=list)
    missing_r_packages: list[MissingRPackage] = field(default_factory=list)
    required_packages: list[str] = field(default_factory=list)
    env_id: str = ""
    env_ready: bool = False
    env_isolation: str = "auto"
    declarative_runtime_required: bool = False
    declarative_runtime_ready: bool = False
    legacy_runtime_required: bool = True
    installable: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_nodes
            or self.missing_executables
            or self.missing_packages
            or self.missing_r_packages
            or self.errors
        )

    @property
    def execution_ready(self) -> bool:
        """Separate the selected runtime's readiness from Pixi installation.

        Host execution is permitted only when explicitly selected and no
        package environment needs verification. A ready Pixi environment does
        not prove those packages are available to the host interpreter.
        """
        if self.has_issues:
            return False
        if self.declarative_runtime_required and not self.declarative_runtime_ready:
            return False
        if self.env_isolation == "off":
            return not self.required_packages
        if self.env_isolation not in {"auto", "always"}:
            return False
        return not self.legacy_runtime_required or self.env_ready

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.missing_nodes:
            parts.append(f"{len(self.missing_nodes)} node(s)")
        if self.missing_executables:
            parts.append(f"{len(self.missing_executables)} tool(s)")
        if self.missing_packages:
            parts.append(f"{len(self.missing_packages)} Python package(s)")
        if self.missing_r_packages:
            parts.append(f"{len(self.missing_r_packages)} R package(s)")
        if self.env_isolation == "off" and self.required_packages:
            parts.append("host package requirements are unverified; select an isolated environment")
        elif not self.env_ready and self.required_packages:
            parts.append(f"env not ready ({len(self.required_packages)} packages)")
        elif not self.env_ready and self.env_isolation != "off" and self.legacy_runtime_required:
            parts.append("workflow environment is not installed")
        parts.extend(self.errors)
        return ", ".join(parts) if parts else "All dependencies satisfied"

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_nodes": [
                {
                    "node_type": n.node_type,
                    "git_url": n.git_url,
                    "git_commit": n.git_commit,
                    "requirements": n.requirements,
                    "message": n.message,
                }
                for n in self.missing_nodes
            ],
            "missing_executables": [
                {
                    "name": e.name,
                    "conda_package": e.conda_package,
                    "node_types": e.node_types,
                    "message": e.message,
                }
                for e in self.missing_executables
            ],
            "missing_packages": [
                {
                    "name": p.name,
                    "source": p.source,
                    "node_types": p.node_types,
                    "message": p.message,
                }
                for p in self.missing_packages
            ],
            "missing_r_packages": [
                {
                    "name": p.name,
                    "source": p.source,
                    "node_types": p.node_types,
                    "message": p.message,
                }
                for p in self.missing_r_packages
            ],
            "required_packages": self.required_packages,
            "env_id": self.env_id,
            "env_ready": self.env_ready,
            "env_isolation": self.env_isolation,
            "declarative_runtime_required": self.declarative_runtime_required,
            "declarative_runtime_ready": self.declarative_runtime_ready,
            "legacy_runtime_required": self.legacy_runtime_required,
            "execution_ready": self.execution_ready,
            "installable": self.installable,
            "errors": self.errors,
            "has_issues": self.has_issues,
            "summary": self.summary,
        }


async def _resolve_node_type(
    node_type: str,
    node_ids: list[str],
    registry: Any,
    manifest: dict[str, Any],
) -> tuple[
    list[MissingNode],
    list[MissingExecutable],
    list[MissingPackage],
    dict[str, list[str]],
]:
    """Resolve dependencies for a single node type.

    Returns missing nodes, required executables (for later filtering),
    missing packages, and a map of R packages to the node types that require them.
    """
    missing_nodes: list[MissingNode] = []
    required_executables: list[MissingExecutable] = []
    missing_packages: list[MissingPackage] = []
    r_packages_to_check: dict[str, list[str]] = {}

    node_class = None
    if registry is not None and hasattr(registry, "get"):
        node_class = registry.get(node_type)

    if node_class is None:
        manifest_entry = manifest.get(node_type, {})
        git_url = manifest_entry.get("git_url", "")
        git_commit = manifest_entry.get("git_commit", "")
        requirements = manifest_entry.get("requirements", [])
        if not isinstance(requirements, list):
            requirements = []

        if git_url:
            msg = f"Custom node '{node_type}' is not installed. Source: {git_url}"
        else:
            msg = (
                f"Custom node '{node_type}' is not installed and no git URL "
                f"was recorded in the workflow manifest."
            )

        missing_nodes.append(
            MissingNode(
                node_type=node_type,
                git_url=git_url,
                git_commit=git_commit,
                requirements=[str(req) for req in requirements if req],
                message=msg,
            )
        )
        return missing_nodes, required_executables, missing_packages, r_packages_to_check

    # Collect required executables (availability checked later against env)
    executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
    conda_packages = getattr(node_class, "REQUIRED_CONDA_PACKAGES", [])

    for exe in executables:
        conda_pkg = ""
        if conda_packages:
            conda_pkg = conda_packages[0]
        else:
            conda_pkg = EXECUTABLE_TO_CONDA_PACKAGE.get(exe, exe)

        required_executables.append(
            MissingExecutable(
                name=exe,
                conda_package=conda_pkg,
                node_types=[node_type],
                message=f"Executable '{exe}' required by '{node_type}'",
            )
        )

    # Collect required R packages for later batch check
    r_packages = getattr(node_class, "REQUIRED_R_PACKAGES", [])
    for pkg in r_packages:
        r_packages_to_check.setdefault(pkg, []).append(node_type)

    # Check for requirements.txt in custom node package
    module_name = getattr(node_class, "__module__", "")
    if not module_name.startswith("bionodulo.nodes.builtin"):
        try:
            module = __import__(module_name, fromlist=[""])
            module_file = getattr(module, "__file__", None)
            if module_file:
                module_dir = Path(module_file).parent
                req_file = module_dir / "requirements.txt"
                if req_file.exists():
                    reqs = [
                        line.strip()
                        for line in req_file.read_text().splitlines()
                        if line.strip() and not line.startswith("#")
                    ]
                    for req in reqs:
                        pkg_name = req.split("==")[0].split(">=")[0].strip()
                        missing_packages.append(
                            MissingPackage(
                                name=pkg_name,
                                source="pip",
                                node_types=[node_type],
                                message=f"Python package '{pkg_name}' from {node_type} requirements",
                            )
                        )
        except Exception as exc:
            logger.debug("Could not check requirements for %s: %s", node_type, exc)

    return missing_nodes, required_executables, missing_packages, r_packages_to_check


async def _resolve_workflow_async(
    workflow: dict[str, Any],
    registry: Any,
    workspace_dir: str | Path = "./workspace",
    *,
    env_isolation: str = "auto",
) -> ResolutionReport:
    """Async implementation of dependency resolution."""
    report = ResolutionReport(env_isolation=env_isolation)
    if env_isolation not in {"auto", "always", "off"}:
        report.errors.append(f"Unsupported environment isolation mode: {env_isolation}")
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    # Collect node types and their usages
    node_type_usages: dict[str, list[str]] = {}
    for node in nodes:
        if isinstance(node, dict):
            node_type = node.get("type", "")
            node_id = node.get("id", "")
        else:
            node_type = getattr(node, "type", "")
            node_id = getattr(node, "id", "")
        if node_type:
            node_type_usages.setdefault(node_type, []).append(node_id)

    manifest = workflow.get("node_manifest", {})
    if not isinstance(manifest, dict) or not manifest:
        manifest = build_node_manifest(workflow, registry)

    # Run checks for each node type concurrently
    coros = [
        _resolve_node_type(node_type, node_ids, registry, manifest)
        for node_type, node_ids in node_type_usages.items()
    ]

    results = await asyncio.gather(*coros, return_exceptions=True)

    r_packages_to_check: dict[str, list[str]] = {}

    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Node-type resolution failed: %s", result)
            report.errors.append(str(result))
            continue

        missing_nodes, missing_executables, missing_packages, node_r_pkgs = result
        report.missing_nodes.extend(missing_nodes)
        report.missing_executables.extend(missing_executables)
        report.missing_packages.extend(missing_packages)

        for r_package_name, node_types in node_r_pkgs.items():
            r_packages_to_check.setdefault(r_package_name, []).extend(node_types)

    # Declarative CWL nodes run from separately realized, descriptor-bound
    # prefixes. Verify those prefixes directly instead of asking the legacy
    # Pixi planner to solve their packages into a second environment.
    declarative_classes: dict[str, Any] = {}
    if registry is not None and hasattr(registry, "get"):
        for node_type in node_type_usages:
            node_class = registry.get(node_type)
            if node_class is not None and _is_declarative_cwl_class(node_class):
                declarative_classes[node_type] = node_class
    declarative_results = await asyncio.gather(
        *(
            _verify_declarative_cwl_class(node_class, workspace_dir)
            for node_class in declarative_classes.values()
        )
    )
    report.declarative_runtime_required = bool(declarative_classes)
    report.declarative_runtime_ready = bool(declarative_classes) and all(
        error is None for error in declarative_results
    )
    # Built-in file/graph operations explicitly run in the app process and have
    # no tool environment. Their presence must not demand an empty Pixi install
    # before a separately verified generated tool can run.
    def needs_legacy_runtime(node_type: str) -> bool:
        if node_type in declarative_classes:
            return False
        node_class = registry.get(node_type) if registry is not None and hasattr(registry, "get") else None
        return not (
            node_class is not None
            and getattr(node_class, "__module__", "").startswith("bionodulo.nodes.builtin.")
            and getattr(node_class, "REQUIRES_EXTERNAL_TOOLS", True) is False
            and not any(getattr(node_class, key, None) for key in (
                "REQUIRED_EXECUTABLES", "REQUIRED_CONDA_PACKAGES", "REQUIRED_R_PACKAGES", "ENVIRONMENT",
            ))
        )

    report.legacy_runtime_required = any(needs_legacy_runtime(node_type) for node_type in node_type_usages)
    for node_type, error in zip(declarative_classes, declarative_results, strict=True):
        if error is not None:
            report.errors.append(f"declarative CWL runtime for {node_type!r} is not ready: {error}")
            report.installable = False

    # If any node was missing without a git URL, mark as not installable
    if any(not n.git_url for n in report.missing_nodes):
        report.installable = False

    # Build required packages list and env status
    environment_plan = workflow_to_environment_plan(workflow, registry)
    report.required_packages = list(environment_plan.all_packages)
    report.env_id = get_environment_plan_id(environment_plan)
    env_dir = get_env_dir(report.env_id, workspace_dir)
    report.env_ready = is_env_ready(env_dir, environment_plan.environment_names)

    # Filter executables: available if on PATH or in ready env
    deduped_exes: dict[str, MissingExecutable] = {}
    for exe in report.missing_executables:
        if exe.name in deduped_exes:
            deduped_exes[exe.name].node_types.extend(exe.node_types)
        else:
            deduped_exes[exe.name] = exe

    report.missing_executables = []
    for exe in deduped_exes.values():
        if shutil.which(exe.name):
            continue  # Available on system PATH
        if report.env_ready and env_isolation != "off":
            # Env is installed — check if binary exists inside it
            env_bins = (
                env_dir / ".pixi" / "envs" / env_name / "bin" / exe.name
                for env_name in environment_plan.environment_names
            )
            if any(env_bin.exists() for env_bin in env_bins):
                continue
        report.missing_executables.append(exe)

    # Filter R packages: available if env is ready (they're in the manifest)
    if r_packages_to_check and (not report.env_ready or env_isolation == "off"):
        for pkg_name, node_types in r_packages_to_check.items():
            source = (
                "bioconductor"
                if pkg_name.lower()
                in {
                    "deseq2",
                    "edger",
                    "limma",
                    "biostrings",
                    "genomicranges",
                    "rtracklayer",
                    "complexheatmap",
                    "summarizedexperiment",
                    "tximport",
                    "ape",
                    "phyloseq",
                    "variantannotation",
                }
                else "cran"
            )
            report.missing_r_packages.append(
                MissingRPackage(
                    name=pkg_name,
                    source=source,
                    node_types=node_types,
                    message=f"R package '{pkg_name}' required by {', '.join(node_types)}",
                )
            )

    # Deduplicate Python packages
    seen_pkgs: dict[str, MissingPackage] = {}
    for missing_package in report.missing_packages:
        if missing_package.name in seen_pkgs:
            seen_pkgs[missing_package.name].node_types.extend(missing_package.node_types)
        else:
            seen_pkgs[missing_package.name] = missing_package
    report.missing_packages = list(seen_pkgs.values())

    # Deduplicate R packages
    seen_r_pkgs: dict[str, MissingRPackage] = {}
    for missing_r_package in report.missing_r_packages:
        if missing_r_package.name in seen_r_pkgs:
            seen_r_pkgs[missing_r_package.name].node_types.extend(missing_r_package.node_types)
        else:
            seen_r_pkgs[missing_r_package.name] = missing_r_package
    report.missing_r_packages = list(seen_r_pkgs.values())

    return report


def resolve_workflow(
    workflow: dict[str, Any],
    registry: Any,
    workspace_dir: str | Path = "./workspace",
    *,
    env_isolation: str = "auto",
) -> ResolutionReport:
    """Resolve dependencies for a workflow.

    This is a synchronous wrapper around the async implementation.
    Callers inside an async context should await _resolve_workflow_async directly.
    """
    return asyncio.run(_resolve_workflow_async(workflow, registry, workspace_dir, env_isolation=env_isolation))
