"""Shared bacterial assembly and Snippy contracts for final owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin._assembly_typing_contracts import (
    TOOLS_IUC_GIT_COMMIT,
    ToolsIUCCommandContract,
)


class RavenContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/raven"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "1.8.3+galaxy0"
    PACKAGE_CONSTRAINT = "raven-assembler==1.8.3"


class ShovillContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/shovill"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "1.4.2+galaxy1"
    PACKAGE_CONSTRAINT = "shovill==1.4.2"


class SnippyContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/snippy"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "4.6.0+galaxy0"
    PACKAGE_CONSTRAINT = "snippy==4.6.0; tar==1.32"


class _RavenContract(RavenContractNode):
    """Assemble long uncorrected reads with the Galaxy IUC Raven wrapper behavior."""

    LEGACY_NODE_ID = "raven"
    DISPLAY_NAME = "Raven"
    REQUIRED_CONDA_PACKAGES = ["raven-assembler"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble Oxford Nanopore or other long uncorrected reads with Raven."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Raven",
        "raven",
        "raven-assembler",
        "Oxford Nanopore",
        "long-read assembler",
        "de novo assembly",
        "Graphical Fragment Assembly",
        "GFA",
    ]
    RETURN_TYPES = ("FASTA", "GFA")
    RETURN_NAMES = ("out_fasta", "out_gfa")
    REQUIRED_EXECUTABLES = ["raven"]
    DOCUMENTATION_URL = RAVEN_DOCUMENTATION_URL
    CITATION_DOIS = [RAVEN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{RAVEN_CITATION_DOI}"]
    CITATION_TEXT = RAVEN_CITATION_TEXT
    VERSION = "1.8.3+galaxy0"
    SHELL = True

    INPUT_FORMATS = ["fasta", "fasta.gz", "fastq", "fastq.gz"]
    STAGED_INPUTS = {
        "fasta": "./input.fa",
        "fasta.gz": "./input.fa.gz",
        "fastq": "./input.fq",
        "fastq.gz": "./input.fq.gz",
    }

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_format", "") or "").strip()
        if explicit:
            return explicit
        input_path = str(inputs.get("input_reads", "") or "")
        suffixes = [suffix.lower().lstrip(".") for suffix in Path(input_path).suffixes]
        if len(suffixes) >= 2 and suffixes[-2:] == ["fasta", "gz"]:
            return "fasta.gz"
        if len(suffixes) >= 2 and suffixes[-2:] == ["fastq", "gz"]:
            return "fastq.gz"
        if suffixes and suffixes[-1] in {"fa", "fasta", "fna"}:
            return "fasta"
        if suffixes and suffixes[-1] in {"fq", "fastq"}:
            return "fastq"
        return "fastq.gz"

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        return cls.STAGED_INPUTS.get(cls._input_format(inputs), "./input.fq.gz")

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        return str(int(value))

    @classmethod
    def _format_number(cls, inputs: dict[str, Any], key: str, default: float) -> str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        parsed = float(value)
        return str(int(parsed)) if parsed.is_integer() else format(parsed, "g")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input(inputs)
        cmd = [
            "raven",
            "--kmer-len",
            cls._format_int(inputs, "kmer_len", 15),
            "--window-len",
            cls._format_int(inputs, "window_len", 5),
            "--frequency",
            cls._format_number(inputs, "frequency", 0.001),
            "--polishing-rounds",
            cls._format_int(inputs, "polishing_rounds", 2),
            "--match",
            cls._format_int(inputs, "match", 3),
            "--mismatch",
            cls._format_int(inputs, "mismatch", -5),
            "--gap",
            cls._format_int(inputs, "gap", -4),
            "--kMaxNumOverlaps",
            cls._format_int(inputs, "kMaxNumOverlaps", 32),
            "--identity",
            cls._format_number(inputs, "identity", 0),
            "--min-unitig-size",
            cls._format_int(inputs, "min_unitig_size", 9999),
        ]
        if inputs.get("use_micromizers"):
            cmd.append("--use-micromizers")
        if inputs.get("graphical_fragment_assembly", True):
            cmd.extend(["--graphical-fragment-assembly", cls._output_path(inputs, "out.gfa")])
        slots = "${GALAXY_SLOTS:-4}"
        cmd.extend(["--disable-checkpoints", "-t", slots, staged, ">", cls._output_path(inputs, "out.fasta")])
        raven_command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"{_shell_join(['ln', '-s', str(inputs.get('input_reads', '')), staged])} && {raven_command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out.fasta"]
        if inputs.get("graphical_fragment_assembly", True):
            outputs.append(out / "out.gfa")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_float_min(cls, inputs: dict[str, Any], key: str, default: float, minimum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_reads", "")).strip():
            return "input_reads is required"
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        for key, default, minimum in (
            ("kmer_len", 15, 1),
            ("window_len", 5, 1),
            ("kMaxNumOverlaps", 32, 1),
            ("min_unitig_size", 9999, 0),
            ("polishing_rounds", 2, 0),
        ):
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        for key, default in (("frequency", 0.001), ("identity", 0)):
            result = cls._validate_float_min(inputs, key, default, 0)
            if result is not True:
                return result
        try:
            int(inputs.get("match", 3) if inputs.get("match", 3) not in (None, "") else 3)
            int(inputs.get("mismatch", -5) if inputs.get("mismatch", -5) not in (None, "") else -5)
            gap = int(inputs.get("gap", -4) if inputs.get("gap", -4) not in (None, "") else -4)
        except (TypeError, ValueError):
            return "match, mismatch, and gap must be integers"
        if gap > -1:
            return "gap must be less than or equal to -1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_reads": (
                    "FILE",
                    {"description": "FASTA, FASTQ, FASTA.GZ, or FASTQ.GZ long-read data to assemble"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fastq.gz",
                        "options": cls.INPUT_FORMATS,
                        "description": "Galaxy dataset format used to stage the input file name",
                    },
                ),
                "kmer_len": (
                    "INT",
                    {"default": 15, "min": 1, "description": "Length of minimizers used to find overlaps"},
                ),
                "window_len": (
                    "INT",
                    {"default": 5, "min": 1, "description": "Length of the sliding window used to sample minimizers"},
                ),
                "frequency": (
                    "FLOAT",
                    {"default": 0.001, "min": 0, "description": "Threshold for ignoring the most frequent minimizers"},
                ),
                "identity": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Minimum overlap identity; zero disables identity filtering",
                    },
                ),
                "kMaxNumOverlaps": (
                    "INT",
                    {"default": 32, "min": 1, "description": "Maximum overlaps kept during pile creation"},
                ),
                "min_unitig_size": ("INT", {"default": 9999, "min": 0, "description": "Minimal unitig size"}),
                "polishing_rounds": (
                    "INT",
                    {"default": 2, "min": 0, "description": "Number of racon polishing rounds"},
                ),
                "match": ("INT", {"default": 3, "description": "Racon match score"}),
                "mismatch": ("INT", {"default": -5, "description": "Racon mismatch penalty"}),
                "gap": ("INT", {"default": -4, "max": -1, "description": "Racon gap penalty"}),
                "graphical_fragment_assembly": (
                    "BOOLEAN",
                    {"default": True, "description": "Emit a Graphical Fragment Assembly output"},
                ),
                "use_micromizers": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Use micromizers rather than minimizers for graph construction",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ShovillContract(ShovillContractNode):
    """Assemble bacterial isolate genomes with the Galaxy IUC Shovill wrapper behavior."""

    LEGACY_NODE_ID = "shovill"
    DISPLAY_NAME = "Shovill"
    REQUIRED_CONDA_PACKAGES = ["shovill"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble bacterial isolate genomes from Illumina paired-end reads with Shovill."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Shovill",
        "shovill",
        "SPAdes",
        "Faster SPAdes assembly",
        "Illumina paired-end",
        "bacterial isolate assembly",
        "skesa",
        "megahit",
        "velvet",
        "contigs.fa",
    ]
    RETURN_TYPES = ("TXT", "FASTA", "TXT", "BAM", "GFA")
    RETURN_NAMES = ("shovill_std_log", "contigs", "contigs_graph", "bamfiles", "skesa_gfa")
    REQUIRED_EXECUTABLES = ["shovill"]
    DOCUMENTATION_URL = SHOVILL_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SHOVILL_CITATION_URL]
    CITATION_TEXT = SHOVILL_CITATION_TEXT
    VERSION = "1.4.2+galaxy1"
    SHELL = True

    LIB_TYPES = ["paired", "collection"]
    FASTQ_FORMATS = ["fastq", "fastq.gz", "fastqsanger", "fastqsanger.gz", "fastqsanger.bz2"]
    COPY_FORMATS = {"fastqsanger.gz", "fastqsanger.bz2"}
    ASSEMBLERS = ["skesa", "megahit", "velvet", "spades"]
    NOCORR_OPTIONS = ["no_correction", "yes_correction"]

    @classmethod
    def _format_value(cls, inputs: dict[str, Any], key: str, default: str) -> str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        return str(value)

    @classmethod
    def _single_quote(cls, value: Any) -> str:
        return "'" + str(value).replace("'", "'\"'\"'") + "'"

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("input_collection")
        if isinstance(collection, dict):
            return str(collection.get("forward", "") or ""), str(collection.get("reverse", "") or "")
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return str(collection[0]), str(collection[1])
        return "", ""

    @classmethod
    def _read_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._format_value(inputs, "lib_type", "paired") == "collection":
            return cls._collection_reads(inputs)
        return str(inputs.get("R1", "") or ""), str(inputs.get("R2", "") or "")

    @classmethod
    def _read_format(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        explicit = str(inputs.get(key, "") or "").strip()
        if explicit:
            return explicit
        suffixes = [suffix.lower().lstrip(".") for suffix in Path(path).suffixes]
        if len(suffixes) >= 2 and suffixes[-2:] in (["fastq", "gz"], ["fq", "gz"]):
            return "fastq.gz"
        if len(suffixes) >= 2 and suffixes[-2:] in (["fastq", "bz2"], ["fq", "bz2"]):
            return "fastqsanger.bz2"
        return "fastqsanger"

    @classmethod
    def _stage_command(cls, source: str, staged: str, fastq_format: str) -> str:
        operation = "cp" if fastq_format in cls.COPY_FORMATS else "ln -s"
        return f"{operation} {shlex.quote(source)} {shlex.quote(staged)}"

    @classmethod
    def _outdir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        r1, r2 = cls._read_paths(inputs)
        r1_format = cls._read_format(inputs, "R1_format", r1)
        r2_format = cls._read_format(inputs, "R2_format", r2)
        r1_staged = f"fastq_r1.{r1_format}"
        r2_staged = f"fastq_r2.{r2_format}"
        commands = [
            cls._stage_command(r1, r1_staged, r1_format),
            cls._stage_command(r2, r2_staged, r2_format),
            r"GALAXY_MEMORY_GB=$((${GALAXY_MEMORY_MB:-8192}/1024))",
            r"SHOVILL_RAM=${SHOVILL_RAM:-${GALAXY_MEMORY_GB}}",
        ]
        slots = "${GALAXY_SLOTS:-1}"
        ram = "${SHOVILL_RAM:-8}"
        cmd = [
            "shovill",
            "--outdir",
            cls._outdir(inputs),
            "--cpus",
            slots,
            "--ram",
            ram,
            "--R1",
            r1_staged,
            "--R2",
            r2_staged,
        ]
        if inputs.get("trim"):
            cmd.append("--trim")
        cmd.extend(
            [
                "--namefmt",
                cls._single_quote(inputs.get("namefmt", "contig%05d") or "contig%05d"),
                "--depth",
                cls._format_value(inputs, "depth", "100"),
            ]
        )
        if str(inputs.get("gsize", "") or "").strip():
            cmd.extend(["--gsize", str(inputs.get("gsize"))])
        if str(inputs.get("kmers", "") or "").strip():
            cmd.extend(["--kmers", str(inputs.get("kmers"))])
        if str(inputs.get("opts", "") or "").strip():
            cmd.extend(["--opts", cls._single_quote(inputs.get("opts"))])
        assembler = cls._format_value(inputs, "assembler", "spades")
        cmd.extend(
            [
                "--minlen",
                cls._format_value(inputs, "minlen", "0"),
                "--mincov",
                cls._format_value(inputs, "mincov", "2"),
                "--assembler",
                assembler,
            ]
        )
        if assembler == "spades" and inputs.get("plasmid"):
            cmd.append("--plasmid")
        if cls._format_value(inputs, "nocorr", "no_correction") == "no_correction":
            cmd.append("--nocorr")
        elif inputs.get("keepfiles"):
            cmd.append("--keepfiles")
        shovill_command = _shell_join(cmd).replace(shlex.quote(slots), slots).replace(shlex.quote(ram), ram)
        shovill_command = shovill_command.replace(shlex.quote(cls._single_quote(inputs.get("namefmt", "contig%05d"))), cls._single_quote(inputs.get("namefmt", "contig%05d") or "contig%05d"))
        if str(inputs.get("opts", "") or "").strip():
            shovill_command = shovill_command.replace(
                shlex.quote(cls._single_quote(inputs.get("opts"))),
                cls._single_quote(inputs.get("opts")),
            )
        commands.append(shovill_command)
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "out"
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if inputs.get("log", True):
            outputs.append(out / "shovill.log")
        outputs.append(out / "contigs.fa")
        assembler = cls._format_value(inputs, "assembler", "spades")
        if assembler == "skesa":
            outputs.append(out / "skesa.gfa")
        else:
            outputs.append(out / "spades.gfa")
        if cls._format_value(inputs, "nocorr", "no_correction") == "yes_correction" and inputs.get("keepfiles"):
            outputs.append(out / "shovill.bam")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        lib_type = cls._format_value(inputs, "lib_type", "paired")
        if lib_type not in cls.LIB_TYPES:
            return f"lib_type must be one of: {', '.join(cls.LIB_TYPES)}"
        r1, r2 = cls._read_paths(inputs)
        if lib_type == "collection":
            if not r1 or not r2:
                return "input_collection with forward and reverse reads is required for collection input"
        else:
            if not r1:
                return "R1 is required for paired input"
            if not r2:
                return "R2 is required for paired input"
        r1_format = cls._read_format(inputs, "R1_format", r1)
        r2_format = cls._read_format(inputs, "R2_format", r2)
        if r1_format not in cls.FASTQ_FORMATS:
            return f"R1_format must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        if r2_format not in cls.FASTQ_FORMATS:
            return f"R2_format must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        assembler = cls._format_value(inputs, "assembler", "spades")
        if assembler not in cls.ASSEMBLERS:
            return f"assembler must be one of: {', '.join(cls.ASSEMBLERS)}"
        if inputs.get("plasmid") and assembler != "spades":
            return "plasmid mode is only available with the spades assembler"
        nocorr = cls._format_value(inputs, "nocorr", "no_correction")
        if nocorr not in cls.NOCORR_OPTIONS:
            return f"nocorr must be one of: {', '.join(cls.NOCORR_OPTIONS)}"
        for key, default in (("depth", 100), ("minlen", 0), ("mincov", 2)):
            result = cls._validate_int_min(inputs, key, default, 0)
            if result is not True:
                return result
        if not str(inputs.get("namefmt", "contig%05d") or "").strip():
            return "namefmt is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "lib_type": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": cls.LIB_TYPES,
                        "description": "Galaxy input layout: paired FASTQ datasets or a paired collection",
                    },
                ),
                "R1": ("FASTQ", {"description": "Forward reads for paired input"}),
                "R2": ("FASTQ", {"description": "Reverse reads for paired input"}),
            },
            "optional": {
                "input_collection": (
                    "FILE",
                    {"default": "", "description": "Paired collection object with forward and reverse reads"},
                ),
                "R1_format": (
                    "STRING",
                    {"default": "fastqsanger", "options": cls.FASTQ_FORMATS, "description": "Galaxy extension for R1"},
                ),
                "R2_format": (
                    "STRING",
                    {"default": "fastqsanger", "options": cls.FASTQ_FORMATS, "description": "Galaxy extension for R2"},
                ),
                "trim": (
                    "BOOLEAN",
                    {"default": False, "description": "Use Trimmomatic to remove common adapters first"},
                ),
                "assembler": (
                    "STRING",
                    {
                        "default": "spades",
                        "options": cls.ASSEMBLERS,
                        "description": "Assembler backend used by Shovill",
                    },
                ),
                "plasmid": ("BOOLEAN", {"default": False, "description": "Enable SPAdes plasmid mode"}),
                "namefmt": (
                    "STRING",
                    {"default": "contig%05d", "description": "printf-style contig FASTA ID format"},
                ),
                "depth": (
                    "INT",
                    {"default": 100, "min": 0, "description": "Subsample R1/R2 to this depth; 0 disables subsampling"},
                ),
                "gsize": (
                    "STRING",
                    {"default": "", "description": "Estimated genome size, for example 4.8M; blank autodetects"},
                ),
                "kmers": ("STRING", {"default": "", "description": "Comma-separated k-mer sizes; blank selects AUTO"}),
                "opts": ("STRING", {"default": "", "description": "Extra assembler options passed through Shovill"}),
                "nocorr": (
                    "STRING",
                    {
                        "default": "no_correction",
                        "options": cls.NOCORR_OPTIONS,
                        "description": "Galaxy correction selector; no_correction adds --nocorr",
                    },
                ),
                "keepfiles": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep BAM files when post-assembly correction is enabled"},
                ),
                "minlen": ("INT", {"default": 0, "min": 0, "description": "Minimum output contig length"}),
                "mincov": ("INT", {"default": 2, "min": 0, "description": "Minimum contig coverage"}),
                "log": ("BOOLEAN", {"default": True, "description": "Return shovill.log as an output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SnippyContract(SnippyContractNode):
    """Call bacterial SNPs and indels with the Galaxy IUC Snippy wrapper behavior."""

    LEGACY_NODE_ID = "snippy"
    DISPLAY_NAME = "Snippy"
    REQUIRED_CONDA_PACKAGES = ["snippy", "tar"]
    CATEGORY = "variant"
    DESCRIPTION = "Call SNPs and indels between a haploid reference genome and reads or contigs with Snippy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Snippy",
        "snippy",
        "haploid variant calling",
        "fast bacterial variant calling",
        "NGS reads",
        "core genome alignment",
        "snippy-core",
        "SNPs",
        "indels",
    ]
    RETURN_TYPES = ("VCF", "GFF", "TSV", "TSV", "TXT", "FASTA", "FASTA", "BAM", "ZIP")
    RETURN_NAMES = (
        "snpvcf",
        "snpgff",
        "snptab",
        "snpsum",
        "snplog",
        "snpalign",
        "snpconsensus",
        "snpsbam",
        "outdir",
    )
    REQUIRED_EXECUTABLES = ["snippy", "tar"]
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = "4.6.0+galaxy0"
    SHELL = True

    REFERENCE_SOURCES = ["history", "cached"]
    REFERENCE_TYPES = ["fasta", "genbank"]
    INPUT_SELECTORS = ["paired", "single", "paired_collection", "paired_iv", "contigs"]
    OUTPUT_SELECTIONS = ["outvcf", "outgff", "outtab", "outsum", "outlog", "outaln", "outcon", "outbam", "outzip"]
    DEFAULT_OUTPUTS = ["outvcf", "outtab", "outzip"]
    OUTPUT_FILES = {
        "outvcf": ("out", "snps.vcf"),
        "outgff": ("out", "snps.gff"),
        "outtab": ("out", "snps.tab"),
        "outsum": ("out", "snps.txt"),
        "outlog": ("out", "snps.log"),
        "outaln": ("out", "snps.aligned.fa"),
        "outcon": ("out", "snps.consensus.fa"),
        "outbam": ("out", "snps.bam"),
        "outzip": ("", "out.tgz"),
    }

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", "history") or "history")

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_type", "fasta") or "fasta")

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("outputs"))
        return selected or list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        return str(int(value))

    @classmethod
    def _format_float(cls, inputs: dict[str, Any], key: str, default: float) -> str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        parsed = float(value)
        if key == "minqual":
            return str(value)
        return str(int(parsed)) if parsed.is_integer() else format(parsed, "g")

    @classmethod
    def _reference_stage_command(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        ref_file = str(inputs.get("ref_file", "") or "")
        if cls._reference_source(inputs) == "cached":
            return _shell_join(["ln", "-sf", ref_file, "ref.fna"]), "ref.fna"
        if cls._reference_type(inputs) == "genbank":
            return _shell_join(["ln", "-sf", ref_file, "ref.gbk"]), "ref.gbk"
        return _shell_join(["ln", "-sf", ref_file, "ref.fna"]), "ref.fna"

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("fastq_input")
        if isinstance(collection, dict):
            return str(collection.get("forward", "") or ""), str(collection.get("reverse", "") or "")
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return str(collection[0]), str(collection[1])
        return "", ""

    @classmethod
    def _dir_name(cls, inputs: dict[str, Any]) -> str:
        selector = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if selector == "paired":
            label = str(inputs.get("fastq_input1_label", "") or Path(str(inputs.get("fastq_input1", ""))).name)
        elif selector == "paired_collection":
            collection = inputs.get("fastq_input")
            label = str(collection.get("name", "") if isinstance(collection, dict) else "")
            if not label:
                forward, _reverse = cls._collection_reads(inputs)
                label = Path(forward).name
        elif selector == "single":
            label = str(inputs.get("fastq_input_single_label", "") or Path(str(inputs.get("fastq_input_single", ""))).name)
        elif selector == "paired_iv":
            label = str(
                inputs.get("fastq_input_interleaved_label", "")
                or Path(str(inputs.get("fastq_input_interleaved", ""))).name
            )
        else:
            label = str(inputs.get("fasta_input_label", "") or Path(str(inputs.get("fasta_input", ""))).name)
        return _safe_identifier(label)

    @classmethod
    def _input_args(cls, inputs: dict[str, Any]) -> list[str]:
        selector = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if selector == "paired":
            return ["--R1", str(inputs.get("fastq_input1", "") or ""), "--R2", str(inputs.get("fastq_input2", "") or "")]
        if selector == "paired_collection":
            forward, reverse = cls._collection_reads(inputs)
            return ["--R1", forward, "--R2", reverse]
        if selector == "single":
            return ["--se", str(inputs.get("fastq_input_single", "") or "")]
        if selector == "paired_iv":
            return ["--peil", str(inputs.get("fastq_input_interleaved", "") or "")]
        return ["--ctgs", str(inputs.get("fasta_input", "") or "")]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_stage, ref_name = cls._reference_stage_command(inputs)
        dir_name = cls._dir_name(inputs)
        memory = "$((${GALAXY_MEMORY_MB:-4096}/1024))"
        slots = "${GALAXY_SLOTS:-1}"
        cmd = [
            "snippy",
            "--outdir",
            dir_name,
            "--cpus",
            slots,
            "--ram",
            memory,
            "--ref",
            ref_name,
            "--mapqual",
            cls._format_int(inputs, "mapqual", 60),
            "--mincov",
            cls._format_int(inputs, "mincov", 10),
            "--minfrac",
            cls._format_float(inputs, "minfrac", 0.9),
            "--minqual",
            cls._format_float(inputs, "minqual", 100.0),
        ]
        if str(inputs.get("rgid", "") or "").strip():
            cmd.extend(["--rgid", str(inputs.get("rgid"))])
        if str(inputs.get("bwaopt", "") or "").strip():
            cmd.extend(["--bwaopt", str(inputs.get("bwaopt"))])
        cmd.extend(cls._input_args(inputs))
        snippy_command = _shell_join(cmd).replace(shlex.quote(slots), slots).replace(shlex.quote(memory), memory)
        commands = [ref_stage, snippy_command]
        if "outcon" in cls._selected_outputs(inputs) and inputs.get("rename_cons"):
            commands.append(f"sed -i 's/>.*/>{dir_name}/' {shlex.quote(f'{dir_name}/snps.consensus.fa')}")
        commands.extend(
            [
                f"cp -r {shlex.quote(dir_name)} {shlex.quote(f'{_out(inputs)}/out')}",
                f"tar -czf {shlex.quote(f'{_out(inputs)}/out.tgz')} {shlex.quote(dir_name)}",
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "out").mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        selected = set(cls._selected_outputs(inputs))
        for selection in cls.OUTPUT_SELECTIONS:
            if selection not in selected:
                continue
            output_subdir, filename = cls.OUTPUT_FILES[selection]
            outputs.append(out / output_subdir / filename if output_subdir else out / filename)
        return outputs

    @classmethod
    def _validate_nonnegative_int(cls, inputs: dict[str, Any], key: str, default: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < 0:
            return f"{key} must be greater than or equal to 0"
        return True

    @classmethod
    def _validate_nonnegative_float(cls, inputs: dict[str, Any], key: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < 0:
            return f"{key} must be greater than or equal to 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not str(inputs.get("ref_file", "") or "").strip():
            return "ref_file is required"
        ref_type = cls._reference_type(inputs)
        if source == "history" and ref_type not in cls.REFERENCE_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REFERENCE_TYPES)}"
        selector = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if selector not in cls.INPUT_SELECTORS:
            return f"fastq_input_selector must be one of: {', '.join(cls.INPUT_SELECTORS)}"
        if selector == "paired":
            if not str(inputs.get("fastq_input1", "") or "").strip():
                return "fastq_input1 is required for paired input"
            if not str(inputs.get("fastq_input2", "") or "").strip():
                return "fastq_input2 is required for paired input"
        elif selector == "paired_collection":
            forward, reverse = cls._collection_reads(inputs)
            if not forward or not reverse:
                return "fastq_input collection with forward and reverse reads is required"
        elif selector == "single":
            if not str(inputs.get("fastq_input_single", "") or "").strip():
                return "fastq_input_single is required for single input"
        elif selector == "paired_iv":
            if not str(inputs.get("fastq_input_interleaved", "") or "").strip():
                return "fastq_input_interleaved is required for interleaved paired input"
        elif not str(inputs.get("fasta_input", "") or "").strip():
            return "fasta_input is required for contigs input"
        for key, default in (("mapqual", 60), ("mincov", 10)):
            result = cls._validate_nonnegative_int(inputs, key, default)
            if result is not True:
                return result
        result = cls._validate_nonnegative_float(inputs, "minqual", 100.0)
        if result is not True:
            return result
        try:
            minfrac = float(inputs.get("minfrac", 0.9) if inputs.get("minfrac", 0.9) not in (None, "") else 0.9)
        except (TypeError, ValueError):
            return "minfrac must be a number"
        if minfrac < 0 or minfrac > 1:
            return "minfrac must be between 0 and 1"
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCES,
                        "description": "Use a reference from history or a cached Galaxy fasta index",
                    },
                ),
                "ref_file": ("FILE", {"description": "Reference genome FASTA, GenBank, or cached reference path"}),
                "fastq_input_selector": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": cls.INPUT_SELECTORS,
                        "description": "Galaxy input type for paired, single, interleaved, or contig inputs",
                    },
                ),
            },
            "optional": {
                "ref_type": (
                    "STRING",
                    {"default": "fasta", "options": cls.REFERENCE_TYPES, "description": "History reference datatype"},
                ),
                "fastq_input1": ("FASTQ", {"default": "", "description": "Forward reads for paired input"}),
                "fastq_input2": ("FASTQ", {"default": "", "description": "Reverse reads for paired input"}),
                "fastq_input1_label": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Galaxy element identifier for paired R1"},
                ),
                "fastq_input_single": ("FASTQ", {"default": "", "description": "Single-end reads"}),
                "fastq_input_single_label": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Galaxy element identifier for single reads"},
                ),
                "fastq_input": (
                    "FILE",
                    {"default": "", "description": "Paired collection object with forward and reverse reads"},
                ),
                "fastq_input_interleaved": (
                    "FASTQ",
                    {"default": "", "description": "Interleaved paired-end reads"},
                ),
                "fastq_input_interleaved_label": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Galaxy element identifier for interleaved reads"},
                ),
                "fasta_input": ("FASTA", {"default": "", "description": "Assembled contigs for --ctgs mode"}),
                "fasta_input_label": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Galaxy element identifier for contigs"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "description": "Galaxy output files to collect from the Snippy run",
                    },
                ),
                "mapqual": ("INT", {"default": 60, "min": 0, "description": "Minimum mapping quality"}),
                "mincov": ("INT", {"default": 10, "min": 0, "description": "Minimum coverage to call a SNP"}),
                "minfrac": (
                    "FLOAT",
                    {"default": 0.9, "min": 0, "max": 1, "description": "Minimum variant evidence fraction"},
                ),
                "minqual": ("FLOAT", {"default": 100.0, "min": 0, "description": "Minimum VCF QUAL"}),
                "rgid": ("STRING", {"default": "", "description": "BAM header read-group ID"}),
                "bwaopt": ("STRING", {"default": "", "description": "Extra BWA MEM options"}),
                "rename_cons": (
                    "BOOLEAN",
                    {"default": False, "description": "Rename consensus FASTA header to the input identifier"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SnippyCoreContract(SnippyContractNode):
    """Combine multiple Snippy outputs into a core SNP alignment."""

    LEGACY_NODE_ID = "snippy_core"
    DISPLAY_NAME = "snippy-core"
    REQUIRED_CONDA_PACKAGES = ["snippy", "tar"]
    CATEGORY = "variant"
    DESCRIPTION = "Combine multiple Snippy outputs into a core SNP alignment."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "snippy-core",
        "Snippy core",
        "Snippy",
        "core SNP alignment",
        "core genome alignment",
        "core SNP phylogeny",
        "bacterial SNP alignment",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "TSV", "TXT")
    RETURN_NAMES = ("alignment_fasta", "full_alignment_fasta", "alignment_table", "alignment_summary")
    REQUIRED_EXECUTABLES = ["snippy-core", "tar"]
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = "4.6.0+galaxy0"
    SHELL = True

    REFERENCE_SOURCES = ["history", "cached"]
    REFERENCE_TYPES = ["fasta", "genbank"]
    OUTPUT_SELECTIONS = ["outaln", "outfull", "outtab", "outtxt"]
    DEFAULT_OUTPUTS = ["outaln"]
    OUTPUT_FILES = {
        "outaln": "core.aln",
        "outfull": "core.full.aln",
        "outtab": "core.tab",
        "outtxt": "core.txt",
    }

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", "history") or "history")

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_type", "fasta") or "fasta")

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("outputs"))
        return selected or list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _reference_stage_command(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        ref_file = str(inputs.get("ref_file", "") or "")
        if cls._reference_source(inputs) == "cached":
            return _shell_join(["ln", "-sf", ref_file, "ref.fna"]), "ref.fna"
        if cls._reference_type(inputs) == "genbank":
            return _shell_join(["ln", "-sf", ref_file, "ref.gbk"]), "ref.gbk"
        return _shell_join(["ln", "-sf", ref_file, "ref.fna"]), "ref.fna"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_stage, ref_name = cls._reference_stage_command(inputs)
        commands = [ref_stage, "mkdir snippy_dirs"]
        commands.extend(
            _shell_join(["tar", "-xf", archive, "-C", "snippy_dirs"])
            for archive in _as_list(inputs.get("indirs"))
            if archive.strip()
        )
        snippy_cmd = f"{_shell_join(['snippy-core', '--ref', ref_name])} snippy_dirs/*"
        commands.extend([snippy_cmd, f"mkdir -p {shlex.quote(_out(inputs))}"])
        commands.extend(
            f"cp {shlex.quote(filename)} {shlex.quote(f'{_out(inputs)}/{filename}')}"
            for filename in (cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs))
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        indirs = [indir for indir in _as_list(inputs.get("indirs")) if indir.strip()]
        if len(indirs) < 2:
            return "at least two indirs are required"
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not str(inputs.get("ref_file", "") or "").strip():
            return "ref_file is required"
        ref_type = cls._reference_type(inputs)
        if source == "history" and ref_type not in cls.REFERENCE_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REFERENCE_TYPES)}"
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "indirs": (
                    "FILE",
                    {
                        "multiple": True,
                        "description": "Snippy output tar archives produced with cleanup disabled",
                    },
                ),
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCES,
                        "description": "Use a reference from history or a cached Galaxy fasta index",
                    },
                ),
                "ref_file": ("FILE", {"description": "Reference genome FASTA, GenBank, or cached reference path"}),
            },
            "optional": {
                "ref_type": (
                    "STRING",
                    {"default": "fasta", "options": cls.REFERENCE_TYPES, "description": "History reference datatype"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "Galaxy output files to collect from the snippy-core run",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SnippyCleanFullAlnContract(SnippyContractNode):
    """Replace non-standard characters in a Snippy whole-genome alignment."""

    LEGACY_NODE_ID = "snippy_clean_full_aln"
    DISPLAY_NAME = "snippy-clean_full_aln"
    REQUIRED_CONDA_PACKAGES = ["snippy", "tar"]
    CATEGORY = "variant"
    DESCRIPTION = "Replace non-standard sequence characters in a Snippy core.full.aln alignment."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "snippy-clean_full_aln",
        "Snippy clean full alignment",
        "Snippy",
        "core.full.aln",
        "clean.full.aln",
        "whole genome SNP alignment",
        "Gubbins",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("clean_full_aln",)
    REQUIRED_EXECUTABLES = ["snippy-clean_full_aln"]
    DOCUMENTATION_URL = SNIPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SNIPPY_CITATION_URL]
    CITATION_TEXT = SNIPPY_CITATION_TEXT
    VERSION = "4.6.0+galaxy0"
    SHELL = True

    OUTPUT_FILENAME = "clean.full.aln"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILENAME}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["snippy-clean_full_aln", str(inputs.get("full_aln", "") or "")]
        if inputs.get("custom_char_selector"):
            cmd.extend(["--to", str(inputs.get("to_char", "N") or "N")])
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("full_aln", "") or "").strip():
            return "full_aln is required"
        if inputs.get("custom_char_selector"):
            to_char = str(inputs.get("to_char", "") or "")
            if not to_char:
                return "to_char is required when custom_char_selector is true"
            if "'" in to_char:
                return "to_char must not contain a single quote"
            if len(to_char) != 1:
                return "to_char must be a single replacement character"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "full_aln": (
                    "FASTA",
                    {"description": "Snippy core.full.aln FASTA alignment to clean"},
                ),
            },
            "optional": {
                "custom_char_selector": (
                    "BOOLEAN",
                    {"default": False, "description": "Use a custom replacement character instead of Snippy's N"},
                ),
                "to_char": (
                    "STRING",
                    {
                        "default": "N",
                        "description": "Single replacement character for non-AGTCN-gap symbols when custom mode is enabled",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
