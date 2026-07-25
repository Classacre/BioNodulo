from __future__ import annotations

import gzip
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.input_family import adapter as input_adapter
from bionodulo.nodes.builtin.input_family.adapter import CopyInputNode
from bionodulo.nodes.builtin.inputs import (
    InputDirectoryNode,
    InputFASTANode,
    InputFASTQNode,
    InputFileNode,
    InputGFFNode,
    InputVCFNode,
    SampleSheetNode,
)


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


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
        }), "email": (
            "STRING",
            {
                "default": "",
                "advanced": True,
                "description": "NCBI contact email required when source=ncbi",
            },
        )},
        "hidden": {"file_path": ("STRING", {"description": "Alias for reference (backward compatibility)"})},
    }
    assert InputFileNode.INPUT_TYPES() == {
        "required": {"file": ("FILE", {"description": "Local path, URL, or NCBI accession for the file. With source=auto, http(s)/ftp URLs are downloaded byte-for-byte and everything else is a local path."})},
        "optional": {"source": ("STRING", {
            "default": "auto",
            "options": ["auto", "local", "url", "ncbi"],
            "description": "How to interpret the value: auto (URL or local), local file, URL download, or NCBI accession (efetch).",
        }), "email": (
            "STRING",
            {
                "default": "",
                "advanced": True,
                "description": "NCBI contact email required when source=ncbi",
            },
        )},
        "hidden": {"file_path": ("STRING", {"description": "Alias for file (backward compatibility)"})},
    }
    assert InputDirectoryNode.INPUT_TYPES() == {
        "required": {"directory": ("DIRECTORY", {"description": "Path to directory"})},
        "optional": {},
        "hidden": {},
    }
    assert InputVCFNode.INPUT_TYPES() == {
        "required": {
            "vcf": (
                ("VCF", "VCF_GZ"),
                {"description": "Path or URL to a VCF file; remote bgzip bytes are preserved"},
            )
        },
        "optional": {
            "vcf_index": (
                "VCF_INDEX",
                {
                    "default": "",
                    "description": "Optional TBI or CSI staged as an exact compressed-VCF sibling",
                },
            )
        },
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
    assert result == {
        "outputs": {"vcf": "", "vcf_gz": copied, "vcf_index": ""}
    }


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

    url = _ncbi_efetch_url("NR_074517.1", email="user@example.org")
    assert url.startswith("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?")
    assert "id=NR_074517.1" in url
    assert "rettype=fasta" in url
    # Multiple comma-separated accessions are joined.
    multi = _ncbi_efetch_url("A.1, B.2", email="user@example.org")
    assert "id=A.1%2CB.2" in multi or "id=A.1,B.2" in multi
    assert "tool=bionodulo" in url
    assert "email=user%40example.org" in url


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


def test_input_family_has_stable_ids_and_exact_runtime_authorities() -> None:
    nodes = (
        InputDirectoryNode,
        InputFASTANode,
        InputFASTQNode,
        InputFileNode,
        InputGFFNode,
        InputVCFNode,
        SampleSheetNode,
    )
    assert {node.NODE_ID for node in nodes} == {
        "input_directory",
        "input_fasta",
        "input_fastq",
        "input_file",
        "input_gff",
        "input_sample_sheet",
        "input_vcf",
    }
    assert {node.VERSION for node in nodes} == {"2.1.0"}
    assert CopyInputNode.PYTHON_VERSION == "3.12.13"
    assert CopyInputNode.PYTHON_SOURCE_COMMIT == (
        "3bb231a6a5dc02b95658877318bf61501a7209e9"
    )
    assert CopyInputNode.FOCUSED_OWNERSHIP_COMMIT == (
        "827ffffc57530d60becfc66f190c35e79d2df7fc"
    )
    assert CopyInputNode.AUDIT_STATUS == (
        "contract-checked-no-external-network-execution"
    )
    assert SampleSheetNode.PRODUCT_SOURCE_COMMIT == (
        CopyInputNode.FOCUSED_OWNERSHIP_COMMIT
    )
    assert SampleSheetNode.SOURCE_AUTHORITIES["python_copy_runtime"] == (
        CopyInputNode.SOURCE_AUTHORITIES["python_copy_runtime"]
    )
    assert SampleSheetNode.SOURCE_AUTHORITIES["python_url_runtime"] == (
        CopyInputNode.SOURCE_AUTHORITIES["python_url_runtime"]
    )
    assert SampleSheetNode.EXIT_SEMANTICS == CopyInputNode.EXIT_SEMANTICS
    assert "ftps" not in input_adapter.URL_SCHEMES
    assert InputVCFNode.FORMAT_SPEC_GIT_COMMIT == (
        "da617203a9527537746e200abda2885bec3a822c"
    )
    assert InputVCFNode.RETURN_TYPES == ("VCF", "VCF_GZ", "VCF_INDEX")
    assert InputVCFNode.RETURN_NAMES == ("vcf", "vcf_gz", "vcf_index")


@pytest.mark.asyncio
async def test_unsupported_ftps_is_rejected_before_opening_a_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme 'ftps'"):
        await InputFASTANode().run(
            reference="ftps://example.org/reference.fa",
            source="url",
            output_dir=tmp_path / "out",
        )


def test_url_cache_uses_the_complete_url_not_only_the_basename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = {
        "https://one.example/data/R1.fq": b"first\n",
        "https://two.example/other/R1.fq": b"second\n",
    }
    calls: list[str] = []

    def fake_urlopen(request: Any, **_kwargs: Any) -> _Response:
        calls.append(request.full_url)
        return _Response(urls[request.full_url])

    monkeypatch.setattr(input_adapter.urllib.request, "urlopen", fake_urlopen)
    context = SimpleNamespace(workspace_dir=tmp_path)
    first = input_adapter._download_to_cache(
        next(iter(urls)), context, decompress_gzip=False
    )
    second = input_adapter._download_to_cache(
        list(urls)[1], context, decompress_gzip=False
    )
    repeated = input_adapter._download_to_cache(
        next(iter(urls)), context, decompress_gzip=False
    )

    assert first.name == second.name == "R1.fq"
    assert first.parent != second.parent
    assert first.read_bytes() == b"first\n"
    assert second.read_bytes() == b"second\n"
    assert repeated == first
    assert calls == list(urls)


def test_failed_gzip_decode_does_not_poison_the_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = iter((b"not gzip", gzip.compress(b">ref\nACGT\n")))
    calls = 0

    def fake_urlopen(_request: Any, **_kwargs: Any) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(next(payloads))

    monkeypatch.setattr(input_adapter.urllib.request, "urlopen", fake_urlopen)
    context = SimpleNamespace(workspace_dir=tmp_path)
    url = "https://example.org/reference.fa.gz"

    with pytest.raises(gzip.BadGzipFile):
        input_adapter._download_to_cache(url, context)

    cache_dir = (
        tmp_path
        / ".bionodulo"
        / "url_cache"
        / input_adapter._url_cache_key(url)
    )
    assert not [path for path in cache_dir.iterdir() if path.is_file()]

    recovered = input_adapter._download_to_cache(url, context)
    assert recovered.read_bytes() == b">ref\nACGT\n"
    assert calls == 2
    assert not list(cache_dir.glob("*.part"))


@pytest.mark.asyncio
async def test_remote_fasta_gzip_is_atomically_decoded_for_legacy_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = gzip.compress(b">ref\nACGT\n")
    monkeypatch.setattr(
        input_adapter.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(payload),
    )
    context = SimpleNamespace(
        workspace_dir=tmp_path / "workspace",
        node_dir=tmp_path / "node",
    )

    result = await InputFASTANode().run(
        reference="https://example.org/reference.fa.gz",
        context=context,
    )

    staged = Path(result["outputs"]["reference"])
    assert staged.name == "reference.fa"
    assert staged.read_bytes() == b">ref\nACGT\n"
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_remote_fastq_and_generic_gzip_preserve_compressed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = {
        "https://example.org/reads.fastq.gz": gzip.compress(b"@read\nACGT\n+\n!!!!\n"),
        "https://example.org/archive.dat.gz": gzip.compress(b"opaque bytes\n"),
    }

    def fake_urlopen(request: Any, **_kwargs: Any) -> _Response:
        return _Response(payloads[request.full_url])

    monkeypatch.setattr(input_adapter.urllib.request, "urlopen", fake_urlopen)
    context = SimpleNamespace(workspace_dir=tmp_path / "workspace")

    fastq_result = await InputFASTQNode().run(
        reads=["https://example.org/reads.fastq.gz"],
        context=context,
        output_dir=tmp_path / "fastq-out",
    )
    file_result = await InputFileNode().run(
        file="https://example.org/archive.dat.gz",
        context=context,
        output_dir=tmp_path / "file-out",
    )

    staged_fastq = Path(fastq_result["outputs"]["read1"])
    staged_file = Path(file_result["outputs"]["file"])
    assert staged_fastq.name == "reads.fastq.gz"
    assert staged_fastq.read_bytes() == payloads["https://example.org/reads.fastq.gz"]
    assert staged_file.name == "archive.dat.gz"
    assert staged_file.read_bytes() == payloads["https://example.org/archive.dat.gz"]


@pytest.mark.asyncio
async def test_duplicate_fastq_basenames_fail_before_staging(tmp_path: Path) -> None:
    first = tmp_path / "lane1" / "reads.fastq"
    second = tmp_path / "lane2" / "reads.fastq"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("@first\nA\n+\n!\n")
    second.write_text("@second\nT\n+\n!\n")
    output = tmp_path / "out"

    with pytest.raises(ValueError, match="duplicate destination basenames"):
        await InputFASTQNode().run(reads=[first, second], output_dir=output)

    assert not list(output.iterdir())


@pytest.mark.asyncio
async def test_failed_file_stage_preserves_the_previous_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source" / "sample.txt"
    source.parent.mkdir()
    source.write_text("new\n")
    output = tmp_path / "out"
    output.mkdir()
    destination = output / source.name
    destination.write_text("previous\n")

    def fail_copy(_source: Any, staged: Any) -> None:
        Path(staged).write_text("partial\n")
        raise OSError("synthetic copy failure")

    monkeypatch.setattr(input_adapter.shutil, "copy2", fail_copy)
    with pytest.raises(OSError, match="synthetic copy failure"):
        await InputFileNode().run(file=source, output_dir=output)

    assert destination.read_text() == "previous\n"
    assert not list(output.glob(".*.staging-*.part"))


@pytest.mark.asyncio
async def test_directory_restaging_replaces_instead_of_merging_stale_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "database"
    source.mkdir(parents=True)
    (source / "current.txt").write_text("first\n")
    stale = source / "stale.txt"
    stale.write_text("remove me\n")
    output = tmp_path / "out"

    await InputDirectoryNode().run(directory=source, output_dir=output)
    stale.unlink()
    (source / "current.txt").write_text("second\n")
    result = await InputDirectoryNode().run(directory=source, output_dir=output)

    staged = Path(result["outputs"]["directory"])
    assert (staged / "current.txt").read_text() == "second\n"
    assert not (staged / "stale.txt").exists()
    assert not list(output.glob(".*.backup-*"))


@pytest.mark.asyncio
async def test_remote_vcf_gzip_bytes_and_suffix_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = gzip.compress(b"##fileformat=VCFv4.5\n")
    monkeypatch.setattr(
        input_adapter.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _Response(payload),
    )
    context = SimpleNamespace(
        workspace_dir=tmp_path / "workspace",
        node_dir=tmp_path / "node",
    )

    result = await InputVCFNode().run(
        vcf="https://example.org/variants.vcf.gz",
        context=context,
    )

    staged = Path(result["outputs"]["vcf_gz"])
    assert result["outputs"]["vcf"] == ""
    assert result["outputs"]["vcf_index"] == ""
    assert staged.name == "variants.vcf.gz"
    assert staged.read_bytes() == payload


@pytest.mark.asyncio
async def test_vcf_index_is_staged_as_an_exact_tbi_or_csi_sibling(
    tmp_path: Path,
) -> None:
    source = tmp_path / "variants.vcf.gz"
    source.write_bytes(b"bgzip-placeholder")
    uploaded_index = tmp_path / "uploaded.tbi"
    uploaded_index.write_bytes(b"tabix-placeholder")

    result = await InputVCFNode().run(
        vcf=source,
        vcf_index=uploaded_index,
        output_dir=tmp_path / "out",
    )

    staged_vcf = Path(result["outputs"]["vcf_gz"])
    staged_index = Path(result["outputs"]["vcf_index"])
    assert staged_index == Path(f"{staged_vcf}.tbi")
    assert staged_index.read_bytes() == uploaded_index.read_bytes()


@pytest.mark.asyncio
async def test_vcf_index_copy_failure_leaves_no_half_promoted_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "variants.vcf.gz"
    source.write_bytes(b"bgzip-placeholder")
    uploaded_index = tmp_path / "uploaded.tbi"
    uploaded_index.write_bytes(b"tabix-placeholder")
    output = tmp_path / "out"

    real_copy2 = input_adapter.shutil.copy2

    def fail_index_copy(source_path: Any, destination_path: Any) -> Any:
        if Path(source_path) == uploaded_index:
            Path(destination_path).write_bytes(b"partial-index")
            raise OSError("synthetic index copy failure")
        return real_copy2(source_path, destination_path)

    monkeypatch.setattr(input_adapter.shutil, "copy2", fail_index_copy)
    with pytest.raises(OSError, match="synthetic index copy failure"):
        await InputVCFNode().run(
            vcf=source,
            vcf_index=uploaded_index,
            output_dir=output,
        )

    assert not (output / "variants.vcf.gz").exists()
    assert not (output / "variants.vcf.gz.tbi").exists()
    assert not list(output.glob(".vcf-bundle-*"))


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (
            {"vcf": "variants.vcf", "vcf_index": "variants.vcf.tbi"},
            "only valid with a bgzip-compressed VCF",
        ),
        (
            {"vcf": "variants.vcf.gz", "vcf_index": "variants.vcf.gz.idx"},
            "must end in .tbi or .csi",
        ),
    ],
)
def test_vcf_index_contract_rejects_invalid_pairings(
    inputs: dict[str, Any],
    message: str,
) -> None:
    assert message in str(InputVCFNode.VALIDATE_INPUTS(inputs))
