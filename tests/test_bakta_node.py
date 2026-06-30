from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def test_bakta_exposes_galaxy_metadata_inputs_outputs_and_doi() -> None:
    node_info = _registry().object_info()["bakta"]

    assert node_info["display_name"] == "Bakta"
    assert node_info["category"] == "annotation"
    assert node_info["description"] == (
        "Rapid and standardized annotation of bacterial genomes, MAGs and plasmids."
    )
    assert node_info["output"] == [
        "TSV",
        "GFF3",
        "GBFF",
        "EMBL",
        "FASTA",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
        "TXT",
        "JSON",
        "SVG",
        "TXT",
    ]
    assert node_info["output_name"] == [
        "annotation_tsv",
        "annotation_gff3",
        "annotation_gbff",
        "annotation_embl",
        "annotation_fna",
        "annotation_ffn",
        "annotation_faa",
        "hypotheticals_tsv",
        "hypotheticals_faa",
        "summary_txt",
        "annotation_json",
        "annotation_plot",
        "logfile",
    ]
    assert node_info["required_executables"] == ["bakta", "ln", "mkdir", "cp"]
    assert node_info["required_conda_packages"] == ["bakta"]
    assert node_info["documentation_url"] == "https://github.com/oschwengers/bakta"
    assert node_info["citation_dois"] == ["10.1099/mgen.0.000685"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1099/mgen.0.000685"]
    assert "Bakta" in node_info["citation_text"]
    assert node_info["version"] == "1.9.4+galaxy1"
    assert "Galaxy" in node_info["search_aliases"]
    assert "MAGs" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_file", "bakta_db", "amrfinder_db"}
    assert inputs["required"]["input_file"][0] == "FASTA"
    assert inputs["required"]["bakta_db"][0] == "DIRECTORY"
    assert inputs["required"]["amrfinder_db"][0] == "DIRECTORY"
    assert set(inputs["optional"]) == {
        "min_contig_length",
        "genus",
        "species",
        "strain",
        "plasmid",
        "complete",
        "prodigal",
        "translation_table",
        "keep_contig_headers",
        "replicons",
        "compliant",
        "proteins",
        "meta",
        "regions",
        "skip_analysis",
        "output_selection",
        "threads",
    }
    assert inputs["optional"]["translation_table"][1]["options"] == ["4", "11"]
    assert inputs["optional"]["translation_table"][1]["default"] == "11"
    assert inputs["optional"]["skip_analysis"][1]["is_list"] is True
    assert inputs["optional"]["skip_analysis"][1]["options"] == [
        "--skip-trna",
        "--skip-tmrna",
        "--skip-rrna",
        "--skip-ncrna",
        "--skip-ncrna-region",
        "--skip-crispr",
        "--skip-cds",
        "--skip-pseudo",
        "--skip-sorf",
        "--skip-gap",
        "--skip-ori",
        "--skip-plot",
    ]
    assert inputs["optional"]["output_selection"][1]["default"] == [
        "file_tsv",
        "file_gff3",
        "file_ffn",
        "file_plot",
    ]


def test_bakta_renders_galaxy_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("bakta")

    command = node_class.render_command(
        {
            "input_file": "assembly with spaces.fna",
            "bakta_db": "/refs/bakta db",
            "amrfinder_db": "/refs/amrfinder",
            "min_contig_length": 250,
            "genus": "Escherichia",
            "species": "coli O157:H7",
            "strain": "Sakai",
            "plasmid": "pOSAK1",
            "complete": True,
            "prodigal": "training.tf",
            "translation_table": "4",
            "keep_contig_headers": True,
            "replicons": "replicons.tsv",
            "compliant": True,
            "proteins": "trusted proteins.faa",
            "regions": "regions.gff",
            "skip_analysis": ["--skip-trna", "--skip-plot"],
            "threads": 6,
            "output": "/work/bakta",
        }
    )

    assert node_class.SHELL is True
    assert command == (
        "mkdir -p ./database_path/amrfinderplus-db /work/bakta && "
        "ln -s '/refs/bakta db'/* database_path && "
        "ln -s /refs/amrfinder/ database_path/amrfinderplus-db/latest && "
        "bakta --verbose --threads 6 --db ./database_path --output bakta_output "
        "--min-contig-length 250 --prefix bakta_output --genus Escherichia "
        "--species 'coli O157:H7' --strain Sakai --plasmid pOSAK1 --complete "
        "--prodigal-tf training.tf --translation-table 4 --gram '?' --keep-contig-headers "
        "--replicons replicons.tsv --compliant --proteins 'trusted proteins.faa' --regions regions.gff "
        "--skip-trna --skip-plot 'assembly with spaces.fna' 2>&1 | tee /work/bakta/logfile.txt && "
        "cp bakta_output/bakta_output.tsv /work/bakta/annotation_tsv.tsv && "
        "cp bakta_output/bakta_output.gff3 /work/bakta/annotation_gff3.gff3 && "
        "cp bakta_output/bakta_output.ffn /work/bakta/annotation_ffn.fasta && "
        "cp bakta_output/bakta_output.svg /work/bakta/annotation_plot.svg"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bakta" / "annotation_tsv.tsv",
        tmp_path / "bakta" / "annotation_gff3.gff3",
        tmp_path / "bakta" / "annotation_ffn.fasta",
        tmp_path / "bakta" / "annotation_plot.svg",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"output_selection": ["file_faa", "sum_txt", "log_txt"]},
        tmp_path,
    ) == [
        tmp_path / "bakta" / "annotation_faa.fasta",
        tmp_path / "bakta" / "summary_txt.txt",
        tmp_path / "bakta" / "logfile.txt",
    ]

    assert node_class.VALIDATE_INPUTS({}) == "input_file is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "assembly.fna"}) == "bakta_db is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "assembly.fna", "bakta_db": "/db"}) == (
        "amrfinder_db is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "assembly.fna", "bakta_db": "/db", "amrfinder_db": "/amr", "min_contig_length": -1}
    ) == "min_contig_length must be >= 0"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "assembly.fna", "bakta_db": "/db", "amrfinder_db": "/amr", "translation_table": "99"}
    ) == "translation_table must be one of: 4, 11"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "assembly.fna", "bakta_db": "/db", "amrfinder_db": "/amr", "skip_analysis": ["--bad"]}
    ) == (
        "skip_analysis entries must be one of: --skip-trna, --skip-tmrna, --skip-rrna, --skip-ncrna, "
        "--skip-ncrna-region, --skip-crispr, --skip-cds, --skip-pseudo, --skip-sorf, --skip-gap, --skip-ori, "
        "--skip-plot"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "assembly.fna", "bakta_db": "/db", "amrfinder_db": "/amr", "output_selection": ["bad"]}
    ) == (
        "output_selection entries must be one of: file_tsv, file_gff3, file_gbff, file_embl, file_fna, "
        "file_ffn, file_faa, hypo_tsv, hypo_fa, sum_txt, file_json, file_plot, log_txt"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "assembly.fna", "bakta_db": "/db", "amrfinder_db": "/amr"}) is True


def test_bakta_environment_metadata_is_declared() -> None:
    registry = _registry()

    assert EXECUTABLE_TO_CONDA_PACKAGE["bakta"] == "bakta"
    assert PACKAGE_MIN_VERSIONS["bakta"] == ">=1.9.0"
    assert workflow_to_packages({"nodes": [{"id": "annotate", "type": "bakta"}]}, registry) == [
        "bakta",
        "cp",
        "ln",
        "mkdir",
    ]
