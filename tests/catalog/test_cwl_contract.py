from __future__ import annotations

import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.compiler import CatalogCompiler
from bionodulo.nodes.contract.cwl import (
    CwlImportError,
    CwlInputBinding,
    CwlInputKind,
    CwlInvocation,
    CwlLiteralArgument,
    DECLARATIVE_CWL_FACTORY,
    import_cwl,
)
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutableProbe,
    ExecutionPlatform,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.outputs import StdoutCollector


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
PLATFORM = ExecutionPlatform.LINUX_AMD64


def test_catalog_artifacts_can_be_imported_first_in_a_fresh_interpreter() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import bionodulo.nodes.catalog.artifacts; import bionodulo.nodes.contract.cwl",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def locked_environment(tool_id: str = "coreutils", tool_version: str = "9.5") -> PixiEnvironment:
    """Synthetic contract fixture; it is never presented as execution evidence."""

    artifact = CondaLockedArtifact(
        kind="conda",
        name=tool_id,
        version=tool_version,
        build="test_0",
        filename=f"{tool_id}-{tool_version}-test_0.conda",
        url=f"https://packages.example.org/linux-64/{tool_id}-{tool_version}-test_0.conda",
        sha256=SHA_B,
        size_bytes=1024,
    )
    lock = PlatformLock(
        platform=PLATFORM,
        environment_name=f"{tool_id}-runtime",
        resolver_platform="linux-64",
        resolver=ResolverIdentity(name="pixi", version="0.68.1", config_digest=SHA_A),
        native_lock_sha256=SHA_C,
        artifacts=(artifact,),
    )
    return PixiEnvironment(
        environment_id=f"{tool_id}-runtime",
        platforms=(PLATFORM,),
        packages=(f"{tool_id}=={tool_version}",),
        locks=(lock,),
        executable_probes=tuple(
            ExecutableProbe(
                probe_id=f"{executable}-version",
                locator=f"bin/{executable}",
                version_arguments=("--version",),
                version_line_prefix=f"{executable} (fixture) ",
                expected_version=tool_version,
                fingerprint=SHA_A,
            )
            for executable in ("cat", "printf", "sort")
        ),
    )


def cat_document() -> dict[str, object]:
    # Shape retained from the standard CWL cat example: stdout is also exposed
    # as a File output whose glob names the redirected stdout path.
    return {
        "class": "CommandLineTool",
        "cwlVersion": "v1.2",
        "doc": "Print the contents of a file to stdout using 'cat'.",
        "inputs": {
            "file1": {
                "type": "File",
                "label": "Input File",
                "doc": "The file that will be copied using 'cat'",
                "inputBinding": {"position": 1},
            }
        },
        "outputs": {
            "output_file": {
                "type": "File",
                "outputBinding": {"glob": "output.txt"},
            }
        },
        "baseCommand": "cat",
        "stdout": "output.txt",
    }


def import_cat(document: dict[str, object] | None = None):
    return import_cwl(
        dict(cat_document() if document is None else document),
        node_id="cwl_cat",
        environment=locked_environment(),
        tool_id="coreutils",
        tool_version="9.5",
        source_uri="https://example.org/cwl/cat3-nodocker.cwl",
    )


def test_imports_standard_map_form_stdout_file_without_per_tool_factory() -> None:
    spec = import_cat()

    assert spec.execution_factory == DECLARATIVE_CWL_FACTORY
    assert spec.evidence is None
    assert spec.maturity is None
    assert spec.identity.machine_id == "cwl_cat"
    assert spec.cwl_invocation is not None
    assert spec.cwl_invocation.base_command == ("cat",)
    assert spec.cwl_invocation.input_bindings == (
        CwlInputBinding(
            input_id="file1",
            kind=CwlInputKind.FILE,
            required=True,
            position=1,
        ),
    )
    assert isinstance(spec.outputs[0].collector, StdoutCollector)
    assert spec.outputs[0].collector.relative_path == "output.txt"
    assert spec.outputs[0].require_nonempty is False


def test_imports_list_form_flags_and_keeps_unbound_optional_parameter_out_of_argv() -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": ["sort"],
        "inputs": [
            {
                "id": "reverse",
                "type": "boolean",
                "inputBinding": {"position": 1, "prefix": "-r"},
            },
            {"id": "input", "type": "File", "inputBinding": {"position": 2}},
            {"id": "name", "type": "string?"},
        ],
        "stdout": "output.txt",
        "outputs": [
            {"id": "output", "type": "File", "outputBinding": {"glob": "output.txt"}},
        ],
    }

    spec = import_cat(document)
    assert [binding.input_id for binding in spec.cwl_invocation.input_bindings] == ["reverse", "input"]
    assert [parameter.parameter_id for parameter in spec.parameters] == ["name", "reverse"]
    assert spec.parameters[0].required is False
    assert spec.parameters[0].has_default is False


def test_imports_scalar_defaults_and_literal_arguments_in_canonical_position_order() -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "printf",
        "arguments": [{"valueFrom": "literal", "position": 1}],
        "inputs": {
            "count": {
                "type": "int?",
                "default": 2,
                "inputBinding": {"position": 2, "prefix": "--count"},
            },
            "ratio": {
                "type": "float?",
                "default": 0.5,
                "inputBinding": {"position": 3, "prefix": "--ratio"},
            },
        },
        "outputs": {"out": {"type": "stdout"}},
        "stdout": "out.txt",
    }
    spec = import_cat(document)

    assert spec.cwl_invocation.literal_arguments == (CwlLiteralArgument(value="literal", position=1),)
    assert [parameter.default for parameter in spec.parameters] == [2, 0.5]


def test_imports_optional_union_in_either_cwl_order() -> None:
    document = cat_document()
    document["inputs"] = {
        "first": {"type": ["null", "string"]},
        "second": {"type": ["string", "null"]},
    }

    spec = import_cat(document)

    assert [parameter.parameter_id for parameter in spec.parameters] == ["first", "second"]
    assert all(parameter.required is False for parameter in spec.parameters)


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"class": "Workflow"}, "CommandLineTool only"),
        ({"requirements": [{"class": "ShellCommandRequirement"}]}, "unsupported field"),
        ({"stdin": "input.txt"}, "unsupported field"),
        ({"stderr": "error.txt"}, "unsupported field"),
    ],
)
def test_rejects_unsupported_top_level_semantics(update: dict[str, object], message: str) -> None:
    document = cat_document()
    document.update(update)
    with pytest.raises(CwlImportError, match=message):
        import_cat(document)


def test_rejects_expressions_shell_joining_and_ambiguous_positions() -> None:
    expression = cat_document()
    expression["arguments"] = [{"valueFrom": "$(inputs.file1.path)", "position": 2}]
    with pytest.raises(CwlImportError, match="expressions are unsupported"):
        import_cat(expression)

    joined = cat_document()
    joined["inputs"]["file1"]["inputBinding"]["separate"] = False  # type: ignore[index]
    with pytest.raises(CwlImportError, match="separate=false"):
        import_cat(joined)

    duplicate = cat_document()
    duplicate["arguments"] = [{"valueFrom": "literal", "position": 1}]
    with pytest.raises(CwlImportError, match="positions must be unique"):
        import_cat(duplicate)

    multiple_outputs = cat_document()
    multiple_outputs["outputs"]["second"] = {  # type: ignore[index]
        "type": "File",
        "outputBinding": {"glob": "second.txt"},
    }
    with pytest.raises(CwlImportError, match="exactly one output"):
        import_cat(multiple_outputs)


@pytest.mark.parametrize("input_id", ["context", "output_dir"])
def test_rejects_adapter_reserved_input_ids_during_import_and_model_validation(input_id: str) -> None:
    document = cat_document()
    document["inputs"] = {input_id: {"type": "string"}}
    with pytest.raises(CwlImportError, match="reserved by the execution adapter"):
        import_cat(document)

    valid_document = cat_document()
    valid_document["inputs"] = {"safe": {"type": "string"}}
    payload = import_cat(valid_document).model_dump(mode="python")
    payload["parameters"][0]["parameter_id"] = input_id
    with pytest.raises(ValidationError, match="reserved by the execution adapter"):
        NodeSpec.model_validate(payload)


def test_probe_fallback_matches_base_command_name_and_rejects_ambiguity() -> None:
    probe = ExecutableProbe(
        probe_id="echo-version",
        locator="bin/echo",
        version_arguments=("--version",),
        version_line_prefix="echo (GNU coreutils) ",
        expected_version="9.5",
        fingerprint=SHA_A,
    )
    environment = locked_environment().model_copy(update={"executable_probes": (probe,)})
    spec = import_cwl(
        {
            "cwlVersion": "v1.2",
            "class": "CommandLineTool",
            "baseCommand": "echo",
            "inputs": {"message": {"type": "string", "inputBinding": {"position": 1}}},
            "outputs": {"out": {"type": "stdout"}},
            "stdout": "out.txt",
        },
        node_id="echo_probe",
        environment=environment,
        tool_id="echo",
        tool_version="9.5",
        source_uri="https://example.org/echo.cwl",
    )
    assert spec.runtime_binding.probe_id == "echo-version"

    second_probe = probe.model_copy(update={"probe_id": "echo-version-duplicate"})
    ambiguous = environment.model_copy(update={"executable_probes": (probe, second_probe)})
    with pytest.raises(CwlImportError, match="ambiguous executable probes"):
        import_cwl(
            {
                "cwlVersion": "v1.2",
                "class": "CommandLineTool",
                "baseCommand": "echo",
                "inputs": {},
                "outputs": {"out": {"type": "stdout"}},
                "stdout": "out.txt",
            },
            node_id="ambiguous_echo_probe",
            environment=ambiguous,
            tool_id="echo",
            tool_version="9.5",
            source_uri="https://example.org/echo.cwl",
        )


def test_package_binding_still_requires_exact_fingerprinted_command_probe() -> None:
    environment = locked_environment()
    cat_probe = next(probe for probe in environment.executable_probes if probe.probe_id == "cat-version")
    missing_fingerprint = environment.model_copy(
        update={"executable_probes": (cat_probe.model_copy(update={"fingerprint": None}),)}
    )
    with pytest.raises(CwlImportError, match="must declare a binary fingerprint"):
        import_cwl(
            cat_document(),
            node_id="cat_without_fingerprint",
            environment=missing_fingerprint,
            tool_id="coreutils",
            tool_version="9.5",
            source_uri="https://example.org/cat.cwl",
        )

    wrong_version = environment.model_copy(
        update={"executable_probes": (cat_probe.model_copy(update={"expected_version": "9.4"}),)}
    )
    with pytest.raises(CwlImportError, match="exactly one executable probe"):
        import_cwl(
            cat_document(),
            node_id="cat_wrong_probe_version",
            environment=wrong_version,
            tool_id="coreutils",
            tool_version="9.5",
            source_uri="https://example.org/cat.cwl",
        )


def test_descriptor_digest_and_contract_digest_change_with_original_document() -> None:
    first = import_cat()
    changed_document = cat_document()
    changed_document["doc"] = "A changed upstream description."
    second = import_cat(changed_document)

    assert first.cwl_invocation.descriptor_sha256 != second.cwl_invocation.descriptor_sha256
    assert first.contract_digest() != second.contract_digest()
    assert json.dumps(first.contract_projection(), sort_keys=True) != json.dumps(
        second.contract_projection(), sort_keys=True
    )


def test_retains_exact_raw_source_receipt_separately_from_canonical_descriptor_digest() -> None:
    spec = import_cwl(
        cat_document(),
        node_id="cwl_cat",
        environment=locked_environment(),
        tool_id="coreutils",
        tool_version="9.5",
        source_uri="https://example.org/cwl/cat3-nodocker.cwl",
        source_content_sha256=SHA_A,
        source_size_bytes=731,
    )

    assert spec.cwl_invocation.source_content_sha256 == SHA_A
    assert spec.cwl_invocation.source_size_bytes == 731
    assert spec.cwl_invocation.descriptor_sha256 != SHA_A


@pytest.mark.parametrize(
    "source_fields",
    [
        {"source_content_sha256": SHA_A},
        {"source_size_bytes": 731},
        {"source_content_sha256": "sha256:not-a-digest", "source_size_bytes": 731},
        {"source_content_sha256": SHA_A, "source_size_bytes": -1},
    ],
)
def test_rejects_incomplete_or_malformed_raw_source_receipts(source_fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CwlInvocation(
            source_uri="https://example.org/tool.cwl",
            descriptor_sha256=SHA_B,
            base_command=("tool",),
            **source_fields,
        )


def test_cwl_model_rejects_position_ties_across_inputs_and_literals() -> None:
    with pytest.raises(ValidationError, match="positions must be unique"):
        CwlInvocation(
            source_uri="https://example.org/tool.cwl",
            descriptor_sha256=SHA_A,
            base_command=("tool",),
            input_bindings=(
                CwlInputBinding(
                    input_id="value",
                    kind=CwlInputKind.STRING,
                    required=True,
                    position=1,
                ),
            ),
            literal_arguments=(CwlLiteralArgument(value="fixed", position=1),),
        )


def test_compiler_emits_full_runtime_descriptor_only_for_imported_specs() -> None:
    spec = import_cat()
    compiled = CatalogCompiler().compile((spec,))
    runtime = compiled.runtime["nodes"][spec.identity.stable_id]

    assert runtime["execution_factory"] == DECLARATIVE_CWL_FACTORY
    assert runtime["runtime_descriptor"] == {
        "kind": "cwl_v1_2_command_line_tool",
        "invocation": spec.cwl_invocation.model_dump(mode="json", round_trip=True),
        "artifact_inputs": [item.model_dump(mode="json", round_trip=True) for item in spec.artifact_inputs],
        "parameters": [item.model_dump(mode="json", round_trip=True) for item in spec.parameters],
        "outputs": [item.model_dump(mode="json", round_trip=True) for item in spec.outputs],
        "environment": spec.environment.model_dump(mode="json", round_trip=True),
        "runtime_binding": spec.runtime_binding.model_dump(mode="json", round_trip=True),
    }
