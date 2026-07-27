from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.builtin.annotation_family import (
    IntersectGenesNode,
    ProkkaNode,
    SnpEffNode,
    VEPNode,
)
from bionodulo.nodes.registry import NodeRegistry


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
    assembly = tmp_path / "contigs.fa"
    assembly.write_text(">contig\nACGT\n", encoding="ascii")
    inputs = {
        "assembly": str(assembly),
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
        str(assembly),
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


def test_prokka_uses_native_auto_genetic_code_and_validates_filename(tmp_path: Path) -> None:
    assembly = tmp_path / "contigs.fa"
    assembly.write_text(">contig\nACGT\n", encoding="ascii")
    inputs = {"assembly": str(assembly), "prefix": "genome", "kingdom": "Bacteria"}
    assert "--gcode" not in ProkkaNode.render_command(inputs)
    assert ProkkaNode.VALIDATE_INPUTS({**inputs, "prefix": "../escape"}) == (
        "Input 'prefix' must be a filename without directory components"
    )
    assert "must be one of" in str(ProkkaNode.VALIDATE_INPUTS({**inputs, "kingdom": "Fungi"}))
    assert "at most 25" in str(ProkkaNode.VALIDATE_INPUTS({**inputs, "gcode": 26}))


def test_prokka_requires_a_materialized_nonempty_assembly(tmp_path: Path) -> None:
    base = {"prefix": "genome", "kingdom": "Bacteria"}
    missing = tmp_path / "missing.fa"
    directory = tmp_path / "assembly-dir"
    directory.mkdir()
    empty = tmp_path / "empty.fa"
    empty.touch()

    for assembly in (missing, directory):
        inputs = {**base, "assembly": assembly}
        assert ProkkaNode.VALIDATE_INPUTS(inputs) is True
        with pytest.raises(ValueError, match="materialized regular file"):
            ProkkaNode.PREPARE_EXECUTION(inputs, [])
    with pytest.raises(ValueError, match="must be non-empty"):
        ProkkaNode.PREPARE_EXECUTION({**base, "assembly": empty}, [])


def _snpeff_inputs(tmp_path: Path, **overrides: object) -> dict[str, object]:
    vcf = tmp_path / "inputs" / "variants.vcf.gz"
    vcf.parent.mkdir(parents=True, exist_ok=True)
    vcf.write_bytes(b"synthetic-vcf")
    database = tmp_path / "uploads" / "snpEffectPredictor.bin"
    database.parent.mkdir(parents=True, exist_ok=True)
    database.write_bytes(b"synthetic-predictor")
    values: dict[str, object] = {
        "vcf": str(vcf),
        "genome": "GRCh38.105",
        "database": str(database),
        "memory": 12,
        "output": str(tmp_path / "runs" / "snpeff"),
    }
    values.update(overrides)
    return values


def test_snpeff_captures_stdout_without_shell_redirection(tmp_path: Path) -> None:
    data_dir = tmp_path / "source-data"
    genome_dir = data_dir / "GRCh38.105"
    genome_dir.mkdir(parents=True)
    (genome_dir / "snpEff.config").write_text("GRCh38.105.genome : synthetic\n", encoding="ascii")
    inputs = _snpeff_inputs(
        tmp_path,
        data_dir=str(data_dir),
        canonical=True,
        no_upstream=True,
        no_downstream=True,
        no_intergenic=True,
    )
    outputs = SnpEffNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    SnpEffNode.PREPARE_EXECUTION(inputs, outputs)
    prepared_root = outputs[0].parent / "snpeff_data"

    assert SnpEffNode.STDOUT_OUTPUT_INDEX == 0
    assert SnpEffNode.render_command(inputs) == [
        "snpEff",
        "-Xmx12g",
        "-noLog",
        "-noDownload",
        "-v",
        # SnpEff resolves a genome through its config; without -c it falls back
        # to the bundled one and dies with "Property: '<genome>.genome' not
        # found" for any custom database.
        "-c",
        str(prepared_root / "snpEff.config"),
        "-dataDir",
        str(prepared_root),
        "-stats",
        str(tmp_path / "runs" / "snpeff" / "summary_report.html"),
        "-canon",
        "-no-upstream",
        "-no-downstream",
        "-no-intergenic",
        "GRCh38.105",
        str(tmp_path / "runs" / "snpeff" / "inputs" / "variants.vcf.gz"),
    ]
    assert [path.name for path in outputs] == [
        "annotated_vcf.vcf",
        "summary_report.html",
        "summary_report.genes.txt",
    ]
    assert Path(str(inputs["database"])) == prepared_root / "GRCh38.105" / "snpEffectPredictor.bin"
    assert Path(str(inputs["vcf"])) == outputs[0].parent / "inputs" / "variants.vcf.gz"
    assert (prepared_root / "GRCh38.105" / "snpEff.config").is_file()
    assert all(token not in {">", "|", "&&"} for token in SnpEffNode.render_command(inputs))


def test_snpeff_requires_materialized_inputs_and_stages_a_separate_predictor(tmp_path: Path) -> None:
    inputs = _snpeff_inputs(tmp_path)
    assert SnpEffNode.VALIDATE_INPUTS(inputs) is True
    missing_database = {**inputs, "database": tmp_path / "missing.bin"}
    assert SnpEffNode.VALIDATE_INPUTS(missing_database) is True
    with pytest.raises(ValueError, match="materialized regular file"):
        SnpEffNode.PREPARE_EXECUTION(
            missing_database,
            SnpEffNode.PLAN_OUTPUTS(missing_database, tmp_path / "missing-run"),
        )
    assert "at least 1" in str(SnpEffNode.VALIDATE_INPUTS({**inputs, "memory": 0}))
    for genome in ("../bad", " padded", "padded ", "-option", "bad genome"):
        assert "unpadded SnpEff identifier" in str(SnpEffNode.VALIDATE_INPUTS({**inputs, "genome": genome}))

    outputs = SnpEffNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    SnpEffNode.PREPARE_EXECUTION(inputs, outputs)
    expected = outputs[0].parent / "snpeff_data" / "GRCh38.105" / "snpEffectPredictor.bin"
    assert Path(str(inputs["database"])) == expected
    assert Path(str(inputs["data_dir"])) == expected.parents[1]
    assert expected.read_bytes() == b"synthetic-predictor"
    assert SnpEffNode.VALIDATE_INPUTS(inputs) is True


def test_snpeff_rejects_wrong_data_root_and_symlink_entries(tmp_path: Path) -> None:
    inputs = _snpeff_inputs(tmp_path)
    data_root = tmp_path / "data"
    data_root.mkdir()
    wrong_root_inputs = {**inputs, "data_dir": data_root}
    outputs = SnpEffNode.PLAN_OUTPUTS(wrong_root_inputs, tmp_path / "wrong-root-run")
    with pytest.raises(ValueError, match="data_dir/GRCh38[.]105.*materialized directory"):
        SnpEffNode.PREPARE_EXECUTION(wrong_root_inputs, outputs)

    genome_dir = data_root / "GRCh38.105"
    genome_dir.mkdir()
    target = tmp_path / "external.config"
    target.write_text("GRCh38.105.genome : external\n", encoding="ascii")
    (genome_dir / "snpEff.config").symlink_to(target)
    symlink_inputs = {**inputs, "data_dir": data_root}
    outputs = SnpEffNode.PLAN_OUTPUTS(symlink_inputs, tmp_path / "symlink-run")
    with pytest.raises(ValueError, match="must not contain symbolic links"):
        SnpEffNode.PREPARE_EXECUTION(symlink_inputs, outputs)


def test_snpeff_staging_never_deletes_an_overlapping_predictor(tmp_path: Path) -> None:
    inputs = _snpeff_inputs(tmp_path)
    outputs = SnpEffNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    prepared_database = outputs[0].parent / "snpeff_data" / "GRCh38.105" / "snpEffectPredictor.bin"
    prepared_database.parent.mkdir(parents=True)
    prepared_database.write_bytes(b"already-prepared")
    inputs["database"] = prepared_database

    SnpEffNode.PREPARE_EXECUTION(inputs, outputs)
    assert prepared_database.read_bytes() == b"already-prepared"

    nested_database = outputs[0].parent / "snpeff_data" / "GRCh38.105" / "other.bin"
    nested_database.write_bytes(b"must-survive")
    conflicting = {**_snpeff_inputs(tmp_path / "conflict"), "database": nested_database}
    with pytest.raises(ValueError, match="must not be inside"):
        SnpEffNode.PREPARE_EXECUTION(conflicting, outputs)
    assert nested_database.read_bytes() == b"must-survive"


def _make_vep_cache(
    root: Path,
    *,
    assembly: str = "GRCh38",
    info_assembly: str | None = None,
    info_species: str | None = "homo_sapiens",
    serialiser_type: str = "storable",
    include_capabilities: bool = True,
    include_info: bool = True,
    include_shard: bool = True,
    empty_shard: bool = False,
) -> Path:
    cache = root / f"113_{assembly}"
    cache.mkdir(parents=True, exist_ok=True)
    if include_info:
        info_lines = [f"assembly\t{info_assembly or assembly}"]
        if info_species is not None:
            info_lines.append(f"species\t{info_species}")
        if serialiser_type != "storable":
            info_lines.append(f"serialiser_type\t{serialiser_type}")
        if include_capabilities:
            info_lines.extend(("variation_cols\tvariation_name,AF", "sift\tb", "polyphen\tb"))
        (cache / "info.txt").write_text("\n".join(info_lines) + "\n", encoding="ascii")
    if include_shard:
        region = cache / "1"
        region.mkdir(exist_ok=True)
        suffix = "sereal" if serialiser_type == "sereal" else "gz"
        (region / f"1-1000000.{suffix}").write_bytes(b"" if empty_shard else b"synthetic-cache-shard")
    return cache


def _vep_inputs(tmp_path: Path, **overrides: object) -> dict[str, object]:
    vcf = tmp_path / "inputs" / "variants.vcf.gz"
    vcf.parent.mkdir(parents=True, exist_ok=True)
    vcf.write_bytes(b"synthetic-vcf")
    cache = _make_vep_cache(tmp_path / "cache")
    values: dict[str, object] = {
        "vcf": str(vcf),
        "cache_dir": str(cache),
        "assembly": "GRCh38",
        "species": "homo_sapiens",
        "threads": 8,
        "output_format": "vcf",
        "output": str(tmp_path / "runs" / "vep"),
    }
    values.update(overrides)
    return values


def test_vep_everything_uses_one_explicit_offline_cache(tmp_path: Path) -> None:
    inputs = _vep_inputs(tmp_path, everything=True)
    command = VEPNode.render_command(inputs)
    assert command == [
        "vep",
        "--input_file",
        str(tmp_path / "inputs" / "variants.vcf.gz"),
        "--output_file",
        str(tmp_path / "runs" / "vep" / "annotated_vcf.vcf"),
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
        str(tmp_path / "cache" / "113_GRCh38"),
        "--force_overwrite",
        "--everything",
        "--stats_file",
        str(tmp_path / "runs" / "vep" / "vep_report.html"),
    ]
    assert "--dir_cache" not in command


def test_vep_selective_annotations_and_indexed_clinvar(tmp_path: Path) -> None:
    clinvar = tmp_path / "clinvar" / "clinvar.vcf.gz"
    clinvar.parent.mkdir()
    clinvar.write_bytes(b"synthetic-clinvar")
    clinvar_index = tmp_path / "indexes" / "clinvar.vcf.gz.tbi"
    clinvar_index.parent.mkdir()
    clinvar_index.write_bytes(b"synthetic-tabix")
    inputs = _vep_inputs(
        tmp_path,
        everything=False,
        symbol=True,
        af=False,
        max_af=True,
        sift="s",
        polyphen="p",
        clinvar=str(clinvar),
        clinvar_index=str(clinvar_index),
        output_format="tab",
    )
    outputs = VEPNode.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    VEPNode.PREPARE_EXECUTION(inputs, outputs)
    command = VEPNode.render_command(inputs)
    staged_clinvar = outputs[0].parent / "custom_annotations" / "clinvar.vcf.gz"
    assert command[-4:] == [
        "--custom",
        f"file={staged_clinvar},short_name=ClinVar,format=vcf,type=exact,fields=CLNSIG",
        "--stats_file",
        str(tmp_path / "runs" / "vep" / "vep_report.html"),
    ]
    assert "--everything" not in command
    assert "--symbol" in command
    assert "--af" not in command
    assert command[command.index("--sift") : command.index("--sift") + 2] == ["--sift", "s"]
    assert command[command.index("--polyphen") : command.index("--polyphen") + 2] == [
        "--polyphen",
        "p",
    ]
    assert [path.name for path in outputs] == [
        "annotated_vcf.tab",
        "vep_report.html",
    ]
    assert Path(str(inputs["clinvar_index"])) == Path(f"{staged_clinvar}.tbi")
    assert VEPNode.VALIDATE_INPUTS(inputs) is True


def test_vep_rejects_missing_or_mismatched_custom_vcf_index(tmp_path: Path) -> None:
    inputs = _vep_inputs(tmp_path)
    clinvar = tmp_path / "clinvar.vcf.gz"
    clinvar.write_bytes(b"synthetic-clinvar")
    wrong_index = tmp_path / "clinvar.tbi"
    wrong_index.write_bytes(b"synthetic-tabix")
    assert "named exactly '<clinvar>.tbi'" in str(
        VEPNode.VALIDATE_INPUTS({**inputs, "clinvar": clinvar, "clinvar_index": wrong_index})
    )
    assert VEPNode.VALIDATE_INPUTS({**inputs, "clinvar_index": wrong_index}) == (
        "Input 'clinvar_index' requires 'clinvar'"
    )
    assert "must be one of" in str(VEPNode.VALIDATE_INPUTS({**inputs, "output_format": "json"}))

    missing_index = tmp_path / "missing" / "clinvar.vcf.gz.tbi"
    materialized_inputs = {**inputs, "clinvar": clinvar, "clinvar_index": missing_index}
    assert VEPNode.VALIDATE_INPUTS(materialized_inputs) is True
    with pytest.raises(ValueError, match="clinvar_index.*materialized regular file"):
        VEPNode.PREPARE_EXECUTION(
            materialized_inputs,
            VEPNode.PLAN_OUTPUTS(materialized_inputs, tmp_path / "missing-index-run"),
        )


def test_vep_rejects_cache_roots_wrong_releases_and_incomplete_leaves(tmp_path: Path) -> None:
    inputs = _vep_inputs(tmp_path)
    assert VEPNode.VALIDATE_INPUTS(inputs) is True
    VEPNode.PREPARE_EXECUTION(inputs, VEPNode.PLAN_OUTPUTS(inputs, tmp_path / "valid-run"))
    assert "exact VEP cache leaf" in str(
        VEPNode.VALIDATE_INPUTS({**inputs, "cache_dir": Path(str(inputs["cache_dir"])).parent})
    )

    wrong_release = tmp_path / "wrong-release" / "112_GRCh38"
    wrong_release.mkdir(parents=True)
    (wrong_release / "info.txt").write_text("assembly\tGRCh38\n", encoding="ascii")
    region = wrong_release / "1"
    region.mkdir()
    (region / "1-1000000.gz").write_bytes(b"shard")
    assert "named '113_GRCh38'" in str(VEPNode.VALIDATE_INPUTS({**inputs, "cache_dir": wrong_release}))

    missing_info_inputs = {
        **inputs,
        "cache_dir": _make_vep_cache(tmp_path / "missing-info", include_info=False),
    }
    with pytest.raises(ValueError, match="cache_dir/info[.]txt"):
        VEPNode.PREPARE_EXECUTION(missing_info_inputs, [])
    mismatch = _make_vep_cache(tmp_path / "mismatch", info_assembly="GRCh37")
    with pytest.raises(ValueError, match="does not match requested assembly"):
        VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": mismatch}, [])
    no_shard = _make_vep_cache(tmp_path / "no-shard", include_shard=False)
    with pytest.raises(ValueError, match="transcript shard"):
        VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": no_shard}, [])
    empty_shard = _make_vep_cache(tmp_path / "empty-shard", empty_shard=True)
    with pytest.raises(ValueError, match="readable, non-empty.*transcript shard"):
        VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": empty_shard}, [])


def test_vep_accepts_sereal_cache_and_enforces_requested_capabilities(tmp_path: Path) -> None:
    inputs = _vep_inputs(tmp_path)
    sereal_cache = _make_vep_cache(tmp_path / "sereal", serialiser_type="sereal")
    VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": sereal_cache}, [])

    limited_cache = _make_vep_cache(tmp_path / "limited", include_capabilities=False)
    with pytest.raises(ValueError, match="variation columns required for AF"):
        VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": limited_cache, "af": True}, [])
    with pytest.raises(ValueError, match="requested SIFT capability"):
        VEPNode.PREPARE_EXECUTION({**inputs, "cache_dir": limited_cache, "sift": "b"}, [])


def test_vep_stages_tilde_expanded_clinvar_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    clinvar = home / "clinvar.vcf.gz"
    clinvar.write_bytes(b"synthetic-clinvar")
    clinvar_index = home / "clinvar.vcf.gz.tbi"
    clinvar_index.write_bytes(b"synthetic-tabix")
    monkeypatch.setenv("HOME", str(home))
    inputs = _vep_inputs(
        tmp_path,
        clinvar="~/clinvar.vcf.gz",
        clinvar_index="~/clinvar.vcf.gz.tbi",
    )
    outputs = VEPNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    VEPNode.PREPARE_EXECUTION(inputs, outputs)

    staged = outputs[0].parent / "custom_annotations" / "clinvar.vcf.gz"
    assert Path(str(inputs["clinvar"])) == staged
    assert staged.read_bytes() == b"synthetic-clinvar"
    assert Path(str(inputs["clinvar_index"])).read_bytes() == b"synthetic-tabix"


@pytest.mark.asyncio
async def test_annotation_dry_run_accepts_unmaterialized_runtime_inputs(tmp_path: Path) -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    workflow = {
        "name": "Annotation dry-run contract",
        "nodes": [
            {
                "id": "prokka-preview",
                "type": "prokka",
                "params": {"assembly": "/planned/contigs.fa"},
            },
            {
                "id": "snpeff-preview",
                "type": "snpeff",
                "params": {
                    "vcf": "/planned/variants.vcf.gz",
                    "genome": "GRCh38.105",
                    "database": "/planned/snpEffectPredictor.bin",
                },
            },
            {
                "id": "vep-preview",
                "type": "vep",
                "params": {
                    "vcf": "/planned/variants.vcf.gz",
                    "cache_dir": "/planned/homo_sapiens/113_GRCh38",
                },
            },
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )

    preview = await executor.dry_run("annotation-preview", workflow)

    plans = {node["node_id"]: node for node in preview["nodes"]}
    assert plans["prokka-preview"]["command"][-1] == "/planned/contigs.fa"
    snpeff_command = plans["snpeff-preview"]["command"]
    assert snpeff_command[-2:] == ["GRCh38.105", "/planned/variants.vcf.gz"]
    assert snpeff_command[snpeff_command.index("-dataDir") + 1].endswith("/snpeff-preview/snpeff/snpeff_data")
    vep_command = plans["vep-preview"]["command"]
    assert vep_command[vep_command.index("--full_cache_dir") + 1] == ("/planned/homo_sapiens/113_GRCh38")


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
