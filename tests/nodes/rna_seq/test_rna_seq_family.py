from __future__ import annotations

import inspect
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
        if issubclass(obj, BaseNode)
        and obj not in {BaseNode}
        and obj.__module__ == rna_seq.__name__
        and obj.NODE_ID
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
    assert KallistoIndexNode.VERSION == KallistoQuantNode.VERSION == "0.52.0"
    assert KallistoIndexNode.GIT_COMMIT == "4e9f29cf3b021260415430c057a22469ca081391"
    assert FeatureCountsNode.VERSION == "2.1.1"
    assert FeatureCountsNode.SOURCE_SHA256 == (
        "6392d7c66831cdd767e58251892a79a51b6fab8ed0ba9671ad5e85ff1ab01eaa"
    )

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
    validation = SalmonQuantNode.VALIDATE_INPUTS(
        {"index": str(index), "threads": 1}
    )
    assert message in str(validation)


@pytest.mark.parametrize(
    ("relative_path", "empty"),
    [("index.ssi.mphf", False), ("refseq.bin", True)],
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
    assert "even number" in str(
        SalmonQuantNode.VALIDATE_INPUTS({**inputs, "reads": reads[:3]})
    )
    assert "not valid" in str(SalmonQuantNode.VALIDATE_INPUTS({**inputs, "lib_type": "SF"}))


def test_salmon_quant_fake_execution_keeps_quant_directory(tmp_path: Path) -> None:
    index = tmp_path / "salmon-index"
    _materialize_salmon_index(index)
    reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1.fq.gz", "r2.fq.gz")
    ]

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "quant.sf").write_text("Name\tTPM\tNumReads\n", encoding="utf-8")
        (output / "cmd_info.json").write_text("{}", encoding="utf-8")
        (output / "lib_format_counts.json").write_text("{}", encoding="utf-8")
        (output / "aux_info").mkdir()
        (output / "aux_info" / "meta_info.json").write_text("{}", encoding="utf-8")
        (output / "libParams").mkdir()
        (output / "libParams" / "flenDist.txt").write_text("0.5", encoding="utf-8")
        (output / "logs").mkdir()
        (output / "logs" / "salmon_quant.log").write_text("done\n", encoding="utf-8")

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
    [("lib_format_counts.json", True), ("logs/salmon_quant.log", False)],
)
async def test_salmon_quant_rejects_missing_or_empty_companion_artifacts(
    tmp_path: Path,
    invalid_relative_path: str,
    leave_missing: bool,
) -> None:
    index = tmp_path / "salmon-index"
    _materialize_salmon_index(index)
    reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1.fq.gz", "r2.fq.gz")
    ]

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


@pytest.mark.asyncio
async def test_kallisto_index_rejects_zero_byte_output_after_zero_exit(tmp_path: Path) -> None:
    transcripts = _materialize_file(tmp_path / "transcripts.fa", ">tx\nACGT\n")

    def materialize(command: list[str] | str, _kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        index = Path(command[command.index("-i") + 1])
        index.parent.mkdir(parents=True, exist_ok=True)
        index.touch()

    with pytest.raises(RuntimeError, match="Kallisto index output is missing or empty"):
        await KallistoIndexNode().run(
            transcripts=transcripts,
            threads=1,
            context=_fake_context(tmp_path, materialize),
            output_dir=tmp_path,
        )


def test_kallisto_quant_requires_even_pairs_and_single_end_fragment_parameters(tmp_path: Path) -> None:
    index = _materialize_file(tmp_path / "transcripts.idx", "index\n")
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
    assert "even number" in str(
        KallistoQuantNode.VALIDATE_INPUTS({**paired, "reads": paired_reads[:3]})
    )
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
    assert KallistoQuantNode.render_command(single)[-7:] == [
        "-b",
        "25",
        "--single",
        "-l",
        "200.0",
        "-s",
        "20.0",
        single["reads"][0],
    ][-7:]
    assert "requires fragment_length" in str(
        KallistoQuantNode.VALIDATE_INPUTS({k: v for k, v in single.items() if k not in {"fragment_length", "sd"}})
    )


def test_kallisto_quant_fake_execution_captures_stderr_and_native_outputs(tmp_path: Path) -> None:
    index = _materialize_file(tmp_path / "transcripts.idx", "index\n")
    reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1.fq.gz", "r2.fq.gz")
    ]

    def materialize(command: list[str] | str, kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "abundance.tsv").write_text("target_id\ttpm\test_counts\n", encoding="utf-8")
        (output / "run_info.json").write_text("{}", encoding="utf-8")
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
@pytest.mark.parametrize("leave_missing", [True, False])
async def test_kallisto_quant_rejects_missing_or_empty_run_info(
    tmp_path: Path,
    leave_missing: bool,
) -> None:
    index = _materialize_file(tmp_path / "transcripts.idx", "index\n")
    reads = [
        _materialize_file(tmp_path / name, "@read\nACGT\n+\n!!!!\n")
        for name in ("r1.fq.gz", "r2.fq.gz")
    ]

    def materialize(command: list[str] | str, kwargs: dict[str, Any]) -> None:
        assert isinstance(command, list)
        output = Path(command[command.index("-o") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "abundance.tsv").write_text("target_id\ttpm\test_counts\n", encoding="utf-8")
        if not leave_missing:
            (output / "run_info.json").write_text("", encoding="utf-8")
        Path(kwargs["stderr_path"]).write_text("[quant] complete\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="run_info.json"):
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
    }
    assert FeatureCountsNode.VALIDATE_INPUTS(inputs) is True
    command = FeatureCountsNode.render_command({**inputs, "output": str(tmp_path / "featurecounts")})
    assert "-T 6" in command
    assert "${GALAXY_SLOTS:-2}" not in command
    assert "-p --countReadPairs" in command
    assert "-P -d 50 -D 600 -B" in command
    assert "-O --fraction" in command
    assert "fraction requires" in str(
        FeatureCountsNode.VALIDATE_INPUTS({**inputs, "multifeat": ""})
    )
    assert "requires only_both_ends" in str(
        FeatureCountsNode.VALIDATE_INPUTS({**inputs, "only_both_ends": False})
    )


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
    expected = {
        name: str(path)
        for name, path in FeatureCountsNode.MAP_PLANNED_OUTPUTS(planned).items()
    }
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
        validation = SalmonIndexNode.VALIDATE_INPUTS(
            {"transcripts": missing, "threads": 1}
        )
    elif family == "kallisto":
        validation = KallistoIndexNode.VALIDATE_INPUTS(
            {"transcripts": missing, "threads": 1}
        )
    else:
        validation = FeatureCountsNode.VALIDATE_INPUTS(
            {"alignment": missing, "anno_select": "builtin"}
        )

    assert validation is not True
    assert "not a materialized file" in str(validation)
