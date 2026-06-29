from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path
from typing import Any

from bionodulo.nodes.registry import NodeRegistry


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


class _RecordingCommandContext:
    def __init__(self, node_dir: Path) -> None:
        self.node_dir = node_dir
        self.commands: list[str | list[str]] = []

    async def run_command(self, cmd: str | list[str], **_: Any) -> dict[str, Any]:
        self.commands.append(cmd)
        if isinstance(cmd, list):
            try:
                output_path = Path(cmd[cmd.index("-o") + 1])
            except (ValueError, IndexError):
                output_path = self.node_dir / "fastani.tsv"
        else:
            output_path = self.node_dir / "fastani.tsv"
        output_path.write_text("q1.fna\tr1.fna\t99.9\t1200\t1200\n", encoding="utf-8")
        output_path.with_suffix(output_path.suffix + ".matrix").write_text("2\nq1\t0\n", encoding="utf-8")
        output_path.with_suffix(output_path.suffix + ".visual").write_text("q1\tr1\t1\t1200\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


def test_galaxy_parity_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "busco": {
            "display_name": "BUSCO",
            "category": "assembly",
            "required_executables": ["busco"],
            "required_conda_packages": ["busco"],
            "doi": "10.1093/bioinformatics/btv351",
        },
        "htseq_count": {
            "display_name": "HTSeq-count",
            "category": "rna_seq",
            "required_executables": ["htseq-count", "samtools"],
            "required_conda_packages": ["htseq", "samtools"],
            "doi": "10.1093/bioinformatics/btu638",
        },
        "seqkit_stats": {
            "display_name": "SeqKit Stats",
            "category": "qc",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_grep": {
            "display_name": "SeqKit Grep",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_head": {
            "display_name": "SeqKit Head",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_fx2tab": {
            "display_name": "SeqKit fx2tab",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_sort": {
            "display_name": "SeqKit Sort",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_locate": {
            "display_name": "SeqKit Locate",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_translate": {
            "display_name": "SeqKit Translate",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_split2": {
            "display_name": "SeqKit Split2",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "amrfinderplus": {
            "display_name": "AMRFinderPlus",
            "category": "annotation",
            "required_executables": ["amrfinder"],
            "required_conda_packages": ["ncbi-amrfinderplus"],
            "doi": "10.1038/s41598-021-91456-0",
        },
        "checkm2": {
            "display_name": "CheckM2",
            "category": "qc",
            "required_executables": ["checkm2"],
            "required_conda_packages": ["checkm2"],
            "doi": "10.1038/s41592-023-01940-w",
        },
        "das_tool": {
            "display_name": "DAS Tool",
            "category": "metagenomics",
            "required_executables": ["DAS_Tool"],
            "required_conda_packages": ["das_tool"],
            "doi": "10.1038/s41564-018-0171-1",
        },
        "fasta_to_contig2bin": {
            "display_name": "FASTA to Contig2Bin",
            "category": "metagenomics",
            "required_executables": ["Fasta_to_Contig2Bin.sh"],
            "required_conda_packages": ["das_tool"],
            "doi": "10.1038/s41564-018-0171-1",
        },
        "bandage_info": {
            "display_name": "Bandage Info",
            "category": "assembly",
            "required_executables": ["Bandage"],
            "required_conda_packages": ["bandage_ng"],
            "doi": "10.1093/bioinformatics/btv383",
        },
        "bandage_image": {
            "display_name": "Bandage Image",
            "category": "visualization",
            "required_executables": ["Bandage"],
            "required_conda_packages": ["bandage_ng"],
            "doi": "10.1093/bioinformatics/btv383",
        },
        "adapter_removal": {
            "display_name": "AdapterRemoval",
            "category": "trimming",
            "required_executables": ["AdapterRemoval"],
            "required_conda_packages": ["adapterremoval"],
            "doi": "10.1186/s13104-016-1900-2",
        },
        "assembly_stats": {
            "display_name": "Assembly Stats",
            "category": "assembly",
            "required_executables": ["asm2stats.minmaxgc.pl"],
            "required_conda_packages": ["rjchallis-assembly-stats"],
            "doi": "10.5281/zenodo.322347",
        },
        "amas_summary": {
            "display_name": "AMAS Summary",
            "category": "phylogeny",
            "required_executables": ["python"],
            "required_conda_packages": ["amas"],
            "doi": "10.7717/peerj.1660",
        },
        "amas_concat": {
            "display_name": "AMAS Concat",
            "category": "phylogeny",
            "required_executables": ["python"],
            "required_conda_packages": ["amas"],
            "doi": "10.7717/peerj.1660",
        },
        "vsearch_search": {
            "display_name": "VSEARCH Search",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_cluster": {
            "display_name": "VSEARCH Cluster",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_dereplication": {
            "display_name": "VSEARCH Dereplication",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_masking": {
            "display_name": "VSEARCH Masking",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_shuffling": {
            "display_name": "VSEARCH Shuffling",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_sorting": {
            "display_name": "VSEARCH Sorting",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_alignment": {
            "display_name": "VSEARCH Alignment",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_chimera_detection": {
            "display_name": "VSEARCH Chimera Detection",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "diamond_makedb": {
            "display_name": "DIAMOND MakeDB",
            "category": "databases",
            "required_executables": ["diamond"],
            "required_conda_packages": ["diamond"],
            "doi": "10.1038/s41592-021-01101-x",
        },
        "diamond_align": {
            "display_name": "DIAMOND Align",
            "category": "alignment",
            "required_executables": ["diamond"],
            "required_conda_packages": ["diamond"],
            "doi": "10.1038/s41592-021-01101-x",
        },
        "hmmer_hmmalign": {
            "display_name": "HMMER hmmalign",
            "category": "alignment",
            "required_executables": ["hmmalign"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmbuild": {
            "display_name": "HMMER hmmbuild",
            "category": "annotation",
            "required_executables": ["hmmbuild"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmconvert": {
            "display_name": "HMMER hmmconvert",
            "category": "annotation",
            "required_executables": ["hmmconvert"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmemit": {
            "display_name": "HMMER hmmemit",
            "category": "annotation",
            "required_executables": ["hmmemit"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmfetch": {
            "display_name": "HMMER hmmfetch",
            "category": "annotation",
            "required_executables": ["hmmfetch"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_jackhmmer": {
            "display_name": "HMMER jackhmmer",
            "category": "annotation",
            "required_executables": ["jackhmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_phmmer": {
            "display_name": "HMMER phmmer",
            "category": "annotation",
            "required_executables": ["phmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_nhmmer": {
            "display_name": "HMMER nhmmer",
            "category": "annotation",
            "required_executables": ["nhmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/bioinformatics/btt403",
        },
        "hmmer_nhmmscan": {
            "display_name": "HMMER nhmmscan",
            "category": "annotation",
            "required_executables": ["nhmmscan", "hmmpress"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/bioinformatics/btt403",
        },
        "hmmer_alimask": {
            "display_name": "HMMER alimask",
            "category": "annotation",
            "required_executables": ["alimask"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmsearch": {
            "display_name": "HMMER hmmsearch",
            "category": "annotation",
            "required_executables": ["hmmsearch"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmscan": {
            "display_name": "HMMER hmmscan",
            "category": "annotation",
            "required_executables": ["hmmscan"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "mmseqs2_easy_search": {
            "display_name": "MMseqs2 Easy Search",
            "category": "alignment",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/nbt.3988",
        },
        "mmseqs2_easy_cluster": {
            "display_name": "MMseqs2 Easy Cluster",
            "category": "clustering",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/nbt.3988",
        },
        "mmseqs2_easy_linclust_clustering": {
            "display_name": "MMseqs2 Easy Linclust",
            "category": "clustering",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/s41467-018-04964-5",
        },
        "mmseqs2_easy_linsearch": {
            "display_name": "MMseqs2 Easy Linsearch",
            "category": "alignment",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/nbt.3988",
        },
        "mmseqs2_easy_rbh": {
            "display_name": "MMseqs2 Easy RBH",
            "category": "alignment",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/nbt.3988",
        },
        "mmseqs2_easy_taxonomy": {
            "display_name": "MMseqs2 Easy Taxonomy",
            "category": "taxonomy",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1093/bioinformatics/btab184",
        },
        "mmseqs2_taxonomy_assignment": {
            "display_name": "MMseqs2 Taxonomy",
            "category": "taxonomy",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1093/bioinformatics/btab184",
        },
        "kaiju": {
            "display_name": "Kaiju",
            "category": "taxonomy",
            "required_executables": ["kaiju", "kaijup", "kaijux"],
            "required_conda_packages": ["kaiju"],
            "doi": "10.1038/ncomms11257",
        },
        "kaiju_add_taxon_names": {
            "display_name": "Kaiju Add Taxon Names",
            "category": "taxonomy",
            "required_executables": ["kaiju-addTaxonNames"],
            "required_conda_packages": ["kaiju"],
            "doi": "10.1038/ncomms11257",
        },
        "kaiju2krona": {
            "display_name": "Kaiju2Krona",
            "category": "taxonomy",
            "required_executables": ["kaiju2krona"],
            "required_conda_packages": ["kaiju"],
            "doi": "10.1038/ncomms11257",
        },
        "kaiju_merge_outputs": {
            "display_name": "Kaiju Merge Outputs",
            "category": "taxonomy",
            "required_executables": ["kaiju-mergeOutputs"],
            "required_conda_packages": ["kaiju"],
            "doi": "10.1038/ncomms11257",
        },
        "kaiju2table": {
            "display_name": "Kaiju2Table",
            "category": "taxonomy",
            "required_executables": ["kaiju2table"],
            "required_conda_packages": ["kaiju"],
            "doi": "10.1038/ncomms11257",
        },
        "kraken": {
            "display_name": "Kraken",
            "category": "metagenomics",
            "required_executables": ["kraken"],
            "required_conda_packages": ["kraken"],
            "doi": "10.1186/gb-2014-15-3-r46",
        },
        "kraken_filter": {
            "display_name": "Kraken Filter",
            "category": "metagenomics",
            "required_executables": ["kraken-filter"],
            "required_conda_packages": ["kraken"],
            "doi": "10.1186/gb-2014-15-3-r46",
        },
        "kraken_report": {
            "display_name": "Kraken Report",
            "category": "metagenomics",
            "required_executables": ["kraken-report"],
            "required_conda_packages": ["kraken"],
            "doi": "10.1186/gb-2014-15-3-r46",
        },
        "kraken_translate": {
            "display_name": "Kraken Translate",
            "category": "metagenomics",
            "required_executables": ["kraken-translate"],
            "required_conda_packages": ["kraken"],
            "doi": "10.1186/gb-2014-15-3-r46",
        },
        "kraken_mpa_report": {
            "display_name": "Kraken MPA Report",
            "category": "metagenomics",
            "required_executables": ["kraken-mpa-report"],
            "required_conda_packages": ["kraken"],
            "doi": "10.1186/gb-2014-15-3-r46",
        },
        "krakentools_combine_kreports": {
            "display_name": "Krakentools Combine Kraken Reports",
            "category": "taxonomy",
            "required_executables": ["combine_kreports.py"],
            "required_conda_packages": ["krakentools"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "krakentools_alpha_diversity": {
            "display_name": "Krakentools Alpha Diversity",
            "category": "taxonomy",
            "required_executables": ["alpha_diversity.py"],
            "required_conda_packages": ["krakentools"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "krakentools_beta_diversity": {
            "display_name": "Krakentools Beta Diversity",
            "category": "taxonomy",
            "required_executables": ["beta_diversity.py"],
            "required_conda_packages": ["krakentools"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "krakentools_kreport2krona": {
            "display_name": "Krakentools Kreport2Krona",
            "category": "taxonomy",
            "required_executables": ["kreport2krona.py"],
            "required_conda_packages": ["krakentools"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "krakentools_kreport2mpa": {
            "display_name": "Krakentools Kreport2MPA",
            "category": "taxonomy",
            "required_executables": ["kreport2mpa.py"],
            "required_conda_packages": ["krakentools"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "krakentools_extract_kraken_reads": {
            "display_name": "Krakentools Extract Kraken Reads By ID",
            "category": "taxonomy",
            "required_executables": ["extract_kraken_reads.py", "gzip"],
            "required_conda_packages": ["krakentools", "gzip"],
            "doi": "10.1038/s41596-022-00738-y",
        },
        "taxpasta": {
            "display_name": "Taxpasta",
            "category": "taxonomy",
            "required_executables": ["taxpasta"],
            "required_conda_packages": ["taxpasta"],
            "doi": "10.21105/joss.05627",
        },
        "humann_join_tables": {
            "display_name": "HUMAnN Join Tables",
            "category": "metagenomics",
            "required_executables": ["humann_join_tables"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_renorm_table": {
            "display_name": "HUMAnN Renormalize Table",
            "category": "metagenomics",
            "required_executables": ["humann_renorm_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_split_table": {
            "display_name": "HUMAnN Split Table",
            "category": "metagenomics",
            "required_executables": ["humann_split_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_split_stratified_table": {
            "display_name": "HUMAnN Split Stratified Table",
            "category": "metagenomics",
            "required_executables": ["humann_split_stratified_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_reduce_table": {
            "display_name": "HUMAnN Reduce Table",
            "category": "metagenomics",
            "required_executables": ["humann_reduce_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_regroup_table": {
            "display_name": "HUMAnN Regroup Table",
            "category": "metagenomics",
            "required_executables": ["humann_regroup_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_rename_table": {
            "display_name": "HUMAnN Rename Table",
            "category": "metagenomics",
            "required_executables": ["humann_rename_table"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_unpack_pathways": {
            "display_name": "HUMAnN Unpack Pathways",
            "category": "metagenomics",
            "required_executables": ["humann_unpack_pathways"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "humann_barplot": {
            "display_name": "HUMAnN Barplot",
            "category": "metagenomics",
            "required_executables": ["humann_barplot"],
            "required_conda_packages": ["humann"],
            "doi": "10.7554/eLife.65088",
        },
        "hybpiper": {
            "display_name": "HybPiper",
            "category": "phylogeny",
            "required_executables": ["hybpiper"],
            "required_conda_packages": ["hybpiper"],
            "doi": "10.3732/apps.1600016",
        },
        "hyphy_absrel": {
            "display_name": "HyPhy-aBSREL",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msv022",
        },
        "hyphy_annotate": {
            "display_name": "HyPhy Annotate",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msz197",
        },
        "hyphy_b_still": {
            "display_name": "HyPhy-B-STILL",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/mst030",
        },
        "hyphy_bgm": {
            "display_name": "HyPhy-BGM",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/bioinformatics/btn313",
        },
        "hyphy_fade": {
            "display_name": "HyPhy-FADE",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/mst030",
        },
        "hyphy_fel": {
            "display_name": "HyPhy-FEL",
            "category": "phylogeny",
            "required_executables": ["HYPHYMPI", "mpirun"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msi105",
        },
        "hyphy_fubar": {
            "display_name": "HyPhy-FUBAR",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/mst030",
        },
        "hyphy_gard": {
            "display_name": "HyPhy-GARD",
            "category": "phylogeny",
            "required_executables": ["HYPHYMPI", "mpirun"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msl051",
        },
        "hyphy_infer_stasis_clusters": {
            "display_name": "HyPhy-Infer Stasis Clusters",
            "category": "phylogeny",
            "required_executables": ["python3"],
            "required_conda_packages": ["python", "numpy", "scipy"],
            "doi": "10.1093/molbev/msz197",
        },
        "hyphy_meme": {
            "display_name": "HyPhy-MEME",
            "category": "phylogeny",
            "required_executables": ["HYPHYMPI", "mpirun"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1371/journal.pgen.1002764",
        },
        "hyphy_prime": {
            "display_name": "HyPhy-PRIME",
            "category": "phylogeny",
            "required_executables": ["HYPHYMPI", "mpirun"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.64898/2026.03.09.710461",
        },
        "hyphy_relax": {
            "display_name": "HyPhy-RELAX",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msu400",
        },
        "hyphy_slac": {
            "display_name": "HyPhy-SLAC",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msi105",
        },
        "hyphy_sm19": {
            "display_name": "HyPhy-SM2019",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/genetics/123.3.603",
        },
        "hyphy_strike_ambigs": {
            "display_name": "Replace ambiguous codons",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/bioinformatics/bti079",
        },
        "hyphy_busted": {
            "display_name": "HyPhy-BUSTED",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msv035",
        },
        "hyphy_cfel": {
            "display_name": "HyPhy-CFEL",
            "category": "phylogeny",
            "required_executables": ["HYPHYMPI", "mpirun"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msaa263",
        },
        "hyphy_conv": {
            "display_name": "HyPhy-Conv",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msz197",
        },
        "hyphy_cln": {
            "display_name": "HyPhy-CLN",
            "category": "phylogeny",
            "required_executables": ["hyphy"],
            "required_conda_packages": ["hyphy"],
            "doi": "10.1093/molbev/msz197",
        },
        "merge_metaphlan_tables": {
            "display_name": "Merge MetaPhlAn Tables",
            "category": "metagenomics",
            "required_executables": ["merge_metaphlan_tables.py"],
            "required_conda_packages": ["metaphlan"],
            "doi": "10.1038/s41587-023-01688-w",
        },
        "extract_metaphlan_database": {
            "display_name": "Extract MetaPhlAn DB",
            "category": "metagenomics",
            "required_executables": ["bowtie2-inspect", "python"],
            "required_conda_packages": ["metaphlan"],
            "doi": "10.1038/s41587-023-01688-w",
        },
        "customize_metaphlan_database": {
            "display_name": "Customize MetaPhlAn DB",
            "category": "metagenomics",
            "required_executables": ["python", "seqtk"],
            "required_conda_packages": ["metaphlan", "seqtk"],
            "doi": "10.1038/s41587-023-01688-w",
        },
        "recentrifuge": {
            "display_name": "Recentrifuge",
            "category": "metagenomics",
            "required_executables": ["rcf"],
            "required_conda_packages": ["recentrifuge"],
            "doi": "10.1371/journal.pcbi.1006967",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith(("https://", "http://"))
        assert "Galaxy" in node_info["search_aliases"]


def test_busco_renders_galaxy_aligned_completeness_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("busco")

    cmd = node_class.render_command(
        {
            "input": "assembly.fasta",
            "mode": "genome",
            "lineage_dataset": "bacteria_odb10",
            "lineage_mode": "select_lineage",
            "gene_predictor": "miniprot",
            "threads": 8,
            "offline": True,
            "download_path": "/db/busco",
            "evalue": 0.001,
            "limit": 3,
            "contig_break": 10,
            "output": "/work/busco",
        }
    )

    assert cmd == [
        "busco",
        "--in",
        "assembly.fasta",
        "--mode",
        "genome",
        "--out",
        "busco_galaxy",
        "--out_path",
        "/work/busco",
        "--cpu",
        "8",
        "--evalue",
        "0.001",
        "--limit",
        "3",
        "--contig_break",
        "10",
        "--offline",
        "--download_path",
        "/db/busco",
        "--lineage_dataset",
        "bacteria_odb10",
        "--miniprot",
    ]

    outputs = node_class.PLAN_OUTPUTS({}, tmp_path)
    assert outputs == [
        tmp_path / "busco" / "short_summary.txt",
        tmp_path / "busco" / "full_table.tsv",
        tmp_path / "busco" / "missing_buscos.tsv",
        tmp_path / "busco" / "summary.png",
    ]


def test_htseq_count_renders_counting_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("htseq_count")

    cmd = node_class.render_command(
        {
            "samfile": "aligned.bam",
            "gfffile": "genes.gtf",
            "mode": "intersection-nonempty",
            "stranded": "reverse",
            "minaqual": 10,
            "featuretype": "exon",
            "idattr": "gene_id",
            "nonunique": "fraction",
            "secondary_alignments": "ignore",
            "supplementary_alignments": "score",
            "order": "name",
            "sort_bam": True,
            "output": "/work/htseq_count",
        }
    )

    assert cmd == [
        "samtools",
        "sort",
        "-n",
        "-o",
        "/work/htseq_count/name_sorted.bam",
        "aligned.bam",
        "&&",
        "htseq-count",
        "--format=bam",
        "--mode=intersection-nonempty",
        "--stranded=reverse",
        "--minaqual=10",
        "--type=exon",
        "--idattr=gene_id",
        "--nonunique=fraction",
        "--secondary-alignments=ignore",
        "--supplementary-alignments=score",
        "--order=name",
        "/work/htseq_count/name_sorted.bam",
        "genes.gtf",
        ">",
        "/work/htseq_count/counts.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "htseq_count" / "counts.tsv"]


def test_seqkit_stats_renders_statistics_command() -> None:
    node_class = _node_class("seqkit_stats")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "all": True,
            "basename": True,
            "skip_err": True,
            "tabular": True,
            "output": "/work/seqkit_stats",
        }
    ) == [
        "seqkit",
        "stats",
        "reads.fastq.gz",
        "--all",
        "--basename",
        "--skip-err",
        "--tabular",
        ">",
        "/work/seqkit_stats/stats.tsv",
    ]


def test_seqkit_grep_exposes_sequence_and_count_outputs() -> None:
    info = _registry().object_info()["seqkit_grep"]

    assert info["output"] == ["FASTQ", "FASTA", "STATS_FILE"]
    assert info["output_name"] == ["fastq_output", "fasta_output", "count"]


def test_seqkit_grep_renders_sequence_expression_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_grep")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "pattern_mode": "expression",
            "pattern": "ATGC",
            "by_seq": True,
            "max_mismatch": 2,
            "ignore_case": True,
            "only_positive_strand": True,
            "region": "1:120",
            "threads": 6,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_grep",
        }
    ) == [
        "seqkit",
        "grep",
        "--threads",
        "6",
        "--pattern",
        "ATGC",
        "--by-seq",
        "--ignore-case",
        "--max-mismatch",
        "2",
        "--only-positive-strand",
        "--region",
        "1:120",
        "reads.fastq.gz",
        ">",
        "/work/seqkit_grep/grep.fastq.gz",
    ]
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_grep" / "grep.fastq.gz",
    ]


def test_seqkit_grep_renders_pattern_file_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_grep")

    assert node_class.render_command(
        {
            "input": "records.fasta.gz",
            "pattern_mode": "file",
            "pattern_file": "patterns.txt",
            "allow_duplicated_patterns": True,
            "by_name": True,
            "circular": True,
            "count": True,
            "degenerate": True,
            "delete_matched": True,
            "invert_match": True,
            "threads": 4,
            "output": "/work/seqkit_grep",
        }
    ) == [
        "seqkit",
        "grep",
        "--threads",
        "4",
        "--pattern-file",
        "patterns.txt",
        "--allow-duplicated-patterns",
        "--by-name",
        "--circular",
        "--count",
        "--degenerate",
        "--delete-matched",
        "--invert-match",
        "records.fasta.gz",
        ">",
        "/work/seqkit_grep/count.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"count": True}, tmp_path) == [
        tmp_path / "seqkit_grep" / "count.txt",
    ]


def test_seqkit_head_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_head"]

    assert info["output"] == ["FASTQ"]
    assert info["output_name"] == ["head_output"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_head_renders_head_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_head")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "number": 25,
            "threads": 8,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_head",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastq.gz && "
        "seqkit head input.fastq.gz --number 25 -o /work/seqkit_head/head.fastq.gz --threads 8"
    )
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_head" / "head.fastq.gz",
    ]


def test_seqkit_fx2tab_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_fx2tab"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["tabular"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_fx2tab_renders_rich_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_fx2tab")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "input_ext": "fastqsanger.gz",
            "alphabet": True,
            "avg_qual": True,
            "base_percentages": ["A", "T"],
            "base_counts": ["A", "N"],
            "gc": True,
            "gc_skew": True,
            "header_line": True,
            "length": True,
            "name": True,
            "no_qual": True,
            "only_id": True,
            "seq_hash": True,
            "qual_ascii_base": 33,
            "output": "/work/seqkit_fx2tab",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastqsanger.gz && "
        "seqkit fx2tab input.fastqsanger.gz --alphabet --avg-qual -B AT -C AN --gc --gc-skew "
        "--header-line --length --name --no-qual --only-id --qual-ascii-base 33 --seq-hash "
        "> /work/seqkit_fx2tab/fx2tab.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "seqkit_fx2tab" / "fx2tab.tsv",
    ]


def test_seqkit_sort_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_sort"]

    assert info["output"] == ["FASTQ"]
    assert info["output_name"] == ["sorted_sequences"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_sort_renders_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_sort")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "input_ext": "fastq.gz",
            "output_ext": "fastq.gz",
            "sort_by": "--by-seq",
            "reverse": True,
            "threads": 12,
            "output": "/work/seqkit_sort",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastq.gz && "
        "seqkit sort input.fastq.gz --reverse --by-seq -o /work/seqkit_sort/sorted.fastq.gz --threads 12"
    )
    assert node_class.PLAN_OUTPUTS({"output_ext": "fasta.gz"}, tmp_path) == [
        tmp_path / "seqkit_sort" / "sorted.fasta.gz",
    ]


def test_seqkit_locate_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_locate"]

    assert info["output"] == ["TSV", "BED", "GFF_GTF"]
    assert info["output_name"] == ["tabular", "bed", "gtf"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_locate_renders_expression_bed_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_locate")

    assert node_class.render_command(
        {
            "input": "genome.fasta.gz",
            "input_ext": "fasta.gz",
            "pattern_mode": "expression",
            "pattern": "A[TU]G",
            "use_regexp": True,
            "output_mode": "--bed",
            "circular": True,
            "hide_matched": True,
            "ignore_case": True,
            "max_mismatch": 1,
            "only_positive_strand": True,
            "id_ncbi": True,
            "seq_type": "dna",
            "threads": 8,
            "output": "/work/seqkit_locate",
        }
    ) == (
        "ln -sf genome.fasta.gz input.fasta.gz && "
        "seqkit locate --threads 8 --pattern 'A[TU]G' --use-regexp --bed --circular "
        "--hide-matched --ignore-case --max-mismatch 1 --only-positive-strand --id-ncbi "
        "--seq-type dna input.fasta.gz > /work/seqkit_locate/locate.bed"
    )
    assert node_class.PLAN_OUTPUTS({"output_mode": "--bed"}, tmp_path) == [
        tmp_path / "seqkit_locate" / "locate.bed",
    ]


def test_seqkit_locate_renders_pattern_file_gtf_command_without_incompatible_fmi(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_locate")

    command = node_class.render_command(
        {
            "input": "records.fasta",
            "input_ext": "fasta",
            "pattern_mode": "file",
            "pattern_file": "motifs.fasta",
            "output_mode": "--gtf",
            "degenerate": True,
            "max_mismatch": 2,
            "use_fmi": True,
            "non_greedy": True,
            "seq_type": "protein",
            "threads": 4,
            "output": "/work/seqkit_locate",
        }
    )

    assert command == (
        "ln -sf records.fasta input.fasta && "
        "seqkit locate --threads 4 --pattern-file motifs.fasta --gtf --degenerate "
        "--non-greedy --seq-type protein input.fasta > /work/seqkit_locate/locate.gtf"
    )
    assert "--max-mismatch" not in command
    assert "--use-fmi" not in command
    assert node_class.PLAN_OUTPUTS({"output_mode": "--gtf"}, tmp_path) == [
        tmp_path / "seqkit_locate" / "locate.gtf",
    ]


def test_seqkit_translate_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_translate"]

    assert info["output"] == ["FASTA", "FASTQ"]
    assert info["output_name"] == ["translated_fasta", "translated_fastq"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_translate_renders_multiframe_unknown_codon_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_translate")

    assert node_class.render_command(
        {
            "input": "cds.fasta.gz",
            "frame": ["2", "3"],
            "unknown_action": "translate",
            "allow_unknown_codon": True,
            "append_frame": True,
            "clean": True,
            "init_codon_as_M": True,
            "transl_table": "3",
            "output_ext": "fasta.gz",
            "output": "/work/seqkit_translate",
        }
    ) == [
        "seqkit",
        "translate",
        "cds.fasta.gz",
        "-o",
        "/work/seqkit_translate/translated.fasta.gz",
        "--allow-unknown-codon",
        "--append-frame",
        "--clean",
        "-f",
        "2,3",
        "--init-codon-as-M",
        "-T",
        "3",
    ]
    assert node_class.PLAN_OUTPUTS({"output_ext": "fasta.gz"}, tmp_path) == [
        tmp_path / "seqkit_translate" / "translated.fasta.gz",
    ]


def test_seqkit_translate_renders_trim_fastq_command_without_unknown_translation(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_translate")

    command = node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "unknown_action": "trimming",
            "trim": True,
            "allow_unknown_codon": True,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_translate",
        }
    )

    assert command == [
        "seqkit",
        "translate",
        "reads.fastq.gz",
        "-o",
        "/work/seqkit_translate/translated.fastq.gz",
        "--trim",
        "-f",
        "1",
        "-T",
        "1",
    ]
    assert "--allow-unknown-codon" not in command
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_translate" / "translated.fastq.gz",
    ]


def test_seqkit_split2_exposes_galaxy_aligned_directory_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_split2"]

    assert info["output"] == ["DIRECTORY", "DIRECTORY"]
    assert info["output_name"] == ["split_files", "paired_split_files"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_split2_renders_single_length_split_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_split2")

    assert node_class.render_command(
        {
            "input_type": "single",
            "input_1": "hairpin.fa.gz",
            "input_1_ext": "fasta.gz",
            "split_selector": "by_length",
            "by_length": "50K",
            "threads": 6,
            "output": "/work/seqkit_split2",
        }
    ) == (
        "mkdir -p /work/seqkit_split2/split_files && "
        "ln -sf hairpin.fa.gz input.fasta.gz && "
        "seqkit split2 input.fasta.gz -l 50K -o seqkit_split2 "
        "-O /work/seqkit_split2/split_files -j 6"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "single"}, tmp_path) == [
        tmp_path / "seqkit_split2" / "split_files",
    ]


def test_seqkit_split2_renders_paired_part_split_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_split2")

    assert node_class.render_command(
        {
            "input_type": "paired_collection",
            "input_1": "reads_1.fq.gz",
            "input_2": "reads_2.fq.gz",
            "input_1_ext": "fastqsanger.gz",
            "input_2_ext": "fastqsanger.gz",
            "split_selector": "by_part",
            "by_part": 2,
            "threads": 8,
            "output": "/work/seqkit_split2",
        }
    ) == (
        "mkdir -p /work/seqkit_split2/paired_split_files && "
        "ln -sf reads_1.fq.gz input_1.fastqsanger.gz && "
        "ln -sf reads_2.fq.gz input_2.fastqsanger.gz && "
        "seqkit split2 -1 input_1.fastqsanger.gz -2 input_2.fastqsanger.gz "
        "-p 2 --by-part-prefix 'seqkit_split2_R{read}_' -o seqkit_split2 "
        "-O /work/seqkit_split2/paired_split_files -j 8 && "
        "(find /work/seqkit_split2/paired_split_files/ -type f -name 'seqkit_split2_*.*' | "
        "while read -r file; do mv \"$file\" \"$(echo \"$file\" | "
        "sed -E 's/(seqkit_split2)_(R1|R2)_([0-9]+)(\\..+)/\\1_\\3_\\2\\4/' | "
        "sed -E 's/_R1/_forward/; s/_R2/_reverse/')\"; done)"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "paired_collection"}, tmp_path) == [
        tmp_path / "seqkit_split2" / "paired_split_files",
    ]


def test_amrfinderplus_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amrfinderplus"]

    assert info["output"] == ["TSV", "TSV", "FASTA", "FASTA", "FASTA"]
    assert info["output_name"] == [
        "amrfinderplus_report",
        "mutation_all_report",
        "protein_output",
        "nucleotide_output",
        "nucleotide_flank5_output",
    ]


def test_amrfinderplus_renders_nucleotide_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amrfinderplus")

    assert node_class.render_command(
        {
            "database": "/db/amrfinderplus/latest",
            "input_select": "nucleotide",
            "nucleotide_input": "enterococcus_faecalis.fna",
            "nucleotide_flank5_size": 150,
            "organism_select": "add_organism",
            "organism": "Enterococcus_faecalis",
            "plus": True,
            "report_common": True,
            "ident_min": 0.1,
            "coverage_min": 0.1,
            "translation_table": "11",
            "report_all_equal": True,
            "print_node": True,
            "name": "sample_1",
            "threads": 8,
            "output": "/work/amrfinderplus",
        }
    ) == [
        "amrfinder",
        "--threads",
        "8",
        "--database",
        "/db/amrfinderplus/latest",
        "--nucleotide",
        "enterococcus_faecalis.fna",
        "--nucleotide_flank5_size",
        "150",
        "--nucleotide_flank5_output",
        "/work/amrfinderplus/amrfinderplus_flanking_sequence_output.fasta",
        "--nucleotide_output",
        "/work/amrfinderplus/amrfinderplus_nucleotide_output.fasta",
        "--organism",
        "Enterococcus_faecalis",
        "--report_common",
        "--ident_min",
        "0.1",
        "--coverage_min",
        "0.1",
        "--translation_table",
        "11",
        "--name",
        "sample_1",
        "--plus",
        "--report_all_equal",
        "--print_node",
        "--output",
        "/work/amrfinderplus/amrfinderplus_report.tsv",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"input_select": "nucleotide", "nucleotide_flank5_size": 150},
        tmp_path,
    ) == [
        tmp_path / "amrfinderplus" / "amrfinderplus_report.tsv",
        tmp_path / "amrfinderplus" / "amrfinderplus_nucleotide_output.fasta",
        tmp_path / "amrfinderplus" / "amrfinderplus_flanking_sequence_output.fasta",
    ]


def test_amrfinderplus_renders_combined_mode_with_mutation_and_version_columns(tmp_path: Path) -> None:
    node_class = _node_class("amrfinderplus")

    assert node_class.render_command(
        {
            "database": "/db/amrfinderplus/V4.2-2026-05-15.1",
            "database_name": "V4.2-2026-05-15.1",
            "input_select": "nucl_prot",
            "nucleotide_input": "e_faecalis_rast.fna",
            "protein_input": "e_faecalis_rast.faa",
            "gff_annotation": "e_faecalis_rast.gff",
            "annotation_format": "rast",
            "organism_select": "add_organism",
            "organism": "Enterococcus_faecalis",
            "mutation_all": True,
            "ident_min": 0.1,
            "coverage_min": 0.1,
            "plus": True,
            "print_node": True,
            "name": "test_5",
            "add_version_columns": True,
            "threads": 4,
            "output": "/work/amrfinderplus",
        }
    ) == [
        "amrfinder",
        "--threads",
        "4",
        "--database",
        "/db/amrfinderplus/V4.2-2026-05-15.1",
        "--nucleotide",
        "e_faecalis_rast.fna",
        "--protein",
        "e_faecalis_rast.faa",
        "--gff",
        "e_faecalis_rast.gff",
        "--annotation_format",
        "rast",
        "--nucleotide_output",
        "/work/amrfinderplus/amrfinderplus_nucleotide_output.fasta",
        "--protein_output",
        "/work/amrfinderplus/amrfinderplus_protein_output.fasta",
        "--organism",
        "Enterococcus_faecalis",
        "--mutation_all",
        "/work/amrfinderplus/mutation_all_report.tsv",
        "--ident_min",
        "0.1",
        "--coverage_min",
        "0.1",
        "--name",
        "test_5",
        "--plus",
        "--print_node",
        "--output",
        "/work/amrfinderplus/amrfinderplus_report.tsv",
        "&&",
        "python",
        "-c",
        (
            "from pathlib import Path\n"
            "tool_version = '4.2.7'\n"
            "database = Path('/db/amrfinderplus/V4.2-2026-05-15.1')\n"
            "database_version = (database / 'version.txt').read_text().strip() if (database / 'version.txt').is_file() else 'V4.2-2026-05-15.1'\n"
            "for report in [Path('/work/amrfinderplus/amrfinderplus_report.tsv'), Path('/work/amrfinderplus/mutation_all_report.tsv')]:\n"
            "    if not report.is_file() or report.stat().st_size == 0:\n"
            "        continue\n"
            "    lines = report.read_text().splitlines()\n"
            "    if not lines:\n"
            "        continue\n"
            "    updated = [lines[0] + '\\tDatabase version\\tTool version']\n"
            "    updated.extend(line + '\\t' + database_version + '\\t' + tool_version for line in lines[1:])\n"
            "    report.write_text('\\n'.join(updated) + '\\n')\n"
        ),
    ]
    assert node_class.PLAN_OUTPUTS(
        {"input_select": "nucl_prot", "organism_select": "add_organism", "mutation_all": True},
        tmp_path,
    ) == [
        tmp_path / "amrfinderplus" / "amrfinderplus_report.tsv",
        tmp_path / "amrfinderplus" / "mutation_all_report.tsv",
        tmp_path / "amrfinderplus" / "amrfinderplus_protein_output.fasta",
        tmp_path / "amrfinderplus" / "amrfinderplus_nucleotide_output.fasta",
    ]


def test_checkm2_exposes_quality_and_discovered_output_collections() -> None:
    info = _registry().object_info()["checkm2"]

    assert info["output"] == ["TSV", "FASTA_LIST", "TSV_LIST"]
    assert info["output_name"] == ["quality", "protein_files", "diamond_files"]


def test_checkm2_renders_protein_all_models_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("checkm2")

    assert node_class.render_command(
        {
            "input": ["test1.faa", "test2.faa"],
            "database_path": "/db/checkm2/uniref100.KO.1.dmnd",
            "model": "--allmodels",
            "genes": True,
            "ttable": "13",
            "threads": 12,
            "output": "/work/checkm2",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/checkm2/input_dir",
        "/work/checkm2/output",
        "&&",
        "ln",
        "-sf",
        "test1.faa",
        "/work/checkm2/input_dir/test1.faa.dat",
        "&&",
        "ln",
        "-sf",
        "test2.faa",
        "/work/checkm2/input_dir/test2.faa.dat",
        "&&",
        "checkm2",
        "predict",
        "--input",
        "/work/checkm2/input_dir",
        "--allmodels",
        "--genes",
        "--ttable",
        "13",
        "-x",
        ".dat",
        "--threads",
        "12",
        "--database_path",
        "/db/checkm2/uniref100.KO.1.dmnd",
        "--output-directory",
        "/work/checkm2/output",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "checkm2" / "output" / "quality_report.tsv",
        tmp_path / "checkm2" / "output" / "protein_files",
        tmp_path / "checkm2" / "output" / "diamond_output",
    ]


def test_checkm2_renders_specific_model_command_with_safe_input_names() -> None:
    node_class = _node_class("checkm2")

    assert node_class.render_command(
        {
            "input": ["MAG 01.fna", "bin#2.fa.gz"],
            "database_path": "/db/checkm2/current.dmnd",
            "model": "--specific",
            "genes": False,
            "threads": 4,
            "output": "/work/checkm2",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/checkm2/input_dir",
        "/work/checkm2/output",
        "&&",
        "ln",
        "-sf",
        "MAG 01.fna",
        "/work/checkm2/input_dir/MAG_01.fna.dat",
        "&&",
        "ln",
        "-sf",
        "bin#2.fa.gz",
        "/work/checkm2/input_dir/bin_2.fa.gz.dat",
        "&&",
        "checkm2",
        "predict",
        "--input",
        "/work/checkm2/input_dir",
        "--specific",
        "-x",
        ".dat",
        "--threads",
        "4",
        "--database_path",
        "/db/checkm2/current.dmnd",
        "--output-directory",
        "/work/checkm2/output",
    ]


def test_das_tool_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["das_tool"]

    assert info["output"] == ["TSV", "TSV", "TEXT", "TSV", "FASTA_LIST", "FASTA", "FASTA"]
    assert info["output_name"] == [
        "summary",
        "contigs2bin",
        "log",
        "eval",
        "bins",
        "unbinned_contigs",
        "proteins",
    ]


def test_das_tool_renders_command_with_proteins_and_binning_labels(tmp_path: Path) -> None:
    node_class = _node_class("das_tool")

    assert node_class.render_command(
        {
            "contigs": "assembly.fasta",
            "bins": ["metabat.tabular", "MaxBin bins.tsv"],
            "labels": ["", "max bin!"],
            "proteins": "predicted proteins.faa",
            "search_engine": "blastp",
            "score_threshold": 0.6,
            "duplicate_penalty": 0.7,
            "megabin_penalty": 0.2,
            "max_iter_post_threshold": 12,
            "write_bin_evals": True,
            "write_bins": "",
            "write_unbinned": True,
            "debug": True,
            "threads": 8,
            "output": "/work/das_tool",
        }
    ) == [
        "ln",
        "-sf",
        "predicted proteins.faa",
        "/work/das_tool/proteins",
        "&&",
        "DAS_Tool",
        "--contigs",
        "assembly.fasta",
        "--outputbasename",
        "/work/das_tool/outputs",
        "--bins",
        "metabat.tabular,MaxBin bins.tsv",
        "--labels",
        "metabat.tabular,max_bin_",
        "--search_engine",
        "blastp",
        "--proteins",
        "/work/das_tool/proteins",
        "--score_threshold",
        "0.6",
        "--duplicate_penalty",
        "0.7",
        "--megabin_penalty",
        "0.2",
        "--max_iter_post_threshold",
        "12",
        "--write_bin_evals",
        "--debug",
        "--threads",
        "8",
    ]
    assert node_class.PLAN_OUTPUTS({"write_bin_evals": True, "write_bins": ""}, tmp_path) == [
        tmp_path / "das_tool" / "outputs_DASTool_summary.tsv",
        tmp_path / "das_tool" / "outputs_DASTool_contig2bin.tsv",
        tmp_path / "das_tool" / "outputs_DASTool.log",
        tmp_path / "das_tool" / "outputs_allBins.eval",
    ]


def test_das_tool_plans_optional_bins_unbinned_and_proteins_outputs(tmp_path: Path) -> None:
    node_class = _node_class("das_tool")

    assert node_class.render_command(
        {
            "contigs": "assembly.fasta",
            "binning": [
                {"bins": "metabat.tabular", "labels": "metabat"},
                {"bins": "concoct table.tsv", "labels": "concoct"},
            ],
            "search_engine": "diamond",
            "score_threshold": 0.5,
            "duplicate_penalty": 0.6,
            "megabin_penalty": 0.5,
            "max_iter_post_threshold": 10,
            "output_proteins": True,
            "write_bins": "--write_bins",
            "write_unbinned": True,
            "threads": 4,
            "output": "/work/das_tool",
        }
    ) == [
        "DAS_Tool",
        "--contigs",
        "assembly.fasta",
        "--outputbasename",
        "/work/das_tool/outputs",
        "--bins",
        "metabat.tabular,concoct table.tsv",
        "--labels",
        "metabat,concoct",
        "--search_engine",
        "diamond",
        "--score_threshold",
        "0.5",
        "--duplicate_penalty",
        "0.6",
        "--megabin_penalty",
        "0.5",
        "--max_iter_post_threshold",
        "10",
        "--write_bins",
        "--write_unbinned",
        "--threads",
        "4",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"output_proteins": True, "write_bins": "--write_bins", "write_unbinned": True},
        tmp_path,
    ) == [
        tmp_path / "das_tool" / "outputs_DASTool_summary.tsv",
        tmp_path / "das_tool" / "outputs_DASTool_contig2bin.tsv",
        tmp_path / "das_tool" / "outputs_DASTool.log",
        tmp_path / "das_tool" / "outputs_DASTool_bins",
        tmp_path / "das_tool" / "outputs_DASTool_bins" / "unbinned.fa",
        tmp_path / "das_tool" / "outputs_proteins.faa",
    ]


def test_fasta_to_contig2bin_exposes_single_tabular_output() -> None:
    info = _registry().object_info()["fasta_to_contig2bin"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["contigs2bin"]


def test_fasta_to_contig2bin_renders_galaxy_helper_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("fasta_to_contig2bin")

    assert node_class.render_command(
        {
            "inputs": ["maxbin2.001.fa", "bin set/002.fa"],
            "element_identifiers": ["001", "bin/set 002"],
            "output": "/work/fasta_to_contig2bin",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/fasta_to_contig2bin/inputs",
        "&&",
        "ln",
        "-sf",
        "maxbin2.001.fa",
        "/work/fasta_to_contig2bin/inputs/001.fasta",
        "&&",
        "ln",
        "-sf",
        "bin set/002.fa",
        "/work/fasta_to_contig2bin/inputs/bin_set_002.fasta",
        "&&",
        "Fasta_to_Contig2Bin.sh",
        "--extension",
        "fasta",
        "--input_folder",
        "/work/fasta_to_contig2bin/inputs",
        ">",
        "/work/fasta_to_contig2bin/contigs2bin.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "fasta_to_contig2bin" / "contigs2bin.tsv",
    ]


def test_bandage_nodes_expose_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()

    assert info["bandage_info"]["output"] == ["TSV"]
    assert info["bandage_info"]["output_name"] == ["outfile"]
    assert info["bandage_image"]["output"] == ["IMAGE"]
    assert info["bandage_image"]["output_name"] == ["outfile"]


def test_bandage_info_renders_headless_statistics_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bandage_info")

    assert node_class.render_command(
        {
            "input_file": "assembly graph.gfa",
            "tsv": True,
            "output": "/work/bandage_info",
        }
    ) == [
        "ln",
        "-sf",
        "assembly graph.gfa",
        "/work/bandage_info/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
        "Bandage",
        "info",
        "/work/bandage_info/input.gfa",
        "--tsv",
        "|",
        "sed",
        r"s/:\s\+/:\t/g",
        ">",
        "/work/bandage_info/out.tab",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bandage_info" / "out.tab",
    ]


def test_bandage_image_renders_graph_image_command_and_dynamic_output(tmp_path: Path) -> None:
    node_class = _node_class("bandage_image")

    assert node_class.render_command(
        {
            "input_file": "assembly.fastg",
            "output_format": "svg",
            "height": 800,
            "width": 1200,
            "fontsize": 12,
            "nodewidth": 8.5,
            "names": True,
            "lengths": True,
            "output": "/work/bandage_image",
        }
    ) == [
        "ln",
        "-sf",
        "assembly.fastg",
        "/work/bandage_image/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
        "Bandage",
        "image",
        "/work/bandage_image/input.gfa",
        "/work/bandage_image/out.svg",
        "--height",
        "800",
        "--width",
        "1200",
        "--fontsize",
        "12",
        "--nodewidth",
        "8.5",
        "--names",
        "--lengths",
    ]
    assert node_class.PLAN_OUTPUTS({"output_format": "svg"}, tmp_path) == [
        tmp_path / "bandage_image" / "out.svg",
    ]


def test_adapter_removal_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["adapter_removal"]

    assert info["output"] == [
        "TEXT",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
    ]
    assert info["output_name"] == [
        "output_settings",
        "output_truncated",
        "output_forward_truncated",
        "output_reverse_truncated",
        "output_interleaved_truncated",
        "output_singleton_truncated",
        "output_collapsed",
        "output_collapsed_truncated",
        "output_discarded",
    ]
    assert (
        info["citation_text"]
        == "AdapterRemoval v2: rapid adapter trimming, identification, and read merging."
    )


def test_adapter_removal_renders_single_read_defaults_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("adapter_removal")

    assert node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads1.fastq.gz",
            "output": "/work/adapter_removal",
        }
    ) == (
        "ln -sf reads1.fastq.gz read1fastqsanger.gz && "
        "AdapterRemoval --file1 read1fastqsanger.gz --threads ${GALAXY_SLOTS:-8} "
        "--qualitybase 33 --qualitybase-output 33 --qualitymax 41 "
        "--adapter1 AGATCGGAAGAGCACACGTCTGAACTCCAGTCACNNNNNNATCTCGTATGCCGTCTTCTGCTTG "
        "--adapter2 AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT "
        "--minadapteroverlap 0 --mm 3.0 --shift 2 --maxns 1000 --minquality 2 "
        "--minlength 15 --maxlength 4294967295 --minalignmentlength 11 "
        "--settings /work/adapter_removal/output_settings.txt "
        "--output1 /work/adapter_removal/output_truncated.fastq"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "single"}, tmp_path) == [
        tmp_path / "adapter_removal" / "output_settings.txt",
        tmp_path / "adapter_removal" / "output_truncated.fastq",
    ]


def test_adapter_removal_renders_paired_interleaved_command_and_optional_outputs(tmp_path: Path) -> None:
    node_class = _node_class("adapter_removal")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fq.gz",
            "read2": "sample R2.fq.gz",
            "interleaved_output": "yes",
            "identify_adapters": True,
            "combined_output": True,
            "convert_uracils": True,
            "mask_degenerate_bases": True,
            "adapter_list": "adapters.tsv",
            "trim5p": True,
            "trim5p_mate1": 2,
            "trim5p_mate2": 3,
            "trim3p": True,
            "trim3p_mate1": 4,
            "trim3p_mate2": 5,
            "trimns": True,
            "trimqualities": True,
            "sliding_window": True,
            "window_size": 8,
            "preserve5p": True,
            "collapse": True,
            "collapse_deterministic": True,
            "collapse_conservatively": True,
            "output_select": "output_singleton,output_collapsed,output_collapsed_truncated,output_discarded",
            "output": "/work/adapter_removal",
        }
    ) == (
        "ln -sf 'sample R1.fq.gz' read1fastqsanger.gz && "
        "ln -sf 'sample R2.fq.gz' read2fastqsanger.gz && "
        "AdapterRemoval --file1 read1fastqsanger.gz --file2 read2fastqsanger.gz "
        "--identify-adapters --interleaved-output --combined-output "
        "--threads ${GALAXY_SLOTS:-8} --qualitybase 33 --qualitybase-output 33 --qualitymax 41 "
        "--convert-uracils --mask-degenerate-bases "
        "--adapter1 AGATCGGAAGAGCACACGTCTGAACTCCAGTCACNNNNNNATCTCGTATGCCGTCTTCTGCTTG "
        "--adapter2 AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT "
        "--adapter-list adapters.tsv --minadapteroverlap 0 --mm 3.0 --shift 2 "
        "--trim5p 2 3 --trim3p 4 5 --trimns --maxns 1000 --trimqualities "
        "--trimwindows 8 --minquality 2 --preserve5p --minlength 15 --maxlength 4294967295 "
        "--collapse --minalignmentlength 11 --collapse-deterministic --collapse-conservatively "
        "--settings /work/adapter_removal/output_settings.txt "
        "--output1 /work/adapter_removal/output_interleaved_truncated.fastq "
        "--singleton /work/adapter_removal/output_singleton_truncated.fastq "
        "--outputcollapsed /work/adapter_removal/output_collapsed.fastq "
        "--outputcollapsedtruncated /work/adapter_removal/output_collapsed_truncated.fastq "
        "--discarded /work/adapter_removal/output_discarded.fastq"
    )
    assert node_class.PLAN_OUTPUTS(
        {
            "input_type": "pair",
            "interleaved_output": "yes",
            "output_select": [
                "output_singleton",
                "output_collapsed",
                "output_collapsed_truncated",
                "output_discarded",
            ],
        },
        tmp_path,
    ) == [
        tmp_path / "adapter_removal" / "output_settings.txt",
        tmp_path / "adapter_removal" / "output_interleaved_truncated.fastq",
        tmp_path / "adapter_removal" / "output_singleton_truncated.fastq",
        tmp_path / "adapter_removal" / "output_collapsed.fastq",
        tmp_path / "adapter_removal" / "output_collapsed_truncated.fastq",
        tmp_path / "adapter_removal" / "output_discarded.fastq",
    ]


def test_trimn_exposes_galaxy_metadata_and_citations() -> None:
    node_info = _registry().object_info()["trimn"]

    assert node_info["display_name"] == "TrimN"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Trim N stretches")
    assert node_info["output"] == ["FASTA"]
    assert node_info["output_name"] == ["trimmed_fasta"]
    assert node_info["required_executables"] == [
        "remove_fake_cut_sites_DNAnexus.py",
        "trim_Ns_DNAnexus.py",
        "clip_regions_DNAnexus.py",
    ]
    assert node_info["required_conda_packages"] == ["trimns_vgp"]
    assert node_info["documentation_url"] == "https://github.com/VGP/vgp-assembly/tree/master/pipeline/trim"
    assert node_info["citation_dois"] == ["10.1101/2020.05.22.110833", "10.1101/2020.06.30.177956"]
    assert "https://doi.org/10.1101/2020.05.22.110833" in node_info["citation_urls"]
    assert "Vertebrate Genomes Project" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "trim_Ns_DNAnexus.py" in node_info["search_aliases"]


def test_trimn_renders_three_stage_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("trimn")

    assert node_class.render_command(
        {
            "fasta_in": "assembly scaffolds.fa",
            "output": "/work/trimn",
        }
    ) == (
        "remove_fake_cut_sites_DNAnexus.py 'assembly scaffolds.fa' "
        "/work/trimn/step1_out.fasta /work/trimn/step1.log && "
        "trim_Ns_DNAnexus.py 'assembly scaffolds.fa' /work/trimn/step2_out.list && "
        "clip_regions_DNAnexus.py /work/trimn/step1_out.fasta /work/trimn/step2_out.list "
        "/work/trimn/final_out.fasta"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "trimn" / "final_out.fasta"]


def test_trimn_validates_required_fasta_input() -> None:
    node_class = _node_class("trimn")

    assert node_class.VALIDATE_INPUTS({"fasta_in": ""}) == "fasta_in is required"


def test_assembly_stats_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["assembly_stats"]

    assert info["output"] == ["HTML_REPORT", "JSON"]
    assert info["output_name"] == ["output_html", "output_json"]


def test_assembly_stats_renders_html_visualisation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("assembly_stats")

    assert node_class.render_command(
        {
            "input_fasta": "assembly.fasta",
            "output_format": "html",
            "output": "/work/assembly_stats",
            "tool_directory": "/iuc/tools/assembly-stats",
        }
    ) == (
        'SRC="$(dirname $(which asm2stats.pl))/../opt/assembly-stats" && '
        "mkdir -p /work/assembly_stats/output_files/json && "
        'cp -r "$SRC/css/" /work/assembly_stats/output_files && '
        'cp -r "$SRC/js/" /work/assembly_stats/output_files && '
        "cp /iuc/tools/assembly-stats/d3-tip.js /work/assembly_stats/output_files/js/d3-tip.js && "
        "cp /iuc/tools/assembly-stats/assembly-stats.html /work/assembly_stats/output.html && "
        "cp /iuc/tools/assembly-stats/assembly-stats.html /work/assembly_stats/output_files && "
        "asm2stats.minmaxgc.pl assembly.fasta > "
        "/work/assembly_stats/output_files/json/output.assembly-stats.json"
    )

    assert node_class.PLAN_OUTPUTS({"output_format": "html"}, tmp_path) == [
        tmp_path / "assembly_stats" / "output.html",
    ]


def test_assembly_stats_renders_json_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("assembly_stats")

    assert node_class.render_command(
        {
            "input_fasta": "assembly.fasta",
            "output_format": "json",
            "output": "/work/assembly_stats",
        }
    ) == "asm2stats.minmaxgc.pl assembly.fasta > /work/assembly_stats/output.json"

    assert node_class.PLAN_OUTPUTS({"output_format": "json"}, tmp_path) == [
        tmp_path / "assembly_stats" / "output.json",
    ]


def test_amas_summary_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_summary"]

    assert info["output"] == ["TEXT", "DIRECTORY"]
    assert info["output_name"] == ["summary_out", "taxon_summaries"]


def test_amas_summary_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_summary")

    assert node_class.render_command(
        {
            "input_files": ["alignments/gene one.fas", "gene2.nex"],
            "input_labels": ["gene one.fas", "gene2.nex"],
            "input_format": "nex",
            "data_type": "dna",
            "by_taxon": True,
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_summary",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/gene one.fas' gene2.nex --format nexus) && "
        "ln -sf 'alignments/gene one.fas' gene_one.fas && "
        "ln -sf gene2.nex gene2.nex && "
        "python -m amas.AMAS summary --by-taxon --in-files gene_one.fas gene2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_summary/taxon_summaries && "
        "find . -maxdepth 1 -name '*-seq-summary.txt' -exec mv {} /work/amas_summary/taxon_summaries/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"by_taxon": True}, tmp_path) == [
        tmp_path / "amas_summary" / "summary.txt",
        tmp_path / "amas_summary" / "taxon_summaries",
    ]


def test_amas_summary_renders_minimal_command_and_summary_output(tmp_path: Path) -> None:
    node_class = _node_class("amas_summary")

    assert node_class.render_command(
        {
            "input_files": ["gene1.fasta"],
            "data_type": "aa",
            "input_format": "fasta",
            "output": "/work/amas_summary",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "gene1.fasta --format fasta) && "
        "ln -sf gene1.fasta gene1.fasta && "
        "python -m amas.AMAS summary --in-files gene1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}"'
    )

    assert node_class.PLAN_OUTPUTS({"by_taxon": False}, tmp_path) == [
        tmp_path / "amas_summary" / "summary.txt",
    ]


def test_amas_concat_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_concat"]

    assert info["output"] == ["ALIGNMENT", "TEXT"]
    assert info["output_name"] == ["output", "partitions_out"]


def test_amas_concat_renders_partitioned_concat_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_concat")

    assert node_class.render_command(
        {
            "input_files": ["gene A.fasta", "geneB.fasta"],
            "input_labels": ["gene A.fasta", "geneB.fasta"],
            "input_format": "fasta",
            "out_format": "phylip",
            "part_format": "nexus",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_concat",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'gene A.fasta' geneB.fasta --format fasta) && "
        "ln -sf 'gene A.fasta' gene_A.fasta && "
        "ln -sf geneB.fasta geneB.fasta && "
        "python -m amas.AMAS concat --concat-part partitions.txt --concat-out concatenated.out "
        "--part-format nexus --out-format phylip --in-files gene_A.fasta geneB.fasta "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align'
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "phylip", "part_format": "nexus"}, tmp_path) == [
        tmp_path / "amas_concat" / "concatenated.phy",
        tmp_path / "amas_concat" / "partitions.nex",
    ]


def test_amas_concat_plans_interleaved_nexus_and_raxml_partitions(tmp_path: Path) -> None:
    node_class = _node_class("amas_concat")

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus-int", "part_format": "raxml"}, tmp_path) == [
        tmp_path / "amas_concat" / "concatenated.nex",
        tmp_path / "amas_concat" / "partitions.txt",
    ]


def test_amas_split_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_split"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["split_alignments"]


def test_amas_split_renders_checked_split_command_and_directory_output(tmp_path: Path) -> None:
    node_class = _node_class("amas_split")

    assert node_class.render_command(
        {
            "input_file": "concat result.phy",
            "input_label": "concat result.phy",
            "input_format": "phylip",
            "split_by": "partitions.txt",
            "remove_empty": True,
            "out_format": "fasta",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_split",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'concat result.phy' --format phylip) && "
        "ln -sf 'concat result.phy' concat_result.phy && "
        "python -m amas.AMAS split --split-by partitions.txt --remove-empty "
        "--out-format fasta --in-files concat_result.phy "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_split/split_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_split/split_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "fasta"}, tmp_path) == [
        tmp_path / "amas_split" / "split_alignments",
    ]


def test_amas_split_renders_minimal_nexus_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_split")

    assert node_class.render_command(
        {
            "input_file": "combined.nex",
            "split_by": "parts.txt",
            "out_format": "nexus-int",
            "data_type": "aa",
            "output": "/work/amas_split",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "combined.nex --format nexus) && "
        "ln -sf combined.nex combined.nex && "
        "python -m amas.AMAS split --split-by parts.txt --out-format nexus-int "
        "--in-files combined.nex "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_split/split_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_split/split_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_split" / "split_alignments",
    ]


def test_amas_remove_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_remove"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["reduced_alignments"]


def test_amas_remove_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_remove")

    assert node_class.render_command(
        {
            "input_files": ["alignments/gene one.fas", "gene2.nex"],
            "input_labels": ["gene one.fas", "gene2.nex"],
            "input_format": "nex",
            "taxa_to_remove": "OTU9 OTU10 Sample_A",
            "out_format": "nexus-int",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_remove",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/gene one.fas' gene2.nex --format nexus) && "
        "ln -sf 'alignments/gene one.fas' gene_one.fas && "
        "ln -sf gene2.nex gene2.nex && "
        "python -m amas.AMAS remove --taxa-to-remove OTU9 OTU10 Sample_A "
        "--out-format nexus-int --in-files gene_one.fas gene2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_remove/reduced_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_remove/reduced_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus-int"}, tmp_path) == [
        tmp_path / "amas_remove" / "reduced_alignments",
    ]


def test_amas_remove_renders_minimal_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_remove")

    assert node_class.render_command(
        {
            "input_files": ["gene1.fasta"],
            "taxa_to_remove": "BadTaxon",
            "out_format": "fasta",
            "data_type": "aa",
            "output": "/work/amas_remove",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "gene1.fasta --format fasta) && "
        "ln -sf gene1.fasta gene1.fasta && "
        "python -m amas.AMAS remove --taxa-to-remove BadTaxon --out-format fasta "
        "--in-files gene1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_remove/reduced_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_remove/reduced_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_remove" / "reduced_alignments",
    ]


def test_amas_replicate_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_replicate"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["replicate_alignments"]


def test_amas_replicate_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_replicate")

    assert node_class.render_command(
        {
            "input_files": ["alignments/locus one.fas", "locus2.nex"],
            "input_labels": ["locus one.fas", "locus2.nex"],
            "input_format": "nex",
            "replicate_replicates": 10,
            "replicate_loci": 2,
            "out_format": "nexus",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_replicate",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/locus one.fas' locus2.nex --format nexus) && "
        "ln -sf 'alignments/locus one.fas' locus_one.fas && "
        "ln -sf locus2.nex locus2.nex && "
        "python -m amas.AMAS replicate --rep-aln 10 2 --out-format nexus "
        "--in-files locus_one.fas locus2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_replicate/replicate_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_replicate/replicate_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus"}, tmp_path) == [
        tmp_path / "amas_replicate" / "replicate_alignments",
    ]


def test_amas_replicate_renders_minimal_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_replicate")

    assert node_class.render_command(
        {
            "input_files": ["locus1.fasta"],
            "replicate_replicates": 2,
            "replicate_loci": 1,
            "out_format": "fasta",
            "data_type": "aa",
            "output": "/work/amas_replicate",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "locus1.fasta --format fasta) && "
        "ln -sf locus1.fasta locus1.fasta && "
        "python -m amas.AMAS replicate --rep-aln 2 1 --out-format fasta "
        "--in-files locus1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_replicate/replicate_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_replicate/replicate_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_replicate" / "replicate_alignments",
    ]


def test_clustalw_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["clustalw"]

    assert node_info["display_name"] == "ClustalW"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Align DNA or protein FASTA sequences")
    assert node_info["output"] == ["ALIGNMENT", "PHYLOGENY_TREE"]
    assert node_info["output_name"] == ["alignment", "guide_tree"]
    assert node_info["required_executables"] == ["clustalw2"]
    assert node_info["required_conda_packages"] == ["clustalw"]
    assert node_info["documentation_url"] == "http://www.clustal.org/clustal2/"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btm404"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btm404"]
    assert node_info["citation_text"] == "Clustal W and Clustal X version 2.0."
    assert "Galaxy" in node_info["search_aliases"]
    assert "multiple sequence alignment" in node_info["search_aliases"]


def test_clustalw_renders_dna_slow_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("clustalw")

    assert node_class.render_command(
        {
            "input": "sequences.fa",
            "sequence_type": "DNA",
            "outform": "fasta",
            "out_order": "ALIGNED",
            "range_mode": "part",
            "seq_range_start": 5,
            "seq_range_end": 120,
            "outputtree": "PHYLIP",
            "kimura": True,
            "tossgaps": True,
            "algorithm": "slow",
            "pwdnamatrix": "IUB",
            "dn_matrix": "CLUSTALW",
            "pwgapopen": 2,
            "pwgapext": 1.5,
            "gapopen": 8,
            "gapext": 0.3,
            "endgaps": True,
            "gapdist": 4,
            "nopgap": True,
            "nohgap": True,
            "maxdiv": 30,
            "negative": True,
            "transweight": 0.75,
            "output": "/work/clustalw",
        }
    ) == (
        "ln -sf sequences.fa input.fasta && "
        "clustalw2 -INFILE=input.fasta -OUTFILE=/work/clustalw/alignment.fasta -OUTORDER=ALIGNED "
        "-TYPE=DNA -OUTPUT=FASTA -RANGE=5,120 -PWDNAMATRIX=IUB -PWGAPOPEN=2 -PWGAPEXT=1.5 "
        "-DNAMATRIX=CLUSTALW -GAPOPEN=8 -GAPEXT=0.3 -ENDGAPS -GAPDIST=4 -NOPGAP -NOHGAP "
        "-MAXDIV=30 -NEGATIVE -TRANSWEIGHT=0.75 -OUTPUTTREE=PHYLIP -KIMURA -TOSSGAPS && "
        "cp input.dnd /work/clustalw/guide_tree.dnd"
    )
    assert node_class.PLAN_OUTPUTS({"outform": "fasta"}, tmp_path) == [
        tmp_path / "clustalw" / "alignment.fasta",
        tmp_path / "clustalw" / "guide_tree.dnd",
    ]


def test_clustalw_renders_protein_quicktree_command_and_validates_input(tmp_path: Path) -> None:
    node_class = _node_class("clustalw")

    assert node_class.render_command(
        {
            "input": "proteins.fa",
            "sequence_type": "PROTEIN",
            "outform": "clustal",
            "out_seqnos": True,
            "out_order": "INPUT",
            "algorithm": "fast",
            "ktuple": 1,
            "topdiags": 2,
            "window": 3,
            "pairgap": 4,
            "score": "ABSOLUTE",
            "pwmatrix": "BLOSUM",
            "matrix": "GONNET",
            "outputtree": "NJ",
            "output": "/work/clustalw",
        }
    ) == (
        "ln -sf proteins.fa input.fasta && "
        "clustalw2 -INFILE=input.fasta -OUTFILE=/work/clustalw/alignment.aln -OUTORDER=INPUT "
        "-TYPE=PROTEIN -OUTPUT=CLUSTAL -SEQNOS=ON -QUICKTREE -KTUPLE=1 -TOPDIAGS=2 -WINDOW=3 "
        "-PAIRGAP=4 -SCORE=ABSOLUTE -MATRIX=GONNET -OUTPUTTREE=NJ && "
        "cp input.dnd /work/clustalw/guide_tree.dnd"
    )
    assert node_class.PLAN_OUTPUTS({"outform": "clustal"}, tmp_path) == [
        tmp_path / "clustalw" / "alignment.aln",
        tmp_path / "clustalw" / "guide_tree.dnd",
    ]
    assert node_class.PLAN_OUTPUTS({"outform": "phylip"}, tmp_path) == [
        tmp_path / "clustalw" / "alignment.phy",
        tmp_path / "clustalw" / "guide_tree.dnd",
    ]
    assert node_class.VALIDATE_INPUTS({"input": ""}) == "input FASTA is required"


def test_quicktree_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["quicktree"]

    assert node_info["display_name"] == "Quicktree"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Construct phylogenetic trees")
    assert node_info["output"] == ["PHYLOGENY_TREE"]
    assert node_info["output_name"] == ["output_file"]
    assert node_info["required_executables"] == ["quicktree", "esl-reformat"]
    assert node_info["required_conda_packages"] == ["quicktree", "hmmer"]
    assert node_info["documentation_url"] == "https://github.com/khowe/quicktree"
    assert node_info["citation_dois"] == ["10.1093/oxfordjournals.molbev.a040454"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/oxfordjournals.molbev.a040454"]
    assert "neighbor-joining method" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "distance matrix" in node_info["search_aliases"]


def test_quicktree_renders_alignment_and_distance_commands(tmp_path: Path) -> None:
    node_class = _node_class("quicktree")

    assert node_class.render_command(
        {
            "format": "align",
            "input_file": "protein alignment.fa",
            "output_type": "tree_out",
            "upgma": True,
            "kimura": True,
            "boot": 100,
            "output": "/work/quicktree",
        }
    ) == (
        "esl-reformat -o input.quicktree stockholm 'protein alignment.fa' && "
        "quicktree -in a -out t -upgma -kimura -boot 100 input.quicktree > /work/quicktree/output_file.nwk"
    )
    assert node_class.render_command(
        {
            "format": "dist",
            "input_file": "distances.phy",
            "output_type": "dist_out",
            "output": "/work/quicktree",
        }
    ) == (
        "ln -s distances.phy input.quicktree && "
        "quicktree -in m -out m input.quicktree > /work/quicktree/output_file.dist"
    )
    assert node_class.PLAN_OUTPUTS({"output_type": "tree_out"}, tmp_path) == [
        tmp_path / "quicktree" / "output_file.nwk",
    ]
    assert node_class.PLAN_OUTPUTS({"output_type": "dist_out"}, tmp_path) == [
        tmp_path / "quicktree" / "output_file.dist",
    ]
    assert node_class.VALIDATE_INPUTS({"format": "align", "input_file": ""}) == (
        "input alignment or distance matrix is required"
    )
    assert node_class.VALIDATE_INPUTS({"format": "align", "input_file": "alignment.fa", "boot": -1}) == (
        "boot must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"format": "dist", "input_file": "distances.phy", "output_type": "dist_out"}) is True


def test_flash_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["flash"]

    assert node_info["display_name"] == "FLASH"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Merge paired-end reads")
    assert node_info["output"] == [
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "TSV",
        "STATS_FILE",
        "STATS_FILE",
        "TSV",
        "TSV",
        "STATS_FILE",
        "STATS_FILE",
    ]
    assert node_info["output_name"] == [
        "merged_reads",
        "unmerged_forward_reads",
        "unmerged_reverse_reads",
        "histogram_table",
        "raw_log",
        "histogram_text",
        "innie_histogram_table",
        "outie_histogram_table",
        "innie_histogram_text",
        "outie_histogram_text",
    ]
    assert node_info["required_executables"] == ["flash"]
    assert node_info["required_conda_packages"] == ["flash"]
    assert node_info["documentation_url"] == "https://ccb.jhu.edu/software/FLASH/"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btr507"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btr507"]
    assert "fast length adjustment of short reads" in node_info["citation_text"].lower()
    assert "Galaxy" in node_info["search_aliases"]
    assert "read merging" in node_info["search_aliases"]


def test_flash_renders_individual_reads_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("flash")

    assert node_class.render_command(
        {
            "layout": "individual",
            "forward": "reads R1.fastq.gz",
            "reverse": "reads R2.fastq.gz",
            "min_overlap": 12,
            "max_overlap": 80,
            "max_mismatch_density": 0.15,
            "allow_outies": True,
            "generate_histogram": True,
            "save_log": True,
            "phred_offset": 33,
            "gzip": True,
            "threads": 8,
            "output": "/work/flash",
        }
    ) == [
        "flash",
        "--threads=${GALAXY_SLOTS:-8}",
        "-m",
        "12",
        "-M",
        "80",
        "-x",
        "0.15",
        "--allow-outies",
        "reads R1.fastq.gz",
        "reads R2.fastq.gz",
        "-p",
        "33",
        "-z",
        "--output-prefix",
        "/work/flash/out",
        "--output-suffix=",
        ">",
        "/work/flash/flash.log",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"allow_outies": True, "generate_histogram": True, "save_log": True, "gzip": True},
        tmp_path,
    ) == [
        tmp_path / "flash" / "out.extendedFrags.fastq.gz",
        tmp_path / "flash" / "out.notCombined_1.fastq.gz",
        tmp_path / "flash" / "out.notCombined_2.fastq.gz",
        tmp_path / "flash" / "out.hist",
        tmp_path / "flash" / "flash.log",
        tmp_path / "flash" / "out.histogram",
        tmp_path / "flash" / "out.hist.innie",
        tmp_path / "flash" / "out.hist.outie",
        tmp_path / "flash" / "out.histogram.innie",
        tmp_path / "flash" / "out.histogram.outie",
    ]


def test_flash_renders_collection_reads_command_and_validates_inputs(tmp_path: Path) -> None:
    node_class = _node_class("flash")

    assert node_class.render_command(
        {
            "layout": "collection",
            "reads": {"forward": "collection_R1.fastq", "reverse": "collection_R2.fastq"},
            "min_overlap": 10,
            "max_overlap": 65,
            "max_mismatch_density": 0.25,
            "allow_outies": False,
            "generate_histogram": False,
            "save_log": False,
            "phred_offset": 64,
            "gzip": False,
            "threads": 4,
            "output": "/work/flash",
        }
    ) == [
        "flash",
        "--threads=${GALAXY_SLOTS:-4}",
        "-m",
        "10",
        "-M",
        "65",
        "-x",
        "0.25",
        "collection_R1.fastq",
        "collection_R2.fastq",
        "-p",
        "64",
        "--output-prefix",
        "/work/flash/out",
        "--output-suffix=",
    ]
    assert node_class.PLAN_OUTPUTS({"allow_outies": False, "generate_histogram": False, "save_log": False}, tmp_path) == [
        tmp_path / "flash" / "out.extendedFrags.fastq",
        tmp_path / "flash" / "out.notCombined_1.fastq",
        tmp_path / "flash" / "out.notCombined_2.fastq",
        tmp_path / "flash" / "out.hist",
    ]
    assert node_class.VALIDATE_INPUTS({"layout": "individual", "forward": "r1.fastq", "reverse": ""}) == (
        "forward and reverse reads are required"
    )
    assert node_class.VALIDATE_INPUTS({"layout": "collection", "reads": {"forward": "r1.fastq"}}) == (
        "paired collection requires forward and reverse reads"
    )


def test_fraggenescan_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["fraggenescan"]

    assert node_info["display_name"] == "FragGeneScan"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Find complete and fragmented genes")
    assert node_info["output"] == ["TSV", "FASTA", "FASTA", "GFF"]
    assert node_info["output_name"] == ["coordinates", "nucleotide_sequences", "protein_sequences", "gff"]
    assert node_info["required_executables"] == ["run_FragGeneScan.pl"]
    assert node_info["required_conda_packages"] == ["fraggenescan"]
    assert node_info["documentation_url"] == "https://omics.informatics.indiana.edu/FragGeneScan/"
    assert node_info["citation_dois"] == ["10.1093/nar/gkq747"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/nar/gkq747"]
    assert "FragGeneScan" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "fragmented genes" in node_info["search_aliases"]


def test_fraggenescan_renders_prediction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("fraggenescan")

    assert node_class.render_command(
        {
            "genome": "short reads.fasta",
            "complete": False,
            "train": "illumina_10",
            "threads": 6,
            "output": "/work/fraggenescan",
        }
    ) == [
        "run_FragGeneScan.pl",
        "-genome",
        "short reads.fasta",
        "-out",
        "/work/fraggenescan/output_file_name",
        "-complete",
        "0",
        "-train",
        "illumina_10",
        "-thread=${GALAXY_SLOTS:-6}",
    ]
    assert node_class.render_command(
        {
            "genome": "complete-genome.fna",
            "complete": True,
            "train": "complete",
            "output": "/work/fraggenescan",
        }
    )[-3:] == ["-train", "complete", "-thread=${GALAXY_SLOTS:-4}"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "fraggenescan" / "output_file_name.out",
        tmp_path / "fraggenescan" / "output_file_name.ffn",
        tmp_path / "fraggenescan" / "output_file_name.faa",
        tmp_path / "fraggenescan" / "output_file_name.gff",
    ]
    assert node_class.VALIDATE_INPUTS({"genome": ""}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"genome": "reads.fa", "threads": 0}) == "threads must be >= 1"
    assert node_class.VALIDATE_INPUTS({"genome": "reads.fa", "threads": 1}) is True


def test_prodigal_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["prodigal"]

    assert node_info["display_name"] == "Prodigal Gene Predictor"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Predict protein-coding genes")
    assert node_info["output"] == ["FILE", "FASTA", "FASTA", "TSV"]
    assert node_info["output_name"] == ["coordinates", "protein_translations", "nucleotide_sequences", "start_sites"]
    assert node_info["required_executables"] == ["prodigal"]
    assert node_info["required_conda_packages"] == ["prodigal"]
    assert node_info["documentation_url"] == "https://github.com/hyattpd/Prodigal"
    assert node_info["citation_dois"] == ["10.1186/1471-2105-11-119"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1186/1471-2105-11-119"]
    assert "prokaryotic gene recognition" in node_info["citation_text"].lower()
    assert "Galaxy" in node_info["search_aliases"]
    assert "translation initiation sites" in node_info["search_aliases"]


def test_prodigal_renders_gene_prediction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("prodigal")

    assert node_class.render_command(
        {
            "input_fa": "contigs.fa",
            "input_train": "trained model.trn",
            "out_format": "gff",
            "procedure": "meta",
            "trans_table": "4",
            "closed": True,
            "force_nonsd": True,
            "masked_seq": True,
            "output": "/work/prodigal",
        }
    ) == [
        "prodigal",
        "-i",
        "contigs.fa",
        "-t",
        "trained model.trn",
        "-o",
        "/work/prodigal/output.gff3",
        "-f",
        "gff",
        "-p",
        "meta",
        "-g",
        "4",
        "-a",
        "/work/prodigal/output.faa",
        "-d",
        "/work/prodigal/output.fnn",
        "-s",
        "/work/prodigal/output.start",
        "-c",
        "-n",
        "-m",
    ]
    assert node_class.render_command(
        {
            "input_fa": "input.fna",
            "output": "/work/prodigal",
        }
    ) == [
        "prodigal",
        "-i",
        "input.fna",
        "-o",
        "/work/prodigal/output.gbk",
        "-f",
        "gbk",
        "-p",
        "single",
        "-g",
        "11",
        "-a",
        "/work/prodigal/output.faa",
        "-d",
        "/work/prodigal/output.fnn",
        "-s",
        "/work/prodigal/output.start",
    ]
    assert node_class.PLAN_OUTPUTS({"out_format": "gff"}, tmp_path) == [
        tmp_path / "prodigal" / "output.gff3",
        tmp_path / "prodigal" / "output.faa",
        tmp_path / "prodigal" / "output.fnn",
        tmp_path / "prodigal" / "output.start",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path)[0] == tmp_path / "prodigal" / "output.gbk"
    assert node_class.VALIDATE_INPUTS({"input_fa": ""}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_fa": "contigs.fa", "out_format": "bad"}) == (
        "out_format must be one of: gbk, gff, sqn, sco"
    )
    assert node_class.VALIDATE_INPUTS({"input_fa": "contigs.fa", "trans_table": "26"}) == (
        "trans_table must be an integer from 1 to 25"
    )
    assert node_class.VALIDATE_INPUTS({"input_fa": "contigs.fa", "procedure": "single", "trans_table": "11"}) is True


def test_eukrep_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["eukrep"]

    assert node_info["display_name"] == "EukRep"
    assert node_info["category"] == "metagenomics"
    assert node_info["description"].startswith("Classify eukaryotic and prokaryotic")
    assert node_info["output"] == ["FASTA", "FASTA", "STATS_FILE", "STATS_FILE"]
    assert node_info["output_name"] == [
        "eukaryote_sequences",
        "prokaryote_sequences",
        "eukaryote_names",
        "prokaryote_names",
    ]
    assert node_info["required_executables"] == ["EukRep"]
    assert node_info["required_conda_packages"] == ["eukrep"]
    assert node_info["documentation_url"] == "https://github.com/patrickwest/EukRep"
    assert node_info["citation_dois"] == ["10.1101/gr.228429.117"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1101/gr.228429.117"]
    assert "Genome-reconstruction for eukaryotes" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "metagenomic eukaryotes" in node_info["search_aliases"]


def test_eukrep_renders_fasta_and_names_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("eukrep")

    assert node_class.render_command(
        {
            "input": "metagenome scaffolds.fa.gz",
            "min": 5000,
            "kmer_len": 4,
            "prokarya": True,
            "seq_names": False,
            "stringency": "strict",
            "tie": "skip",
            "output": "/work/eukrep",
        }
    ) == (
        "ln -s 'metagenome scaffolds.fa.gz' input.fa.gz && "
        "EukRep -i input.fa.gz -o /work/eukrep/output.fa --min 5000 --kmer_len 4 "
        "--prokarya /work/eukrep/output_prokarya.fa -m strict --tie skip"
    )
    assert node_class.PLAN_OUTPUTS({"prokarya": True, "seq_names": False}, tmp_path) == [
        tmp_path / "eukrep" / "output.fa",
        tmp_path / "eukrep" / "output_prokarya.fa",
    ]
    assert node_class.render_command(
        {
            "input": "contigs.fasta",
            "min": 3000,
            "kmer_len": 5,
            "prokarya": True,
            "seq_names": True,
            "stringency": "balanced",
            "tie": "euk",
            "output": "/work/eukrep",
        }
    ) == (
        "ln -s contigs.fasta input.fasta && "
        "EukRep -i input.fasta -o /work/eukrep/output.fa --min 3000 --kmer_len 5 "
        "--prokarya /work/eukrep/output_prokarya.fa --seq_names -m balanced --tie euk"
    )
    assert node_class.PLAN_OUTPUTS({"prokarya": True, "seq_names": True}, tmp_path) == [
        tmp_path / "eukrep" / "output.fa",
        tmp_path / "eukrep" / "output_prokarya.fa",
    ]
    assert node_class.PLAN_OUTPUTS({"prokarya": False, "seq_names": True}, tmp_path) == [
        tmp_path / "eukrep" / "output.fa",
    ]
    assert node_class.VALIDATE_INPUTS({"input": ""}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input": "contigs.fa", "kmer_len": 2}) == "kmer_len must be between 3 and 6"
    assert node_class.VALIDATE_INPUTS({"input": "contigs.fa", "min": -1}) == "min must be >= 0"
    assert node_class.VALIDATE_INPUTS({"input": "contigs.fa", "stringency": "bad"}) == (
        "stringency must be one of: strict, balanced, lenient"
    )
    assert node_class.VALIDATE_INPUTS({"input": "contigs.fa", "tie": "bad"}) == "tie must be one of: euk, prok, rand, skip"
    assert node_class.VALIDATE_INPUTS({"input": "contigs.fa", "kmer_len": 5, "min": 0}) is True


def test_gamma_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["gamma"]

    assert node_info["display_name"] == "GAMMA"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Find and annotate gene matches")
    assert node_info["output"] == ["TSV", "GFF", "FASTA"]
    assert node_info["output_name"] == ["gamma_out", "gamma_gff", "gamma_fasta"]
    assert node_info["required_executables"] == ["GAMMA.py"]
    assert node_info["required_conda_packages"] == ["GAMMA"]
    assert node_info["documentation_url"] == "https://github.com/rastanton/GAMMA"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btab607"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btab607"]
    assert "rapid identification, classification and annotation" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "Gene Allele Mutation Microbial Assessment" in node_info["search_aliases"]


def test_gamma_renders_gene_match_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("gamma")

    assert node_class.render_command(
        {
            "input_fasta": "assembly contigs.fa",
            "input_db": "resfinder genes.fasta",
            "all": True,
            "identity": 95,
            "extended": True,
            "fasta": True,
            "gff": True,
            "headless": True,
            "output": "/work/gamma",
        }
    ) == (
        "GAMMA.py 'assembly contigs.fa' 'resfinder genes.fasta' /work/gamma/gamma_out "
        "-a -i 95 -e -f -g -l"
    )
    assert node_class.render_command(
        {
            "input_fasta": "assembly.fa",
            "input_db": "genes.fa",
            "output": "/work/gamma",
        }
    ) == "GAMMA.py assembly.fa genes.fa /work/gamma/gamma_out -i 90"
    assert node_class.PLAN_OUTPUTS({"gff": True, "fasta": True}, tmp_path) == [
        tmp_path / "gamma" / "gamma_out.gamma",
        tmp_path / "gamma" / "gamma_out.gff",
        tmp_path / "gamma" / "gamma_out.fasta",
    ]
    assert node_class.PLAN_OUTPUTS({"gff": False, "fasta": False}, tmp_path) == [
        tmp_path / "gamma" / "gamma_out.gamma",
    ]
    assert node_class.VALIDATE_INPUTS({"input_fasta": "", "input_db": "genes.fa"}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": ""}) == "gene database FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "identity": -1}) == (
        "identity must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "identity": 101}) == (
        "identity must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "identity": 90}) is True


def test_gamma_s_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["gamma_s"]

    assert node_info["display_name"] == "GAMMA-S"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Find gene matches")
    assert node_info["output"] == ["TSV"]
    assert node_info["output_name"] == ["gamma_s_out"]
    assert node_info["required_executables"] == ["GAMMA-S.py"]
    assert node_info["required_conda_packages"] == ["GAMMA"]
    assert node_info["documentation_url"] == "https://github.com/rastanton/GAMMA"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btab607"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btab607"]
    assert "rapid identification, classification and annotation" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "GAMMA-S" in node_info["search_aliases"]


def test_gamma_s_renders_sequence_match_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("gamma_s")

    assert node_class.render_command(
        {
            "input_fasta": "query proteins.fa",
            "input_db": "db proteins.fa",
            "all": True,
            "identity": 85,
            "extended": True,
            "protein": True,
            "minimum": 40,
            "output": "/work/gamma_s",
        }
    ) == (
        "GAMMA-S.py 'query proteins.fa' 'db proteins.fa' /work/gamma_s/gamma-s_out "
        "-a -i 85 -e -p -m 40"
    )
    assert node_class.render_command(
        {
            "input_fasta": "assembly.fa",
            "input_db": "genes.fa",
            "output": "/work/gamma_s",
        }
    ) == "GAMMA-S.py assembly.fa genes.fa /work/gamma_s/gamma-s_out -i 90 -m 20"
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "gamma_s" / "gamma-s_out.gamma",
    ]
    assert node_class.VALIDATE_INPUTS({"input_fasta": "", "input_db": "genes.fa"}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": ""}) == "gene database FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "identity": -1}) == (
        "identity must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "minimum": 101}) == (
        "minimum must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_fasta": "assembly.fa", "input_db": "genes.fa", "identity": 90, "minimum": 20}) is True


def test_red_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["red"]

    assert node_info["display_name"] == "Red"
    assert node_info["category"] == "genomics"
    assert node_info["description"].startswith("Detect and mask repeats")
    assert node_info["output"] == ["FASTA", "BED"]
    assert node_info["output_name"] == ["masked", "bed"]
    assert node_info["required_executables"] == ["Red"]
    assert node_info["required_conda_packages"] == ["red"]
    assert node_info["documentation_url"] == "https://github.com/BioinformaticsToolsmith/Red"
    assert node_info["citation_dois"] == ["10.1186/s12859-015-0654-5"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1186/s12859-015-0654-5"]
    assert "detecting repeats de-novo" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "repeat masking" in node_info["search_aliases"]


def test_red_renders_repeat_masking_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("red")

    assert node_class.render_command(
        {
            "input": "draft genome.fa",
            "threads": 8,
            "output": "/work/red",
        }
    ) == (
        "mkdir -p /work/red/input /work/red/output && "
        "ln -s 'draft genome.fa' /work/red/input/genome.fa && "
        "Red -gnm /work/red/input/ -msk /work/red/output/ -rpt /work/red/output/ -frm 2 "
        "-cor ${GALAXY_SLOTS:-8}"
    )
    assert node_class.render_command(
        {
            "input": "genome.fa",
            "output": "/work/red",
        }
    ).endswith("-cor ${GALAXY_SLOTS:-1}")
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "red" / "output" / "genome.msk",
        tmp_path / "red" / "output" / "genome.bed",
    ]
    assert node_class.VALIDATE_INPUTS({"input": ""}) == "genome FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input": "genome.fa", "threads": 0}) == "threads must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input": "genome.fa", "threads": 1}) is True


def test_abritamr_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["abritamr"]

    assert node_info["display_name"] == "abriTAMR"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Detect and collate antimicrobial resistance")
    assert node_info["output"] == ["TSV", "TSV", "TSV", "TSV", "STATS_FILE"]
    assert node_info["output_name"] == [
        "abriTAMR_output",
        "matches_summary",
        "partials_summary",
        "virulence_summary",
        "log",
    ]
    assert node_info["required_executables"] == ["abritamr"]
    assert node_info["required_conda_packages"] == ["abritamr"]
    assert node_info["documentation_url"] == "https://github.com/MDU-PHL/abritamr"
    assert node_info["citation_dois"] == ["10.5281/zenodo.7370627"]
    assert node_info["citation_urls"] == ["https://doi.org/10.5281/zenodo.7370627"]
    assert "MDU-PHL/abritamr" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "AMR gene detection" in node_info["search_aliases"]


def test_abritamr_renders_manifest_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("abritamr")

    assert node_class.render_command(
        {
            "contig": ["sample A.fasta", "sample_B.fasta"],
            "contig_labels": ["sample A", "sample_B"],
            "species": "Salmonella",
            "identity": 0.9,
            "jobs": 6,
            "output": "/work/abritamr",
        }
    ) == (
        "printf '%s\\t%s\\n' 'sample A' 'sample A.fasta' sample_B sample_B.fasta > /work/abritamr/input.tsv && "
        "abritamr run --contigs /work/abritamr/input.tsv --species Salmonella --identity 0.9 "
        "--jobs ${GALAXY_SLOTS:-6}"
    )
    assert node_class.render_command(
        {
            "contig": "sample.fasta",
            "output": "/work/abritamr",
        }
    ) == (
        "printf '%s\\t%s\\n' sample.fasta sample.fasta > /work/abritamr/input.tsv && "
        "abritamr run --contigs /work/abritamr/input.tsv --jobs ${GALAXY_SLOTS:-4}"
    )
    assert node_class.PLAN_OUTPUTS({"log_file": True}, tmp_path) == [
        tmp_path / "abritamr" / "abritamr.txt",
        tmp_path / "abritamr" / "summary_matches.txt",
        tmp_path / "abritamr" / "summary_partials.txt",
        tmp_path / "abritamr" / "summary_virulence.txt",
        tmp_path / "abritamr" / "abritamr.log",
    ]
    assert node_class.PLAN_OUTPUTS({"log_file": False}, tmp_path) == [
        tmp_path / "abritamr" / "abritamr.txt",
        tmp_path / "abritamr" / "summary_matches.txt",
        tmp_path / "abritamr" / "summary_partials.txt",
        tmp_path / "abritamr" / "summary_virulence.txt",
    ]
    assert node_class.VALIDATE_INPUTS({"contig": []}) == "at least one contig FASTA is required"
    assert node_class.VALIDATE_INPUTS({"contig": ["sample.fa"], "identity": -0.1}) == "identity must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS({"contig": ["sample.fa"], "jobs": 0}) == "jobs must be >= 1"
    assert node_class.VALIDATE_INPUTS({"contig": ["sample.fa"], "identity": 0.9, "jobs": 1}) is True


def test_nonpareil_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["nonpareil"]

    assert node_info["display_name"] == "Nonpareil"
    assert node_info["category"] == "metagenomics"
    assert node_info["description"].startswith("Estimate metagenomic coverage")
    assert node_info["output"] == ["TSV", "TSV", "STATS_FILE", "JSON", "TSV"]
    assert node_info["output_name"] == [
        "summary",
        "all_data_output",
        "log",
        "json_output",
        "mating_vector_output",
    ]
    assert node_info["required_executables"] == ["nonpareil", "NonpareilCurves.R"]
    assert node_info["required_conda_packages"] == ["nonpareil"]
    assert node_info["documentation_url"] == "https://nonpareil.readthedocs.io/"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btt584"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btt584"]
    assert "redundancy-based approach" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "metagenomic coverage" in node_info["search_aliases"]


def test_nonpareil_renders_coverage_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("nonpareil")

    assert node_class.render_command(
        {
            "input": "reads sample.fasta",
            "input_format": "fasta",
            "summary_label": "reads sample.fasta",
            "algo": "alignment",
            "subsampling": 0.7,
            "subsample_per_point": 1024,
            "min_overlapping": 50,
            "max_query_reads": 1000,
            "use_portion_in_output": True,
            "min_sampling_portion": 0,
            "max_sampling_portion": 1,
            "sampling_portion_interval": 0.01,
            "use_rev_comp": True,
            "n_as_mismatches": True,
            "sim_thres": 0.95,
            "kmer_size": 24,
            "proba": 0.5,
            "seed": 1000,
            "threads": 6,
            "max_memory": 2048,
            "log_test": True,
            "json_object": True,
            "output": "/work/nonpareil",
        }
    ) == (
        "ln -s 'reads sample.fasta' /work/nonpareil/input && "
        "nonpareil -s /work/nonpareil/input -T alignment -f fasta -d 0.7 -n 1024 -L 50 -X 1000 "
        "-R ${NONPAREIL_MAX_MEMORY:-2048} -t ${GALAXY_SLOTS:-6} -b /work/nonpareil/output "
        "-a /work/nonpareil/all_data_output.tsv -C /work/nonpareil/mating_vector_output.tsv "
        "-l /work/nonpareil/nonpareil.log -o /work/nonpareil/reads_sample.fasta -F -m 0 -M 1 -i 0.01 "
        "-c -N -S 0.95 -k 24 -x 0.5 -r 1000 && "
        "cp /work/nonpareil/reads_sample.fasta /work/nonpareil/summary.tsv && "
        "NonpareilCurves.R --json /work/nonpareil/curves.json /work/nonpareil/reads_sample.fasta"
    )
    assert node_class.render_command(
        {
            "input": "reads.fastq",
            "input_format": "fastq",
            "output": "/work/nonpareil",
        }
    ) == (
        "ln -s reads.fastq /work/nonpareil/input && "
        "nonpareil -s /work/nonpareil/input -T kmer -f fastq -d 0.7 -n 1024 -L 50 -X 1000 "
        "-R ${NONPAREIL_MAX_MEMORY:-1024} -t ${GALAXY_SLOTS:-2} -b /work/nonpareil/output "
        "-a /work/nonpareil/all_data_output.tsv -C /work/nonpareil/mating_vector_output.tsv "
        "-o /work/nonpareil/reads.fastq -m 0 -M 1 -i 0.01 -k 24 -r 1000 && "
        "cp /work/nonpareil/reads.fastq /work/nonpareil/summary.tsv"
    )
    assert node_class.PLAN_OUTPUTS({"log_test": True, "json_object": True}, tmp_path) == [
        tmp_path / "nonpareil" / "summary.tsv",
        tmp_path / "nonpareil" / "all_data_output.tsv",
        tmp_path / "nonpareil" / "nonpareil.log",
        tmp_path / "nonpareil" / "curves.json",
        tmp_path / "nonpareil" / "mating_vector_output.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"log_test": False, "json_object": False}, tmp_path) == [
        tmp_path / "nonpareil" / "summary.tsv",
        tmp_path / "nonpareil" / "all_data_output.tsv",
        tmp_path / "nonpareil" / "mating_vector_output.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({"input": ""}) == "input sequences are required"
    assert node_class.VALIDATE_INPUTS({"input": "reads.fastq", "algo": "bad"}) == "algo must be one of: alignment, kmer"
    assert node_class.VALIDATE_INPUTS({"input": "reads.fastq", "input_format": "bad"}) == (
        "input_format must be one of: fasta, fastq"
    )
    assert node_class.VALIDATE_INPUTS({"input": "reads.fastq", "min_overlapping": 101}) == (
        "min_overlapping must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input": "reads.fastq", "threads": 0}) == "threads must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input": "reads.fastq", "algo": "kmer", "input_format": "fastq"}) is True


def test_bbtools_bbduk_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_bbduk"]

    assert node_info["display_name"] == "BBTools BBDuk"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Filter, trim, and mask FASTQ reads")
    assert node_info["output"] == [
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "TSV",
        "TSV",
        "TSV",
        "FASTA",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "STATS_FILE",
    ]
    assert node_info["output_name"] == [
        "forward_unmatched",
        "reverse_unmatched",
        "forward_matched",
        "reverse_matched",
        "singletons",
        "stats",
        "refstats",
        "rpkm",
        "dump",
        "base_composition_histogram",
        "quality_histogram",
        "quality_count_histogram",
        "average_quality_histogram",
        "boxplot_quality_histogram",
        "read_length_histogram",
        "polymer_length_histogram",
        "gc_histogram",
        "entropy_histogram",
        "log",
    ]
    assert node_info["required_executables"] == ["bbduk.sh"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbduk-guide/"
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "entropy filtering" in node_info["search_aliases"]


def test_bbtools_bbduk_renders_filtering_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_bbduk")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fastq.gz",
            "read2": "sample R2.fastq.gz",
            "reference_type": "files",
            "reference": ["adapters.fa.gz", "phiX.fa"],
            "outputs_select": ["outu", "outm", "outs"],
            "output_stats_select": ["stats", "ref", "dump"],
            "output_hists_select": ["quhist", "lhist"],
            "ktrim": "r",
            "minlength": 30,
            "k": 23,
            "rcomp": False,
            "maskmiddle": False,
            "minkmerhits": 2,
            "minkmerfraction": 0.1,
            "mincovfraction": 0.2,
            "hammingdistance": 1,
            "qhdist": 1,
            "editdistance": 1,
            "forbidn": True,
            "trimfailures": True,
            "findbestmatch": True,
            "skipr1": True,
            "skipr2": False,
            "entropy": 0.9,
            "entropymask": "t",
            "entropywindow": 60,
            "entropyk": 6,
            "log_file": True,
            "threads": 12,
            "output": "/work/bbduk",
        }
    ) == (
        "ln -s 'sample R1.fastq.gz' /work/bbduk/forward.fastq.gz && "
        "ln -s 'sample R2.fastq.gz' /work/bbduk/reverse.fastq.gz && "
        "gunzip -c adapters.fa.gz > /work/bbduk/adapters.fa.gz.fa && "
        "ln -s phiX.fa /work/bbduk/phiX.fa.fa && "
        "bbduk.sh in=/work/bbduk/forward.fastq.gz in2=/work/bbduk/reverse.fastq.gz "
        "out=/work/bbduk/forward_unmatched.fastq out2=/work/bbduk/reverse_unmatched.fastq "
        "outm=/work/bbduk/forward_matched.fastq outm2=/work/bbduk/reverse_matched.fastq "
        "outs=/work/bbduk/singletons.fastq ref=/work/bbduk/adapters.fa.gz.fa,/work/bbduk/phiX.fa.fa "
        "k=23 ktrim=r minlength=30 rcomp=f maskmiddle=f minkmerhits=2 minkmerfraction=0.1 "
        "mincovfraction=0.2 hammingdistance=1 qhdist=1 editdistance=1 forbidn=t trimfailures=t "
        "findbestmatch=t skipr1=t skipr2=f entropy=0.9 entropymask=t entropywindow=60 entropyk=6 "
        "stats=/work/bbduk/stats.tsv refstats=/work/bbduk/refstats.tsv dump=/work/bbduk/kmer_dump.fasta "
        "qhist=/work/bbduk/quality_histogram.tsv lhist=/work/bbduk/read_length_histogram.tsv "
        "t=${GALAXY_SLOTS:-12} 2> >(tee /work/bbduk/bbduk.log >&2)"
    )
    assert node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads.fastq",
            "reference_type": "keywords",
            "reference": ["adapters", "phix"],
            "outputs_select": "outu",
            "output": "/work/bbduk",
        }
    ) == (
        "ln -s reads.fastq /work/bbduk/forward.fastq && "
        "bbduk.sh in=/work/bbduk/forward.fastq out=/work/bbduk/forward_unmatched.fastq "
        "ref=adapters,phix k=27 rcomp=t maskmiddle=t minkmerhits=1 minkmerfraction=0 "
        "mincovfraction=0 hammingdistance=0 qhdist=0 editdistance=0 forbidn=f trimfailures=f "
        "findbestmatch=f skipr1=f skipr2=f t=${GALAXY_SLOTS:-4}"
    )
    assert node_class.PLAN_OUTPUTS(
        {
            "input_type": "pair",
            "outputs_select": ["outu", "outm", "outs"],
            "output_stats_select": ["stats", "ref", "dump"],
            "output_hists_select": ["quhist", "lhist"],
            "log_file": True,
        },
        tmp_path,
    ) == [
        tmp_path / "bbtools_bbduk" / "forward_unmatched.fastq",
        tmp_path / "bbtools_bbduk" / "reverse_unmatched.fastq",
        tmp_path / "bbtools_bbduk" / "forward_matched.fastq",
        tmp_path / "bbtools_bbduk" / "reverse_matched.fastq",
        tmp_path / "bbtools_bbduk" / "singletons.fastq",
        tmp_path / "bbtools_bbduk" / "stats.tsv",
        tmp_path / "bbtools_bbduk" / "refstats.tsv",
        tmp_path / "bbtools_bbduk" / "kmer_dump.fasta",
        tmp_path / "bbtools_bbduk" / "quality_histogram.tsv",
        tmp_path / "bbtools_bbduk" / "read_length_histogram.tsv",
        tmp_path / "bbtools_bbduk" / "bbduk.log",
    ]
    assert node_class.PLAN_OUTPUTS({"outputs_select": "outu"}, tmp_path) == [
        tmp_path / "bbtools_bbduk" / "forward_unmatched.fastq",
    ]
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": ""}) == "read1 FASTQ is required"
    assert node_class.VALIDATE_INPUTS({"input_type": "pair", "read1": "r1.fq", "read2": ""}) == "read2 FASTQ is required for paired input"
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "reference_type": "files"}) == (
        "at least one reference FASTA is required when reference_type is files"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "k": 0}) == "k must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "entropy": 2}) == (
        "entropy must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "outputs_select": []}) == (
        "at least one read output must be selected"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "outputs_select": "outu"}) is True


def test_bbtools_bbmerge_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_bbmerge"]

    assert node_info["display_name"] == "BBTools BBMerge"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Merge overlapping paired-end reads")
    assert node_info["output"] == ["FASTQ", "FASTQ", "TSV"]
    assert node_info["output_name"] == ["merged_reads", "unmerged_reads", "insert_length_histogram"]
    assert node_info["required_executables"] == ["bbmerge.sh"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == (
        "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmerge-guide/"
    )
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "overlapping mates" in node_info["search_aliases"]


def test_bbtools_bbmerge_renders_merge_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_bbmerge")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fastq.gz",
            "read2": "sample R2.fastq.gz",
            "qtrim": "lr",
            "trimq": 12,
            "minlength_after_trim": 75,
            "qt_usequality": False,
            "ecco": True,
            "trimnonoverlapping": True,
            "mininsert": 40,
            "minoverlap": 14,
            "minq": 10,
            "maxq": 42,
            "entropy": False,
            "efilter": 7,
            "pfilter": 0.001,
            "kfilter": 0,
            "merge_usequality": False,
            "adapter1": "AAA",
            "adapter2": "TTT",
            "merge_mode": "Flat mode",
            "margin": 4,
            "mismatches": 2,
            "requireratiomatch": True,
            "strictness": "loose",
            "threads": 8,
            "memory_mb": 8192,
            "output": "/work/bbmerge",
        }
    ) == (
        "ln -s 'sample R1.fastq.gz' /work/bbmerge/forward.fastq.gz && "
        "ln -s 'sample R2.fastq.gz' /work/bbmerge/reverse.fastq.gz && "
        'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
        'export _JAVA_OPTIONS="${_JAVA_OPTIONS} -Xmx${GALAXY_MEMORY_MB:-8192}m -Xms256m"; fi && '
        'bbmerge.sh tmpdir="$TMPDIR" t="${GALAXY_SLOTS:-8}" '
        "in1=/work/bbmerge/forward.fastq.gz in2=/work/bbmerge/reverse.fastq.gz interleaved=f "
        "out=/work/bbmerge/merged.fastq outu=/work/bbmerge/unmerged.fastq "
        "ihist=/work/bbmerge/ihist.tabular touppercase=t qtrim=lr trimq=12 minlength=75 usequality=f "
        "usejni=f ecco=t trimnonoverlapping=t mininsert=40 minoverlap=14 minq=10 maxq=42 "
        "entropy=f efilter=7 pfilter=0.001 kfilter=0 usequality=f adapter1=AAA adapter2=TTT "
        "margin=4 mismatches=2 requireratiomatch=t loose=t"
    )
    assert node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads.fastq",
            "output": "/work/bbmerge",
        }
    ) == (
        "ln -s reads.fastq /work/bbmerge/forward.fastq && "
        'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
        'export _JAVA_OPTIONS="${_JAVA_OPTIONS} -Xmx${GALAXY_MEMORY_MB:-4096}m -Xms256m"; fi && '
        'bbmerge.sh tmpdir="$TMPDIR" t="${GALAXY_SLOTS:-2}" '
        "in=/work/bbmerge/forward.fastq interleaved=t out=/work/bbmerge/merged.fastq "
        "outu=/work/bbmerge/unmerged.fastq ihist=/work/bbmerge/ihist.tabular touppercase=t "
        "qtrim=f trimq=6 minlength=60 usequality=t usejni=f ecco=f trimnonoverlapping=f "
        "mininsert=35 minoverlap=12 minq=9 maxq=41 entropy=t efilter=6 pfilter=0.00004 "
        "kfilter=41 usequality=t maxratio=0.09 ratiomargin=5.5 ratiooffset=0.55 "
        "maxmismatches=20 ratiominoverlapreduction=0 minsecondratio=0.1 default=t"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bbtools_bbmerge" / "merged.fastq",
        tmp_path / "bbtools_bbmerge" / "unmerged.fastq",
        tmp_path / "bbtools_bbmerge" / "ihist.tabular",
    ]
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": ""}) == "read1 FASTQ is required"
    assert node_class.VALIDATE_INPUTS({"input_type": "pair", "read1": "r1.fq", "read2": ""}) == (
        "read2 FASTQ is required for paired input"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "bad", "read1": "reads.fq"}) == (
        "input_type must be one of: single, pair, paired"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "threads": 0}) == (
        "threads must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "pfilter": -1}) == (
        "pfilter must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq"}) is True


def test_bbtools_bbnorm_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_bbnorm"]

    assert node_info["display_name"] == "BBTools BBNorm"
    assert node_info["category"] == "qc"
    assert node_info["description"].startswith("Normalize sequencing coverage")
    assert node_info["output"] == ["FASTQ", "FASTQ", "FASTQ", "FASTQ", "TSV", "TSV"]
    assert node_info["output_name"] == [
        "normalised_R1",
        "normalised_R2",
        "normalised_pair",
        "discarded_reads",
        "kmer_hist_input",
        "kmer_hist_output",
    ]
    assert node_info["required_executables"] == ["bbnorm.sh"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbnorm-guide/"
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "coverage normalization" in node_info["search_aliases"]


def test_bbtools_bbnorm_renders_normalization_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_bbnorm")

    assert node_class.render_command(
        {
            "input_type": "PE_2files",
            "read1": "sample R1.fastq.gz",
            "read2": "sample R2.fastq.gz",
            "target": 80,
            "maxdepth": 120,
            "mindepth": 8,
            "minkmers": 20,
            "percentile": 60,
            "uselowerdepth": False,
            "deterministic": False,
            "fixspikes": True,
            "passes": 3,
            "k": 29,
            "bits": 8,
            "hashes": 4,
            "prefilter": True,
            "prehashes": 3,
            "prefilterbits": 2,
            "prefiltersize": 0.25,
            "buildpasses": 2,
            "minq": 10,
            "minprob": 0.7,
            "rdk": False,
            "hdp": 91,
            "ldp": 20,
            "tossbadreads": True,
            "requirebothbad": True,
            "errordetectratio": 130,
            "highthresh": 13,
            "lowthresh": 4,
            "ecc": True,
            "ecclimit": 4,
            "errorcorrectratio": 150,
            "echighthresh": 24,
            "eclowthresh": 3,
            "eccmaxqual": 40,
            "meo": True,
            "mue": False,
            "overlap": True,
            "save_discarded_reads": True,
            "save_kmer_hists": True,
            "threads": 10,
            "memory_mb": 8192,
            "output": "/work/bbnorm",
        }
    ) == (
        "ln -s 'sample R1.fastq.gz' /work/bbnorm/forward.fastq.gz && "
        "ln -s 'sample R2.fastq.gz' /work/bbnorm/reverse.fastq.gz && "
        'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
        'export _JAVA_OPTIONS="${_JAVA_OPTIONS} -Xmx${GALAXY_MEMORY_MB:-8192}m -Xms256m"; fi && '
        'bbnorm.sh tmpdir="$TMPDIR" t="${GALAXY_SLOTS:-10}" '
        "in1=/work/bbnorm/forward.fastq.gz in2=/work/bbnorm/reverse.fastq.gz interleaved=f "
        "out=/work/bbnorm/normalised_R1.fastq out2=/work/bbnorm/normalised_R2.fastq "
        "outt=/work/bbnorm/discarded.fastq touppercase=t "
        "hist=/work/bbnorm/kmer_hist_input.tabular histout=/work/bbnorm/kmer_hist_output.tabular "
        "k=29 bits=8 hashes=4 prefilter=t prehashes=3 prefilterbits=2 prefiltersize=0.25 "
        "buildpasses=2 minq=10 minprob=0.7 rdk=f fixspikes=t target=80 maxdepth=120 "
        "mindepth=8 minkmers=20 percentile=60 uselowerdepth=f deterministic=f passes=3 "
        "hdp=91 ldp=20 tossbadreads=t requirebothbad=t errordetectratio=130 highthresh=13 lowthresh=4 "
        "ecc=t ecclimit=4 errorcorrectratio=150 echighthresh=24 eclowthresh=3 eccmaxqual=40 meo=t mue=f overlap=t"
    )
    assert node_class.render_command(
        {
            "input_type": "single_end",
            "read1": "reads.fastq",
            "output": "/work/bbnorm",
        }
    ) == (
        "ln -s reads.fastq /work/bbnorm/forward.fastq && "
        'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
        'export _JAVA_OPTIONS="${_JAVA_OPTIONS} -Xmx${GALAXY_MEMORY_MB:-4096}m -Xms256m"; fi && '
        'bbnorm.sh tmpdir="$TMPDIR" t="${GALAXY_SLOTS:-2}" '
        "in=/work/bbnorm/forward.fastq interleaved=f out=/work/bbnorm/normalised_R1.fastq "
        "touppercase=t k=31 bits=16 hashes=3 buildpasses=1 minq=6 minprob=0.5 rdk=t "
        "fixspikes=f target=100 maxdepth=-1 mindepth=5 minkmers=15 percentile=54 "
        "uselowerdepth=t deterministic=t passes=2 hdp=90 ldp=25 tossbadreads=f requirebothbad=f "
        "errordetectratio=125 highthresh=12 lowthresh=3"
    )
    assert node_class.PLAN_OUTPUTS(
        {"input_type": "PE_2files", "save_discarded_reads": True, "save_kmer_hists": True},
        tmp_path,
    ) == [
        tmp_path / "bbtools_bbnorm" / "normalised_R1.fastq",
        tmp_path / "bbtools_bbnorm" / "normalised_R2.fastq",
        tmp_path / "bbtools_bbnorm" / "discarded.fastq",
        tmp_path / "bbtools_bbnorm" / "kmer_hist_input.tabular",
        tmp_path / "bbtools_bbnorm" / "kmer_hist_output.tabular",
    ]
    assert node_class.PLAN_OUTPUTS({"input_type": "paired"}, tmp_path) == [
        tmp_path / "bbtools_bbnorm" / "normalised_R1.fastq",
        tmp_path / "bbtools_bbnorm" / "normalised_R2.fastq",
    ]
    assert node_class.VALIDATE_INPUTS({"input_type": "single_end", "read1": ""}) == "read1 FASTQ is required"
    assert node_class.VALIDATE_INPUTS({"input_type": "PE_2files", "read1": "r1.fq", "read2": ""}) == (
        "read2 FASTQ is required for paired input"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "bad", "read1": "reads.fq"}) == (
        "input_type must be one of: single_end, PE_1file, PE_2files, paired"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single_end", "read1": "reads.fq", "target": 0}) == (
        "target must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single_end", "read1": "reads.fq", "percentile": 101}) == (
        "percentile must be between 1 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single_end", "read1": "reads.fq"}) is True


def test_bbtools_tadpole_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_tadpole"]

    assert node_info["display_name"] == "BBTools Tadpole"
    assert node_info["category"] == "assembly"
    assert node_info["description"].startswith("Assemble, extend, or correct reads")
    assert node_info["output"] == ["FASTQ", "FASTQ", "FASTA"]
    assert node_info["output_name"] == ["output", "reverse_output", "fastadump"]
    assert node_info["required_executables"] == ["tadpole.sh"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/tadpole-guide/"
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "kmer assembler" in node_info["search_aliases"]


def test_bbtools_tadpole_renders_mode_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_tadpole")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fastq.gz",
            "read2": "sample R2.fastq.gz",
            "mode": "correct",
            "fastadump": True,
            "mincounttodump": 3,
            "threads": 9,
            "output": "/work/tadpole",
        }
    ) == (
        "ln -s 'sample R1.fastq.gz' /work/tadpole/forward.fastq.gz && "
        "ln -s 'sample R2.fastq.gz' /work/tadpole/reverse.fastq.gz && "
        "tadpole.sh in=/work/tadpole/forward.fastq.gz in2=/work/tadpole/reverse.fastq.gz "
        "fastadump=t mincounttodump=3 dump=/work/tadpole/fastadump.fasta "
        "out=/work/tadpole/output.fastq out2=/work/tadpole/reverse_output.fastq "
        "mode=correct threads=${GALAXY_SLOTS:-9} overwrite=true"
    )
    assert node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads.fastq",
            "mode": "contig",
            "fastadump": False,
            "output": "/work/tadpole",
        }
    ) == (
        "ln -s reads.fastq /work/tadpole/forward.fastq && "
        "tadpole.sh in=/work/tadpole/forward.fastq fastadump=f mincounttodump=1 "
        "out=/work/tadpole/output.fastq mode=contig threads=${GALAXY_SLOTS:-4} overwrite=true"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "pair", "mode": "correct", "fastadump": True}, tmp_path) == [
        tmp_path / "bbtools_tadpole" / "output.fastq",
        tmp_path / "bbtools_tadpole" / "reverse_output.fastq",
        tmp_path / "bbtools_tadpole" / "fastadump.fasta",
    ]
    assert node_class.PLAN_OUTPUTS({"input_type": "pair", "mode": "contig", "fastadump": True}, tmp_path) == [
        tmp_path / "bbtools_tadpole" / "output.fastq",
        tmp_path / "bbtools_tadpole" / "fastadump.fasta",
    ]
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": ""}) == "read1 FASTQ is required"
    assert node_class.VALIDATE_INPUTS({"input_type": "pair", "read1": "r1.fq", "read2": ""}) == (
        "read2 FASTQ is required for paired input"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "mode": "bad"}) == (
        "mode must be one of: contig, extend, correct"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "mincounttodump": 0}) == (
        "mincounttodump must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq"}) is True


def test_bbtools_callvariants_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_callvariants"]

    assert node_info["display_name"] == "BBTools CallVariants"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call variants from aligned BAM files")
    assert node_info["output"] == ["VCF", "TSV", "TSV", "TSV"]
    assert node_info["output_name"] == ["variants", "score_histogram", "zygosity_histogram", "quality_histogram"]
    assert node_info["required_executables"] == ["callvariants.sh"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/callvariants-guide/"
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "variant caller" in node_info["search_aliases"]


def test_bbtools_callvariants_renders_variant_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_callvariants")

    assert node_class.render_command(
        {
            "input": "sample alignments.bam",
            "reference": "reference genome.fa",
            "ploidy": 2,
            "output_format": "vcf",
            "output_variant_score_hist": True,
            "output_zygosity_hist": True,
            "output_quality_hist": True,
            "threads": 7,
            "output": "/work/callvariants",
        }
    ) == (
        "ln -s 'sample alignments.bam' /work/callvariants/sample_alignments.bam.bam && "
        "callvariants.sh in=/work/callvariants/sample_alignments.bam.bam threads=${GALAXY_SLOTS:-7} "
        "'ref=reference genome.fa' ploidy=2 shist=/work/callvariants/score_histogram.tsv "
        "zhist=/work/callvariants/zygosity_histogram.tsv qhist=/work/callvariants/quality_histogram.tsv "
        "vcf=out.vcf && mv out.vcf /work/callvariants/variants.vcf"
    )
    assert node_class.render_command(
        {
            "input": "mapped.bam",
            "reference": "ref.fa",
            "output_format": "gff",
            "output": "/work/callvariants",
        }
    ) == (
        "ln -s mapped.bam /work/callvariants/mapped.bam.bam && "
        "callvariants.sh in=/work/callvariants/mapped.bam.bam threads=${GALAXY_SLOTS:-4} "
        "ref=ref.fa ploidy=1 outgff=out.gff && mv out.gff /work/callvariants/variants.gff"
    )
    assert node_class.PLAN_OUTPUTS(
        {
            "output_format": "vcf",
            "output_variant_score_hist": True,
            "output_zygosity_hist": True,
            "output_quality_hist": True,
        },
        tmp_path,
    ) == [
        tmp_path / "bbtools_callvariants" / "variants.vcf",
        tmp_path / "bbtools_callvariants" / "score_histogram.tsv",
        tmp_path / "bbtools_callvariants" / "zygosity_histogram.tsv",
        tmp_path / "bbtools_callvariants" / "quality_histogram.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"output_format": "txt"}, tmp_path) == [
        tmp_path / "bbtools_callvariants" / "variants.txt",
    ]
    assert node_class.VALIDATE_INPUTS({"input": "", "reference": "ref.fa"}) == "input BAM is required"
    assert node_class.VALIDATE_INPUTS({"input": "mapped.bam", "reference": ""}) == "reference FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input": "mapped.bam", "reference": "ref.fa", "ploidy": 0}) == (
        "ploidy must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"input": "mapped.bam", "reference": "ref.fa", "output_format": "bad"}) == (
        "output_format must be one of: vcf, gff, txt"
    )
    assert node_class.VALIDATE_INPUTS({"input": "mapped.bam", "reference": "ref.fa"}) is True


def test_bbtools_bbmap_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["bbtools_bbmap"]

    assert node_info["display_name"] == "BBTools BBMap"
    assert node_info["category"] == "alignment"
    assert node_info["description"].startswith("Map short reads")
    assert node_info["output"] == ["BAM", "BAM", "BAM"]
    assert node_info["output_name"] == ["all_reads", "unmapped_reads", "mapped_reads"]
    assert node_info["required_executables"] == ["bbmap.sh", "samtools"]
    assert node_info["required_conda_packages"] == ["bbmap", "samtools"]
    assert node_info["documentation_url"] == "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmap-guide/"
    assert node_info["citation_dois"] == ["10.1371/journal.pone.0185056"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pone.0185056"]
    assert "Accurate paired shotgun read merging via overlap" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "short-read aligner" in node_info["search_aliases"]


def test_bbtools_bbmap_renders_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bbtools_bbmap")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fastq.gz",
            "read2": "sample R2.fastq.gz",
            "reference": "reference genome.fa",
            "output_sort": "unsorted",
            "maxindel": 20000,
            "strictmaxindel": True,
            "minid": 0.85,
            "local": True,
            "ambiguous": "all",
            "qtrim": "lr",
            "trimq": 12,
            "secondary": True,
            "maxsites": 9,
            "idfilter": 1,
            "threads": 6,
            "output": "/work/bbmap",
        }
    ) == (
        "ln -s 'sample R1.fastq.gz' /work/bbmap/forward.fastq.gz && "
        "ln -s 'sample R2.fastq.gz' /work/bbmap/reverse.fastq.gz && "
        "bbmap.sh nodisk=f 'ref=reference genome.fa' k=13 usemodulo=f rebuild=f "
        "in=/work/bbmap/forward.fastq.gz in2=/work/bbmap/reverse.fastq.gz "
        "fastareadlen=500 unpigz=f touppercase=t reads=-1 samplerate=1 skipreads=0 "
        "maxindel=20000 strictmaxindel=t tipsearch=100 minid=0.85 minhits=1 local=t "
        "perfectmode=f semiperfectmode=f threads=${GALAXY_SLOTS:-6} ambiguous=all "
        "samestrandpairs=f requirecorrectstrand=t killbadpairs=f pairedonly=f rcomp=f rcompmate=f "
        "pairlen=32000 rescuedist=1200 rescuemismatches=32 averagepairdist=100 deterministic=f "
        "bandwidthratio=0 bandwidth=0 usejni=f maxsites2=800 ignorefrequentkmers=t excludefraction=0.03 "
        "greedy=t kfilter=0 qin=auto qout=auto qtrim=lr untrim=f trimq=12 mintrimlength=60 "
        "fakefastaquality=-1 ignorebadquality=f usequality=t minaveragequality=0 maqb=0 idfilter=1 "
        "subfilter=-1 insfilter=-1 delfilter=-1 indelfilter=-1 editfilter=-1 inslenfilter=-1 "
        "dellenfilter=-1 nfilter=-1 secondary=t maxsites=9 sssr=0.95 ssao=f quickmatch=f "
        "trimreaddescriptions=f machineout=f printunmappedcount=f renamebyinsert=f "
        "out=all_reads.bam outu=unmapped_reads.bam outm=mapped_reads.bam && "
        "mv all_reads.bam /work/bbmap/all_reads.bam && "
        "mv unmapped_reads.bam /work/bbmap/unmapped_reads.bam && "
        "mv mapped_reads.bam /work/bbmap/mapped_reads.bam"
    )
    coordinate_command = node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads.fastq",
            "reference": "ref.fa",
            "output_sort": "coordinate",
            "output": "/work/bbmap",
        }
    )
    assert "samtools sort --no-PG -@${GALAXY_SLOTS:-4}" in coordinate_command
    assert "-o /work/bbmap/all_reads.bam all_reads.bam" in coordinate_command
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bbtools_bbmap" / "all_reads.bam",
        tmp_path / "bbtools_bbmap" / "unmapped_reads.bam",
        tmp_path / "bbtools_bbmap" / "mapped_reads.bam",
    ]
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "", "reference": "ref.fa"}) == (
        "read1 FASTQ is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "pair", "read1": "r1.fq", "read2": "", "reference": "ref.fa"}) == (
        "read2 FASTQ is required for paired input"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "reference": ""}) == (
        "reference FASTA is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "reference": "ref.fa", "output_sort": "bad"}) == (
        "output_sort must be one of: coordinate, name, unsorted"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "single", "read1": "reads.fq", "reference": "ref.fa"}) is True


def test_plasclass_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["plasclass"]

    assert node_info["display_name"] == "PlasClass"
    assert node_info["category"] == "metagenomics"
    assert node_info["description"].startswith("Classify plasmid and chromosome")
    assert node_info["output"] == ["TSV"]
    assert node_info["output_name"] == ["classification_scores"]
    assert node_info["required_executables"] == ["classify_fasta.py"]
    assert node_info["required_conda_packages"] == ["plasclass"]
    assert node_info["documentation_url"] == "https://github.com/Shamir-Lab/PlasClass"
    assert node_info["citation_dois"] == ["10.1371/journal.pcbi.1007781"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1371/journal.pcbi.1007781"]
    assert "PlasClass improves plasmid sequence classification" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "plasmid sequence classification" in node_info["search_aliases"]


def test_plasclass_renders_classification_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("plasclass")

    assert node_class.render_command(
        {
            "fasta": "assembly contigs.fa",
            "threads": 8,
            "output": "/work/plasclass",
        }
    ) == [
        "classify_fasta.py",
        "--fasta",
        "assembly contigs.fa",
        "--outfile",
        "/work/plasclass/classification_scores.tsv",
        "--num_processes",
        "${GALAXY_SLOTS:-8}",
    ]
    assert node_class.render_command(
        {
            "fasta": "contigs.fa",
            "output": "/work/plasclass",
        }
    )[-2:] == ["--num_processes", "${GALAXY_SLOTS:-1}"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "plasclass" / "classification_scores.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({"fasta": ""}) == "input FASTA is required"
    assert node_class.VALIDATE_INPUTS({"fasta": "contigs.fa", "threads": 0}) == "threads must be >= 1"
    assert node_class.VALIDATE_INPUTS({"fasta": "contigs.fa", "threads": 1}) is True


def test_plasflow_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["plasflow"]

    assert node_info["display_name"] == "PlasFlow"
    assert node_info["category"] == "metagenomics"
    assert node_info["description"].startswith("Predict plasmid sequences")
    assert node_info["output"] == ["TSV", "FASTA", "FASTA", "FASTA"]
    assert node_info["output_name"] == ["probability_table", "chromosomes", "plasmids", "unclassified"]
    assert node_info["required_executables"] == ["PlasFlow.py"]
    assert node_info["required_conda_packages"] == ["plasflow"]
    assert node_info["documentation_url"] == "https://github.com/smaegol/PlasFlow"
    assert node_info["citation_dois"] == ["10.1093/nar/gkx1321"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/nar/gkx1321"]
    assert "genome signatures" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "plasmid prediction" in node_info["search_aliases"]


def test_plasflow_renders_galaxy_staging_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("plasflow")

    assert node_class.render_command(
        {
            "read_file": "metagenome contigs.fasta.gz",
            "threshold": 0.85,
            "output": "/work/plasflow",
        }
    ) == (
        "gunzip -c 'metagenome contigs.fasta.gz' > reads.fasta && "
        "PlasFlow.py --input reads.fasta --output /work/plasflow/output --threshold 0.85"
    )
    assert node_class.render_command(
        {
            "read_file": "contigs.fasta",
            "output": "/work/plasflow",
        }
    ) == (
        "ln -s contigs.fasta reads.fasta && "
        "PlasFlow.py --input reads.fasta --output /work/plasflow/output --threshold 0.7"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "plasflow" / "output",
        tmp_path / "plasflow" / "output_chromosomes.fasta",
        tmp_path / "plasflow" / "output_plasmids.fasta",
        tmp_path / "plasflow" / "output_unclassified.fasta",
    ]
    assert node_class.VALIDATE_INPUTS({"read_file": ""}) == "contig FASTA is required"
    assert node_class.VALIDATE_INPUTS({"read_file": "contigs.fasta", "threshold": -0.1}) == (
        "threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"read_file": "contigs.fasta", "threshold": 1.1}) == (
        "threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"read_file": "contigs.fasta", "threshold": 0.7}) is True


def test_minia_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["minia"]

    assert node_info["display_name"] == "Minia"
    assert node_info["category"] == "assembly"
    assert node_info["description"].startswith("Assemble short reads")
    assert node_info["output"] == ["FASTA"]
    assert node_info["output_name"] == ["contigs"]
    assert node_info["required_executables"] == ["minia"]
    assert node_info["required_conda_packages"] == ["minia"]
    assert node_info["documentation_url"] == "https://github.com/GATB/minia"
    assert node_info["citation_dois"] == ["10.1186/1748-7188-8-22"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1186/1748-7188-8-22"]
    assert "de Bruijn graph" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "Bloom filter" in node_info["search_aliases"]


def test_minia_renders_assembly_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("minia")

    assert node_class.render_command(
        {
            "in": "reads sample.fastq.gz",
            "kmer_size": 55,
            "abundance_min": 3,
            "abundance_max": 120,
            "threads": 6,
            "output": "/work/minia",
        }
    ) == (
        "ln -s 'reads sample.fastq.gz' infile.fastq.gz && "
        "minia -in infile.fastq.gz -kmer-size 55 -abundance-min 3 -abundance-max 120 "
        "-nb-cores ${GALAXY_SLOTS:-6} -out /work/minia/output"
    )
    assert node_class.render_command(
        {
            "in": "reads.fa",
            "kmer_size": 31,
            "output": "/work/minia",
        }
    ) == (
        "ln -s reads.fa infile.fa && "
        "minia -in infile.fa -kmer-size 31 -nb-cores ${GALAXY_SLOTS:-1} -out /work/minia/output"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "minia" / "output.contigs.fa",
    ]
    assert node_class.VALIDATE_INPUTS({"in": ""}) == "input reads are required"
    assert node_class.VALIDATE_INPUTS({"in": "reads.fa", "kmer_size": 0}) == "kmer_size must be >= 1"
    assert node_class.VALIDATE_INPUTS({"in": "reads.fa", "abundance_min": -1}) == "abundance_min must be >= 0"
    assert node_class.VALIDATE_INPUTS({"in": "reads.fa", "threads": 0}) == "threads must be >= 1"
    assert node_class.VALIDATE_INPUTS({"in": "reads.fa", "kmer_size": 31, "threads": 1}) is True


def test_miniasm_exposes_galaxy_metadata_and_citation() -> None:
    node_info = _registry().object_info()["miniasm"]

    assert node_info["display_name"] == "Miniasm"
    assert node_info["category"] == "assembly"
    assert node_info["description"].startswith("Assemble noisy long reads")
    assert node_info["output"] == ["GFA"]
    assert node_info["output_name"] == ["assembly_graph"]
    assert node_info["required_executables"] == ["miniasm"]
    assert node_info["required_conda_packages"] == ["miniasm"]
    assert node_info["documentation_url"] == "https://github.com/lh3/miniasm"
    assert node_info["citation_dois"] == ["10.1093/bioinformatics/btw152"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1093/bioinformatics/btw152"]
    assert "fast mapping and de novo assembly" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "noisy long reads" in node_info["search_aliases"]


def test_miniasm_renders_galaxy_wrapper_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("miniasm")

    assert node_class.render_command(
        {
            "read_file": "reads sample.fq.gz",
            "paf": "overlaps sample.paf.gz",
            "min_match": 99,
            "min_iden": 0.04,
            "min_span": 999,
            "min_cov": 2,
            "min_ovlp": 999,
            "max_hang": 999,
            "int_thres": 0.7,
            "max_gap_diff": 999,
            "max_bub_dist": 45000,
            "min_utg_size": 3,
            "n_rounds": 2,
            "final_drop_ratio": 0.7,
            "output": "/work/miniasm",
        }
    ) == (
        "miniasm -f 'reads sample.fq.gz' -m 99 -i 0.04 -s 999 -c 2 "
        "-o 999 -h 999 -I 0.7 -g 999 -d 45000 -e 3 -n 2 -F 0.7 "
        "'overlaps sample.paf.gz' > /work/miniasm/assembly_graph.gfa"
    )
    assert node_class.render_command(
        {
            "read_file": "reads.fq",
            "paf": "overlaps.paf",
            "output": "/work/miniasm",
        }
    ) == (
        "miniasm -f reads.fq -m 100 -i 0.05 -s 1000 -c 3 "
        "-o 1000 -h 1000 -I 0.08 -g 1000 -d 50000 -e 4 -n 3 -F 0.8 "
        "overlaps.paf > /work/miniasm/assembly_graph.gfa"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "miniasm" / "assembly_graph.gfa",
    ]
    assert node_class.VALIDATE_INPUTS({"read_file": "", "paf": "overlaps.paf"}) == "sequence reads are required"
    assert node_class.VALIDATE_INPUTS({"read_file": "reads.fq", "paf": ""}) == "PAF overlaps are required"
    assert node_class.VALIDATE_INPUTS({"read_file": "reads.fq", "paf": "overlaps.paf", "min_match": -1}) == (
        "min_match must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"read_file": "reads.fq", "paf": "overlaps.paf", "min_iden": -0.1}) == (
        "min_iden must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"read_file": "reads.fq", "paf": "overlaps.paf"}) is True


def test_prinseq_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["prinseq"]

    assert info["output"] == ["FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ"]
    assert info["output_name"] == [
        "good_sequences",
        "rejected_sequences",
        "good_sequences_1",
        "good_sequences_1_singletons",
        "good_sequences_2",
        "rejected_sequences_2",
    ]
    assert info["citation_dois"] == ["10.1093/bioinformatics/btr026"]
    assert info["required_executables"] == ["prinseq-lite.pl"]
    assert info["required_conda_packages"] == ["prinseq"]


def test_prinseq_renders_single_end_filter_and_trim_command(tmp_path: Path) -> None:
    node_class = _node_class("prinseq")

    assert node_class.render_command(
        {
            "input_singles": "reads.fastq.gz",
            "paired": False,
            "phred64": True,
            "min_len": 60,
            "min_qual_mean": 15,
            "ns_max_p": 2,
            "trim_qual_right": 20,
            "trim_qual_type": "min",
            "trim_qual_rule": "lt",
            "trim_qual_window": 1,
            "trim_qual_step": 1,
            "output": "/work/prinseq",
        }
    ) == (
        "set -eu && mkdir -p /work/prinseq/tmp && "
        "gunzip -c reads.fastq.gz > fwd.fastq && "
        "touch /work/prinseq/tmp/good_sequences.fastq /work/prinseq/tmp/rejected_sequences.fastq && "
        "prinseq-lite.pl -fastq fwd.fastq -phred64 -out_good /work/prinseq/tmp/good_sequences "
        "-out_bad /work/prinseq/tmp/rejected_sequences -min_len 60 -min_qual_mean 15 -ns_max_p 2 "
        "-trim_qual_right 20 -trim_qual_type min -trim_qual_rule lt -trim_qual_window 1 -trim_qual_step 1 && "
        "gzip -c /work/prinseq/tmp/good_sequences.fastq > /work/prinseq/good_sequences.fastq.gz && "
        "gzip -c /work/prinseq/tmp/rejected_sequences.fastq > /work/prinseq/rejected_sequences.fastq.gz"
    )

    assert node_class.PLAN_OUTPUTS({"paired": False}, tmp_path) == [
        tmp_path / "prinseq" / "good_sequences.fastq.gz",
        tmp_path / "prinseq" / "rejected_sequences.fastq.gz",
    ]


def test_prinseq_renders_paired_end_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("prinseq")

    assert node_class.render_command(
        {
            "input_mate1": "r1.fastq",
            "input_mate2": "r2.fastq",
            "paired": True,
            "min_len": 50,
            "min_qual_mean": 15,
            "ns_max_p": 2,
            "trim_qual_right": 20,
            "output": "/work/prinseq",
        }
    ) == (
        "set -eu && mkdir -p /work/prinseq/tmp && "
        "ln -sf r1.fastq fwd.fastq && ln -sf r2.fastq rev.fastq && "
        "touch /work/prinseq/tmp/good_sequences_1.fastq /work/prinseq/tmp/good_sequences_1_singletons.fastq "
        "/work/prinseq/tmp/rejected_sequences_1.fastq /work/prinseq/tmp/good_sequences_2.fastq "
        "/work/prinseq/tmp/good_sequences_2_singletons.fastq /work/prinseq/tmp/rejected_sequences_2.fastq && "
        "prinseq-lite.pl -fastq fwd.fastq -fastq2 rev.fastq -out_good /work/prinseq/tmp/good_sequences "
        "-out_bad /work/prinseq/tmp/rejected_sequences -min_len 50 -min_qual_mean 15 -ns_max_p 2 "
        "-trim_qual_right 20 && "
        "cp /work/prinseq/tmp/good_sequences_1.fastq /work/prinseq/good_sequences_1.fastq && "
        "cp /work/prinseq/tmp/good_sequences_1_singletons.fastq /work/prinseq/good_sequences_1_singletons.fastq && "
        "cp /work/prinseq/tmp/rejected_sequences_1.fastq /work/prinseq/rejected_sequences_1.fastq && "
        "cp /work/prinseq/tmp/good_sequences_2.fastq /work/prinseq/good_sequences_2.fastq && "
        "cp /work/prinseq/tmp/good_sequences_2_singletons.fastq /work/prinseq/good_sequences_2_singletons.fastq && "
        "cp /work/prinseq/tmp/rejected_sequences_2.fastq /work/prinseq/rejected_sequences_2.fastq"
    )

    assert node_class.PLAN_OUTPUTS({"paired": True, "compress_output": False}, tmp_path) == [
        tmp_path / "prinseq" / "good_sequences_1.fastq",
        tmp_path / "prinseq" / "good_sequences_1_singletons.fastq",
        tmp_path / "prinseq" / "rejected_sequences_1.fastq",
        tmp_path / "prinseq" / "good_sequences_2.fastq",
        tmp_path / "prinseq" / "good_sequences_2_singletons.fastq",
        tmp_path / "prinseq" / "rejected_sequences_2.fastq",
    ]


def test_vsearch_search_and_cluster_render_commands_and_outputs(tmp_path: Path) -> None:
    search_class = _node_class("vsearch_search")
    cluster_class = _node_class("vsearch_cluster")

    assert search_class.render_command(
        {
            "query": "queries.fasta",
            "database": "db.fasta",
            "search_mode": "usearch_global",
            "identity": 0.97,
            "strand": "both",
            "maxaccepts": 10,
            "maxrejects": 32,
            "threads": 6,
            "output": "/work/vsearch_search",
        }
    ) == [
        "vsearch",
        "--usearch_global",
        "queries.fasta",
        "--db",
        "db.fasta",
        "--id",
        "0.97",
        "--strand",
        "both",
        "--maxaccepts",
        "10",
        "--maxrejects",
        "32",
        "--threads",
        "6",
        "--blast6out",
        "/work/vsearch_search/matches.tsv",
        "--alnout",
        "/work/vsearch_search/alignments.txt",
        "--notmatched",
        "/work/vsearch_search/unmatched.fasta",
    ]
    assert search_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_search" / "matches.tsv",
        tmp_path / "vsearch_search" / "alignments.txt",
        tmp_path / "vsearch_search" / "unmatched.fasta",
    ]

    assert cluster_class.render_command(
        {
            "sequences": "amplicons.fasta",
            "cluster_mode": "cluster_fast",
            "identity": 0.99,
            "strand": "plus",
            "sizein": True,
            "sizeout": True,
            "threads": 4,
            "output": "/work/vsearch_cluster",
        }
    ) == [
        "vsearch",
        "--cluster_fast",
        "amplicons.fasta",
        "--id",
        "0.99",
        "--strand",
        "plus",
        "--sizein",
        "--sizeout",
        "--threads",
        "4",
        "--centroids",
        "/work/vsearch_cluster/centroids.fasta",
        "--uc",
        "/work/vsearch_cluster/clusters.uc",
    ]


def test_vsearch_dereplication_renders_abundance_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_dereplication")
    info = _registry().object_info()["vsearch_dereplication"]

    assert info["output"] == ["FASTA", "TSV"]
    assert info["output_name"] == ["dereplicated_sequences", "uclust_output"]
    assert node_class.render_command(
        {
            "infile": "amplicons.fasta",
            "threads": 6,
            "minuniquesize": 2,
            "maxuniquesize": 100000,
            "sizein": True,
            "sizeout": True,
            "strand": "both",
            "topn": 10000,
            "uc": True,
            "output": "/work/vsearch_dereplication",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--derep_fulllength",
        "amplicons.fasta",
        "--maxuniquesize",
        "100000",
        "--minuniquesize",
        "2",
        "--output",
        "/work/vsearch_dereplication/dereplicated.fasta",
        "--sizein",
        "--sizeout",
        "--strand",
        "both",
        "--topn",
        "10000",
        "--uc",
        "/work/vsearch_dereplication/dereplication.uc",
    ]

    assert node_class.PLAN_OUTPUTS({"uc": True}, tmp_path) == [
        tmp_path / "vsearch_dereplication" / "dereplicated.fasta",
        tmp_path / "vsearch_dereplication" / "dereplication.uc",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_dereplication" / "dereplicated.fasta",
    ]


def test_vsearch_masking_renders_maskfasta_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_masking")
    info = _registry().object_info()["vsearch_masking"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["masked_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "qmask": "dust",
            "hardmask": True,
            "output": "/work/vsearch_masking",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--qmask",
        "dust",
        "--hardmask",
        "--maskfasta",
        "db.fasta",
        "--output",
        "/work/vsearch_masking/masked.fasta",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "qmask": "none",
            "hardmask": False,
            "output": "/work/vsearch_masking",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--maskfasta",
        "db.fasta",
        "--output",
        "/work/vsearch_masking/masked.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_masking" / "masked.fasta",
    ]


def test_vsearch_shuffling_renders_shuffle_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_shuffling")
    info = _registry().object_info()["vsearch_shuffling"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["shuffled_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "randseed": 1,
            "topn": 5,
            "output": "/work/vsearch_shuffling",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--output",
        "/work/vsearch_shuffling/shuffled.fasta",
        "--randseed",
        "1",
        "--shuffle",
        "db.fasta",
        "--topn",
        "5",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "randseed": 0,
            "topn": "",
            "output": "/work/vsearch_shuffling",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--output",
        "/work/vsearch_shuffling/shuffled.fasta",
        "--randseed",
        "0",
        "--shuffle",
        "db.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_shuffling" / "shuffled.fasta",
    ]


def test_vsearch_sorting_renders_length_and_abundance_commands(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_sorting")
    info = _registry().object_info()["vsearch_sorting"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["sorted_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "sorting_mode": "sortbylength",
            "relabel": "With spaces",
            "sizeout": True,
            "topn": 5,
            "output": "/work/vsearch_sorting",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--sortbylength",
        "db.fasta",
        "--output",
        "/work/vsearch_sorting/sorted.fasta",
        "--relabel",
        "With spaces",
        "--sizeout",
        "--topn",
        "5",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "sorting_mode": "sortbyabundance",
            "minsize": 2,
            "maxsize": 500,
            "sizeout": False,
            "topn": "",
            "output": "/work/vsearch_sorting",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--sortbysize",
        "db.fasta",
        "--minsize",
        "2",
        "--maxsize",
        "500",
        "--output",
        "/work/vsearch_sorting/sorted.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_sorting" / "sorted.fasta",
    ]


def test_vsearch_alignment_renders_allpairs_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_alignment")
    info = _registry().object_info()["vsearch_alignment"]

    assert info["output"] == ["STATS_FILE", "TSV"]
    assert info["output_name"] == ["alignments", "userfields"]
    assert node_class.render_command(
        {
            "infile": "reads.fasta",
            "threads": 6,
            "acceptall": True,
            "id": 0.97,
            "iddef": 2,
            "query_cov": 0.95,
            "userfields_output_select": "yes",
            "userfields": ["query", "target"],
            "output": "/work/vsearch_alignment",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--acceptall",
        "--id",
        "0.97",
        "--iddef",
        "2",
        "--allpairs_global",
        "reads.fasta",
        "--alnout",
        "/work/vsearch_alignment/alignments.txt",
        "--query_cov",
        "0.95",
        "--userfields",
        "query+target",
        "--userout",
        "/work/vsearch_alignment/userfields.tsv",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"userfields_output_select": "yes", "userfields": ["query", "target"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
        tmp_path / "vsearch_alignment" / "userfields.tsv",
    ]
    assert node_class.render_command(
        {
            "infile": "reads.fasta",
            "userfields_output_select": "no",
            "userfields": ["query", "target"],
            "output": "/work/vsearch_alignment",
        }
    ) == [
        "vsearch",
        "--threads",
        "4",
        "--notrunclabels",
        "--id",
        "0.97",
        "--iddef",
        "2",
        "--allpairs_global",
        "reads.fasta",
        "--alnout",
        "/work/vsearch_alignment/alignments.txt",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"userfields_output_select": "no", "userfields": ["query", "target"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
    ]


def test_vsearch_chimera_detection_renders_uchime_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_chimera_detection")
    info = _registry().object_info()["vsearch_chimera_detection"]

    assert info["output"] == ["FASTA", "FASTA", "STATS_FILE", "TSV"]
    assert info["output_name"] == ["chimeras", "nonchimeras", "uchime_alignments", "uchimeout"]
    assert node_class.render_command(
        {
            "detection_mode": "denovo",
            "infile_denovo": "amplicons.fasta",
            "threads": 6,
            "abskew": 2.0,
            "dn": 1.4,
            "mindiffs": 3,
            "mindiv": 0.8,
            "minh": 0.28,
            "xn": 8.0,
            "outputs": ["nonchimeras", "uchimealns", "uchimeout"],
            "output": "/work/vsearch_chimera_detection",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--abskew",
        "2.0",
        "--chimeras",
        "/work/vsearch_chimera_detection/chimeras.fasta",
        "--dn",
        "1.4",
        "--mindiffs",
        "3",
        "--mindiv",
        "0.8",
        "--minh",
        "0.28",
        "--xn",
        "8.0",
        "--uchime_denovo",
        "amplicons.fasta",
        "--nonchimeras",
        "/work/vsearch_chimera_detection/nonchimeras.fasta",
        "--uchimealns",
        "/work/vsearch_chimera_detection/uchime_alignments.txt",
        "--uchimeout",
        "/work/vsearch_chimera_detection/uchimeout.tsv",
    ]
    assert node_class.render_command(
        {
            "detection_mode": "reference",
            "infile_reference": "queries.fasta",
            "db": "gold.fasta",
            "self_param": True,
            "selfid_param": True,
            "outputs": ["uchimeout"],
            "output": "/work/vsearch_chimera_detection",
        }
    ) == [
        "vsearch",
        "--threads",
        "4",
        "--notrunclabels",
        "--abskew",
        "2.0",
        "--chimeras",
        "/work/vsearch_chimera_detection/chimeras.fasta",
        "--dn",
        "1.4",
        "--mindiffs",
        "3",
        "--mindiv",
        "0.8",
        "--minh",
        "0.28",
        "--xn",
        "8.0",
        "--self",
        "--selfid",
        "--uchime_ref",
        "queries.fasta",
        "--db",
        "gold.fasta",
        "--uchimeout",
        "/work/vsearch_chimera_detection/uchimeout.tsv",
    ]

    assert node_class.PLAN_OUTPUTS(
        {"outputs": ["nonchimeras", "uchimealns", "uchimeout"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_chimera_detection" / "chimeras.fasta",
        tmp_path / "vsearch_chimera_detection" / "nonchimeras.fasta",
        tmp_path / "vsearch_chimera_detection" / "uchime_alignments.txt",
        tmp_path / "vsearch_chimera_detection" / "uchimeout.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_chimera_detection" / "chimeras.fasta",
    ]


def test_diamond_nodes_render_database_and_alignment_commands(tmp_path: Path) -> None:
    makedb_class = _node_class("diamond_makedb")
    align_class = _node_class("diamond_align")

    assert makedb_class.render_command(
        {
            "infile": "proteins.faa",
            "threads": 12,
            "taxonmap": "prot.accession2taxid.gz",
            "taxonnodes": "nodes.dmp",
            "taxonnames": "names.dmp",
            "output": "/work/diamond_makedb",
        }
    ) == [
        "diamond",
        "makedb",
        "--threads",
        "12",
        "--in",
        "proteins.faa",
        "--db",
        "/work/diamond_makedb/database",
        "--taxonmap",
        "prot.accession2taxid.gz",
        "--taxonnodes",
        "nodes.dmp",
        "--taxonnames",
        "names.dmp",
    ]
    assert makedb_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "diamond_makedb" / "database.dmnd"]

    assert align_class.render_command(
        {
            "query": "reads.fasta",
            "database": "nr.dmnd",
            "method": "blastx",
            "threads": 10,
            "sensitivity": "--very-sensitive",
            "evalue": 1e-5,
            "max_target_seqs": 25,
            "matrix": "BLOSUM62",
            "query_gencode": 1,
            "query_strand": "both",
            "min_orf": 20,
            "outfmt": "6 qseqid sseqid pident length evalue bitscore",
            "output": "/work/diamond_align",
        }
    ) == [
        "diamond",
        "blastx",
        "--threads",
        "10",
        "--db",
        "nr.dmnd",
        "--query",
        "reads.fasta",
        "--out",
        "/work/diamond_align/matches.tsv",
        "--outfmt",
        "6",
        "qseqid",
        "sseqid",
        "pident",
        "length",
        "evalue",
        "bitscore",
        "--very-sensitive",
        "--evalue",
        "1e-05",
        "--max-target-seqs",
        "25",
        "--matrix",
        "BLOSUM62",
        "--query-gencode",
        "1",
        "--strand",
        "both",
        "--min-orf",
        "20",
    ]


def test_hmmer_alimask_renders_mask_ranges_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_alimask")
    info = _registry().object_info()["hmmer_alimask"]

    assert info["output"] == ["ALIGNMENT"]
    assert info["output_name"] == ["masked_alignment"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["optional"]["symfrac"][1]["displayOptions"] == {
        "show": {"model_construction": ["fast"]},
    }
    assert info["input"]["optional"]["wid"][1]["displayOptions"] == {
        "show": {"relative_weighting": ["--wblosum"]},
    }
    assert node_class.render_command(
        {
            "msafile": "globins.sto",
            "range_type": "model",
            "ranges": ["10-20", "45-60"],
            "input_format": "--amino",
            "model_construction": "fast",
            "symfrac": 0.45,
            "fragthresh": 0.7,
            "relative_weighting": "--wblosum",
            "wid": 0.8,
            "seed": 4,
            "output": "/work/alimask",
        }
    ) == [
        "alimask",
        "--modelrange",
        "10-20,45-60",
        "--amino",
        "--fast",
        "--symfrac",
        "0.45",
        "--fragthresh",
        "0.7",
        "--wblosum",
        "--wid",
        "0.8",
        "--seed",
        "4",
        "globins.sto",
        "/work/alimask/masked.sto",
    ]

    assert node_class.render_command(
        {
            "msafile": "globins.sto",
            "range_type": "ali",
            "ranges": ["5-15"],
            "input_format": "--dna",
            "model_construction": "hand",
            "relative_weighting": "--wpb",
            "seed": 42,
            "output": "/work/alimask",
        }
    ) == [
        "alimask",
        "--alirange",
        "5-15",
        "--dna",
        "--hand",
        "--fragthresh",
        "0.5",
        "--wpb",
        "--seed",
        "42",
        "globins.sto",
        "/work/alimask/masked.sto",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_alimask" / "masked.sto"]


def test_hmmer_hmmalign_renders_stockholm_alignment_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmalign")
    info = _registry().object_info()["hmmer_hmmalign"]

    assert info["output"] == ["ALIGNMENT"]
    assert info["output_name"] == ["alignment"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["input_format_select"][1]["options"] == ["--amino", "--dna", "--rna"]
    assert node_class.render_command(
        {
            "seq": "globins45.fa",
            "hmmfile": "globins4.hmm",
            "trim": True,
            "input_format_select": "--amino",
            "output": "/work/hmmalign",
        }
    ) == [
        "hmmalign",
        "--trim",
        "--amino",
        "--outformat",
        "stockholm",
        "globins4.hmm",
        "globins45.fa",
        ">",
        "/work/hmmalign/alignment.sto",
    ]

    assert node_class.render_command(
        {
            "seq": "reads.fasta",
            "hmmfile": "model.hmm",
            "trim": False,
            "input_format_select": "--rna",
            "output": "/work/hmmalign",
        }
    ) == [
        "hmmalign",
        "--rna",
        "--outformat",
        "stockholm",
        "model.hmm",
        "reads.fasta",
        ">",
        "/work/hmmalign/alignment.sto",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmalign" / "alignment.sto"]


def test_hmmer_hmmbuild_renders_profile_build_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmbuild")
    info = _registry().object_info()["hmmer_hmmbuild"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["hmm_profile"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["optional"]["symfrac"][1]["displayOptions"] == {
        "show": {"model_construction": ["fast"]},
    }
    assert info["input"]["optional"]["wid"][1]["displayOptions"] == {
        "show": {"relative_weighting": ["--wblosum"]},
    }
    assert info["input"]["optional"]["esigma"][1]["displayOptions"] == {
        "show": {"effective_weighting": ["eent"]},
    }
    assert node_class.render_command(
        {
            "msafile": "globins4.sto",
            "hmmname": "globins",
            "input_format_select": "--amino",
            "model_construction": "fast",
            "symfrac": 0.6,
            "fragthresh": 0.4,
            "relative_weighting": "--wblosum",
            "wid": 0.7,
            "effective_weighting": "eent",
            "eset": 2.5,
            "ere": 0.59,
            "esigma": 45,
            "prior": "--pnone",
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "eml": 220,
            "emn": 210,
            "evl": 230,
            "evn": 220,
            "efl": 120,
            "efn": 210,
            "eft": 0.05,
            "threads": 6,
            "seed": 4,
            "w_beta": 1e-7,
            "w_length": 450,
            "maxinsertlen": 25,
            "output": "/work/hmmbuild",
        }
    ) == [
        "hmmbuild",
        "-n",
        "globins",
        "--amino",
        "--fast",
        "--symfrac",
        "0.6",
        "--fragthresh",
        "0.4",
        "--wblosum",
        "--wid",
        "0.7",
        "--eent",
        "--eset",
        "2.5",
        "--ere",
        "0.59",
        "--esigma",
        "45",
        "--pnone",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "--EmL",
        "220",
        "--EmN",
        "210",
        "--EvL",
        "230",
        "--EvN",
        "220",
        "--EfL",
        "120",
        "--EfN",
        "210",
        "--Eft",
        "0.05",
        "--cpu",
        "5",
        "--seed",
        "4",
        "--w_beta",
        "1e-07",
        "--w_length",
        "450",
        "--maxinsertlen",
        "25",
        "/work/hmmbuild/profile.hmm",
        "globins4.sto",
    ]

    assert node_class.render_command(
        {
            "msafile": "MADE1.sto",
            "input_format_select": "--dna",
            "model_construction": "hand",
            "relative_weighting": "--wpb",
            "effective_weighting": "enone",
            "prior": "",
            "single_sequence_scoring": "false",
            "threads": 1,
            "seed": 42,
            "output": "/work/hmmbuild",
        }
    ) == [
        "hmmbuild",
        "--dna",
        "--hand",
        "--fragthresh",
        "0.5",
        "--wpb",
        "--enone",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "/work/hmmbuild/profile.hmm",
        "MADE1.sto",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmbuild" / "profile.hmm"]


def test_hmmer_hmmconvert_renders_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmconvert")
    info = _registry().object_info()["hmmer_hmmconvert"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["converted_profile"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["format"][1]["options"] == ["-a", "-2"]
    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "format": "-2",
            "output": "/work/hmmconvert",
        }
    ) == [
        "hmmconvert",
        "-2",
        "globins4.hmm",
        ">",
        "/work/hmmconvert/converted.hmm2",
    ]
    assert node_class.render_command(
        {
            "hmmfile": "legacy.hmm2",
            "format": "-a",
            "output": "/work/hmmconvert",
        }
    ) == [
        "hmmconvert",
        "-a",
        "legacy.hmm2",
        ">",
        "/work/hmmconvert/converted.hmm3",
    ]
    assert node_class.PLAN_OUTPUTS({"format": "-2"}, tmp_path) == [tmp_path / "hmmer_hmmconvert" / "converted.hmm2"]
    assert node_class.PLAN_OUTPUTS({"format": "-a"}, tmp_path) == [tmp_path / "hmmer_hmmconvert" / "converted.hmm3"]


def test_hmmer_hmmemit_renders_sampling_command_and_dynamic_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmemit")
    info = _registry().object_info()["hmmer_hmmemit"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["emitted_sequences"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["output_mode"][1]["options"] == ["fasta", "aln", "mrcs", "mrcsf", "sample"]
    assert info["input"]["optional"]["length"][1]["displayOptions"] == {
        "show": {"output_mode": ["sample"]},
    }
    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "output_mode": "fasta",
            "n_fasta": 3,
            "seed": 4,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "3",
        "--seed",
        "4",
        "globins4.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "output_mode": "aln",
            "n_alignment": 10,
            "seed": 4,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "10",
        "-a",
        "--seed",
        "4",
        "globins4.hmm",
        ">",
        "/work/hmmemit/emitted.sto",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "output_mode": "mrcsf",
            "minl": 0.75,
            "minu": 0.35,
            "seed": 42,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "--minl",
        "0.75",
        "--minu",
        "0.35",
        "-C",
        "--seed",
        "42",
        "profile.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "output_mode": "sample",
            "n_sample": 2,
            "length": 600,
            "emission_profile": "--uniglocal",
            "seed": 7,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "2",
        "-p",
        "-L",
        "600",
        "--uniglocal",
        "--seed",
        "7",
        "profile.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]
    assert node_class.PLAN_OUTPUTS({"output_mode": "aln"}, tmp_path) == [tmp_path / "hmmer_hmmemit" / "emitted.sto"]
    assert node_class.PLAN_OUTPUTS({"output_mode": "mrcs"}, tmp_path) == [tmp_path / "hmmer_hmmemit" / "emitted.fasta"]


def test_hmmer_hmmfetch_renders_model_selection_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmfetch")
    info = _registry().object_info()["hmmer_hmmfetch"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["selected_hmm_models"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["hmmfile"][0] == "FILE"
    assert info["input"]["required"]["keyfile"][0] == "FILE"
    assert node_class.render_command(
        {
            "hmmfile": "pfam-a.hmm",
            "keyfile": "models.txt",
            "output": "/work/hmmfetch",
        }
    ) == [
        "hmmfetch",
        "-f",
        "pfam-a.hmm",
        "models.txt",
        ">",
        "/work/hmmfetch/selected.hmm",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmfetch" / "selected.hmm"]


def test_hmmer_jackhmmer_renders_iterative_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_jackhmmer")
    info = _registry().object_info()["hmmer_jackhmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TSV"]
    assert info["output_name"] == ["output", "tblout", "domtblout"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["required"]["seqdb"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "domtblout"]
    assert info["input"]["optional"]["output_formats"][1]["list"] is True
    assert info["input"]["optional"]["popen"][1]["displayOptions"] == {
        "show": {"single_sequence_scoring": ["singlemx"]},
    }
    assert info["input"]["optional"]["incT"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert node_class.render_command(
        {
            "seqfile": "query.fa",
            "seqdb": "uniprot.fa",
            "iterations": 3,
            "output_formats": ["tblout", "domtblout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "threshold_mode": "score",
            "score_threshold": 25,
            "incT": 30,
            "max": True,
            "F1": 0.01,
            "F2": 0.002,
            "F3": 1e-6,
            "nobias": True,
            "relative_weighting": "--wblosum",
            "wid": 0.65,
            "effective_weighting": "eent",
            "eset": 2.0,
            "ere": 0.59,
            "esigma": 45,
            "prior": "--pnone",
            "eml": 220,
            "emn": 210,
            "evl": 230,
            "evn": 220,
            "efl": 120,
            "efn": 210,
            "eft": 0.05,
            "nonull2": True,
            "z": 1000,
            "domz": 50,
            "threads": 6,
            "seed": 4,
            "output": "/work/jackhmmer",
        }
    ) == [
        "jackhmmer",
        "-N",
        "3",
        "--tblout",
        "/work/jackhmmer/results.tblout",
        "--domtblout",
        "/work/jackhmmer/domains.domtblout",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "-T",
        "25",
        "--incT",
        "30",
        "--max",
        "--F1",
        "0.01",
        "--F2",
        "0.002",
        "--F3",
        "1e-06",
        "--nobias",
        "--wblosum",
        "--wid",
        "0.65",
        "--eent",
        "--eset",
        "2.0",
        "--ere",
        "0.59",
        "--esigma",
        "45",
        "--pnone",
        "--EmL",
        "220",
        "--EmN",
        "210",
        "--EvL",
        "230",
        "--EvN",
        "220",
        "--EfL",
        "120",
        "--EfN",
        "210",
        "--Eft",
        "0.05",
        "--nonull2",
        "-Z",
        "1000",
        "--domZ",
        "50",
        "--cpu",
        "5",
        "--seed",
        "4",
        "query.fa",
        "uniprot.fa",
        ">",
        "/work/jackhmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "seqfile": "query.fa",
            "seqdb": "uniprot.fa",
            "output_formats": [],
            "threshold_mode": "evalue",
            "evalue": 10,
            "threads": 1,
            "seed": 42,
            "output": "/work/jackhmmer",
        }
    ) == [
        "jackhmmer",
        "-N",
        "5",
        "-E",
        "10",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--wpb",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "query.fa",
        "uniprot.fa",
        ">",
        "/work/jackhmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_jackhmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_jackhmmer" / "results.tblout",
        "domtblout": tmp_path / "hmmer_jackhmmer" / "domains.domtblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": []}, tmp_path) == {
        "output": tmp_path / "hmmer_jackhmmer" / "output.txt",
    }


def test_hmmer_phmmer_renders_protein_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_phmmer")
    info = _registry().object_info()["hmmer_phmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TSV", "TSV"]
    assert info["output_name"] == ["output", "tblout", "domtblout", "pfamtblout"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["required"]["seqdb"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "domtblout", "pfamtblout"]
    assert info["input"]["optional"]["domT"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert "relative_weighting" not in info["input"]["optional"]
    assert "effective_weighting" not in info["input"]["optional"]
    assert "prior" not in info["input"]["optional"]
    assert node_class.render_command(
        {
            "seqfile": "globins.fa",
            "seqdb": "uniprot.fa",
            "output_formats": ["tblout", "domtblout", "pfamtblout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.04,
            "pextend": 0.45,
            "threshold_mode": "score",
            "score_threshold": 35,
            "incT": 40,
            "domT": 20,
            "incdomT": 25,
            "max": True,
            "F1": 0.03,
            "F2": 0.004,
            "F3": 2e-6,
            "nobias": True,
            "eml": 240,
            "emn": 230,
            "evl": 250,
            "evn": 240,
            "efl": 130,
            "efn": 220,
            "eft": 0.06,
            "nonull2": True,
            "z": 2000,
            "domz": 75,
            "threads": 8,
            "seed": 4,
            "output": "/work/phmmer",
        }
    ) == [
        "phmmer",
        "--tblout",
        "/work/phmmer/results.tblout",
        "--domtblout",
        "/work/phmmer/domains.domtblout",
        "--pfamtblout",
        "/work/phmmer/pfam.tblout",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.04",
        "--pextend",
        "0.45",
        "-T",
        "35",
        "--incT",
        "40",
        "--domT",
        "20",
        "--incdomT",
        "25",
        "--max",
        "--F1",
        "0.03",
        "--F2",
        "0.004",
        "--F3",
        "2e-06",
        "--nobias",
        "--EmL",
        "240",
        "--EmN",
        "230",
        "--EvL",
        "250",
        "--EvN",
        "240",
        "--EfL",
        "130",
        "--EfN",
        "220",
        "--Eft",
        "0.06",
        "--nonull2",
        "-Z",
        "2000",
        "--domZ",
        "75",
        "--cpu",
        "7",
        "--seed",
        "4",
        "globins.fa",
        "uniprot.fa",
        ">",
        "/work/phmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "seqfile": "globins.fa",
            "seqdb": "uniprot.fa",
            "output_formats": [],
            "threshold_mode": "evalue",
            "evalue": 10,
            "domE": 10,
            "threads": 1,
            "seed": 42,
            "output": "/work/phmmer",
        }
    ) == [
        "phmmer",
        "-E",
        "10",
        "--domE",
        "10",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "globins.fa",
        "uniprot.fa",
        ">",
        "/work/phmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_phmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_phmmer" / "results.tblout",
        "domtblout": tmp_path / "hmmer_phmmer" / "domains.domtblout",
        "pfamtblout": tmp_path / "hmmer_phmmer" / "pfam.tblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": ["tblout"]}, tmp_path) == {
        "output": tmp_path / "hmmer_phmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_phmmer" / "results.tblout",
    }


def test_hmmer_nhmmer_renders_nucleotide_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_nhmmer")
    info = _registry().object_info()["hmmer_nhmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TEXT", "TEXT"]
    assert info["output_name"] == ["output", "tblout", "dfamtblout", "aliscoresout"]
    assert "10.1093/bioinformatics/btt403" in info["citation_dois"]
    assert info["input"]["required"]["hmmfile"][0] == "FILE"
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "dfamtblout"]
    assert info["input"]["optional"]["output_formats"][1]["options"] == ["tblout", "dfamtblout", "aliscoresout"]
    assert info["input"]["optional"]["input_format_select"][1]["options"] == ["--dna", "--rna"]
    assert info["input"]["optional"]["cut_mode"][1]["options"] == ["none", "--cut_ga", "--cut_nc", "--cut_tc"]
    assert info["input"]["optional"]["score_threshold"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert node_class.render_command(
        {
            "hmmfile": "MADE1.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": ["tblout", "dfamtblout", "aliscoresout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "threshold_mode": "score",
            "score_threshold": 27,
            "incT": 31,
            "max": True,
            "F1": 0.04,
            "F2": 0.005,
            "F3": 3e-6,
            "nobias": True,
            "input_format_select": "--rna",
            "nonull2": True,
            "z": 1500,
            "domz": 60,
            "w_beta": 1e-7,
            "w_length": 120,
            "threads": 8,
            "seed": 4,
            "output": "/work/nhmmer",
        }
    ) == [
        "nhmmer",
        "--tblout",
        "/work/nhmmer/results.tblout",
        "--dfamtblout",
        "/work/nhmmer/dfam.tblout",
        "--aliscoresout",
        "/work/nhmmer/alignment_scores.txt",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "-T",
        "27",
        "--incT",
        "31",
        "--max",
        "--F1",
        "0.04",
        "--F2",
        "0.005",
        "--F3",
        "3e-06",
        "--nobias",
        "--rna",
        "--nonull2",
        "-Z",
        "1500",
        "--domZ",
        "60",
        "--w_beta",
        "1e-07",
        "--w_length",
        "120",
        "--cpu",
        "7",
        "--seed",
        "4",
        "MADE1.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "hmmfile": "MADE1.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": [],
            "threshold_mode": "cut",
            "cut_mode": "--cut_ga",
            "input_format_select": "--dna",
            "threads": 1,
            "seed": 42,
            "output": "/work/nhmmer",
        }
    ) == [
        "nhmmer",
        "--cut_ga",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--dna",
        "--cpu",
        "1",
        "--seed",
        "42",
        "MADE1.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_nhmmer" / "results.tblout",
        "dfamtblout": tmp_path / "hmmer_nhmmer" / "dfam.tblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": ["aliscoresout"]}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmer" / "output.txt",
        "aliscoresout": tmp_path / "hmmer_nhmmer" / "alignment_scores.txt",
    }


def test_hmmer_nhmmscan_renders_database_scan_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_nhmmscan")
    info = _registry().object_info()["hmmer_nhmmscan"]

    assert info["output"] == ["STATS_FILE", "TSV", "TEXT", "TEXT"]
    assert info["output_name"] == ["output", "tblout", "dfamtblout", "aliscoresout"]
    assert "10.1093/bioinformatics/btt403" in info["citation_dois"]
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["required"]["hmm_source"][1]["options"] == ["history", "indexed"]
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "dfamtblout"]
    assert info["input"]["optional"]["B1"][1]["default"] == 110
    assert info["input"]["optional"]["B2"][1]["default"] == 240
    assert info["input"]["optional"]["B3"][1]["default"] == 1000
    assert info["input"]["optional"]["cut_mode"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["cut"]},
    }
    assert node_class.render_command(
        {
            "hmm_source": "history",
            "hmmfile": "MADE1.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": ["tblout", "dfamtblout", "aliscoresout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "threshold_mode": "score",
            "score_threshold": 23,
            "incT": 29,
            "max": True,
            "F1": 0.04,
            "F2": 0.005,
            "F3": 3e-6,
            "nobias": True,
            "B1": 120,
            "B2": 260,
            "B3": 1100,
            "nonull2": True,
            "z": 1500,
            "domz": 60,
            "w_beta": 1e-7,
            "w_length": 120,
            "threads": 8,
            "seed": 4,
            "output": "/work/nhmmscan",
        }
    ) == [
        "hmmpress",
        "MADE1.hmm",
        "&&",
        "nhmmscan",
        "--tblout",
        "/work/nhmmscan/results.tblout",
        "--dfamtblout",
        "/work/nhmmscan/dfam.tblout",
        "--aliscoresout",
        "/work/nhmmscan/alignment_scores.txt",
        "--acc",
        "--noali",
        "--notextw",
        "-T",
        "23",
        "--incT",
        "29",
        "--max",
        "--F1",
        "0.04",
        "--F2",
        "0.005",
        "--F3",
        "3e-06",
        "--nobias",
        "--B1",
        "120",
        "--B2",
        "260",
        "--B3",
        "1100",
        "--nonull2",
        "-Z",
        "1500",
        "--domZ",
        "60",
        "--w_beta",
        "1e-07",
        "--w_length",
        "120",
        "--cpu",
        "7",
        "--seed",
        "4",
        "MADE1.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmscan/output.txt",
    ]
    assert node_class.render_command(
        {
            "hmm_source": "indexed",
            "hmmdb": "/indexes/dfam.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": [],
            "threshold_mode": "cut",
            "cut_mode": "--cut_ga",
            "threads": 1,
            "seed": 42,
            "output": "/work/nhmmscan",
        }
    ) == [
        "nhmmscan",
        "--cut_ga",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--B1",
        "110",
        "--B2",
        "240",
        "--B3",
        "1000",
        "--cpu",
        "1",
        "--seed",
        "42",
        "/indexes/dfam.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmscan/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmscan" / "output.txt",
        "tblout": tmp_path / "hmmer_nhmmscan" / "results.tblout",
        "dfamtblout": tmp_path / "hmmer_nhmmscan" / "dfam.tblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": ["aliscoresout"]}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmscan" / "output.txt",
        "aliscoresout": tmp_path / "hmmer_nhmmscan" / "alignment_scores.txt",
    }


def test_hmmer_nodes_render_table_outputs() -> None:
    hmmsearch_class = _node_class("hmmer_hmmsearch")
    hmmscan_class = _node_class("hmmer_hmmscan")

    assert hmmsearch_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "seqdb": "proteins.fasta",
            "evalue": 1e-3,
            "incE": 1e-5,
            "cut_ga": True,
            "notextw": True,
            "threads": 4,
            "output": "/work/hmmsearch",
        }
    ) == [
        "hmmsearch",
        "--cpu",
        "4",
        "-E",
        "0.001",
        "--incE",
        "1e-05",
        "--cut_ga",
        "--notextw",
        "--tblout",
        "/work/hmmsearch/results.tblout",
        "--domtblout",
        "/work/hmmsearch/domains.domtblout",
        "--pfamtblout",
        "/work/hmmsearch/pfam.tblout",
        "-o",
        "/work/hmmsearch/output.txt",
        "profile.hmm",
        "proteins.fasta",
    ]

    assert hmmscan_class.render_command(
        {
            "seqfile": "proteins.fasta",
            "hmmdb": "pfam.hmm",
            "domE": 0.01,
            "incdomE": 0.001,
            "cut_tc": True,
            "threads": 2,
            "output": "/work/hmmscan",
        }
    ) == [
        "hmmscan",
        "--cpu",
        "2",
        "--domE",
        "0.01",
        "--incdomE",
        "0.001",
        "--cut_tc",
        "--tblout",
        "/work/hmmscan/results.tblout",
        "--domtblout",
        "/work/hmmscan/domains.domtblout",
        "--pfamtblout",
        "/work/hmmscan/pfam.tblout",
        "-o",
        "/work/hmmscan/output.txt",
        "pfam.hmm",
        "proteins.fasta",
    ]


def test_hmmer_nodes_skip_blank_advanced_thresholds_from_default_params() -> None:
    node_class = _node_class("hmmer_hmmsearch")

    cmd = node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "seqdb": "proteins.fasta",
            "evalue": 10,
            "incE": "",
            "domE": "",
            "incdomE": "",
            "threads": 1,
            "output": "/work/hmmsearch",
        }
    )

    assert "--incE" not in cmd
    assert "--domE" not in cmd
    assert "--incdomE" not in cmd


def test_mmseqs2_easy_search_renders_sensitive_search_command() -> None:
    node_class = _node_class("mmseqs2_easy_search")

    assert node_class.render_command(
        {
            "query_fasta": "query.fasta",
            "target_fasta": "target.fasta",
            "search_type": 0,
            "sensitivity": 7.5,
            "evalue": 1e-5,
            "min_seq_id": 0.4,
            "cov": 0.6,
            "cov_mode": 2,
            "format_output": "query,target,pident,evalue,qaln,taln",
            "num_iterations": 2,
            "threads": 8,
            "output": "/work/mmseqs",
        }
    ) == [
        "mmseqs",
        "easy-search",
        "query.fasta",
        "target.fasta",
        "/work/mmseqs/search_results",
        "/work/mmseqs/tmp",
        "--search-type",
        "0",
        "-s",
        "7.5",
        "-e",
        "1e-05",
        "--min-seq-id",
        "0.4",
        "-c",
        "0.6",
        "--cov-mode",
        "2",
        "--format-output",
        "query,target,pident,evalue,qaln,taln",
        "--num-iterations",
        "2",
        "--threads",
        "8",
    ]


def test_mmseqs2_easy_cluster_renders_cascaded_cluster_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_easy_cluster")
    info = _registry().object_info()["mmseqs2_easy_cluster"]

    assert info["output"] == ["FASTA", "FASTA", "TSV"]
    assert info["output_name"] == ["representative_sequences", "clustered_sequences", "cluster_tsv"]
    assert "10.1038/nbt.3988" in info["citation_dois"]
    assert info["input"]["required"]["input_fasta"][0] == "FASTA"
    assert info["input"]["optional"]["dbtype"][1]["options"] == ["0", "1", "2"]
    assert info["input"]["optional"]["min_seq_id"][1]["default"] == 0.3
    assert info["input"]["optional"]["cov"][1]["default"] == 0.8
    assert info["input"]["optional"]["output_selection"][1]["default"] == [
        "file_rep_seq",
        "file_all_seq",
        "file_cluster_tsv",
    ]

    assert node_class.render_command(
        {
            "input_fasta": "proteins.fasta.gz",
            "dbtype": "1",
            "comp_bias_corr_scale": 0.7,
            "add_self_matches": 1,
            "kmer_length": 6,
            "mask": 0,
            "mask_prob": 0.75,
            "mask_lower_case": 1,
            "mask_n_repeat": 3,
            "spaced_kmer_mode": 0,
            "sensitivity": 7.5,
            "max_seqs": 500,
            "split": 2,
            "split_mode": 1,
            "diag_score": 0,
            "exact_kmer_matching": 1,
            "min_ungapped_score": 20,
            "convertalis": 1,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "min_aln_len": 40,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "score_bias": 0.4,
            "realign": 1,
            "realign_score_bias": -0.1,
            "realign_max_seqs": 5000,
            "corr_score_weight": 0.2,
            "alignment_mode": 3,
            "evalue": 1e-6,
            "min_seq_id": 0.55,
            "cov": 0.9,
            "cov_mode": 2,
            "max_rejected": 200,
            "max_accept": 150,
            "cluster_mode": 2,
            "max_iterations": 100,
            "similarity_type": 1,
            "rescore_mode": 2,
            "shuffle": 0,
            "id_offset": 10,
            "threads": 12,
            "max_seq_len": 50000,
            "filter_hits": 1,
            "sort_results": 1,
            "output": "/work/mmseqs_cluster",
        }
    ) == (
        "ln -sf proteins.fasta.gz input.fasta.gz && "
        "mmseqs easy-cluster input.fasta.gz /work/mmseqs_cluster/result /work/mmseqs_cluster/tmp "
        "--comp-bias-corr-scale 0.7 --dbtype 1 --add-self-matches 1 -k 6 --mask 0 "
        "--mask-prob 0.75 --mask-lower-case 1 --mask-n-repeat 3 --spaced-kmer-mode 0 "
        "-s 7.5 --max-seqs 500 --split 2 --split-mode 1 --diag-score 0 "
        "--exact-kmer-matching 1 --min-ungapped-score 20 -a 1 --alignment-output-mode 3 "
        "--wrapped-scoring 1 --min-aln-len 40 --seq-id-mode 1 --alt-ali 2 --score-bias 0.4 "
        "--realign 1 --realign-score-bias -0.1 --realign-max-seqs 5000 --corr-score-weight 0.2 "
        "--alignment-mode 3 -e 1e-06 --min-seq-id 0.55 -c 0.9 --cov-mode 2 --max-rejected 200 "
        "--max-accept 150 --cluster-mode 2 --max-iterations 100 --similarity-type 1 "
        "--rescore-mode 2 --shuffle 0 --id-offset 10 --threads 12 --max-seq-len 50000 "
        "--filter-hits 1 --sort-results 1"
    )
    assert node_class.render_command(
        {
            "input_fasta": "contigs.fa",
            "dbtype": "2",
            "zdrop": 80,
            "threads": 1,
            "output": "/work/mmseqs_cluster",
        }
    ).startswith(
        "ln -sf contigs.fa input.fa && "
        "mmseqs easy-cluster input.fa /work/mmseqs_cluster/result /work/mmseqs_cluster/tmp "
        "--zdrop 80 --dbtype 2"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_easy_cluster" / "result_rep_seq.fasta",
        tmp_path / "mmseqs2_easy_cluster" / "result_all_seqs.fasta",
        tmp_path / "mmseqs2_easy_cluster" / "result_cluster.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"output_selection": ["file_rep_seq", "file_cluster_tsv"]}, tmp_path) == [
        tmp_path / "mmseqs2_easy_cluster" / "result_rep_seq.fasta",
        tmp_path / "mmseqs2_easy_cluster" / "result_cluster.tsv",
    ]


def test_mmseqs2_easy_linclust_renders_linear_cluster_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_easy_linclust_clustering")
    info = _registry().object_info()["mmseqs2_easy_linclust_clustering"]

    assert info["output"] == ["FASTA", "FASTA", "TSV"]
    assert info["output_name"] == ["representative_sequences", "clustered_sequences", "cluster_tsv"]
    assert "10.1038/s41467-018-04964-5" in info["citation_dois"]
    assert info["input"]["required"]["input_fasta"][0] == "FASTA"
    assert info["input"]["optional"]["dbtype"][1]["options"] == ["0", "1", "2"]
    assert info["input"]["optional"]["min_seq_id"][1]["default"] == 0
    assert info["input"]["optional"]["cov"][1]["default"] == 0.8
    assert info["input"]["optional"]["spaced_kmer_mode"][1]["default"] == "0"
    assert info["input"]["optional"]["kmer_per_seq"][1]["default"] == 21
    assert info["input"]["optional"]["output_selection"][1]["default"] == [
        "file_rep_seq",
        "file_all_seq",
        "file_cluster_tsv",
    ]

    assert node_class.render_command(
        {
            "input_fasta": "proteins.fasta",
            "dbtype": "1",
            "comp_bias_corr_scale": 0.6,
            "kmer_per_seq_scale": 0.15,
            "add_self_matches": 1,
            "kmer_length": 7,
            "mask": 0,
            "mask_prob": 0.7,
            "mask_lower_case": 1,
            "mask_n_repeat": 2,
            "spaced_kmer_mode": 1,
            "convertalis": 1,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "min_aln_len": 35,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "score_bias": 0.3,
            "realign": 1,
            "realign_score_bias": -0.05,
            "realign_max_seqs": 3000,
            "corr_score_weight": 0.25,
            "alignment_mode": 2,
            "evalue": 1e-5,
            "min_seq_id": 0.5,
            "cov": 0.85,
            "cov_mode": 1,
            "max_rejected": 100,
            "max_accept": 80,
            "cluster_mode": 2,
            "max_iterations": 120,
            "similarity_type": 1,
            "cluster_weight_threshold": 0.95,
            "kmer_per_seq": 30,
            "hash_shift": 99,
            "include_only_extendable": 1,
            "ignore_multi_kmer": 1,
            "rescore_mode": 3,
            "shuffle": 0,
            "id_offset": 5,
            "threads": 16,
            "max_seq_len": 70000,
            "filter_hits": 1,
            "sort_results": 1,
            "output": "/work/mmseqs_linclust",
        }
    ) == (
        "ln -sf proteins.fasta input.fasta && "
        "mmseqs easy-linclust input.fasta /work/mmseqs_linclust/result /work/mmseqs_linclust/tmp "
        "--comp-bias-corr-scale 0.6 --kmer-per-seq-scale 0.15 --dbtype 1 --add-self-matches 1 "
        "-k 7 --mask 0 --mask-prob 0.7 --mask-lower-case 1 --mask-n-repeat 2 --spaced-kmer-mode 1 "
        "-a 1 --alignment-output-mode 3 --wrapped-scoring 1 --min-aln-len 35 --seq-id-mode 1 "
        "--alt-ali 2 --score-bias 0.3 --realign 1 --realign-score-bias -0.05 --realign-max-seqs 3000 "
        "--corr-score-weight 0.25 --alignment-mode 2 -e 1e-05 --min-seq-id 0.5 -c 0.85 --cov-mode 1 "
        "--max-rejected 100 --max-accept 80 --cluster-mode 2 --max-iterations 120 --similarity-type 1 "
        "--cluster-weight-threshold 0.95 --kmer-per-seq 30 --hash-shift 99 --include-only-extendable 1 "
        "--ignore-multi-kmer 1 --rescore-mode 3 --shuffle 0 --id-offset 5 --threads 16 --max-seq-len 70000 "
        "--filter-hits 1 --sort-results 1"
    )
    assert node_class.render_command(
        {
            "input_fasta": "reads.fasta.gz",
            "dbtype": "2",
            "zdrop": 90,
            "kmer_per_seq_scale": 0.2,
            "adjust_kmer_len": 1,
            "threads": 1,
            "output": "/work/mmseqs_linclust",
        }
    ).startswith(
        "ln -sf reads.fasta.gz input.fasta.gz && "
        "mmseqs easy-linclust input.fasta.gz /work/mmseqs_linclust/result /work/mmseqs_linclust/tmp "
        "--zdrop 90 --kmer-per-seq-scale 0.2 --adjust-kmer-len 1 --dbtype 2"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_easy_linclust_clustering" / "result_rep_seq.fasta",
        tmp_path / "mmseqs2_easy_linclust_clustering" / "result_all_seqs.fasta",
        tmp_path / "mmseqs2_easy_linclust_clustering" / "result_cluster.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"output_selection": ["file_all_seq"]}, tmp_path) == [
        tmp_path / "mmseqs2_easy_linclust_clustering" / "result_all_seqs.fasta",
    ]


def test_mmseqs2_easy_linsearch_renders_linear_search_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_easy_linsearch")
    info = _registry().object_info()["mmseqs2_easy_linsearch"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["search_results"]
    assert "10.1038/nbt.3988" in info["citation_dois"]
    assert info["input"]["required"]["query_fasta"][0] == "FASTA"
    assert info["input"]["required"]["target_source"][1]["options"] == ["history", "cached"]
    assert info["input"]["optional"]["format_mode"][1]["options"] == ["0", "4", "2", "1", "3"]
    assert info["input"]["optional"]["format_fields"][1]["default"] == [
        "query",
        "target",
        "pident",
        "evalue",
        "bits",
    ]
    assert info["input"]["optional"]["kmer_per_seq"][1]["default"] == 21

    assert node_class.render_command(
        {
            "query_fasta": "query.fastq.gz",
            "target_source": "history",
            "target_fasta": "target.fasta",
            "dbtype": "1",
            "comp_bias_corr_scale": 0.6,
            "kmer_per_seq_scale": 0.2,
            "add_self_matches": 1,
            "mask": 0,
            "mask_prob": 0.7,
            "mask_lower_case": 1,
            "mask_n_repeat": 4,
            "convertalis": 1,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "min_aln_len": 25,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "score_bias": 0.2,
            "realign": 1,
            "realign_score_bias": -0.05,
            "realign_max_seqs": 4000,
            "corr_score_weight": 0.3,
            "alignment_mode": 2,
            "evalue": 1e-4,
            "min_seq_id": 0.75,
            "cov": 0.8,
            "cov_mode": 1,
            "max_rejected": 120,
            "max_accept": 80,
            "kmer_per_seq": 40,
            "id_offset": 9,
            "format_mode": "4",
            "format_fields": ["query", "target", "pident", "evalue", "qcov"],
            "search_type": 3,
            "threads": 12,
            "max_seq_len": 50000,
            "output": "/work/mmseqs_linsearch",
        }
    ) == (
        "ln -sf query.fastq.gz query.fastq.gz && ln -sf target.fasta target.fasta && "
        "mmseqs easy-linsearch query.fastq.gz target.fasta /work/mmseqs_linsearch/search_results /work/mmseqs_linsearch/tmp "
        "--comp-bias-corr-scale 0.6 --kmer-per-seq-scale 0.2 --dbtype 1 --add-self-matches 1 "
        "--mask 0 --mask-prob 0.7 --mask-lower-case 1 --mask-n-repeat 4 -a 1 --alignment-output-mode 3 "
        "--wrapped-scoring 1 --min-aln-len 25 --seq-id-mode 1 --alt-ali 2 --score-bias 0.2 --realign 1 "
        "--realign-score-bias -0.05 --realign-max-seqs 4000 --corr-score-weight 0.3 --alignment-mode 2 "
        "-e 0.0001 --min-seq-id 0.75 -c 0.8 --cov-mode 1 --max-rejected 120 --max-accept 80 "
        "--kmer-per-seq 40 --id-offset 9 --format-output query,target,pident,evalue,qcov --format-mode 4 "
        "--search-type 3 --threads 12 --max-seq-len 50000"
    )
    assert node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "target_source": "cached",
            "target_database": "/indexes/mmseqs",
            "create_linindex": True,
            "dbtype": "2",
            "zdrop": 80,
            "kmer_per_seq_scale": 0.1,
            "adjust_kmer_len": 1,
            "format_mode": "1",
            "format_fields": [],
            "threads": 1,
            "output": "/work/mmseqs_linsearch",
        }
    ).startswith(
        "ln -sf reads.fa query.fa && cp -r /indexes/mmseqs/database* . && "
        "mmseqs createlinindex database /work/mmseqs_linsearch/tmp && "
        "mmseqs easy-linsearch query.fa database /work/mmseqs_linsearch/search_results /work/mmseqs_linsearch/tmp "
        "--zdrop 80 --kmer-per-seq-scale 0.1 --adjust-kmer-len 1 --dbtype 2"
    )
    assert "--format-output" not in node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "target_source": "cached",
            "target_database": "/indexes/mmseqs",
            "format_mode": "1",
            "format_fields": ["query", "target"],
            "output": "/work/mmseqs_linsearch",
        }
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_easy_linsearch" / "search_results.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"format_mode": "1"}, tmp_path) == [
        tmp_path / "mmseqs2_easy_linsearch" / "search_results.sam",
    ]
    assert node_class.PLAN_OUTPUTS({"format_mode": "3"}, tmp_path) == [
        tmp_path / "mmseqs2_easy_linsearch" / "search_results.html",
    ]


def test_mmseqs2_easy_rbh_renders_reciprocal_best_hit_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_easy_rbh")
    info = _registry().object_info()["mmseqs2_easy_rbh"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["search_results"]
    assert "10.1038/nbt.3988" in info["citation_dois"]
    assert info["input"]["required"]["query_fasta"][0] == "FASTA"
    assert info["input"]["required"]["target_source"][1]["options"] == ["history", "cached"]
    assert info["input"]["optional"]["spaced_kmer_mode"][1]["default"] == "1"
    assert info["input"]["optional"]["sensitivity"][1]["default"] == 5.7
    assert info["input"]["optional"]["chain_alignments"][1]["default"] == 0
    assert info["input"]["optional"]["merge_query"][1]["default"] == 1
    assert info["input"]["optional"]["strand"][1]["options"] == ["0", "1", "2"]
    assert info["input"]["optional"]["format_mode"][1]["options"] == ["0", "4", "2", "1", "3"]

    assert node_class.render_command(
        {
            "query_fasta": "query.fastq.gz",
            "target_source": "history",
            "target_fasta": "target.fasta",
            "dbtype": "1",
            "comp_bias_corr_scale": 0.7,
            "add_self_matches": 1,
            "kmer_length": 6,
            "mask": 0,
            "mask_prob": 0.7,
            "mask_lower_case": 1,
            "mask_n_repeat": 3,
            "spaced_kmer_mode": 0,
            "sensitivity": 7.5,
            "max_seqs": 500,
            "split": 2,
            "split_mode": 1,
            "diag_score": 0,
            "exact_kmer_matching": 1,
            "min_ungapped_score": 20,
            "convertalis": 1,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "min_aln_len": 25,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "score_bias": 0.2,
            "realign": 1,
            "realign_score_bias": -0.05,
            "realign_max_seqs": 4000,
            "corr_score_weight": 0.3,
            "alignment_mode": 2,
            "evalue": 1e-4,
            "min_seq_id": 0.8,
            "cov": 0.8,
            "cov_mode": 1,
            "max_rejected": 120,
            "max_accept": 80,
            "format_mode": "4",
            "format_fields": ["query", "target", "pident", "evalue", "qcov", "tcov"],
            "search_type": 2,
            "threads": 12,
            "max_seq_len": 50000,
            "filter_hits": 1,
            "sort_results": 1,
            "chain_alignments": 1,
            "merge_query": 0,
            "strand": 2,
            "output": "/work/mmseqs_rbh",
        }
    ) == (
        "ln -s query.fastq.gz query.fastq.gz && ln -s target.fasta target.fasta && "
        "mmseqs easy-rbh query.fastq.gz target.fasta /work/mmseqs_rbh/search_results /work/mmseqs_rbh/tmp "
        "--comp-bias-corr-scale 0.7 --dbtype 1 --add-self-matches 1 -k 6 --mask 0 "
        "--mask-prob 0.7 --mask-lower-case 1 --mask-n-repeat 3 --spaced-kmer-mode 0 "
        "-s 7.5 --max-seqs 500 --split 2 --split-mode 1 --diag-score 0 --exact-kmer-matching 1 "
        "--min-ungapped-score 20 -a 1 --alignment-output-mode 3 --wrapped-scoring 1 --min-aln-len 25 "
        "--seq-id-mode 1 --alt-ali 2 --score-bias 0.2 --realign 1 --realign-score-bias -0.05 "
        "--realign-max-seqs 4000 --corr-score-weight 0.3 --alignment-mode 2 -e 0.0001 --min-seq-id 0.8 "
        "-c 0.8 --cov-mode 1 --max-rejected 120 --max-accept 80 "
        "--format-output query,target,pident,evalue,qcov,tcov --format-mode 4 --search-type 2 "
        "--threads 12 --max-seq-len 50000 --filter-hits 1 --sort-results 1 --chain-alignments 1 "
        "--merge-query 0 --strand 2"
    )
    assert node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "target_source": "cached",
            "target_database": "/indexes/mmseqs",
            "dbtype": "2",
            "zdrop": 80,
            "format_mode": "1",
            "format_fields": ["query", "target"],
            "threads": 1,
            "output": "/work/mmseqs_rbh",
        }
    ).startswith(
        "ln -s reads.fa query.fa && "
        "mmseqs easy-rbh query.fa /indexes/mmseqs/database /work/mmseqs_rbh/search_results /work/mmseqs_rbh/tmp "
        "--zdrop 80 --dbtype 2"
    )
    assert "--format-output" not in node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "target_source": "cached",
            "target_database": "/indexes/mmseqs",
            "format_mode": "1",
            "format_fields": ["query", "target"],
            "output": "/work/mmseqs_rbh",
        }
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_easy_rbh" / "search_results.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"format_mode": "1"}, tmp_path) == [
        tmp_path / "mmseqs2_easy_rbh" / "search_results.sam",
    ]
    assert node_class.PLAN_OUTPUTS({"format_mode": "3"}, tmp_path) == [
        tmp_path / "mmseqs2_easy_rbh" / "search_results.html",
    ]


def test_mmseqs2_easy_taxonomy_renders_taxonomic_assignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_easy_taxonomy")
    info = _registry().object_info()["mmseqs2_easy_taxonomy"]

    assert info["output"] == ["TSV", "TXT", "TSV", "TXT"]
    assert info["output_name"] == ["lca_results", "kraken_report", "top_hit_alignments", "top_hit_report"]
    assert "10.1093/bioinformatics/btab184" in info["citation_dois"]
    assert info["input"]["required"]["query_fasta"][0] == "FASTA"
    assert info["input"]["required"]["database_type"][1]["options"] == ["amino_acid_tax", "nucleotides_tax"]
    assert info["input"]["required"]["target_database"][0] == "FILE"
    assert info["input"]["optional"]["search_type"][1]["options"] == ["0", "1", "2", "3", "4"]
    assert info["input"]["optional"]["evalue"][1]["default"] == 1
    assert info["input"]["optional"]["max_rejected"][1]["default"] == 5
    assert info["input"]["optional"]["max_accept"][1]["default"] == 30
    assert info["input"]["optional"]["mask_profile"][1]["default"] == 1
    assert info["input"]["optional"]["lca_mode"][1]["default"] == "3"
    assert info["input"]["optional"]["output_selection"][1]["default"] == ["report"]

    assert node_class.render_command(
        {
            "query_fasta": "mystery.fastq.gz",
            "database_type": "amino_acid_tax",
            "target_database": "/indexes/uniprot",
            "download_tax_db": True,
            "dbtype": "1",
            "comp_bias_corr_scale": 0.7,
            "add_self_matches": 1,
            "kmer_length": 6,
            "mask": 0,
            "mask_prob": 0.7,
            "mask_lower_case": 1,
            "mask_n_repeat": 3,
            "spaced_kmer_mode": 0,
            "sensitivity": 7.5,
            "max_seqs": 500,
            "split": 2,
            "split_mode": 1,
            "diag_score": 0,
            "exact_kmer_matching": 1,
            "min_ungapped_score": 20,
            "convertalis": 1,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "min_aln_len": 25,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "score_bias": 0.2,
            "realign": 1,
            "realign_score_bias": -0.05,
            "realign_max_seqs": 4000,
            "corr_score_weight": 0.3,
            "alignment_mode": 2,
            "evalue": 1e-4,
            "min_seq_id": 0.8,
            "cov": 0.8,
            "cov_mode": 1,
            "max_rejected": 12,
            "max_accept": 8,
            "mask_profile": 0,
            "e_profile": 0.002,
            "wg": 1,
            "filter_msa": 0,
            "filter_min_enable": 10,
            "max_seq_id": 0.85,
            "qid": "0.15,0.30",
            "qsc": -10,
            "profile_cov": 0.2,
            "diff": 500,
            "pseudo_cnt_mode": 1,
            "exhaustive_search": 1,
            "lca_search": 1,
            "orf_filter_e": 50,
            "orf_filter_s": 3,
            "lca_mode": "1",
            "majority": 0.7,
            "vote_mode": "2",
            "tax_lineage": "1",
            "blacklist": "12908,28384",
            "taxon_list": "2,2157",
            "search_type": 2,
            "threads": 12,
            "max_seq_len": 50000,
            "filter_hits": 1,
            "sort_results": 1,
            "chain_alignments": 1,
            "merge_query": 0,
            "output": "/work/mmseqs_taxonomy",
        }
    ) == (
        "ln -s mystery.fastq.gz query.fastq.gz && cp -r /indexes/uniprot/database* . && "
        "mmseqs createtaxdb database /work/mmseqs_taxonomy/tmp && "
        "mmseqs easy-taxonomy query.fastq.gz database /work/mmseqs_taxonomy/result /work/mmseqs_taxonomy/tmp "
        "--comp-bias-corr-scale 0.7 --dbtype 1 --add-self-matches 1 -k 6 --mask 0 "
        "--mask-prob 0.7 --mask-lower-case 1 --mask-n-repeat 3 --spaced-kmer-mode 0 "
        "-s 7.5 --max-seqs 500 --split 2 --split-mode 1 --diag-score 0 --exact-kmer-matching 1 "
        "--min-ungapped-score 20 -a 1 --alignment-output-mode 3 --wrapped-scoring 1 --min-aln-len 25 "
        "--seq-id-mode 1 --alt-ali 2 --score-bias 0.2 --realign 1 --realign-score-bias -0.05 "
        "--realign-max-seqs 4000 --corr-score-weight 0.3 --alignment-mode 2 -e 0.0001 --min-seq-id 0.8 "
        "-c 0.8 --cov-mode 1 --max-rejected 12 --max-accept 8 --mask-profile 0 --e-profile 0.002 "
        "--wg 1 --filter-msa 0 --filter-min-enable 10 --max-seq-id 0.85 --qid 0.15,0.30 "
        "--qsc -10 --cov 0.2 --diff 500 --pseudo-cnt-mode 1 --exhaustive-search 1 --lca-search 1 "
        "--orf-filter-e 50 --orf-filter-s 3 --lca-mode 1 --majority 0.7 --vote-mode 2 --tax-lineage 1 "
        "--blacklist 12908,28384 --taxon-list 2,2157 --search-type 2 --threads 12 --max-seq-len 50000 "
        "--filter-hits 1 --sort-results 1 --chain-alignments 1 --merge-query 0"
    )
    assert node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "database_type": "nucleotides_tax",
            "target_database": "/indexes/nt_tax",
            "dbtype": "2",
            "zdrop": 80,
            "search_type": 3,
            "output": "/work/mmseqs_taxonomy",
        }
    ).startswith(
        "ln -s reads.fa query.fa && "
        "mmseqs easy-taxonomy query.fa /indexes/nt_tax/database /work/mmseqs_taxonomy/result /work/mmseqs_taxonomy/tmp "
        "--zdrop 80 --dbtype 2"
    )
    command_without_tax_filters = node_class.render_command(
        {
            "query_fasta": "reads.fa",
            "target_database": "/indexes/nt_tax",
            "blacklist": "",
            "taxon_list": "",
            "output": "/work/mmseqs_taxonomy",
        }
    )
    assert "--blacklist" not in command_without_tax_filters
    assert "--taxon-list" not in command_without_tax_filters
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_easy_taxonomy" / "result_lca.tsv",
        tmp_path / "mmseqs2_easy_taxonomy" / "result_report.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"output_selection": ["report", "tophit_aln", "tophit_report"]}, tmp_path) == [
        tmp_path / "mmseqs2_easy_taxonomy" / "result_lca.tsv",
        tmp_path / "mmseqs2_easy_taxonomy" / "result_report.txt",
        tmp_path / "mmseqs2_easy_taxonomy" / "result_tophit_aln.tsv",
        tmp_path / "mmseqs2_easy_taxonomy" / "result_tophit_report.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"output_selection": []}, tmp_path) == [
        tmp_path / "mmseqs2_easy_taxonomy" / "result_lca.tsv",
    ]


def test_mmseqs2_taxonomy_assignment_renders_chained_taxonomy_pipeline_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mmseqs2_taxonomy_assignment")
    info = _registry().object_info()["mmseqs2_taxonomy_assignment"]

    assert info["output"] == ["TSV", "TXT", "HTML"]
    assert info["output_name"] == ["taxonomy_tsv", "kraken_report", "krona_report"]
    assert "10.1093/bioinformatics/btab184" in info["citation_dois"]
    assert info["input"]["required"]["input_fasta"][0] == "FASTA"
    assert info["input"]["required"]["database_type"][1]["options"] == ["amino_acid_tax", "nucleotides_tax"]
    assert info["input"]["required"]["target_database"][0] == "FILE"
    assert info["input"]["optional"]["sensitivity"][1]["default"] == 2
    assert info["input"]["optional"]["alignment_mode"][1]["default"] == "1"
    assert info["input"]["optional"]["evalue"][1]["default"] == 1
    assert info["input"]["optional"]["max_rejected"][1]["default"] == 5
    assert info["input"]["optional"]["max_accept"][1]["default"] == 30
    assert info["input"]["optional"]["keep_kraken_report"][1]["default"] is True
    assert info["input"]["optional"]["keep_krona_report"][1]["default"] is True
    assert info["input"]["optional"]["first_seq_as_repr"][1]["default"] == 0

    assert node_class.render_command(
        {
            "input_fasta": "mystery.fastq.gz",
            "database_type": "amino_acid_tax",
            "target_database": "/indexes/uniprot",
            "download_tax_db": True,
            "filter_taxon_list": "2,2157",
            "dbtype": "1",
            "comp_bias_corr_scale": 0.7,
            "shuffle": 0,
            "add_self_matches": 1,
            "sensitivity": 5.7,
            "kmer_length": 6,
            "target_search_mode": 1,
            "max_seqs": 500,
            "split": 2,
            "split_mode": 1,
            "diag_score": 0,
            "exact_kmer_matching": 1,
            "mask": 0,
            "mask_prob": 0.7,
            "mask_lower_case": 1,
            "mask_n_repeat": 3,
            "min_ungapped_score": 20,
            "spaced_kmer_mode": 0,
            "convertalis": 1,
            "alignment_mode": 2,
            "alignment_output_mode": 3,
            "wrapped_scoring": 1,
            "evalue": 1e-4,
            "min_seq_id": 0.8,
            "min_aln_len": 25,
            "seq_id_mode": 1,
            "alt_ali": 2,
            "cov": 0.8,
            "cov_mode": 1,
            "max_rejected": 12,
            "max_accept": 8,
            "score_bias": 0.2,
            "realign": 1,
            "realign_score_bias": -0.05,
            "realign_max_seqs": 4000,
            "corr_score_weight": 0.3,
            "exhaustive_search_filter": 1,
            "mask_profile": 0,
            "e_profile": 0.002,
            "wg": 1,
            "filter_msa": 0,
            "filter_min_enable": 10,
            "max_seq_id": 0.85,
            "qid": "0.15,0.30",
            "qsc": -10,
            "profile_cov": 0.2,
            "diff": 500,
            "pseudo_cnt_mode": 1,
            "exhaustive_search": 1,
            "lca_search": 1,
            "orf_filter_e": 50,
            "orf_filter_s": 3,
            "lca_mode": "1",
            "majority": 0.7,
            "vote_mode": "2",
            "tax_lineage": "1",
            "blacklist": "12908,28384",
            "taxon_list": "!9606",
            "rescore_mode": "2",
            "allow_deletion": 1,
            "min_length": 45,
            "max_length": 10000,
            "max_gaps": 5,
            "contig_start_mode": "1",
            "contig_end_mode": "0",
            "orf_start_mode": "2",
            "forward_frames": "1,3",
            "reverse_frames": "2",
            "translation_table": "11",
            "translate": 1,
            "use_all_table_starts": 1,
            "id_offset": 10,
            "sequence_overlap": 3,
            "sequence_split_mode": "0",
            "headers_split_mode": "1",
            "search_type": 2,
            "prefilter_mode": "1",
            "threads": 12,
            "max_seq_len": 50000,
            "filter_hits": 1,
            "sort_results": 1,
            "chain_alignments": 1,
            "merge_query": 0,
            "first_seq_as_repr": 1,
            "target_column": 2,
            "full_header": 1,
            "idx_seq_src": "2",
            "keep_kraken_report": True,
            "keep_krona_report": False,
            "output": "/work/mmseqs_taxonomy_assignment",
        }
    ) == (
        "ln -s -f mystery.fastq.gz input && "
        "mmseqs createdb input /work/mmseqs_taxonomy_assignment/sequenceDB --dbtype 1 --shuffle 0 && "
        "cp -r /indexes/uniprot/database* . && "
        "mmseqs createtaxdb database /work/mmseqs_taxonomy_assignment/tmp && "
        "mmseqs filtertaxseqdb database /work/mmseqs_taxonomy_assignment/database_filtered --taxon-list 2,2157 && "
        "mmseqs taxonomy /work/mmseqs_taxonomy_assignment/sequenceDB /work/mmseqs_taxonomy_assignment/database_filtered "
        "/work/mmseqs_taxonomy_assignment/output_taxonomy /work/mmseqs_taxonomy_assignment/tmp "
        "--comp-bias-corr-scale 0.7 --add-self-matches 1 -s 5.7 -k 6 --target-search-mode 1 "
        "--max-seqs 500 --split 2 --split-mode 1 --diag-score 0 --exact-kmer-matching 1 --mask 0 "
        "--mask-prob 0.7 --mask-lower-case 1 --mask-n-repeat 3 --min-ungapped-score 20 --spaced-kmer-mode 0 "
        "-a 1 --alignment-mode 2 --alignment-output-mode 3 --wrapped-scoring 1 -e 0.0001 --min-seq-id 0.8 "
        "--min-aln-len 25 --seq-id-mode 1 --alt-ali 2 -c 0.8 --cov-mode 1 --max-rejected 12 "
        "--max-accept 8 --score-bias 0.2 --realign 1 --realign-score-bias -0.05 --realign-max-seqs 4000 "
        "--corr-score-weight 0.3 --exhaustive-search-filter 1 --mask-profile 0 --e-profile 0.002 --wg 1 "
        "--filter-msa 0 --filter-min-enable 10 --max-seq-id 0.85 --qid 0.15,0.30 --qsc -10 --cov 0.2 "
        "--diff 500 --pseudo-cnt-mode 1 --exhaustive-search 1 --lca-search 1 --orf-filter-e 50 "
        "--orf-filter-s 3 --lca-mode 1 --majority 0.7 --vote-mode 2 --tax-lineage 1 --blacklist 12908,28384 "
        "--taxon-list '!9606' --rescore-mode 2 --allow-deletion 1 --min-length 45 --max-length 10000 "
        "--max-gaps 5 --contig-start-mode 1 --contig-end-mode 0 --orf-start-mode 2 --forward-frames 1,3 "
        "--reverse-frames 2 --translation-table 11 --translate 1 --use-all-table-starts 1 --id-offset 10 "
        "--sequence-overlap 3 --sequence-split-mode 0 --headers-split-mode 1 --search-type 2 --prefilter-mode 1 "
        "--threads 12 --max-seq-len 50000 --filter-hits 1 --sort-results 1 --chain-alignments 1 --merge-query 0 && "
        "mmseqs createtsv /work/mmseqs_taxonomy_assignment/sequenceDB /work/mmseqs_taxonomy_assignment/output_taxonomy "
        "/work/mmseqs_taxonomy_assignment/taxo_result.tsv --first-seq-as-repr 1 --target-column 2 --full-header 1 "
        "--idx-seq-src 2 --threads 12 && "
        "mmseqs taxonomyreport /work/mmseqs_taxonomy_assignment/database_filtered "
        "/work/mmseqs_taxonomy_assignment/output_taxonomy /work/mmseqs_taxonomy_assignment/taxo_result.txt "
        "--report-mode 0 --threads 12"
    )

    command_without_optional_reports = node_class.render_command(
        {
            "input_fasta": "reads.fa",
            "database_type": "nucleotides_tax",
            "target_database": "/indexes/nt_tax",
            "filter_taxon_list": "",
            "blacklist": "",
            "taxon_list": "",
            "dbtype": "2",
            "zdrop": 80,
            "search_type": 3,
            "keep_kraken_report": False,
            "keep_krona_report": False,
            "output": "/work/mmseqs_taxonomy_assignment",
        }
    )
    assert command_without_optional_reports.startswith(
        "ln -s -f reads.fa input && "
        "mmseqs createdb input /work/mmseqs_taxonomy_assignment/sequenceDB --dbtype 2 --shuffle 1 && "
        "mmseqs taxonomy /work/mmseqs_taxonomy_assignment/sequenceDB /indexes/nt_tax/database "
        "/work/mmseqs_taxonomy_assignment/output_taxonomy /work/mmseqs_taxonomy_assignment/tmp --zdrop 80 "
    )
    assert "createtaxdb" not in command_without_optional_reports
    assert "filtertaxseqdb" not in command_without_optional_reports
    assert "--blacklist" not in command_without_optional_reports
    assert "--taxon-list" not in command_without_optional_reports
    assert "taxonomyreport" not in command_without_optional_reports

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.tsv",
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.txt",
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.html",
    ]
    assert node_class.PLAN_OUTPUTS({"keep_krona_report": False}, tmp_path) == [
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.tsv",
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"keep_kraken_report": False, "keep_krona_report": False}, tmp_path) == [
        tmp_path / "mmseqs2_taxonomy_assignment" / "taxo_result.tsv",
    ]


def test_kaiju_renders_galaxy_aligned_taxonomy_and_best_sequence_modes(tmp_path: Path) -> None:
    node_class = _node_class("kaiju")
    info = _registry().object_info()["kaiju"]

    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["taxonomic_classification", "best_matching_sequences"]
    assert info["citation_dois"] == ["10.1038/ncomms11257"]
    assert info["citation_text"] == "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    assert info["input"]["required"]["input_type"][1]["options"] == ["single", "paired"]
    assert info["input"]["required"]["reads"][0] == "FASTQ"
    assert info["input"]["required"]["reference_database"][0] == "DIRECTORY"
    assert info["input"]["optional"]["task"][1]["options"] == ["tax", "best_sequence"]
    assert info["input"]["optional"]["mode"][1]["default"] == "greedy"
    assert info["input"]["optional"]["low_complexity"][1]["default"] is True

    assert node_class.render_command(
        {
            "input_type": "paired",
            "reads_1": "sample_R1.fastq.gz",
            "reads_2": "sample_R2.fastq.gz",
            "reference_database": "/db/kaiju/nr",
            "task": "tax",
            "protein": False,
            "low_complexity": True,
            "mode": "greedy",
            "mismatches": 5,
            "match_length": 13,
            "match_score": 75,
            "evalue": 0.001,
            "verbose": True,
            "threads": 12,
            "output": "/work/kaiju",
        }
    ) == [
        "kaiju",
        "-t",
        "/db/kaiju/nr/nodes.dmp",
        "-o",
        "/work/kaiju/kaiju_taxonomy.tsv",
        "-f",
        "/db/kaiju/nr/database.fmi",
        "-i",
        "sample_R1.fastq.gz",
        "-j",
        "sample_R2.fastq.gz",
        "-z",
        "12",
        "-x",
        "-a",
        "greedy",
        "-e",
        "5",
        "-m",
        "13",
        "-s",
        "75",
        "-E",
        "0.001",
        "-v",
    ]

    assert node_class.render_command(
        {
            "input_type": "single",
            "reads": "proteins.faa",
            "reference_database": "/db/kaiju/refseq",
            "task": "best_sequence",
            "protein": True,
            "low_complexity": False,
            "mode": "mem",
            "threads": 4,
            "output": "/work/kaiju",
        }
    ) == [
        "kaijup",
        "-o",
        "/work/kaiju/kaiju_best_sequences.tsv",
        "-f",
        "/db/kaiju/refseq/database.fmi",
        "-i",
        "proteins.faa",
        "-z",
        "4",
        "-p",
        "-X",
        "-a",
        "mem",
    ]

    assert node_class.render_command(
        {
            "input_type": "single",
            "reads": "reads.fastq",
            "reference_database": "/db/kaiju/refseq",
            "task": "best_sequence",
            "protein": False,
            "low_complexity": True,
            "output": "/work/kaiju",
        }
    )[0] == "kaijux"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kaiju" / "kaiju_taxonomy.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"task": "best_sequence"}, tmp_path) == [
        tmp_path / "kaiju" / "kaiju_best_sequences.tsv",
    ]


def test_kaiju_add_taxon_names_renders_annotation_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kaiju_add_taxon_names")
    info = _registry().object_info()["kaiju_add_taxon_names"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["taxon_names_table"]
    assert info["citation_dois"] == ["10.1038/ncomms11257"]
    assert info["citation_text"] == "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    assert info["input"]["required"]["kaiju_table"][0] == "TSV"
    assert info["input"]["required"]["reference_database"][0] == "DIRECTORY"
    assert info["input"]["optional"]["rank"][1]["options"] == [
        "",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "species",
    ]
    assert info["input"]["optional"]["print_full_taxon_path"][1]["default"] is False

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju.out",
            "reference_database": "/db/kaiju/nr",
            "exclude_unclassified": True,
            "rank": "family",
            "print_full_taxon_path": False,
            "output": "/work/kaiju_taxnames",
        }
    ) == [
        "kaiju-addTaxonNames",
        "-t",
        "/db/kaiju/nr/nodes.dmp",
        "-n",
        "/db/kaiju/nr/names.dmp",
        "-i",
        "kaiju.out",
        "-o",
        "/work/kaiju_taxnames/kaiju_taxon_names.tsv",
        "-u",
        "-r",
        "family",
    ]

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju.out",
            "reference_database": "/db/kaiju/refseq",
            "rank": "",
            "print_full_taxon_path": True,
            "output": "/work/kaiju_taxnames",
        }
    ) == [
        "kaiju-addTaxonNames",
        "-t",
        "/db/kaiju/refseq/nodes.dmp",
        "-n",
        "/db/kaiju/refseq/names.dmp",
        "-i",
        "kaiju.out",
        "-o",
        "/work/kaiju_taxnames/kaiju_taxon_names.tsv",
        "-p",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kaiju_add_taxon_names" / "kaiju_taxon_names.tsv",
    ]


def test_kaiju2krona_renders_krona_import_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kaiju2krona")
    info = _registry().object_info()["kaiju2krona"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["krona_import_tsv"]
    assert info["citation_dois"] == ["10.1038/ncomms11257"]
    assert info["citation_text"] == "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    assert info["input"]["required"]["kaiju_table"][0] == "TSV"
    assert info["input"]["required"]["reference_database"][0] == "DIRECTORY"
    assert info["input"]["optional"]["include_unclassified"][1]["default"] is False
    assert info["input"]["optional"]["selected_ranks"][1]["default"] == []

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju.out",
            "reference_database": "/db/kaiju/nr",
            "include_unclassified": True,
            "selected_ranks": ["superkingdom", "phylum", "genus"],
            "output": "/work/kaiju2krona",
        }
    ) == [
        "kaiju2krona",
        "-t",
        "/db/kaiju/nr/nodes.dmp",
        "-n",
        "/db/kaiju/nr/names.dmp",
        "-i",
        "kaiju.out",
        "-o",
        "/work/kaiju2krona/kaiju_krona.tsv",
        "-u",
        "-l",
        "superkingdom.phylum.genus",
    ]

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju_taxnames.out",
            "reference_database": "/db/kaiju/refseq",
            "include_unclassified": False,
            "selected_ranks": [],
            "output": "/work/kaiju2krona",
        }
    ) == [
        "kaiju2krona",
        "-t",
        "/db/kaiju/refseq/nodes.dmp",
        "-n",
        "/db/kaiju/refseq/names.dmp",
        "-i",
        "kaiju_taxnames.out",
        "-o",
        "/work/kaiju2krona/kaiju_krona.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kaiju2krona" / "kaiju_krona.tsv",
    ]


def test_kaiju_merge_outputs_renders_sorted_merge_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kaiju_merge_outputs")
    info = _registry().object_info()["kaiju_merge_outputs"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["merged_classification"]
    assert info["citation_dois"] == ["10.1038/ncomms11257"]
    assert info["citation_text"] == "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    assert info["input"]["required"]["kaiju_table"][0] == "TSV"
    assert info["input"]["required"]["kraken_table"][0] == "TSV"
    assert info["input"]["optional"]["reference_database"][0] == "DIRECTORY"
    assert info["input"]["optional"]["conflict_mode"][1]["default"] == "lca"
    assert info["input"]["optional"]["conflict_mode"][1]["options"] == ["1", "2", "lca", "lowest"]
    assert info["input"]["optional"]["use_score"][1]["default"] is False

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju calls.tsv",
            "kraken_table": "kraken.out",
            "reference_database": "/db/kaiju/nr",
            "conflict_mode": "lca",
            "use_score": True,
            "output": "/work/kaiju_merge",
        }
    ) == (
        "sort -k2,2 'kaiju calls.tsv' > kaiju.out.sort && "
        "sort -k2,2 kraken.out > kraken.out.sort && "
        "kaiju-mergeOutputs -i kaiju.out.sort -j kraken.out.sort "
        "-o /work/kaiju_merge/kaiju_merged_outputs.tsv -c lca "
        "-t /db/kaiju/nr/nodes.dmp -s -v"
    )

    assert node_class.render_command(
        {
            "kaiju_table": "kaiju.out",
            "kraken_table": "other.tsv",
            "conflict_mode": "1",
            "use_score": False,
            "output": "/work/kaiju_merge",
        }
    ) == (
        "sort -k2,2 kaiju.out > kaiju.out.sort && "
        "sort -k2,2 other.tsv > kraken.out.sort && "
        "kaiju-mergeOutputs -i kaiju.out.sort -j kraken.out.sort "
        "-o /work/kaiju_merge/kaiju_merged_outputs.tsv -c 1 -v"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kaiju_merge_outputs" / "kaiju_merged_outputs.tsv",
    ]


def test_kaiju2table_renders_summary_table_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kaiju2table")
    info = _registry().object_info()["kaiju2table"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["summary_table"]
    assert info["citation_dois"] == ["10.1038/ncomms11257"]
    assert info["citation_text"] == "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    assert info["input"]["required"]["kaiju_tables"][0] == "TSV"
    assert info["input"]["required"]["reference_database"][0] == "DIRECTORY"
    assert info["input"]["required"]["rank"][1]["options"] == [
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "species",
    ]
    assert info["input"]["optional"]["tax_path_report"][1]["options"] == ["", "full", "partial"]
    assert info["input"]["optional"]["selected_ranks"][1]["default"] == []

    assert node_class.render_command(
        {
            "kaiju_tables": ["sample A.tsv", "kaiju-taxnames.out"],
            "element_identifiers": ["sample A", "kaiju-taxnames.out"],
            "reference_database": "/db/kaiju/nr",
            "rank": "genus",
            "minimum_percentage": 1.5,
            "minimum_reads": "",
            "expand_viruses": True,
            "exclude_unclassified": True,
            "tax_path_report": "partial",
            "selected_ranks": ["superkingdom", "phylum", "genus"],
            "output": "/work/kaiju2table",
        }
    ) == (
        "ln -sf 'sample A.tsv' sample_A && "
        "ln -sf kaiju-taxnames.out kaiju-taxnames.out && "
        "kaiju2table -t /db/kaiju/nr/nodes.dmp -n /db/kaiju/nr/names.dmp -r genus "
        "-o /work/kaiju2table/kaiju_summary.tsv -m 1.5 -e -u -l superkingdom,phylum,genus "
        "sample_A kaiju-taxnames.out"
    )

    assert node_class.render_command(
        {
            "kaiju_tables": "single.tsv",
            "reference_database": "/db/kaiju/refseq",
            "rank": "species",
            "minimum_percentage": "",
            "minimum_reads": 12,
            "tax_path_report": "full",
            "output": "/work/kaiju2table",
        }
    ) == (
        "ln -sf single.tsv single.tsv && "
        "kaiju2table -t /db/kaiju/refseq/nodes.dmp -n /db/kaiju/refseq/names.dmp -r species "
        "-o /work/kaiju2table/kaiju_summary.tsv -c 12 -p single.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kaiju2table" / "kaiju_summary.tsv",
    ]


def test_kraken_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["kraken"]

    assert info["display_name"] == "Kraken"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Assign taxonomic labels to sequencing reads with Kraken."
    assert info["search_aliases"] == [
        "Galaxy",
        "Kraken",
        "taxonomic classification",
        "metagenomics",
        "k-mer exact alignment",
        "classified reads",
        "unclassified reads",
        "quick mode",
    ]
    assert info["version"] == "1.1.1"
    assert info["output"] == ["KRAKEN_OUTPUT", "FASTQ", "FASTQ"]
    assert info["output_name"] == ["classification", "classified_reads", "unclassified_reads"]
    assert info["required_executables"] == ["kraken"]
    assert info["required_conda_packages"] == ["kraken"]
    assert info["documentation_url"] == "http://ccb.jhu.edu/software/kraken/"
    assert info["citation_dois"] == ["10.1186/gb-2014-15-3-r46"]
    assert info["citation_text"] == "Kraken: ultrafast metagenomic sequence classification using exact alignments."

    assert info["input"]["required"]["input_type"][1]["options"] == ["single", "paired", "paired_collection"]
    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["required"]["input_sequences"][0] == "FASTQ"
    assert info["input"]["optional"]["input_format"][1]["options"] == ["fastq", "fasta"]
    assert info["input"]["optional"]["split_reads"][1]["default"] is False
    assert info["input"]["optional"]["only_classified_output"][1]["default"] is False
    assert info["input"]["optional"]["quick"][1]["default"] == "no"
    assert info["input"]["optional"]["min_hits"][1]["displayOptions"] == {"show": {"quick": ["yes"]}}


def test_kraken_renders_single_fasta_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken")

    assert node_class.render_command(
        {
            "input_type": "single",
            "input_sequences": "reads.fa",
            "input_format": "fasta",
            "db": "/db/kraken",
            "threads": 4,
            "only_classified_output": True,
            "output": "/work/kraken",
        }
    ) == (
        "kraken --threads 4 --db /db/kraken --only-classified-output --fasta-input reads.fa "
        "> /work/kraken/classification.kraken"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kraken" / "classification.kraken",
    ]


def test_kraken_renders_paired_quick_split_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken")

    assert node_class.render_command(
        {
            "input_type": "paired",
            "forward_input": "sample R1.fastq",
            "reverse_input": "sample R2.fastq",
            "input_format": "fastq",
            "db": "/db/kraken legacy",
            "threads": 8,
            "quick": "yes",
            "min_hits": 3,
            "check_names": True,
            "split_reads": True,
            "output": "/work/kraken",
        }
    ) == (
        "kraken --threads 8 --db '/db/kraken legacy' --quick --min-hits 3 --fastq-input "
        "'sample R1.fastq' 'sample R2.fastq' --paired --check-names "
        "--classified-out /work/kraken/classified_reads.fastq "
        "--unclassified-out /work/kraken/unclassified_reads.fastq "
        "> /work/kraken/classification.kraken"
    )

    assert node_class.PLAN_OUTPUTS({"split_reads": True, "input_format": "fastq"}, tmp_path) == [
        tmp_path / "kraken" / "classification.kraken",
        tmp_path / "kraken" / "classified_reads.fastq",
        tmp_path / "kraken" / "unclassified_reads.fastq",
    ]


def test_kraken_renders_paired_collection_and_validates_wrapper_inputs() -> None:
    node_class = _node_class("kraken")

    assert node_class.render_command(
        {
            "input_type": "paired_collection",
            "input_pair": {"forward": "lane1_R1.fq", "reverse": "lane1_R2.fq"},
            "db": "/db/minikraken",
            "check_names": False,
            "output": "/work/kraken",
        }
    ) == (
        "kraken --threads 1 --db /db/minikraken --fastq-input lane1_R1.fq lane1_R2.fq --paired "
        "> /work/kraken/classification.kraken"
    )

    assert node_class.VALIDATE_INPUTS({"input_sequences": "reads.fq"}) == "Kraken database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input_type": "single"}) == "Single-end input sequences are required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input_type": "paired", "forward_input": "R1.fq"}) == (
        "Forward and reverse reads are required for paired input"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input_type": "paired_collection", "input_pair": []}) == (
        "Paired collection input is required"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input_sequences": "reads.fq", "quick": "yes", "min_hits": 0}) == (
        "Quick mode min_hits must be at least 1"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input_sequences": "reads.fq"}) is True


def test_kraken_report_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["kraken_report"]

    assert info["display_name"] == "Kraken Report"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Generate a tabular sample report from classic Kraken classification output."
    assert info["search_aliases"] == [
        "Galaxy",
        "Kraken Report",
        "kraken-report",
        "sample report",
        "taxonomy summary",
        "classification report",
        "NCBI taxonomy ID",
    ]
    assert info["version"] == "1.3.1"
    assert info["output"] == ["KRAKEN_REPORT"]
    assert info["output_name"] == ["report"]
    assert info["required_executables"] == ["kraken-report"]
    assert info["required_conda_packages"] == ["kraken"]
    assert info["documentation_url"] == "http://ccb.jhu.edu/software/kraken/"
    assert info["citation_dois"] == ["10.1186/gb-2014-15-3-r46"]
    assert info["citation_text"] == "Kraken: ultrafast metagenomic sequence classification using exact alignments."

    assert info["input"]["required"]["kraken_output"][0] == "STRING"
    assert info["input"]["required"]["kraken_output"][1]["description"] == "Taxonomy classification produced by Kraken"
    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_kraken_report_renders_report_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken_report")

    assert node_class.render_command(
        {
            "kraken_output": "sample classification.kraken",
            "db": "/db/mini kraken",
            "output": "/work/kraken_report",
        }
    ) == (
        "kraken-report --db '/db/mini kraken' 'sample classification.kraken' "
        "> /work/kraken_report/kraken_report.tsv"
    )

    assert node_class.render_command(
        {
            "kraken_output": "classification.kraken",
            "db": "/db/kraken",
            "output": "/work/kraken_report",
        }
    ) == "kraken-report --db /db/kraken classification.kraken > /work/kraken_report/kraken_report.tsv"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kraken_report" / "kraken_report.tsv",
    ]


def test_kraken_report_validates_wrapper_inputs() -> None:
    node_class = _node_class("kraken_report")

    assert node_class.VALIDATE_INPUTS({"kraken_output": "classification.kraken"}) == "Kraken database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken"}) == "Kraken classification output is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "kraken_output": "classification.kraken"}) is True


def test_kraken_filter_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["kraken_filter"]

    assert info["display_name"] == "Kraken Filter"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Filter classic Kraken classification output by confidence score."
    assert info["search_aliases"] == [
        "Galaxy",
        "Kraken Filter",
        "kraken-filter",
        "confidence threshold",
        "classification filter",
        "taxonomy confidence",
        "unclassified",
    ]
    assert info["version"] == "1.3.1"
    assert info["output"] == ["KRAKEN_OUTPUT"]
    assert info["output_name"] == ["filtered_output"]
    assert info["required_executables"] == ["kraken-filter"]
    assert info["required_conda_packages"] == ["kraken"]
    assert info["documentation_url"] == "http://ccb.jhu.edu/software/kraken/"
    assert info["citation_dois"] == ["10.1186/gb-2014-15-3-r46"]
    assert info["citation_text"] == "Kraken: ultrafast metagenomic sequence classification using exact alignments."

    assert info["input"]["required"]["input"][0] == "STRING"
    assert info["input"]["required"]["input"][1]["description"] == "Taxonomy classification produced by Kraken"
    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["optional"]["threshold"][0] == "FLOAT"
    assert info["input"]["optional"]["threshold"][1]["default"] == 0
    assert info["input"]["optional"]["threshold"][1]["min"] == 0
    assert info["input"]["optional"]["threshold"][1]["max"] == 1


def test_kraken_filter_renders_threshold_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken_filter")

    assert node_class.render_command(
        {
            "input": "sample classification.kraken",
            "db": "/db/mini kraken",
            "threshold": 0.25,
            "output": "/work/kraken_filter",
        }
    ) == (
        "kraken-filter --db '/db/mini kraken' --threshold 0.25 'sample classification.kraken' "
        "> /work/kraken_filter/filtered_output.kraken"
    )

    assert node_class.render_command(
        {
            "input": "classification.kraken",
            "db": "/db/kraken",
            "output": "/work/kraken_filter",
        }
    ) == "kraken-filter --db /db/kraken --threshold 0 classification.kraken > /work/kraken_filter/filtered_output.kraken"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kraken_filter" / "filtered_output.kraken",
    ]


def test_kraken_filter_validates_wrapper_inputs() -> None:
    node_class = _node_class("kraken_filter")

    assert node_class.VALIDATE_INPUTS({"input": "classification.kraken"}) == "Kraken database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken"}) == "Kraken classification output is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input": "classification.kraken", "threshold": "bad"}) == (
        "Confidence threshold must be a number between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input": "classification.kraken", "threshold": -0.1}) == (
        "Confidence threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input": "classification.kraken", "threshold": 1.1}) == (
        "Confidence threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input": "classification.kraken", "threshold": 0.5}) is True


def test_kraken_translate_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["kraken_translate"]

    assert info["display_name"] == "Kraken Translate"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Convert Kraken taxonomy IDs into taxonomic lineage names."
    assert info["search_aliases"] == [
        "Galaxy",
        "Kraken Translate",
        "kraken-translate",
        "taxonomy labels",
        "lineage names",
        "MPA format",
        "standard ranks",
    ]
    assert info["version"] == "1.3.1"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["translated"]
    assert info["required_executables"] == ["kraken-translate"]
    assert info["required_conda_packages"] == ["kraken"]
    assert info["documentation_url"] == "http://ccb.jhu.edu/software/kraken/"
    assert info["citation_dois"] == ["10.1186/gb-2014-15-3-r46"]
    assert info["citation_text"] == "Kraken: ultrafast metagenomic sequence classification using exact alignments."

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "Taxonomy classification produced by Kraken"
    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["optional"]["mpa_format"][0] == "BOOLEAN"
    assert info["input"]["optional"]["mpa_format"][1]["default"] is False


def test_kraken_translate_renders_translation_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken_translate")

    assert node_class.render_command(
        {
            "input": "sample classification.kraken",
            "db": "/db/mini kraken",
            "mpa_format": True,
            "output": "/work/kraken_translate",
        }
    ) == (
        "kraken-translate --db '/db/mini kraken' --mpa-format 'sample classification.kraken' "
        "> /work/kraken_translate/translated.tsv"
    )

    assert node_class.render_command(
        {
            "input": "classification.kraken",
            "db": "/db/kraken",
            "output": "/work/kraken_translate",
        }
    ) == "kraken-translate --db /db/kraken classification.kraken > /work/kraken_translate/translated.tsv"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kraken_translate" / "translated.tsv",
    ]


def test_kraken_translate_validates_wrapper_inputs() -> None:
    node_class = _node_class("kraken_translate")

    assert node_class.VALIDATE_INPUTS({"input": "classification.kraken"}) == "Kraken database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken"}) == "Kraken classification output is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "input": "classification.kraken"}) is True


def test_kraken_mpa_report_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["kraken_mpa_report"]

    assert info["display_name"] == "Kraken MPA Report"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Summarize classic Kraken classifications across taxonomic ranks for multiple samples."
    assert info["search_aliases"] == [
        "Galaxy",
        "Kraken MPA Report",
        "kraken-mpa-report",
        "multiple samples",
        "taxonomic ranks",
        "MetaPhlAn style",
        "show zeros",
        "header line",
    ]
    assert info["version"] == "1.3.1"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output_report"]
    assert info["required_executables"] == ["kraken-mpa-report"]
    assert info["required_conda_packages"] == ["kraken"]
    assert info["documentation_url"] == "http://ccb.jhu.edu/software/kraken/"
    assert info["citation_dois"] == ["10.1186/gb-2014-15-3-r46"]
    assert info["citation_text"] == "Kraken: ultrafast metagenomic sequence classification using exact alignments."

    assert info["input"]["required"]["classification"][0] == "TSV"
    assert info["input"]["required"]["classification"][1]["multiple"] is True
    assert info["input"]["required"]["classification"][1]["description"] == "One or more Kraken classification outputs"
    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["optional"]["show_zeros"][0] == "BOOLEAN"
    assert info["input"]["optional"]["show_zeros"][1]["default"] is False
    assert info["input"]["optional"]["header_line"][0] == "BOOLEAN"
    assert info["input"]["optional"]["header_line"][1]["default"] is False


def test_kraken_mpa_report_renders_multi_sample_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("kraken_mpa_report")

    assert node_class.render_command(
        {
            "classification": ["alpha classification.tsv", "beta/classification.tsv", "beta/classification.tsv"],
            "element_identifiers": ["sample/one", "sample\tone", "sample/one"],
            "db": "/db/mini kraken",
            "show_zeros": True,
            "header_line": True,
            "output": "/work/kraken_mpa_report",
        }
    ) == (
        "ln -s 'alpha classification.tsv' sample-one && "
        "ln -s beta/classification.tsv sample-one_1 && "
        "ln -s beta/classification.tsv sample-one_2 && "
        "kraken-mpa-report --db '/db/mini kraken' sample-one sample-one_1 sample-one_2 "
        "--show-zeros --header-line > /work/kraken_mpa_report/output_report.tsv"
    )

    assert node_class.render_command(
        {
            "classification": ["sample1.kraken", "sample2.kraken"],
            "db": "/db/kraken",
            "output": "/work/kraken_mpa_report",
        }
    ) == (
        "kraken-mpa-report --db /db/kraken sample1.kraken sample2.kraken "
        "> /work/kraken_mpa_report/output_report.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "kraken_mpa_report" / "output_report.tsv",
    ]


def test_kraken_mpa_report_validates_wrapper_inputs() -> None:
    node_class = _node_class("kraken_mpa_report")

    assert node_class.VALIDATE_INPUTS({"classification": ["sample.kraken"]}) == "Kraken database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken"}) == "At least one Kraken classification output is required"
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "classification": []}) == (
        "At least one Kraken classification output is required"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/db/kraken", "classification": ["sample.kraken"]}) is True


def test_krakentools_combine_kreports_renders_report_merge_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_combine_kreports")
    info = _registry().object_info()["krakentools_combine_kreports"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["combined_report"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["reports"][0] == "TSV"
    assert info["input"]["required"]["reports"][1]["multiple"] is True
    assert info["input"]["optional"]["display_headers"][1]["default"] is True
    assert info["input"]["optional"]["only_combined"][1]["default"] is False

    assert node_class.render_command(
        {
            "reports": ["alpha report.tsv", "beta.report"],
            "element_identifiers": ["S1 report", "S2.report"],
            "display_headers": True,
            "only_combined": True,
            "output": "/work/krakentools_combine",
        }
    ) == (
        "ln -s 'alpha report.tsv' S1_report && "
        "ln -s beta.report S2.report && "
        "combine_kreports.py --reports S1_report S2.report "
        "--output /work/krakentools_combine/combined_kreport.tsv "
        "--display-headers --only-combined"
    )

    assert node_class.render_command(
        {
            "reports": ["alpha.report", "beta.report"],
            "display_headers": False,
            "only_combined": False,
            "output": "/work/krakentools_combine",
        }
    ) == (
        "combine_kreports.py --reports alpha.report beta.report "
        "--output /work/krakentools_combine/combined_kreport.tsv --no-headers"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "krakentools_combine_kreports" / "combined_kreport.tsv",
    ]


def test_krakentools_alpha_diversity_renders_metric_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_alpha_diversity")
    info = _registry().object_info()["krakentools_alpha_diversity"]

    assert info["output"] == ["TEXT"]
    assert info["output_name"] == ["alpha_diversity"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["abundance_file"][0] == "TSV"
    assert info["input"]["optional"]["alpha"][1]["default"] == "Sh"
    assert info["input"]["optional"]["alpha"][1]["options"] == ["Sh", "BP", "Si", "ISi", "F"]

    assert node_class.render_command(
        {
            "abundance_file": "bracken abundance.tsv",
            "alpha": "ISi",
            "output": "/work/krakentools_alpha",
        }
    ) == (
        "alpha_diversity.py --filename 'bracken abundance.tsv' --alpha ISi "
        "> /work/krakentools_alpha/alpha_diversity.txt"
    )

    assert node_class.render_command(
        {
            "filename": "bracken.tabular",
            "output": "/work/krakentools_alpha",
        }
    ) == (
        "alpha_diversity.py --filename bracken.tabular --alpha Sh "
        "> /work/krakentools_alpha/alpha_diversity.txt"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "krakentools_alpha_diversity" / "alpha_diversity.txt",
    ]


def test_krakentools_beta_diversity_renders_distance_matrix_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_beta_diversity")
    info = _registry().object_info()["krakentools_beta_diversity"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["beta_diversity"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["taxonomy_files"][0] == "TSV"
    assert info["input"]["required"]["taxonomy_files"][1]["multiple"] is True
    assert info["input"]["optional"]["sample_type"][1]["default"] == "single"
    assert info["input"]["optional"]["sample_type"][1]["options"] == ["single", "simple", "bracken", "kreport", "krona"]
    assert info["input"]["optional"]["level"][1]["default"] == "all"
    assert info["input"]["optional"]["level"][1]["options"] == ["all", "S", "G", "F", "O"]

    assert node_class.render_command(
        {
            "taxonomy_files": ["beta kreport 1.tsv", "beta-kreport-2.tsv"],
            "element_identifiers": ["Sample 1", "Sample#2"],
            "sample_type": "kreport",
            "level": "G",
            "output": "/work/krakentools_beta",
        }
    ) == (
        "ln -s 'beta kreport 1.tsv' Sample_1 && "
        "ln -s beta-kreport-2.tsv Sample_2 && "
        "beta_diversity.py --inputs Sample_1 Sample_2 --type kreport --level G "
        "> /work/krakentools_beta/beta_diversity.tsv"
    )

    assert node_class.render_command(
        {
            "inputs": ["bracken1.tsv", "bracken2.tsv"],
            "sample_type": "bracken",
            "level": "S",
            "output": "/work/krakentools_beta",
        }
    ) == (
        "ln -s bracken1.tsv bracken1.tsv && "
        "ln -s bracken2.tsv bracken2.tsv && "
        "beta_diversity.py --inputs bracken1.tsv bracken2.tsv --type bracken "
        "> /work/krakentools_beta/beta_diversity.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "krakentools_beta_diversity" / "beta_diversity.tsv",
    ]


def test_krakentools_kreport2krona_renders_conversion_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_kreport2krona")
    info = _registry().object_info()["krakentools_kreport2krona"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["krona_text"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["report"][0] == "TSV"
    assert info["input"]["optional"]["intermediate_ranks"][1]["default"] is False

    assert node_class.render_command(
        {
            "report": "sample report.tabular",
            "intermediate_ranks": True,
            "output": "/work/krakentools_krona",
        }
    ) == (
        "kreport2krona.py --report 'sample report.tabular' "
        "--output /work/krakentools_krona/krona_text.tsv --intermediate-ranks"
    )

    assert node_class.render_command(
        {
            "report": "sample.tabular",
            "output": "/work/krakentools_krona",
        }
    ) == "kreport2krona.py --report sample.tabular --output /work/krakentools_krona/krona_text.tsv"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "krakentools_kreport2krona" / "krona_text.tsv",
    ]


def test_krakentools_kreport2mpa_renders_metaphlan_conversion_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_kreport2mpa")
    info = _registry().object_info()["krakentools_kreport2mpa"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["metaphlan_profile"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["report"][0] == "TSV"
    assert info["input"]["optional"]["intermediate_ranks"][1]["default"] is False
    assert info["input"]["optional"]["percentages"][1]["default"] is False

    assert node_class.render_command(
        {
            "report": "sample report.tabular",
            "intermediate_ranks": True,
            "percentages": True,
            "output": "/work/krakentools_mpa",
        }
    ) == (
        "kreport2mpa.py --report 'sample report.tabular' "
        "--output /work/krakentools_mpa/metaphlan_profile.tsv "
        "--intermediate-ranks --percentages"
    )

    assert node_class.render_command(
        {
            "report": "sample.tabular",
            "output": "/work/krakentools_mpa",
        }
    ) == "kreport2mpa.py --report sample.tabular --output /work/krakentools_mpa/metaphlan_profile.tsv"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "krakentools_kreport2mpa" / "metaphlan_profile.tsv",
    ]


def test_krakentools_extract_kraken_reads_renders_extraction_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("krakentools_extract_kraken_reads")
    info = _registry().object_info()["krakentools_extract_kraken_reads"]

    assert info["output"] == ["FASTA", "FASTA", "DIRECTORY"]
    assert info["output_name"] == ["forward_reads", "reverse_reads", "paired_reads"]
    assert info["citation_dois"] == ["10.1038/s41596-022-00738-y"]
    assert info["citation_text"] == "Metagenome analysis using the Kraken software suite."
    assert info["input"]["required"]["library_type"][1]["default"] == "single"
    assert info["input"]["required"]["library_type"][1]["options"] == ["single", "paired", "paired_collection"]
    assert info["input"]["required"]["taxid"][0] == "STRING"
    assert info["input"]["required"]["results"][0] == "TSV"
    assert info["input"]["optional"]["max_reads"][1]["default"] == 100000000
    assert info["input"]["optional"]["fastq_output"][1]["default"] is False
    assert info["input"]["optional"]["include_children"][1]["default"] is False

    assert node_class.render_command(
        {
            "library_type": "single",
            "input_1": "reads R1.fq",
            "results": "kraken results.tsv",
            "taxid": "10386 11176",
            "max_reads": 2,
            "exclude": True,
            "fastq_output": True,
            "include_parents": True,
            "report": "kraken report.tsv",
            "output": "/work/krakentools_extract",
        }
    ) == (
        "extract_kraken_reads.py -k 'kraken results.tsv' -s 'reads R1.fq' "
        "-o output_1.fastq --taxid 10386 11176 --max 2 --include-parents "
        "--exclude --fastq-output --report 'kraken report.tsv' && "
        "gzip -cvf output_1.fastq > /work/krakentools_extract/output_1.fastq.gz"
    )

    assert node_class.render_command(
        {
            "library_type": "paired",
            "input_1": "reads/R1.fastq.gz",
            "input_2": "reads/R2.fastq.gz",
            "input_1_ext": "fastq.gz",
            "results": "kraken2.results",
            "taxid": "11176",
            "include_children": True,
            "report": "kraken2.report",
            "output": "/work/krakentools_extract",
        }
    ) == (
        "ln -s reads/R1.fastq.gz input_1.gz && "
        "ln -s reads/R2.fastq.gz input_2.gz && "
        "extract_kraken_reads.py -k kraken2.results -s input_1.gz -o output_1.fasta "
        "--taxid 11176 --max 100000000 --include-children -s2 input_2.gz "
        "-o2 output_2.fasta --report kraken2.report && "
        "gzip -cvf output_1.fasta > /work/krakentools_extract/output_1.fasta.gz && "
        "gzip -cvf output_2.fasta > /work/krakentools_extract/output_2.fasta.gz"
    )

    assert node_class.PLAN_OUTPUTS({"fastq_output": True}, tmp_path) == [
        tmp_path / "krakentools_extract_kraken_reads" / "output_1.fastq.gz",
        tmp_path / "krakentools_extract_kraken_reads" / "output_2.fastq.gz",
        tmp_path / "krakentools_extract_kraken_reads" / "paired_reads",
    ]


def test_taxpasta_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["taxpasta"]

    assert info["display_name"] == "Taxpasta"
    assert info["category"] == "taxonomy"
    assert info["description"] == "Standardise and merge taxonomic profiles from common metagenomic profilers."
    assert info["search_aliases"] == [
        "Galaxy",
        "taxpasta",
        "taxonomic profile standardisation",
        "taxonomy aggregation",
        "BIOM",
        "Kraken2 report",
        "MetaPhlAn",
        "DIAMOND taxonomy",
    ]
    assert info["version"] == "0.7.0"
    assert info["output"] == ["TSV", "BIOM"]
    assert info["output_name"] == ["tabular_output", "biom_output"]
    assert info["required_executables"] == ["taxpasta"]
    assert info["required_conda_packages"] == ["taxpasta"]
    assert info["documentation_url"] == "https://taxpasta.readthedocs.io/en/latest/"
    assert info["citation_dois"] == ["10.21105/joss.05627"]
    assert info["citation_text"] == "TAXPASTA: TAXonomic Profile Aggregation and STAndardisation."

    assert info["input"]["required"]["action"][1]["options"] == ["standardise", "merge"]
    assert info["input"]["required"]["profiler"][1]["options"] == [
        "bracken",
        "Centrifuge",
        "diamond",
        "ganon",
        "kaiju",
        "kraken2",
        "krakenuniq",
        "megan6",
        "metaphlan",
        "motus",
    ]
    assert info["input"]["required"]["infile"][0] == "TSV"
    assert info["input"]["required"]["infile"][1]["multiple"] is True
    assert info["input"]["required"]["taxonomy"][0] == "DIRECTORY"
    assert info["input"]["optional"]["output_format"][1]["options"] == ["TSV", "BIOM"]
    assert info["input"]["optional"]["wide"][1]["default"] is True
    assert info["input"]["optional"]["wide"][1]["displayOptions"] == {
        "show": {"action": ["merge"], "output_format": ["TSV"]},
    }
    assert info["input"]["optional"]["add_name"][1]["default"] is True
    assert info["input"]["optional"]["add_rank_lineage"][1]["default"] is False


def test_taxpasta_renders_standardise_and_merge_tsv_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("taxpasta")

    assert node_class.render_command(
        {
            "action": "standardise",
            "profiler": "kraken2",
            "infile": "sample report.tsv",
            "taxonomy": "/db/ncbi taxonomy",
            "add_name": True,
            "add_rank": True,
            "add_lineage": True,
            "add_id_lineage": True,
            "add_rank_lineage": True,
            "output": "/work/taxpasta",
        }
    ) == (
        "taxpasta standardise --profiler kraken2 --taxonomy '/db/ncbi taxonomy' "
        "--output-format TSV --output /work/taxpasta/tabular_output.tsv "
        "--add-name --add-rank --add-lineage --add-id-lineage --add-rank-lineage "
        "'sample report.tsv'"
    )

    assert node_class.render_command(
        {
            "action": "merge",
            "profiler": "metaphlan",
            "infile": ["ERR7569997.txt", "ERR7569998.txt"],
            "taxonomy": "/db/taxonomy",
            "output_format": "TSV",
            "wide": False,
            "add_name": True,
            "add_rank": False,
            "add_lineage": False,
            "add_id_lineage": False,
            "add_rank_lineage": False,
            "output": "/work/taxpasta",
        }
    ) == (
        "taxpasta merge --profiler metaphlan --taxonomy /db/taxonomy "
        "--output-format TSV --output /work/taxpasta/tabular_output.tsv --long "
        "--add-name ERR7569997.txt ERR7569998.txt"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "taxpasta" / "tabular_output.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"action": "merge", "output_format": "TSV"}, tmp_path) == [
        tmp_path / "taxpasta" / "tabular_output.tsv",
    ]


def test_taxpasta_renders_merge_biom_command_and_validates_wrapper_inputs(tmp_path: Path) -> None:
    node_class = _node_class("taxpasta")

    assert node_class.render_command(
        {
            "action": "merge",
            "profiler": "kraken2",
            "infile": [
                "2612_pe-ERR5766176-db1.kraken2.report.txt",
                "2611_se-ERR5766174-db1.kraken2.report.txt",
            ],
            "taxonomy": "/db/taxonomy",
            "output_format": "BIOM",
            "add_name": True,
            "add_rank": False,
            "add_lineage": False,
            "add_id_lineage": False,
            "add_rank_lineage": False,
            "output": "/work/taxpasta",
        }
    ) == (
        "taxpasta merge --profiler kraken2 --taxonomy /db/taxonomy "
        "--output-format BIOM --output /work/taxpasta/biom_output.biom "
        "--add-name 2612_pe-ERR5766176-db1.kraken2.report.txt 2611_se-ERR5766174-db1.kraken2.report.txt"
    )

    assert node_class.PLAN_OUTPUTS({"action": "merge", "output_format": "BIOM"}, tmp_path) == [
        tmp_path / "taxpasta" / "biom_output.biom",
    ]
    assert node_class.VALIDATE_INPUTS({"profiler": "kraken2", "taxonomy": "/db/taxonomy"}) == (
        "At least one Taxpasta input report is required"
    )
    assert node_class.VALIDATE_INPUTS({"infile": ["report.tsv"], "taxonomy": "/db/taxonomy"}) == (
        "Taxpasta profiler is required"
    )
    assert node_class.VALIDATE_INPUTS({"infile": ["report.tsv"], "profiler": "kraken2"}) == (
        "NCBI taxonomy directory is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"infile": ["report.tsv"], "profiler": "kraken2", "taxonomy": "/db/taxonomy", "output_format": "JSON"}
    ) == "Unsupported Taxpasta output format: JSON"
    assert node_class.VALIDATE_INPUTS({"infile": ["report.tsv"], "profiler": "kraken2", "taxonomy": "/db/taxonomy"}) is True


def test_humann_join_tables_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_join_tables"]

    assert info["display_name"] == "HUMAnN Join Tables"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Join gene, pathway, or taxonomy HUMAnN/MetaPhlAn tables into one table."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_join_tables",
        "Join merge",
        "gene table",
        "pathway table",
        "taxonomy table",
        "MetaPhlAn table",
        "multi-sample table",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_join_tables"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_urls"] == [
        "https://doi.org/10.7554/eLife.65088",
        "https://doi.org/10.1371/journal.pcbi.1002358",
    ]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["inputs"][0] == "TSV"
    assert info["input"]["required"]["inputs"][1]["multiple"] is True
    assert info["input"]["required"]["inputs"][1]["description"] == (
        "Gene, pathway, or taxonomy tables to join"
    )
    assert info["input"]["optional"]["element_identifiers"][0] == "STRING"
    assert info["input"]["optional"]["element_identifiers"][1]["multiple"] is True
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_join_tables_renders_join_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("humann_join_tables")

    assert node_class.render_command(
        {
            "inputs": ["demo pathabundance.tsv", "demo/pathcoverage.tsv", "demo/metaphlan.tsv"],
            "element_identifiers": ["humann Abundance", "humann/Coverage", "MetaPhlAn taxonomy"],
            "output": "/work/humann_join_tables",
        }
    ) == (
        "mkdir tmp_dir && "
        "ln -s 'demo pathabundance.tsv' tmp_dir/humann_Abundance && "
        "ln -s demo/pathcoverage.tsv tmp_dir/humann_Coverage && "
        "ln -s demo/metaphlan.tsv tmp_dir/MetaPhlAn_taxonomy && "
        "humann_join_tables -i tmp_dir -o /work/humann_join_tables/joined_tables.tsv"
    )

    assert node_class.render_command(
        {
            "inputs": ["sample1.tsv", "sample 2.tsv", "sample3.tsv"],
            "output": "/work/humann_join_tables",
        }
    ) == (
        "mkdir tmp_dir && "
        "ln -s sample1.tsv tmp_dir/sample1.tsv && "
        "ln -s 'sample 2.tsv' tmp_dir/sample_2.tsv && "
        "ln -s sample3.tsv tmp_dir/sample3.tsv && "
        "humann_join_tables -i tmp_dir -o /work/humann_join_tables/joined_tables.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_join_tables" / "joined_tables.tsv",
    ]


def test_humann_join_tables_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_join_tables")

    assert node_class.VALIDATE_INPUTS({}) == "At least one HUMAnN or MetaPhlAn table is required"
    assert node_class.VALIDATE_INPUTS({"inputs": []}) == "At least one HUMAnN or MetaPhlAn table is required"
    assert node_class.VALIDATE_INPUTS({"inputs": ["pathabundance.tsv"]}) is True


def test_humann_renorm_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_renorm_table"]

    assert info["display_name"] == "HUMAnN Renormalize Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Renormalize HUMAnN gene or pathway tables to CPM or relative abundance units."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_renorm_table",
        "Renormalize",
        "copies per million",
        "relative abundance",
        "community total",
        "levelwise total",
        "UNMAPPED",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_renorm_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "HUMAnN gene or pathway table"
    assert info["input"]["optional"]["units"][1]["default"] == "cpm"
    assert info["input"]["optional"]["units"][1]["options"] == ["cpm", "relab"]
    assert info["input"]["optional"]["mode"][1]["default"] == "community"
    assert info["input"]["optional"]["mode"][1]["options"] == ["community", "levelwise"]
    assert info["input"]["optional"]["special"][1]["default"] is True
    assert info["input"]["optional"]["update_snames"][1]["default"] is True
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_renorm_table_renders_normalization_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("humann_renorm_table")

    assert node_class.render_command(
        {
            "input": "demo pathabundance.tsv",
            "units": "cpm",
            "mode": "community",
            "special": False,
            "update_snames": False,
            "output": "/work/humann_renorm_table",
        }
    ) == (
        "humann_renorm_table --input 'demo pathabundance.tsv' "
        "-o /work/humann_renorm_table/renormalized_table.tsv "
        "--units cpm --mode community --special n"
    )

    assert node_class.render_command(
        {
            "input": "demo_pathabundance.tsv",
            "units": "relab",
            "mode": "levelwise",
            "special": True,
            "update_snames": True,
            "output": "/work/humann_renorm_table",
        }
    ) == (
        "humann_renorm_table --input demo_pathabundance.tsv "
        "-o /work/humann_renorm_table/renormalized_table.tsv "
        "--units relab --mode levelwise --special y --update-snames"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_renorm_table" / "renormalized_table.tsv",
    ]


def test_humann_renorm_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_renorm_table")

    assert node_class.VALIDATE_INPUTS({}) == "HUMAnN gene or pathway table is required"
    assert node_class.VALIDATE_INPUTS({"input": "pathabundance.tsv", "units": "rpm"}) == (
        "Unsupported HUMAnN normalization units: rpm"
    )
    assert node_class.VALIDATE_INPUTS({"input": "pathabundance.tsv", "mode": "samplewise"}) == (
        "Unsupported HUMAnN normalization mode: samplewise"
    )
    assert node_class.VALIDATE_INPUTS({"input": "pathabundance.tsv"}) is True


def test_humann_split_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_split_table"]

    assert info["display_name"] == "HUMAnN Split Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Split a merged HUMAnN feature table into one table per sample."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_split_table",
        "Split",
        "merged table",
        "one file per sample",
        "taxonomy index",
        "PICRUSt",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["split_tables"]
    assert info["required_executables"] == ["humann_split_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "Merged HUMAnN gene or pathway table"
    assert info["input"]["optional"]["taxonomy_index"][0] == "INT"
    assert info["input"]["optional"]["taxonomy_index"][1]["default"] == ""
    assert info["input"]["optional"]["taxonomy_level"][1]["options"] == [
        "Kingdom",
        "Phylum",
        "Class",
        "Order",
        "Family",
        "Genus",
        "Species",
    ]
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_split_table_renders_split_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("humann_split_table")

    assert node_class.render_command(
        {
            "input": "demo joined pathabundance pathcoverage.tsv",
            "output": "/work/humann_split_table",
        }
    ) == (
        "humann_split_table --input 'demo joined pathabundance pathcoverage.tsv' "
        "-o /work/humann_split_table/split_tables"
    )

    assert node_class.render_command(
        {
            "input": "picrust_metagenome.tsv",
            "taxonomy_index": 4,
            "taxonomy_level": "Genus",
            "output": "/work/humann_split_table",
        }
    ) == (
        "humann_split_table --input picrust_metagenome.tsv -o /work/humann_split_table/split_tables "
        "--taxonomy_index 4 --taxonomy_level Genus"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_split_table" / "split_tables",
    ]


def test_humann_split_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_split_table")

    assert node_class.VALIDATE_INPUTS({}) == "Merged HUMAnN table is required"
    assert node_class.VALIDATE_INPUTS({"input": "merged.tsv", "taxonomy_level": "Strain"}) == (
        "Unsupported HUMAnN taxonomy level: Strain"
    )
    assert node_class.VALIDATE_INPUTS({"input": "merged.tsv", "taxonomy_index": "gene"}) == (
        "Taxonomy index must be an integer"
    )
    assert node_class.VALIDATE_INPUTS({"input": "merged.tsv", "taxonomy_index": -1}) == (
        "Taxonomy index must be zero or greater"
    )
    assert node_class.VALIDATE_INPUTS({"input": "merged.tsv", "taxonomy_index": 0}) is True


def test_humann_split_stratified_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_split_stratified_table"]

    assert info["display_name"] == "HUMAnN Split Stratified Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Split a stratified HUMAnN table into stratified and unstratified tables."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_split_stratified_table",
        "Split a HUMAnN table",
        "stratified table",
        "unstratified table",
        "gene families",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["stratified", "unstratified"]
    assert info["required_executables"] == ["humann_split_stratified_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "Stratified HUMAnN table"
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_split_stratified_table_renders_split_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("humann_split_stratified_table")

    assert node_class.render_command(
        {
            "input": "demo genefamilies.tsv",
            "output": "/work/humann_split_stratified_table",
        }
    ) == (
        "humann_split_stratified_table --input 'demo genefamilies.tsv' "
        "--output /work/humann_split_stratified_table/split_stratified"
    )

    assert node_class.PLAN_OUTPUTS({"input": "demo_genefamilies.tsv"}, tmp_path) == [
        tmp_path
        / "humann_split_stratified_table"
        / "split_stratified"
        / "demo_genefamilies_stratified.tsv",
        tmp_path
        / "humann_split_stratified_table"
        / "split_stratified"
        / "demo_genefamilies_unstratified.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"input": "demo_genefamilies.tsv.gz"}, tmp_path) == [
        tmp_path
        / "humann_split_stratified_table"
        / "split_stratified"
        / "demo_genefamilies_stratified.tsv",
        tmp_path
        / "humann_split_stratified_table"
        / "split_stratified"
        / "demo_genefamilies_unstratified.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_split_stratified_table" / "split_stratified" / "stratified.tsv",
        tmp_path / "humann_split_stratified_table" / "split_stratified" / "unstratified.tsv",
    ]


def test_humann_split_stratified_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_split_stratified_table")

    assert node_class.VALIDATE_INPUTS({}) == "Stratified HUMAnN table is required"
    assert node_class.VALIDATE_INPUTS({"input": "demo_genefamilies.tsv"}) is True


def test_humann_reduce_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_reduce_table"]

    assert info["display_name"] == "HUMAnN Reduce Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Reduce a joined HUMAnN table by applying a row-wise summary function."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_reduce_table",
        "Reduce",
        "joined HUMAnN table",
        "row-wise summary",
        "max sum mean min",
        "sort by value",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_reduce_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "Joined HUMAnN gene, pathway, or taxonomic table"
    assert info["input"]["optional"]["function"][0] == "STRING"
    assert info["input"]["optional"]["function"][1]["default"] == "max"
    assert info["input"]["optional"]["function"][1]["options"] == ["max", "sum", "mean", "min"]
    assert info["input"]["optional"]["sort_by"][0] == "STRING"
    assert info["input"]["optional"]["sort_by"][1]["default"] == "name"
    assert info["input"]["optional"]["sort_by"][1]["options"] == ["name", "value", "level"]
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_reduce_table_renders_reduce_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("humann_reduce_table")

    assert node_class.render_command(
        {
            "input": "demo joined pathabundance pathcoverage.tsv",
            "output": "/work/humann_reduce_table",
        }
    ) == (
        "humann_reduce_table --input 'demo joined pathabundance pathcoverage.tsv' "
        "-o /work/humann_reduce_table/reduced_table.tsv --function max --sort-by name"
    )

    assert node_class.render_command(
        {
            "input": "demo_joined_pathabundance_pathcoverage.tsv",
            "function": "mean",
            "sort_by": "value",
            "output": "/work/humann_reduce_table",
        }
    ) == (
        "humann_reduce_table --input demo_joined_pathabundance_pathcoverage.tsv "
        "-o /work/humann_reduce_table/reduced_table.tsv --function mean --sort-by value"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_reduce_table" / "reduced_table.tsv",
    ]


def test_humann_reduce_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_reduce_table")

    assert node_class.VALIDATE_INPUTS({}) == "Joined HUMAnN table is required"
    assert node_class.VALIDATE_INPUTS({"input": "joined.tsv", "function": "median"}) == (
        "Unsupported HUMAnN reduction function: median"
    )
    assert node_class.VALIDATE_INPUTS({"input": "joined.tsv", "sort_by": "sample"}) == (
        "Unsupported HUMAnN reduce sort option: sample"
    )
    assert node_class.VALIDATE_INPUTS({"input": "joined.tsv", "function": "sum", "sort_by": "level"}) is True


def test_humann_regroup_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_regroup_table"]

    assert info["display_name"] == "HUMAnN Regroup Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Regroup HUMAnN gene-family features into functional categories."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_regroup_table",
        "Regroup",
        "gene families",
        "MetaCyc reactions",
        "UniRef90",
        "custom mapping",
        "UNGROUPED",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_regroup_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "HUMAnN gene families table"
    assert info["input"]["optional"]["function"][1]["default"] == "sum"
    assert info["input"]["optional"]["function"][1]["options"] == ["sum", "mean"]
    assert info["input"]["optional"]["grouping_type"][1]["default"] == "standard"
    assert info["input"]["optional"]["grouping_type"][1]["options"] == ["standard", "large", "custom"]
    assert info["input"]["optional"]["groups"][1]["options"] == ["uniref90_rxn", "uniref50_rxn"]
    assert info["input"]["optional"]["grouping"][0] == "FILE"
    assert info["input"]["optional"]["custom"][0] == "TSV"
    assert info["input"]["optional"]["precision"][1]["default"] == 3
    assert info["input"]["optional"]["ungrouped"][1]["default"] is True
    assert info["input"]["optional"]["protected"][1]["default"] is True
    assert info["input"]["optional"]["reversed"][1]["default"] is False
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_regroup_table_renders_standard_large_and_custom_commands(tmp_path: Path) -> None:
    node_class = _node_class("humann_regroup_table")

    assert node_class.render_command(
        {
            "input": "demo genefamilies.tsv",
            "output": "/work/humann_regroup_table",
        }
    ) == (
        "humann_regroup_table --input 'demo genefamilies.tsv' "
        "--output /work/humann_regroup_table/regrouped_table.tsv --function sum "
        "--groups uniref90_rxn --precision 3 --ungrouped Y --protected Y"
    )

    assert node_class.render_command(
        {
            "input": "demo_genefamilies.tsv",
            "function": "mean",
            "grouping_type": "large",
            "grouping": "utility_mapping-full-map_go_uniref90-3.0.0-29042021",
            "reversed": True,
            "precision": 4,
            "ungrouped": False,
            "protected": False,
            "output": "/work/humann_regroup_table",
        }
    ) == (
        "humann_regroup_table --input demo_genefamilies.tsv "
        "--output /work/humann_regroup_table/regrouped_table.tsv --function mean "
        "--custom utility_mapping-full-map_go_uniref90-3.0.0-29042021 --reversed "
        "--precision 4 --ungrouped N --protected N"
    )

    assert node_class.render_command(
        {
            "input": "demo_genefamilies.tsv",
            "grouping_type": "custom",
            "custom": "map go uniref90.txt",
            "reversed": False,
            "output": "/work/humann_regroup_table",
        }
    ) == (
        "humann_regroup_table --input demo_genefamilies.tsv "
        "--output /work/humann_regroup_table/regrouped_table.tsv --function sum "
        "--custom 'map go uniref90.txt' --precision 3 --ungrouped Y --protected Y"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_regroup_table" / "regrouped_table.tsv",
    ]


def test_humann_regroup_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_regroup_table")

    assert node_class.VALIDATE_INPUTS({}) == "HUMAnN gene families table is required"
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "function": "max"}) == (
        "Unsupported HUMAnN regroup function: max"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "grouping_type": "database"}) == (
        "Unsupported HUMAnN grouping type: database"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "groups": "uniref90_go"}) == (
        "Unsupported HUMAnN built-in grouping: uniref90_go"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "grouping_type": "large"}) == (
        "HUMAnN utility mapping file is required"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "grouping_type": "custom"}) == (
        "Custom HUMAnN grouping file is required"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genefamilies.tsv", "precision": -1}) == (
        "Precision must be zero or greater"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input": "genefamilies.tsv", "grouping_type": "custom", "custom": "map.tsv", "precision": 0}
    ) is True


def test_humann_rename_table_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_rename_table"]

    assert info["display_name"] == "HUMAnN Rename Table"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Attach readable names to HUMAnN gene, pathway, or regrouped feature IDs."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_rename_table",
        "Rename features",
        "feature names",
        "MetaCyc reactions",
        "UniRef90 name",
        "custom mapping",
        "NO_NAME",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_rename_table"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "HUMAnN gene, pathway, or regrouped feature table"
    assert info["input"]["optional"]["renaming_type"][1]["default"] == "standard"
    assert info["input"]["optional"]["renaming_type"][1]["options"] == ["standard", "advanced", "custom"]
    assert info["input"]["optional"]["names"][1]["default"] == "metacyc-rxn"
    assert info["input"]["optional"]["names"][1]["options"] == [
        "metacyc-rxn",
        "metacyc-pwy",
        "infogo1000",
        "kegg-module",
        "ec",
        "go",
        "pfam",
        "eggnog",
        "kegg-pathway",
        "kegg-orthology",
    ]
    assert info["input"]["optional"]["advanced_names"][0] == "FILE"
    assert info["input"]["optional"]["custom"][0] == "TSV"
    assert info["input"]["optional"]["simplify"][1]["default"] is False
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_rename_table_renders_standard_advanced_and_custom_commands(tmp_path: Path) -> None:
    node_class = _node_class("humann_rename_table")

    assert node_class.render_command(
        {
            "input": "regrouped gene families.tsv",
            "output": "/work/humann_rename_table",
        }
    ) == (
        "humann_rename_table --input 'regrouped gene families.tsv' "
        "-o /work/humann_rename_table/renamed_table.tsv --names metacyc-rxn"
    )

    assert node_class.render_command(
        {
            "input": "demo_genefamilies.tsv",
            "renaming_type": "advanced",
            "advanced_names": "utility_mapping-full-map_uniref90_name-3.0.0-29042021",
            "simplify": True,
            "output": "/work/humann_rename_table",
        }
    ) == (
        "humann_rename_table --input demo_genefamilies.tsv "
        "-o /work/humann_rename_table/renamed_table.tsv "
        "--custom utility_mapping-full-map_uniref90_name-3.0.0-29042021 --simplify"
    )

    assert node_class.render_command(
        {
            "input": "demo_genefamilies.tsv",
            "renaming_type": "custom",
            "custom": "map uniref90 name.txt",
            "output": "/work/humann_rename_table",
        }
    ) == (
        "humann_rename_table --input demo_genefamilies.tsv "
        "-o /work/humann_rename_table/renamed_table.tsv --custom 'map uniref90 name.txt'"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_rename_table" / "renamed_table.tsv",
    ]


def test_humann_rename_table_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_rename_table")

    assert node_class.VALIDATE_INPUTS({}) == "HUMAnN feature table is required"
    assert node_class.VALIDATE_INPUTS({"input": "features.tsv", "renaming_type": "database"}) == (
        "Unsupported HUMAnN renaming type: database"
    )
    assert node_class.VALIDATE_INPUTS({"input": "features.tsv", "names": "uniref90"}) == (
        "Unsupported HUMAnN built-in name map: uniref90"
    )
    assert node_class.VALIDATE_INPUTS({"input": "features.tsv", "renaming_type": "advanced"}) == (
        "HUMAnN utility name mapping file is required"
    )
    assert node_class.VALIDATE_INPUTS({"input": "features.tsv", "renaming_type": "custom"}) == (
        "Custom HUMAnN name mapping file is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input": "features.tsv", "renaming_type": "custom", "custom": "names.tsv"}
    ) is True


def test_humann_unpack_pathways_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_unpack_pathways"]

    assert info["display_name"] == "HUMAnN Unpack Pathways"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Add gene-family or EC abundance stratification to HUMAnN pathway abundance tables."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_unpack_pathways",
        "Unpack pathway abundances",
        "pathway abundance",
        "gene family abundance",
        "EC abundance",
        "reaction mapping",
        "remove taxonomy",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert info["required_executables"] == ["humann_unpack_pathways"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input_genes"][0] == "TSV"
    assert info["input"]["required"]["input_genes"][1]["description"] == "HUMAnN gene family or EC abundance table"
    assert info["input"]["required"]["input_pathways"][0] == "TSV"
    assert info["input"]["required"]["input_pathways"][1]["description"] == "HUMAnN pathway abundance table"
    assert info["input"]["optional"]["gene_mapping"][0] == "TSV"
    assert info["input"]["optional"]["gene_mapping"][1]["default"] == ""
    assert info["input"]["optional"]["pathway_mapping"][0] == "TSV"
    assert info["input"]["optional"]["pathway_mapping"][1]["default"] == ""
    assert info["input"]["optional"]["remove_taxonomy"][1]["default"] is False
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_unpack_pathways_renders_default_and_mapping_commands(tmp_path: Path) -> None:
    node_class = _node_class("humann_unpack_pathways")

    assert node_class.render_command(
        {
            "input_genes": "demo genefamilies.tsv",
            "input_pathways": "demo_pathabundance.tsv",
            "output": "/work/humann_unpack_pathways",
        }
    ) == (
        "humann_unpack_pathways --input-genes 'demo genefamilies.tsv' "
        "--input-pathways demo_pathabundance.tsv "
        "--output /work/humann_unpack_pathways/unpacked_pathways.tsv"
    )

    assert node_class.render_command(
        {
            "input_genes": "demo_genefamilies.tsv",
            "input_pathways": "demo_pathabundance.tsv",
            "gene_mapping": "gene to reaction.tsv",
            "pathway_mapping": "reaction to pathway.tsv",
            "remove_taxonomy": True,
            "output": "/work/humann_unpack_pathways",
        }
    ) == (
        "humann_unpack_pathways --input-genes demo_genefamilies.tsv "
        "--input-pathways demo_pathabundance.tsv --gene-mapping 'gene to reaction.tsv' "
        "--pathway-mapping 'reaction to pathway.tsv' --remove-taxonomy "
        "--output /work/humann_unpack_pathways/unpacked_pathways.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "humann_unpack_pathways" / "unpacked_pathways.tsv",
    ]


def test_humann_unpack_pathways_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_unpack_pathways")

    assert node_class.VALIDATE_INPUTS({}) == "HUMAnN gene family or EC abundance table is required"
    assert node_class.VALIDATE_INPUTS({"input_genes": "genes.tsv"}) == (
        "HUMAnN pathway abundance table is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_genes": "genes.tsv", "input_pathways": "pathways.tsv"}
    ) is True


def test_humann_barplot_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["humann_barplot"]

    assert info["display_name"] == "HUMAnN Barplot"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Plot a single stratified HUMAnN feature across samples."
    assert info["search_aliases"] == [
        "Galaxy",
        "HUMAnN",
        "humann_barplot",
        "Barplot",
        "stratified HUMAnN features",
        "focal feature",
        "top taxa",
        "Bray-Curtis",
        "metadata sorting",
    ]
    assert info["version"] == "3.9"
    assert info["output"] == ["IMAGE"]
    assert info["output_name"] == ["barplot"]
    assert info["required_executables"] == ["humann_barplot"]
    assert info["required_conda_packages"] == ["humann"]
    assert info["documentation_url"] == "https://huttenhower.sph.harvard.edu/humann/"
    assert info["citation_dois"] == ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    assert info["citation_text"] == (
        "bioBakery 3: a platform for analyzing meta'omic datasets; "
        "HUMAnN: the HMP Unified Metabolic Analysis Network."
    )

    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["input"][1]["description"] == "HUMAnN table with optional metadata"
    assert info["input"]["required"]["focal_feature"][0] == "STRING"
    assert info["input"]["required"]["focal_feature"][1]["description"] == "Feature ID of interest"
    assert info["input"]["optional"]["last_metadata"][1]["default"] == ""
    assert info["input"]["optional"]["top_taxa"][1]["default"] == 18
    assert info["input"]["optional"]["sort"][1]["default"] == ["none"]
    assert info["input"]["optional"]["sort"][1]["multiple"] is True
    assert info["input"]["optional"]["sort"][1]["options"] == [
        "none",
        "sum",
        "dominant",
        "braycurtis",
        "braycurtis_w",
        "metadata",
    ]
    assert info["input"]["optional"]["scaling"][1]["options"] == ["original", "logstack", "totalsum"]
    assert info["input"]["optional"]["no_grid"][1]["default"] is True
    assert info["input"]["optional"]["height"][1]["default"] == 11.0
    assert info["input"]["optional"]["width"][1]["default"] == 6.0
    assert info["input"]["optional"]["format"][1]["default"] == "pdf"
    assert info["input"]["optional"]["format"][1]["options"] == ["pdf", "png", "svg"]
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_humann_barplot_renders_default_and_configured_commands(tmp_path: Path) -> None:
    node_class = _node_class("humann_barplot")

    assert node_class.render_command(
        {
            "input": "hmp pathabund.tsv",
            "focal_feature": "ANAGLYCOLYSIS-PWY",
            "output": "/work/humann_barplot",
        }
    ) == (
        "humann_barplot --input 'hmp pathabund.tsv' --focal-feature ANAGLYCOLYSIS-PWY "
        "--top-taxa 18 --sort none --max-metalevels 7 --scaling original --no-grid "
        "--dimensions 11.0 6.0 --legend-cols 3 --legend-rows 10 --legend-height 1.0 "
        "--output /work/humann_barplot/output.pdf"
    )

    assert node_class.render_command(
        {
            "input": "hmp_pathabund.txt",
            "last_metadata": "STSite",
            "focal_feature": "ANAGLYCOLYSIS-PWY",
            "top_taxa": 12,
            "as_genera": True,
            "exclude_unclassified": True,
            "remove_zeros": True,
            "sort": ["brawcurtis", "metadata"],
            "taxa_colormap": "tab20",
            "focal_metadata": "STSite",
            "meta_colormap": "Set2",
            "max_metalevels": 5,
            "scaling": "logstack",
            "ymin": 0,
            "ymax": 100,
            "no_grid": False,
            "height": 8,
            "width": 4,
            "units": "CPM",
            "legend_cols": 2,
            "legend_rows": 8,
            "legend_height": 0.75,
            "format": "svg",
            "output": "/work/humann_barplot",
        }
    ) == (
        "humann_barplot --input hmp_pathabund.txt --last-metadata STSite "
        "--focal-feature ANAGLYCOLYSIS-PWY --top-taxa 12 --as-genera "
        "--exclude-unclassified --remove-zeros --sort braycurtis metadata "
        "--taxa-colormap tab20 --focal-metadata STSite --meta-colormap Set2 "
        "--max-metalevels 5 --scaling logstack --ylims 0 100 --dimensions 8 4 "
        "--units CPM --legend-cols 2 --legend-rows 8 --legend-height 0.75 "
        "--output /work/humann_barplot/output.svg"
    )

    assert node_class.PLAN_OUTPUTS({"format": "png"}, tmp_path) == [
        tmp_path / "humann_barplot" / "output.png",
    ]


def test_humann_barplot_validates_wrapper_inputs() -> None:
    node_class = _node_class("humann_barplot")

    assert node_class.VALIDATE_INPUTS({}) == "HUMAnN table is required"
    assert node_class.VALIDATE_INPUTS({"input": "pathabund.tsv"}) == "HUMAnN focal feature is required"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "sort": ["file"]}
    ) == "Unsupported HUMAnN barplot sort method: file"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "sort": ["braycurtis"]}
    ) == "HUMAnN Bray-Curtis sorting requires remove_zeros"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "scaling": "sqrt"}
    ) == "Unsupported HUMAnN barplot scaling: sqrt"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "format": "jpg"}
    ) == "Unsupported HUMAnN barplot output format: jpg"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "top_taxa": -1}
    ) == "Top taxa must be zero or greater"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "top_taxa": 1.5}
    ) == "Top taxa must be zero or greater"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "height": 0}
    ) == "Plot height must be greater than zero"
    assert node_class.VALIDATE_INPUTS(
        {"input": "pathabund.tsv", "focal_feature": "PWY", "ymin": 0}
    ) == "Both y-axis limits are required when setting y-axis limits"
    assert node_class.VALIDATE_INPUTS(
        {
            "input": "pathabund.tsv",
            "focal_feature": "PWY",
            "sort": ["braycurtis_w"],
            "remove_zeros": True,
        }
    ) is True


def test_hybpiper_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hybpiper"]

    assert info["display_name"] == "HybPiper"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Analyse targeted sequence capture data with HybPiper."
    assert info["search_aliases"] == [
        "Galaxy",
        "HybPiper",
        "targeted sequence capture",
        "target loci assembly",
        "check targetfile",
        "fix targetfile",
        "retrieve sequences",
        "recovery heatmap",
        "paralog warnings",
    ]
    assert info["version"] == "2.1.6"
    assert info["output"] == [
        "FASTA",
        "TEXT",
        "TSV",
        "FILE",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "TEXT",
    ]
    assert info["output_name"] == [
        "fixed_targetfile",
        "targetfile_ctl_file",
        "targetfile_report",
        "hybpiper_archive",
        "hybpiper_stats",
        "hybpiper_heatmaps",
        "dna_sequences",
        "aa_sequences",
        "intron_sequences",
        "supercontig_sequences",
        "dummy_output",
    ]
    assert info["required_executables"] == ["hybpiper"]
    assert info["required_conda_packages"] == ["hybpiper"]
    assert info["documentation_url"] == "https://github.com/mossmatters/HybPiper"
    assert info["citation_dois"] == ["10.3732/apps.1600016"]
    assert info["citation_urls"] == ["https://doi.org/10.3732/apps.1600016"]
    assert info["citation_text"] == (
        "HybPiper: Extracting coding sequence and introns for phylogenetics from "
        "high-throughput sequencing reads using target enrichment."
    )

    assert info["input"]["required"]["targetfile_dna"][0] == "FASTA"
    assert info["input"]["optional"]["hybpiper_job"][1]["default"] == "assemble"
    assert info["input"]["optional"]["hybpiper_job"][1]["options"] == [
        "check_and_fix_targetfile",
        "assemble",
        "stats",
    ]
    assert info["input"]["optional"]["paired_forward"][0] == "FASTQ"
    assert info["input"]["optional"]["paired_reverse"][0] == "FASTQ"
    assert info["input"]["optional"]["sample_name"][0] == "STRING"
    assert info["input"]["optional"]["hybpiper_results"][0] == "FILE"
    assert info["input"]["optional"]["hybpiper_results"][1]["multiple"] is True
    assert info["input"]["optional"]["sample_names"][1]["multiple"] is True
    assert info["input"]["optional"]["stats_type_select"][1]["default"] == ["gene"]
    assert info["input"]["optional"]["stats_type_select"][1]["options"] == ["gene", "supercontig"]
    assert info["input"]["optional"]["heatmap"][1]["default"] is False
    assert info["input"]["optional"]["sequence_type_select"][1]["default"] == ["dna"]
    assert info["input"]["optional"]["sequence_type_select"][1]["options"] == [
        "dna",
        "aa",
        "intron",
        "supercontig",
    ]
    assert info["input"]["hidden"]["output"][0] == "STRING"


def test_hybpiper_renders_check_fix_and_assemble_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hybpiper")

    assert node_class.render_command(
        {
            "targetfile_dna": "targets/test targets.fasta.gz",
            "hybpiper_job": "check_and_fix_targetfile",
            "output": "/work/hybpiper",
        }
    ) == (
        "ln -s 'targets/test targets.fasta.gz' ./target_file.fasta && "
        "hybpiper check_targetfile --targetfile_dna target_file.fasta && "
        "mv fix_targetfile*.ctl hybpiper.ctl && "
        "hybpiper fix_targetfile --targetfile_dna target_file.fasta --allow_gene_removal hybpiper.ctl"
    )

    assert node_class.PLAN_OUTPUTS({"hybpiper_job": "check_and_fix_targetfile"}, tmp_path) == [
        tmp_path / "hybpiper" / "target_file_fixed.fasta",
        tmp_path / "hybpiper" / "hybpiper.ctl",
        tmp_path / "hybpiper" / "fix_targetfile_report.tsv",
    ]

    assert node_class.render_command(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "assemble",
            "paired_forward": "reads/NZ874_R1.fastq.gz",
            "paired_reverse": "reads/NZ874_R2.fastq.gz",
            "sample_name": "NZ874",
            "threads": 12,
            "output": "/work/hybpiper",
        }
    ) == (
        "ln -s targets.fasta ./target_file.fasta && "
        "hybpiper assemble --readfiles reads/NZ874_R1.fastq.gz reads/NZ874_R2.fastq.gz "
        "--targetfile_dna target_file.fasta --diamond --cpu 12 --prefix NZ874 && "
        "tar -cvf /work/hybpiper/hybpiper_archive.tar --directory=NZ874 ."
    )

    assert node_class.PLAN_OUTPUTS({"hybpiper_job": "assemble"}, tmp_path) == [
        tmp_path / "hybpiper" / "hybpiper_archive.tar",
    ]


def test_hybpiper_renders_stats_command_and_dynamic_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hybpiper")

    assert node_class.render_command(
        {
            "targetfile_dna": "test_targets.fasta.gz",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz", "sample two.tar"],
            "sample_names": ["NZ874", "sample-two"],
            "stats_type_select": ["gene", "supercontig"],
            "heatmap": True,
            "sequence_type_select": ["dna", "aa", "intron", "supercontig"],
            "output": "/work/hybpiper",
        }
    ) == (
        "ln -s test_targets.fasta.gz ./target_file.fasta && "
        "mkdir -p NZ874 && tar -xf NZ874.tar.gz -C NZ874 && echo NZ874 >> namelist.txt && "
        "mkdir -p sample-two && tar -xf 'sample two.tar' -C sample-two && echo sample-two >> namelist.txt && "
        "hybpiper stats --targetfile_dna target_file.fasta --stats_filename stats.gene "
        "--seq_lengths_filename seq_lengths.gene gene namelist.txt && "
        "hybpiper recovery_heatmap --heatmap_filename heatmap.gene --heatmap_filetype svg "
        "seq_lengths.gene.tsv && "
        "hybpiper stats --targetfile_dna target_file.fasta --stats_filename stats.supercontig "
        "--seq_lengths_filename seq_lengths.supercontig supercontig namelist.txt && "
        "hybpiper recovery_heatmap --heatmap_filename heatmap.supercontig --heatmap_filetype svg "
        "seq_lengths.supercontig.tsv && "
        "mkdir fasta.dna && hybpiper retrieve_sequences --targetfile_dna target_file.fasta "
        "--sample_names namelist.txt --fasta_dir fasta.dna dna && "
        "mkdir fasta.aa && hybpiper retrieve_sequences --targetfile_dna target_file.fasta "
        "--sample_names namelist.txt --fasta_dir fasta.aa aa && "
        "mkdir fasta.intron && hybpiper retrieve_sequences --targetfile_dna target_file.fasta "
        "--sample_names namelist.txt --fasta_dir fasta.intron intron && "
        "mkdir fasta.supercontig && hybpiper retrieve_sequences --targetfile_dna target_file.fasta "
        "--sample_names namelist.txt --fasta_dir fasta.supercontig supercontig && "
        "mkdir -p /work/hybpiper/hybpiper_stats && "
        "cp stats.gene.tsv /work/hybpiper/hybpiper_stats/stats.gene.tsv && "
        "cp seq_lengths.gene.tsv /work/hybpiper/hybpiper_stats/seq_lengths.gene.tsv && "
        "cp stats.supercontig.tsv /work/hybpiper/hybpiper_stats/stats.supercontig.tsv && "
        "cp seq_lengths.supercontig.tsv /work/hybpiper/hybpiper_stats/seq_lengths.supercontig.tsv && "
        "mkdir -p /work/hybpiper/hybpiper_heatmaps && "
        "cp heatmap.gene.svg /work/hybpiper/hybpiper_heatmaps/heatmap.gene.svg && "
        "cp heatmap.supercontig.svg /work/hybpiper/hybpiper_heatmaps/heatmap.supercontig.svg && "
        "cp -r fasta.dna /work/hybpiper/dna_sequences && "
        "cp -r fasta.aa /work/hybpiper/aa_sequences && "
        "cp -r fasta.intron /work/hybpiper/intron_sequences && "
        "cp -r fasta.supercontig /work/hybpiper/supercontig_sequences"
    )

    assert node_class.PLAN_OUTPUTS(
        {
            "hybpiper_job": "stats",
            "stats_type_select": ["gene", "supercontig"],
            "heatmap": True,
            "sequence_type_select": ["dna", "aa", "intron", "supercontig"],
        },
        tmp_path,
    ) == [
        tmp_path / "hybpiper" / "hybpiper_stats",
        tmp_path / "hybpiper" / "hybpiper_heatmaps",
        tmp_path / "hybpiper" / "dna_sequences",
        tmp_path / "hybpiper" / "aa_sequences",
        tmp_path / "hybpiper" / "intron_sequences",
        tmp_path / "hybpiper" / "supercontig_sequences",
    ]


def test_hybpiper_validates_wrapper_inputs() -> None:
    node_class = _node_class("hybpiper")

    assert node_class.VALIDATE_INPUTS({}) == "HybPiper target FASTA is required"
    assert node_class.VALIDATE_INPUTS({"targetfile_dna": "targets.fasta", "hybpiper_job": "download"}) == (
        "Unsupported HybPiper job: download"
    )
    assert node_class.VALIDATE_INPUTS(
        {"targetfile_dna": "targets.fasta", "hybpiper_job": "assemble", "paired_forward": "R1.fastq"}
    ) == "HybPiper assemble requires paired forward and reverse reads"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "assemble",
            "paired_forward": "R1.fastq",
            "paired_reverse": "R2.fastq",
            "sample_name": "NZ 874",
        }
    ) == "HybPiper sample identifiers may only contain letters, numbers, underscores, and hyphens"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": [],
        }
    ) == "At least one HybPiper assemble archive is required"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz"],
            "sample_names": ["NZ 874"],
        }
    ) == "HybPiper sample identifiers may only contain letters, numbers, underscores, and hyphens"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz"],
            "stats_type_select": [],
            "sequence_type_select": [],
        }
    ) == "At least one HybPiper statistics or sequence output must be selected"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz"],
            "stats_type_select": [],
            "heatmap": True,
            "sequence_type_select": ["dna"],
        }
    ) == "HybPiper heatmap requires at least one statistics output"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz"],
            "stats_type_select": ["gene", "exon"],
        }
    ) == "Unsupported HybPiper statistics output: exon"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "stats",
            "hybpiper_results": ["NZ874.tar.gz"],
            "sequence_type_select": ["dna", "protein"],
        }
    ) == "Unsupported HybPiper sequence output: protein"
    assert node_class.VALIDATE_INPUTS(
        {
            "targetfile_dna": "targets.fasta",
            "hybpiper_job": "assemble",
            "paired_forward": "R1.fastq",
            "paired_reverse": "R2.fastq",
            "sample_name": "NZ874",
        }
    ) is True


def test_hyphy_absrel_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_absrel"]

    assert info["display_name"] == "HyPhy-aBSREL"
    assert info["category"] == "phylogeny"
    assert info["description"] == (
        "Detect episodic diversifying selection with adaptive Branch-Site Random Effects Likelihood."
    )
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "aBSREL",
        "adaptive branch-site random effects likelihood",
        "episodic diversifying selection",
        "selection",
        "phylogenetics",
    ]
    assert info["output"] == ["TEXT", "JSON"]
    assert info["output_name"] == ["absrel_md_report", "absrel_output"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://www.hyphy.org/methods/selection-methods/#absrel"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msv022"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msv022",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Less Is More: an adaptive branch-site random effects model for efficient detection of "
        "episodic diversifying selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["gencodeid"][1]["options"] == [
        "Universal",
        "Vertebrate-mtDNA",
        "Yeast-mtDNA",
        "Mold-Protozoan-mtDNA",
        "Invertebrate-mtDNA",
        "Ciliate-Nuclear",
        "Echinoderm-mtDNA",
        "Euplotid-Nuclear",
        "Alt-Yeast-Nuclear",
        "Ascidian-mtDNA",
        "Flatworm-mtDNA",
        "Blepharisma-Nuclear",
        "Chlorophycean-mtDNA",
        "Trematode-mtDNA",
        "Scenedesmus-obliquus-mtDNA",
        "Thraustochytrium-mtDNA",
        "Pterobranchia-mtDNA",
        "SR1-and-Gracilibacteria",
        "Pachysolen-Nuclear",
        "Mesodinium-Nuclear",
        "Peritrich-Nuclear",
        "Cephalodiscidae-mtDNA",
    ]
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["multiple_hits"][1]["default"] == "None"
    assert info["input"]["optional"]["multiple_hits"][1]["options"] == ["None", "Double", "Double+Triple"]
    assert info["input"]["optional"]["srv_enabled"][1]["default"] is True
    assert info["input"]["optional"]["syn_rates"][1]["default"] == 3
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]


def test_hyphy_absrel_renders_default_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_absrel")

    assert node_class.render_command(
        {
            "input_file": "absrel-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "absrel-in1.nhx",
            "output": "/work/hyphy_absrel",
        }
    ) == (
        "ln -s absrel-in1.nhx input.nhx && "
        "ln -s absrel-in1.fa input.fasta && "
        "ln -s /work/hyphy_absrel/absrel_output.json input.fasta.aBSREL.json && "
        "hyphy CPU=4 absrel --alignment ./input.fasta --tree input.nhx --code Universal "
        "--branches All --output /work/hyphy_absrel/absrel_output.json --multiple-hits None "
        "--srv Yes --syn-rates 3 --blb 1.0 --kill-zero-lengths Yes > /work/hyphy_absrel/absrel_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_absrel" / "absrel_stdout.md",
        tmp_path / "hyphy_absrel" / "absrel_output.json",
    ]


def test_hyphy_absrel_renders_custom_branch_command_without_tree_or_srv() -> None:
    node_class = _node_class("hyphy_absrel")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "multiple_hits": "Double+Triple",
            "srv_enabled": False,
            "blb": 0.5,
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_absrel",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        "ln -s /work/hyphy_absrel/absrel_output.json input.nex.aBSREL.json && "
        "hyphy CPU=8 absrel --alignment ./input.nex --code Vertebrate-mtDNA "
        "--branches 'Foreground clade' --output /work/hyphy_absrel/absrel_output.json "
        "--multiple-hits Double+Triple --blb 0.5 --kill-zero-lengths Constrain "
        "> /work/hyphy_absrel/absrel_stdout.md"
    )
    assert "--tree" not in command
    assert "--srv" not in command
    assert "--syn-rates" not in command


def test_hyphy_absrel_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_absrel")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-aBSREL alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-aBSREL branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-aBSREL custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "multiple_hits": "Triple"}) == (
        "Unsupported HyPhy-aBSREL multiple-hits mode: Triple"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "srv_enabled": True, "syn_rates": 0}) == (
        "HyPhy-aBSREL synonymous rate classes must be between 1 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-aBSREL zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-aBSREL threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "blb": -0.1}) == (
        "HyPhy-aBSREL BLB resampling value must be non-negative"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "branch_sel": "specify",
            "branch_label": "Foreground",
            "gencodeid": "Universal",
            "multiple_hits": "Double",
            "srv_enabled": True,
            "syn_rates": 3,
            "kill_zero_lengths": "Yes",
            "threads": 4,
            "blb": 1.0,
        }
    ) is True


def test_hyphy_annotate_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_annotate"]

    assert info["display_name"] == "HyPhy Annotate"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Annotate a Newick/NHX phylogenetic tree with HyPhy label-tree."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "label-tree",
        "Annotate",
        "Newick annotation",
        "branch labels",
        "phylogenetic tree annotation",
    ]
    assert info["output"] == ["PHYLOGENY_TREE", "TEXT"]
    assert info["output_name"] == ["labeled_tree", "annotate_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/lib/label-tree.bf"
    assert info["citation_dois"] == ["10.1093/molbev/msz197"]
    assert info["citation_urls"] == ["https://doi.org/10.1093/molbev/msz197"]
    assert info["citation_text"] == "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies."
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_tree"][0] == "STRING"
    assert info["input"]["required"]["selection_method"][1]["default"] == "regexp"
    assert info["input"]["required"]["selection_method"][1]["options"] == ["regexp", "list"]
    assert info["input"]["optional"]["regexp"][0] == "STRING"
    assert info["input"]["optional"]["list_file"][0] == "FILE"
    assert info["input"]["optional"]["label"][1]["default"] == "Foreground"
    assert info["input"]["optional"]["reroot"][1]["default"] == "None"
    assert info["input"]["optional"]["invert"][1]["default"] is False
    assert info["input"]["optional"]["internal_nodes"][1]["default"] == "All descendants"
    assert info["input"]["optional"]["internal_nodes"][1]["options"] == [
        "All descendants",
        "None",
        "All descendants, no MRCA",
        "Some descendants",
        "Parsimony",
    ]
    assert info["input"]["optional"]["leaf_nodes"][1]["default"] == "Label"
    assert info["input"]["optional"]["leaf_nodes"][1]["options"] == ["Label", "Skip"]


def test_hyphy_annotate_renders_regexp_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_annotate")

    assert node_class.render_command(
        {
            "input_tree": "annotate-in1.nhx",
            "selection_method": "regexp",
            "regexp": "_USA_",
            "label": "Annotated",
            "reroot": "None",
            "invert": False,
            "internal_nodes": "All descendants",
            "leaf_nodes": "Label",
            "output": "/work/hyphy_annotate",
        }
    ) == (
        "cp annotate-in1.nhx input.nhx && "
        "hyphy label-tree --tree input.nhx --output /work/hyphy_annotate/labeled_tree.nhx "
        "--regexp _USA_ --label Annotated --reroot None --invert No "
        "--internal-nodes 'All descendants' --leaf-nodes Label "
        "> /work/hyphy_annotate/annotate_stdout.md 2>/dev/null"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_annotate" / "labeled_tree.nhx",
        tmp_path / "hyphy_annotate" / "annotate_stdout.md",
    ]


def test_hyphy_annotate_renders_list_command_with_inverted_selection() -> None:
    node_class = _node_class("hyphy_annotate")

    assert node_class.render_command(
        {
            "input_tree": "trees/input tree.nhx",
            "selection_method": "list",
            "list_file": "annotate-list1.txt",
            "label": "Foreground clade",
            "reroot": "gb_MW540268",
            "invert": True,
            "internal_nodes": "Parsimony",
            "leaf_nodes": "Skip",
            "output": "/work/hyphy_annotate",
        }
    ) == (
        "cp 'trees/input tree.nhx' input.nhx && "
        "hyphy label-tree --tree input.nhx --output /work/hyphy_annotate/labeled_tree.nhx "
        "--list annotate-list1.txt --label 'Foreground clade' --reroot gb_MW540268 --invert Yes "
        "--internal-nodes Parsimony --leaf-nodes Skip "
        "> /work/hyphy_annotate/annotate_stdout.md 2>/dev/null"
    )


def test_hyphy_annotate_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_annotate")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy Annotate input tree is required"
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.nhx", "selection_method": "regexp"}) == (
        "HyPhy Annotate regular expression is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.nhx", "selection_method": "list"}) == (
        "HyPhy Annotate sequence list file is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.nhx", "selection_method": "manual"}) == (
        "Unsupported HyPhy Annotate selection method: manual"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_tree": "tree.nhx", "selection_method": "regexp", "regexp": "bad\\"}
    ) == "HyPhy Annotate regular expression must not end with a backslash"
    assert node_class.VALIDATE_INPUTS(
        {"input_tree": "tree.nhx", "selection_method": "regexp", "regexp": "_USA_", "label": ""}
    ) == "HyPhy Annotate label is required"
    assert node_class.VALIDATE_INPUTS(
        {"input_tree": "tree.nhx", "selection_method": "regexp", "regexp": "_USA_", "internal_nodes": "Everywhere"}
    ) == "Unsupported HyPhy Annotate internal-node strategy: Everywhere"
    assert node_class.VALIDATE_INPUTS(
        {"input_tree": "tree.nhx", "selection_method": "regexp", "regexp": "_USA_", "leaf_nodes": "Maybe"}
    ) == "Unsupported HyPhy Annotate leaf-node strategy: Maybe"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_tree": "tree.nhx",
            "selection_method": "list",
            "list_file": "names.txt",
            "label": "Annotated",
            "reroot": "None",
            "internal_nodes": "Some descendants",
            "leaf_nodes": "Skip",
        }
    ) is True


def test_hyphy_b_still_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_b_still"]

    assert info["display_name"] == "HyPhy-B-STILL"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect invariant or near-invariant codon sites with HyPhy B-STILL."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "B-STILL",
        "Bayesian Significance Test of Invariant Low Likelihoods",
        "FUBAR",
        "invariant sites",
        "purifying selection",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["b_still_output", "b_still_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == (
        "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/SelectionAnalyses/B-STILL.bf"
    )
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/mst030"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/mst030",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["method"][1]["default"] == "Variational-Bayes"
    assert info["input"]["optional"]["method"][1]["options"] == [
        "Variational-Bayes",
        "Metropolis-Hastings",
        "Collapsed-Gibbs",
    ]
    assert info["input"]["optional"]["grid"][1]["default"] == 20
    assert info["input"]["optional"]["concentration_parameter"][1]["default"] == 0.5
    assert info["input"]["optional"]["non_zero"][1]["default"] is False
    assert info["input"]["optional"]["ebf"][1]["default"] == 10.0
    assert info["input"]["optional"]["radius_threshold"][1]["default"] == 0.5
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["chains"][1]["default"] == 5
    assert info["input"]["optional"]["chain_length"][1]["default"] == 2000000
    assert info["input"]["optional"]["burn_in"][1]["default"] == 1000000
    assert info["input"]["optional"]["samples"][1]["default"] == 100


def test_hyphy_b_still_renders_default_variational_bayes_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_b_still")

    assert node_class.render_command(
        {
            "input_file": "fubar-in1.fa.gz",
            "input_ext": "fasta.gz",
            "input_nhx": "fubar-in1.nhx",
            "output": "/work/hyphy_b_still",
        }
    ) == (
        "ln -s fubar-in1.nhx input.nhx && "
        "ln -s fubar-in1.fa.gz input.fasta.gz && "
        "hyphy b-still --alignment ./input.fasta.gz --tree input.nhx --code Universal "
        "--method Variational-Bayes --grid 20 --concentration_parameter 0.5 "
        "--non-zero No --ebf 10.0 --radius-threshold 0.5 --kill-zero-lengths Yes "
        "--output /work/hyphy_b_still/b_still_output.json "
        "> /work/hyphy_b_still/b_still_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_b_still" / "b_still_output.json",
        tmp_path / "hyphy_b_still" / "b_still_stdout.md",
    ]


def test_hyphy_b_still_renders_collapsed_gibbs_command_without_tree() -> None:
    node_class = _node_class("hyphy_b_still")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "method": "Collapsed-Gibbs",
            "chains": 7,
            "chain_length": 3000000,
            "burn_in": 1200000,
            "samples": 250,
            "grid": 35,
            "concentration_parameter": 0.75,
            "non_zero": True,
            "ebf": 25,
            "radius_threshold": 0.75,
            "kill_zero_lengths": "Constrain",
            "output": "/work/hyphy_b_still",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        "hyphy b-still --alignment ./input.nex --code Vertebrate-mtDNA "
        "--method Collapsed-Gibbs --chains 7 --chain-length 3000000 "
        "--burn-in 1200000 --samples 250 --grid 35 --concentration_parameter 0.75 "
        "--non-zero Yes --ebf 25 --radius-threshold 0.75 --kill-zero-lengths Constrain "
        "--output /work/hyphy_b_still/b_still_output.json "
        "> /work/hyphy_b_still/b_still_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_b_still_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_b_still")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-B-STILL alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Bootstrap"}) == (
        "Unsupported HyPhy-B-STILL posterior estimation method: Bootstrap"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid": 4}) == (
        "HyPhy-B-STILL grid points must be between 5 and 50"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid": 51}) == (
        "HyPhy-B-STILL grid points must be between 5 and 50"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "concentration_parameter": 0}) == (
        "HyPhy-B-STILL concentration parameter must be between 0.001 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "ebf": -0.1}) == (
        "HyPhy-B-STILL EBF threshold must be non-negative"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "radius_threshold": 11}) == (
        "HyPhy-B-STILL radius threshold must be between 0 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-B-STILL zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Metropolis-Hastings", "chains": 1}) == (
        "HyPhy-B-STILL chains must be between 2 and 20"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "chain_length": 499999}
    ) == "HyPhy-B-STILL chain length must be between 500000 and 50000000"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Metropolis-Hastings", "burn_in": 99999}
    ) == "HyPhy-B-STILL burn-in samples must be between 100000 and 1900000"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "samples": 49}
    ) == "HyPhy-B-STILL samples per chain must be between 50 and 1000000"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "gencodeid": "Universal",
            "method": "Variational-Bayes",
            "grid": 20,
            "concentration_parameter": 0.5,
            "non_zero": False,
            "ebf": 10,
            "radius_threshold": 0.5,
            "kill_zero_lengths": "Yes",
        }
    ) is True


def test_hyphy_bgm_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_bgm"]

    assert info["display_name"] == "HyPhy-BGM"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect coevolving sites in sequence alignments with HyPhy Bayesian graphical models."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "BGM",
        "Bayesian graphical model",
        "Spidermonkey",
        "coevolving sites",
        "correlated substitutions",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["bgm_output", "bgm_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#BGM"
    assert info["citation_dois"] == [
        "10.1093/molbev/msz197",
        "10.1093/bioinformatics/btn313",
        "10.1371/journal.pcbi.0030231",
    ]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/bioinformatics/btn313",
        "https://doi.org/10.1371/journal.pcbi.0030231",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Spidermonkey: rapid detection of co-evolving sites using Bayesian graphical models; "
        "An evolutionary-network model reveals stratified interactions in the V3 loop of the HIV-1 envelope."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Sequence alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["datatype"][1]["default"] == "codon"
    assert info["input"]["optional"]["datatype"][1]["options"] == ["nucleotide", "amino-acid", "codon"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["baseline_model"][1]["default"] == "LG"
    assert info["input"]["optional"]["baseline_model"][1]["options"] == [
        "LG",
        "WAG",
        "JTT",
        "JC69",
        "mtMet",
        "mtVer",
        "mtInv",
        "gcpREV",
        "HIVBm",
        "HIVWm",
        "GTR",
    ]
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["chain_length"][1]["default"] == 100000
    assert info["input"]["optional"]["burn_in"][1]["default"] == 10000
    assert info["input"]["optional"]["samples"][1]["default"] == 100
    assert info["input"]["optional"]["parents"][1]["default"] == 1
    assert info["input"]["optional"]["min_subs"][1]["default"] == 1
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_bgm_renders_default_codon_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_bgm")

    assert node_class.render_command(
        {
            "input_file": "bgm-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "bgm-in1.nhx",
            "output": "/work/hyphy_bgm",
        }
    ) == (
        "ln -s bgm-in1.nhx input.nhx && "
        "ln -s bgm-in1.fa input.fasta && "
        "TOLERATE_NUMERICAL_ERRORS=1 hyphy CPU=4 bgm --alignment ./input.fasta "
        "--tree input.nhx --type codon --code Universal --branches All --steps 100000 "
        "--burn-in 10000 --samples 100 --max-parents 1 --min-subs 1 "
        "--output /work/hyphy_bgm/bgm_output.json > /work/hyphy_bgm/bgm_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_bgm" / "bgm_output.json",
        tmp_path / "hyphy_bgm" / "bgm_stdout.md",
    ]


def test_hyphy_bgm_renders_amino_acid_command_with_custom_branch_without_tree() -> None:
    node_class = _node_class("hyphy_bgm")

    command = node_class.render_command(
        {
            "input_file": "protein alignment.fasta",
            "input_ext": "fasta",
            "datatype": "amino-acid",
            "baseline_model": "WAG",
            "branch_sel": "specify",
            "branch_label": "Compensatory clade",
            "chain_length": 250000,
            "burn_in": 50000,
            "samples": 250,
            "parents": 2,
            "min_subs": 3,
            "threads": 8,
            "output": "/work/hyphy_bgm",
        }
    )

    assert command == (
        "ln -s 'protein alignment.fasta' input.fasta && "
        "TOLERATE_NUMERICAL_ERRORS=1 hyphy CPU=8 bgm --alignment ./input.fasta "
        "--type amino-acid --baseline_model WAG --branches 'Compensatory clade' "
        "--steps 250000 --burn-in 50000 --samples 250 --max-parents 2 --min-subs 3 "
        "--output /work/hyphy_bgm/bgm_output.json > /work/hyphy_bgm/bgm_stdout.md"
    )
    assert "--tree" not in command
    assert "--code" not in command


def test_hyphy_bgm_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_bgm")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-BGM alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "datatype": "rna"}) == (
        "Unsupported HyPhy-BGM data type: rna"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "datatype": "codon", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "datatype": "amino-acid", "baseline_model": "PAM250"}
    ) == "Unsupported HyPhy-BGM amino-acid substitution model: PAM250"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-BGM branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-BGM custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "chain_length": -1}) == (
        "HyPhy-BGM chain length must be between 0 and 1000000000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "burn_in": -1}) == (
        "HyPhy-BGM burn-in must be between 0 and 1000000000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "samples": 0}) == (
        "HyPhy-BGM samples must be between 1 and 100000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "parents": 4}) == (
        "HyPhy-BGM maximum parents must be between 1 and 3"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "min_subs": 0}) == (
        "HyPhy-BGM minimum substitutions must be between 1 and 1000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-BGM threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "datatype": "nucleotide",
            "branch_sel": "Internal",
            "chain_length": 100000,
            "burn_in": 10000,
            "samples": 100,
            "parents": 1,
            "min_subs": 1,
            "threads": 4,
        }
    ) is True


def test_hyphy_fade_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_fade"]

    assert info["display_name"] == "HyPhy-FADE"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Test a protein alignment for directional selection with HyPhy FADE."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "FADE",
        "FUBAR Approach to Directional Evolution",
        "directional selection",
        "protein alignment",
        "amino acid substitution bias",
        "empirical Bayes factor",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["fade_output", "fade_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#FADE"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/mst030"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/mst030",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Protein alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["model"][1]["default"] == "GTR"
    assert info["input"]["optional"]["model"][1]["options"] == [
        "LG",
        "WAG",
        "JTT",
        "JC69",
        "mtMet",
        "mtVer",
        "mtInv",
        "gcpREV",
        "HIVBm",
        "HIVWm",
        "GTR",
    ]
    assert info["input"]["optional"]["method"][1]["default"] == "Variational-Bayes"
    assert info["input"]["optional"]["method"][1]["options"] == [
        "Variational-Bayes",
        "Metropolis-Hastings",
        "Collapsed-Gibbs",
    ]
    assert info["input"]["optional"]["grid"][1]["default"] == 20
    assert info["input"]["optional"]["concentration_parameter"][1]["default"] == 0.5
    assert info["input"]["optional"]["chains"][1]["default"] == 5
    assert info["input"]["optional"]["chain_length"][1]["default"] == 2000000
    assert info["input"]["optional"]["burn_in"][1]["default"] == 1000000
    assert info["input"]["optional"]["samples"][1]["default"] == 100


def test_hyphy_fade_renders_default_variational_bayes_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_fade")

    assert node_class.render_command(
        {
            "input_file": "fade-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "fade-in1.nhx",
            "output": "/work/hyphy_fade",
        }
    ) == (
        "ln -s fade-in1.nhx input.nhx && "
        "ln -s fade-in1.fa input.fasta && "
        "hyphy fade --alignment input.fasta --tree input.nhx --branches All "
        "--model GTR --method Variational-Bayes --grid 20 --concentration_parameter 0.5 "
        "--output /work/hyphy_fade/fade_output.json > /work/hyphy_fade/fade_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_fade" / "fade_output.json",
        tmp_path / "hyphy_fade" / "fade_stdout.md",
    ]


def test_hyphy_fade_renders_mcmc_command_with_custom_branch_without_tree() -> None:
    node_class = _node_class("hyphy_fade")

    command = node_class.render_command(
        {
            "input_file": "protein alignment.nex",
            "input_ext": "nex",
            "branch_sel": "specify",
            "branch_label": "Directional clade",
            "model": "WAG",
            "method": "Metropolis-Hastings",
            "chains": 7,
            "chain_length": 3000000,
            "burn_in": 1200000,
            "samples": 250,
            "grid": 35,
            "concentration_parameter": 0.75,
            "output": "/work/hyphy_fade",
        }
    )

    assert command == (
        "ln -s 'protein alignment.nex' input.nex && "
        "hyphy fade --alignment input.nex --branches 'Directional clade' "
        "--model WAG --method Metropolis-Hastings --chains 7 --chain-length 3000000 "
        "--burn-in 1200000 --samples 250 --grid 35 --concentration_parameter 0.75 "
        "--output /work/hyphy_fade/fade_output.json > /work/hyphy_fade/fade_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_fade_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_fade")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-FADE protein alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-FADE input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-FADE branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-FADE custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "model": "PAM250"}) == (
        "Unsupported HyPhy-FADE amino-acid substitution model: PAM250"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Bootstrap"}) == (
        "Unsupported HyPhy-FADE posterior estimation method: Bootstrap"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid": 4}) == (
        "HyPhy-FADE grid points must be between 5 and 50"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "concentration_parameter": 1.5}) == (
        "HyPhy-FADE concentration parameter must be between 0.001 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Metropolis-Hastings", "chains": 1}) == (
        "HyPhy-FADE chains must be between 2 and 20"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "chain_length": 499999}
    ) == "HyPhy-FADE chain length must be between 500000 and 50000000"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "burn_in": 99999}
    ) == "HyPhy-FADE burn-in samples must be between 100000 and 1900000"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "samples": 49}) == (
        "HyPhy-FADE samples per chain must be between 50 and 1000000"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "branch_sel": "Internal",
            "model": "GTR",
            "method": "Variational-Bayes",
            "grid": 20,
            "concentration_parameter": 0.5,
        }
    ) is True


def test_hyphy_fel_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_fel"]

    assert info["display_name"] == "HyPhy-FEL"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect pervasive site-level selection with HyPhy Fixed Effects Likelihood."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "FEL",
        "Fixed Effects Likelihood",
        "pervasive selection",
        "site-level selection",
        "diversifying selection",
        "purifying selection",
        "synonymous rate variation",
        "multiple nucleotide substitutions",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["fel_output", "fel_md_report"]
    assert info["required_executables"] == ["HYPHYMPI", "mpirun"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#FEL"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msi105"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msi105",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Not So Different After All: A Comparison of Methods for Detecting Amino Acid Sites Under Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["multiple_hits"][1]["default"] == "None"
    assert info["input"]["optional"]["multiple_hits"][1]["options"] == ["None", "Double", "Double+Triple"]
    assert info["input"]["optional"]["site_multihit"][1]["default"] == "Estimate"
    assert info["input"]["optional"]["site_multihit"][1]["options"] == ["Estimate", "No"]
    assert info["input"]["optional"]["srv"][1]["default"] == "Yes"
    assert info["input"]["optional"]["srv"][1]["options"] == ["Yes", "No"]
    assert info["input"]["optional"]["pvalue"][1]["default"] == 0.1
    assert info["input"]["optional"]["ci"][1]["default"] is False
    assert info["input"]["optional"]["resample"][1]["default"] == 0
    assert info["input"]["optional"]["restrict_sites"][1]["default"] is False
    assert info["input"]["optional"]["limit_to_sites"][1]["default"] == "null"
    assert info["input"]["optional"]["save_lf_for_sites"][1]["default"] == "null"
    assert info["input"]["optional"]["precision"][1]["default"] == "standard"
    assert info["input"]["optional"]["precision"][1]["options"] == ["standard", "reduced"]
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["full_model"][1]["default"] is True
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_fel_renders_default_mpi_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_fel")

    assert node_class.render_command(
        {
            "input_file": "absrel-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "absrel-in1.nhx",
            "output": "/work/hyphy_fel",
        }
    ) == (
        "ln -s absrel-in1.nhx input.nhx && "
        "ln -s absrel-in1.fa input.fasta && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI fel --alignment ./input.fasta --tree input.nhx --code Universal "
        "--multiple-hits None --branches All --srv Yes --pvalue 0.1 --precision standard "
        "--output /work/hyphy_fel/fel_output.json --kill-zero-lengths Yes --full-model Yes "
        "> /work/hyphy_fel/fel_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_fel" / "fel_output.json",
        tmp_path / "hyphy_fel" / "fel_stdout.md",
    ]


def test_hyphy_fel_renders_advanced_mpi_command_without_tree() -> None:
    node_class = _node_class("hyphy_fel")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "multiple_hits": "Double+Triple",
            "site_multihit": "No",
            "srv": "No",
            "pvalue": 0.05,
            "ci": True,
            "resample": 25,
            "restrict_sites": True,
            "limit_to_sites": "1,2,3",
            "save_lf_for_sites": "4,5",
            "precision": "reduced",
            "kill_zero_lengths": "Constrain",
            "full_model": False,
            "threads": 8,
            "output": "/work/hyphy_fel",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 8} '
        "HYPHYMPI fel --alignment ./input.nex --code Vertebrate-mtDNA --multiple-hits Double+Triple "
        "--branches 'Foreground clade' --srv No --pvalue 0.05 --resample 25 --limit-to-sites 1,2,3 "
        "--save-lf-for-sites 4,5 --precision reduced --ci Yes --output /work/hyphy_fel/fel_output.json "
        "--site-multihit No --kill-zero-lengths Constrain > /work/hyphy_fel/fel_stdout.md"
    )
    assert "--tree" not in command
    assert "--full-model" not in command


def test_hyphy_fel_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_fel")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-FEL alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-FEL input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-FEL branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-FEL custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "multiple_hits": "Triple"}) == (
        "Unsupported HyPhy-FEL multiple-hits mode: Triple"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "multiple_hits": "Double", "site_multihit": "Global"}
    ) == "Unsupported HyPhy-FEL site-multihit mode: Global"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "srv": "Maybe"}) == (
        "Unsupported HyPhy-FEL synonymous rate variation setting: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "pvalue": 1.1}) == (
        "HyPhy-FEL p-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "resample": 1001}) == (
        "HyPhy-FEL resampling replicates must be between 0 and 1000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "precision": "exact"}) == (
        "Unsupported HyPhy-FEL optimization precision: exact"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-FEL zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-FEL threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "branch_sel": "Internal",
            "multiple_hits": "Double",
            "site_multihit": "Estimate",
            "srv": "Yes",
            "pvalue": 0.1,
            "resample": 0,
            "precision": "standard",
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_fubar_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_fubar"]

    assert info["display_name"] == "HyPhy-FUBAR"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect pervasive site-level selection with HyPhy FUBAR."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "FUBAR",
        "Fast Unconstrained Bayesian AppRoximation",
        "pervasive selection",
        "site-level selection",
        "diversifying selection",
        "purifying selection",
        "posterior probability",
        "empirical Bayes factor",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["fubar_output", "fubar_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#FUBAR"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/mst030"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/mst030",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "FUBAR: A Fast, Unconstrained Bayesian AppRoximation for Inferring Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["method"][1]["default"] == "Variational-Bayes"
    assert info["input"]["optional"]["method"][1]["options"] == [
        "Variational-Bayes",
        "Metropolis-Hastings",
        "Collapsed-Gibbs",
    ]
    assert info["input"]["optional"]["grid"][1]["default"] == 20
    assert info["input"]["optional"]["concentration_parameter"][1]["default"] == 0.5
    assert info["input"]["optional"]["non_zero"][1]["default"] is False
    assert info["input"]["optional"]["chains"][1]["default"] == 5
    assert info["input"]["optional"]["chain_length"][1]["default"] == 2000000
    assert info["input"]["optional"]["burn_in"][1]["default"] == 1000000
    assert info["input"]["optional"]["samples"][1]["default"] == 100
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]


def test_hyphy_fubar_renders_default_variational_bayes_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_fubar")

    assert node_class.render_command(
        {
            "input_file": "fubar-in1.fa.gz",
            "input_ext": "fasta.gz",
            "input_nhx": "fubar-in1.nhx",
            "output": "/work/hyphy_fubar",
        }
    ) == (
        "ln -s fubar-in1.nhx input.nhx && "
        "ln -s fubar-in1.fa.gz input.fasta.gz && "
        "ln -s /work/hyphy_fubar/fubar_output.json input.fasta.gz.FUBAR.json && "
        "hyphy fubar --alignment ./input.fasta.gz --tree input.nhx --code Universal "
        "--method Variational-Bayes --grid 20 --concentration_parameter 0.5 "
        "--non-zero No --kill-zero-lengths Yes > /work/hyphy_fubar/fubar_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_fubar" / "fubar_output.json",
        tmp_path / "hyphy_fubar" / "fubar_stdout.md",
    ]


def test_hyphy_fubar_renders_mcmc_command_without_tree() -> None:
    node_class = _node_class("hyphy_fubar")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "method": "Collapsed-Gibbs",
            "chains": 7,
            "chain_length": 3000000,
            "burn_in": 1200000,
            "samples": 250,
            "grid": 35,
            "concentration_parameter": 0.75,
            "non_zero": True,
            "kill_zero_lengths": "Constrain",
            "output": "/work/hyphy_fubar",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        "ln -s /work/hyphy_fubar/fubar_output.json input.nex.FUBAR.json && "
        "hyphy fubar --alignment ./input.nex --code Vertebrate-mtDNA --method Collapsed-Gibbs "
        "--chains 7 --chain-length 3000000 --burn-in 1200000 --samples 250 "
        "--grid 35 --concentration_parameter 0.75 --non-zero Yes --kill-zero-lengths Constrain "
        "> /work/hyphy_fubar/fubar_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_fubar_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_fubar")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-FUBAR alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-FUBAR input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Bootstrap"}) == (
        "Unsupported HyPhy-FUBAR posterior estimation method: Bootstrap"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid": 4}) == (
        "HyPhy-FUBAR grid points must be between 5 and 50"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "concentration_parameter": 1.5}) == (
        "HyPhy-FUBAR concentration parameter must be between 0.001 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-FUBAR zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Metropolis-Hastings", "chains": 1}) == (
        "HyPhy-FUBAR chains must be between 2 and 20"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "chain_length": 499999}
    ) == "HyPhy-FUBAR chain length must be between 500000 and 50000000"
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "burn_in": 99999}
    ) == "HyPhy-FUBAR burn-in samples must be between 100000 and 1900000"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "method": "Collapsed-Gibbs", "samples": 49}) == (
        "HyPhy-FUBAR samples per chain must be between 50 and 1000000"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "method": "Variational-Bayes",
            "grid": 20,
            "concentration_parameter": 0.5,
            "kill_zero_lengths": "Yes",
        }
    ) is True


def test_hyphy_gard_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_gard"]

    assert info["display_name"] == "HyPhy-GARD"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect recombination breakpoints with HyPhy Genetic Algorithm for Recombination Detection."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "GARD",
        "Genetic Algorithm for Recombination Detection",
        "recombination detection",
        "breakpoints",
        "phylogenetic incongruence",
        "partitioned alignment",
        "site-to-site rate variation",
        "phylogenetics",
    ]
    assert info["output"] == ["ALIGNMENT", "JSON", "TEXT"]
    assert info["output_name"] == ["gard_output", "gard_output_json", "gard_md_report"]
    assert info["required_executables"] == ["HYPHYMPI", "mpirun"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "https://veg.github.io/hyphy-site/methods/gard/"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msl051"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msl051",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Automated Phylogenetic Detection of Recombination Using a Genetic Algorithm."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Sequence alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["datatype"][1]["default"] == "nucleotide"
    assert info["input"]["optional"]["datatype"][1]["options"] == ["nucleotide", "amino-acid", "codon"]
    assert info["input"]["optional"]["model"][1]["default"] == "GTR"
    assert info["input"]["optional"]["model"][1]["options"] == [
        "LG",
        "WAG",
        "JTT",
        "JC69",
        "mtMet",
        "mtVer",
        "mtInv",
        "gcpREV",
        "HIVBm",
        "HIVWm",
        "GTR",
    ]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["rate"][1]["default"] == ""
    assert info["input"]["optional"]["rate"][1]["options"] == ["", "GDD", "Gamma"]
    assert info["input"]["optional"]["rate_classes"][1]["default"] == 2
    assert info["input"]["optional"]["rate_classes"][1]["min"] == 2
    assert info["input"]["optional"]["rate_classes"][1]["max"] == 6
    assert info["input"]["optional"]["max_breakpoints"][1]["default"] == 10000
    assert info["input"]["optional"]["max_breakpoints"][1]["min"] == 1
    assert info["input"]["optional"]["max_breakpoints"][1]["max"] == 10000
    assert info["input"]["optional"]["mode"][1]["default"] == "Normal"
    assert info["input"]["optional"]["mode"][1]["options"] == ["Normal", "Faster"]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_gard_renders_default_nucleotide_mpi_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_gard")

    assert node_class.render_command(
        {
            "input_file": "gard-in1.fa",
            "input_ext": "fasta",
            "output": "/work/hyphy_gard",
        }
    ) == (
        "ln -s gard-in1.fa input.fasta && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI gard --alignment input.fasta --type nucleotide --max-breakpoints 10000 --mode Normal "
        'ENV="TOLERATE_NUMERICAL_ERRORS=1;" --output /work/hyphy_gard/gard_output.json '
        "--output-lf /work/hyphy_gard/gard_output.nex > /work/hyphy_gard/gard_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_gard" / "gard_output.nex",
        tmp_path / "hyphy_gard" / "gard_output.json",
        tmp_path / "hyphy_gard" / "gard_stdout.md",
    ]


def test_hyphy_gard_renders_amino_acid_and_codon_mpi_commands() -> None:
    node_class = _node_class("hyphy_gard")

    amino_command = node_class.render_command(
        {
            "input_file": "protein alignment.nex",
            "input_ext": "nex",
            "datatype": "amino-acid",
            "model": "WAG",
            "rate": "Gamma",
            "rate_classes": 4,
            "max_breakpoints": 500,
            "mode": "Faster",
            "threads": 8,
            "output": "/work/hyphy_gard",
        }
    )
    assert amino_command == (
        "ln -s 'protein alignment.nex' input.nex && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 8} '
        "HYPHYMPI gard --alignment input.nex --type amino-acid --model WAG --rv Gamma --rate-classes 4 "
        "--max-breakpoints 500 --mode Faster "
        'ENV="TOLERATE_NUMERICAL_ERRORS=1;" --output /work/hyphy_gard/gard_output.json '
        "--output-lf /work/hyphy_gard/gard_output.nex > /work/hyphy_gard/gard_stdout.md"
    )
    assert "--code" not in amino_command

    codon_command = node_class.render_command(
        {
            "input_file": "codon alignment.fa.gz",
            "input_ext": "fasta.gz",
            "datatype": "codon",
            "gencodeid": "Vertebrate-mtDNA",
            "rate": "GDD",
            "rate_classes": 6,
            "output": "/work/hyphy_gard",
        }
    )
    assert codon_command == (
        "ln -s 'codon alignment.fa.gz' input.fasta.gz && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI gard --alignment input.fasta.gz --type codon --code Vertebrate-mtDNA "
        "--rv GDD --rate-classes 6 --max-breakpoints 10000 --mode Normal "
        'ENV="TOLERATE_NUMERICAL_ERRORS=1;" --output /work/hyphy_gard/gard_output.json '
        "--output-lf /work/hyphy_gard/gard_output.nex > /work/hyphy_gard/gard_stdout.md"
    )
    assert "--model" not in codon_command


def test_hyphy_gard_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_gard")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-GARD alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-GARD input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "datatype": "rna"}) == (
        "Unsupported HyPhy-GARD data type: rna"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "datatype": "amino-acid", "model": "PAM250"}
    ) == "Unsupported HyPhy-GARD amino-acid substitution model: PAM250"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "datatype": "codon", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "rate": "Beta"}) == (
        "Unsupported HyPhy-GARD rate variation setting: Beta"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "rate": "GDD", "rate_classes": 1}) == (
        "HyPhy-GARD rate classes must be between 2 and 6"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "max_breakpoints": 0}) == (
        "HyPhy-GARD maximum breakpoints must be between 1 and 10000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "mode": "Turbo"}) == (
        "Unsupported HyPhy-GARD run mode: Turbo"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-GARD threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "datatype": "nucleotide",
            "rate": "Gamma",
            "rate_classes": 2,
            "max_breakpoints": 10000,
            "mode": "Normal",
            "threads": 4,
        }
    ) is True


def test_hyphy_infer_stasis_clusters_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_infer_stasis_clusters"]

    assert info["display_name"] == "HyPhy-Infer Stasis Clusters"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Identify regional footprints of extreme purifying selection from B-STILL results."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "B-STILL",
        "Infer Stasis Clusters",
        "stasis clusters",
        "purifying selection",
        "Empirical Bayes Factor",
        "hypergeometric scan statistic",
        "family-wise error rate",
        "protein domains",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["output_json", "output_log"]
    assert info["required_executables"] == ["python3"]
    assert info["required_conda_packages"] == ["python", "numpy", "scipy"]
    assert info["documentation_url"] == "https://github.com/galaxyproject/tools-iuc/tree/main/tools/hyphy"
    assert info["citation_dois"] == ["10.1093/molbev/msz197"]
    assert info["citation_urls"] == ["https://doi.org/10.1093/molbev/msz197"]
    assert info["citation_text"] == "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies."
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_json"][0] == "JSON"
    assert info["input"]["required"]["input_json"][1]["description"] == "JSON output file from HyPhy B-STILL analysis"
    assert info["input"]["optional"]["ebf"][1]["default"] == 10.0
    assert info["input"]["optional"]["ebf"][1]["min"] == 0
    assert info["input"]["optional"]["ebf"][1]["max"] == 10000
    assert info["input"]["optional"]["permutations"][1]["default"] == 10000
    assert info["input"]["optional"]["permutations"][1]["min"] == 100
    assert info["input"]["optional"]["permutations"][1]["max"] == 100000
    assert info["input"]["optional"]["alpha"][1]["default"] == 0.05
    assert info["input"]["optional"]["alpha"][1]["min"] == 0.001
    assert info["input"]["optional"]["alpha"][1]["max"] == 0.5
    assert info["input"]["optional"]["max_cluster"][1]["default"] == 30
    assert info["input"]["optional"]["max_cluster"][1]["min"] == 3
    assert info["input"]["optional"]["max_cluster"][1]["max"] == 100
    assert info["input"]["optional"]["merge"][1]["default"] == 15
    assert info["input"]["optional"]["merge"][1]["min"] == 0
    assert info["input"]["optional"]["merge"][1]["max"] == 100
    assert info["input"]["optional"]["script_path"][0] == "FILE"
    assert info["input"]["optional"]["script_path"][1]["default"].endswith("infer_stasis_clusters.py")


def test_hyphy_infer_stasis_clusters_renders_default_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_infer_stasis_clusters")

    command = node_class.render_command(
        {
            "input_json": "bstill-in1.json",
            "output": "/work/hyphy_infer_stasis_clusters",
        }
    )

    assert command.startswith("python3 ")
    tokens = shlex.split(command)
    assert tokens[0] == "python3"
    assert tokens[1].endswith("infer_stasis_clusters.py")
    assert tokens[2] == "bstill-in1.json"
    assert command.endswith(
        "--ebf 10.0 --permutations 10000 --alpha 0.05 --max-cluster 30 --merge 15 "
        "--output /work/hyphy_infer_stasis_clusters/output_json.json "
        "> /work/hyphy_infer_stasis_clusters/output_log.txt"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_infer_stasis_clusters" / "output_json.json",
        tmp_path / "hyphy_infer_stasis_clusters" / "output_log.txt",
    ]


def test_hyphy_infer_stasis_clusters_renders_custom_script_and_thresholds() -> None:
    node_class = _node_class("hyphy_infer_stasis_clusters")

    assert node_class.render_command(
        {
            "input_json": "B-STILL results.json",
            "script_path": "/opt/galaxy tools/infer_stasis_clusters.py",
            "ebf": 1.5,
            "permutations": 250,
            "alpha": 0.01,
            "max_cluster": 12,
            "merge": 0,
            "output": "/work/hyphy_infer_stasis_clusters",
        }
    ) == (
        "python3 '/opt/galaxy tools/infer_stasis_clusters.py' 'B-STILL results.json' "
        "--ebf 1.5 --permutations 250 --alpha 0.01 --max-cluster 12 --merge 0 "
        "--output /work/hyphy_infer_stasis_clusters/output_json.json "
        "> /work/hyphy_infer_stasis_clusters/output_log.txt"
    )


def test_hyphy_infer_stasis_clusters_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_infer_stasis_clusters")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-Infer Stasis Clusters B-STILL JSON input is required"
    assert node_class.VALIDATE_INPUTS({"input_json": "bstill.json", "ebf": -0.1}) == (
        "HyPhy-Infer Stasis Clusters EBF threshold must be between 0 and 10000"
    )
    assert node_class.VALIDATE_INPUTS({"input_json": "bstill.json", "permutations": 99}) == (
        "HyPhy-Infer Stasis Clusters permutations must be between 100 and 100000"
    )
    assert node_class.VALIDATE_INPUTS({"input_json": "bstill.json", "alpha": 0.0009}) == (
        "HyPhy-Infer Stasis Clusters alpha must be between 0.001 and 0.5"
    )
    assert node_class.VALIDATE_INPUTS({"input_json": "bstill.json", "max_cluster": 2}) == (
        "HyPhy-Infer Stasis Clusters maximum cluster size must be between 3 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"input_json": "bstill.json", "merge": 101}) == (
        "HyPhy-Infer Stasis Clusters merge distance must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_json": "bstill.json",
            "ebf": 10.0,
            "permutations": 10000,
            "alpha": 0.05,
            "max_cluster": 30,
            "merge": 15,
        }
    ) is True


def test_hyphy_meme_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_meme"]

    assert info["display_name"] == "HyPhy-MEME"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect pervasive or episodic site-level diversifying selection with HyPhy MEME."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "MEME",
        "Mixed Effects Model of Evolution",
        "episodic diversifying selection",
        "pervasive selection",
        "site-level selection",
        "positive selection",
        "multiple nucleotide substitutions",
        "imputed states",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["meme_output", "meme_md_report"]
    assert info["required_executables"] == ["HYPHYMPI", "mpirun"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#MEME"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1371/journal.pgen.1002764"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1371/journal.pgen.1002764",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Detecting Individual Sites Subject to Episodic Diversifying Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["p_value"][1]["default"] == 0.1
    assert info["input"]["optional"]["p_value"][1]["min"] == 0
    assert info["input"]["optional"]["p_value"][1]["max"] == 1
    assert info["input"]["optional"]["resample"][1]["default"] == 0
    assert info["input"]["optional"]["resample"][1]["min"] == 0
    assert info["input"]["optional"]["resample"][1]["max"] == 1000
    assert info["input"]["optional"]["rates"][1]["default"] == 2
    assert info["input"]["optional"]["rates"][1]["min"] == 2
    assert info["input"]["optional"]["rates"][1]["max"] == 4
    assert info["input"]["optional"]["multiple_hits"][1]["default"] == "None"
    assert info["input"]["optional"]["multiple_hits"][1]["options"] == ["None", "Double", "Double+Triple"]
    assert info["input"]["optional"]["site_multihit"][1]["default"] == "Estimate"
    assert info["input"]["optional"]["site_multihit"][1]["options"] == ["Estimate", "No"]
    assert info["input"]["optional"]["impute_states"][1]["default"] is False
    assert info["input"]["optional"]["precision"][1]["default"] == "standard"
    assert info["input"]["optional"]["precision"][1]["options"] == ["standard", "reduced"]
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["restrict_sites"][1]["default"] is False
    assert info["input"]["optional"]["limit_to_sites"][1]["default"] == ""
    assert info["input"]["optional"]["save_lf_for_sites"][1]["default"] == ""
    assert info["input"]["optional"]["full_model"][1]["default"] is True
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_meme_renders_default_mpi_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_meme")

    assert node_class.render_command(
        {
            "input_file": "meme-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "meme-in1.nhx",
            "output": "/work/hyphy_meme",
        }
    ) == (
        "ln -s meme-in1.nhx input.nhx && "
        "ln -s meme-in1.fa input.fasta && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI meme --alignment ./input.fasta --tree input.nhx --code Universal --branches All "
        "--pvalue 0.1 --resample 0 --rates 2 --multiple-hits None --impute-states No "
        "--precision standard --kill-zero-lengths Yes --output /work/hyphy_meme/meme_output.json "
        "--full-model Yes > /work/hyphy_meme/meme_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_meme" / "meme_output.json",
        tmp_path / "hyphy_meme" / "meme_stdout.md",
    ]


def test_hyphy_meme_renders_advanced_mpi_command_without_tree() -> None:
    node_class = _node_class("hyphy_meme")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "p_value": 0.05,
            "resample": 25,
            "rates": 4,
            "multiple_hits": "Double+Triple",
            "site_multihit": "No",
            "impute_states": True,
            "precision": "reduced",
            "kill_zero_lengths": "Constrain",
            "restrict_sites": True,
            "limit_to_sites": "1,2,3",
            "save_lf_for_sites": "4,5",
            "full_model": False,
            "threads": 8,
            "output": "/work/hyphy_meme",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 8} '
        "HYPHYMPI meme --alignment ./input.nex --code Vertebrate-mtDNA --branches 'Foreground clade' "
        "--pvalue 0.05 --resample 25 --rates 4 --multiple-hits Double+Triple --site-multihit No "
        "--impute-states Yes --precision reduced --kill-zero-lengths Constrain --limit-to-sites 1,2,3 "
        "--save-lf-for-sites 4,5 --output /work/hyphy_meme/meme_output.json --full-model No "
        "> /work/hyphy_meme/meme_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_meme_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_meme")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-MEME alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-MEME input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-MEME branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-MEME custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "p_value": 1.1}) == (
        "HyPhy-MEME p-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "resample": 1001}) == (
        "HyPhy-MEME resampling replicates must be between 0 and 1000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "rates": 1}) == (
        "HyPhy-MEME omega rate classes must be between 2 and 4"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "multiple_hits": "Triple"}) == (
        "Unsupported HyPhy-MEME multiple-hits mode: Triple"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "multiple_hits": "Double", "site_multihit": "Global"}
    ) == "Unsupported HyPhy-MEME site-multihit mode: Global"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "precision": "exact"}) == (
        "Unsupported HyPhy-MEME optimization precision: exact"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-MEME zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-MEME threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "branch_sel": "Internal",
            "p_value": 0.1,
            "resample": 0,
            "rates": 2,
            "multiple_hits": "Double",
            "site_multihit": "Estimate",
            "precision": "standard",
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_prime_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_prime"]

    assert info["display_name"] == "HyPhy-PRIME"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Model site-level physicochemical selection with HyPhy PRIME."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "PRIME",
        "Property Informed Models of Evolution",
        "PRoperty Informed Models of Evolution",
        "physicochemical selection",
        "biochemical properties",
        "amino-acid properties",
        "property-informed codon model",
        "site-level constraints",
        "protein evolution",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT", "JSON"]
    assert info["output_name"] == ["prime_output", "prime_md_report", "intermediate_fits"]
    assert info["required_executables"] == ["HYPHYMPI", "mpirun"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#PRIME"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.64898/2026.03.09.710461"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.64898/2026.03.09.710461",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Characterizing Physicochemical Selection in Protein Evolution with Property-Informed Models (PRIME)."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["prop_source_type"][1]["default"] == "builtin"
    assert info["input"]["optional"]["prop_source_type"][1]["options"] == ["builtin", "custom"]
    assert info["input"]["optional"]["prop_set"][1]["default"] == "3PROP"
    assert info["input"]["optional"]["prop_set"][1]["options"] == [
        "Atchley",
        "2PROP",
        "3PROP",
        "4PROP",
        "5PROP",
        "Random-2",
        "Random-3",
        "Random-4",
        "Random-5",
    ]
    assert info["input"]["optional"]["property_file"][0] == "JSON"
    assert info["input"]["optional"]["p_value"][1]["default"] == 0.1
    assert info["input"]["optional"]["p_value"][1]["min"] == 0
    assert info["input"]["optional"]["p_value"][1]["max"] == 1
    assert info["input"]["optional"]["impute_states"][1]["default"] is False
    assert info["input"]["optional"]["save_intermediate"][1]["default"] is False
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_prime_renders_default_mpi_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_prime")

    assert node_class.render_command(
        {
            "input_file": "prime-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "prime-in1.nhx",
            "output": "/work/hyphy_prime",
        }
    ) == (
        "ln -s prime-in1.nhx input.nhx && "
        "ln -s prime-in1.fa input.fasta && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI prime --alignment ./input.fasta --tree input.nhx --code Universal --branches All "
        "--property-set 3PROP --pvalue 0.1 --impute-states No --kill-zero-lengths Yes "
        "--output /work/hyphy_prime/prime_output.json > /work/hyphy_prime/prime_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_prime" / "prime_output.json",
        tmp_path / "hyphy_prime" / "prime_stdout.md",
    ]


def test_hyphy_prime_renders_custom_property_command_with_intermediate_fits(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_prime")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "prop_source_type": "custom",
            "property_file": "property weights.json",
            "p_value": 0.05,
            "impute_states": True,
            "save_intermediate": True,
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_prime",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 8} '
        "HYPHYMPI prime --alignment ./input.nex --code Vertebrate-mtDNA --branches 'Foreground clade' "
        "--property-set Custom --property-file 'property weights.json' --pvalue 0.05 --impute-states Yes "
        "--intermediate-fits /work/hyphy_prime/intermediate_fits.json --kill-zero-lengths Constrain "
        "--output /work/hyphy_prime/prime_output.json > /work/hyphy_prime/prime_stdout.md"
    )
    assert "--tree" not in command

    assert node_class.PLAN_OUTPUTS({"save_intermediate": True}, tmp_path) == [
        tmp_path / "hyphy_prime" / "prime_output.json",
        tmp_path / "hyphy_prime" / "prime_stdout.md",
        tmp_path / "hyphy_prime" / "intermediate_fits.json",
    ]


def test_hyphy_prime_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_prime")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-PRIME alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-PRIME input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-PRIME branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-PRIME custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "prop_source_type": "remote"}) == (
        "Unsupported HyPhy-PRIME property source: remote"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "prop_set": "6PROP"}) == (
        "Unsupported HyPhy-PRIME property set: 6PROP"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "prop_source_type": "custom"}) == (
        "HyPhy-PRIME custom property source requires a property JSON file"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "p_value": 1.1}) == (
        "HyPhy-PRIME p-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-PRIME zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-PRIME threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "branch_sel": "Internal",
            "prop_source_type": "builtin",
            "prop_set": "Atchley",
            "p_value": 0.1,
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_relax_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_relax"]

    assert info["display_name"] == "HyPhy-RELAX"
    assert info["category"] == "phylogeny"
    assert info["description"] == (
        "Detect relaxed or intensified selection in a codon-based phylogenetic framework with HyPhy RELAX."
    )
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "RELAX",
        "relaxed selection",
        "intensified selection",
        "selection intensity",
        "phylogenetic framework",
        "test branches",
        "reference branches",
        "group mode",
        "multiple alignments",
        "synonymous rate variation",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["relax_output", "relax_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#RELAX"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msu400"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msu400",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "RELAX: Detecting Relaxed Selection in a Phylogenetic Framework."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_type"][1]["default"] == "single"
    assert info["input"]["optional"]["input_type"][1]["options"] == ["single", "multiple"]
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["input_data_and_tree"][0] == "JSON"
    assert info["input"]["optional"]["input_files"][1]["multiple"] is True
    assert info["input"]["optional"]["input_trees"][1]["multiple"] is True
    assert info["input"]["optional"]["input_exts"][1]["multiple"] is True
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["models"][1]["default"] == "All"
    assert info["input"]["optional"]["models"][1]["options"] == ["All", "Minimal"]
    assert info["input"]["optional"]["test"][1]["default"] == "Unlabeled branches"
    assert info["input"]["optional"]["reference"][1]["default"] == ""
    assert info["input"]["optional"]["mode"][1]["default"] == "Classic mode"
    assert info["input"]["optional"]["mode"][1]["options"] == ["Classic mode", "Group mode"]
    assert info["input"]["optional"]["reference_group"][1]["default"] == ""
    assert info["input"]["optional"]["grid_size"][1]["default"] == 250
    assert info["input"]["optional"]["grid_size"][1]["max"] == 5000
    assert info["input"]["optional"]["starting_points"][1]["default"] == 1
    assert info["input"]["optional"]["starting_points"][1]["max"] == 1000
    assert info["input"]["optional"]["syn_rates"][1]["default"] == 3
    assert info["input"]["optional"]["syn_rates"][1]["min"] == 1
    assert info["input"]["optional"]["syn_rates"][1]["max"] == 10
    assert info["input"]["optional"]["rates"][1]["default"] == 3
    assert info["input"]["optional"]["rates"][1]["min"] == 2
    assert info["input"]["optional"]["rates"][1]["max"] == 10
    assert info["input"]["optional"]["srv"][1]["default"] == "No"
    assert info["input"]["optional"]["srv"][1]["options"] == ["No", "Yes", "Branch-site", "HMM"]
    assert info["input"]["optional"]["multiple_hits"][1]["default"] == "None"
    assert info["input"]["optional"]["multiple_hits"][1]["options"] == ["None", "Double", "Double+Triple"]
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["threads"][1]["default"] == 1


def test_hyphy_relax_renders_single_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_relax")

    assert node_class.render_command(
        {
            "input_file": "relax-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "relax-in1.nhx",
            "test": "TEST",
            "output": "/work/hyphy_relax",
        }
    ) == (
        "ln -s relax-in1.nhx input.nhx && "
        "ln -s relax-in1.fa input.fasta && "
        'export OMP_NUM_THREADS="${GALAXY_SLOTS:-1}" && '
        "hyphy relax --alignment input.fasta --tree input.nhx --models All --code Universal --test TEST "
        "--mode 'Classic mode' --grid-size 250 --starting-points 1 --syn-rates 3 --rates 3 --srv No "
        "--kill-zero-lengths Yes --output /work/hyphy_relax/relax_output.json "
        "> /work/hyphy_relax/relax_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_relax" / "relax_output.json",
        tmp_path / "hyphy_relax" / "relax_stdout.md",
    ]


def test_hyphy_relax_renders_multiple_alignment_group_mode_command() -> None:
    node_class = _node_class("hyphy_relax")

    command = node_class.render_command(
        {
            "input_type": "multiple",
            "input_data_and_tree": [
                {"input_file": "first alignment.fa", "input_ext": "fasta", "input_nhx": "first tree.nhx"},
                {"input_file": "second.nex", "input_ext": "nex", "input_nhx": ""},
            ],
            "gencodeid": "Vertebrate-mtDNA",
            "models": "Minimal",
            "test": "Unlabeled branches",
            "reference": "Reference clade",
            "mode": "Group mode",
            "reference_group": "TEST",
            "grid_size": 500,
            "starting_points": 2,
            "syn_rates": 4,
            "rates": 5,
            "srv": "HMM",
            "multiple_hits": "Double+Triple",
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_relax",
        }
    )

    assert command == (
        "ln -s 'first alignment.fa' input_0.fasta && "
        "ln -s 'first tree.nhx' input_0.nhx && "
        "echo input_0.fasta >> filelist.txt && "
        "ln -s second.nex input_1.nex && "
        "echo input_1.nex >> filelist.txt && "
        'export OMP_NUM_THREADS="${GALAXY_SLOTS:-8}" && '
        "hyphy relax --multiple-files Yes --filelist filelist.txt --tree input_0.nhx --models Minimal "
        "--code Vertebrate-mtDNA --test 'Unlabeled branches' --reference 'Reference clade' "
        "--mode 'Group mode' --reference-group TEST --grid-size 500 --starting-points 2 --syn-rates 4 "
        "--rates 5 --srv HMM --multiple-hits Double+Triple --kill-zero-lengths Constrain "
        "--output /work/hyphy_relax/relax_output.json > /work/hyphy_relax/relax_stdout.md"
    )


def test_hyphy_relax_accepts_parallel_multiple_input_lists() -> None:
    node_class = _node_class("hyphy_relax")

    command = node_class.render_command(
        {
            "input_type": "multiple",
            "input_files": ["alpha.fa", "beta.nex"],
            "input_exts": ["fasta", "nex"],
            "input_trees": ["alpha.nhx", "beta.nhx"],
            "test": "TEST",
            "output": "/work/hyphy_relax",
        }
    )

    assert "ln -s alpha.fa input_0.fasta" in command
    assert "ln -s beta.nex input_1.nex" in command
    assert "--tree input_0.nhx --tree input_1.nhx" in command


def test_hyphy_relax_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_relax")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-RELAX alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_type": "remote", "input_file": "alignment.fa"}) == (
        "Unsupported HyPhy-RELAX input type: remote"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-RELAX input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "models": "Fast"}) == (
        "Unsupported HyPhy-RELAX analysis type: Fast"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "test": ""}) == (
        "HyPhy-RELAX test branch label is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "mode": "Batch mode"}) == (
        "Unsupported HyPhy-RELAX run mode: Batch mode"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid_size": 5001}) == (
        "HyPhy-RELAX grid size must be between 1 and 5000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "starting_points": 0}) == (
        "HyPhy-RELAX starting points must be between 1 and 1000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "syn_rates": 0}) == (
        "HyPhy-RELAX synonymous rate classes must be between 1 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "rates": 1}) == (
        "HyPhy-RELAX non-synonymous rate classes must be between 2 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "srv": "Maybe"}) == (
        "Unsupported HyPhy-RELAX synonymous rate variation setting: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "multiple_hits": "Triple"}) == (
        "Unsupported HyPhy-RELAX multiple-hits mode: Triple"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-RELAX zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-RELAX threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "multiple", "input_data_and_tree": []}) == (
        "HyPhy-RELAX multiple-input mode requires at least one alignment"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_type": "multiple",
            "input_data_and_tree": [{"input_file": "alignment.fa", "input_ext": "stockholm"}],
        }
    ) == "Unsupported HyPhy-RELAX input extension: stockholm"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_type": "multiple",
            "input_data_and_tree": [{"input_file": "alignment.fa", "input_ext": "fasta"}],
            "test": "TEST",
        }
    ) is True


def test_hyphy_slac_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_slac"]

    assert info["display_name"] == "HyPhy-SLAC"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect pervasive site-level selection with HyPhy SLAC."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "SLAC",
        "Single Likelihood Ancestor Counting",
        "pervasive selection",
        "site-level selection",
        "ancestral state reconstruction",
        "synonymous substitutions",
        "nonsynonymous substitutions",
        "positive selection",
        "purifying selection",
        "phylogenetics",
    ]
    assert info["output"] == ["TEXT", "JSON"]
    assert info["output_name"] == ["slac_md_report", "slac_output"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#SLAC"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msi105"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msi105",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Not So Different After All: A Comparison of Methods for Detecting Amino Acid Sites Under Selection."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["p_value"][1]["default"] == 0.1
    assert info["input"]["optional"]["p_value"][1]["min"] == 0
    assert info["input"]["optional"]["p_value"][1]["max"] == 1
    assert info["input"]["optional"]["number_of_samples"][1]["default"] == 0
    assert info["input"]["optional"]["number_of_samples"][1]["min"] == 0
    assert info["input"]["optional"]["number_of_samples"][1]["max"] == 10000
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_slac_renders_default_hyphy_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_slac")

    assert node_class.render_command(
        {
            "input_file": "slac-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "slac-in1.nhx",
            "output": "/work/hyphy_slac",
        }
    ) == (
        "ln -s slac-in1.nhx input.nhx && "
        "ln -s slac-in1.fa input.fasta && "
        "hyphy CPU=4 slac --alignment ./input.fasta --tree input.nhx --code Universal --branches All "
        "--samples 0 --pvalue 0.1 --output /work/hyphy_slac/slac_output.json --kill-zero-lengths Yes "
        "> /work/hyphy_slac/slac_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_slac" / "slac_stdout.md",
        tmp_path / "hyphy_slac" / "slac_output.json",
    ]


def test_hyphy_slac_renders_advanced_hyphy_command_without_tree() -> None:
    node_class = _node_class("hyphy_slac")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "p_value": 0.05,
            "number_of_samples": 100,
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_slac",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        "hyphy CPU=8 slac --alignment ./input.nex --code Vertebrate-mtDNA --branches 'Foreground clade' "
        "--samples 100 --pvalue 0.05 --output /work/hyphy_slac/slac_output.json "
        "--kill-zero-lengths Constrain > /work/hyphy_slac/slac_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_slac_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_slac")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-SLAC alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-SLAC input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-SLAC branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-SLAC custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "p_value": 1.1}) == (
        "HyPhy-SLAC p-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "number_of_samples": 10001}) == (
        "HyPhy-SLAC ancestral reconstruction samples must be between 0 and 10000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-SLAC zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-SLAC threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "branch_sel": "Internal",
            "p_value": 0.1,
            "number_of_samples": 0,
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_sm19_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_sm19"]

    assert info["display_name"] == "HyPhy-SM2019"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Partition trees using the modified Slatkin-Maddison test with HyPhy SM2019."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "SM2019",
        "SM19",
        "Structured Slatkin-Maddison",
        "Modified Slatkin-Maddison Test",
        "population segregation",
        "gene flow",
        "migration events",
        "compartmentalization",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["sm19_output", "sm19_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "https://github.com/veg/hyphy-analyses/tree/master/SlatkinMaddison"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/genetics/123.3.603"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/genetics/123.3.603",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "A cladistic measure of gene flow inferred from the phylogenies of alleles."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "STRING"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Newick, NHX, or NEXUS tree whose leaf names can be partitioned by regular expression"
    )
    assert info["input"]["required"]["partitions"][0] == "JSON"
    assert info["input"]["required"]["partitions"][1]["description"] == (
        "List of partition objects with label and regex fields"
    )
    assert info["input"]["required"]["partitions"][1]["default"] == [
        {"label": "Partition 1", "regex": "P1[0-9]+"},
        {"label": "Partition 2", "regex": "P2[0-9]+"},
    ]
    assert info["input"]["required"]["partitions"][1]["min_items"] == 2
    assert info["input"]["required"]["partitions"][1]["max_items"] == 50
    assert info["input"]["optional"]["replicates"][1]["default"] == 100
    assert info["input"]["optional"]["replicates"][1]["min"] == 1
    assert info["input"]["optional"]["replicates"][1]["max"] == 1000000
    assert info["input"]["optional"]["weight"][1]["default"] == 0.2
    assert info["input"]["optional"]["weight"][1]["min"] == 0
    assert info["input"]["optional"]["weight"][1]["max"] == 1
    assert info["input"]["optional"]["use_bootstrap"][1]["default"] is True
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_sm19_renders_default_hyphy_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_sm19")

    assert node_class.render_command(
        {
            "input_file": "sm19-in1.nhx",
            "partitions": [
                {"label": "Blood", "regex": "B[0-9]+"},
                {"label": "Semen", "regex": "S[0-9]+"},
            ],
            "replicates": 1000,
            "weight": 0.2,
            "use_bootstrap": True,
            "output": "/work/hyphy_sm19",
        }
    ) == (
        "ln -s sm19-in1.nhx sm19_input.nhx && "
        "hyphy CPU=4 sm --tree ./sm19_input.nhx --groups 2 --description-1 Blood --regexp-1 'B[0-9]+' "
        "--description-2 Semen --regexp-2 'S[0-9]+' --replicates 1000 --weight 0.2 "
        "--use-bootstrap Yes --output /work/hyphy_sm19/sm19_output.json > /work/hyphy_sm19/sm19_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_sm19" / "sm19_output.json",
        tmp_path / "hyphy_sm19" / "sm19_stdout.md",
    ]


def test_hyphy_sm19_renders_advanced_hyphy_command_without_bootstrap() -> None:
    node_class = _node_class("hyphy_sm19")

    assert node_class.render_command(
        {
            "input_file": "tree with spaces.nexus",
            "partitions": [
                {"label": "Compartment A", "regex": "^A(1|2)$"},
                {"label": "Compartment B", "regex": "^B[0-9]+$"},
                {"label": "Compartment C", "regex": "C sample"},
            ],
            "replicates": 50,
            "weight": 0,
            "use_bootstrap": "No",
            "threads": 8,
            "output": "/work/hyphy_sm19",
        }
    ) == (
        "ln -s 'tree with spaces.nexus' sm19_input.nhx && "
        "hyphy CPU=8 sm --tree ./sm19_input.nhx --groups 3 --description-1 'Compartment A' "
        "--regexp-1 '^A(1|2)$' --description-2 'Compartment B' --regexp-2 '^B[0-9]+$' "
        "--description-3 'Compartment C' --regexp-3 'C sample' --replicates 50 --weight 0 "
        "--use-bootstrap No --output /work/hyphy_sm19/sm19_output.json > /work/hyphy_sm19/sm19_stdout.md"
    )


def test_hyphy_sm19_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_sm19")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-SM2019 input tree is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "tree.nhx", "partitions": []}) == (
        "HyPhy-SM2019 requires between 2 and 50 partitions"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B[0-9]+"}],
        }
    ) == "HyPhy-SM2019 requires between 2 and 50 partitions"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": f"P{i}", "regex": f"P{i}"} for i in range(51)],
        }
    ) == "HyPhy-SM2019 requires between 2 and 50 partitions"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "", "regex": "S"}],
        }
    ) == "HyPhy-SM2019 partition labels and regular expressions are required"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "Semen", "regex": ""}],
        }
    ) == "HyPhy-SM2019 partition labels and regular expressions are required"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "Semen", "regex": "S"}],
            "replicates": 0,
        }
    ) == "HyPhy-SM2019 bootstrap replicates must be between 1 and 1000000"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "Semen", "regex": "S"}],
            "weight": 1.1,
        }
    ) == "HyPhy-SM2019 structured permutation weight must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "Semen", "regex": "S"}],
            "threads": 0,
        }
    ) == "HyPhy-SM2019 threads must be a positive integer"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "tree.nhx",
            "partitions": [{"label": "Blood", "regex": "B"}, {"label": "Semen", "regex": "S"}],
            "replicates": 100,
            "weight": 0.2,
            "threads": 4,
        }
    ) is True


def test_hyphy_strike_ambigs_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_strike_ambigs"]

    assert info["display_name"] == "Replace ambiguous codons"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Replace ambiguous codons in an in-frame alignment using HyPhy."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "Strike-Ambigs",
        "Replace ambiguous codons",
        "ambiguous codons",
        "codon alignment",
        "FASTA",
        "gap codons",
        "sequencing ambiguity",
        "phylogenetics",
    ]
    assert info["output"] == ["FASTA", "TEXT"]
    assert info["output_name"] == ["output", "strike_ambigs_md_report"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/bioinformatics/bti079"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/bioinformatics/bti079",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "HyPhy: hypothesis testing using phylogenies."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["alignment"][0] == "FASTA"
    assert info["input"]["required"]["alignment"][1]["description"] == "In-frame codon alignment in FASTA format"
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert "Vertebrate-mtDNA" in info["input"]["optional"]["gencodeid"][1]["options"]


def test_hyphy_strike_ambigs_renders_hyphy_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_strike_ambigs")

    assert node_class.render_command(
        {
            "alignment": "strike-ambigs-in1.fa",
            "gencodeid": "Universal",
            "output": "/work/hyphy_strike_ambigs",
        }
    ) == (
        "hyphy ${HYPHY_STRIKE_AMBIGS_BF:-strike-ambigs.bf} --alignment strike-ambigs-in1.fa --code Universal "
        "--output /work/hyphy_strike_ambigs/output.fasta > /work/hyphy_strike_ambigs/strike_ambigs_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_strike_ambigs" / "output.fasta",
        tmp_path / "hyphy_strike_ambigs" / "strike_ambigs_stdout.md",
    ]


def test_hyphy_strike_ambigs_renders_advanced_hyphy_command() -> None:
    node_class = _node_class("hyphy_strike_ambigs")

    assert node_class.render_command(
        {
            "alignment": "codon alignment.fa",
            "gencodeid": "Vertebrate-mtDNA",
            "batch_file": "/opt/hyphy/scripts/strike-ambigs.bf",
            "output": "/work/hyphy_strike_ambigs",
        }
    ) == (
        "hyphy /opt/hyphy/scripts/strike-ambigs.bf --alignment 'codon alignment.fa' --code Vertebrate-mtDNA "
        "--output /work/hyphy_strike_ambigs/output.fasta > /work/hyphy_strike_ambigs/strike_ambigs_stdout.md"
    )


def test_hyphy_strike_ambigs_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_strike_ambigs")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy Strike-Ambigs alignment input is required"
    assert node_class.VALIDATE_INPUTS({"alignment": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"alignment": "alignment.fa", "gencodeid": "Universal"}) is True


def test_hyphy_busted_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_busted"]

    assert info["display_name"] == "HyPhy-BUSTED"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Detect gene-wide episodic diversifying selection with HyPhy BUSTED."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "BUSTED",
        "Branch-site Unrestricted Statistical Test",
        "Bayesian UnresTricted Test of Episodic Diversification",
        "episodic diversifying selection",
        "gene-wide selection",
        "positive selection",
        "synonymous rate variation",
        "multiple synonymous rate classes",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT", "PHYLOGENY_TREE"]
    assert info["output_name"] == ["busted_output", "busted_md_report", "alternative_model"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://hyphy.org/methods/selection-methods/#busted"
    assert info["citation_dois"] == [
        "10.1093/molbev/msz197",
        "10.1093/molbev/msv035",
        "10.1093/molbev/msaa037",
        "10.1093/molbev/msaf068",
    ]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msv035",
        "https://doi.org/10.1093/molbev/msaa037",
        "https://doi.org/10.1093/molbev/msaf068",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Gene-Wide Identification of Episodic Selection; "
        "Synonymous Site-to-Site Substitution Rate Variation Dramatically Inflates False Positive Rates of "
        "Selection Analyses: Ignore at Your Own Peril; "
        "A New Comparative Framework for Estimating Selection on Synonymous Substitutions."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sel"][1]["default"] == "All"
    assert info["input"]["optional"]["branch_sel"][1]["options"] == [
        "All",
        "Internal",
        "Leaves",
        "Unlabeled-branches",
        "specify",
    ]
    assert info["input"]["optional"]["syn_rates"][1]["default"] == 3
    assert info["input"]["optional"]["rates"][1]["default"] == 3
    assert info["input"]["optional"]["grid_size"][1]["default"] == 250
    assert info["input"]["optional"]["starting_points"][1]["default"] == 1
    assert info["input"]["optional"]["multiple_hits"][1]["default"] == "None"
    assert info["input"]["optional"]["multiple_hits"][1]["options"] == ["None", "Double", "Double+Triple"]
    assert info["input"]["optional"]["error_sink"][1]["default"] is True
    assert info["input"]["optional"]["save_alternative_model"][1]["default"] is False
    assert info["input"]["optional"]["mss_enabled"][1]["default"] is False
    assert info["input"]["optional"]["mss_type"][1]["default"] == "Full"
    assert info["input"]["optional"]["mss_type"][1]["options"] == [
        "Full",
        "SynREV",
        "SynREV2",
        "SynREV2g",
        "SynREVCodon",
        "Random",
        "Empirical",
        "File",
        "Codon-file",
    ]
    assert info["input"]["optional"]["mss_classes"][1]["default"] == 2
    assert info["input"]["optional"]["mss_file"][0] == "FILE"
    assert info["input"]["optional"]["mss_neutral"][1]["default"] == "neutral"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_busted_renders_default_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_busted")

    assert node_class.render_command(
        {
            "input_file": "absrel-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "absrel-in1.nhx",
            "output": "/work/hyphy_busted",
        }
    ) == (
        "ln -s absrel-in1.nhx input.nhx && "
        "ln -s absrel-in1.fa input.fasta && "
        "TOLERATE_NUMERICAL_ERRORS=1 hyphy CPU=4 busted --alignment ./input.fasta "
        "--tree input.nhx --code Universal --branches All --output /work/hyphy_busted/busted_output.json "
        "--syn-rates 3 --rates 3 --grid-size 250 --starting-points 1 --error-sink Yes "
        "--kill-zero-lengths Yes > /work/hyphy_busted/busted_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_busted" / "busted_output.json",
        tmp_path / "hyphy_busted" / "busted_stdout.md",
    ]
    assert node_class.PLAN_OUTPUTS({"save_alternative_model": True}, tmp_path) == [
        tmp_path / "hyphy_busted" / "busted_output.json",
        tmp_path / "hyphy_busted" / "busted_stdout.md",
        tmp_path / "hyphy_busted" / "alternative_model.nhx",
    ]


def test_hyphy_busted_renders_advanced_command_with_saved_model_and_mss() -> None:
    node_class = _node_class("hyphy_busted")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sel": "specify",
            "branch_label": "Foreground clade",
            "syn_rates": 5,
            "rates": 4,
            "grid_size": 500,
            "starting_points": 10,
            "multiple_hits": "None",
            "error_sink": False,
            "save_alternative_model": True,
            "mss_enabled": True,
            "mss_type": "Codon-file",
            "mss_file": "mss partitions.tsv",
            "mss_neutral": "NEUTRAL",
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_busted",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        "TOLERATE_NUMERICAL_ERRORS=1 hyphy CPU=8 busted --alignment ./input.nex "
        "--code Vertebrate-mtDNA --branches 'Foreground clade' "
        "--output /work/hyphy_busted/busted_output.json --syn-rates 5 --rates 4 "
        "--grid-size 500 --starting-points 10 --save-fit /work/hyphy_busted/alternative_model.nhx "
        "--mss Yes --mss-type Codon-file --mss-file 'mss partitions.tsv' --mss-neutral NEUTRAL "
        "--kill-zero-lengths Constrain > /work/hyphy_busted/busted_stdout.md"
    )
    assert "--tree" not in command
    assert "--multiple-hits" not in command
    assert "--error-sink" not in command


def test_hyphy_busted_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_busted")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-BUSTED alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "Foreground"}) == (
        "Unsupported HyPhy-BUSTED branch selection: Foreground"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sel": "specify"}) == (
        "HyPhy-BUSTED custom branch selection requires a branch label"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "syn_rates": 0}) == (
        "HyPhy-BUSTED synonymous rate classes must be between 1 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "rates": 1}) == (
        "HyPhy-BUSTED non-synonymous rate classes must be between 2 and 10"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "grid_size": 0}) == (
        "HyPhy-BUSTED grid size must be between 1 and 5000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "starting_points": 0}) == (
        "HyPhy-BUSTED starting points must be between 1 and 1000"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "multiple_hits": "Triple"}) == (
        "Unsupported HyPhy-BUSTED multiple-hits mode: Triple"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-BUSTED zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-BUSTED threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": "alignment.fa", "mss_enabled": True, "mss_type": "Codon-file"}
    ) == "HyPhy-BUSTED MSS file is required for Codon-file"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "mss_enabled": True,
            "mss_type": "Random",
            "mss_classes": 0,
        }
    ) == "HyPhy-BUSTED MSS classes must be a positive integer"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "multiple_hits": "Double",
            "mss_enabled": True,
            "mss_type": "Full",
        }
    ) == "HyPhy-BUSTED MSS cannot be combined with multiple-hit correction"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "gencodeid": "Universal",
            "branch_sel": "Internal",
            "syn_rates": 3,
            "rates": 3,
            "grid_size": 250,
            "starting_points": 1,
            "multiple_hits": "Double",
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_cfel_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_cfel"]

    assert info["display_name"] == "HyPhy-CFEL"
    assert info["category"] == "phylogeny"
    assert info["description"] == (
        "Test for site-wise selective pressure differences among clades or branch sets with HyPhy Contrast-FEL."
    )
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "CFEL",
        "Contrast-FEL",
        "Fixed Effects Likelihood",
        "Contrast-FEL branch sets",
        "branch sets",
        "clade selection",
        "selective pressure differences",
        "site-wise selection",
        "phylogenetics",
    ]
    assert info["output"] == ["JSON", "TEXT"]
    assert info["output_name"] == ["cfel_output", "cfel_md_report"]
    assert info["required_executables"] == ["HYPHYMPI", "mpirun"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert info["documentation_url"] == "http://www.hyphy.org/methods/other/contrast-fel/"
    assert info["citation_dois"] == ["10.1093/molbev/msz197", "10.1093/molbev/msaa263"]
    assert info["citation_urls"] == [
        "https://doi.org/10.1093/molbev/msz197",
        "https://doi.org/10.1093/molbev/msaa263",
    ]
    assert info["citation_text"] == (
        "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies; "
        "Contrast-FEL: A Test for Differences in Selective Pressures at Individual Sites among Clades and "
        "Sets of Branches."
    )
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "Codon alignment in FASTA, compressed FASTA, or NEXUS format"
    )
    assert info["input"]["optional"]["input_nhx"][0] == "FILE"
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == ["fasta", "fasta.gz", "nex"]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["branch_sets"][1]["default"] == ["Test"]
    assert info["input"]["optional"]["branch_sets"][1]["multiple"] is True
    assert info["input"]["optional"]["pvalue"][1]["default"] == 0.05
    assert info["input"]["optional"]["qvalue"][1]["default"] == 0.2
    assert info["input"]["optional"]["srv"][1]["default"] == "Yes"
    assert info["input"]["optional"]["srv"][1]["options"] == ["Yes", "No"]
    assert info["input"]["optional"]["permutations"][1]["default"] is False
    assert info["input"]["optional"]["limit_to_sites"][1]["default"] == ""
    assert info["input"]["optional"]["save_lf_for_sites"][1]["default"] == ""
    assert info["input"]["optional"]["intermediate_fits"][1]["default"] is False
    assert info["input"]["optional"]["kill_zero_lengths"][1]["default"] == "Yes"
    assert info["input"]["optional"]["kill_zero_lengths"][1]["options"] == ["Yes", "Constrain", "No"]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_cfel_renders_default_mpi_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_cfel")

    assert node_class.render_command(
        {
            "input_file": "cfel-in1.fa",
            "input_ext": "fasta",
            "input_nhx": "cfel-in1.nhx",
            "branch_sets": ["Internal branches", "Terminal branches"],
            "output": "/work/hyphy_cfel",
        }
    ) == (
        "ln -s cfel-in1.nhx input.nhx && "
        "ln -s cfel-in1.fa input.fasta && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 4} '
        "HYPHYMPI contrast-fel --alignment input.fasta --tree input.nhx --code Universal "
        "--branch-set 'Internal branches' --branch-set 'Terminal branches' --srv Yes --permutations No "
        "--pvalue 0.05 --qvalue 0.2 --kill-zero-lengths Yes "
        "--output /work/hyphy_cfel/cfel_output.json > /work/hyphy_cfel/cfel_stdout.md"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_cfel" / "cfel_output.json",
        tmp_path / "hyphy_cfel" / "cfel_stdout.md",
    ]


def test_hyphy_cfel_renders_advanced_command_without_tree() -> None:
    node_class = _node_class("hyphy_cfel")

    command = node_class.render_command(
        {
            "input_file": "codon alignment.nex",
            "input_ext": "nex",
            "gencodeid": "Vertebrate-mtDNA",
            "branch_sets": ["Test", "Reference group"],
            "srv": "No",
            "permutations": True,
            "pvalue": 0.01,
            "qvalue": 0.1,
            "limit_to_sites": "1,3,5",
            "save_lf_for_sites": "2-4",
            "intermediate_fits": True,
            "kill_zero_lengths": "Constrain",
            "threads": 8,
            "output": "/work/hyphy_cfel",
        }
    )

    assert command == (
        "ln -s 'codon alignment.nex' input.nex && "
        '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${TMPDIR:-.}" -np 8} '
        "HYPHYMPI contrast-fel --alignment input.nex --code Vertebrate-mtDNA "
        "--branch-set Test --branch-set 'Reference group' --srv No --permutations Yes "
        "--pvalue 0.01 --qvalue 0.1 --limit-to-sites 1,3,5 --save-lf-for-sites 2-4 "
        "--intermediate-fits /work/hyphy_cfel/intermediate_fits.json --kill-zero-lengths Constrain "
        "--output /work/hyphy_cfel/cfel_output.json > /work/hyphy_cfel/cfel_stdout.md"
    )
    assert "--tree" not in command


def test_hyphy_cfel_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_cfel")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-CFEL alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sets": []}) == (
        "HyPhy-CFEL requires at least one branch set"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "branch_sets": [""]}) == (
        "HyPhy-CFEL branch set labels must be non-empty"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "srv": "Maybe"}) == (
        "Unsupported HyPhy-CFEL synonymous rate variation setting: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "pvalue": -0.1}) == (
        "HyPhy-CFEL p-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "qvalue": 1.1}) == (
        "HyPhy-CFEL q-value threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "kill_zero_lengths": "Maybe"}) == (
        "Unsupported HyPhy-CFEL zero-length branch handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-CFEL threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "gencodeid": "Universal",
            "branch_sets": ["Internal branches", "Terminal branches"],
            "srv": "Yes",
            "pvalue": 0.05,
            "qvalue": 0.2,
            "kill_zero_lengths": "Yes",
            "threads": 4,
        }
    ) is True


def test_hyphy_conv_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_conv"]

    assert info["display_name"] == "HyPhy-Conv"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Translate an in-frame codon alignment to proteins with HyPhy CONV."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "CONV",
        "CodonToProtein",
        "codon to protein",
        "translate codon alignment",
        "amino acid translation",
        "CodonToProtein amino acid translation",
        "protein alignment",
        "keep deletions",
        "skip deletions",
        "phylogenetics",
    ]
    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["proteins"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert (
        info["documentation_url"]
        == "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CodonToProtein.bf"
    )
    assert info["citation_dois"] == ["10.1093/molbev/msz197"]
    assert info["citation_urls"] == ["https://doi.org/10.1093/molbev/msz197"]
    assert info["citation_text"] == "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies."
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "In-frame codon alignment in FASTA format"
    )
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["deletions"][1]["default"] == "Skip Deletions"
    assert info["input"]["optional"]["deletions"][1]["options"] == ["Keep Deletions", "Skip Deletions"]


def test_hyphy_conv_renders_default_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_conv")

    assert node_class.render_command(
        {
            "input_file": "conv-in1.fa",
            "output": "/work/hyphy_conv",
        }
    ) == (
        "cp conv-in1.fa conv_input.fa && "
        "ENV='TOLERATE_NUMERICAL_ERRORS=1;' hyphy conv Universal 'Skip Deletions' "
        "conv_input.fa /work/hyphy_conv/proteins.nex"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_conv" / "proteins.nex",
    ]


def test_hyphy_conv_renders_keep_deletions_command() -> None:
    node_class = _node_class("hyphy_conv")

    assert node_class.render_command(
        {
            "input_file": "codon alignment.fa",
            "gencodeid": "Vertebrate-mtDNA",
            "deletions": "Keep Deletions",
            "output": "/work/hyphy_conv",
        }
    ) == (
        "cp 'codon alignment.fa' conv_input.fa && "
        "ENV='TOLERATE_NUMERICAL_ERRORS=1;' hyphy conv Vertebrate-mtDNA 'Keep Deletions' "
        "conv_input.fa /work/hyphy_conv/proteins.nex"
    )


def test_hyphy_conv_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_conv")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-Conv codon alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "deletions": "Maybe"}) == (
        "Unsupported HyPhy-Conv deletion handling: Maybe"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "gencodeid": "Universal",
            "deletions": "Keep Deletions",
        }
    ) is True


def test_hyphy_cln_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["hyphy_cln"]

    assert info["display_name"] == "HyPhy-CLN"
    assert info["category"] == "phylogeny"
    assert info["description"] == "Clean and normalize codon alignments with HyPhy CLN."
    assert info["search_aliases"] == [
        "Galaxy",
        "HyPhy",
        "CLN",
        "CleanStopCodons",
        "CleanStopCodons duplicate sequences",
        "clean alignment",
        "normalize alignment",
        "duplicate sequences",
        "gap-only sites",
        "stop codons",
        "sequence identifiers",
        "phylogenetics",
    ]
    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["cleaned_alignment"]
    assert info["required_executables"] == ["hyphy"]
    assert info["required_conda_packages"] == ["hyphy"]
    assert (
        info["documentation_url"]
        == "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CleanStopCodons.bf"
    )
    assert info["citation_dois"] == ["10.1093/molbev/msz197"]
    assert info["citation_urls"] == ["https://doi.org/10.1093/molbev/msz197"]
    assert info["citation_text"] == "HyPhy 2.5: a customizable platform for evolutionary hypothesis testing using phylogenies."
    assert info["version"] == "2.5.96"

    assert info["input"]["required"]["input_file"][0] == "FASTA"
    assert info["input"]["required"]["input_file"][1]["description"] == (
        "In-frame codon alignment in FASTA, compressed FASTA, NEXUS, PHYLIP, or MEGA format"
    )
    assert info["input"]["optional"]["input_ext"][1]["default"] == "fasta"
    assert info["input"]["optional"]["input_ext"][1]["options"] == [
        "fasta",
        "fasta.gz",
        "nex",
        "nexus",
        "phylip",
        "mega",
    ]
    assert info["input"]["optional"]["gencodeid"][1]["default"] == "Universal"
    assert info["input"]["optional"]["filtering_method"][1]["default"] == "No/No"
    assert info["input"]["optional"]["filtering_method"][1]["options"] == [
        "No/No",
        "No/Yes",
        "Yes/No",
        "Yes/Yes",
        "Disallow stops",
    ]
    assert info["input"]["optional"]["threads"][1]["default"] == 4


def test_hyphy_cln_renders_default_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hyphy_cln")

    assert node_class.render_command(
        {
            "input_file": "conv-in1.fa",
            "input_ext": "fasta",
            "output": "/work/hyphy_cln",
        }
    ) == (
        "ln -s conv-in1.fa input.fasta && "
        "hyphy CPU=4 cln --alignment input.fasta --code Universal --filtering-method No/No "
        "--output /work/hyphy_cln/cleaned_alignment.fasta"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "hyphy_cln" / "cleaned_alignment.fasta",
    ]


def test_hyphy_cln_renders_advanced_command() -> None:
    node_class = _node_class("hyphy_cln")

    assert node_class.render_command(
        {
            "input_file": "codon alignment.phy",
            "input_ext": "phylip",
            "gencodeid": "Vertebrate-mtDNA",
            "filtering_method": "Disallow stops",
            "threads": 8,
            "output": "/work/hyphy_cln",
        }
    ) == (
        "ln -s 'codon alignment.phy' input.phylip && "
        "hyphy CPU=8 cln --alignment input.phylip --code Vertebrate-mtDNA "
        "--filtering-method 'Disallow stops' --output /work/hyphy_cln/cleaned_alignment.fasta"
    )


def test_hyphy_cln_validates_wrapper_inputs() -> None:
    node_class = _node_class("hyphy_cln")

    assert node_class.VALIDATE_INPUTS({}) == "HyPhy-CLN alignment input is required"
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "input_ext": "stockholm"}) == (
        "Unsupported HyPhy-CLN input extension: stockholm"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "gencodeid": "Mars"}) == (
        "Unsupported HyPhy genetic code: Mars"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "filtering_method": "Maybe"}) == (
        "Unsupported HyPhy-CLN filtering method: Maybe"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": "alignment.fa", "threads": 0}) == (
        "HyPhy-CLN threads must be a positive integer"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "input_file": "alignment.fa",
            "input_ext": "fasta",
            "gencodeid": "Universal",
            "filtering_method": "Yes/Yes",
            "threads": 4,
        }
    ) is True


def test_merge_metaphlan_tables_renders_join_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("merge_metaphlan_tables")
    info = _registry().object_info()["merge_metaphlan_tables"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["merged_abundance_table"]
    assert info["citation_dois"] == ["10.1038/s41587-023-01688-w"]
    assert info["citation_text"] == "Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4."
    assert info["input"]["required"]["abundance_tables"][0] == "TSV"
    assert info["input"]["required"]["abundance_tables"][1]["multiple"] is True
    assert info["input"]["optional"]["element_identifiers"][1]["multiple"] is True
    assert info["input"]["optional"]["gtdb_profiles"][1]["default"] is False

    assert node_class.render_command(
        {
            "abundance_tables": ["Sample A_profile.tsv", "sample-B.txt"],
            "element_identifiers": ["SRS014464-Anterior_nares", "sample B"],
            "output": "/work/merge_metaphlan",
        }
    ) == (
        "ln -s 'Sample A_profile.tsv' SRS014464-Anterior_nares && "
        "ln -s sample-B.txt sample_B && "
        "merge_metaphlan_tables.py SRS014464-Anterior_nares sample_B "
        "> /work/merge_metaphlan/merged_metaphlan_tables.tsv"
    )

    assert node_class.render_command(
        {
            "inputs": ["gtdb1.tsv", "gtdb2.tsv"],
            "gtdb_profiles": True,
            "output": "/work/merge_metaphlan",
        }
    ) == (
        "ln -s gtdb1.tsv gtdb1.tsv && "
        "ln -s gtdb2.tsv gtdb2.tsv && "
        "merge_metaphlan_tables.py --gtdb_profiles gtdb1.tsv gtdb2.tsv "
        "> /work/merge_metaphlan/merged_metaphlan_tables.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "merge_metaphlan_tables" / "merged_metaphlan_tables.tsv",
    ]


def test_extract_metaphlan_database_renders_database_export_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("extract_metaphlan_database")
    info = _registry().object_info()["extract_metaphlan_database"]

    assert info["output"] == ["FASTA", "JSON"]
    assert info["output_name"] == ["marker_sequences", "marker_metadata"]
    assert info["citation_dois"] == ["10.1038/s41587-023-01688-w"]
    assert info["citation_text"] == "Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4."
    assert info["input"]["required"]["database_path"][0] == "DIRECTORY"
    assert info["input"]["required"]["database_key"][0] == "STRING"
    assert info["input"]["optional"]["customizemetadata_script"][0] == "FILE"
    assert info["input"]["optional"]["customizemetadata_script"][1]["default"] == "customizemetadata.py"

    assert node_class.render_command(
        {
            "database_path": "/db/metaphlan",
            "database_key": "mpa_vJun23_CHOCOPhlAnSGB_202403",
            "output": "/work/extract_metaphlan_database",
        }
    ) == (
        "bowtie2-inspect /db/metaphlan/mpa_vJun23_CHOCOPhlAnSGB_202403 "
        "> /work/extract_metaphlan_database/marker_sequences.fasta && "
        "python customizemetadata.py transform_pkl_to_json "
        "--pkl /db/metaphlan/mpa_vJun23_CHOCOPhlAnSGB_202403.pkl "
        "--json /work/extract_metaphlan_database/marker_metadata.json"
    )

    assert node_class.render_command(
        {
            "database_path": "/db/metaphlan",
            "database_key": "mpa_vJun23_CHOCOPhlAnSGB_202403",
            "customizemetadata_script": "/opt/galaxy tools/customizemetadata.py",
            "output": "/work/extract_metaphlan_database",
        }
    ) == (
        "bowtie2-inspect /db/metaphlan/mpa_vJun23_CHOCOPhlAnSGB_202403 "
        "> /work/extract_metaphlan_database/marker_sequences.fasta && "
        "python '/opt/galaxy tools/customizemetadata.py' transform_pkl_to_json "
        "--pkl /db/metaphlan/mpa_vJun23_CHOCOPhlAnSGB_202403.pkl "
        "--json /work/extract_metaphlan_database/marker_metadata.json"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "extract_metaphlan_database" / "marker_sequences.fasta",
        tmp_path / "extract_metaphlan_database" / "marker_metadata.json",
    ]


def test_customize_metaphlan_database_renders_add_remove_keep_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("customize_metaphlan_database")
    info = _registry().object_info()["customize_metaphlan_database"]

    assert info["output"] == ["FASTA", "JSON"]
    assert info["output_name"] == ["out_fasta", "out_json"]
    assert info["citation_dois"] == ["10.1038/s41587-023-01688-w"]
    assert info["input"]["required"]["marker_sequences"][0] == "FASTA"
    assert info["input"]["required"]["marker_metadata"][0] == "JSON"
    assert info["input"]["optional"]["operation"][1]["options"] == ["add_marker", "remove_markers", "keep_markers"]
    assert info["input"]["optional"]["genome_lengths"][1]["multiple"] is True
    assert info["input"]["optional"]["customizemetadata_script"][1]["default"] == "customizemetadata.py"

    assert node_class.render_command(
        {
            "marker_sequences": "test-db-without-one-marker.fasta",
            "marker_metadata": "test-db-without-one-marker.json",
            "operation": "add_marker",
            "new_marker_sequences": "marker_sequence.fasta",
            "marker_name": "13076__A0A2I1PE66__CYJ72_10760",
            "marker_length": 540,
            "genome_lengths": [2411251],
            "genbank_accessions": ["GCA_002847845"],
            "kingdom_names": ["Bacteria"],
            "kingdom_ids": [2],
            "phylum_names": ["Bacilli"],
            "phylum_ids": [1239],
            "class_names": ["Negativicutes"],
            "class_ids": [91061],
            "order_names": ["Lactobacillales"],
            "order_ids": [186826],
            "family_names": ["Aerococcaceae"],
            "family_ids": [186827],
            "genus_names": ["Globicatella"],
            "genus_ids": [13075],
            "species_names": ["Globicatella_sanguinis"],
            "species_ids": [13076],
            "strain_names": ["GCA_002847845"],
            "output": "/work/customize_metaphlan_database",
        }
    ) == (
        "python customizemetadata.py add_marker --in_json test-db-without-one-marker.json "
        "--out_json /work/customize_metaphlan_database/custom_marker_metadata.json "
        "--name 13076__A0A2I1PE66__CYJ72_10760 --m_length 540 "
        "--g_length 2411251 --gca GCA_002847845 --k_name Bacteria --k_id 2 "
        "--p_name Bacilli --p_id 1239 --c_name Negativicutes --c_id 91061 "
        "--o_name Lactobacillales --o_id 186826 --f_name Aerococcaceae --f_id 186827 "
        "--g_name Globicatella --g_id 13075 --s_name Globicatella_sanguinis --s_id 13076 "
        "--t_name GCA_002847845 && "
        "cat test-db-without-one-marker.fasta marker_sequence.fasta "
        "> /work/customize_metaphlan_database/custom_marker_sequences.fasta"
    )

    assert node_class.render_command(
        {
            "marker_sequences": "test-db.fasta",
            "marker_metadata": "test-db.json",
            "operation": "remove_markers",
            "markers": "marker.txt",
            "output": "/work/customize_metaphlan_database",
        }
    ) == (
        "python customizemetadata.py remove_markers --in_json test-db.json --markers marker.txt "
        "--out_json /work/customize_metaphlan_database/custom_marker_metadata.json "
        "--kept_markers kept_markers.txt && "
        "seqtk subseq test-db.fasta kept_markers.txt "
        "> /work/customize_metaphlan_database/custom_marker_sequences.fasta"
    )

    assert node_class.render_command(
        {
            "marker_sequences": "test-db.fasta",
            "marker_metadata": "test-db.json",
            "operation": "keep_markers",
            "markers": "marker.txt",
            "customizemetadata_script": "/opt/galaxy tools/customizemetadata.py",
            "output": "/work/customize_metaphlan_database",
        }
    ) == (
        "python '/opt/galaxy tools/customizemetadata.py' keep_markers --in_json test-db.json "
        "--markers marker.txt --out_json /work/customize_metaphlan_database/custom_marker_metadata.json && "
        "seqtk subseq test-db.fasta marker.txt "
        "> /work/customize_metaphlan_database/custom_marker_sequences.fasta"
    )

    assert node_class.VALIDATE_INPUTS(
        {
            "marker_sequences": "test-db.fasta",
            "marker_metadata": "test-db.json",
            "operation": "add_marker",
            "new_marker_sequences": "marker_sequence.fasta",
            "marker_name": "marker",
            "marker_length": 540,
            "genome_lengths": [2411251],
            "genbank_accessions": [],
        }
    ) == "Add-marker taxonomy fields must have the same number of values as genome_lengths"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "customize_metaphlan_database" / "custom_marker_sequences.fasta",
        tmp_path / "customize_metaphlan_database" / "custom_marker_metadata.json",
    ]


def test_recentrifuge_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["recentrifuge"]

    assert info["display_name"] == "Recentrifuge"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Robust comparative analysis and contamination removal for metagenomics."
    assert info["search_aliases"] == [
        "Galaxy",
        "Recentrifuge",
        "robust contamination removal",
        "comparative analysis",
        "metagenomics",
        "Centrifuge",
        "Kraken",
        "CLARK",
        "LMAT",
        "generic classifier",
    ]
    assert info["version"] == "1.16.1"
    assert info["output"] == ["HTML_REPORT", "TEXT", "TSV", "TSV", "FILE"]
    assert info["output_name"] == ["html_report", "logfile", "data_table", "stat_table", "xlsx_report"]
    assert info["required_executables"] == ["rcf"]
    assert info["required_conda_packages"] == ["recentrifuge"]
    assert info["documentation_url"] == "https://github.com/khyox/recentrifuge"
    assert info["citation_dois"] == ["10.1371/journal.pcbi.1006967"]
    assert info["citation_urls"] == ["https://doi.org/10.1371/journal.pcbi.1006967"]
    assert info["citation_text"] == "Recentrifuge: Robust comparative analysis and contamination removal for metagenomics."

    assert info["input"]["required"]["input_file"][0] == "TSV"
    assert info["input"]["required"]["input_file"][1]["multiple"] is True
    assert info["input"]["required"]["filetype"][1]["options"] == ["centrifuge", "clark", "generic", "lmat", "kraken"]
    assert info["input"]["required"]["database_name"][0] == "DIRECTORY"
    assert info["input"]["optional"]["format"][1]["displayOptions"] == {"show": {"filetype": ["generic"]}}
    assert info["input"]["optional"]["extra"][1]["default"] == "CSV"
    assert info["input"]["optional"]["extra"][1]["options"] == ["CSV", "DYNOMICS", "FULL", "TSV"]
    assert info["input"]["optional"]["nohtml"][1]["default"] is False
    assert info["input"]["optional"]["no_logfile"][1]["default"] is False
    assert info["input"]["optional"]["scoring"][1]["options"] == [
        "",
        "SHEL",
        "LENGTH",
        "LOGLENGTH",
        "NORMA",
        "LMAT",
        "CLARK_C",
        "CLARK_G",
        "KRAKEN",
        "GENERIC",
    ]
    assert info["input"]["optional"]["summary"][1]["default"] == "ADD"
    assert info["input"]["optional"]["summary"][1]["options"] == ["ADD", "ONLY", "AVOID"]


def test_recentrifuge_renders_kraken_csv_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("recentrifuge")

    assert node_class.render_command(
        {
            "input_file": ["kraken sample.out", "control.kraken"],
            "element_identifiers": ["Tumor sample#1", "negative.control"],
            "filetype": "kraken",
            "database_name": "/db/ncbi_taxonomy",
            "extra": "CSV",
            "output": "/work/recentrifuge",
        }
    ) == (
        "mkdir -p input_dir && "
        "ln -s 'kraken sample.out' 'input_dir/Tumor sample_1.krk' && "
        "ln -s control.kraken input_dir/negative_control.krk && "
        "rcf -n /db/ncbi_taxonomy -k input_dir -e CSV -o output --scoring KRAKEN "
        "--summary ADD | tee /work/recentrifuge/logfile.txt"
    )

    assert node_class.PLAN_OUTPUTS({"extra": "CSV"}, tmp_path) == [
        tmp_path / "recentrifuge" / "output.rcf.html",
        tmp_path / "recentrifuge" / "logfile.txt",
        tmp_path / "recentrifuge" / "output.rcf.data.csv",
        tmp_path / "recentrifuge" / "output.rcf.stat.csv",
    ]


def test_recentrifuge_renders_centrifuge_tsv_command_and_suppressed_reports(tmp_path: Path) -> None:
    node_class = _node_class("recentrifuge")

    assert node_class.render_command(
        {
            "input_file": ["centrifuge.out", "centrifuge 2.out"],
            "filetype": "centrifuge",
            "database_name": "/db/ncbi_taxonomy",
            "extra": "TSV",
            "nohtml": True,
            "no_logfile": True,
            "scoring": "LENGTH",
            "summary": "ONLY",
            "strain": True,
            "output": "/work/recentrifuge",
        }
    ) == (
        "mkdir -p input_dir && "
        "ln -s centrifuge.out input_dir/centrifuge_out.out && "
        "ln -s 'centrifuge 2.out' 'input_dir/centrifuge 2_out.out' && "
        "rcf -n /db/ncbi_taxonomy -f input_dir -e TSV -o output --nohtml "
        "--scoring LENGTH --summary ONLY --strain > /work/recentrifuge/logfile.txt"
    )

    assert node_class.PLAN_OUTPUTS({"extra": "TSV", "nohtml": True, "no_logfile": True}, tmp_path) == [
        tmp_path / "recentrifuge" / "output.rcf.data.tsv",
        tmp_path / "recentrifuge" / "output.rcf.stat.tsv",
    ]


def test_recentrifuge_renders_generic_full_command_with_advanced_options(tmp_path: Path) -> None:
    node_class = _node_class("recentrifuge")

    assert node_class.render_command(
        {
            "input_file": ["generic calls.tsv"],
            "element_identifiers": ["generic sample.tsv"],
            "filetype": "generic",
            "format": "TYP:csv,TID:1,LEN:3,SCO:6,UNC:0",
            "database_name": "/db/ncbi taxonomy",
            "extra": "FULL",
            "controls": 2,
            "scoring": "NORMA",
            "minscore_value": 5,
            "mintaxa": 3,
            "exclude_taxa_name": "9606,10090",
            "include_taxa_name": "2,2157",
            "avoidcross": True,
            "ctrlminscore": 7,
            "ctrlmintaxa": 4,
            "summary": "AVOID",
            "takeoutroot": True,
            "nokollapse": True,
            "sequential": True,
            "output": "/work/recentrifuge",
        }
    ) == (
        "mkdir -p input_dir && "
        "ln -s 'generic calls.tsv' 'input_dir/generic sample_tsv' && "
        "rcf -n '/db/ncbi taxonomy' -g input_dir "
        "--format TYP:csv,TID:1,LEN:3,SCO:6,UNC:0 -e FULL -o output "
        "--controls 2 --scoring NORMA --minscore 5 --mintaxa 3 "
        "--exclude 9606,10090 --include 2,2157 --avoidcross "
        "--ctrlminscore 7 --ctrlmintaxa 4 --summary AVOID --takeoutroot "
        "--nokollapse --sequential | tee /work/recentrifuge/logfile.txt"
    )

    assert node_class.PLAN_OUTPUTS({"extra": "FULL", "nohtml": False, "no_logfile": False}, tmp_path) == [
        tmp_path / "recentrifuge" / "output.rcf.html",
        tmp_path / "recentrifuge" / "logfile.txt",
        tmp_path / "recentrifuge" / "output.rcf.xlsx",
    ]
    assert node_class.PLAN_OUTPUTS({"extra": "DYNOMICS", "nohtml": True}, tmp_path) == [
        tmp_path / "recentrifuge" / "logfile.txt",
        tmp_path / "recentrifuge" / "output.rcf.xlsx",
    ]


def test_recentrifuge_validates_required_wrapper_inputs() -> None:
    node_class = _node_class("recentrifuge")

    assert node_class.VALIDATE_INPUTS({"database_name": "/db/ncbi_taxonomy", "filetype": "kraken"}) == (
        "At least one taxonomy input file is required"
    )
    assert node_class.VALIDATE_INPUTS({"input_file": ["calls.tsv"], "filetype": "kraken"}) == (
        "NCBI taxonomy database is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input_file": ["calls.tsv"], "database_name": "/db/ncbi_taxonomy", "filetype": "generic"}
    ) == "Generic input mode requires a format string"
    assert (
        node_class.VALIDATE_INPUTS(
            {"input_file": ["calls.tsv"], "database_name": "/db/ncbi_taxonomy", "filetype": "kraken"}
        )
        is True
    )


def test_centrifuge_exposes_galaxy_aligned_inputs_outputs_and_citation() -> None:
    info = _registry().object_info()["centrifuge"]

    assert info["display_name"] == "Centrifuge"
    assert info["category"] == "metagenomics"
    assert info["description"] == "Read-based metagenome characterization with Centrifuge."
    assert info["search_aliases"] == [
        "Galaxy",
        "Centrifuge",
        "metagenomic classification",
        "taxonomic classification",
        "read-based metagenomics",
        "SRA accession",
        "FM index",
    ]
    assert info["version"] == "1.0.4_beta"
    assert info["output"] == ["TSV", "SAM", "TSV"]
    assert info["output_name"] == ["tabular_output", "sam_output", "report"]
    assert info["required_executables"] == ["centrifuge"]
    assert info["required_conda_packages"] == ["centrifuge"]
    assert info["documentation_url"] == "https://ccb.jhu.edu/software/centrifuge/"
    assert info["citation_dois"] == ["10.1101/gr.210641.116"]
    assert info["citation_urls"] == ["https://doi.org/10.1101/gr.210641.116"]
    assert info["citation_text"] == "Centrifuge: rapid and sensitive classification of metagenomic sequences."

    assert info["input"]["required"]["db"][0] == "DIRECTORY"
    assert info["input"]["required"]["db"][1]["description"] == "Centrifuge index filename prefix or database directory"
    assert info["input"]["optional"]["unpaired_reads"][0] == "FASTQ"
    assert info["input"]["optional"]["unpaired_reads"][1]["multiple"] is True
    assert info["input"]["optional"]["paired_reads"][0] == "FASTQ_LIST"
    assert info["input"]["optional"]["paired_reads"][1]["multiple"] is True
    assert info["input"]["optional"]["sra"][0] == "STRING"
    assert info["input"]["optional"]["out_fmt"][1]["default"] == "tab"
    assert info["input"]["optional"]["out_fmt"][1]["options"] == ["tab", "sam"]
    assert (
        info["input"]["optional"]["tab_fmt_cols"][1]["default"]
        == "readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches"
    )
    assert info["input"]["optional"]["min_hitlen"][1]["default"] == 22
    assert info["input"]["optional"]["min_hitlen"][1]["min"] == 16
    assert info["input"]["optional"]["host_taxids"][1]["advanced"] is True
    assert info["input"]["optional"]["exclude_taxids"][1]["advanced"] is True


def test_centrifuge_renders_unpaired_tab_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("centrifuge")

    assert node_class.render_command(
        {
            "db": "/indexes/p_compressed+h+v",
            "unpaired_reads": ["sample A.fq", "sample_B.fastq"],
            "skip": 3,
            "upto": 6,
            "trim5": 10,
            "trim3": 5,
            "ignore_quals": True,
            "norc": True,
            "seed": 123,
            "min_hitlen": 83,
            "min_totallen": 100,
            "host_taxids": "9606,10090",
            "exclude_taxids": "9913",
            "threads": 8,
            "output": "/work/centrifuge",
        }
    ) == (
        "centrifuge --out-fmt tab --tab-fmt-cols "
        "readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches "
        "--threads 8 --skip 3 --upto 6 --trim5 10 --trim3 5 --ignore-quals --norc --seed 123 "
        "--min-hitlen 83 --min-totallen 100 --host-taxids 9606,10090 --exclude-taxids 9913 "
        "-x /indexes/p_compressed+h+v -U 'sample A.fq' -U sample_B.fastq "
        "-S /work/centrifuge/centrifuge_output.tsv --report-file /work/centrifuge/centrifuge_report.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "centrifuge" / "centrifuge_output.tsv",
        tmp_path / "centrifuge" / "centrifuge_report.tsv",
    ]


def test_centrifuge_renders_paired_sam_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("centrifuge")

    assert node_class.render_command(
        {
            "db": "/indexes/bacteria",
            "paired_reads": [
                {"forward": "reads R1.fq", "reverse": "reads R2.fq"},
                ("lane2_R1.fq", "lane2_R2.fq"),
            ],
            "out_fmt": "sam",
            "tab_fmt_cols": "readID,taxID,score",
            "nofw": True,
            "non_deterministic": True,
            "threads": 4,
            "output": "/work/centrifuge",
        }
    ) == (
        "centrifuge --out-fmt sam --tab-fmt-cols readID,taxID,score --threads 4 "
        "--nofw --non-deterministic --min-hitlen 22 -x /indexes/bacteria "
        "-1 'reads R1.fq' -2 'reads R2.fq' -1 lane2_R1.fq -2 lane2_R2.fq "
        "-S /work/centrifuge/centrifuge_output.sam --report-file /work/centrifuge/centrifuge_report.tsv"
    )

    assert node_class.PLAN_OUTPUTS({"out_fmt": "sam"}, tmp_path) == [
        tmp_path / "centrifuge" / "centrifuge_output.sam",
        tmp_path / "centrifuge" / "centrifuge_report.tsv",
    ]


def test_centrifuge_renders_sra_command_and_validates_wrapper_inputs(tmp_path: Path) -> None:
    node_class = _node_class("centrifuge")

    assert node_class.render_command(
        {
            "db": "/indexes/refseq",
            "sra": "SRR353653,SRR353654",
            "output": "/work/centrifuge",
        }
    ) == (
        "centrifuge --out-fmt tab --tab-fmt-cols "
        "readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches "
        "--threads 1 --min-hitlen 22 -x /indexes/refseq --sra-acc SRR353653,SRR353654 "
        "-S /work/centrifuge/centrifuge_output.tsv --report-file /work/centrifuge/centrifuge_report.tsv"
    )

    assert node_class.VALIDATE_INPUTS({"unpaired_reads": ["sample.fq"]}) == "Centrifuge database is required"
    assert node_class.VALIDATE_INPUTS({"db": "/indexes/refseq"}) == (
        "At least one unpaired read, paired read collection, or SRA accession is required"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/indexes/refseq", "unpaired_reads": ["sample.fq"], "norc": True, "nofw": True}) == (
        "Centrifuge cannot disable both forward and reverse-complement mapping"
    )
    assert node_class.VALIDATE_INPUTS({"db": "/indexes/refseq", "unpaired_reads": ["sample.fq"], "min_hitlen": 15}) == (
        "Minimum hit length must be at least 16"
    )
    assert node_class.VALIDATE_INPUTS(
        {"db": "/indexes/refseq", "unpaired_reads": ["sample.fq"], "tab_fmt_cols": "FooBar"}
    ) == "Unsupported Centrifuge tabular output column: FooBar"
    assert node_class.VALIDATE_INPUTS({"db": "/indexes/refseq", "sra": "SRR353653,SRR353654"}) is True

    assert node_class.PLAN_OUTPUTS({"out_fmt": "tab"}, tmp_path) == [
        tmp_path / "centrifuge" / "centrifuge_output.tsv",
        tmp_path / "centrifuge" / "centrifuge_report.tsv",
    ]


def test_galaxy_parity_second_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "mash_dist": {
            "display_name": "Mash Dist",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "mash_sketch": {
            "display_name": "Mash Sketch",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "mash_paste": {
            "display_name": "Mash Paste",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "mash_screen": {
            "display_name": "Mash Screen",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-019-1841-x",
        },
        "fastani": {
            "display_name": "FastANI",
            "category": "genomics",
            "required_executables": ["fastANI"],
            "required_conda_packages": ["fastani"],
            "doi": "10.1038/s41467-018-07641-9",
        },
        "lofreq_call": {
            "display_name": "LoFreq Call",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "lofreq_alnqual": {
            "display_name": "LoFreq Alignment Quality",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "lofreq_indelqual": {
            "display_name": "LoFreq Indel Quality",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1101/gr.112326.110",
        },
        "lofreq_filter": {
            "display_name": "LoFreq Filter",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "lofreq_viterbi": {
            "display_name": "LoFreq Viterbi Realignment",
            "category": "variant",
            "required_executables": ["lofreq", "samtools"],
            "required_conda_packages": ["lofreq", "samtools"],
            "doi": "10.1093/nar/gks918",
        },
        "freyja_variants": {
            "display_name": "Freyja Variants",
            "category": "variant",
            "required_executables": ["freyja"],
            "required_conda_packages": ["freyja"],
            "doi": "10.1038/s41586-022-05049-6",
        },
        "freyja_demix": {
            "display_name": "Freyja Demix",
            "category": "variant",
            "required_executables": ["freyja", "sed"],
            "required_conda_packages": ["freyja", "sed"],
            "doi": "10.1038/s41586-022-05049-6",
        },
        "freyja_boot": {
            "display_name": "Freyja Boot",
            "category": "variant",
            "required_executables": ["freyja"],
            "required_conda_packages": ["freyja"],
            "doi": "10.1038/s41586-022-05049-6",
        },
        "freyja_aggregate_plot": {
            "display_name": "Freyja Aggregate Plot",
            "category": "variant",
            "required_executables": ["freyja"],
            "required_conda_packages": ["freyja"],
            "doi": "10.1038/s41586-022-05049-6",
        },
        "preseq_c_curve": {
            "display_name": "Preseq c_curve",
            "category": "qc",
            "required_executables": ["preseq"],
            "required_conda_packages": ["preseq"],
            "doi": "10.1038/nmeth.2375",
        },
        "preseq_lc_extrap": {
            "display_name": "Preseq lc_extrap",
            "category": "qc",
            "required_executables": ["preseq"],
            "required_conda_packages": ["preseq"],
            "doi": "10.1038/nmeth.2375",
        },
        "abyss_pe": {
            "display_name": "ABySS",
            "category": "assembly",
            "required_executables": ["abyss-pe"],
            "required_conda_packages": ["abyss", "bwa"],
            "doi": "10.1101/gr.214346.116",
        },
        "bayescan": {
            "display_name": "BayeScan",
            "category": "population_genetics",
            "required_executables": ["bayescan2"],
            "required_conda_packages": ["bayescan"],
            "doi": "10.1534/genetics.108.092221",
        },
        "bellerophon": {
            "display_name": "Bellerophon",
            "category": "assembly",
            "required_executables": ["bellerophon", "samtools"],
            "required_conda_packages": ["bellerophon", "samtools"],
            "doi": "10.1038/s41586-021-03451-0",
        },
        "chromeister": {
            "display_name": "Chromeister",
            "category": "comparative_genomics",
            "required_executables": ["CHROMEISTER", "compute_score.R", "compute_score-nogrid.R", "detect_events.py"],
            "required_conda_packages": ["chromeister"],
            "doi": "10.1038/s41598-019-46773-w",
        },
        "bigwig_outlier_bed": {
            "display_name": "Bigwig outliers to bed features",
            "category": "genomics",
            "required_executables": ["python"],
            "required_conda_packages": ["python", "numpy", "pybigtools"],
            "doi": "10.1093/bioinformatics/btae350",
        },
        "ampligone": {
            "display_name": "AmpliGone",
            "category": "sequence",
            "required_executables": ["ampligone"],
            "required_conda_packages": ["AmpliGone"],
            "doi": "10.5281/zenodo.7684307",
        },
        "binette": {
            "display_name": "Binette",
            "category": "metagenomics",
            "required_executables": ["binette"],
            "required_conda_packages": ["binette"],
            "doi": "10.21105/joss.06782",
        },
        "bin_refiner": {
            "display_name": "Binning refiner",
            "category": "metagenomics",
            "required_executables": ["Binning_refiner"],
            "required_conda_packages": ["binning_refiner"],
            "doi": "10.1093/bioinformatics/btx086",
        },
        "beagle": {
            "display_name": "Beagle",
            "category": "variant",
            "required_executables": ["beagle"],
            "required_conda_packages": ["beagle"],
            "doi": "10.1016/j.ajhg.2018.07.015",
        },
        "breseq": {
            "display_name": "breseq",
            "category": "variant",
            "required_executables": ["breseq", "gdtools", "tar"],
            "required_conda_packages": ["breseq", "tar"],
            "doi": "10.1007/978-1-4939-0554-6_12",
        },
        "biscot": {
            "display_name": "BiSCoT",
            "category": "assembly",
            "required_executables": ["biscot"],
            "required_conda_packages": ["biscot", "blat", "ucsc-pslsort", "ucsc-pslreps"],
            "doi": "10.7717/peerj.10150",
        },
        "bigscape": {
            "display_name": "BiG-SCAPE",
            "category": "secondary_metabolism",
            "required_executables": ["bigscape", "hmmpress"],
            "required_conda_packages": ["bigscape"],
            "doi": "10.1038/s41589-019-0400-9",
        },
        "compleasm": {
            "display_name": "compleasm",
            "category": "assembly",
            "required_executables": ["compleasm"],
            "required_conda_packages": ["compleasm"],
            "doi": "10.1101/2023.06.03.543588",
        },
        "eastr": {
            "display_name": "EASTR",
            "category": "rna_seq",
            "required_executables": ["eastr", "bowtie2-build"],
            "required_conda_packages": ["eastr-cpp", "bowtie2"],
            "doi": "10.1038/s41467-023-43017-4",
        },
        "export2graphlan": {
            "display_name": "Export to GraPhlAn",
            "category": "visualization",
            "required_executables": ["export2graphlan.py"],
            "required_conda_packages": ["export2graphlan"],
            "doi": "10.7717/peerj.1029",
        },
        "graphlan_annotate": {
            "display_name": "GraPhlAn Annotate",
            "category": "visualization",
            "required_executables": ["graphlan_annotate.py"],
            "required_conda_packages": ["graphlan"],
            "doi": "10.7717/peerj.1029",
        },
        "graphlan": {
            "display_name": "GraPhlAn",
            "category": "visualization",
            "required_executables": ["graphlan.py"],
            "required_conda_packages": ["graphlan"],
            "doi": "10.7717/peerj.1029",
        },
        "exonerate": {
            "display_name": "Exonerate",
            "category": "alignment",
            "required_executables": ["exonerate", "python"],
            "required_conda_packages": ["exonerate", "python", "bcbiogff"],
            "doi": "10.1186/1471-2105-6-31",
        },
        "evidencemodeler": {
            "display_name": "EVidenceModeler",
            "category": "annotation",
            "required_executables": ["EVidenceModeler"],
            "required_conda_packages": ["evidencemodeler"],
            "doi": "10.1186/gb-2008-9-1-r7",
        },
        "comebin": {
            "display_name": "COMEBin",
            "category": "metagenomics",
            "required_executables": ["run_comebin.sh"],
            "required_conda_packages": ["comebin"],
            "doi": "10.1038/s41467-023-44290-z",
        },
        "comebin_bam": {
            "display_name": "Generate BAM file for COMEBin",
            "category": "metagenomics",
            "required_executables": ["gen_cov_file.sh"],
            "required_conda_packages": ["comebin"],
            "doi": "10.1038/s41467-023-44290-z",
        },
        "drep_compare": {
            "display_name": "dRep compare",
            "category": "metagenomics",
            "required_executables": ["dRep"],
            "required_conda_packages": ["drep"],
            "doi": "10.1038/ismej.2017.126",
        },
        "drep_dereplicate": {
            "display_name": "dRep dereplicate",
            "category": "metagenomics",
            "required_executables": ["dRep"],
            "required_conda_packages": ["drep", "checkm-genome"],
            "doi": "10.1038/ismej.2017.126",
        },
        "cami_amber": {
            "display_name": "CAMI AMBER",
            "category": "metagenomics",
            "required_executables": ["amber.py"],
            "required_conda_packages": ["cami-amber"],
            "doi": "10.1093/gigascience/giy069",
        },
        "cami_amber_add": {
            "display_name": "CAMI AMBER add length column",
            "category": "metagenomics",
            "required_executables": ["add_length_column.py"],
            "required_conda_packages": ["cami-amber"],
            "doi": "10.1093/gigascience/giy069",
        },
        "cami_amber_convert": {
            "display_name": "CAMI AMBER convert to biobox",
            "category": "metagenomics",
            "required_executables": ["convert_fasta_bins_to_biobox_format.py"],
            "required_conda_packages": ["cami-amber"],
            "doi": "10.1093/gigascience/giy069",
        },
        "fargene": {
            "display_name": "fargene",
            "category": "annotation",
            "required_executables": ["fargene", "tar"],
            "required_conda_packages": ["fargene", "tar"],
            "doi": "10.1186/s40168-019-0670-1",
        },
        "metabat2": {
            "display_name": "MetaBAT2",
            "category": "metagenomics",
            "required_executables": ["metabat2"],
            "required_conda_packages": ["metabat2"],
            "doi": "10.7717/peerj.7359",
        },
        "metabat2_jgi_summarize_bam_contig_depths": {
            "display_name": "Calculate contig depths",
            "category": "metagenomics",
            "required_executables": ["jgi_summarize_bam_contig_depths"],
            "required_conda_packages": ["metabat2"],
            "doi": "10.7717/peerj.7359",
        },
        "fastspar": {
            "display_name": "FastSpar",
            "category": "metagenomics",
            "required_executables": ["fastspar"],
            "required_conda_packages": ["fastspar"],
            "doi": "10.1093/bioinformatics/bty734",
        },
        "fastspar_reduce": {
            "display_name": "FastSpar: Reduce correlation table",
            "category": "metagenomics",
            "required_executables": ["fastspar_reduce"],
            "required_conda_packages": ["fastspar"],
            "doi": "10.1093/bioinformatics/bty734",
        },
        "fastspar_pvalues": {
            "display_name": "FastSpar: estimate p-values",
            "category": "metagenomics",
            "required_executables": ["fastspar", "fastspar_bootstrap", "fastspar_pvalues", "parallel"],
            "required_conda_packages": ["fastspar", "parallel"],
            "doi": "10.1093/bioinformatics/bty734",
        },
        "taxonkit_name2taxid": {
            "display_name": "Name2taxid",
            "category": "taxonomy",
            "required_executables": ["taxonkit", "tar"],
            "required_conda_packages": ["taxonkit", "tar"],
            "doi": "10.1016/j.jgg.2021.03.006",
        },
        "ivar_trim": {
            "display_name": "iVar Trim",
            "category": "variant",
            "required_executables": ["scheme-convert", "ivar", "samtools"],
            "required_conda_packages": ["ivar", "viramp-hub", "samtools"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_variants": {
            "display_name": "iVar Variants",
            "category": "variant",
            "required_executables": ["samtools", "ivar"],
            "required_conda_packages": ["samtools", "ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_consensus": {
            "display_name": "iVar Consensus",
            "category": "variant",
            "required_executables": ["samtools", "ivar"],
            "required_conda_packages": ["samtools", "ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_filtervariants": {
            "display_name": "iVar Filter Variants",
            "category": "variant",
            "required_executables": ["ivar"],
            "required_conda_packages": ["ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_removereads": {
            "display_name": "iVar Remove Reads",
            "category": "variant",
            "required_executables": ["scheme-convert", "ivar", "python"],
            "required_conda_packages": ["ivar", "viramp-hub", "python"],
            "doi": "10.1186/s13059-018-1618-7",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith(("https://", "http://"))
        assert "Galaxy" in node_info["search_aliases"]


def test_mash_dist_renders_distance_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_dist")

    assert node_class.render_command(
        {
            "reference": "ref.msh",
            "query": "query.msh",
            "table_output": True,
            "threads": 6,
            "pvalue": 0.05,
            "distance": 0.25,
            "output": "/work/mash_dist",
        }
    ) == [
        "mash",
        "dist",
        "-t",
        "-p",
        "6",
        "-v",
        "0.05",
        "-d",
        "0.25",
        "ref.msh",
        "query.msh",
        ">",
        "/work/mash_dist/distances.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_dist" / "distances.tsv"]


def test_mash_sketch_renders_reads_and_assembly_commands(tmp_path: Path) -> None:
    node_class = _node_class("mash_sketch")
    info = _registry().object_info()["mash_sketch"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["sketch"]
    assert node_class.render_command(
        {
            "reads_assembly_selector": "reads",
            "reads_input_selector": "single",
            "reads": "reads.fastq.gz",
            "minimum_kmer_copies": 10,
            "target_coverage": 30,
            "genome_size": 5000000,
            "sketch_size": 5000,
            "kmer_size": 21,
            "prob_threshold": 0.01,
            "output": "/work/mash_sketch",
        }
    ) == (
        "ln -sf reads.fastq.gz reads.fastq.gz && "
        "mash sketch -s 5000 -k 21 -w 0.01 -m 10 -r -c 30 -g 5000000 "
        "reads.fastq.gz -o /work/mash_sketch/sketch"
    )
    assert node_class.render_command(
        {
            "reads_assembly_selector": "assembly",
            "assembly": "contigs.fasta",
            "individual_sequences": True,
            "threads": 8,
            "sketch_size": 1000,
            "kmer_size": 17,
            "prob_threshold": 0.1,
            "output": "/work/mash_sketch",
        }
    ) == (
        "ln -sf contigs.fasta contigs.fasta && "
        "mash sketch -s 1000 -k 17 -w 0.1 -p 8 -i contigs.fasta -o /work/mash_sketch/sketch"
    )
    assert node_class.render_command(
        {
            "reads_assembly_selector": "reads",
            "reads_input_selector": "paired",
            "reads_1": "L1 R1.fastq.gz",
            "reads_2": "L1 R2.fastq.gz",
            "minimum_kmer_copies": 2,
            "output": "/work/mash_sketch",
        }
    ) == (
        "cat 'L1 R1.fastq.gz' 'L1 R2.fastq.gz' > L1_R1.fastq.gz && "
        "mash sketch -s 1000 -k 21 -w 0.01 -m 2 -r L1_R1.fastq.gz -o /work/mash_sketch/sketch"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_sketch" / "sketch.msh"]


def test_mash_paste_renders_merge_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_paste")
    info = _registry().object_info()["mash_paste"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["sketch"]
    assert node_class.render_command(
        {
            "msh_files": ["alpha sketch.msh", "beta.msh"],
            "output": "/work/mash_paste",
        }
    ) == (
        "ln -sf 'alpha sketch.msh' alpha_sketch.msh && "
        "ln -sf beta.msh beta.msh && "
        "mash paste /work/mash_paste/sketch alpha_sketch.msh beta.msh"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_paste" / "sketch.msh"]


def test_mash_screen_renders_single_and_paired_commands_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_screen")
    info = _registry().object_info()["mash_screen"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["screen"]
    assert "10.1186/s13059-019-1841-x" in info["citation_dois"]
    assert "10.1186/s13059-016-0997-x" in info["citation_dois"]
    assert node_class.render_command(
        {
            "queries": "Ref Seq.msh",
            "pool_input_selector": "single",
            "pool": "reads.fastq.gz",
            "winner_takes_all": True,
            "minimum_identity_to_report": 0.8,
            "maximum_p_value_to_report": 0.05,
            "output": "/work/mash_screen",
        }
    ) == (
        "ln -sf 'Ref Seq.msh' queries.msh && "
        "mash screen -w -i 0.8 -v 0.05 queries.msh reads.fastq.gz > /work/mash_screen/screen.tsv"
    )
    assert node_class.render_command(
        {
            "queries": "refs.msh",
            "pool_input_selector": "paired",
            "pool_1": "R1.fastq.gz",
            "pool_2": "R2.fastq.gz",
            "winner_takes_all": False,
            "output": "/work/mash_screen",
        }
    ) == (
        "ln -sf refs.msh queries.msh && "
        "mash screen -i 0.0 -v 1.0 queries.msh R1.fastq.gz R2.fastq.gz > /work/mash_screen/screen.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_screen" / "screen.tsv"]


def test_fastani_renders_many_to_many_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("fastani")

    assert node_class.render_command(
        {
            "query": ["q1.fna", "q2.fna"],
            "reference": ["r1.fna", "r2.fna"],
            "threads": 12,
            "frag_len": 3000,
            "min_fraction": 0.2,
            "kmer": 16,
            "matrix": True,
            "visualize": True,
            "output": "/work/fastani",
        }
    ) == [
        "fastANI",
        "--ql",
        "/work/fastani/query.lst",
        "--rl",
        "/work/fastani/ref.lst",
        "-o",
        "/work/fastani/fastani.tsv",
        "-t",
        "12",
        "--fragLen",
        "3000",
        "--minFraction",
        "0.2",
        "-k",
        "16",
        "--matrix",
        "--visualize",
    ]

    assert node_class.PLAN_OUTPUTS({"matrix": True, "visualize": True}, tmp_path) == [
        tmp_path / "fastani" / "fastani.tsv",
        tmp_path / "fastani" / "fastani.tsv.matrix",
        tmp_path / "fastani" / "fastani.tsv.visual",
    ]


def test_fastani_run_writes_many_to_many_list_files(tmp_path: Path) -> None:
    node_class = _node_class("fastani")
    context = _RecordingCommandContext(tmp_path / "fastani")

    result = asyncio.run(
        node_class().run(
            query=["q1.fna", "q2.fna"],
            reference=["r1.fna", "r2.fna"],
            threads=2,
            matrix=True,
            visualize=True,
            context=context,
            output_dir=tmp_path,
        )
    )

    assert result == (
        str(tmp_path / "fastani" / "fastani.tsv"),
        str(tmp_path / "fastani" / "fastani.tsv.matrix"),
        str(tmp_path / "fastani" / "fastani.tsv.visual"),
    )
    assert (tmp_path / "fastani" / "query.lst").read_text(encoding="utf-8") == "q1.fna\nq2.fna\n"
    assert (tmp_path / "fastani" / "ref.lst").read_text(encoding="utf-8") == "r1.fna\nr2.fna\n"
    assert context.commands


def test_fastani_run_writes_single_file_lists_for_planned_outputs(tmp_path: Path) -> None:
    node_class = _node_class("fastani")
    context = _RecordingCommandContext(tmp_path / "fastani")

    result = asyncio.run(
        node_class().run(
            query="q1.fna",
            reference="r1.fna",
            threads=2,
            context=context,
            output_dir=tmp_path,
        )
    )

    assert result == (
        str(tmp_path / "fastani" / "fastani.tsv"),
    )
    assert (tmp_path / "fastani" / "query.lst").read_text(encoding="utf-8") == "q1.fna\n"
    assert (tmp_path / "fastani" / "ref.lst").read_text(encoding="utf-8") == "r1.fna\n"


def test_lofreq_call_renders_configured_variant_call_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_call")

    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "bed": "targets.bed",
            "variant_types": "--call-indels",
            "threads": 4,
            "min_cov": 5,
            "max_depth": 100000,
            "use_orphan": True,
            "min_bq": 10,
            "min_alt_bq": 12,
            "def_alt_bq": 20,
            "alnquals_to_use": "-A",
            "extended_baq": "-e",
            "min_mq": 20,
            "max_mq": 60,
            "src_qual": True,
            "ign_vcf": ["known.vcf.gz", "panel.vcf"],
            "def_nm_q": -1,
            "min_jq": 5,
            "min_alt_jq": 7,
            "def_alt_jq": 9,
            "sig": 0.01,
            "bonf": "dynamic",
            "no_default_filter": True,
            "output": "/work/lofreq",
        }
    ) == [
        "lofreq",
        "call-parallel",
        "--pp-threads",
        "4",
        "--verbose",
        "--ref",
        "ref.fa",
        "--out",
        "/work/lofreq/variants.vcf",
        "--call-indels",
        "--bed",
        "targets.bed",
        "--min-cov",
        "5",
        "--max-depth",
        "100000",
        "--use-orphan",
        "--min-bq",
        "10",
        "--min-alt-bq",
        "12",
        "--def-alt-bq",
        "20",
        "-A",
        "-e",
        "--min-mq",
        "20",
        "--max-mq",
        "60",
        "--src-qual",
        "--ign-vcf",
        "known.vcf.gz,panel.vcf",
        "--def-nm-q",
        "-1",
        "--min-jq",
        "5",
        "--min-alt-jq",
        "7",
        "--def-alt-jq",
        "9",
        "--sig",
        "0.01",
        "--bonf",
        "dynamic",
        "--no-default-filter",
        "reads.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_call" / "variants.vcf"]


def test_lofreq_alnqual_renders_alignment_quality_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_alnqual")
    info = _registry().object_info()["lofreq_alnqual"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["reads_with_alignment_qualities"]
    assert info["input"]["optional"]["extended_baq"][1]["displayOptions"] == {
        "show": {"alnquals_to_use": ["", "-A"]},
    }
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "",
            "extended_baq": True,
            "recompute_all": False,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "-B",
            "recompute_all": True,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "-B",
        "-r",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "-B",
            "extended_baq": False,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "-B",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_alnqual" / "alnqual.bam"]


def test_lofreq_indelqual_renders_uniform_and_dindel_commands_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_indelqual")
    info = _registry().object_info()["lofreq_indelqual"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["reads_with_indel_qualities"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert "10.1101/gr.112326.110" in info["citation_dois"]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "uniform",
            "insertions": 20,
            "deletions": 30,
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--uniform",
        "20,30",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "uniform",
            "insertions": 20,
            "deletions": "",
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--uniform",
        "20",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "dindel",
            "reference": "ref.fa",
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--dindel",
        "--ref",
        "ref.fa",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_indelqual" / "indelqual.bam"]


def test_lofreq_filter_renders_quality_coverage_af_and_strand_bias_filters(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_filter")
    info = _registry().object_info()["lofreq_filter"]

    assert info["output"] == ["VCF"]
    assert info["output_name"] == ["filtered_variants"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert info["input"]["optional"]["snvqual_thresh"][1]["displayOptions"] == {
        "show": {"snvqual_filter": ["min-phred"]},
    }
    assert info["input"]["optional"]["indelqual_alpha"][1]["displayOptions"] == {
        "show": {"indelqual_filter": ["mtc"]},
    }
    assert node_class.render_command(
        {
            "invcf": "calls.vcf",
            "keep_only": "",
            "snvqual_filter": "min-phred",
            "snvqual_thresh": 38,
            "indelqual_filter": "min-phred",
            "indelqual_thresh": 20,
            "cov_min": 12,
            "cov_max": 300,
            "af_min": 0.02,
            "af_max": 0.7,
            "strand_bias": "mtc",
            "sb_mtc": "fdr",
            "sb_alpha": 0.001,
            "sb_compound": False,
            "sb_indels": True,
            "flag_or_drop": "--print-all",
            "output": "/work/lofreq_filter",
        }
    ) == [
        "lofreq",
        "filter",
        "-i",
        "calls.vcf",
        "--no-defaults",
        "--verbose",
        "--print-all",
        "-Q",
        "38",
        "-K",
        "20",
        "-v",
        "12",
        "-V",
        "300",
        "-a",
        "0.02",
        "-A",
        "0.7",
        "-b",
        "fdr",
        "-c",
        "0.001",
        "--sb-no-compound",
        "--sb-incl-indels",
        "-o",
        "/work/lofreq_filter/filtered.vcf",
    ]
    assert node_class.render_command(
        {
            "invcf": "calls.vcf",
            "keep_only": "--only-snvs",
            "snvqual_filter": "mtc",
            "snvqual_mtc": "bonf",
            "snvqual_alpha": 0.01,
            "snvqual_ntests": 66,
            "cov_min": 0,
            "cov_max": 0,
            "af_min": 0.05,
            "af_max": 1,
            "strand_bias": "no",
            "output": "/work/lofreq_filter",
        }
    ) == [
        "lofreq",
        "filter",
        "-i",
        "calls.vcf",
        "--no-defaults",
        "--verbose",
        "--only-snvs",
        "-q",
        "bonf",
        "-r",
        "0.01",
        "-s",
        "66",
        "-v",
        "0",
        "-V",
        "0",
        "-a",
        "0.05",
        "-A",
        "1",
        "-o",
        "/work/lofreq_filter/filtered.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_filter" / "filtered.vcf"]


def test_lofreq_viterbi_renders_realignment_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_viterbi")
    info = _registry().object_info()["lofreq_viterbi"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["realigned_reads"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert info["input"]["optional"]["defqual"][1]["displayOptions"] == {
        "show": {"replace_bq2": ["fixed"]},
    }
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "keepflags": True,
            "replace_bq2": "fixed",
            "defqual": 17,
            "threads": 8,
            "output": "/work/lofreq_viterbi",
        }
    ) == [
        "lofreq",
        "viterbi",
        "--ref",
        "ref.fa",
        "--keepflags",
        "--defqual",
        "17",
        "--out",
        "/work/lofreq_viterbi/tmp.bam",
        "reads.bam",
        "&&",
        "samtools",
        "sort",
        "--no-PG",
        "-T",
        "${TMPDIR:-.}",
        "-@",
        "8",
        "-O",
        "BAM",
        "-o",
        "/work/lofreq_viterbi/realigned.bam",
        "/work/lofreq_viterbi/tmp.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "replace_bq2": "dynamic",
            "output": "/work/lofreq_viterbi",
        }
    ) == [
        "lofreq",
        "viterbi",
        "--ref",
        "ref.fa",
        "--defqual",
        "-1",
        "--out",
        "/work/lofreq_viterbi/tmp.bam",
        "reads.bam",
        "&&",
        "samtools",
        "sort",
        "--no-PG",
        "-T",
        "${TMPDIR:-.}",
        "-@",
        "1",
        "-O",
        "BAM",
        "-o",
        "/work/lofreq_viterbi/realigned.bam",
        "/work/lofreq_viterbi/tmp.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_viterbi" / "realigned.bam"]


def test_ivar_trim_renders_primer_trim_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_trim")
    info = _registry().object_info()["ivar_trim"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["trimmed_bam"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert info["input"]["optional"]["amplicon_info"][1]["displayOptions"] == {
        "show": {"amplicon_mode": ["provided"]},
    }
    assert info["input"]["optional"]["min_len"][1]["displayOptions"] == {
        "show": {"trimmed_length_filter": ["custom"]},
    }
    assert node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "provided",
            "amplicon_info": "pairs.tsv",
            "primer_pos_wiggle": 3,
            "include_reads_without_primers": True,
            "trimmed_length_filter": "custom",
            "min_len": 45,
            "min_qual": 25,
            "window_width": 6,
            "threads": 8,
            "output": "/work/ivar_trim",
        }
    ) == [
        "scheme-convert",
        "--to",
        "bed",
        "--bed-type",
        "ivar",
        "-o",
        "/work/ivar_trim/ivar.bed",
        "primers.bed",
        "&&",
        "scheme-convert",
        "-a",
        "pairs.tsv",
        "--to",
        "amplicon-info",
        "-r",
        "outer",
        "-o",
        "/work/ivar_trim/amplicon_info.tsv",
        "/work/ivar_trim/ivar.bed",
        "&&",
        "ivar",
        "trim",
        "-i",
        "aligned.sorted.bam",
        "-b",
        "/work/ivar_trim/ivar.bed",
        "-f",
        "/work/ivar_trim/amplicon_info.tsv",
        "-x",
        "3",
        "-e",
        "-m",
        "45",
        "-q",
        "25",
        "-s",
        "6",
        "|",
        "samtools",
        "sort",
        "-@",
        "8",
        "-T",
        "${TMPDIR:-.}",
        "-o",
        "/work/ivar_trim/trimmed.sorted.bam",
        "-",
    ]

    computed_cmd = node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "computed",
            "trimmed_length_filter": "auto",
            "output": "/work/ivar_trim",
        }
    )
    assert "-a" not in computed_cmd
    assert "-f" in computed_cmd
    assert "-1" in computed_cmd

    no_filter_cmd = node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "none",
            "trimmed_length_filter": "off",
            "output": "/work/ivar_trim",
        }
    )
    assert "amplicon-info" not in no_filter_cmd
    assert "-f" not in no_filter_cmd
    assert no_filter_cmd[no_filter_cmd.index("-m") + 1] == "0"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_trim" / "trimmed.sorted.bam"]


def test_freyja_variants_renders_variant_and_depth_command_outputs(tmp_path: Path) -> None:
    node_class = _node_class("freyja_variants")
    info = _registry().object_info()["freyja_variants"]

    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["variants", "depths"]
    assert "10.1038/s41586-022-05049-6" in info["citation_dois"]
    assert node_class.render_command(
        {
            "bam_file": "aligned.bam",
            "ref_file": "NC_045512_Hu-1.fasta",
            "output": "/work/freyja_variants",
        }
    ) == [
        "freyja",
        "variants",
        "aligned.bam",
        "--variants",
        "/work/freyja_variants/variants.tsv",
        "--depths",
        "/work/freyja_variants/depths.tsv",
        "--ref",
        "NC_045512_Hu-1.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "freyja_variants" / "variants.tsv",
        tmp_path / "freyja_variants" / "depths.tsv",
    ]


def test_freyja_demix_renders_lineage_abundance_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("freyja_demix")
    info = _registry().object_info()["freyja_demix"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["abundances"]
    assert "10.1038/s41586-022-05049-6" in info["citation_dois"]
    assert info["input"]["optional"]["usher_barcodes"][1]["displayOptions"] == {
        "show": {"barcodes_source": ["custom"]},
    }
    assert node_class.render_command(
        {
            "variants_in": "variants.tsv",
            "depth_file": "depths.tsv",
            "sample_name_source": "manual",
            "sample_name": "Sample One",
            "barcodes_source": "custom",
            "usher_barcodes": "barcodes.csv",
            "meta": "lineage_meta.json",
            "eps": 0.0001,
            "confirmedonly": True,
            "wgisaid": True,
            "depth_cutoff": 20,
            "output": "/work/freyja_demix",
        }
    ) == [
        "ln",
        "-sf",
        "barcodes.csv",
        "/work/freyja_demix/usher_barcodes.csv",
        "&&",
        "ln",
        "-sf",
        "variants.tsv",
        "/work/freyja_demix/Sample_One.tsv",
        "&&",
        "freyja",
        "demix",
        "/work/freyja_demix/Sample_One.tsv",
        "depths.tsv",
        "--eps",
        "0.0001",
        "--meta",
        "lineage_meta.json",
        "--confirmedonly",
        "--wgisaid",
        "--barcodes",
        "/work/freyja_demix/usher_barcodes.csv",
        "--covcut",
        "20",
        "--output",
        "/work/freyja_demix/abundances_raw.tsv",
        "&&",
        "sed",
        "s/Sample_One.tsv/Sample One/",
        "/work/freyja_demix/abundances_raw.tsv",
        ">",
        "/work/freyja_demix/abundances.tsv",
    ]

    auto_cmd = node_class.render_command(
        {
            "variants_in": "/inputs/wastewater-sample.vcf",
            "depth_file": "depths.tsv",
            "barcodes_source": "repo",
            "output": "/work/freyja_demix",
        }
    )
    assert "/work/freyja_demix/wastewater-sample.vcf" in auto_cmd
    assert "--barcodes" not in auto_cmd

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "freyja_demix" / "abundances.tsv"]


def test_freyja_boot_renders_bootstrap_command_and_optional_plots(tmp_path: Path) -> None:
    node_class = _node_class("freyja_boot")
    info = _registry().object_info()["freyja_boot"]

    assert info["output"] == ["CSV", "CSV", "PDF", "PDF"]
    assert info["output_name"] == [
        "boot_lineages",
        "boot_summarized",
        "boot_lineages_plot",
        "boot_summarized_plot",
    ]
    assert "10.1038/s41586-022-05049-6" in info["citation_dois"]
    assert info["input"]["optional"]["usher_barcodes"][1]["displayOptions"] == {
        "show": {"barcodes_source": ["custom"]},
    }
    assert node_class.render_command(
        {
            "variants_file": "variants.tsv",
            "depth_file": "depths.tsv",
            "barcodes_source": "custom",
            "usher_barcodes": "barcodes.csv",
            "meta": "lineage_meta.json",
            "eps": 0.0001,
            "confirmedonly": True,
            "pathogen": "SARS-CoV-2",
            "threads": 8,
            "nb": 100,
            "boxplot_pdf": True,
            "output": "/work/freyja_boot",
        }
    ) == [
        "ln",
        "-sf",
        "barcodes.csv",
        "/work/freyja_boot/usher_barcodes.csv",
        "&&",
        "freyja",
        "boot",
        "variants.tsv",
        "depths.tsv",
        "--eps",
        "0.0001",
        "--meta",
        "lineage_meta.json",
        "--confirmedonly",
        "--pathogen",
        "SARS-CoV-2",
        "--nt",
        "${GALAXY_SLOTS:-8}",
        "--nb",
        "100",
        "--output_base",
        "/work/freyja_boot/boot_output",
        "--barcodes",
        "/work/freyja_boot/usher_barcodes.csv",
        "--boxplot",
        "pdf",
    ]

    assert node_class.PLAN_OUTPUTS({"boxplot_pdf": True}, tmp_path) == [
        tmp_path / "freyja_boot" / "boot_output_lineages.csv",
        tmp_path / "freyja_boot" / "boot_output_summarized.csv",
        tmp_path / "freyja_boot" / "boot_output_lineages.pdf",
        tmp_path / "freyja_boot" / "boot_output_summarized.pdf",
    ]
    assert node_class.PLAN_OUTPUTS({"boxplot_pdf": False}, tmp_path) == [
        tmp_path / "freyja_boot" / "boot_output_lineages.csv",
        tmp_path / "freyja_boot" / "boot_output_summarized.csv",
    ]


def test_freyja_aggregate_plot_renders_aggregate_dashboard_and_plot_outputs(tmp_path: Path) -> None:
    node_class = _node_class("freyja_aggregate_plot")
    info = _registry().object_info()["freyja_aggregate_plot"]

    assert info["output"] == ["TSV", "HTML_REPORT", "PDF"]
    assert info["output_name"] == ["aggregated", "abundances_dashboard", "abundances_plot"]
    assert "10.1038/s41586-022-05049-6" in info["citation_dois"]
    assert node_class.render_command(
        {
            "aggregation_mode": "aggregate",
            "demix_file": ["sample A.tsv", "sample_B.tsv"],
            "plot_format": "plot_and_dash",
            "csv_meta": "metadata.csv",
            "plot_title": "Local WW Dashboard",
            "plot_intro": "Variant surveillance",
            "lineages": True,
            "mincov": 75,
            "interval": "D",
            "output": "/work/freyja_aggregate_plot",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/freyja_aggregate_plot/demix_outputs",
        "&&",
        "ln",
        "-sf",
        "sample A.tsv",
        "/work/freyja_aggregate_plot/demix_outputs/sample_A.tsv",
        "&&",
        "ln",
        "-sf",
        "sample_B.tsv",
        "/work/freyja_aggregate_plot/demix_outputs/sample_B.tsv",
        "&&",
        "freyja",
        "aggregate",
        "/work/freyja_aggregate_plot/demix_outputs",
        "--output",
        "/work/freyja_aggregate_plot/aggregated.tsv",
        "&&",
        "printf",
        "%s",
        "Local WW Dashboard",
        ">",
        "/work/freyja_aggregate_plot/plot_title.txt",
        "&&",
        "printf",
        "%s",
        "Variant surveillance",
        ">",
        "/work/freyja_aggregate_plot/plot_intro.txt",
        "&&",
        "freyja",
        "dash",
        "--mincov",
        "75",
        "/work/freyja_aggregate_plot/aggregated.tsv",
        "metadata.csv",
        "/work/freyja_aggregate_plot/plot_title.txt",
        "/work/freyja_aggregate_plot/plot_intro.txt",
        "--output",
        "/work/freyja_aggregate_plot/abundances_dashboard.html",
        "&&",
        "freyja",
        "plot",
        "--lineages",
        "--mincov",
        "75",
        "/work/freyja_aggregate_plot/aggregated.tsv",
        "--output",
        "/work/freyja_aggregate_plot/abundances_plot.pdf",
        "--times",
        "metadata.csv",
        "--interval",
        "D",
        "--windowsize",
        "70",
    ]

    provided_cmd = node_class.render_command(
        {
            "aggregation_mode": "provided",
            "tsv_aggregated": "already_aggregated.tsv",
            "plot_format": "plot",
            "lineages": False,
            "mincov": 60,
            "metadata_mode": "none",
            "output": "/work/freyja_aggregate_plot",
        }
    )
    assert "aggregate" not in provided_cmd
    assert "already_aggregated.tsv" in provided_cmd
    assert "--times" not in provided_cmd

    assert node_class.PLAN_OUTPUTS({"aggregation_mode": "aggregate", "plot_format": "plot_and_dash"}, tmp_path) == [
        tmp_path / "freyja_aggregate_plot" / "aggregated.tsv",
        tmp_path / "freyja_aggregate_plot" / "abundances_dashboard.html",
        tmp_path / "freyja_aggregate_plot" / "abundances_plot.pdf",
    ]
    assert node_class.PLAN_OUTPUTS({"aggregation_mode": "provided", "plot_format": "dash"}, tmp_path) == [
        tmp_path / "freyja_aggregate_plot" / "abundances_dashboard.html",
    ]


def test_preseq_c_curve_renders_library_complexity_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("preseq_c_curve")
    info = _registry().object_info()["preseq_c_curve"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["complexity_curve"]
    assert "10.1038/nmeth.2375" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "step_size": 2000,
            "max_read_len": 150,
            "verbose": True,
            "output": "/work/preseq_c_curve",
        }
    ) == [
        "ln",
        "-sf",
        "aligned.sorted.bam",
        "/work/preseq_c_curve/input.bam",
        "&&",
        "preseq",
        "c_curve",
        "-B",
        "/work/preseq_c_curve/input.bam",
        "-v",
        "-s",
        "2000",
        "-l",
        "150",
        "-o",
        "/work/preseq_c_curve/complexity_curve.tsv",
    ]

    no_limit_cmd = node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "step_size": 1000,
            "output": "/work/preseq_c_curve",
        }
    )
    assert "-l" not in no_limit_cmd
    assert "-v" not in no_limit_cmd
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "preseq_c_curve" / "complexity_curve.tsv"]


def test_preseq_lc_extrap_renders_library_yield_extrapolation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("preseq_lc_extrap")
    info = _registry().object_info()["preseq_lc_extrap"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["yield_extrapolation"]
    assert "10.1038/nmeth.2375" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "extrap_limit": 100000,
            "step_size": 10000,
            "verbose": True,
            "output": "/work/preseq_lc_extrap",
        }
    ) == [
        "ln",
        "-sf",
        "aligned.sorted.bam",
        "/work/preseq_lc_extrap/input.bam",
        "&&",
        "preseq",
        "lc_extrap",
        "-B",
        "/work/preseq_lc_extrap/input.bam",
        "-v",
        "-e",
        "100000",
        "-s",
        "10000",
        "-o",
        "/work/preseq_lc_extrap/yield_extrapolation.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "preseq_lc_extrap" / "yield_extrapolation.tsv",
    ]


def test_abyss_pe_renders_paired_and_long_read_assembly_command_outputs(tmp_path: Path) -> None:
    node_class = _node_class("abyss_pe")
    info = _registry().object_info()["abyss_pe"]

    assert info["output"] == ["FASTA", "FASTA", "FASTA", "FASTA", "FASTA", "TSV"]
    assert info["output_name"] == ["unitigs", "contigs", "scaffolds", "long_scaffolds", "indels", "stats"]
    assert "10.1101/gr.214346.116" in info["citation_dois"]
    assert "10.1101/gr.089532.108" in info["citation_dois"]
    assert node_class.render_command(
        {
            "libraries": [
                {"type": "lib", "forward": "reads R1.fastq.gz", "reverse": "reads R2.fastq.gz"},
                {"type": "long", "reads": ["long reads.fa"]},
            ],
            "k": 50,
            "K": 25,
            "q": 4,
            "SS": True,
            "s": 500,
            "N": "15-20",
            "threads": 8,
            "memory_mb": 16000,
            "output": "/work/abyss_pe",
        }
    ) == [
        "ln",
        "-sf",
        "reads R1.fastq.gz",
        "/work/abyss_pe/lib_forward_0.fastq.gz",
        "&&",
        "ln",
        "-sf",
        "reads R2.fastq.gz",
        "/work/abyss_pe/lib_reverse_0.fastq.gz",
        "&&",
        "ln",
        "-sf",
        "long reads.fa",
        "/work/abyss_pe/long_1.fa",
        "&&",
        "abyss-pe",
        "name=abyss",
        "j=${GALAXY_SLOTS:-8}",
        "B=$(( ${GALAXY_MEMORY_MB:-16000} * 9 / 10 ))M",
        "k=50",
        "K=25",
        "q=4",
        "SS=--SS",
        "s=500",
        "N=15-20",
        "lib=lib0",
        "long=long1",
        "lib0=/work/abyss_pe/lib_forward_0.fastq.gz /work/abyss_pe/lib_reverse_0.fastq.gz",
        "long1=/work/abyss_pe/long_1.fa",
    ]

    assert node_class.PLAN_OUTPUTS({"libraries": [{"type": "lib"}, {"type": "long"}]}, tmp_path) == [
        tmp_path / "abyss_pe" / "abyss-unitigs.fa",
        tmp_path / "abyss_pe" / "abyss-contigs.fa",
        tmp_path / "abyss_pe" / "abyss-scaffolds.fa",
        tmp_path / "abyss_pe" / "abyss-long-scaffs.fa",
        tmp_path / "abyss_pe" / "abyss-indel.fa",
        tmp_path / "abyss_pe" / "abyss-stats.tab",
    ]
    assert node_class.PLAN_OUTPUTS({"libraries": [{"type": "se", "reads": ["reads.fastq.gz"]}]}, tmp_path) == [
        tmp_path / "abyss_pe" / "abyss-unitigs.fa",
        tmp_path / "abyss_pe" / "abyss-indel.fa",
        tmp_path / "abyss_pe" / "abyss-stats.tab",
    ]


def test_bayescan_renders_population_selection_scan_command_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bayescan")
    info = _registry().object_info()["bayescan"]

    assert info["output"] == ["TXT", "TXT", "TXT", "TXT", "TXT", "TXT"]
    assert info["output_name"] == ["log", "selection", "verification", "acceptance_rate", "pilot_runs", "allele_frequencies"]
    assert "10.1534/genetics.108.092221" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input": "population genotypes.txt",
            "discard_loci_file": "discard loci.tsv",
            "snp_genotypes_matrix": True,
            "fstats": True,
            "sample_size": 7000,
            "thinning_interval": 20,
            "num_pilot_runs": 25,
            "length_pilot_run": 6000,
            "burn": 55000,
            "prior_odds": 12,
            "lower_prior": 0.05,
            "higher_prior": 0.95,
            "threshold": 0.2,
            "pilot_runs": True,
            "allele_frequency": True,
            "output": "/work/bayescan",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/bayescan/output_dir",
        "&&",
        "bayescan2",
        "population genotypes.txt",
        "-od",
        "/work/bayescan/output_dir",
        "-d",
        "discard loci.tsv",
        "-fstat",
        "-snp",
        "-out_pilot",
        "-out_freq",
        "-o",
        "bayescan",
        "-n",
        "7000",
        "-thin",
        "20",
        "-nbp",
        "25",
        "-pilot",
        "6000",
        "-burn",
        "55000",
        "-pr_odds",
        "12",
        "-lb_fis",
        "0.05",
        "-hb_fis",
        "0.95",
        "-aflp_pc",
        "0.2",
        ">",
        "/work/bayescan/bayescan.log",
    ]

    assert node_class.PLAN_OUTPUTS(
        {"pilot_runs": True, "allele_frequency": True},
        tmp_path,
    ) == [
        tmp_path / "bayescan" / "bayescan.log",
        tmp_path / "bayescan" / "output_dir" / "bayescan.sel",
        tmp_path / "bayescan" / "output_dir" / "bayescan_Verif.txt",
        tmp_path / "bayescan" / "output_dir" / "bayescan_AccRte.txt",
        tmp_path / "bayescan" / "output_dir" / "bayescan_prop.txt",
        tmp_path / "bayescan" / "output_dir" / "bayescan_freq.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bayescan" / "bayescan.log",
        tmp_path / "bayescan" / "output_dir" / "bayescan.sel",
        tmp_path / "bayescan" / "output_dir" / "bayescan_Verif.txt",
        tmp_path / "bayescan" / "output_dir" / "bayescan_AccRte.txt",
    ]


def test_bellerophon_renders_chimeric_read_filter_merge_command_output(tmp_path: Path) -> None:
    node_class = _node_class("bellerophon")
    info = _registry().object_info()["bellerophon"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["merged_bam"]
    assert "10.1038/s41586-021-03451-0" in info["citation_dois"]
    assert node_class.render_command(
        {
            "forward": "forward reads.bam",
            "reverse": "reverse reads.sam",
            "forward_format": "bam",
            "reverse_format": "sam",
            "quality": 12,
            "threads": 6,
            "output": "/work/bellerophon",
        }
    ) == [
        "ln",
        "-s",
        "forward reads.bam",
        "/work/bellerophon/forward_input.bam",
        "&&",
        "ln",
        "-s",
        "reverse reads.sam",
        "/work/bellerophon/reverse_input.sam",
        "&&",
        "bellerophon",
        "--forward",
        "/work/bellerophon/forward_input.bam",
        "--reverse",
        "/work/bellerophon/reverse_input.sam",
        "--quality",
        "12",
        "--output",
        "/work/bellerophon/merged_out.bam",
        "--threads",
        "${GALAXY_SLOTS:-6}",
        "&&",
        "samtools",
        "sort",
        "--no-PG",
        "-O",
        "BAM",
        "-o",
        "/work/bellerophon/merged.bam",
        "-@",
        "${GALAXY_SLOTS:-6}",
        "/work/bellerophon/merged_out.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bellerophon" / "merged.bam",
    ]


def test_chromeister_renders_pairwise_genome_comparison_command_outputs(tmp_path: Path) -> None:
    node_class = _node_class("chromeister")
    info = _registry().object_info()["chromeister"]

    assert info["output"] == ["TXT", "IMAGE", "CSV", "TXT", "IMAGE", "TXT"]
    assert info["output_name"] == ["matrix", "dotplot_png", "metainfo_csv", "events_txt", "events_png", "score"]
    assert "10.1038/s41598-019-46773-w" in info["citation_dois"]
    assert node_class.render_command(
        {
            "query": "query genome.fa",
            "db": "reference genome.fa",
            "dimension": 500,
            "kmer": 16,
            "diffuse": 3,
            "grid": False,
            "pngevents": True,
            "output": "/work/chromeister",
        }
    ) == [
        "ln",
        "-s",
        "query genome.fa",
        "/work/chromeister/query_genome.fa",
        "&&",
        "ln",
        "-s",
        "reference genome.fa",
        "/work/chromeister/reference_genome.fa",
        "&&",
        "CHROMEISTER",
        "-query",
        "/work/chromeister/query_genome.fa",
        "-db",
        "/work/chromeister/reference_genome.fa",
        "-dimension",
        "500",
        "-kmer",
        "16",
        "-diffuse",
        "3",
        "-out",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat",
        "&&",
        "compute_score-nogrid.R",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat",
        "500",
        ">",
        "/work/chromeister/comparison_score.txt",
        "&&",
        "detect_events.py",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat.raw.txt",
        "png",
        "&&",
        "mv",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat.events.png",
        "/work/chromeister/events.png",
        "&&",
        "mv",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat",
        "/work/chromeister/comparison_matrix.txt",
        "&&",
        "mv",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat.filt.png",
        "/work/chromeister/dotplot.png",
        "&&",
        "mv",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat.events.txt",
        "/work/chromeister/events.txt",
        "&&",
        "mv",
        "/work/chromeister/query_genome.fa-reference_genome.fa.mat.csv",
        "/work/chromeister/comparison_metainfo.csv",
    ]

    assert node_class.PLAN_OUTPUTS({"pngevents": True}, tmp_path) == [
        tmp_path / "chromeister" / "comparison_matrix.txt",
        tmp_path / "chromeister" / "dotplot.png",
        tmp_path / "chromeister" / "comparison_metainfo.csv",
        tmp_path / "chromeister" / "events.txt",
        tmp_path / "chromeister" / "events.png",
        tmp_path / "chromeister" / "comparison_score.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "chromeister" / "comparison_matrix.txt",
        tmp_path / "chromeister" / "dotplot.png",
        tmp_path / "chromeister" / "comparison_metainfo.csv",
        tmp_path / "chromeister" / "events.txt",
        tmp_path / "chromeister" / "comparison_score.txt",
    ]


def test_bigwig_outlier_bed_renders_conditional_bed_and_table_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bigwig_outlier_bed")
    info = _registry().object_info()["bigwig_outlier_bed"]

    assert info["output"] == ["BED", "BED", "BED", "BED", "TXT"]
    assert info["output_name"] == ["high_low_bed", "high_bed", "low_bed", "zero_bed", "contig_statistics"]
    assert "10.1093/bioinformatics/btae350" in info["citation_dois"]
    assert node_class.render_command(
        {
            "bigwig": ["coverage A.bw", "coverage B.bw"],
            "bigwiglabels": ["sample A", "sample B"],
            "outbeds": "outlohi",
            "tableout": "create",
            "minwin": 25,
            "qhi": 0.95,
            "qlo": 0.05,
            "script": "bigwig_outlier_bed.py",
            "output": "/work/bigwig_outlier_bed",
        }
    ) == [
        "python",
        "bigwig_outlier_bed.py",
        "--bigwig",
        "coverage A.bw",
        "--bigwig",
        "coverage B.bw",
        "--bigwiglabels",
        "sample A",
        "--bigwiglabels",
        "sample B",
        "--outbeds",
        "outlohi",
        "--bedouthi",
        "/work/bigwig_outlier_bed/high_regions.bed",
        "--bedoutlo",
        "/work/bigwig_outlier_bed/low_regions.bed",
        "--minwin",
        "25",
        "--qhi",
        "0.95",
        "--qlo",
        "0.05",
        "--tableoutfile",
        "/work/bigwig_outlier_bed/contig_statistics.txt",
    ]

    assert node_class.PLAN_OUTPUTS({"outbeds": "outlohi", "tableout": "create"}, tmp_path) == [
        tmp_path / "bigwig_outlier_bed" / "high_regions.bed",
        tmp_path / "bigwig_outlier_bed" / "low_regions.bed",
        tmp_path / "bigwig_outlier_bed" / "contig_statistics.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"outbeds": "outtab", "tableout": "donotmake"}, tmp_path) == [
        tmp_path / "bigwig_outlier_bed" / "contig_statistics.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"outbeds": "outzero", "tableout": "donotmake"}, tmp_path) == [
        tmp_path / "bigwig_outlier_bed" / "zero_regions.bed",
    ]


def test_ampligone_renders_primer_removal_command_and_optional_export(tmp_path: Path) -> None:
    node_class = _node_class("ampligone")
    info = _registry().object_info()["ampligone"]

    assert info["output"] == ["FASTQ", "BED"]
    assert info["output_name"] == ["cleaned_reads", "primer_coordinates"]
    assert "10.5281/zenodo.7684307" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "input_ext": "fastqsanger.gz",
            "reference": "SARS CoV 2.fa",
            "primers": "ARTIC primers.fasta",
            "primers_ext": "fasta",
            "export_primers": True,
            "amplicon_type": "fragmented",
            "fragment_lookaround_size": 15,
            "error_rate": 0.08,
            "threads": 8,
            "output": "/work/ampligone",
        }
    ) == [
        "ln",
        "-sf",
        "reads.fastq.gz",
        "/work/ampligone/reads.fastq.gz",
        "&&",
        "touch",
        "/work/ampligone/cleaned_reads.fastq.gz",
        "&&",
        "ln",
        "-sf",
        "/work/ampligone/cleaned_reads.fastq.gz",
        "/work/ampligone/output.fastq.gz",
        "&&",
        "ln",
        "-sf",
        "SARS CoV 2.fa",
        "/work/ampligone/reference.fasta",
        "&&",
        "ln",
        "-sf",
        "ARTIC primers.fasta",
        "/work/ampligone/primers.fasta",
        "&&",
        "touch",
        "/work/ampligone/primer_coordinates.bed",
        "&&",
        "ln",
        "-sf",
        "/work/ampligone/primer_coordinates.bed",
        "/work/ampligone/primers.bed",
        "&&",
        "ampligone",
        "--input",
        "/work/ampligone/reads.fastq.gz",
        "--reference",
        "/work/ampligone/reference.fasta",
        "--primers",
        "/work/ampligone/primers.fasta",
        "--threads",
        "${GALAXY_SLOTS:-8}",
        "--amplicon-type",
        "fragmented",
        "--fragment-lookaround-size",
        "15",
        "--error-rate",
        "0.08",
        "--export-primers",
        "/work/ampligone/primers.bed",
        "--output",
        "/work/ampligone/output.fastq.gz",
    ]

    assert node_class.PLAN_OUTPUTS({"input_ext": "fastqsanger.gz", "primers_ext": "fasta", "export_primers": True}, tmp_path) == [
        tmp_path / "ampligone" / "cleaned_reads.fastq.gz",
        tmp_path / "ampligone" / "primer_coordinates.bed",
    ]
    assert node_class.PLAN_OUTPUTS({"input_ext": "bam", "primers_ext": "bed", "export_primers": True}, tmp_path) == [
        tmp_path / "ampligone" / "cleaned_reads.fastq",
    ]


def test_binette_renders_binning_refinement_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("binette")
    info = _registry().object_info()["binette"]

    assert info["output"] == ["DIRECTORY", "DIRECTORY", "TSV"]
    assert info["output_name"] == ["bins", "quality_reports", "final_quality_report"]
    assert info["input"]["required"]["contig2bin_tables"][1]["multiple"] is True
    assert info["input"]["required"]["contig2bin_tables"][1]["min_items"] == 2
    assert "10.21105/joss.06782" in info["citation_dois"]
    assert node_class.render_command(
        {
            "contig2bin_tables": ["A bins.tsv", "B bins.tsv", "C bins.tsv"],
            "contigs": "all contigs.fasta.gz",
            "proteins": "predicted proteins.faa.gz",
            "min_completeness": 5,
            "contamination_weight": 0,
            "database_type": "his",
            "checkm2_db": "checkm2 tiny database.dmnd",
            "threads": 6,
            "output": "/work/binette",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/binette/input",
        "/work/binette/output",
        "&&",
        "ln",
        "-s",
        "A bins.tsv",
        "/work/binette/input/bin_table_0.tsv",
        "&&",
        "ln",
        "-s",
        "B bins.tsv",
        "/work/binette/input/bin_table_1.tsv",
        "&&",
        "ln",
        "-s",
        "C bins.tsv",
        "/work/binette/input/bin_table_2.tsv",
        "&&",
        "ln",
        "-s",
        "all contigs.fasta.gz",
        "/work/binette/input_contigs.fasta",
        "&&",
        "ln",
        "-s",
        "checkm2 tiny database.dmnd",
        "/work/binette/input_database.dmnd",
        "&&",
        "ln",
        "-s",
        "predicted proteins.faa.gz",
        "/work/binette/input_proteins.fasta",
        "&&",
        "binette",
        "-b",
        "/work/binette/input/*.tsv",
        "-c",
        "/work/binette/input_contigs.fasta",
        "-p",
        "/work/binette/input_proteins.fasta",
        "--min_completeness",
        "5",
        "-t",
        "${GALAXY_SLOTS:-6}",
        "-o",
        "/work/binette/output/",
        "-w",
        "0",
        "--checkm2_db",
        "/work/binette/input_database.dmnd",
    ]

    assert node_class.render_command(
        {
            "contig2bin_tables": ["A.tsv", "B.tsv"],
            "contigs": "assembly.fa",
            "min_completeness": 40,
            "contamination_weight": 2,
            "database_type": "cached",
            "checkm2_db_path": "/db/checkm2/current.dmnd",
            "threads": 2,
            "output": "/work/binette",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/binette/input",
        "/work/binette/output",
        "&&",
        "ln",
        "-s",
        "A.tsv",
        "/work/binette/input/bin_table_0.tsv",
        "&&",
        "ln",
        "-s",
        "B.tsv",
        "/work/binette/input/bin_table_1.tsv",
        "&&",
        "ln",
        "-s",
        "assembly.fa",
        "/work/binette/input_contigs.fasta",
        "&&",
        "binette",
        "-b",
        "/work/binette/input/*.tsv",
        "-c",
        "/work/binette/input_contigs.fasta",
        "--min_completeness",
        "40",
        "-t",
        "${GALAXY_SLOTS:-2}",
        "-o",
        "/work/binette/output/",
        "-w",
        "2",
        "--checkm2_db",
        "/db/checkm2/current.dmnd",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "binette" / "output" / "final_bins",
        tmp_path / "binette" / "output" / "input_bins_quality_reports",
        tmp_path / "binette" / "output" / "final_bins_quality_reports.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({"contig2bin_tables": ["A.tsv"], "contigs": "assembly.fa"}) == (
        "at least two contig-to-bin tables are required"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "contig2bin_tables": ["A.tsv", "B.tsv"],
            "contigs": "assembly.fa",
            "database_type": "his",
            "checkm2_db": "",
        }
    ) == "CheckM2 DIAMOND database is required for history database mode"
    assert node_class.VALIDATE_INPUTS(
        {
            "contig2bin_tables": ["A.tsv", "B.tsv"],
            "contigs": "assembly.fa",
            "database_type": "cached",
            "checkm2_db_path": "/db/checkm2/current.dmnd",
        }
    ) is True


def test_bin_refiner_renders_refinement_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("bin_refiner")
    info = _registry().object_info()["bin_refiner"]

    assert info["output"] == ["DIRECTORY", "TSV", "TSV"]
    assert info["output_name"] == ["refined_bins", "refined_contigs", "sources_and_length"]
    assert info["input"]["required"]["input_bins"][1]["multiple"] is True
    assert "10.1093/bioinformatics/btx086" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bins": ["MetaBAT 17.fa.gz", "Concoct/bin 1.fasta", "MaxBin#2.fa"],
            "element_identifiers": ["MetaBAT 17", "Concoct/bin 1", ""],
            "input_exts": ["fasta.gz", "fasta", "fasta"],
            "m": 256,
            "output": "/work/bin_refiner",
        }
    ) == (
        "mkdir -p /work/bin_refiner/input_bin_dir/bins && "
        "gunzip -c 'MetaBAT 17.fa.gz' > /work/bin_refiner/input_bin_dir/bins/MetaBAT_17.fasta.gz && "
        "ln -s 'Concoct/bin 1.fasta' /work/bin_refiner/input_bin_dir/bins/Concoct_bin_1.fasta && "
        "ln -s 'MaxBin#2.fa' /work/bin_refiner/input_bin_dir/bins/MaxBin_2.fa.fasta && "
        "Binning_refiner -i /work/bin_refiner/input_bin_dir -p refined -m 256 && "
        "mv /work/bin_refiner/refined_Binning_refiner_outputs/refined_contigs.txt "
        "/work/bin_refiner/refined_contigs.tsv && "
        "mv /work/bin_refiner/refined_Binning_refiner_outputs/refined_sources_and_length.txt "
        "/work/bin_refiner/sources_and_length.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bin_refiner" / "refined_Binning_refiner_outputs" / "refined_refined_bins",
        tmp_path / "bin_refiner" / "refined_contigs.tsv",
        tmp_path / "bin_refiner" / "sources_and_length.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({"input_bins": []}) == "at least one binned FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_bins": ["bin.fa"], "m": 0}) == "minimum refined bin size must be >= 1 Kbp"
    assert node_class.VALIDATE_INPUTS({"input_bins": ["bin.fa"], "m": 1}) is True


def test_beagle_renders_phasing_imputation_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("beagle")
    info = _registry().object_info()["beagle"]

    assert info["output"] == ["VCF", "TXT"]
    assert info["output_name"] == ["vcf_file", "log_file"]
    assert "10.1016/j.ajhg.2018.07.015" in info["citation_dois"]
    assert "10.1086/521987" in info["citation_dois"]
    assert node_class.render_command(
        {
            "gt": "target genotypes.vcf.gz",
            "gt_ext": "vcf_bgzip",
            "ref": "reference panel.vcf.gz",
            "ref_ext": "vcf_bgzip",
            "map": "plink genetic.map",
            "chrom": "22:100-",
            "excludesamples": "excluded samples.txt",
            "excludemarkers": "excluded markers.txt",
            "ne": 500000,
            "window": 30.0,
            "overlap": 3.0,
            "seed": 42,
            "err": 0.02,
            "burnin": 4,
            "iterations": 10,
            "phase_states": 250,
            "impute": False,
            "imp_states": 1200,
            "imp_segment": 5.0,
            "imp_step": 0.2,
            "cluster": 0.01,
            "ap": True,
            "gp": True,
            "out_format": "vcf",
            "threads": 8,
            "output": "/work/beagle",
        }
    ) == [
        "ln",
        "-s",
        "reference panel.vcf.gz",
        "/work/beagle/ref.vcf_bgzip",
        "&&",
        "ln",
        "-s",
        "target genotypes.vcf.gz",
        "/work/beagle/tmp.gz",
        "&&",
        "beagle",
        "gt=/work/beagle/tmp.gz",
        "ref=/work/beagle/ref.vcf_bgzip",
        "map=plink genetic.map",
        "chrom=22:100-",
        "excludesamples=excluded samples.txt",
        "excludemarkers=excluded markers.txt",
        "ne=500000",
        "window=30.0",
        "overlap=3.0",
        "seed=42",
        "err=0.02",
        "burnin=4",
        "iterations=10",
        "phase-states=250",
        "impute=false",
        "imp-states=1200",
        "imp-segment=5.0",
        "imp-step=0.2",
        "cluster=0.01",
        "ap=true",
        "gp=true",
        "out=/work/beagle/out",
        "nthreads=${GALAXY_SLOTS:-8}",
        "&&",
        "gunzip",
        "/work/beagle/out.vcf.gz",
        "&&",
        "mv",
        "/work/beagle/out.vcf",
        "/work/beagle/phased_imputed.vcf",
    ]

    assert node_class.render_command(
        {
            "gt": "study.vcf",
            "out_format": "vcf_bgzip",
            "threads": 2,
            "output": "/work/beagle",
        }
    ) == [
        "beagle",
        "gt=study.vcf",
        "ne=1000000",
        "window=40.0",
        "overlap=2.0",
        "burnin=3",
        "iterations=12",
        "phase-states=280",
        "impute=true",
        "imp-states=1600",
        "imp-segment=6.0",
        "imp-step=0.1",
        "cluster=0.005",
        "ap=false",
        "gp=false",
        "out=/work/beagle/out",
        "nthreads=${GALAXY_SLOTS:-2}",
        "&&",
        "mv",
        "/work/beagle/out.vcf.gz",
        "/work/beagle/phased_imputed.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({"out_format": "vcf_bgzip", "output_log": True}, tmp_path) == [
        tmp_path / "beagle" / "phased_imputed.vcf.gz",
        tmp_path / "beagle" / "out.log",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "beagle" / "phased_imputed.vcf",
    ]
    assert node_class.VALIDATE_INPUTS({"gt": ""}) == "VCF genotype input is required"
    assert node_class.VALIDATE_INPUTS({"gt": "study.vcf", "window": 2.0, "overlap": 2.0}) == (
        "window must be at least 1.1 times overlap"
    )
    assert node_class.VALIDATE_INPUTS({"gt": "study.vcf", "err": 1.2}) == "err must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS({"gt": "study.vcf"}) is True


def test_breseq_renders_detect_annotate_commands_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("breseq")
    info = _registry().object_info()["breseq"]

    assert info["output"] == ["HTML_REPORT", "HTML_REPORT", "TSV", "TSV", "ZIP", "TXT", "TSV", "PHYLIP", "JSON"]
    assert info["output_name"] == [
        "report",
        "annreport",
        "output",
        "genomediff",
        "zip_output",
        "log",
        "tabdelim",
        "phylipout",
        "jsonout",
    ]
    assert "10.1007/978-1-4939-0554-6_12" in info["citation_dois"]
    assert node_class.render_command(
        {
            "mode": "detect",
            "references": ["lambda.gbk", "mobile element.gb"],
            "fastqs": ["reads R1.fastq.gz", "reads R2.fastq.gz"],
            "name": "smallest",
            "polymorphism_prediction": True,
            "predict_junctions": False,
            "formats": ["html", "log", "gd", "zip"],
            "threads": 6,
            "output": "/work/breseq",
        }
    ) == [
        "breseq",
        "--num-processors",
        "${GALAXY_SLOTS:-6}",
        "-o",
        "/work/breseq/results",
        "--reference",
        "lambda.gbk",
        "--reference",
        "mobile element.gb",
        "reads R1.fastq.gz",
        "reads R2.fastq.gz",
        "--name",
        "smallest",
        "--polymorphism-prediction",
        "--no-junction-prediction",
        "&&",
        "cp",
        "/work/breseq/results/output/output.gd",
        "/work/breseq/output.gd",
        "&&",
        "cp",
        "/work/breseq/results/output/index.html",
        "/work/breseq/report.html",
        "&&",
        "mkdir",
        "-p",
        "/work/breseq/report_extra_files",
        "&&",
        "cp",
        "-R",
        "/work/breseq/results/output/.",
        "/work/breseq/report_extra_files",
        "&&",
        "tar",
        "-zcf",
        "/work/breseq/results.tar.gz",
        "/work/breseq/results",
        "&&",
        "cp",
        "/work/breseq/results/output/log.txt",
        "/work/breseq/log.txt",
    ]

    assert node_class.render_command(
        {
            "mode": "annotate",
            "references": ["lambda.gbk"],
            "gds": ["sample A.gd", "sample B.gd"],
            "formats": ["html", "gd", "tsv", "json"],
            "output": "/work/breseq",
        }
    ) == [
        "gdtools",
        "ANNOTATE",
        "--format",
        "html",
        "-o",
        "/work/breseq/annotated_report.html",
        "--reference",
        "lambda.gbk",
        "sample A.gd",
        "sample B.gd",
        "&&",
        "gdtools",
        "ANNOTATE",
        "--format",
        "gd",
        "-o",
        "/work/breseq/annotated.gd",
        "--reference",
        "lambda.gbk",
        "sample A.gd",
        "sample B.gd",
        "&&",
        "gdtools",
        "ANNOTATE",
        "--format",
        "tsv",
        "-o",
        "/work/breseq/annotated.tsv",
        "--reference",
        "lambda.gbk",
        "sample A.gd",
        "sample B.gd",
        "&&",
        "gdtools",
        "ANNOTATE",
        "--format",
        "json",
        "-o",
        "/work/breseq/annotated.json",
        "--reference",
        "lambda.gbk",
        "sample A.gd",
        "sample B.gd",
    ]

    assert node_class.PLAN_OUTPUTS({"mode": "detect", "formats": ["html", "log", "gd", "zip"]}, tmp_path) == [
        tmp_path / "breseq" / "report.html",
        tmp_path / "breseq" / "output.gd",
        tmp_path / "breseq" / "results.tar.gz",
        tmp_path / "breseq" / "log.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"mode": "annotate", "formats": ["html", "gd", "tsv", "json"]}, tmp_path) == [
        tmp_path / "breseq" / "annotated_report.html",
        tmp_path / "breseq" / "annotated.gd",
        tmp_path / "breseq" / "annotated.tsv",
        tmp_path / "breseq" / "annotated.json",
    ]
    assert node_class.VALIDATE_INPUTS({"mode": "detect", "fastqs": ["reads.fq"]}) == (
        "at least one reference genome is required"
    )
    assert node_class.VALIDATE_INPUTS({"mode": "detect", "references": ["lambda.gbk"]}) == (
        "at least one FASTQ read file is required for detect mode"
    )
    assert node_class.VALIDATE_INPUTS({"mode": "compare", "references": ["lambda.gbk"], "gds": ["a.gd"]}) == (
        "compare mode requires at least two GenomeDiff inputs"
    )
    assert node_class.VALIDATE_INPUTS({"mode": "annotate", "references": ["lambda.gbk"], "gds": ["a.gd"]}) is True


def test_biscot_renders_scaffolding_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("biscot")
    info = _registry().object_info()["biscot"]

    assert info["output"] == ["TXT", "FASTA", "AGP"]
    assert info["output_name"] == ["log", "fasta", "agp"]
    assert info["input"]["optional"]["secondary_map_cmap_2"][1]["default"] == ""
    assert "10.7717/peerj.10150" in info["citation_dois"]
    assert node_class.render_command(
        {
            "cmap_ref": "anchor reference.cmap",
            "cmap_1": "query map.cmap",
            "xmap_1": "primary alignment.xmap",
            "key": "bionano key.tsv",
            "contigs": "assembly contigs.fa",
            "log_file": True,
            "output": "/work/biscot",
        }
    ) == [
        "biscot",
        "--cmap-ref",
        "anchor reference.cmap",
        "--cmap-1",
        "query map.cmap",
        "--xmap-1",
        "primary alignment.xmap",
        "--key",
        "bionano key.tsv",
        "--contigs",
        "assembly contigs.fa",
        "&&",
        "cp",
        "biscot/biscot.log",
        "/work/biscot/biscot.log",
        "&&",
        "cp",
        "biscot/scaffolds.fasta",
        "/work/biscot/scaffolds.fasta",
        "&&",
        "cp",
        "biscot/scaffolds.agp",
        "/work/biscot/scaffolds.agp",
    ]

    assert node_class.render_command(
        {
            "cmap_ref": "ref.cmap",
            "cmap_1": "enzyme A.cmap",
            "xmap_1": "enzyme A.xmap",
            "secondary_map_cmap_2": "enzyme B.cmap",
            "secondary_map_xmap_2": "enzyme B.xmap",
            "xmap_2enz": "both enzymes.xmap",
            "only_confirmed_pos": True,
            "key": "bionano.tsv",
            "contigs": "contigs.fa",
            "output": "/work/biscot",
        }
    ) == [
        "biscot",
        "--cmap-ref",
        "ref.cmap",
        "--cmap-1",
        "enzyme A.cmap",
        "--xmap-1",
        "enzyme A.xmap",
        "--key",
        "bionano.tsv",
        "--contigs",
        "contigs.fa",
        "--cmap-2",
        "enzyme B.cmap",
        "--xmap-2",
        "enzyme B.xmap",
        "--xmap-2enz",
        "both enzymes.xmap",
        "--only-confirmed-pos",
        "&&",
        "cp",
        "biscot/scaffolds.fasta",
        "/work/biscot/scaffolds.fasta",
        "&&",
        "cp",
        "biscot/scaffolds.agp",
        "/work/biscot/scaffolds.agp",
    ]

    assert node_class.PLAN_OUTPUTS({"log_file": True}, tmp_path) == [
        tmp_path / "biscot" / "biscot.log",
        tmp_path / "biscot" / "scaffolds.fasta",
        tmp_path / "biscot" / "scaffolds.agp",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "biscot" / "scaffolds.fasta",
        tmp_path / "biscot" / "scaffolds.agp",
    ]
    assert node_class.VALIDATE_INPUTS({"cmap_1": "query.cmap", "xmap_1": "query.xmap", "key": "key.tsv", "contigs": "contigs.fa"}) == (
        "cmap_ref is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {
            "cmap_ref": "ref.cmap",
            "cmap_1": "query.cmap",
            "xmap_1": "query.xmap",
            "secondary_map_cmap_2": "second.cmap",
            "key": "key.tsv",
            "contigs": "contigs.fa",
        }
    ) == "secondary_map_xmap_2 is required when secondary_map_cmap_2 is provided"
    assert node_class.VALIDATE_INPUTS(
        {"cmap_ref": "ref.cmap", "cmap_1": "query.cmap", "xmap_1": "query.xmap", "key": "key.tsv", "contigs": "contigs.fa"}
    ) is True


def test_bigscape_renders_network_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("bigscape")
    info = _registry().object_info()["bigscape"]

    assert info["output"] == ["HTML_REPORT", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "TXT"]
    assert info["output_name"] == [
        "html",
        "network_annotations",
        "clan_tables",
        "clustering_tables",
        "network_files",
        "logfile",
    ]
    assert info["input"]["optional"]["mibig"][1]["options"] == ["", "--mibig", "--mibig21", "--mibig14", "--mibig13"]
    assert "10.1038/s41589-019-0400-9" in info["citation_dois"]
    assert node_class.render_command(
        {
            "inputdir": ["cluster one.gbk", "cluster two.gbk"],
            "element_identifiers": ["NC_001.region001", "NC 002/region002"],
            "pfam_dir": "Pfam-A.hmm",
            "mibig": "--mibig21",
            "label": "experiment A",
            "verbose": True,
            "log": True,
            "include_singletons": True,
            "domain_overlap_cutoff": 0.2,
            "min_big_size": 1000,
            "mix": True,
            "no_classify": True,
            "banned_classes": ["NRPS", "RiPPs"],
            "cutoffs": [0.3, 0.5],
            "clans_off": True,
            "clan_cutoff": [0.25, 0.65],
            "hybrids_off": True,
            "mode": "global",
            "anchorfile": "anchors.txt",
            "anchor_identifier": "custom_anchor.txt",
            "force_hmmscan": True,
            "domain_includelist": "domains.txt",
            "output": "/work/bigscape",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/bigscape/html_extra_files",
        "/work/bigscape/result",
        "/work/bigscape/input",
        "/work/bigscape/pfam",
        "&&",
        "ln",
        "-s",
        "cluster one.gbk",
        "/work/bigscape/input/region.NC_001.region001.gbk",
        "&&",
        "ln",
        "-s",
        "cluster two.gbk",
        "/work/bigscape/input/region.NC_002_region002.gbk",
        "&&",
        "ln",
        "-s",
        "Pfam-A.hmm",
        "/work/bigscape/pfam/Pfam-A.hmm",
        "&&",
        "hmmpress",
        "/work/bigscape/pfam/Pfam-A.hmm",
        "&&",
        "ln",
        "-s",
        "anchors.txt",
        "/work/bigscape/custom_anchor.txt",
        "&&",
        "bigscape",
        "--inputdir",
        "/work/bigscape/input",
        "--mibig21",
        "--outputdir",
        "/work/bigscape/result",
        "--label",
        "experiment A",
        "--pfam_dir",
        "/work/bigscape/pfam",
        "--cores",
        "${GALAXY_SLOTS:-8}",
        "--verbose",
        "--include_singletons",
        "--domain_overlap_cutoff",
        "0.2",
        "--min_bgc_size",
        "1000",
        "--mix",
        "--no_classify",
        "--banned_classes",
        "NRPS",
        "RiPPs",
        "--cutoffs",
        "0.3",
        "0.5",
        "--clans-off",
        "--clan_cutoff",
        "0.25",
        "0.65",
        "--hybrids-off",
        "--mode",
        "global",
        "--anchorfile",
        "custom_anchor.txt",
        "--force_hmmscan",
        "--domain_includelist",
        ">",
        "/work/bigscape/log.txt",
        "&&",
        "cp",
        "/work/bigscape/result/index.html",
        "/work/bigscape/index.html",
        "&&",
        "cp",
        "-r",
        "/work/bigscape/result/html_content",
        "/work/bigscape/html_extra_files",
        "&&",
        "cp",
        "/work/bigscape/log.txt",
        "/work/bigscape/bigscape.log",
    ]

    assert node_class.PLAN_OUTPUTS({"log": True, "clans_off": False}, tmp_path) == [
        tmp_path / "bigscape" / "index.html",
        tmp_path / "bigscape" / "network_annotations",
        tmp_path / "bigscape" / "clan_tables",
        tmp_path / "bigscape" / "clustering_tables",
        tmp_path / "bigscape" / "network_files",
        tmp_path / "bigscape" / "bigscape.log",
    ]
    assert node_class.PLAN_OUTPUTS({"clans_off": True}, tmp_path) == [
        tmp_path / "bigscape" / "index.html",
        tmp_path / "bigscape" / "network_annotations",
        tmp_path / "bigscape" / "clustering_tables",
        tmp_path / "bigscape" / "network_files",
    ]
    assert node_class.VALIDATE_INPUTS({"pfam_dir": "Pfam-A.hmm"}) == "at least one GenBank BGC input is required"
    assert node_class.VALIDATE_INPUTS({"inputdir": ["cluster.gbk"]}) == "Pfam-A.hmm input is required"
    assert node_class.VALIDATE_INPUTS({"inputdir": ["cluster.gbk"], "pfam_dir": "Pfam-A.hmm", "domain_overlap_cutoff": 1.5}) == (
        "domain_overlap_cutoff must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"inputdir": ["cluster.gbk"], "pfam_dir": "Pfam-A.hmm", "cutoffs": [0.05]}) == (
        "cutoff values must be between 0.1 and 1.0"
    )
    assert node_class.VALIDATE_INPUTS({"inputdir": ["cluster.gbk"], "pfam_dir": "Pfam-A.hmm"}) is True


def test_compleasm_renders_completeness_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("compleasm")
    info = _registry().object_info()["compleasm"]

    assert info["output"] == ["TSV", "TSV", "GFF", "FASTA", "TXT"]
    assert info["output_name"] == ["full_table_busco", "full_table", "miniprot", "translated_protein", "summary"]
    assert info["input"]["optional"]["outputs"][1]["options"] == [
        "full_table_busco",
        "full_table",
        "miniprot",
        "translated_protein",
        "summary",
    ]
    assert "10.1101/2023.06.03.543588" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input": "genome assembly.fa",
            "busco_database_path": "/db/busco",
            "lineage_dataset": "entomoplasmatales_odb10",
            "mode": "lite",
            "specified_contigs": "chr1 chr2",
            "outputs": ["summary", "full_table", "miniprot"],
            "threads": 5,
            "output": "/work/compleasm",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/compleasm/galaxy_db",
        "&&",
        "ln",
        "-s",
        "/db/busco/lineages/entomoplasmatales_odb10",
        "/work/compleasm/galaxy_db/entomoplasmatales_odb10",
        "&&",
        "touch",
        "/work/compleasm/galaxy_db/entomoplasmatales_odb10.done",
        "&&",
        "compleasm",
        "run",
        "-a",
        "genome assembly.fa",
        "-o",
        "/work/compleasm/galaxy_output",
        "--mode",
        "lite",
        "-L",
        "/work/compleasm/galaxy_db",
        "-l",
        "entomoplasmatales_odb10",
        "-t",
        "${GALAXY_SLOTS:-5}",
        "--specified_contigs",
        "chr1 chr2",
        "&&",
        "cp",
        "/work/compleasm/galaxy_output/entomoplasmatales_odb10/full_table.tsv",
        "/work/compleasm/full_table.tsv",
        "&&",
        "cp",
        "/work/compleasm/galaxy_output/entomoplasmatales_odb10/miniprot_output.gff",
        "/work/compleasm/miniprot.gff",
        "&&",
        "cp",
        "/work/compleasm/galaxy_output/summary.txt",
        "/work/compleasm/summary.txt",
    ]

    assert node_class.PLAN_OUTPUTS({"outputs": ["summary", "full_table", "miniprot"]}, tmp_path) == [
        tmp_path / "compleasm" / "full_table.tsv",
        tmp_path / "compleasm" / "miniprot.gff",
        tmp_path / "compleasm" / "summary.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "compleasm" / "full_table_busco.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({"busco_database_path": "/db/busco", "lineage_dataset": "lineage_odb10"}) == (
        "input genome FASTA is required"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genome.fa", "lineage_dataset": "lineage_odb10"}) == (
        "BUSCO database path is required"
    )
    assert node_class.VALIDATE_INPUTS({"input": "genome.fa", "busco_database_path": "/db/busco"}) == (
        "lineage_dataset is required"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input": "genome.fa", "busco_database_path": "/db/busco", "lineage_dataset": "lineage_odb10", "outputs": ["bad"]}
    ) == "unknown compleasm output: bad"
    assert node_class.VALIDATE_INPUTS(
        {
            "input": "genome.fa",
            "busco_database_path": "/db/busco",
            "lineage_dataset": "lineage_odb10",
            "specified_contigs": "chr1;rm",
        }
    ) == "specified_contigs may contain only letters, numbers, underscores, and spaces"
    assert node_class.VALIDATE_INPUTS({"input": "genome.fa", "busco_database_path": "/db/busco", "lineage_dataset": "lineage_odb10"}) is True


def test_eastr_renders_splice_junction_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("eastr")
    info = _registry().object_info()["eastr"]

    assert info["output"] == ["BED", "BAM", "BED", "BED", "TXT"]
    assert info["output_name"] == ["removed_junctions", "filtered_bam", "kept_junctions", "original_junctions", "log"]
    assert info["input"]["required"]["input_select"][1]["options"] == ["bam", "gtf", "bed"]
    assert "10.1038/s41467-023-43017-4" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_select": "bam",
            "input": "aligned reads.bam",
            "bam_index": "aligned reads.bam.bai",
            "reference": "genome reference.fa",
            "optional_outputs": ["kept", "original"],
            "bt2_k": 12,
            "overhang": 60,
            "anchor": 9,
            "min_duplicate_exon_length": 31,
            "min_junc_score": 2,
            "match_score": 4,
            "mismatch_penalty": 5,
            "kmer": 4,
            "window": 3,
            "min_chain_score": 30,
            "trusted_bed": "trusted junctions.bed",
            "log": True,
            "threads": 7,
            "output": "/work/eastr",
        }
    ) == [
        "ln",
        "-s",
        "genome reference.fa",
        "/work/eastr/reference.fa",
        "&&",
        "ln",
        "-s",
        "aligned reads.bam",
        "/work/eastr/input.bam",
        "&&",
        "ln",
        "-s",
        "aligned reads.bam.bai",
        "/work/eastr/input.bam.bai",
        "&&",
        "eastr",
        "-r",
        "/work/eastr/reference.fa",
        "-p",
        "${GALAXY_SLOTS:-7}",
        "--bam",
        "/work/eastr/input.bam",
        "--out_filtered_bam",
        "/work/eastr/filtered.bam",
        "--out_removed_junctions",
        "/work/eastr/removed_junctions.bed",
        "--out_kept_junctions",
        "/work/eastr/kept_junctions.bed",
        "--out_original_junctions",
        "/work/eastr/original_junctions.bed",
        "--bt2_k",
        "12",
        "-o",
        "60",
        "-a",
        "9",
        "--min_duplicate_exon_length",
        "31",
        "--min_junc_score",
        "2",
        "-A",
        "4",
        "-B",
        "5",
        "-k",
        "4",
        "-w",
        "3",
        "-m",
        "30",
        "--trusted_bed",
        "trusted junctions.bed",
        "--verbose",
        "2>",
        "/work/eastr/eastr.log",
    ]

    assert node_class.render_command(
        {
            "input_select": "gtf",
            "input": "annotation.gtf",
            "reference": "genome.fa",
            "optional_outputs": "kept,original",
            "output": "/work/eastr",
        }
    ) == [
        "ln",
        "-s",
        "genome.fa",
        "/work/eastr/reference.fa",
        "&&",
        "eastr",
        "-r",
        "/work/eastr/reference.fa",
        "-p",
        "${GALAXY_SLOTS:-1}",
        "--gtf",
        "annotation.gtf",
        "--out_removed_junctions",
        "/work/eastr/removed_junctions.bed",
        "--out_kept_junctions",
        "/work/eastr/kept_junctions.bed",
        "--out_original_junctions",
        "/work/eastr/original_junctions.bed",
        "--bt2_k",
        "10",
        "-o",
        "50",
        "-a",
        "7",
        "--min_duplicate_exon_length",
        "27",
        "--min_junc_score",
        "1",
        "-A",
        "3",
        "-B",
        "4",
        "-k",
        "3",
        "-w",
        "2",
        "-m",
        "25",
    ]

    assert node_class.PLAN_OUTPUTS({"input_select": "bam", "optional_outputs": ["kept", "original"], "log": True}, tmp_path) == [
        tmp_path / "eastr" / "removed_junctions.bed",
        tmp_path / "eastr" / "filtered.bam",
        tmp_path / "eastr" / "kept_junctions.bed",
        tmp_path / "eastr" / "original_junctions.bed",
        tmp_path / "eastr" / "eastr.log",
    ]
    assert node_class.PLAN_OUTPUTS({"input_select": "bed"}, tmp_path) == [
        tmp_path / "eastr" / "removed_junctions.bed",
    ]
    assert node_class.VALIDATE_INPUTS({"input": "reads.bam", "reference": "reference.fa"}) == "input_select is required"
    assert node_class.VALIDATE_INPUTS({"input_select": "bam", "reference": "reference.fa"}) == "input is required"
    assert node_class.VALIDATE_INPUTS({"input_select": "bam", "input": "reads.bam"}) == "reference FASTA is required"
    assert node_class.VALIDATE_INPUTS({"input_select": "bam", "input": "reads.bam", "reference": "reference.fa", "bt2_k": 0}) == (
        "bt2_k must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"input_select": "vcf", "input": "input.vcf", "reference": "reference.fa"}) == (
        "input_select must be one of: bam, gtf, bed"
    )
    assert node_class.VALIDATE_INPUTS({"input_select": "bed", "input": "introns.bed", "reference": "reference.fa"}) is True


def test_export2graphlan_renders_conversion_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("export2graphlan")
    info = _registry().object_info()["export2graphlan"]

    assert info["output"] == ["TXT", "TXT"]
    assert info["output_name"] == ["tree", "annotation"]
    assert info["input"]["required"]["lefse_input"][0] == "FILE"
    assert "10.7717/peerj.1029" in info["citation_dois"]
    assert node_class.render_command(
        {
            "lefse_input": "profile table.tsv",
            "lefse_output": "lefse result.tsv",
            "annotations": "2,3",
            "external_annotations": "4",
            "background_levels": "1,2",
            "background_clades": "k__Bacteria,p__Firmicutes",
            "background_colors": "(0;0;0.9),(60;0.4;0.8)",
            "title": "Microbiome tree",
            "title_font_size": 18,
            "def_clade_size": 10,
            "min_clade_size": 20,
            "max_clade_size": 200,
            "def_font_size": 10,
            "min_font_size": 8,
            "max_font_size": 12,
            "annotation_legend_font_size": 10,
            "abundance_threshold": 20.5,
            "most_abundant": 15,
            "least_biomarkers": 3,
            "fname_row": 0,
            "sname_row": 1,
            "metadata_rows": 2,
            "skip_rows": "0,1",
            "sperc": 75.5,
            "fperc": 80.0,
            "stop": 6,
            "ftop": 8,
            "output": "/work/export2graphlan",
        }
    ) == [
        "export2graphlan.py",
        "--lefse_input",
        "profile table.tsv",
        "--lefse_output",
        "lefse result.tsv",
        "-t",
        "/work/export2graphlan/tree.txt",
        "-a",
        "/work/export2graphlan/annotation.txt",
        "--annotations",
        "2,3",
        "--external_annotations",
        "4",
        "--background_levels",
        "1,2",
        "--background_clades",
        "k__Bacteria,p__Firmicutes",
        "--background_colors",
        "(0;0;0.9),(60;0.4;0.8)",
        "--title",
        "Microbiome tree",
        "--title_font_size",
        "18",
        "--def_clade_size",
        "10",
        "--min_clade_size",
        "20",
        "--max_clade_size",
        "200",
        "--def_font_size",
        "10",
        "--min_font_size",
        "8",
        "--max_font_size",
        "12",
        "--annotation_legend_font_size",
        "10",
        "--abundance_threshold",
        "20.5",
        "--most_abundant",
        "15",
        "--least_biomarkers",
        "3",
        "--fname_row",
        "0",
        "--sname_row",
        "1",
        "--metadata_rows",
        "2",
        "--skip_rows",
        "0,1",
        "--sperc",
        "75.5",
        "--fperc",
        "80.0",
        "--stop",
        "6",
        "--ftop",
        "8",
    ]

    assert node_class.render_command({"lefse_input": "profile.tsv", "output": "/work/export2graphlan"}) == [
        "export2graphlan.py",
        "--lefse_input",
        "profile.tsv",
        "-t",
        "/work/export2graphlan/tree.txt",
        "-a",
        "/work/export2graphlan/annotation.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "export2graphlan" / "tree.txt",
        tmp_path / "export2graphlan" / "annotation.txt",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "lefse_input is required"
    assert node_class.VALIDATE_INPUTS({"lefse_input": "profile.tsv", "title_font_size": 0}) == "title_font_size must be >= 1"
    assert node_class.VALIDATE_INPUTS({"lefse_input": "profile.tsv", "abundance_threshold": -0.1}) == (
        "abundance_threshold must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"lefse_input": "profile.tsv", "skip_rows": "0,two"}) == (
        "skip_rows must be comma-separated integer row indexes"
    )
    assert node_class.VALIDATE_INPUTS({"lefse_input": "profile.tsv"}) is True


def test_graphlan_annotate_renders_annotation_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("graphlan_annotate")
    info = _registry().object_info()["graphlan_annotate"]

    assert info["output"] == ["PHYLOXML"]
    assert info["output_name"] == ["output_tree"]
    assert info["input"]["required"]["input_tree"][0] == "STRING"
    assert "10.7717/peerj.1029" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_tree": "tree.nwk",
            "annot": "annotation.txt",
            "output": "/work/graphlan_annotate",
        }
    ) == [
        "graphlan_annotate.py",
        "--annot",
        "annotation.txt",
        "tree.nwk",
        "/work/graphlan_annotate/output_tree.phyloxml",
    ]
    assert node_class.render_command({"input_tree": "tree.nhx", "output": "/work/graphlan_annotate"}) == [
        "graphlan_annotate.py",
        "tree.nhx",
        "/work/graphlan_annotate/output_tree.phyloxml",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "graphlan_annotate" / "output_tree.phyloxml",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "input_tree is required"
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.nwk"}) is True


def test_graphlan_renders_tree_image_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("graphlan")
    info = _registry().object_info()["graphlan"]

    assert info["output"] == ["IMAGE"]
    assert info["output_name"] == ["image"]
    assert info["input"]["required"]["input_tree"][0] == "STRING"
    assert info["input"]["optional"]["image_format"][1]["options"] == ["png", "pdf", "ps", "eps", "svg"]
    assert "10.7717/peerj.1029" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_tree": "intermediary_tree.xml",
            "image_format": "png",
            "dpi": 100,
            "size": 7,
            "pad": 2,
            "output": "/work/graphlan",
        }
    ) == [
        "graphlan.py",
        "--format",
        "png",
        "--size",
        "7",
        "--pad",
        "2",
        "--dpi",
        "100",
        "intermediary_tree.xml",
        "/work/graphlan/image.png",
    ]
    assert node_class.render_command(
        {
            "input_tree": "intermediary_tree.xml",
            "image_format": "svg",
            "size": 10,
            "output": "/work/graphlan",
        }
    ) == [
        "graphlan.py",
        "--format",
        "svg",
        "--size",
        "10",
        "intermediary_tree.xml",
        "/work/graphlan/image.svg",
    ]
    assert node_class.PLAN_OUTPUTS({"image_format": "pdf"}, tmp_path) == [
        tmp_path / "graphlan" / "image.pdf",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "input_tree is required"
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.xml", "image_format": "jpg"}) == (
        "image_format must be one of: png, pdf, ps, eps, svg"
    )
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.xml", "size": 0}) == "size must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.xml", "image_format": "png", "dpi": 0}) == "dpi must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input_tree": "tree.xml", "image_format": "svg"}) is True


def test_exonerate_renders_pairwise_alignment_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("exonerate")
    info = _registry().object_info()["exonerate"]

    assert info["output"] == ["GFF", "GFF3", "TXT"]
    assert info["output_name"] == ["output_gff", "output_gff3", "output_ali"]
    assert info["input"]["required"]["query"][0] == "FASTA"
    assert info["input"]["optional"]["model"][1]["options"] == ["ungapped", "est2genome", "protein2genome", "coding2coding"]
    assert "10.1186/1471-2105-6-31" in info["citation_dois"]
    assert node_class.render_command(
        {
            "query": "transcriptome.fa",
            "target": "genome.fa",
            "model": "est2genome",
            "outformat": "targetgff",
            "score": 150,
            "percent": 70.5,
            "bestn": 3,
            "minintron": 100,
            "maxintron": 200,
            "threads": 6,
            "gff3_converter": "/tools/exonerate/exonerategff_to_gff3.py",
            "output": "/work/exonerate",
        }
    ) == (
        "exonerate --query transcriptome.fa --target genome.fa --score 150 --percent 70.5 --bestn 3 --verbose 0 "
        "--model est2genome --querytype dna --targettype dna --minintron 100 --maxintron 200 "
        "--cores ${GALAXY_SLOTS:-6} --showalignment no --showvulgar no --showtargetgff yes --showquerygff no "
        "> /work/exonerate/output.gff && python /tools/exonerate/exonerategff_to_gff3.py "
        "/work/exonerate/output.gff > /work/exonerate/output.gff3"
    )
    assert node_class.render_command(
        {
            "query": "query.fa",
            "target": "target.fa",
            "model": "ungapped",
            "outformat": "alignment",
            "output": "/work/exonerate",
        }
    ) == (
        "exonerate --query query.fa --target target.fa --score 100 --percent 0.0 --bestn 0 --verbose 0 "
        "--cores ${GALAXY_SLOTS:-1} --showalignment yes --showvulgar no > /work/exonerate/output.txt"
    )
    assert node_class.render_command(
        {
            "query": "query.fa",
            "target": "target.fa",
            "model": "protein2genome",
            "outformat": "querygff",
            "output": "/work/exonerate",
        }
    ) == (
        "exonerate --query query.fa --target target.fa --score 100 --percent 0.0 --bestn 0 --verbose 0 "
        "--model protein2genome --querytype protein --targettype dna --cores ${GALAXY_SLOTS:-1} "
        "--showalignment no --showvulgar no --showtargetgff no --showquerygff yes > /work/exonerate/output.gff "
        "&& python exonerategff_to_gff3.py /work/exonerate/output.gff > /work/exonerate/output.gff3"
    )
    assert node_class.PLAN_OUTPUTS({"outformat": "targetgff"}, tmp_path) == [
        tmp_path / "exonerate" / "output.gff",
        tmp_path / "exonerate" / "output.gff3",
    ]
    assert node_class.PLAN_OUTPUTS({"outformat": "alignment"}, tmp_path) == [
        tmp_path / "exonerate" / "output.txt",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "query FASTA is required"
    assert node_class.VALIDATE_INPUTS({"query": "query.fa"}) == "target FASTA is required"
    assert node_class.VALIDATE_INPUTS({"query": "query.fa", "target": "target.fa", "model": "bad"}) == (
        "model must be one of: ungapped, est2genome, protein2genome, coding2coding"
    )
    assert node_class.VALIDATE_INPUTS({"query": "query.fa", "target": "target.fa", "outformat": "bad"}) == (
        "outformat must be one of: targetgff, querygff, alignment"
    )
    assert node_class.VALIDATE_INPUTS({"query": "query.fa", "target": "target.fa", "score": -1}) == "score must be >= 0"
    assert node_class.VALIDATE_INPUTS({"query": "query.fa", "target": "target.fa", "percent": 101}) == (
        "percent must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"query": "query.fa", "target": "target.fa", "model": "est2genome"}) is True


def test_evidencemodeler_renders_gene_structure_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("evidencemodeler")
    info = _registry().object_info()["evidencemodeler"]

    assert info["output"] == ["GFF3", "FASTA"]
    assert info["output_name"] == ["evm_gff", "evm_pep"]
    assert info["input"]["required"]["input_genome"][0] == "FASTA"
    assert "10.1186/gb-2008-9-1-r7" in info["citation_dois"]
    assert "10.1080/21501203.2011.606851" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_genome": "genome.fasta",
            "input_predictions": "gene_predictions.gff3",
            "input_weights": "weights.txt",
            "input_proteins": "protein_alignments.gff3",
            "input_transcript": "transcript_alignments.gff3",
            "input_repeat": "repeats.gff3",
            "input_terminalexon": "terminal_exons.gff3",
            "segmentsize": 120000,
            "overlapsize": 15000,
            "stop_codon": ["TAA", "TGA"],
            "min_intron_length": 25,
            "search_long_introns": 1,
            "re_search_intergenic": 1,
            "terminal_intergenic_re_search": 0,
            "output": "/work/evidencemodeler",
        }
    ) == (
        "ln -s genome.fasta input_genome.fasta && ln -s gene_predictions.gff3 input_predictions.gff && "
        "ln -s weights.txt input_weights.txt && ln -s protein_alignments.gff3 input_proteins.gff && "
        "ln -s transcript_alignments.gff3 input_transcript.gff && EVidenceModeler --sample_id galaxy "
        "--genome ./input_genome.fasta --gene_predictions ./input_predictions.gff --weights ./input_weights.txt "
        "--protein_alignments ./input_proteins.gff --segmentSize 120000 --overlapSize 15000 "
        "--transcript_alignments ./input_transcript.gff --repeats repeats.gff3 --terminalExons terminal_exons.gff3 "
        "--stop_codons TAA,TGA --min_intron_length 25 --search_long_introns 1 --re_search_intergenic 1 "
        "--terminal_intergenic_re_search 0 && cp galaxy.EVM.gff3 /work/evidencemodeler/galaxy.EVM.gff3 "
        "&& cp galaxy.EVM.pep /work/evidencemodeler/galaxy.EVM.pep"
    )
    assert node_class.render_command(
        {
            "input_genome": "genome.fasta",
            "input_predictions": "gene_predictions.gff3",
            "input_weights": "weights.txt",
            "input_proteins": "protein_alignments.gff3",
            "output": "/work/evidencemodeler",
        }
    ) == (
        "ln -s genome.fasta input_genome.fasta && ln -s gene_predictions.gff3 input_predictions.gff && "
        "ln -s weights.txt input_weights.txt && ln -s protein_alignments.gff3 input_proteins.gff && "
        "EVidenceModeler --sample_id galaxy --genome ./input_genome.fasta --gene_predictions ./input_predictions.gff "
        "--weights ./input_weights.txt --protein_alignments ./input_proteins.gff --segmentSize 100000 --overlapSize 10000 "
        "--stop_codons TAA,TGA,TAG --min_intron_length 20 --search_long_introns 0 --re_search_intergenic 0 "
        "--terminal_intergenic_re_search 0 && cp galaxy.EVM.gff3 /work/evidencemodeler/galaxy.EVM.gff3 "
        "&& cp galaxy.EVM.pep /work/evidencemodeler/galaxy.EVM.pep"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "evidencemodeler" / "galaxy.EVM.gff3",
        tmp_path / "evidencemodeler" / "galaxy.EVM.pep",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "input_genome is required"
    assert node_class.VALIDATE_INPUTS({"input_genome": "genome.fasta"}) == "input_predictions is required"
    assert node_class.VALIDATE_INPUTS(
        {"input_genome": "genome.fasta", "input_predictions": "pred.gff3", "input_weights": "weights.txt"}
    ) == "input_proteins is required"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_genome": "genome.fasta",
            "input_predictions": "pred.gff3",
            "input_weights": "weights.txt",
            "input_proteins": "protein.gff3",
            "segmentsize": 0,
        }
    ) == "segmentsize must be >= 1"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_genome": "genome.fasta",
            "input_predictions": "pred.gff3",
            "input_weights": "weights.txt",
            "input_proteins": "protein.gff3",
            "stop_codon": ["TAA", "BAD"],
        }
    ) == "stop_codon values must be one or more of: TAA, TGA, TAG"
    assert node_class.VALIDATE_INPUTS(
        {
            "input_genome": "genome.fasta",
            "input_predictions": "pred.gff3",
            "input_weights": "weights.txt",
            "input_proteins": "protein.gff3",
        }
    ) is True


def test_comebin_renders_binning_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("comebin")
    info = _registry().object_info()["comebin"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["bins"]
    assert info["input"]["required"]["assembly_file"][0] == "FASTA"
    assert info["input"]["required"]["bam_files"][1]["multiple"] is True
    assert "10.1038/s41467-023-44290-z" in info["citation_dois"]
    assert node_class.render_command(
        {
            "assembly_file": "assembly file.fa",
            "assembly_identifier": "Sample Assembly 1",
            "bam_files": ["sample A.bam", "sample/B.bam"],
            "bam_identifiers": ["sample A", "sample/B"],
            "learning": 8,
            "loss": 0.07,
            "emb_comebin": 1024,
            "emb_cov": 512,
            "batch": 256,
            "threads": 10,
            "output": "/work/comebin",
        }
    ) == (
        "mkdir -p /work/comebin outputs bam_files && ln -s 'assembly file.fa' Sample_Assembly_1.fasta && "
        "ln -s 'sample A.bam' ./bam_files/sample_A.bam && ln -s sample/B.bam ./bam_files/sample_B.bam && "
        "run_comebin.sh -a Sample_Assembly_1.fasta -o outputs -p bam_files -t ${GALAXY_SLOTS:-10} "
        "-l 0.07 -n 8 -e 1024 -c 512 -b 256 && cp -r outputs/comebin_res/comebin_res_bins /work/comebin/bins"
    )
    assert node_class.render_command(
        {
            "assembly_file": "assembly.fa",
            "bam_files": "sample.bam",
            "output": "/work/comebin",
        }
    ) == (
        "mkdir -p /work/comebin outputs bam_files && ln -s assembly.fa assembly.fa.fasta && "
        "ln -s sample.bam ./bam_files/sample.bam && run_comebin.sh -a assembly.fa.fasta -o outputs -p bam_files "
        "-t ${GALAXY_SLOTS:-12} -l 0.15 -n 6 -e 2048 -c 2048 -b 1024 && "
        "cp -r outputs/comebin_res/comebin_res_bins /work/comebin/bins"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "comebin" / "bins",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "assembly_file is required"
    assert node_class.VALIDATE_INPUTS({"assembly_file": "assembly.fa"}) == "at least one BAM file is required"
    assert node_class.VALIDATE_INPUTS({"assembly_file": "assembly.fa", "bam_files": ["sample.bam"], "learning": 0}) == (
        "learning must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS({"assembly_file": "assembly.fa", "bam_files": ["sample.bam"], "loss": 0}) == (
        "loss must be > 0"
    )
    assert node_class.VALIDATE_INPUTS({"assembly_file": "assembly.fa", "bam_files": ["sample.bam"]}) is True


def test_comebin_bam_renders_coverage_bam_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("comebin_bam")
    info = _registry().object_info()["comebin_bam"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["bam_file"]
    assert info["input"]["required"]["assembly"][0] == "FASTA"
    assert info["input"]["required"]["read_type"][1]["options"] == ["normal", "single"]
    assert "10.1038/s41467-023-44290-z" in info["citation_dois"]
    assert node_class.render_command(
        {
            "assembly": "assembly.fa.gz",
            "read_type": "normal",
            "input_type": "paired",
            "paired_reads": {"forward": "reads R1.fastq.gz", "reverse": "reads R2.fastq.gz"},
            "length": 1500,
            "threads": 4,
            "output": "/work/comebin_bam",
        }
    ) == (
        "mkdir -p outputs /work/comebin_bam && ln -s assembly.fa.gz assembly.fasta.gz && gunzip assembly.fasta.gz && "
        "ln -s 'reads R1.fastq.gz' read_1.fastq.gz && ln -s 'reads R2.fastq.gz' read_2.fastq.gz && "
        "gunzip read_1.fastq.gz && gunzip read_2.fastq.gz && gen_cov_file.sh -a assembly.fasta -o outputs "
        "-t ${GALAXY_SLOTS:-4} -l 1500 read_1.fastq read_2.fastq && "
        "mv outputs/work_files/read.bam /work/comebin_bam/bam_file.bam"
    )
    assert node_class.render_command(
        {
            "assembly": "assembly.fa",
            "read_type": "normal",
            "input_type": "single",
            "forward": "R1.fastq",
            "reverse": "R2.fastq",
            "output": "/work/comebin_bam",
        }
    ) == (
        "mkdir -p outputs /work/comebin_bam && ln -s assembly.fa assembly.fasta && "
        "ln -s R1.fastq read_1.fastq && ln -s R2.fastq read_2.fastq && "
        "gen_cov_file.sh -a assembly.fasta -o outputs -t ${GALAXY_SLOTS:-1} -l 1000 read_1.fastq read_2.fastq && "
        "mv outputs/work_files/read.bam /work/comebin_bam/bam_file.bam"
    )
    assert node_class.render_command(
        {
            "assembly": "assembly.fa",
            "read_type": "single",
            "single_reads": "single.fastq.gz",
            "output": "/work/comebin_bam",
        }
    ) == (
        "mkdir -p outputs /work/comebin_bam && ln -s assembly.fa assembly.fasta && "
        "ln -s single.fastq.gz read.fastq.gz && gunzip read.fastq.gz && "
        "gen_cov_file.sh -a assembly.fasta -o outputs -t ${GALAXY_SLOTS:-1} -l 1000 --single-end read.fastq && "
        "mv outputs/work_files/read.bam /work/comebin_bam/bam_file.bam"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "comebin_bam" / "bam_file.bam",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "assembly is required"
    assert node_class.VALIDATE_INPUTS({"assembly": "assembly.fa", "read_type": "normal", "input_type": "single", "forward": "R1.fastq"}) == (
        "forward and reverse reads are required"
    )
    assert node_class.VALIDATE_INPUTS({"assembly": "assembly.fa", "read_type": "single"}) == "single_reads is required"
    assert node_class.VALIDATE_INPUTS({"assembly": "assembly.fa", "read_type": "single", "single_reads": "reads.fastq", "length": 0}) == (
        "length must be >= 1"
    )
    assert node_class.VALIDATE_INPUTS(
        {"assembly": "assembly.fa", "read_type": "normal", "input_type": "single", "forward": "R1.fastq", "reverse": "R2.fastq"}
    ) is True


def test_drep_compare_renders_genome_comparison_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("drep_compare")
    info = _registry().object_info()["drep_compare"]

    assert info["output"] == ["TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV"]
    assert info["output_name"] == [
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
    ]
    assert info["input"]["required"]["genomes"][0] == "STRING"
    assert info["input"]["required"]["genomes"][1]["multiple"] is True
    assert info["input"]["required"]["genomes"][1]["min"] == 2
    assert info["input"]["optional"]["comparison_steps"][1]["options"] == ["default", "SkipMash", "SkipSecondary"]
    assert "10.1038/ismej.2017.126" in info["citation_dois"]
    assert node_class.render_command(
        {
            "genomes": ["Genome A.fa", "sample/B.fna"],
            "genome_identifiers": ["Genome A", "sample/B"],
            "threads": 6,
            "output": "/work/drep_compare",
        }
    ) == (
        "mkdir -p /work/drep_compare && ln -s 'Genome A.fa' Genome_A.fasta && ln -s sample/B.fna sample_B.fasta && "
        "dRep compare outdir -g Genome_A.fasta sample_B.fasta --MASH_sketch 1000 --P_ani 0.9 "
        "--primary_chunksize 5000 --S_algorithm ANImf --n_PRESET normal --coverage_method larger --S_ani 0.99 "
        "--cov_thresh 0.1 --clusterAlg average --warn_dist 0.25 --warn_sim 0.98 --warn_aln 0.25 "
        "--processors ${GALAXY_SLOTS:-6} && cp outdir/log/logger.log /work/drep_compare/log.txt && "
        "cp outdir/log/warnings.txt /work/drep_compare/warnings.txt && "
        "cp outdir/figures/Primary_clustering_dendrogram.pdf /work/drep_compare/Primary_clustering_dendrogram.pdf && "
        "cp outdir/figures/Clustering_scatterplots.pdf /work/drep_compare/Clustering_scatterplots.pdf"
    )
    assert node_class.render_command(
        {
            "genomes": ["001", "002", "003"],
            "comparison_steps": "SkipMash",
            "S_algorithm": "fastANI",
            "greedy_secondary_clustering": True,
            "clusterAlg": "single",
            "run_tertiary_clustering": True,
            "warn_dist": 0.2,
            "warn_sim": 0.97,
            "warn_aln": 0.3,
            "select_outputs": ["log", "Cdb", "Ndb"],
            "output": "/work/drep_compare",
        }
    ) == (
        "mkdir -p /work/drep_compare && ln -s 001 001.fasta && ln -s 002 002.fasta && ln -s 003 003.fasta && "
        "dRep compare outdir -g 001.fasta 002.fasta 003.fasta --SkipMash --S_algorithm fastANI "
        "--greedy_secondary_clustering --S_ani 0.99 --cov_thresh 0.1 --clusterAlg single --run_tertiary_clustering "
        "--warn_dist 0.2 --warn_sim 0.97 --warn_aln 0.3 --processors ${GALAXY_SLOTS:-1} && "
        "cp outdir/log/logger.log /work/drep_compare/log.txt && "
        "cp outdir/data_tables/Cdb.csv /work/drep_compare/Cdb.csv && cp outdir/data_tables/Ndb.csv /work/drep_compare/Ndb.csv"
    )
    assert node_class.render_command(
        {
            "genomes": ["a.fa", "b.fa"],
            "comparison_steps": "SkipSecondary",
            "MASH_sketch": 2000,
            "P_ani": 0.85,
            "multiround_primary_clustering": True,
            "primary_chunksize": 200,
            "select_outputs": ["log", "Mdb"],
            "output": "/work/drep_compare",
        }
    ) == (
        "mkdir -p /work/drep_compare && ln -s a.fa a.fa.fasta && ln -s b.fa b.fa.fasta && "
        "dRep compare outdir -g a.fa.fasta b.fa.fasta --MASH_sketch 2000 --P_ani 0.85 "
        "--multiround_primary_clustering --primary_chunksize 200 --SkipSecondary --clusterAlg average "
        "--warn_dist 0.25 --warn_sim 0.98 --warn_aln 0.25 --processors ${GALAXY_SLOTS:-1} && "
        "cp outdir/log/logger.log /work/drep_compare/log.txt && cp outdir/data_tables/Mdb.csv /work/drep_compare/Mdb.csv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "drep_compare" / "log.txt",
        tmp_path / "drep_compare" / "warnings.txt",
        tmp_path / "drep_compare" / "Primary_clustering_dendrogram.pdf",
        tmp_path / "drep_compare" / "Clustering_scatterplots.pdf",
    ]
    assert node_class.PLAN_OUTPUTS({"select_outputs": ["log", "Cdb", "Ndb"]}, tmp_path) == [
        tmp_path / "drep_compare" / "log.txt",
        tmp_path / "drep_compare" / "Cdb.csv",
        tmp_path / "drep_compare" / "Ndb.csv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "at least two genome FASTA files are required"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "comparison_steps": "bad"}) == (
        "comparison_steps must be one of: default, SkipMash, SkipSecondary"
    )
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "S_algorithm": "bad"}) == (
        "S_algorithm must be one of: fastANI, ANImf, ANIn, gANI, goANI"
    )
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "P_ani": 1.2}) == "P_ani must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "MASH_sketch": -1}) == "MASH_sketch must be >= 0"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"]}) is True


def test_drep_dereplicate_renders_dereplication_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("drep_dereplicate")
    info = _registry().object_info()["drep_dereplicate"]

    assert info["output"] == ["DIRECTORY", "TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV", "PDF", "PDF", "CSV", "TSV"]
    assert info["output_name"] == [
        "dereplicated_genomes",
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
        "cluster_scoring",
        "winning_genomes",
        "widb",
        "chdb",
    ]
    assert info["input"]["required"]["genomes"][0] == "STRING"
    assert info["input"]["required"]["genomes"][1]["multiple"] is True
    assert info["input"]["optional"]["quality_source"][1]["options"] == ["checkm", "genomeInfo", "ignoreGenomeQuality"]
    assert "10.1038/ismej.2017.126" in info["citation_dois"]
    assert node_class.render_command(
        {
            "genomes": ["Genome A.fa", "sample/B.fna"],
            "genome_identifiers": ["Genome A", "sample/B"],
            "quality_source": "checkm",
            "checkM_method": "taxonomy_wf",
            "set_recursion": 2000,
            "length": 60000,
            "completeness": 80,
            "contamination": 10,
            "threads": 8,
            "output": "/work/drep_dereplicate",
        }
    ) == (
        "mkdir -p /work/drep_dereplicate && ln -s 'Genome A.fa' Genome_A.fasta && ln -s sample/B.fna sample_B.fasta && "
        "dRep dereplicate outdir -g Genome_A.fasta sample_B.fasta --length 60000 --completeness 80 --contamination 10 "
        "--checkM_method taxonomy_wf --set_recurison 2000 --checkm_group_size 2000 --MASH_sketch 1000 --P_ani 0.9 "
        "--primary_chunksize 5000 --S_algorithm ANImf --n_PRESET normal --coverage_method larger --S_ani 0.99 --cov_thresh 0.1 "
        "--clusterAlg average --completeness_weight 1 --contamination_weight 5 --strain_heterogeneity_weight 1 --N50_weight 0.5 "
        "--size_weight 0 --centrality_weight 1 --warn_dist 0.25 --warn_sim 0.98 --warn_aln 0.25 --processors ${GALAXY_SLOTS:-8} "
        "|| (rc=$?; ls -ltr `find outdir -type f`; cat outdir/data/checkM/checkM_outdir/checkm.log; "
        "cat outdir/log/logger.log; exit $rc) && cp -r outdir/dereplicated_genomes /work/drep_dereplicate/dereplicated_genomes && "
        "cp outdir/log/logger.log /work/drep_dereplicate/log.txt && cp outdir/log/warnings.txt /work/drep_dereplicate/warnings.txt && "
        "cp outdir/figures/Primary_clustering_dendrogram.pdf /work/drep_dereplicate/Primary_clustering_dendrogram.pdf && "
        "cp outdir/figures/Clustering_scatterplots.pdf /work/drep_dereplicate/Clustering_scatterplots.pdf && "
        "cp outdir/figures/Cluster_scoring.pdf /work/drep_dereplicate/Cluster_scoring.pdf && "
        "cp outdir/figures/Winning_genomes.pdf /work/drep_dereplicate/Winning_genomes.pdf && "
        "cp outdir/data_tables/Widb.csv /work/drep_dereplicate/Widb.csv"
    )
    assert node_class.render_command(
        {
            "genomes": ["001", "002"],
            "quality_source": "genomeInfo",
            "genomeInfo": "quality info.csv",
            "extra_weight_table": "weights.tsv",
            "completeness_weight": 1.5,
            "contamination_weight": 4,
            "strain_heterogeneity_weight": 0.8,
            "N50_weight": 0.25,
            "size_weight": 0.1,
            "centrality_weight": 2,
            "select_outputs": ["log", "Chdb"],
            "output": "/work/drep_dereplicate",
        }
    ) == (
        "mkdir -p /work/drep_dereplicate && ln -s 001 001.fasta && ln -s 002 002.fasta && "
        "dRep dereplicate outdir -g 001.fasta 002.fasta --length 50000 --completeness 75 --contamination 25 "
        "--genomeInfo 'quality info.csv' --MASH_sketch 1000 --P_ani 0.9 --primary_chunksize 5000 --S_algorithm ANImf "
        "--n_PRESET normal --coverage_method larger --S_ani 0.99 --cov_thresh 0.1 --clusterAlg average "
        "--completeness_weight 1.5 --contamination_weight 4 --strain_heterogeneity_weight 0.8 --N50_weight 0.25 "
        "--size_weight 0.1 --centrality_weight 2 --extra_weight_table weights.tsv --warn_dist 0.25 --warn_sim 0.98 "
        "--warn_aln 0.25 --processors ${GALAXY_SLOTS:-1} || (rc=$?; ls -ltr `find outdir -type f`; "
        "cat outdir/data/checkM/checkM_outdir/checkm.log; cat outdir/log/logger.log; exit $rc) && "
        "cp -r outdir/dereplicated_genomes /work/drep_dereplicate/dereplicated_genomes && "
        "cp outdir/log/logger.log /work/drep_dereplicate/log.txt && "
        "cp outdir/data/checkM/checkM_outdir/Chdb.tsv /work/drep_dereplicate/Chdb.tsv"
    )
    assert node_class.render_command(
        {
            "genomes": ["a.fa", "b.fa"],
            "quality_source": "ignoreGenomeQuality",
            "select_outputs": ["log"],
            "output": "/work/drep_dereplicate",
        }
    ).startswith(
        "mkdir -p /work/drep_dereplicate && ln -s a.fa a.fa.fasta && ln -s b.fa b.fa.fasta && "
        "dRep dereplicate outdir -g a.fa.fasta b.fa.fasta --length 50000 --completeness 75 --contamination 25 "
        "--ignoreGenomeQuality"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "drep_dereplicate" / "dereplicated_genomes",
        tmp_path / "drep_dereplicate" / "log.txt",
        tmp_path / "drep_dereplicate" / "warnings.txt",
        tmp_path / "drep_dereplicate" / "Primary_clustering_dendrogram.pdf",
        tmp_path / "drep_dereplicate" / "Clustering_scatterplots.pdf",
        tmp_path / "drep_dereplicate" / "Cluster_scoring.pdf",
        tmp_path / "drep_dereplicate" / "Winning_genomes.pdf",
        tmp_path / "drep_dereplicate" / "Widb.csv",
    ]
    assert node_class.PLAN_OUTPUTS({"select_outputs": ["log", "Chdb"]}, tmp_path) == [
        tmp_path / "drep_dereplicate" / "dereplicated_genomes",
        tmp_path / "drep_dereplicate" / "log.txt",
        tmp_path / "drep_dereplicate" / "Chdb.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "at least two genome FASTA files are required"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "quality_source": "bad"}) == (
        "quality_source must be one of: checkm, genomeInfo, ignoreGenomeQuality"
    )
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "quality_source": "genomeInfo"}) == "genomeInfo is required"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "completeness": 101}) == "completeness must be between 0 and 100"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "checkm_group_size": 0}) == "checkm_group_size must be >= 1"
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"], "strain_heterogeneity_weight": 2}) == (
        "strain_heterogeneity_weight must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"genomes": ["a.fa", "b.fa"]}) is True


def test_cami_amber_renders_evaluation_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("cami_amber")
    info = _registry().object_info()["cami_amber"]

    assert info["output"] == ["HTML_REPORT", "TSV", "TSV", "TSV"]
    assert info["output_name"] == ["html", "result", "metrics_genome", "metrics_bin"]
    assert info["input"]["required"]["gold_standard_file"][0] == "TSV"
    assert info["input"]["required"]["binning_files"][1]["multiple"] is True
    assert info["input"]["optional"]["ncbi_mode"][1]["options"] == ["none", "manual", "data"]
    assert "10.1093/gigascience/giy069" in info["citation_dois"]
    assert node_class.render_command(
        {
            "gold_standard_file": "gsa mapping.tsv",
            "binning_files": ["elated.tsv", "goofy.tsv", "naughty.tsv"],
            "labels": ["test1", "test2", "test3"],
            "filter": 1,
            "min_length": 200,
            "desc": "TEST FOR GALAXY",
            "min_completeness": [50, 70, 90],
            "max_contamination": [2],
            "remove_genomes": "unique_common.tsv",
            "remove_keyword": "circular element",
            "genome_coverage": "coverage.tsv",
            "ncbi_mode": "manual",
            "ncbi_files": ["nodes.dmp", "merged.dmp", "names.dmp"],
            "ncbi_identifiers": ["nodes.dmp", "merged.dmp", "names.dmp"],
            "output": "/work/cami_amber",
        }
    ) == (
        "mkdir -p output inputs /work/cami_amber/html_files ncbi && ln -s nodes.dmp ./ncbi/nodes.dmp && "
        "ln -s merged.dmp ./ncbi/merged.dmp && ln -s names.dmp ./ncbi/names.dmp && "
        "ln -s elated.tsv ./inputs/0.tsv && ln -s goofy.tsv ./inputs/1.tsv && ln -s naughty.tsv ./inputs/2.tsv && "
        "amber.py -g 'gsa mapping.tsv' -l test1,test2,test3 -p 1 -n 200 -d 'TEST FOR GALAXY' "
        "--min_completeness 50,70,90 --max_contamination 2 -r unique_common.tsv -k 'circular element' "
        "--genome_coverage coverage.tsv --ncbi_dir ncbi -o output inputs/0.tsv inputs/1.tsv inputs/2.tsv && "
        "mv output/heatmap_bar.png /work/cami_amber/html_files && cp output/index.html /work/cami_amber/index.html && "
        "cp output/results.tsv /work/cami_amber/results.tsv && "
        "cp output/genome_metrics_cami1.tsv /work/cami_amber/genome_metrics_cami1.tsv && "
        "cp output/bin_metrics.tsv /work/cami_amber/bin_metrics.tsv"
    )
    assert node_class.render_command(
        {
            "gold_standard_file": "gold.tsv",
            "binning_files": ["bin1.tsv", "bin2.tsv"],
            "ncbi_mode": "data",
            "ncbi_dir": "/ref/ncbi-taxonomy",
            "output": "/work/cami_amber",
        }
    ) == (
        "mkdir -p output inputs /work/cami_amber/html_files && ln -s bin1.tsv ./inputs/0.tsv && ln -s bin2.tsv ./inputs/1.tsv && "
        "amber.py -g gold.tsv -p 0 --ncbi_dir /ref/ncbi-taxonomy -o output inputs/0.tsv inputs/1.tsv && "
        "mv output/heatmap_bar.png /work/cami_amber/html_files && cp output/index.html /work/cami_amber/index.html && "
        "cp output/results.tsv /work/cami_amber/results.tsv && "
        "cp output/genome_metrics_cami1.tsv /work/cami_amber/genome_metrics_cami1.tsv && "
        "cp output/bin_metrics.tsv /work/cami_amber/bin_metrics.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "cami_amber" / "index.html",
        tmp_path / "cami_amber" / "results.tsv",
        tmp_path / "cami_amber" / "genome_metrics_cami1.tsv",
        tmp_path / "cami_amber" / "bin_metrics.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "gold_standard_file is required"
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv"}) == "at least one binning file is required"
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"], "labels": ["a", "b"]}) == (
        "labels count must match binning_files count"
    )
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"], "filter": -1}) == "filter must be >= 0"
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"], "min_completeness": [50, 101]}) == (
        "min_completeness values must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"], "ncbi_mode": "manual"}) == (
        "ncbi_files are required when ncbi_mode is manual"
    )
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"], "ncbi_mode": "data"}) == (
        "ncbi_dir is required when ncbi_mode is data"
    )
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "binning_files": ["bin.tsv"]}) is True


def test_cami_amber_add_renders_length_column_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("cami_amber_add")
    info = _registry().object_info()["cami_amber_add"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["file"]
    assert info["input"]["required"]["gold_standard_file"][0] == "TSV"
    assert info["input"]["required"]["fasta_file"][0] == "FILE"
    assert "10.1093/gigascience/giy069" in info["citation_dois"]
    assert node_class.render_command(
        {
            "gold_standard_file": "gold standard.tsv",
            "gold_standard_identifier": "Gold Standard 1.tsv",
            "fasta_file": "reads file.fa.gz",
            "fasta_identifier": "reads 1.fa.gz",
            "output": "/work/cami_amber_add",
        }
    ) == (
        "mkdir -p /work/cami_amber_add && ln -s 'gold standard.tsv' Gold_Standard_1.tsv && "
        "ln -s 'reads file.fa.gz' reads_1.fa.gz && add_length_column.py -g Gold_Standard_1.tsv -f reads_1.fa.gz "
        "> gold_standard_file.tsv && cp gold_standard_file.tsv /work/cami_amber_add/gold_standard_file.tsv"
    )
    assert node_class.render_command(
        {
            "gold_standard_file": "gold.tsv",
            "fasta_file": "reads.fastq",
            "output": "/work/cami_amber_add",
        }
    ) == (
        "mkdir -p /work/cami_amber_add && ln -s gold.tsv gold.tsv && ln -s reads.fastq reads.fastq && "
        "add_length_column.py -g gold.tsv -f reads.fastq > gold_standard_file.tsv && "
        "cp gold_standard_file.tsv /work/cami_amber_add/gold_standard_file.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "cami_amber_add" / "gold_standard_file.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "gold_standard_file is required"
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv"}) == "fasta_file is required"
    assert node_class.VALIDATE_INPUTS({"gold_standard_file": "gold.tsv", "fasta_file": "reads.fa.gz"}) is True


def test_cami_amber_convert_renders_biobox_conversion_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("cami_amber_convert")
    info = _registry().object_info()["cami_amber_convert"]

    assert info["output"] == ["TSV", "DIRECTORY"]
    assert info["output_name"] == ["binning_file", "binning_collection"]
    assert info["input"]["required"]["files"][0] == "FASTA"
    assert info["input"]["required"]["files"][1]["multiple"] is True
    assert info["input"]["required"]["work"][1]["options"] == ["single", "all"]
    assert "10.1093/gigascience/giy069" in info["citation_dois"]
    assert node_class.render_command(
        {
            "work": "single",
            "files": ["test add1.fasta", "test_add2.fasta"],
            "file_identifiers": ["test add1.fasta", "test_add2.fasta"],
            "output": "/work/cami_amber_convert",
        }
    ) == (
        "mkdir -p output /work/cami_amber_convert && ln -s 'test add1.fasta' test_add1.fasta && "
        "ln -s test_add2.fasta test_add2.fasta && convert_fasta_bins_to_biobox_format.py -o output/test_add1.tsv "
        "test_add1.fasta && convert_fasta_bins_to_biobox_format.py -o output/test_add2.tsv test_add2.fasta && "
        "cp -r output /work/cami_amber_convert/binning_collection"
    )
    assert node_class.render_command(
        {
            "work": "all",
            "files": ["test_add1.fasta", "test_add2.fasta"],
            "output": "/work/cami_amber_convert",
        }
    ) == (
        "mkdir -p output /work/cami_amber_convert && ln -s test_add1.fasta test_add1.fasta && "
        "ln -s test_add2.fasta test_add2.fasta && convert_fasta_bins_to_biobox_format.py -o output/binning.tsv "
        "test_add1.fasta test_add2.fasta && cp output/binning.tsv /work/cami_amber_convert/binning.tsv"
    )
    assert node_class.PLAN_OUTPUTS({"work": "all"}, tmp_path) == [
        tmp_path / "cami_amber_convert" / "binning.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"work": "single", "files": ["test_add1.fasta", "test_add2.fasta"]}, tmp_path) == [
        tmp_path / "cami_amber_convert" / "binning_collection",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "at least one FASTA file is required"
    assert node_class.VALIDATE_INPUTS({"files": ["a.fa"], "work": "bad"}) == "work must be one of: single, all"
    assert node_class.VALIDATE_INPUTS({"files": ["a.fa"], "work": "single", "file_identifiers": ["a", "b"]}) == (
        "file_identifiers count must match files count"
    )
    assert node_class.VALIDATE_INPUTS({"files": ["a.fa"], "work": "single"}) is True


def test_fargene_renders_arg_prediction_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("fargene")
    info = _registry().object_info()["fargene"]

    assert info["output"] == ["TXT", "TGZ", "TXT", "DIRECTORY", "DIRECTORY"]
    assert info["output_name"] == ["summary", "retrieved_fragments", "fargene_log", "hmmsearchresults", "predicted_genes"]
    assert info["input"]["required"]["input_type"][1]["options"] == ["paired", "collection", "sequence"]
    assert info["input"]["required"]["models"][1]["options"] == ["class_a", "class_b_1_2", "class_b_3", "class_c", "class_d_1", "class_d_2", "qnr"]
    assert "10.1186/s40168-019-0670-1" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_type": "paired",
            "R1": "reads R1.fastq.gz",
            "R2": "reads R2.fastq.gz",
            "R1_identifier": "reads R1",
            "R2_identifier": "reads R2",
            "models": "class_b_1_2",
            "meta_score": 0.4,
            "score": 12,
            "protein": True,
            "min_orf_length": 120,
            "retrieve_whole": True,
            "no_quality_filtering": True,
            "threads": 8,
            "output": "/work/fargene",
        }
    ) == (
        "mkdir -p /work/fargene && ln -fs 'reads R1.fastq.gz' reads_R1.fastq && "
        "ln -fs 'reads R2.fastq.gz' reads_R2.fastq && fargene --infiles '*.fastq' --meta --hmm-model class_b_1_2 "
        "--output fargene_output --tmp-dir tmp -p ${GALAXY_SLOTS:-8} --meta-score 0.4 --score 12 --protein "
        "--min-orf-length 120 --retrieve-whole --no-quality-filtering && tar -czf retrievedFragments.tar.gz "
        "fargene_output/retrievedFragments 2>&1 && cp fargene_output/results_summary.txt /work/fargene/results_summary.txt && "
        "cp retrievedFragments.tar.gz /work/fargene/retrievedFragments.tar.gz && cp fargene_analysis.log /work/fargene/fargene_analysis.log && "
        "cp -r fargene_output/hmmsearchresults /work/fargene/hmmsearchresults && cp -r fargene_output/predictedGenes /work/fargene/predictedGenes"
    )
    assert node_class.render_command(
        {
            "input_type": "collection",
            "input_collection": [
                {"forward": "pair1_R1.fastq", "reverse": "pair1_R2.fastq", "identifier": "Pair 1"},
                {"forward": "pair2_R1.fastq", "reverse": "pair2_R2.fastq", "identifier": "Pair 2"},
            ],
            "models": "qnr",
            "output": "/work/fargene",
        }
    ).startswith(
        "mkdir -p /work/fargene && ln -fs pair1_R1.fastq Pair_1_1.fastq && ln -fs pair1_R2.fastq Pair_1_2.fastq && "
        "ln -fs pair2_R1.fastq Pair_2_1.fastq && ln -fs pair2_R2.fastq Pair_2_2.fastq && "
        "fargene --infiles '*.fastq' --meta --hmm-model qnr"
    )
    assert node_class.render_command(
        {
            "input_type": "sequence",
            "input_sequence": ["klebsiella plasmid.fasta", "contigs.fa"],
            "sequence_identifiers": ["klebsiella plasmid", "contigs.fa"],
            "models": "class_a",
            "no_orf_predict": True,
            "orf_finder": True,
            "store_peptides": True,
            "output": "/work/fargene",
        }
    ) == (
        "mkdir -p /work/fargene && ln -fs 'klebsiella plasmid.fasta' klebsiella_plasmid.fasta && "
        "ln -fs contigs.fa contigs.fa.fasta && fargene --infiles '*.fasta' --hmm-model class_a --output fargene_output "
        "--tmp-dir tmp -p ${GALAXY_SLOTS:-4} --no-orf-predict --orf-finder --store-peptides 2>&1 && "
        "cp fargene_output/results_summary.txt /work/fargene/results_summary.txt && "
        "cp fargene_analysis.log /work/fargene/fargene_analysis.log && "
        "cp -r fargene_output/hmmsearchresults /work/fargene/hmmsearchresults && "
        "cp -r fargene_output/predictedGenes /work/fargene/predictedGenes"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "paired"}, tmp_path) == [
        tmp_path / "fargene" / "results_summary.txt",
        tmp_path / "fargene" / "retrievedFragments.tar.gz",
        tmp_path / "fargene" / "fargene_analysis.log",
        tmp_path / "fargene" / "hmmsearchresults",
        tmp_path / "fargene" / "predictedGenes",
    ]
    assert node_class.PLAN_OUTPUTS({"input_type": "sequence"}, tmp_path) == [
        tmp_path / "fargene" / "results_summary.txt",
        tmp_path / "fargene" / "fargene_analysis.log",
        tmp_path / "fargene" / "hmmsearchresults",
        tmp_path / "fargene" / "predictedGenes",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "input_type must be one of: paired, collection, sequence"
    assert node_class.VALIDATE_INPUTS({"input_type": "paired", "R1": "r1.fastq"}) == "R1 and R2 are required for paired input"
    assert node_class.VALIDATE_INPUTS({"input_type": "collection"}) == "input_collection is required for collection input"
    assert node_class.VALIDATE_INPUTS({"input_type": "sequence"}) == "input_sequence is required for sequence input"
    assert node_class.VALIDATE_INPUTS({"input_type": "sequence", "input_sequence": ["a.fa"], "models": "bad"}) == (
        "models must be one of: class_a, class_b_1_2, class_b_3, class_c, class_d_1, class_d_2, qnr"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "sequence", "input_sequence": ["a.fa"], "models": "class_a", "score": -1}) == (
        "score must be >= 0"
    )
    assert node_class.VALIDATE_INPUTS({"input_type": "sequence", "input_sequence": ["a.fa"], "models": "class_a"}) is True


def test_metabat2_renders_binning_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("metabat2")
    info = _registry().object_info()["metabat2"]

    assert info["output"] == ["DIRECTORY", "TSV", "DIRECTORY", "FASTA", "FASTA", "FASTA", "TXT"]
    assert info["output_name"] == ["bins", "bin_saveCls", "bin_onlyLabel", "lowDepth", "tooShort", "unbinned", "process_log"]
    assert info["input"]["required"]["inFile"][0] == "FASTA"
    assert info["input"]["optional"]["base_coverage_depth"][1]["options"] == ["no", "yes"]
    assert info["input"]["optional"]["extra_outputs"][1]["options"] == ["lowDepth", "tooShort", "unbinned", "log"]
    assert "10.7717/peerj.7359" in info["citation_dois"]
    assert node_class.render_command(
        {
            "inFile": "assembly.fa.gz",
            "seed": 345678,
            "extra_outputs": ["lowDepth", "tooShort", "unbinned", "log"],
            "threads": 12,
            "output": "/work/metabat2",
        }
    ) == (
        "mkdir -p bins /work/metabat2 && metabat2 --inFile assembly.fa.gz --outFile bins/bin --minContig 2500 "
        "--minSmallContig 1000 --maxP 95 --minS 60 --maxEdges 200 --pTNF 0 --minRecruitingSize 10 --minCV 1.0 "
        "--minCVSum 1.0 --seed 345678 --minClsSize 200000 --numThreads ${GALAXY_SLOTS:-12} --unbinned "
        "> process_log.txt && mv process_log.txt /work/metabat2/process_log.txt && cp -r bins /work/metabat2/bins && "
        "cp bins/bin.lowDepth.fa /work/metabat2/bin.lowDepth.fa && cp bins/bin.tooShort.fa /work/metabat2/bin.tooShort.fa && "
        "cp bins/bin.unbinned.fa /work/metabat2/bin.unbinned.fa"
    )
    assert node_class.render_command(
        {
            "inFile": "assembly.fa",
            "base_coverage_depth": "yes",
            "abdFile": "depth matrix.tsv",
            "minCV": 0.1,
            "minCVSum": 0.2,
            "saveCls": True,
            "fullHeader": True,
            "output": "/work/metabat2",
        }
    ) == (
        "mkdir -p bins /work/metabat2 && metabat2 --inFile assembly.fa --outFile bins/bin --abdFile 'depth matrix.tsv' "
        "--minContig 2500 --minSmallContig 1000 --maxP 95 --minS 60 --maxEdges 200 --pTNF 0 --minRecruitingSize 10 "
        "--minCV 0.1 --minCVSum 0.2 --seed 0 --minClsSize 200000 --numThreads ${GALAXY_SLOTS:-4} --fullHeader "
        "--noBinOut > process_log.txt && cp bins/bin.MemberMatrix.txt /work/metabat2/bin.MemberMatrix.txt"
    )
    assert node_class.render_command(
        {
            "inFile": "assembly.fa",
            "base_coverage_depth": "yes",
            "cvExt": "coverage.tsv",
            "onlyLabel": True,
            "noAdd": True,
            "output": "/work/metabat2",
        }
    ).startswith(
        "mkdir -p bins /work/metabat2 && metabat2 --inFile assembly.fa --outFile bins/bin --cvExt coverage.tsv "
        "--minContig 2500 --minSmallContig 1000 --maxP 95 --minS 60 --maxEdges 200 --pTNF 0 --noAdd"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "metabat2" / "bins",
    ]
    assert node_class.PLAN_OUTPUTS({"saveCls": True}, tmp_path) == [
        tmp_path / "metabat2" / "bin.MemberMatrix.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"onlyLabel": True}, tmp_path) == [
        tmp_path / "metabat2" / "bin_onlyLabel",
    ]
    assert node_class.PLAN_OUTPUTS({"extra_outputs": ["lowDepth", "tooShort", "unbinned", "log"]}, tmp_path) == [
        tmp_path / "metabat2" / "bins",
        tmp_path / "metabat2" / "bin.lowDepth.fa",
        tmp_path / "metabat2" / "bin.tooShort.fa",
        tmp_path / "metabat2" / "bin.unbinned.fa",
        tmp_path / "metabat2" / "process_log.txt",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "inFile is required"
    assert node_class.VALIDATE_INPUTS({"inFile": "assembly.fa", "base_coverage_depth": "yes"}) == (
        "abdFile or cvExt is required when base_coverage_depth is yes"
    )
    assert node_class.VALIDATE_INPUTS({"inFile": "assembly.fa", "saveCls": True, "onlyLabel": True}) == (
        "saveCls and onlyLabel cannot both be enabled"
    )
    assert node_class.VALIDATE_INPUTS({"inFile": "assembly.fa", "minContig": 1000}) == "minContig must be >= 1500"
    assert node_class.VALIDATE_INPUTS({"inFile": "assembly.fa", "maxP": 101}) == "maxP must be between 1 and 100"
    assert node_class.VALIDATE_INPUTS({"inFile": "assembly.fa"}) is True


def test_metabat2_jgi_depths_renders_contig_depth_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("metabat2_jgi_summarize_bam_contig_depths")
    info = _registry().object_info()["metabat2_jgi_summarize_bam_contig_depths"]

    assert info["output"] == ["TSV", "FASTA", "TSV", "TSV", "TSV"]
    assert info["output_name"] == ["outputDepth", "outputPairedContigs", "outputGC", "outputReadStats", "outputKmers"]
    assert info["input"]["required"]["mode_type"][1]["options"] == ["individual", "co"]
    assert info["input"]["optional"]["use_reference"][1]["options"] == ["no", "yes"]
    assert "10.7717/peerj.7359" in info["citation_dois"]
    assert node_class.render_command(
        {
            "mode_type": "individual",
            "bam_indiv_input": "sample.bam",
            "percentIdentity": 95,
            "output_paired_contigs": True,
            "noIntraDepthVariance": True,
            "showDepth": True,
            "minMapQual": 20,
            "weightMapQual": 0.5,
            "includeEdgeBases": True,
            "maxEdgeBases": 100,
            "use_reference": "yes",
            "reference_source": "history",
            "referenceFasta": "reference.fa",
            "gcWindow": 250,
            "shredLength": 12000,
            "shredDepth": 8,
            "minContigLength": 1000,
            "minContigDepth": 0.2,
            "output": "/work/metabat2_depths",
        }
    ) == (
        "mkdir -p /work/metabat2_depths && jgi_summarize_bam_contig_depths --outputDepth /work/metabat2_depths/outputDepth.tsv "
        "--percentIdentity 95 --pairedContigs /work/metabat2_depths/outputPairedContigs.fa --noIntraDepthVariance --showDepth "
        "--minMapQual 20 --weightMapQual 0.5 --includeEdgeBases --maxEdgeBases 100 --referenceFasta reference.fa "
        "--outputGC /work/metabat2_depths/outputGC.tsv --gcWindow 250 --outputReadStats /work/metabat2_depths/outputReadStats.tsv "
        "--outputKmers /work/metabat2_depths/outputKmers.tsv --shredLength 12000 --shredDepth 8 --minContigLength 1000 "
        "--minContigDepth 0.2 sample.bam"
    )
    assert node_class.render_command(
        {
            "mode_type": "co",
            "bam_co_inputs": ["a.bam", "b.bam"],
            "use_reference": "yes",
            "reference_source": "cached",
            "referenceFasta": "/refs/ref.fa",
            "output": "/work/metabat2_depths",
        }
    ) == (
        "mkdir -p /work/metabat2_depths && jgi_summarize_bam_contig_depths --outputDepth /work/metabat2_depths/outputDepth.tsv "
        "--percentIdentity 97 --minMapQual 0 --weightMapQual 0.0 --maxEdgeBases 75 --referenceFasta /refs/ref.fa "
        "--outputGC /work/metabat2_depths/outputGC.tsv --gcWindow 100 --outputReadStats /work/metabat2_depths/outputReadStats.tsv "
        "--outputKmers /work/metabat2_depths/outputKmers.tsv --shredLength 16000 --shredDepth 5 --minContigLength 1 "
        "--minContigDepth 0.0 a.bam b.bam"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputDepth.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"output_paired_contigs": True, "use_reference": "yes"}, tmp_path) == [
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputDepth.tsv",
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputPairedContigs.fa",
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputGC.tsv",
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputReadStats.tsv",
        tmp_path / "metabat2_jgi_summarize_bam_contig_depths" / "outputKmers.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "mode_type must be one of: individual, co"
    assert node_class.VALIDATE_INPUTS({"mode_type": "individual"}) == "bam_indiv_input is required for individual mode"
    assert node_class.VALIDATE_INPUTS({"mode_type": "co"}) == "at least one BAM is required for co mode"
    assert node_class.VALIDATE_INPUTS({"mode_type": "individual", "bam_indiv_input": "a.bam", "use_reference": "yes"}) == (
        "referenceFasta is required when use_reference is yes"
    )
    assert node_class.VALIDATE_INPUTS({"mode_type": "individual", "bam_indiv_input": "a.bam", "percentIdentity": 101}) == (
        "percentIdentity must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"mode_type": "individual", "bam_indiv_input": "a.bam"}) is True


def test_fastspar_renders_correlation_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("fastspar")
    info = _registry().object_info()["fastspar"]

    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["correlation", "covariance"]
    assert info["input"]["required"]["otu_table"][0] == "TSV"
    assert info["input"]["optional"]["iterations"][1]["default"] == 50
    assert "10.1093/bioinformatics/bty734" in info["citation_dois"]
    assert "10.1371/journal.pcbi.1002687" in info["citation_dois"]
    assert node_class.render_command(
        {
            "otu_table": "absolute otu counts.tsv",
            "iterations": 100,
            "exclude_iterations": 20,
            "threshold": 0.2,
            "seed": 7,
            "threads": 8,
            "output": "/work/fastspar",
        }
    ) == (
        "mkdir -p /work/fastspar && fastspar --otu_table 'absolute otu counts.tsv' --iterations 100 "
        "--exclude_iterations 20 --threshold 0.2 --seed 7 --correlation /work/fastspar/median_correlation.tsv "
        "--covariance /work/fastspar/median_covariance.tsv --threads ${GALAXY_SLOTS:-8} --yes"
    )
    assert node_class.render_command(
        {
            "otu_table": "otu.tsv",
            "output": "/work/fastspar",
        }
    ) == (
        "mkdir -p /work/fastspar && fastspar --otu_table otu.tsv --iterations 50 --exclude_iterations 10 "
        "--threshold 0.1 --seed 1 --correlation /work/fastspar/median_correlation.tsv "
        "--covariance /work/fastspar/median_covariance.tsv --threads ${GALAXY_SLOTS:-1} --yes"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "fastspar" / "median_correlation.tsv",
        tmp_path / "fastspar" / "median_covariance.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "otu_table is required"
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "iterations": 0}) == "iterations must be between 1 and 1000"
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "exclude_iterations": 101}) == (
        "exclude_iterations must be between 0 and 100"
    )
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "threshold": 1.5}) == "threshold must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv"}) is True


def test_fastspar_reduce_renders_sparse_filter_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("fastspar_reduce")
    info = _registry().object_info()["fastspar_reduce"]

    assert info["display_name"] == "FastSpar: Reduce correlation table"
    assert info["description"] == "Filter FastSpar correlation and p-value matrices into sparse tabular edge lists."
    assert info["input"]["required"]["correlation_table"][0] == "TSV"
    assert info["input"]["required"]["pvalue_table"][0] == "TSV"
    assert info["input"]["optional"]["correlation"][1]["default"] == 0.1
    assert info["input"]["optional"]["pvalue"][1]["default"] == 0.05
    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["correlations", "pvalues"]
    assert "10.1093/bioinformatics/bty734" in info["citation_dois"]
    assert "10.1371/journal.pcbi.1002687" in info["citation_dois"]
    assert node_class.render_command(
        {
            "correlation_table": "median correlation.tsv",
            "pvalue_table": "p values.tsv",
            "correlation": 0.2,
            "pvalue": 0.01,
            "output": "/work/fastspar_reduce",
        }
    ) == (
        "mkdir -p /work/fastspar_reduce && fastspar_reduce --correlation_table 'median correlation.tsv' "
        "--pvalue_table 'p values.tsv' --correlation 0.2 --pvalue 0.01 --output_prefix sparse && "
        "mv sparse_filtered_correlation.tsv /work/fastspar_reduce/filtered_correlations.tsv && "
        "mv sparse_filtered_pvalue.tsv /work/fastspar_reduce/filtered_pvalues.tsv"
    )
    assert node_class.render_command(
        {
            "correlation_table": "cor.tsv",
            "pvalue_table": "p.tsv",
            "output": "/work/fastspar_reduce",
        }
    ) == (
        "mkdir -p /work/fastspar_reduce && fastspar_reduce --correlation_table cor.tsv --pvalue_table p.tsv "
        "--correlation 0.1 --pvalue 0.05 --output_prefix sparse && "
        "mv sparse_filtered_correlation.tsv /work/fastspar_reduce/filtered_correlations.tsv && "
        "mv sparse_filtered_pvalue.tsv /work/fastspar_reduce/filtered_pvalues.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "fastspar_reduce" / "filtered_correlations.tsv",
        tmp_path / "fastspar_reduce" / "filtered_pvalues.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "correlation_table is required"
    assert node_class.VALIDATE_INPUTS({"correlation_table": "cor.tsv"}) == "pvalue_table is required"
    assert node_class.VALIDATE_INPUTS(
        {"correlation_table": "cor.tsv", "pvalue_table": "p.tsv", "correlation": 1.1}
    ) == "correlation must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS(
        {"correlation_table": "cor.tsv", "pvalue_table": "p.tsv", "pvalue": -0.01}
    ) == "pvalue must be between 0 and 1"
    assert node_class.VALIDATE_INPUTS({"correlation_table": "cor.tsv", "pvalue_table": "p.tsv"}) is True


def test_fastspar_pvalues_renders_bootstrap_pipeline_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("fastspar_pvalues")
    info = _registry().object_info()["fastspar_pvalues"]

    assert info["display_name"] == "FastSpar: estimate p-values"
    assert info["description"] == "Estimate empirical p-values for FastSpar correlations with bootstrap resampling."
    assert info["input"]["required"]["otu_table"][0] == "TSV"
    assert info["input"]["optional"]["correlation_mode"][1]["default"] == "original"
    assert info["input"]["optional"]["correlation_mode"][1]["options"] == ["new", "original"]
    assert info["input"]["optional"]["number"][1]["default"] == 1000
    assert info["input"]["optional"]["pseudo"][1]["default"] is False
    assert info["output"] == ["TSV", "TSV", "TSV"]
    assert info["output_name"] == ["correlation", "covariance", "pvalues"]
    assert "10.1093/bioinformatics/bty734" in info["citation_dois"]
    assert "10.1371/journal.pcbi.1002687" in info["citation_dois"]

    assert node_class.render_command(
        {
            "otu_table": "absolute otu counts.tsv",
            "correlation_mode": "original",
            "correlation_file": "median correlation.tsv",
            "number": 10,
            "iterations": 100,
            "exclude_iterations": 20,
            "threshold": 0.2,
            "seed": 7,
            "pseudo": True,
            "threads": 8,
            "output": "/work/fastspar_pvalues",
        }
    ) == (
        "mkdir -p /work/fastspar_pvalues bootstrap_counts bootstrap_correlation && "
        "fastspar_bootstrap --otu_table 'absolute otu counts.tsv' --number 10 --prefix bootstrap_counts/data "
        "--seed 7 --threads ${GALAXY_SLOTS:-8} && "
        "parallel --max-procs ${GALAXY_SLOTS:-8} fastspar --otu_table {} --correlation "
        "bootstrap_correlation/cor_{/} --covariance bootstrap_correlation/cov_{/} --iterations 100 "
        "--exclude_iterations 20 --threshold 0.2 --seed 7 ::: bootstrap_counts/* && "
        "fastspar_pvalues --otu_table 'absolute otu counts.tsv' --correlation 'median correlation.tsv' "
        "--prefix bootstrap_correlation/cor_data_ --permutations 10 --pseudo --threads ${GALAXY_SLOTS:-8} "
        "--outfile /work/fastspar_pvalues/pvalues.tsv"
    )
    assert node_class.render_command(
        {
            "otu_table": "otu.tsv",
            "correlation_mode": "new",
            "number": 10,
            "output": "/work/fastspar_pvalues",
        }
    ) == (
        "mkdir -p /work/fastspar_pvalues bootstrap_counts bootstrap_correlation && "
        "fastspar --otu_table otu.tsv --iterations 50 --exclude_iterations 10 --threshold 0.1 --seed 1 "
        "--correlation /work/fastspar_pvalues/median_correlation.tsv --covariance "
        "/work/fastspar_pvalues/median_covariance.tsv --threads ${GALAXY_SLOTS:-1} --yes && "
        "fastspar_bootstrap --otu_table otu.tsv --number 10 --prefix bootstrap_counts/data --seed 1 "
        "--threads ${GALAXY_SLOTS:-1} && "
        "parallel --max-procs ${GALAXY_SLOTS:-1} fastspar --otu_table {} --correlation "
        "bootstrap_correlation/cor_{/} --covariance bootstrap_correlation/cov_{/} --iterations 50 "
        "--exclude_iterations 10 --threshold 0.1 --seed 1 ::: bootstrap_counts/* && "
        "fastspar_pvalues --otu_table otu.tsv --correlation /work/fastspar_pvalues/median_correlation.tsv "
        "--prefix bootstrap_correlation/cor_data_ --permutations 10 --threads ${GALAXY_SLOTS:-1} "
        "--outfile /work/fastspar_pvalues/pvalues.tsv"
    )
    assert node_class.PLAN_OUTPUTS({"correlation_mode": "original"}, tmp_path) == [
        tmp_path / "fastspar_pvalues" / "pvalues.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"correlation_mode": "new"}, tmp_path) == [
        tmp_path / "fastspar_pvalues" / "median_correlation.tsv",
        tmp_path / "fastspar_pvalues" / "median_covariance.tsv",
        tmp_path / "fastspar_pvalues" / "pvalues.tsv",
    ]
    assert node_class.VALIDATE_INPUTS({}) == "otu_table is required"
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "correlation_mode": "original"}) == (
        "correlation_file is required when correlation_mode is original"
    )
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "correlation_mode": "new", "number": 9}) == (
        "number must be between 10 and 10000"
    )
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "correlation_mode": "new", "threshold": -0.1}) == (
        "threshold must be between 0 and 1"
    )
    assert node_class.VALIDATE_INPUTS({"otu_table": "otu.tsv", "correlation_mode": "new", "number": 10}) is True


def test_taxonkit_name2taxid_renders_taxonomy_setup_command_outputs_and_validation(tmp_path: Path) -> None:
    node_class = _node_class("taxonkit_name2taxid")
    info = _registry().object_info()["taxonkit_name2taxid"]

    assert info["display_name"] == "Name2taxid"
    assert info["description"] == "Convert NCBI taxon names in a tabular column to taxids with TaxonKit."
    assert info["input"]["required"]["input"][0] == "TSV"
    assert info["input"]["required"]["name_field"][0] == "INT"
    assert info["input"]["required"]["data_source"][1]["options"] == ["cached", "history"]
    assert info["input"]["optional"]["sci_name"][1]["default"] is False
    assert info["input"]["optional"]["show_rank"][1]["default"] is False
    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["output"]
    assert "10.1016/j.jgg.2021.03.006" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input": "names table.tsv",
            "name_field": 2,
            "data_source": "history",
            "taxdump": "taxdump.tar.gz",
            "sci_name": True,
            "show_rank": True,
            "output": "/work/name2taxid",
        }
    ) == (
        "mkdir -p /work/name2taxid .taxonkit && ln -s taxdump.tar.gz taxdump.tar.gz && "
        "tar -xf taxdump.tar.gz -C . && taxonkit name2taxid --data-dir . --name-field 2 "
        "--sci-name --show-rank 'names table.tsv' > /work/name2taxid/names2taxid.tsv"
    )
    assert node_class.render_command(
        {
            "input": "names.tsv",
            "name_field": 1,
            "data_source": "cached",
            "taxonomy_dir": "/ref/ncbi_taxonomy",
            "output": "/work/name2taxid",
        }
    ) == (
        "mkdir -p /work/name2taxid .taxonkit && ln -s /ref/ncbi_taxonomy/names.dmp names.dmp && "
        "ln -s /ref/ncbi_taxonomy/merged.dmp merged.dmp && ln -s /ref/ncbi_taxonomy/nodes.dmp nodes.dmp && "
        "ln -s /ref/ncbi_taxonomy/delnodes.dmp delnodes.dmp && taxonkit name2taxid --data-dir . "
        "--name-field 1 names.tsv > /work/name2taxid/names2taxid.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "taxonkit_name2taxid" / "names2taxid.tsv"]
    assert node_class.VALIDATE_INPUTS({}) == "input is required"
    assert node_class.VALIDATE_INPUTS({"input": "names.tsv"}) == "name_field is required"
    assert node_class.VALIDATE_INPUTS({"input": "names.tsv", "name_field": 0}) == "name_field must be >= 1"
    assert node_class.VALIDATE_INPUTS({"input": "names.tsv", "name_field": 1, "data_source": "history"}) == (
        "taxdump is required when data_source is history"
    )
    assert node_class.VALIDATE_INPUTS({"input": "names.tsv", "name_field": 1, "data_source": "cached"}) == (
        "taxonomy_dir is required when data_source is cached"
    )
    assert node_class.VALIDATE_INPUTS(
        {"input": "names.tsv", "name_field": 1, "data_source": "cached", "taxonomy_dir": "/ref/taxonomy"}
    ) is True


def test_ivar_variants_renders_mpileup_pipeline_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("ivar_variants")

    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "ref": "ref.fa",
            "min_qual": 25,
            "min_freq": 0.1,
            "output_format": "tabular_and_vcf",
            "gtf": "genes.gff",
            "pass_only": True,
            "output": "/work/ivar",
        }
    ) == [
        "samtools",
        "mpileup",
        "-A",
        "-d",
        "0",
        "--reference",
        "ref.fa",
        "-B",
        "-Q",
        "0",
        "sorted.bam",
        "|",
        "ivar",
        "variants",
        "-p",
        "/work/ivar/variants",
        "-q",
        "25",
        "-t",
        "0.1",
        "-r",
        "ref.fa",
        "-g",
        "genes.gff",
        "&&",
        "ivar_variants_to_vcf.py",
        "--pass_only",
        "/work/ivar/variants.tsv",
        "/work/ivar/variants.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({"output_format": "tabular_and_vcf"}, tmp_path) == [
        tmp_path / "ivar_variants" / "variants.tsv",
        tmp_path / "ivar_variants" / "variants.vcf",
    ]


def test_ivar_consensus_renders_mpileup_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_consensus")
    info = _registry().object_info()["ivar_consensus"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["consensus_fasta"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "min_qual": 25,
            "min_freq": 0.5,
            "min_indel_freq": 0.9,
            "min_depth": 12,
            "depth_action": "-n -",
            "output": "/work/ivar_consensus",
        }
    ) == [
        "samtools",
        "mpileup",
        "-A",
        "-a",
        "-d",
        "0",
        "-Q",
        "0",
        "sorted.bam",
        "|",
        "ivar",
        "consensus",
        "-p",
        "/work/ivar_consensus/consensus",
        "-q",
        "25",
        "-t",
        "0.5",
        "-c",
        "0.9",
        "-m",
        "12",
        "-n",
        "-",
    ]
    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "depth_action": "-k",
            "output": "/work/ivar_consensus",
        }
    )[-1] == "-k"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_consensus" / "consensus.fa"]


def test_ivar_filtervariants_renders_replicate_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_filtervariants")
    info = _registry().object_info()["ivar_filtervariants"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["filtered_variants"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "inputs": ["replicate-a.tsv", "replicate-b.tsv", "replicate-c.tsv"],
            "min_fraction": 0.5,
            "output": "/work/ivar_filtervariants",
        }
    ) == [
        "ivar",
        "filtervariants",
        "-t",
        "0.5",
        "-p",
        "/work/ivar_filtervariants/filtered",
        "replicate-a.tsv",
        "replicate-b.tsv",
        "replicate-c.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_filtervariants" / "filtered.tsv"]


def test_ivar_complete_mask_expands_masked_primers_to_full_amplicons(tmp_path: Path) -> None:
    from bionodulo.nodes.scripts.ivar_complete_mask import complete_mask_file

    masked = tmp_path / "masked_primers.txt"
    amplicons = tmp_path / "amplicon_info.tsv"
    masked.write_text("400_2_out_L\t400_3_out_R\n", encoding="utf-8")
    amplicons.write_text(
        "400_1_out_L\t400_1_out_R\n"
        "400_2_out_L\t400_2_out_R\n"
        "400_3_out_L\t400_3_out_R\n",
        encoding="utf-8",
    )

    result = complete_mask_file(masked, amplicons)

    assert result == ["400_2_out_L", "400_2_out_R", "400_3_out_L", "400_3_out_R"]
    assert masked.read_text(encoding="utf-8") == "400_2_out_L\t400_2_out_R\t400_3_out_L\t400_3_out_R\n"


def test_ivar_removereads_renders_mask_and_remove_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_removereads")
    info = _registry().object_info()["ivar_removereads"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["filtered_bam"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "trimmed.sorted.bam",
            "variants_tsv": "primer_variants.tsv",
            "input_bed": "primers.bed",
            "amplicon_mode": "provided",
            "amplicon_info": "pairs.tsv",
            "output": "/work/ivar_removereads",
        }
    ) == [
        "scheme-convert",
        "--to",
        "bed",
        "--bed-type",
        "ivar",
        "-o",
        "/work/ivar_removereads/ivar.bed",
        "primers.bed",
        "&&",
        "scheme-convert",
        "-a",
        "pairs.tsv",
        "--to",
        "amplicon-info",
        "-o",
        "/work/ivar_removereads/amplicon_info.tsv",
        "/work/ivar_removereads/ivar.bed",
        "&&",
        "ivar",
        "getmasked",
        "-i",
        "primer_variants.tsv",
        "-b",
        "/work/ivar_removereads/ivar.bed",
        "-f",
        "/work/ivar_removereads/amplicon_info.tsv",
        "-p",
        "/work/ivar_removereads/masked_primers",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.ivar_complete_mask",
        "/work/ivar_removereads/masked_primers.txt",
        "/work/ivar_removereads/amplicon_info.tsv",
        "&&",
        "ivar",
        "removereads",
        "-i",
        "trimmed.sorted.bam",
        "-b",
        "/work/ivar_removereads/ivar.bed",
        "-p",
        "/work/ivar_removereads/removed_reads.bam",
        "-t",
        "/work/ivar_removereads/masked_primers.txt",
    ]

    computed_cmd = node_class.render_command(
        {
            "input_bam": "trimmed.sorted.bam",
            "variants_tsv": "primer_variants.tsv",
            "input_bed": "primers.bed",
            "amplicon_mode": "computed",
            "output": "/work/ivar_removereads",
        }
    )
    assert "-a" not in computed_cmd
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_removereads" / "removed_reads.bam"]


def test_galaxy_parity_third_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "gtdbtk_classify_wf": {
            "display_name": "GTDB-Tk Classify",
            "category": "taxonomy",
            "required_executables": ["gtdbtk"],
            "required_conda_packages": ["gtdbtk"],
            "doi": "10.1093/bioinformatics/btz848",
        },
        "rseqc_infer_experiment": {
            "display_name": "RSeQC Infer Experiment",
            "category": "rna_seq",
            "required_executables": ["infer_experiment.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_fpkm_count": {
            "display_name": "RSeQC FPKM Count",
            "category": "rna_seq",
            "required_executables": ["FPKM_count.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_rpkm_saturation": {
            "display_name": "RSeQC RPKM Saturation",
            "category": "rna_seq",
            "required_executables": ["RPKM_saturation.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_bam2wig": {
            "display_name": "RSeQC BAM to Wiggle",
            "category": "rna_seq",
            "required_executables": ["bam2wig.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_clipping_profile": {
            "display_name": "RSeQC Clipping Profile",
            "category": "rna_seq",
            "required_executables": ["clipping_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_deletion_profile": {
            "display_name": "RSeQC Deletion Profile",
            "category": "rna_seq",
            "required_executables": ["deletion_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_gene_body_coverage": {
            "display_name": "RSeQC Gene Body Coverage",
            "category": "rna_seq",
            "required_executables": ["geneBody_coverage.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_gene_body_coverage2": {
            "display_name": "RSeQC Gene Body Coverage BigWig",
            "category": "rna_seq",
            "required_executables": ["geneBody_coverage2.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_inner_distance": {
            "display_name": "RSeQC Inner Distance",
            "category": "rna_seq",
            "required_executables": ["inner_distance.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_insertion_profile": {
            "display_name": "RSeQC Insertion Profile",
            "category": "rna_seq",
            "required_executables": ["insertion_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_hexamer": {
            "display_name": "RSeQC Read Hexamer",
            "category": "rna_seq",
            "required_executables": ["read_hexamer.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_quality": {
            "display_name": "RSeQC Read Quality",
            "category": "rna_seq",
            "required_executables": ["read_quality.py"],
            "required_conda_packages": ["rseqc", "r-base"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_rna_fragment_size": {
            "display_name": "RSeQC RNA Fragment Size",
            "category": "rna_seq",
            "required_executables": ["RNA_fragment_size.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_junction_annotation": {
            "display_name": "RSeQC Junction Annotation",
            "category": "rna_seq",
            "required_executables": ["junction_annotation.py"],
            "required_conda_packages": ["rseqc", "r-base"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_junction_saturation": {
            "display_name": "RSeQC Junction Saturation",
            "category": "rna_seq",
            "required_executables": ["junction_saturation.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_mismatch_profile": {
            "display_name": "RSeQC Mismatch Profile",
            "category": "rna_seq",
            "required_executables": ["mismatch_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_gc": {
            "display_name": "RSeQC Read GC",
            "category": "rna_seq",
            "required_executables": ["read_GC.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_nvc": {
            "display_name": "RSeQC Read NVC",
            "category": "rna_seq",
            "required_executables": ["read_NVC.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_bam_stat": {
            "display_name": "RSeQC BAM Stat",
            "category": "rna_seq",
            "required_executables": ["bam_stat.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_distribution": {
            "display_name": "RSeQC Read Distribution",
            "category": "rna_seq",
            "required_executables": ["read_distribution.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_duplication": {
            "display_name": "RSeQC Read Duplication",
            "category": "rna_seq",
            "required_executables": ["read_duplication.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_tin": {
            "display_name": "RSeQC Transcript Integrity Number",
            "category": "rna_seq",
            "required_executables": ["tin.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1186/s12859-016-0922-z",
        },
        "bedtools_coveragebed": {
            "display_name": "BEDTools Coverage",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_genomecoveragebed": {
            "display_name": "BEDTools Genome Coverage",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith(("https://", "http://"))
        assert "Galaxy" in node_info["search_aliases"]


def test_gtdbtk_classify_wf_renders_classification_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("gtdbtk_classify_wf")

    assert node_class.render_command(
        {
            "input": ["G1.fna.gz", "G2.fna.gz"],
            "extension": "fna.gz",
            "gtdbtk_data_path": "/db/gtdbtk",
            "threads": 8,
            "min_perc_aa": 15,
            "force": True,
            "min_af": 0.7,
            "full_tree": True,
            "skip_ani_screen": True,
            "output_process_log": True,
            "output": "/work/gtdbtk",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/gtdbtk/input_dir",
        "/work/gtdbtk/output_dir",
        "&&",
        "ln",
        "-sf",
        "G1.fna.gz",
        "/work/gtdbtk/input_dir/G1.fna.gz",
        "&&",
        "ln",
        "-sf",
        "G2.fna.gz",
        "/work/gtdbtk/input_dir/G2.fna.gz",
        "&&",
        "export",
        "GTDBTK_DATA_PATH=/db/gtdbtk",
        "&&",
        "gtdbtk",
        "classify_wf",
        "--genome_dir",
        "/work/gtdbtk/input_dir",
        "--extension",
        "fna.gz",
        "--out_dir",
        "/work/gtdbtk/output_dir",
        "--cpus",
        "8",
        "--min_perc_aa",
        "15",
        "--force",
        "--min_af",
        "0.7",
        "--full_tree",
        "--skip_ani_screen",
        "&&",
        "cat",
        "/work/gtdbtk/output_dir/gtdbtk.warnings.log",
        "/work/gtdbtk/output_dir/gtdbtk.log",
        ">",
        "/work/gtdbtk/process.log",
    ]

    assert node_class.PLAN_OUTPUTS({"output_process_log": True}, tmp_path) == [
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "align",
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "identify",
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "classify",
        tmp_path / "gtdbtk_classify_wf" / "output_dir",
        tmp_path / "gtdbtk_classify_wf" / "process.log",
    ]


def test_rseqc_infer_experiment_renders_strandedness_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_infer_experiment")

    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "sample_size": 200000,
            "mapq": 30,
            "output": "/work/rseqc_infer_experiment",
        }
    ) == [
        "infer_experiment.py",
        "-i",
        "aligned.bam",
        "-r",
        "genes.bed",
        "--sample-size",
        "200000",
        "--mapq",
        "30",
        ">",
        "/work/rseqc_infer_experiment/infer_experiment.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_infer_experiment" / "infer_experiment.txt",
    ]


def test_rseqc_fpkm_count_renders_expression_quantification_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_fpkm_count")
    info = _registry().object_info()["rseqc_fpkm_count"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["fpkm_counts"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "strand_specific": "pair",
            "pair_type": "ds",
            "skip_multi_hits": True,
            "mapq": 20,
            "only_exonic": True,
            "single_read": "0.5",
            "output": "/work/rseqc_fpkm_count",
        }
    ) == [
        "FPKM_count.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_fpkm_count/output",
        "-r",
        "genes.bed12",
        "-d",
        "1+-,1-+,2++,2--",
        "--skip-multi-hits",
        "--mapq",
        "20",
        "--only-exonic",
        "--single-read=0.5",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_fpkm_count" / "output.FPKM.xls",
    ]


def test_rseqc_rpkm_saturation_renders_saturation_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_rpkm_saturation")
    info = _registry().object_info()["rseqc_rpkm_saturation"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == ["saturation_plot", "rpkm_values", "raw_counts", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "strand_specific": "none",
            "percentile_floor": 10,
            "percentile_ceiling": 90,
            "percentile_step": 10,
            "rpkm_cutoff": "0.05",
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_rpkm_saturation",
        }
    ) == [
        "RPKM_saturation.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_rpkm_saturation/output",
        "-r",
        "genes.bed",
        "-l",
        "10",
        "-u",
        "90",
        "-s",
        "10",
        "-c",
        "0.05",
        "--mapq",
        "25",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "strand_specific": "pair",
            "pair_type": "ds",
            "output": "/work/rseqc_rpkm_saturation",
        }
    ) == [
        "RPKM_saturation.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_rpkm_saturation/output",
        "-r",
        "genes.bed",
        "-d",
        "1+-,1-+,2++,2--",
        "-l",
        "5",
        "-u",
        "100",
        "-s",
        "5",
        "-c",
        "0.01",
        "--mapq",
        "30",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.pdf",
        tmp_path / "rseqc_rpkm_saturation" / "output.eRPKM.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.rawCount.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.pdf",
        tmp_path / "rseqc_rpkm_saturation" / "output.eRPKM.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.rawCount.xls",
    ]


def test_rseqc_bam2wig_renders_wiggle_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_bam2wig")
    info = _registry().object_info()["rseqc_bam2wig"]

    assert info["output"] == ["WIG", "WIG", "WIG"]
    assert info["output_name"] == ["wiggle", "forward_wiggle", "reverse_wiggle"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "normalize": True,
            "totalwig": 100,
            "skip_multi_hits": True,
            "mapq": 20,
            "strand_specific": "none",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-t",
        "100",
        "--skip-multi-hits",
        "--mapq",
        "20",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "strand_specific": "pair",
            "pair_type": "ds",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-d",
        "1+-,1-+,2++,2--",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "strand_specific": "single",
            "single_type": "d",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-d",
        "+-,-+",
    ]

    assert node_class.PLAN_OUTPUTS({"strand_specific": "none"}, tmp_path) == [
        tmp_path / "rseqc_bam2wig" / "outfile.wig",
    ]
    assert node_class.PLAN_OUTPUTS({"strand_specific": "pair"}, tmp_path) == [
        tmp_path / "rseqc_bam2wig" / "outfile.Forward.wig",
        tmp_path / "rseqc_bam2wig" / "outfile.Reverse.wig",
    ]


def test_rseqc_clipping_profile_renders_clipping_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_clipping_profile")
    info = _registry().object_info()["rseqc_clipping_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["clipping_profile_plot", "clipping_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "layout": "PE",
            "rscript_output": True,
            "output": "/work/rseqc_clipping_profile",
        }
    ) == [
        "clipping_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_clipping_profile/output",
        "-q",
        "20",
        "-s",
        "PE",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.pdf",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.xls",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.pdf",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.xls",
    ]


def test_rseqc_deletion_profile_renders_deletion_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_deletion_profile")
    info = _registry().object_info()["rseqc_deletion_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["deletion_profile_plot", "deletion_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "read_align_length": 101,
            "read_num": 500000,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_deletion_profile",
        }
    ) == [
        "deletion_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_deletion_profile/output",
        "-l",
        "101",
        "-n",
        "500000",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.pdf",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.txt",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.pdf",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.txt",
    ]


def test_rseqc_gene_body_coverage_renders_single_bam_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage")
    info = _registry().object_info()["rseqc_gene_body_coverage"]

    assert info["output"] == ["IMAGE", "IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["coverage_curves", "coverage_heatmap", "coverage_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "sample.bam",
            "refgene": "genes.bed12",
            "minimum_length": 150,
            "rscript_output": True,
            "output": "/work/rseqc_gene_body_coverage",
        }
    ) == [
        "geneBody_coverage.py",
        "-i",
        "sample.bam",
        "-r",
        "genes.bed12",
        "--minimum_length",
        "150",
        "-o",
        "/work/rseqc_gene_body_coverage/output",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "sample.bam", "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]
    assert node_class.PLAN_OUTPUTS({"input": "sample.bam", "rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
    ]


def test_rseqc_gene_body_coverage_renders_merged_bam_command_and_heatmap(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage")

    assert node_class.render_command(
        {
            "input": ["sample A.bam", "sample-B.bam", "sample-B.bam"],
            "refgene": "genes.bed12",
            "minimum_length": 100,
            "output": "/work/rseqc_gene_body_coverage",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/rseqc_gene_body_coverage/input_bams",
        "&&",
        "ln",
        "-sf",
        "sample A.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample_A.bam",
        "&&",
        "ln",
        "-sf",
        "sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.bam",
        "&&",
        "ln",
        "-sf",
        "sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.2.bam",
        "&&",
        "printf",
        "%s\\n",
        "/work/rseqc_gene_body_coverage/input_bams/sample_A.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.2.bam",
        ">",
        "/work/rseqc_gene_body_coverage/input_list.txt",
        "&&",
        "geneBody_coverage.py",
        "-i",
        "/work/rseqc_gene_body_coverage/input_list.txt",
        "-r",
        "genes.bed12",
        "--minimum_length",
        "100",
        "-o",
        "/work/rseqc_gene_body_coverage/output",
    ]

    assert node_class.PLAN_OUTPUTS({"input": ["A.bam", "B.bam", "C.bam"], "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.heatMap.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]
    assert node_class.PLAN_OUTPUTS({"input": ["A.bam", "B.bam"], "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]


def test_rseqc_gene_body_coverage2_renders_bigwig_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage2")
    info = _registry().object_info()["rseqc_gene_body_coverage2"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["coverage_plot", "coverage_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "coverage.bw",
            "refgene": "genes.bed12",
            "rscript_output": True,
            "output": "/work/rseqc_gene_body_coverage2",
        }
    ) == [
        "geneBody_coverage2.py",
        "-i",
        "coverage.bw",
        "-r",
        "genes.bed12",
        "-o",
        "/work/rseqc_gene_body_coverage2/output",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.pdf",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.pdf",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.txt",
    ]


def test_rseqc_inner_distance_renders_insert_size_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_inner_distance")
    info = _registry().object_info()["rseqc_inner_distance"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == ["inner_distance_plot", "inner_distances", "inner_distance_frequency", "r_script"]
    assert node_class.render_command(
        {
            "input": "paired.bam",
            "refgene": "genes.bed12",
            "sample_size": 500000,
            "lower_bound": -200,
            "upper_bound": 300,
            "step": 10,
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_inner_distance",
        }
    ) == [
        "inner_distance.py",
        "-i",
        "paired.bam",
        "-o",
        "/work/rseqc_inner_distance/output",
        "-r",
        "genes.bed12",
        "--sample-size",
        "500000",
        "--lower-bound",
        "-200",
        "--upper-bound",
        "300",
        "--step",
        "10",
        "--mapq",
        "25",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.pdf",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_freq.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.pdf",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_freq.txt",
    ]


def test_rseqc_insertion_profile_renders_inserted_base_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_insertion_profile")
    info = _registry().object_info()["rseqc_insertion_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["insertion_profile_plot", "insertion_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "layout": "PE",
            "rscript_output": True,
            "output": "/work/rseqc_insertion_profile",
        }
    ) == [
        "insertion_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_insertion_profile/output",
        "-q",
        "20",
        "-s",
        "PE",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.pdf",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.xls",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.pdf",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.xls",
    ]


def test_rseqc_read_hexamer_renders_multi_input_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_hexamer")
    info = _registry().object_info()["rseqc_read_hexamer"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["hexamer_frequencies"]
    assert node_class.render_command(
        {
            "inputs": ["reads/R1.fastq.gz", "reads/R1.fastq.gz", "transcripts.fa"],
            "refgenome": "genome.fa",
            "refgene": "mrna.fa",
            "output": "/work/rseqc_read_hexamer",
        }
    ) == (
        "gunzip -c reads/R1.fastq.gz > R1_fastq_gz && "
        "gunzip -c reads/R1.fastq.gz > R1_fastq_gz.1 && "
        "ln -sf transcripts.fa transcripts_fa && "
        "read_hexamer.py -i R1_fastq_gz,R1_fastq_gz.1,transcripts_fa "
        "-r genome.fa -g mrna.fa > /work/rseqc_read_hexamer/read_hexamer.tsv"
    )
    assert node_class.render_command(
        {
            "inputs": ["reads R2.fastq", "amplicons.fasta"],
            "output": "/work/rseqc_read_hexamer",
        }
    ) == (
        "ln -sf 'reads R2.fastq' reads_R2_fastq && "
        "ln -sf amplicons.fasta amplicons_fasta && "
        "read_hexamer.py -i reads_R2_fastq,amplicons_fasta > /work/rseqc_read_hexamer/read_hexamer.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_read_hexamer" / "read_hexamer.tsv",
    ]


def test_rseqc_read_quality_renders_phred_quality_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_quality")
    info = _registry().object_info()["rseqc_read_quality"]

    assert info["output"] == ["IMAGE", "IMAGE", "TEXT"]
    assert info["output_name"] == ["quality_heatmap", "quality_boxplot", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "reduce": 500,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_read_quality",
        }
    ) == [
        "read_quality.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_quality/output",
        "-r",
        "500",
        "--mapq",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_quality" / "output.qual.heatmap.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.boxplot.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_quality" / "output.qual.heatmap.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.boxplot.pdf",
    ]


def test_rseqc_rna_fragment_size_renders_fragment_size_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_rna_fragment_size")
    info = _registry().object_info()["rseqc_rna_fragment_size"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["fragment_sizes"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "mapq": 20,
            "frag_num": 5,
            "output": "/work/rseqc_rna_fragment_size",
        }
    ) == [
        "RNA_fragment_size.py",
        "-i",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--mapq",
        "20",
        "--frag-num",
        "5",
        ">",
        "/work/rseqc_rna_fragment_size/fragment_sizes.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_rna_fragment_size" / "fragment_sizes.tsv",
    ]


def test_rseqc_junction_annotation_renders_splice_junction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_junction_annotation")
    info = _registry().object_info()["rseqc_junction_annotation"]

    assert info["output"] == ["IMAGE", "IMAGE", "TSV", "TEXT", "STATS_FILE"]
    assert info["output_name"] == [
        "splice_events_plot",
        "splice_junction_plot",
        "junctions",
        "r_script",
        "stats",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_junction_annotation",
        }
    ) == [
        "junction_annotation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_annotation/output",
        "--min-intron",
        "75",
        "--mapq",
        "20",
        "2>",
        "/work/rseqc_junction_annotation/stats.txt",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_junction_annotation" / "output.splice_events.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.splice_junction.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.junction.xls",
        tmp_path / "rseqc_junction_annotation" / "output.junction_plot.r",
        tmp_path / "rseqc_junction_annotation" / "stats.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_junction_annotation" / "output.splice_events.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.splice_junction.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.junction.xls",
        tmp_path / "rseqc_junction_annotation" / "stats.txt",
    ]


def test_rseqc_junction_saturation_renders_saturation_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_junction_saturation")
    info = _registry().object_info()["rseqc_junction_saturation"]

    assert info["output"] == ["IMAGE", "TEXT"]
    assert info["output_name"] == ["junction_saturation_plot", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "min_coverage": 2,
            "mapq": 20,
            "output": "/work/rseqc_junction_saturation",
        }
    ) == [
        "junction_saturation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_saturation/output",
        "--min-intron",
        "75",
        "--min-coverage",
        "2",
        "--mapq",
        "20",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "min_coverage": 2,
            "mapq": 20,
            "percentiles_mode": "specify",
            "percentile_floor": 10,
            "percentile_ceiling": 90,
            "percentile_step": 10,
            "output": "/work/rseqc_junction_saturation",
        }
    ) == [
        "junction_saturation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_saturation/output",
        "--min-intron",
        "75",
        "--min-coverage",
        "2",
        "--mapq",
        "20",
        "--percentile-floor",
        "10",
        "--percentile-ceiling",
        "90",
        "--percentile-step",
        "10",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.pdf",
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.pdf",
    ]


def test_rseqc_mismatch_profile_renders_mismatch_profile_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_mismatch_profile")
    info = _registry().object_info()["rseqc_mismatch_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["mismatch_profile_plot", "mismatch_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "read_align_length": 101,
            "read_num": 500000,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_mismatch_profile",
        }
    ) == [
        "mismatch_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_mismatch_profile/output",
        "-l",
        "101",
        "-n",
        "500000",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.pdf",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.xls",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.pdf",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.xls",
    ]


def test_rseqc_read_gc_renders_gc_content_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_gc")
    info = _registry().object_info()["rseqc_read_gc"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["gc_plot", "gc_counts", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.sam",
            "mapq": 15,
            "rscript_output": True,
            "output": "/work/rseqc_read_gc",
        }
    ) == [
        "read_GC.py",
        "--input-file",
        "aligned.sam",
        "--out-prefix",
        "/work/rseqc_read_gc/output",
        "--mapq",
        "15",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_gc" / "output.GC_plot.pdf",
        tmp_path / "rseqc_read_gc" / "output.GC.xls",
        tmp_path / "rseqc_read_gc" / "output.GC_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_gc" / "output.GC_plot.pdf",
        tmp_path / "rseqc_read_gc" / "output.GC.xls",
    ]


def test_rseqc_read_nvc_renders_nucleotide_cycle_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_nvc")
    info = _registry().object_info()["rseqc_read_nvc"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["nvc_plot", "nvc_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "nx": False,
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_read_nvc",
        }
    ) == [
        "read_NVC.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_nvc/output",
        "--mapq",
        "25",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "nx": True,
            "mapq": 25,
            "output": "/work/rseqc_read_nvc",
        }
    ) == [
        "read_NVC.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_nvc/output",
        "--nx",
        "--mapq",
        "25",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.pdf",
        tmp_path / "rseqc_read_nvc" / "output.NVC.xls",
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.pdf",
        tmp_path / "rseqc_read_nvc" / "output.NVC.xls",
    ]


def test_rseqc_bam_stat_renders_mapping_stats_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_bam_stat")
    info = _registry().object_info()["rseqc_bam_stat"]

    assert info["output"] == ["STATS_FILE"]
    assert info["output_name"] == ["mapping_stats"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "output": "/work/rseqc_bam_stat",
        }
    ) == [
        "bam_stat.py",
        "-i",
        "aligned.bam",
        "-q",
        "20",
        ">",
        "/work/rseqc_bam_stat/bam_stat.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_bam_stat" / "bam_stat.txt",
    ]


def test_rseqc_read_distribution_renders_feature_distribution_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_distribution")
    info = _registry().object_info()["rseqc_read_distribution"]

    assert info["output"] == ["STATS_FILE"]
    assert info["output_name"] == ["read_distribution"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "output": "/work/rseqc_read_distribution",
        }
    ) == [
        "read_distribution.py",
        "-i",
        "aligned.bam",
        "-r",
        "genes.bed12",
        ">",
        "/work/rseqc_read_distribution/read_distribution.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_read_distribution" / "read_distribution.txt",
    ]


def test_rseqc_read_duplication_renders_duplication_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_duplication")
    info = _registry().object_info()["rseqc_read_duplication"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == [
        "duplication_plot",
        "position_duplication",
        "sequence_duplication",
        "r_script",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "up_limit": 750,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_read_duplication",
        }
    ) == [
        "read_duplication.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_read_duplication/output",
        "-u",
        "750",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.pdf",
        tmp_path / "rseqc_read_duplication" / "output.pos.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.seq.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.pdf",
        tmp_path / "rseqc_read_duplication" / "output.pos.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.seq.DupRate.xls",
    ]


def test_rseqc_tin_renders_transcript_integrity_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_tin")
    info = _registry().object_info()["rseqc_tin"]

    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["tin_summary", "tin_table"]
    assert info["citation_dois"] == ["10.1186/s12859-016-0922-z", "10.1093/bioinformatics/bts356"]
    assert node_class.render_command(
        {
            "input": ["sample one.bam", "sample one.bam", "batch/sample-two.bam"],
            "refgene": "genes.bed12",
            "minCov": 12,
            "samplesize": 80,
            "subtractbackground": True,
            "output": "/work/rseqc_tin",
        }
    ) == (
        "mkdir -p /work/rseqc_tin/input_bams && "
        "ln -sf 'sample one.bam' /work/rseqc_tin/input_bams/sample_one.bam && "
        "ln -sf 'sample one.bam' /work/rseqc_tin/input_bams/sample_one.2.bam && "
        "ln -sf batch/sample-two.bam /work/rseqc_tin/input_bams/sample-two.bam && "
        "printf '%s\\n' /work/rseqc_tin/input_bams/sample_one.bam "
        "/work/rseqc_tin/input_bams/sample_one.2.bam /work/rseqc_tin/input_bams/sample-two.bam "
        "> /work/rseqc_tin/input_list.txt && "
        "tin.py -i /work/rseqc_tin/input_list.txt --refgene genes.bed12 --minCov 12 --sample-size 80 "
        "--subtract-background && mv *summary.txt /work/rseqc_tin/summary.tab && mv *tin.xls /work/rseqc_tin/tin.xls"
    )
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "output": "/work/rseqc_tin",
        }
    ) == (
        "mkdir -p /work/rseqc_tin/input_bams && "
        "ln -sf aligned.bam /work/rseqc_tin/input_bams/aligned.bam && "
        "printf '%s\\n' /work/rseqc_tin/input_bams/aligned.bam > /work/rseqc_tin/input_list.txt && "
        "tin.py -i /work/rseqc_tin/input_list.txt --refgene genes.bed12 --minCov 10 --sample-size 100 && "
        "mv *summary.txt /work/rseqc_tin/summary.tab && mv *tin.xls /work/rseqc_tin/tin.xls"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_tin" / "summary.tab",
        tmp_path / "rseqc_tin" / "tin.xls",
    ]


def test_bedtools_coveragebed_renders_depth_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_coveragebed")

    assert node_class.render_command(
        {
            "inputA": "windows.bed",
            "inputB": ["reads.bam", "capture.bed"],
            "split": True,
            "strandedness": True,
            "d": True,
            "mean": True,
            "overlap_a": 0.5,
            "overlap_b": 0.2,
            "reciprocal_overlap": True,
            "a_or_b": True,
            "sorted": True,
            "output": "/work/bedtools_coveragebed",
        }
    ) == [
        "bedtools",
        "coverage",
        "-d",
        "-split",
        "-s",
        "-mean",
        "-f",
        "0.5",
        "-F",
        "0.2",
        "-r",
        "-e",
        "-a",
        "windows.bed",
        "-b",
        "reads.bam",
        "capture.bed",
        "-sorted",
        "|",
        "sort",
        "-k1,1",
        "-k2,2n",
        ">",
        "/work/bedtools_coveragebed/coverage.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_coveragebed" / "coverage.bed",
    ]


def test_bedtools_genomecoveragebed_renders_bam_bedgraph_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_genomecoveragebed")

    assert node_class.render_command(
        {
            "input_type": "bam",
            "input": "reads.bam",
            "report": "bg",
            "zero_regions": True,
            "scale": 0.5,
            "split": True,
            "strand": "+",
            "d": True,
            "five": True,
            "output": "/work/bedtools_genomecoveragebed",
        }
    ) == [
        "bedtools",
        "genomecov",
        "-ibam",
        "reads.bam",
        "-split",
        "-strand",
        "+",
        "-bga",
        "-scale",
        "0.5",
        "-d",
        "-5",
        ">",
        "/work/bedtools_genomecoveragebed/genome_coverage.bedgraph",
    ]

    assert node_class.PLAN_OUTPUTS({"report": "bg"}, tmp_path) == [
        tmp_path / "bedtools_genomecoveragebed" / "genome_coverage.bedgraph",
    ]
    assert node_class.PLAN_OUTPUTS({"report": "hist"}, tmp_path) == [
        tmp_path / "bedtools_genomecoveragebed" / "genome_coverage.tsv",
    ]


def test_galaxy_parity_bedtools_followup_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_subtractbed": {
            "display_name": "BEDTools Subtract",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_mergebed": {
            "display_name": "BEDTools Merge",
            "category": "genomics",
            "required_executables": ["mergeBed"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_sortbed": {
            "display_name": "BEDTools Sort",
            "category": "genomics",
            "required_executables": ["sortBed"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_getfastabed": {
            "display_name": "BEDTools getfasta",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith(("https://", "http://"))
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_subtractbed_renders_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_subtractbed")

    assert node_class.render_command(
        {
            "inputA": "targets.bed",
            "inputB": "blacklist.bed",
            "strand": "opposite",
            "overlap": 0.8,
            "remove_if_overlap": "remove_feature",
            "output": "/work/bedtools_subtractbed",
        }
    ) == [
        "bedtools",
        "subtract",
        "-S",
        "-a",
        "targets.bed",
        "-b",
        "blacklist.bed",
        "-f",
        "0.8",
        "-A",
        ">",
        "/work/bedtools_subtractbed/subtracted.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_subtractbed" / "subtracted.bed",
    ]


def test_bedtools_mergebed_renders_column_operations_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_mergebed")

    assert node_class.render_command(
        {
            "input": "sorted_regions.bed",
            "strand": "forward",
            "distance": 1000,
            "header": True,
            "columns": "4,5",
            "operations": "collapse,mean",
            "output": "/work/bedtools_mergebed",
        }
    ) == [
        "mergeBed",
        "-i",
        "sorted_regions.bed",
        "-S",
        "+",
        "-d",
        "1000",
        "-header",
        "-c",
        "4,5",
        "-o",
        "collapse,mean",
        ">",
        "/work/bedtools_mergebed/merged.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_mergebed" / "merged.bed",
    ]


def test_bedtools_sortbed_renders_genome_order_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_sortbed")

    assert node_class.render_command(
        {
            "input": "regions.gff",
            "sort_by": "-chrThenScoreD",
            "genome": "chrom.sizes",
            "output": "/work/bedtools_sortbed",
        }
    ) == [
        "sortBed",
        "-i",
        "regions.gff",
        "-chrThenScoreD",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_sortbed/sorted.gff",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "regions.gff"}, tmp_path) == [
        tmp_path / "bedtools_sortbed" / "sorted.gff",
    ]


def test_bedtools_getfastabed_renders_sequence_extraction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_getfastabed")

    assert node_class.render_command(
        {
            "input": "exons.bed12",
            "fasta": "genome.fa",
            "name_only": True,
            "tab": True,
            "strand": True,
            "split": True,
            "output": "/work/bedtools_getfastabed",
        }
    ) == [
        "ln",
        "-s",
        "genome.fa",
        "input.fasta",
        "&&",
        "bedtools",
        "getfasta",
        "-nameOnly",
        "-tab",
        "-s",
        "-split",
        "-fi",
        "input.fasta",
        "-bed",
        "exons.bed12",
        "-fo",
        "/work/bedtools_getfastabed/extracted.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({"tab": True}, tmp_path) == [
        tmp_path / "bedtools_getfastabed" / "extracted.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"tab": False}, tmp_path) == [
        tmp_path / "bedtools_getfastabed" / "extracted.fasta",
    ]


def test_galaxy_parity_bedtools_interval_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_complementbed": {
            "display_name": "BEDTools Complement",
            "required_executables": ["complementBed"],
        },
        "bedtools_flankbed": {
            "display_name": "BEDTools Flank",
            "required_executables": ["flankBed"],
        },
        "bedtools_slopbed": {
            "display_name": "BEDTools Slop",
            "required_executables": ["bedtools"],
        },
        "bedtools_windowbed": {
            "display_name": "BEDTools Window",
            "required_executables": ["bedtools"],
        },
        "bedtools_map": {
            "display_name": "BEDTools Map",
            "required_executables": ["bedtools"],
        },
        "bedtools_multiintersectbed": {
            "display_name": "BEDTools Multiple Intersect",
            "required_executables": ["bedtools"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith("https://bedtools.readthedocs.io/")
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_complementbed_renders_genome_gap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_complementbed")

    assert node_class.render_command(
        {
            "input": "covered.bed",
            "genome": "chrom.sizes",
            "output": "/work/bedtools_complementbed",
        }
    ) == [
        "complementBed",
        "-i",
        "covered.bed",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_complementbed/complement.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_complementbed" / "complement.bed",
    ]


def test_bedtools_flankbed_renders_fractional_stranded_flank_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_flankbed")

    assert node_class.render_command(
        {
            "input": "genes.bed",
            "genome": "chrom.sizes",
            "pct": True,
            "strand": True,
            "addition_mode": "lr",
            "left": 0.2,
            "right": 0.5,
            "output": "/work/bedtools_flankbed",
        }
    ) == [
        "flankBed",
        "-pct",
        "-s",
        "-g",
        "chrom.sizes",
        "-i",
        "genes.bed",
        "-l",
        "0.2",
        "-r",
        "0.5",
        ">",
        "/work/bedtools_flankbed/flanks.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_flankbed" / "flanks.bed",
    ]


def test_bedtools_slopbed_renders_symmetric_extension_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_slopbed")

    assert node_class.render_command(
        {
            "inputA": "peaks.bed",
            "genome": "chrom.sizes",
            "addition_mode": "b",
            "both": 250,
            "header": True,
            "output": "/work/bedtools_slopbed",
        }
    ) == [
        "bedtools",
        "slop",
        "-g",
        "chrom.sizes",
        "-i",
        "peaks.bed",
        "-b",
        "250",
        "-header",
        ">",
        "/work/bedtools_slopbed/slopped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_slopbed" / "slopped.bed",
    ]


def test_bedtools_windowbed_renders_asymmetric_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_windowbed")

    assert node_class.render_command(
        {
            "inputA": "promoters.bed",
            "inputB": "enhancers.bed",
            "addition_mode": "lr",
            "left": 200,
            "right": 20000,
            "strand": "same",
            "number": True,
            "header": True,
            "output": "/work/bedtools_windowbed",
        }
    ) == [
        "bedtools",
        "window",
        "-a",
        "promoters.bed",
        "-b",
        "enhancers.bed",
        "-sm",
        "-l",
        "200",
        "-r",
        "20000",
        "-c",
        "-header",
        ">",
        "/work/bedtools_windowbed/window.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_windowbed" / "window.bed",
    ]


def test_bedtools_map_renders_column_operation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_map")

    assert node_class.render_command(
        {
            "inputA": "exons.bed",
            "inputB": "coverage.bedgraph",
            "columns": "4",
            "operations": "mean",
            "strand": "opposite",
            "overlap": 0.5,
            "overlap_b": 0.25,
            "reciprocal": True,
            "split": True,
            "header": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_map",
        }
    ) == [
        "bedtools",
        "map",
        "-a",
        "exons.bed",
        "-b",
        "coverage.bedgraph",
        "-S",
        "-c",
        "4",
        "-o",
        "mean",
        "-f",
        "0.5",
        "-F",
        "0.25",
        "-r",
        "-split",
        "-header",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_map/mapped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_map" / "mapped.bed",
    ]


def test_bedtools_multiintersectbed_renders_custom_names_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_multiintersectbed")

    assert node_class.render_command(
        {
            "inputs": ["a.bed", "b.bed", "c.bed"],
            "names": ["sampleA", "sampleB", "sampleC"],
            "header": True,
            "cluster": True,
            "filler": "0",
            "empty": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_multiintersectbed",
        }
    ) == [
        "bedtools",
        "multiinter",
        "-header",
        "-cluster",
        "-filler",
        "0",
        "-empty",
        "-g",
        "chrom.sizes",
        "-i",
        "a.bed",
        "b.bed",
        "c.bed",
        "-names",
        "sampleA",
        "sampleB",
        "sampleC",
        ">",
        "/work/bedtools_multiintersectbed/multiintersect.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_multiintersectbed" / "multiintersect.bed",
    ]


def test_galaxy_parity_bedtools_statistics_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_clusterbed": {
            "display_name": "BEDTools Cluster",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_jaccard": {
            "display_name": "BEDTools Jaccard",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_fisher": {
            "display_name": "BEDTools Fisher",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_reldistbed": {
            "display_name": "BEDTools Relative Distance",
            "required_executables": ["bedtools"],
            "doi": "10.1371/journal.pcbi.1002529",
        },
        "bedtools_spacingbed": {
            "display_name": "BEDTools Spacing",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_groupbybed": {
            "display_name": "BEDTools GroupBy",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith("https://bedtools.readthedocs.io/")
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_clusterbed_renders_stranded_cluster_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_clusterbed")

    assert node_class.render_command(
        {
            "inputA": "sorted.bed",
            "strand": True,
            "distance": 500,
            "output": "/work/bedtools_clusterbed",
        }
    ) == [
        "bedtools",
        "cluster",
        "-s",
        "-d",
        "500",
        "-i",
        "sorted.bed",
        ">",
        "/work/bedtools_clusterbed/clustered.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_clusterbed" / "clustered.bed",
    ]


def test_bedtools_jaccard_renders_overlap_statistic_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_jaccard")

    assert node_class.render_command(
        {
            "inputA": "a.bed",
            "inputB": "b.bed",
            "strand": True,
            "split": True,
            "reciprocal": True,
            "overlap": 0.2,
            "overlap_b": 0.3,
            "output": "/work/bedtools_jaccard",
        }
    ) == [
        "bedtools",
        "jaccard",
        "-s",
        "-split",
        "-r",
        "-f",
        "0.2",
        "-F",
        "0.3",
        "-a",
        "a.bed",
        "-b",
        "b.bed",
        ">",
        "/work/bedtools_jaccard/jaccard.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_jaccard" / "jaccard.tsv",
    ]


def test_bedtools_fisher_renders_exact_test_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_fisher")

    assert node_class.render_command(
        {
            "inputA": "case.bed",
            "inputB": "background.bed",
            "genome": "chrom.sizes",
            "strand": "same",
            "split": True,
            "overlap": 0.5,
            "reciprocal": True,
            "merge": True,
            "output": "/work/bedtools_fisher",
        }
    ) == [
        "bedtools",
        "fisher",
        "-s",
        "-split",
        "-a",
        "case.bed",
        "-b",
        "background.bed",
        "-f",
        "0.5",
        "-g",
        "chrom.sizes",
        "-r",
        "-m",
        ">",
        "/work/bedtools_fisher/fisher.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_fisher" / "fisher.txt",
    ]


def test_bedtools_reldistbed_renders_relative_distance_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_reldistbed")

    assert node_class.render_command(
        {
            "inputA": "enhancers.bed",
            "inputB": "tss.bed",
            "detail": True,
            "output": "/work/bedtools_reldistbed",
        }
    ) == [
        "bedtools",
        "reldist",
        "-a",
        "enhancers.bed",
        "-b",
        "tss.bed",
        "-detail",
        ">",
        "/work/bedtools_reldistbed/relative_distance.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_reldistbed" / "relative_distance.tsv",
    ]


def test_bedtools_spacingbed_renders_spacing_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_spacingbed")

    assert node_class.render_command(
        {
            "input": "sorted.bed",
            "output": "/work/bedtools_spacingbed",
        }
    ) == [
        "bedtools",
        "spacing",
        "-i",
        "sorted.bed",
        ">",
        "/work/bedtools_spacingbed/spacing.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_spacingbed" / "spacing.bed",
    ]


def test_bedtools_groupbybed_renders_summary_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_groupbybed")

    assert node_class.render_command(
        {
            "inputA": "annotated.bed",
            "group": "1,2,3",
            "columns": "9",
            "operation": "median",
            "output": "/work/bedtools_groupbybed",
        }
    ) == [
        "bedtools",
        "groupby",
        "-i",
        "annotated.bed",
        "-g",
        "1,2,3",
        "-c",
        "9",
        "-o",
        "median",
        ">",
        "/work/bedtools_groupbybed/grouped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_groupbybed" / "grouped.bed",
    ]


def test_galaxy_parity_bedtools_conversion_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_bamtobed": {
            "display_name": "BEDTools BAM to BED",
            "required_executables": ["bedtools", "samtools"],
            "required_conda_packages": ["bedtools", "samtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bamtobed.html",
        },
        "bedtools_bed12tobed6": {
            "display_name": "BEDTools BED12 to BED6",
            "required_executables": ["bed12ToBed6"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bed12tobed6.html",
        },
        "bedtools_bedtobam": {
            "display_name": "BEDTools BED to BAM",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bedtobam.html",
        },
        "bedtools_bedpetobam": {
            "display_name": "BEDTools BEDPE to BAM",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bedpetobam.html",
        },
        "bedtools_makewindowsbed": {
            "display_name": "BEDTools Make Windows",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/makewindows.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_bamtobed_renders_bedpe_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bamtobed")

    assert node_class.render_command(
        {
            "input": "alignments.bam",
            "option": "bedpe",
            "split": True,
            "ed_score": True,
            "tag": "NM",
            "threads": 6,
            "output": "/work/bedtools_bamtobed",
        }
    ) == [
        "samtools",
        "sort",
        "-n",
        "-@",
        "6",
        "-T",
        "/work/bedtools_bamtobed/tmp",
        "alignments.bam",
        ">",
        "/work/bedtools_bamtobed/input.bam",
        "&&",
        "bedtools",
        "bamtobed",
        "-bedpe",
        "-ed",
        "-split",
        "-tag",
        "NM",
        "-i",
        "/work/bedtools_bamtobed/input.bam",
        ">",
        "/work/bedtools_bamtobed/converted.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bamtobed" / "converted.bed",
    ]


def test_bedtools_bed12tobed6_renders_block_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bed12tobed6")

    assert node_class.render_command(
        {
            "input": "transcripts.bed12",
            "output": "/work/bedtools_bed12tobed6",
        }
    ) == [
        "bed12ToBed6",
        "-i",
        "transcripts.bed12",
        ">",
        "/work/bedtools_bed12tobed6/bed6.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bed12tobed6" / "bed6.bed",
    ]


def test_bedtools_bedtobam_renders_bed12_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedtobam")

    assert node_class.render_command(
        {
            "input": "features.bed",
            "bed12": True,
            "genome": "chrom.sizes",
            "mapq": 42,
            "output": "/work/bedtools_bedtobam",
        }
    ) == [
        "bedtools",
        "bedtobam",
        "-bed12",
        "-mapq",
        "42",
        "-g",
        "chrom.sizes",
        "-i",
        "features.bed",
        ">",
        "/work/bedtools_bedtobam/converted.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedtobam" / "converted.bam",
    ]


def test_bedtools_bedpetobam_renders_paired_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedpetobam")

    assert node_class.render_command(
        {
            "input": "pairs.bedpe",
            "genome": "chrom.sizes",
            "mapq": 60,
            "output": "/work/bedtools_bedpetobam",
        }
    ) == [
        "bedtools",
        "bedpetobam",
        "-mapq",
        "60",
        "-i",
        "pairs.bedpe",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_bedpetobam/paired.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedpetobam" / "paired.bam",
    ]


def test_bedtools_makewindowsbed_renders_sliding_windows_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_makewindowsbed")

    assert node_class.render_command(
        {
            "type": "bed",
            "input": "regions.bed",
            "action": "windowsize",
            "windowsize": 1000,
            "step_size": 250,
            "sourcename": "srcwinnum",
            "output": "/work/bedtools_makewindowsbed",
        }
    ) == [
        "bedtools",
        "makewindows",
        "-b",
        "regions.bed",
        "-w",
        "1000",
        "-s",
        "250",
        "-i",
        "srcwinnum",
        ">",
        "/work/bedtools_makewindowsbed/windows.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_makewindowsbed" / "windows.bed",
    ]


def test_galaxy_parity_bedtools_annotation_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_annotatebed": {
            "display_name": "BEDTools Annotate",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/annotate.html",
        },
        "bedtools_expandbed": {
            "display_name": "BEDTools Expand",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/expand.html",
        },
        "bedtools_maskfastabed": {
            "display_name": "BEDTools Mask FASTA",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html",
        },
        "bedtools_multicovtbed": {
            "display_name": "BEDTools MultiCov",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/multicov.html",
        },
        "bedtools_nucbed": {
            "display_name": "BEDTools Nucleotide Content",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/nuc.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_annotatebed_renders_named_coverage_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_annotatebed")

    assert node_class.render_command(
        {
            "inputA": "regions.bed",
            "beds": ["enhancers.bed", "promoters.bed"],
            "names": ["enhancer", "promoter"],
            "strand": "same",
            "counts": True,
            "both": True,
            "output": "/work/bedtools_annotatebed",
        }
    ) == [
        "bedtools",
        "annotate",
        "-i",
        "regions.bed",
        "-files",
        "enhancers.bed",
        "promoters.bed",
        "-names",
        "enhancer",
        "promoter",
        "-s",
        "-counts",
        "-both",
        ">",
        "/work/bedtools_annotatebed/annotated.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_annotatebed" / "annotated.bed",
    ]


def test_bedtools_expandbed_renders_column_expansion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_expandbed")

    assert node_class.render_command(
        {
            "input": "tagged.bed",
            "columns": "4,5",
            "output": "/work/bedtools_expandbed",
        }
    ) == [
        "bedtools",
        "expand",
        "-c",
        "4,5",
        "-i",
        "tagged.bed",
        ">",
        "/work/bedtools_expandbed/expanded.bed",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "tagged.gff3"}, tmp_path) == [
        tmp_path / "bedtools_expandbed" / "expanded.gff",
    ]


def test_bedtools_maskfastabed_renders_soft_mask_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_maskfastabed")

    assert node_class.render_command(
        {
            "input": "mask_regions.bed",
            "fasta": "genome.fa",
            "soft": True,
            "mask_character": "X",
            "full_header": True,
            "output": "/work/bedtools_maskfastabed",
        }
    ) == [
        "bedtools",
        "maskfasta",
        "-soft",
        "-mc",
        "X",
        "-fi",
        "genome.fa",
        "-bed",
        "mask_regions.bed",
        "-fo",
        "/work/bedtools_maskfastabed/masked.fasta",
        "-fullHeader",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_maskfastabed" / "masked.fasta",
    ]


def test_bedtools_multicovtbed_renders_bam_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_multicovtbed")

    assert node_class.render_command(
        {
            "input": "targets.bed",
            "bams": ["case.bam", "control.bam"],
            "strand": "opposite",
            "overlap": 0.5,
            "reciprocal": True,
            "split": True,
            "q": 20,
            "duplicate": True,
            "failed": True,
            "proper": True,
            "output": "/work/bedtools_multicovtbed",
        }
    ) == [
        "bedtools",
        "multicov",
        "-bed",
        "targets.bed",
        "-bams",
        "case.bam",
        "control.bam",
        "-S",
        "-f",
        "0.5",
        "-r",
        "-split",
        "-q",
        "20",
        "-D",
        "-F",
        "-p",
        ">",
        "/work/bedtools_multicovtbed/multicov.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_multicovtbed" / "multicov.bed",
    ]


def test_bedtools_nucbed_renders_sequence_pattern_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_nucbed")

    assert node_class.render_command(
        {
            "input": "regions.bed",
            "fasta": "genome.fa",
            "strand": True,
            "seq": True,
            "pattern": "TAC",
            "ignore_case": True,
            "output": "/work/bedtools_nucbed",
        }
    ) == [
        "bedtools",
        "nuc",
        "-s",
        "-seq",
        "-pattern",
        "TAC",
        "-C",
        "-fi",
        "genome.fa",
        "-bed",
        "regions.bed",
        ">",
        "/work/bedtools_nucbed/nucleotide_content.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_nucbed" / "nucleotide_content.tsv",
    ]


def test_galaxy_parity_bedtools_randomization_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_randombed": {
            "display_name": "BEDTools Random",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/random.html",
        },
        "bedtools_shufflebed": {
            "display_name": "BEDTools Shuffle",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/shuffle.html",
        },
        "bedtools_unionbedgraph": {
            "display_name": "BEDTools Union BedGraph",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/unionbedg.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == ["bedtools"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_randombed_renders_seeded_interval_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_randombed")

    assert node_class.render_command(
        {
            "genome": "chrom.sizes",
            "length": 250,
            "intervals": 1000,
            "seed": 17,
            "output": "/work/bedtools_randombed",
        }
    ) == [
        "bedtools",
        "random",
        "-g",
        "chrom.sizes",
        "-l",
        "250",
        "-n",
        "1000",
        "-seed",
        "17",
        ">",
        "/work/bedtools_randombed/random.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_randombed" / "random.bed",
    ]


def test_bedtools_shufflebed_renders_excluded_same_chromosome_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_shufflebed")

    assert node_class.render_command(
        {
            "inputA": "peaks.bed",
            "genome": "chrom.sizes",
            "bedpe": True,
            "seed": 23,
            "exclude": "gaps.bed",
            "overlap": 0.2,
            "chrom": True,
            "chromfirst": True,
            "no_overlap": True,
            "allow_beyond": True,
            "maxtries": 5000,
            "output": "/work/bedtools_shufflebed",
        }
    ) == [
        "bedtools",
        "shuffle",
        "-g",
        "chrom.sizes",
        "-i",
        "peaks.bed",
        "-bedpe",
        "-seed",
        "23",
        "-excl",
        "gaps.bed",
        "-f",
        "0.2",
        "-chrom",
        "-chromFirst",
        "-noOverlapping",
        "-allowBeyondChromEnd",
        "-maxTries",
        "5000",
        ">",
        "/work/bedtools_shufflebed/shuffled.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_shufflebed" / "shuffled.bed",
    ]


def test_bedtools_unionbedgraph_renders_named_empty_union_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_unionbedgraph")

    assert node_class.render_command(
        {
            "inputs": ["sample1.bg", "sample2.bg"],
            "names": ["case", "control"],
            "header": True,
            "filler": "0",
            "empty": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_unionbedgraph",
        }
    ) == [
        "bedtools",
        "unionbedg",
        "-header",
        "-filler",
        "0",
        "-empty",
        "-g",
        "chrom.sizes",
        "-i",
        "sample1.bg",
        "sample2.bg",
        "-names",
        "case",
        "control",
        ">",
        "/work/bedtools_unionbedgraph/union.bedgraph",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_unionbedgraph" / "union.bedgraph",
    ]


def test_galaxy_parity_bedtools_overlap_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_closestbed": {
            "display_name": "BEDTools ClosestBed",
            "required_executables": ["closestBed"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html",
        },
        "bedtools_intersectbed": {
            "display_name": "BEDTools Intersect Intervals",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools", "samtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_closestbed_renders_distance_mode_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_closestbed")

    assert node_class.render_command(
        {
            "inputA": "query.bed",
            "inputB": ["genes.bed", "enhancers.bed"],
            "strand": "opposite",
            "distance": True,
            "distance_mode": "a",
            "ignore_upstream": True,
            "first_upstream": True,
            "ignore_overlaps": True,
            "mdb": "all",
            "ties": "first",
            "k": 3,
            "output": "/work/bedtools_closestbed",
        }
    ) == [
        "closestBed",
        "-S",
        "-d",
        "-D",
        "a",
        "-iu",
        "-fu",
        "-io",
        "-mdb",
        "all",
        "-t",
        "first",
        "-k",
        "3",
        "-a",
        "query.bed",
        "-b",
        "genes.bed",
        "enhancers.bed",
        ">",
        "/work/bedtools_closestbed/closest.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_closestbed" / "closest.bed",
    ]


def test_bedtools_intersectbed_renders_reduced_named_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_intersectbed")

    assert node_class.render_command(
        {
            "inputA": "reads.bam",
            "inputB": ["promoters.bed", "enhancers.bed"],
            "names": ["promoters", "enhancers"],
            "overlap_mode": ["-wa", "-wb"],
            "split": True,
            "strand": "same",
            "overlap": 0.5,
            "overlap_b": 0.25,
            "either_fraction": True,
            "invert": True,
            "once": True,
            "header": True,
            "sorted": True,
            "genome": "chrom.sizes",
            "bed": True,
            "count": True,
            "output": "/work/bedtools_intersectbed",
        }
    ) == [
        "bedtools",
        "intersect",
        "-a",
        "reads.bam",
        "-b",
        "promoters.bed",
        "enhancers.bed",
        "-names",
        "promoters",
        "enhancers",
        "-split",
        "-s",
        "-f",
        "0.5",
        "-F",
        "0.25",
        "-e",
        "-v",
        "-u",
        "-header",
        "-wa",
        "-wb",
        "-sorted",
        "-g",
        "chrom.sizes",
        "-bed",
        "-c",
        ">",
        "/work/bedtools_intersectbed/intersect.bed",
    ]

    assert node_class.PLAN_OUTPUTS({"bed": True}, tmp_path) == [
        tmp_path / "bedtools_intersectbed" / "intersect.bed",
    ]


def test_galaxy_parity_bedtools_legacy_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_bedtoigv": {
            "display_name": "BEDTools BED to IGV",
            "documentation_url": "https://github.com/galaxyproject/tools-iuc/blob/main/tools/bedtools/bedToIgv.xml",
            "output": ["TEXT"],
            "required_executables": ["bedToIgv"],
            "search_alias": "bedtoigv",
        },
        "bedtools_links": {
            "display_name": "BEDTools LinksBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/links.html",
            "output": ["HTML"],
            "required_executables": ["bedtools"],
            "search_alias": "linksbed ucsc",
        },
        "bedtools_overlapbed": {
            "display_name": "BEDTools OverlapBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/overlap.html",
            "output": ["BED"],
            "required_executables": ["bedtools"],
            "search_alias": "overlapbed custom score",
        },
        "bedtools_tagbed": {
            "display_name": "BEDTools TagBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/tag.html",
            "output": ["BAM"],
            "required_executables": ["bedtools"],
            "search_alias": "tagbed bam tags",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bedtools_bedtoigv_renders_snapshot_batch_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedtoigv")

    assert node_class.render_command(
        {
            "input": "targets.bed",
            "sort": "base",
            "clps": True,
            "name": True,
            "slop": 250,
            "img": "svg",
            "output": "/work/bedtools_bedtoigv",
        }
    ) == [
        "bedToIgv",
        "-i",
        "targets.bed",
        "-sort",
        "base",
        "-clps",
        "-name",
        "-slop",
        "250",
        "-img",
        "svg",
        ">",
        "/work/bedtools_bedtoigv/igv_batch_script.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedtoigv" / "igv_batch_script.txt",
    ]


def test_bedtools_links_renders_browser_links_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_links")

    assert node_class.render_command(
        {
            "input": "genes.bed",
            "basename": "http://mirror.example.edu",
            "org": "mouse",
            "db": "mm10",
            "output": "/work/bedtools_links",
        }
    ) == [
        "bedtools",
        "links",
        "-base",
        "http://mirror.example.edu",
        "-org",
        "mouse",
        "-db",
        "mm10",
        "-i",
        "genes.bed",
        ">",
        "/work/bedtools_links/links.html",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_links" / "links.html",
    ]


def test_bedtools_overlapbed_renders_column_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_overlapbed")

    assert node_class.render_command(
        {
            "input": "windowed.bed",
            "cols": [2, 3, 6, 7],
            "output": "/work/bedtools_overlapbed",
        }
    ) == [
        "bedtools",
        "overlap",
        "-i",
        "windowed.bed",
        "-cols",
        "2,3,6,7",
        ">",
        "/work/bedtools_overlapbed/overlap.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_overlapbed" / "overlap.bed",
    ]


def test_bedtools_tagbed_renders_annotation_tag_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_tagbed")

    assert node_class.render_command(
        {
            "inputA": "alignments.bam",
            "inputB": ["genes.bed", "enhancers.gff"],
            "overlap": 0.75,
            "strand": "opposite",
            "tag": "ZG",
            "field": "-labels -intervals",
            "output": "/work/bedtools_tagbed",
        }
    ) == [
        "bedtools",
        "tag",
        "-i",
        "alignments.bam",
        "-files",
        "genes.bed",
        "enhancers.gff",
        "-f",
        "0.75",
        "-S",
        "-tag",
        "ZG",
        "-labels",
        "-intervals",
        ">",
        "/work/bedtools_tagbed/tagged.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_tagbed" / "tagged.bam",
    ]


def test_bedops_sort_bed_exposes_citation_and_dependency_metadata() -> None:
    node_info = _registry().object_info()["bedops_sort_bed"]

    assert node_info["display_name"] == "BEDOPS Sort BED"
    assert node_info["category"] == "genomics"
    assert node_info["description"].startswith("Sort one or more BED files")
    assert node_info["output"] == ["BED"]
    assert node_info["output_name"] == ["sorted_bed"]
    assert node_info["required_executables"] == ["sort-bed"]
    assert node_info["required_conda_packages"] == ["bedops"]
    assert node_info["documentation_url"] == "https://bedops.readthedocs.io/en/latest/content/reference/file-management/sorting/sort-bed.html"
    assert "10.1093/bioinformatics/bts277" in node_info["citation_dois"]
    assert "https://doi.org/10.1093/bioinformatics/bts277" in node_info["citation_urls"]
    assert "BEDOPS: high-performance genomic feature operations" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "sort-bed" in node_info["search_aliases"]


def test_bedops_sort_bed_renders_sort_unique_and_duplicate_commands(tmp_path: Path) -> None:
    node_class = _node_class("bedops_sort_bed")

    assert node_class.render_command(
        {
            "inputs": ["sample.bed"],
            "memory_mb": 2048,
            "tmpdir": "/scratch/job",
            "output": "/work/bedops_sort_bed",
        }
    ) == [
        "sort-bed",
        "--max-mem",
        "2048M",
        "--tmpdir",
        "/scratch/job",
        "sample.bed",
        ">",
        "/work/bedops_sort_bed/sorted.bed",
    ]

    assert node_class.render_command(
        {
            "inputs": ["a.bed", "b.bed"],
            "unique": True,
            "memory_mb": 1024,
            "output": "/work/bedops_sort_bed",
        }
    ) == [
        "sort-bed",
        "--max-mem",
        "1024M",
        "--tmpdir",
        ".",
        "--unique",
        "a.bed",
        "b.bed",
        ">",
        "/work/bedops_sort_bed/sorted.bed",
    ]

    assert node_class.render_command(
        {
            "inputs": ["a.bed", "b.bed"],
            "duplicates": True,
            "memory_mb": 512,
            "output": "/work/bedops_sort_bed",
        }
    ) == [
        "sort-bed",
        "--max-mem",
        "512M",
        "--tmpdir",
        ".",
        "--duplicates",
        "a.bed",
        "b.bed",
        ">",
        "/work/bedops_sort_bed/sorted.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "bedops_sort_bed" / "sorted.bed"]


def test_bedops_sort_bed_validates_inputs_and_filter_modes() -> None:
    node_class = _node_class("bedops_sort_bed")

    assert node_class.VALIDATE_INPUTS({"inputs": [], "memory_mb": 1024}) == "at least one BED input is required"
    assert (
        node_class.VALIDATE_INPUTS({"inputs": ["sample.bed"], "unique": True, "duplicates": True})
        == "unique and duplicates modes are mutually exclusive"
    )


def test_galaxy_parity_bcftools_utility_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_concat": {
            "display_name": "BCFtools Concat",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#concat",
            "output": ["VCF_GZ"],
            "search_alias": "concatenate vcf",
        },
        "bcftools_consensus": {
            "display_name": "BCFtools Consensus",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#consensus",
            "output": ["FASTA"],
            "search_alias": "consensus fasta",
        },
        "bcftools_query": {
            "display_name": "BCFtools Query",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#query",
            "output": ["TSV"],
            "search_alias": "extract fields",
        },
        "bcftools_query_list_samples": {
            "display_name": "BCFtools List Samples",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#query",
            "output": ["TSV"],
            "search_alias": "list samples",
        },
        "bcftools_reheader": {
            "display_name": "BCFtools Reheader",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#reheader",
            "output": ["VCF_GZ"],
            "search_alias": "rename samples",
        },
        "bcftools_view": {
            "display_name": "BCFtools View",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#view",
            "output": ["VCF_GZ"],
            "search_alias": "subset vcf",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/gigascience/giab008" in node_info["citation_urls"]
        assert "https://doi.org/10.1093/bioinformatics/btp352" in node_info["citation_urls"]
        assert "Galaxy" in node_info["search_aliases"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_concat_renders_ligate_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_concat")

    assert node_class.render_command(
        {
            "input_files": ["chr1.vcf.gz", "chr2.vcf.gz"],
            "allow_overlaps": True,
            "rm_dups": "all",
            "ligate": True,
            "ligate_mode": "--ligate-force",
            "compact_ps": True,
            "min_pq": 40,
            "regions": "chr1,chr2",
            "output_type": "z",
            "threads": 8,
            "output": "/work/bcftools_concat",
        }
    ) == [
        "bcftools",
        "concat",
        "--allow-overlaps",
        "--rm-dups",
        "all",
        "--ligate",
        "--ligate-force",
        "--compact-PS",
        "--min-PQ",
        "40",
        "--regions",
        "chr1,chr2",
        "--output-type",
        "z",
        "--threads",
        "8",
        "chr1.vcf.gz",
        "chr2.vcf.gz",
        ">",
        "/work/bcftools_concat/concat.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_concat" / "concat.vcf.gz",
    ]


def test_bcftools_consensus_renders_masked_haplotype_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_consensus")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "reference": "ref.fa",
            "mode": "haplotype",
            "haplotype": "1pIu",
            "sample": "tumor",
            "mask": ["lowcov.bed", "repeats.bed"],
            "mask_with": "N,lc",
            "absent": "N",
            "mark_del": "-",
            "mark_ins": "uc",
            "mark_snv": "lc",
            "include": "QUAL>20",
            "exclude": "FILTER='LowQual'",
            "chain": True,
            "output": "/work/bcftools_consensus",
        }
    ) == [
        "bcftools",
        "consensus",
        "--fasta-ref",
        "ref.fa",
        "-H",
        "1pIu",
        "--sample",
        "tumor",
        "--mask",
        "lowcov.bed",
        "--mask-with",
        "N",
        "--mask",
        "repeats.bed",
        "--mask-with",
        "lc",
        "--absent",
        "N",
        "--mark-del",
        "-",
        "--mark-ins",
        "uc",
        "--mark-snv",
        "lc",
        "--include",
        "QUAL>20",
        "--exclude",
        "FILTER='LowQual'",
        "--chain",
        "/work/bcftools_consensus/consensus.chain",
        "--output",
        "/work/bcftools_consensus/consensus.fa",
        "calls.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({"chain": True}, tmp_path) == [
        tmp_path / "bcftools_consensus" / "consensus.fa",
        tmp_path / "bcftools_consensus" / "consensus.chain",
    ]


def test_bcftools_query_renders_multifile_restricted_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_query")

    assert node_class.render_command(
        {
            "input_files": ["case.vcf.gz", "control.vcf.gz"],
            "format": "%CHROM\\t%POS\\t%REF\\t%ALT[\\t%SAMPLE=%GT]\\n",
            "allow_undef_tags": True,
            "print_header": True,
            "samples": "S1,S2",
            "regions": "chr1:1-1000",
            "targets": "targets.bed",
            "include": "QUAL>30",
            "exclude": "TYPE='indel'",
            "collapse": "snps",
            "output": "/work/bcftools_query",
        }
    ) == [
        "bcftools",
        "query",
        "--format",
        "%CHROM\\t%POS\\t%REF\\t%ALT[\\t%SAMPLE=%GT]\\n",
        "--allow-undef-tags",
        "--print-header",
        "--collapse",
        "snps",
        "--regions",
        "chr1:1-1000",
        "--samples",
        "S1,S2",
        "--targets",
        "targets.bed",
        "--include",
        "QUAL>30",
        "--exclude",
        "TYPE='indel'",
        "case.vcf.gz",
        "control.vcf.gz",
        ">",
        "/work/bcftools_query/query.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_query" / "query.tsv",
    ]


def test_bcftools_list_samples_renders_query_list_samples_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_query_list_samples")

    assert node_class.render_command(
        {
            "input_file": "cohort.bcf",
            "output": "/work/bcftools_query_list_samples",
        }
    ) == [
        "bcftools",
        "query",
        "--list-samples",
        "cohort.bcf",
        ">",
        "/work/bcftools_query_list_samples/samples.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_query_list_samples" / "samples.tsv",
    ]


def test_bcftools_reheader_renders_header_and_sample_rename_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_reheader")

    assert node_class.render_command(
        {
            "input_file": "old.vcf.gz",
            "header": "new_header.vcf",
            "sample_file": "samples.tsv",
            "output_type": "z",
            "output": "/work/bcftools_reheader",
        }
    ) == [
        "bcftools",
        "reheader",
        "--header",
        "new_header.vcf",
        "--samples",
        "samples.tsv",
        "old.vcf.gz",
        "|",
        "bcftools",
        "view",
        "--output-type",
        "z",
        ">",
        "/work/bcftools_reheader/reheadered.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_reheader" / "reheadered.vcf.gz",
    ]


def test_bcftools_view_renders_subset_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_view")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "samples": "S1,S2",
            "force_samples": True,
            "trim_alt_alleles": True,
            "no_update": True,
            "min_ac": 2,
            "max_af": 0.9,
            "select_genotype": "het",
            "types": ["snps", "indels"],
            "exclude_types": ["mnps"],
            "known_or_novel": "--known",
            "min_alleles": 2,
            "max_alleles": 4,
            "phased": "--phased",
            "uncalled": "--exclude-uncalled",
            "private": "--private",
            "drop_genotypes": True,
            "header": "--no-header",
            "compression_level": 6,
            "regions": "chr2",
            "targets": "targets.bed",
            "include": "QUAL>50",
            "exclude": "DP<10",
            "output_type": "z",
            "threads": 6,
            "output": "/work/bcftools_view",
        }
    ) == [
        "bcftools",
        "view",
        "--trim-alt-alleles",
        "--no-update",
        "--samples",
        "S1,S2",
        "--force-samples",
        "--min-ac",
        "2",
        "--genotype",
        "het",
        "--known",
        "--min-alleles",
        "2",
        "--max-alleles",
        "4",
        "--phased",
        "--max-af",
        "0.9",
        "--exclude-uncalled",
        "--types",
        "snps,indels",
        "--exclude-types",
        "mnps",
        "--private",
        "--drop-genotypes",
        "--no-header",
        "--compression-level",
        "6",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "--include",
        "QUAL>50",
        "--exclude",
        "DP<10",
        "--output-type",
        "z",
        "--threads",
        "6",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_view/view.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_view" / "view.vcf.gz",
    ]


def test_galaxy_parity_bcftools_conversion_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_merge": {
            "display_name": "BCFtools Merge",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#merge",
            "output": ["VCF_GZ"],
            "search_alias": "merge samples",
        },
        "bcftools_isec": {
            "display_name": "BCFtools Isec",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#isec",
            "output": ["VCF_GZ"],
            "search_alias": "variant intersection",
        },
        "bcftools_gtcheck": {
            "display_name": "BCFtools GTcheck",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#gtcheck",
            "output": ["TSV"],
            "search_alias": "sample identity",
        },
        "bcftools_convert_to_vcf": {
            "display_name": "BCFtools Convert to VCF",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#convert",
            "output": ["VCF_GZ"],
            "search_alias": "gvcf to vcf",
        },
        "bcftools_convert_from_vcf": {
            "display_name": "BCFtools Convert from VCF",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#convert",
            "output": ["TSV", "TSV", "TSV"],
            "search_alias": "vcf to shapeit",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_merge_renders_multisample_merge_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_merge")

    assert node_class.render_command(
        {
            "input_files": ["tumor.vcf.gz", "normal.bcf"],
            "force_samples": True,
            "info_rules": "DP:sum,AD:join",
            "merge": "both",
            "no_index": True,
            "print_header": True,
            "use_header": "merged_header.vcf",
            "apply_filters": "PASS,.",
            "regions": "chr1:1-1000",
            "regions_overlap": "1",
            "include": "QUAL>20",
            "exclude": "FILTER='LowQual'",
            "output_type": "z",
            "threads": 4,
            "output": "/work/bcftools_merge",
        }
    ) == [
        "bcftools",
        "merge",
        "--print-header",
        "--use-header",
        "merged_header.vcf",
        "--force-samples",
        "--info-rules",
        "DP:sum,AD:join",
        "--merge",
        "both",
        "--no-index",
        "--apply-filters",
        "PASS,.",
        "--regions",
        "chr1:1-1000",
        "--regions-overlap",
        "1",
        "--include",
        "QUAL>20",
        "--exclude",
        "FILTER='LowQual'",
        "--output-type",
        "z",
        "--threads",
        "4",
        "tumor.vcf.gz",
        "normal.bcf",
        ">",
        "/work/bcftools_merge/merged.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_merge" / "merged.vcf.gz",
    ]


def test_bcftools_isec_renders_intersection_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_isec")

    assert node_class.render_command(
        {
            "input_files": ["case.vcf.gz", "control.vcf.gz", "truth.vcf.gz"],
            "nfiles": "+2",
            "complement": True,
            "collapse": "all",
            "apply_filters": "PASS",
            "regions": "chr2",
            "targets": "targets.bed",
            "targets_overlap": "0",
            "include": "AF>0.05",
            "exclude": "TYPE='ref'",
            "output_type": "v",
            "threads": 2,
            "output": "/work/bcftools_isec",
        }
    ) == [
        "bcftools",
        "isec",
        "--complement",
        "--nfiles",
        "+2",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "--targets-overlap",
        "0",
        "--collapse",
        "all",
        "--apply-filters",
        "PASS",
        "--include",
        "AF>0.05",
        "--exclude",
        "TYPE='ref'",
        "--output-type",
        "v",
        "--threads",
        "2",
        "case.vcf.gz",
        "control.vcf.gz",
        "truth.vcf.gz",
        ">",
        "/work/bcftools_isec/isec.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({"output_type": "v"}, tmp_path) == [
        tmp_path / "bcftools_isec" / "isec.vcf",
    ]


def test_bcftools_gtcheck_renders_identity_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_gtcheck")

    assert node_class.render_command(
        {
            "input_file": "query.vcf.gz",
            "genotypes": "reference.bcf",
            "all_sites": True,
            "homs_only": True,
            "query_sample": "QUERY1",
            "target_sample": "TARGET1",
            "plot": "discordance",
            "regions": "chr3",
            "targets": "sites.bed",
            "output": "/work/bcftools_gtcheck",
        }
    ) == [
        "bcftools",
        "gtcheck",
        "--genotypes",
        "reference.bcf",
        "--all-sites",
        "--homs-only",
        "--plot",
        "discordance",
        "--query-sample",
        "QUERY1",
        "--target-sample",
        "TARGET1",
        "--regions",
        "chr3",
        "--targets",
        "sites.bed",
        "query.vcf.gz",
        ">",
        "/work/bcftools_gtcheck/gtcheck.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_gtcheck" / "gtcheck.tsv",
    ]


def test_bcftools_convert_to_vcf_renders_tsv_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_convert_to_vcf")

    assert node_class.render_command(
        {
            "convert_from": "tsv",
            "input_file": "variants.tsv",
            "reference": "ref.fa",
            "samples": "SAMPLE1,SAMPLE2",
            "columns": "ID,CHROM,POS,AA",
            "output_type": "z",
            "output": "/work/bcftools_convert_to_vcf",
        }
    ) == [
        "bcftools",
        "convert",
        "--output-type",
        "z",
        "--fasta-ref",
        "ref.fa",
        "--samples",
        "SAMPLE1,SAMPLE2",
        "--columns",
        "ID,CHROM,POS,AA",
        "--tsv2vcf",
        "variants.tsv",
        ">",
        "/work/bcftools_convert_to_vcf/converted.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_convert_to_vcf" / "converted.vcf.gz",
    ]


def test_bcftools_convert_from_vcf_renders_hap_legend_sample_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_convert_from_vcf")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "convert_to": "hap_legend_sample",
            "vcf_ids": True,
            "haploid2diploid": True,
            "sex_file": "sex.tsv",
            "keep_duplicates": True,
            "samples": "S1,S2",
            "regions": "chrX",
            "targets": "targets.bed",
            "include": "MAF>0.01",
            "exclude": "FILTER!='PASS'",
            "output": "/work/bcftools_convert_from_vcf",
        }
    ) == [
        "bcftools",
        "convert",
        "--vcf-ids",
        "--haploid2diploid",
        "--haplegendsample",
        "/work/bcftools_convert_from_vcf/converted.hap,/work/bcftools_convert_from_vcf/converted.legend,/work/bcftools_convert_from_vcf/converted.samples",
        "--sex",
        "sex.tsv",
        "--keep-duplicates",
        "--include",
        "MAF>0.01",
        "--exclude",
        "FILTER!='PASS'",
        "--regions",
        "chrX",
        "--targets",
        "targets.bed",
        "--samples",
        "S1,S2",
        "cohort.vcf.gz",
        ".",
    ]

    assert node_class.PLAN_OUTPUTS({"convert_to": "hap_legend_sample"}, tmp_path) == [
        tmp_path / "bcftools_convert_from_vcf" / "converted.hap",
        tmp_path / "bcftools_convert_from_vcf" / "converted.legend",
        tmp_path / "bcftools_convert_from_vcf" / "converted.samples",
    ]


def test_galaxy_parity_bcftools_analysis_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_cnv": {
            "display_name": "BCFtools CNV",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#cnv",
            "output": ["TSV", "TSV", "HTML"],
            "search_alias": "copy number variation",
            "required_conda_packages": ["bcftools", "htslib", "matplotlib"],
        },
        "bcftools_csq": {
            "display_name": "BCFtools CSQ",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#csq",
            "output": ["VCF_GZ"],
            "search_alias": "consequence prediction",
            "required_conda_packages": ["bcftools", "htslib"],
        },
        "bcftools_roh": {
            "display_name": "BCFtools ROH",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#roh",
            "output": ["TSV"],
            "search_alias": "runs of homozygosity",
            "required_conda_packages": ["bcftools", "htslib"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_cnv_renders_pairwise_hmm_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_cnv")

    assert node_class.render_command(
        {
            "input_file": "intensity.vcf.gz",
            "query_sample": "tumor",
            "control_sample": "normal",
            "AF_file": "af.tsv",
            "plot_threshold": 15,
            "aberrant_query": 0.7,
            "aberrant_control": 0.95,
            "optimize": 0.3,
            "baf_weight": 0.8,
            "baf_dev_query": 0.05,
            "baf_dev_control": 0.04,
            "lrr_weight": 0.4,
            "lrr_dev_query": 0.3,
            "lrr_dev_control": 0.2,
            "lrr_smooth_win": 20,
            "same_prob": 0.6,
            "err_prob": 0.0002,
            "xy_prob": 1e-8,
            "regions": "chr10,chr11",
            "regions_overlap": "1",
            "targets": "cnv_targets.bed",
            "output": "/work/bcftools_cnv",
        }
    ) == [
        "bcftools",
        "cnv",
        "--output-dir",
        "/work/bcftools_cnv/cnv_tmp",
        "-c",
        "normal",
        "-s",
        "tumor",
        "--AF-file",
        "af.tsv",
        "--plot-threshold",
        "15",
        "--aberrant",
        "0.7,0.95",
        "--optimize",
        "0.3",
        "--BAF-weight",
        "0.8",
        "--BAF-dev",
        "0.05,0.04",
        "--LRR-weight",
        "0.4",
        "--LRR-dev",
        "0.3,0.2",
        "--LRR-smooth-win",
        "20",
        "--same-prob",
        "0.6",
        "--err-prob",
        "0.0002",
        "--xy-prob",
        "1e-08",
        "--regions",
        "chr10,chr11",
        "--regions-overlap",
        "1",
        "--targets",
        "cnv_targets.bed",
        "intensity.vcf.gz",
        "&&",
        "python",
        "-c",
        node_class.CNV_POSTPROCESS_SCRIPT,
        "/work/bcftools_cnv/cnv_tmp",
        "/work/bcftools_cnv/cnv.tab",
        "/work/bcftools_cnv/summary.tab",
        "/work/bcftools_cnv/plots.html",
        "1",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_cnv" / "cnv.tab",
        tmp_path / "bcftools_cnv" / "summary.tab",
        tmp_path / "bcftools_cnv" / "plots.html",
    ]
    assert node_class.PLAN_OUTPUTS({"generate_plots": True}, tmp_path) == [
        tmp_path / "bcftools_cnv" / "cnv.tab",
        tmp_path / "bcftools_cnv" / "summary.tab",
        tmp_path / "bcftools_cnv" / "plots.html",
    ]


def test_bcftools_csq_renders_haplotype_consequence_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_csq")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "reference": "ref.fa",
            "gff_annot": "genes.gff3",
            "ncsq": 32,
            "local_csq": True,
            "phase": "R",
            "custom_tag": "MYCSQ",
            "trim_protein_seq": 12,
            "genetic_code": "1",
            "samples": "S1,S2",
            "regions": "chr1",
            "targets": "coding.bed",
            "include": "QUAL>30",
            "exclude": "TYPE='ref'",
            "output_type": "z",
            "output": "/work/bcftools_csq",
        }
    ) == [
        "bcftools",
        "csq",
        "--fasta-ref",
        "ref.fa",
        "--gff-annot",
        "genes.gff3",
        "--ncsq",
        "32",
        "--local-csq",
        "--phase",
        "R",
        "--custom-tag",
        "MYCSQ",
        "--trim-protein-seq",
        "12",
        "--genetic-code",
        "1",
        "--samples",
        "S1,S2",
        "--include",
        "QUAL>30",
        "--exclude",
        "TYPE='ref'",
        "--regions",
        "chr1",
        "--targets",
        "coding.bed",
        "--output-type",
        "z",
        "phased.vcf.gz",
        ">",
        "/work/bcftools_csq/csq.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_csq" / "csq.vcf.gz",
    ]


def test_bcftools_roh_renders_autozygosity_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_roh")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "sample": "S1",
            "AF_file": "af.tsv",
            "AF_tag": "AF",
            "AF_dflt": 0.4,
            "estimate_AF": "samples.txt",
            "GTs_only": 30,
            "skip_indels": True,
            "genetic_map": "map.txt",
            "rec_rate": 1e-8,
            "buffer_size": 10000,
            "buffer_overlap": 100,
            "ignore_homref": True,
            "include_noalt": True,
            "hw_to_az": 6.7e-8,
            "az_to_hw": 5e-9,
            "viterbi_training": True,
            "regions": "chr1",
            "targets": "roh_targets.bed",
            "samples": "S1",
            "output_type": "r",
            "output": "/work/bcftools_roh",
        }
    ) == [
        "bcftools",
        "roh",
        "--sample",
        "S1",
        "--AF-file",
        "af.tsv",
        "--AF-tag",
        "AF",
        "--AF-dflt",
        "0.4",
        "--estimate-AF",
        "samples.txt",
        "--GTs-only",
        "30",
        "--skip-indels",
        "--genetic-map",
        "map.txt",
        "--rec-rate",
        "1e-08",
        "--buffer-size",
        "10000,100",
        "--ignore-homref",
        "--include-noalt",
        "--hw-to-az",
        "6.7e-08",
        "--az-to-hw",
        "5e-09",
        "--viterbi-training",
        "--regions",
        "chr1",
        "--targets",
        "roh_targets.bed",
        "--samples",
        "S1",
        "--output-type",
        "r",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_roh/roh.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_roh" / "roh.tsv",
    ]


def test_bcftools_roh_accepts_fractional_gts_only_and_gates_buffer_overlap() -> None:
    node_class = _node_class("bcftools_roh")

    input_types = node_class.INPUT_TYPES()
    assert input_types["optional"]["GTs_only"][0] == "FLOAT"

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "GTs_only": 30.5,
            "buffer_size": 10000,
            "output": "/work/bcftools_roh",
        }
    ) == [
        "bcftools",
        "roh",
        "--GTs-only",
        "30.5",
        "--buffer-size",
        "10000",
        "--output-type",
        "r",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_roh/roh.tsv",
    ]

    assert "--buffer-size" not in node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "buffer_overlap": 100,
            "output": "/work/bcftools_roh",
        }
    )


def test_galaxy_parity_bcftools_plugin_nodes_expose_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_plugin_counts": {
            "display_name": "BCFtools +counts",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#counts",
            "output": ["TSV"],
            "search_alias": "variant counts",
        },
        "bcftools_plugin_dosage": {
            "display_name": "BCFtools +dosage",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#dosage",
            "output": ["TSV"],
            "search_alias": "genotype dosage",
        },
        "bcftools_plugin_missing2ref": {
            "display_name": "BCFtools +missing2ref",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#missing2ref",
            "output": ["VCF_GZ"],
            "search_alias": "set missing genotypes",
        },
        "bcftools_plugin_tag2tag": {
            "display_name": "BCFtools +tag2tag",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#tag2tag",
            "output": ["VCF_GZ"],
            "search_alias": "convert genotype tags",
        },
        "bcftools_plugin_fill_an_ac": {
            "display_name": "BCFtools +fill-AN-AC",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "fill AN AC",
        },
        "bcftools_plugin_fill_tags": {
            "display_name": "BCFtools +fill-tags",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html",
            "output": ["VCF_GZ"],
            "search_alias": "fill INFO tags",
        },
        "bcftools_plugin_setgt": {
            "display_name": "BCFtools +setGT",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.setGT.html",
            "output": ["VCF_GZ"],
            "search_alias": "set genotype calls",
        },
        "bcftools_plugin_fixploidy": {
            "display_name": "BCFtools +fixploidy",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "fix ploidy",
        },
        "bcftools_plugin_mendelian": {
            "display_name": "BCFtools +mendelian2",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.mendelian.html",
            "output": ["VCF_GZ"],
            "search_alias": "mendelian consistency",
        },
        "bcftools_plugin_impute_info": {
            "display_name": "BCFtools +impute-info",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "imputation info",
        },
        "bcftools_plugin_color_chrs": {
            "display_name": "BCFtools +color-chrs",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["TSV", "IMAGE"],
            "required_executables": ["bcftools", "color-chrs.pl"],
            "search_alias": "color shared chromosomal segments",
        },
        "bcftools_plugin_frameshifts": {
            "display_name": "BCFtools +frameshifts",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "required_executables": ["bcftools", "bgzip", "tabix"],
            "search_alias": "frameshift indels",
        },
        "bcftools_plugin_split_vep": {
            "display_name": "BCFtools +split-vep",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.split-vep.html",
            "output": ["VCF_GZ"],
            "search_alias": "split VEP annotations",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == metadata.get("required_executables", ["bcftools"])
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_plugin_counts_renders_filtered_table_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_counts")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "include": "QUAL>20",
            "exclude": "TYPE='ref'",
            "regions": "chr1",
            "targets": "targets.bed",
            "output": "/work/bcftools_plugin_counts",
        }
    ) == [
        "bcftools",
        "plugin",
        "counts",
        "--include",
        "QUAL>20",
        "--exclude",
        "TYPE='ref'",
        "--regions",
        "chr1",
        "--targets",
        "targets.bed",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_plugin_counts/counts.raw.txt",
        "&&",
        "python",
        "-c",
        node_class.COUNTS_POSTPROCESS_SCRIPT,
        "/work/bcftools_plugin_counts/counts.raw.txt",
        "/work/bcftools_plugin_counts/counts.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_counts" / "counts.tsv",
    ]


def test_bcftools_plugin_counts_postprocesses_galaxy_table(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_counts")
    raw_counts = tmp_path / "counts.raw.txt"
    output = tmp_path / "counts.tsv"
    raw_counts.write_text(
        "Number of samples: 3\n"
        "Number of SNPs: 11\n"
        "Number of INDELs: 4\n"
        "Number of total sites: 15\n",
        encoding="utf-8",
    )

    old_argv = sys.argv
    sys.argv = ["counts-postprocess", str(raw_counts), str(output)]
    try:
        exec(node_class.COUNTS_POSTPROCESS_SCRIPT, {"__name__": "__main__"})
    finally:
        sys.argv = old_argv

    assert output.read_text(encoding="utf-8") == "#samples\tSNPs\tINDELs\tsites\n3\t11\t4\t15\n"


def test_bcftools_plugin_dosage_renders_plugin_options_after_separator(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_dosage")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "regions": "chr2",
            "targets": "targets.bed",
            "include": "N_ALT=1",
            "tags": "PL,GT",
            "output": "/work/bcftools_plugin_dosage",
        }
    ) == [
        "bcftools",
        "plugin",
        "dosage",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "calls.vcf.gz",
        "--",
        "--tags",
        "PL,GT",
        ">",
        "/work/bcftools_plugin_dosage/dosage.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_dosage" / "dosage.tsv",
    ]


def test_bcftools_plugin_missing2ref_renders_vcf_transform_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_missing2ref")

    assert node_class.render_command(
        {
            "input_file": "missing.vcf.gz",
            "phased": True,
            "major": True,
            "regions": "chr3",
            "threads": 6,
            "output": "/work/bcftools_plugin_missing2ref",
        }
    ) == [
        "bcftools",
        "plugin",
        "missing2ref",
        "--regions",
        "chr3",
        "--output-type",
        "z",
        "--threads",
        "6",
        "missing.vcf.gz",
        "--",
        "--phased",
        "--major",
        ">",
        "/work/bcftools_plugin_missing2ref/missing2ref.vcf.gz",
    ]

    input_types = node_class.INPUT_TYPES()
    assert "output_type" not in input_types["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_missing2ref" / "missing2ref.vcf.gz",
    ]


def test_bcftools_plugin_tag2tag_renders_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_tag2tag")

    assert node_class.render_command(
        {
            "input_file": "gp.vcf.gz",
            "conversion": "--gp-to-gt",
            "replace": True,
            "threshold": 0.2,
            "exclude": "FILTER='LowQual'",
            "threads": 3,
            "output": "/work/bcftools_plugin_tag2tag",
        }
    ) == [
        "bcftools",
        "plugin",
        "tag2tag",
        "--exclude",
        "FILTER='LowQual'",
        "--output-type",
        "z",
        "--threads",
        "3",
        "gp.vcf.gz",
        "--",
        "--gp-to-gt",
        "--replace",
        "--threshold",
        "0.2",
        ">",
        "/work/bcftools_plugin_tag2tag/tag2tag.vcf.gz",
    ]

    input_types = node_class.INPUT_TYPES()
    assert "output_type" not in input_types["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_tag2tag" / "tag2tag.vcf.gz",
    ]


def test_bcftools_plugin_fill_an_ac_renders_vcf_annotation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fill_an_ac")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "include": "TYPE='snp'",
            "regions": "chr1:1-100",
            "targets": "targets.tsv.gz",
            "threads": 5,
            "output": "/work/bcftools_plugin_fill_an_ac",
        }
    ) == [
        "bcftools",
        "plugin",
        "fill-AN-AC",
        "--include",
        "TYPE='snp'",
        "--regions",
        "chr1:1-100",
        "--targets",
        "targets.tsv.gz",
        "--output-type",
        "z",
        "--threads",
        "5",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_plugin_fill_an_ac/fill_an_ac.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fill_an_ac" / "fill_an_ac.vcf.gz",
    ]


def test_bcftools_plugin_fill_tags_renders_plugin_tags_samples_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fill_tags")

    assert node_class.render_command(
        {
            "input_file": "cohort.bcf",
            "tags": ["AN", "AC", "AC_Het"],
            "samples": "S1,S2",
            "samples_file": "populations.tsv",
            "invert_samples_file": True,
            "drop_missing": True,
            "regions": "chr2",
            "exclude": "FILTER='LowQual'",
            "threads": 8,
            "output": "/work/bcftools_plugin_fill_tags",
        }
    ) == [
        "bcftools",
        "plugin",
        "fill-tags",
        "--exclude",
        "FILTER='LowQual'",
        "--regions",
        "chr2",
        "--output-type",
        "z",
        "--threads",
        "8",
        "cohort.bcf",
        "--",
        "--tags",
        "AN,AC,AC_Het",
        "--samples",
        "S1,S2",
        "--samples-file",
        "^populations.tsv",
        "--drop-missing",
        ">",
        "/work/bcftools_plugin_fill_tags/fill_tags.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fill_tags" / "fill_tags.vcf.gz",
    ]


def test_bcftools_plugin_setgt_renders_genotype_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_setgt")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "target_gt": "q",
            "new_gt": "0",
            "include": 'GT="." && FMT/DP>0',
            "exclude": "GQ<20",
            "seed": 13,
            "regions": "chr7",
            "targets": "targets.bed",
            "threads": 2,
            "output": "/work/bcftools_plugin_setgt",
        }
    ) == [
        "bcftools",
        "plugin",
        "setGT",
        "--regions",
        "chr7",
        "--targets",
        "targets.bed",
        "--output-type",
        "z",
        "--threads",
        "2",
        "calls.vcf.gz",
        "--",
        "--target-gt",
        "q",
        "--new-gt",
        "0",
        "--include",
        'GT="." && FMT/DP>0',
        "--exclude",
        "GQ<20",
        "--seed",
        "13",
        ">",
        "/work/bcftools_plugin_setgt/setgt.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_setgt" / "setgt.vcf.gz",
    ]


def test_bcftools_plugin_fixploidy_renders_ploidy_files_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fixploidy")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "ploidy_file": "ploidy.tsv",
            "sex": "sample_sex.tsv",
            "default_ploidy": 2,
            "force_ploidy": 4,
            "regions": "chrX",
            "include": "TYPE='snp'",
            "threads": 3,
            "output": "/work/bcftools_plugin_fixploidy",
        }
    ) == [
        "bcftools",
        "plugin",
        "fixploidy",
        "--include",
        "TYPE='snp'",
        "--regions",
        "chrX",
        "--output-type",
        "z",
        "--threads",
        "3",
        "cohort.vcf.gz",
        "--",
        "--ploidy",
        "ploidy.tsv",
        "--sex",
        "sample_sex.tsv",
        "--default-ploidy",
        "2",
        "--force-ploidy",
        "4",
        "--tags",
        "GT",
        ">",
        "/work/bcftools_plugin_fixploidy/fixploidy.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fixploidy" / "fixploidy.vcf.gz",
    ]


def test_bcftools_plugin_mendelian_renders_inline_trio_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_mendelian")

    assert node_class.render_command(
        {
            "input_file": "family.vcf.gz",
            "trios_src": "trio",
            "child": "NA00006",
            "mother": "NA00001",
            "father": "NA00002",
            "num_x": "1X",
            "mode": ["a", "d", "e"],
            "rules": "GRCh38",
            "regions": "chr1",
            "targets": "targets.bed",
            "exclude": "QUAL<20",
            "output": "/work/bcftools_plugin_mendelian",
        }
    ) == [
        "bcftools",
        "plugin",
        "mendelian2",
        "--regions",
        "chr1",
        "--targets",
        "targets.bed",
        "--exclude",
        "QUAL<20",
        "--output-type",
        "z",
        "family.vcf.gz",
        "--",
        "--pfm",
        "1X:NA00006,NA00002,NA00001",
        "--rules",
        "GRCh38",
        "--mode",
        "ade",
        "2>",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
        ">",
        "/work/bcftools_plugin_mendelian/mendelian.vcf.gz",
        "&&",
        "cat",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_mendelian" / "mendelian.vcf.gz",
    ]


def test_bcftools_plugin_mendelian_renders_ped_file_command() -> None:
    node_class = _node_class("bcftools_plugin_mendelian")

    assert node_class.render_command(
        {
            "input_file": "family.vcf.gz",
            "trios_src": "trio_file",
            "trio_file": "family.ped",
            "rules_file": "inheritance.tsv",
            "mode": "M,S",
            "output": "/work/bcftools_plugin_mendelian",
        }
    ) == [
        "bcftools",
        "plugin",
        "mendelian2",
        "--output-type",
        "z",
        "family.vcf.gz",
        "--",
        "--ped",
        "family.ped",
        "--rules-file",
        "inheritance.tsv",
        "--mode",
        "MS",
        "2>",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
        ">",
        "/work/bcftools_plugin_mendelian/mendelian.vcf.gz",
        "&&",
        "cat",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
    ]


def test_bcftools_plugin_impute_info_renders_vcf_transform_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_impute_info")

    assert node_class.render_command(
        {
            "input_file": "imputed.vcf.gz",
            "include": "N_ALT=1",
            "regions": "chr20",
            "targets": "impute_targets.tsv",
            "threads": 4,
            "output": "/work/bcftools_plugin_impute_info",
        }
    ) == [
        "bcftools",
        "plugin",
        "impute-info",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr20",
        "--targets",
        "impute_targets.tsv",
        "--output-type",
        "z",
        "--threads",
        "4",
        "imputed.vcf.gz",
        ">",
        "/work/bcftools_plugin_impute_info/impute_info.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_impute_info" / "impute_info.vcf.gz",
    ]


def test_bcftools_plugin_color_chrs_renders_trio_plot_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_color_chrs")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "sample_rel_sel": "trio",
            "mother": "M",
            "father": "F",
            "child": "C",
            "regions": "chr1",
            "include": "N_ALT=1",
            "threads": 4,
            "output": "/work/bcftools_plugin_color_chrs",
        }
    ) == [
        "bcftools",
        "plugin",
        "color-chrs",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr1",
        "--threads",
        "4",
        "phased.vcf.gz",
        "--",
        "--trio",
        "M,F,C",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "color-chrs.pl",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "/work/bcftools_plugin_color_chrs/color_chrs.tsv",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.svg",
        "/work/bcftools_plugin_color_chrs/color_chrs.svg",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_color_chrs" / "color_chrs.tsv",
        tmp_path / "bcftools_plugin_color_chrs" / "color_chrs.svg",
    ]


def test_bcftools_plugin_color_chrs_renders_unrelated_pair_command() -> None:
    node_class = _node_class("bcftools_plugin_color_chrs")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "sample_rel_sel": "unrelated",
            "sample_a": "A",
            "sample_b": "B",
            "output": "/work/bcftools_plugin_color_chrs",
        }
    ) == [
        "bcftools",
        "plugin",
        "color-chrs",
        "phased.vcf.gz",
        "--",
        "--unrelated",
        "A,B",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "color-chrs.pl",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "/work/bcftools_plugin_color_chrs/color_chrs.tsv",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.svg",
        "/work/bcftools_plugin_color_chrs/color_chrs.svg",
    ]


def test_bcftools_plugin_frameshifts_renders_indexed_exons_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_frameshifts")

    assert node_class.render_command(
        {
            "input_file": "indels.vcf.gz",
            "exons": "exons.bed",
            "include": "TYPE='indel'",
            "regions": "chr12",
            "targets": "coding.bed",
            "threads": 7,
            "output": "/work/bcftools_plugin_frameshifts",
        }
    ) == [
        "bgzip",
        "-c",
        "exons.bed",
        ">",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        "&&",
        "tabix",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        "&&",
        "bcftools",
        "plugin",
        "frameshifts",
        "--include",
        "TYPE='indel'",
        "--regions",
        "chr12",
        "--targets",
        "coding.bed",
        "--output-type",
        "z",
        "--threads",
        "7",
        "indels.vcf.gz",
        "--",
        "--exons",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        ">",
        "/work/bcftools_plugin_frameshifts/frameshifts.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_frameshifts" / "frameshifts.vcf.gz",
    ]


def test_bcftools_plugin_split_vep_renders_annotation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_split_vep")

    assert node_class.render_command(
        {
            "input_file": "annotated.vcf.gz",
            "a": "ANN",
            "c": "IMPACT,gnomAD_AF:Float",
            "d": True,
            "allow_undef_tags": True,
            "p": "vep",
            "s": "worst",
            "include": "IMPACT='HIGH'",
            "regions": "chr5",
            "output": "/work/bcftools_plugin_split_vep",
        }
    ) == [
        "bcftools",
        "plugin",
        "split-vep",
        "--include",
        "IMPACT='HIGH'",
        "--regions",
        "chr5",
        "--output-type",
        "z",
        "annotated.vcf.gz",
        "--",
        "-a",
        "ANN",
        "-c",
        "IMPACT,gnomAD_AF:Float",
        "-d",
        "--allow-undef-tags",
        "-p",
        "vep",
        "-s",
        "worst",
        ">",
        "/work/bcftools_plugin_split_vep/split_vep.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_split_vep" / "split_vep.vcf.gz",
    ]
