#!/usr/bin/env python3
"""Audit committed Pixi-lock coverage for official workflow templates.

Cloud workers deliberately refuse to solve workflow environments at runtime.
Every official template that needs external packages must therefore resolve to
an exact ``bionodulo/environments/locks/<environment-id>/`` bundle containing
both ``pixi.toml`` and ``pixi.lock``.

This command performs no solve or install. It exits non-zero with a stable,
actionable inventory when a bundle is missing or inconsistent.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import yaml

# Ensure the repository root is importable when this file is executed directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bionodulo.environments.manifest import (  # noqa: E402
    _manifest_text_for_plan,
    get_environment_plan_id,
    workflow_to_environment_plan,
)
from bionodulo.nodes.registry import NodeRegistry  # noqa: E402

DEFAULT_TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULT_LOCKS_DIR = REPO_ROOT / "bionodulo" / "environments" / "locks"

LockStatus = Literal["base", "locked", "missing", "invalid"]


@dataclass(frozen=True)
class TemplateLockRecord:
    """One template's deterministic environment-lock audit result."""

    template: str
    environment_id: str
    packages: tuple[str, ...]
    environment_names: tuple[str, ...]
    status: LockStatus
    detail: str = ""


@dataclass(frozen=True)
class TemplateLockReport:
    """Complete sorted result for the official template directory."""

    records: tuple[TemplateLockRecord, ...]

    @property
    def ok(self) -> bool:
        return bool(self.records) and all(record.status in {"base", "locked"} for record in self.records)

    def count(self, status: LockStatus) -> int:
        return sum(record.status == status for record in self.records)


def _workflow_node_types(workflow: dict[str, Any]) -> tuple[str, ...]:
    raw_nodes = workflow.get("nodes", [])
    if isinstance(raw_nodes, dict):
        nodes = list(raw_nodes.values())
    elif isinstance(raw_nodes, list):
        nodes = raw_nodes
    else:
        raise ValueError("workflow nodes must be a list or object")
    node_types: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("workflow nodes must be objects")
        node_type = node.get("type")
        if not isinstance(node_type, str) or not node_type:
            raise ValueError("every workflow node must have a non-empty type")
        node_types.add(node_type)
    return tuple(sorted(node_types))


def _lock_has_linux_64_environments(lock_path: Path, environment_names: tuple[str, ...]) -> bool:
    try:
        payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return False
    if not isinstance(payload, dict):
        return False
    platforms = payload.get("platforms")
    if not isinstance(platforms, list) or not any(
        isinstance(platform, dict) and platform.get("name") == "linux-64"
        for platform in platforms
    ):
        return False
    environments = payload.get("environments")
    if not isinstance(environments, dict):
        return False
    for name in environment_names:
        environment = environments.get(name)
        if not isinstance(environment, dict):
            return False
        packages = environment.get("packages")
        linux_packages = packages.get("linux-64") if isinstance(packages, dict) else None
        if not isinstance(linux_packages, list) or not linux_packages:
            return False
    return isinstance(payload.get("packages"), list) and bool(payload["packages"])


def _bundle_status(
    locks_dir: Path,
    environment_id: str,
    environment_names: tuple[str, ...],
    manifest_text: str,
) -> tuple[LockStatus, str]:
    bundle_dir = locks_dir / environment_id
    manifest_path = bundle_dir / "pixi.toml"
    lock_path = bundle_dir / "pixi.lock"
    manifest_exists = manifest_path.is_file()
    lock_exists = lock_path.is_file()
    if not manifest_exists and not lock_exists:
        return "missing", "expected pixi.toml and pixi.lock"
    missing = [name for name, exists in (("pixi.toml", manifest_exists), ("pixi.lock", lock_exists)) if not exists]
    if missing:
        return "invalid", f"incomplete bundle; missing {', '.join(missing)}"
    try:
        manifest = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "invalid", f"cannot read pixi.toml: {exc}"
    if manifest != manifest_text:
        return "invalid", "pixi.toml does not match the current package constraints"
    if not _lock_has_linux_64_environments(lock_path, environment_names):
        names = ", ".join(environment_names)
        return "invalid", f"pixi.lock has no valid linux-64 environments: {names}"
    return "locked", ""


def audit_template_environment_locks(
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    locks_dir: Path = DEFAULT_LOCKS_DIR,
    registry: Any | None = None,
) -> TemplateLockReport:
    """Return sorted lock coverage without invoking Pixi or external tools."""
    active_registry = registry if registry is not None else NodeRegistry()
    records: list[TemplateLockRecord] = []
    for template_path in sorted(templates_dir.glob("*.json"), key=lambda path: path.name):
        try:
            workflow = json.loads(template_path.read_text(encoding="utf-8"))
            if not isinstance(workflow, dict):
                raise ValueError("workflow root must be an object")
            unknown = tuple(
                node_type
                for node_type in _workflow_node_types(workflow)
                if active_registry.get(node_type) is None
            )
            if unknown:
                records.append(
                    TemplateLockRecord(
                        template=template_path.name,
                        environment_id="",
                        packages=(),
                        environment_names=(),
                        status="invalid",
                        detail=f"unknown node types: {', '.join(unknown)}",
                    )
                )
                continue
            environment_plan = workflow_to_environment_plan(workflow, active_registry)
            packages = tuple(environment_plan.all_packages)
            environment_names = environment_plan.environment_names
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            records.append(
                TemplateLockRecord(
                    template=template_path.name,
                    environment_id="",
                    packages=(),
                    environment_names=(),
                    status="invalid",
                    detail=f"invalid template: {exc}",
                )
            )
            continue

        if not packages:
            records.append(
                TemplateLockRecord(
                    template=template_path.name,
                    environment_id="base",
                    packages=(),
                    environment_names=("default",),
                    status="base",
                )
            )
            continue

        environment_id = get_environment_plan_id(environment_plan)
        status, detail = _bundle_status(
            locks_dir,
            environment_id,
            environment_names,
            _manifest_text_for_plan(environment_plan),
        )
        records.append(
            TemplateLockRecord(
                template=template_path.name,
                environment_id=environment_id,
                packages=packages,
                environment_names=environment_names,
                status=status,
                detail=detail,
            )
        )
    return TemplateLockReport(records=tuple(records))


def format_report(report: TemplateLockReport) -> str:
    """Format a deterministic, actionable human-readable gate result."""
    lines = [f"official template environment locks: {'PASS' if report.ok else 'FAIL'}"]
    if not report.records:
        lines.append("INVALID no JSON workflow templates were found")
    for record in report.records:
        if record.status in {"base", "locked"}:
            continue
        packages = ",".join(record.packages) or "-"
        expected = (
            f"{record.environment_id}/pixi.toml,{record.environment_id}/pixi.lock"
            if record.environment_id
            else "-"
        )
        lines.append(
            f"{record.status.upper()} {record.template} "
            f"environment={record.environment_id or '-'} packages=[{packages}] "
            f"expected=[{expected}] detail={record.detail}"
        )
    lines.append(
        "summary: "
        f"templates={len(report.records)} "
        f"base={report.count('base')} "
        f"locked={report.count('locked')} "
        f"missing={report.count('missing')} "
        f"invalid={report.count('invalid')}"
    )
    if not report.ok:
        lines.append(
            "Generate and review the listed bundles in bionodulo/environments/locks; "
            "this audit does not run pixi lock or install packages."
        )
    return "\n".join(lines)


def _json_payload(report: TemplateLockReport) -> str:
    return json.dumps(
        {
            "ok": report.ok,
            "summary": {
                "templates": len(report.records),
                "base": report.count("base"),
                "locked": report.count("locked"),
                "missing": report.count("missing"),
                "invalid": report.count("invalid"),
            },
            "records": [asdict(record) for record in report.records],
        },
        indent=2,
        sort_keys=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates-dir", type=Path, default=DEFAULT_TEMPLATES_DIR)
    parser.add_argument("--locks-dir", type=Path, default=DEFAULT_LOCKS_DIR)
    parser.add_argument("--json", action="store_true", help="emit stable JSON instead of text")
    args = parser.parse_args(argv)

    report = audit_template_environment_locks(args.templates_dir, args.locks_dir)
    print(_json_payload(report) if args.json else format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
