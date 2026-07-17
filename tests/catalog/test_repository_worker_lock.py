from __future__ import annotations

from copy import deepcopy
import tomllib
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from bionodulo.nodes.environment_compiler import pixi_lock_v7


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BOTO3_SPEC = ">=1.43.50,<1.44"
BOTO3_STACK = frozenset(
    {"boto3", "botocore", "jmespath", "python-dateutil", "s3transfer", "six", "urllib3"}
)
ENVIRONMENT_NAMES = ("default", "worker")
RESOLVER_PLATFORMS = ("linux-64", "linux-aarch64")
BOTO3_CONTEXTS = tuple(
    (environment_name, resolver_platform)
    for environment_name in ENVIRONMENT_NAMES
    for resolver_platform in RESOLVER_PLATFORMS
)


def _assert_universal_boto3_stack(lock_content: bytes) -> None:
    context_identities: dict[tuple[str, str], dict[str, tuple[str, str]]] = {}
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            lock_content,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        selected_pypi = {item.name: item for item in selected if item.kind == "pypi"}
        stack = {name: item for name, item in selected_pypi.items() if name in BOTO3_STACK}
        assert stack.keys() == BOTO3_STACK
        assert Version(stack["boto3"].version) in SpecifierSet(BOTO3_SPEC)
        assert "awscrt" not in selected_pypi
        assert all(item.filename.endswith(".whl") for item in stack.values())
        context_identities[(environment_name, resolver_platform)] = {
            name: (item.url, item.sha256) for name, item in stack.items()
        }

    universal_identity = context_identities[BOTO3_CONTEXTS[0]]
    assert context_identities == {
        context: universal_identity for context in BOTO3_CONTEXTS
    }, "boto3 stack URL/SHA identities must match across every lock context"


def _lock_with_worker_jmespath_divergence(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    original = next(package for package in packages if package.get("name") == "jmespath")
    original_url = original["pypi"]
    worker_url = original_url.replace("jmespath-1.1.0-", "jmespath-1.1.1-")
    assert worker_url != original_url

    worker_package = deepcopy(original)
    worker_package.update(pypi=worker_url, version="1.1.1", sha256="f" * 64)
    packages.append(worker_package)
    packages.sort(
        key=lambda package: (
            ("conda", package["conda"]) if "conda" in package else ("pypi", package["pypi"])
        )
    )

    for references in document["environments"]["worker"]["packages"].values():
        worker_reference = next(reference for reference in references if reference.get("pypi") == original_url)
        worker_reference["pypi"] = worker_url

    return yaml.safe_dump(document, sort_keys=False).encode("utf-8")


def test_worker_manifest_declares_bounded_boto3_runtime() -> None:
    manifest = tomllib.loads((REPOSITORY_ROOT / "pixi.toml").read_text(encoding="utf-8"))

    assert manifest["pypi-dependencies"]["boto3"] == BOTO3_SPEC


def test_boto3_stack_names_are_the_exact_transitive_closure() -> None:
    assert BOTO3_STACK == frozenset(
        {"boto3", "botocore", "jmespath", "python-dateutil", "s3transfer", "six", "urllib3"}
    )


def test_boto3_stack_guard_rejects_cross_environment_artifact_divergence() -> None:
    mutated_lock = _lock_with_worker_jmespath_divergence((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    jmespath_identities: dict[tuple[str, str], tuple[str, str]] = {}
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        jmespath = next(item for item in selected if item.kind == "pypi" and item.name == "jmespath")
        jmespath_identities[(environment_name, resolver_platform)] = (jmespath.url, jmespath.sha256)

    assert jmespath_identities[("default", "linux-64")] == jmespath_identities[("default", "linux-aarch64")]
    assert jmespath_identities[("worker", "linux-64")] == jmespath_identities[("worker", "linux-aarch64")]
    assert jmespath_identities[("default", "linux-64")] != jmespath_identities[("worker", "linux-64")]
    with pytest.raises(AssertionError, match="URL/SHA identities must match"):
        _assert_universal_boto3_stack(mutated_lock)


def test_repository_lock_contains_one_universal_boto3_stack() -> None:
    _assert_universal_boto3_stack((REPOSITORY_ROOT / "pixi.lock").read_bytes())
