from __future__ import annotations

import inspect
import struct
from pathlib import Path
from typing import Any, Callable

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import rna_seq
from bionodulo.nodes.builtin.rna_seq_family.featurecounts import FeatureCountsNode
from bionodulo.nodes.builtin.rna_seq_family.feature_counts_alias import FeatureCountsAliasNode
from bionodulo.nodes.builtin.rna_seq_family.kallisto import (
    KallistoIndexNode,
    KallistoQuantNode,
)
from bionodulo.nodes.builtin.rna_seq_family.salmon import (
    SalmonIndexNode,
    SalmonQuantNode,
)
from bionodulo.nodes.builtin import wrapped_annotation_sequence


def _fake_context(tmp_path: Path, materialize: Callable[[list[str] | str, dict[str, Any]], None]):
    class FakeContext:
        node_dir = tmp_path

        def __init__(self) -> None:
            self.command: list[str] | str | None = None
            self.kwargs: dict[str, Any] = {}

        async def run_command(self, command: list[str] | str, **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            materialize(command, kwargs)
            return {"returncode": 0, "stdout": "", "stderr": ""}

    return FakeContext()


def _materialize_file(path: Path, content: str = "synthetic\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _materialize_kallisto_index(
    path: Path,
    *,
    version: int = KallistoIndexNode.INDEX_VERSION,
    graph: bytes = b"synthetic graph",
) -> str:
    """Materialize the binary prefix Kallisto 0.52.0 reads before quantification."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("@N", version) + struct.pack("@N", len(graph)) + graph)
    return str(path)


def _materialize_salmon_index(path: Path, index_version: int = 1) -> str:
    _materialize_file(
        path / "info.json",
        f'{{"has_ec_table": false, "index_version": {index_version}}}',
    )
    for relative_path in SalmonIndexNode.REQUIRED_INDEX_FILES:
        _materialize_file(path / relative_path, "index artifact\n")
    return str(path)


def test_stable_ids_are_owned_by_focused_modules_and_legacy_aliases_remain() -> None:
    assert SalmonIndexNode.__module__.endswith("rna_seq_family.salmon")
    assert SalmonQuantNode.__module__.endswith("rna_seq_family.salmon")
    assert KallistoIndexNode.__module__.endswith("rna_seq_family.kallisto")
    assert KallistoQuantNode.__module__.endswith("rna_seq_family.kallisto")
    assert FeatureCountsNode.__module__.endswith("rna_seq_family.featurecounts")
    assert FeatureCountsAliasNode.__module__.endswith("rna_seq_family.feature_counts_alias")
    assert rna_seq.SalmonIndexNode is SalmonIndexNode
    assert rna_seq.SalmonQuantNode is SalmonQuantNode
    assert rna_seq.KallistoIndexNode is KallistoIndexNode
    assert rna_seq.KallistoQuantNode is KallistoQuantNode

    legacy_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(rna_seq, inspect.isclass)
        if issubclass(obj, BaseNode) and obj not in {BaseNode} and obj.__module__ == rna_seq.__name__ and obj.NODE_ID
    }
    assert {"salmon_index", "salmon_quant", "kallisto_index", "kallisto_quant"}.isdisjoint(legacy_ids)
    assert "feature_counts" not in legacy_ids
    assert wrapped_annotation_sequence.FeatureCountsNode is FeatureCountsNode
    wrapped_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(wrapped_annotation_sequence, inspect.isclass)
        if issubclass(obj, BaseNode)
        and obj is not BaseNode
        and obj.__module__ == wrapped_annotation_sequence.__name__
        and obj.NODE_ID
    }
    assert "featurecounts" not in wrapped_ids


def test_pinned_sources_and_output_contracts_are_exact() -> None:
    assert SalmonIndexNode.VERSION == SalmonQuantNode.VERSION == "2.3.4"
    assert SalmonIndexNode.GIT_COMMIT == "d53fed6f0af6966a40825558f0edf71b6df7cf52"
    for node_class in (SalmonIndexNode, SalmonQuantNode):
        assert node_class.CONDA_PACKAGE_CONSTRAINTS == {"salmon": "2.3.4"}
        assert node_class.PACKAGE_CONSTRAINTS == ("salmon==2.3.4",)
        assert node_class.SOURCE_AUTHORITIES["cli_contract"].endswith("crates/salmon-cli/src/main.rs")
        assert node_class.AUDIT_STATUS == "contract-checked-no-binary-execution"
        assert "non-zero" in node_class.EXIT_SEMANTICS
    assert KallistoIndexNode.VERSION == KallistoQuantNode.VERSION == "0.52.0"
    assert KallistoIndexNode.GIT_COMMIT == "4e9f29cf3b021260415430c057a22469ca081391"
    assert KallistoIndexNode.CONDA_PACKAGE_CONSTRAINTS == {"kallisto": "0.52.0"}
    assert KallistoIndexNode.PACKAGE_CONSTRAINTS == ("kallisto==0.52.0",)
    assert KallistoIndexNode.INDEX_VERSION == 13
    assert KallistoIndexNode.SOURCE_AUTHORITIES["index_format"] == "src/KmerIndex.h; src/KmerIndex.cpp"
    assert KallistoQuantNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert FeatureCountsNode.VERSION == "2.1.1"
    assert FeatureCountsNode.SOURCE_SHA256 == ("6392d7c66831cdd767e58251892a79a51b6fab8ed0ba9671ad5e85ff1ab01eaa")
    assert FeatureCountsNode.CONDA_PACKAGE_CONSTRAINTS == {
        "subread": "2.1.1",
        "samtools": "1.23.1",
    }
    assert FeatureCountsNode.SOURCE_AUTHORITIES["cli_contract"] == "src/readSummary.c"
    assert FeatureCountsNode.AUDIT_STATUS == "contract-checked-no-binary-execution"
    assert "non-zero" in FeatureCountsNode.EXIT_SEMANTICS
    featurecounts_options = FeatureCountsNode.INPUT_TYPES()["optional"]
    assert featurecounts_options["threads"][1]["default"] == 1
    assert featurecounts_options["exclude_chimerics"][1]["default"] is False

    assert SalmonIndexNode.RETURN_TYPES == ("INDEX_DIR",)
    assert SalmonQuantNode.RETURN_TYPES == ("COUNTS", "DIRECTORY")
    assert KallistoIndexNode.RETURN_TYPES == ("FILE",)
    assert KallistoQuantNode.RETURN_TYPES == ("ABUNDANCE", "TXT")
    assert FeatureCountsNode.RETURN_TYPES == ("COUNTS", "TSV", "TSV", "BAM", "TSV")


def test_salmon_index_validates_odd_k_and_renders_multiple_transcripts(tmp_path: Path) -> None:
    transcripts = [
        _materialize_file(tmp_path / "tx_a.fa", ">a\nACGT\n"),
        _materialize_file(tmp_path / "tx_b.fa", ">b\nTGCA\n"),
    ]
    inputs = {"transcripts": transcripts, "threads": 4, "kmer": 31}
    assert SalmonIndexNode.VALIDATE_INPUTS(inputs) is True
    assert SalmonIndexNode.render_command({**inputs, "output": str(tmp_path / "salmon_index")}) == [
        "salmon",
        "index",
        "-t",
        *transcripts,
        "-i",
        str(tmp_path / "salmon_index" / "index"),
        "-p",
        "4",
        "-k",
        "31",
    ]
    assert "odd" in str(SalmonIndexNode.VALIDATE_INPUTS({**inputs, "kmer": 32}))
    assert "1 and 63" in str(SalmonIndexNode.VALIDATE_INPUTS({**inputs, "kmer": 65}))


def test_salmon_thread_contract_matches_upstream_zero_and_unbounded_semantics(
    tmp_path: Path,
) -> None:
    transcripts = _materialize_file(tmp_path / "transcripts.fa", ">tx\nACGT\n")
    assert SalmonIndexNode.INPUT_TYPES()["required"]["threads"][1]["default"] == 0
    assert SalmonQuantNode.INPUT_TYPES()["required"]["threads"][1]["default"] == 0
    assert SalmonIndexNode.VALIDATE_INPUTS({"transcripts": transcripts, "threads": 0}) is True
    assert SalmonIndexNode.VALIDATE_INPUTS({"transcripts": transcripts, "threads": 65}) is True
    assert "zero or a positive" in str(SalmonIndexNode.VALIDATE_INPUTS({"transcripts": transcripts, "threads": -1}))
    assert "integer" in str(SalmonIndexNode.VALIDATE_INPUTS({"transcripts": transcripts, "threads": True}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("info_payload", "message"),
    [
        (None, "missing required info.json"),
        ("", "info.json is empty"),
        ("{", "cannot parse index info.json"),
        ('{"index_version": 0}', "index format v0 is too old"),
    ],
)
async def test_salmon_rejects_invalid_index_info_after_build_and_before_quant(
    tmp_path: Path,
    info_payload: str | None,
    message: str,
) -> None:
    transcripts = _materialize_file(tmp_path / "transcripts.fa", ">tx\nACGT\n")

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        index = Path(command[command.index("-i") + 1])
        index.mkdir(parents=True, exist_ok=True)
        if info_payload is not None:
            (index / "info.json").write_text(info_payload, encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        await SalmonIndexNode().run(
            transcripts=transcripts,
            threads=1,
            context=_fake_context(tmp_path, materialize),
            output_dir=tmp_path,
        )

    index = tmp_path / "salmon_index" / "index"
    validation = SalmonQuantNode.VALIDATE_INPUTS({"index": str(index), "threads": 1})
    assert message in str(validation)


@pytest.mark.parametrize(
    ("relative_path", "empty"),
    [
        ("index.ssi.mphf", False),
        ("refseq.bin", True),
        ("duplicate_clusters.tsv", False),
    ],
)
def test_salmon_quant_rejects_incomplete_index_bundles(
    tmp_path: Path,
    relative_path: str,
    empty: bool,
) -> None:
    index = Path(_materialize_salmon_index(tmp_path / "salmon-index"))
    artifact = index / relative_path
    if empty:
        artifact.write_bytes(b"")
    else:
        artifact.unlink()

    validation = SalmonQuantNode.VALIDATE_INPUTS({"index": index, "threads": 1})

    assert "Salmon index is incomplete" in str(validation)
    assert relative_path in str(validation)


def test_salmon_bias_corrections_are_upstream_opt_in_defaults(tmp_path: Path) -> None:
    index = _materialize_salmon_index(tmp_path / "salmon-index")
    read = _materialize_file(tmp_path / "reads.fq", "@read\nACGT\n+\n!!!!\n")
    inputs = {"index": index, "reads": read, "single_end": True, "threads": 1}

    optional = SalmonQuantNode.INPUT_TYPES()["optional"]
    command = SalmonQuantNode.render_command(inputs)

    assert optional["gc_bias"][1]["default"] is False
    assert optional["seq_bias"][1]["default"] is False
    assert "--gcBias" not in command
    assert "--seqBias" not in command


def test_salmon_quant_preserves_all_paired_lists_and_valid_library_types(tmp_path: Path) -> None:
    index = tmp_path / "salmon-index"
    _materialize_salmon_index(index)
    reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1_a.fq.gz", "r2_a.fq.gz", "r1_b.fq.gz", "r2_b.fq.gz")
    ]
    inputs = {
        "index": str(index),
        "reads": reads,
        "threads": 8,
        "lib_type": "OSF",
        "gc_bias": False,
        "seq_bias": True,
    }
    assert SalmonQuantNode.VALIDATE_INPUTS(inputs) is True
    assert SalmonQuantNode.render_command(inputs) == [
        "salmon",
        "quant",
        "-i",
        str(index),
        "-l",
        "OSF",
        "-o",
        ".",
        "-p",
        "8",
        "-1",
        reads[0],
        reads[2],
        "-2",
        reads[1],
        reads[3],
        "--seqBias",
    ]
    assert "even number" in str(SalmonQuantNode.VALIDATE_INPUTS({**inputs, "reads": reads[:3]}))
    assert "not valid" in str(SalmonQuantNode.VALIDATE_INPUTS({**inputs, "lib_type": "SF"}))

    assert SalmonQuantNode.VALIDATE_INPUTS({**inputs, "lib_type": "isr"}) is True
    command = SalmonQuantNode.render_command({**inputs, "lib_type": "isr"})
    assert command[command.index("-l") + 1] == "ISR"


@pytest.mark.parametrize(
    ("field", "invalid"),
    [("single_end", "false"), ("gc_bias", 1), ("seq_bias", None)],
)
def test_salmon_quant_rejects_non_boolean_controls(
    tmp_path: Path,
    field: str,
    invalid: object,
) -> None:
    index = _materialize_salmon_index(tmp_path / "salmon-index")
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]

    validation = SalmonQuantNode.VALIDATE_INPUTS({"index": index, "reads": reads, "threads": 0, field: invalid})

    assert field in str(validation)
    assert "must be a boolean" in str(validation)


def test_salmon_quant_fake_execution_keeps_quant_directory(tmp_path: Path) -> None:
    index = tmp_path / "salmon-index"
    _materialize_salmon_index(index)
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        for relative_path in SalmonQuantNode.REQUIRED_QUANT_FILES:
            _materialize_file(output / relative_path)

    context = _fake_context(tmp_path, materialize)
    result = __import__("asyncio").run(
        SalmonQuantNode().run(
            index=str(index),
            reads=reads,
            threads=2,
            context=context,
            output_dir=tmp_path,
        )
    )
    quant_dir = tmp_path / "salmon_quant"
    assert result == (str(quant_dir / "quant.sf"), str(quant_dir))
    assert (quant_dir / "aux_info" / "meta_info.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invalid_relative_path", "leave_missing"),
    [
        ("lib_format_counts.json", True),
        ("aux_info/fld.gz", True),
        ("logs/salmon_quant.log", False),
    ],
)
async def test_salmon_quant_rejects_missing_or_empty_companion_artifacts(
    tmp_path: Path,
    invalid_relative_path: str,
    leave_missing: bool,
) -> None:
    index = tmp_path / "salmon-index"
    _materialize_salmon_index(index)
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        for relative_path in SalmonQuantNode.REQUIRED_QUANT_FILES:
            path = output / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative_path == invalid_relative_path and leave_missing:
                continue
            path.write_text("" if relative_path == invalid_relative_path else "synthetic\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Salmon quant output is incomplete"):
        await SalmonQuantNode().run(
            index=str(index),
            reads=reads,
            threads=1,
            context=_fake_context(tmp_path, materialize),
            output_dir=tmp_path,
        )


def test_kallisto_index_is_a_file_and_validates_kmer_and_threads(tmp_path: Path) -> None:
    transcripts = _materialize_file(tmp_path / "transcripts.fa", ">tx\nACGT\n")
    inputs = {"transcripts": transcripts, "threads": 1, "kmer": 3}
    assert KallistoIndexNode.VALIDATE_INPUTS(inputs) is True
    outputs = KallistoIndexNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert outputs == [tmp_path / "kallisto_index" / "transcripts.idx"]
    assert KallistoIndexNode.render_command({**inputs, "output": str(tmp_path / "kallisto_index")}) == [
        "kallisto",
        "index",
        "-i",
        str(tmp_path / "kallisto_index" / "transcripts.idx"),
        "-k",
        "3",
        "-t",
        "1",
        transcripts,
    ]
    assert "odd" in str(KallistoIndexNode.VALIDATE_INPUTS({**inputs, "kmer": 4}))
    assert "between 3 and 31" in str(KallistoIndexNode.VALIDATE_INPUTS({**inputs, "kmer": 33}))
    assert KallistoIndexNode.VALIDATE_INPUTS({**inputs, "threads": 65}) is True


@pytest.mark.asyncio
async def test_kallisto_index_rejects_zero_byte_output_after_zero_exit(tmp_path: Path) -> None:
    transcripts = _materialize_file(tmp_path / "transcripts.fa", ">tx\nACGT\n")

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        index = Path(command[command.index("-i") + 1])
        index.parent.mkdir(parents=True, exist_ok=True)
        index.touch()

    with pytest.raises(RuntimeError, match="Kallisto index output is invalid: index file is empty"):
        await KallistoIndexNode().run(
            transcripts=transcripts,
            threads=1,
            context=_fake_context(tmp_path, materialize),
            output_dir=tmp_path,
        )


def test_kallisto_quant_requires_even_pairs_and_single_end_fragment_parameters(tmp_path: Path) -> None:
    index = _materialize_kallisto_index(tmp_path / "transcripts.idx")
    paired_reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1.fq.gz", "r2.fq.gz", "r1b.fq.gz", "r2b.fq.gz")
    ]
    paired = {
        "index": index,
        "reads": paired_reads,
        "threads": 2,
        "bootstrap": 0,
    }
    assert KallistoQuantNode.VALIDATE_INPUTS(paired) is True
    assert KallistoQuantNode.render_command(paired) == [
        "kallisto",
        "quant",
        "-i",
        index,
        "-o",
        ".",
        "-t",
        "2",
        *paired_reads,
    ]
    assert "even number" in str(KallistoQuantNode.VALIDATE_INPUTS({**paired, "reads": paired_reads[:3]}))
    single = {
        "index": index,
        "reads": [_materialize_file(tmp_path / "single.fq.gz", "@read\nACGT\n+\n!!!!\n")],
        "threads": 1,
        "single_end": True,
        "fragment_length": 200.0,
        "sd": 20.0,
        "bootstrap": 25,
    }
    assert KallistoQuantNode.VALIDATE_INPUTS(single) is True
    assert (
        KallistoQuantNode.render_command(single)[-7:]
        == [
            "-b",
            "25",
            "--single",
            "-l",
            "200.0",
            "-s",
            "20.0",
            single["reads"][0],
        ][-7:]
    )
    assert "requires positive fragment_length" in str(
        KallistoQuantNode.VALIDATE_INPUTS({k: v for k, v in single.items() if k not in {"fragment_length", "sd"}})
    )


def test_kallisto_quant_preserves_documented_paired_overrides_and_bias(tmp_path: Path) -> None:
    index = _materialize_kallisto_index(tmp_path / "transcripts.idx")
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]
    inputs = {
        "index": index,
        "reads": reads,
        "threads": 65,
        "bootstrap": 1001,
        "bias": True,
        "fragment_length": 200.0,
        "sd": 20.0,
    }

    assert KallistoQuantNode.VALIDATE_INPUTS(inputs) is True
    assert KallistoQuantNode.render_command(inputs) == [
        "kallisto",
        "quant",
        "-i",
        index,
        "-o",
        ".",
        "-t",
        "65",
        "-b",
        "1001",
        "--bias",
        "-l",
        "200.0",
        "-s",
        "20.0",
        *reads,
    ]
    assert KallistoQuantNode.VALIDATE_INPUTS({**inputs, "fragment_length": 0.0, "sd": 0.0}) is True


def test_kallisto_quant_rejects_wrong_or_truncated_binary_index(tmp_path: Path) -> None:
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]
    wrong_version = _materialize_kallisto_index(tmp_path / "wrong.idx", version=12)
    assert "index format v12" in str(
        KallistoQuantNode.VALIDATE_INPUTS({"index": wrong_version, "reads": reads, "threads": 1})
    )

    truncated = tmp_path / "truncated.idx"
    truncated.write_bytes(struct.pack("@N", 13) + struct.pack("@N", 10) + b"short")
    assert "truncated" in str(KallistoQuantNode.VALIDATE_INPUTS({"index": truncated, "reads": reads, "threads": 1}))


def test_kallisto_quant_fake_execution_captures_stderr_and_native_outputs(tmp_path: Path) -> None:
    index = _materialize_kallisto_index(tmp_path / "transcripts.idx")
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]

    def materialize(command: list[str] | str, kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "abundance.tsv").write_text(
            "target_id\tlength\teff_length\test_counts\ttpm\n",
            encoding="utf-8",
        )
        (output / "run_info.json").write_text(
            '{"kallisto_version": "0.52.0", "index_version": 13}',
            encoding="utf-8",
        )
        (output / "abundance.h5").write_bytes(b"hdf5")
        Path(kwargs["stderr_path"]).write_text(
            "[quant] will process file 1: sample.fq.gz\n"
            "[quant] processed 2 reads, 1 reads pseudoaligned\n"
            "[quant] quantifying the abundances\n",
            encoding="utf-8",
        )

    context = _fake_context(tmp_path, materialize)
    result = __import__("asyncio").run(
        KallistoQuantNode().run(
            index=index,
            reads=reads,
            threads=2,
            context=context,
            output_dir=tmp_path,
        )
    )
    output = tmp_path / "kallisto_quant"
    assert result == (str(output / "abundance.tsv"), str(output / "kallisto.stderr.log"))
    assert "stderr_path" in context.kwargs
    assert (output / "run_info.json").exists()
    assert (output / "abundance.h5").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("run_info_payload", "message"),
    [(None, "run_info.json"), ("", "run_info.json"), ("{}", "unexpected kallisto_version")],
)
async def test_kallisto_quant_rejects_invalid_run_info(
    tmp_path: Path,
    run_info_payload: str | None,
    message: str,
) -> None:
    index = _materialize_kallisto_index(tmp_path / "transcripts.idx")
    reads = [_materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n") for name in ("r1.fq.gz", "r2.fq.gz")]

    def materialize(command: list[str] | str, kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "abundance.tsv").write_text(
            "target_id\tlength\teff_length\test_counts\ttpm\n",
            encoding="utf-8",
        )
        if run_info_payload is not None:
            (output / "run_info.json").write_text(run_info_payload, encoding="utf-8")
        Path(kwargs["stderr_path"]).write_text("[quant] complete\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        await KallistoQuantNode().run(
            index=index,
            reads=reads,
            threads=1,
            context=_fake_context(tmp_path, materialize),
            output_dir=tmp_path,
        )


def test_featurecounts_uses_threads_and_enforces_documented_constraints(tmp_path: Path) -> None:
    alignment = _materialize_file(tmp_path / "reads.bam", "BAM\n")
    annotation = _materialize_file(tmp_path / "genes.gff.gz", "chr1\tsource\tgene\t1\t4\t.\t+\t.\tID=g1\n")
    inputs = {
        "alignment": alignment,
        "anno_select": "history",
        "reference_gene_sets": annotation,
        "threads": 6,
        "paired_end_status": "PE_fragments",
        "only_both_ends": True,
        "check_distance": True,
        "gff_feature_type": "exon",
        "gff_feature_attribute": "gene_id",
        "multifeat": "-O",
        "fraction": True,
        "by_read_group": True,
        "R": True,
    }
    assert FeatureCountsNode.VALIDATE_INPUTS(inputs) is True
    command = FeatureCountsNode.render_command({**inputs, "output": str(tmp_path / "featurecounts")})
    assert "-T 6" in command
    assert "${GALAXY_SLOTS:-2}" not in command
    assert "-p --countReadPairs" in command
    assert "-P -d 50 -D 600 -B" in command
    assert "-O --fraction" in command
    assert "--byReadGroup" in command
    assert "cut -f 1,7- body.txt" in command
    assert f"-R BAM --Rpath {tmp_path / 'featurecounts'}" in command
    assert f"{tmp_path / 'featurecounts' / 'reads.bam.featureCounts.bam'}" in command
    assert "*.featureCounts.bam" not in command
    assert "fraction requires" in str(FeatureCountsNode.VALIDATE_INPUTS({**inputs, "multifeat": ""}))
    assert "requires only_both_ends" in str(FeatureCountsNode.VALIDATE_INPUTS({**inputs, "only_both_ends": False}))
    assert FeatureCountsNode.VALIDATE_INPUTS({**inputs, "threads": 64}) is True
    assert "between 1 and 64" in str(FeatureCountsNode.VALIDATE_INPUTS({**inputs, "threads": 65}))


def test_featurecounts_medium_format_preserves_every_count_column(tmp_path: Path) -> None:
    command = FeatureCountsNode.render_command(
        {
            "alignment": "/planned/reads.bam",
            "anno_select": "builtin",
            "format": "tabdel_medium",
            "by_read_group": True,
            "output": str(tmp_path / "featurecounts"),
        }
    )

    assert "--byReadGroup" in command
    assert "cut -f 1,7- body.txt > expression_matrix.txt" in command


def test_featurecounts_long_read_mode_enforces_source_thread_and_read_constraints(tmp_path: Path) -> None:
    inputs = {
        "alignment": _materialize_file(tmp_path / "long_reads.bam", "BAM\n"),
        "anno_select": "history",
        "reference_gene_sets": _materialize_file(
            tmp_path / "genes.gtf",
            'chr1\tsource\texon\t1\t4\t.\t+\t.\tgene_id "g1";\n',
        ),
        "threads": 1,
        "long_reads": True,
        "paired_end_status": "single_end",
    }

    assert FeatureCountsNode.VALIDATE_INPUTS(inputs) is True
    command = FeatureCountsNode.render_command({**inputs, "output": str(tmp_path / "featurecounts")})
    assert "-T 1" in command
    assert "-L" in command
    assert "long_reads requires threads=1" == FeatureCountsNode.VALIDATE_INPUTS({**inputs, "threads": 2})
    assert "supports reads only" in str(
        FeatureCountsNode.VALIDATE_INPUTS({**inputs, "paired_end_status": "PE_fragments", "count_read_pairs": True})
    )


def test_featurecounts_matches_source_mapq_bound_and_literal_header_rewrite(tmp_path: Path) -> None:
    """The 2.1.1 CLI rejects MAPQ >255 and headers may contain literal path characters."""

    alignment = _materialize_file(tmp_path / "reads|control.bam", "BAM\n")
    assert FeatureCountsNode.VALIDATE_INPUTS(
        {"alignment": alignment, "anno_select": "builtin", "mapping_quality": 255}
    ) is True
    assert "mapping_quality must be <= 255" in str(
        FeatureCountsNode.VALIDATE_INPUTS(
            {"alignment": alignment, "anno_select": "builtin", "mapping_quality": 256}
        )
    )

    command = FeatureCountsNode.render_command(
        {
            "alignment": alignment,
            "anno_select": "builtin",
            "output": str(tmp_path / "featurecounts"),
        }
    )
    assert "sed -e 's#" in command
    assert "reads|control\\.bam#reads|control.bam#g'" in command

    windows_style = r"/work/paired\\reads.bam"
    assignment_command = FeatureCountsNode.render_command(
        {
            "alignment": windows_style,
            "anno_select": "builtin",
            "R": True,
            "output": str(tmp_path / "featurecounts"),
        }
    )
    assert "paired\\\\reads.bam.featureCounts.bam" not in assignment_command
    assert "reads.bam.featureCounts.bam" in assignment_command


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("include_feature_lengths", "annotate_bam", "count_junctions"),
    [
        (False, False, False),
        (False, False, True),
        (False, True, False),
        (False, True, True),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, True, True),
    ],
)
async def test_featurecounts_fake_execution_maps_every_optional_output_combination_by_name(
    tmp_path: Path,
    include_feature_lengths: bool,
    annotate_bam: bool,
    count_junctions: bool,
) -> None:
    inputs = {
        "alignment": _materialize_file(tmp_path / "reads.bam", "BAM\n"),
        "anno_select": "history",
        "reference_gene_sets": _materialize_file(
            tmp_path / "genes.gtf",
            'chr1\tsource\tgene\t1\t4\t.\t+\t.\tgene_id "g1";\n',
        ),
        "threads": 2,
        "include_feature_length_file": include_feature_lengths,
        "R": annotate_bam,
        "count_exon_exon_junction_reads": "-J" if count_junctions else "",
    }
    planned = FeatureCountsNode.PLAN_OUTPUTS(inputs, tmp_path)

    def materialize(_command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        for path in planned:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".bam":
                path.write_bytes(b"BAM")
            else:
                path.write_text("synthetic\n", encoding="utf-8")

    context = _fake_context(tmp_path, materialize)
    result = await FeatureCountsNode().run(
        **inputs,
        context=context,
        output_dir=tmp_path,
    )
    expected = {name: str(path) for name, path in FeatureCountsNode.MAP_PLANNED_OUTPUTS(planned).items()}
    assert result == {"outputs": expected}
    assert expected["counts"].endswith("/counts.tsv")
    assert expected["summary"].endswith("/summary.tsv")
    assert ("feature_lengths" in expected) is include_feature_lengths
    assert ("annotated_bam" in expected) is annotate_bam
    assert ("junction_counts" in expected) is count_junctions


@pytest.mark.parametrize("family", ["salmon", "kallisto", "featurecounts"])
def test_rna_families_reject_unmaterialized_primary_inputs(tmp_path: Path, family: str) -> None:
    missing = str(tmp_path / "missing-input")
    if family == "salmon":
        validation = SalmonIndexNode.VALIDATE_INPUTS({"transcripts": missing, "threads": 1})
    elif family == "kallisto":
        validation = KallistoIndexNode.VALIDATE_INPUTS({"transcripts": missing, "threads": 1})
    else:
        validation = FeatureCountsNode.VALIDATE_INPUTS({"alignment": missing, "anno_select": "builtin"})

    assert validation is not True
    assert "not a materialized file" in str(validation)
