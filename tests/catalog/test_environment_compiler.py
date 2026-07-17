from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml
from packaging.utils import canonicalize_name, parse_wheel_filename
from pydantic import ValidationError

from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.environment_compiler import compiler


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


def verified_pixi(
    executable_path: Path = Path("/opt/bionodulo/pixi-0.68.1/bin/pixi"),
    *,
    platform: ExecutionPlatform = ExecutionPlatform.LINUX_AMD64,
    version: str = "0.68.1",
) -> compiler.VerifiedPixiExecutable:
    return compiler.VerifiedPixiExecutable(
        executable_path=executable_path,
        version=version,
        distribution=compiler.PIXI_DISTRIBUTIONS[platform],
    )


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
    depends = tuple(str(dependency) for dependency in listed["depends"])
    constrains = tuple(str(constraint) for constraint in listed["constrains"])
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

    selected = compiler._validate_pixi_lock(
        content,
        environment_name="default",
        resolver_platform="linux-64",
    )

    assert len(selected) > 100
    assert any(package.kind == "conda" and package.name == "python" for package in selected)
    assert any(package.kind == "pypi" and package.name == "numpy" for package in selected)


def test_decoder_accepts_realistic_full_conda_and_pypi_records() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record(), pypi_record()))

    assert tuple(type(record) for record in records) == (
        compiler.PixiPypiListRecord,
        compiler.PixiCondaListRecord,
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
        compiler.decode_pixi_list_json(content)


@pytest.mark.parametrize("field", ("kind", "index_url", "track_features"))
def test_decoder_rejects_missing_required_abi_fields(field: str) -> None:
    record = conda_record()
    record.pop(field)

    with pytest.raises(ValidationError, match=field):
        compiler.decode_pixi_list_json(encoded(record))


def test_decoder_rejects_unknown_abi_fields() -> None:
    with pytest.raises(ValidationError, match="unknown_field"):
        compiler.decode_pixi_list_json(encoded(conda_record(unknown_field=True)))


@pytest.mark.parametrize("kind", ("conda-forge", "wheel", "", None))
def test_kind_is_the_only_strict_conda_pypi_discriminator(kind: object) -> None:
    with pytest.raises(ValidationError, match="kind"):
        compiler.decode_pixi_list_json(encoded(conda_record(kind=kind)))


def test_decoder_requires_null_pypi_file_name_as_emitted_by_pixi() -> None:
    with pytest.raises(ValidationError, match="file_name"):
        compiler.decode_pixi_list_json(encoded(pypi_record(file_name="numpy.whl")))


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
        compiler.decode_pixi_list_json(encoded(pypi_record(**{field: value})))


def test_decoder_rejects_duplicate_json_object_keys() -> None:
    content = encoded(conda_record()).replace(
        b'"name":"samtools"',
        b'"name":"other","name":"samtools"',
        1,
    )

    with pytest.raises(ValueError, match="duplicate JSON key: name"):
        compiler.decode_pixi_list_json(content)


def test_decoder_accepts_missing_optional_sha_but_admission_rejects_it() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record(sha256=None)))

    assert records[0].sha256 is None
    with pytest.raises(ValueError, match="sha256"):
        compiler.admit_pixi_records(
            records,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize("digest", ("sha256:" + SHA_A, "A" * 64, "a" * 63, "g" * 64))
def test_decoder_rejects_non_pixiesque_sha256_text(digest: str) -> None:
    with pytest.raises(ValidationError, match="sha256"):
        compiler.decode_pixi_list_json(encoded(conda_record(sha256=digest)))


def test_admission_builds_strict_sorted_platform_lock() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record(), python_record(), pypi_record()))

    admitted = compiler.admit_pixi_records(
        reversed(records),
        pixi=verified_pixi(),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
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
    records = compiler.decode_pixi_list_json(
        encoded(
            python_record(),
            pypi_record(
                name="scikit_learn",
                version="1.4.2",
                url=f"https://files.pythonhosted.org/packages/{filename}",
            ),
        )
    )

    admitted = compiler.admit_pixi_records(
        records,
        pixi=verified_pixi(),
        environment_name="python-analysis",
        platform=ExecutionPlatform.LINUX_AMD64,
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
    records = compiler.decode_pixi_list_json(encoded(record))

    with pytest.raises(ValueError):
        compiler.admit_pixi_records(
            records,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
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
    records = compiler.decode_pixi_list_json(encoded(pypi_record(url=url)))

    with pytest.raises(ValueError, match="name|version"):
        compiler.admit_pixi_records(
            records,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize("version", (6, 8, "7", True, None))
def test_compiler_independently_requires_pixi_lock_format_seven(version: object) -> None:
    with pytest.raises(ValueError, match="version 7"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(version=version),
            pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            content,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_unknown_v7_fields_and_noncanonical_root_order() -> None:
    unknown = lockfile() + b"unknown: true\n"
    valid = lockfile()
    reordered = valid.replace(b"version: 7\nplatforms:\n", b"platforms:\n", 1)
    reordered += b"version: 7\n"

    with pytest.raises(ValueError, match="unknown|top-level"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            unknown,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="canonical|order"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            reordered,
            pixi=verified_pixi(),
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

    selected = compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
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
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            content,
            pixi=verified_pixi(),
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
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("legacy_bz2_md5", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_legacy_bz2_md5_is_retained_on_native_package() -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("legacy_bz2_md5", "f" * 32),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].legacy_bz2_md5 == "f" * 32


@pytest.mark.parametrize("value", (None, {}, [], True, -1, 1.5, "1", 2**64))
def test_v7_legacy_bz2_size_rejects_values_outside_optional_u64(value: object) -> None:
    with pytest.raises(ValueError, match="legacy_bz2_size"):
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("legacy_bz2_size", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", (0, 2**64 - 1))
def test_v7_legacy_bz2_size_is_retained_on_native_package(value: int) -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("legacy_bz2_size", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].legacy_bz2_size == value


@pytest.mark.parametrize("value", (None, {}, [], 1, True, "f" * 257, "feature\nvalue"))
def test_v7_features_rejects_values_outside_optional_bounded_string(value: object) -> None:
    with pytest.raises(ValueError, match="features"):
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("features", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", ("", "mkl"))
def test_v7_features_is_retained_on_native_package(value: str) -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("features", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].features == value


@pytest.mark.parametrize("value", (None, {}, [], 1, True, "p" * 1025, "lib\nsite-packages"))
def test_v7_python_site_packages_path_rejects_values_outside_bounded_string(value: object) -> None:
    with pytest.raises(ValueError, match="python_site_packages_path"):
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("python_site_packages_path", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("value", ("", "lib/python3.11/site-packages"))
def test_v7_python_site_packages_path_is_retained_on_native_package(value: str) -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("python_site_packages_path", value),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].python_site_packages_path == value


@pytest.mark.parametrize("value", ({}, {"python": "3.11"}))
def test_v7_binary_conda_package_rejects_source_variants_field(value: object) -> None:
    with pytest.raises(ValueError, match="variants|binary"):
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("variants", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("field", ("build_packages", "host_packages"))
def test_v7_pypi_wheel_rejects_source_selector_fields_even_when_empty(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        compiler._validate_pixi_lock(
            lockfile_with_pypi_field(field, []),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_conda_timestamp_accepts_signed_upstream_integer() -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("timestamp", -1),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].timestamp == -1


@pytest.mark.parametrize("value", (None, True, 1.5, "1", -(2**63) - 1, 2**63))
def test_v7_conda_timestamp_rejects_values_outside_signed_i64(value: object) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("timestamp", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_explicit_null_channel_overrides_url_derived_channel() -> None:
    compiled = compiler.compile_pixi_platform_lock(
        encoded(conda_record(source=None)),
        lockfile_with_conda_field("channel", None),
        pixi=verified_pixi(),
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
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("channel", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_extra_depends_retains_sorted_map_and_ordered_vectors() -> None:
    selected = compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
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
    selected = compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
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
    selected = compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
            lockfile_with_conda_field("purls", value),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


def test_v7_flags_retains_ordered_upstream_vector() -> None:
    selected = compiler._validate_pixi_lock(
        lockfile_with_conda_field("flags", ["deprecated", "revoked"]),
        environment_name="alignment-tools",
        resolver_platform="linux-64",
    )

    assert selected[0].flags == ("deprecated", "revoked")


@pytest.mark.parametrize("value", (None, {}, "deprecated", [], [1], ["flag\nvalue"]))
def test_v7_flags_rejects_values_outside_nonempty_ordered_string_vector(value: object) -> None:
    with pytest.raises(ValueError, match="flags"):
        compiler._validate_pixi_lock(
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
        compiler._validate_pixi_lock(
            lockfile_with_conda_field(field, None),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize("field", ("md5", "index", "requires_python"))
def test_v7_pypi_ordinary_optional_fields_reject_explicit_null(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        compiler._validate_pixi_lock(
            lockfile_with_pypi_field(field, None),
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )


@pytest.mark.parametrize(
    "native_update",
    (
        {"sha256": SHA_B},
        {"size": int(conda_record()["size_bytes"]) + 1},
    ),
)
def test_compiler_rejects_native_metadata_contradiction_for_same_url(
    native_update: dict[str, object],
) -> None:
    document = yaml.safe_load(lockfile())
    document["packages"][0].update(native_update)
    content = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="native|metadata|sha256|size"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            content,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_selected_reference_to_resolve_to_exactly_one_top_level_record() -> None:
    missing_document = yaml.safe_load(lockfile())
    missing_document["packages"] = []
    missing = yaml.safe_dump(missing_document, sort_keys=False).encode("utf-8")

    with pytest.raises(ValueError, match="exactly one|top-level package"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            missing,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="exactly one|duplicate|top-level package"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(duplicate_top_package=True),
            pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            oversized,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="depth|nested"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            too_deep,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )
    with pytest.raises(ValueError, match="package count|packages"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            too_many,
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_empty_selected_platform_output() -> None:
    with pytest.raises(ValueError, match="empty"):
        compiler.compile_pixi_platform_lock(
            encoded(),
            lockfile(),
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_exact_environment_name_in_native_lock() -> None:
    with pytest.raises(ValueError, match="environment_name"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile("other-environment"),
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_selected_platform_in_native_lock() -> None:
    with pytest.raises(ValueError, match="selected platform linux-64"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(resolver_platform="linux-aarch64"),
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_binds_listed_artifacts_to_selected_lock_references() -> None:
    with pytest.raises(ValueError, match="selected platform package references"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(
                package_references=(
                    (
                        "conda",
                        "https://conda.anaconda.org/bioconda/linux-64/bcftools-1.20-h8b25389_0.conda",
                    ),
                )
            ),
            pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(record),
            lockfile(package_references=(("conda", str(record["url"])),)),
            pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(record),
            lockfile(),
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_accepts_explicit_noarch_python_metadata_on_platform_subdir() -> None:
    compiled = compiler.compile_pixi_platform_lock(
        encoded(conda_record(noarch="python")),
        lockfile_with_conda_field("noarch", "python"),
        pixi=verified_pixi(),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].name == "samtools"


@pytest.mark.parametrize("value", (None, {}, [], True, "", "none", "Python"))
def test_v7_noarch_rejects_values_outside_exact_upstream_variants(value: object) -> None:
    with pytest.raises(ValueError, match="noarch"):
        compiler._validate_pixi_lock(
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(record),
        lockfile(package_references=(("conda", url),)),
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(record),
        lockfile(package_references=(("conda", url),)),
        pixi=verified_pixi(),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.artifacts[0].build == "h123abc4"


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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(mutex),
        lockfile_with_conda_field(
            "build_number",
            20,
            content=lockfile(package_references=(("conda", url),)),
        ),
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(python, wheel),
        lockfile(package_references=references),
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(python, wheel),
        native_lock,
        pixi=verified_pixi(),
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

    compiled = compiler.compile_pixi_platform_lock(
        encoded(python, wheel),
        native_lock,
        pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(python, wheel),
            content,
            pixi=verified_pixi(),
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
        compiler.compile_pixi_platform_lock(
            encoded(python, wheel),
            lockfile(package_references=references),
            pixi=verified_pixi(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_digest_is_sensitive_to_exact_environment_name() -> None:
    first = compiler.compile_pixi_platform_lock(
        encoded(conda_record()),
        lockfile("alignment-tools"),
        pixi=verified_pixi(),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    second = compiler.compile_pixi_platform_lock(
        encoded(conda_record()),
        lockfile("other-environment"),
        pixi=verified_pixi(),
        environment_name="other-environment",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert first.native_lock_sha256 != second.native_lock_sha256
    assert first.lock_digest() != second.lock_digest()


def test_verified_runner_uses_one_frozen_read_only_platform_list_command(tmp_path: Path) -> None:
    commands: list[tuple[str, ...]] = []
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock)

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        assert cwd == tmp_path
        commands.append(command)
        return encoded(conda_record())

    compiled = compiler.compile_pixi_platform_lock_with_runner(
        runner,
        pixi=verified_pixi(),
        workspace_root=tmp_path,
        pixi_lock_content=native_lock,
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.environment_name == "alignment-tools"
    assert commands == [
        (
            "/opt/bionodulo/pixi-0.68.1/bin/pixi",
            "list",
            "--frozen",
            "--no-install",
            "--json",
            "--environment",
            "alignment-tools",
            "--platform",
            "linux-64",
            "--manifest-path",
            str(tmp_path / "pixi.toml"),
        ),
    ]
    assert all("install" not in command for command in commands)


def test_injected_runner_without_verified_pixi_identity_is_rejected(tmp_path: Path) -> None:
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock)
    commands: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        commands.append(command)
        return encoded(conda_record())

    with pytest.raises(ValueError, match="verified Pixi"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )

    assert commands == []


def test_captured_bytes_cannot_claim_pinned_resolver_without_verified_identity() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record()))

    with pytest.raises(ValueError, match="verified Pixi"):
        compiler.admit_pixi_records(
            records,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )
    with pytest.raises(ValueError, match="verified Pixi"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_verified_pixi_identity_rejects_path_lookup_name() -> None:
    with pytest.raises(ValidationError, match="absolute|PATH"):
        verified_pixi(Path("pixi"))


def test_runner_rejects_verified_distribution_for_wrong_target_platform(tmp_path: Path) -> None:
    native_lock = lockfile(resolver_platform="linux-aarch64")
    (tmp_path / "pixi.lock").write_bytes(native_lock)
    commands: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        commands.append(command)
        return encoded(conda_record())

    with pytest.raises(ValueError, match="distribution|target platform"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(platform=ExecutionPlatform.LINUX_AMD64),
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_ARM64,
        )

    assert commands == []


def test_injected_runner_requires_supplied_lock_to_equal_workspace_lock(tmp_path: Path) -> None:
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock + b"# different exact bytes\n")
    commands: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        commands.append(command)
        return encoded(conda_record()) if command[1] == "list" else b""

    with pytest.raises(ValueError, match="supplied pixi.lock bytes must equal workspace pixi.lock"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(),
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )

    assert commands == []


def test_injected_runner_rejects_lock_mutation_during_commands(tmp_path: Path) -> None:
    native_lock = lockfile()
    lock_path = tmp_path / "pixi.lock"
    lock_path.write_bytes(native_lock)

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        if command[1] == "list":
            lock_path.write_bytes(native_lock + b"# mutated during list\n")
            return encoded(conda_record())
        return b""

    with pytest.raises(ValueError, match="workspace pixi.lock changed during locked Pixi commands"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(),
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_locked_runner_success_does_not_bypass_native_version_validation(tmp_path: Path) -> None:
    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        return encoded(conda_record()) if command[1] == "list" else b""

    with pytest.raises(ValueError, match="version 7"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(),
            workspace_root=tmp_path,
            pixi_lock_content=lockfile(version=6),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_runner_rejects_pixi_environment_mutation(tmp_path: Path) -> None:
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock)

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        generated = cwd / ".pixi" / "envs" / "default"
        generated.mkdir(parents=True)
        (generated / "mutated").write_bytes(b"installed")
        return encoded(conda_record())

    with pytest.raises(ValueError, match=r"read-only|\.pixi|workspace"):
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(),
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_runner_detects_workspace_mutation_even_when_capture_raises(tmp_path: Path) -> None:
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock)

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        generated = cwd / ".pixi" / "envs" / "default"
        generated.mkdir(parents=True)
        (generated / "mutated").write_bytes(b"installed")
        raise RuntimeError("capture failed after mutation")

    with pytest.raises(ValueError, match=r"read-only|\.pixi|workspace") as captured:
        compiler.compile_pixi_platform_lock_with_runner(
            runner,
            pixi=verified_pixi(),
            workspace_root=tmp_path,
            pixi_lock_content=native_lock,
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )

    assert isinstance(captured.value.__context__, RuntimeError)


def test_pixi_release_identity_and_linux_distribution_checksums_are_pinned() -> None:
    assert compiler.PIXI_VERSION == "0.68.1"
    assert compiler.PIXI_TAG_COMMIT == "a2453cacd4a02bc99ee84b5e6015ec83bbb2d397"
    assert compiler.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_AMD64].sha256 == (
        "sha256:f61a9546898cc1caad1956d1b5bba0408de5a24854b648631c0b49555520ed42"
    )
    assert compiler.PIXI_DISTRIBUTIONS[ExecutionPlatform.LINUX_ARM64].sha256 == (
        "sha256:b2b21272578600086e92f4e1d0e42cb7409c8e541688b9ea61aed7dd6a07a5ad"
    )
    assert all(
        distribution.url.startswith("https://github.com/prefix-dev/pixi/releases/download/v0.68.1/")
        for distribution in compiler.PIXI_DISTRIBUTIONS.values()
    )
