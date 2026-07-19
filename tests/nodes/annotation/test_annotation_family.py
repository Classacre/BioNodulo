from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.annotation_family import (
    IntersectGenesNode,
    ProkkaNode,
    SnpEffNode,
    VEPNode,
)


@pytest.mark.parametrize(
    ("node", "node_id", "version", "commit", "packages"),
    [
        (
            ProkkaNode,
            "prokka",
            "1.15.6",
            "d7b72388989e1fba42c8c68482a36a70dbd3bac4",
            {"prokka": "1.15.6"},
        ),
        (
            SnpEffNode,
            "snpeff",
            "5.2",
            "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2",
            {"snpeff": "5.2", "openjdk": "17.*"},
        ),
        (
            VEPNode,
            "vep",
            "113.4",
            "a6786e4357f442a81624f58d9e79f343909d717f",
            {"ensembl-vep": "113.4"},
        ),
        (
            IntersectGenesNode,
            "intersect_genes",
            "1.0.0",
            "ca74cf20800257fe98db3f8b4787885f6815b8fb",
            None,
        ),
    ],
)
def test_pinned_authority_metadata(
    node: type,
    node_id: str,
    version: str,
    commit: str,
    packages: dict[str, str] | None,
) -> None:
    assert node.NODE_ID == node_id
    assert node.VERSION == version
    assert node.GIT_COMMIT == commit
    assert node.GIT_URL.startswith("https://github.com/")
    assert node.SOURCE_URL.startswith("https://github.com/")
    assert node.UPSTREAM_SOURCE
    assert node.EXIT_SEMANTICS
    if packages is not None:
        assert node.SHELL is False
        assert dict(node.CONDA_PACKAGE_CONSTRAINTS) == packages


def test_source_defaults_are_recorded_in_input_metadata() -> None:
    assert ProkkaNode.INPUT_TYPES()["optional"]["threads"][1]["default"] == 8
    assert ProkkaNode.INPUT_TYPES()["optional"]["gcode"][1]["default"] == 0
    assert SnpEffNode.INPUT_TYPES()["optional"]["memory"][1]["default"] == 8
    vep_options = VEPNode.INPUT_TYPES()["optional"]
    assert vep_options["threads"][1]["default"] == 1
    assert vep_options["everything"][1]["default"] is False
    assert vep_options["symbol"][1]["default"] is False
    assert vep_options["sift"][1]["default"] == ""


def test_prokka_direct_argv_and_documented_outputs(tmp_path: Path) -> None:
    inputs = {
        "assembly": "/inputs/contigs.fa",
        "threads": 12,
        "prefix": "isolate_7",
        "kingdom": "Archaea",
        "genus": "Pyrococcus",
        "species": "furiosus",
        "strain": "DSM_3638",
        "gcode": 11,
        "output": "/runs/prokka",
    }

    assert ProkkaNode.render_command(inputs) == [
        "prokka",
        "--outdir",
        "/runs/prokka",
        "--prefix",
        "isolate_7",
        "--cpus",
        "12",
        "--kingdom",
        "Archaea",
        "--force",
        "--genus",
        "Pyrococcus",
        "--species",
        "furiosus",
        "--strain",
        "DSM_3638",
        "--gcode",
        "11",
        "/inputs/contigs.fa",
    ]
    assert [path.name for path in ProkkaNode.PLAN_OUTPUTS(inputs, tmp_path)] == [
        "isolate_7.gff",
        "isolate_7.gbk",
        "isolate_7.faa",
        "isolate_7.fna",
        "isolate_7.ffn",
        "isolate_7.sqn",
        "isolate_7.fsa",
        "isolate_7.tbl",
        "isolate_7.err",
        "isolate_7.log",
        "isolate_7.txt",
        "isolate_7.tsv",
    ]


def test_prokka_uses_native_auto_genetic_code_and_validates_filename() -> None:
    inputs = {"assembly": "contigs.fa", "prefix": "genome", "kingdom": "Bacteria"}
    assert "--gcode" not in ProkkaNode.render_command(inputs)
    assert ProkkaNode.VALIDATE_INPUTS({**inputs, "prefix": "../escape"}) == (
        "Input 'prefix' must be a filename without directory components"
    )
    assert "must be one of" in str(ProkkaNode.VALIDATE_INPUTS({**inputs, "kingdom": "Fungi"}))
    assert "at most 25" in str(ProkkaNode.VALIDATE_INPUTS({**inputs, "gcode": 26}))


def _snpeff_inputs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "vcf": "/inputs/variants.vcf.gz",
        "genome": "GRCh38.105",
        "data_dir": "/refs/snpeff",
        "database": "/refs/snpeff/GRCh38.105/snpEffectPredictor.bin",
        "memory": 12,
        "output": "/runs/snpeff",
    }
    values.update(overrides)
    return values


def test_snpeff_captures_stdout_without_shell_redirection(tmp_path: Path) -> None:
    inputs = _snpeff_inputs(
        canonical=True,
        no_upstream=True,
        no_downstream=True,
        no_intergenic=True,
    )

    assert SnpEffNode.STDOUT_OUTPUT_INDEX == 0
    assert SnpEffNode.render_command(inputs) == [
        "snpEff",
        "-Xmx12g",
        "-noLog",
        "-v",
        "-dataDir",
        "/refs/snpeff",
        "-stats",
        "/runs/snpeff/summary_report.html",
        "-canon",
        "-no-upstream",
        "-no-downstream",
        "-no-intergenic",
        "GRCh38.105",
        "/inputs/variants.vcf.gz",
    ]
    assert [path.name for path in SnpEffNode.PLAN_OUTPUTS(inputs, tmp_path)] == [
        "annotated_vcf.vcf",
        "summary_report.html",
        "summary_report.genes.txt",
    ]
    assert all(token not in {">", "|", "&&"} for token in SnpEffNode.render_command(inputs))


def test_snpeff_requires_the_exact_predictor_database() -> None:
    assert SnpEffNode.VALIDATE_INPUTS(_snpeff_inputs()) is True
    validation = SnpEffNode.VALIDATE_INPUTS(_snpeff_inputs(database="/refs/snpeff/other/snpEffectPredictor.bin"))
    assert "exact path '/refs/snpeff/GRCh38.105/snpEffectPredictor.bin'" in str(validation)
    assert "at least 1" in str(SnpEffNode.VALIDATE_INPUTS(_snpeff_inputs(memory=0)))
    assert "genome identifier" in str(SnpEffNode.VALIDATE_INPUTS(_snpeff_inputs(genome="../bad")))


def _vep_inputs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "vcf": "/inputs/variants.vcf.gz",
        "cache_dir": "/refs/vep/homo_sapiens/113_GRCh38",
        "assembly": "GRCh38",
        "species": "homo_sapiens",
        "threads": 8,
        "output_format": "vcf",
        "output": "/runs/vep",
    }
    values.update(overrides)
    return values


def test_vep_everything_uses_one_explicit_offline_cache() -> None:
    command = VEPNode.render_command(_vep_inputs(everything=True))
    assert command == [
        "vep",
        "--input_file",
        "/inputs/variants.vcf.gz",
        "--output_file",
        "/runs/vep/annotated_vcf.vcf",
        "--format",
        "vcf",
        "--vcf",
        "--fork",
        "8",
        "--species",
        "homo_sapiens",
        "--assembly",
        "GRCh38",
        "--offline",
        "--full_cache_dir",
        "/refs/vep/homo_sapiens/113_GRCh38",
        "--force_overwrite",
        "--everything",
        "--stats_file",
        "/runs/vep/vep_report.html",
    ]
    assert "--dir_cache" not in command


def test_vep_selective_annotations_and_indexed_clinvar(tmp_path: Path) -> None:
    inputs = _vep_inputs(
        everything=False,
        symbol=True,
        af=False,
        max_af=True,
        sift="s",
        polyphen="p",
        clinvar="/refs/clinvar.vcf.gz",
        clinvar_index="/refs/clinvar.vcf.gz.tbi",
        output_format="tab",
    )
    command = VEPNode.render_command(inputs)
    assert command[-4:] == [
        "--custom",
        "file=/refs/clinvar.vcf.gz,short_name=ClinVar,format=vcf,type=exact,fields=CLNSIG",
        "--stats_file",
        "/runs/vep/vep_report.html",
    ]
    assert "--everything" not in command
    assert "--symbol" in command
    assert "--af" not in command
    assert command[command.index("--sift") : command.index("--sift") + 2] == ["--sift", "s"]
    assert command[command.index("--polyphen") : command.index("--polyphen") + 2] == [
        "--polyphen",
        "p",
    ]
    assert [path.name for path in VEPNode.PLAN_OUTPUTS(inputs, tmp_path)] == [
        "annotated_vcf.tab",
        "vep_report.html",
    ]


def test_vep_rejects_missing_or_mismatched_custom_vcf_index() -> None:
    assert "exact path '/refs/clinvar.vcf.gz.tbi'" in str(
        VEPNode.VALIDATE_INPUTS(_vep_inputs(clinvar="/refs/clinvar.vcf.gz", clinvar_index="/refs/clinvar.tbi"))
    )
    assert VEPNode.VALIDATE_INPUTS(_vep_inputs(clinvar_index="/refs/orphan.tbi")) == (
        "Input 'clinvar_index' requires 'clinvar'"
    )
    assert "must be one of" in str(VEPNode.VALIDATE_INPUTS(_vep_inputs(output_format="json")))


@pytest.mark.asyncio
async def test_intersect_genes_json_contract_is_deterministic(tmp_path: Path) -> None:
    query = tmp_path / "query.tsv"
    query.write_text("gene\tlog2fc\nTp53\t2\nEGFR\t1\ntp53\t3\n\n", encoding="utf-8")
    database = tmp_path / "sets.json"
    database.write_text(
        json.dumps({"RTK": ["EGFR", "ERBB2"], "Checkpoint": ["TP53", "TP53", "CDKN1A"]}),
        encoding="utf-8",
    )

    overlap_path, summary_path = await IntersectGenesNode().run(
        input_genes=query,
        database=database,
        input_column="gene",
        database_format="auto",
        case_sensitive=False,
        output_dir=tmp_path / "out",
    )

    with Path(overlap_path).open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle, delimiter="\t")) == [
            {"gene": "Tp53", "gene_set": "Checkpoint"},
            {"gene": "EGFR", "gene_set": "RTK"},
        ]
    assert json.loads(Path(summary_path).read_text(encoding="utf-8")) == {
        "query_gene_count": 2,
        "overlap_gene_count": 2,
        "sets": [
            {"gene_set": "Checkpoint", "overlap_count": 1, "set_size": 2, "genes": ["Tp53"]},
            {"gene_set": "RTK", "overlap_count": 1, "set_size": 2, "genes": ["EGFR"]},
        ],
    }


@pytest.mark.asyncio
async def test_intersect_genes_auto_detects_csv_database(tmp_path: Path) -> None:
    query = tmp_path / "genes.txt"
    query.write_text("A\nB\n", encoding="utf-8")
    database = tmp_path / "sets.csv"
    database.write_text("gene_set,gene\nset2,B\nset1,A\n", encoding="utf-8")

    overlap_path, _ = await IntersectGenesNode().run(
        input_genes=query,
        database=database,
        output_dir=tmp_path,
    )
    assert Path(overlap_path).read_text(encoding="utf-8").splitlines() == [
        "gene\tgene_set",
        "A\tset1",
        "B\tset2",
    ]


@pytest.mark.asyncio
async def test_intersect_genes_fails_closed_on_bad_table_schema(tmp_path: Path) -> None:
    query = tmp_path / "genes.txt"
    query.write_text("A\n", encoding="utf-8")
    database = tmp_path / "bad.tsv"
    database.write_text("pathway\tmember\nset1\tA\n", encoding="utf-8")

    with pytest.raises(ValueError, match="gene_set and gene"):
        await IntersectGenesNode().run(
            input_genes=query,
            database=database,
            database_format="tsv",
            output_dir=tmp_path,
        )
