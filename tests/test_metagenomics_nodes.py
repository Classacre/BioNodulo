from pathlib import Path

from bionodulo.nodes.builtin.metagenomics import HUMAnNNode, MetaPhlAnNode
from bionodulo.nodes.registry import NodeRegistry


def _object_info(node_id: str) -> dict:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry.object_info()[node_id]


def test_humann_plans_standard_functional_profile_outputs() -> None:
    outputs = HUMAnNNode.PLAN_OUTPUTS(
        {"reads": ["reads_forward.fastq", "reads_reverse.fastq"]},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/humann/output_dir.out",
        "/tmp/run/humann/output_dir.out/reads_forward_genefamilies.tsv",
        "/tmp/run/humann/output_dir.out/reads_forward_pathabundance.tsv",
        "/tmp/run/humann/output_dir.out/reads_forward_pathcoverage.tsv",
    ]


def test_humann_plans_single_read_stem_outputs() -> None:
    outputs = HUMAnNNode.PLAN_OUTPUTS({"reads": "sample.fastq.gz"}, Path("/tmp/run"))

    assert [path.name for path in outputs] == [
        "output_dir.out",
        "sample_genefamilies.tsv",
        "sample_pathabundance.tsv",
        "sample_pathcoverage.tsv",
    ]


def test_metaphlan_exposes_galaxy_aligned_metadata_and_inputs() -> None:
    info = _object_info("metaphlan")

    assert info["display_name"] == "MetaPhlAn"
    assert info["category"] == "metagenomics"
    assert info["output"] == ["METAPHLAN_PROFILE", "TSV", "SAM", "BIOM", "DIRECTORY", "TSV", "TSV", "FASTQ", "DIRECTORY"]
    assert info["output_name"] == [
        "profile",
        "mapout",
        "sam_output",
        "biom_output",
        "split_levels",
        "krona_output",
        "vsc_breadth_coverage",
        "subsampled_reads",
        "subsampled_paired_reads",
    ]
    assert info["required_executables"] == ["metaphlan"]
    assert info["required_conda_packages"] == ["metaphlan"]
    assert info["citation_dois"] == ["10.1038/s41587-023-01688-w"]
    assert info["citation_urls"] == ["https://doi.org/10.1038/s41587-023-01688-w"]
    assert "Galaxy" in info["search_aliases"]

    assert info["input"]["required"]["reads"][0] == "FASTQ_LIST"
    assert info["input"]["required"]["bt2_db"][0] == "DIRECTORY"
    assert info["input"]["optional"]["input_selector"][1]["options"] == ["raw", "sam", "mapout"]
    assert info["input"]["optional"]["raw_selector"][1]["options"] == ["single", "multiple", "paired", "paired_collection"]
    assert info["input"]["optional"]["db_selector"][1]["options"] == ["cached", "history"]
    assert info["input"]["optional"]["analysis_type"][1]["options"] == [
        "rel_ab",
        "rel_ab_w_read_stats",
        "clade_profiles",
        "marker_ab_table",
        "marker_pres_table",
    ]
    assert info["input"]["optional"]["organism_profiling"][1]["multiple"] is True
    assert info["input"]["optional"]["biom_format_output"][1]["default"] is False
    assert info["input"]["optional"]["krona_output"][1]["default"] is False


def test_metaphlan_renders_raw_single_cached_database_command_and_outputs(tmp_path: Path) -> None:
    cmd = MetaPhlAnNode.render_command(
        {
            "reads": "reads.fasta.gz",
            "input_selector": "raw",
            "raw_selector": "single",
            "input_ext": "fasta.gz",
            "read_min_len": 70,
            "bt2_ps": "sensitive",
            "min_mapq_val": 5,
            "bt2_db": "/db/metaphlan",
            "index": "mpa_vJun23_CHOCOPhlAnSGB_202403",
            "analysis_type": "rel_ab",
            "tax_lev": "a",
            "split_levels": True,
            "organism_profiling": ["ignore_eukaryotes", "ignore_ksgbs"],
            "stat": "avg_g",
            "stat_q": 0.2,
            "perc_nonzero": 0.33,
            "avoid_disqm": True,
            "sample_id_key": "SampleID",
            "sample_id": "SRS014464",
            "skip_unclassified_estimation": True,
            "krona_output": True,
            "threads": 4,
            "offline": True,
            "output": "/work/metaphlan",
        }
    )

    assert cmd == (
        "zcat reads.fasta.gz > in && "
        "metaphlan in --input_type fasta --read_min_len 70 --bt2_ps sensitive --min_mapq_val 5 "
        "--db_dir /db/metaphlan --index mpa_vJun23_CHOCOPhlAnSGB_202403 "
        "-t rel_ab --tax_lev a --ignore_eukaryotes --ignore_ksgbs --stat avg_g --stat_q 0.2 "
        "--perc_nonzero 0.33 --avoid_disqm --sample_id_key SampleID --sample_id SRS014464 "
        "--skip_unclassified_estimation -o /work/metaphlan/profile.metaphlan.tsv --mapout mapout "
        "-s /work/metaphlan/sam_output.sam --nproc 4 --offline && "
        "mv mapout /work/metaphlan/mapout.tsv && "
        "mkdir split_levels && "
        "python formatoutput.py split_levels --metaphlan_output /work/metaphlan/profile.metaphlan.tsv "
        "--outdir split_levels && "
        "mv split_levels /work/metaphlan/split_levels && "
        "python formatoutput.py format_for_krona --metaphlan_output /work/metaphlan/profile.metaphlan.tsv "
        "--krona_output /work/metaphlan/krona_output.tsv"
    )

    assert MetaPhlAnNode.PLAN_OUTPUTS({"krona_output": True, "split_levels": True}, tmp_path) == [
        tmp_path / "metaphlan" / "profile.metaphlan.tsv",
        tmp_path / "metaphlan" / "mapout.tsv",
        tmp_path / "metaphlan" / "sam_output.sam",
        tmp_path / "metaphlan" / "split_levels",
        tmp_path / "metaphlan" / "krona_output.tsv",
    ]


def test_metaphlan_renders_paired_subsampling_and_history_database_command(tmp_path: Path) -> None:
    cmd = MetaPhlAnNode.render_command(
        {
            "reads": ["R1.fastq", "R2.fastq"],
            "paired": True,
            "input_selector": "raw",
            "raw_selector": "paired",
            "input_ext": "fastq",
            "db_selector": "history",
            "custom_marker_sequences": "custom_markers.fasta",
            "custom_marker_metadata": "custom_markers.json",
            "analysis_type": "marker_ab_table",
            "nreads": 12000,
            "min_alignment_len": 80,
            "subsample_mode": "paired",
            "subsampling_paired": 1000,
            "mapping_subsampling": True,
            "subsampling_seed": 7,
            "threads": 8,
            "output": "/work/metaphlan",
        }
    )

    assert cmd == (
        "ln -s R1.fastq in_f && ln -s R2.fastq in_r && "
        "mkdir ref_db && "
        "bowtie2-build --large-index custom_markers.fasta ref_db/custom_db && "
        "python customizemetadata.py transform_json_to_pkl --json custom_markers.json --pkl ref_db/custom_db.pkl && "
        "metaphlan -1 in_f -2 in_r --input_type fastq --read_min_len 70 --bt2_ps very-sensitive "
        "--min_mapq_val 5 --db_dir ref_db/ --index custom_db -t marker_ab_table --nreads 12000 "
        "--min_alignment_len 80 --stat tavg_g --stat_q 0.2 --perc_nonzero 0.33 --avoid_disqm "
        "--sample_id_key SampleID --sample_id Metaphlan_Analysis -o /work/metaphlan/profile.metaphlan.tsv "
        "--mapout mapout -s /work/metaphlan/sam_output.sam --nproc 8 --subsampling_paired 1000 "
        "--mapping_subsampling --subsampling_seed 7 --subsampling_output subsampled.out && "
        "mv mapout /work/metaphlan/mapout.tsv"
    )

    assert MetaPhlAnNode.PLAN_OUTPUTS({"subsample_mode": "paired"}, tmp_path) == [
        tmp_path / "metaphlan" / "profile.metaphlan.tsv",
        tmp_path / "metaphlan" / "mapout.tsv",
        tmp_path / "metaphlan" / "sam_output.sam",
        tmp_path / "metaphlan" / "subsampled_paired_reads",
    ]


def test_metaphlan_renders_sam_input_biom_and_vsc_outputs(tmp_path: Path) -> None:
    cmd = MetaPhlAnNode.render_command(
        {
            "reads": "mapped.sam",
            "input_selector": "sam",
            "bt2_db": "/db/metaphlan",
            "index": "mpa_vJun23_CHOCOPhlAnSGB_202403",
            "profile_vsc": True,
            "vsc_breadth": 0.75,
            "analysis_type": "marker_pres_table",
            "pres_th": 2,
            "biom_format_output": True,
            "use_group_representative": True,
            "CAMI_format_output": True,
            "threads": 2,
            "output": "/work/metaphlan",
        }
    )

    assert cmd == (
        "metaphlan mapped.sam --input_type sam --nreads $(cat mapped.sam | grep -c -v '^@') "
        "--db_dir /db/metaphlan --index mpa_vJun23_CHOCOPhlAnSGB_202403 --profile_vsc "
        "--vsc_out /work/metaphlan/vsc_breadth_coverage.tsv --vsc_breadth 0.75 "
        "-t marker_pres_table --pres_th 2 --stat tavg_g --stat_q 0.2 --perc_nonzero 0.33 "
        "--avoid_disqm --sample_id_key SampleID --sample_id Metaphlan_Analysis "
        "--use_group_representative --CAMI_format_output -o /work/metaphlan/biom_output.biom "
        "--mapout mapout -s /work/metaphlan/sam_output.sam --nproc 2"
    )

    assert MetaPhlAnNode.PLAN_OUTPUTS(
        {"input_selector": "sam", "biom_format_output": True, "profile_vsc": True},
        tmp_path,
    ) == [
        tmp_path / "metaphlan" / "profile.metaphlan.tsv",
        tmp_path / "metaphlan" / "biom_output.biom",
        tmp_path / "metaphlan" / "vsc_breadth_coverage.tsv",
    ]


def test_metaphlan_validates_paired_and_history_inputs() -> None:
    assert MetaPhlAnNode.VALIDATE_INPUTS(
        {
            "reads": ["R1.fastq"],
            "paired": True,
            "raw_selector": "paired",
            "bt2_db": "/db/metaphlan",
            "index": "mpa_vJun23_CHOCOPhlAnSGB_202403",
        }
    ) == "Paired MetaPhlAn input requires two read files"

    assert MetaPhlAnNode.VALIDATE_INPUTS(
        {
            "reads": ["R1.fastq", "R2.fastq"],
            "db_selector": "history",
            "custom_marker_sequences": "custom_markers.fasta",
        }
    ) == "custom_marker_metadata is required when db_selector is history"
