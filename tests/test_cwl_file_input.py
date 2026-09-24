"""The CWL File input bridge preserves explicit metadata without inference."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes import cwl_reference_runtime as runtime
from bionodulo.nodes.builtin.input_family.cwl_file import CwlFileInputNode
from bionodulo.nodes.contract.cwl_reference import import_cwl_reference
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.execution.executor import WorkflowExecutor

from .nodes.test_cwl_reference_runtime import ENGINE_VERSION, _environment


FORMAT_URI = "http://edamontology.org/format_1929"


def test_cwl_file_input_requires_explicit_absolute_format_declaration() -> None:
    assert CwlFileInputNode.VALIDATE_INPUTS({"file": "reads.fa"}) is True
    assert CwlFileInputNode.VALIDATE_INPUTS(
        {"file": "reads.fa", "format_uri": FORMAT_URI}
    ) is True
    assert "absolute URI" in str(
        CwlFileInputNode.VALIDATE_INPUTS(
            {"file": "reads.fa", "format_uri": "FASTA"}
        )
    )
    assert "credential-free" in str(
        CwlFileInputNode.VALIDATE_INPUTS(
            {"file": "reads.fa", "format_uri": "https://user@example.org/format"}
        )
    )
    assert "CWL File object" in str(
        CwlFileInputNode.VALIDATE_INPUTS(
            {"file": "reads.fa", "secondary_files": '[{"location":"reads.fa.fai"}]'}
        )
    )


@pytest.mark.asyncio
async def test_cwl_file_input_stages_primary_and_explicit_secondary_files(tmp_path: Path) -> None:
    source = tmp_path / "source" / "reference.fa"
    source.parent.mkdir()
    source.write_text(">chr1\nACGT\n", encoding="utf-8")
    index = source.with_name("reference.fa.fai")
    index.write_text("chr1\t4\t6\t4\t5\n", encoding="utf-8")
    context = SimpleNamespace(
        node_dir=tmp_path / "node",
        workspace_dir=tmp_path,
        node_id="cwl-source",
        run_metadata={},
    )

    result = await CwlFileInputNode().run(
        file=str(source),
        format_uri=FORMAT_URI,
        secondary_files=json.dumps(
            [
                {
                    "class": "File",
                    "location": str(index),
                    "basename": "reference.fa.fai",
                    "format": "http://edamontology.org/format_2330",
                }
            ]
        ),
        context=context,
    )

    value = result["outputs"]["file"]
    assert value["class"] == "File"
    assert value["format"] == FORMAT_URI
    assert Path(value["location"]).read_bytes() == source.read_bytes()
    assert Path(value["location"]) != source
    assert len(value["secondaryFiles"]) == 1
    secondary = value["secondaryFiles"][0]
    assert secondary["basename"] == "reference.fa.fai"
    assert Path(secondary["location"]).read_bytes() == index.read_bytes()
    assert Path(secondary["location"]) != index
    assert context.run_metadata["cwl_file_inputs"]["cwl-source"] == {
        "format_uri": FORMAT_URI,
        "format_semantics": "user_declaration_not_content_validation",
        "secondary_file_count": 1,
    }


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name == "nt" or not os.environ.get("BIONODULO_CWLTOOL"),
    reason="real cwltool format validation requires configured native Linux engine",
)
async def test_real_cwltool_accepts_explicit_format_from_cwl_file_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "seqtk",
        "inputs": {
            "source": {
                "type": "File",
                "format": FORMAT_URI,
                "inputBinding": {"position": 1},
            }
        },
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    spec = import_cwl_reference(
        json.dumps(document, separators=(",", ":")),
        node_id="generated_format_bridge",
        source_uri="https://example.org/format-bridge.cwl",
        biotools_accession="seqtk",
        biotools_uri="https://bio.tools/seqtk",
        environment=_environment(),
        primary_package="seqtk",
        primary_package_version="1.4",
        engine_version=ENGINE_VERSION,
    )
    node = runtime.bind_cwl_reference_node(spec)
    input_options = node.INPUT_TYPES()["required"]["source"][1]
    assert input_options["cwl_formats"] == [FORMAT_URI]
    assert "Connect CWL File Input" in input_options["description"]
    source = tmp_path / "transcripts.fa"
    source.write_text(">one\nACGT\n", encoding="utf-8")
    engine = Path(os.environ["BIONODULO_CWLTOOL"])
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    primary = prefix / "bin" / "seqtk"
    primary.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "pathlib.Path('result.txt').write_text(pathlib.Path(sys.argv[1]).read_text())\n",
        encoding="utf-8",
    )
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
            "shell_path": None,
            "shell_sha256": None,
        }

    monkeypatch.setattr(runtime, "verify_reference_runtime", verified)
    registry = NodeRegistry.create_isolated()
    registry.register(CwlFileInputNode)
    registry.register(node)
    executor = WorkflowExecutor(
        workspace_dir=tmp_path / "app",
        cache_dir=tmp_path / "cache",
        registry=registry,
        settings=SimpleNamespace(
            execution=SimpleNamespace(
                max_workers=1,
                env_isolation="off",
                content_hashing="strong",
                timeout_seconds=60,
            ),
            api_secrets={},
        ),
    )
    workflow = {
        "nodes": [
            {
                "id": "input",
                "type": CwlFileInputNode.NODE_ID,
                "params": {"file": str(source), "format_uri": FORMAT_URI},
            },
            {"id": "tool", "type": node.NODE_ID, "params": {}},
        ],
        "edges": [
            {
                "source_node": "input",
                "source_output": "file",
                "target_node": "tool",
                "target_input": "source",
            }
        ],
    }
    try:
        result = await executor.execute("format-edge", workflow)
    finally:
        executor.cache.close()

    assert result["status"] == "completed", result
    bridge_value = result["node_results"]["input"]["outputs"]["file"]
    assert bridge_value["format"] == FORMAT_URI
    assert Path(bridge_value["location"]).is_file()
    output = Path(result["node_results"]["tool"]["outputs"]["result"])
    assert output.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
