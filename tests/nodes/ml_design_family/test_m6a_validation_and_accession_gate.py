"""Focused contracts for m6a_validation_metrics and accession_gate."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import (
    AccessionGateNode,
    M6AValidationMetricsNode,
)
from bionodulo.nodes.builtin.ml_design_family.m6a_validation_metrics import (
    mann_whitney_auroc,
    normalise_chrom,
    parse_gtf,
    precision_at_recall,
    spearman,
)

GLORI_HEADER = (
    "Chr,Sites,Strand,Gene,Transcript,NonCR,AGcov,Acov,Genecov,Ratio,NormeRatio,Pvalue,P_adjust,Sample"
)


def _context(tmp_path: Path) -> SimpleNamespace:
    node_dir = tmp_path / "run"
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def _summary(result: tuple[str, str, str, str]) -> dict:
    return json.loads(Path(result[3]).read_text(encoding="utf-8"))


def _rows(path: str) -> list[dict[str, str]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]


def test_chromosome_name_normalisation_reconciles_ucsc_and_ensembl() -> None:
    assert normalise_chrom("chr1") == "1"
    assert normalise_chrom("1") == "1"
    assert normalise_chrom("chrX") == "X"
    assert normalise_chrom("X") == "X"
    assert normalise_chrom("chrY") == "Y"
    assert normalise_chrom("chrM") == "MT"
    assert normalise_chrom("MT") == "MT"
    assert normalise_chrom("chrMT") == "MT"
    assert normalise_chrom("CHR1") == "CHR1"


def test_auroc_and_spearman_match_hand_computed_values() -> None:
    import numpy as np

    labels = np.array([True, True, True, False, False, False])
    assert mann_whitney_auroc(labels, np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])) == 1.0
    tied = mann_whitney_auroc(labels, np.array([0.9, 0.5, 0.7, 0.5, 0.2, 0.1]))
    assert tied == pytest.approx(8.5 / 9.0)
    assert mann_whitney_auroc(labels, np.ones(6)) == 0.5
    assert mann_whitney_auroc(np.array([True, True, True]), np.array([0.5, 0.6, 0.7])) is None

    assert spearman(np.array([1.0, 2, 3, 4, 5, 6]), np.array([3.0, 1, 2, 5, 4, 6])) == pytest.approx(13.5 / 17.5)
    assert spearman(np.array([0.9, 0.5, 0.7]), np.array([0.8, 0.4, 0.6])) == pytest.approx(1.0)
    assert spearman(np.array([0.9, 0.5, 0.7]), np.array([0.4, 0.8, 0.6])) == pytest.approx(-1.0)
    tied_spearman = spearman(np.array([1.0, 1.0, 2.0]), np.array([1.0, 2.0, 2.0]))
    assert tied_spearman == pytest.approx(0.5)
    assert spearman(np.array([1.0]), np.array([1.0])) is None


def test_precision_at_recall_reports_first_threshold_reaching_target() -> None:
    import numpy as np

    labels = np.array([True, True, False, False])
    result = precision_at_recall(labels, np.array([0.9, 0.4, 0.8, 0.1]), 0.5)
    assert result == {"precision": 1.0, "threshold": 0.9, "recall": 0.5}
    assert precision_at_recall(np.array([False, False]), np.array([0.5, 0.6]), 0.5) is None


@pytest.mark.asyncio
async def test_m6a_metrics_match_six_site_hand_computation(tmp_path: Path) -> None:
    sites = _write(
        tmp_path / "sites.tsv",
        "\n".join(
            [
                "chrom\tpos\tstrand\tvalid_coverage\tpercent_modified\tcanonical_base",
                "chr1\t100\t+\t50\t90\tA",
                "chr1\t200\t+\t50\t50\tA",
                "chr1\t300\t+\t50\t70\tA",
                "chr1\t400\t+\t50\t50\tA",
                "chr1\t500\t+\t50\t20\tA",
                "chr1\t700\t+\t50\t10\tA",
            ]
        )
        + "\n",
    )
    glori = _write(
        tmp_path / "glori.csv",
        "\n".join(
            [
                GLORI_HEADER,
                "1,100,+,G,T,0,50,50,1.0,0.8,0.8,0.01,0.01,S",
                "1,200,+,G,T,0,50,50,1.0,0.4,0.4,0.01,0.01,S",
                "1,300,+,G,T,0,50,50,1.0,0.6,0.6,0.01,0.01,S",
                "1,400,+,G,T,0,50,50,1.0,0.05,0.05,0.5,0.5,S",
                "1,500,+,G,T,0,50,50,1.0,0.0,0.0,0.9,0.9,S",
                "1,600,+,G,T,0,50,50,1.0,0.5,0.5,0.01,0.01,S",
            ]
        )
        + "\n",
    )
    node = M6AValidationMetricsNode()
    result = await node.run(
        sites_tsv=sites, glori_csv=glori, ratio_threshold=0.3, context=_context(tmp_path)
    )
    summary = _summary(result)
    assert summary["n_ours_input_rows"] == 6
    assert summary["n_glori_sites"] == 6
    assert summary["n_glori_positive"] == 4
    assert summary["n_joined"] == 5
    assert summary["confusion_joined"] == {"TP": 3, "FP": 1, "FN": 0, "TN": 1}
    assert summary["metrics"]["auroc"] == pytest.approx(5.5 / 6.0)
    precision = summary["metrics"]["precision_at_recall_0_5"]
    assert precision["precision"] == 1.0
    assert precision["threshold"] == pytest.approx(0.7)
    assert precision["recall"] == pytest.approx(2.0 / 3.0)
    assert summary["metrics"]["recall_at_ratio_threshold"] == pytest.approx(3.0 / 4.0)
    assert summary["metrics"]["stoichiometry_spearman"] == pytest.approx(1.0)
    assert summary["params"]["drach_filter_applied"] is True

    rows = _rows(result[0])
    by_pos = {int(row["pos"]): row for row in rows}
    assert by_pos[100]["classification"] == "TP"
    assert by_pos[400]["classification"] == "FP"
    assert by_pos[500]["classification"] == "TN"


@pytest.mark.asyncio
async def test_m6a_metrics_separate_strong_signal_on_two_hundred_sites(tmp_path: Path) -> None:
    rng = random.Random(11)
    ours: list[str] = ["chrom\tpos\tstrand\tvalid_coverage\tpercent_modified\tcanonical_base"]
    glori: list[str] = [GLORI_HEADER]
    for index in range(100):
        ratio = rng.uniform(0.15, 0.9)
        fdr = rng.uniform(0.001, 0.01)
        glori.append(f"1,{1000 + index},+,G,T,0,50,50,1.0,{ratio:.4f},{ratio:.4f},0.01,{fdr:.4f},S")
        ours.append(
            f"chr1\t{1000 + index}\t+\t{rng.randint(30, 100)}\t"
            f"{min(max(ratio + rng.gauss(0.2, 0.06), 0.0), 1.0) * 100:.4f}\tA"
        )
    for index in range(100):
        ratio = rng.uniform(0.0, 0.05)
        fdr = rng.uniform(0.2, 0.9)
        glori.append(f"1,{5000 + index},+,G,T,0,50,50,1.0,{ratio:.4f},{ratio:.4f},0.01,{fdr:.4f},S")
        ours.append(
            f"chr1\t{5000 + index}\t+\t{rng.randint(30, 100)}\t"
            f"{min(max(ratio * 0.4 + rng.gauss(0.02, 0.02), 0.0), 1.0) * 100:.4f}\tA"
        )
    for index in range(10):
        ours.append(f"chr2\t{9000 + index}\t+\t5\t90.0000\tA")
    sites = _write(tmp_path / "sites.tsv", "\n".join(ours) + "\n")
    glori = _write(tmp_path / "glori.csv", "\n".join(glori) + "\n")

    node = M6AValidationMetricsNode()
    result = await node.run(sites_tsv=sites, glori_csv=glori, context=_context(tmp_path))
    summary = _summary(result)
    assert summary["n_ours_input_rows"] == 210
    assert summary["n_ours_sites"] == 200
    assert summary["n_joined"] == 200
    assert summary["n_glori_positive"] == 100
    assert summary["metrics"]["auroc"] > 0.9
    assert summary["metrics"]["recall_at_ratio_threshold"] >= 0.95
    assert summary["metrics"]["stoichiometry_spearman"] > 0.8
    assert summary["confusion_joined"]["TP"] >= 95
    assert summary["confusion_joined"]["FP"] <= 10


@pytest.mark.asyncio
async def test_m6a_metrics_accept_pileup_shape_and_scale_1000(tmp_path: Path) -> None:
    sites = _write(
        tmp_path / "bedmethyl.tsv",
        "\n".join(
            [
                "chrom\tstart\tstrand\tNvalid_cov\tscore",
                "chr1\t100\t+\t50\t500",
                "chr1\t200\t+\t50\t900",
            ]
        )
        + "\n",
    )
    glori = _write(
        tmp_path / "glori.csv",
        "\n".join(
            [
                GLORI_HEADER,
                "chr1,101,+,G,T,0,50,50,1.0,0.5,0.5,0.01,0.01,S",
                "chr1,201,+,G,T,0,50,50,1.0,0.9,0.9,0.01,0.01,S",
            ]
        )
        + "\n",
    )
    node = M6AValidationMetricsNode()
    result = await node.run(
        sites_tsv=sites, glori_csv=glori, percent_scale="1000", context=_context(tmp_path)
    )
    summary = _summary(result)
    assert summary["n_joined"] == 2
    assert summary["columns_used"]["coverage"] == "Nvalid_cov"
    assert summary["columns_used"]["value"] == "score"
    assert summary["params"]["drach_filter_applied"] is False
    rows = _rows(result[0])
    assert float(rows[0]["our_ratio"]) == pytest.approx(0.5)
    assert float(rows[1]["our_ratio"]) == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_m6a_metrics_drach_filter_drops_non_a_canonical_sites(tmp_path: Path) -> None:
    sites = _write(
        tmp_path / "sites.tsv",
        "\n".join(
            [
                "chrom\tpos\tstrand\tvalid_coverage\tmod_ratio\tcanonical_base",
                "chr1\t100\t+\t50\t0.9\tA",
                "chr1\t200\t+\t50\t0.9\tC",
            ]
        )
        + "\n",
    )
    glori = _write(
        tmp_path / "glori.csv",
        "\n".join(
            [
                GLORI_HEADER,
                "1,100,+,G,T,0,50,50,1.0,0.8,0.8,0.01,0.01,S",
                "1,200,+,G,T,0,50,50,1.0,0.8,0.8,0.01,0.01,S",
            ]
        )
        + "\n",
    )
    node = M6AValidationMetricsNode()
    context = _context(tmp_path)
    filtered = _summary(
        await node.run(
            sites_tsv=sites, glori_csv=glori, percent_scale="fraction", context=context
        )
    )
    assert filtered["n_ours_sites"] == 1
    unfiltered = _summary(
        await node.run(
            sites_tsv=sites, glori_csv=glori, percent_scale="fraction", drach_filter=False, context=context
        )
    )
    assert unfiltered["n_ours_sites"] == 2


def _gtf_text() -> str:
    return "\n".join(
        [
            '1\tannotation\ttranscript\t100\t999\t.\t+\t.\tgene_id "G1"; transcript_id "ENST1";',
            '1\tannotation\texon\t100\t999\t.\t+\t.\ttranscript_id "ENST1";',
            '1\tannotation\tfive_prime_utr\t100\t299\t.\t+\t.\ttranscript_id "ENST1";',
            '1\tannotation\tCDS\t300\t699\t.\t+\t.\ttranscript_id "ENST1";',
            '1\tannotation\tthree_prime_utr\t700\t999\t.\t+\t.\ttranscript_id "ENST1";',
            '2\tannotation\ttranscript\t1000\t1899\t.\t-\t.\ttranscript_id "ENST2";',
            '2\tannotation\tCDS\t1300\t1699\t.\t-\t.\ttranscript_id "ENST2";',
        ]
    ) + "\n"


def test_parse_gtf_builds_regions_from_feature_ranges(tmp_path: Path) -> None:
    gtf_path = tmp_path / "anno.gtf"
    gtf_path.write_text(_gtf_text(), encoding="utf-8")
    transcripts = {record.transcript_id: record for record in parse_gtf(gtf_path)}
    plus = transcripts["ENST1"]
    assert plus.chrom == "1"
    assert plus.region_of(150) == "5UTR"
    assert plus.region_of(500) == "CDS"
    assert plus.region_of(800) == "3UTR"
    assert plus.fractional_position(150) == pytest.approx(50.0 / 900.0)
    minus = transcripts["ENST2"]
    assert minus.region_of(1100) == "3UTR"
    assert minus.region_of(1800) == "5UTR"
    assert minus.fractional_position(1899) == pytest.approx(0.0)
    assert minus.fractional_position(1000) == pytest.approx(899.0 / 900.0)


@pytest.mark.asyncio
async def test_m6a_metrics_metagene_classifies_regions_and_bins(tmp_path: Path) -> None:
    sites = _write(
        tmp_path / "sites.tsv",
        "\n".join(
            [
                "chrom\tpos\tstrand\tvalid_coverage\tpercent_modified\tcanonical_base",
                "chr1\t150\t+\t50\t50\tA",
                "chr1\t500\t+\t50\t50\tA",
                "chr1\t800\t+\t50\t50\tA",
                "chr2\t1100\t+\t50\t50\tA",
                "chr2\t1800\t+\t50\t50\tA",
            ]
        )
        + "\n",
    )
    glori = _write(
        tmp_path / "glori.csv",
        GLORI_HEADER + "\n1,500,+,G,T,0,50,50,1.0,0.8,0.8,0.01,0.01,S\n",
    )
    gtf = _write(tmp_path / "anno.gtf", _gtf_text())
    node = M6AValidationMetricsNode()
    result = await node.run(sites_tsv=sites, glori_csv=glori, gtf=gtf, context=_context(tmp_path))
    summary = _summary(result)
    assert summary["metagene"]["enabled"] is True
    assert summary["metagene"]["n_annotated"] == 5
    assert summary["metagene"]["n_unassigned"] == 0

    rows = _rows(result[1])
    regions = {(row["chrom"], row["pos"]): row["region"] for row in rows}
    assert regions[("chr1", "150")] == "5UTR"
    assert regions[("chr1", "500")] == "CDS"
    assert regions[("chr1", "800")] == "3UTR"
    assert regions[("chr2", "1100")] == "3UTR"
    assert regions[("chr2", "1800")] == "5UTR"
    by_site = {(row["chrom"], row["pos"]): row for row in rows}
    assert float(by_site[("chr1", "150")]["fractional_position"]) == pytest.approx(50.0 / 900.0, abs=1e-6)
    assert float(by_site[("chr2", "1800")]["fractional_position"]) == pytest.approx(99.0 / 900.0, abs=1e-6)

    bins = _rows(result[2])
    assert len(bins) == 50
    assert sum(int(row["n_sites"]) for row in bins) == 5
    assert int(bins[2]["n_sites"]) == 1
    assert int(bins[0]["n_sites"]) == 0


@pytest.mark.asyncio
async def test_m6a_metrics_rejects_missing_columns_and_bad_rows(tmp_path: Path) -> None:
    glori = _write(tmp_path / "glori.csv", GLORI_HEADER + "\n1,100,+,G,T,0,50,50,1.0,0.8,0.8,0.01,0.01,S\n")
    node = M6AValidationMetricsNode()
    context = _context(tmp_path)
    incomplete = _write(tmp_path / "bad.tsv", "chrom\tpos\tstrand\nchr1\t100\t+\n")
    with pytest.raises(ValueError, match="missing required column"):
        await node.run(sites_tsv=incomplete, glori_csv=glori, context=context)
    malformed = _write(
        tmp_path / "malformed.tsv",
        "chrom\tpos\tstrand\tvalid_coverage\tpercent_modified\nchr1\tX\t+\t50\t10\n",
    )
    with pytest.raises(ValueError, match="non-numeric"):
        await node.run(sites_tsv=malformed, glori_csv=glori, context=context)
    valid_sites = _write(
        tmp_path / "valid.tsv",
        "chrom\tpos\tstrand\tvalid_coverage\tpercent_modified\nchr1\t100\t+\t50\t10\n",
    )
    bad_glori = _write(tmp_path / "bad_glori.csv", "Chr,Sites\n1,100\n")
    with pytest.raises(ValueError, match="glori_csv' header is missing"):
        await node.run(sites_tsv=valid_sites, glori_csv=bad_glori, context=context)
    assert M6AValidationMetricsNode.VALIDATE_INPUTS(
        {"sites_tsv": "s", "glori_csv": "g", "percent_scale": "5000"}
    ) == "Input 'percent_scale' must be one of: 100, 1000, fraction"


EXTRACT_HEADER = (
    "read_id\tforward_read_position\tref_position\tchrom\tmod_strand\tref_strand\tref_mod_strand\t"
    "fw_soft_clipped_start\tfw_soft_clipped_end\talignment_start\talignment_end\tread_length\t"
    "mod_qual\tmod_code\tbase_qual\tref_kmer\tquery_kmer\tcanonical_base\tmodified_primary_base\t"
    "inferred\tflag"
)


def _extract_row(read_id: str, chrom: str, pos: int, strand: str, mod_qual: int, canonical: str = "A") -> str:
    return (
        f"{read_id}\t0\t{pos}\t{chrom}\tf\t{strand}\t{strand}\t0\t0\t{max(pos - 10, 0)}\t{pos + 10}\t"
        f"100\t{mod_qual}\tm\t20\tACGTA\tACGTA\t{canonical}\tA\tfalse\t0"
    )


@pytest.mark.asyncio
async def test_m6a_metrics_aggregates_raw_modkit_extract_table(tmp_path: Path) -> None:
    extract = _write(
        tmp_path / "extract.tsv",
        "\n".join(
            [
                EXTRACT_HEADER,
                _extract_row("r1", "chr1", 999, "+", 255),
                _extract_row("r2", "chr1", 999, "+", 255),
                _extract_row("r3", "chr1", 999, "+", 0),
                _extract_row("r4", "chr1", 999, "+", 127),
                _extract_row("r5", "chr1", 1999, "+", 0),
                _extract_row("r6", "chr1", 1999, "+", 0),
                _extract_row("r7", "chr1", 1999, "+", 0),
                _extract_row("r8", "chr2", 4999, "-", 255),
                _extract_row("r9", "chr2", 4999, "-", 255),
                _extract_row("r10", "chr2", 4999, "-", 255),
                _extract_row("r11", ".", -1, ".", 200),
            ]
        )
        + "\n",
    )
    glori = _write(
        tmp_path / "glori.csv",
        "\n".join(
            [
                GLORI_HEADER,
                "1,1000,+,G,T,0,50,50,1.0,0.62,0.62,0.01,0.01,S",
                "1,2000,+,G,T,0,50,50,1.0,0.0,0.0,0.9,0.9,S",
                "2,5000,-,G,T,0,50,50,1.0,0.9,0.9,0.01,0.01,S",
            ]
        )
        + "\n",
    )
    node = M6AValidationMetricsNode()
    result = await node.run(
        sites_tsv=extract, glori_csv=glori, min_coverage=1, ratio_threshold=0.3, context=_context(tmp_path)
    )
    summary = _summary(result)
    assert summary["input_mode_used"] == "extract_raw"
    assert summary["params"]["input_mode"] == "auto"
    assert summary["n_ours_input_rows"] == 11
    assert summary["n_ours_sites"] == 3
    assert summary["n_joined"] == 3
    rows = _rows(result[0])
    by_site = {(row["chrom"], row["pos"], row["strand"]): row for row in rows}
    hot = by_site[("chr1", "1000", "+")]
    assert int(hot["coverage"]) == 4
    assert float(hot["our_ratio"]) == pytest.approx((255 + 255 + 0 + 127) / 4 / 255)
    assert hot["classification"] == "TP"
    cold = by_site[("chr1", "2000", "+")]
    assert int(cold["coverage"]) == 3
    assert float(cold["our_ratio"]) == pytest.approx(0.0)
    assert cold["classification"] == "TN"
    minus = by_site[("chr2", "5000", "-")]
    assert float(minus["our_ratio"]) == pytest.approx(1.0)
    assert minus["classification"] == "TP"


@pytest.mark.asyncio
async def test_m6a_metrics_reads_gz_inputs_and_forced_modes(tmp_path: Path) -> None:
    import gzip

    extract_text = "\n".join(
        [
            EXTRACT_HEADER,
            _extract_row("r1", "chr1", 999, "+", 255),
            _extract_row("r2", "chr1", 999, "+", 0),
        ]
    ) + "\n"
    sites_gz = tmp_path / "extract.tsv.gz"
    sites_gz.write_bytes(gzip.compress(extract_text.encode("utf-8")))
    glori_text = (
        GLORI_HEADER + "\n1,1000,+,G,T,0,50,50,1.0,0.5,0.5,0.01,0.01,S\n"
    )
    glori_gz = tmp_path / "glori.csv.gz"
    glori_gz.write_bytes(gzip.compress(glori_text.encode("utf-8")))

    node = M6AValidationMetricsNode()
    result = await node.run(
        sites_tsv=str(sites_gz), glori_csv=str(glori_gz), min_coverage=1, context=_context(tmp_path)
    )
    summary = _summary(result)
    assert summary["input_mode_used"] == "extract_raw"
    assert summary["n_joined"] == 1
    rows = _rows(result[0])
    assert float(rows[0]["our_ratio"]) == pytest.approx(0.5)

    forced = await node.run(
        sites_tsv=str(sites_gz),
        glori_csv=str(glori_gz),
        input_mode="extract_raw",
        min_coverage=1,
        context=_context(tmp_path),
    )
    assert _summary(forced)["input_mode_used"] == "extract_raw"

    with pytest.raises(ValueError, match="missing required column"):
        await node.run(
            sites_tsv=str(sites_gz),
            glori_csv=str(glori_gz),
            input_mode="per_site",
            context=_context(tmp_path),
        )
    assert M6AValidationMetricsNode.VALIDATE_INPUTS(
        {"sites_tsv": "s", "glori_csv": "g", "input_mode": "sniff"}
    ) == "Input 'input_mode' must be one of: auto, per_site, extract_raw"


MANIFEST_HEADER = "accession\tresolved_version\tfeature_used\tfetch_date\tsha256\tfile\tnotes"


def _manifest(rows: list[str]) -> str:
    return "\n".join([MANIFEST_HEADER, *rows]) + "\n"


@pytest.mark.asyncio
async def test_accession_gate_passes_verified_manifest(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    payload_file = data / "record1.fa"
    payload_file.write_text(">x\nACGT\n", encoding="utf-8")
    digest = hashlib.sha256(payload_file.read_bytes()).hexdigest()
    manifest = _write(
        tmp_path / "manifest.tsv",
        _manifest([f"SRR000001\t1\tfeature\t2026-01-15\t{digest}\tdata/record1.fa\tok"]),
    )
    node = AccessionGateNode()
    status_path, all_pass = await node.run(manifest=manifest, context=_context(tmp_path))
    assert all_pass is True
    payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["n_rows"] == 1
    assert payload["rows"][0]["file_status"] == "verified"
    assert payload["rows"][0]["observed_sha256"].lower() == digest


@pytest.mark.asyncio
async def test_accession_gate_fails_closed_on_missing_sha256(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "record1.fa").write_text(">x\nACGT\n", encoding="utf-8")
    manifest = _write(
        tmp_path / "manifest.tsv",
        _manifest(
            [
                "SRR000001\t1\tfeature\t2026-01-15\t\tdata/record1.fa\tmissing hash",
                "SRR000002\t1\tfeature\t2026-01-15\tdeadbeef\tdata/record1.fa\tok",
            ]
        ),
    )
    node = AccessionGateNode()
    with pytest.raises(RuntimeError, match="row\\(s\\): 2"):
        await node.run(manifest=manifest, context=_context(tmp_path))
    payload = json.loads(
        (tmp_path / "run" / "accession_gate" / "manifest_status.json").read_text(encoding="utf-8")
    )
    assert payload["passed"] is False
    assert payload["rows"][0]["errors"] == ["empty sha256"]
    assert payload["rows"][1]["file_status"] == "hash_mismatch"


@pytest.mark.asyncio
async def test_accession_gate_wrong_sha256_and_bad_date_report_errors(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    payload_file = data / "record2.fa"
    payload_file.write_text(">y\nACGT\n", encoding="utf-8")
    digest = hashlib.sha256(payload_file.read_bytes()).hexdigest()
    manifest = _write(
        tmp_path / "manifest.tsv",
        _manifest(
            [
                f"SRR000003\t1\tfeature\t2026-13-99\t{digest}\tdata/record2.fa\tbad date",
            ]
        ),
    )
    node = AccessionGateNode()
    status_path, all_pass = await node.run(
        manifest=manifest, fail_closed=False, context=_context(tmp_path)
    )
    assert all_pass is False
    payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    assert payload["rows"][0]["errors"] == ["fetch_date is not a valid YYYY-MM-DD date"]


@pytest.mark.asyncio
async def test_accession_gate_files_optional_mode_skips_existence_checks(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.tsv",
        _manifest(["SRR000004\t1\tfeature\t2026-02-02\t0123\tdata/absent.fa\tnot fetched"]),
    )
    node = AccessionGateNode()
    status_path, all_pass = await node.run(
        manifest=manifest, require_files_exist=False, context=_context(tmp_path)
    )
    assert all_pass is True
    payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    assert payload["rows"][0]["file_status"] == "skipped"


@pytest.mark.asyncio
async def test_accession_gate_rejects_structurally_invalid_manifests(tmp_path: Path) -> None:
    node = AccessionGateNode()
    context = _context(tmp_path)
    header_only = _write(tmp_path / "header_only.tsv", MANIFEST_HEADER + "\n")
    with pytest.raises(ValueError, match="no data rows"):
        await node.run(manifest=header_only, context=context)
    wrong_header = _write(tmp_path / "wrong_header.tsv", "accession\tsha256\nSRR1\tab\n")
    with pytest.raises(ValueError, match="missing required column"):
        await node.run(manifest=wrong_header, context=context)
    ragged = _write(tmp_path / "ragged.tsv", _manifest(["SRR1\t1\tf\t2026-01-01\tab\tdata/x.fa"]))
    with pytest.raises(ValueError, match="expected 7"):
        await node.run(manifest=ragged, context=context)


@pytest.mark.asyncio
async def test_accession_gate_base_dir_pins_workspace_root(tmp_path: Path, monkeypatch) -> None:
    """Relative 'file' entries resolve against base_dir first, then manifest dir, then cwd."""
    workspace = tmp_path / "workspace"
    staged = workspace / "data"
    staged.mkdir(parents=True)
    payload = staged / "record1.fa"
    payload.write_text(">x\nACGT\n", encoding="utf-8")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    manifest_dir = workspace / "templates" / "data"
    manifest_dir.mkdir(parents=True)
    manifest = _write(
        manifest_dir / "verified_inputs.tsv",
        _manifest([f"SRR000001\t1\tfeature\t2026-01-15\t{digest}\tdata/record1.fa\tok"]),
    )
    monkeypatch.chdir(tmp_path)

    node = AccessionGateNode()
    _, all_pass = await node.run(
        manifest=manifest,
        base_dir=str(workspace),
        context=_context(tmp_path),
    )
    assert all_pass is True

    status_path, all_pass = await node.run(
        manifest=manifest, fail_closed=False, context=_context(tmp_path / "no-basedir")
    )
    assert all_pass is False
    payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    assert payload["base_dir"] == ""
    assert payload["rows"][0]["file_status"] == "missing"
