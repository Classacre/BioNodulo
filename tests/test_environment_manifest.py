from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import (
    generate_manifest,
    get_env_dir,
    get_env_id,
    is_env_ready,
)
from bionodulo.manager.resolver import resolve_workflow


def test_environment_id_changes_with_effective_package_constraint(monkeypatch) -> None:
    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", ">=1.15")
    old_id = get_env_id(["samtools"])

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "1.23.1")

    assert get_env_id(["samtools"]) != old_id


def test_environment_id_still_normalizes_order_case_and_duplicates() -> None:
    assert get_env_id(["samtools", "bcftools"]) == get_env_id(
        [" BCFTOOLS ", "samtools", "SAMTOOLS"]
    )


def test_resolver_does_not_reuse_ready_environment_from_old_constraint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ToolNode:
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_R_PACKAGES: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
            return {"required": {}, "optional": {}, "hidden": {}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return ToolNode if node_type == "tool" else None

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", ">=1.15")
    old_env_dir = get_env_dir(get_env_id(["samtools"]), tmp_path)
    generate_manifest(old_env_dir, ["samtools"])
    (old_env_dir / ".pixi" / "envs" / "default" / "bin").mkdir(parents=True)
    assert is_env_ready(old_env_dir) is True

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "1.23.1")
    report = resolve_workflow(
        {"nodes": [{"id": "tool_001", "type": "tool"}], "edges": []},
        Registry(),
        tmp_path,
    )
    selected_env_dir = get_env_dir(report.env_id, tmp_path)

    assert report.required_packages == ["samtools"]
    assert selected_env_dir != old_env_dir
    assert report.env_ready is False
