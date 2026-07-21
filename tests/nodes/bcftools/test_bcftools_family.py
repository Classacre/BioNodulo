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
        {"input_file": "in.vcf"},
        ["bcftools", "norm", "--sort", "pos", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/normalized.vcf.gz", "in.vcf"],
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
        ["bcftools", "isec", "--nfiles", "=2", "--write", "1", "--collapse", "none", "-Oz", "-o", f"{OUTPUT}/isec.vcf.gz", "a.vcf.gz", "b.vcf.gz"],
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
        ["bcftools", "convert", "--gensample2vcf", "in.gen,in.samples", "--threads", "4", "-Oz", "-o", f"{OUTPUT}/converted.vcf.gz"],
    ),
    (
        "bcftools_convert_from_vcf",
        {"input_file": "in.vcf"},
        ["bcftools", "convert", "--gensample", f"{OUTPUT}/results/converted.gen,{OUTPUT}/results/converted.samples", "--threads", "4", "in.vcf"],
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
        ["bcftools", "+fixploidy", "-Oz", "-o", f"{OUTPUT}/fixploidy.vcf.gz", "in.vcf", "--", "--default-ploidy", "2", "--tags", "GT"],
    ),
    (
        "bcftools_plugin_mendelian",
        {"input_file": "in.vcf", "child": "C", "father": "F", "mother": "M"},
        ["bcftools", "+mendelian2", "-Oz", "-o", f"{OUTPUT}/mendelian.vcf.gz", "in.vcf", "--", "--mode", "a", "--pfm", "2X:C,F,M", "--rules", "GRCh37"],
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
        ["bcftools", "+frameshifts", "-Oz", "-o", f"{OUTPUT}/frameshifts.vcf.gz", "in.vcf", "--", "--exons", "exons.bed.gz"],
    ),
    (
        "bcftools_plugin_split_vep",
        {"input_file": "in.vcf", "columns": "Consequence"},
        ["bcftools", "+split-vep", "--columns", "Consequence", "-Oz", "-o", f"{OUTPUT}/split_vep.vcf.gz", "in.vcf"],
    ),
]


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
    assert node_class.REQUIRED_EXECUTABLES == ["bcftools"]
    assert node_class.REQUIRED_CONDA_PACKAGES == ["bcftools", "htslib"]
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
    assert "soft_filter" in str(
        node_class.VALIDATE_INPUTS({"input_file": "in.vcf", "mask": "chr1:1-10"})
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "in.vcf",
            "mask": "chr1:1-10",
            "soft_filter": "Masked",
        }
    ) is True


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
