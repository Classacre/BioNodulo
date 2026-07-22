"""Compact contract coverage for the focused BCFtools 1.24 family."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.registry import NodeRegistry


OUTPUT = "/work/node"
FORMAT = r"%CHROM\t%POS\n"


CASES: list[tuple[str, dict[str, object], list[str]]] = [
    (
        "bcftools_mpileup",
        {"input_bams": ["a.bam"], "no_reference": True},
        ["bcftools", "mpileup", "--no-reference", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/mpileup.vcf.gz", "a.bam"],
    ),
    (
        "bcftools_call",
        {"input_file": "in.vcf"},
        ["bcftools", "call", "-m", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/called.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_filter",
        {"input_file": "in.vcf"},
        ["bcftools", "filter", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/filtered.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_norm",
        {"input_file": "in.vcf", "multiallelics": "-both"},
        [
            "bcftools",
            "norm",
            "--multiallelics",
            "-both",
            "--sort",
            "pos",
            "--threads",
            "4",
            "-Oz",
            "-o",
            f"{OUTPUT}/normalized.vcf.gz",
            "in.vcf",
        ],
    ),
    (
        "bcftools_view",
        {"input_file": "in.vcf"},
        ["bcftools", "view", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/view.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_concat",
        {"input_files": ["a.vcf", "b.vcf"]},
        ["bcftools", "concat", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/concat.vcf.gz", "a.vcf", "b.vcf"],
    ),
    (
        "bcftools_merge",
        {"input_files": ["a.vcf", "b.vcf"], "no_index": True},
        ["bcftools", "merge", "--no-index", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/merged.vcf.gz", "a.vcf", "b.vcf"],
    ),
    (
        "bcftools_isec",
        {"input_files": ["a.vcf.gz", "b.vcf.gz"], "input_indexes": ["a.vcf.gz.tbi", "b.vcf.gz.tbi"]},
        [
            "bcftools",
            "isec",
            "--nfiles",
            "=2",
            "--write",
            "1",
            "--collapse",
            "none",
            "-Oz",
            "-o",
            f"{OUTPUT}/isec.vcf.gz",
            "a.vcf.gz",
            "b.vcf.gz",
        ],
    ),
    (
        "bcftools_reheader",
        {"input_file": "in.vcf.gz", "samples": ["S1"]},
        ["bcftools", "reheader", "--samples-list", "S1", "-o", f"{OUTPUT}/reheadered.vcf.gz", "in.vcf.gz"],
    ),
    (
        "bcftools_stats",
        {"input_file": "in.vcf"},
        ["bcftools", "stats", "--collapse", "none", "in.vcf"],
    ),
    (
        "bcftools_consensus",
        {"input_file": "in.vcf.gz", "input_index": "in.vcf.gz.tbi", "reference": "ref.fa"},
        ["bcftools", "consensus", "--fasta-ref", "ref.fa", "-I", "in.vcf.gz"],
    ),
    (
        "bcftools_query",
        {"input_files": ["in.vcf"], "format": FORMAT},
        ["bcftools", "query", "-f", FORMAT, "-o", f"{OUTPUT}/query.tsv", "in.vcf"],
    ),
    (
        "bcftools_query_list_samples",
        {"input_file": "in.vcf"},
        ["bcftools", "query", "-l", "-o", f"{OUTPUT}/samples.tsv", "in.vcf"],
    ),
    (
        "bcftools_gtcheck",
        {"input_file": "in.vcf"},
        ["bcftools", "gtcheck", "-o", f"{OUTPUT}/gtcheck.tsv", "in.vcf"],
    ),
    (
        "bcftools_roh",
        {"input_file": "in.vcf"},
        ["bcftools", "roh", "-Or", "-o", f"{OUTPUT}/roh.tsv", "in.vcf"],
    ),
    (
        "bcftools_convert_to_vcf",
        {"mode": "gen_sample", "input_file": "in.gen", "sample_file": "in.samples"},
        [
            "bcftools",
            "convert",
            "--gensample2vcf",
            "in.gen,in.samples",
            "--threads",
            "4",
            "-Oz",
            "-o",
            f"{OUTPUT}/converted.vcf.gz",
        ],
    ),
    (
        "bcftools_convert_from_vcf",
        {"input_file": "in.vcf"},
        [
            "bcftools",
            "convert",
            "--gensample",
            f"{OUTPUT}/results/converted.gen,{OUTPUT}/results/converted.samples",
            "--threads",
            "4",
            "in.vcf",
        ],
    ),
    (
        "bcftools_cnv",
        {"input_file": "in.vcf", "query_sample": "S1"},
        ["bcftools", "cnv", "--output-dir", f"{OUTPUT}/results", "--query-sample", "S1", "in.vcf"],
    ),
    (
        "bcftools_csq",
        {"input_file": "in.vcf", "reference": "ref.fa", "reference_index": "ref.fa.fai", "gff_annot": "genes.gff3"},
        ["bcftools", "csq", "-f", "ref.fa", "-g", "genes.gff3", "-Oz", "-o", f"{OUTPUT}/csq.vcf.gz", "in.vcf"],
    ),
    ("bcftools_plugin_counts", {"input_file": "in.vcf"}, ["bcftools", "+counts", "in.vcf"]),
    (
        "bcftools_plugin_dosage",
        {"input_file": "in.vcf"},
        ["bcftools", "+dosage", "in.vcf", "--", "-t", "PL,GL,GT"],
    ),
    (
        "bcftools_plugin_missing2ref",
        {"input_file": "in.vcf"},
        ["bcftools", "+missing2ref", "-Oz", "-o", f"{OUTPUT}/missing2ref.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_plugin_tag2tag",
        {"input_file": "in.vcf"},
        ["bcftools", "+tag2tag", "-Oz", "-o", f"{OUTPUT}/tag2tag.vcf.gz", "in.vcf", "--", "--GP-to-GL"],
    ),
    (
        "bcftools_plugin_fill_an_ac",
        {"input_file": "in.vcf"},
        ["bcftools", "+fill-AN-AC", "-Oz", "-o", f"{OUTPUT}/fill_an_ac.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_plugin_fill_tags",
        {"input_file": "in.vcf"},
        ["bcftools", "+fill-tags", "-Oz", "-o", f"{OUTPUT}/fill_tags.vcf.gz", "in.vcf", "--", "--tags", "all"],
    ),
    (
        "bcftools_plugin_setgt",
        {"input_file": "in.vcf"},
        ["bcftools", "+setGT", "-Oz", "-o", f"{OUTPUT}/setgt.vcf.gz", "in.vcf", "--", "-t", ".", "-n", "0"],
    ),
    (
        "bcftools_plugin_fixploidy",
        {"input_file": "in.vcf"},
        [
            "bcftools",
            "+fixploidy",
            "-Oz",
            "-o",
            f"{OUTPUT}/fixploidy.vcf.gz",
            "in.vcf",
            "--",
            "--default-ploidy",
            "2",
            "--tags",
            "GT",
        ],
    ),
    (
        "bcftools_plugin_mendelian",
        {"input_file": "in.vcf", "child": "C", "father": "F", "mother": "M"},
        [
            "bcftools",
            "+mendelian2",
            "-Oz",
            "-o",
            f"{OUTPUT}/mendelian.vcf.gz",
            "in.vcf",
            "--",
            "--mode",
            "a",
            "--pfm",
            "2X:C,F,M",
            "--rules",
            "GRCh37",
        ],
    ),
    (
        "bcftools_plugin_impute_info",
        {"input_file": "in.vcf"},
        ["bcftools", "+impute-info", "-Oz", "-o", f"{OUTPUT}/impute_info.vcf.gz", "in.vcf"],
    ),
    (
        "bcftools_plugin_color_chrs",
        {"input_file": "in.vcf", "sample_a": "A", "sample_b": "B"},
        ["bcftools", "+color-chrs", "in.vcf", "--", "--unrelated", "A,B", "-p", f"{OUTPUT}/color_chrs"],
    ),
    (
        "bcftools_plugin_frameshifts",
        {"input_file": "in.vcf", "exons": "exons.bed.gz", "exons_index": "exons.bed.gz.tbi"},
        [
            "bcftools",
            "+frameshifts",
            "-Oz",
            "-o",
            f"{OUTPUT}/frameshifts.vcf.gz",
            "in.vcf",
            "--",
            "--exons",
            "exons.bed.gz",
        ],
    ),
    (
        "bcftools_plugin_split_vep",
        {"input_file": "in.vcf", "columns": "Consequence"},
        ["bcftools", "+split-vep", "--columns", "Consequence", "-Oz", "-o", f"{OUTPUT}/split_vep.vcf.gz", "in.vcf"],
    ),
]


CORE_NODE_IDS = {case[0] for case in CASES[:19]}


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.mark.parametrize("node_id,inputs,expected", CASES, ids=[case[0] for case in CASES])
def test_bcftools_contract_renders_native_argv(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    expected: list[str],
) -> None:
    node_class = registry.get(node_id)
    rendered_inputs = {"output": OUTPUT, **inputs}
    assert node_class.VALIDATE_INPUTS(rendered_inputs) is True
    assert node_class.render_command(rendered_inputs) == expected
    assert not {">", "|", "&&"}.intersection(expected)


@pytest.mark.parametrize("node_id,_,__", CASES, ids=[case[0] for case in CASES])
def test_bcftools_family_metadata_and_outputs(
    registry: NodeRegistry,
    node_id: str,
    _: dict[str, object],
    __: list[str],
    tmp_path: Path,
) -> None:
    node_class = registry.get(node_id)
    assert node_class.VERSION == "1.24"
    assert node_class.GIT_COMMIT == "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    if node_id == "bcftools_cnv":
        assert node_class.REQUIRED_EXECUTABLES == ["bcftools", "python"]
        assert node_class.REQUIRED_CONDA_PACKAGES == [
            "bcftools",
            "htslib",
            "python",
            "numpy",
            "matplotlib",
        ]
    else:
        assert node_class.REQUIRED_EXECUTABLES == ["bcftools"]
        assert node_class.REQUIRED_CONDA_PACKAGES == ["bcftools", "htslib"]
    if node_id in CORE_NODE_IDS:
        assert node_class.SOURCE_REVISION == node_class.GIT_COMMIT
        assert node_class.UPSTREAM_SOURCE
        assert node_class.UPSTREAM_SOURCE in node_class.SOURCE_PATHS
        assert node_class.UPSTREAM_DOC in node_class.SOURCE_PATHS
        assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
        assert node_class.EXECUTION_EVIDENCE == "not-run"
    assert node_class.DOCUMENTATION_URL.startswith("https://")
    assert node_class.SHELL is False
    outputs = node_class.PLAN_OUTPUTS({}, tmp_path)
    assert outputs
    assert outputs[0].parent == tmp_path / node_id or outputs[0].parent.parent == tmp_path / node_id


def test_bcftools_registry_moves_exactly_the_wrapped_family_ids(registry: NodeRegistry) -> None:
    expected = {case[0] for case in CASES}
    assert len(expected) == 32
    assert expected.issubset(registry.all())
    for node_id in expected:
        assert registry.get(node_id).__module__.startswith("bionodulo.nodes.builtin.bcftools_family")
    assert not {
        node_id
        for node_id, node_class in registry.all().items()
        if node_id.startswith("bcftools_") and node_class.__module__.endswith("wrapped_bcftools")
    }


@pytest.mark.parametrize(
    "node_id,inputs",
    [
        ("bcftools_mpileup", {"input_bams": ["a.bam"], "reference": "ref.fa"}),
        ("bcftools_mpileup", {"input_bams": ["a.bam"], "no_reference": True, "regions": "chr1"}),
        ("bcftools_norm", {"input_file": "in.vcf", "reference": "ref.fa"}),
        ("bcftools_merge", {"input_files": ["a.vcf.gz", "b.vcf.gz"]}),
        ("bcftools_isec", {"input_files": ["a.vcf.gz", "b.vcf.gz"], "input_indexes": ["wrong.tbi"]}),
        ("bcftools_consensus", {"input_file": "in.vcf.gz", "input_index": "wrong.tbi", "reference": "ref.fa"}),
        ("bcftools_view", {"input_file": "in.bcf", "input_index": "in.bcf.tbi", "regions": "chr1"}),
        ("bcftools_plugin_frameshifts", {"input_file": "in.vcf", "exons": "exons.bed.gz", "exons_index": "wrong.tbi"}),
    ],
)
def test_bcftools_random_access_contracts_fail_closed(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
) -> None:
    assert registry.get(node_id).VALIDATE_INPUTS(inputs) is not True


def test_bcftools_filter_preserves_official_template_expr_alias(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_filter")
    command = node_class.render_command({"vcf": "in.vcf", "expr": "QUAL>=20", "output": OUTPUT, "threads": 0})
    assert command == [
        "bcftools",
        "filter",
        "--include",
        "QUAL>=20",
        "-Oz",
        "-o",
        f"{OUTPUT}/filtered.vcf.gz",
        "in.vcf",
    ]


def test_bcftools_filter_requires_soft_filter_for_mask_modes(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_filter")
    assert "soft_filter" in str(node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "mask": "chr1:1-10"}))
    assert (
        node_class.VALIDATE_INPUTS(
            {
                "input_file": "in.vcf",
                "mask": "chr1:1-10",
                "soft_filter": "Masked",
            }
        )
        is True
    )


@pytest.mark.parametrize(
    "value",
    ["-1", "3:bad", "3:indel,bad", "3:"],
)
def test_bcftools_filter_rejects_source_invalid_snp_gap_syntax(
    registry: NodeRegistry,
    value: str,
) -> None:
    node_class = registry.get("bcftools_filter")
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "snp_gap": value}) is not True


def test_bcftools_filter_accepts_documented_unbounded_threads_and_gap_types(
    registry: NodeRegistry,
) -> None:
    node_class = registry.get("bcftools_filter")
    inputs = {
        "input_file": "in.vcf",
        "threads": 256,
        "snp_gap": "3:indel,mnp,bnd,other,overlap",
        "soft_filter": "Gap",
        "mask_file": "regions.bed",
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command({**inputs, "output": OUTPUT})[:4] == [
        "bcftools",
        "filter",
        "--soft-filter",
        "Gap",
    ]


@pytest.mark.parametrize("target", ["r:0", "r:1", ".,r:0.5"])
def test_bcftools_setgt_rejects_source_invalid_target_syntax(
    registry: NodeRegistry,
    target: str,
) -> None:
    node_class = registry.get("bcftools_plugin_setgt")
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "target_gt": target}) is not True


def test_bcftools_stdout_and_dynamic_output_modes(registry: NodeRegistry) -> None:
    stdout_nodes = {
        "bcftools_stats",
        "bcftools_consensus",
        "bcftools_plugin_counts",
        "bcftools_plugin_dosage",
    }
    directory_nodes = {"bcftools_cnv", "bcftools_convert_from_vcf"}
    for node_id, _, _ in CASES:
        node_class = registry.get(node_id)
        assert (node_class.STDOUT_OUTPUT_INDEX == 0) is (node_id in stdout_nodes)
        if node_id in directory_nodes:
            assert node_class.RETURN_TYPES == ("DIRECTORY",)


@pytest.mark.parametrize(
    "node_id,inputs",
    [
        ("bcftools_call", {"input_file": "in.vcf", "regions": "chr1", "regions_file": "regions.txt"}),
        ("bcftools_view", {"input_file": "in.vcf", "targets": "chr1", "targets_file": "targets.txt"}),
        ("bcftools_stats", {"input_file": "in.vcf", "samples": "S1", "samples_file": "samples.txt"}),
        ("bcftools_filter", {"input_file": "in.vcf", "threads": -1}),
        ("bcftools_filter", {"input_file": "in.vcf", "regions_overlap": "bad"}),
    ],
)
def test_bcftools_common_parser_invariants_fail_closed(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
) -> None:
    assert registry.get(node_id).VALIDATE_INPUTS(inputs) is not True


def test_bcftools_mpileup_zero_depth_means_unlimited(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_mpileup")
    inputs = {"input_bams": ["a.bam"], "no_reference": True, "max_depth": 0, "threads": 0}
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command({**inputs, "output": OUTPUT}) == [
        "bcftools",
        "mpileup",
        "--no-reference",
        "--max-depth",
        "0",
        "-Oz",
        "-o",
        f"{OUTPUT}/mpileup.vcf.gz",
        "a.bam",
    ]


@pytest.mark.parametrize(
    "extra",
    [
        {"constrain": "trio"},
        {"constrain": "alleles"},
        {"constrain": "alleles", "caller": "consensus", "targets": "chr1"},
        {"insert_missed": True},
        {"gvcf": ["5"], "variants_only": True},
        {"caller": "consensus", "group_samples": "groups.tsv"},
        {"group_samples_tag": "AD"},
        {"caller": "consensus", "prior_freqs": "AN,AC"},
        {"caller": "consensus", "prior": 0.001},
        {"pval_threshold": 0.5},
        {"novel_rate": "1e-8"},
        {"ploidy": "GRCh38", "ploidy_file": "ploidy.tsv"},
    ],
)
def test_bcftools_call_rejects_source_invalid_or_nonfunctional_modes(
    registry: NodeRegistry,
    extra: dict[str, object],
) -> None:
    assert registry.get("bcftools_call").VALIDATE_INPUTS({"input_file": "in.vcf", **extra}) is not True


def test_bcftools_call_accepts_allele_constraint_with_targets(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_call")
    inputs = {
        "input_file": "in.vcf",
        "constrain": "alleles",
        "targets_file": "alleles.tsv.gz",
        "insert_missed": True,
        "threads": 0,
        "output": OUTPUT,
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "call",
        "-m",
        "--constrain",
        "alleles",
        "--targets-file",
        "alleles.tsv.gz",
        "--insert-missed",
        "-Oz",
        "-o",
        f"{OUTPUT}/called.vcf.gz",
        "in.vcf",
    ]


def test_bcftools_filter_accepts_combined_append_reset_mode(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_filter")
    inputs = {"input_file": "in.vcf", "mode": "+x", "threads": 0, "output": OUTPUT}
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs)[2:4] == ["--mode", "+x"]


@pytest.mark.parametrize(
    "inputs",
    [
        {"input_file": "in.vcf"},
        {"input_file": "in.vcf", "atom_overlaps": ".", "rm_dup": "exact"},
        {"input_file": "in.vcf", "multi_overlaps": ".", "atomize": True},
        {"input_file": "in.vcf", "strict_filter": True, "multiallelics": "-both"},
    ],
)
def test_bcftools_norm_rejects_missing_or_mismatched_operations(
    registry: NodeRegistry,
    inputs: dict[str, object],
) -> None:
    assert registry.get("bcftools_norm").VALIDATE_INPUTS(inputs) is not True


def test_bcftools_norm_accepts_unbounded_nonnegative_threads(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_norm")
    inputs = {"input_file": "in.vcf", "atomize": True, "threads": 256}
    assert node_class.VALIDATE_INPUTS(inputs) is True


@pytest.mark.parametrize(
    "extra",
    [
        {"ligate_force": True},
        {"ligate_warn": True},
        {"naive": True, "naive_force": True},
        {"allow_overlaps": True, "rm_duplicates": True, "rm_dups": "exact"},
        {"ligate": True, "ligate_force": True, "ligate_warn": True},
    ],
)
def test_bcftools_concat_rejects_silent_or_conflicting_modes(
    registry: NodeRegistry,
    extra: dict[str, object],
) -> None:
    inputs = {"input_files": ["a.vcf", "b.vcf"], **extra}
    assert registry.get("bcftools_concat").VALIDATE_INPUTS(inputs) is not True


def test_bcftools_merge_force_single_allows_one_indexed_input(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_merge")
    inputs = {
        "input_files": ["a.vcf.gz"],
        "input_indexes": ["a.vcf.gz.tbi"],
        "force_single": True,
        "threads": 0,
        "output": OUTPUT,
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "merge",
        "--force-single",
        "-Oz",
        "-o",
        f"{OUTPUT}/merged.vcf.gz",
        "a.vcf.gz",
    ]
    assert node_class.VALIDATE_INPUTS({"input_files": ["a.vcf"], "no_index": True}) is not True


def test_bcftools_consensus_binds_each_replacement_to_its_mask(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_consensus")
    inputs = {
        "input_file": "in.vcf.gz",
        "input_index": "in.vcf.gz.tbi",
        "reference": "ref.fa",
        "iupac_codes": False,
        "masks": ["first.bed", "second.bed"],
        "mask_with": ["lc", "?"],
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "consensus",
        "--fasta-ref",
        "ref.fa",
        "--mask",
        "first.bed",
        "--mask-with",
        "lc",
        "--mask",
        "second.bed",
        "--mask-with",
        "?",
        "in.vcf.gz",
    ]
    assert node_class.VALIDATE_INPUTS({**inputs, "haplotype": "1"}) is True


@pytest.mark.parametrize(
    "extra",
    [
        {"mask_with": ["N"]},
        {"masks": ["a.bed", "b.bed"], "mask_with": ["N", "lc", "uc"]},
        {"masks": ["a.bed"], "mask_with": ["many"]},
        {"absent": "NA"},
        {"mark_ins": "upper"},
        {"mark_snv": "\n"},
    ],
)
def test_bcftools_consensus_rejects_source_invalid_marking_options(
    registry: NodeRegistry,
    extra: dict[str, object],
) -> None:
    inputs = {
        "input_file": "in.vcf.gz",
        "input_index": "in.vcf.gz.tbi",
        "reference": "ref.fa",
        **extra,
    }
    assert registry.get("bcftools_consensus").VALIDATE_INPUTS(inputs) is not True


@pytest.mark.parametrize(
    "extra",
    [
        {"samples": "S1"},
        {"use": "GT,DP"},
        {"use": "GT,PL,GT"},
        {"use": "GT,PL"},
        {"pairs": "A,B,C"},
        {"homs_only": True},
        {"samples": "gt:G"},
        {"samples_file": "list.txt"},
        {"samples_file": "gt:list.txt", "samples_file_source": "gt"},
        {"samples_file_source": "qry"},
    ],
)
def test_bcftools_gtcheck_rejects_invalid_selectors_and_modes(
    registry: NodeRegistry,
    extra: dict[str, object],
) -> None:
    assert registry.get("bcftools_gtcheck").VALIDATE_INPUTS({"input_file": "in.vcf", **extra}) is not True


def test_bcftools_gtcheck_accepts_distinct_prefixed_selectors(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_gtcheck")
    inputs = {
        "input_file": "in.vcf.gz",
        "input_index": "in.vcf.gz.tbi",
        "genotypes": "reference.vcf.gz",
        "genotypes_index": "reference.vcf.gz.tbi",
        "samples": "qry:A",
        "samples_file": "list.txt",
        "samples_file_source": "gt",
        "use": "GT,PL",
        "output": OUTPUT,
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "gtcheck",
        "--genotypes",
        "reference.vcf.gz",
        "--samples",
        "qry:A",
        "--samples-file",
        "gt:list.txt",
        "--use",
        "GT,PL",
        "-o",
        f"{OUTPUT}/gtcheck.tsv",
        "in.vcf.gz",
    ]


def test_bcftools_roh_af_fallback_and_plain_output_contract(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_roh")
    valid = {"input_file": "in.vcf", "af_default": 0.1, "af_tag": "AF"}
    assert node_class.VALIDATE_INPUTS(valid) is True
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "af_tag": "AF", "estimate_af": "-"}) is not True
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "af_file": "af.tsv", "targets": "chr1"}) is not True
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "output_type": "rz"}) is not True
    rendered = node_class.render_command({"input_file": "in.vcf", "output_type": "sr", "threads": 8, "output": OUTPUT})
    assert rendered[-6:] == ["--threads", "8", "-Osr", "-o", f"{OUTPUT}/roh.tsv", "in.vcf"]


@pytest.mark.parametrize(
    "inputs",
    [
        {"mode": "gen_sample", "input_file": "in.gen", "sample_file": "in.samples", "sex_file": "sex.tsv"},
        {"mode": "gen_sample", "input_file": "in.gen", "sample_file": "in.samples", "haploid2diploid": True},
        {"mode": "hap_sample", "input_file": "in.hap", "sample_file": "in.samples", "convert_3n6": True},
        {
            "mode": "hap_legend_sample",
            "input_file": "in.hap",
            "legend_file": "in.legend",
            "sample_file": "in.samples",
            "vcf_ids": True,
        },
    ],
)
def test_bcftools_convert_to_vcf_rejects_noop_or_unsupported_flags(
    registry: NodeRegistry,
    inputs: dict[str, object],
) -> None:
    assert registry.get("bcftools_convert_to_vcf").VALIDATE_INPUTS(inputs) is not True


def test_bcftools_convert_to_vcf_renders_gen_format_controls(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_convert_to_vcf")
    inputs = {
        "mode": "gen_sample",
        "input_file": "in.gen",
        "sample_file": "in.samples",
        "convert_3n6": True,
        "vcf_ids": True,
        "threads": 0,
        "output": OUTPUT,
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "convert",
        "--gensample2vcf",
        "in.gen,in.samples",
        "--3N6",
        "--vcf-ids",
        "-Oz",
        "-o",
        f"{OUTPUT}/converted.vcf.gz",
    ]


def test_bcftools_convert_from_vcf_restores_documented_controls(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_convert_from_vcf")
    inputs = {
        "input_file": "in.vcf",
        "convert_to": "gen_sample",
        "tag": "GP",
        "convert_3n6": True,
        "vcf_ids": True,
        "sex_file": "sex.tsv",
        "keep_duplicates": True,
        "include": "QUAL>20",
        "targets": "chr1",
        "samples": "S1",
        "threads": 0,
        "output": OUTPUT,
    }
    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = node_class.render_command(inputs)
    assert command[:4] == [
        "bcftools",
        "convert",
        "--gensample",
        f"{OUTPUT}/results/converted.gen,{OUTPUT}/results/converted.samples",
    ]
    assert command[4:] == [
        "--tag",
        "GP",
        "--3N6",
        "--vcf-ids",
        "--sex",
        "sex.tsv",
        "--keep-duplicates",
        "--include",
        "QUAL>20",
        "--samples",
        "S1",
        "--targets",
        "chr1",
        "in.vcf",
    ]


@pytest.mark.parametrize(
    "extra",
    [
        {"tag": "GL"},
        {"haploid2diploid": True},
        {"convert_to": "hap_sample", "tag": "GT"},
        {"convert_to": "hap_legend_sample", "keep_duplicates": True},
    ],
)
def test_bcftools_convert_from_vcf_rejects_mode_specific_noops(
    registry: NodeRegistry,
    extra: dict[str, object],
) -> None:
    assert registry.get("bcftools_convert_from_vcf").VALIDATE_INPUTS({"input_file": "in.vcf", **extra}) is not True


def test_bcftools_cnv_allows_source_default_single_sample(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_cnv")
    inputs = {"input_file": "in.vcf", "output": OUTPUT}
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == [
        "bcftools",
        "cnv",
        "--output-dir",
        f"{OUTPUT}/results",
        "in.vcf",
    ]
    assert node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "control_sample": "control"}) is not True


def test_bcftools_csq_enforces_trim_bound_and_renders_threads(registry: NodeRegistry) -> None:
    node_class = registry.get("bcftools_csq")
    base = {
        "input_file": "in.vcf",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "gff_annot": "genes.gff3",
    }
    assert node_class.VALIDATE_INPUTS({**base, "trim_protein_seq": 0}) is not True
    command = node_class.render_command({**base, "threads": 6, "output": OUTPUT})
    assert command[-6:] == [
        "--threads",
        "6",
        "-Oz",
        "-o",
        f"{OUTPUT}/csq.vcf.gz",
        "in.vcf",
    ]
