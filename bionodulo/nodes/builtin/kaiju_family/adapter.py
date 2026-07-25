"""Shared Kaiju contracts for focused protein taxonomy nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.taxonomy_family.protein_contracts import ValidatedCommandContract


KAIJU_GIT_COMMIT = "55a0a14f454f86f09df6d424e39847d9ddc4ab7e"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"


class KaijuContractNode(ValidatedCommandContract):
    """Kaiju 1.10.1 plus the exact Galaxy IUC wrapper authority."""

    GIT_URL = "https://github.com/bioinformatics-centre/kaiju.git"
    GIT_COMMIT = KAIJU_GIT_COMMIT
    SOURCE_URL = f"https://github.com/bioinformatics-centre/kaiju/tree/{KAIJU_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "kaiju==1.10.1"
    GALAXY_WRAPPER_VERSION = "1.10.1+galaxy2"
    GALAXY_WRAPPER_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
    GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    GALAXY_WRAPPER_SOURCE_URL = (
        f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/kaiju"
    )
    EXIT_SEMANTICS = "Kaiju or wrapper validation failures must produce a non-zero command result."


class _KaijuContract(KaijuContractNode):
    """Classify metagenomic reads with the Galaxy IUC Kaiju wrapper behavior."""

    LEGACY_NODE_ID = "kaiju"
    DISPLAY_NAME = "Kaiju"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Classify metagenomic reads or report best matching database sequences with Kaiju."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "taxonomic classification",
        "metagenomics",
        "protein-level classifier",
        "best matching sequence",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("taxonomic_classification", "best_matching_sequences")
    REQUIRED_EXECUTABLES = ["kaiju", "kaijup", "kaijux"]
    DOCUMENTATION_URL = "https://github.com/bioinformatics-centre/kaiju"
    CITATION_DOIS = ["10.1038/ncomms11257"]
    CITATION_URLS = [f"{DOI_URL}10.1038/ncomms11257"]
    CITATION_TEXT = "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    VERSION = "1.10.1"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        input_type = str(inputs.get("input_type", "single") or "single")
        normalized.setdefault("reads", "unused")
        normalized.setdefault("reads_1", "unused")
        normalized.setdefault("reads_2", "unused")
        validation = super().VALIDATE_INPUTS(normalized)
        if validation is not True:
            return validation
        if input_type == "single" and not str(inputs.get("reads", "")).strip():
            return "reads is required when input_type=single"
        if input_type == "paired" and not all(
            str(inputs.get(name, "")).strip() for name in ("reads_1", "reads_2")
        ):
            return "reads_1 and reads_2 are required when input_type=paired"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        task = str(inputs.get("task", "tax"))
        protein = bool(inputs.get("protein", False))
        reference = str(inputs.get("reference_database", "")).rstrip("/")

        if task == "tax":
            cmd = [
                "kaiju",
                "-t",
                f"{reference}/nodes.dmp",
                "-o",
                f"{out}/kaiju_taxonomy.tsv",
            ]
        else:
            cmd = [
                "kaijup" if protein else "kaijux",
                "-o",
                f"{out}/kaiju_best_sequences.tsv",
            ]

        cmd.extend(["-f", f"{reference}/database.fmi"])
        if str(inputs.get("input_type", "single")) == "paired":
            cmd.extend(["-i", str(inputs.get("reads_1", "")), "-j", str(inputs.get("reads_2", ""))])
        else:
            cmd.extend(["-i", str(inputs.get("reads", ""))])

        cmd.extend(["-z", str(inputs.get("threads", 1))])
        if protein:
            cmd.append("-p")
        cmd.append("-x" if inputs.get("low_complexity", True) else "-X")

        mode = str(inputs.get("mode", "greedy"))
        cmd.extend(["-a", mode])
        if mode == "greedy":
            cmd.extend(
                [
                    "-e",
                    str(inputs.get("mismatches", 3)),
                    "-m",
                    str(inputs.get("match_length", 11)),
                    "-s",
                    str(inputs.get("match_score", 65)),
                    "-E",
                    str(inputs.get("evalue", 0.01)),
                ]
            )
        if inputs.get("verbose", False):
            cmd.append("-v")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("task", "tax")) == "best_sequence":
            return [out / "kaiju_best_sequences.tsv"]
        return [out / "kaiju_taxonomy.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "paired"], "description": "Single or paired read inputs"},
                ),
                "reads": ("FASTQ", {"description": "Single-end FASTA/FASTQ reads"}),
                "reads_1": ("FASTQ", {"description": "Forward reads for paired input"}),
                "reads_2": ("FASTQ", {"description": "Reverse reads for paired input"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing database.fmi and nodes.dmp"},
                ),
            },
            "optional": {
                "task": (
                    "STRING",
                    {"default": "tax", "options": ["tax", "best_sequence"], "description": "Taxonomic classification or best sequence lookup"},
                ),
                "protein": (
                    "BOOLEAN",
                    {"default": False, "description": "Input sequences are protein sequences"},
                ),
                "low_complexity": (
                    "BOOLEAN",
                    {"default": True, "description": "Enable SEG low-complexity filtering"},
                ),
                "mode": (
                    "STRING",
                    {"default": "greedy", "options": ["greedy", "mem"], "description": "Kaiju MEM or greedy search mode"},
                ),
                "mismatches": ("INT", {"default": 3, "min": 0, "description": "Greedy-mode mismatches allowed"}),
                "match_length": ("INT", {"default": 11, "min": 1, "description": "Greedy-mode minimum match length"}),
                "match_score": ("INT", {"default": 65, "min": 1, "description": "Greedy-mode minimum match score"}),
                "evalue": ("FLOAT", {"default": 0.01, "min": 0, "description": "Greedy-mode minimum E-value"}),
                "verbose": (
                    "BOOLEAN",
                    {"default": False, "description": "Include additional classification columns"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KaijuAddTaxonNamesContract(KaijuContractNode):
    """Append taxon names or taxonomic paths to Kaiju output tables."""

    LEGACY_NODE_ID = "kaiju_add_taxon_names"
    DISPLAY_NAME = "Kaiju Add Taxon Names"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Append taxon names or taxonomic paths to Kaiju output tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju-addTaxonNames",
        "taxon names",
        "Print full taxon path",
        "readable taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("taxon_names_table",)
    REQUIRED_EXECUTABLES = ["kaiju-addTaxonNames"]
    DOCUMENTATION_URL = _KaijuContract.DOCUMENTATION_URL
    CITATION_DOIS = _KaijuContract.CITATION_DOIS
    CITATION_URLS = _KaijuContract.CITATION_URLS
    CITATION_TEXT = _KaijuContract.CITATION_TEXT
    VERSION = _KaijuContract.VERSION

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju-addTaxonNames",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-i",
            str(inputs.get("kaiju_table", "")),
            "-o",
            f"{out}/kaiju_taxon_names.tsv",
        ]
        if inputs.get("exclude_unclassified", False):
            cmd.append("-u")
        rank = str(inputs.get("rank", ""))
        if rank:
            cmd.extend(["-r", rank])
        if inputs.get("print_full_taxon_path", False):
            cmd.append("-p")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_taxon_names.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not count unclassified reads in percentage totals"},
                ),
                "rank": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "phylum", "class", "order", "family", "genus", "species"],
                        "description": "Optional rank whose taxon name should be appended",
                    },
                ),
                "print_full_taxon_path": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Print the full taxon path instead of a rank-specific taxon name",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _Kaiju2KronaContract(KaijuContractNode):
    """Convert Kaiju classifications into a Krona import table."""

    LEGACY_NODE_ID = "kaiju2krona"
    DISPLAY_NAME = "Kaiju2Krona"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert Kaiju output into a Krona-compatible taxonomy import table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju2krona",
        "Krona import",
        "selected ranks",
        "taxonomy sunburst",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("krona_import_tsv",)
    REQUIRED_EXECUTABLES = ["kaiju2krona"]
    DOCUMENTATION_URL = _KaijuContract.DOCUMENTATION_URL
    CITATION_DOIS = _KaijuContract.CITATION_DOIS
    CITATION_URLS = _KaijuContract.CITATION_URLS
    CITATION_TEXT = _KaijuContract.CITATION_TEXT
    VERSION = _KaijuContract.VERSION

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju2krona",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-i",
            str(inputs.get("kaiju_table", "")),
            "-o",
            f"{out}/kaiju_krona.tsv",
        ]
        if inputs.get("include_unclassified", False):
            cmd.append("-u")
        selected_ranks = ".".join(_as_list(inputs.get("selected_ranks")))
        if selected_ranks:
            cmd.extend(["-l", selected_ranks])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_krona.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        ranks = ["superkingdom", "phylum", "class", "order", "family", "genus", "species"]
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "include_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Include count for unclassified reads"},
                ),
                "selected_ranks": (
                    "STRING",
                    {
                        "default": [],
                        "options": ranks,
                        "multiple": True,
                        "description": "Taxonomic ranks to print as dot-delimited Krona paths",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KaijuMergeOutputsContract(KaijuContractNode):
    """Merge Kaiju and Kraken-style classification tables."""

    LEGACY_NODE_ID = "kaiju_merge_outputs"
    DISPLAY_NAME = "Kaiju Merge Outputs"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Merge Kaiju and Kraken-style classification output tables with conflict resolution."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju-mergeOutputs",
        "merge classifications",
        "conflict resolution",
        "Kraken table",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("merged_classification",)
    REQUIRED_EXECUTABLES = ["kaiju-mergeOutputs"]
    DOCUMENTATION_URL = _KaijuContract.DOCUMENTATION_URL
    CITATION_DOIS = _KaijuContract.CITATION_DOIS
    CITATION_URLS = _KaijuContract.CITATION_URLS
    CITATION_TEXT = _KaijuContract.CITATION_TEXT
    VERSION = _KaijuContract.VERSION
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        conflict_mode = str(inputs.get("conflict_mode", "lca"))
        cmd = [
            "kaiju-mergeOutputs",
            "-i",
            "kaiju.out.sort",
            "-j",
            "kraken.out.sort",
            "-o",
            f"{out}/kaiju_merged_outputs.tsv",
            "-c",
            conflict_mode,
        ]
        if conflict_mode in {"lca", "lowest"}:
            reference = str(inputs.get("reference_database", "")).rstrip("/")
            cmd.extend(["-t", f"{reference}/nodes.dmp"])
        if inputs.get("use_score", False):
            cmd.append("-s")
        cmd.append("-v")

        commands = [
            f"sort -k2,2 {shlex.quote(str(inputs.get('kaiju_table', '')))} > kaiju.out.sort",
            f"sort -k2,2 {shlex.quote(str(inputs.get('kraken_table', '')))} > kraken.out.sort",
            shlex.join(cmd),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_merged_outputs.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table sorted by read identifier before merging"}),
                "kraken_table": (
                    "TSV",
                    {"description": "Second classification table in Kaiju/Kraken column format"},
                ),
            },
            "optional": {
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp for LCA conflict modes"},
                ),
                "conflict_mode": (
                    "STRING",
                    {
                        "default": "lca",
                        "options": ["1", "2", "lca", "lowest"],
                        "description": "Resolve conflicting taxon IDs from the first input, second input, LCA, or lowest lineage match",
                    },
                ),
                "use_score": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the fourth-column classification score to prefer better-scoring taxa"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
