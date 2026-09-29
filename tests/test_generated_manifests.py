"""Regression tests for the generated-node manifest checker CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_generated_manifests.py"
MANIFESTS = REPO_ROOT / "reports" / "node-expansion"


def _run_checker(manifest_dir: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(CHECKER), str(manifest_dir)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_checker_cli_runs_from_outside_repo_without_pythonpath(tmp_path: Path) -> None:
    result = _run_checker(MANIFESTS, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    checked = re.search(r"checked (\d+) generated nodes against their manifests", result.stdout)
    assert checked is not None
    assert int(checked.group(1)) > 0
    assert "all generated nodes agree with their manifests" in result.stdout


def test_checker_rejects_incomplete_manifest_directory(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "partial-manifests"
    manifest_dir.mkdir()
    (manifest_dir / "csvtk-generated.json").write_text(
        json.dumps({"records": []}), encoding="utf-8"
    )

    result = _run_checker(manifest_dir, tmp_path)

    assert result.returncode != 0
    assert "missing family manifest:" in result.stdout
    assert "seqkit-generated.json" in result.stdout
    assert "no generated nodes were checked" in result.stdout


def test_bgziptabix_wrapper_is_excluded_until_its_contract_is_known() -> None:
    manifest = json.loads((MANIFESTS / "vcflib-generated.json").read_text(encoding="utf-8"))
    record = next(record for record in manifest["records"]
                  if record.get("tool") == "bgziptabix")
    assert record["status"] == "skipped_unsupported_shell_wrapper"
    assert "vcflib_bgziptabix" not in manifest["generated_node_ids"]
    ids = json.loads((REPO_ROOT / "bionodulo/nodes/generated/vcflib_node_ids.json")
                     .read_text(encoding="utf-8"))
    assert "vcflib_bgziptabix" not in ids["node_ids"]
    assert not (REPO_ROOT / "bionodulo/nodes/builtin/vcflib_family/vcflib_bgziptabix.py").exists()


def test_csvtk_version_is_excluded_as_non_data_command() -> None:
    manifest = json.loads((MANIFESTS / "csvtk-generated.json").read_text(encoding="utf-8"))
    record = next(record for record in manifest["records"]
                  if record.get("subcommand") == "version")
    assert record["status"] == "skipped_non_data_command"
    assert "csvtk_version" not in manifest["generated_node_ids"]
    ids = json.loads((REPO_ROOT / "bionodulo/nodes/generated/csvtk_node_ids.json")
                     .read_text(encoding="utf-8"))
    assert "csvtk_version" not in ids["node_ids"]
    assert not (REPO_ROOT / "bionodulo/nodes/builtin/csvtk_family/csvtk_version.py").exists()


def test_generated_nodes_have_source_descriptions_not_help_banners() -> None:
    records = []
    for path in MANIFESTS.glob("*-generated.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        records.extend(record for record in manifest["records"]
                       if record.get("status") == "generated")
    assert len(records) == 373
    for record in records:
        description = record.get("description", record.get("documentation", "")).strip()
        assert description, record["node_id"]
        assert not description.lower().startswith(("usage:", "options:", "version:",
                                                   "warning:", "this is a")), record["node_id"]
    by_id = {record["node_id"]: record for record in records}
    assert by_id["vcflib_vcfallelicprimitives"]["description"].startswith(
        "Realign reference and alternate alleles"
    )
    assert by_id["vcflib_vcfld"]["description"] == "Compute LD"
