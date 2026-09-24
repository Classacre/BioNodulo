"""Readiness follows the selected runtime; missing requirements never pass."""
from pathlib import Path

import pytest

from bionodulo.manager.resolver import (
    MissingExecutable, MissingNode, MissingPackage, MissingRPackage,
    ResolutionReport, resolve_workflow,
)
from bionodulo.nodes.registry import NodeRegistry


def test_real_builtin_without_packages_can_use_explicit_host_runtime(tmp_path: Path):
    workflow = {"nodes": [{"id": "normalize", "type": "normalize_data"}], "edges": []}
    registry = NodeRegistry.create_isolated()
    host = resolve_workflow(workflow, registry, tmp_path, env_isolation="off")
    assert not host.env_ready
    assert host.required_packages == []
    assert host.execution_ready
    assert host.to_dict()["execution_ready"] is True
    for mode in ("auto", "always"):
        isolated = resolve_workflow(workflow, registry, tmp_path, env_isolation=mode)
        assert not isolated.execution_ready
        assert "environment is not installed" in isolated.summary


@pytest.mark.parametrize("issue", [
    {"missing_nodes": [MissingNode("absent")]},
    {"missing_executables": [MissingExecutable("absent")]},
    {"missing_packages": [MissingPackage("absent")]},
    {"missing_r_packages": [MissingRPackage("absent")]},
    {"errors": ["dependency resolution failed"]},
])
def test_missing_dependencies_and_resolution_errors_always_block(issue):
    for mode in ("off", "auto", "always"):
        assert not ResolutionReport(env_ready=True, env_isolation=mode, **issue).execution_ready


def test_installed_pixi_does_not_prove_host_package_requirements():
    report = ResolutionReport(env_ready=True, env_isolation="off", required_packages=["biopython"])
    assert not report.execution_ready
    assert "host package requirements are unverified" in report.summary
    report.env_isolation = "always"
    assert report.execution_ready


def test_unknown_runtime_policy_is_not_execution_ready():
    assert not ResolutionReport(env_ready=True, env_isolation="unsupported").execution_ready
