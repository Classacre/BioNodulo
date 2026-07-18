from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.builtin.epigenomics import DSS_DMR_SCRIPT
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_macs2_bdgpeak_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["macs2_bdgpeak"]
    assert node_info["display_name"] == "MACS2 BdgPeak"
    assert node_info["category"] == "chip_seq"
    assert node_info["description"].startswith("Call peaks from bedGraph signal tracks")
    assert node_info["output"] == ["BED"]
    assert node_info["output_name"] == ["peaks"]
    assert node_info["required_executables"] == ["macs2"]
    assert node_info["required_conda_packages"] == ["macs2"]
    assert "bdgpeakcall" in node_info["search_aliases"]
    assert "bedgraph peaks" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"treatment_bdg"}
    assert set(inputs["optional"]) == {
        "control_bdg",
        "method",
        "cutoff",
        "min_length",
        "max_gap",
        "name",
    }


def test_macs2_bdgpeak_renders_bdgpeakcall_command() -> None:
    node_class = _node_class("macs2_bdgpeak")

    cmd = node_class.render_command({
        "treatment_bdg": "chip_treat_pileup.bdg",
        "control_bdg": "chip_control_lambda.bdg",
        "method": "bdgpeakcall",
        "cutoff": 2.0,
        "min_length": 200,
        "max_gap": 75,
        "name": "sample peaks",
        "output": "/tmp/run/macs2_bdgpeak",
    })

    assert cmd == [
        "macs2",
        "bdgcmp",
        "-t",
        "chip_treat_pileup.bdg",
        "-c",
        "chip_control_lambda.bdg",
        "-m",
        "FE",
        "-o",
        "/tmp/run/macs2_bdgpeak/sample_peaks_FE.bdg",
        "&&",
        "macs2",
        "bdgpeakcall",
        "-i",
        "/tmp/run/macs2_bdgpeak/sample_peaks_FE.bdg",
        "-c",
        "2.0",
        "-l",
        "200",
        "-g",
        "75",
        "-o",
        "/tmp/run/macs2_bdgpeak/sample_peaks.bed",
    ]


def test_macs2_bdgpeak_renders_direct_bdgpeakcall_without_control() -> None:
    node_class = _node_class("macs2_bdgpeak")

    cmd = node_class.render_command({
        "treatment_bdg": "fold_enrichment.bdg",
        "method": "bdgpeakcall",
        "cutoff": 1.5,
        "min_length": 150,
        "max_gap": 50,
        "name": "direct",
        "output": "/tmp/run/macs2_bdgpeak",
    })

    assert cmd == [
        "macs2",
        "bdgpeakcall",
        "-i",
        "fold_enrichment.bdg",
        "-c",
        "1.5",
        "-l",
        "150",
        "-g",
        "50",
        "-o",
        "/tmp/run/macs2_bdgpeak/direct.bed",
    ]


def test_macs2_bdgpeak_renders_bdgcmp_without_peak_calling() -> None:
    node_class = _node_class("macs2_bdgpeak")

    cmd = node_class.render_command({
        "treatment_bdg": "treat.bdg",
        "control_bdg": "control.bdg",
        "method": "bdgcmp",
        "name": "score track",
        "output": "/tmp/run/macs2_bdgpeak",
    })

    assert cmd == [
        "macs2",
        "bdgcmp",
        "-t",
        "treat.bdg",
        "-c",
        "control.bdg",
        "-m",
        "FE",
        "-o",
        "/tmp/run/macs2_bdgpeak/score_track.bed",
    ]


def test_macs2_bdgpeak_plans_peak_output() -> None:
    node_class = _node_class("macs2_bdgpeak")

    outputs = node_class.PLAN_OUTPUTS({"name": "sample peaks"}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/macs2_bdgpeak/sample_peaks.bed"]


def test_macs2_bdgpeak_rejects_invalid_mode_and_missing_control_for_bdgcmp() -> None:
    node_class = _node_class("macs2_bdgpeak")

    assert node_class.VALIDATE_INPUTS({"treatment_bdg": "signal.bdg", "method": "custom"}) == "Unsupported MACS2 bedGraph mode: custom"
    assert (
        node_class.VALIDATE_INPUTS({"treatment_bdg": "signal.bdg", "method": "bdgcmp"})
        == "control_bdg is required when method is bdgcmp"
    )


def test_macs2_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["macs2"] == "macs2"
    assert PACKAGE_MIN_VERSIONS["macs2"] == ">=2.2.9"


def test_dss_dmr_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dss_dmr"]
    assert node_info["display_name"] == "DSS DMR"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Detect differentially methylated regions")
    assert node_info["output"] == ["BED", "FILE"]
    assert node_info["output_name"] == ["dmr", "dmr_stats"]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == ["r-base", "bioconductor-dss", "r-readr"]
    assert "differential methylation" in node_info["search_aliases"]
    assert "DSS" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"methylation_files", "sample_info", "condition_column", "sample_column"}
    assert set(inputs["optional"]) == {"smoothing", "delta", "pvalue", "minlen", "mincg", "output_prefix"}


def test_dss_dmr_renders_rscript_command() -> None:
    node_class = _node_class("dss_dmr")

    cmd = node_class.render_command({
        "methylation_files": "tumor.tsv,normal.tsv",
        "sample_info": "samples.tsv",
        "condition_column": "condition",
        "sample_column": "sample",
        "smoothing": True,
        "delta": 0.2,
        "pvalue": 0.001,
        "minlen": 75,
        "mincg": 4,
        "output_prefix": "case control",
        "output": "/tmp/run/dss_dmr",
    })

    assert cmd == [
        "Rscript",
        str(DSS_DMR_SCRIPT),
        "--methylation-files",
        "tumor.tsv,normal.tsv",
        "--sample-info",
        "samples.tsv",
        "--condition-column",
        "condition",
        "--sample-column",
        "sample",
        "--output-bed",
        "/tmp/run/dss_dmr/case_control.dmr.bed",
        "--output-stats",
        "/tmp/run/dss_dmr/case_control.dmr_stats.tsv",
        "--delta",
        "0.2",
        "--pvalue",
        "0.001",
        "--minlen",
        "75",
        "--mincg",
        "4",
        "--smoothing",
    ]


def test_dss_dmr_accepts_list_inputs_and_omits_smoothing_flag() -> None:
    node_class = _node_class("dss_dmr")

    cmd = node_class.render_command({
        "methylation_files": ["tumor.tsv", "normal.tsv"],
        "sample_info": "samples.tsv",
        "condition_column": "group",
        "sample_column": "sample_id",
        "smoothing": False,
        "output": "/tmp/run/dss_dmr",
    })

    assert "--smoothing" not in cmd
    assert cmd == [
        "Rscript",
        str(DSS_DMR_SCRIPT),
        "--methylation-files",
        "tumor.tsv,normal.tsv",
        "--sample-info",
        "samples.tsv",
        "--condition-column",
        "group",
        "--sample-column",
        "sample_id",
        "--output-bed",
        "/tmp/run/dss_dmr/dss_dmr.dmr.bed",
        "--output-stats",
        "/tmp/run/dss_dmr/dss_dmr.dmr_stats.tsv",
        "--delta",
        "0.1",
        "--pvalue",
        "0.001",
        "--minlen",
        "50",
        "--mincg",
        "3",
    ]


def test_dss_dmr_plans_named_outputs() -> None:
    node_class = _node_class("dss_dmr")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "case control"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/dss_dmr/case_control.dmr.bed",
        "/tmp/run/dss_dmr/case_control.dmr_stats.tsv",
    ]


def test_dss_dmr_rejects_missing_or_single_methylation_file() -> None:
    node_class = _node_class("dss_dmr")

    assert (
        node_class.VALIDATE_INPUTS({
            "methylation_files": "",
            "sample_info": "samples.tsv",
            "condition_column": "condition",
            "sample_column": "sample",
        })
        == "At least two methylation files are required"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "methylation_files": "tumor.tsv",
            "sample_info": "samples.tsv",
            "condition_column": "condition",
            "sample_column": "sample",
        })
        == "At least two methylation files are required"
    )


def test_dss_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["Rscript"] == "r-base"
    assert PACKAGE_MIN_VERSIONS["bioconductor-dss"] == ">=2.48.0"


def test_modkit_dmr_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["modkit_dmr"]
    assert node_info["display_name"] == "Modkit DMR"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Detect differentially methylated regions")
    assert node_info["output"] == ["BED", "FILE"]
    assert node_info["output_name"] == ["dmr", "log"]
    assert node_info["required_executables"] == ["modkit"]
    assert node_info["required_conda_packages"] == ["modkit"]
    assert "dmr pair" in node_info["search_aliases"]
    assert "differential methylation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sample_a", "sample_b", "reference", "base", "threads"}
    assert set(inputs["optional"]) == {"index_a", "index_b", "regions", "segment", "fine_grained", "output_prefix"}


def test_modkit_dmr_renders_pair_command_with_region_indexes_and_segment() -> None:
    node_class = _node_class("modkit_dmr")

    cmd = node_class.render_command({
        "sample_a": "normal.bed.gz",
        "index_a": "normal.bed.gz.tbi",
        "sample_b": "tumor.bed.gz",
        "index_b": "tumor.bed.gz.tbi",
        "reference": "grch38.fa",
        "regions": "cpg_islands.bed",
        "segment": "segments.bed",
        "base": "C,A",
        "threads": 32,
        "fine_grained": True,
        "output_prefix": "tumor normal",
        "output": "/tmp/run/modkit_dmr",
    })

    assert cmd == [
        "modkit",
        "dmr",
        "pair",
        "-a",
        "normal.bed.gz",
        "--index-a",
        "normal.bed.gz.tbi",
        "-b",
        "tumor.bed.gz",
        "--index-b",
        "tumor.bed.gz.tbi",
        "-o",
        "/tmp/run/modkit_dmr/tumor_normal.dmr.bed",
        "--ref",
        "grch38.fa",
        "--base",
        "C",
        "--base",
        "A",
        "--threads",
        "32",
        "--log-filepath",
        "/tmp/run/modkit_dmr/tumor_normal.dmr.log",
        "-r",
        "cpg_islands.bed",
        "--segment",
        "segments.bed",
        "--fine-grained",
    ]


def test_modkit_dmr_omits_optional_flags_for_single_base_analysis() -> None:
    node_class = _node_class("modkit_dmr")

    cmd = node_class.render_command({
        "sample_a": "control.bed.gz",
        "sample_b": "case.bed.gz",
        "reference": "ref.fa",
        "base": ["C"],
        "threads": 4,
        "fine_grained": False,
        "output": "/tmp/run/modkit_dmr",
    })

    assert "--index-a" not in cmd
    assert "--index-b" not in cmd
    assert "-r" not in cmd
    assert "--segment" not in cmd
    assert "--fine-grained" not in cmd
    assert cmd == [
        "modkit",
        "dmr",
        "pair",
        "-a",
        "control.bed.gz",
        "-b",
        "case.bed.gz",
        "-o",
        "/tmp/run/modkit_dmr/modkit_dmr.dmr.bed",
        "--ref",
        "ref.fa",
        "--base",
        "C",
        "--threads",
        "4",
        "--log-filepath",
        "/tmp/run/modkit_dmr/modkit_dmr.dmr.log",
    ]


def test_modkit_dmr_plans_named_outputs() -> None:
    node_class = _node_class("modkit_dmr")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "tumor normal"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/modkit_dmr/tumor_normal.dmr.bed",
        "/tmp/run/modkit_dmr/tumor_normal.dmr.log",
    ]


def test_modkit_dmr_rejects_empty_required_values_and_invalid_threads() -> None:
    node_class = _node_class("modkit_dmr")

    assert (
        node_class.VALIDATE_INPUTS({
            "sample_a": "",
            "sample_b": "case.bed.gz",
            "reference": "ref.fa",
            "base": "C",
            "threads": 1,
        })
        == "sample_a is required"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "sample_a": "control.bed.gz",
            "sample_b": "case.bed.gz",
            "reference": "ref.fa",
            "base": [],
            "threads": 1,
        })
        == "At least one base is required"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "sample_a": "control.bed.gz",
            "sample_b": "case.bed.gz",
            "reference": "ref.fa",
            "base": "C",
            "threads": 0,
        })
        == "threads must be at least 1"
    )


def test_modkit_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["modkit"] == "modkit"
    assert PACKAGE_MIN_VERSIONS["modkit"] == ">=0.4.3"
    assert workflow_to_packages({"nodes": [{"id": "dmr", "type": "modkit_dmr"}]}, registry) == ["modkit"]


def test_methyldackel_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["methyldackel"]
    assert node_info["display_name"] == "MethylDackel"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Extract per-base methylation")
    assert node_info["output"] == ["BED", "BED"]
    assert node_info["output_name"] == ["methylation_bedgraph", "mbias_report"]
    assert node_info["required_executables"] == ["MethylDackel"]
    assert node_info["required_conda_packages"] == ["methyldackel"]
    assert "pileometh" in node_info["search_aliases"]
    assert "cpg" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "output_prefix"}
    assert set(inputs["optional"]) == {"merge_context", "min_depth"}


def test_methyldackel_renders_default_command() -> None:
    node_class = _node_class("methyldackel")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "ref.fa",
        "output_prefix": "sample",
        "merge_context": True,
        "min_depth": 5,
        "output": "/tmp/run/methyldackel",
    })

    assert cmd == [
        "MethylDackel",
        "mbias",
        "ref.fa",
        "sample.bam",
        "/tmp/run/methyldackel/sample",
        "&&",
        "MethylDackel",
        "extract",
        "ref.fa",
        "sample.bam",
        "-o",
        "/tmp/run/methyldackel/sample",
        "--bedGraph",
        "--mergeContext",
        "--minDepth",
        "5",
    ]


def test_methyldackel_omits_optional_flags() -> None:
    node_class = _node_class("methyldackel")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "ref.fa",
        "output_prefix": "sample",
        "merge_context": False,
        "min_depth": 0,
        "output": "/tmp/run/methyldackel",
    })

    assert "--mergeContext" not in cmd
    assert "--minDepth" not in cmd
    assert cmd[-4:] == ["sample.bam", "-o", "/tmp/run/methyldackel/sample", "--bedGraph"]


def test_methyldackel_plans_bed_outputs() -> None:
    node_class = _node_class("methyldackel")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/methyldackel/methylation_bedgraph.bed",
        "/tmp/run/methyldackel/mbias_report.bed",
    ]


def test_deeptools_bamcoverage_is_registered_for_epigenomics_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["deeptools_bamcoverage"]
    assert node_info["display_name"] == "deepTools bamCoverage"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Convert BAM to bigWig")
    assert node_info["output"] == ["BIGWIG"]
    assert node_info["output_name"] == ["coverage_bw"]
    assert node_info["required_executables"] == ["bamCoverage"]
    assert node_info["required_conda_packages"] == ["deeptools"]
    assert "bigwig" in node_info["search_aliases"]
    assert "coverage" in node_info["search_aliases"]
    assert "atac-seq" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "bam_index", "threads", "normalize_using"}
    assert set(inputs["optional"]) == {
        "bin_size",
        "effective_genome_size",
        "center_reads",
        "ignore_duplicates",
        "extend_reads",
        "blacklist",
    }


def test_deeptools_bamcoverage_renders_default_command() -> None:
    node_class = _node_class("deeptools_bamcoverage")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "threads": 4,
        "normalize_using": "CPM",
        "bin_size": 10,
        "ignore_duplicates": True,
        "output": "/tmp/run/deeptools_bamcoverage",
    })

    assert cmd == [
        "bamCoverage",
        "-b",
        "sample.bam",
        "-o",
        "/tmp/run/deeptools_bamcoverage/coverage_bw.bw",
        "-p",
        "4",
        "--binSize",
        "10",
        "--normalizeUsing",
        "CPM",
        "--ignoreDuplicates",
    ]


def test_deeptools_bamcoverage_renders_optional_flags() -> None:
    node_class = _node_class("deeptools_bamcoverage")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "threads": 8,
        "normalize_using": "RPGC",
        "bin_size": 25,
        "effective_genome_size": 2913022398,
        "center_reads": True,
        "ignore_duplicates": True,
        "extend_reads": 150,
        "blacklist": "blacklist.bed",
        "output": "/tmp/run/deeptools_bamcoverage",
    })

    assert "--normalizeUsing" in cmd
    assert cmd[cmd.index("--normalizeUsing") + 1] == "RPGC"
    assert "--effectiveGenomeSize" in cmd
    assert cmd[cmd.index("--effectiveGenomeSize") + 1] == "2913022398"
    assert "--centerReads" in cmd
    assert "--ignoreDuplicates" in cmd
    assert "--extendReads" in cmd
    assert cmd[cmd.index("--extendReads") + 1] == "150"
    assert "--blackListFileName" in cmd
    assert cmd[cmd.index("--blackListFileName") + 1] == "blacklist.bed"


def test_deeptools_bamcoverage_omits_disabled_optional_flags() -> None:
    node_class = _node_class("deeptools_bamcoverage")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "threads": 2,
        "normalize_using": "None",
        "bin_size": 50,
        "effective_genome_size": 0,
        "center_reads": False,
        "ignore_duplicates": False,
        "extend_reads": 0,
        "blacklist": "",
        "output": "/tmp/run/deeptools_bamcoverage",
    })

    assert "--normalizeUsing" not in cmd
    assert "--effectiveGenomeSize" not in cmd
    assert "--centerReads" not in cmd
    assert "--ignoreDuplicates" not in cmd
    assert "--extendReads" not in cmd
    assert "--blackListFileName" not in cmd


def test_deeptools_bamcoverage_plans_bigwig_output() -> None:
    node_class = _node_class("deeptools_bamcoverage")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/deeptools_bamcoverage/coverage_bw.bw"]


def test_deeptools_compute_matrix_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["deeptools_compute_matrix"]
    assert node_info["display_name"] == "deepTools computeMatrix"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Prepare signal matrices")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["matrix"]
    assert node_info["required_executables"] == ["computeMatrix"]
    assert node_info["required_conda_packages"] == ["deeptools"]
    assert "computematrix" in node_info["search_aliases"]
    assert "heatmap matrix" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bigwig", "regions", "mode", "threads"}
    assert set(inputs["optional"]) == {
        "reference_point",
        "before_region",
        "after_region",
        "region_body_length",
        "skip_zeros",
    }


def test_deeptools_compute_matrix_renders_reference_point_command() -> None:
    node_class = _node_class("deeptools_compute_matrix")

    cmd = node_class.render_command({
        "bigwig": "signal.bw",
        "regions": "genes.bed",
        "mode": "reference-point",
        "threads": 8,
        "bin_size": 25,
        "reference_point": "TSS",
        "before_region": 2000,
        "after_region": 1000,
        "skip_zeros": True,
        "output": "/tmp/run/deeptools_compute_matrix",
    })

    assert cmd == [
        "computeMatrix",
        "reference-point",
        "-S",
        "signal.bw",
        "-R",
        "genes.bed",
        "-o",
        "/tmp/run/deeptools_compute_matrix/matrix.gz",
        "-p",
        "8",
        "--binSize",
        "25",
        "--referencePoint",
        "TSS",
        "-b",
        "2000",
        "-a",
        "1000",
        "--skipZeros",
    ]


def test_deeptools_compute_matrix_renders_scale_regions_command() -> None:
    node_class = _node_class("deeptools_compute_matrix")

    cmd = node_class.render_command({
        "bigwig": "signal.bw",
        "regions": "genes.bed",
        "mode": "scale-regions",
        "threads": 4,
        "bin_size": 10,
        "before_region": 3000,
        "after_region": 3000,
        "region_body_length": 5000,
        "skip_zeros": False,
        "output": "/tmp/run/deeptools_compute_matrix",
    })

    assert cmd == [
        "computeMatrix",
        "scale-regions",
        "-S",
        "signal.bw",
        "-R",
        "genes.bed",
        "-o",
        "/tmp/run/deeptools_compute_matrix/matrix.gz",
        "-p",
        "4",
        "--binSize",
        "10",
        "-b",
        "3000",
        "-a",
        "3000",
        "--regionBodyLength",
        "5000",
    ]


def test_deeptools_compute_matrix_plans_matrix_output() -> None:
    node_class = _node_class("deeptools_compute_matrix")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/deeptools_compute_matrix/matrix.out"]


def test_deeptools_plot_heatmap_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["deeptools_plot_heatmap"]
    assert node_info["display_name"] == "deepTools Plot Heatmap"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Publication-quality heatmaps")
    assert node_info["output"] == ["IMAGE", "IMAGE"]
    assert node_info["output_name"] == ["heatmap", "profile_plot"]
    assert node_info["required_executables"] == ["plotHeatmap"]
    assert node_info["required_conda_packages"] == ["deeptools"]
    assert "plotheatmap" in node_info["search_aliases"]
    assert "profile plot" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"matrix"}
    assert set(inputs["optional"]) == {
        "heatmap_height",
        "heatmap_width",
        "colormap",
        "sort_regions",
        "kmeans",
        "plot_title",
    }


def test_deeptools_plot_heatmap_renders_heatmap_and_profile_command() -> None:
    node_class = _node_class("deeptools_plot_heatmap")

    cmd = node_class.render_command({
        "matrix": "matrix.gz",
        "heatmap_height": 30,
        "heatmap_width": 20,
        "colormap": "viridis",
        "sort_regions": "descend",
        "kmeans": 4,
        "plot_title": "Signal heatmap",
        "output": "/tmp/run/deeptools_plot_heatmap",
    })

    assert cmd == [
        "plotHeatmap",
        "-m",
        "matrix.gz",
        "--heatmapHeight",
        "30",
        "--heatmapWidth",
        "20",
        "--colorMap",
        "viridis",
        "--outFileName",
        "/tmp/run/deeptools_plot_heatmap/heatmap.png",
        "--sortRegions",
        "descend",
        "--kmeans",
        "4",
        "--plotTitle",
        "Signal heatmap",
        "&&",
        "plotProfile",
        "-m",
        "matrix.gz",
        "--outFileName",
        "/tmp/run/deeptools_plot_heatmap/profile_plot.png",
        "--plotTitle",
        "Signal heatmap",
    ]


def test_deeptools_plot_heatmap_omits_disabled_optional_flags() -> None:
    node_class = _node_class("deeptools_plot_heatmap")

    cmd = node_class.render_command({
        "matrix": "matrix.gz",
        "heatmap_height": 25,
        "heatmap_width": 15,
        "colormap": "RdBu_r",
        "sort_regions": "no",
        "kmeans": 0,
        "plot_title": "",
        "output": "/tmp/run/deeptools_plot_heatmap",
    })

    assert "--sortRegions" not in cmd
    assert "--kmeans" not in cmd
    assert "--plotTitle" not in cmd
    assert "&&" in cmd


def test_deeptools_plot_heatmap_plans_image_outputs() -> None:
    node_class = _node_class("deeptools_plot_heatmap")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/deeptools_plot_heatmap/heatmap.png",
        "/tmp/run/deeptools_plot_heatmap/profile_plot.png",
    ]


def test_deeptools_plot_profile_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["deeptools_plot_profile"]
    assert node_info["display_name"] == "deepTools Plot Profile"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Plot average signal profiles")
    assert node_info["output"] == ["IMAGE"]
    assert node_info["output_name"] == ["profile"]
    assert node_info["required_executables"] == ["plotProfile"]
    assert node_info["required_conda_packages"] == ["deeptools"]
    assert "plotprofile" in node_info["search_aliases"]
    assert "average profile" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"matrix"}
    assert set(inputs["optional"]) == {
        "plot_title",
        "plot_type",
        "plot_height",
        "plot_width",
        "per_group",
        "colors",
        "samples_label",
        "regions_label",
        "y_axis_label",
        "start_label",
        "end_label",
        "legend_location",
    }


def test_deeptools_plot_profile_renders_full_command() -> None:
    node_class = _node_class("deeptools_plot_profile")

    cmd = node_class.render_command({
        "matrix": "matrix.gz",
        "plot_title": "ATAC signal",
        "plot_type": "se",
        "plot_height": 6.5,
        "plot_width": 9.0,
        "per_group": True,
        "colors": "red blue green",
        "samples_label": "Ctrl Treated",
        "regions_label": "Promoters Enhancers",
        "y_axis_label": "RPGC normalized signal",
        "start_label": "-3 kb",
        "end_label": "+3 kb",
        "legend_location": "upper-right",
        "output": "/tmp/run/deeptools_plot_profile",
    })

    assert cmd == [
        "plotProfile",
        "-m",
        "matrix.gz",
        "--outFileName",
        "/tmp/run/deeptools_plot_profile/profile.png",
        "--plotTitle",
        "ATAC signal",
        "--plotType",
        "se",
        "--plotHeight",
        "6.5",
        "--plotWidth",
        "9.0",
        "--perGroup",
        "--colors",
        "red blue green",
        "--samplesLabel",
        "Ctrl Treated",
        "--regionsLabel",
        "Promoters Enhancers",
        "--yAxisLabel",
        "RPGC normalized signal",
        "--startLabel",
        "-3 kb",
        "--endLabel",
        "+3 kb",
        "--legendLocation",
        "upper-right",
    ]


def test_deeptools_plot_profile_omits_disabled_optional_flags() -> None:
    node_class = _node_class("deeptools_plot_profile")

    cmd = node_class.render_command({
        "matrix": "matrix.gz",
        "plot_title": "",
        "plot_type": "lines",
        "plot_height": 0,
        "plot_width": 0,
        "per_group": False,
        "colors": "",
        "samples_label": "",
        "regions_label": "",
        "y_axis_label": "",
        "start_label": "",
        "end_label": "",
        "legend_location": "best",
        "output": "/tmp/run/deeptools_plot_profile",
    })

    assert cmd == [
        "plotProfile",
        "-m",
        "matrix.gz",
        "--outFileName",
        "/tmp/run/deeptools_plot_profile/profile.png",
        "--plotType",
        "lines",
        "--legendLocation",
        "best",
    ]


def test_deeptools_plot_profile_plans_image_output() -> None:
    node_class = _node_class("deeptools_plot_profile")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/deeptools_plot_profile/profile.png"]


def test_deeptools_plot_profile_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["plotProfile"] == "deeptools"
    assert workflow_to_packages({"nodes": [{"id": "profile", "type": "deeptools_plot_profile"}]}, registry) == [
        "deeptools"
    ]


def test_hic_pro_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["hic_pro"]
    assert node_info["display_name"] == "HiC-Pro Pipeline"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Complete Hi-C processing")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["hic_results"]
    assert node_info["required_executables"] == ["HiC-Pro"]
    assert node_info["required_conda_packages"] == ["hic-pro"]
    assert "hic-pro" in node_info["search_aliases"]
    assert "3d genome" in node_info["search_aliases"]
    assert "contact matrix" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {
        "input_dir",
        "genome_fasta",
        "bowtie2_index_dir",
        "chrom_sizes",
        "threads",
    }
    assert set(inputs["optional"]) == {"min_mapq", "bin_sizes", "max_iter"}


def test_hic_pro_renders_command_and_config_file(tmp_path: Path) -> None:
    node_class = _node_class("hic_pro")
    output_dir = tmp_path / "hic_pro"

    cmd = node_class.render_command({
        "input_dir": "fastqs/",
        "genome_fasta": "hg38.fa",
        "bowtie2_index_dir": "bt2_index/",
        "chrom_sizes": "hg38.chrom.sizes",
        "threads": 12,
        "min_mapq": 20,
        "bin_sizes": "10000 40000",
        "max_iter": 50,
        "output": str(output_dir),
    })

    config_file = output_dir / "hicpro_config.txt"
    assert cmd == [
        "HiC-Pro",
        "-i",
        "fastqs/",
        "-o",
        str(output_dir),
        "-c",
        str(config_file),
    ]
    assert config_file.read_text() == (
        "N_CPU = 12\n"
        "REFERENCE_GENOME = hg38.fa\n"
        "GENOME_SIZE = hg38.chrom.sizes\n"
        "BOWTIE2_IDX_PATH = bt2_index/\n"
        "PAIR1_EXT = _R1\n"
        "PAIR2_EXT = _R2\n"
        "MIN_MAPQ = 20\n"
        "BIN_SIZE = 10000 40000\n"
        "MAX_ITER = 50\n"
    )


def test_hic_pro_renders_default_config_values(tmp_path: Path) -> None:
    node_class = _node_class("hic_pro")
    output_dir = tmp_path / "hic_pro"

    node_class.render_command({
        "input_dir": "fastqs/",
        "genome_fasta": "hg38.fa",
        "bowtie2_index_dir": "bt2_index/",
        "chrom_sizes": "hg38.chrom.sizes",
        "output": str(output_dir),
    })

    config_text = (output_dir / "hicpro_config.txt").read_text()
    assert "N_CPU = 8\n" in config_text
    assert "MIN_MAPQ = 10\n" in config_text
    assert "BIN_SIZE = 5000 10000 20000 40000 100000 1000000\n" in config_text
    assert "MAX_ITER = 100\n" in config_text


def test_hic_pro_plans_results_directory() -> None:
    node_class = _node_class("hic_pro")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/hic_pro/hic_results"]


def test_juicer_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["juicer"]
    assert node_info["display_name"] == "Juicer Pipeline"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Process Hi-C data with Juicer")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["hic_file"]
    assert node_info["required_executables"] == ["juicer.sh"]
    assert node_info["required_conda_packages"] == ["juicer"]
    assert "juicebox" in node_info["search_aliases"]
    assert "hiccups" in node_info["search_aliases"]
    assert "tad" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"fastq_dir", "genome_id", "chrom_sizes", "restriction_site"}
    assert set(inputs["optional"]) == {"restriction_sites_bed"}


def test_juicer_renders_command_with_restriction_sites_bed() -> None:
    node_class = _node_class("juicer")

    cmd = node_class.render_command({
        "fastq_dir": "fastqs/",
        "genome_id": "hg38",
        "chrom_sizes": "hg38.chrom.sizes",
        "restriction_site": "GATC",
        "restriction_sites_bed": "restriction_sites.bed",
        "output": "/tmp/run/juicer",
    })

    assert cmd == [
        "juicer.sh",
        "-g",
        "hg38",
        "-d",
        "fastqs/",
        "-s",
        "GATC",
        "-p",
        "hg38.chrom.sizes",
        "-D",
        "/tmp/run/juicer",
        "-y",
        "restriction_sites.bed",
    ]


def test_juicer_omits_optional_restriction_sites_bed() -> None:
    node_class = _node_class("juicer")

    cmd = node_class.render_command({
        "fastq_dir": "fastqs/",
        "genome_id": "mm10",
        "chrom_sizes": "mm10.chrom.sizes",
        "restriction_site": "none",
        "restriction_sites_bed": "",
        "output": "/tmp/run/juicer",
    })

    assert cmd == [
        "juicer.sh",
        "-g",
        "mm10",
        "-d",
        "fastqs/",
        "-s",
        "none",
        "-p",
        "mm10.chrom.sizes",
        "-D",
        "/tmp/run/juicer",
    ]


def test_juicer_plans_hic_output() -> None:
    node_class = _node_class("juicer")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/juicer/hic_file.hic"]


def test_cooler_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cooler"]
    assert node_info["display_name"] == "Cooler Matrix"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Create, zoomify, and balance Hi-C contact matrices")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["mcool"]
    assert node_info["required_executables"] == ["cooler"]
    assert node_info["required_conda_packages"] == ["cooler", "cooltools"]
    assert "contact matrix" in node_info["search_aliases"]
    assert "mcool" in node_info["search_aliases"]
    assert "ice normalization" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_data", "mode"}
    assert set(inputs["optional"]) == {"chrom_sizes", "bin_size", "threads"}


def test_cooler_renders_cload_zoomify_balance_command() -> None:
    node_class = _node_class("cooler")

    cmd = node_class.render_command({
        "input_data": "valid_pairs.pairs.gz",
        "mode": "cload",
        "chrom_sizes": "hg38.chrom.sizes",
        "bin_size": 10000,
        "threads": 8,
        "output": "/tmp/run/cooler",
    })

    assert cmd == [
        "cooler",
        "cload",
        "pairs",
        "hg38.chrom.sizes:10000",
        "valid_pairs.pairs.gz",
        "/tmp/run/cooler/matrix.cool",
        "&&",
        "cooler",
        "zoomify",
        "-p",
        "8",
        "-o",
        "/tmp/run/cooler/mcool.mcool",
        "/tmp/run/cooler/matrix.cool",
        "&&",
        "cooler",
        "balance",
        "-p",
        "8",
        "/tmp/run/cooler/mcool.mcool",
    ]


def test_cooler_renders_csort_command() -> None:
    node_class = _node_class("cooler")

    cmd = node_class.render_command({
        "input_data": "valid_pairs.pairs",
        "mode": "csort",
        "chrom_sizes": "hg38.chrom.sizes",
        "threads": 4,
        "output": "/tmp/run/cooler",
    })

    assert cmd == [
        "cooler",
        "csort",
        "-k2,2n",
        "-k4,4n",
        "-c1",
        "-c3",
        "-p",
        "4",
        "hg38.chrom.sizes",
        "valid_pairs.pairs",
        "/tmp/run/cooler/sorted.pairs.gz",
    ]


def test_cooler_renders_balance_command() -> None:
    node_class = _node_class("cooler")

    cmd = node_class.render_command({
        "input_data": "matrix.mcool",
        "mode": "balance",
        "threads": 12,
    })

    assert cmd == ["cooler", "balance", "--cis-only", "-p", "12", "matrix.mcool"]


def test_cooler_plans_mcool_output() -> None:
    node_class = _node_class("cooler")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/cooler/mcool.mcool"]


def test_cooltools_compartments_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cooltools_compartments"]
    assert node_info["display_name"] == "cooltools Compartments"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Call A/B compartments")
    assert node_info["output"] == ["TSV", "FILE"]
    assert node_info["output_name"] == ["compartment_track", "eigenvalues"]
    assert node_info["required_executables"] == ["cooltools"]
    assert node_info["required_conda_packages"] == ["cooltools"]
    assert "eigs-cis" in node_info["search_aliases"]
    assert "compartments" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cooler_uri"}
    assert set(inputs["optional"]) == {
        "phasing_track",
        "view_file",
        "n_eigs",
        "clr_weight_name",
        "ignore_diags",
        "output_prefix",
    }


def test_cooltools_compartments_renders_eigs_cis_command() -> None:
    node_class = _node_class("cooltools_compartments")

    cmd = node_class.render_command({
        "cooler_uri": "matrix.mcool::resolutions/100000",
        "phasing_track": "gc.tsv::GC",
        "view_file": "view.tsv",
        "n_eigs": 2,
        "clr_weight_name": "weight",
        "ignore_diags": 3,
        "output_prefix": "sample compartments",
        "output": "/tmp/run/cooltools_compartments",
    })

    assert cmd == [
        "cooltools",
        "eigs-cis",
        "--phasing-track",
        "gc.tsv::GC",
        "--view",
        "view.tsv",
        "--n-eigs",
        "2",
        "--clr-weight-name",
        "weight",
        "--ignore-diags",
        "3",
        "-o",
        "/tmp/run/cooltools_compartments/sample_compartments",
        "matrix.mcool::resolutions/100000",
    ]


def test_cooltools_compartments_omits_empty_optional_flags() -> None:
    node_class = _node_class("cooltools_compartments")

    cmd = node_class.render_command({
        "cooler_uri": "matrix.cool",
        "phasing_track": "",
        "view_file": "",
        "n_eigs": 1,
        "clr_weight_name": "",
        "ignore_diags": 0,
        "output": "/tmp/run/cooltools_compartments",
    })

    assert "--phasing-track" not in cmd
    assert "--view" not in cmd
    assert "--clr-weight-name" not in cmd
    assert "--ignore-diags" not in cmd
    assert cmd == [
        "cooltools",
        "eigs-cis",
        "--n-eigs",
        "1",
        "-o",
        "/tmp/run/cooltools_compartments/compartments",
        "matrix.cool",
    ]


def test_cooltools_compartments_plans_eigs_outputs() -> None:
    node_class = _node_class("cooltools_compartments")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "sample compartments"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cooltools_compartments/sample_compartments.cis.vecs.tsv",
        "/tmp/run/cooltools_compartments/sample_compartments.cis.lam.txt",
    ]


def test_cooltools_compartments_rejects_invalid_eigenvector_settings() -> None:
    node_class = _node_class("cooltools_compartments")

    assert node_class.VALIDATE_INPUTS({"cooler_uri": "matrix.cool", "n_eigs": 0}) == "n_eigs must be at least 1."
    assert (
        node_class.VALIDATE_INPUTS({"cooler_uri": "matrix.cool", "n_eigs": 1, "ignore_diags": -1})
        == "ignore_diags must be zero or greater."
    )


def test_cooltools_insulation_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cooltools_insulation"]
    assert node_info["display_name"] == "cooltools Insulation"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Calculate diamond insulation scores")
    assert node_info["output"] == ["TSV"]
    assert node_info["output_name"] == ["insulation"]
    assert node_info["required_executables"] == ["cooltools"]
    assert node_info["required_conda_packages"] == ["cooltools"]
    assert "insulation" in node_info["search_aliases"]
    assert "boundaries" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cooler_uri", "window_sizes"}
    assert set(inputs["optional"]) == {
        "view_file",
        "nproc",
        "clr_weight_name",
        "ignore_diags",
        "min_frac_valid_pixels",
        "min_dist_bad_bin",
        "threshold",
        "window_pixels",
        "append_raw_scores",
        "chunksize",
    }


def test_cooltools_insulation_renders_boundary_command() -> None:
    node_class = _node_class("cooltools_insulation")

    cmd = node_class.render_command({
        "cooler_uri": "matrix.mcool::resolutions/25000",
        "window_sizes": "100000,250000",
        "view_file": "view.tsv",
        "nproc": 6,
        "clr_weight_name": "weight",
        "ignore_diags": 2,
        "min_frac_valid_pixels": 0.75,
        "min_dist_bad_bin": 1,
        "threshold": "Li",
        "window_pixels": True,
        "append_raw_scores": True,
        "chunksize": 5000000,
        "output": "/tmp/run/cooltools_insulation",
    })

    assert cmd == [
        "cooltools",
        "insulation",
        "-p",
        "6",
        "-o",
        "/tmp/run/cooltools_insulation/insulation.tsv",
        "--view",
        "view.tsv",
        "--clr-weight-name",
        "weight",
        "--ignore-diags",
        "2",
        "--min-frac-valid-pixels",
        "0.75",
        "--min-dist-bad-bin",
        "1",
        "--threshold",
        "Li",
        "--window-pixels",
        "--append-raw-scores",
        "--chunksize",
        "5000000",
        "matrix.mcool::resolutions/25000",
        "100000",
        "250000",
    ]


def test_cooltools_insulation_omits_empty_optional_flags() -> None:
    node_class = _node_class("cooltools_insulation")

    cmd = node_class.render_command({
        "cooler_uri": "matrix.cool",
        "window_sizes": "100000",
        "nproc": 1,
        "view_file": "",
        "clr_weight_name": "",
        "ignore_diags": 0,
        "threshold": "",
        "window_pixels": False,
        "append_raw_scores": False,
        "chunksize": 0,
        "output": "/tmp/run/cooltools_insulation",
    })

    assert "--view" not in cmd
    assert "--clr-weight-name" not in cmd
    assert "--ignore-diags" not in cmd
    assert "--threshold" not in cmd
    assert "--window-pixels" not in cmd
    assert "--append-raw-scores" not in cmd
    assert "--chunksize" not in cmd
    assert cmd == [
        "cooltools",
        "insulation",
        "-p",
        "1",
        "-o",
        "/tmp/run/cooltools_insulation/insulation.tsv",
        "matrix.cool",
        "100000",
    ]


def test_cooltools_insulation_plans_insulation_output() -> None:
    node_class = _node_class("cooltools_insulation")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/cooltools_insulation/insulation.tsv"]


def test_cooltools_insulation_rejects_invalid_window_and_resource_settings() -> None:
    node_class = _node_class("cooltools_insulation")

    assert node_class.VALIDATE_INPUTS({"cooler_uri": "matrix.cool", "window_sizes": ""}) == "At least one window size is required."
    assert (
        node_class.VALIDATE_INPUTS({"cooler_uri": "matrix.cool", "window_sizes": "100000", "nproc": 0})
        == "nproc must be at least 1."
    )
    assert (
        node_class.VALIDATE_INPUTS({"cooler_uri": "matrix.cool", "window_sizes": "100000", "min_frac_valid_pixels": 1.5})
        == "min_frac_valid_pixels must be between 0 and 1."
    )


def test_cooltools_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["cooltools"] == "cooltools"
    assert PACKAGE_MIN_VERSIONS["cooltools"] == ">=0.7.0"
