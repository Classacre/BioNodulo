from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import pytest
import yaml  # type: ignore[import-untyped]
from packaging.utils import canonicalize_name, parse_wheel_filename
from pydantic import ValidationError

from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.environment_compiler import compiler, pixi_identity, pixi_lock_v7


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "d" * 64
PYPI_DEPENDENCY = "typing-extensions>=4.0 ; python_version < '3.11'"


def conda_record(**updates: object) -> dict[str, object]:
    filename = "samtools-1.20-h50ea8bc_0.conda"
    record: dict[str, object] = {
        "name": "samtools",
        "version": "1.20",
        "build": "h50ea8bc_0",
        "build_number": 0,
        "size_bytes": 1_234_567,
        "kind": "conda",
        "source": "https://conda.anaconda.org/bioconda",
        "license": "MIT",
        "license_family": "MIT",
        "is_explicit": True,
        "md5": "c" * 32,
        "sha256": SHA_A,
        "arch": "x86_64",
        "platform": "linux",
        "subdir": "linux-64",
        "timestamp": 1_716_000_000_000,
        "noarch": None,
        "file_name": filename,
        "url": f"https://conda.anaconda.org/bioconda/linux-64/{filename}",
        "index_url": None,
        "requested_spec": "samtools ==1.20",
        "constrains": [],
        "depends": ["htslib >=1.20,<1.21.0a0"],
        "track_features": [],
    }
    record.update(updates)
    return record


def pypi_record(**updates: object) -> dict[str, object]:
    filename = "numpy-1.26.4-cp311-cp311-manylinux_2_17_x86_64.whl"
    record: dict[str, object] = {
        "name": "numpy",
        "version": "1.26.4",
        "build": None,
        "build_number": None,
        "size_bytes": 18_261_024,
        "kind": "pypi",
        "source": "https://pypi.org/simple",
        "license": None,
        "license_family": None,
        "is_explicit": True,
        "md5": None,
        "sha256": SHA_B,
        "arch": None,
        "platform": None,
        "subdir": None,
        "timestamp": None,
        "noarch": None,
        "file_name": None,
        "url": f"https://files.pythonhosted.org/packages/{filename}",
        "index_url": "https://pypi.org/simple",
        "requested_spec": "numpy==1.26.4",
        "constrains": [],
        "depends": [PYPI_DEPENDENCY],
        "track_features": [],
    }
    record.update(updates)
    return record


def python_record(*, version: str = "3.11.9", **updates: object) -> dict[str, object]:
    filename = f"python-{version}-h0_cpython.conda"
    return conda_record(
        name="python",
        version=version,
        build="h0_cpython",
        build_number=0,
        size_bytes=31_000_000,
        source="https://conda.anaconda.org/conda-forge",
        license="Python-2.0",
        license_family=None,
        md5="e" * 32,
        sha256=SHA_C,
        file_name=filename,
        url=f"https://conda.anaconda.org/conda-forge/linux-64/{filename}",
        requested_spec=">=3.11,<3.12",
        constrains=["python_abi 3.11.* *_cp311"],
        depends=[],
        **updates,
    )


def encoded(*records: dict[str, object]) -> bytes:
    ordered = tuple(sorted(records, key=lambda record: str(record["name"])))
    return json.dumps(ordered, separators=(",", ":")).encode("utf-8")


def resolver_identity() -> ResolverIdentity:
    return ResolverIdentity(
        name="pixi",
        version="0.68.1",
        config_digest="sha256:" + "a" * 64,
    )


def compile_captured_platform_lock(
    pixi_list_content: bytes,
    pixi_lock_content: bytes,
    *,
    environment_name: str,
    platform: ExecutionPlatform,
) -> PlatformLock:
    return pixi_lock_v7._compile_captured_platform_lock(
        pixi_list_content=pixi_list_content,
        pixi_lock_content=pixi_lock_content,
        resolver=resolver_identity(),
        environment_name=environment_name,
        target_platform=platform,
    )


def write_synthetic_pixi(path: Path, content: bytes = b"synthetic pixi executable") -> Path:
    path.write_bytes(content)
    path.chmod(0o755)
    return path


def synthetic_distribution_map(
    content: bytes,
    *,
    expected_binary_sha256: str | None = None,
) -> dict[ExecutionPlatform, pixi_identity.PixiDistribution]:
    digest = expected_binary_sha256 or "sha256:" + hashlib.sha256(content).hexdigest()
    return {
        ExecutionPlatform.LINUX_AMD64: pixi_identity.PixiDistribution(
            filename="pixi-synthetic.tar.gz",
            url="https://example.org/pixi-synthetic.tar.gz",
            archive_sha256="sha256:" + "a" * 64,
            binary_sha256=digest,
        )
    }


def lockfile(
    environment_name: str = "alignment-tools",
    *,
    version: object = 7,
    resolver_platform: str = "linux-64",
    package_references: tuple[tuple[str, str], ...] | None = None,
    native_sha256: str | None = None,
    include_platforms: bool = True,
    include_packages: bool = True,
    duplicate_top_package: bool = False,
) -> bytes:
    references = package_references or (("conda", str(conda_record()["url"])),)
    selected = "".join(f"      - {kind}: {json.dumps(url)}\n" for kind, url in references)
    platform_section = f"platforms:\n- name: {resolver_platform}\n" if include_platforms else ""
    indexes = "    indexes:\n    - https://pypi.org/simple\n" if any(kind == "pypi" for kind, _ in references) else ""
    top_level = "".join(
        _native_conda_package(url, sha256=native_sha256)
        if kind == "conda"
        else _native_pypi_package(url, sha256=native_sha256)
        for kind, url in references
    )
    if duplicate_top_package:
        top_level += _native_conda_package(references[0][1], sha256=native_sha256)
    packages_section = f"packages:\n{top_level}" if include_packages else ""
    return (
        f"version: {json.dumps(version)}\n{platform_section}environments:\n  {environment_name}:\n"
        "    channels:\n    - url: https://conda.anaconda.org/bioconda/\n"
        f"{indexes}    packages:\n      {resolver_platform}:\n{selected}{packages_section}"
    ).encode("utf-8")


def _native_conda_package(url: str, *, sha256: str | None = None) -> str:
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    listed = python_record() if filename.startswith("python-") else conda_record()
    depends = tuple(str(dependency) for dependency in cast(list[object], listed["depends"]))
    constrains = tuple(str(constraint) for constraint in cast(list[object], listed["constrains"]))
    depends_yaml = "  depends: []\n" if not depends else "  depends:\n" + "".join(f"  - {item}\n" for item in depends)
    constrains_yaml = "" if not constrains else "  constrains:\n" + "".join(f"  - {item}\n" for item in constrains)
    license_family_yaml = "" if listed["license_family"] is None else f"  license_family: {listed['license_family']}\n"
    return (
        f"- conda: {json.dumps(url)}\n"
        f"  sha256: {sha256 or listed['sha256']}\n"
        f"  md5: {listed['md5']}\n"
        f"{depends_yaml}"
        f"{constrains_yaml}"
        f"  license: {listed['license']}\n"
        f"{license_family_yaml}"
        "  purls: []\n"
        "  run_exports: {}\n"
        f"  size: {listed['size_bytes']}\n"
        f"  timestamp: {listed['timestamp']}\n"
    )


def _native_pypi_package(url: str, *, sha256: str | None = None) -> str:
    listed = pypi_record()
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    name, version, _, _ = parse_wheel_filename(filename)
    return (
        f"- pypi: {json.dumps(url)}\n"
        f"  name: {canonicalize_name(str(name))}\n"
        f"  version: {version}\n"
        f"  sha256: {sha256 or listed['sha256']}\n"
        "  requires_dist:\n"
        f"  - {PYPI_DEPENDENCY}\n"
        "  requires_python: '>=3.9'\n"
    )


_CONDA_V7_FIELDS = (
    "conda",
    "name",
    "version",
    "build",
    "build_number",
    "subdir",
    "noarch",
    "variants",
    "sha256",
    "md5",
    "legacy_bz2_md5",
    "depends",
    "constrains",
    "extra_depends",
    "channel",
    "features",
    "flags",
    "track_features",
    "file_name",
    "license",
    "license_family",
    "purls",
    "run_exports",
    "size",
    "legacy_bz2_size",
    "timestamp",
    "python_site_packages_path",
)


def lockfile_with_conda_field(field: str, value: object, *, content: bytes | None = None) -> bytes:
    document = yaml.safe_load(lockfile() if content is None else content)
    package = document["packages"][0]
    document["packages"][0] = {
        key: value if key == field else package[key] for key in _CONDA_V7_FIELDS if key == field or key in package
    }
    return yaml.safe_dump(document, sort_keys=False).encode("utf-8")


_PYPI_V7_FIELDS = (
    "pypi",
    "name",
    "version",
    "md5",
    "sha256",
    "index",
    "requires_dist",
    "requires_python",
    "build_packages",
    "host_packages",
)


def lockfile_with_pypi_field(field: str, value: object) -> bytes:
    python = python_record()
    wheel = pypi_record()
    document = yaml.safe_load(
        lockfile(
            package_references=(
                ("conda", str(python["url"])),
                ("pypi", str(wheel["url"])),
            )
        )
    )
    package = document["packages"][1]
    document["packages"][1] = {
        key: value if key == field else package[key] for key in _PYPI_V7_FIELDS if key == field or key in package
    }
    return yaml.safe_dump(document, sort_keys=False).encode("utf-8")


def test_decoder_accepts_repository_lock_emitted_by_pinned_pixi_0681() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    content = (repository_root / "pixi.lock").read_bytes()

    selected = pixi_lock_v7._validate_pixi_lock(
        content,
        environment_name="default",
        resolver_platform="linux-64",
    )

    assert len(selected) > 100
    assert any(package.kind == "conda" and package.name == "python" for package in selected)
    assert any(package.kind == "pypi" and package.name == "numpy" for package in selected)


def test_lock_v7_requires_exact_bytes() -> None:
    with pytest.raises(TypeError, match="exact .*bytes"):
        pixi_lock_v7._validate_pixi_lock(
            cast(bytes, bytearray(lockfile())),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    "content",
    (
        b"",
        b"#" + b"x" * (8 * 1024 * 1024),
    ),
)
def test_lock_v7_requires_bounded_bytes(content: bytes) -> None:
    with pytest.raises(ValueError, match="size|bytes"):
        pixi_lock_v7._validate_pixi_lock(
            content,
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_decoder_accepts_realistic_full_conda_and_pypi_records() -> None:
    records = pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(), pypi_record()))

    assert tuple(type(record) for record in records) == (
        pixi_lock_v7.PixiPypiListRecord,
        pixi_lock_v7.PixiCondaListRecord,
    )
    assert len(conda_record()) == 24
    assert len(pypi_record()) == 24
    assert records[0].source == "https://pypi.org/simple"
    assert records[0].file_name is None
    assert records[0].license is None
    assert records[1].source == "https://conda.anaconda.org/bioconda"


def test_decoder_rejects_list_records_outside_pixi_name_order() -> None:
    content = json.dumps((conda_record(), pypi_record()), separators=(",", ":")).encode("utf-8")

    with pytest.raises(ValueError, match="name order|sorted by name"):
        pixi_lock_v7.decode_pixi_list_json(content)


@pytest.mark.parametrize("field", ("kind", "index_url", "track_features"))
def test_decoder_rejects_missing_required_abi_fields(field: str) -> None:
    record = conda_record()
    record.pop(field)

    with pytest.raises(ValidationError, match=field):
        pixi_lock_v7.decode_pixi_list_json(encoded(record))


def test_decoder_rejects_unknown_abi_fields() -> None:
    with pytest.raises(ValidationError, match="unknown_field"):
        pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(unknown_field=True)))


@pytest.mark.parametrize("kind", ("conda-forge", "wheel", "", None))
def test_kind_is_the_only_strict_conda_pypi_discriminator(kind: object) -> None:
    with pytest.raises(ValidationError, match="kind"):
        pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(kind=kind)))


def test_decoder_requires_null_pypi_file_name_as_emitted_by_pixi() -> None:
    with pytest.raises(ValidationError, match="file_name"):
        pixi_lock_v7.decode_pixi_list_json(encoded(pypi_record(file_name="numpy.whl")))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("license", "MIT"),
        ("license_family", "MIT"),
        ("arch", "x86_64"),
        ("platform", "linux"),
        ("subdir", "linux-64"),
        ("timestamp", 1_716_000_000_000),
        ("noarch", "python"),
        ("constrains", ["python >=3.11"]),
        ("track_features", ["cuda"]),
    ),
)
def test_decoder_rejects_impossible_pypi_serializer_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match=field):
        pixi_lock_v7.decode_pixi_list_json(encoded(pypi_record(**{field: value})))


def test_decoder_rejects_duplicate_json_object_keys() -> None:
    content = encoded(conda_record()).replace(
        b'"name":"samtools"',
        b'"name":"other","name":"samtools"',
        1,
    )

    with pytest.raises(ValueError, match="duplicate JSON key: name"):
        pixi_lock_v7.decode_pixi_list_json(content)


def test_decoder_accepts_missing_optional_sha_but_admission_rejects_it() -> None:
    records = pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(sha256=None)))

    assert records[0].sha256 is None
    with pytest.raises(ValueError, match="sha256"):
        pixi_lock_v7.admit_pixi_records(
            records,
            resolver=resolver_identity(),
            environment_name="alignment-tools",
            target_platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize("digest", ("sha256:" + SHA_A, "A" * 64, "a" * 63, "g" * 64))
def test_decoder_rejects_non_pixiesque_sha256_text(digest: str) -> None:
    with pytest.raises(ValidationError, match="sha256"):
        pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(sha256=digest)))


def test_admission_builds_strict_sorted_platform_lock() -> None:
    records = pixi_lock_v7.decode_pixi_list_json(encoded(conda_record(), python_record(), pypi_record()))

    admitted = pixi_lock_v7.admit_pixi_records(
        reversed(records),
        resolver=resolver_identity(),
        environment_name="alignment-tools",
        target_platform=ExecutionPlatform.LINUX_AMD64,
        native_lock_sha256="sha256:" + SHA_A,
    )

    assert admitted.environment_name == "alignment-tools"
    assert admitted.resolver.name == "pixi"
    assert admitted.resolver.version == "0.68.1"
    assert admitted.resolver_platform == "linux-64"
    assert tuple(artifact.name for artifact in admitted.artifacts) == ("numpy", "python", "samtools")
    assert tuple(artifact.kind for artifact in admitted.artifacts) == ("pypi", "conda", "conda")
    assert admitted.artifacts[0].filename.endswith(".whl")


def test_pypi_admission_normalizes_pixis_dist_info_package_name() -> None:
    filename = "scikit_learn-1.4.2-py3-none-any.whl"
    records = pixi_lock_v7.decode_pixi_list_json(
        encoded(
            python_record(),
            pypi_record(
                name="scikit_learn",
                version="1.4.2",
                url=f"https://files.pythonhosted.org/packages/{filename}",
            ),
        )
    )

    admitted = pixi_lock_v7.admit_pixi_records(
        records,
        resolver=resolver_identity(),
        environment_name="python-analysis",
        target_platform=ExecutionPlatform.LINUX_AMD64,
        native_lock_sha256="sha256:" + SHA_A,
    )

    assert records[1].name == "scikit_learn"
    assert next(artifact for artifact in admitted.artifacts if artifact.kind == "pypi").name == "scikit-learn"


@pytest.mark.parametrize(
    "record",
    (
        conda_record(file_name="samtools-1.20-h50ea8bc_0.zip", url="https://example.org/samtools-1.20-h50ea8bc_0.zip"),
        pypi_record(url="https://files.pythonhosted.org/packages/numpy-1.26.4.tar.gz"),
        pypi_record(url="file:///tmp/numpy-1.26.4-py3-none-any.whl"),
        pypi_record(is_editable=True),
    ),
)
def test_admission_rejects_nonbinary_or_mutable_records(record: dict[str, object]) -> None:
    records = pixi_lock_v7.decode_pixi_list_json(encoded(record))

    with pytest.raises(ValueError):
        pixi_lock_v7.admit_pixi_records(
            records,
            resolver=resolver_identity(),
            environment_name="alignment-tools",
            target_platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://files.pythonhosted.org/packages/pandas-1.26.4-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/numpy-1.25.0-py3-none-any.whl",
    ),
)
def test_admission_rejects_pypi_url_name_or_version_disagreement(url: str) -> None:
    records = pixi_lock_v7.decode_pixi_list_json(encoded(pypi_record(url=url)))

    with pytest.raises(ValueError, match="name|version"):
        pixi_lock_v7.admit_pixi_records(
            records,
            resolver=resolver_identity(),
            environment_name="alignment-tools",
            target_platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize("version", (6, 8, "7", True, None))
def test_compiler_independently_requires_pixi_lock_format_seven(version: object) -> None:
    with pytest.raises(ValueError, match="version 7"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            lockfile(version=version),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


@pytest.mark.parametrize(
    "content",
    (
        lockfile(include_platforms=False),
        lockfile(include_packages=False),
        b"version: 7\nplatforms:\n- name: linux-64\npackages: []\n",
    ),
)
def test_compiler_rejects_incomplete_v7_top_level_shape(content: bytes) -> None:
    with pytest.raises(ValueError, match="top-level|platforms|environments|packages"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            content,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_unknown_v7_fields_and_noncanonical_root_order() -> None:
    unknown = lockfile() + b"unknown: true\n"
    valid = lockfile()
    reordered = valid.replace(b"version: 7\nplatforms:\n", b"platforms:\n", 1)
    reordered += b"version: 7\n"

    with pytest.raises(ValueError, match="unknown|top-level"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            unknown,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="canonical|order"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            reordered,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_v7_environment_indexes_preserve_semantic_upstream_order() -> None:
    document = yaml.safe_load(lockfile())
    environment = document["environments"]["alignment-tools"]
    document["environments"]["alignment-tools"] = {
        "channels": environment["channels"],
        "indexes": ["https://z.example/simple", "https://a.example/simple"],
        "packages": environment["packages"],
    }
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    selected = pixi_lock_v7._validate_pixi_lock(
        content,
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].name == "samtools"


@pytest.mark.parametrize(
    "index",
    (
        "https://user@packages.example.org/simple",
        "https://packages.example.org/simple?token=secret",
    ),
)
def test_v7_environment_indexes_reject_noncanonical_https_urls(index: str) -> None:
    document = yaml.safe_load(lockfile())
    environment = document["environments"]["alignment-tools"]
    document["environments"]["alignment-tools"] = {
        "channels": environment["channels"],
        "indexes": [index],
        "packages": environment["packages"],
    }
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="index"):
        pixi_lock_v7._validate_pixi_lock(
            content,
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://user@conda.example.org/channel/",
        "https://conda.example.org/channel/?token=secret",
    ),
)
def test_v7_environment_channels_reject_noncanonical_https_urls(url: str) -> None:
    document = yaml.safe_load(lockfile())
    document["environments"]["alignment-tools"]["channels"][0]["url"] = url
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="channel"):
        pixi_lock_v7._validate_pixi_lock(
            content,
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    ("content", "message"),
    (
        (b"version: !!int 7\nplatforms: []\nenvironments: {}\npackages: []\n", "tag"),
        (b"version: 7\nplatforms: &platforms []\nenvironments: {}\npackages: []\n", "anchor"),
        (
            b"version: 7\nplatforms: &platforms []\nenvironments: {}\npackages: *platforms\n",
            "alias|anchor",
        ),
        (
            b"version: 7\nplatforms: []\nenvironments:\n  default:\n    <<: {}\n"
            b"    channels: []\n    packages: {}\npackages: []\n",
            "merge",
        ),
        (
            lockfile().replace(b"version: 7\n", b"version: 7\nversion: 7\n", 1),
            "duplicate",
        ),
    ),
)
def test_compiler_rejects_yaml_graph_features_and_duplicate_keys(content: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        compile_captured_platform_lock(
            encoded(conda_record()),
            content,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


@pytest.mark.parametrize(
    "value",
    (
        None,
        {},
        [],
        1,
        True,
        "A" * 32,
        "a" * 31,
        "a" * 33,
    ),
)
def test_v7_legacy_bz2_md5_rejects_values_outside_optional_lowercase_md5(value: object) -> None:
    with pytest.raises(ValueError, match="legacy_bz2_md5"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("legacy_bz2_md5", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_legacy_bz2_md5_is_retained_on_native_package() -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("legacy_bz2_md5", "f" * 32),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].legacy_bz2_md5 == "f" * 32


@pytest.mark.parametrize("value", (None, {}, [], True, -1, 1.5, "1", 2**64))
def test_v7_legacy_bz2_size_rejects_values_outside_optional_u64(value: object) -> None:
    with pytest.raises(ValueError, match="legacy_bz2_size"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("legacy_bz2_size", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", (0, 2**64 - 1))
def test_v7_legacy_bz2_size_is_retained_on_native_package(value: int) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("legacy_bz2_size", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].legacy_bz2_size == value


@pytest.mark.parametrize("value", (None, {}, [], 1, True, "f" * 257, "feature\nvalue"))
def test_v7_features_rejects_values_outside_optional_bounded_string(value: object) -> None:
    with pytest.raises(ValueError, match="features"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("features", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", ("", "mkl"))
def test_v7_features_is_retained_on_native_package(value: str) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("features", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].features == value


@pytest.mark.parametrize("value", (None, {}, [], 1, True, "p" * 1025, "lib\nsite-packages"))
def test_v7_python_site_packages_path_rejects_values_outside_bounded_string(value: object) -> None:
    with pytest.raises(ValueError, match="python_site_packages_path"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("python_site_packages_path", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", ("", "lib/python3.11/site-packages"))
def test_v7_python_site_packages_path_is_retained_on_native_package(value: str) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("python_site_packages_path", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].python_site_packages_path == value


@pytest.mark.parametrize("value", ({}, {"python": "3.11"}))
def test_v7_binary_conda_package_rejects_source_variants_field(value: object) -> None:
    with pytest.raises(ValueError, match="variants|binary"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("variants", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("field", ("build_packages", "host_packages"))
def test_v7_pypi_wheel_rejects_source_selector_fields_even_when_empty(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_pypi_field(field, []),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_conda_timestamp_accepts_signed_upstream_integer() -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("timestamp", -1),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].timestamp == -1


@pytest.mark.parametrize("value", (None, True, 1.5, "1", -(2**63) - 1, 2**63))
def test_v7_conda_timestamp_rejects_values_outside_signed_i64(value: object) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("timestamp", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_explicit_null_channel_overrides_url_derived_channel() -> None:
    compiled = compile_captured_platform_lock(
        encoded(conda_record(source=None)),
        lockfile_with_conda_field("channel", None),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].name == "samtools"


@pytest.mark.parametrize(
    "value",
    (
        {},
        [],
        1,
        True,
        "http://packages.example.org/channel",
        "https://user@packages.example.org/channel",
        "https://packages.example.org/channel?query=1",
        "https://packages.example.org/channel/",
    ),
)
def test_v7_channel_rejects_values_outside_canonical_optional_https_url(value: object) -> None:
    with pytest.raises(ValueError, match="channel"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("channel", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_extra_depends_retains_sorted_map_and_ordered_vectors() -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field(
            "extra_depends",
            {"feature-a": ["zlib >=1.3", "openssl >=3"], "feature-b": []},
        ),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].extra_depends == (
        ("feature-a", ("zlib >=1.3", "openssl >=3")),
        ("feature-b", ()),
    )


@pytest.mark.parametrize(
    "value",
    (
        None,
        {},
        [],
        {"feature": "zlib"},
        {"feature": [1]},
        {"z": [], "a": []},
    ),
)
def test_v7_extra_depends_rejects_values_outside_canonical_btree_map(value: object) -> None:
    with pytest.raises(ValueError, match="extra_depends"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("extra_depends", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ({}, ()),
        (
            {"weak": ["zlib >=1.3"], "noarch": []},
            (("weak", ("zlib >=1.3",)), ("noarch", ())),
        ),
    ),
)
def test_v7_run_exports_retains_known_empty_or_ordered_mapping(
    value: object,
    expected: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("run_exports", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].run_exports == expected


@pytest.mark.parametrize(
    "value",
    (None, [], {"weak": "zlib"}, {"unknown": []}, {"strong": [], "weak": []}),
)
def test_v7_run_exports_rejects_values_outside_exact_upstream_mapping(value: object) -> None:
    with pytest.raises(ValueError, match="run_exports"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("run_exports", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ([], ()),
        (
            ["pkg:conda/samtools@1.20?channel=bioconda"],
            ("pkg:conda/samtools@1.20?channel=bioconda",),
        ),
    ),
)
def test_v7_purls_retains_optional_sorted_package_url_set(
    value: object,
    expected: tuple[str, ...],
) -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("purls", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].purls == expected


@pytest.mark.parametrize(
    "value",
    (
        None,
        {},
        [1],
        ["not-a-purl"],
        ["pkg:conda/a", "pkg:conda/a"],
        ["pkg:conda/z", "pkg:conda/a"],
    ),
)
def test_v7_purls_rejects_values_outside_canonical_btree_set(value: object) -> None:
    with pytest.raises(ValueError, match="purls"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("purls", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_flags_retains_ordered_upstream_vector() -> None:
    selected = pixi_lock_v7._validate_pixi_lock(
        lockfile_with_conda_field("flags", ["deprecated", "revoked"]),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].flags == ("deprecated", "revoked")


@pytest.mark.parametrize("value", (None, {}, "deprecated", [], [1], ["flag\nvalue"]))
def test_v7_flags_rejects_values_outside_nonempty_ordered_string_vector(value: object) -> None:
    with pytest.raises(ValueError, match="flags"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("flags", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    "field",
    ("name", "version", "build", "subdir", "file_name", "license", "license_family"),
)
def test_v7_conda_ordinary_optional_fields_reject_explicit_null(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field(field, None),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("field", ("md5", "index", "requires_python"))
def test_v7_pypi_ordinary_optional_fields_reject_explicit_null(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_pypi_field(field, None),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    "native_update",
    (
        {"sha256": SHA_B},
        {"size": int(cast(int, conda_record()["size_bytes"])) + 1},
    ),
)
def test_compiler_rejects_native_metadata_contradiction_for_same_url(
    native_update: dict[str, object],
) -> None:
    document = yaml.safe_load(lockfile())
    document["packages"][0].update(native_update)
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="native|metadata|sha256|size"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            content,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_selected_reference_to_resolve_to_exactly_one_top_level_record() -> None:
    missing_document = yaml.safe_load(lockfile())
    missing_document["packages"] = []
    missing = yaml.safe_dump(missing_document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="exactly one|top-level package"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            missing,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="exactly one|duplicate|top-level package"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            lockfile(duplicate_top_package=True),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_excessive_lock_bytes_depth_and_package_count() -> None:
    oversized = lockfile() + b"#" + b"x" * (8 * 1024 * 1024)
    too_deep = (
        lockfile()
        + b"unknown:\n"
        + b"".join(b"  " * depth + f"level_{depth}:\n".encode("ascii") for depth in range(1, 35))
    )
    document = yaml.safe_load(lockfile())
    document["packages"] = [deepcopy(document["packages"][0]) for _ in range(4097)]
    too_many = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="bytes|size"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            oversized,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="depth|nested"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            too_deep,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="package count|packages"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            too_many,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_empty_selected_platform_output() -> None:
    with pytest.raises(ValueError, match="empty"):
        compile_captured_platform_lock(
            encoded(),
            lockfile(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_exact_environment_name_in_native_lock() -> None:
    with pytest.raises(ValueError, match="environment_name"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            lockfile("other-environment"),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_selected_platform_in_native_lock() -> None:
    with pytest.raises(ValueError, match="selected platform linux-64"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            lockfile(resolver_platform="linux-aarch64"),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_binds_listed_artifacts_to_selected_lock_references() -> None:
    with pytest.raises(ValueError, match="selected platform package references"):
        compile_captured_platform_lock(
            encoded(conda_record()),
            lockfile(
                package_references=(
                    (
                        "conda",
                        "https://conda.anaconda.org/bioconda/linux-64/bcftools-1.20-h8b25389_0.conda",
                    ),
                )
            ),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_conda_record_from_another_platform() -> None:
    record = conda_record(
        arch="aarch64",
        subdir="linux-aarch64",
        url="https://conda.anaconda.org/bioconda/linux-aarch64/samtools-1.20-h50ea8bc_0.conda",
    )

    with pytest.raises(ValueError, match="selected platform linux-64"):
        compile_captured_platform_lock(
            encoded(record),
            lockfile(package_references=(("conda", str(record["url"])),)),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("arch", "aarch64"),
        ("platform", "win"),
    ),
)
def test_compiler_rejects_conda_platform_metadata_contradictions(field: str, value: str) -> None:
    record = conda_record(**{field: value})

    with pytest.raises(ValueError, match="metadata|platform|arch|noarch"):
        compile_captured_platform_lock(
            encoded(record),
            lockfile(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_accepts_explicit_noarch_python_metadata_on_platform_subdir() -> None:
    compiled = compile_captured_platform_lock(
        encoded(conda_record(noarch="python")),
        lockfile_with_conda_field("noarch", "python"),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].name == "samtools"


@pytest.mark.parametrize("value", (None, {}, [], True, "", "none", "Python"))
def test_v7_noarch_rejects_values_outside_exact_upstream_variants(value: object) -> None:
    with pytest.raises(ValueError, match="noarch"):
        pixi_lock_v7._validate_pixi_lock(
            lockfile_with_conda_field("noarch", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_noarch_python_heuristic_matches_builds_containing_py() -> None:
    filename = "demo-1.0-h123_py311_0.conda"
    url = f"https://conda.anaconda.org/conda-forge/noarch/{filename}"
    record = conda_record(
        name="demo",
        version="1.0",
        build="h123_py311_0",
        build_number=0,
        source="https://conda.anaconda.org/conda-forge",
        arch=None,
        platform=None,
        subdir="noarch",
        noarch="python",
        file_name=filename,
        url=url,
    )

    compiled = compile_captured_platform_lock(
        encoded(record),
        lockfile(package_references=(("conda", url),)),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].name == "demo"


def test_v7_build_number_is_derived_from_any_trailing_ascii_digits() -> None:
    filename = "demo-1.0-h123abc4.conda"
    url = f"https://conda.anaconda.org/conda-forge/linux-64/{filename}"
    record = conda_record(
        name="demo",
        version="1.0",
        build="h123abc4",
        build_number=4,
        source="https://conda.anaconda.org/conda-forge",
        file_name=filename,
        url=url,
    )

    compiled = compile_captured_platform_lock(
        encoded(record),
        lockfile(package_references=(("conda", url),)),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    artifact = compiled.artifacts[0]
    assert isinstance(artifact, CondaLockedArtifact)
    assert artifact.build == "h123abc4"


def test_compiler_preserves_conda_name_spelling_during_native_reconciliation() -> None:
    filename = "_openmp_mutex-4.5-20_gnu.conda"
    url = f"https://conda.anaconda.org/conda-forge/linux-64/{filename}"
    mutex = conda_record(
        name="_openmp_mutex",
        version="4.5",
        build="20_gnu",
        build_number=20,
        source="https://conda.anaconda.org/conda-forge",
        file_name=filename,
        url=url,
    )

    compiled = compile_captured_platform_lock(
        encoded(mutex),
        lockfile_with_conda_field(
            "build_number",
            20,
            content=lockfile(package_references=(("conda", url),)),
        ),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].name == "_openmp_mutex"


def test_compiler_reconciles_locked_python_and_pypi_wheel_end_to_end() -> None:
    python = python_record()
    wheel = pypi_record()
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )

    compiled = compile_captured_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert tuple((artifact.kind, artifact.name) for artifact in compiled.artifacts) == (
        ("pypi", "numpy"),
        ("conda", "python"),
    )


def test_compiler_reconciles_pypi_list_depends_with_native_requires_dist() -> None:
    python = python_record()
    wheel = pypi_record()
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )

    compiled = compile_captured_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert any(artifact.kind == "pypi" for artifact in compiled.artifacts)


def test_compiler_accepts_pypi_list_record_without_cached_size() -> None:
    python = python_record()
    wheel = pypi_record(size_bytes=None)
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )

    compiled = compile_captured_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    pypi_artifact = next(artifact for artifact in compiled.artifacts if artifact.kind == "pypi")
    assert pypi_artifact.size_bytes is None


def test_compiler_preserves_custom_pypi_index_url_spelling() -> None:
    custom_index = "https://packages.example.org/simple/"
    python = python_record()
    wheel = pypi_record(source=custom_index, index_url=custom_index)
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )
    native_lock = (
        lockfile(package_references=references)
        .replace(
            b"    - https://pypi.org/simple\n",
            f"    - {custom_index}\n".encode("ascii"),
            1,
        )
        .replace(
            b"  requires_dist:\n",
            f"  index: {custom_index}\n  requires_dist:\n".encode("ascii"),
            1,
        )
    )

    compiled = compile_captured_platform_lock(
        encoded(python, wheel),
        native_lock,
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert any(artifact.kind == "pypi" for artifact in compiled.artifacts)


def test_v7_omitted_pypi_index_uses_selected_environment_first_index() -> None:
    default_index = "https://primary.example/simple/"
    python = python_record()
    wheel = pypi_record(source=default_index, index_url=default_index)
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )
    document = yaml.safe_load(lockfile(package_references=references))
    environment = document["environments"]["alignment-tools"]
    document["environments"]["alignment-tools"] = {
        "channels": environment["channels"],
        "indexes": [default_index, "https://pypi.org/simple"],
        "packages": environment["packages"],
    }
    native_lock = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    compiled = compile_captured_platform_lock(
        encoded(python, wheel),
        native_lock,
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert any(artifact.kind == "pypi" for artifact in compiled.artifacts)


def test_compiler_rejects_malformed_native_pypi_dependency_marker() -> None:
    python = python_record()
    wheel = pypi_record()
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )
    document = yaml.safe_load(lockfile(package_references=references))
    document["packages"][1]["requires_dist"] = ["typing-extensions>=4.0 ; python_version ==="]
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="dependency marker|requires_dist|malformed"):
        compile_captured_platform_lock(
            encoded(python, wheel),
            content,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_windows_wheel_for_linux_platform() -> None:
    python = python_record()
    windows_filename = "numpy-1.26.4-cp311-cp311-win_amd64.whl"
    wheel = pypi_record(url=f"https://files.pythonhosted.org/packages/{windows_filename}")
    references = (
        ("conda", str(python["url"])),
        ("pypi", str(wheel["url"])),
    )

    with pytest.raises(ValueError, match="wheel|incompatible|platform"):
        compile_captured_platform_lock(
            encoded(python, wheel),
            lockfile(package_references=references),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_digest_is_sensitive_to_exact_environment_name() -> None:
    first = compile_captured_platform_lock(
        encoded(conda_record()),
        lockfile("alignment-tools"),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    second = compile_captured_platform_lock(
        encoded(conda_record()),
        lockfile("other-environment"),
        environment_name="other-environment",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert first.native_lock_sha256 != second.native_lock_sha256
    assert first.lock_digest() != second.lock_digest()


def test_pixi_release_identity_and_linux_distribution_checksums_are_pinned() -> None:
    assert pixi_identity.PIXI_VERSION == "0.68.1"
    assert pixi_identity.PIXI_TAG_COMMIT == "a2453cacd4a02bc99ee84b5e6015ec83bbb2d397"
    assert pixi_identity.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_AMD64].archive_sha256 == (
        "sha256:f61a9546898cc1caad1956d1b5bba0408de5a24854b648631c0b49555520ed42"
    )
    assert pixi_identity.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_AMD64].binary_sha256 == (
        "sha256:01d29d4b78ab07badf57edda0b3d200bc705d5afb6da9960ebabe7010cd836e4"
    )
    assert pixi_identity.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_ARM64].archive_sha256 == (
        "sha256:b2b21272578600086e92f4e1d0e42cb7409c8e541688b9ea61aed7dd6a07a5ad"
    )
    assert pixi_identity.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_ARM64].binary_sha256 == (
        "sha256:a86916c9cf8c84fe8e1a8fbac117dc8bc85a0bf9cfc63e7382d6d45e5101f179"
    )
    assert all(
        distribution.url.startswith("https://github.com/prefix-dev/pixi/releases/download/v0.68.1/")
        for distribution in pixi_identity.PIXI_DISTRIBUTIONS.values()
    )


def test_pixi_identity_rejects_wrong_binary_sha256(tmp_path: Path) -> None:
    content = b"synthetic pixi executable"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)

    with pytest.raises(ValueError, match="SHA-256"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(
                content,
                expected_binary_sha256="sha256:" + "0" * 64,
            ),
        )


def test_pixi_identity_rejects_relative_executable_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"synthetic pixi executable"
    write_synthetic_pixi(tmp_path / "pixi", content)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="absolute|PATH"):
        pixi_identity._open_verified_pixi(
            Path("pixi"),
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(content),
        )


def test_pixi_identity_rejects_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="readable|exist"):
        pixi_identity._open_verified_pixi(
            tmp_path / "pixi",
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(b"missing"),
        )


def test_pixi_identity_rejects_symlink(tmp_path: Path) -> None:
    content = b"synthetic pixi executable"
    target = write_synthetic_pixi(tmp_path / "pixi-target", content)
    link = tmp_path / "pixi"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="symlink|regular"):
        pixi_identity._open_verified_pixi(
            link,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(content),
        )


def test_pixi_identity_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "pixi"
    directory.mkdir()

    with pytest.raises(ValueError, match="regular"):
        pixi_identity._open_verified_pixi(
            directory,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(b""),
        )


def test_pixi_identity_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "pixi"
    os.mkfifo(fifo)

    with pytest.raises(ValueError, match="regular"):
        pixi_identity._open_verified_pixi(
            fifo,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(b""),
        )


def test_pixi_identity_rejects_zero_byte_binary(tmp_path: Path) -> None:
    binary = write_synthetic_pixi(tmp_path / "pixi", b"")

    with pytest.raises(ValueError, match="size|empty|byte"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(b""),
        )


def test_pixi_identity_rejects_oversized_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"123456789"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)
    monkeypatch.setattr(pixi_identity, "_MAX_PIXI_BINARY_BYTES", len(content) - 1)

    with pytest.raises(ValueError, match="size|bytes"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(content),
        )


def test_pixi_identity_rejects_non_executable_regular_file(tmp_path: Path) -> None:
    content = b"synthetic pixi executable"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)
    binary.chmod(0o644)

    with pytest.raises(ValueError, match="executable|permission"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(content),
        )


def test_pixi_identity_retains_verified_fd_across_path_replacement(tmp_path: Path) -> None:
    content = b"verified pixi bytes"
    replacement = b"unverified replacement"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(content),
    ) as verified:
        original = tmp_path / "pixi-original"
        binary.rename(original)
        write_synthetic_pixi(binary, replacement)

        assert verified.executable == f"/proc/self/fd/{verified.fd}"
        assert Path(verified.executable).read_bytes() == content
        assert verified.resolver.config_digest == "sha256:" + "a" * 64

    with pytest.raises(ValueError, match="closed"):
        _ = verified.fd


def test_pixi_identity_rejects_in_place_mutation_during_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"verified pixi bytes"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)
    real_read = os.read
    mutated = False

    def mutate_after_eof(fd: int, size: int) -> bytes:
        nonlocal mutated
        chunk = real_read(fd, size)
        if not chunk and not mutated:
            with binary.open("ab") as handle:
                handle.write(b"mutated")
            mutated = True
        return chunk

    monkeypatch.setattr(pixi_identity.os, "read", mutate_after_eof)

    with pytest.raises(ValueError, match="changed|metadata"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(content),
        )


def test_verified_x86_host_handle_compiles_arm_target_lock(tmp_path: Path) -> None:
    content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", content)
    filename = "samtools-1.20-h50ea8bc_0.conda"
    url = f"https://conda.anaconda.org/bioconda/linux-aarch64/{filename}"
    arm_record = conda_record(
        arch="aarch64",
        subdir="linux-aarch64",
        url=url,
    )

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(content),
    ) as verified:
        compiled = pixi_lock_v7._compile_captured_platform_lock(
            pixi_list_content=encoded(arm_record),
            pixi_lock_content=lockfile(
                resolver_platform="linux-aarch64",
                package_references=(("conda", url),),
            ),
            resolver=verified.resolver,
            environment_name="alignment-tools",
            target_platform=ExecutionPlatform.LINUX_ARM64,
        )

    assert compiled.platform is ExecutionPlatform.LINUX_ARM64
    assert compiled.resolver.config_digest == "sha256:" + "a" * 64


def test_private_compiler_stages_exact_bytes_and_uses_locked_no_install(tmp_path: Path) -> None:
    binary_content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", binary_content)
    filename = "samtools-1.20-h50ea8bc_0.conda"
    url = f"https://conda.anaconda.org/bioconda/linux-aarch64/{filename}"
    arm_record = conda_record(arch="aarch64", subdir="linux-aarch64", url=url)
    pixi_toml_content = b"[workspace]\nname = 'fixture'\nchannels = ['bioconda']\nplatforms = ['linux-aarch64']\n"
    pixi_lock_content = lockfile(
        resolver_platform="linux-aarch64",
        package_references=(("conda", url),),
    )
    seen: list[tuple[tuple[str, ...], Path, int]] = []

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        assert sorted(path.name for path in cwd.iterdir()) == ["pixi.lock", "pixi.toml"]
        assert (cwd / "pixi.toml").read_bytes() == pixi_toml_content
        assert (cwd / "pixi.lock").read_bytes() == pixi_lock_content
        seen.append((command, cwd, executable_fd))
        return encoded(arm_record)

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(binary_content),
    ) as verified:
        compiled = compiler._compile_with_capture_for_test(
            pixi_toml_content=pixi_toml_content,
            pixi_lock_content=pixi_lock_content,
            capture=capture,
            verified_pixi=verified,
            target_platform=ExecutionPlatform.LINUX_ARM64,
            environment_name="alignment-tools",
        )

    command, stage, executable_fd = seen[0]
    assert command[0] == f"/proc/self/fd/{executable_fd}"
    assert command[1:5] == ("list", "--locked", "--no-install", "--json")
    assert command[5:9] == ("--environment", "alignment-tools", "--platform", "linux-aarch64")
    assert command[9] == "--manifest-path"
    assert not stage.exists()
    assert compiled.platform is ExecutionPlatform.LINUX_ARM64


@pytest.mark.parametrize(
    ("pixi_toml_content", "error_type", "message"),
    (
        (bytearray(b"[workspace]\n"), TypeError, "exact bytes"),
        (b"", ValueError, "between 1 and"),
        (b"x" * (1024 * 1024 + 1), ValueError, "between 1 and"),
    ),
)
def test_private_compiler_requires_exact_bounded_manifest_bytes(
    pixi_toml_content: object,
    error_type: type[Exception],
    message: str,
) -> None:
    capture_called = False

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        nonlocal capture_called
        capture_called = True
        return encoded(conda_record())

    with pytest.raises(error_type, match=message):
        compiler._compile_with_capture_for_test(
            pixi_toml_content=cast(bytes, pixi_toml_content),
            pixi_lock_content=lockfile(),
            capture=capture,
            verified_pixi=cast(pixi_identity._VerifiedPixiHandle, None),
            target_platform=ExecutionPlatform.LINUX_AMD64,
            environment_name="alignment-tools",
        )

    assert not capture_called


def test_private_compiler_accepts_manifest_at_one_mib_limit(tmp_path: Path) -> None:
    binary_content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", binary_content)

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(binary_content),
    ) as verified:
        compiled = compiler._compile_with_capture_for_test(
            pixi_toml_content=b"#" * (1024 * 1024),
            pixi_lock_content=lockfile(),
            capture=lambda command, cwd, executable_fd: encoded(conda_record()),
            verified_pixi=verified,
            target_platform=ExecutionPlatform.LINUX_AMD64,
            environment_name="alignment-tools",
        )

    assert compiled.platform is ExecutionPlatform.LINUX_AMD64


def test_capture_owns_subprocess_fd_cwd_and_pipes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = ("/proc/self/fd/41", "list", "--locked", "--no-install", "--json")
    calls: list[tuple[tuple[str, ...], Path, tuple[int, ...], bool, int, int]] = []

    def run(
        invoked: tuple[str, ...],
        *,
        cwd: Path,
        pass_fds: tuple[int, ...],
        check: bool,
        stdout: int,
        stderr: int,
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((invoked, cwd, pass_fds, check, stdout, stderr))
        return subprocess.CompletedProcess(invoked, 0, stdout=encoded(conda_record()), stderr=b"")

    monkeypatch.setattr(compiler.subprocess, "run", run)

    captured = compiler._capture_pixi_list(command, tmp_path, 41)

    assert captured == encoded(conda_record())
    assert calls == [
        (
            command,
            tmp_path,
            (41,),
            True,
            subprocess.PIPE,
            subprocess.PIPE,
        )
    ]


def test_capture_reports_bounded_nonzero_exit_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = ("/proc/self/fd/41", "list", "--locked", "--no-install", "--json")
    stderr_content = b"controlled failure\n" + b"x" * 5000 + b"must-not-escape"

    def run(
        invoked: tuple[str, ...],
        *,
        cwd: Path,
        pass_fds: tuple[int, ...],
        check: bool,
        stdout: int,
        stderr: int,
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(23, invoked, output=b"ignored", stderr=stderr_content)

    monkeypatch.setattr(compiler.subprocess, "run", run)

    with pytest.raises(ValueError, match="exit code 23: controlled failure") as captured:
        compiler._capture_pixi_list(command, tmp_path, 41)

    assert len(str(captured.value)) < 4200
    assert "must-not-escape" not in str(captured.value)
    assert isinstance(captured.value.__cause__, subprocess.CalledProcessError)


def test_private_compiler_cleans_stage_after_capture_failure(tmp_path: Path) -> None:
    binary_content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", binary_content)
    pixi_toml_content = b"[workspace]\nname = 'fixture'\nchannels = ['bioconda']\nplatforms = ['linux-64']\n"
    pixi_lock_content = lockfile()
    stages: list[Path] = []

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        stages.append(cwd)
        raise RuntimeError("capture failed")

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(binary_content),
    ) as verified:
        with pytest.raises(RuntimeError, match="capture failed"):
            compiler._compile_with_capture_for_test(
                pixi_toml_content=pixi_toml_content,
                pixi_lock_content=pixi_lock_content,
                capture=capture,
                verified_pixi=verified,
                target_platform=ExecutionPlatform.LINUX_AMD64,
                environment_name="alignment-tools",
            )

    assert len(stages) == 1
    assert not stages[0].exists()


def test_private_compiler_rejects_stage_mutation_after_capture_error(tmp_path: Path) -> None:
    binary_content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", binary_content)
    pixi_toml_content = b"[workspace]\nname = 'fixture'\nchannels = ['bioconda']\nplatforms = ['linux-64']\n"
    pixi_lock_content = lockfile()

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        (cwd / ".pixi").mkdir()
        raise RuntimeError("capture failed after mutation")

    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(binary_content),
    ) as verified:
        with pytest.raises(ValueError, match=r"only pixi\.toml and pixi\.lock") as captured:
            compiler._compile_with_capture_for_test(
                pixi_toml_content=pixi_toml_content,
                pixi_lock_content=pixi_lock_content,
                capture=capture,
                verified_pixi=verified,
                target_platform=ExecutionPlatform.LINUX_AMD64,
                environment_name="alignment-tools",
            )

    assert isinstance(captured.value.__context__, RuntimeError)


def test_public_compiler_opens_verified_host_and_compiles_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary_content = b"verified x86 host pixi"
    binary = write_synthetic_pixi(tmp_path / "pixi", binary_content)
    filename = "samtools-1.20-h50ea8bc_0.conda"
    url = f"https://conda.anaconda.org/bioconda/linux-aarch64/{filename}"
    arm_record = conda_record(arch="aarch64", subdir="linux-aarch64", url=url)
    pixi_toml_content = b"[workspace]\nplatforms = ['linux-aarch64']\n"
    pixi_lock_content = lockfile(
        resolver_platform="linux-aarch64",
        package_references=(("conda", url),),
    )
    real_open = pixi_identity._open_verified_pixi
    opened: list[tuple[Path, ExecutionPlatform]] = []
    captures: list[tuple[tuple[str, ...], Path, int]] = []

    def open_verified(
        executable_path: Path,
        *,
        host_platform: ExecutionPlatform,
    ) -> pixi_identity._VerifiedPixiHandle:
        opened.append((executable_path, host_platform))
        return real_open(
            executable_path,
            host_platform=host_platform,
            distributions=synthetic_distribution_map(binary_content),
        )

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        captures.append((command, cwd, executable_fd))
        assert (cwd / "pixi.toml").read_bytes() == pixi_toml_content
        assert (cwd / "pixi.lock").read_bytes() == pixi_lock_content
        return encoded(arm_record)

    monkeypatch.setattr(pixi_identity, "_open_verified_pixi", open_verified)
    monkeypatch.setattr(compiler, "_capture_pixi_list", capture)

    compiled = compiler.compile_pixi_platform_lock(
        pixi_toml_content,
        pixi_lock_content,
        pixi_executable=binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        target_platform=ExecutionPlatform.LINUX_ARM64,
        environment_name="alignment-tools",
    )

    assert opened == [(binary, ExecutionPlatform.LINUX_AMD64)]
    assert len(captures) == 1
    assert captures[0][0][0] == f"/proc/self/fd/{captures[0][2]}"
    assert not captures[0][1].exists()
    assert compiled.platform is ExecutionPlatform.LINUX_ARM64
    assert compiled.resolver.config_digest == "sha256:" + "a" * 64


def test_public_compiler_exposes_only_exact_byte_verified_binary_boundary() -> None:
    signature = inspect.signature(compiler.compile_pixi_platform_lock)

    assert tuple(signature.parameters) == (
        "pixi_toml_content",
        "pixi_lock_content",
        "pixi_executable",
        "host_platform",
        "target_platform",
        "environment_name",
    )
    assert not hasattr(compiler, "admit_pixi_records")
    assert not hasattr(compiler, "compile_pixi_platform_lock_with_runner")
    assert not hasattr(compiler, "VerifiedPixiExecutable")
