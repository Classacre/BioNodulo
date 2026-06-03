from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_modkit_pileup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["modkit_pileup"]
    assert node_info["display_name"] == "Modkit Pileup"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Generate bedMethyl pileup")
    assert node_info["output"] == ["BED"]
    assert node_info["output_name"] == ["bedmethyl"]
    assert node_info["required_executables"] == ["modkit"]
    assert node_info["required_conda_packages"] == ["modkit"]
    assert "methylation" in node_info["search_aliases"]
    assert "bedmethyl" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "threads"}
    assert set(inputs["optional"]) == {"combine_strands", "region", "bedgraph"}


def test_modkit_pileup_renders_bedmethyl_command() -> None:
    node_class = _node_class("modkit_pileup")

    cmd = node_class.render_command({
        "bam": "calls.bam",
        "reference": "hg38.fa",
        "threads": 12,
        "combine_strands": True,
        "region": "chr1:1-1000000",
        "bedgraph": True,
        "output": "/tmp/run/modkit_pileup",
    })

    assert cmd == [
        "modkit",
        "pileup",
        "calls.bam",
        "/tmp/run/modkit_pileup/bedmethyl.bed",
        "--ref",
        "hg38.fa",
        "--threads",
        "12",
        "--combine-strands",
        "--region",
        "chr1:1-1000000",
        "--bedgraph",
    ]


def test_modkit_pileup_omits_empty_optional_flags() -> None:
    node_class = _node_class("modkit_pileup")

    cmd = node_class.render_command({
        "bam": "calls.bam",
        "reference": "hg38.fa",
        "threads": 4,
        "combine_strands": False,
        "region": "",
        "bedgraph": False,
        "output": "/tmp/run/modkit_pileup",
    })

    assert cmd == [
        "modkit",
        "pileup",
        "calls.bam",
        "/tmp/run/modkit_pileup/bedmethyl.bed",
        "--ref",
        "hg38.fa",
        "--threads",
        "4",
    ]


def test_modkit_pileup_plans_bed_output() -> None:
    node_class = _node_class("modkit_pileup")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/modkit_pileup/bedmethyl.bed"]


def test_chopper_filter_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["chopper_filter"]
    assert node_info["display_name"] == "Chopper Filter"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Filter and trim ONT reads")
    assert node_info["output"] == ["FASTQ"]
    assert node_info["output_name"] == ["filtered_reads"]
    assert node_info["required_executables"] == ["chopper"]
    assert node_info["required_conda_packages"] == ["chopper"]
    assert "nanopore" in node_info["search_aliases"]
    assert "quality filter" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads"}
    assert set(inputs["optional"]) == {
        "min_quality",
        "min_length",
        "max_length",
        "headcrop",
        "tailcrop",
        "threads",
    }


def test_chopper_filter_renders_filter_command() -> None:
    node_class = _node_class("chopper_filter")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "min_quality": 12,
        "min_length": 1000,
        "max_length": 50000,
        "headcrop": 25,
        "tailcrop": 10,
        "threads": 8,
        "output": "/tmp/run/chopper_filter",
    })

    assert cmd == [
        "chopper",
        "-i",
        "reads.fastq.gz",
        "-q",
        "12",
        "-l",
        "1000",
        "--maxlength",
        "50000",
        "--headcrop",
        "25",
        "--tailcrop",
        "10",
        "-t",
        "8",
        ">",
        "/tmp/run/chopper_filter/filtered_reads.fastq.gz",
    ]


def test_chopper_filter_omits_zero_optional_flags() -> None:
    node_class = _node_class("chopper_filter")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "min_quality": 0,
        "min_length": 0,
        "max_length": 0,
        "headcrop": 0,
        "tailcrop": 0,
        "threads": 0,
        "output": "/tmp/run/chopper_filter",
    })

    assert cmd == [
        "chopper",
        "-i",
        "reads.fastq.gz",
        ">",
        "/tmp/run/chopper_filter/filtered_reads.fastq.gz",
    ]


def test_chopper_filter_plans_fastq_output() -> None:
    node_class = _node_class("chopper_filter")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/chopper_filter/filtered_reads.fastq.gz"]


def test_nanoplot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["nanoplot"]
    assert node_info["display_name"] == "NanoPlot QC"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("QC plots for ONT and PacBio")
    assert node_info["output"] == ["HTML_REPORT", "STATS_FILE"]
    assert node_info["output_name"] == ["qc_report", "qc_stats"]
    assert node_info["required_executables"] == ["NanoPlot"]
    assert node_info["required_conda_packages"] == ["nanoplot"]
    assert "nanopore" in node_info["search_aliases"]
    assert "read stats" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"fastq"}
    assert set(inputs["optional"]) == {
        "bam",
        "summary",
        "threads",
        "plot_format",
        "max_length",
        "min_length",
        "loglength",
    }


def test_nanoplot_renders_fastq_qc_command() -> None:
    node_class = _node_class("nanoplot")

    cmd = node_class.render_command({
        "fastq": "reads.fastq.gz",
        "bam": "",
        "summary": "",
        "threads": 8,
        "plot_format": "png",
        "max_length": 50000,
        "min_length": 1000,
        "loglength": True,
        "output": "/tmp/run/nanoplot",
    })

    assert cmd == [
        "NanoPlot",
        "--outdir",
        "/tmp/run/nanoplot",
        "--threads",
        "8",
        "--format",
        "png",
        "--N50",
        "--fastq",
        "reads.fastq.gz",
        "--maxlength",
        "50000",
        "--minlength",
        "1000",
        "--loglength",
    ]


def test_nanoplot_renders_alternative_input_commands() -> None:
    node_class = _node_class("nanoplot")

    bam_cmd = node_class.render_command({
        "fastq": "",
        "bam": "calls.bam",
        "summary": "",
        "threads": 4,
        "plot_format": "pdf",
        "output": "/tmp/run/nanoplot",
    })
    summary_cmd = node_class.render_command({
        "fastq": "",
        "bam": "",
        "summary": "sequencing_summary.txt",
        "threads": 4,
        "plot_format": "jpg",
        "output": "/tmp/run/nanoplot",
    })

    assert bam_cmd == [
        "NanoPlot",
        "--outdir",
        "/tmp/run/nanoplot",
        "--threads",
        "4",
        "--format",
        "pdf",
        "--N50",
        "--bam",
        "calls.bam",
    ]
    assert summary_cmd == [
        "NanoPlot",
        "--outdir",
        "/tmp/run/nanoplot",
        "--threads",
        "4",
        "--format",
        "jpg",
        "--N50",
        "--summary",
        "sequencing_summary.txt",
    ]


def test_nanoplot_omits_empty_optional_flags() -> None:
    node_class = _node_class("nanoplot")

    cmd = node_class.render_command({
        "fastq": "reads.fastq.gz",
        "bam": "",
        "summary": "",
        "threads": 4,
        "plot_format": "png",
        "max_length": 0,
        "min_length": 0,
        "loglength": False,
        "output": "/tmp/run/nanoplot",
    })

    assert cmd == [
        "NanoPlot",
        "--outdir",
        "/tmp/run/nanoplot",
        "--threads",
        "4",
        "--format",
        "png",
        "--N50",
        "--fastq",
        "reads.fastq.gz",
    ]


def test_nanoplot_plans_real_output_names() -> None:
    node_class = _node_class("nanoplot")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/nanoplot/NanoPlot-report.html",
        "/tmp/run/nanoplot/NanoStats.txt",
    ]


def test_medaka_consensus_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["medaka_consensus"]
    assert node_info["display_name"] == "Medaka Consensus"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Neural network polishing")
    assert node_info["output"] == ["FASTA"]
    assert node_info["output_name"] == ["polished_assembly"]
    assert node_info["required_executables"] == ["medaka_consensus"]
    assert node_info["required_conda_packages"] == ["medaka"]
    assert "nanopore" in node_info["search_aliases"]
    assert "assembly polish" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "draft", "threads"}
    assert set(inputs["optional"]) == {"model", "bam"}


def test_medaka_consensus_renders_polishing_command() -> None:
    node_class = _node_class("medaka_consensus")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "draft": "draft.fasta",
        "threads": 12,
        "model": "r1041_e82_400_sup_v5.0.0",
        "bam": "alignment.bam",
        "output": "/tmp/run/medaka_consensus",
    })

    assert cmd == [
        "medaka_consensus",
        "-i",
        "reads.fastq.gz",
        "-d",
        "draft.fasta",
        "-o",
        "/tmp/run/medaka_consensus",
        "-t",
        "12",
        "-m",
        "r1041_e82_400_sup_v5.0.0",
        "-b",
        "alignment.bam",
    ]


def test_medaka_consensus_omits_empty_optional_flags() -> None:
    node_class = _node_class("medaka_consensus")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "draft": "draft.fasta",
        "threads": 4,
        "model": "",
        "bam": "",
        "output": "/tmp/run/medaka_consensus",
    })

    assert cmd == [
        "medaka_consensus",
        "-i",
        "reads.fastq.gz",
        "-d",
        "draft.fasta",
        "-o",
        "/tmp/run/medaka_consensus",
        "-t",
        "4",
    ]


def test_medaka_consensus_plans_consensus_fasta_output() -> None:
    node_class = _node_class("medaka_consensus")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/medaka_consensus/consensus.fasta"]


def test_dorado_basecaller_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dorado_basecaller"]
    assert node_info["display_name"] == "Dorado Basecaller"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Basecall ONT POD5 reads")
    assert node_info["output"] == ["BAM"]
    assert node_info["output_name"] == ["basecalled_bam"]
    assert node_info["required_executables"] == ["dorado"]
    assert node_info["required_conda_packages"] == ["dorado"]
    assert node_info["experimental"] is True
    assert "modified bases" in node_info["search_aliases"]
    assert "methylation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"pod5_dir", "model"}
    assert set(inputs["optional"]) == {
        "modified_bases",
        "kit_name",
        "trim",
        "min_qscore",
        "reference",
    }


def test_dorado_basecaller_renders_basecalling_command() -> None:
    node_class = _node_class("dorado_basecaller")

    cmd = node_class.render_command({
        "pod5_dir": "pod5/",
        "model": "sup@latest",
        "modified_bases": "5mC 6mA",
        "kit_name": "SQK-NBD114-24",
        "trim": "adapters",
        "min_qscore": 10,
        "reference": "hg38.fa",
        "output": "/tmp/run/dorado_basecaller",
    })

    assert cmd == [
        "dorado",
        "basecaller",
        "sup@latest",
        "pod5/",
        "--modified-bases",
        "5mC",
        "6mA",
        "--kit-name",
        "SQK-NBD114-24",
        "--trim",
        "adapters",
        "--min-qscore",
        "10",
        "--reference",
        "hg38.fa",
        ">",
        "/tmp/run/dorado_basecaller/basecalled_bam.bam",
    ]


def test_dorado_basecaller_omits_empty_optional_flags() -> None:
    node_class = _node_class("dorado_basecaller")

    cmd = node_class.render_command({
        "pod5_dir": "pod5/",
        "model": "hac@latest",
        "modified_bases": "",
        "kit_name": "",
        "trim": "",
        "min_qscore": 0,
        "reference": "",
        "output": "/tmp/run/dorado_basecaller",
    })

    assert cmd == [
        "dorado",
        "basecaller",
        "hac@latest",
        "pod5/",
        ">",
        "/tmp/run/dorado_basecaller/basecalled_bam.bam",
    ]


def test_dorado_basecaller_plans_bam_output() -> None:
    node_class = _node_class("dorado_basecaller")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/dorado_basecaller/basecalled_bam.bam"]
