"""Shared MMseqs2 contracts for focused protein taxonomy nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.taxonomy_family.protein_contracts import ValidatedCommandContract


MMSEQS2_GIT_COMMIT = "b804fbe384e6f6c9fe96322ec0e92d48bccd0a42"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"


class MMseqs2ContractNode(ValidatedCommandContract):
    """MMseqs2 17-b804f plus the exact Galaxy IUC wrapper authority."""

    GIT_URL = "https://github.com/soedinglab/MMseqs2.git"
    GIT_COMMIT = MMSEQS2_GIT_COMMIT
    SOURCE_URL = f"https://github.com/soedinglab/MMseqs2/tree/{MMSEQS2_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "mmseqs2==17-b804f"
    GALAXY_WRAPPER_VERSION = "17-b804f+galaxy1"
    GALAXY_WRAPPER_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
    GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    GALAXY_WRAPPER_SOURCE_URL = (
        f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/mmseqs2"
    )
    EXIT_SEMANTICS = "MMseqs2 or wrapper validation failures must produce a non-zero command result."


def _validate_target_source(inputs: dict[str, Any]) -> bool | str:
    source = str(inputs.get("target_source", "history") or "history")
    if source == "history" and not str(inputs.get("target_fasta", "")).strip():
        return "target_fasta is required when target_source=history"
    if source == "cached" and not str(inputs.get("target_database", "")).strip():
        return "target_database is required when target_source=cached"
    return True


class _MMseqs2EasySearchContract(MMseqs2ContractNode):
    """Run MMseqs2 easy-search for sensitive sequence homology search."""

    LEGACY_NODE_ID = "mmseqs2_easy_search"
    DISPLAY_NAME = "MMseqs2 Easy Search"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run MMseqs2 easy-search for protein, nucleotide, or translated homology searches."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "mmseqs2", "mmseqs", "easy-search", "homology", "sequence search"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = "https://github.com/soedinglab/MMseqs2/wiki"
    CITATION_DOIS = [
        "10.1038/nbt.3988",
        "10.1038/s41467-018-04964-5",
        "10.1093/bioinformatics/btab184",
    ]
    CITATION_URLS = [
        "https://doi.org/10.1038/nbt.3988",
        "https://doi.org/10.1038/s41467-018-04964-5",
        "https://doi.org/10.1093/bioinformatics/btab184",
    ]
    CITATION_TEXT = "MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets."
    VERSION = "17-b804f"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "mmseqs",
            "easy-search",
            str(inputs.get("query_fasta", "")),
            str(inputs.get("target_fasta", inputs.get("target_database", ""))),
            f"{out}/search_results",
            f"{out}/tmp",
            "--search-type",
            str(inputs.get("search_type", 0)),
            "-s",
            str(inputs.get("sensitivity", 5.7)),
            "-e",
            str(inputs.get("evalue", 0.001)),
            "--min-seq-id",
            str(inputs.get("min_seq_id", 0.0)),
            "-c",
            str(inputs.get("cov", 0.0)),
            "--cov-mode",
            str(inputs.get("cov_mode", 0)),
        ]
        _add_if_value(cmd, "--format-output", inputs.get("format_output", "query,target,pident,evalue,bits"))
        _add_if_value(cmd, "--num-iterations", inputs.get("num_iterations", 1))
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "search_results"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/Q file"}),
                "target_fasta": ("FASTA", {"description": "Target FASTA database"}),
            },
            "optional": {
                "search_type": ("INT", {"default": 0, "min": 0, "max": 4, "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide"}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 15}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov_mode": ("INT", {"default": 0, "min": 0, "max": 5}),
                "format_output": ("STRING", {"default": "query,target,pident,evalue,bits"}),
                "num_iterations": ("INT", {"default": 1, "min": 1, "max": 20, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2EasyClusterContract(MMseqs2ContractNode):
    """Cluster protein or nucleotide sequences with MMseqs2 easy-cluster."""

    LEGACY_NODE_ID = "mmseqs2_easy_cluster"
    DISPLAY_NAME = "MMseqs2 Easy Cluster"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster protein or nucleotide sequences with MMseqs2 cascaded clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-cluster",
        "cascaded clustering",
        "sequence clustering",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "TSV")
    RETURN_NAMES = ("representative_sequences", "clustered_sequences", "cluster_tsv")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = "https://github.com/soedinglab/MMseqs2/wiki"
    CITATION_DOIS = _MMseqs2EasySearchContract.CITATION_DOIS
    CITATION_URLS = _MMseqs2EasySearchContract.CITATION_URLS
    CITATION_TEXT = _MMseqs2EasySearchContract.CITATION_TEXT
    VERSION = _MMseqs2EasySearchContract.VERSION
    SHELL = True

    @classmethod
    def _input_link_name(cls, input_fasta: Any) -> str:
        suffixes = Path(str(input_fasta or "")).suffixes
        if suffixes[-2:] == [".fasta", ".gz"]:
            return "input.fasta.gz"
        if suffixes[-2:] == [".fa", ".gz"]:
            return "input.fa.gz"
        if suffixes and suffixes[-1].lower() in {".fasta", ".fa", ".faa", ".fna", ".ffn", ".gz"}:
            return f"input{suffixes[-1].lower()}"
        return "input.fasta"

    @classmethod
    def _add_dbtype_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
        cmd.extend(["--dbtype", dbtype])

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
                "-s",
                str(inputs.get("sensitivity", 5.7)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
            ]
        )

    @classmethod
    def _add_align_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-a",
                str(inputs.get("convertalis", 0)),
                "--alignment-output-mode",
                str(inputs.get("alignment_output_mode", 0)),
                "--wrapped-scoring",
                str(inputs.get("wrapped_scoring", 0)),
                "--min-aln-len",
                str(inputs.get("min_aln_len", 0)),
                "--seq-id-mode",
                str(inputs.get("seq_id_mode", 0)),
                "--alt-ali",
                str(inputs.get("alt_ali", 0)),
                "--score-bias",
                str(inputs.get("score_bias", 0)),
                "--realign",
                str(inputs.get("realign", 0)),
                "--realign-score-bias",
                str(inputs.get("realign_score_bias", -0.2)),
                "--realign-max-seqs",
                str(inputs.get("realign_max_seqs", 2147483647)),
                "--corr-score-weight",
                str(inputs.get("corr_score_weight", 0)),
                "--alignment-mode",
                str(inputs.get("alignment_mode", 0)),
                "-e",
                str(inputs.get("evalue", 0.001)),
                "--min-seq-id",
                str(inputs.get("min_seq_id", 0.3)),
                "-c",
                str(inputs.get("cov", 0.8)),
                "--cov-mode",
                str(inputs.get("cov_mode", 0)),
                "--max-rejected",
                str(inputs.get("max_rejected", 2147483647)),
                "--max-accept",
                str(inputs.get("max_accept", 2147483647)),
            ]
        )

    @classmethod
    def _add_clustering_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--cluster-mode",
                str(inputs.get("cluster_mode", 0)),
                "--max-iterations",
                str(inputs.get("max_iterations", 1000)),
                "--similarity-type",
                str(inputs.get("similarity_type", 2)),
            ]
        )

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--rescore-mode",
                str(inputs.get("rescore_mode", 0)),
                "--shuffle",
                str(inputs.get("shuffle", 1)),
                "--id-offset",
                str(inputs.get("id_offset", 0)),
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        linked_input = cls._input_link_name(input_fasta)
        cmd = ["mmseqs", "easy-cluster", linked_input, f"{out}/result", f"{out}/tmp"]
        cls._add_dbtype_options(cmd, inputs)
        cls._add_prefilter_options(cmd, inputs)
        cls._add_align_options(cmd, inputs)
        cls._add_clustering_options(cmd, inputs)
        cls._add_misc_options(cmd, inputs)
        return f"ln -sf {shlex.quote(input_fasta)} {shlex.quote(linked_input)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(_as_list(inputs.get("output_selection")))
        if not selected:
            selected = {"file_rep_seq", "file_all_seq", "file_cluster_tsv"}
        outputs = {
            "file_rep_seq": out / "result_rep_seq.fasta",
            "file_all_seq": out / "result_all_seqs.fasta",
            "file_cluster_tsv": out / "result_cluster.tsv",
        }
        return [path for key, path in outputs.items() if key in selected]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Protein or nucleotide FASTA sequences to cluster"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0.3, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "cluster_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "max_iterations": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "similarity_type": ("STRING", {"default": "2", "options": ["1", "2"], "advanced": True}),
                "rescore_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "shuffle": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "options": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "list": True,
                        "description": "MMseqs2 easy-cluster output files to keep",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2EasyLinclustContract(_MMseqs2EasyClusterContract):
    """Cluster very large sequence sets in linear time with MMseqs2 Linclust."""

    LEGACY_NODE_ID = "mmseqs2_easy_linclust_clustering"
    DISPLAY_NAME = "MMseqs2 Easy Linclust"
    DESCRIPTION = "Cluster very large protein or nucleotide datasets in linear time with MMseqs2 Linclust."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-linclust",
        "linclust",
        "linear clustering",
    ]
    CITATION_DOIS = [
        "10.1038/s41467-018-04964-5",
        *_MMseqs2EasySearchContract.CITATION_DOIS,
    ]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-018-04964-5", *_MMseqs2EasySearchContract.CITATION_URLS]
    CITATION_TEXT = "Clustering huge protein sequence sets in linear time."

    @classmethod
    def _add_dbtype_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
            _add_if_value(cmd, "--kmer-per-seq-scale", inputs.get("kmer_per_seq_scale", 0.0))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
            _add_if_value(cmd, "--kmer-per-seq-scale", inputs.get("kmer_per_seq_scale", 0.0))
            _add_if_value(cmd, "--adjust-kmer-len", inputs.get("adjust_kmer_len", 0))
        cmd.extend(["--dbtype", dbtype])

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 0)),
            ]
        )

    @classmethod
    def _add_kmermatcher_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--cluster-weight-threshold",
                str(inputs.get("cluster_weight_threshold", 0.9)),
                "--kmer-per-seq",
                str(inputs.get("kmer_per_seq", 21)),
                "--hash-shift",
                str(inputs.get("hash_shift", 67)),
                "--include-only-extendable",
                str(inputs.get("include_only_extendable", 0)),
                "--ignore-multi-kmer",
                str(inputs.get("ignore_multi_kmer", 0)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        linked_input = cls._input_link_name(input_fasta)
        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        cmd = ["mmseqs", "easy-linclust", linked_input, f"{out}/result", f"{out}/tmp"]
        cls._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        cls._add_align_options(cmd, effective_inputs)
        cls._add_clustering_options(cmd, effective_inputs)
        cls._add_kmermatcher_options(cmd, effective_inputs)
        cls._add_misc_options(cmd, effective_inputs)
        return f"ln -sf {shlex.quote(input_fasta)} {shlex.quote(linked_input)} && {shlex.join(cmd)}"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Protein or nucleotide FASTA sequences to cluster"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "kmer_per_seq_scale": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1", "2"]}},
                    },
                ),
                "adjust_kmer_len": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "cluster_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "max_iterations": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "similarity_type": ("STRING", {"default": "2", "options": ["1", "2"], "advanced": True}),
                "cluster_weight_threshold": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "kmer_per_seq": ("INT", {"default": 21, "min": 1, "advanced": True}),
                "hash_shift": ("INT", {"default": 67, "min": 0, "advanced": True}),
                "include_only_extendable": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "ignore_multi_kmer": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "rescore_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "shuffle": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "options": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "list": True,
                        "description": "MMseqs2 easy-linclust output files to keep",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2EasyLinsearchContract(MMseqs2ContractNode):
    """Run MMseqs2 easy-linsearch for linear-time homology search."""

    LEGACY_NODE_ID = "mmseqs2_easy_linsearch"
    DISPLAY_NAME = "MMseqs2 Easy Linsearch"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run fast linear-time homology searches against large MMseqs2 target databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-linsearch",
        "linsearch",
        "linear homology search",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = _MMseqs2EasySearchContract.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1038/nbt.3988"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nbt.3988"]
    CITATION_TEXT = _MMseqs2EasySearchContract.CITATION_TEXT
    VERSION = _MMseqs2EasySearchContract.VERSION
    SHELL = True

    @classmethod
    def _sequence_link_name(cls, prefix: str, source: Any) -> str:
        suffixes = [suffix.lower() for suffix in Path(str(source or "")).suffixes]
        allowed_exts = {"fasta", "fa", "fastq", "fq", "faa", "fna", "ffn"}
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            ext = suffixes[-2].lstrip(".").replace("sanger", "").replace("illumina", "")
            if ext in allowed_exts:
                return f"{prefix}.{ext}.gz"
        if suffixes:
            ext = suffixes[-1].lstrip(".").replace("sanger", "").replace("illumina", "")
            if ext in allowed_exts:
                return f"{prefix}.{ext}"
        return f"{prefix}.fasta"

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
            ]
        )

    @classmethod
    def _add_kmermatcher_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--kmer-per-seq", str(inputs.get("kmer_per_seq", 21))])

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--id-offset",
                str(inputs.get("id_offset", 0)),
            ]
        )

    @classmethod
    def _format_fields(cls, inputs: dict[str, Any]) -> str:
        fields = _as_list(
            inputs.get(
                "format_fields",
                ["query", "target", "pident", "evalue", "bits"],
            )
        )
        return ",".join(fields)

    @classmethod
    def _add_output_format_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        format_mode = str(inputs.get("format_mode", "0"))
        format_fields = cls._format_fields(inputs)
        if format_mode in {"0", "2", "4"} and format_fields:
            cmd.extend(["--format-output", format_fields])
        cmd.extend(["--format-mode", format_mode])

    @classmethod
    def _add_search_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--search-type",
                str(inputs.get("search_type", 0)),
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
            ]
        )

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        if str(inputs.get("target_source", "history")) == "cached":
            database_root = str(inputs.get("target_database", ""))
            if inputs.get("create_linindex"):
                prelude = [
                    f"cp -r {shlex.quote(database_root)}/database* .",
                    f"mmseqs createlinindex database {shlex.quote(f'{out}/tmp')}",
                ]
                return prelude, "database"
            target = f"{database_root.rstrip('/')}/database" if database_root else "database"
            return [], target

        target_fasta = str(inputs.get("target_fasta", ""))
        linked_target = cls._sequence_link_name("target", target_fasta)
        return [f"ln -sf {shlex.quote(target_fasta)} {shlex.quote(linked_target)}"], linked_target

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return _validate_target_source(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = cls._sequence_link_name("query", query_fasta)
        prelude = [f"ln -sf {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)

        cmd = [
            "mmseqs",
            "easy-linsearch",
            linked_query,
            target,
            f"{out}/search_results",
            f"{out}/tmp",
        ]
        _MMseqs2EasyLinclustContract._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        _MMseqs2EasyClusterContract._add_align_options(cmd, effective_inputs)
        cls._add_kmermatcher_options(cmd, effective_inputs)
        cls._add_misc_options(cmd, effective_inputs)
        cls._add_output_format_options(cmd, effective_inputs)
        cls._add_search_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {"1": "sam", "3": "html"}.get(str(inputs.get("format_mode", "0")), "tsv")
        return [out / f"search_results.{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "target_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": ["history", "cached"],
                        "description": "Use a target FASTA from history or a cached MMseqs2 database",
                    },
                ),
                "target_fasta": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Target FASTA/FASTQ file for history mode",
                        "displayOptions": {"show": {"target_source": ["history"]}},
                    },
                ),
                "target_database": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Cached MMseqs2 database directory containing database* files",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "kmer_per_seq_scale": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1", "2"]}},
                    },
                ),
                "adjust_kmer_len": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "kmer_per_seq": ("INT", {"default": 21, "min": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "format_fields": (
                    "STRING",
                    {
                        "default": ["query", "target", "pident", "evalue", "bits"],
                        "options": [
                            "query",
                            "target",
                            "pident",
                            "alnlen",
                            "mismatch",
                            "gapopen",
                            "qstart",
                            "qend",
                            "tstart",
                            "tend",
                            "evalue",
                            "bits",
                            "qcov",
                            "tcov",
                        ],
                        "list": True,
                        "description": "Comma-separated fields for BLAST tabular-like output modes",
                    },
                ),
                "format_mode": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "4", "2", "1", "3"],
                        "description": "MMseqs2 output format mode: BLAST-like, SAM, or HTML",
                    },
                ),
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "create_linindex": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "advanced": True,
                        "description": "Create a linear index for copied cached database files before searching",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2EasyRBHContract(MMseqs2ContractNode):
    """Identify reciprocal best hits with MMseqs2 easy-rbh."""

    LEGACY_NODE_ID = "mmseqs2_easy_rbh"
    DISPLAY_NAME = "MMseqs2 Easy RBH"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Identify reciprocal best hits between two sequence sets for ortholog detection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-rbh",
        "reciprocal best hit",
        "ortholog detection",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = _MMseqs2EasySearchContract.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1038/nbt.3988"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nbt.3988"]
    CITATION_TEXT = _MMseqs2EasySearchContract.CITATION_TEXT
    VERSION = _MMseqs2EasySearchContract.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        if str(inputs.get("target_source", "history")) == "cached":
            database_root = str(inputs.get("target_database", ""))
            target = f"{database_root.rstrip('/')}/database" if database_root else "database"
            return [], target
        target_fasta = str(inputs.get("target_fasta", ""))
        linked_target = _MMseqs2EasyLinsearchContract._sequence_link_name("target", target_fasta)
        return [f"ln -s {shlex.quote(target_fasta)} {shlex.quote(linked_target)}"], linked_target

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return _validate_target_source(inputs)

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
            ]
        )

    @classmethod
    def _add_search_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-s",
                str(inputs.get("sensitivity", 5.7)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
            ]
        )

    @classmethod
    def _add_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
            ]
        )

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
                "--strand",
                str(inputs.get("strand", 1)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = _MMseqs2EasyLinsearchContract._sequence_link_name("query", query_fasta)
        prelude = [f"ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)

        cmd = [
            "mmseqs",
            "easy-rbh",
            linked_query,
            target,
            f"{out}/search_results",
            f"{out}/tmp",
        ]
        _MMseqs2EasyClusterContract._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        cls._add_search_common_options(cmd, effective_inputs)
        _MMseqs2EasyClusterContract._add_align_options(cmd, effective_inputs)
        _MMseqs2EasyLinsearchContract._add_output_format_options(cmd, effective_inputs)
        cmd.extend(["--search-type", str(effective_inputs.get("search_type", 0))])
        cls._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {"1": "sam", "3": "html"}.get(str(inputs.get("format_mode", "0")), "tsv")
        return [out / f"search_results.{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "target_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": ["history", "cached"],
                        "description": "Use a target FASTA from history or a cached MMseqs2 database",
                    },
                ),
                "target_fasta": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Target FASTA file for history mode",
                        "displayOptions": {"show": {"target_source": ["history"]}},
                    },
                ),
                "target_database": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Cached MMseqs2 database directory containing database* files",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "format_fields": _MMseqs2EasyLinsearchContract.INPUT_TYPES()["optional"]["format_fields"],
                "format_mode": _MMseqs2EasyLinsearchContract.INPUT_TYPES()["optional"]["format_mode"],
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "chain_alignments": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "merge_query": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "strand": ("STRING", {"default": "1", "options": ["0", "1", "2"], "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2EasyTaxonomyContract(MMseqs2ContractNode):
    """Assign taxonomy to sequences with MMseqs2 easy-taxonomy."""

    LEGACY_NODE_ID = "mmseqs2_easy_taxonomy"
    DISPLAY_NAME = "MMseqs2 Easy Taxonomy"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Assign taxonomy to query sequences against an MMseqs2 taxonomy database using LCA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-taxonomy",
        "taxonomy assignment",
        "LCA",
        "metagenomic classification",
    ]
    RETURN_TYPES = ("TSV", "TXT", "TSV", "TXT")
    RETURN_NAMES = ("lca_results", "kraken_report", "top_hit_alignments", "top_hit_report")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = _MMseqs2EasySearchContract.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1093/bioinformatics/btab184"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btab184"]
    CITATION_TEXT = "Fast and sensitive taxonomic assignment to metagenomic contigs."
    VERSION = _MMseqs2EasySearchContract.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        database_root = str(inputs.get("target_database", ""))
        if inputs.get("download_tax_db"):
            return [
                f"cp -r {shlex.quote(database_root)}/database* .",
                f"mmseqs createtaxdb database {shlex.quote(f'{out}/tmp')}",
            ], "database"
        target = f"{database_root.rstrip('/')}/database" if database_root else "database"
        return [], target

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("target_database", "")).strip():
            return "target_database is required"
        return True

    @classmethod
    def _add_profile_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--mask-profile",
                str(inputs.get("mask_profile", 1)),
                "--e-profile",
                str(inputs.get("e_profile", 0.001)),
                "--wg",
                str(inputs.get("wg", 0)),
                "--filter-msa",
                str(inputs.get("filter_msa", 1)),
                "--filter-min-enable",
                str(inputs.get("filter_min_enable", 0)),
                "--max-seq-id",
                str(inputs.get("max_seq_id", 0.9)),
                "--qid",
                str(inputs.get("qid", "0")),
                "--qsc",
                str(inputs.get("qsc", -20)),
                "--cov",
                str(inputs.get("profile_cov", 0)),
                "--diff",
                str(inputs.get("diff", 1000)),
                "--pseudo-cnt-mode",
                str(inputs.get("pseudo_cnt_mode", 0)),
                "--exhaustive-search",
                str(inputs.get("exhaustive_search", 0)),
                "--lca-search",
                str(inputs.get("lca_search", 0)),
            ]
        )

    @classmethod
    def _add_taxonomy_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--orf-filter-e",
                str(inputs.get("orf_filter_e", 100)),
                "--orf-filter-s",
                str(inputs.get("orf_filter_s", 2)),
                "--lca-mode",
                str(inputs.get("lca_mode", 3)),
                "--majority",
                str(inputs.get("majority", 0.5)),
                "--vote-mode",
                str(inputs.get("vote_mode", 1)),
                "--tax-lineage",
                str(inputs.get("tax_lineage", 0)),
            ]
        )
        _add_if_value(cmd, "--blacklist", inputs.get("blacklist"))
        _add_if_value(cmd, "--taxon-list", inputs.get("taxon_list"))

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = _MMseqs2EasyLinsearchContract._sequence_link_name("query", query_fasta)
        prelude = [f"ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("evalue", 1)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)
        effective_inputs.setdefault("max_rejected", 5)
        effective_inputs.setdefault("max_accept", 30)

        cmd = [
            "mmseqs",
            "easy-taxonomy",
            linked_query,
            target,
            f"{out}/result",
            f"{out}/tmp",
        ]
        _MMseqs2EasyClusterContract._add_dbtype_options(cmd, effective_inputs)
        _MMseqs2EasyRBHContract._add_prefilter_options(cmd, effective_inputs)
        _MMseqs2EasyRBHContract._add_search_common_options(cmd, effective_inputs)
        _MMseqs2EasyClusterContract._add_align_options(cmd, effective_inputs)
        cls._add_profile_options(cmd, effective_inputs)
        cls._add_taxonomy_options(cmd, effective_inputs)
        cmd.extend(["--search-type", str(effective_inputs.get("search_type", 0))])
        _MMseqs2EasyRBHContract._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(_as_list(inputs.get("output_selection")))
        outputs = [out / "result_lca.tsv"]
        if "output_selection" not in inputs:
            selected = {"report"}
        if "report" in selected:
            outputs.append(out / "result_report.txt")
        if "tophit_aln" in selected:
            outputs.append(out / "result_tophit_aln.tsv")
        if "tophit_report" in selected:
            outputs.append(out / "result_tophit_report.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "database_type": (
                    "STRING",
                    {
                        "default": "amino_acid_tax",
                        "options": ["amino_acid_tax", "nucleotides_tax"],
                        "description": "Taxonomy database type: amino acid or nucleotide",
                    },
                ),
                "target_database": ("FILE", {"default": "", "description": "Cached MMseqs2 taxonomy database directory"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 1, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 5, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 30, "min": 0, "advanced": True}),
                "mask_profile": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "e_profile": ("FLOAT", {"default": 0.001, "min": 0, "advanced": True}),
                "wg": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "filter_msa": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "filter_min_enable": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "max_seq_id": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "advanced": True}),
                "qid": ("STRING", {"default": "0", "advanced": True}),
                "qsc": ("FLOAT", {"default": -20, "min": -50, "max": 100, "advanced": True}),
                "profile_cov": ("FLOAT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "diff": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "pseudo_cnt_mode": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "exhaustive_search": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "lca_search": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "orf_filter_e": ("FLOAT", {"default": 100, "min": 0, "advanced": True}),
                "orf_filter_s": ("FLOAT", {"default": 2, "min": 0, "advanced": True}),
                "lca_mode": ("STRING", {"default": "3", "options": ["1", "3", "4"]}),
                "majority": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "vote_mode": ("STRING", {"default": "1", "options": ["0", "1", "2"]}),
                "tax_lineage": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "blacklist": ("STRING", {"default": "", "advanced": True}),
                "taxon_list": ("STRING", {"default": "", "advanced": True}),
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "chain_alignments": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "merge_query": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["report"],
                        "options": ["report", "tophit_aln", "tophit_report"],
                        "list": True,
                        "description": "Additional MMseqs2 taxonomy outputs to keep",
                    },
                ),
                "download_tax_db": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MMseqs2TaxonomyAssignmentContract(MMseqs2ContractNode):
    """Run the lower-level MMseqs2 taxonomy assignment pipeline."""

    LEGACY_NODE_ID = "mmseqs2_taxonomy_assignment"
    DISPLAY_NAME = "MMseqs2 Taxonomy"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Run the fine-grained MMseqs2 taxonomy workflow with optional taxon filtering and reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "taxonomy",
        "taxonomy assignment",
        "filtertaxseqdb",
        "Kraken report",
        "Krona report",
    ]
    RETURN_TYPES = ("TSV", "TXT", "HTML")
    RETURN_NAMES = ("taxonomy_tsv", "kraken_report", "krona_report")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = _MMseqs2EasySearchContract.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1093/bioinformatics/btab184"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btab184"]
    CITATION_TEXT = "Fast and sensitive taxonomic assignment to metagenomic contigs."
    VERSION = _MMseqs2EasySearchContract.VERSION
    SHELL = True

    @classmethod
    def _database_source(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("download_tax_db"):
            return "database"
        database_root = str(inputs.get("target_database", ""))
        return f"{database_root.rstrip('/')}/database" if database_root else "database"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("target_database", "")).strip():
            return "target_database is required"
        return True

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-s",
                str(inputs.get("sensitivity", 2)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--target-search-mode",
                str(inputs.get("target_search_mode", 0)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
            ]
        )

    @classmethod
    def _add_align_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-a",
                str(inputs.get("convertalis", 0)),
                "--alignment-mode",
                str(inputs.get("alignment_mode", 1)),
                "--alignment-output-mode",
                str(inputs.get("alignment_output_mode", 0)),
                "--wrapped-scoring",
                str(inputs.get("wrapped_scoring", 0)),
                "-e",
                str(inputs.get("evalue", 1)),
                "--min-seq-id",
                str(inputs.get("min_seq_id", 0)),
                "--min-aln-len",
                str(inputs.get("min_aln_len", 0)),
                "--seq-id-mode",
                str(inputs.get("seq_id_mode", 0)),
                "--alt-ali",
                str(inputs.get("alt_ali", 0)),
                "-c",
                str(inputs.get("cov", 0)),
                "--cov-mode",
                str(inputs.get("cov_mode", 0)),
                "--max-rejected",
                str(inputs.get("max_rejected", 5)),
                "--max-accept",
                str(inputs.get("max_accept", 30)),
                "--score-bias",
                str(inputs.get("score_bias", 0)),
                "--realign",
                str(inputs.get("realign", 0)),
                "--realign-score-bias",
                str(inputs.get("realign_score_bias", -0.2)),
                "--realign-max-seqs",
                str(inputs.get("realign_max_seqs", 2147483647)),
                "--corr-score-weight",
                str(inputs.get("corr_score_weight", 0)),
                "--exhaustive-search-filter",
                str(inputs.get("exhaustive_search_filter", 0)),
            ]
        )

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        _MMseqs2EasyTaxonomyContract._add_taxonomy_options(cmd, inputs)
        cmd.extend(
            [
                "--rescore-mode",
                str(inputs.get("rescore_mode", 0)),
                "--allow-deletion",
                str(inputs.get("allow_deletion", 0)),
                "--min-length",
                str(inputs.get("min_length", 30)),
                "--max-length",
                str(inputs.get("max_length", 32734)),
                "--max-gaps",
                str(inputs.get("max_gaps", 2147483647)),
                "--contig-start-mode",
                str(inputs.get("contig_start_mode", 2)),
                "--contig-end-mode",
                str(inputs.get("contig_end_mode", 2)),
                "--orf-start-mode",
                str(inputs.get("orf_start_mode", 1)),
                "--forward-frames",
                str(inputs.get("forward_frames", "1,2,3")),
                "--reverse-frames",
                str(inputs.get("reverse_frames", "1,2,3")),
                "--translation-table",
                str(inputs.get("translation_table", 1)),
                "--translate",
                str(inputs.get("translate", 0)),
                "--use-all-table-starts",
                str(inputs.get("use_all_table_starts", 0)),
                "--id-offset",
                str(inputs.get("id_offset", 0)),
                "--sequence-overlap",
                str(inputs.get("sequence_overlap", 0)),
                "--sequence-split-mode",
                str(inputs.get("sequence_split_mode", 1)),
                "--headers-split-mode",
                str(inputs.get("headers_split_mode", 0)),
                "--search-type",
                str(inputs.get("search_type", 3 if inputs.get("database_type") == "nucleotides_tax" else 0)),
                "--prefilter-mode",
                str(inputs.get("prefilter_mode", 0)),
            ]
        )

    @classmethod
    def _add_common_and_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
            ]
        )

    @classmethod
    def _taxonomy_command(cls, inputs: dict[str, Any], out: str, taxonomy_database: str) -> list[str]:
        cmd = [
            "mmseqs",
            "taxonomy",
            f"{out}/sequenceDB",
            taxonomy_database,
            f"{out}/output_taxonomy",
            f"{out}/tmp",
        ]
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
        cls._add_prefilter_options(cmd, inputs)
        cls._add_align_options(cmd, inputs)
        _MMseqs2EasyTaxonomyContract._add_profile_options(cmd, inputs)
        cls._add_misc_options(cmd, inputs)
        cls._add_common_and_expert_options(cmd, inputs)
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        commands = [
            shlex.join(["ln", "-s", "-f", input_fasta, "input"]),
            shlex.join(
                [
                    "mmseqs",
                    "createdb",
                    "input",
                    f"{out}/sequenceDB",
                    "--dbtype",
                    str(inputs.get("dbtype", 0)),
                    "--shuffle",
                    str(inputs.get("shuffle", 1)),
                ]
            ),
        ]

        if inputs.get("download_tax_db"):
            database_root = str(inputs.get("target_database", ""))
            commands.extend(
                [
                    f"cp -r {shlex.quote(database_root)}/database* .",
                    shlex.join(["mmseqs", "createtaxdb", "database", f"{out}/tmp"]),
                ]
            )

        taxonomy_database = cls._database_source(inputs)
        filter_taxon_list = str(inputs.get("filter_taxon_list", ""))
        if filter_taxon_list:
            filtered_database = f"{out}/database_filtered"
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "filtertaxseqdb",
                        taxonomy_database,
                        filtered_database,
                        "--taxon-list",
                        filter_taxon_list,
                    ]
                )
            )
            taxonomy_database = filtered_database

        commands.append(shlex.join(cls._taxonomy_command(inputs, out, taxonomy_database)))
        commands.append(
            shlex.join(
                [
                    "mmseqs",
                    "createtsv",
                    f"{out}/sequenceDB",
                    f"{out}/output_taxonomy",
                    f"{out}/taxo_result.tsv",
                    "--first-seq-as-repr",
                    str(inputs.get("first_seq_as_repr", 0)),
                    "--target-column",
                    str(inputs.get("target_column", 1)),
                    "--full-header",
                    str(inputs.get("full_header", 0)),
                    "--idx-seq-src",
                    str(inputs.get("idx_seq_src", 0)),
                    "--threads",
                    str(inputs.get("threads", 1)),
                ]
            )
        )

        if inputs.get("keep_kraken_report", True):
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "taxonomyreport",
                        taxonomy_database,
                        f"{out}/output_taxonomy",
                        f"{out}/taxo_result.txt",
                        "--report-mode",
                        "0",
                        "--threads",
                        str(inputs.get("threads", 1)),
                    ]
                )
            )
        if inputs.get("keep_krona_report", True):
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "taxonomyreport",
                        taxonomy_database,
                        f"{out}/output_taxonomy",
                        f"{out}/taxo_result.html",
                        "--report-mode",
                        "1",
                        "--threads",
                        str(inputs.get("threads", 1)),
                    ]
                )
            )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "taxo_result.tsv"]
        if inputs.get("keep_kraken_report", True):
            outputs.append(out / "taxo_result.txt")
        if inputs.get("keep_krona_report", True):
            outputs.append(out / "taxo_result.html")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        taxonomy_optional = dict(_MMseqs2EasyTaxonomyContract.INPUT_TYPES()["optional"])
        taxonomy_optional.update(
            {
                "sensitivity": ("FLOAT", {"default": 2, "min": 1, "max": 7.5}),
                "target_search_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1"], "advanced": True},
                ),
                "alignment_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1", "2", "3", "4"], "advanced": True},
                ),
                "exhaustive_search_filter": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1, "advanced": True},
                ),
                "filter_taxon_list": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional taxon list for pre-filtering the taxonomy database",
                    },
                ),
                "rescore_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True},
                ),
                "allow_deletion": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_length": ("INT", {"default": 30, "min": 0, "advanced": True}),
                "max_length": ("INT", {"default": 32734, "min": 0, "advanced": True}),
                "max_gaps": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "contig_start_mode": (
                    "STRING",
                    {"default": "2", "options": ["0", "1", "2"], "advanced": True},
                ),
                "contig_end_mode": (
                    "STRING",
                    {"default": "2", "options": ["0", "1", "2"], "advanced": True},
                ),
                "orf_start_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1", "2"], "advanced": True},
                ),
                "forward_frames": ("STRING", {"default": "1,2,3", "advanced": True}),
                "reverse_frames": ("STRING", {"default": "1,2,3", "advanced": True}),
                "translation_table": (
                    "STRING",
                    {
                        "default": "1",
                        "options": [
                            "1",
                            "2",
                            "3",
                            "4",
                            "5",
                            "6",
                            "9",
                            "10",
                            "11",
                            "12",
                            "13",
                            "14",
                            "15",
                            "16",
                            "21",
                            "22",
                            "23",
                            "24",
                            "25",
                            "26",
                            "27",
                            "28",
                            "29",
                            "30",
                            "31",
                        ],
                        "advanced": True,
                    },
                ),
                "translate": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "use_all_table_starts": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1, "advanced": True},
                ),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sequence_overlap": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sequence_split_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1"], "advanced": True},
                ),
                "headers_split_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1"], "advanced": True},
                ),
                "prefilter_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2"], "advanced": True},
                ),
                "first_seq_as_repr": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "target_column": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "full_header": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "idx_seq_src": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2"], "advanced": True},
                ),
                "keep_kraken_report": (
                    "BOOLEAN",
                    {"default": True, "description": "Generate a Kraken-style taxonomy report"},
                ),
                "keep_krona_report": (
                    "BOOLEAN",
                    {"default": True, "description": "Generate a Krona HTML taxonomy report"},
                ),
            }
        )
        taxonomy_optional.pop("output_selection", None)
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "database_type": (
                    "STRING",
                    {
                        "default": "amino_acid_tax",
                        "options": ["amino_acid_tax", "nucleotides_tax"],
                        "description": "Taxonomy database type: amino acid or nucleotide",
                    },
                ),
                "target_database": ("FILE", {"default": "", "description": "Cached MMseqs2 taxonomy database directory"}),
            },
            "optional": taxonomy_optional,
            "hidden": {"output": ("STRING", {})},
        }
