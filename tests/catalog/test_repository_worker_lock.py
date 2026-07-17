from __future__ import annotations

from copy import deepcopy
import tomllib
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
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
TARGET_MACHINE = {"linux-64": "x86_64", "linux-aarch64": "aarch64"}
UNAVAILABLE_TARGET_MARKERS = ("platform_release", "platform_version")
ACTIVE_ARM_DEPENDENCY = (
    "boto3-extra>=1 ; python_version == '3.12' and sys_platform == 'linux' "
    "and platform_machine == 'aarch64'"
)


def _package_identity(package: dict[str, object]) -> tuple[str, str]:
    kind = "conda" if "conda" in package else "pypi"
    url = package[kind]
    assert isinstance(url, str)
    return kind, url


def _encode_mutated_lock(document: dict[str, object]) -> bytes:
    packages = document["packages"]
    assert isinstance(packages, list)
    packages.sort(key=_package_identity)

    environments = document["environments"]
    assert isinstance(environments, dict)
    for environment in environments.values():
        for references in environment["packages"].values():
            references.sort(key=_package_identity)
    return yaml.safe_dump(document, sort_keys=False).encode("utf-8")


def _selected_python_version(
    selected: tuple[pixi_lock_v7._NativePackage, ...],
    *,
    resolver_platform: str,
) -> Version:
    python_records = [
        item
        for item in selected
        if item.kind == "conda" and canonicalize_name(item.name) == "python"
    ]
    assert len(python_records) == 1, "selected context must contain exactly one Python runtime"
    python_record = python_records[0]
    assert python_record.subdir == resolver_platform
    assert python_record.build is not None and python_record.build.endswith("_cpython")

    python_version = Version(python_record.version)
    assert len(python_version.release) >= 2
    return python_version


def _marker_environment(python_version: Version, *, resolver_platform: str) -> dict[str, str]:
    return {
        "implementation_name": "cpython",
        "implementation_version": str(python_version),
        "os_name": "posix",
        "platform_machine": TARGET_MACHINE[resolver_platform],
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": str(python_version),
        "platform_python_implementation": "CPython",
        "python_version": ".".join(str(part) for part in python_version.release[:2]),
        "sys_platform": "linux",
        "extra": "",
    }


def _selected_pypi_by_name(
    selected: tuple[pixi_lock_v7._NativePackage, ...],
) -> dict[str, pixi_lock_v7._NativePackage]:
    records = [item for item in selected if item.kind == "pypi"]
    normalized_names = [canonicalize_name(item.name) for item in records]
    assert len(normalized_names) == len(
        set(normalized_names)
    ), "selected lock contains a duplicate normalized PyPI name"
    return dict(zip(normalized_names, records, strict=True))


def _requirement_is_active(requirement: Requirement, marker_environment: dict[str, str]) -> bool:
    if requirement.marker is None:
        return True
    marker_text = str(requirement.marker)
    assert not any(name in marker_text for name in UNAVAILABLE_TARGET_MARKERS), (
        "boto3 dependency marker uses target values unavailable from pixi.lock"
    )
    return requirement.marker.evaluate(environment=marker_environment, context="metadata")


def _active_boto3_dependency_closure(
    selected_pypi: dict[str, pixi_lock_v7._NativePackage],
    *,
    marker_environment: dict[str, str],
    python_version: Version,
) -> frozenset[str]:
    pending = ["boto3"]
    active: set[str] = set()
    while pending:
        name = pending.pop()
        if name in active:
            continue
        package = selected_pypi.get(name)
        assert package is not None, f"active boto3 dependency {name!r} is missing from selected lock"
        active.add(name)
        if package.requires_python is not None:
            requires_python = SpecifierSet(package.requires_python)
            assert python_version in requires_python, (
                f"selected Python {python_version} does not satisfy requires_python "
                f"{requires_python} for {name}"
            )
        for requirement_text in package.requires_dist:
            requirement = Requirement(requirement_text)
            if not _requirement_is_active(requirement, marker_environment):
                continue
            assert requirement.url is None, "active direct-URL requirement cannot be validated without fetching"
            assert not requirement.extras, "active boto3 dependency extras require solver semantics"
            dependency_name = canonicalize_name(requirement.name)
            dependency = selected_pypi.get(dependency_name)
            assert dependency is not None, (
                f"active boto3 dependency {dependency_name!r} is missing from selected lock"
            )
            dependency_version = Version(dependency.version)
            assert not dependency_version.is_prerelease, (
                "active boto3 dependency prerelease requires resolver selection semantics"
            )
            assert dependency_version in requirement.specifier, (
                f"selected {dependency_name} {dependency_version} does not satisfy active requirement "
                f"{requirement.specifier}"
            )
            pending.append(dependency_name)
    return frozenset(active)


def _assert_universal_boto3_stack(lock_content: bytes) -> None:
    context_identities: dict[tuple[str, str], dict[str, tuple[str, str]]] = {}
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            lock_content,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        selected_pypi = _selected_pypi_by_name(selected)
        python_version = _selected_python_version(selected, resolver_platform=resolver_platform)
        closure = _active_boto3_dependency_closure(
            selected_pypi,
            marker_environment=_marker_environment(
                python_version,
                resolver_platform=resolver_platform,
            ),
            python_version=python_version,
        )
        assert closure == BOTO3_STACK, "active boto3 dependency closure must be exactly seven packages"
        stack = {name: selected_pypi[name] for name in sorted(closure)}
        assert Version(stack["boto3"].version) in SpecifierSet(BOTO3_SPEC)
        assert "awscrt" not in selected_pypi
        assert all(item.filename.endswith("-none-any.whl") for item in stack.values()), (
            "boto3 stack artifacts must be architecture-neutral wheels ending in -none-any.whl"
        )
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

    for references in document["environments"]["worker"]["packages"].values():
        worker_reference = next(reference for reference in references if reference.get("pypi") == original_url)
        worker_reference["pypi"] = worker_url

    return _encode_mutated_lock(document)


def _lock_with_platform_specific_jmespath_wheel(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    jmespath = next(package for package in packages if package.get("name") == "jmespath")
    original_url = jmespath["pypi"]
    platform_url = original_url.replace(
        "-py3-none-any.whl",
        "-py3-none-manylinux_2_17_x86_64.whl",
    )
    assert platform_url != original_url
    jmespath.update(pypi=platform_url, sha256="e" * 64)

    for environment in document["environments"].values():
        for references in environment["packages"].values():
            reference = next(item for item in references if item.get("pypi") == original_url)
            reference["pypi"] = platform_url
    return _encode_mutated_lock(document)


def _lock_with_duplicate_jmespath_records(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    original = next(package for package in packages if package.get("name") == "jmespath")
    duplicate = deepcopy(original)
    duplicate_url = duplicate["pypi"].replace("jmespath-1.1.0-", "jmespath-1.1.1-")
    duplicate.update(pypi=duplicate_url, version="1.1.1", sha256="d" * 64)
    packages.append(duplicate)

    for environment in document["environments"].values():
        for references in environment["packages"].values():
            references.append({"pypi": duplicate_url})
    return _encode_mutated_lock(document)


def _lock_with_eighth_active_boto3_dependency(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    boto3 = next(package for package in packages if package.get("name") == "boto3")
    boto3["requires_dist"].append(ACTIVE_ARM_DEPENDENCY)

    dependency_url = (
        "https://files.pythonhosted.org/packages/00/00/"
        "0000000000000000000000000000000000000000000000000000000000000000/"
        "boto3_extra-1.0.0-py3-none-any.whl"
    )
    packages.append(
        {
            "pypi": dependency_url,
            "name": "boto3-extra",
            "version": "1.0.0",
            "sha256": "c" * 64,
            "requires_python": ">=3.12",
        }
    )
    for environment in document["environments"].values():
        environment["packages"]["linux-aarch64"].append({"pypi": dependency_url})
    return _encode_mutated_lock(document)


def _lock_with_incompatible_botocore_version(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    botocore = next(package for package in packages if package.get("name") == "botocore")
    original_url = botocore["pypi"]
    incompatible_url = original_url.replace("botocore-1.43.50-", "botocore-1.44.99-")
    assert incompatible_url != original_url
    botocore.update(pypi=incompatible_url, version="1.44.99", sha256="b" * 64)

    for environment in document["environments"].values():
        for references in environment["packages"].values():
            reference = next(item for item in references if item.get("pypi") == original_url)
            reference["pypi"] = incompatible_url
    return _encode_mutated_lock(document)


def _lock_with_incompatible_botocore_python(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    botocore = next(package for package in document["packages"] if package.get("name") == "botocore")
    botocore["requires_python"] = ">=99"
    return _encode_mutated_lock(document)


def _lock_with_direct_url_botocore_requirement(lock_content: bytes) -> bytes:
    document = yaml.safe_load(lock_content)
    packages = document["packages"]
    botocore = next(package for package in packages if package.get("name") == "botocore")
    boto3 = next(package for package in packages if package.get("name") == "boto3")
    requirements = boto3["requires_dist"]
    requirement_index = next(
        index
        for index, requirement in enumerate(requirements)
        if requirement.startswith("botocore>=") and "extra" not in requirement
    )
    requirements[requirement_index] = f"botocore @ {botocore['pypi']}"
    return _encode_mutated_lock(document)


def test_worker_manifest_declares_bounded_boto3_runtime() -> None:
    manifest = tomllib.loads((REPOSITORY_ROOT / "pixi.toml").read_text(encoding="utf-8"))

    assert manifest["pypi-dependencies"]["boto3"] == BOTO3_SPEC


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


def test_boto3_stack_guard_rejects_platform_specific_wheel() -> None:
    mutated_lock = _lock_with_platform_specific_jmespath_wheel((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        jmespath = next(item for item in selected if item.kind == "pypi" and item.name == "jmespath")
        assert jmespath.filename.endswith("-none-manylinux_2_17_x86_64.whl")

    with pytest.raises(AssertionError, match="architecture-neutral wheels"):
        _assert_universal_boto3_stack(mutated_lock)


def test_boto3_stack_guard_rejects_duplicate_normalized_pypi_name() -> None:
    mutated_lock = _lock_with_duplicate_jmespath_records((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        selected_names = [canonicalize_name(item.name) for item in selected if item.kind == "pypi"]
        assert selected_names.count("jmespath") == 2

    with pytest.raises(AssertionError, match="duplicate normalized PyPI name"):
        _assert_universal_boto3_stack(mutated_lock)


def test_boto3_stack_guard_rejects_eighth_active_dependency() -> None:
    mutated_lock = _lock_with_eighth_active_boto3_dependency((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        selected_names = {canonicalize_name(item.name) for item in selected if item.kind == "pypi"}
        assert ("boto3-extra" in selected_names) is (resolver_platform == "linux-aarch64")

    with pytest.raises(AssertionError, match="active boto3 dependency closure"):
        _assert_universal_boto3_stack(mutated_lock)


def test_boto3_stack_guard_rejects_incompatible_active_dependency_version() -> None:
    mutated_lock = _lock_with_incompatible_botocore_version((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        botocore = next(item for item in selected if item.kind == "pypi" and item.name == "botocore")
        assert botocore.version == "1.44.99"

    with pytest.raises(AssertionError, match="does not satisfy active requirement"):
        _assert_universal_boto3_stack(mutated_lock)


def test_boto3_stack_guard_rejects_incompatible_requires_python() -> None:
    mutated_lock = _lock_with_incompatible_botocore_python((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        botocore = next(item for item in selected if item.kind == "pypi" and item.name == "botocore")
        assert botocore.requires_python == ">=99"

    with pytest.raises(AssertionError, match="does not satisfy requires_python"):
        _assert_universal_boto3_stack(mutated_lock)


def test_boto3_stack_guard_fails_closed_on_active_direct_url_requirement() -> None:
    mutated_lock = _lock_with_direct_url_botocore_requirement((REPOSITORY_ROOT / "pixi.lock").read_bytes())
    for environment_name, resolver_platform in BOTO3_CONTEXTS:
        selected = pixi_lock_v7._validate_pixi_lock(
            mutated_lock,
            environment_name=environment_name,
            resolver_platform=resolver_platform,
        )
        boto3 = next(item for item in selected if item.kind == "pypi" and item.name == "boto3")
        assert any(Requirement(requirement).url is not None for requirement in boto3.requires_dist)

    with pytest.raises(AssertionError, match="active direct-URL requirement"):
        _assert_universal_boto3_stack(mutated_lock)


def test_repository_lock_contains_one_universal_boto3_stack() -> None:
    _assert_universal_boto3_stack((REPOSITORY_ROOT / "pixi.lock").read_bytes())
