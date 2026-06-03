from __future__ import annotations

from pathlib import Path

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
