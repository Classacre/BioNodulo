from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.bcftools_family.filter_vcf import FilterVCFNode
from bionodulo.nodes.registry import _to_frontend_input_spec


def test_filter_vcf_is_pinned_and_returns_an_indexed_vcf_pair() -> None:
    assert FilterVCFNode.VERSION == "1.24"
    assert FilterVCFNode.GIT_COMMIT == "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    assert FilterVCFNode.RETURN_TYPES == ("VCF_GZ", "VCF_INDEX")
    assert FilterVCFNode.RETURN_NAMES == ("filtered_vcf", "filtered_vcf_index")
    assert FilterVCFNode.REQUIRED_EXECUTABLES == ["bcftools"]
    assert FilterVCFNode.PACKAGE_CONSTRAINTS == ("bcftools==1.24",)
    assert FilterVCFNode.DOCUMENTATION_SOURCE_SHA256 == (
        "378bcf1f2faa5cef1f776c8cdcfdf096ad4b977a9e9d811a9c74d4d5830af0f7"
    )
    assert FilterVCFNode.UPSTREAM_SOURCE_SHA256 == (
        "0834e06b0a6338e36b21f105b1a49c5f337c8f4dc358abe68cf6b59026f16412"
    )
    assert FilterVCFNode.SHELL is False

    socket_type, _ = _to_frontend_input_spec(FilterVCFNode.INPUT_TYPES()["required"]["vcf"])
    assert socket_type == "VCF|VCF_GZ|BCF"


def test_filter_vcf_renders_one_native_bcftools_view_command(tmp_path: Path) -> None:
    command = FilterVCFNode.render_command(
        {
            "vcf": "cohort.vcf.gz",
            "regions": "chr1:100-200,chr2:500-900",
            "samples": "S1,S2",
            "min_qual": 30.0,
            "min_dp": 10,
            "pass_only": True,
            "biallelic_only": True,
            "snp_only": True,
            "threads": 4,
            "output": tmp_path / "filter_vcf",
        }
    )
    assert command == [
        "bcftools",
        "view",
        "--threads",
        "4",
        "--regions",
        "chr1:100-200,chr2:500-900",
        "--samples",
        "S1,S2",
        "--min-alleles",
        "2",
        "--max-alleles",
        "2",
        "--types",
        "snps",
        "--include",
        'QUAL >= 30.0 && INFO/DP >= 10 && FILTER == "PASS"',
        "-Oz",
        "--write-index=csi",
        "-o",
        str(tmp_path / "filter_vcf" / "filtered_vcf.vcf.gz"),
        "cohort.vcf.gz",
    ]
    assert command.count("bcftools") == 1
    assert not {"|", ">", "&&"}.intersection(command)


def test_filter_vcf_groups_custom_expressions_and_preserves_explicit_zero_maxima() -> None:
    inputs = {
        "vcf": "cohort.vcf.gz",
        "min_qual": 30.0,
        "max_dp": 0,
        "max_af": 0.0,
        "custom_filter": 'TYPE="snp" || TYPE="indel"',
    }
    assert FilterVCFNode.VALIDATE_INPUTS(inputs) is True
    assert FilterVCFNode._filter_expression(inputs) == (
        'QUAL >= 30.0 && INFO/DP <= 0 && (TYPE="snp" || TYPE="indel")'
    )
    command = FilterVCFNode.render_command({**inputs, "output": "/tmp/out"})
    assert command[command.index("--max-af") : command.index("--max-af") + 2] == ["--max-af", "0.0"]


def test_filter_vcf_af_controls_use_native_ac_an_filters() -> None:
    command = FilterVCFNode.render_command(
        {
            "vcf": "cohort.vcf.gz",
            "min_af": 0.2,
            "max_af": 0.8,
            "output": "/tmp/out",
        }
    )
    assert command[command.index("--min-af") : command.index("--min-af") + 2] == ["--min-af", "0.2"]
    assert command[command.index("--max-af") : command.index("--max-af") + 2] == ["--max-af", "0.8"]
    assert "INFO/AF" not in command


def test_regions_require_an_explicit_colocated_index() -> None:
    assert "vcf_index is required" in str(
        FilterVCFNode.VALIDATE_INPUTS({"vcf": "/data/cohort.vcf.gz", "regions": "chr1"})
    )
    assert FilterVCFNode.VALIDATE_INPUTS(
        {
            "vcf": "/data/cohort.vcf.gz",
            "vcf_index": "/data/cohort.vcf.gz.csi",
            "regions": "chr1",
        }
    ) is True
    assert "colocated" in str(
        FilterVCFNode.VALIDATE_INPUTS(
            {
                "vcf": "/data/cohort.vcf.gz",
                "vcf_index": "/other/cohort.vcf.gz.csi",
                "regions": "chr1",
            }
        )
    )
    assert "indexed BGZF" in str(FilterVCFNode.VALIDATE_INPUTS({"vcf": "cohort.vcf", "regions": "chr1"}))


def test_filter_vcf_stages_random_access_input_and_sidecar_together(tmp_path: Path) -> None:
    source = tmp_path / "source" / "cohort.vcf.gz"
    source.parent.mkdir()
    source.write_bytes(b"vcf")
    index = Path(f"{source}.tbi")
    index.write_bytes(b"tbi")
    inputs: dict[str, Any] = {"vcf": source, "vcf_index": index, "regions": "chr1"}
    outputs = FilterVCFNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    FilterVCFNode.PREPARE_EXECUTION(inputs, outputs)

    staged = tmp_path / "run" / "filter_vcf" / "input" / "input.vcf.gz"
    assert inputs == {"vcf": str(staged), "vcf_index": f"{staged}.tbi", "regions": "chr1"}
    assert staged.read_bytes() == b"vcf"
    assert Path(f"{staged}.tbi").read_bytes() == b"tbi"


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"vcf": "cohort.vcf.gz", "snp_only": True, "indel_only": True}, "cannot both"),
        ({"vcf": "cohort.vcf.gz", "min_dp": 20, "max_dp": 10}, "min_dp"),
        ({"vcf": "cohort.vcf.gz", "min_af": 0.8, "max_af": 0.2}, "min_af"),
        ({"vcf": "cohort.vcf.gz", "threads": True}, "threads"),
    ],
)
def test_filter_vcf_invalid_contracts_fail_closed(inputs: dict[str, Any], message: str) -> None:
    validation = FilterVCFNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


def test_filter_vcf_preserves_upstream_thread_default_and_rejects_stale_output_type() -> None:
    threads = FilterVCFNode.INPUT_TYPES()["optional"]["threads"]
    assert threads == ("INT", {"default": 0, "min": 0})
    assert FilterVCFNode.VALIDATE_INPUTS({"vcf": "cohort.vcf", "threads": 128}) is True
    assert FilterVCFNode.render_command({"vcf": "cohort.vcf"})[:4] == [
        "bcftools",
        "view",
        "--threads",
        "0",
    ]
    assert "output_type is stale" in str(
        FilterVCFNode.VALIDATE_INPUTS({"vcf": "cohort.vcf", "output_type": "VCF_GZ"})
    )


@pytest.mark.asyncio
async def test_filter_vcf_fake_execution_requires_vcf_and_csi(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            output = Path(command[command.index("-o") + 1])
            output.write_bytes(b"vcf")
            Path(f"{output}.csi").write_bytes(b"csi")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await FilterVCFNode().run(vcf="cohort.vcf.gz", context=Context())
    assert result == (
        str(tmp_path / "run" / "filter_vcf" / "filtered_vcf.vcf.gz"),
        str(tmp_path / "run" / "filter_vcf" / "filtered_vcf.vcf.gz.csi"),
    )
