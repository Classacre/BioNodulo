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
    assert "queryname" in collate_info["search_aliases"]

    fixmate_info = info["samtools_fixmate"]
    assert fixmate_info["display_name"] == "Samtools Fixmate"
    assert fixmate_info["category"] == "samtools"
    assert fixmate_info["description"].startswith("Add mate coordinates")
    assert fixmate_info["output"] == ["BAM"]
    assert fixmate_info["output_name"] == ["fixmate_bam"]
    assert fixmate_info["required_executables"] == ["samtools"]
    assert fixmate_info["required_conda_packages"] == ["samtools"]
    assert "markdup" in fixmate_info["search_aliases"]

    assert set(collate_info["input"]["required"]) == {"bam", "threads"}
    assert set(collate_info["input"]["optional"]) == set()
    assert set(fixmate_info["input"]["required"]) == {"bam", "threads"}
    assert set(fixmate_info["input"]["optional"]) == {
        "add_markdup_tags",
        "remove_secondary_unmapped",
    }


def test_samtools_collate_and_fixmate_render_duplicate_marking_prerequisite_commands() -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")
    collated_bam = "/work/samtools_collate/name_collated_bam.bam"

    assert collate_class.render_command(
        {
            "bam": "/data/sample.aligned.bam",
            "threads": 4,
            "output": "/work/samtools_collate",
        }
    ) == [
        "samtools",
        "collate",
        "-@",
        "4",
        "-T",
        "/work/samtools_collate/tmp",
        "-o",
        collated_bam,
        "/data/sample.aligned.bam",
    ]

    assert fixmate_class.render_command(
        {
            "bam": collated_bam,
            "threads": 4,
            "output": "/work/samtools_fixmate",
            "add_markdup_tags": True,
            "remove_secondary_unmapped": True,
        }
    ) == [
        "samtools",
        "fixmate",
        "-@",
        "4",
        "-m",
        "-r",
        collated_bam,
        "/work/samtools_fixmate/fixmate_bam.bam",
    ]


def test_samtools_collate_and_fixmate_plan_fixed_composable_outputs(tmp_path: Path) -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")

    collate_outputs = collate_class.PLAN_OUTPUTS({"bam": "/data/tumor.bam"}, tmp_path)
    fixmate_outputs = fixmate_class.PLAN_OUTPUTS(
        {"bam": str(collate_outputs[0])},
        tmp_path,
    )

    assert collate_outputs == [
        tmp_path / "samtools_collate" / "name_collated_bam.bam"
    ]
    assert fixmate_outputs == [
        tmp_path / "samtools_fixmate" / "fixmate_bam.bam"
    ]


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
    assert "remove duplicates" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "threads"}
    assert set(inputs["optional"]) == {
        "remove_duplicates",
        "mark_supplementary",
        "optical_distance",
        "read_coords",
        "clear_existing",
    }


def test_samtools_markdup_renders_default_marking_command() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.render_command(
        {
            "bam": "/data/sample.sorted.fixmate.bam",
            "threads": 8,
            "output": "/work/samtools_markdup",
        }
    ) == [
        "samtools",
        "markdup",
        "-@",
        "8",
        "-f",
        "/work/samtools_markdup/duplicate_stats.stats.txt",
        "/data/sample.sorted.fixmate.bam",
        "/work/samtools_markdup/marked_bam.bam",
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
            "optical_distance": 120,
            "read_coords": "(\\d+):(\\d+):(\\d+)",
            "clear_existing": True,
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
        "/work/samtools_markdup/duplicate_stats.stats.txt",
        "/data/sample.bam",
        "/work/samtools_markdup/marked_bam.bam",
    ]


def test_samtools_markdup_plans_fixed_outputs_for_distinct_input_stems(tmp_path: Path) -> None:
    node_class = _node_class("samtools_markdup")
    expected_outputs = [
        tmp_path / "samtools_markdup" / "marked_bam.bam",
        tmp_path / "samtools_markdup" / "duplicate_stats.stats.txt",
    ]

    tumor_outputs = node_class.PLAN_OUTPUTS({"bam": "/data/tumor.bam"}, tmp_path)
    normal_outputs = node_class.PLAN_OUTPUTS(
        {"bam": "/data/normal.name_collated.fixmate.sorted.bam"},
        tmp_path,
    )

    assert tumor_outputs == expected_outputs
    assert normal_outputs == expected_outputs
    assert expected_outputs[0].parent.exists()


def test_samtools_markdup_rejects_invalid_numeric_options() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 0}) == "threads must be between 1 and 64"
    assert (
        node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 2, "optical_distance": -1})
        == "optical_distance must be non-negative"
    )


def test_samtools_bionodulo_builtin_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "samtools_idxstats": {
            "display_name": "Samtools Idxstats",
            "output": ["TSV"],
            "output_name": ["idxstats"],
            "aliases": ["BioNodulo builtin", "idxstats", "MultiQC"],
        },
        "samtools_depth": {
            "display_name": "Samtools Depth",
            "output": ["TSV"],
            "output_name": ["depth"],
            "aliases": ["BioNodulo builtin", "depth", "coverage depth"],
        },
        "samtools_faidx": {
            "display_name": "Samtools Faidx",
            "output": ["FASTA", "FASTA_INDEX", "SEQUENCE_DICTIONARY"],
            "output_name": ["reference", "fai_index", "sequence_dictionary"],
            "aliases": ["BioNodulo builtin", "faidx", "FASTA index", "sequence dictionary"],
        },
        "samtools_coverage": {
            "display_name": "Samtools Coverage",
            "output": ["TSV"],
            "output_name": ["coverage"],
            "aliases": ["BioNodulo builtin", "coverage", "histogram"],
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


def test_samtools_faidx_renders_reference_sidecar_commands(tmp_path: Path) -> None:
    node_class = _node_class("samtools_faidx")

    assert node_class.render_command(
        {
            "reference": "/work/samtools_faidx/reference.fa",
            "threads": 1,
            "output": "/work/samtools_faidx",
        }
    ) == [
        "samtools",
        "faidx",
        "-@",
        "1",
        "--fai-idx",
        "/work/samtools_faidx/reference.fa.fai",
        "/work/samtools_faidx/reference.fa",
        "&&",
        "samtools",
        "dict",
        "-u",
        "file:reference.fa",
        "-o",
        "/work/samtools_faidx/reference.dict",
        "/work/samtools_faidx/reference.fa",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "samtools_faidx" / "reference.fa",
        tmp_path / "samtools_faidx" / "reference.fa.fai",
        tmp_path / "samtools_faidx" / "reference.dict",
    ]


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


def test_samtools_bionodulo_builtin_followup_nodes_expose_citation_and_dependency_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "samtools_bedcov": {
            "display_name": "Samtools Bedcov",
            "output": ["TSV"],
            "output_name": ["interval_coverage"],
            "aliases": ["BioNodulo builtin", "bedcov", "interval coverage"],
        },
        "samtools_calmd": {
            "display_name": "Samtools Calmd",
            "output": ["BAM"],
            "output_name": ["calmd_bam"],
            "aliases": ["BioNodulo builtin", "calmd", "MD tags", "BAQ"],
        },
        "samtools_ampliconclip": {
            "display_name": "Samtools Ampliconclip",
            "output": ["BAM", "BEDGRAPH"],
            "output_name": ["clipped_bam", "primer_counts"],
            "aliases": ["BioNodulo builtin", "ampliconclip", "primer trimming"],
        },
        "samtools_fastx": {
            "display_name": "Samtools Fastx",
            "output": ["FILE", "FILE", "FILE", "FILE", "FILE", "FILE", "FILE"],
            "output_name": ["reads", "read1", "read2", "singletons", "nonspecific", "index1", "index2"],
            "aliases": ["BioNodulo builtin", "fastx", "bam2fq", "FASTQ extraction"],
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


def test_samtools_bionodulo_builtin_remaining_nodes_expose_citation_and_dependency_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "samtools_mpileup": {
            "display_name": "Samtools Mpileup",
            "output": ["FILE"],
            "output_name": ["pileup"],
            "aliases": ["BioNodulo builtin", "mpileup", "pileup", "BAQ"],
        },
        "samtools_reheader": {
            "display_name": "Samtools Reheader",
            "output": ["BAM"],
            "output_name": ["reheadered_bam"],
            "aliases": ["BioNodulo builtin", "reheader", "SAM header"],
        },
        "samtools_split": {
            "display_name": "Samtools Split",
            "output": ["DIRECTORY"],
            "output_name": ["readgroup_bams"],
            "aliases": ["BioNodulo builtin", "split", "read groups"],
        },
        "samtools_slice_bam": {
            "display_name": "Samtools Slice BAM",
            "output": ["BAM"],
            "output_name": ["sliced_bam"],
            "aliases": ["BioNodulo builtin", "slice", "regions"],
        },
        "samtools_phase": {
            "display_name": "Samtools Phase",
            "output": ["STATS_FILE", "BAM", "BAM", "BAM"],
            "output_name": ["phase_sets", "phase0", "phase1", "chimera"],
            "aliases": ["BioNodulo builtin", "phase", "heterozygous SNPs"],
        },
        "samtools_consensus": {
            "display_name": "Samtools Consensus",
            "output": ["FASTA"],
            "output_name": ["consensus"],
            "aliases": ["BioNodulo builtin", "consensus", "Bayesian", "Gap5"],
        },
        "samtools_bam_to_cram": {
            "display_name": "Samtools BAM to CRAM",
            "output": ["CRAM"],
            "output_name": ["cram"],
            "aliases": ["BioNodulo builtin", "BAM to CRAM", "CRAM compression", "reference based compression"],
        },
        "samtools_cram_to_bam": {
            "display_name": "Samtools CRAM to BAM",
            "output": ["BAM"],
            "output_name": ["bam"],
            "aliases": ["BioNodulo builtin", "CRAM to BAM", "CRAM decompression", "reference"],
        },
        "samtools_bam_to_sam": {
            "display_name": "Samtools BAM to SAM",
            "output": ["SAM"],
            "output_name": ["sam"],
            "aliases": ["BioNodulo builtin", "BAM to SAM", "SAM output", "header only"],
        },
        "bam_to_sam": {
            "display_name": "BAM-to-SAM",
            "output": ["SAM"],
            "output_name": ["output1"],
            "aliases": ["BioNodulo builtin", "bam_to_sam", "BAM-to-SAM", "converted SAM"],
        },
        "samtools_sam_to_bam": {
            "display_name": "Samtools SAM to BAM",
            "output": ["BAM"],
            "output_name": ["bam"],
            "aliases": ["BioNodulo builtin", "SAM to BAM", "sorted BAM", "reference index"],
        },
        "sam_to_bam": {
            "display_name": "SAM-to-BAM",
            "output": ["BAM"],
            "output_name": ["output1"],
            "aliases": ["BioNodulo builtin", "sam_to_bam", "SAM-to-BAM", "converted BAM"],
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


def test_samtools_mpileup_renders_advanced_pileup_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_mpileup")

    assert node_class.render_command(
        {
            "input_bams": ["tumor.bam", "normal.bam"],
            "reference": "reference.fa",
            "required_flags": [2, 64],
            "skipped_flags": [4, 256, 512, 1024],
            "region": "chr17:100-150",
            "positions_bed": "targets.bed",
            "exclude_read_groups": "bad_rg.txt",
            "ignore_overlaps": True,
            "count_orphans": True,
            "disable_baq": True,
            "adjust_mq": 50,
            "max_depth": 8000,
            "redo_baq": True,
            "min_mq": 20,
            "min_bq": 13,
            "illumina13": True,
            "output_bp": True,
            "output_mq": True,
            "output_qname": True,
            "all_positions": "-aa",
            "output_extra": "NM,AM",
            "output": "/work/samtools_mpileup",
        }
    ) == [
        "samtools",
        "mpileup",
        "-f",
        "reference.fa",
        "tumor.bam",
        "normal.bam",
        "--rf",
        "66",
        "--ff",
        "1796",
        "-r",
        "chr17:100-150",
        "-l",
        "targets.bed",
        "-G",
        "bad_rg.txt",
        "-x",
        "-A",
        "-B",
        "-C",
        "50",
        "-d",
        "8000",
        "-E",
        "-q",
        "20",
        "-Q",
        "13",
        "-6",
        "-O",
        "-s",
        "--output-QNAME",
        "-aa",
        "--output-extra",
        "NM,AM",
        "--output",
        "/work/samtools_mpileup/pileup.pileup",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_mpileup" / "pileup.pileup"]


def test_samtools_reheader_renders_header_replacement_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_reheader")

    assert node_class.render_command(
        {
            "input_header": "source_header.bam",
            "input_file": "target.bam",
            "no_pg": True,
            "output": "/work/samtools_reheader",
        }
    ) == [
        "samtools",
        "reheader",
        "source_header.bam",
        "target.bam",
        "--no-PG",
        ">",
        "/work/samtools_reheader/reheadered.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_reheader" / "reheadered.bam"]


def test_samtools_split_renders_readgroup_split_command_and_output_dir(tmp_path: Path) -> None:
    node_class = _node_class("samtools_split")

    assert node_class.render_command(
        {
            "input_bam": "sample.bam",
            "header": "replacement_header.sam",
            "threads": 6,
            "output": "/work/samtools_split",
        }
    ) == [
        "samtools",
        "split",
        "-f",
        "/work/samtools_split/readgroup_bams/Read_Group_%!.bam",
        "--output-fmt",
        "bam",
        "-h",
        "replacement_header.sam",
        "-u",
        "/work/samtools_split/unaccounted.bam",
        "-@",
        "5",
        "sample.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_split" / "readgroup_bams"]


def test_samtools_slice_bam_renders_bed_and_manual_region_commands(tmp_path: Path) -> None:
    node_class = _node_class("samtools_slice_bam")

    assert node_class.render_command(
        {
            "input_bam": "sample.bam",
            "threads": 4,
            "memory_mb": 2048,
            "slice_method": "bed",
            "input_interval": "targets.bed",
            "output": "/work/samtools_slice_bam",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "3",
        "-b",
        "-L",
        "targets.bed",
        "-o",
        "/work/samtools_slice_bam/unsorted_output.bam",
        "sample.bam",
        "&&",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-T",
        "/work/samtools_slice_bam/tmp",
        "-@",
        "3",
        "-m",
        "1536M",
        "-o",
        "/work/samtools_slice_bam/sliced.bam",
        "/work/samtools_slice_bam/unsorted_output.bam",
    ]

    assert node_class.render_command(
        {
            "input_bam": "sample.bam",
            "slice_method": "manual",
            "regions": ["chrM:1-1000", "chr1:10-20"],
            "output": "/work/samtools_slice_bam",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "0",
        "-b",
        "-o",
        "/work/samtools_slice_bam/unsorted_output.bam",
        "sample.bam",
        "chrM:1-1000",
        "chr1:10-20",
        "&&",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-T",
        "/work/samtools_slice_bam/tmp",
        "-@",
        "0",
        "-m",
        "576M",
        "-o",
        "/work/samtools_slice_bam/sliced.bam",
        "/work/samtools_slice_bam/unsorted_output.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_slice_bam" / "sliced.bam"]


def test_samtools_phase_renders_advanced_phase_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samtools_phase")

    assert node_class.render_command(
        {
            "input_bam": "sample.bam",
            "block_length": 21,
            "min_het": 40,
            "min_bq": 18,
            "read_depth": 512,
            "ignore_chimeras": True,
            "drop_ambiguous": True,
            "output": "/work/samtools_phase",
        }
    ) == [
        "samtools",
        "phase",
        "-b",
        "/work/samtools_phase/phase_wrapper",
        "-F",
        "-k",
        "21",
        "-q",
        "40",
        "-Q",
        "18",
        "-D",
        "512",
        "-A",
        "sample.bam",
        ">",
        "/work/samtools_phase/phase_sets.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "samtools_phase" / "phase_sets.txt",
        tmp_path / "samtools_phase" / "phase_wrapper.0.bam",
        tmp_path / "samtools_phase" / "phase_wrapper.1.bam",
        tmp_path / "samtools_phase" / "phase_wrapper.chimera.bam",
    ]


def test_samtools_consensus_renders_simple_mode_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_consensus")

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "threads": 5,
            "format": "fastq",
            "min_mq": 21,
            "min_bq": 7,
            "required_flags": [2, 64],
            "skipped_flags": [4, 256],
            "mode": "simple",
            "use_qual": True,
            "consensus_fraction": 0.9,
            "heterozygous_fraction": 0.2,
            "min_depth": 3,
            "region": "chr1:100-200",
            "line_len": -1,
            "output_all": True,
            "show_deletions": True,
            "show_insertions": False,
            "ambig": True,
            "mark_insertions": True,
            "output": "/work/samtools_consensus",
        }
    ) == [
        "samtools",
        "consensus",
        "sample.bam",
        "-f",
        "fastq",
        "-@",
        "4",
        "--min-MQ",
        "21",
        "--min-BQ",
        "7",
        "--rf",
        "66",
        "--ff",
        "260",
        "-m",
        "simple",
        "-q",
        "-c",
        "0.9",
        "-H",
        "0.2",
        "--min-depth",
        "3",
        "-r",
        "chr1:100-200",
        "-l",
        "-1",
        "-a",
        "--show-del",
        "yes",
        "--show-ins",
        "no",
        "--ambig",
        "--mark-ins",
        ">",
        "/work/samtools_consensus/consensus.fastq",
    ]

    assert node_class.PLAN_OUTPUTS({"format": "fastq"}, tmp_path) == [
        tmp_path / "samtools_consensus" / "consensus.fastq"
    ]


def test_samtools_consensus_renders_manual_bayesian_reference_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_consensus")

    assert node_class.render_command(
        {
            "input": "reads.cram",
            "threads": 2,
            "format": "pileup",
            "mode": "bayesian_116",
            "config": "manual",
            "cutoff": 5,
            "use_mq": True,
            "adjust_mq": False,
            "nm_halo": 30,
            "low_mq": 2,
            "high_mq": 55,
            "scale_mq": 1.5,
            "p_het": 0.01,
            "p_indel": 0.02,
            "het_scale": 4.0,
            "homopoly_fix": True,
            "homopoly_score": 0.3,
            "qual_calibration": ":hifi",
            "min_depth": 1,
            "reference": "reference.fa",
            "line_len": 70,
            "output": "/work/samtools_consensus",
        }
    ) == [
        "samtools",
        "consensus",
        "reads.cram",
        "-f",
        "pileup",
        "-@",
        "1",
        "--min-MQ",
        "0",
        "--min-BQ",
        "0",
        "-m",
        "bayesian_116",
        "-C",
        "5",
        "--use-MQ",
        "--no-adj-MQ",
        "--NM-halo",
        "30",
        "--low-MQ",
        "2",
        "--high-MQ",
        "55",
        "--scale-MQ",
        "1.5",
        "--P-het",
        "0.01",
        "--P-indel",
        "0.02",
        "--het-scale",
        "4.0",
        "-p",
        "--homopoly-score",
        "0.3",
        "--qual-calibration",
        ":hifi",
        "--min-depth",
        "1",
        "-T",
        "reference.fa",
        "-l",
        "70",
        "--show-del",
        "no",
        "--show-ins",
        "yes",
        ">",
        "/work/samtools_consensus/consensus.pileup",
    ]

    assert node_class.PLAN_OUTPUTS({"format": "pileup"}, tmp_path) == [
        tmp_path / "samtools_consensus" / "consensus.pileup"
    ]


def test_samtools_bam_to_cram_renders_full_file_conversion_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_bam_to_cram")

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "reference": "reference.fa",
            "threads": 5,
            "output": "/work/samtools_bam_to_cram",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "4",
        "-C",
        "-h",
        "-o",
        "/work/samtools_bam_to_cram/output.cram",
        "-T",
        "reference.fa",
        "-t",
        "reference.fa.fai",
        "--output-fmt-option",
        "no_ref",
        "sample.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_bam_to_cram" / "output.cram"]


def test_samtools_bam_to_cram_renders_region_and_bed_filters() -> None:
    node_class = _node_class("samtools_bam_to_cram")

    assert node_class.render_command(
        {
            "input": "sample.sam",
            "reference": "reference.fa",
            "reference_index": "custom.fa.fai",
            "threads": 2,
            "target_region": "region",
            "region_string": "chr1:100-200",
            "output": "/work/samtools_bam_to_cram",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "1",
        "-C",
        "-h",
        "-o",
        "/work/samtools_bam_to_cram/output.cram",
        "-T",
        "reference.fa",
        "-t",
        "custom.fa.fai",
        "--output-fmt-option",
        "no_ref",
        "sample.sam",
        "chr1:100-200",
    ]

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "reference": "reference.fa",
            "target_region": "regions_bed_file",
            "regions_bed_file": "targets.bed",
            "output": "/work/samtools_bam_to_cram",
        }
    ) == [
        "samtools",
        "view",
        "-L",
        "targets.bed",
        "-@",
        "0",
        "-C",
        "-h",
        "-o",
        "/work/samtools_bam_to_cram/output.cram",
        "-T",
        "reference.fa",
        "-t",
        "reference.fa.fai",
        "--output-fmt-option",
        "no_ref",
        "sample.bam",
    ]


def test_samtools_bam_to_cram_validates_reference_and_region_inputs() -> None:
    node_class = _node_class("samtools_bam_to_cram")

    assert (
        node_class.VALIDATE_INPUTS({"input": "sample.bam", "reference": "", "threads": 1})
        == "reference is required for BAM to CRAM conversion"
    )
    assert (
        node_class.VALIDATE_INPUTS(
            {
                "input": "sample.bam",
                "reference": "reference.fa",
                "threads": 1,
                "target_region": "region",
            }
        )
        == "region_string is required when target_region is region"
    )
    assert (
        node_class.VALIDATE_INPUTS(
            {
                "input": "sample.bam",
                "reference": "reference.fa",
                "threads": 1,
                "target_region": "regions_bed_file",
            }
        )
        == "regions_bed_file is required when target_region is regions_bed_file"
    )


def test_samtools_cram_to_bam_renders_full_file_conversion_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_cram_to_bam")

    assert node_class.render_command(
        {
            "input": "sample.cram",
            "reference": "reference.fa",
            "threads": 6,
            "output": "/work/samtools_cram_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "5",
        "-b",
        "-T",
        "reference.fa",
        "-o",
        "/work/samtools_cram_to_bam/output.bam",
        "sample.cram",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_cram_to_bam" / "output.bam"]


def test_samtools_cram_to_bam_renders_region_and_bed_filters() -> None:
    node_class = _node_class("samtools_cram_to_bam")

    assert node_class.render_command(
        {
            "input": "sample.cram",
            "reference": "reference.fa",
            "threads": 2,
            "target_region": "region",
            "region_string": "chr2:50-150",
            "output": "/work/samtools_cram_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-@",
        "1",
        "-b",
        "-T",
        "reference.fa",
        "-o",
        "/work/samtools_cram_to_bam/output.bam",
        "sample.cram",
        "chr2:50-150",
    ]

    assert node_class.render_command(
        {
            "input": "sample.cram",
            "reference": "reference.fa",
            "target_region": "regions_bed_file",
            "regions_bed_file": "targets.bed",
            "output": "/work/samtools_cram_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-L",
        "targets.bed",
        "-@",
        "0",
        "-b",
        "-T",
        "reference.fa",
        "-o",
        "/work/samtools_cram_to_bam/output.bam",
        "sample.cram",
    ]


def test_samtools_cram_to_bam_validates_reference_and_region_inputs() -> None:
    node_class = _node_class("samtools_cram_to_bam")

    assert (
        node_class.VALIDATE_INPUTS({"input": "sample.cram", "reference": "", "threads": 1})
        == "reference is required for CRAM to BAM conversion"
    )
    assert (
        node_class.VALIDATE_INPUTS(
            {
                "input": "sample.cram",
                "reference": "reference.fa",
                "threads": 1,
                "target_region": "region",
            }
        )
        == "region_string is required when target_region is region"
    )
    assert (
        node_class.VALIDATE_INPUTS(
            {
                "input": "sample.cram",
                "reference": "reference.fa",
                "threads": 1,
                "target_region": "regions_bed_file",
            }
        )
        == "regions_bed_file is required when target_region is regions_bed_file"
    )


def test_samtools_bam_to_sam_renders_header_modes_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_bam_to_sam")

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "header": "-h",
            "output": "/work/samtools_bam_to_sam",
        }
    ) == [
        "samtools",
        "view",
        "-o",
        "/work/samtools_bam_to_sam/output.sam",
        "-h",
        "sample.bam",
    ]

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "header": "-H",
            "output": "/work/samtools_bam_to_sam",
        }
    ) == [
        "samtools",
        "view",
        "-o",
        "/work/samtools_bam_to_sam/output.sam",
        "-H",
        "sample.bam",
    ]

    assert node_class.render_command(
        {
            "input": "sample.bam",
            "header": "",
            "output": "/work/samtools_bam_to_sam",
        }
    ) == [
        "samtools",
        "view",
        "-o",
        "/work/samtools_bam_to_sam/output.sam",
        "sample.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_bam_to_sam" / "output.sam"]


def test_samtools_bam_to_sam_validates_header_mode() -> None:
    node_class = _node_class("samtools_bam_to_sam")

    assert node_class.VALIDATE_INPUTS({"header": "-h"}) == "Required input 'input' is missing"
    assert (
        node_class.VALIDATE_INPUTS({"input": "sample.bam", "header": "--headers"})
        == "header must be one of -h, -H, or an empty string"
    )


def test_galaxy_bam_to_sam_renders_wrapper_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bam_to_sam")

    assert node_class.render_command(
        {
            "input1": "aligned reads.bam",
            "header": "-h",
            "output": "/work/bam_to_sam",
        }
    ) == ["samtools", "view", "-o", "/work/bam_to_sam/output1.sam", "-h", "aligned reads.bam"]

    assert node_class.render_command(
        {
            "input1": "aligned reads.bam",
            "header": "-H",
            "output": "/work/bam_to_sam",
        }
    ) == ["samtools", "view", "-o", "/work/bam_to_sam/output1.sam", "-H", "aligned reads.bam"]

    assert node_class.render_command(
        {
            "input1": "aligned reads.bam",
            "header": "",
            "output": "/work/bam_to_sam",
        }
    ) == ["samtools", "view", "-o", "/work/bam_to_sam/output1.sam", "aligned reads.bam"]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "bam_to_sam" / "output1.sam"]


def test_galaxy_bam_to_sam_validates_required_input_and_header_mode() -> None:
    node_class = _node_class("bam_to_sam")

    assert node_class.VALIDATE_INPUTS({"header": "-h"}) == "Required input 'input1' is missing"
    assert (
        node_class.VALIDATE_INPUTS({"input1": "aligned.bam", "header": "--headers"})
        == "header must be one of -h, -H, or an empty string"
    )
    assert node_class.VALIDATE_INPUTS({"input1": "aligned.bam", "header": ""}) is True


def test_samtools_sam_to_bam_renders_sorted_conversion_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("samtools_sam_to_bam")

    assert node_class.render_command(
        {
            "input": "sample.sam",
            "reference": "reference.fa",
            "reference_index": "reference.fa.fai",
            "threads": 5,
            "memory_mb": 2048,
            "output": "/work/samtools_sam_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-b",
        "-@",
        "4",
        "-t",
        "reference.fa.fai",
        "sample.sam",
        "|",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-@",
        "4",
        "-m",
        "1536M",
        "-o",
        "/work/samtools_sam_to_bam/output.bam",
        "-T",
        "/work/samtools_sam_to_bam/tmp",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "samtools_sam_to_bam" / "output.bam"]


def test_samtools_sam_to_bam_uses_default_reference_index_and_validates_reference() -> None:
    node_class = _node_class("samtools_sam_to_bam")

    assert node_class.render_command(
        {
            "input": "sample.sam",
            "reference": "reference.fa",
            "threads": 1,
            "output": "/work/samtools_sam_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-b",
        "-@",
        "0",
        "-t",
        "reference.fa.fai",
        "sample.sam",
        "|",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-@",
        "0",
        "-m",
        "576M",
        "-o",
        "/work/samtools_sam_to_bam/output.bam",
        "-T",
        "/work/samtools_sam_to_bam/tmp",
    ]

    assert (
        node_class.VALIDATE_INPUTS({"input": "sample.sam", "reference": "", "threads": 1})
        == "reference is required for SAM to BAM conversion"
    )


def test_galaxy_sam_to_bam_renders_history_reference_conversion_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("sam_to_bam")

    assert node_class.render_command(
        {
            "input": "sample alignments.sam",
            "addref_select": "history",
            "ref": "reference genome.fa",
            "threads": 6,
            "memory_mb": 2048,
            "output": "/work/sam_to_bam",
        }
    ) == [
        "ln",
        "-s",
        "reference genome.fa",
        "reference.fa",
        "&&",
        "samtools",
        "faidx",
        "reference.fa",
        "&&",
        "samtools",
        "view",
        "-b",
        "-@",
        "5",
        "-t",
        "reference.fa.fai",
        "sample alignments.sam",
        "|",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-@",
        "5",
        "-m",
        "1536M",
        "-o",
        "/work/sam_to_bam/output1.bam",
        "-T",
        "${TMPDIR:-.}",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "sam_to_bam" / "output1.bam"]


def test_galaxy_sam_to_bam_renders_cached_reference_conversion_pipeline() -> None:
    node_class = _node_class("sam_to_bam")

    assert node_class.render_command(
        {
            "input": "sample.sam",
            "addref_select": "cached",
            "cached_ref_path": "/data/db/equCab2chrM.fa",
            "threads": 1,
            "memory_mb": 768,
            "output": "/work/sam_to_bam",
        }
    ) == [
        "samtools",
        "view",
        "-b",
        "-@",
        "0",
        "-t",
        "/data/db/equCab2chrM.fa.fai",
        "sample.sam",
        "|",
        "samtools",
        "sort",
        "-O",
        "bam",
        "-@",
        "0",
        "-m",
        "576M",
        "-o",
        "/work/sam_to_bam/output1.bam",
        "-T",
        "${TMPDIR:-.}",
    ]


def test_galaxy_sam_to_bam_validates_reference_selection_and_resources() -> None:
    node_class = _node_class("sam_to_bam")

    assert node_class.VALIDATE_INPUTS({"addref_select": "history", "ref": "reference.fa"}) == (
        "Required input 'input' is missing"
    )
    assert node_class.VALIDATE_INPUTS({"input": "sample.sam", "addref_select": "history"}) == (
        "ref is required when addref_select is history"
    )
    assert node_class.VALIDATE_INPUTS({"input": "sample.sam", "addref_select": "cached"}) == (
        "cached_ref_path is required when addref_select is cached"
    )
    assert node_class.VALIDATE_INPUTS({"input": "sample.sam", "addref_select": "other"}) == (
        "addref_select must be one of: history, cached"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input": "sample.sam", "addref_select": "history", "ref": "reference.fa", "threads": 0}
    ) == "threads must be greater than 0"
    assert node_class.VALIDATE_INPUTS(
        {"input": "sample.sam", "addref_select": "history", "ref": "reference.fa", "memory_mb": 0}
    ) == "memory_mb must be greater than 0"
    assert node_class.VALIDATE_INPUTS({"input": "sample.sam", "addref_select": "history", "ref": "reference.fa"}) is True
