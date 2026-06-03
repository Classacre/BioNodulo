from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_bismark_align_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bismark_align"]
    assert node_info["display_name"] == "Bismark Align"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Align bisulfite sequencing reads")
    assert node_info["output"] == ["BAM"]
    assert node_info["output_name"] == ["aligned_bam"]
    assert node_info["required_executables"] == ["bismark"]
    assert node_info["required_conda_packages"] == ["bismark"]
    assert "bisulfite" in node_info["search_aliases"]
    assert "methylation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"r1", "genome_folder", "parallel_instances"}
    assert set(inputs["optional"]) == {"r2", "non_directional"}


def test_bismark_align_renders_paired_end_command() -> None:
    node_class = _node_class("bismark_align")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "r2": "sample_R2.fastq.gz",
        "genome_folder": "bismark_genome/",
        "parallel_instances": 4,
        "non_directional": True,
        "output": "/tmp/run/bismark_align",
    })

    assert cmd == [
        "bismark",
        "--genome",
        "bismark_genome/",
        "-o",
        "/tmp/run/bismark_align",
        "--parallel",
        "4",
        "-p",
        "-1",
        "sample_R1.fastq.gz",
        "-2",
        "sample_R2.fastq.gz",
        "--non_directional",
    ]


def test_bismark_align_renders_single_end_command() -> None:
    node_class = _node_class("bismark_align")

    cmd = node_class.render_command({
        "r1": "sample.fastq.gz",
        "r2": "",
        "genome_folder": "bismark_genome/",
        "parallel_instances": 1,
        "non_directional": False,
        "output": "/tmp/run/bismark_align",
    })

    assert cmd == [
        "bismark",
        "--genome",
        "bismark_genome/",
        "-o",
        "/tmp/run/bismark_align",
        "--parallel",
        "1",
        "-p",
        "sample.fastq.gz",
    ]


def test_bismark_align_plans_bam_output() -> None:
    node_class = _node_class("bismark_align")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/bismark_align/aligned_bam.bam"]


def test_bismark_methylation_extractor_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bismark_methylation_extractor"]
    assert node_info["display_name"] == "Bismark Methylation Extractor"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Extract methylation calls")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["methylation_output"]
    assert node_info["required_executables"] == ["bismark_methylation_extractor"]
    assert node_info["required_conda_packages"] == ["bismark"]
    assert "bedgraph" in node_info["search_aliases"]
    assert "methylation" in node_info["search_aliases"]
    assert "cytosine" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "multicore"}
    assert set(inputs["optional"]) == {"cytosine_report", "genome_folder", "no_overlap", "merge_non_cpg"}


def test_bismark_methylation_extractor_renders_default_command() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "multicore": 4,
        "cytosine_report": True,
        "genome_folder": "bismark_genome/",
        "no_overlap": True,
        "merge_non_cpg": False,
        "output": "/tmp/run/bismark_methylation_extractor",
    })

    assert cmd == [
        "bismark_methylation_extractor",
        "--bedGraph",
        "--comprehensive",
        "--gzip",
        "--multicore",
        "4",
        "--output",
        "/tmp/run/bismark_methylation_extractor",
        "--cytosine_report",
        "--genome_folder",
        "bismark_genome/",
        "--no_overlap",
        "sample.bam",
    ]


def test_bismark_methylation_extractor_omits_optional_flags() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "multicore": 1,
        "cytosine_report": False,
        "no_overlap": False,
        "merge_non_cpg": True,
        "output": "/tmp/run/bismark_methylation_extractor",
    })

    assert cmd == [
        "bismark_methylation_extractor",
        "--bedGraph",
        "--comprehensive",
        "--gzip",
        "--multicore",
        "1",
        "--output",
        "/tmp/run/bismark_methylation_extractor",
        "--merge_non_CpG",
        "sample.bam",
    ]


def test_bismark_methylation_extractor_plans_output_directory() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/bismark_methylation_extractor/methylation_output"]


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
    assert set(inputs["required"]) == {"bam", "threads", "normalize_using"}
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
