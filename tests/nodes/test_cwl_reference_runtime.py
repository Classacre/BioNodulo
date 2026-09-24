"""Shared cwltool execution remains descriptor-driven and artifact-safe."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes import cwl_reference_runtime as runtime
from bionodulo.nodes.contract.cwl_reference import import_cwl_reference
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.registry import NodeRegistry


ENGINE_VERSION = "3.2.20260720092025"
SHA_A = "sha256:" + "a" * 64


def _environment() -> PixiEnvironment:
    artifact = CondaLockedArtifact(
        name="seqtk",
        version="1.4",
        build="test_0",
        filename="seqtk-1.4-test_0.conda",
        url="https://packages.example.org/linux-64/seqtk-1.4-test_0.conda",
        sha256="sha256:" + "b" * 64,
        size_bytes=1024,
    )
    lock = PlatformLock(
        platform=ExecutionPlatform.LINUX_AMD64,
        environment_name="reference-runtime",
        resolver_platform="linux-64",
        resolver=ResolverIdentity(name="micromamba", version="2.3.3", config_digest=SHA_A),
        native_lock_sha256="sha256:" + "c" * 64,
        artifacts=(artifact,),
    )
    return PixiEnvironment(
        environment_id="reference-runtime",
        platforms=(ExecutionPlatform.LINUX_AMD64,),
        packages=("seqtk==1.4",),
        locks=(lock,),
    )


def _spec(*, schemas: bool = False):
    document: dict[str, object] = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "hints": [{"class": "DockerRequirement", "dockerPull": "seqtk:1.4"}],
        "inputs": {
            "reads": {"type": {"type": "array", "items": "File"}},
            "mode": {
                "type": {"type": "enum", "symbols": ["fast", "sensitive"]},
                "default": "fast",
            },
            "thresholds": {
                "type": {"type": "array", "items": "int"},
                "default": [10, 20],
            },
        },
        "outputs": {
            "primary": {"type": "File", "outputBinding": {"glob": "primary.txt"}},
            "reports": {
                "type": {"type": "array", "items": "File"},
                "outputBinding": {"glob": "*.report"},
            },
        },
    }
    if schemas:
        document["$schemas"] = ["https://example.org/schema.ttl"]
    return import_cwl_reference(
        json.dumps(document, separators=(",", ":")),
        node_id="generated_seqtk",
        source_uri="https://example.org/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )


def _secondary_spec(secondary_files: object):
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {
            "genome": {"type": "File", "secondaryFiles": secondary_files},
        },
        "outputs": {
            "result": {"type": "File", "outputBinding": {"glob": "result.txt"}},
        },
    }
    return import_cwl_reference(
        json.dumps(document, separators=(",", ":")),
        node_id="generated_secondary_seqtk",
        source_uri="https://example.org/secondary-seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )


def _capability_spec(document: dict[str, object], *, node_id: str):
    return import_cwl_reference(
        json.dumps(document, separators=(",", ":")),
        node_id=node_id,
        source_uri=f"https://example.org/{node_id}.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )


def test_binding_projects_multiple_files_parameters_and_runtime_identity() -> None:
    node = runtime.bind_cwl_reference_node(_spec())

    inputs = node.INPUT_TYPES()
    assert inputs["required"]["reads"] == ("FILE", {"multiple": True})
    assert inputs["optional"]["mode"][1]["default"] == "fast"
    assert inputs["optional"]["mode"][1]["options"] == ["fast", "sensitive"]
    assert inputs["optional"]["thresholds"] == (
        "JSON",
        {"default": [10, 20], "multiline": True},
    )
    assert node.RETURN_TYPES == ("FILE", "FILE")
    assert node.RETURN_NAMES == ("primary", "reports")
    assert node.ENVIRONMENT["type"] == "declarative_cwl"
    assert node.EXECUTOR_CACHE_POLICY == "always_run"


def test_scalar_output_publication_preserves_cwl_type_and_rejects_wrong_value(tmp_path: Path) -> None:
    document = {
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtk",
        "inputs": {},
        "outputs": {
            "count": {"type": "int", "outputBinding": {"outputEval": "1"}},
            "ratio": {"type": "float", "outputBinding": {"outputEval": "1.5"}},
            "label": {"type": "string", "outputBinding": {"outputEval": "'x'"}},
            "valid": {"type": "boolean", "outputBinding": {"outputEval": "true"}},
            "counts": {"type": "int[]", "outputBinding": {"outputEval": "[2, 3]"}},
        },
    }
    spec = _capability_spec(document, node_id="scalar_outputs")
    reference = spec.cwl_reference
    assert reference is not None
    result = {"count": 3, "ratio": 1.5, "label": "reads", "valid": True, "counts": [2, 3]}
    receipts = runtime._publish_outputs(reference, result, tmp_path)
    assert {item["cwl_type"] for item in receipts} == {"integer", "number", "string", "boolean"}
    for item in receipts:
        path = tmp_path / str(item["published_path"])
        expected = result[item["port_id"]]
        if isinstance(expected, list):
            expected = expected[int(path.name[:4])]
        assert json.loads(path.read_text()) == expected
    with pytest.raises(ValueError, match="not a integer value"):
        runtime._publish_outputs(reference, {**result, "count": True}, tmp_path / "bad")
    with pytest.raises(ValueError, match="not a number value"):
        runtime._publish_outputs(reference, {**result, "ratio": float("nan")}, tmp_path / "nonfinite")


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="safe descriptor output collection is Linux-only")
async def test_reference_runtime_stages_inputs_and_publishes_cwltool_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = _spec(schemas=True)
    node = runtime.bind_cwl_reference_node(spec)
    engine = tmp_path / "cwltool"
    engine.write_bytes(b"engine")
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    primary_executable = prefix / "bin" / "seqtk"
    primary_executable.write_bytes(b"tool")
    source_a = tmp_path / "a.fa"
    source_b = tmp_path / "b.fa"
    source_a.write_text(">a\nAC\n", encoding="utf-8")
    source_b.write_text(">b\nGT\n", encoding="utf-8")

    async def verified(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "engine_path": str(engine),
            "engine_sha256": runtime._sha256_file(engine),
            "engine_version": ENGINE_VERSION,
            "environment_prefix": str(prefix),
            "primary_executable": str(primary_executable),
            "primary_executable_sha256": runtime._sha256_file(primary_executable),
            "nodejs_path": None,
            "nodejs_sha256": None,
        }

    observed: dict[str, Any] = {}

    async def execute(
        command: list[str],
        *,
        stdout_path: Path | None = None,
        env: dict[str, str] | None = None,
        **_kwargs: object,
    ) -> dict[str, Any]:
        observed["command"] = command
        observed["env"] = env
        descriptor = Path(command[-2])
        job = Path(command[-1])
        observed["source"] = descriptor.read_text(encoding="utf-8")
        observed["job"] = json.loads(job.read_text(encoding="utf-8"))
        outdir = Path(command[command.index("--outdir") + 1])
        primary = outdir / "primary.txt"
        report_a = outdir / "a.report"
        report_b = outdir / "b.report"
        primary.write_text("primary", encoding="utf-8")
        report_a.write_text("a", encoding="utf-8")
        report_b.write_text("b", encoding="utf-8")
        assert stdout_path is not None
        stdout_path.write_text(
            json.dumps(
                {
                    "primary": {"class": "File", "path": str(primary)},
                    "reports": [
                        {"class": "File", "path": str(report_a)},
                        {"class": "File", "path": str(report_b)},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return {"returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(runtime, "verify_reference_runtime", verified)
    monkeypatch.setattr(runtime, "_run_process", execute)
    context = SimpleNamespace(
        node_dir=tmp_path / "node",
        node_id="generated",
        run_metadata={},
        executor=None,
    )

    primary_path, report_paths = await node().run(
        context=context,
        reads=[str(source_a), str(source_b)],
    )

    assert "--no-container" in observed["command"]
    assert "--skip-schemas" in observed["command"]
    assert observed["command"][observed["command"].index("--preserve-environment") + 1] == (
        "PYTHONDONTWRITEBYTECODE"
    )
    assert observed["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert observed["source"] == spec.cwl_reference.source_text
    staged = observed["job"]["reads"]
    assert [Path(item["path"]).name for item in staged] == ["a.fa", "b.fa"]
    assert all(Path(item["path"]) != original for item, original in zip(staged, (source_a, source_b)))
    assert source_a.read_text(encoding="utf-8") == ">a\nAC\n"
    assert Path(primary_path).read_text(encoding="utf-8") == "primary"
    assert [Path(path).read_text(encoding="utf-8") for path in report_paths] == ["a", "b"]
    receipt = context.run_metadata["cwl_reference"]["generated"]
    assert receipt["source_content_sha256"] == (
        "sha256:" + hashlib.sha256(spec.cwl_reference.source_text.encode()).hexdigest()
    )
    assert len(receipt["output_publication"]) == 3


def test_file_format_uri_is_preserved_on_staged_job_object(tmp_path: Path) -> None:
    spec = _spec()
    source = tmp_path / "reads.sam"
    source.write_text("@HD\tVN:1.6\n", encoding="utf-8")
    reference = spec.cwl_reference
    assert reference is not None

    job, receipts = runtime._build_job(
        reference,
        {
            "reads": [
                {
                    "class": "File",
                    "location": str(source),
                    "format": "http://edamontology.org/format_2573",
                }
            ]
        },
        tmp_path / "stage",
    )

    assert job["reads"][0]["format"] == "http://edamontology.org/format_2573"
    assert receipts[0]["format"] == "http://edamontology.org/format_2573"


def test_many_artifact_input_wraps_single_graph_edge_value(tmp_path: Path) -> None:
    file_spec = _spec()
    file_reference = file_spec.cwl_reference
    assert file_reference is not None
    source_file = tmp_path / "single.fa"
    source_file.write_text(">one\nAC\n", encoding="utf-8")
    file_node = runtime.bind_cwl_reference_node(file_spec)

    assert file_node.VALIDATE_INPUTS({"reads": str(source_file)}) is True
    file_job, _ = runtime._build_job(
        file_reference,
        {"reads": str(source_file)},
        tmp_path / "file-stage",
    )
    assert isinstance(file_job["reads"], list) and len(file_job["reads"]) == 1
    assert Path(file_job["reads"][0]["path"]).read_bytes() == source_file.read_bytes()

    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {"indexes": {"type": {"type": "array", "items": "Directory"}}},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    directory_spec = _capability_spec(document, node_id="generated_directory_array")
    directory_reference = directory_spec.cwl_reference
    assert directory_reference is not None
    source_directory = tmp_path / "index"
    source_directory.mkdir()
    (source_directory / "data").write_text("index", encoding="utf-8")
    directory_node = runtime.bind_cwl_reference_node(directory_spec)

    assert directory_node.VALIDATE_INPUTS({"indexes": str(source_directory)}) is True
    directory_job, _ = runtime._build_job(
        directory_reference,
        {"indexes": str(source_directory)},
        tmp_path / "directory-stage",
    )
    assert isinstance(directory_job["indexes"], list) and len(directory_job["indexes"]) == 1
    assert Path(directory_job["indexes"][0]["path"]).is_dir()


def test_json_array_widget_value_is_parsed_for_cwl_job(tmp_path: Path) -> None:
    spec = _spec()
    reference = spec.cwl_reference
    assert reference is not None

    job, _receipts = runtime._build_job(
        reference,
        {"thresholds": "[3,5,8]", "mode": "sensitive"},
        tmp_path / "stage",
    )

    assert job["thresholds"] == [3, 5, 8]
    assert job["mode"] == "sensitive"
    mapping = next(item for item in reference.input_mappings if item.port_id == "thresholds")
    with pytest.raises(ValueError, match="must contain a JSON array"):
        runtime._parameter_value(mapping, '"not-an-array"')
    with pytest.raises(ValueError, match="not valid JSON"):
        runtime._parameter_value(mapping, "[broken")


def test_reference_catalog_with_file_json_array_and_enum_loads(tmp_path: Path) -> None:
    spec = _spec()
    catalog = tmp_path / "reference-catalog.json"
    catalog.write_text(
        json.dumps({"schema_version": 1, "specs": [spec.model_dump(mode="json")]}),
        encoding="utf-8",
    )

    registry = NodeRegistry.create_isolated()
    assert registry.load_declarative_catalog(catalog, allow_unverified=True) == 1
    metadata = registry.object_info(spec.identity.machine_id)
    inputs = metadata["input"]
    assert inputs["required"]["reads"] == ("FILE", {"multiple": True})
    assert inputs["optional"]["thresholds"] == (
        "JSON",
        {"default": [10, 20], "multiline": True},
    )
    assert inputs["optional"]["mode"] == (
        "STRING",
        {"default": "fast", "options": ["fast", "sensitive"]},
    )


def test_literal_secondary_file_patterns_stage_private_immutable_copies(tmp_path: Path) -> None:
    spec = _secondary_spec([".fai", "^.dict", "^.optional?"])
    reference = spec.cwl_reference
    assert reference is not None
    source = tmp_path / "source" / "reference.fa"
    source.parent.mkdir()
    source.write_text(">chr1\nACGT\n", encoding="utf-8")
    fai = source.with_name("reference.fa.fai")
    fai.write_text("chr1\t4\t6\t4\t5\n", encoding="utf-8")
    dictionary = source.with_name("reference.dict")
    dictionary.write_text("@SQ\tSN:chr1\tLN:4\n", encoding="utf-8")

    job, receipts = runtime._build_job(reference, {"genome": str(source)}, tmp_path / "stage")

    primary = Path(job["genome"]["path"])
    secondaries = job["genome"]["secondaryFiles"]
    assert {item["basename"] for item in secondaries} == {"reference.fa.fai", "reference.dict"}
    assert all(Path(item["path"]).parent == primary.parent for item in secondaries)
    assert all(Path(item["path"]).stat().st_mode & 0o222 == 0 for item in secondaries)
    assert source.read_text(encoding="utf-8") == ">chr1\nACGT\n"
    assert fai.read_text(encoding="utf-8") == "chr1\t4\t6\t4\t5\n"
    assert sum(receipt.get("role") == "secondary" for receipt in receipts) == 2


def test_dynamic_secondary_expression_requires_and_stages_explicit_metadata(tmp_path: Path) -> None:
    spec = _secondary_spec('$(self.basename+".fai")')
    reference = spec.cwl_reference
    assert reference is not None
    source = tmp_path / "reference.fa"
    source.write_text(">chr1\nACGT\n", encoding="utf-8")
    fai = tmp_path / "supplied-index"
    fai.write_text("chr1\t4\t6\t4\t5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="supply explicit File.secondaryFiles"):
        runtime._build_job(reference, {"genome": str(source)}, tmp_path / "missing-stage")

    job, _receipts = runtime._build_job(
        reference,
        {
            "genome": {
                "class": "File",
                "location": str(source),
                "secondaryFiles": [
                    {"class": "File", "location": str(fai), "basename": "reference.fa.fai"}
                ],
            }
        },
        tmp_path / "explicit-stage",
    )

    staged = job["genome"]["secondaryFiles"]
    assert staged[0]["basename"] == "reference.fa.fai"
    assert Path(staged[0]["path"]).read_text(encoding="utf-8") == fai.read_text(encoding="utf-8")


def test_missing_required_literal_secondary_file_fails_before_execution(tmp_path: Path) -> None:
    spec = _secondary_spec(".fai")
    reference = spec.cwl_reference
    assert reference is not None
    source = tmp_path / "reference.fa"
    source.write_text(">chr1\nACGT\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requires secondary file 'reference.fa.fai'"):
        runtime._build_job(reference, {"genome": str(source)}, tmp_path / "stage")


def test_output_publication_rejects_paths_outside_engine_output_and_symlinks(tmp_path: Path) -> None:
    spec = _secondary_spec(".fai")
    reference = spec.cwl_reference
    assert reference is not None
    outside = tmp_path / "host-secret.txt"
    outside.write_text("do not publish", encoding="utf-8")
    attempt = tmp_path / "attempt"
    (attempt / "engine-output").mkdir(parents=True)

    with pytest.raises(ValueError, match="outside the private engine output directory"):
        runtime._publish_outputs(
            reference,
            {"result": {"class": "File", "path": str(outside)}},
            attempt,
        )

    symlink_attempt = tmp_path / "symlink-attempt"
    engine_output = symlink_attempt / "engine-output"
    engine_output.mkdir(parents=True)
    link = engine_output / "result.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    with pytest.raises(ValueError, match="outside the private engine output directory|symbolic link"):
        runtime._publish_outputs(
            reference,
            {"result": {"class": "File", "path": str(link)}},
            symlink_attempt,
        )


def test_directory_inputs_and_nested_record_artifacts_are_staged_as_private_trees(tmp_path: Path) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {
            "reference": {"type": "Directory"},
            "record": {
                "type": [
                    "null",
                    {
                        "type": "record",
                        "name": "record",
                        "fields": {"annotation": {"type": "File"}},
                    },
                ]
            },
        },
        "outputs": {"result": {"type": "Directory"}},
    }
    spec = _capability_spec(document, node_id="generated_directory")
    reference = spec.cwl_reference
    assert reference is not None
    source_directory = tmp_path / "reference"
    source_directory.mkdir()
    (source_directory / "genome.fa").write_text(">chr1\nACGT\n", encoding="utf-8")
    annotation = tmp_path / "genes.gff"
    annotation.write_text("chr1\ttest\tgene\t1\t4\t.\t+\t.\tID=g1\n", encoding="utf-8")

    job, receipts = runtime._build_job(
        reference,
        {
            "reference": {"class": "Directory", "location": str(source_directory)},
            "record": {"annotation": {"class": "File", "location": str(annotation)}},
        },
        tmp_path / "stage",
    )

    staged_directory = Path(job["reference"]["path"])
    staged_annotation = Path(job["record"]["annotation"]["path"])
    assert staged_directory != source_directory
    assert (staged_directory / "genome.fa").read_text(encoding="utf-8") == ">chr1\nACGT\n"
    assert staged_annotation != annotation
    assert staged_annotation.read_bytes() == annotation.read_bytes()
    assert all(path.stat().st_mode & 0o222 == 0 for path in staged_directory.rglob("*"))
    assert any(receipt.get("role") == "nested_file" for receipt in receipts)


def test_directory_staging_and_publication_reject_symlinks(tmp_path: Path) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {"reference": {"type": "Directory"}},
        "outputs": {"result": {"type": "Directory"}},
    }
    spec = _capability_spec(document, node_id="generated_directory_symlink")
    reference = spec.cwl_reference
    assert reference is not None
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = source / "escape"
    try:
        link.symlink_to(outside)
    except OSError:
        return

    with pytest.raises(ValueError, match="contains a symbolic link"):
        runtime._build_job(reference, {"reference": str(source)}, tmp_path / "stage")

    attempt = tmp_path / "attempt"
    engine_directory = attempt / "engine-output" / "result"
    engine_directory.mkdir(parents=True)
    (engine_directory / "escape").symlink_to(outside)
    with pytest.raises(ValueError, match="contains a symbolic link"):
        runtime._publish_outputs(
            reference,
            {"result": {"class": "Directory", "path": str(engine_directory)}},
            attempt,
        )


def test_artifact_union_input_preserves_shape_and_output_normalizes_singleton(tmp_path: Path) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {"reads": {"type": ["File", {"type": "array", "items": "File"}]}},
        "outputs": {
            "alignments": {
                "type": ["File", {"type": "array", "items": "File"}],
                "outputBinding": {"glob": "*.bam"},
            }
        },
    }
    spec = _capability_spec(document, node_id="generated_artifact_union")
    reference = spec.cwl_reference
    assert reference is not None
    source = tmp_path / "reads.fastq"
    source.write_text("@r\nAC\n+\nII\n", encoding="utf-8")

    singleton_job, _ = runtime._build_job(
        reference,
        {"reads": {"class": "File", "location": str(source)}},
        tmp_path / "single-stage",
    )
    array_job, _ = runtime._build_job(
        reference,
        {"reads": [{"class": "File", "location": str(source)}]},
        tmp_path / "array-stage",
    )
    assert isinstance(singleton_job["reads"], dict)
    assert isinstance(array_job["reads"], list)
    assert Path(singleton_job["reads"]["path"]) != source

    attempt = tmp_path / "attempt-union"
    engine_output = attempt / "engine-output"
    engine_output.mkdir(parents=True)
    alignment = engine_output / "one.bam"
    alignment.write_bytes(b"BAM")
    receipts = runtime._publish_outputs(
        reference,
        {"alignments": {"class": "File", "path": str(alignment)}},
        attempt,
    )

    assert len(receipts) == 1
    assert (attempt / str(receipts[0]["published_path"])).read_bytes() == b"BAM"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name == "nt" or not os.environ.get("BIONODULO_CWLTOOL"),
    reason="real cwltool capability execution requires configured native Linux engine",
)
async def test_real_cwltool_executes_shell_requirement_and_preserves_python_bytecode_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "requirements": [{"class": "ShellCommandRequirement"}],
        "baseCommand": "seqtk",
        "inputs": {"message": {"type": "string", "inputBinding": {"position": 1}}},
        "stdout": "result.txt",
        "outputs": {"result": {"type": "stdout"}},
    }
    spec = _capability_spec(document, node_id="generated_shell")
    node = runtime.bind_cwl_reference_node(spec)
    engine = Path(os.environ["BIONODULO_CWLTOOL"])
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    primary = prefix / "bin" / "seqtk"
    primary.write_text('#!/bin/sh\nprintf "%s:%s\\n" "$PYTHONDONTWRITEBYTECODE" "$1"\n', encoding="utf-8")
    primary.chmod(0o755)

    async def verified(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "engine_path": str(engine),
            "engine_sha256": runtime._sha256_file(engine),
            "environment_prefix": str(prefix),
            "primary_executable": str(primary),
            "primary_executable_sha256": runtime._sha256_file(primary),
            "nodejs_path": None,
            "nodejs_sha256": None,
            "shell_path": str(Path("/bin/sh").resolve()),
            "shell_sha256": runtime._sha256_file(Path("/bin/sh").resolve()),
        }

    monkeypatch.setattr(runtime, "verify_reference_runtime", verified)
    context = SimpleNamespace(node_dir=tmp_path / "node", node_id="shell", run_metadata={}, executor=None)

    (result,) = await node().run(context=context, message="hello world")

    assert Path(result).read_text(encoding="utf-8") == "1:hello world\n"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name == "nt" or not os.environ.get("BIONODULO_CWLTOOL"),
    reason="real cwltool capability execution requires configured native Linux engine",
)
async def test_real_cwltool_stages_and_publishes_directory_trees(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {"source": {"type": "Directory", "inputBinding": {"position": 1}}},
        "outputs": {"result": {"type": "Directory", "outputBinding": {"glob": "result-dir"}}},
    }
    spec = _capability_spec(document, node_id="generated_directory_real")
    node = runtime.bind_cwl_reference_node(spec)
    engine = Path(os.environ["BIONODULO_CWLTOOL"])
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    primary = prefix / "bin" / "seqtk"
    primary.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, shutil, sys\n"
        "shutil.copytree(sys.argv[1], 'result-dir')\n"
        "pathlib.Path('result-dir/generated.txt').write_text('generated')\n",
        encoding="utf-8",
    )
    primary.chmod(0o755)
    source = tmp_path / "source"
    source.mkdir()
    (source / "input.txt").write_text("original", encoding="utf-8")

    async def verified(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "engine_path": str(engine),
            "engine_sha256": runtime._sha256_file(engine),
            "environment_prefix": str(prefix),
            "primary_executable": str(primary),
            "primary_executable_sha256": runtime._sha256_file(primary),
            "nodejs_path": None,
            "nodejs_sha256": None,
            "shell_path": None,
            "shell_sha256": None,
        }

    monkeypatch.setattr(runtime, "verify_reference_runtime", verified)
    context = SimpleNamespace(node_dir=tmp_path / "node", node_id="directory", run_metadata={}, executor=None)

    (result,) = await node().run(context=context, source=str(source))

    published = Path(result)
    assert published.is_dir()
    assert (published / "input.txt").read_text(encoding="utf-8") == "original"
    assert (published / "generated.txt").read_text(encoding="utf-8") == "generated"
    assert list(source.iterdir()) == [source / "input.txt"]
