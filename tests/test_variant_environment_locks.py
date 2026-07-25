from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from bionodulo.environments.manifest import (
    get_environment_plan_id,
    workflow_to_environment_plan,
)
from bionodulo.nodes.registry import NodeRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("template_name", "environment_id"),
    [
        ("variant_calling_pipeline.json", "4997531d441c35bf"),
        ("wgs_variant_pipeline.json", "5789cfdfd03011a4"),
    ],
)
def test_variant_templates_partition_only_manta_into_a_named_environment(
    template_name: str,
    environment_id: str,
) -> None:
    workflow = json.loads((REPO_ROOT / "templates" / template_name).read_text(encoding="utf-8"))
    plan = workflow_to_environment_plan(workflow, NodeRegistry())

    assert get_environment_plan_id(plan) == environment_id
    assert plan.environment_names == ("default", "manta")
    assert plan.packages_for("manta") == ("manta",)
    assert "manta" not in plan.default_packages
    assert {"bcftools", "htslib", "samtools"} <= set(plan.default_packages)


@pytest.mark.parametrize("environment_id", ["4997531d441c35bf", "5789cfdfd03011a4"])
def test_variant_locks_attest_compatible_hts_build_and_manta_python2_island(
    environment_id: str,
) -> None:
    lock = yaml.safe_load(
        (REPO_ROOT / "bionodulo/environments/locks" / environment_id / "pixi.lock").read_text(
            encoding="utf-8"
        )
    )
    environments = lock["environments"]
    default_urls = {
        item["conda"]
        for item in environments["default"]["packages"]["linux-64"]
        if "conda" in item
    }
    manta_urls = {
        item["conda"]
        for item in environments["manta"]["packages"]["linux-64"]
        if "conda" in item
    }

    assert any(url.endswith("/bcftools-1.24-h487d631_0.conda") for url in default_urls)
    assert any(url.endswith("/htslib-1.23.1-h633afcb_0.conda") for url in default_urls)
    assert any(url.endswith("/samtools-1.23.1-ha83d96e_0.conda") for url in default_urls)
    assert any(url.endswith("/manta-1.6.0-py27h9948957_6.tar.bz2") for url in manta_urls)
    assert any("/python-2.7.15-" in url for url in manta_urls)
    assert not any("/manta-" in url for url in default_urls)
    assert not any("/samtools-" in url or "/bcftools-" in url for url in manta_urls)
