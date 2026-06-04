from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.builtin.long_read import MedakaConsensusNode
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


def test_medaka_alias_is_registered_by_builtin_loading() -> None:
    registry = NodeRegistry.create_isolated()

    registry.load_builtin_nodes()

    alias = registry.get("medaka")
    assert alias is not None
    assert issubclass(alias, MedakaConsensusNode)


def test_medaka_alias_overrides_only_planner_and_search_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("medaka")
    assert alias is not None

    assert alias.NODE_ID == "medaka"
    assert alias.DISPLAY_NAME == "Medaka"
    assert alias.DESCRIPTION == "Polish Oxford Nanopore draft assemblies with Medaka."
    assert {
        "medaka",
        "medaka consensus",
        "polish",
        "consensus",
        "nanopore",
        "assembly polish",
    }.issubset(alias.SEARCH_ALIASES)

    assert alias.CATEGORY == MedakaConsensusNode.CATEGORY
    assert alias.RETURN_TYPES == MedakaConsensusNode.RETURN_TYPES
    assert alias.RETURN_NAMES == MedakaConsensusNode.RETURN_NAMES
    assert alias.REQUIRED_EXECUTABLES == MedakaConsensusNode.REQUIRED_EXECUTABLES
    assert alias.REQUIRED_CONDA_PACKAGES == MedakaConsensusNode.REQUIRED_CONDA_PACKAGES
    assert alias.DOCUMENTATION_URL == MedakaConsensusNode.DOCUMENTATION_URL
    assert alias.VERSION == MedakaConsensusNode.VERSION
    assert alias.SHELL == MedakaConsensusNode.SHELL
    assert alias.INPUT_TYPES() == MedakaConsensusNode.INPUT_TYPES()
    assert alias.render_command.__func__ is MedakaConsensusNode.render_command.__func__
    assert alias.PLAN_OUTPUTS.__func__ is MedakaConsensusNode.PLAN_OUTPUTS.__func__


def test_medaka_alias_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["medaka"]
    assert node_info["display_name"] == "Medaka"
    assert node_info["category"] == "long_read"
    assert node_info["description"] == "Polish Oxford Nanopore draft assemblies with Medaka."
    assert node_info["output"] == ["FASTA"]
    assert node_info["output_name"] == ["polished_assembly"]
    assert node_info["required_executables"] == ["medaka_consensus"]
    assert node_info["required_conda_packages"] == ["medaka"]
    assert {
        "medaka",
        "medaka consensus",
        "polish",
        "consensus",
        "nanopore",
        "assembly polish",
    }.issubset(node_info["search_aliases"])

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "draft", "threads"}
    assert set(inputs["optional"]) == {"model", "bam"}


def test_medaka_alias_renders_polishing_command_and_plans_alias_output_path() -> None:
    node_class = _node_class("medaka")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "draft": "draft.fasta",
        "threads": 12,
        "model": "r1041_e82_400_sup_v5.0.0",
        "bam": "alignment.bam",
        "output": "/tmp/run/medaka",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "medaka_consensus",
        "-i",
        "reads.fastq.gz",
        "-d",
        "draft.fasta",
        "-o",
        "/tmp/run/medaka",
        "-t",
        "12",
        "-m",
        "r1041_e82_400_sup_v5.0.0",
        "-b",
        "alignment.bam",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/medaka/consensus.fasta"]


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


def test_dorado_correct_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dorado_correct"]
    assert node_info["display_name"] == "Dorado Correct"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Correct ONT reads with Dorado HERRO")
    assert node_info["output"] == ["FASTQ"]
    assert node_info["output_name"] == ["corrected_reads"]
    assert node_info["required_executables"] == ["dorado"]
    assert node_info["required_conda_packages"] == ["dorado"]
    assert node_info["experimental"] is True
    assert "herro" in node_info["search_aliases"]
    assert "read correction" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "threads"}
    assert set(inputs["optional"]) == {"device"}


def test_dorado_correct_renders_herro_command() -> None:
    node_class = _node_class("dorado_correct")

    cmd = node_class.render_command({
        "reads": "reads.fastq",
        "threads": 8,
        "device": "cuda:0",
        "output": "/tmp/run/dorado_correct",
    })

    assert cmd == [
        "dorado",
        "correct",
        "-t",
        "8",
        "--device",
        "cuda:0",
        "reads.fastq",
        ">",
        "/tmp/run/dorado_correct/corrected_reads.fastq",
    ]


def test_dorado_correct_omits_empty_optional_flags() -> None:
    node_class = _node_class("dorado_correct")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "threads": 4,
        "device": "",
        "output": "/tmp/run/dorado_correct",
    })

    assert "--device" not in cmd
    assert cmd == [
        "dorado",
        "correct",
        "-t",
        "4",
        "reads.fastq.gz",
        ">",
        "/tmp/run/dorado_correct/corrected_reads.fastq",
    ]


def test_dorado_correct_plans_corrected_fastq_output() -> None:
    node_class = _node_class("dorado_correct")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/dorado_correct/corrected_reads.fastq"]


def test_dorado_correct_validation_rejects_empty_reads_and_invalid_threads() -> None:
    node_class = _node_class("dorado_correct")

    assert node_class.VALIDATE_INPUTS({"reads": "", "threads": 4}) == "reads is required."
    assert node_class.VALIDATE_INPUTS({"reads": "reads.fastq", "threads": 0}) == "threads must be at least 1."


def test_dorado_correct_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["dorado"] == "dorado"
    assert PACKAGE_MIN_VERSIONS["dorado"] == ">=0.9.6"
    assert workflow_to_packages({"nodes": [{"id": "correct", "type": "dorado_correct"}]}, registry) == ["dorado"]


def test_dorado_demux_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dorado_demux"]
    assert node_info["display_name"] == "Dorado Demux"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Demultiplex ONT reads")
    assert node_info["output"] == ["DIRECTORY", "TSV"]
    assert node_info["output_name"] == ["demux_dir", "barcode_summary"]
    assert node_info["required_executables"] == ["dorado"]
    assert node_info["required_conda_packages"] == ["dorado"]
    assert node_info["experimental"] is True
    assert "barcoding" in node_info["search_aliases"]
    assert "demultiplex" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "mode"}
    assert set(inputs["optional"]) == {
        "kit_name",
        "sample_sheet",
        "barcode_arrangement",
        "barcode_sequences",
        "emit_fastq",
        "emit_summary",
        "no_trim",
        "sort_bam",
        "recursive",
        "threads",
        "output_name",
    }


def test_dorado_demux_renders_classify_and_demux_command() -> None:
    node_class = _node_class("dorado_demux")

    cmd = node_class.render_command({
        "reads": "calls.bam",
        "mode": "classify",
        "kit_name": "SQK-NBD114-24",
        "sample_sheet": "samples.csv",
        "barcode_arrangement": "arrangement.toml",
        "barcode_sequences": "barcodes.fasta",
        "emit_fastq": True,
        "emit_summary": True,
        "no_trim": True,
        "sort_bam": False,
        "recursive": True,
        "threads": 6,
        "output_name": "run one",
        "output": "/tmp/run/dorado_demux",
    })

    assert cmd == [
        "dorado",
        "demux",
        "--output-dir",
        "/tmp/run/dorado_demux/run_one",
        "--kit-name",
        "SQK-NBD114-24",
        "--sample-sheet",
        "samples.csv",
        "--barcode-arrangement",
        "arrangement.toml",
        "--barcode-sequences",
        "barcodes.fasta",
        "--emit-fastq",
        "--emit-summary",
        "--no-trim",
        "--recursive",
        "--threads",
        "6",
        "calls.bam",
    ]


def test_dorado_demux_renders_no_classify_split_command() -> None:
    node_class = _node_class("dorado_demux")

    cmd = node_class.render_command({
        "reads": "/data/basecalled.bam",
        "mode": "split",
        "kit_name": "",
        "emit_fastq": False,
        "emit_summary": False,
        "no_trim": True,
        "sort_bam": True,
        "recursive": False,
        "threads": 0,
        "output_name": "",
        "output": "/tmp/run/dorado_demux",
    })

    assert "--kit-name" not in cmd
    assert "--emit-fastq" not in cmd
    assert "--emit-summary" not in cmd
    assert "--threads" not in cmd
    assert cmd == [
        "dorado",
        "demux",
        "--output-dir",
        "/tmp/run/dorado_demux/basecalled_demux",
        "--no-classify",
        "--no-trim",
        "--sort-bam",
        "/data/basecalled.bam",
    ]


def test_dorado_demux_plans_output_directory_and_summary() -> None:
    node_class = _node_class("dorado_demux")

    outputs = node_class.PLAN_OUTPUTS(
        {"reads": "/data/calls.bam", "output_name": "run one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/dorado_demux/run_one",
        "/tmp/run/dorado_demux/run_one/barcode_summary.tsv",
    ]


def test_dorado_demux_validation_rejects_invalid_mode_and_missing_kit() -> None:
    node_class = _node_class("dorado_demux")

    assert node_class.VALIDATE_INPUTS({
        "reads": "calls.bam",
        "mode": "trim",
    }) == "Unsupported Dorado demux mode: trim"
    assert node_class.VALIDATE_INPUTS({
        "reads": "calls.bam",
        "mode": "classify",
        "kit_name": "",
    }) == "kit_name is required when mode is classify."
    assert node_class.VALIDATE_INPUTS({
        "reads": "calls.bam",
        "mode": "split",
        "kit_name": "SQK-NBD114-24",
    }) == "kit_name cannot be used when mode is split."
    assert node_class.VALIDATE_INPUTS({
        "reads": "calls.bam",
        "mode": "split",
        "sort_bam": True,
        "no_trim": False,
    }) == "sort_bam requires no_trim so mapped reads remain valid."


def test_dorado_duplex_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dorado_duplex"]
    assert node_info["display_name"] == "Dorado Duplex"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Duplex basecalling")
    assert node_info["output"] == ["BAM"]
    assert node_info["output_name"] == ["duplex_bam"]
    assert node_info["required_executables"] == ["dorado"]
    assert node_info["required_conda_packages"] == ["dorado"]
    assert node_info["experimental"] is True
    assert "double-strand" in node_info["search_aliases"]
    assert "high accuracy" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"pod5_dir", "model"}
    assert set(inputs["optional"]) == {"modified_bases", "threads"}


def test_dorado_duplex_renders_duplex_command() -> None:
    node_class = _node_class("dorado_duplex")

    cmd = node_class.render_command({
        "pod5_dir": "pod5/",
        "model": "sup@latest",
        "threads": 8,
        "modified_bases": "5mC 6mA",
        "output": "/tmp/run/dorado_duplex",
    })

    assert cmd == [
        "dorado",
        "duplex",
        "sup@latest",
        "pod5/",
        "-t",
        "8",
        "--modified-bases",
        "5mC",
        "6mA",
        ">",
        "/tmp/run/dorado_duplex/duplex_bam.bam",
    ]


def test_dorado_duplex_omits_empty_optional_flags() -> None:
    node_class = _node_class("dorado_duplex")

    cmd = node_class.render_command({
        "pod5_dir": "pod5/",
        "model": "hac@latest",
        "threads": 4,
        "modified_bases": "",
        "output": "/tmp/run/dorado_duplex",
    })

    assert cmd == [
        "dorado",
        "duplex",
        "hac@latest",
        "pod5/",
        "-t",
        "4",
        ">",
        "/tmp/run/dorado_duplex/duplex_bam.bam",
    ]


def test_dorado_duplex_plans_bam_output() -> None:
    node_class = _node_class("dorado_duplex")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/dorado_duplex/duplex_bam.bam"]
