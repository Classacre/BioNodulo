from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

import yaml

from bionodulo.execution.catalog_canary import (
    SAMTOOLS_FIRST_WAVE_ENVIRONMENT_ID,
    SAMTOOLS_FIRST_WAVE_LOCK_SHA256,
    SAMTOOLS_FIRST_WAVE_MANIFEST_SHA256,
    SAMTOOLS_FIRST_WAVE_PACKAGE_SHA256,
)


def test_canary_environment_identity_is_the_minimal_samtools_plan() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    root = (
        repository_root
        / "bionodulo"
        / "environments"
        / "locks"
        / SAMTOOLS_FIRST_WAVE_ENVIRONMENT_ID
    )
    manifest_bytes = (root / "pixi.toml").read_bytes()
    lock_bytes = (root / "pixi.lock").read_bytes()

    assert "sha256:" + hashlib.sha256(manifest_bytes).hexdigest() == (
        SAMTOOLS_FIRST_WAVE_MANIFEST_SHA256
    )
    assert "sha256:" + hashlib.sha256(lock_bytes).hexdigest() == (
        SAMTOOLS_FIRST_WAVE_LOCK_SHA256
    )
    manifest = tomllib.loads(manifest_bytes.decode("utf-8"))
    assert manifest["workspace"]["platforms"] == ["linux-64"]
    assert manifest["dependencies"] == {"samtools": "1.23.1"}

    lock = yaml.safe_load(lock_bytes)
    packages = lock["packages"]
    conda_urls = [record["conda"] for record in packages if "conda" in record]
    samtools = next(url for url in conda_urls if "/samtools-1.23.1-" in url)
    samtools_record = next(record for record in packages if record.get("conda") == samtools)
    assert "sha256:" + samtools_record["sha256"] == SAMTOOLS_FIRST_WAVE_PACKAGE_SHA256
    assert all("chopper" not in url for url in conda_urls)
    assert all("nanoplot" not in url for url in conda_urls)
    assert all("ont-modkit" not in url for url in conda_urls)

    dockerignore = (repository_root / ".dockerignore").read_text(encoding="utf-8")
    assert "!bionodulo/environments/" in dockerignore
    assert "!bionodulo/environments/**" in dockerignore
