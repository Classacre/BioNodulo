from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.artifacts import ArtifactContainer, Cardinality
from bionodulo.nodes.contract.compiler import CatalogCompiler
from bionodulo.nodes.contract.cwl_reference import (
    CWL_REFERENCE_FACTORY,
    CwlReferenceContract,
    CwlReferenceImportError,
    import_cwl_reference,
    inspect_reference_document,
)
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.parameters import ValueKind


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
ENGINE_VERSION = "3.1.20250715140722"


def locked_environment() -> PixiEnvironment:
    artifacts = tuple(
        CondaLockedArtifact(
            kind="conda",
            name=name,
            version=version,
            build="test_0",
            filename=f"{name}-{version}-test_0.conda",
            url=f"https://packages.example.org/linux-64/{name}-{version}-test_0.conda",
            sha256=digest,
            size_bytes=1024,
        )
        for name, version, digest in (("seqtk", "1.4", SHA_B),)
    )
    lock = PlatformLock(
        platform=ExecutionPlatform.LINUX_AMD64,
        environment_name="reference-runtime",
        resolver_platform="linux-64",
        resolver=ResolverIdentity(name="pixi", version="0.68.1", config_digest=SHA_C),
        native_lock_sha256=SHA_C,
        artifacts=artifacts,
    )
    return PixiEnvironment(
        environment_id="reference-runtime",
        platforms=(ExecutionPlatform.LINUX_AMD64,),
        packages=("seqtk==1.4",),
        locks=(lock,),
    )


def reference_document() -> dict[str, object]:
    return {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "label": "Generated sequence tool",
        "baseCommand": "seqtk",
        "requirements": [{"class": "InlineJavascriptRequirement"}],
        "hints": [
            {"class": "DockerRequirement", "dockerPull": "example/seqtk:1.4"},
            {"class": "ResourceRequirement", "ramMin": 512},
        ],
        "inputs": {
            "reads": {"type": {"type": "array", "items": "File"}},
            "mode": {
                "type": {"type": "enum", "symbols": ["fast", "sensitive"]},
                "default": "fast",
            },
            "threshold": {"type": ["null", "double"]},
            "labels": {"type": {"type": "array", "items": "string"}, "default": []},
        },
        "outputs": {
            "primary": {"type": "File", "outputBinding": {"glob": "primary.txt"}},
            "reports": {
                "type": {"type": "array", "items": "File"},
                "outputBinding": {"glob": "*.report"},
            },
        },
    }


def import_reference(document: dict[str, object] | None = None):
    source = json.dumps(reference_document() if document is None else document, separators=(",", ":"))
    return import_cwl_reference(
        source,
        node_id="generated_seqtk",
        source_uri="https://example.org/tools/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=locked_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )


@pytest.mark.parametrize("version", ["v1.0", "v1.1", "v1.2"])
def test_inspection_projects_file_arrays_enums_json_arrays_and_multiple_outputs(version: str) -> None:
    document = reference_document()
    document["cwlVersion"] = version
    inspection = inspect_reference_document(document)

    assert inspection.cwl_version == version
    assert inspection.artifact_inputs[0].port_id == "reads"
    assert inspection.artifact_inputs[0].cardinality is Cardinality.MANY
    parameters = {parameter.parameter_id: parameter for parameter in inspection.parameters}
    assert parameters["mode"].kind is ValueKind.STRING
    assert parameters["mode"].choices == ("fast", "sensitive")
    assert parameters["labels"].kind is ValueKind.JSON
    assert parameters["threshold"].required is False
    outputs = {output.port_id: output for output in inspection.outputs}
    assert outputs["primary"].cardinality is Cardinality.ONE
    assert outputs["primary"].collector.pattern == "published/primary/*"
    assert outputs["reports"].cardinality is Cardinality.MANY
    assert outputs["reports"].collector.maximum == 4096
    assert inspection.docker_hint_present is True
    assert inspection.unfulfilled_hints == ("DockerRequirement", "ResourceRequirement")


def test_import_retains_exact_source_and_biotools_identity_without_release_evidence() -> None:
    document = reference_document()
    source = json.dumps(document, indent=2) + "\n"
    spec = import_cwl_reference(
        source.encode("utf-8"),
        node_id="generated_seqtk",
        source_uri="https://example.org/tools/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=locked_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )

    assert spec.execution_factory == CWL_REFERENCE_FACTORY
    assert spec.cwl_reference.source_text == source
    assert spec.cwl_reference.source_size_bytes == len(source.encode("utf-8"))
    assert spec.cwl_reference.biotools_accession == "seqtk"
    assert spec.cwl_reference.biotools_uri == "https://bio.tools/seqtk"
    assert spec.runtime_binding.package_name == "seqtk"
    assert spec.evidence is None
    assert spec.maturity is None

    runtime = CatalogCompiler().compile((spec,)).runtime["nodes"][spec.identity.stable_id]
    assert runtime["runtime_descriptor"]["kind"] == "cwl_reference_command_line_tool"
    assert runtime["runtime_descriptor"]["reference"]["source_text"] == source


def test_multiline_upstream_prose_is_bounded_for_ui_without_changing_source() -> None:
    document = reference_document()
    document["label"] = "  Sequence\n tool  "
    document["doc"] = "First line.\nSecond line.\n" + "x" * 3000 + "\n"
    source = json.dumps(document, indent=2) + "\n"
    spec = import_cwl_reference(
        source,
        node_id="generated_seqtk_prose",
        source_uri="https://example.org/tools/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=locked_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )

    assert spec.presentation.display_name == "Sequence tool"
    assert spec.presentation.description.startswith("First line. Second line.")
    assert len(spec.presentation.description) == 2048
    assert spec.cwl_reference.source_text == source


def test_unlabelled_descriptor_uses_decoded_source_filename_not_machine_id() -> None:
    document = reference_document()
    document.pop("label")
    source = json.dumps(document)
    spec = import_cwl_reference(
        source,
        node_id="auto_bedtools_bedtools_bamtobed_1_89acbdd4",
        source_uri="https://example.org/bedtools/bedtools_bamtobed%201.cwl",
        biotools_accession="bedtools",
        biotools_uri="https://bio.tools/bedtools",
        environment=locked_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )

    assert spec.presentation.display_name == "Bedtools Bamtobed 1"
    assert spec.identity.machine_id == "auto_bedtools_bedtools_bamtobed_1_89acbdd4"
    assert spec.cwl_reference.source_text == source


@pytest.mark.parametrize(
    "requirement",
    ["DockerRequirement", "ResourceRequirement", "NetworkAccess"],
)
def test_rejects_native_requirements_that_cannot_be_honored(requirement: str) -> None:
    document = reference_document()
    document["requirements"] = [{"class": requirement}]
    with pytest.raises(CwlReferenceImportError, match="cannot honor required"):
        inspect_reference_document(document)


def test_admits_shell_and_directory_inputs_outputs() -> None:
    document = reference_document()
    document["requirements"] = [{"class": "ShellCommandRequirement"}]
    document["inputs"] = {
        "reference": {"type": "Directory"},
        "optional_directories": {"type": ["null", {"type": "array", "items": "Directory"}]},
    }
    document["outputs"] = {
        "result": {"type": "Directory"},
        "reports": {"type": {"type": "array", "items": "Directory"}},
    }

    inspection = inspect_reference_document(document)

    inputs = {item.port_id: item for item in inspection.artifact_inputs}
    assert inputs["reference"].artifact_type == "artifact.directory"
    assert inputs["reference"].cardinality is Cardinality.ONE
    assert inputs["optional_directories"].cardinality is Cardinality.MANY
    outputs = {item.port_id: item for item in inspection.outputs}
    assert outputs["result"].artifact_type == "artifact.directory"
    assert outputs["result"].collector.container is ArtifactContainer.DIRECTORY
    assert outputs["reports"].cardinality is Cardinality.MANY
    assert "ShellCommandRequirement" not in inspection.unfulfilled_hints


def test_normalizes_file_or_file_array_output_union_to_many() -> None:
    document = reference_document()
    document["outputs"] = {
        "alignments": {"type": ["File", {"type": "array", "items": "File"}]},
    }

    inspection = inspect_reference_document(document)

    assert inspection.output_mappings[0].kind == "file"
    assert inspection.output_mappings[0].array is True
    assert inspection.outputs[0].cardinality is Cardinality.MANY
    assert inspection.outputs[0].collector.minimum == 0


def test_preserves_file_or_file_array_input_union_as_json() -> None:
    document = reference_document()
    document["inputs"] = {
        "reads": {"type": ["File", {"type": "array", "items": "File"}]},
    }

    inspection = inspect_reference_document(document)

    assert inspection.artifact_inputs == ()
    assert inspection.parameters[0].kind is ValueKind.JSON
    assert inspection.input_mappings[0].kind == "json"
    assert inspection.input_mappings[0].array is False


def test_projects_record_and_record_union_inputs_as_json() -> None:
    document = reference_document()
    document["inputs"] = {
        "genome": {
            "type": [
                "null",
                {
                    "type": "record",
                    "name": "genome",
                    "fields": {"fasta": {"type": "File"}, "index": {"type": "Directory"}},
                },
            ]
        },
        "strand": {
            "type": [
                "null",
                {"type": "record", "name": "forward", "fields": {"forward": "boolean"}},
                {"type": "record", "name": "reverse", "fields": {"reverse": "boolean"}},
            ]
        },
    }

    inspection = inspect_reference_document(document)

    parameters = {item.parameter_id: item for item in inspection.parameters}
    assert parameters["genome"].kind is ValueKind.JSON
    assert parameters["genome"].required is False
    assert parameters["strand"].kind is ValueKind.JSON
    assert all(item.kind == "json" for item in inspection.input_mappings)


@pytest.mark.parametrize("output_type,kind", [("string", "string"), ("int", "integer"), ("float", "number"), ("boolean", "boolean")])
def test_scalar_outputs_project_to_json_artifacts(output_type: object, kind: str) -> None:
    document = reference_document()
    document["outputs"] = {"value": {"type": output_type}}
    inspection = inspect_reference_document(document)
    assert inspection.outputs[0].artifact_type == "artifact.file"
    assert inspection.output_mappings[0].kind == kind


def test_rejects_external_includes_and_duplicate_yaml_keys() -> None:
    document = reference_document()
    document["inputs"] = {"reads": {"$import": "inputs.yml"}}
    with pytest.raises(CwlReferenceImportError, match=r"rejects \$import"):
        inspect_reference_document(document)

    duplicate = """cwlVersion: v1.2
class: CommandLineTool
baseCommand: seqtk
inputs: {}
inputs: {}
outputs:
  out: File
"""
    with pytest.raises(CwlReferenceImportError, match="duplicate mapping key"):
        import_cwl_reference(
            duplicate,
            node_id="duplicate",
            source_uri="https://example.org/duplicate.cwl",
            biotools_accession="seqtk",
            biotools_uri="https://bio.tools/seqtk",
            environment=locked_environment(),
            primary_package="seqtk",
            primary_package_version="1.4",
            engine_version=ENGINE_VERSION,
        )


def test_top_level_https_schemas_are_retained_but_explicitly_unfulfilled() -> None:
    document = reference_document()
    document["$schemas"] = ["https://example.org/formats/edam.ttl"]
    inspection = inspect_reference_document(document)
    assert "external_schema_not_loaded" in inspection.unfulfilled_hints

    source = json.dumps(document)
    spec = import_cwl_reference(
        source,
        node_id="generated_seqtk_schema",
        source_uri="https://example.org/tools/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=locked_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )
    assert spec.cwl_reference.source_text == source
    assert "external_schema_not_loaded" in spec.cwl_reference.unfulfilled_hints

    for invalid in ("http://example.org/schema", "relative-schema.yml", ["https://example.org/#fragment"]):
        invalid_document = reference_document()
        invalid_document["$schemas"] = invalid if isinstance(invalid, list) else [invalid]
        with pytest.raises(CwlReferenceImportError, match=r"\$schemas"):
            inspect_reference_document(invalid_document)


def test_tool_environment_is_independent_from_pinned_reference_engine() -> None:
    environment = locked_environment()
    source = json.dumps(reference_document())
    spec = import_cwl_reference(
        source,
        node_id="generated_seqtk",
        source_uri="https://example.org/tools/seqtk.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=environment,
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )
    assert all(package.name != "cwltool" for package in spec.environment.packages)
    assert spec.cwl_reference.engine_version == ENGINE_VERSION


def test_reference_contract_rejects_source_digest_or_size_drift() -> None:
    spec = import_reference()
    payload = spec.cwl_reference.model_dump(mode="python")
    payload["source_size_bytes"] += 1
    with pytest.raises(ValidationError, match="byte count"):
        CwlReferenceContract.model_validate(payload)


def test_nodespec_revalidation_rejects_engine_lock_and_parameter_projection_drift() -> None:
    payload = import_reference().model_dump(mode="python")
    payload["cwl_reference"]["engine_version"] = ">=0.0.0"
    with pytest.raises(ValidationError, match="exact version"):
        NodeSpec.model_validate(payload)

    payload = import_reference().model_dump(mode="python")
    threshold_parameter = next(item for item in payload["parameters"] if item["parameter_id"] == "threshold")
    threshold_parameter["kind"] = ValueKind.BOOLEAN
    with pytest.raises(ValidationError, match="inconsistent parameter kind"):
        NodeSpec.model_validate(payload)
