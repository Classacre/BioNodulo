from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.inputs import (
    InputDirectoryNode,
    InputFASTANode,
    InputFASTQNode,
    InputFileNode,
    InputGFFNode,
    InputVCFNode,
    SampleSheetNode,
)


def test_input_node_schemas_are_preserved() -> None:
    assert InputFASTQNode.RETURN_TYPES == ("FASTQ_LIST", "FASTQ", "FASTQ")
    assert InputFASTQNode.RETURN_NAMES == ("reads", "read1", "read2")
    assert InputFASTQNode.INPUT_TYPES() == {
        "required": {
            "reads": ("FASTQ_LIST", {
                "description": "Path(s) or URL(s) to FASTQ file(s). For paired-end, provide two. URLs (http/https/ftp) are downloaded to the workspace cache on first run.",
            }),
        },
        "optional": {
            "sample_name": ("STRING", {"default": "sample"}),
        },
        "hidden": {},
    }
    assert InputFASTANode.INPUT_TYPES() == {
        "required": {"reference": ("FASTA", {"description": "Local path, URL, or NCBI accession for the FASTA. With source=auto, http(s)/ftp URLs are downloaded (gzip auto-decompressed) and everything else is a local path."})},
        "optional": {"source": ("STRING", {
            "default": "auto",
            "options": ["auto", "local", "url", "ncbi"],
            "description": "How to interpret the value: auto (URL or local), local file, URL download, or NCBI accession (efetch).",
        })},
        "hidden": {"file_path": ("STRING", {"description": "Alias for reference (backward compatibility)"})},
    }
    assert InputFileNode.INPUT_TYPES() == {
        "required": {"file": ("FILE", {"description": "Local path, URL, or NCBI accession for the file. With source=auto, http(s)/ftp URLs are downloaded (gzip auto-decompressed) and everything else is a local path."})},
        "optional": {"source": ("STRING", {
            "default": "auto",
            "options": ["auto", "local", "url", "ncbi"],
            "description": "How to interpret the value: auto (URL or local), local file, URL download, or NCBI accession (efetch).",
        })},
        "hidden": {"file_path": ("STRING", {"description": "Alias for file (backward compatibility)"})},
    }
    assert InputDirectoryNode.INPUT_TYPES() == {
        "required": {"directory": ("DIRECTORY", {"description": "Path to directory"})},
        "optional": {},
        "hidden": {},
    }
    assert InputVCFNode.INPUT_TYPES() == {
        "required": {"vcf": (("VCF", "VCF_GZ"), {"description": "Path or URL to a VCF file. http(s)/ftp URLs are downloaded on first use."})},
        "optional": {},
        "hidden": {},
    }
    assert InputGFFNode.INPUT_TYPES() == {
        "required": {"annotation": ("GFF_GTF", {"description": "Path or URL to a GFF3/GTF file. http(s)/ftp URLs are downloaded on first use (gzip auto-decompressed)."})},
        "optional": {},
        "hidden": {"file_path": ("STRING", {"description": "Alias for annotation (backward compatibility)"})},
    }
    assert SampleSheetNode.INPUT_TYPES() == {
        "required": {
            "sample_sheet": ("SAMPLE_SHEET", {
                "description": "Path or URL to sample sheet CSV (columns: sample, fastq_1, fastq_2, condition). http(s) URLs are downloaded on first use.",
            }),
        },
        "optional": {},
        "hidden": {},
    }


@pytest.mark.asyncio
async def test_copy_input_node_resolves_relative_alias_against_context_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    node_dir = tmp_path / "node"
    workspace.mkdir()
    source = workspace / "reference.fa"
    source.write_text(">chr1\nACGT\n")
    context = SimpleNamespace(workspace_dir=workspace, node_dir=node_dir)

    result = await InputFASTANode().run(file_path="reference.fa", context=context)

    copied = node_dir / "reference.fa"
    assert result == {"outputs": {"reference": str(copied.resolve())}}
    assert copied.read_text() == source.read_text()


@pytest.mark.asyncio
async def test_fastq_input_preserves_paired_list_and_scalar_outputs(tmp_path: Path) -> None:
    r1 = tmp_path / "sample_R1.fastq"
    r2 = tmp_path / "sample_R2.fastq"
    r1.write_text("@r1\nA\n+\n!\n")
    r2.write_text("@r2\nT\n+\n!\n")
    out_dir = tmp_path / "out"

    result = await InputFASTQNode().run(reads=[str(r1), str(r2)], output_dir=out_dir)

    copied_r1 = str((out_dir / r1.name).resolve())
    copied_r2 = str((out_dir / r2.name).resolve())
    assert result == {
        "outputs": {
            "reads": [copied_r1, copied_r2],
            "read1": copied_r1,
            "read2": copied_r2,
        }
    }
    assert (out_dir / r1.name).read_text() == r1.read_text()
    assert (out_dir / r2.name).read_text() == r2.read_text()


@pytest.mark.asyncio
async def test_fastq_input_single_end_omits_read2_scalar_output(tmp_path: Path) -> None:
    read = tmp_path / "sample.fastq"
    read.write_text("@r1\nA\n+\n!\n")
    out_dir = tmp_path / "out"

    result = await InputFASTQNode().run(reads=[str(read)], output_dir=out_dir)

    copied = str((out_dir / read.name).resolve())
    assert result == {"outputs": {"reads": [copied], "read1": copied}}


@pytest.mark.asyncio
async def test_fastq_input_rejects_empty_or_more_than_paired_reads(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="one single-end file or two paired-end files"):
        await InputFASTQNode().run(output_dir=tmp_path / "empty")

    reads = []
    for index in range(3):
        read = tmp_path / f"read_{index}.fastq"
        read.write_text("@r\nA\n+\n!\n")
        reads.append(str(read))

    with pytest.raises(ValueError, match="one single-end file or two paired-end files"):
        await InputFASTQNode().run(reads=reads, output_dir=tmp_path / "too-many")


@pytest.mark.asyncio
async def test_vcf_input_exposes_only_the_matching_active_output(tmp_path: Path) -> None:
    source = tmp_path / "variants.vcf.gz"
    source.write_text("##fileformat=VCFv4.2\n")
    out_dir = tmp_path / "out"

    result = await InputVCFNode().run(vcf=str(source), output_dir=out_dir)

    copied = str((out_dir / source.name).resolve())
    assert result == {"outputs": {"vcf": "", "vcf_gz": copied}}


@pytest.mark.asyncio
async def test_directory_input_preserves_dir_path_alias_and_recursive_copy(tmp_path: Path) -> None:
    source_dir = tmp_path / "data"
    nested = source_dir / "nested"
    nested.mkdir(parents=True)
    (nested / "sample.txt").write_text("sample\n")
    out_dir = tmp_path / "out"

    result = await InputDirectoryNode().run(dir_path=str(source_dir), output_dir=out_dir)

    copied = out_dir / source_dir.name
    assert result == {"outputs": {"directory": str(copied.resolve())}}
    assert (copied / "nested" / "sample.txt").read_text() == "sample\n"


@pytest.mark.asyncio
async def test_file_and_directory_inputs_validate_source_kind(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("sample\n")
    source_dir = tmp_path / "data"
    source_dir.mkdir()

    with pytest.raises(ValueError, match="Expected a file input"):
        await InputFileNode().run(file=str(source_dir), output_dir=tmp_path / "file-out")
    with pytest.raises(ValueError, match="Expected a directory input"):
        await InputDirectoryNode().run(
            directory=str(source_file), output_dir=tmp_path / "directory-out"
        )


@pytest.mark.asyncio
async def test_input_copy_is_idempotent_at_destination_and_invalid_modes_fail_closed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("sample\n")

    result = await InputFileNode().run(file=str(source), output_dir=tmp_path)
    assert result == {"outputs": {"file": str(source.resolve())}}

    with pytest.raises(ValueError, match="must be one of"):
        await InputFileNode().run(
            file=str(source), source="guess", output_dir=tmp_path / "invalid"
        )


def test_ncbi_efetch_url_builder() -> None:
    from bionodulo.nodes.builtin.inputs import _ncbi_efetch_url

    url = _ncbi_efetch_url("NR_074517.1")
    assert url.startswith("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?")
    assert "id=NR_074517.1" in url
    assert "rettype=fasta" in url
    # Multiple comma-separated accessions are joined.
    multi = _ncbi_efetch_url("A.1, B.2")
    assert "id=A.1%2CB.2" in multi or "id=A.1,B.2" in multi


def test_input_fasta_source_modes_resolve(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    node_dir = tmp_path / "node"
    node_dir.mkdir()
    fasta = src_dir / "seq.fasta"
    fasta.write_text(">a\nACGT\n")
    ctx = SimpleNamespace(workspace_dir=str(tmp_path), node_dir=str(node_dir))

    import asyncio

    # Explicit local mode copies the file.
    out = asyncio.run(InputFASTANode().run(reference=str(fasta), source="local", context=ctx))
    copied = list(out["outputs"].values())[0]
    assert Path(copied).exists()

    # Default (no source) still works (backward compatible).
    out2 = asyncio.run(InputFASTANode().run(reference=str(fasta), context=ctx))
    assert Path(list(out2["outputs"].values())[0]).exists()
