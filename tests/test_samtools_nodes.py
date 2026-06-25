from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_samtools_duplicate_marking_path_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    collate_info = info["samtools_collate"]
    assert collate_info["display_name"] == "Samtools Collate"
    assert collate_info["category"] == "samtools"
    assert collate_info["description"].startswith("Name-collate a BAM")
    assert collate_info["output"] == ["BAM"]
    assert collate_info["output_name"] == ["name_collated_bam"]
    assert collate_info["required_executables"] == ["samtools"]
    assert collate_info["required_conda_packages"] == ["samtools"]
    assert "markdup prerequisite" in collate_info["search_aliases"]

    fixmate_info = info["samtools_fixmate"]
    assert fixmate_info["display_name"] == "Samtools Fixmate"
    assert fixmate_info["category"] == "samtools"
    assert fixmate_info["description"].startswith("Add mate coordinates")
    assert fixmate_info["output"] == ["BAM"]
    assert fixmate_info["output_name"] == ["fixmate_bam"]
    assert fixmate_info["required_executables"] == ["samtools"]
    assert fixmate_info["required_conda_packages"] == ["samtools"]
    assert "markdup prerequisite" in fixmate_info["search_aliases"]

    assert set(collate_info["input"]["required"]) == {"bam", "threads"}
    assert set(collate_info["input"]["optional"]) == {"output_name", "temp_prefix"}
    assert set(fixmate_info["input"]["required"]) == {"bam", "threads"}
    assert set(fixmate_info["input"]["optional"]) == {"add_markdup_tags", "remove_secondary_and_unmapped", "output_name"}


def test_samtools_collate_and_fixmate_render_duplicate_marking_prerequisite_commands() -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")

    assert collate_class.render_command(
        {
            "bam": "/data/sample.aligned.bam",
            "threads": 4,
            "output": "/work/samtools_collate",
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "collate",
        "-@",
        "4",
        "-o",
        "/work/samtools_collate/sample.name_collated.bam",
        "/data/sample.aligned.bam",
    ]

    assert fixmate_class.render_command(
        {
            "bam": "/work/samtools_collate/sample.name_collated.bam",
            "threads": 4,
            "output": "/work/samtools_fixmate",
            "remove_secondary_and_unmapped": True,
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "fixmate",
        "-@",
        "4",
        "-m",
        "-r",
        "/work/samtools_collate/sample.name_collated.bam",
        "/work/samtools_fixmate/sample.fixmate.bam",
    ]


def test_samtools_collate_and_fixmate_plan_safe_named_outputs(tmp_path: Path) -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")

    collate_outputs = collate_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)
    fixmate_outputs = fixmate_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)

    assert [path.name for path in collate_outputs] == ["tumor_normal.name_collated.bam"]
    assert [path.name for path in fixmate_outputs] == ["tumor_normal.fixmate.bam"]
    assert collate_outputs[0].parent == tmp_path / "samtools_collate"
    assert fixmate_outputs[0].parent == tmp_path / "samtools_fixmate"


def test_samtools_markdup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["samtools_markdup"]
    assert node_info["display_name"] == "Samtools Markdup"
    assert node_info["category"] == "samtools"
    assert node_info["description"].startswith("Mark or remove duplicate alignments")
    assert node_info["output"] == ["BAM", "STATS_FILE"]
    assert node_info["output_name"] == ["marked_bam", "duplicate_stats"]
    assert node_info["requires_external_tools"] is True
    assert node_info["required_executables"] == ["samtools"]
    assert node_info["required_conda_packages"] == ["samtools"]
    assert "mark duplicates" in node_info["search_aliases"]
    assert "picard equivalent" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "threads"}
    assert set(inputs["optional"]) == {
        "remove_duplicates",
        "mark_supplementary",
        "mark_optical_duplicates",
        "optical_distance",
        "read_name_regex",
        "clear_existing_duplicate_flags",
        "output_name",
    }


def test_samtools_markdup_renders_default_marking_command() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.render_command(
        {
            "bam": "/data/sample.sorted.fixmate.bam",
            "threads": 8,
            "output": "/work/samtools_markdup",
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "markdup",
        "-@",
        "8",
        "-f",
        "/work/samtools_markdup/sample.duplicate_stats.txt",
        "/data/sample.sorted.fixmate.bam",
        "/work/samtools_markdup/sample.markdup.bam",
    ]


def test_samtools_markdup_renders_remove_and_optical_duplicate_options() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.render_command(
        {
            "bam": "/data/sample.bam",
            "threads": 2,
            "output": "/work/samtools_markdup",
            "remove_duplicates": True,
            "mark_supplementary": True,
            "mark_optical_duplicates": True,
            "optical_distance": 120,
            "read_name_regex": "(\\d+):(\\d+):(\\d+)",
            "clear_existing_duplicate_flags": True,
            "output_name": "tumor normal",
        }
    ) == [
        "samtools",
        "markdup",
        "-@",
        "2",
        "-r",
        "-S",
        "-d",
        "120",
        "--read-coords",
        "(\\d+):(\\d+):(\\d+)",
        "-c",
        "-f",
        "/work/samtools_markdup/tumor_normal.duplicate_stats.txt",
        "/data/sample.bam",
        "/work/samtools_markdup/tumor_normal.markdup.bam",
    ]


def test_samtools_markdup_plans_safe_named_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samtools_markdup")

    outputs = node_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)

    assert [path.name for path in outputs] == [
        "tumor_normal.markdup.bam",
        "tumor_normal.duplicate_stats.txt",
    ]
    assert outputs[0].parent == tmp_path / "samtools_markdup"
    assert outputs[0].parent.exists()


def test_samtools_markdup_infers_clean_output_stem_from_processed_bam_name(tmp_path: Path) -> None:
    node_class = _node_class("samtools_markdup")

    outputs = node_class.PLAN_OUTPUTS({"bam": "/data/sample.name_collated.fixmate.sorted.bam"}, tmp_path)

    assert [path.name for path in outputs] == [
        "sample.markdup.bam",
        "sample.duplicate_stats.txt",
    ]


def test_samtools_markdup_rejects_invalid_numeric_options() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 0}) == "threads must be between 1 and 64"
    assert (
        node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 2, "optical_distance": -1})
        == "optical_distance must be non-negative"
    )


def test_samtools_galaxy_parity_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "samtools_idxstats": {
            "display_name": "Samtools Idxstats",
            "output": ["TSV"],
            "output_name": ["idxstats"],
            "aliases": ["Galaxy", "idxstats", "MultiQC"],
        },
        "samtools_depth": {
            "display_name": "Samtools Depth",
            "output": ["TSV"],
            "output_name": ["depth"],
            "aliases": ["Galaxy", "depth", "coverage depth"],
        },
        "samtools_faidx": {
            "display_name": "Samtools Faidx",
            "output": ["TSV"],
            "output_name": ["fai_index"],
            "aliases": ["Galaxy", "faidx", "FASTA index"],
        },
        "samtools_coverage": {
            "display_name": "Samtools Coverage",
            "output": ["TSV"],
            "output_name": ["coverage"],
            "aliases": ["Galaxy", "coverage", "histogram"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "samtools"
        assert node_info["output"] == metadata["output"]
        assert node_info["output_name"] == metadata["output_name"]
        assert node_info["required_executables"] == ["samtools"]
        assert node_info["required_conda_packages"] == ["samtools"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/gigascience/giab008" in node_info["citation_urls"]
        assert "SAMtools" in node_info["citation_text"]
        for alias in metadata["aliases"]:
            assert alias in node_info["search_aliases"]


def test_samtools_idxstats_renders_index_statistics_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_idxstats")

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "threads": 5,
            "output": "/work/samtools_idxstats",
        }
    ) == [
        "samtools",
        "idxstats",
        "-@",
        "4",
        "sample.bam",
        ">",
        "/work/samtools_idxstats/idxstats.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_idxstats" / "idxstats.tsv"]


def test_samtools_depth_renders_region_filtered_depth_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_depth")

    assert node_class.render_command(
        {
            "input_bams": ["tumor.bam", "normal.bam"],
            "all": "-a",
            "input_bed": "targets.bed",
            "minlength": 75,
            "maxdepth": 10000,
            "basequality": 20,
            "mapquality": 30,
            "required_flags": [2, 64],
            "skipped_flags": [4, 256, 512, 1024],
            "deletions": True,
            "single_read": True,
            "header": True,
            "output": "/work/samtools_depth",
        }
    ) == [
        "samtools",
        "depth",
        "-a",
        "-b",
        "targets.bed",
        "-l",
        "75",
        "-m",
        "10000",
        "-q",
        "20",
        "-Q",
        "30",
        "-g",
        "66",
        "-G",
        "1796",
        "-J",
        "-s",
        "-H",
        "tumor.bam",
        "normal.bam",
        ">",
        "/work/samtools_depth/depth.tsv",
    ]

    assert node_class.render_command(
        {
            "input_bams": "tumor.bam",
            "region": "chr7:100-200",
            "output": "/work/samtools_depth",
        }
    ) == [
        "samtools",
        "depth",
        "-r",
        "chr7:100-200",
        "tumor.bam",
        ">",
        "/work/samtools_depth/depth.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_depth" / "depth.tsv"]


def test_samtools_faidx_renders_fastq_and_compressed_index_commands(tmp_path: Path) -> None:
    node_class = _node_class("samtools_faidx")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "fastq": True,
            "compressed": True,
            "output": "/work/samtools_faidx",
        }
    ) == [
        "ln",
        "-sf",
        "reads.fastq.gz",
        "/work/samtools_faidx/input.gz",
        "&&",
        "samtools",
        "faidx",
        "--fastq",
        "/work/samtools_faidx/input.gz",
        "--fai-idx",
        "/work/samtools_faidx/fai_index.tsv",
        "--gzi-idx",
        "/work/samtools_faidx/input.gz.gzi",
        "||",
        "(",
        "echo",
        "Failed to index compressed reference. Trying decompressed ...",
        "1>&2",
        "&&",
        "gzip",
        "-dc",
        "/work/samtools_faidx/input.gz",
        ">",
        "/work/samtools_faidx/input.plain",
        "&&",
        "samtools",
        "faidx",
        "--fastq",
        "/work/samtools_faidx/input.plain",
        "--fai-idx",
        "/work/samtools_faidx/fai_index.tsv",
        ")",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_faidx" / "fai_index.tsv"]


def test_samtools_coverage_renders_table_and_histogram_commands(tmp_path: Path) -> None:
    node_class = _node_class("samtools_coverage")

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "min_read_length": 50,
            "min_mq": 20,
            "min_bq": 15,
            "required_flags": [2],
            "skipped_flags": [4, 256],
            "region": "chr1:1-1000",
            "histogram": False,
            "output": "/work/samtools_coverage",
        }
    ) == [
        "samtools",
        "coverage",
        "sample.bam",
        "-l",
        "50",
        "-q",
        "20",
        "-Q",
        "15",
        "--rf",
        "2",
        "--ff",
        "260",
        "-r",
        "chr1:1-1000",
        "-o",
        "/work/samtools_coverage/coverage.tsv",
    ]

    assert node_class.render_command(
        {
            "input_bams": ["tumor.bam", "normal.bam"],
            "histogram": True,
            "n_bins": 50,
            "output": "/work/samtools_coverage",
        }
    ) == [
        "samtools",
        "coverage",
        "tumor.bam",
        "normal.bam",
        "-l",
        "0",
        "-q",
        "0",
        "-Q",
        "0",
        "-m",
        "-w",
        "50",
        "-o",
        "/work/samtools_coverage/coverage.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_coverage" / "coverage.tsv"]


def test_samtools_galaxy_parity_followup_nodes_expose_citation_and_dependency_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "samtools_bedcov": {
            "display_name": "Samtools Bedcov",
            "output": ["TSV"],
            "output_name": ["interval_coverage"],
            "aliases": ["Galaxy", "bedcov", "interval coverage"],
        },
        "samtools_calmd": {
            "display_name": "Samtools Calmd",
            "output": ["BAM"],
            "output_name": ["calmd_bam"],
            "aliases": ["Galaxy", "calmd", "MD tags", "BAQ"],
        },
        "samtools_ampliconclip": {
            "display_name": "Samtools Ampliconclip",
            "output": ["BAM", "BEDGRAPH"],
            "output_name": ["clipped_bam", "primer_counts"],
            "aliases": ["Galaxy", "ampliconclip", "primer trimming"],
        },
        "samtools_fastx": {
            "display_name": "Samtools Fastx",
            "output": ["FILE", "FILE", "FILE", "FILE", "FILE", "FILE", "FILE"],
            "output_name": ["reads", "read1", "read2", "singletons", "nonspecific", "index1", "index2"],
            "aliases": ["Galaxy", "fastx", "bam2fq", "FASTQ extraction"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "samtools"
        assert node_info["output"] == metadata["output"]
        assert node_info["output_name"] == metadata["output_name"]
        assert node_info["required_executables"] == ["samtools"]
        assert node_info["required_conda_packages"] == ["samtools"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btr076" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/gigascience/giab008" in node_info["citation_urls"]
        assert "https://doi.org/10.1093/bioinformatics/btr076" in node_info["citation_urls"]
        assert "Base Alignment Quality" in node_info["citation_text"]
        for alias in metadata["aliases"]:
            assert alias in node_info["search_aliases"]


def test_samtools_bedcov_renders_interval_coverage_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_bedcov")

    assert node_class.render_command(
        {
            "input_bed": "targets.bed",
            "input_bams": ["tumor.bam", "normal.bam"],
            "mapq": 30,
            "countdel": True,
            "required_flags": [2, 64],
            "skipped_flags": [4, 256, 512, 1024],
            "depth_thresh": 10,
            "output": "/work/samtools_bedcov",
        }
    ) == [
        "samtools",
        "bedcov",
        "-Q",
        "30",
        "-j",
        "-g",
        "66",
        "-G",
        "1796",
        "-d",
        "10",
        "targets.bed",
        "tumor.bam",
        "normal.bam",
        ">",
        "/work/samtools_bedcov/interval_coverage.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "samtools_bedcov" / "interval_coverage.tsv"
    ]


def test_samtools_calmd_renders_baq_and_advanced_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_calmd")

    assert node_class.render_command(
        {
            "input": "alignments.bam",
            "reference": "reference.fa",
            "threads": 6,
            "calculate_baq": True,
            "modify_quality": True,
            "extended_baq": True,
            "change_identical": True,
            "adjust_mq": 50,
            "output": "/work/samtools_calmd",
        }
    ) == [
        "samtools",
        "calmd",
        "-r",
        "-A",
        "-E",
        "-e",
        "-C",
        "50",
        "-b",
        "-@",
        "5",
        "alignments.bam",
        "reference.fa",
        ">",
        "/work/samtools_calmd/calmd.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_calmd" / "calmd.bam"]


def test_samtools_ampliconclip_renders_primer_clipping_pipeline_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samtools_ampliconclip")

    assert node_class.render_command(
        {
            "input_bed": "primers.bed",
            "input_bam": "amplicons.bam",
            "threads": 4,
            "memory_mb": 2048,
            "hard_clip": True,
            "strand": True,
            "both_ends": True,
            "no_excluded": True,
            "min_length": 30,
            "tolerance": 6,
            "write_primer_counts": True,
            "output": "/work/samtools_ampliconclip",
        }
    ) == [
        "samtools",
        "ampliconclip",
        "--hard-clip",
        "--fail-len",
        "30",
        "--tolerance",
        "6",
        "--strand",
        "-b",
        "primers.bed",
        "-u",
        "--both-ends",
        "--no-excluded",
        "--primer-counts",
        "/work/samtools_ampliconclip/primer_counts.bedgraph",
        "-@",
        "3",
        "amplicons.bam",
        "|",
        "samtools",
        "collate",
        "-@",
        "3",
        "-O",
        "-u",
        "-",
        "|",
        "samtools",
        "fixmate",
        "-@",
        "3",
        "-u",
        "-",
        "-",
        "|",
        "samtools",
        "sort",
        "-@",
        "3",
        "-m",
        "1536M",
        "-T",
        "/work/samtools_ampliconclip/tmp",
        "-o",
        "/work/samtools_ampliconclip/clipped.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "samtools_ampliconclip" / "clipped.bam",
        tmp_path / "samtools_ampliconclip" / "primer_counts.bedgraph",
    ]


def test_samtools_fastx_renders_split_fastq_extraction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samtools_fastx")

    assert node_class.render_command(
        {
            "input": "reads.name_sorted.bam",
            "threads": 8,
            "memory_mb": 1600,
            "name_sorted": True,
            "output_format": "fastq",
            "outputs": ["read1", "read2", "singletons", "other"],
            "default_quality": 30,
            "output_quality": True,
            "illumina_casava": True,
            "copy_tags": True,
            "copy_arbitrary_tags": "MD,ia",
            "read_numbering": "-N",
            "required_flags": [1],
            "skipped_flags": [256, 2048],
            "skipped_flags_all": [4, 8],
            "write_index_reads": True,
            "write_i1": True,
            "write_i2": False,
            "index_format": "n2i2",
            "barcode_tag": "BC",
            "quality_tag": "QT",
            "output": "/work/samtools_fastx",
        }
    ) == [
        "ln",
        "-sf",
        "reads.name_sorted.bam",
        "/work/samtools_fastx/input",
        "&&",
        "samtools",
        "fastq",
        "-@",
        "7",
        "-v",
        "30",
        "-O",
        "-i",
        "-t",
        "-T",
        "MD,ia",
        "-N",
        "-1",
        "/work/samtools_fastx/read1.fastq",
        "-2",
        "/work/samtools_fastx/read2.fastq",
        "-s",
        "/work/samtools_fastx/singletons.fastq",
        "-f",
        "1",
        "-F",
        "2304",
        "-G",
        "12",
        "--i1",
        "/work/samtools_fastx/i1.fastq",
        "--index-format",
        "n2i2",
        "--barcode-tag",
        "BC",
        "--quality-tag",
        "QT",
        "/work/samtools_fastx/input",
        ">",
        "/work/samtools_fastx/reads.fastq",
    ]

    assert node_class.PLAN_OUTPUTS({"output_format": "fastq"}, tmp_path) == [
        tmp_path / "samtools_fastx" / "reads.fastq",
        tmp_path / "samtools_fastx" / "read1.fastq",
        tmp_path / "samtools_fastx" / "read2.fastq",
        tmp_path / "samtools_fastx" / "singletons.fastq",
        tmp_path / "samtools_fastx" / "nonspecific.fastq",
        tmp_path / "samtools_fastx" / "index1.fastq",
        tmp_path / "samtools_fastx" / "index2.fastq",
    ]
