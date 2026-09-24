"""Resolver readiness for separately realized declarative CWL runtimes."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.manager import resolver
from bionodulo.nodes.declarative_cwl import DECLARATIVE_CWL_FACTORY


class _Registry:
    def __init__(self, nodes: dict[str, type]) -> None:
        self._nodes = nodes

    def get(self, node_type: str) -> type | None:
        return self._nodes.get(node_type)


class _DeclarativeNode:
    __module__ = "bionodulo.nodes.builtin.declarative_test"
    NODE_ID = "declarative_test"
    CONTRACT_SPEC = SimpleNamespace(
        cwl_invocation=object(),
        execution_factory=DECLARATIVE_CWL_FACTORY,
    )
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_R_PACKAGES: list[str] = []


class _LegacyNode:
    __module__ = "bionodulo.nodes.builtin.legacy_test"
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    REQUIRED_R_PACKAGES: list[str] = []


def _workflow(*node_types: str) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": f"node-{index}", "type": node_type}
            for index, node_type in enumerate(node_types)
        ],
        "edges": [],
    }


def test_verified_declarative_only_workflow_is_ready_without_claiming_pixi_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def verified(_node_class: type, _workspace_dir: str | Path) -> str | None:
        return None

    monkeypatch.setattr(resolver, "_verify_declarative_cwl_class", verified)
    report = resolver.resolve_workflow(
        _workflow("declarative"),
        _Registry({"declarative": _DeclarativeNode}),
        tmp_path,
        env_isolation="auto",
    )

    assert report.env_ready is False
    assert report.declarative_runtime_required is True
    assert report.declarative_runtime_ready is True
    assert report.legacy_runtime_required is False
    assert report.execution_ready is True
    assert report.summary == "All dependencies satisfied"


def test_missing_declarative_prefix_remains_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def missing(_node_class: type, _workspace_dir: str | Path) -> str | None:
        return "locked CWL environment is not realized"

    monkeypatch.setattr(resolver, "_verify_declarative_cwl_class", missing)
    report = resolver.resolve_workflow(
        _workflow("declarative"),
        _Registry({"declarative": _DeclarativeNode}),
        tmp_path,
        env_isolation="auto",
    )

    assert report.env_ready is False
    assert report.declarative_runtime_ready is False
    assert report.execution_ready is False
    assert report.installable is False
    assert "not realized" in report.summary


def test_constructed_unready_declarative_report_fails_closed_in_host_mode() -> None:
    report = resolver.ResolutionReport(
        env_isolation="off",
        declarative_runtime_required=True,
        declarative_runtime_ready=False,
        legacy_runtime_required=False,
    )

    assert report.execution_ready is False


def test_mixed_workflow_still_requires_legacy_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def verified(_node_class: type, _workspace_dir: str | Path) -> str | None:
        return None

    monkeypatch.setattr(resolver, "_verify_declarative_cwl_class", verified)
    report = resolver.resolve_workflow(
        _workflow("declarative", "legacy"),
        _Registry({"declarative": _DeclarativeNode, "legacy": _LegacyNode}),
        tmp_path,
        env_isolation="auto",
    )

    assert report.declarative_runtime_ready is True
    assert report.legacy_runtime_required is True
    assert report.required_packages == ["samtools"]
    assert report.env_ready is False
    assert report.execution_ready is False


def test_builtin_input_file_can_feed_generated_tool_without_empty_pixi_environment(monkeypatch, tmp_path):
    from bionodulo.nodes.builtin.input_family.file import InputFileNode

    async def verified(_node_class, _workspace_dir):
        return None

    monkeypatch.setattr(resolver, "_verify_declarative_cwl_class", verified)
    report = resolver.resolve_workflow(
        _workflow("declarative", "input_file"),
        _Registry({"declarative": _DeclarativeNode, "input_file": InputFileNode}),
        tmp_path,
        env_isolation="auto",
    )
    assert report.required_packages == []
    assert report.env_ready is False
    assert report.legacy_runtime_required is False
    assert report.execution_ready is True


def test_no_external_tools_flag_does_not_override_declared_dependencies(monkeypatch, tmp_path):
    class ContradictoryNode(_LegacyNode):
        __module__ = "bionodulo.nodes.builtin.example"
        REQUIRES_EXTERNAL_TOOLS = False

    report = resolver.resolve_workflow(
        _workflow("legacy"), _Registry({"legacy": ContradictoryNode}), tmp_path,
    )
    assert report.legacy_runtime_required is True
    assert report.execution_ready is False


@pytest.mark.asyncio
async def test_declarative_verifier_rejects_contract_metadata_digest_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bionodulo.nodes.declarative_cwl as runtime

    environment = SimpleNamespace(environment_id="locked-runtime")
    spec = SimpleNamespace(environment=environment)
    node_class = SimpleNamespace(
        CONTRACT_SPEC=spec,
        ENVIRONMENT={
            "type": "declarative_cwl",
            "name": "locked-runtime",
            "digest": "sha256:" + "0" * 64,
        },
    )
    monkeypatch.setattr(runtime, "_validate_bound_spec", lambda _spec: spec)
    monkeypatch.setattr(runtime, "_environment_digest", lambda _spec: "sha256:" + "1" * 64)

    error = await resolver._verify_declarative_cwl_class(node_class, tmp_path)

    assert error == "bound node environment digest does not match its contract"


@pytest.mark.asyncio
async def test_declarative_verifier_rejects_incompatible_host_before_prefix_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bionodulo.nodes.declarative_cwl as runtime

    digest = "sha256:" + "1" * 64
    environment = SimpleNamespace(environment_id="locked-runtime")
    spec = SimpleNamespace(environment=environment)
    node_class = SimpleNamespace(
        CONTRACT_SPEC=spec,
        ENVIRONMENT={"type": "declarative_cwl", "name": "locked-runtime", "digest": digest},
    )
    monkeypatch.setattr(runtime, "_validate_bound_spec", lambda _spec: spec)
    monkeypatch.setattr(runtime, "_environment_digest", lambda _spec: digest)

    def incompatible(_spec: object) -> None:
        raise RuntimeError("locked environment does not support this host")

    monkeypatch.setattr(runtime, "_assert_supported_host", incompatible)

    error = await resolver._verify_declarative_cwl_class(node_class, tmp_path)

    assert error == "locked environment does not support this host"


def test_stdout_workspace_capability_failure_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bionodulo.nodes.contract.outputs as outputs

    spec = SimpleNamespace(
        outputs=(
            SimpleNamespace(
                collector=outputs.StdoutCollector(relative_path="result.bin", maximum_bytes=16)
            ),
        ),
    )

    def unsupported(*_args: object, **_kwargs: object) -> object:
        raise outputs.OutputCollectionError(
            "filesystem does not support safe anonymous stdout staging"
        )

    monkeypatch.setattr(outputs, "collect_outputs", unsupported)

    with pytest.raises(RuntimeError, match="writable native Linux filesystem workspace"):
        resolver._verify_declarative_stdout_workspace(spec, tmp_path)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.skipif(os.name != "posix", reason="safe anonymous stdout publication is Linux-only")
def test_native_linux_workspace_supports_stdout_publication(tmp_path: Path) -> None:
    from bionodulo.nodes.contract.outputs import StdoutCollector

    spec = SimpleNamespace(
        outputs=(
            SimpleNamespace(
                collector=StdoutCollector(relative_path="result.bin", maximum_bytes=16)
            ),
        ),
    )

    resolver._verify_declarative_stdout_workspace(spec, tmp_path)
    assert not tuple(tmp_path.iterdir())
