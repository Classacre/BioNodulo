from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from bionodulo.nodes.environment_compiler import pixi_lock_v7


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BOTO3_SPEC = ">=1.43.50,<1.44"
BOTO3_STACK = frozenset({"boto3", "botocore", "jmespath", "s3transfer", "urllib3"})


def test_worker_manifest_declares_bounded_boto3_runtime() -> None:
    manifest = tomllib.loads((REPOSITORY_ROOT / "pixi.toml").read_text(encoding="utf-8"))

    assert manifest["pypi-dependencies"]["boto3"] == BOTO3_SPEC


@pytest.mark.parametrize("environment_name", ("default", "worker"))
@pytest.mark.parametrize("resolver_platform", ("linux-64", "linux-aarch64"))
def test_repository_lock_contains_bounded_boto3_stack(
    environment_name: str,
    resolver_platform: str,
) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        (REPOSITORY_ROOT / "pixi.lock").read_bytes(),
        environment_name=environment_name,
        resolver_platform=resolver_platform,
    )

    selected_pypi = {item.name: item for item in selected if item.kind == "pypi"}
    assert BOTO3_STACK <= selected_pypi.keys()
    assert Version(selected_pypi["boto3"].version) in SpecifierSet(BOTO3_SPEC)
    assert "awscrt" not in selected_pypi
    assert all(selected_pypi[name].filename.endswith("-py3-none-any.whl") for name in BOTO3_STACK)


@pytest.mark.parametrize("environment_name", ("default", "worker"))
def test_repository_boto3_stack_is_identical_across_platforms(environment_name: str) -> None:
    platform_identities: list[dict[str, tuple[str, str]]] = []
    for resolver_platform in ("linux-64", "linux-aarch64"):
        selected = pixi_lock_v7._validate_pixi_lock(
            (REPOSITORY_ROOT / "pixi.lock").read_bytes(),
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        platform_identities.append(
            {
                item.name: (item.url, item.sha256)
                for item in selected
                if item.kind == "pypi" and item.name in BOTO3_STACK
            }
        )

    assert all(identity.keys() == BOTO3_STACK for identity in platform_identities)
    assert platform_identities[0] == platform_identities[1]
