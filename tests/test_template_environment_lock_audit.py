from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.environments.manifest import (
    generate_environment_manifest,
    generate_manifest,
    get_env_id,
    get_environment_plan_id,
    workflow_to_environment_plan,
)
from scripts.audit_template_environment_locks import (
    audit_template_environment_locks,
    format_report,
)


class StubNode:
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_R_PACKAGES: list[str] = []


class StubRegistry:
    @staticmethod
    def get(node_type: str) -> type[StubNode] | None:
        return StubNode if node_type == "tool" else None


def _write_template(path: Path, node_type: str) -> None:
    path.write_text(
        json.dumps({"nodes": [{"id": "node", "type": node_type}], "edges": []}),
        encoding="utf-8",
    )


def _write_minimal_lock(path: Path, environment_names: tuple[str, ...] = ("default",)) -> None:
    lines = [
        "version: 7",
        "platforms:",
        "- name: linux-64",
        "environments:",
    ]
    for name in environment_names:
        lines.extend(
            (
                f"  {name}:",
                "    packages:",
                "      linux-64:",
                f"      - conda: https://example.invalid/linux-64/{name}-1.0-0.conda",
            )
        )
    lines.extend(
        (
            "packages:",
            "- conda: https://example.invalid/linux-64/package-1.0-0.conda",
            "  sha256: " + "a" * 64,
            "",
        )
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def test_audit_reports_missing_bundle_with_stable_actionable_inventory(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    locks = tmp_path / "locks"
    templates.mkdir()
    locks.mkdir()
    _write_template(templates / "z_template.json", "tool")
    _write_template(templates / "a_template.json", "tool")

    report = audit_template_environment_locks(templates, locks, StubRegistry())
    environment_id = get_env_id(["samtools"])

    assert report.ok is False
    assert [record.template for record in report.records] == ["a_template.json", "z_template.json"]
    assert {record.status for record in report.records} == {"missing"}
    assert {record.environment_id for record in report.records} == {environment_id}
    assert {record.packages for record in report.records} == {("samtools",)}
    assert format_report(report).splitlines() == [
        "official template environment locks: FAIL",
        f"MISSING a_template.json environment={environment_id} packages=[samtools] "
        f"expected=[{environment_id}/pixi.toml,{environment_id}/pixi.lock] "
        "detail=expected pixi.toml and pixi.lock",
        f"MISSING z_template.json environment={environment_id} packages=[samtools] "
        f"expected=[{environment_id}/pixi.toml,{environment_id}/pixi.lock] "
        "detail=expected pixi.toml and pixi.lock",
        "summary: templates=2 base=0 locked=0 missing=2 invalid=0",
        "Generate and review the listed bundles in bionodulo/environments/locks; "
        "this audit does not run pixi lock or install packages.",
    ]


def test_audit_accepts_an_exact_linux_64_bundle_without_running_pixi(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    locks = tmp_path / "locks"
    templates.mkdir()
    locks.mkdir()
    _write_template(templates / "tool.json", "tool")
    environment_id = get_env_id(["samtools"])
    bundle = locks / environment_id
    generate_manifest(bundle, ["samtools"])
    _write_minimal_lock(bundle / "pixi.lock")

    report = audit_template_environment_locks(templates, locks, StubRegistry())

    assert report.ok is True
    assert report.records[0].status == "locked"
    assert format_report(report).splitlines() == [
        "official template environment locks: PASS",
        "summary: templates=1 base=0 locked=1 missing=0 invalid=0",
    ]


def test_audit_rejects_unknown_nodes_and_incomplete_or_stale_bundles(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    locks = tmp_path / "locks"
    templates.mkdir()
    locks.mkdir()
    _write_template(templates / "unknown.json", "unknown")
    _write_template(templates / "tool.json", "tool")
    environment_id = get_env_id(["samtools"])
    bundle = locks / environment_id
    bundle.mkdir()
    (bundle / "pixi.toml").write_text("stale\n", encoding="utf-8")

    report = audit_template_environment_locks(templates, locks, StubRegistry())
    by_template: dict[str, Any] = {record.template: record for record in report.records}

    assert by_template["unknown.json"].status == "invalid"
    assert by_template["unknown.json"].detail == "unknown node types: unknown"
    assert by_template["tool.json"].status == "invalid"
    assert by_template["tool.json"].detail == "incomplete bundle; missing pixi.lock"

    _write_minimal_lock(bundle / "pixi.lock")
    report = audit_template_environment_locks(templates, locks, StubRegistry())
    by_template = {record.template: record for record in report.records}
    assert by_template["tool.json"].detail == "pixi.toml does not match the current package constraints"


def test_audit_requires_every_named_environment_in_the_same_lock(tmp_path: Path) -> None:
    class MantaNode:
        REQUIRED_CONDA_PACKAGES = ["manta"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT = {"type": "pixi", "name": "manta"}

    class MultiRegistry:
        @staticmethod
        def get(node_type: str) -> type | None:
            return {"tool": StubNode, "manta": MantaNode}.get(node_type)

    templates = tmp_path / "templates"
    locks = tmp_path / "locks"
    templates.mkdir()
    locks.mkdir()
    workflow = {
        "nodes": [
            {"id": "tool", "type": "tool"},
            {"id": "manta", "type": "manta"},
        ],
        "edges": [],
    }
    (templates / "variant.json").write_text(json.dumps(workflow), encoding="utf-8")
    plan = workflow_to_environment_plan(workflow, MultiRegistry())
    bundle = locks / get_environment_plan_id(plan)
    generate_environment_manifest(bundle, plan)
    _write_minimal_lock(bundle / "pixi.lock")

    report = audit_template_environment_locks(templates, locks, MultiRegistry())
    assert report.records[0].status == "invalid"
    assert report.records[0].detail == "pixi.lock has no valid linux-64 environments: default, manta"

    _write_minimal_lock(bundle / "pixi.lock", ("default", "manta"))
    report = audit_template_environment_locks(templates, locks, MultiRegistry())
    assert report.ok is True
    assert report.records[0].environment_names == ("default", "manta")
