"""Executed-run coverage for the deterministic codon-design family."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.codon_design_family import (
    CodonMetricsNode,
    CodonOptimizerNode,
    ImmuneMotifScannerNode,
    MiRNASeedScannerNode,
    UTRFeatureBuilderNode,
)
from bionodulo.nodes.builtin.codon_design_family.adapter import CodonDesignNode, translate_cds
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


FAMILY_IDS = ("codon_optimizer", "codon_metrics", "immune_motif_scanner", "mirna_seed_scanner", "utr_feature_builder")

GFP_PROTEIN = (
    "MASKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTLTYGWQCFSRYPDHMK"
    "RHDFFKSAMPEGYVQERTISFKDDGTYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQK"
    "NGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK"
)


def synthesize_gfp_cds() -> str:
    from bionodulo.nodes.builtin.codon_design_family.adapter import AMINO_ACID_SYNONYMS

    codons: list[str] = []
    for index, amino in enumerate(GFP_PROTEIN):
        family = AMINO_ACID_SYNONYMS[amino]
        codons.append(family[index % len(family)])
    return "".join(codons) + "TAA"


GFP_CDS = synthesize_gfp_cds()


def context_at(base: Path) -> SimpleNamespace:
    return SimpleNamespace(node_dir=base)


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.mark.parametrize("node_id", FAMILY_IDS)
def test_family_contract_metadata(registry: NodeRegistry, node_id: str) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    assert issubclass(node_class, CodonDesignNode)
    assert node_class.CATEGORY == "codon_design"
    assert node_class.REQUIRES_EXTERNAL_TOOLS is False
    assert node_class.REQUIRED_EXECUTABLES == []
    assert node_class.REQUIRED_CONDA_PACKAGES == []
    assert node_class.EXPERIMENTAL is False
    assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES)


@pytest.mark.parametrize(
    ("node_id", "inputs", "expected"),
    [
        ("codon_optimizer", {"cds": ""}, "Input 'cds' must be a non-empty sequence or file path"),
        ("codon_optimizer", {"cds": "ATGGGCCXATAA"}, "invalid characters"),
        ("codon_optimizer", {"cds": "ATGGGCA"}, "divisible by 3"),
        ("codon_optimizer", {"cds": "ATGGGCTAA", "strategy": "greedy"}, "must be one of"),
        ("codon_optimizer", {"cds": "ATGGGCTAA", "gc_target": 1.5}, "Input 'gc_target' must be at most 1"),
        ("codon_optimizer", {"cds": "ATGGGCTAA", "forbidden_motifs": "GGXG"}, "forbidden_motifs' entries must be"),
        ("codon_metrics", {"cds": "ATGGGCTAA", "window": 1}, "Input 'window' must be at least 3"),
        ("immune_motif_scanner", {"sequence": ""}, "Input 'sequence' must be a non-empty sequence or file path"),
        ("immune_motif_scanner", {"sequence": "AUGCGU", "u_run_threshold": 0}, "must be at least 1"),
        ("immune_motif_scanner", {"sequence": "AUGCGU", "tlr9_cpg_motifs": "GTXXT"}, "must use ACGT characters"),
        ("mirna_seed_scanner", {"target": "AUGCGU", "seed_file": ""}, "Input 'seed_file' must be a non-empty path"),
        ("mirna_seed_scanner", {"target": "", "seed_file": "s.tsv"}, "Input 'target' must be a non-empty sequence or file path"),
        ("utr_feature_builder", {}, "Provide at least one of 'five_utr' or 'three_utr'"),
        ("utr_feature_builder", {"five_utr": "AUGCUA", "poly_u_min": 0}, "Input 'poly_u_min' must be at least 1"),
    ],
)
def test_family_validation_rejects_bad_inputs(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    expected: str,
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    validation = node_class.VALIDATE_INPUTS(dict(inputs))
    assert validation is not True
    assert expected in str(validation)


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["uniform", "cai_max", "gc_target", "balanced"])
async def test_codon_optimizer_strategies_preserve_protein(tmp_path: Path, strategy: str) -> None:
    result = await CodonOptimizerNode().run(context=context_at(tmp_path), cds=GFP_CDS, strategy=strategy)
    assert len(result) == 2
    optimized = "".join(
        line for line in Path(result[0]).read_text(encoding="utf-8").splitlines() if not line.startswith(">")
    )
    assert len(optimized) == len(GFP_CDS)
    assert set(optimized) <= set("ACGT")
    assert translate_cds(optimized) == translate_cds(GFP_CDS)
    metrics = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert metrics["strategy"] == strategy
    assert metrics["cai_before"] is not None
    assert metrics["cai_after"] is not None
    assert metrics["protein_length"] == len(GFP_PROTEIN)


@pytest.mark.asyncio
async def test_codon_optimizer_is_deterministic(tmp_path: Path) -> None:
    first = await CodonOptimizerNode().run(context=context_at(tmp_path / "a"), cds=GFP_CDS, strategy="balanced")
    second = await CodonOptimizerNode().run(context=context_at(tmp_path / "b"), cds=GFP_CDS, strategy="balanced")
    assert Path(first[0]).read_text(encoding="utf-8") == Path(second[0]).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_codon_optimizer_cai_max_raises_cai_and_avoids_forbidden_motifs(tmp_path: Path) -> None:
    result = await CodonOptimizerNode().run(
        context=context_at(tmp_path),
        cds=GFP_CDS,
        strategy="cai_max",
        forbidden_motifs="GGGGG,CCCCC",
        avoid_repeats=8,
    )
    metrics = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert metrics["cai_after"] > metrics["cai_before"]
    assert all(count == 0 for count in metrics["motif_counts_after"].values())
    optimized = "".join(
        line for line in Path(result[0]).read_text(encoding="utf-8").splitlines() if not line.startswith(">")
    )
    assert "GGGGG" not in optimized and "CCCCC" not in optimized


@pytest.mark.asyncio
async def test_codon_optimizer_gc_target_pulls_gc_toward_target(tmp_path: Path) -> None:
    low = await CodonOptimizerNode().run(
        context=context_at(tmp_path / "low"), cds=GFP_CDS, strategy="gc_target", gc_target=0.30
    )
    high = await CodonOptimizerNode().run(
        context=context_at(tmp_path / "high"), cds=GFP_CDS, strategy="gc_target", gc_target=0.70
    )
    low_gc = json.loads(Path(low[1]).read_text(encoding="utf-8"))["gc_after"]
    high_gc = json.loads(Path(high[1]).read_text(encoding="utf-8"))["gc_after"]
    assert low_gc < high_gc
    assert low_gc < 0.5 < high_gc


@pytest.mark.asyncio
async def test_codon_optimizer_outputs_rna_alphabet(tmp_path: Path) -> None:
    result = await CodonOptimizerNode().run(
        context=context_at(tmp_path), cds="ATGGGCTAACGTTAA", strategy="cai_max", output_alphabet="rna"
    )
    optimized = "".join(
        line for line in Path(result[0]).read_text(encoding="utf-8").splitlines() if not line.startswith(">")
    )
    assert set(optimized) <= set("ACGU")
    assert optimized.startswith("AUG")


@pytest.mark.asyncio
async def test_codon_optimizer_reads_fasta_file_input(tmp_path: Path) -> None:
    fasta = tmp_path / "gene.fasta"
    fasta.write_text(f">gfp\n{GFP_CDS[:180]}\n", encoding="utf-8")
    result = await CodonOptimizerNode().run(context=context_at(tmp_path), cds=str(fasta), strategy="uniform")
    metrics = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert metrics["length_nt"] == 180
    fasta_text = Path(result[0]).read_text(encoding="utf-8").splitlines()
    assert fasta_text[0] == ">optimized_cds"
    assert all(len(line) <= 60 for line in fasta_text[1:])


@pytest.mark.asyncio
async def test_codon_metrics_computes_gfp_length_metrics(tmp_path: Path) -> None:
    result = await CodonMetricsNode().run(context=context_at(tmp_path), cds=GFP_CDS, window=60)
    metrics = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert metrics["length_nt"] == len(GFP_CDS)
    assert metrics["length_codons"] == len(GFP_CDS) // 3
    assert metrics["cai"] is not None and 0.05 < metrics["cai"] <= 1.0
    assert all(0.0 <= metrics[key] <= 1.0 for key in ("gc", "gc1", "gc2", "gc3"))
    assert 20.0 <= metrics["nc_effective"] <= 64.0
    assert metrics["codon_pair_score"] is not None
    assert metrics["starts_with_atg"] is True
    assert metrics["ends_with_stop"] is True
    assert metrics["internal_stop_count"] == 0
    assert metrics["window_count"] == pytest.approx(len(GFP_CDS) / 60, abs=1)
    assert metrics["window_gc_min"] <= metrics["window_gc_mean"] <= metrics["window_gc_max"]
    tsv_lines = Path(result[1]).read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0] == "metric\tvalue"
    assert any(line.startswith("cai\t") for line in tsv_lines[1:])
    assert not any("\n" in field for line in tsv_lines[1:] for field in line.split("\t"))


@pytest.mark.asyncio
async def test_codon_metrics_rejects_non_multiple_of_three(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="divisible by 3"):
        await CodonMetricsNode().run(context=context_at(tmp_path), cds="ATGGGCA")


@pytest.mark.asyncio
async def test_immune_motif_scanner_counts_literature_motifs(tmp_path: Path) -> None:
    rna40_fragment = "GCCCGUCUUGUUGUGUACUC"
    sequence = rna40_fragment + "UUUU" + "AACGTTAACGTT" + "AUUAUUUA" + "UGUGUU"
    result = await ImmuneMotifScannerNode().run(context=context_at(tmp_path), sequence=sequence, u_run_threshold=4)
    summary = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert summary["length_nt"] == len(sequence)
    assert summary["u_run_count"] == 1
    assert summary["max_u_run_length"] == 4
    assert summary["cpg_dinucleotide_count"] == 3
    assert summary["tlr7_8_motif_counts"]["GUCCUUCAACU"] == 0
    assert summary["tlr7_8_motif_counts"]["UGUGUU"] == 1
    assert summary["tlr9_cpg_motif_counts"]["AACGTT"] == 2
    assert summary["au_rich_4mer_counts"]["AUUA"] == 1
    assert summary["summary_score_heuristic"] > 0
    tsv = Path(result[1]).read_text(encoding="utf-8").splitlines()
    assert tsv[0] == "feature\tmotif\tstart\tend"
    assert any(line.startswith("tlr9_cpg_motif\tAACGTT") for line in tsv[1:])
    assert any(line.startswith("u_run\tUUUU\t") for line in tsv[1:])


@pytest.mark.asyncio
async def test_immune_motif_scanner_accepts_custom_motif_lists(tmp_path: Path) -> None:
    result = await ImmuneMotifScannerNode().run(
        context=context_at(tmp_path),
        sequence="GGGUGUGUGGUAA",
        tlr7_8_motifs="UGUGUG",
        tlr9_cpg_motifs="",
        au_rich_weights="GGGU:2.0",
    )
    summary = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert summary["tlr7_8_motif_counts"] == {"UGUGUG": 1}
    assert summary["tlr9_cpg_motif_counts"] == {}
    assert summary["au_rich_4mer_counts"] == {"GGGU": 1}


@pytest.mark.asyncio
async def test_mirna_seed_scanner_classifies_targetscan_site_types(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.tsv"
    seed_file.write_text("mirna_id\tseed\tweight\nlet-7a\tGAGGTAG\t2.0\nmiR-1\tGTATGAA\t1.0\n", encoding="utf-8")
    target = "GG" + "CUACCUC" + "AA" + "ACUACCUC" + "AA" + "AUACCUC" + "GG"
    result = await MiRNASeedScannerNode().run(context=context_at(tmp_path), target=target, seed_file=str(seed_file))
    hits_tsv = Path(result[0]).read_text(encoding="utf-8").splitlines()
    header = hits_tsv[0].split("\t")
    assert header == ["mirna_id", "seed", "seed_type", "start", "end", "site", "context", "weight"]
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in hits_tsv[1:]]
    let7 = [row for row in rows if row["mirna_id"] == "let-7a"]
    assert {row["seed_type"] for row in let7} == {"7mer-m8", "8mer", "7mer-A1"}
    eight_mer = next(row for row in let7 if row["seed_type"] == "8mer")
    assert eight_mer["site"] == "ACUACCUC"
    assert int(eight_mer["end"]) - int(eight_mer["start"]) == 7
    summary = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert summary["hit_count"] == len(rows)
    assert summary["hits_by_type"] == {"7mer-m8": 1, "8mer": 1, "7mer-A1": 1}
    assert summary["hits_by_mirna"]["let-7a"] == 3
    assert summary["weighted_score"] == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_mirna_seed_scanner_rejects_bad_seed_lengths(tmp_path: Path) -> None:
    seed_file = tmp_path / "bad.tsv"
    seed_file.write_text("mirna_id\tseed\nlet-7a\tGAGGTA\n", encoding="utf-8")
    with pytest.raises(ValueError, match="7 ACGU characters"):
        await MiRNASeedScannerNode().run(
            context=context_at(tmp_path), target="AACUACCUGACUUG", seed_file=str(seed_file)
        )


@pytest.mark.asyncio
async def test_mirna_seed_scanner_reads_csv_seed_tables(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.csv"
    seed_file.write_text("mirna_id,seed,weight\nmiR-124,AAGGCAC,1.5\n", encoding="utf-8")
    result = await MiRNASeedScannerNode().run(
        context=context_at(tmp_path), target="CACGCCTTAGG", seed_file=str(seed_file)
    )
    summary = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert summary["hit_count"] == 0


@pytest.mark.asyncio
async def test_utr_feature_builder_computes_kozak_uorf_and_polyu(tmp_path: Path) -> None:
    five = "UUUUUUAUGAAAUAGGCCACC"
    three = "AUUUAUUUAUUUA"
    result = await UTRFeatureBuilderNode().run(
        context=context_at(tmp_path), five_utr=five, three_utr=three, poly_u_min=5
    )
    features = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    five_features = features["five_utr"]
    assert five_features["length_nt"] == len(five)
    assert five_features["aug_count"] == 1
    assert five_features["poly_u_run_count"] == 1
    assert five_features["max_poly_u_length"] == 6
    assert five_features["uorf_count"] == 1
    kozak = features["kozak"]
    assert kozak["context_minus6_to_minus1"] == "GCCACC"
    assert kozak["minus3_purine"] is True
    assert kozak["plus4_evaluated"] is False
    assert kozak["consensus_matches_minus6_to_minus1"] == 6
    three_features = features["three_utr"]
    assert three_features["au_fraction"] == pytest.approx(1.0)
    assert "mfe_note" in features


@pytest.mark.asyncio
async def test_utr_feature_builder_reads_utr_files(tmp_path: Path) -> None:
    five_file = tmp_path / "five.fa"
    five_file.write_text(">5p\nGCCGCCACC\n", encoding="utf-8")
    result = await UTRFeatureBuilderNode().run(context=context_at(tmp_path), five_utr=str(five_file))
    features = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert features["five_utr"]["length_nt"] == 9
    assert "three_utr" not in features


def _read_tsv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]
    return header, rows


@pytest.mark.asyncio
async def test_codon_metrics_per_record_table_for_multi_record_fasta(tmp_path: Path) -> None:
    fasta = tmp_path / "candidates.fasta"
    fasta.write_text(
        ">cand_0000\nATGGGCTAA\n>cand_0001\nATGGGCTGA\n>cand_0002\nATGTGCCCCTGA\n",
        encoding="utf-8",
    )
    result = await CodonMetricsNode().run(context=context_at(tmp_path), cds=str(fasta), window=3)
    assert len(result) == 4
    header, rows = _read_tsv(result[2])
    assert header == ["id", "cai", "gc", "gc_window_max_dev", "n_codons"]
    assert [row["id"] for row in rows] == ["cand_0000", "cand_0001", "cand_0002"]
    by_id = {row["id"]: row for row in rows}
    assert float(by_id["cand_0000"]["cai"]) == pytest.approx(1.0)
    assert float(by_id["cand_0000"]["gc"]) == pytest.approx(4 / 9)
    assert int(by_id["cand_0000"]["n_codons"]) == 3
    assert float(by_id["cand_0002"]["gc"]) == pytest.approx(7 / 12)
    assert int(by_id["cand_0002"]["n_codons"]) == 4
    # ATG TGC CCC TGA windows with window=3: GC 1/3, 2/3, 1.0, 1/3 around mean 7/12.
    assert float(by_id["cand_0002"]["gc_window_max_dev"]) == pytest.approx(1.0 - 7 / 12)
    payload = json.loads(Path(result[3]).read_text(encoding="utf-8"))
    assert [entry["id"] for entry in payload] == ["cand_0000", "cand_0001", "cand_0002"]
    assert payload[1]["n_codons"] == 3
    aggregate = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert aggregate["length_nt"] == 30


@pytest.mark.asyncio
async def test_immune_motif_scanner_per_record_burden(tmp_path: Path) -> None:
    fasta = tmp_path / "batch.fasta"
    hot = "UUUU" + "AACGTTAACGTT"
    cold = "GCCGCCGCCACC"
    fasta.write_text(f">cand_0000\n{hot}\n>cand_0001\n{cold}\n", encoding="utf-8")
    result = await ImmuneMotifScannerNode().run(context=context_at(tmp_path), sequence=str(fasta))
    assert len(result) == 4
    header, rows = _read_tsv(result[2])
    assert header == ["id", "immune_burden_per_kb", "u_run_count", "cpg_count"]
    by_id = {row["id"]: row for row in rows}
    assert int(by_id["cand_0000"]["u_run_count"]) == 1
    assert int(by_id["cand_0000"]["cpg_count"]) == 2
    # u_runs(1) + weighted 4-mers UUUU(1.0) + UUUA(0.8) + CpG(2), normalised per kb.
    assert float(by_id["cand_0000"]["immune_burden_per_kb"]) == pytest.approx((1 + 1.8 + 2) * 1000 / len(hot))
    assert int(by_id["cand_0001"]["u_run_count"]) == 0
    assert int(by_id["cand_0001"]["cpg_count"]) == 2
    assert float(by_id["cand_0001"]["immune_burden_per_kb"]) == pytest.approx(2 * 1000 / len(cold))
    payload = json.loads(Path(result[3]).read_text(encoding="utf-8"))
    assert [entry["id"] for entry in payload] == ["cand_0000", "cand_0001"]
    assert payload[0]["cpg_count"] == 2


@pytest.mark.asyncio
async def test_mirna_seed_scanner_per_record_weighted_hits(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.tsv"
    seed_file.write_text("mirna_id\tseed\tweight\nlet-7a\tGAGGTAG\t2.0\n", encoding="utf-8")
    fasta = tmp_path / "targets.fasta"
    hit_target = "GG" + "CUACCUC" + "AA" + "ACUACCUC" + "GG"
    miss_target = "GGGGGGGGGGGGGGGG"
    fasta.write_text(f">cand_0000\n{hit_target}\n>cand_0001\n{miss_target}\n", encoding="utf-8")
    result = await MiRNASeedScannerNode().run(
        context=context_at(tmp_path), target=str(fasta), seed_file=str(seed_file)
    )
    assert len(result) == 4
    header, rows = _read_tsv(result[2])
    assert header == ["id", "weighted_hits", "n_hits"]
    by_id = {row["id"]: row for row in rows}
    assert float(by_id["cand_0000"]["weighted_hits"]) == pytest.approx(4.0)
    assert int(by_id["cand_0000"]["n_hits"]) == 2
    assert float(by_id["cand_0001"]["weighted_hits"]) == pytest.approx(0.0)
    assert int(by_id["cand_0001"]["n_hits"]) == 0
    payload = json.loads(Path(result[3]).read_text(encoding="utf-8"))
    assert payload[0]["n_hits"] == 2


@pytest.mark.asyncio
async def test_utr_feature_builder_per_record_rows_for_multi_record_utr_fasta(tmp_path: Path) -> None:
    fasta = tmp_path / "utrs.fasta"
    fasta.write_text(
        ">cand_0000\nGCCGCCACC\n>cand_0001\nUUUUUUUUUU\n",
        encoding="utf-8",
    )
    result = await UTRFeatureBuilderNode().run(context=context_at(tmp_path), five_utr=str(fasta))
    assert len(result) == 3
    header, rows = _read_tsv(result[1])
    assert header == ["id", "kozak", "uorf_count", "gc", "length"]
    by_id = {row["id"]: row for row in rows}
    assert float(by_id["cand_0000"]["kozak"]) == pytest.approx(1.0)
    assert int(by_id["cand_0000"]["uorf_count"]) == 0
    assert float(by_id["cand_0000"]["gc"]) == pytest.approx(8 / 9)
    assert int(by_id["cand_0000"]["length"]) == 9
    assert float(by_id["cand_0001"]["kozak"]) == pytest.approx(0.0)
    assert float(by_id["cand_0001"]["gc"]) == pytest.approx(0.0)
    assert int(by_id["cand_0001"]["length"]) == 10
    payload = json.loads(Path(result[2]).read_text(encoding="utf-8"))
    assert [entry["id"] for entry in payload] == ["cand_0000", "cand_0001"]
    features = json.loads(Path(result[0]).read_text(encoding="utf-8"))
    assert features["five_utr"]["length_nt"] == 19


def test_codon_design_ids_are_owned_by_focused_modules() -> None:
    index = build_index()
    family = {node_id: module for node_id, module in index.items() if node_id in FAMILY_IDS}
    assert set(family) == set(FAMILY_IDS)
    assert all(module.startswith("bionodulo.nodes.builtin.codon_design_family.") for module in family.values())


def test_family_is_changed_reflects_input_content() -> None:
    inputs_one: dict[str, Any] = {"cds": "ATGGGCTAA"}
    inputs_two = {"cds": "ATGGGCATA"}
    assert CodonOptimizerNode.IS_CHANGED(inputs_one) != CodonOptimizerNode.IS_CHANGED(inputs_two)
    assert CodonOptimizerNode.IS_CHANGED(inputs_one) == CodonOptimizerNode.IS_CHANGED(dict(inputs_one))
