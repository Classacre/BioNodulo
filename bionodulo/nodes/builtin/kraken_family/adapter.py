"""Shared Centrifuge and Kraken contracts for focused taxonomy nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.taxonomy_family.protein_contracts import ValidatedCommandContract


CENTRIFUGE_GIT_COMMIT = "77115a711a17ad3d59d3c6f36346012b23fc461a"
KRAKEN_GIT_COMMIT = "e343539a12c3ad5afd38b3e30a7ed6db58c8d2c9"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"


class CentrifugeContractNode(ValidatedCommandContract):
    """Centrifuge 1.0.4-beta semantics pinned to the released source tree."""

    GIT_URL = "https://github.com/DaehwanKimLab/centrifuge.git"
    GIT_COMMIT = CENTRIFUGE_GIT_COMMIT
    SOURCE_URL = f"https://github.com/DaehwanKimLab/centrifuge/tree/{CENTRIFUGE_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "centrifuge==1.0.4_beta"
    EXIT_SEMANTICS = "Centrifuge input and classification failures must produce a non-zero command result."


class KrakenContractNode(ValidatedCommandContract):
    """Kraken 1.1.1 plus the exact Galaxy 1.3.1 wrapper authority."""

    GIT_URL = "https://github.com/DerrickWood/kraken.git"
    GIT_COMMIT = KRAKEN_GIT_COMMIT
    SOURCE_URL = f"https://github.com/DerrickWood/kraken/tree/{KRAKEN_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "kraken==1.1.1"
    GALAXY_WRAPPER_VERSION = "1.3.1"
    GALAXY_WRAPPER_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
    GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    GALAXY_WRAPPER_SOURCE_URL = (
        f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tool_collections/kraken"
    )
    EXIT_SEMANTICS = "Kraken or wrapper validation failures must produce a non-zero command result."


class _CentrifugeContract(CentrifugeContractNode):
    """Classify metagenomic reads with Centrifuge."""

    LEGACY_NODE_ID = "centrifuge"
    DISPLAY_NAME = "Centrifuge"
    REQUIRED_CONDA_PACKAGES = ["centrifuge"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Read-based metagenome characterization with Centrifuge."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Centrifuge",
        "metagenomic classification",
        "taxonomic classification",
        "read-based metagenomics",
        "SRA accession",
        "FM index",
    ]
    RETURN_TYPES = ("TSV", "SAM", "TSV")
    RETURN_NAMES = ("tabular_output", "sam_output", "report")
    REQUIRED_EXECUTABLES = ["centrifuge"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/centrifuge/"
    CITATION_DOIS = ["10.1101/gr.210641.116"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.210641.116"]
    CITATION_TEXT = "Centrifuge: rapid and sensitive classification of metagenomic sequences."
    VERSION = "1.0.4_beta"
    SHELL = True

    _DEFAULT_TAB_COLUMNS = "readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches"
    _TAB_COLUMNS = {
        "readID",
        "seqID",
        "taxID",
        "score",
        "2ndBestScore",
        "hitLength",
        "queryLength",
        "numMatches",
    }

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _paired_values(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        raw_paired_values = inputs.get("paired_reads")
        if raw_paired_values is None or raw_paired_values == "":
            paired_values: list[Any] = []
        elif (
            isinstance(raw_paired_values, (list, tuple))
            and len(raw_paired_values) >= 2
            and not isinstance(raw_paired_values[0], (dict, list, tuple))
        ):
            paired_values = [raw_paired_values]
        elif isinstance(raw_paired_values, (list, tuple)):
            paired_values = list(raw_paired_values)
        else:
            paired_values = [raw_paired_values]
        pairs: list[tuple[str, str]] = []
        for value in paired_values:
            if isinstance(value, dict):
                forward = value.get("forward", value.get("input_1", value.get("r1", "")))
                reverse = value.get("reverse", value.get("input_2", value.get("r2", "")))
                pairs.append((str(forward), str(reverse)))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                pairs.append((str(value[0]), str(value[1])))
            elif value:
                pair_root = str(value).rstrip("/")
                pairs.append((f"{pair_root}/forward", f"{pair_root}/reverse"))
        return pairs

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return "centrifuge_output.sam" if str(inputs.get("out_fmt", "tab")) == "sam" else "centrifuge_output.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Centrifuge database is required"
        if not _as_list(inputs.get("unpaired_reads")) and not cls._paired_values(inputs) and not str(inputs.get("sra", "")).strip():
            return "At least one unpaired read, paired read collection, or SRA accession is required"
        if inputs.get("norc", False) and inputs.get("nofw", False):
            return "Centrifuge cannot disable both forward and reverse-complement mapping"
        try:
            min_hitlen = int(inputs.get("min_hitlen", 22))
        except (TypeError, ValueError):
            return "Minimum hit length must be an integer"
        if min_hitlen < 16:
            return "Minimum hit length must be at least 16"

        columns = str(inputs.get("tab_fmt_cols", cls._DEFAULT_TAB_COLUMNS))
        for column in columns.split(","):
            if column and column not in cls._TAB_COLUMNS:
                return f"Unsupported Centrifuge tabular output column: {column}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "centrifuge",
            "--out-fmt",
            str(inputs.get("out_fmt", "tab")),
            "--tab-fmt-cols",
            str(inputs.get("tab_fmt_cols", cls._DEFAULT_TAB_COLUMNS)),
            "--threads",
            str(inputs.get("threads", 1)),
        ]

        for key, flag in (
            ("skip", "--skip"),
            ("upto", "--upto"),
            ("trim5", "--trim5"),
            ("trim3", "--trim3"),
        ):
            _add_if_value(cmd, flag, inputs.get(key))

        for key, flag in (
            ("ignore_quals", "--ignore-quals"),
            ("nofw", "--nofw"),
            ("norc", "--norc"),
            ("non_deterministic", "--non-deterministic"),
        ):
            if inputs.get(key, False):
                cmd.append(flag)

        _add_if_value(cmd, "--seed", inputs.get("seed"))
        cmd.extend(["--min-hitlen", str(inputs.get("min_hitlen", 22))])
        _add_if_value(cmd, "--min-totallen", inputs.get("min_totallen"))
        _add_if_value(cmd, "--host-taxids", inputs.get("host_taxids"))
        _add_if_value(cmd, "--exclude-taxids", inputs.get("exclude_taxids"))
        cmd.extend(["-x", str(inputs.get("db", ""))])

        for read_path in _as_list(inputs.get("unpaired_reads")):
            cmd.extend(["-U", read_path])
        for forward, reverse in cls._paired_values(inputs):
            cmd.extend(["-1", forward, "-2", reverse])
        _add_if_value(cmd, "--sra-acc", inputs.get("sra"))

        cmd.extend(
            [
                "-S",
                cls._out_path(inputs, cls._output_filename(inputs)),
                "--report-file",
                cls._out_path(inputs, "centrifuge_report.tsv"),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / cls._output_filename(inputs),
            out / "centrifuge_report.tsv",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": (
                    "DIRECTORY",
                    {"description": "Centrifuge index filename prefix or database directory"},
                ),
            },
            "optional": {
                "unpaired_reads": (
                    "FASTQ",
                    {"default": [], "multiple": True, "description": "One or more unpaired FASTQ read files"},
                ),
                "paired_reads": (
                    "FASTQ_LIST",
                    {"default": [], "multiple": True, "description": "One or more paired read collections"},
                ),
                "sra": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SRA accessions, e.g. SRR353653,SRR353654"},
                ),
                "out_fmt": (
                    "STRING",
                    {"default": "tab", "options": ["tab", "sam"], "description": "Classification output format"},
                ),
                "tab_fmt_cols": (
                    "STRING",
                    {
                        "default": cls._DEFAULT_TAB_COLUMNS,
                        "description": "Comma-separated output columns for tabular Centrifuge output",
                    },
                ),
                "skip": ("INT", {"default": "", "min": 0, "description": "Initial reads or read pairs to skip"}),
                "upto": ("INT", {"default": "", "min": 0, "description": "Stop after this many reads or read pairs"}),
                "trim5": ("INT", {"default": "", "min": 0, "description": "Trim bases from the 5 prime end"}),
                "trim3": ("INT", {"default": "", "min": 0, "description": "Trim bases from the 3 prime end"}),
                "ignore_quals": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat all quality values as Phred 30"},
                ),
                "nofw": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not align the forward strand"},
                ),
                "norc": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not align the reverse-complement strand"},
                ),
                "seed": ("INT", {"default": "", "min": 0, "advanced": True}),
                "non_deterministic": (
                    "BOOLEAN",
                    {"default": False, "description": "Use non-deterministic random seeding", "advanced": True},
                ),
                "min_hitlen": (
                    "INT",
                    {"default": 22, "min": 16, "description": "Minimum length of partial hits"},
                ),
                "min_totallen": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum summed length of partial hits per read"},
                ),
                "host_taxids": (
                    "STRING",
                    {"default": "", "description": "Comma-separated host taxonomic IDs", "advanced": True},
                ),
                "exclude_taxids": (
                    "STRING",
                    {"default": "", "description": "Comma-separated taxonomic IDs to exclude", "advanced": True},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakenContract(KrakenContractNode):
    """Assign taxonomy to reads with classic Kraken."""

    LEGACY_NODE_ID = "kraken"
    DISPLAY_NAME = "Kraken"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assign taxonomic labels to sequencing reads with Kraken."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken",
        "taxonomic classification",
        "metagenomics",
        "k-mer exact alignment",
        "classified reads",
        "unclassified reads",
        "quick mode",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "FASTQ", "FASTQ")
    RETURN_NAMES = ("classification", "classified_reads", "unclassified_reads")
    REQUIRED_EXECUTABLES = ["kraken"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.1.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/classification.kraken"

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "")).lower()
        if input_format in {"fasta", "fastq"}:
            return input_format

        paths = [
            str(inputs.get("input_sequences", "")),
            str(inputs.get("forward_input", "")),
            str(inputs.get("reverse_input", "")),
        ]
        raw_pair = inputs.get("input_pair")
        if isinstance(raw_pair, dict):
            paths.extend([str(raw_pair.get("forward", "")), str(raw_pair.get("reverse", ""))])
        elif isinstance(raw_pair, (list, tuple)):
            paths.extend(str(value) for value in raw_pair)
        if any(Path(path).suffix.lower() in {".fa", ".fasta", ".fna"} for path in paths if path):
            return "fasta"
        return "fastq"

    @classmethod
    def _paired_collection(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        pair = inputs.get("input_pair")
        if isinstance(pair, dict):
            return str(pair.get("forward", "")), str(pair.get("reverse", ""))
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return str(pair[0]), str(pair[1])
        if pair:
            root = str(pair).rstrip("/")
            return f"{root}/forward", f"{root}/reverse"
        return "", ""

    @classmethod
    def _read_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = str(inputs.get("input_type", "single"))
        if input_type == "paired":
            return [str(inputs.get("forward_input", "")), str(inputs.get("reverse_input", ""))]
        if input_type == "paired_collection":
            return list(cls._paired_collection(inputs))
        return [str(inputs.get("input_sequences", ""))]

    @classmethod
    def _split_suffix(cls, inputs: dict[str, Any]) -> str:
        return "fasta" if cls._input_format(inputs) == "fasta" else "fastq"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        input_type = str(inputs.get("input_type", "single"))
        if input_type not in {"single", "paired", "paired_collection"}:
            return "input_type must be one of: single, paired, paired_collection"
        if input_type == "paired":
            if not str(inputs.get("forward_input", "")).strip() or not str(inputs.get("reverse_input", "")).strip():
                return "Forward and reverse reads are required for paired input"
        elif input_type == "paired_collection":
            forward, reverse = cls._paired_collection(inputs)
            if not forward or not reverse:
                return "Paired collection input is required"
        elif not str(inputs.get("input_sequences", "")).strip():
            return "Single-end input sequences are required"

        if str(inputs.get("quick", "no")) == "yes":
            try:
                min_hits = int(inputs.get("min_hits", 1))
            except (TypeError, ValueError):
                return "Quick mode min_hits must be an integer"
            if min_hits < 1:
                return "Quick mode min_hits must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get("input_type", "single"))
        input_format = cls._input_format(inputs)
        cmd = [
            "kraken",
            "--threads",
            str(inputs.get("threads", 1)),
            "--db",
            str(inputs.get("db", "")),
        ]
        if inputs.get("only_classified_output", False):
            cmd.append("--only-classified-output")
        if str(inputs.get("quick", "no")) == "yes":
            cmd.extend(["--quick", "--min-hits", str(inputs.get("min_hits", 1))])
        cmd.append("--fastq-input" if input_format == "fastq" else "--fasta-input")
        cmd.extend(read for read in cls._read_inputs(inputs) if read)
        if input_type in {"paired", "paired_collection"}:
            cmd.append("--paired")
            if inputs.get("check_names", False):
                cmd.append("--check-names")
        if inputs.get("split_reads", False):
            suffix = cls._split_suffix(inputs)
            cmd.extend(
                [
                    "--classified-out",
                    f"{_out(inputs)}/classified_reads.{suffix}",
                    "--unclassified-out",
                    f"{_out(inputs)}/unclassified_reads.{suffix}",
                ]
            )
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "classification.kraken"]
        if inputs.get("split_reads", False):
            suffix = cls._split_suffix(inputs)
            outputs.extend([out / f"classified_reads.{suffix}", out / f"unclassified_reads.{suffix}"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired", "paired_collection"],
                        "description": "Single reads, paired reads, or a paired collection",
                    },
                ),
                "db": ("DIRECTORY", {"description": "Kraken database directory"}),
                "input_sequences": (
                    "FASTQ",
                    {
                        "description": "Single-end FASTA or FASTQ reads",
                        "displayOptions": {"show": {"input_type": ["single"]}},
                    },
                ),
            },
            "optional": {
                "forward_input": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Forward reads for paired input",
                        "displayOptions": {"show": {"input_type": ["paired"]}},
                    },
                ),
                "reverse_input": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Reverse reads for paired input",
                        "displayOptions": {"show": {"input_type": ["paired"]}},
                    },
                ),
                "input_pair": (
                    "FASTQ_LIST",
                    {
                        "default": [],
                        "description": "Paired read collection as [forward, reverse] or mapping",
                        "displayOptions": {"show": {"input_type": ["paired_collection"]}},
                    },
                ),
                "input_format": (
                    "STRING",
                    {"default": "fastq", "options": ["fastq", "fasta"], "description": "Input read format"},
                ),
                "split_reads": (
                    "BOOLEAN",
                    {"default": False, "description": "Write classified and unclassified read outputs"},
                ),
                "quick": (
                    "STRING",
                    {"default": "no", "options": ["no", "yes"], "description": "Enable Kraken quick operation"},
                ),
                "min_hits": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of hits required for classification in quick mode",
                        "displayOptions": {"show": {"quick": ["yes"]}},
                    },
                ),
                "only_classified_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Print no Kraken output for unclassified sequences"},
                ),
                "check_names": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Verify paired read names match",
                        "displayOptions": {"show": {"input_type": ["paired", "paired_collection"]}},
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakenReportContract(KrakenContractNode):
    """Generate a classic Kraken taxonomy report."""

    LEGACY_NODE_ID = "kraken_report"
    DISPLAY_NAME = "Kraken Report"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate a tabular sample report from classic Kraken classification output."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Report",
        "kraken-report",
        "sample report",
        "taxonomy summary",
        "classification report",
        "NCBI taxonomy ID",
    ]
    RETURN_TYPES = ("KRAKEN_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["kraken-report"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/kraken_report.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("kraken_output", "")).strip():
            return "Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-report",
            "--db",
            str(inputs.get("db", "")),
            str(inputs.get("kraken_output", "")),
        ]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kraken_report.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kraken_output": (
                    "KRAKEN_OUTPUT",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class _KrakenFilterContract(KrakenContractNode):
    """Filter classic Kraken classification output by confidence threshold."""

    LEGACY_NODE_ID = "kraken_filter"
    DISPLAY_NAME = "Kraken Filter"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Filter classic Kraken classification output by confidence score."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Filter",
        "kraken-filter",
        "confidence threshold",
        "classification filter",
        "taxonomy confidence",
        "unclassified",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT",)
    RETURN_NAMES = ("filtered_output",)
    REQUIRED_EXECUTABLES = ["kraken-filter"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/filtered_output.kraken"

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> float:
        return float(inputs.get("threshold", 0))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("input", "")).strip():
            return "Kraken classification output is required"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return "Confidence threshold must be a number between 0 and 1"
        if not 0 <= threshold <= 1:
            return "Confidence threshold must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-filter",
            "--db",
            str(inputs.get("db", "")),
            "--threshold",
            str(inputs.get("threshold", 0)),
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "filtered_output.kraken"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "KRAKEN_OUTPUT",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "description": "Confidence threshold between 0 and 1",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakenTranslateContract(KrakenContractNode):
    """Convert classic Kraken taxonomy IDs to lineage names."""

    LEGACY_NODE_ID = "kraken_translate"
    DISPLAY_NAME = "Kraken Translate"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert Kraken taxonomy IDs into taxonomic lineage names."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Translate",
        "kraken-translate",
        "taxonomy labels",
        "lineage names",
        "MPA format",
        "standard ranks",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("translated",)
    REQUIRED_EXECUTABLES = ["kraken-translate"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/translated.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("input", "")).strip():
            return "Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-translate",
            "--db",
            str(inputs.get("db", "")),
        ]
        if inputs.get("mpa_format", False):
            cmd.append("--mpa-format")
        cmd.append(str(inputs.get("input", "")))
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "translated.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "TSV",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "mpa_format": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Restrict labels to standard rank assignments in MPA format",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakenMpaReportContract(KrakenContractNode):
    """Generate a classic Kraken MPA-style multi-sample report."""

    LEGACY_NODE_ID = "kraken_mpa_report"
    DISPLAY_NAME = "Kraken MPA Report"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Summarize classic Kraken classifications across taxonomic ranks for multiple samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken MPA Report",
        "kraken-mpa-report",
        "multiple samples",
        "taxonomic ranks",
        "MetaPhlAn style",
        "show zeros",
        "header line",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_report",)
    REQUIRED_EXECUTABLES = ["kraken-mpa-report"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_report.tsv"

    @classmethod
    def _sample_names(cls, classifications: list[str], identifiers: list[str]) -> list[str]:
        names: list[str] = []
        for index, classification in enumerate(classifications):
            if index < len(identifiers) and identifiers[index]:
                name_base = str(identifiers[index]).replace("/", "-").replace("\t", "-")
            else:
                name_base = classification
            name = name_base
            duplicate_index = 1
            while name in names:
                name = f"{name_base}_{duplicate_index}"
                duplicate_index += 1
            names.append(name)
        return names

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not _as_list(inputs.get("classification")):
            return "At least one Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        classifications = _as_list(inputs.get("classification"))
        names = cls._sample_names(classifications, _as_list(inputs.get("element_identifiers")))
        setup = [
            f"ln -s {shlex.quote(classification)} {shlex.quote(name)}"
            for classification, name in zip(classifications, names)
            if classification != name
        ]
        cmd = [
            "kraken-mpa-report",
            "--db",
            str(inputs.get("db", "")),
            *names,
        ]
        if inputs.get("show_zeros", False):
            cmd.append("--show-zeros")
        if inputs.get("header_line", False):
            cmd.append("--header-line")
        _add_shell_redirect(cmd, cls._output_path(inputs))
        rendered = _shell_join(cmd)
        if setup:
            return " && ".join([*setup, rendered])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_report.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "classification": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kraken classification outputs"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional Galaxy element identifiers for sample names"},
                ),
                "show_zeros": (
                    "BOOLEAN",
                    {"default": False, "description": "Display taxa even if they lack reads in every sample"},
                ),
                "header_line": (
                    "BOOLEAN",
                    {"default": False, "description": "Display a header line indicating sample IDs"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
