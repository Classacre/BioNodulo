import json
import zlib
from pathlib import Path

from bionodulo.core.config import Settings
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.provenance.workflow_embed import embed_workflow, extract_workflow
from bionodulo.workflow.export import export_workflow
from bionodulo.workflow.schema import Workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


def test_vcf_header_embedding_and_extraction(tmp_path: Path):
    workflow = Workflow.model_validate({"name": "prov", "nodes": [{"id": "input", "type": "input_file"}]})
    path = tmp_path / "result.vcf"
    path.write_text("##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n", encoding="utf-8")

    embed_workflow(path, workflow.model_dump_json())
    extracted = extract_workflow(path)

    assert extracted["source"] == "header"
    assert extracted["workflow"]["name"] == "prov"


def test_sidecar_embedding_for_generic_file(tmp_path: Path):
    workflow = Workflow.model_validate({"name": "sidecar"})
    path = tmp_path / "table.tsv"
    path.write_text("a\tb\n", encoding="utf-8")

    result = embed_workflow(path, workflow.model_dump_json())
    extracted = extract_workflow(path)

    assert result["mode"] == "sidecar"
    assert extracted["workflow"]["name"] == "sidecar"


def test_png_workflow_metadata_extraction(tmp_path: Path):
    workflow = {"version": "0.1.0", "name": "png", "nodes": [{"id": "input", "type": "input_file"}], "edges": []}
    metadata = b"workflow\x00" + json.dumps(workflow).encode("utf-8")
    path = tmp_path / "workflow.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00")
        + _png_chunk(b"tEXt", metadata)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + _png_chunk(b"IEND", b"")
    )

    extracted = extract_workflow(path)

    assert extracted["source"] == "png_metadata"
    assert extracted["workflow"]["name"] == "png"


def test_snakemake_export_returns_content_and_warnings():
    workflow = Workflow.model_validate({"nodes": [{"id": "input", "type": "input_file"}]})
    result = export_workflow(workflow, registry(), "snakemake")

    assert result["filename"] == "Snakefile"
    assert "rule all" in result["content"]
    assert result["warnings"]


def test_config_file_and_env_defaults(tmp_path: Path, monkeypatch):
    config = tmp_path / "bionodulo.yaml"
    config.write_text(
        """
project_root: .
runs_dir: my_runs
cache_dir: my_cache
custom_nodes_dir: my_nodes
data_roots:
  - data
registries:
  - registry.json
execution:
  strong_hashing: true
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BIONODULO_SECRET_NCBI", "token")

    settings = Settings.from_env(config)

    assert settings.runs_dir == (tmp_path / "my_runs").resolve()
    assert settings.api_secrets["ncbi"] == "token"
    assert settings.execution["strong_hashing"] is True


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + kind + data + checksum.to_bytes(4, "big")
