from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_all_six_cnvkit_operations_pin_the_official_v0912_source() -> None:
    expected_paths = {
        "cnvkit_access": "cnvlib/access.py",
        "cnvkit_antitarget": "cnvlib/antitarget.py",
        "cnvkit_batch": "cnvlib/batch.py",
        "cnvkit_call": "cnvlib/call.py",
        "cnvkit_plot": "cnvlib/scatter.py",
        "cnvkit_target": "cnvlib/target.py",
    }
    for node_id, source_path in expected_paths.items():
        node = _node_class(node_id)
        assert node.VERSION == "0.9.12"
        assert node.GIT_TAG == "v0.9.12"
        assert node.GIT_COMMIT == "dd834b0b5b482f174d1dcb7c35b358087309c6b3"
        assert node.SOURCE_REF == node.GIT_COMMIT
        assert source_path in node.SOURCE_PATHS
        assert node.SOURCE_FILE_SHA256[source_path]
        assert node.PACKAGE_CONSTRAINTS == ("cnvkit==0.9.12",)
        assert node.EXIT_SEMANTICS
        assert node.AUDIT_STATUS == "contract-checked-no-external-execution"


def test_cnvkit_call_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_call"]
    assert node_info["display_name"] == "CNVkit Call"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Convert CNVkit log2 ratios")
    assert node_info["output"] == ["TSV"]
    assert node_info["output_name"] == ["called_segments"]
    assert node_info["required_executables"] == ["cnvkit.py"]
    assert node_info["required_conda_packages"] == ["cnvkit"]
    assert "copy number" in node_info["search_aliases"]
    assert "cnv call" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cns_file"}
    assert set(inputs["optional"]) == {
        "center",
        "center_at",
        "diploid_parx_genome",
        "drop_low_coverage",
        "filters",
        "male_reference",
        "method",
        "min_variant_depth",
        "normal_id",
        "ploidy",
        "purity",
        "sample_id",
        "sample_sex",
        "thresholds",
        "vcf",
        "zygosity_freq",
    }


def test_cnvkit_call_renders_copy_number_command() -> None:
    node_class = _node_class("cnvkit_call")

    cmd = node_class.render_command({
        "cns_file": "tumor.cns",
        "center": "median",
        "filters": ["ci", "sem"],
        "vcf": "tumor.snvs.vcf.gz",
        "sample_id": "TUMOR",
        "normal_id": "NORMAL",
        "zygosity_freq": 0.25,
        "sample_sex": "female",
        "ploidy": 3,
        "purity": 0.72,
        "method": "clonal",
        "drop_low_coverage": True,
        "male_reference": True,
        "diploid_parx_genome": "grch38",
        "output": "/tmp/run/cnvkit_call",
    })

    assert cmd == [
        "cnvkit.py",
        "call",
        "tumor.cns",
        "--center",
        "median",
        "--filter",
        "ci",
        "--filter",
        "sem",
        "--method",
        "clonal",
        "--thresholds=-1.1,-0.25,0.2,0.7",
        "--ploidy",
        "3",
        "--purity",
        "0.72",
        "--drop-low-coverage",
        "--sample-sex",
        "female",
        "--male-reference",
        "--output",
        "/tmp/run/cnvkit_call/called_segments.call.cns",
        "--vcf",
        "tumor.snvs.vcf.gz",
        "--sample-id",
        "TUMOR",
        "--normal-id",
        "NORMAL",
        "--min-variant-depth",
        "20",
        "--zygosity-freq",
        "0.25",
        "--diploid-parx-genome",
        "grch38",
    ]


def test_cnvkit_call_omits_empty_optional_flags() -> None:
    node_class = _node_class("cnvkit_call")

    cmd = node_class.render_command({
        "cns_file": "tumor.cns",
        "sample_sex": "",
        "output": "/tmp/run/cnvkit_call",
    })

    assert cmd == [
        "cnvkit.py",
        "call",
        "tumor.cns",
        "--method",
        "threshold",
        "--thresholds=-1.1,-0.25,0.2,0.7",
        "--ploidy",
        "2",
        "--output",
        "/tmp/run/cnvkit_call/called_segments.call.cns",
    ]


def test_cnvkit_call_plans_cns_output() -> None:
    node_class = _node_class("cnvkit_call")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvkit_call/called_segments.call.cns"
    ]


def test_cnvkit_call_rejects_source_invalid_option_combinations() -> None:
    node = _node_class("cnvkit_call")
    base = {"cns_file": "tumor.cns"}

    assert node.VALIDATE_INPUTS({**base, "center": "median", "center_at": 0.2}) == (
        "center and center_at are mutually exclusive"
    )
    assert node.VALIDATE_INPUTS({**base, "purity": 0}) == "purity must be greater than 0"
    assert node.VALIDATE_INPUTS({**base, "sample_id": "TUMOR"}) == (
        "sample_id, normal_id, and zygosity_freq require a VCF input"
    )
    assert node.VALIDATE_INPUTS({**base, "thresholds": "bad"}) == (
        "thresholds must be comma-separated numbers"
    )


def test_cnvkit_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_plot"]
    assert node_info["display_name"] == "CNVkit Plot"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Generate CNVkit scatter and heatmap")
    assert node_info["output"] == ["PDF_REPORT", "PDF_REPORT"]
    assert node_info["output_name"] == ["scatter_plot", "heatmap_plot"]
    assert node_info["required_executables"] == ["cnvkit.py"]
    assert node_info["required_conda_packages"] == ["cnvkit"]
    assert "cnv plot" in node_info["search_aliases"]
    assert "heatmap" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cnr_file", "cns_file"}
    assert set(inputs["optional"]) == {
        "by_bin",
        "chromosome",
        "delimit_samples",
        "desaturate",
        "gene",
        "title",
        "trend",
        "vertical",
    }


def test_cnvkit_plot_renders_scatter_and_heatmap_commands() -> None:
    node_class = _node_class("cnvkit_plot")

    cmd = node_class.render_command({
        "cnr_file": "tumor.cnr",
        "cns_file": "tumor.cns",
        "chromosome": "chr7",
        "gene": "EGFR",
        "title": "Tumor CNV",
        "by_bin": True,
        "trend": True,
        "desaturate": True,
        "vertical": True,
        "delimit_samples": True,
        "output": "/tmp/run/cnvkit_plot",
    })

    assert cmd == [
        "cnvkit.py",
        "scatter",
        "tumor.cnr",
        "--segment",
        "tumor.cns",
        "--output",
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "--chromosome",
        "chr7",
        "--gene",
        "EGFR",
        "--title",
        "Tumor CNV",
        "--by-bin",
        "--trend",
        "&&",
        "cnvkit.py",
        "heatmap",
        "tumor.cns",
        "--output",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
        "--chromosome",
        "chr7",
        "--title",
        "Tumor CNV",
        "--by-bin",
        "--desaturate",
        "--vertical",
        "--delimit-samples",
    ]


def test_cnvkit_plot_omits_empty_optional_flags() -> None:
    node_class = _node_class("cnvkit_plot")

    cmd = node_class.render_command({
        "cnr_file": "tumor.cnr",
        "cns_file": "tumor.cns",
        "chromosome": "",
        "gene": "",
        "output": "/tmp/run/cnvkit_plot",
    })

    assert cmd == [
        "cnvkit.py",
        "scatter",
        "tumor.cnr",
        "--segment",
        "tumor.cns",
        "--output",
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "&&",
        "cnvkit.py",
        "heatmap",
        "tumor.cns",
        "--output",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
    ]


def test_cnvkit_plot_plans_pdf_outputs() -> None:
    node_class = _node_class("cnvkit_plot")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
    ]


def test_cnvkit_batch_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_batch"]
    assert node_info["display_name"] == "CNVkit Batch Pipeline"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Build a flat or pooled CNV reference")
    assert node_info["output"] == ["DIRECTORY", "FILE"]
    assert node_info["output_name"] == ["results", "reference_cnn"]
    assert node_info["required_executables"] == ["cnvkit.py", "Rscript"]
    assert node_info["required_conda_packages"] == ["cnvkit", "r-base"]
    assert "copy number" in node_info["search_aliases"]
    assert "batch" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {
        "reference",
        "reference_index",
        "tumor_bam_indexes",
        "tumor_bams",
    }
    assert set(inputs["optional"]) == {
        "diagram",
        "method",
        "normal_bam_indexes",
        "normal_bams",
        "scatter",
        "targets",
        "threads",
    }


def test_cnvkit_batch_renders_complete_batch_command() -> None:
    node_class = _node_class("cnvkit_batch")

    cmd = node_class.render_command({
        "tumor_bams": ["tumor-a.bam", "tumor-b.bam"],
        "tumor_bam_indexes": ["tumor-a.bam.bai", "tumor-b.bam.bai"],
        "normal_bams": ["normal-a.bam", "normal-b.bam"],
        "normal_bam_indexes": ["normal-a.bam.bai", "normal-b.bam.bai"],
        "reference": "hg38.fa",
        "reference_index": "hg38.fa.fai",
        "targets": "targets.bed",
        "threads": 8,
        "method": "wgs",
        "diagram": True,
        "scatter": True,
        "output": "/tmp/run/cnvkit_batch",
    })

    assert cmd == [
        "cnvkit.py",
        "batch",
        "tumor-a.bam",
        "tumor-b.bam",
        "--normal",
        "normal-a.bam",
        "normal-b.bam",
        "--fasta",
        "hg38.fa",
        "--output-reference",
        "/tmp/run/cnvkit_batch/results/reference.cnn",
        "--output-dir",
        "/tmp/run/cnvkit_batch/results",
        "--processes",
        "8",
        "--seq-method",
        "wgs",
        "--targets",
        "targets.bed",
        "--scatter",
        "--diagram",
    ]


def test_cnvkit_batch_renders_documented_flat_wgs_reference_mode() -> None:
    node_class = _node_class("cnvkit_batch")

    cmd = node_class.render_command({
        "tumor_bams": "tumor.bam",
        "tumor_bam_indexes": "tumor.bam.bai",
        "reference": "hg38.fa",
        "reference_index": "hg38.fa.fai",
        "threads": 1,
        "normal_bams": [],
        "targets": "",
        "method": "wgs",
        "diagram": False,
        "scatter": False,
        "output": "/tmp/run/cnvkit_batch",
    })

    assert cmd == [
        "cnvkit.py",
        "batch",
        "tumor.bam",
        "--normal",
        "--fasta",
        "hg38.fa",
        "--output-reference",
        "/tmp/run/cnvkit_batch/results/reference.cnn",
        "--output-dir",
        "/tmp/run/cnvkit_batch/results",
        "--processes",
        "1",
        "--seq-method",
        "wgs",
    ]


def test_cnvkit_batch_plans_complete_result_directory_and_reference() -> None:
    node_class = _node_class("cnvkit_batch")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvkit_batch/results",
        "/tmp/run/cnvkit_batch/results/reference.cnn",
    ]


def test_cnvkit_batch_enforces_upstream_reference_build_requirements() -> None:
    node = _node_class("cnvkit_batch")
    base = {
        "tumor_bams": ["tumor.bam"],
        "tumor_bam_indexes": ["tumor.bam.bai"],
        "reference": "hg38.fa",
        "reference_index": "hg38.fa.fai",
        "threads": 1,
    }

    assert node.VALIDATE_INPUTS(base) == "targets BED is required for CNVkit hybrid batch mode"
    assert node.VALIDATE_INPUTS({**base, "method": "wgs"}) is True
    assert node.VALIDATE_INPUTS({**base, "method": "wgs", "threads": -1}) == (
        "threads must be a non-negative integer"
    )
    assert node.VALIDATE_INPUTS({**base, "tumor_bams": []}) == (
        "tumor_bams must contain at least one non-empty path"
    )
    assert "exact colocated index" in str(
        node.VALIDATE_INPUTS({**base, "tumor_bam_indexes": ["wrong.bai"], "method": "wgs"})
    )
    assert "exact colocated" in str(
        node.VALIDATE_INPUTS({**base, "reference_index": "wrong.fai", "method": "wgs"})
    )


@pytest.mark.asyncio
async def test_cnvkit_batch_fails_when_zero_exit_omits_source_defined_artifacts(
    tmp_path: Path,
) -> None:
    node = _node_class("cnvkit_batch")()

    class ReferenceOnlyContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            reference = Path(command[command.index("--output-reference") + 1])
            reference.parent.mkdir(parents=True, exist_ok=True)
            reference.write_text("chromosome\tstart\tend\tgene\tlog2\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not create expected artifact"):
        await node.run(
            context=ReferenceOnlyContext(),
            tumor_bams=["tumor.bam"],
            tumor_bam_indexes=["tumor.bam.bai"],
            reference="hg38.fa",
            reference_index="hg38.fa.fai",
            method="wgs",
        )


def test_cnvnator_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvnator"]
    assert node_info["display_name"] == "CNVnator"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Read-depth based CNV caller")
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["cnv_calls", "root_file"]
    assert node_info["required_executables"] == ["cnvnator"]
    assert node_info["required_conda_packages"] == ["cnvnator"]
    assert "read depth" in node_info["search_aliases"]
    assert "copy number" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "chrom_dir", "bin_size"}
    assert set(inputs["optional"]) == set()


def test_cnvnator_renders_multistep_command_with_chrom_dir() -> None:
    node_class = _node_class("cnvnator")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "reference": "hg38.fa",
        "chrom_dir": "/refs/chroms",
        "bin_size": 250,
        "output": "/tmp/run/cnvnator",
    })

    assert cmd == [
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-tree",
        "tumor.sorted.bam",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-his",
        "250",
        "-d",
        "/refs/chroms",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-stat",
        "250",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-partition",
        "250",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-call",
        "250",
        ">",
        "/tmp/run/cnvnator/cnv_calls.txt",
    ]


def test_cnvnator_omits_empty_chrom_dir_flag() -> None:
    node_class = _node_class("cnvnator")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "chrom_dir": "",
        "output": "/tmp/run/cnvnator",
    })

    assert "-d" not in cmd
    assert cmd == [
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-tree",
        "tumor.sorted.bam",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-his",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-stat",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-partition",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-call",
        "100",
        ">",
        "/tmp/run/cnvnator/cnv_calls.txt",
    ]


def test_cnvnator_plans_call_and_root_outputs() -> None:
    node_class = _node_class("cnvnator")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvnator/cnv_calls.out",
        "/tmp/run/cnvnator/root_file.out",
    ]


def test_control_freec_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["control_freec"]
    assert node_info["display_name"] == "Control-FREEC"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("CNV caller with tumor purity")
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["cnv_profile", "baf_profile"]
    assert node_info["required_executables"] == ["freec"]
    assert node_info["required_conda_packages"] == ["control-freec"]
    assert "freec" in node_info["search_aliases"]
    assert "allelic imbalance" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tumor_bam", "chrom_lengths", "chrom_dir", "window", "threads"}
    assert set(inputs["optional"]) == {"normal_bam", "ploidy"}


def test_control_freec_writes_config_and_renders_command(tmp_path) -> None:
    node_class = _node_class("control_freec")
    out_dir = tmp_path / "control_freec"

    cmd = node_class.render_command({
        "tumor_bam": "tumor.bam",
        "normal_bam": "normal.bam",
        "chrom_lengths": "hg38.chrom.sizes",
        "chrom_dir": "/refs/chroms",
        "ploidy": 3,
        "window": 100000,
        "threads": 12,
        "output": str(out_dir),
    })

    config_file = out_dir / "freec_config.txt"
    assert cmd == ["freec", "-conf", str(config_file)]
    assert config_file.read_text() == (
        "[general]\n"
        "chrLenFile = hg38.chrom.sizes\n"
        "ploidy = 3\n"
        "window = 100000\n"
        "chrFiles = /refs/chroms\n"
        f"outputDir = {out_dir}\n"
        "maxThreads = 12\n"
        "[sample]\n"
        "mateFile = tumor.bam\n"
        "inputFormat = BAM\n"
        "mateOrientation = FR\n"
        "[control]\n"
        "mateFile = normal.bam\n"
        "inputFormat = BAM\n"
        "mateOrientation = FR\n"
    )


def test_control_freec_omits_control_section_without_normal(tmp_path) -> None:
    node_class = _node_class("control_freec")
    out_dir = tmp_path / "control_freec"

    node_class.render_command({
        "tumor_bam": "tumor.bam",
        "chrom_lengths": "hg38.chrom.sizes",
        "chrom_dir": "/refs/chroms",
        "window": 50000,
        "threads": 4,
        "output": str(out_dir),
    })

    config_text = (out_dir / "freec_config.txt").read_text()
    assert "[control]" not in config_text
    assert "ploidy = 2\n" in config_text
    assert "maxThreads = 4\n" in config_text


def test_control_freec_plans_profile_outputs() -> None:
    node_class = _node_class("control_freec")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/control_freec/cnv_profile.out",
        "/tmp/run/control_freec/baf_profile.out",
    ]
