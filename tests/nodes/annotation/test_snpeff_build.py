"""Contract tests for the SnpEff custom-database build node.

`snpeff` runs with `-noDownload`, so a workflow annotating against its own
reference needs a predictor it built itself. These pin the layout snpEff's build
requires: <dataDir>/<genome>/{sequences.fa,genes.<ext>} in, snpEffectPredictor.bin
out, at exactly the path the node declares as its output.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.annotation_family import SnpEffBuildNode

REFERENCE = ">chr1\nACGTACGTAC\n"
ANNOTATION = 'chr1\ttest\tgene\t1\t9\t.\t+\t.\tID=g1\n'


def _inputs(tmp_path: Path, *, gzip_inputs: bool = False, **overrides) -> dict:
    suffix = ".gz" if gzip_inputs else ""
    reference = tmp_path / f"ref.fa{suffix}"
    annotation = tmp_path / f"genes.gff{suffix}"
    if gzip_inputs:
        reference.write_bytes(gzip.compress(REFERENCE.encode()))
        annotation.write_bytes(gzip.compress(ANNOTATION.encode()))
    else:
        reference.write_text(REFERENCE, encoding="ascii")
        annotation.write_text(ANNOTATION, encoding="ascii")
    inputs = {
        "reference": str(reference),
        "annotation": str(annotation),
        "genome": "Wildtype",
        "output": str(tmp_path / "runs"),
    }
    inputs.update(overrides)
    return inputs


def test_predictor_is_planned_where_snpeff_actually_writes_it(tmp_path: Path) -> None:
    """snpEff build writes into <dataDir>/<genome>/, not the node root.

    Planning any other path would let the tool succeed while the declared output
    is missing, which the runner reports as a failed node.
    """
    inputs = _inputs(tmp_path)
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")

    assert len(outputs) == 1
    assert outputs[0].name == "snpEffectPredictor.bin"
    assert outputs[0].parent.name == "Wildtype"
    assert outputs[0].parent.parent.name == "snpeff_data"


def test_prepare_lays_out_the_files_snpeff_build_reads(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)

    genome_dir = outputs[0].parent
    assert (genome_dir / "sequences.fa").read_text(encoding="ascii") == REFERENCE
    assert (genome_dir / "genes.gff").read_text(encoding="ascii") == ANNOTATION
    assert inputs["data_dir"] == str(genome_dir.parent)


def test_gzipped_inputs_are_expanded(tmp_path: Path) -> None:
    """Reference genomes ship gzipped from NCBI/Ensembl; snpEff build wants text."""
    inputs = _inputs(tmp_path, gzip_inputs=True)
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)

    genome_dir = outputs[0].parent
    assert (genome_dir / "sequences.fa").read_text(encoding="ascii") == REFERENCE
    assert (genome_dir / "genes.gff").read_text(encoding="ascii") == ANNOTATION


def test_command_is_direct_argv_with_no_shell_metacharacters(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)
    command = SnpEffBuildNode.render_command(inputs)

    assert command[:3] == ["snpEff", "build", "-Xmx8g"]
    assert "-gff3" in command
    assert command[-1] == "Wildtype"
    assert "-dataDir" in command
    assert command[command.index("-dataDir") + 1] == str(outputs[0].parent.parent)
    assert all(token not in {">", "|", "&&", ";"} for token in command)
    assert SnpEffBuildNode.SHELL is False


def test_annotation_format_selects_the_filename_and_flag(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, annotation_format="gtf22")
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)

    assert (outputs[0].parent / "genes.gtf").is_file()
    assert "-gtf22" in SnpEffBuildNode.render_command(inputs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"genome": "bad genome"},
        {"genome": ""},
        {"annotation_format": "bogus"},
        {"memory": 0},
        {"memory": 999},
    ],
)
def test_invalid_inputs_are_rejected(tmp_path: Path, overrides: dict) -> None:
    assert SnpEffBuildNode.VALIDATE_INPUTS(_inputs(tmp_path, **overrides)) is not True


def test_missing_reference_is_rejected_before_execution(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["reference"] = str(tmp_path / "does-not-exist.fa")
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")

    with pytest.raises(ValueError, match="reference"):
        SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)


def test_build_output_feeds_the_snpeff_annotation_node(tmp_path: Path) -> None:
    """The two nodes must actually compose: build emits what snpeff requires."""
    from bionodulo.nodes.builtin.annotation_family import SnpEffNode

    assert "database" in SnpEffNode.INPUT_TYPES()["required"]
    assert SnpEffBuildNode.RETURN_NAMES[0] == "predictor_database"
    # snpeff also accepts the data root as `data_dir`, which build returns so a
    # graph can wire the whole genome directory rather than just the .bin.
    assert "data_dir" in SnpEffNode.INPUT_TYPES()["optional"]
    assert SnpEffBuildNode.RETURN_NAMES[1] == "data_dir"


def test_config_declares_the_genome_so_snpeff_can_resolve_it(tmp_path: Path) -> None:
    """Staging files on disk is not enough: SnpEff looks the genome up in config.

    Without this the cloud run failed with
        java.lang.RuntimeException: Property: 'Wildtype.genome' not found
    because SnpEff fell back to its bundled snpEff.config, which lists only
    SnpEff's own published genomes -- i.e. never a workflow-built one.
    """
    inputs = _inputs(tmp_path)
    outputs = SnpEffBuildNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffBuildNode.PREPARE_EXECUTION(inputs, outputs)

    data_root = outputs[0].parent.parent
    config = data_root / "snpEff.config"
    text = config.read_text(encoding="utf-8")
    assert "Wildtype.genome" in text
    assert f"data.dir = {data_root}" in text

    command = SnpEffBuildNode.render_command(inputs)
    assert "-c" in command
    assert command[command.index("-c") + 1] == str(config)


def test_snpeff_annotation_also_declares_a_custom_genome(tmp_path: Path) -> None:
    """The annotator has the same requirement as the builder."""
    from bionodulo.nodes.builtin.annotation_family import SnpEffNode

    database = tmp_path / "snpEffectPredictor.bin"
    database.write_bytes(b"predictor")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n", encoding="ascii")
    inputs = {
        "vcf": str(vcf),
        "genome": "Wildtype",
        "database": str(database),
        "output": str(tmp_path / "runs" / "snpeff"),
    }
    outputs = SnpEffNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffNode.PREPARE_EXECUTION(inputs, outputs)

    config = Path(inputs["config"])
    assert "Wildtype.genome" in config.read_text(encoding="utf-8")
    command = SnpEffNode.render_command(inputs)
    assert command[command.index("-c") + 1] == str(config)
