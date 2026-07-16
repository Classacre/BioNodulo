from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.environment_compiler import compiler


SHA_A = "a" * 64
SHA_B = "b" * 64


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
        "depends": ["python>=3.9"],
        "track_features": [],
    }
    record.update(updates)
    return record


def encoded(*records: dict[str, object]) -> bytes:
    return json.dumps(records, separators=(",", ":")).encode("utf-8")


def lockfile(
    environment_name: str = "alignment-tools",
    *,
    version: object = 7,
    resolver_platform: str = "linux-64",
    package_references: tuple[tuple[str, str], ...] | None = None,
) -> bytes:
    references = package_references or (("conda", str(conda_record()["url"])),)
    packages = "".join(f"      - {kind}: {json.dumps(url)}\n" for kind, url in references)
    return (
        f"version: {json.dumps(version)}\nenvironments:\n  {environment_name}:\n"
        f"    packages:\n      {resolver_platform}:\n{packages}"
    ).encode("utf-8")


def test_decoder_accepts_realistic_full_conda_and_pypi_records() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record(), pypi_record()))

    assert tuple(type(record) for record in records) == (
        compiler.PixiCondaListRecord,
        compiler.PixiPypiListRecord,
    )
    assert len(conda_record()) == 24
    assert len(pypi_record()) == 24
    assert records[0].source == "https://conda.anaconda.org/bioconda"
    assert records[1].source == "https://pypi.org/simple"
    assert records[1].file_name is None
    assert records[1].license is None


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
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
            native_lock_sha256="sha256:" + SHA_A,
        )


@pytest.mark.parametrize("digest", ("sha256:" + SHA_A, "A" * 64, "a" * 63, "g" * 64))
def test_decoder_rejects_non_pixiesque_sha256_text(digest: str) -> None:
    with pytest.raises(ValidationError, match="sha256"):
        compiler.decode_pixi_list_json(encoded(conda_record(sha256=digest)))


def test_admission_builds_strict_sorted_platform_lock() -> None:
    records = compiler.decode_pixi_list_json(encoded(conda_record(), pypi_record()))

    admitted = compiler.admit_pixi_records(
        reversed(records),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
        native_lock_sha256="sha256:" + SHA_A,
    )

    assert admitted.environment_name == "alignment-tools"
    assert admitted.resolver.name == "pixi"
    assert admitted.resolver.version == "0.68.1"
    assert admitted.resolver_platform == "linux-64"
    assert tuple(artifact.name for artifact in admitted.artifacts) == ("numpy", "samtools")
    assert tuple(artifact.kind for artifact in admitted.artifacts) == ("pypi", "conda")
    assert admitted.artifacts[0].filename.endswith(".whl")


def test_pypi_admission_normalizes_pixis_dist_info_package_name() -> None:
    filename = "scikit_learn-1.4.2-py3-none-any.whl"
    records = compiler.decode_pixi_list_json(
        encoded(
            pypi_record(
                name="scikit_learn",
                version="1.4.2",
                url=f"https://files.pythonhosted.org/packages/{filename}",
            )
        )
    )

    admitted = compiler.admit_pixi_records(
        records,
        environment_name="python-analysis",
        platform=ExecutionPlatform.LINUX_AMD64,
        native_lock_sha256="sha256:" + SHA_A,
    )

    assert records[0].name == "scikit_learn"
    assert admitted.artifacts[0].name == "scikit-learn"


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
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_rejects_empty_selected_platform_output() -> None:
    with pytest.raises(ValueError, match="empty"):
        compiler.compile_pixi_platform_lock(
            encoded(),
            lockfile(),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_exact_environment_name_in_native_lock() -> None:
    with pytest.raises(ValueError, match="environment_name"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile("other-environment"),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_requires_selected_platform_in_native_lock() -> None:
    with pytest.raises(ValueError, match="selected platform linux-64"):
        compiler.compile_pixi_platform_lock(
            encoded(conda_record()),
            lockfile(resolver_platform="linux-aarch64"),
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
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_compiler_digest_is_sensitive_to_exact_environment_name() -> None:
    first = compiler.compile_pixi_platform_lock(
        encoded(conda_record()),
        lockfile("alignment-tools"),
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    second = compiler.compile_pixi_platform_lock(
        encoded(conda_record()),
        lockfile("other-environment"),
        environment_name="other-environment",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert first.native_lock_sha256 != second.native_lock_sha256
    assert first.lock_digest() != second.lock_digest()


def test_injected_runner_uses_locked_install_and_list_but_never_frozen(tmp_path: Path) -> None:
    commands: list[tuple[str, ...]] = []
    native_lock = lockfile()
    (tmp_path / "pixi.lock").write_bytes(native_lock)

    def runner(command: tuple[str, ...], cwd: Path) -> bytes:
        assert cwd == tmp_path
        commands.append(command)
        return encoded(conda_record()) if command[1] == "list" else b""

    compiled = compiler.compile_pixi_platform_lock_with_runner(
        runner,
        workspace_root=tmp_path,
        pixi_lock_content=native_lock,
        environment_name="alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    assert compiled.environment_name == "alignment-tools"
    assert commands == [
        ("pixi", "install", "--locked", "--environment", "alignment-tools"),
        (
            "pixi",
            "list",
            "--locked",
            "--no-install",
            "--json",
            "--environment",
            "alignment-tools",
            "--platform",
            "linux-64",
        ),
    ]
    assert all("--frozen" not in command for command in commands)


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
            workspace_root=tmp_path,
            pixi_lock_content=lockfile(version=6),
            environment_name="alignment-tools",
            platform=ExecutionPlatform.LINUX_AMD64,
        )


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
