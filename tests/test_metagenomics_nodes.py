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
        "/tmp/run/humann/output",
        "/tmp/run/humann/output/humann_genefamilies.tsv",
        "/tmp/run/humann/output/humann_pathabundance.tsv",
        "/tmp/run/humann/output/humann_pathcoverage.tsv",
        "/tmp/run/humann/humann.log",
    ]


def test_humann_plans_single_read_stem_outputs() -> None:
    outputs = HUMAnNNode.PLAN_OUTPUTS({"reads": "sample.fastq.gz"}, Path("/tmp/run"))

    assert [path.name for path in outputs] == [
        "output",
        "humann_genefamilies.tsv",
        "humann_pathabundance.tsv",
        "humann_pathcoverage.tsv",
        "humann.log",
    ]


def test_humann_exposes_galaxy_aligned_metadata_inputs_and_outputs() -> None:
    info = _object_info("humann")

    assert info["display_name"] == "HUMAnN"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Profile microbial pathway and gene-family abundance with HUMAnN 3."
    assert info["output"] == [
        "HUMANN_OUTPUT",
        "TSV",
        "TSV",
        "TSV",
        "BIOM",
        "BIOM",
        "BIOM",
        "TXT",
        "TSV",
        "TSV",
        "SAM",
        "TSV",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
    ]
    assert info["output_name"] == [
        "output_dir",
        "genefamilies",
        "pathabundance",
        "pathcoverage",
        "genefamilies_biom",
        "pathabundance_biom",
        "pathcoverage_biom",
        "log",
        "metaphlan_bowtie2",
        "metaphlan_bugs_list",
        "bowtie2_alignment",
        "bowtie2_reduced_alignment",
        "bowtie2_unaligned",
        "custom_chocophlan_database",
        "diamond_aligned",
        "diamond_unaligned",
    ]
    assert info["required_executables"] == ["humann"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_urls"] == [
        "https://doi.org/10.7554/eLife.65088",
        "https://doi.org/10.1371/journal.pcbi.1002358",
    ]
    assert "Galaxy" in info["search_aliases"]
    assert "intermediate output files" in info["search_aliases"]

    assert info["input"]["required"]["reads"][0] == "FILE"
    assert info["input"]["required"]["nuc_db"][0] == "DIRECTORY"
    assert info["input"]["required"]["prot_db"][0] == "DIRECTORY"
    assert info["input"]["optional"]["input_selector"][1]["options"] == ["raw", "mapping", "abundance"]
    assert info["input"]["optional"]["workflow_selector"][1]["options"] == [
        "none",
        "bypass_prescreen",
        "bypass_taxonomic_profiling",
        "bypass_nucleotide_index",
        "bypass_nucleotide_search",
        "bypass_translated_search",
    ]
    assert info["input"]["optional"]["output_format"][1]["options"] == ["tsv", "biom"]
    assert info["input"]["optional"]["intermediate_temp"][1]["multiple"] is True
    assert info["input"]["optional"]["gap_fill"][1]["default"] is True


def test_humann_renders_full_history_database_workflow_command(tmp_path: Path) -> None:
    cmd = HUMAnNNode.render_command(
        {
            "reads": "demo.fastq.gz",
            "input_selector": "raw",
            "input_ext": "fastq.gz",
            "workflow_selector": "none",
            "metaphlan_db_selector": "history",
            "metaphlan_bowtie2db": "demo-db-v30.fasta",
            "metaphlan_mpa_pkl": "demo-db-v30.json",
            "nucleotide_db_selector": "history",
            "nucleotide_database": ["g__Bacteroides.s__dorei.ffn.gz", "g__Bacteroides.s__vulgatus.ffn.gz"],
            "nucleotide_database_names": ["g__Bacteroides.s__Bacteroides dorei", "g__Bacteroides.s__Bacteroides vulgatus"],
            "protein_db_selector": "history",
            "protein_database": "uniref90_demo.fasta",
            "search_mode": "uniref90",
            "translated_identity_threshold": 80,
            "prescreen_threshold": 0.02,
            "gap_fill": True,
            "minpath": False,
            "pathways": "unipathway",
            "xipe": True,
            "annotation_gene_index": 4,
            "id_mapping": "map.tsv",
            "output_basename": "demo",
            "output_format": "tsv",
            "output_max_decimals": 5,
            "remove_column_description_output": True,
            "remove_stratified_output": True,
            "threads": 6,
            "output": "/work/humann",
        }
    )

    assert cmd == (
        "mkdir metaphlan_db && "
        "bowtie2-build --large-index demo-db-v30.fasta metaphlan_db/custom_db-v30 && "
        "python customizemetadata.py transform_json_to_pkl --json demo-db-v30.json --pkl metaphlan_db/custom_db-v30.pkl && "
        "mkdir nucleotide_db && "
        "ln -s g__Bacteroides.s__dorei.ffn.gz nucleotide_db/g__Bacteroides.s__Bacteroides_dorei.v201901_v31 && "
        "ln -s g__Bacteroides.s__vulgatus.ffn.gz nucleotide_db/g__Bacteroides.s__Bacteroides_vulgatus.v201901_v31 && "
        "mkdir protein_db && "
        "diamond makedb --in uniref90_demo.fasta --db protein_db/protein-db-201901b --threads 6 && "
        "humann --input demo.fastq.gz --input-format fastq.gz -o /work/humann/output "
        "--metaphlan-options '-t rel_ab --bowtie2db metaphlan_db/ --index custom_db-v30' "
        "--prescreen-threshold 0.02 --nucleotide-database nucleotide_db "
        "--nucleotide-identity-threshold 0 --nucleotide-subject-coverage-threshold 50 "
        "--nucleotide-query-coverage-threshold 90 --translated-alignment diamond "
        "--protein-database protein_db --search-mode uniref90 --evalue 1 --identity-threshold 80 "
        "--translated-subject-coverage-threshold 50 --translated-query-coverage-threshold 90 "
        "--gap-fill on --minpath off --pathways unipathway --xipe on --annotation-gene-index 4 "
        "--id-mapping map.tsv --log-level DEBUG --o-log /work/humann/humann.log "
        "--output-basename demo --output-format tsv --output-max-decimals 5 "
        "--remove-column-description-output --remove-stratified-output --threads 6 --memory-use minimum"
    )

    assert HUMAnNNode.PLAN_OUTPUTS(
        {
            "reads": "demo.fastq.gz",
            "output_basename": "demo",
            "output_format": "tsv",
            "intermediate_temp": [
                "metaphlan_bowtie2",
                "metaphlan_bugs_list",
                "bowtie2_alignment",
                "bowtie2_reduced_alignment",
                "bowtie2_unaligned",
                "custom_chocophlan_database",
                "diamond_aligned",
                "diamond_unaligned",
            ],
        },
        tmp_path,
    ) == [
        tmp_path / "humann" / "output",
        tmp_path / "humann" / "output" / "demo_genefamilies.tsv",
        tmp_path / "humann" / "output" / "demo_pathabundance.tsv",
        tmp_path / "humann" / "output" / "demo_pathcoverage.tsv",
        tmp_path / "humann" / "humann.log",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_metaphlan_bowtie2.txt",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_metaphlan_bugs_list.tsv",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_bowtie2_aligned.sam",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_bowtie2_aligned.tsv",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_bowtie2_unaligned.fa",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_custom_chocophlan_database.ffn",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_diamond_aligned.tsv",
        tmp_path / "humann" / "output" / "demo_temp" / "demo_diamond_unaligned.fa",
    ]


def test_humann_renders_cached_bypass_and_biom_outputs(tmp_path: Path) -> None:
    cmd = HUMAnNNode.render_command(
        {
            "reads": "demo.fasta.gz",
            "input_selector": "raw",
            "workflow_selector": "bypass_prescreen",
            "nuc_db": "/db/chocophlan",
            "prot_db": "/db/uniref50_diamond",
            "output_format": "biom",
            "output_basename": "humann",
            "threads": 4,
            "output": "/work/humann",
        }
    )

    assert cmd == (
        "humann --input demo.fasta.gz --input-format fasta.gz -o /work/humann/output "
        "--bypass-prescreen --nucleotide-database /db/chocophlan --nucleotide-identity-threshold 0 "
        "--nucleotide-subject-coverage-threshold 50 --nucleotide-query-coverage-threshold 90 "
        "--translated-alignment diamond --protein-database /db/uniref50_diamond --search-mode uniref50 "
        "--evalue 1 --translated-subject-coverage-threshold 50 --translated-query-coverage-threshold 90 "
        "--gap-fill on --minpath on --pathways metacyc --xipe off --annotation-gene-index 3 "
        "--log-level DEBUG --o-log /work/humann/humann.log --output-basename humann "
        "--output-format biom --output-max-decimals 10 --threads 4 --memory-use minimum"
    )

    assert HUMAnNNode.PLAN_OUTPUTS({"reads": "demo.fasta.gz", "output_format": "biom"}, tmp_path) == [
        tmp_path / "humann" / "output",
        tmp_path / "humann" / "output" / "humann_genefamilies.biom",
        tmp_path / "humann" / "output" / "humann_pathabundance.biom",
        tmp_path / "humann" / "output" / "humann_pathcoverage.biom",
        tmp_path / "humann" / "humann.log",
    ]


def test_humann_renders_abundance_and_mapping_workflow_variants(tmp_path: Path) -> None:
    abundance_cmd = HUMAnNNode.render_command(
        {
            "reads": "demo_genefamilies.tsv",
            "input_selector": "abundance",
            "input_ext": "tsv",
            "output_basename": "genes",
            "threads": 2,
            "output": "/work/humann",
        }
    )
    mapping_cmd = HUMAnNNode.render_command(
        {
            "reads": "demo.sam",
            "input_selector": "mapping",
            "input_ext": "sam",
            "workflow_selector": "bypass_nucleotide_index",
            "nuc_db": "/db/chocophlan",
            "prot_db": "/db/uniref90_diamond",
            "output": "/work/humann",
        }
    )

    assert abundance_cmd == (
        "humann --input demo_genefamilies.tsv --input-format genetable -o /work/humann/output "
        "--gap-fill on --minpath on --pathways metacyc --xipe off --annotation-gene-index 3 "
        "--log-level DEBUG --o-log /work/humann/humann.log --output-basename genes "
        "--output-format tsv --output-max-decimals 10 --threads 2 --memory-use minimum"
    )
    assert "--bypass-nucleotide-index" in mapping_cmd
    assert "--input-format sam" in mapping_cmd
    assert "--nucleotide-database /db/chocophlan" in mapping_cmd
    assert "--protein-database /db/uniref90_diamond --search-mode uniref90" in mapping_cmd

    assert HUMAnNNode.PLAN_OUTPUTS(
        {"reads": "demo_genefamilies.tsv", "input_selector": "abundance", "output_basename": "genes"},
        tmp_path,
    ) == [
        tmp_path / "humann" / "output",
        tmp_path / "humann" / "output" / "genes_pathabundance.tsv",
        tmp_path / "humann" / "output" / "genes_pathcoverage.tsv",
        tmp_path / "humann" / "humann.log",
    ]


def test_humann_validates_required_workflow_databases() -> None:
    assert HUMAnNNode.VALIDATE_INPUTS(
        {
            "reads": "demo.fastq.gz",
            "workflow_selector": "none",
            "metaphlan_db_selector": "history",
            "metaphlan_bowtie2db": "demo-db-v30.fasta",
            "nuc_db": "/db/chocophlan",
            "prot_db": "/db/uniref90",
        }
    ) == "metaphlan_mpa_pkl is required when metaphlan_db_selector is history"

    assert HUMAnNNode.VALIDATE_INPUTS(
        {
            "reads": "demo.fastq.gz",
            "workflow_selector": "bypass_prescreen",
            "nucleotide_db_selector": "history",
            "prot_db": "/db/uniref90",
        }
    ) == "nucleotide_database is required when nucleotide_db_selector is history"

    assert HUMAnNNode.VALIDATE_INPUTS(
        {
            "reads": "demo.fastq.gz",
            "workflow_selector": "bypass_prescreen",
            "nuc_db": "/db/chocophlan",
            "protein_db_selector": "history",
        }
    ) == "protein_database is required when protein_db_selector is history"


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
