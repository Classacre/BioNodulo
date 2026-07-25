"""Evidence and port contracts for the focused RSeQC 5.0.3 wave."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.rseqc_family.adapter import (
    RSEQC_DOCUMENTATION_REVISION,
    RSEQC_DOCUMENTATION_SHA256,
    RSEQC_DOCUMENTATION_URL,
    RSEQC_PACKAGE_CONSTRAINT,
    RSEQC_PACKAGE_VERSION,
    RSEQC_SOURCE_SHA256,
    RSEQC_SOURCE_URL,
    RSEQC_UPSTREAM_SCRIPT_VERSION,
    RSeQCCommandNode,
)
from bionodulo.nodes.registry import NodeRegistry


NO_DEFAULT = object()

# node ID, primary executable, source script, required ports, optional ports, returns
NODE_CONTRACTS: tuple[
    tuple[
        str,
        str,
        str,
        tuple[tuple[str, Any], ...],
        tuple[tuple[str, Any, Any], ...],
        tuple[tuple[str, str], ...],
    ],
    ...,
] = (
    (
        "rseqc_bam2wig",
        "bam2wig.py",
        "scripts/bam2wig.py",
        (("input", "BAM"), ("bam_index", "BAI"), ("chromsize", "FILE")),
        (
            ("wigsum", "INT", None),
            ("skip_multi_hits", "BOOLEAN", False),
            ("strand", "STRING", ""),
            ("mapq", "INT", 30),
        ),
        (("wiggle_tracks", "FILE_LIST"), ("bigwig_tracks", "FILE_LIST")),
    ),
    (
        "rseqc_bam_stat",
        "bam_stat.py",
        "scripts/bam_stat.py",
        (("input", ("BAM", "SAM")),),
        (("mapq", "INT", 30),),
        (("mapping_stats", "STATS_FILE"),),
    ),
    (
        "rseqc_clipping_profile",
        "clipping_profile.py",
        "scripts/clipping_profile.py",
        (("input", ("BAM", "SAM")), ("layout", "STRING")),
        (("mapq", "INT", 30),),
        (
            ("clipping_profile", "TSV"),
            ("r_script", "TEXT"),
            ("clipping_plots", "FILE_LIST"),
        ),
    ),
    (
        "rseqc_deletion_profile",
        "deletion_profile.py",
        "scripts/deletion_profile.py",
        (("input", "BAM"), ("read_align_length", "INT")),
        (("read_num", "INT", 1000000), ("mapq", "INT", 30)),
        (("deletion_profile", "TSV"), ("r_script", "TEXT"), ("deletion_plot", "IMAGE")),
    ),
    (
        "rseqc_fpkm_count",
        "FPKM_count.py",
        "scripts/FPKM_count.py",
        (("input", "BAM"), ("bam_index", "BAI"), ("refgene", "BED")),
        (
            ("strand", "STRING", ""),
            ("skip_multi_hits", "BOOLEAN", False),
            ("only_exonic", "BOOLEAN", False),
            ("mapq", "INT", 30),
            ("single_read", "FLOAT", 1),
        ),
        (("fpkm_counts", "TSV"),),
    ),
    (
        "rseqc_gene_body_coverage",
        "geneBody_coverage.py",
        "scripts/geneBody_coverage.py",
        (("input", "BAM_LIST"), ("bam_indexes", "FILE_LIST"), ("refgene", "BED")),
        (("minimum_length", "INT", 100), ("format", "STRING", "pdf")),
        (
            ("coverage_table", "TSV"),
            ("r_script", "TEXT"),
            ("coverage_plots", "FILE_LIST"),
        ),
    ),
    (
        "rseqc_gene_body_coverage2",
        "geneBody_coverage2.py",
        "scripts/geneBody_coverage2.py",
        (("input", "BIGWIG"), ("refgene", "BED")),
        (("graph_type", "STRING", "pdf"),),
        (("coverage_table", "TSV"), ("r_script", "TEXT"), ("coverage_plot", "IMAGE")),
    ),
    (
        "rseqc_infer_experiment",
        "infer_experiment.py",
        "scripts/infer_experiment.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (("sample_size", "INT", 200000), ("mapq", "INT", 30)),
        (("infer_experiment", "STATS_FILE"),),
    ),
    (
        "rseqc_inner_distance",
        "inner_distance.py",
        "scripts/inner_distance.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (
            ("sample_size", "INT", 1000000),
            ("lower_bound", "INT", -250),
            ("upper_bound", "INT", 250),
            ("step", "INT", 5),
            ("mapq", "INT", 30),
        ),
        (
            ("inner_distances", "TSV"),
            ("inner_distance_frequency", "TSV"),
            ("r_script", "TEXT"),
            ("inner_distance_plot", "IMAGE"),
        ),
    ),
    (
        "rseqc_insertion_profile",
        "insertion_profile.py",
        "scripts/insertion_profile.py",
        (("input", ("BAM", "SAM")), ("layout", "STRING")),
        (("mapq", "INT", 30),),
        (
            ("insertion_profile", "TSV"),
            ("r_script", "TEXT"),
            ("insertion_profile_plots", "FILE_LIST"),
        ),
    ),
    (
        "rseqc_junction_annotation",
        "junction_annotation.py",
        "scripts/junction_annotation.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (("min_intron", "INT", 50), ("mapq", "INT", 30)),
        (
            ("junctions", "TSV"),
            ("r_script", "TEXT"),
            ("splice_events_plot", "IMAGE"),
            ("splice_junction_plot", "IMAGE"),
            ("junction_bed", "BED"),
            ("junction_interact_bed", "BED"),
        ),
    ),
    (
        "rseqc_junction_saturation",
        "junction_saturation.py",
        "scripts/junction_saturation.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (
            ("percentile_floor", "INT", 5),
            ("percentile_ceiling", "INT", 100),
            ("percentile_step", "INT", 5),
            ("min_intron", "INT", 50),
            ("min_coverage", "INT", 1),
            ("mapq", "INT", 30),
        ),
        (("r_script", "TEXT"), ("junction_saturation_plot", "IMAGE")),
    ),
    (
        "rseqc_mismatch_profile",
        "mismatch_profile.py",
        "scripts/mismatch_profile.py",
        (("input", "BAM"), ("read_align_length", "INT")),
        (("read_num", "INT", 1000000), ("mapq", "INT", 30)),
        (("mismatch_profile", "TSV"), ("r_script", "TEXT"), ("mismatch_profile_plot", "IMAGE")),
    ),
    (
        "rseqc_read_distribution",
        "read_distribution.py",
        "scripts/read_distribution.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (),
        (("read_distribution", "STATS_FILE"),),
    ),
    (
        "rseqc_read_duplication",
        "read_duplication.py",
        "scripts/read_duplication.py",
        (("input", ("BAM", "SAM")),),
        (("up_limit", "INT", 500), ("mapq", "INT", 30)),
        (
            ("sequence_duplication", "TSV"),
            ("position_duplication", "TSV"),
            ("r_script", "TEXT"),
            ("duplication_plot", "IMAGE"),
        ),
    ),
    (
        "rseqc_read_gc",
        "read_GC.py",
        "scripts/read_GC.py",
        (("input", ("BAM", "SAM")),),
        (("mapq", "INT", 30),),
        (("gc_counts", "TSV"), ("r_script", "TEXT"), ("gc_plot", "IMAGE")),
    ),
    (
        "rseqc_read_hexamer",
        "read_hexamer.py",
        "scripts/read_hexamer.py",
        (("inputs", ("FASTA", "FASTQ")),),
        (("refgenome", "FASTA", NO_DEFAULT), ("refgene", "FASTA", NO_DEFAULT)),
        (("hexamer_frequencies", "TSV"),),
    ),
    (
        "rseqc_read_nvc",
        "read_NVC.py",
        "scripts/read_NVC.py",
        (("input", ("BAM", "SAM")),),
        (("nx", "BOOLEAN", False), ("mapq", "INT", 30)),
        (("nvc_table", "TSV"), ("r_script", "TEXT"), ("nvc_plot", "IMAGE")),
    ),
    (
        "rseqc_read_quality",
        "read_quality.py",
        "scripts/read_quality.py",
        (("input", ("BAM", "SAM")),),
        (("reduce", "INT", 1), ("mapq", "INT", 30)),
        (("r_script", "TEXT"), ("quality_boxplot", "IMAGE"), ("quality_heatmap", "IMAGE")),
    ),
    (
        "rseqc_rna_fragment_size",
        "RNA_fragment_size.py",
        "scripts/RNA_fragment_size.py",
        (("input", "BAM"), ("bam_index", "BAI"), ("refgene", "BED")),
        (("mapq", "INT", 30), ("frag_num", "INT", 3)),
        (("fragment_sizes", "TSV"),),
    ),
    (
        "rseqc_rpkm_saturation",
        "RPKM_saturation.py",
        "scripts/RPKM_saturation.py",
        (("input", ("BAM", "SAM")), ("refgene", "BED")),
        (
            ("strand", "STRING", ""),
            ("percentile_floor", "INT", 5),
            ("percentile_ceiling", "INT", 100),
            ("percentile_step", "INT", 5),
            ("rpkm_cutoff", "FLOAT", 0.01),
            ("mapq", "INT", 30),
        ),
        (
            ("rpkm_values", "TSV"),
            ("raw_counts", "TSV"),
            ("r_script", "TEXT"),
            ("saturation_plot", "IMAGE"),
        ),
    ),
    (
        "rseqc_tin",
        "tin.py",
        "scripts/tin.py",
        (("input", "BAM_LIST"), ("bam_indexes", "FILE_LIST"), ("refgene", "BED")),
        (
            ("min_cov", "INT", 10),
            ("sample_size", "INT", 100),
            ("subtract_background", "BOOLEAN", False),
            ("minCov", "INT", None),
            ("samplesize", "INT", None),
            ("subtractbackground", "BOOLEAN", None),
            ("inputs", "BAM_LIST", None),
        ),
        (("tin_results", "DIRECTORY"),),
    ),
)


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.mark.parametrize(
    ("node_id", "executable", "script", "required", "optional", "returns"),
    NODE_CONTRACTS,
    ids=[contract[0] for contract in NODE_CONTRACTS],
)
def test_all_rseqc_node_ports_and_primary_sources(
    registry: NodeRegistry,
    node_id: str,
    executable: str,
    script: str,
    required: tuple[tuple[str, Any], ...],
    optional: tuple[tuple[str, Any, Any], ...],
    returns: tuple[tuple[str, str], ...],
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    ports = node_class.INPUT_TYPES()

    assert node_class.REQUIRED_EXECUTABLES[0] == executable
    assert node_class.UPSTREAM_SCRIPT == script
    assert tuple((name, spec[0]) for name, spec in ports["required"].items()) == required
    assert (
        tuple((name, spec[0], spec[1].get("default", NO_DEFAULT)) for name, spec in ports.get("optional", {}).items())
        == optional
    )
    assert tuple(zip(node_class.RETURN_NAMES, node_class.RETURN_TYPES, strict=True)) == returns


def test_contract_table_covers_exactly_the_22_focused_rseqc_ids(registry: NodeRegistry) -> None:
    expected = {contract[0] for contract in NODE_CONTRACTS}
    discovered = {node_id for node_id in registry.all() if node_id.startswith("rseqc_")}

    assert len(expected) == 22
    assert discovered == expected


def test_archive_documentation_package_and_script_version_evidence(registry: NodeRegistry) -> None:
    assert PACKAGE_MIN_VERSIONS["rseqc"] == RSEQC_PACKAGE_VERSION == "5.0.3"
    assert RSEQC_PACKAGE_CONSTRAINT == "rseqc==5.0.3"
    assert RSEQC_SOURCE_URL.endswith("RSeQC-5.0.3.tar.gz")
    assert RSEQC_SOURCE_SHA256 == "869f542e08f50c8874280d58e4f5565857b0aebac66a8eceef3f23016175061e"
    assert RSEQC_DOCUMENTATION_URL == "https://rseqc.sourceforge.net/"
    assert RSEQC_DOCUMENTATION_REVISION == "2024-10-03T18:06:49Z"
    assert RSEQC_DOCUMENTATION_SHA256 == "5106df3ab8ed63375254a33a059bfb3a471a76ba337f8c2308b872864cf6f839"

    script_versions: dict[str, str] = {}
    for node_id, *_rest in NODE_CONTRACTS:
        node_class = registry.get(node_id)
        assert node_class is not None
        assert issubclass(node_class, RSeQCCommandNode)
        assert node_class.VERSION == node_class.PACKAGE_VERSION == "5.0.3"
        assert node_class.GIT_URL == node_class.GIT_COMMIT == ""
        assert node_class.SOURCE_URL == RSEQC_SOURCE_URL
        assert node_class.SOURCE_SHA256 == RSEQC_SOURCE_SHA256
        assert node_class.SOURCE_REVISION == f"sha256:{RSEQC_SOURCE_SHA256}"
        assert node_class.DOCUMENTATION_REVISION == RSEQC_DOCUMENTATION_REVISION
        assert node_class.DOCUMENTATION_SHA256 == RSEQC_DOCUMENTATION_SHA256
        assert node_class.CONDA_PACKAGE_CONSTRAINTS == {"rseqc": "5.0.3"}
        assert node_class.PACKAGE_CONSTRAINTS == ("rseqc==5.0.3",)
        assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
        script_versions[node_id] = node_class.UPSTREAM_SCRIPT_VERSION

    assert set(script_versions.values()) == {RSEQC_UPSTREAM_SCRIPT_VERSION, "2.6.2"}
    assert script_versions["rseqc_read_quality"] == "2.6.2"
    assert all(
        version == RSEQC_UPSTREAM_SCRIPT_VERSION
        for node_id, version in script_versions.items()
        if node_id != "rseqc_read_quality"
    )


def test_optional_boolean_flags_validate_and_follow_upstream_parser_order(
    registry: NodeRegistry,
) -> None:
    bam2wig = registry.get("rseqc_bam2wig")
    fpkm = registry.get("rseqc_fpkm_count")
    assert bam2wig is not None and fpkm is not None

    bam2wig_inputs = {
        "input": "a.bam",
        "bam_index": "a.bam.bai",
        "chromsize": "chrom.sizes",
        "output": "/work/node",
        "wigsum": 1000,
        "skip_multi_hits": True,
        "strand": "++,-+",
        "mapq": 20,
    }
    assert bam2wig.render_command(bam2wig_inputs) == [
        "bam2wig.py",
        "-i",
        "a.bam",
        "-s",
        "chrom.sizes",
        "-o",
        "/work/node/outfile",
        "-t",
        "1000",
        "-u",
        "-d",
        "++,-+",
        "-q",
        "20",
    ]

    fpkm_inputs = {
        "input": "a.bam",
        "bam_index": "a.bam.bai",
        "refgene": "genes.bed",
        "output": "/work/node",
        "strand": "++,-+",
        "skip_multi_hits": True,
        "only_exonic": True,
        "mapq": 20,
        "single_read": 0.5,
    }
    assert fpkm.render_command(fpkm_inputs) == [
        "FPKM_count.py",
        "-i",
        "a.bam",
        "-o",
        "/work/node/output",
        "-r",
        "genes.bed",
        "-d",
        "++,-+",
        "-u",
        "-e",
        "-q",
        "20",
        "-s",
        "0.5",
    ]

    for node_class, base, keys in (
        (bam2wig, bam2wig_inputs, ("skip_multi_hits",)),
        (fpkm, fpkm_inputs, ("skip_multi_hits", "only_exonic")),
    ):
        for key in keys:
            for invalid in (None, 1, "true"):
                assert node_class.VALIDATE_INPUTS({**base, key: invalid}) == (f"Input '{key}' must be a boolean")


def test_indexed_bam_consumers_declare_and_validate_exact_sibling_sidecars(
    registry: NodeRegistry,
) -> None:
    cases: dict[str, tuple[dict[str, Any], str]] = {
        "rseqc_bam2wig": (
            {"input": "a.bam", "bam_index": "a.bam.bai", "chromsize": "chrom.sizes"},
            "bam_index",
        ),
        "rseqc_fpkm_count": (
            {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"},
            "bam_index",
        ),
        "rseqc_gene_body_coverage": (
            {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"},
            "bam_indexes",
        ),
        "rseqc_rna_fragment_size": (
            {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"},
            "bam_index",
        ),
        "rseqc_tin": (
            {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"},
            "bam_indexes",
        ),
    }
    actual = {
        node_id
        for node_id, *_rest in NODE_CONTRACTS
        if any("bam_index" in name for group in registry.get(node_id).INPUT_TYPES().values() for name in group)
    }
    assert actual == set(cases)

    for node_id, (inputs, index_key) in cases.items():
        node_class = registry.get(node_id)
        assert node_class is not None
        assert node_class.VALIDATE_INPUTS(inputs) is True
        invalid = {**inputs, index_key: ["wrong.bai"] if index_key.endswith("indexes") else "wrong.bai"}
        assert "sibling" in str(node_class.VALIDATE_INPUTS(invalid))


def test_mismatch_profile_is_bam_only_per_script_and_official_manual(registry: NodeRegistry) -> None:
    node_class = registry.get("rseqc_mismatch_profile")
    assert node_class is not None
    input_spec = node_class.INPUT_TYPES()["required"]["input"]

    assert input_spec[0] == "BAM"
    assert "MD" in input_spec[1]["description"]
    assert node_class.DOCUMENTATION_URL == "https://rseqc.sourceforge.net/#mismatch-profile-py"


@pytest.mark.asyncio
async def test_zero_exit_without_planned_artifacts_still_fails_closed(
    tmp_path: Path,
    registry: NodeRegistry,
) -> None:
    node_class = registry.get("rseqc_mismatch_profile")
    assert node_class is not None

    class SuccessfulWithoutOutputs:
        async def run_command(self, _command: list[str], **_kwargs: Any) -> dict[str, Any]:
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not create expected output"):
        await node_class().run(
            context=SuccessfulWithoutOutputs(),
            output_dir=tmp_path,
            input="a.bam",
            read_align_length=101,
        )

    semantics = node_class.EXIT_SEMANTICS
    for claim in ("exit 0", "Rscript", "wigToBigWig", "non-zero", "planned artifact"):
        assert claim in semantics
