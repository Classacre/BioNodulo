from __future__ import annotations

import asyncio
import csv
import json
import os
import subprocess
from pathlib import Path

import pytest

from bionodulo.execution.executor import ExecutionContext
from bionodulo.nodes.builtin.rna_seq_family.tximport import TximportSalmonNode
from bionodulo.nodes.registry import NodeRegistry


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "tximport"
SAMPLE_IDS = ("control", "treated")
FIXED_QUANT = {
    "control": {
        "tx1": {"EffectiveLength": 800.0, "TPM": 300000.0, "NumReads": 30.0},
        "tx2": {"EffectiveLength": 300.0, "TPM": 200000.0, "NumReads": 10.0},
        "tx3": {"EffectiveLength": 1000.0, "TPM": 500000.0, "NumReads": 60.0},
    },
    "treated": {
        "tx1": {"EffectiveLength": 750.0, "TPM": 100000.0, "NumReads": 10.0},
        "tx2": {"EffectiveLength": 250.0, "TPM": 400000.0, "NumReads": 40.0},
        "tx3": {"EffectiveLength": 950.0, "TPM": 500000.0, "NumReads": 50.0},
    },
}
FIXED_TX2GENE = {"tx1": "geneA", "tx2": "geneA", "tx3": "geneB"}


def _inputs() -> dict[str, object]:
    return {
        "quant_files": [
            str(FIXTURE / "sample1" / "quant.sf"),
            str(FIXTURE / "sample2" / "quant.sf"),
        ],
        "sample_ids": ["control", "treated"],
        "tx2gene": str(FIXTURE / "tx2gene.tsv"),
        "counts_from_abundance": "no",
    }


def _matrix(path: Path) -> tuple[list[str], dict[str, list[float]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        rows = {row[0]: [float(value) for value in row[1:]] for row in reader}
    return header, rows


def _hand_computed_gene_oracle(mode: str) -> dict[str, dict[str, list[float]]]:
    """Compute the three gene matrices from the fixed quant.sf values in Python."""
    parsed_quant: dict[str, dict[str, dict[str, float]]] = {}
    for sample_id, directory in zip(SAMPLE_IDS, ("sample1", "sample2"), strict=True):
        with (FIXTURE / directory / "quant.sf").open(encoding="utf-8", newline="") as handle:
            parsed_quant[sample_id] = {
                row["Name"]: {
                    "EffectiveLength": float(row["EffectiveLength"]),
                    "TPM": float(row["TPM"]),
                    "NumReads": float(row["NumReads"]),
                }
                for row in csv.DictReader(handle, delimiter="\t")
            }
    assert parsed_quant == FIXED_QUANT
    with (FIXTURE / "tx2gene.tsv").open(encoding="utf-8", newline="") as handle:
        parsed_mapping = {
            row["transcript_id"]: row["gene_id"]
            for row in csv.DictReader(handle, delimiter="\t")
        }
    assert parsed_mapping == FIXED_TX2GENE

    genes = ("geneA", "geneB")
    transcripts_by_gene = {
        gene: tuple(tx for tx, mapped_gene in FIXED_TX2GENE.items() if mapped_gene == gene)
        for gene in genes
    }
    abundance = {
        gene: [
            sum(FIXED_QUANT[sample][tx]["TPM"] for tx in transcripts_by_gene[gene])
            for sample in SAMPLE_IDS
        ]
        for gene in genes
    }
    unscaled_counts = {
        gene: [
            sum(FIXED_QUANT[sample][tx]["NumReads"] for tx in transcripts_by_gene[gene])
            for sample in SAMPLE_IDS
        ]
        for gene in genes
    }
    effective_length = {
        gene: [
            sum(
                FIXED_QUANT[sample][tx]["TPM"]
                * FIXED_QUANT[sample][tx]["EffectiveLength"]
                for tx in transcripts_by_gene[gene]
            )
            / abundance[gene][sample_index]
            for sample_index, sample in enumerate(SAMPLE_IDS)
        ]
        for gene in genes
    }

    if mode == "no":
        counts = unscaled_counts
    else:
        # tximport 1.38.2 makeCountsFromAbundance uses abundance directly for
        # scaledTPM, abundance * rowMeans(gene length) for lengthScaledTPM,
        # then rescales each sample to the original count-column total.
        library_totals = [
            sum(unscaled_counts[gene][sample_index] for gene in genes)
            for sample_index in range(len(SAMPLE_IDS))
        ]
        average_gene_length = {
            gene: sum(effective_length[gene]) / len(SAMPLE_IDS) for gene in genes
        }
        weights = {
            gene: [
                abundance[gene][sample_index]
                * (average_gene_length[gene] if mode == "lengthScaledTPM" else 1.0)
                for sample_index in range(len(SAMPLE_IDS))
            ]
            for gene in genes
        }
        weight_totals = [
            sum(weights[gene][sample_index] for gene in genes)
            for sample_index in range(len(SAMPLE_IDS))
        ]
        counts = {
            gene: [
                weights[gene][sample_index]
                * library_totals[sample_index]
                / weight_totals[sample_index]
                for sample_index in range(len(SAMPLE_IDS))
            ]
            for gene in genes
        }

    assert abundance == {"geneA": [500000.0, 500000.0], "geneB": [500000.0, 500000.0]}
    assert [sum(abundance[gene][i] for gene in genes) for i in range(2)] == [1e6, 1e6]
    assert effective_length == {"geneA": [600.0, 350.0], "geneB": [1000.0, 950.0]}
    expected_counts = {
        "no": {"geneA": [40.0, 50.0], "geneB": [60.0, 50.0]},
        "scaledTPM": {"geneA": [50.0, 50.0], "geneB": [50.0, 50.0]},
        "lengthScaledTPM": {
            "geneA": [32.75862068965517, 32.75862068965517],
            "geneB": [67.24137931034483, 67.24137931034483],
        },
    }
    for gene in genes:
        assert counts[gene] == pytest.approx(expected_counts[mode][gene], abs=1e-12)
    assert [sum(counts[gene][i] for gene in genes) for i in range(2)] == pytest.approx(
        [100.0, 100.0], abs=1e-12
    )
    return {"counts": counts, "abundance": abundance, "length": effective_length}


def _assert_numeric_matrix(
    actual: dict[str, list[float]], expected: dict[str, list[float]]
) -> None:
    assert actual.keys() == expected.keys()
    for gene in expected:
        # R's text writer retains about 15 significant digits. The fixture arithmetic is
        # exact apart from repeating length-scaled ratios, so 1e-10 is below any
        # biologically meaningful scale here while covering decimal serialization.
        assert actual[gene] == pytest.approx(expected[gene], rel=1e-12, abs=1e-10)


def test_tximport_contract_is_explicit_about_count_semantics(tmp_path: Path) -> None:
    inputs = _inputs()
    outputs = TximportSalmonNode.PLAN_OUTPUTS(inputs, tmp_path)
    TximportSalmonNode.PREPARE_EXECUTION(inputs, outputs)
    command = TximportSalmonNode.render_command(inputs)

    assert TximportSalmonNode.RETURN_TYPES == ("TSV", "TSV", "TSV", "FILE", "JSON")
    assert "COUNTS" not in TximportSalmonNode.RETURN_TYPES
    assert TximportSalmonNode.COUNTS_FROM_ABUNDANCE == ("no", "scaledTPM", "lengthScaledTPM")
    assert command[:3] == ["Rscript", "--vanilla", str(TximportSalmonNode.SCRIPT_PATH)]
    assert [path.name for path in outputs] == [
        "gene_count_scale.tsv",
        "gene_abundance_tpm.tsv",
        "gene_effective_length.tsv",
        "tximport_object.rds",
        "import_metadata.json",
    ]
    assert "dtuScaledTPM is for transcript-level DTU" in str(
        TximportSalmonNode.VALIDATE_INPUTS({**_inputs(), "counts_from_abundance": "dtuScaledTPM"})
    )


def test_tximport_is_lazy_registry_resolvable() -> None:
    node_class = NodeRegistry.create_isolated().get("tximport_salmon")
    assert node_class is TximportSalmonNode
    assert node_class.INPUT_TYPES()["required"]["quant_files"][0] == "COUNTS"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(sample_ids=["one"]), "exactly one identifier"),
        (lambda data: data.update(sample_ids=["same", "same"]), "must be unique"),
        (lambda data: data.update(counts_from_abundance="raw"), "must be one of"),
    ],
)
def test_tximport_rejects_mismatched_parameters(mutation, message: str) -> None:
    inputs = _inputs()
    mutation(inputs)
    assert message in str(TximportSalmonNode.VALIDATE_INPUTS(inputs))


def test_tximport_rejects_malformed_quant_and_mapping(tmp_path: Path) -> None:
    bad_quant = tmp_path / "quant.sf"
    bad_quant.write_text(
        "Name\tLength\tEffectiveLength\tTPM\tNumReads\n"
        "tx1\t100\t80\tNaN\t2\n",
        encoding="utf-8",
    )
    inputs = {**_inputs(), "quant_files": [str(bad_quant)], "sample_ids": ["bad"]}
    assert "non-finite" in str(TximportSalmonNode.VALIDATE_INPUTS(inputs))

    incomplete_map = tmp_path / "tx2gene.tsv"
    incomplete_map.write_text("transcript_id\tgene_id\ntx1\tgeneA\n", encoding="utf-8")
    inputs = {**_inputs(), "tx2gene": str(incomplete_map)}
    assert "missing 2 quantified transcript" in str(TximportSalmonNode.VALIDATE_INPUTS(inputs))

    reordered = tmp_path / "reordered.sf"
    lines = (FIXTURE / "sample2" / "quant.sf").read_text(encoding="utf-8").splitlines()
    reordered.write_text("\n".join([lines[0], lines[2], lines[1], lines[3]]) + "\n", encoding="utf-8")
    inputs = {**_inputs(), "quant_files": [str(FIXTURE / "sample1" / "quant.sf"), str(reordered)]}
    assert "same transcripts in the same order" in str(TximportSalmonNode.VALIDATE_INPUTS(inputs))


def _r_configuration() -> tuple[Path, Path]:
    executable = Path(os.environ.get("TXIMPORT_RSCRIPT", r"C:\Program Files\R\R-4.5.1\bin\Rscript.exe"))
    library = Path(
        os.environ.get(
            "TXIMPORT_R_LIB",
            r"D:\AI\BioNodulo\phd-implementation-2026-09-23\r-library-tximport",
        )
    )
    if not executable.is_file() or not (library / "tximport").is_dir():
        pytest.skip("isolated R 4.5 / tximport integration environment is unavailable")
    return executable, library


def _run_oracle(executable: Path, library: Path, mode: str, output: Path) -> None:
    script = output.with_suffix(".R")
    script.write_text(
        "library(tximport)\n"
        "a <- commandArgs(trailingOnly=TRUE)\n"
        "files <- c(control=a[[1]], treated=a[[2]])\n"
        "map <- read.delim(a[[3]], check.names=FALSE, stringsAsFactors=FALSE)\n"
        "x <- tximport(files, type='salmon', tx2gene=map, countsFromAbundance=a[[4]], "
        "txOut=FALSE, dropInfReps=TRUE)\n"
        "saveRDS(x, a[[5]])\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["R_LIBS_USER"] = str(library)
    subprocess.run(
        [
            str(executable),
            "--vanilla",
            str(script),
            str(FIXTURE / "sample1" / "quant.sf"),
            str(FIXTURE / "sample2" / "quant.sf"),
            str(FIXTURE / "tx2gene.tsv"),
            mode,
            str(output),
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("mode", TximportSalmonNode.COUNTS_FROM_ABUNDANCE)
@pytest.mark.asyncio
async def test_real_executor_matches_python_arithmetic_and_upstream_fidelity_oracles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    executable, library = _r_configuration()
    monkeypatch.setenv("R_LIBS_USER", str(library))
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ.get("PATH", ""))
    node_dir = tmp_path / "app-executor"
    node_dir.mkdir()
    context = ExecutionContext(
        run_id="tximport-fixture",
        node_id="tximport-fixture-node",
        node_type="tximport_salmon",
        node_dir=node_dir,
        workspace_dir=tmp_path,
        params={},
        api_secrets={},
        emit=lambda _event, _payload: None,
        cancel_event=asyncio.Event(),
    )
    inputs = {**_inputs(), "counts_from_abundance": mode}
    result = await TximportSalmonNode().run(**inputs, context=context)
    outputs = [Path(path) for path in result]
    oracle_rds = tmp_path / f"oracle-{mode}.rds"
    _run_oracle(executable, library, mode, oracle_rds)

    comparison = tmp_path / f"compare-{mode}.R"
    comparison.write_text(
        "a <- commandArgs(trailingOnly=TRUE)\n"
        "expected <- readRDS(a[[1]])\n"
        "actual <- readRDS(a[[2]])\n"
        "stopifnot(isTRUE(all.equal(expected$counts, actual$counts, tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(expected$abundance, actual$abundance, tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(expected$length, actual$length, tolerance=1e-12)))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["R_LIBS_USER"] = str(library)
    subprocess.run(
        [str(executable), "--vanilla", str(comparison), str(oracle_rds), str(outputs[3])],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    for matrix_path in outputs[:3]:
        header, rows = _matrix(matrix_path)
        assert header == ["gene_id", "control", "treated"]
        assert set(rows) == {"geneA", "geneB"}
    hand_oracle = _hand_computed_gene_oracle(mode)
    for output_index, kind in enumerate(("counts", "abundance", "length")):
        _header, published = _matrix(outputs[output_index])
        _assert_numeric_matrix(published, hand_oracle[kind])

    rds_export = tmp_path / f"rds-export-{mode}"
    rds_export.mkdir()
    rds_reader = tmp_path / f"read-rds-{mode}.R"
    rds_reader.write_text(
        "a <- commandArgs(trailingOnly=TRUE)\n"
        "x <- readRDS(a[[1]])\n"
        "for (i in seq_along(c('counts','abundance','length'))) {\n"
        "  kind <- c('counts','abundance','length')[[i]]\n"
        "  value <- x[[kind]]\n"
        "  d <- data.frame(gene_id=rownames(value), value, check.names=FALSE)\n"
        "  write.table(d, a[[i + 1]], sep='\\t', quote=FALSE, row.names=FALSE)\n"
        "}\n"
        "writeLines(x$countsFromAbundance, a[[5]])\n",
        encoding="utf-8",
    )
    rds_matrices = [rds_export / f"{kind}.tsv" for kind in ("counts", "abundance", "length")]
    rds_mode = rds_export / "mode.txt"
    subprocess.run(
        [
            str(executable),
            "--vanilla",
            str(rds_reader),
            str(outputs[3]),
            *(str(path) for path in rds_matrices),
            str(rds_mode),
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    for matrix_path, kind in zip(rds_matrices, ("counts", "abundance", "length"), strict=True):
        header, from_rds = _matrix(matrix_path)
        assert header == ["gene_id", "control", "treated"]
        _assert_numeric_matrix(from_rds, hand_oracle[kind])
    assert rds_mode.read_text(encoding="utf-8").strip() == mode
    metadata = json.loads(outputs[4].read_text(encoding="utf-8"))
    assert metadata["tximport_version"] == "1.38.2"
    assert metadata["counts_from_abundance"] == mode
    assert metadata["raw_counts"] is False
    assert metadata["aggregation_level"] == "gene"
    assert metadata["sample_manifest_md5"]
    assert len(metadata["quant_md5"]) == 2
    assert metadata["tx2gene_md5"]
    assert "not raw counts" in metadata["counts_semantics"]
    if mode == "no":
        assert metadata["downstream_offset"] == "required_by_tximport_aware_DGE"
    else:
        assert metadata["downstream_offset"] == "must_not_be_used"


@pytest.mark.asyncio
async def test_single_sample_single_gene_metadata_preserves_array_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable, library = _r_configuration()
    monkeypatch.setenv("R_LIBS_USER", str(library))
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ.get("PATH", ""))
    quant = tmp_path / "quant.sf"
    quant.write_text(
        "Name\tLength\tEffectiveLength\tTPM\tNumReads\n"
        "tx1\t800\t650\t1000000\t12.5\n",
        encoding="utf-8",
    )
    mapping = tmp_path / "tx2gene.tsv"
    mapping.write_text("transcript_id\tgene_id\ntx1\tgeneA\n", encoding="utf-8")
    context = ExecutionContext(
        run_id="single-sample",
        node_id="single-sample-node",
        node_type="tximport_salmon",
        node_dir=tmp_path / "executor",
        workspace_dir=tmp_path,
        params={},
        api_secrets={},
        emit=lambda _event, _payload: None,
        cancel_event=asyncio.Event(),
    )
    outputs = await TximportSalmonNode().run(
        quant_files=[str(quant)],
        sample_ids=["only_sample"],
        tx2gene=str(mapping),
        counts_from_abundance="no",
        context=context,
    )
    metadata = json.loads(Path(outputs[4]).read_text(encoding="utf-8"))
    assert metadata["sample_ids"] == ["only_sample"]
    assert metadata["quant_files"] == [quant.resolve().as_posix()]
    assert isinstance(metadata["quant_md5"], list) and len(metadata["quant_md5"]) == 1
    header, rows = _matrix(Path(outputs[0]))
    assert header == ["gene_id", "only_sample"]
    assert rows == {"geneA": [12.5]}
