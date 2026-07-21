"""Focused source-contract tests for the GATK 4.6.2.0 family."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.variant_family.gatk_adapter import (
    GATKCommandNode,
    validate_gatk_bam_index,
    validate_gatk_variant_index,
)
from bionodulo.nodes.builtin.variant_family.gatk_apply_bqsr import GatkApplyBQSRNode
from bionodulo.nodes.builtin.variant_family.gatk_base_recalibrator import (
    GatkBaseRecalibratorNode,
)
from bionodulo.nodes.builtin.variant_family.gatk_genotype_gvcfs import (
    GatkGenotypeGVCFsNode,
)
from bionodulo.nodes.builtin.variant_family.gatk_haplotype_caller import (
    GatkHaplotypeCallerNode,
)
from bionodulo.nodes.builtin.variant_family.mutect2 import Mutect2Node


GATK_COMMIT = "76edc75c26504da94bbaee66584e107e76ee15de"

NODES = {
    "gatk_haplotype_caller": GatkHaplotypeCallerNode,
    "gatk_genotype_gvcfs": GatkGenotypeGVCFsNode,
    "gatk_base_recalibrator": GatkBaseRecalibratorNode,
    "gatk_apply_bqsr": GatkApplyBQSRNode,
    "mutect2": Mutect2Node,
}

SOURCE_FILES = {
    "gatk_haplotype_caller": (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/"
        "haplotypecaller/HaplotypeCaller.java"
    ),
    "gatk_genotype_gvcfs": (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/GenotypeGVCFs.java"
    ),
    "gatk_base_recalibrator": (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/bqsr/BaseRecalibrator.java"
    ),
    "gatk_apply_bqsr": (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/bqsr/ApplyBQSR.java"
    ),
    "mutect2": "src/main/java/org/broadinstitute/hellbender/tools/walkers/mutect/Mutect2.java",
}

OUTPUT_CONTRACTS = {
    "gatk_haplotype_caller": (
        ("VCF_GZ", "VCF_INDEX"),
        ("vcf", "vcf_index"),
        ("calls.vcf.gz", "calls.vcf.gz.tbi"),
    ),
    "gatk_genotype_gvcfs": (
        ("VCF_GZ", "VCF_INDEX"),
        ("vcf", "vcf_index"),
        ("genotyped.vcf.gz", "genotyped.vcf.gz.tbi"),
    ),
    "gatk_base_recalibrator": (
        ("TABLE",),
        ("recal_table",),
        ("recalibration.table",),
    ),
    "gatk_apply_bqsr": (
        ("BAM", "BAI"),
        ("bam", "bam_index"),
        ("recalibrated.bam", "recalibrated.bai"),
    ),
    "mutect2": (
        ("VCF_GZ", "VCF_INDEX", "STATS_FILE"),
        ("vcf", "vcf_index", "stats"),
        ("unfiltered.vcf.gz", "unfiltered.vcf.gz.tbi", "unfiltered.vcf.gz.stats"),
    ),
}

EXPECTED_PORTS = {
    "gatk_haplotype_caller": {
        "required": {
            "bam",
            "bam_index",
            "reference",
            "reference_index",
            "sequence_dictionary",
            "threads",
        },
        "optional": {
            "emit_ref_confidence",
            "dbsnp",
            "dbsnp_index",
            "stand_call_conf",
            "min_base_quality",
            "sample_ploidy",
            "intervals",
        },
    },
    "gatk_genotype_gvcfs": {
        "required": {
            "gvcf",
            "gvcf_index",
            "reference",
            "reference_index",
            "sequence_dictionary",
        },
        "optional": {
            "gvcfs",
            "intervals",
            "dbsnp",
            "dbsnp_index",
            "standard_min_confidence",
        },
    },
    "gatk_base_recalibrator": {
        "required": {
            "bam",
            "bam_index",
            "reference",
            "reference_index",
            "sequence_dictionary",
            "known_sites",
            "known_sites_indexes",
        },
        "optional": set(),
    },
    "gatk_apply_bqsr": {
        "required": {
            "bam",
            "bam_index",
            "reference",
            "reference_index",
            "sequence_dictionary",
            "recal_table",
        },
        "optional": set(),
    },
    "mutect2": {
        "required": {
            "tumor_bam",
            "tumor_bam_index",
            "reference",
            "reference_index",
            "sequence_dictionary",
        },
        "optional": {
            "normal_bam",
            "normal_bam_index",
            "tumor_sample",
            "normal_sample",
            "germline_resource",
            "germline_resource_index",
            "panel_of_normals",
            "panel_of_normals_index",
            "intervals",
        },
    },
}


def _reference_inputs(root: Path) -> dict[str, Path]:
    reference = root / "reference.fa"
    return {
        "reference": reference,
        "reference_index": Path(f"{reference}.fai"),
        "sequence_dictionary": reference.with_suffix(".dict"),
    }


def _valid_inputs(node_id: str, root: Path) -> dict[str, Any]:
    inputs: dict[str, Any] = _reference_inputs(root)
    bam = root / "sample.bam"
    if node_id == "gatk_haplotype_caller":
        inputs.update({"bam": bam, "bam_index": bam.with_suffix(".bai"), "threads": 4})
    elif node_id == "gatk_genotype_gvcfs":
        gvcf = root / "sample.g.vcf.gz"
        inputs.update({"gvcf": gvcf, "gvcf_index": Path(f"{gvcf}.tbi")})
    elif node_id == "gatk_base_recalibrator":
        known_vcf = root / "known.vcf.gz"
        inputs.update(
            {
                "bam": bam,
                "bam_index": Path(f"{bam}.bai"),
                "known_sites": [known_vcf],
                "known_sites_indexes": [Path(f"{known_vcf}.tbi")],
            }
        )
    elif node_id == "gatk_apply_bqsr":
        inputs.update(
            {
                "bam": bam,
                "bam_index": bam.with_suffix(".bai"),
                "recal_table": root / "recalibration.table",
            }
        )
    elif node_id == "mutect2":
        inputs.update(
            {
                "tumor_bam": bam,
                "tumor_bam_index": Path(f"{bam}.bai"),
            }
        )
    else:  # pragma: no cover - guarded by the fixed test table
        raise AssertionError(node_id)
    return inputs


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_metadata_and_pinned_source_are_exact(node_id: str) -> None:
    node = NODES[node_id]

    assert node.__bases__ == (GATKCommandNode,)
    assert node.NODE_ID == node_id
    assert node.CATEGORY == "variant"
    assert node.VERSION == "4.6.2.0"
    assert node.GIT_URL == "https://github.com/broadinstitute/gatk.git"
    assert node.GIT_COMMIT == GATK_COMMIT
    assert node.REQUIRED_EXECUTABLES == ["gatk"]
    assert node.REQUIRED_CONDA_PACKAGES == ["gatk4"]
    assert node.SHELL is False
    assert node.UPSTREAM_SOURCE == SOURCE_FILES[node_id]


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_input_port_sets_are_exact(node_id: str) -> None:
    input_types = NODES[node_id].INPUT_TYPES()

    assert set(input_types) == {"required", "optional", "hidden"}
    assert set(input_types["required"]) == EXPECTED_PORTS[node_id]["required"]
    assert set(input_types["optional"]) == EXPECTED_PORTS[node_id]["optional"]
    assert input_types["hidden"] == {"output": ("STRING", {})}


def test_source_defaults_are_exposed_exactly() -> None:
    haplotype_inputs = GatkHaplotypeCallerNode.INPUT_TYPES()
    genotype_inputs = GatkGenotypeGVCFsNode.INPUT_TYPES()

    assert haplotype_inputs["required"]["threads"][1]["default"] == 4
    assert haplotype_inputs["optional"]["emit_ref_confidence"][1]["default"] == "NONE"
    assert haplotype_inputs["optional"]["stand_call_conf"][1]["default"] == 30.0
    assert haplotype_inputs["optional"]["min_base_quality"][1]["default"] == 10
    assert haplotype_inputs["optional"]["sample_ploidy"][1]["default"] == 2
    assert genotype_inputs["optional"]["standard_min_confidence"][1]["default"] == 30.0
    assert "max" not in haplotype_inputs["required"]["threads"][1]


def test_haplotype_caller_accepts_source_supported_thread_counts(tmp_path: Path) -> None:
    inputs = _valid_inputs("gatk_haplotype_caller", tmp_path)
    inputs["threads"] = 128
    assert GatkHaplotypeCallerNode.VALIDATE_INPUTS(inputs) is True


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_output_contracts_and_fixed_paths_are_exact(node_id: str, tmp_path: Path) -> None:
    node = NODES[node_id]
    return_types, return_names, filenames = OUTPUT_CONTRACTS[node_id]

    assert node.RETURN_TYPES == return_types
    assert node.RETURN_NAMES == return_names
    assert node.OUTPUT_FILENAMES == filenames
    assert node.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / node_id / filename for filename in filenames
    ]


def test_default_argv_is_exact() -> None:
    root = Path("/data")
    reference = root / "reference.fa"
    bam = root / "sample.bam"
    output_root = Path("/work")
    known_gz = root / "dbsnp.vcf.gz"
    known_vcf = root / "mills.vcf"

    cases = {
        "gatk_haplotype_caller": [
            "gatk",
            "HaplotypeCaller",
            "-R",
            str(reference),
            "-I",
            str(bam),
            "-O",
            str(output_root / "calls.vcf.gz"),
            "--create-output-variant-index",
            "true",
            "--native-pair-hmm-threads",
            "4",
            "--emit-ref-confidence",
            "NONE",
            "--standard-min-confidence-threshold-for-calling",
            "30.0",
            "--min-base-quality-score",
            "10",
            "--sample-ploidy",
            "2",
        ],
        "gatk_genotype_gvcfs": [
            "gatk",
            "GenotypeGVCFs",
            "-R",
            str(reference),
            "-V",
            str(root / "sample.g.vcf.gz"),
            "-O",
            str(output_root / "genotyped.vcf.gz"),
            "--create-output-variant-index",
            "true",
            "--standard-min-confidence-threshold-for-calling",
            "30.0",
        ],
        "gatk_base_recalibrator": [
            "gatk",
            "BaseRecalibrator",
            "-R",
            str(reference),
            "-I",
            str(bam),
            "--known-sites",
            str(known_gz),
            "--known-sites",
            str(known_vcf),
            "-O",
            str(output_root / "recalibration.table"),
        ],
        "gatk_apply_bqsr": [
            "gatk",
            "ApplyBQSR",
            "-R",
            str(reference),
            "-I",
            str(bam),
            "--bqsr-recal-file",
            str(root / "recalibration.table"),
            "-O",
            str(output_root / "recalibrated.bam"),
            "--create-output-bam-index",
            "true",
        ],
        "mutect2": [
            "gatk",
            "Mutect2",
            "-R",
            str(reference),
            "-I",
            str(bam),
            "-O",
            str(output_root / "unfiltered.vcf.gz"),
            "--create-output-variant-index",
            "true",
        ],
    }

    inputs_by_node = {
        node_id: {**_valid_inputs(node_id, root), "output": str(output_root)}
        for node_id in NODES
    }
    inputs_by_node["gatk_base_recalibrator"].update(
        {
            "known_sites": [known_gz, known_vcf],
            "known_sites_indexes": [Path(f"{known_gz}.tbi"), Path(f"{known_vcf}.idx")],
        }
    )

    for node_id, expected in cases.items():
        command = NODES[node_id].render_command(inputs_by_node[node_id])
        assert command == expected
        assert not {">", ">>", "|", "&&", ";"}.intersection(command)
        for key, value in inputs_by_node[node_id].items():
            if "index" in key and value is not None:
                values = value if isinstance(value, list) else [value]
                assert all(str(item) not in command for item in values)


def test_haplotypecaller_renders_optional_source_arguments() -> None:
    inputs = _valid_inputs("gatk_haplotype_caller", Path("/data"))
    inputs.update(
        {
            "output": "/work",
            "threads": 8,
            "emit_ref_confidence": "GVCF",
            "stand_call_conf": 12.5,
            "min_base_quality": 6,
            "sample_ploidy": 4,
            "dbsnp": "/data/dbsnp.vcf.gz",
            "dbsnp_index": "/data/dbsnp.vcf.gz.tbi",
            "intervals": "chr1:1-1000",
        }
    )

    assert GatkHaplotypeCallerNode.render_command(inputs)[-4:] == [
        "--dbsnp",
        "/data/dbsnp.vcf.gz",
        "-L",
        "chr1:1-1000",
    ]


def test_mutect2_renders_explicit_tumor_normal_and_resource_roles() -> None:
    inputs = _valid_inputs("mutect2", Path("/data"))
    inputs.update(
        {
            "output": "/work",
            "normal_bam": "/data/normal.bam",
            "normal_bam_index": "/data/normal.bai",
            "tumor_sample": "TUMOR",
            "normal_sample": "NORMAL",
            "germline_resource": "/data/gnomad.vcf.gz",
            "germline_resource_index": "/data/gnomad.vcf.gz.tbi",
            "panel_of_normals": "/data/pon.vcf.gz",
            "panel_of_normals_index": "/data/pon.vcf.gz.tbi",
            "intervals": "targets.interval_list",
        }
    )

    assert Mutect2Node.render_command(inputs) == [
        "gatk",
        "Mutect2",
        "-R",
        "/data/reference.fa",
        "-I",
        "/data/sample.bam",
        "-I",
        "/data/normal.bam",
        "--tumor-sample",
        "TUMOR",
        "--normal-sample",
        "NORMAL",
        "--germline-resource",
        "/data/gnomad.vcf.gz",
        "--panel-of-normals",
        "/data/pon.vcf.gz",
        "-L",
        "targets.interval_list",
        "-O",
        "/work/unfiltered.vcf.gz",
        "--create-output-variant-index",
        "true",
    ]


@pytest.mark.parametrize("suffix", ["stem", "appended"])
def test_gatk_bam_index_validator_accepts_both_htsjdk_names(
    suffix: str,
    tmp_path: Path,
) -> None:
    bam = tmp_path / "sample.bam"
    index = bam.with_suffix(".bai") if suffix == "stem" else Path(f"{bam}.bai")

    assert validate_gatk_bam_index({"bam": bam, "bam_index": index}) is True


def test_gatk_bam_index_validator_rejects_wrong_sibling(tmp_path: Path) -> None:
    bam = tmp_path / "sample.bam"
    result = validate_gatk_bam_index(
        {"bam": bam, "bam_index": tmp_path / "other.bai"}
    )

    assert result is not True
    assert str(bam.with_suffix(".bai")) in str(result)
    assert str(Path(f"{bam}.bai")) in str(result)


@pytest.mark.parametrize(
    ("variant_name", "index_name"),
    [("resource.vcf.gz", "resource.vcf.gz.tbi"), ("resource.vcf", "resource.vcf.idx")],
)
def test_gatk_variant_index_validator_accepts_exact_source_pair(
    variant_name: str,
    index_name: str,
    tmp_path: Path,
) -> None:
    assert validate_gatk_variant_index(
        {"variant": tmp_path / variant_name, "index": tmp_path / index_name},
        variant_key="variant",
        index_key="index",
    ) is True


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_all_nodes_reject_wrong_reference_sidecars(node_id: str, tmp_path: Path) -> None:
    inputs = _valid_inputs(node_id, tmp_path)
    inputs["reference_index"] = tmp_path / "wrong.fa.fai"

    result = NODES[node_id].VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "reference_index" in str(result)


@pytest.mark.parametrize(
    ("node_id", "bam_key", "index_key"),
    [
        ("gatk_haplotype_caller", "bam", "bam_index"),
        ("gatk_base_recalibrator", "bam", "bam_index"),
        ("gatk_apply_bqsr", "bam", "bam_index"),
        ("mutect2", "tumor_bam", "tumor_bam_index"),
    ],
)
def test_bam_nodes_accept_both_exact_index_forms(
    node_id: str,
    bam_key: str,
    index_key: str,
    tmp_path: Path,
) -> None:
    inputs = _valid_inputs(node_id, tmp_path)
    bam = Path(inputs[bam_key])

    inputs[index_key] = bam.with_suffix(".bai")
    assert NODES[node_id].VALIDATE_INPUTS(inputs) is True
    inputs[index_key] = Path(f"{bam}.bai")
    assert NODES[node_id].VALIDATE_INPUTS(inputs) is True
    inputs[index_key] = tmp_path / "wrong.bai"
    assert NODES[node_id].VALIDATE_INPUTS(inputs) is not True


def test_genotype_gvcfs_legacy_alias_is_single_input_only(tmp_path: Path) -> None:
    inputs = _valid_inputs("gatk_genotype_gvcfs", tmp_path)
    gvcf = inputs.pop("gvcf")
    inputs["gvcfs"] = [gvcf]
    inputs["output"] = str(tmp_path / "out")

    assert GatkGenotypeGVCFsNode.VALIDATE_INPUTS(inputs) is True
    command = GatkGenotypeGVCFsNode.render_command(inputs)
    assert command.count("-V") == 1
    assert command[command.index("-V") + 1] == str(gvcf)

    inputs["gvcfs"] = [gvcf, tmp_path / "second.g.vcf.gz"]
    result = GatkGenotypeGVCFsNode.VALIDATE_INPUTS(inputs)
    assert result is not True
    assert "does not accept multiple GVCFs" in str(result)


def test_genotype_gvcfs_rejects_conflicting_canonical_and_legacy_inputs(
    tmp_path: Path,
) -> None:
    inputs = _valid_inputs("gatk_genotype_gvcfs", tmp_path)
    inputs["gvcfs"] = [tmp_path / "other.g.vcf.gz"]

    result = GatkGenotypeGVCFsNode.VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "conflict" in str(result)


def test_base_recalibrator_requires_one_index_per_known_sites_input(tmp_path: Path) -> None:
    inputs = _valid_inputs("gatk_base_recalibrator", tmp_path)
    second = tmp_path / "second.vcf"
    inputs["known_sites"] = [inputs["known_sites"][0], second]

    result = GatkBaseRecalibratorNode.VALIDATE_INPUTS(inputs)
    assert result is not True
    assert "known_sites_indexes" in str(result)

    inputs["known_sites_indexes"] = [
        inputs["known_sites_indexes"][0],
        Path(f"{second}.idx"),
    ]
    assert GatkBaseRecalibratorNode.VALIDATE_INPUTS(inputs) is True


@pytest.mark.parametrize(
    ("resource_key", "index_key"),
    [
        ("dbsnp", "dbsnp_index"),
        ("germline_resource", "germline_resource_index"),
        ("panel_of_normals", "panel_of_normals_index"),
    ],
)
def test_optional_variant_resources_require_exact_paired_indexes(
    resource_key: str,
    index_key: str,
    tmp_path: Path,
) -> None:
    if resource_key == "dbsnp":
        node = GatkHaplotypeCallerNode
        inputs = _valid_inputs("gatk_haplotype_caller", tmp_path)
    else:
        node = Mutect2Node
        inputs = _valid_inputs("mutect2", tmp_path)
    resource = tmp_path / f"{resource_key}.vcf.gz"
    inputs[resource_key] = resource

    missing = node.VALIDATE_INPUTS(inputs)
    assert missing is not True
    assert index_key in str(missing)

    inputs[index_key] = Path(f"{resource}.tbi")
    assert node.VALIDATE_INPUTS(inputs) is True
    inputs[index_key] = tmp_path / "wrong.tbi"
    assert node.VALIDATE_INPUTS(inputs) is not True


def test_mutect2_requires_complete_normal_mode(tmp_path: Path) -> None:
    inputs = _valid_inputs("mutect2", tmp_path)
    normal_bam = tmp_path / "normal.bam"
    inputs["normal_bam"] = normal_bam

    missing_index = Mutect2Node.VALIDATE_INPUTS(inputs)
    assert missing_index is not True
    assert "normal_bam_index" in str(missing_index)

    inputs["normal_bam_index"] = normal_bam.with_suffix(".bai")
    missing_sample = Mutect2Node.VALIDATE_INPUTS(inputs)
    assert missing_sample is not True
    assert "normal_sample" in str(missing_sample)

    inputs["normal_sample"] = "NORMAL"
    assert Mutect2Node.VALIDATE_INPUTS(inputs) is True

    orphan = _valid_inputs("mutect2", tmp_path)
    orphan["normal_sample"] = "NORMAL"
    assert Mutect2Node.VALIDATE_INPUTS(orphan) is not True


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("threads", True),
        ("threads", 0),
        ("emit_ref_confidence", "INVALID"),
        ("stand_call_conf", -1.0),
        ("min_base_quality", 128),
        ("sample_ploidy", 0),
    ],
)
def test_haplotypecaller_numeric_and_choice_validation_fail_closed(
    key: str,
    value: Any,
    tmp_path: Path,
) -> None:
    inputs = _valid_inputs("gatk_haplotype_caller", tmp_path)
    inputs[key] = value

    assert GatkHaplotypeCallerNode.VALIDATE_INPUTS(inputs) is not True
    with pytest.raises(ValueError):
        GatkHaplotypeCallerNode.render_command(inputs)


@pytest.mark.asyncio
async def test_apply_bqsr_fake_execution_models_source_generated_bai(tmp_path: Path) -> None:
    inputs = _valid_inputs("gatk_apply_bqsr", tmp_path)
    output_root = tmp_path / "outputs"

    class Context:
        node_dir = output_root

        async def run_command(
            self,
            command: str | list[str],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            assert isinstance(command, list)
            output_bam = Path(command[command.index("-O") + 1])
            output_bam.write_bytes(b"BAM")
            output_bam.with_suffix(".bai").write_bytes(b"BAI")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await GatkApplyBQSRNode().run(**inputs, context=Context())

    assert result == (
        str(output_root / "gatk_apply_bqsr" / "recalibrated.bam"),
        str(output_root / "gatk_apply_bqsr" / "recalibrated.bai"),
    )
