"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class GfaToFaNode(CommandNode):
    """Convert GFA segment records to FASTA with Galaxy's helper script."""

    NODE_ID = "gfa_to_fa"
    DISPLAY_NAME = "GFA to FASTA"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "assembly"
    DESCRIPTION = "Convert Graphical Fragment Assembly files to FASTA format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "gfa_to_fa",
        "GFA to FASTA",
        "Graphical Fragment Assembly",
        "assembly graph conversion",
        "GFA v1",
        "FASTA conversion",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("out_fa",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = GFA_TO_FA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [GFA_TO_FA_CITATION_URL]
    CITATION_TEXT = GFA_TO_FA_CITATION_TEXT
    VERSION = "0.1.2"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.fa"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "cat",
            str(inputs.get("in_gfa", "")),
            "|",
            "python",
            str(inputs.get("script_path", "gfa_to_fa.py")),
            ">",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.fa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_gfa", "")).strip():
            return "in_gfa is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_gfa": ("GFA", {"description": "Input GFA file"}),
            },
            "optional": {
                "script_path": (
                    "FILE",
                    {
                        "default": "gfa_to_fa.py",
                        "advanced": True,
                        "description": "Path to the Galaxy gfa_to_fa helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RavenNode(CommandNode):
    """Assemble long uncorrected reads with the Galaxy IUC Raven wrapper behavior."""

    NODE_ID = "raven"
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

class ShovillNode(CommandNode):
    """Assemble bacterial isolate genomes with the Galaxy IUC Shovill wrapper behavior."""

    NODE_ID = "shovill"
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

class SnippyNode(CommandNode):
    """Call bacterial SNPs and indels with the Galaxy IUC Snippy wrapper behavior."""

    NODE_ID = "snippy"
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

class SnippyCoreNode(CommandNode):
    """Combine multiple Snippy outputs into a core SNP alignment."""

    NODE_ID = "snippy_core"
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

class SnippyCleanFullAlnNode(CommandNode):
    """Replace non-standard characters in a Snippy whole-genome alignment."""

    NODE_ID = "snippy_clean_full_aln"
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

class ABRicateNode(CommandNode):
    """Mass screen contigs for antimicrobial resistance and virulence genes with ABRicate."""

    NODE_ID = "abricate"
    DISPLAY_NAME = "ABRicate"
    REQUIRED_CONDA_PACKAGES = ["abricate"]
    CATEGORY = "annotation"
    DESCRIPTION = "Mass screen contigs for antimicrobial resistance and virulence genes with ABRicate."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ABRicate",
        "abricate",
        "antimicrobial resistance",
        "AMR genes",
        "virulence genes",
        "ResFinder",
        "CARD",
        "PlasmidFinder",
        "VFDB",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["abricate"]
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = "1.4.0"
    SHELL = True

    DATABASES = [
        "argannot",
        "card",
        "ecoh",
        "ncbi",
        "resfinder",
        "plasmidfinder",
        "vfdb",
        "megares",
        "ecoli_vf",
        "upec_expec_vf",
    ]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/report.tsv"

    @classmethod
    def _percent_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < 0 or value > 100:
            return f"{name} must be between 0 and 100"
        return True

    @classmethod
    def _format_number(cls, value: Any, default: float) -> str:
        parsed = float(value if value not in (None, "") else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sample_name = _safe_element_identifier(str(inputs.get("file_input", "")))
        cmd = ["abricate", sample_name]
        if inputs.get("no_header"):
            cmd.append("--noheader")
        cmd.append(f"--minid={cls._format_number(inputs.get('min_dna_id'), 80)}")
        cmd.append(f"--mincov={cls._format_number(inputs.get('min_cov'), 80)}")
        cmd.append(f"--db={str(inputs.get('db', 'ncbi') or 'ncbi')}")
        return (
            f"ln -sf {shlex.quote(str(inputs.get('file_input', '')))} {shlex.quote(sample_name)} && "
            f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "report.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("file_input", "")).strip():
            return "file_input is required"
        db = str(inputs.get("db", "ncbi") or "ncbi")
        if db not in cls.DATABASES:
            return f"db must be one of: {', '.join(cls.DATABASES)}"
        for name in ["min_dna_id", "min_cov"]:
            result = cls._percent_range(inputs, name, 80)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file_input": (
                    "FILE",
                    {"description": "FASTA, GenBank, or EMBL contigs to screen for AMR and virulence genes"},
                ),
            },
            "optional": {
                "db": (
                    "STRING",
                    {
                        "default": "ncbi",
                        "options": cls.DATABASES,
                        "description": "ABRicate AMR, plasmid, or virulence database to search",
                    },
                ),
                "no_header": (
                    "BOOLEAN",
                    {"default": False, "description": "Suppress the ABRicate tabular header"},
                ),
                "min_dna_id": (
                    "FLOAT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum nucleotide percent identity"},
                ),
                "min_cov": (
                    "FLOAT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum gene percent coverage"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ABRicateListNode(CommandNode):
    """List ABRicate databases available in the local installation."""

    NODE_ID = "abricate_list"
    DISPLAY_NAME = "ABRicate List"
    REQUIRED_CONDA_PACKAGES = ["abricate"]
    CATEGORY = "annotation"
    DESCRIPTION = "List ABRicate databases available in the local installation."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ABRicate",
        "abricate",
        "ABRicate databases",
        "abricate --list",
        "AMR database list",
        "ResFinder database",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["abricate"]
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = "1.4.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/databases.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return f"abricate --list > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "databases.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class ABRicateSummaryNode(CommandNode):
    """Combine ABRicate reports into a gene presence and coverage matrix."""

    NODE_ID = "abricate_summary"
    DISPLAY_NAME = "ABRicate Summary"
    REQUIRED_CONDA_PACKAGES = ["abricate"]
    CATEGORY = "annotation"
    DESCRIPTION = "Combine ABRicate reports into a gene presence and coverage matrix."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ABRicate",
        "abricate",
        "ABRicate Summary",
        "presence absence matrix",
        "gene coverage matrix",
        "abricate --summary",
        "AMR report summary",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("summary",)
    REQUIRED_EXECUTABLES = ["abricate"]
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = "1.4.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/summary.tsv"

    @classmethod
    def _reports_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/reports"

    @classmethod
    def _reports(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("abricate_reports"))

    @classmethod
    def _labels(cls, inputs: dict[str, Any], reports: list[str]) -> list[str]:
        labels = _as_list(inputs.get("abricate_report_labels"))
        if len(labels) != len(reports):
            return [Path(report).name for report in reports]
        return labels

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reports = cls._reports(inputs)
        labels = cls._labels(inputs, reports)
        reports_dir = cls._reports_dir(inputs)
        commands = [f"mkdir -p {shlex.quote(reports_dir)}"]
        for report, label in zip(reports, labels):
            link_name = _safe_element_identifier(label)
            commands.append(
                f"ln -sf {shlex.quote(report)} {shlex.quote(f'{reports_dir}/{link_name}')}"
            )
        commands.append(
            f"cd {shlex.quote(reports_dir)} && abricate --summary '*' > {shlex.quote(cls._output_path(inputs))}"
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "summary.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reports = cls._reports(inputs)
        if not reports:
            return "at least one ABRicate report is required"
        labels = _as_list(inputs.get("abricate_report_labels"))
        if labels and len(labels) != len(reports):
            return "abricate_report_labels must match the number of reports"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "abricate_reports": (
                    "TSV_LIST",
                    {"multiple": True, "description": "ABRicate tabular reports to combine with abricate --summary"},
                ),
            },
            "optional": {
                "abricate_report_labels": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels matching the report order; defaults to input filenames",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KleborateNode(CommandNode):
    """Screen Klebsiella assemblies with Kleborate."""

    NODE_ID = "kleborate"
    DISPLAY_NAME = "Kleborate"
    REQUIRED_CONDA_PACKAGES = ["kleborate", "kaptive"]
    CATEGORY = "typing"
    DESCRIPTION = "Screen Klebsiella genome assemblies for species, MLST, virulence, resistance, and K/O loci."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kleborate",
        "kleborate",
        "Klebsiella",
        "Klebsiella pneumoniae",
        "KpSC",
        "MLST",
        "virulence score",
        "resistance score",
        "Kaptive",
        "K locus",
        "O locus",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("concise", "full", "kaptive_k", "kaptive_o")
    REQUIRED_EXECUTABLES = ["kleborate"]
    DOCUMENTATION_URL = "https://github.com/klebgenomics/Kleborate"
    CITATION_DOIS = ["10.1038/s41467-021-24448-3", "10.1099/mgen.0.000102"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "A genomic surveillance framework and genotyping tool for Klebsiella pneumoniae and its related species complex; "
        "Kaptive: identification of Klebsiella capsule synthesis loci from whole genome data."
    )
    VERSION = "2.3.2+galaxy1"
    SHELL = True

    @classmethod
    def _assemblies(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("assemblies"))

    @classmethod
    def _staged_assemblies(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        assemblies = cls._assemblies(inputs)
        labels = _as_list(inputs.get("assembly_labels"))
        staged: list[tuple[str, str]] = []
        for index, assembly in enumerate(assemblies):
            label = labels[index] if index < len(labels) else Path(assembly).name
            staged.append((assembly, _safe_identifier(label)))
        return staged

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        return str(int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any]) -> dict[str, str]:
        out = _out(inputs)
        return {
            "concise": f"{out}/kleborate_concise_results.tsv",
            "full": f"{out}/kleborate_results.tsv",
            "kaptive_k": f"{out}/kleborate_kaptive_k_results.tsv",
            "kaptive_o": f"{out}/kleborate_kaptive_o_results.tsv",
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_assemblies(inputs)
        paths = cls._output_paths(inputs)
        commands = [_shell_join(["ln", "-s", source, staged_name]) for source, staged_name in staged]
        cmd = ["kleborate"]
        if inputs.get("resistance", True):
            cmd.append("--resistance")
        cmd.extend(["-o", paths["full"]])
        if inputs.get("kaptive_k"):
            cmd.extend(["--kaptive_k", "--kaptive_k_outfile", paths["kaptive_k"]])
        if inputs.get("kaptive_o"):
            cmd.extend(["--kaptive_o", "--kaptive_o_outfile", paths["kaptive_o"]])
        cmd.extend(
            [
                "--min_identity",
                cls._format_int(inputs, "min_identity", 90),
                "--min_coverage",
                cls._format_int(inputs, "min_coverage", 80),
                "--min_spurious_identity",
                cls._format_int(inputs, "min_spurious_identity", 80),
                "--min_spurious_coverage",
                cls._format_int(inputs, "min_spurious_coverage", 40),
                "--assemblies",
            ]
        )
        cmd.extend(staged_name for _, staged_name in staged)
        cmd.extend([">", paths["concise"]])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "kleborate_concise_results.tsv", out / "kleborate_results.tsv"]
        if inputs.get("kaptive_k"):
            outputs.append(out / "kleborate_kaptive_k_results.tsv")
        if inputs.get("kaptive_o"):
            outputs.append(out / "kleborate_kaptive_o_results.tsv")
        return outputs

    @classmethod
    def _validate_percent(cls, inputs: dict[str, Any], key: str, default: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < 0 or value > 100:
            return f"{key} must be between 0 and 100"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        assemblies = cls._assemblies(inputs)
        if not assemblies:
            return "at least one assembly FASTA is required"
        labels = _as_list(inputs.get("assembly_labels"))
        if labels and len(labels) != len(assemblies):
            return "assembly_labels must match the number of assemblies"
        for key, default in {
            "min_identity": 90,
            "min_coverage": 80,
            "min_spurious_identity": 80,
            "min_spurious_coverage": 40,
        }.items():
            result = cls._validate_percent(inputs, key, default)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assemblies": (
                    "FASTA",
                    {"multiple": True, "description": "FASTA assembly file or files to screen with Kleborate"},
                ),
            },
            "optional": {
                "resistance": (
                    "BOOLEAN",
                    {"default": True, "description": "Turn on acquired resistance and resistance score screening"},
                ),
                "kaptive_k": (
                    "BOOLEAN",
                    {"default": False, "description": "Run Kaptive K-locus capsule typing"},
                ),
                "kaptive_o": (
                    "BOOLEAN",
                    {"default": False, "description": "Run Kaptive O-locus lipopolysaccharide typing"},
                ),
                "min_identity": (
                    "INT",
                    {"default": 90, "min": 0, "max": 100, "description": "Minimum alignment percent identity for main results"},
                ),
                "min_coverage": (
                    "INT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum alignment percent coverage for main results"},
                ),
                "min_spurious_identity": (
                    "INT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum identity for spurious hit reporting"},
                ),
                "min_spurious_coverage": (
                    "INT",
                    {"default": 40, "min": 0, "max": 100, "description": "Minimum coverage for spurious hit reporting"},
                ),
                "assembly_labels": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used in the output table",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PlasmidFinderNode(CommandNode):
    """Identify bacterial plasmid replicons with PlasmidFinder."""

    NODE_ID = "plasmidfinder"
    DISPLAY_NAME = "PlasmidFinder"
    REQUIRED_CONDA_PACKAGES = ["plasmidfinder"]
    CATEGORY = "annotation"
    DESCRIPTION = "Identify plasmid replicons in bacterial assemblies or reads with PlasmidFinder."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasmidFinder",
        "plasmidfinder",
        "plasmid identification",
        "plasmid replicon",
        "pMLST",
        "bacterial WGS",
        "replicon typing",
    ]
    RETURN_TYPES = ("JSON", "FASTA", "FASTA", "TSV", "TXT", "TXT")
    RETURN_NAMES = ("json_file", "hit_file", "plasmid_file", "result_file", "raw_file", "log_file")
    REQUIRED_EXECUTABLES = ["plasmidfinder.py"]
    DOCUMENTATION_URL = PLASMIDFINDER_DOCUMENTATION_URL
    CITATION_DOIS = [PLASMIDFINDER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASMIDFINDER_CITATION_DOI}"]
    CITATION_TEXT = PLASMIDFINDER_CITATION_TEXT
    VERSION = "2.1.6"
    SHELL = True

    INPUT_FORMATS = ["fasta", "fastq"]
    OUTPUT_SELECTIONS = [
        "data_json",
        "hit_fasta",
        "plasmid_fasta",
        "result_tsv",
        "result_txt",
        "logfile",
    ]
    DEFAULT_OUTPUT_SELECTIONS = ["hit_fasta", "plasmid_fasta", "result_tsv", "result_txt"]
    OUTPUT_FILES = {
        "data_json": "data.json",
        "hit_fasta": "Hit_in_genome_seq.fsa",
        "plasmid_fasta": "Plasmid_seqs.fsa",
        "result_tsv": "results_tab.tsv",
        "result_txt": "results.txt",
        "logfile": "log.txt",
    }

    @classmethod
    def _format_fraction(cls, value: Any, default: float) -> str:
        parsed = float(value if value not in (None, "") else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_dir"

    @classmethod
    def _temp_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/temp_dir"

    @classmethod
    def _log_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/log.txt"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("output_selection"))
        return selected or list(cls.DEFAULT_OUTPUT_SELECTIONS)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "fasta") or "fasta")
        method = "kma" if input_format == "fastq" else "blastn"
        cmd = [
            "plasmidfinder.py",
            "-i",
            str(inputs.get("input_file", "")),
            "-p",
            str(inputs.get("database", "")),
            "-l",
            cls._format_fraction(inputs.get("min_cov"), 0.6),
            "-t",
            cls._format_fraction(inputs.get("threshold"), 0.95),
            "-mp",
            method,
            "-x",
            "-o",
            cls._output_dir(inputs),
            "-tmp",
            cls._temp_dir(inputs),
        ]
        return (
            f"mkdir -p {shlex.quote(cls._output_dir(inputs))} {shlex.quote(cls._temp_dir(inputs))} && "
            f"{_shell_join(cmd)} | tee {shlex.quote(cls._log_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs)]

    @classmethod
    def _fraction_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < 0 or value > 1:
            return f"{name} must be between 0 and 1"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        input_format = str(inputs.get("input_format", "fasta") or "fasta")
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        for name, default in [("min_cov", 0.6), ("threshold", 0.95)]:
            result = cls._fraction_range(inputs, name, default)
            if result is not True:
                return result
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"output_selection values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FILE",
                    {"description": "FASTA assembly or FASTQ reads to scan for plasmid replicons"},
                ),
                "database": (
                    "DIRECTORY",
                    {"description": "PlasmidFinder database directory from Galaxy's plasmidfinder_database table"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.INPUT_FORMATS,
                        "description": "Input data type; FASTA uses blastn and FASTQ uses KMA like the Galaxy wrapper",
                    },
                ),
                "min_cov": (
                    "FLOAT",
                    {
                        "default": 0.6,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum fraction of target sequence covered",
                    },
                ),
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.95,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum nucleotide identity fraction",
                    },
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUT_SELECTIONS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "Galaxy output files to collect from the PlasmidFinder run",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class StaramrSearchNode(CommandNode):
    """Scan bacterial assemblies for AMR genes, point mutations, plasmids, and MLST."""

    NODE_ID = "staramr_search"
    DISPLAY_NAME = "staramr"
    REQUIRED_CONDA_PACKAGES = ["staramr", "mlst"]
    CATEGORY = "annotation"
    DESCRIPTION = "Scan bacterial genome assemblies against ResFinder, PointFinder, and PlasmidFinder databases with starAMR."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "staramr",
        "starAMR",
        "ResFinder",
        "PointFinder",
        "PlasmidFinder",
        "antimicrobial resistance",
        "AMR genes",
        "bacterial WGS",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "TSV", "TSV", "TXT", "XLSX", "DIRECTORY")
    RETURN_NAMES = (
        "mlst",
        "summary",
        "detailed_summary",
        "resfinder",
        "plasmidfinder",
        "pointfinder",
        "settings",
        "excel",
        "blast_hits",
    )
    REQUIRED_EXECUTABLES = ["staramr"]
    DOCUMENTATION_URL = STARAMR_DOCUMENTATION_URL
    CITATION_DOIS = [STARAMR_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{STARAMR_CITATION_DOI}"]
    CITATION_TEXT = STARAMR_CITATION_TEXT
    VERSION = "0.12.3"
    SHELL = True

    POINTFINDER_ORGANISMS = [
        "disabled",
        "campylobacter",
        "enterococcus_faecalis",
        "enterococcus_faecium",
        "escherichia_coli",
        "helicobacter_pylori",
        "salmonella",
        "klebsiella",
        "mycobacterium_tuberculosis",
        "neisseria_gonorrhoeae",
        "plasmodium_falciparum",
        "staphylococcus_aureus",
    ]
    EXCLUDE_GENE_OPTIONS = ["default", "custom", "none"]
    PLASMIDFINDER_TYPES = ["include_all", "gram_positive", "enterobacteriaceae"]
    OUTPUT_SELECTIONS = [
        "mlst_table",
        "summary_table",
        "detailed_summary_table",
        "resfinder_table",
        "plasmidfinder_table",
        "pointfinder_table",
        "settings_output",
        "excel_output",
    ]
    DEFAULT_OUTPUT_SELECTIONS = list(OUTPUT_SELECTIONS)
    OUTPUT_FILES = {
        "mlst_table": "mlst.tsv",
        "summary_table": "summary.tsv",
        "detailed_summary_table": "detailed_summary.tsv",
        "resfinder_table": "resfinder.tsv",
        "plasmidfinder_table": "plasmidfinder.tsv",
        "pointfinder_table": "pointfinder.tsv",
        "settings_output": "settings.txt",
        "excel_output": "results.xlsx",
    }
    PERCENT_OPTIONS = {
        "pid_threshold": 98.0,
        "percent_length_overlap_resfinder": 60.0,
        "percent_length_overlap_plasmidfinder": 60.0,
        "percent_length_overlap_pointfinder": 95.0,
    }
    INTEGER_OPTIONS = {
        "genome_size_lower_bound": 4000000,
        "genome_size_upper_bound": 6000000,
        "minimum_N50_value": 10000,
        "minimum_contig_length": 300,
        "unacceptable_number_contigs": 1000,
    }

    @classmethod
    def _out_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("output_selection"))
        return selected or list(cls.DEFAULT_OUTPUT_SELECTIONS)

    @classmethod
    def _format_number(cls, value: Any, default: float | int) -> str:
        parsed = float(value if value not in (None, "") else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def _integer_value(cls, inputs: dict[str, Any], name: str) -> str:
        value = inputs.get(name, cls.INTEGER_OPTIONS[name])
        return str(int(value if value not in (None, "") else cls.INTEGER_OPTIONS[name]))

    @classmethod
    def _genomes(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("genomes"))

    @classmethod
    def _labels(cls, inputs: dict[str, Any], genomes: list[str]) -> list[str]:
        labels = _as_list(inputs.get("genome_labels"))
        if len(labels) != len(genomes):
            return [Path(genome).stem for genome in genomes]
        return labels

    @classmethod
    def _linked_genomes(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        genomes = cls._genomes(inputs)
        labels = cls._labels(inputs, genomes)
        return [
            (genome, f"{_safe_element_identifier(label)}.fasta")
            for genome, label in zip(genomes, labels)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out_dir(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}"]
        linked_genomes = cls._linked_genomes(inputs)
        for genome, linked_name in linked_genomes:
            commands.append(f"ln -sf {shlex.quote(genome)} {shlex.quote(linked_name)}")
        commands.append("export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*'")

        cmd = [
            "staramr",
            "search",
            "-d",
            str(inputs.get("database", "")),
            "--nprocs",
            "${GALAXY_SLOTS:-1}",
            "--genome-size-lower-bound",
            cls._integer_value(inputs, "genome_size_lower_bound"),
            "--genome-size-upper-bound",
            cls._integer_value(inputs, "genome_size_upper_bound"),
            "--minimum-N50-value",
            cls._integer_value(inputs, "minimum_N50_value"),
            "--minimum-contig-length",
            cls._integer_value(inputs, "minimum_contig_length"),
            "--unacceptable-number-contigs",
            cls._integer_value(inputs, "unacceptable_number_contigs"),
            "--pid-threshold",
            cls._format_number(inputs.get("pid_threshold"), cls.PERCENT_OPTIONS["pid_threshold"]),
            "--percent-length-overlap-resfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_resfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_resfinder"],
            ),
            "--percent-length-overlap-plasmidfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_plasmidfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_plasmidfinder"],
            ),
            "--percent-length-overlap-pointfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_pointfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_pointfinder"],
            ),
        ]
        mlst_scheme = str(inputs.get("mlst_scheme", "auto") or "auto")
        if mlst_scheme != "auto":
            cmd.extend(["--mlst-scheme", mlst_scheme])
        for key, flag in (
            ("report_all_blast", "--report-all-blast"),
            ("exclude_negatives", "--exclude-negatives"),
            ("exclude_resistance_phenotypes", "--exclude-resistance-phenotypes"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        exclude_genes_condition = str(inputs.get("exclude_genes_condition", "default") or "default")
        if exclude_genes_condition == "custom":
            cmd.extend(["--exclude-genes-file", str(inputs.get("exclude_genes_file", ""))])
        elif exclude_genes_condition == "none":
            cmd.append("--no-exclude-genes")
        if inputs.get("complex_mutations_file"):
            cmd.extend(["--complex-mutations-file", str(inputs.get("complex_mutations_file"))])
        plasmidfinder_type = str(inputs.get("plasmidfinder_type", "include_all") or "include_all")
        if plasmidfinder_type != "include_all":
            cmd.extend(["--plasmidfinder-database-type", plasmidfinder_type])

        cmd.extend([
            "--output-summary",
            f"{out}/summary.tsv",
            "--output-detailed-summary",
            f"{out}/detailed_summary.tsv",
            "--output-resfinder",
            f"{out}/resfinder.tsv",
            "--output-plasmidfinder",
            f"{out}/plasmidfinder.tsv",
            "--output-settings",
            f"{out}/settings.txt",
            "--output-excel",
            f"{out}/results.xlsx",
            "--output-mlst",
            f"{out}/mlst.tsv",
            "--output-hits-dir",
            f"{out}/staramr_hits",
        ])
        pointfinder_organism = str(inputs.get("pointfinder_organism", "disabled") or "disabled")
        if pointfinder_organism != "disabled":
            cmd.extend(["--output-pointfinder", f"{out}/pointfinder.tsv", "--pointfinder-organism", pointfinder_organism])
        cmd.extend(linked_name for _, linked_name in linked_genomes)
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        pointfinder_enabled = str(inputs.get("pointfinder_organism", "disabled") or "disabled") != "disabled"
        outputs = [
            out / cls.OUTPUT_FILES[selection]
            for selection in cls._selected_outputs(inputs)
            if selection != "pointfinder_table" or pointfinder_enabled
        ]
        outputs.append(out / "staramr_hits")
        return outputs

    @classmethod
    def _validate_percent(cls, inputs: dict[str, Any], name: str) -> bool | str:
        try:
            value = float(inputs.get(name, cls.PERCENT_OPTIONS[name]))
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < 0 or value > 100:
            return f"{name} must be between 0 and 100"
        return True

    @classmethod
    def _validate_integer(cls, inputs: dict[str, Any], name: str) -> bool | str:
        try:
            value = int(inputs.get(name, cls.INTEGER_OPTIONS[name]))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < 0:
            return f"{name} must be at least 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        genomes = cls._genomes(inputs)
        if not genomes:
            return "at least one genome FASTA is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        labels = _as_list(inputs.get("genome_labels"))
        if labels and len(labels) != len(genomes):
            return "genome_labels must match the number of genomes"
        pointfinder_organism = str(inputs.get("pointfinder_organism", "disabled") or "disabled")
        if pointfinder_organism not in cls.POINTFINDER_ORGANISMS:
            return f"pointfinder_organism must be one of: {', '.join(cls.POINTFINDER_ORGANISMS)}"
        plasmidfinder_type = str(inputs.get("plasmidfinder_type", "include_all") or "include_all")
        if plasmidfinder_type not in cls.PLASMIDFINDER_TYPES:
            return f"plasmidfinder_type must be one of: {', '.join(cls.PLASMIDFINDER_TYPES)}"
        exclude_genes_condition = str(inputs.get("exclude_genes_condition", "default") or "default")
        if exclude_genes_condition not in cls.EXCLUDE_GENE_OPTIONS:
            return f"exclude_genes_condition must be one of: {', '.join(cls.EXCLUDE_GENE_OPTIONS)}"
        if exclude_genes_condition == "custom" and not str(inputs.get("exclude_genes_file", "")).strip():
            return "exclude_genes_file is required when exclude_genes_condition is custom"
        for name in cls.PERCENT_OPTIONS:
            result = cls._validate_percent(inputs, name)
            if result is not True:
                return result
        for name in cls.INTEGER_OPTIONS:
            result = cls._validate_integer(inputs, name)
            if result is not True:
                return result
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"output_selection values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genomes": ("FASTA_LIST", {"multiple": True, "description": "Genome assembly FASTA files to scan"}),
                "database": (
                    "DIRECTORY",
                    {"description": "starAMR database directory containing ResFinder, PointFinder, and PlasmidFinder data"},
                ),
            },
            "optional": {
                "pointfinder_organism": (
                    "STRING",
                    {
                        "default": "disabled",
                        "options": cls.POINTFINDER_ORGANISMS,
                        "description": "Enable PointFinder scanning for a validated or unvalidated organism",
                    },
                ),
                "pid_threshold": ("FLOAT", {"default": 98.0, "min": 0, "max": 100, "description": "BLAST percent identity threshold"}),
                "percent_length_overlap_resfinder": (
                    "FLOAT",
                    {"default": 60.0, "min": 0, "max": 100, "description": "Minimum ResFinder BLAST hit length overlap"},
                ),
                "percent_length_overlap_plasmidfinder": (
                    "FLOAT",
                    {"default": 60.0, "min": 0, "max": 100, "description": "Minimum PlasmidFinder BLAST hit length overlap"},
                ),
                "percent_length_overlap_pointfinder": (
                    "FLOAT",
                    {"default": 95.0, "min": 0, "max": 100, "description": "Minimum PointFinder BLAST hit length overlap"},
                ),
                "genome_size_lower_bound": ("INT", {"default": 4000000, "min": 0, "description": "Lower genome size bound for quality metrics"}),
                "genome_size_upper_bound": ("INT", {"default": 6000000, "min": 0, "description": "Upper genome size bound for quality metrics"}),
                "minimum_N50_value": ("INT", {"default": 10000, "min": 0, "description": "Minimum N50 value for quality metrics"}),
                "minimum_contig_length": ("INT", {"default": 300, "min": 0, "description": "Minimum contig length for quality metrics"}),
                "unacceptable_number_contigs": (
                    "INT",
                    {"default": 1000, "min": 0, "description": "Unacceptable number of contigs for quality metrics"},
                ),
                "mlst_scheme": (
                    "STRING",
                    {"default": "auto", "description": "MLST scheme name; auto lets starAMR detect the scheme"},
                ),
                "report_all_blast": ("BOOLEAN", {"default": False, "description": "Report all BLAST hits"}),
                "exclude_negatives": ("BOOLEAN", {"default": False, "description": "Exclude non-resistant phenotype results"}),
                "exclude_resistance_phenotypes": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude predicted resistance phenotype columns"},
                ),
                "exclude_genes_condition": (
                    "STRING",
                    {
                        "default": "default",
                        "options": cls.EXCLUDE_GENE_OPTIONS,
                        "description": "Use starAMR's default gene exclusion list, a custom list, or no exclusion list",
                    },
                ),
                "exclude_genes_file": (
                    "FILE",
                    {"default": "", "description": "Custom gene exclusion table used when exclude_genes_condition is custom"},
                ),
                "complex_mutations_file": (
                    "FILE",
                    {"default": "", "description": "Optional complex mutations table for PointFinder reports"},
                ),
                "plasmidfinder_type": (
                    "STRING",
                    {
                        "default": "include_all",
                        "options": cls.PLASMIDFINDER_TYPES,
                        "description": "Restrict PlasmidFinder database type or include all available types",
                    },
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUT_SELECTIONS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "Galaxy output reports to collect from the starAMR run",
                    },
                ),
                "genome_labels": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional labels matching genomes; used for Galaxy-style sanitized symlink names",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CheckMLineageWFNode(CommandNode):
    """Assess genome-bin quality with CheckM lineage-specific marker sets."""

    NODE_ID = "checkm_lineage_wf"
    DISPLAY_NAME = "CheckM lineage_wf"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assess genome-bin completeness and contamination using lineage-specific marker sets."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "lineage_wf",
        "lineage-specific marker sets",
        "genome bin quality",
        "MAG quality",
        "SAG quality",
        "completeness contamination",
    ]
    RETURN_TYPES = (
        "TSV",
        "FILE",
        "TSV",
        "DIRECTORY",
        "FASTA",
        "PHYLOXML",
        "DIRECTORY",
        "JSON",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "TSV",
        "DIRECTORY",
        "TSV",
        "FILE",
        "DIRECTORY",
        "TSV",
        "TSV",
    )
    RETURN_NAMES = (
        "results",
        "phylo_hmm_info",
        "bin_stats_tree",
        "hmmer_tree",
        "concatenated_fasta",
        "concatenated_tre",
        "hmmer_tree_ali",
        "concatenated_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
        "marker_file",
        "hmmer_analyze",
        "bin_stats_analyze",
        "checkm_hmm_info",
        "hmmer_analyze_ali",
        "bin_stats_ext",
        "marker_gene_stats",
    )
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    INPUT_MODES = ["individual", "collection"]
    EXTRA_OUTPUT_OPTIONS = [
        "phylo_hmm_info",
        "bin_stats_tree",
        "hmmer_tree",
        "concatenated_tre",
        "concatenated_fasta",
        "hmmer_tree_ali",
        "concatenate_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
        "marker_file",
        "hmmer_analyze",
        "bin_stats_analyze",
        "checkm_hmm_info",
        "hmmer_analyze_ali",
        "bin_stats_ext",
        "marker_gene_stats",
    ]
    PLAN_OUTPUT_ORDER = [
        "phylo_hmm_info",
        "bin_stats_tree",
        "hmmer_tree",
        "concatenated_fasta",
        "concatenated_tre",
        "hmmer_tree_ali",
        "concatenate_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
        "marker_file",
        "hmmer_analyze",
        "bin_stats_analyze",
        "checkm_hmm_info",
        "hmmer_analyze_ali",
        "bin_stats_ext",
        "marker_gene_stats",
    ]
    OPTIONAL_OUTPUT_PATHS = {
        "phylo_hmm_info": ("phylo_hmm_info", ("output", "storage", "phylo_hmm_info.pkl.gz")),
        "bin_stats_tree": ("bin_stats_tree", ("output", "storage", "bin_stats.tree.tsv")),
        "hmmer_tree": ("hmmer_tree", ("output", "bins", "hmmer_tree")),
        "concatenated_fasta": ("concatenated_fasta", ("output", "storage", "tree", "concatenated.fasta")),
        "concatenated_tre": ("concatenated_tre", ("output", "storage", "tree", "concatenated.tre")),
        "hmmer_tree_ali": ("hmmer_tree_ali", ("output", "bins", "hmmer_tree_ali")),
        "concatenate_pplacer_json": (
            "concatenated_pplacer_json",
            ("output", "storage", "tree", "concatenated.pplacer.json"),
        ),
        "genes_fna": ("genes_fna", ("output", "bins", "genes_fna")),
        "genes_faa": ("genes_faa", ("output", "bins", "genes_faa")),
        "genes_gff": ("genes_gff", ("output", "bins", "genes_gff")),
        "marker_file": ("marker_file", ("output", "lineage.ms")),
        "hmmer_analyze": ("hmmer_analyze", ("output", "bins", "hmmer_analyze")),
        "bin_stats_analyze": ("bin_stats_analyze", ("output", "storage", "bin_stats.analyze.tsv")),
        "checkm_hmm_info": ("checkm_hmm_info", ("output", "storage", "checkm_hmm_info.pkl.gz")),
        "hmmer_analyze_ali": ("hmmer_analyze_ali", ("output", "bins", "hmmer_analyze_ali")),
        "bin_stats_ext": ("bin_stats_ext", ("output", "storage", "bin_stats_ext.tsv")),
        "marker_gene_stats": ("marker_gene_stats", ("output", "storage", "marker_gene_stats.tsv")),
    }
    DIRECTORY_OUTPUTS = {
        "hmmer_tree",
        "hmmer_tree_ali",
        "genes_fna",
        "genes_faa",
        "genes_gff",
        "hmmer_analyze",
        "hmmer_analyze_ali",
    }

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("bins", inputs.get("bins_ind", inputs.get("bins_coll", inputs.get("input")))))

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("extra_outputs", [])
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get("element_identifiers", inputs.get("identifiers", inputs.get("labels")))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else "" for identifier in raw]
        elif raw is None or raw == "":
            identifiers = []
        else:
            identifiers = [str(raw)]

        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        resolved: list[str] = []
        for index, input_file in enumerate(input_files):
            identifier = identifiers[index] if index < len(identifiers) else ""
            if input_mode == "collection" and identifier:
                resolved.append(_safe_identifier(identifier))
            else:
                resolved.append(_safe_name(input_file))
        return resolved

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        if input_mode == "collection":
            return f"{identifier}.fasta"
        return f"{identifier}.fasta"

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f"{out}/bins"
        checkm_out = f"{out}/output"
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        identifiers = cls._element_identifiers(inputs, input_files)

        cmd = ["mkdir", "-p", bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{bins_dir}/{cls._link_name(input_mode, identifier)}"])
        cmd.extend(["&&", "checkm", "lineage_wf", bins_dir, checkm_out])
        for name, flag in [
            ("reduced_tree", "--reduced_tree"),
            ("ali", "--ali"),
            ("nt", "--nt"),
            ("genes", "--genes"),
        ]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(["--unique", str(inputs.get("unique", 10)), "--multi", str(inputs.get("multi", 10))])
        for name, flag in [
            ("force_domain", "--force_domain"),
            ("no_refinement", "--no_refinement"),
            ("individual_markers", "--individual_markers"),
            ("skip_adj_correction", "--skip_adj_correction"),
            ("skip_pseudogene_correction", "--skip_pseudogene_correction"),
        ]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(["--aai_strain", str(inputs.get("aai_strain", 0.9))])
        cls._add_bool(cmd, inputs, "ignore_thresholds", "--ignore_thresholds")
        threads = str(inputs.get("threads", 1))
        cmd.extend(
            [
                "--e_value",
                str(inputs.get("e_value", "1e-10")),
                "--length",
                str(inputs.get("length", 0.7)),
                "--file",
                f"{out}/results.tsv",
                "--tab_table",
                "--extension",
                "fasta",
                "--threads",
                threads,
                "--pplacer_threads",
                threads,
            ]
        )
        return cmd

    @classmethod
    def _include_optional_output(cls, option: str, inputs: dict[str, Any]) -> bool:
        if option in {"hmmer_tree_ali", "hmmer_analyze_ali"} and not inputs.get("ali"):
            return False
        if option == "genes_fna" and (inputs.get("genes") or not inputs.get("nt")):
            return False
        if option == "genes_gff" and inputs.get("genes"):
            return False
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "results.tsv"]
        selected = cls._extra_outputs(inputs)
        for option in cls.PLAN_OUTPUT_ORDER:
            if option not in selected or not cls._include_optional_output(option, inputs):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "min_items": 1,
                        "description": "Genome-bin FASTA files to assess",
                    },
                ),
            },
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": cls.INPUT_MODES,
                        "description": "Galaxy bin input structure used for naming symlinks",
                    },
                ),
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for bins",
                    },
                ),
                "reduced_tree": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the reduced reference tree for lineage placement"},
                ),
                "ali": ("BOOLEAN", {"default": False, "description": "Generate HMMER alignment files"}),
                "nt": ("BOOLEAN", {"default": False, "description": "Generate nucleotide gene sequences"}),
                "genes": (
                    "BOOLEAN",
                    {"default": False, "description": "Input bins contain amino-acid genes instead of nucleotide contigs"},
                ),
                "unique": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "Minimum unique phylogenetic markers for lineage-specific marker sets",
                    },
                ),
                "multi": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "Maximum multi-copy phylogenetic markers before using domain-level marker sets",
                    },
                ),
                "force_domain": ("BOOLEAN", {"default": False, "description": "Use domain-level marker sets for all bins"}),
                "no_refinement": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable lineage-specific marker set refinement"},
                ),
                "individual_markers": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat marker genes as independent during QA"},
                ),
                "skip_adj_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not exclude adjacent marker genes when estimating contamination"},
                ),
                "skip_pseudogene_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip pseudogene identification and filtering"},
                ),
                "aai_strain": (
                    "FLOAT",
                    {
                        "default": 0.9,
                        "min": 0,
                        "max": 1,
                        "description": "AAI threshold used to identify strain heterogeneity",
                    },
                ),
                "ignore_thresholds": (
                    "BOOLEAN",
                    {"default": False, "description": "Ignore model-specific score thresholds"},
                ),
                "e_value": ("FLOAT", {"default": 1e-10, "min": 0, "max": 1, "description": "E-value cutoff"}),
                "length": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "description": "Minimum target-query overlap fraction"},
                ),
                "extra_outputs": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": cls.EXTRA_OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "Galaxy extra outputs to collect from the workflow",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one bins value is required"
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        for name in ("unique", "multi"):
            try:
                value = int(inputs.get(name, 10))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be >= 0"
        for name, default in {"aai_strain": 0.9, "e_value": 1e-10, "length": 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0 or value > 1:
                return f"{name} must be between 0 and 1"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True

class CheckMTreeNode(CommandNode):
    """Place genome bins in the CheckM reference genome tree."""

    NODE_ID = "checkm_tree"
    DISPLAY_NAME = "CheckM tree"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Place genome bins in the CheckM reference genome tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm tree",
        "genome tree",
        "phylogenetic placement",
        "phylogenetic marker",
        "pplacer",
    ]
    RETURN_TYPES = (
        "FILE",
        "TSV",
        "DIRECTORY",
        "FASTA",
        "PHYLOXML",
        "DIRECTORY",
        "JSON",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
    )
    RETURN_NAMES = (
        "phylo_hmm_info",
        "bin_stats_tree",
        "hmmer_tree",
        "concatenated_fasta",
        "concatenated_tre",
        "hmmer_tree_ali",
        "concatenated_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
    )
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    EXTRA_OUTPUT_OPTIONS = [
        "hmmer_tree_ali",
        "concatenate_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
    ]
    PLAN_OUTPUT_ORDER = [
        "hmmer_tree_ali",
        "concatenate_pplacer_json",
        "genes_fna",
        "genes_faa",
        "genes_gff",
    ]
    DEFAULT_OUTPUT_PATHS = [
        ("phylo_hmm_info", ("output", "storage", "phylo_hmm_info.pkl.gz")),
        ("bin_stats_tree", ("output", "storage", "bin_stats.tree.tsv")),
        ("hmmer_tree", ("output", "bins", "hmmer_tree")),
        ("concatenated_fasta", ("output", "storage", "tree", "concatenated.fasta")),
        ("concatenated_tre", ("output", "storage", "tree", "concatenated.tre")),
    ]
    OPTIONAL_OUTPUT_PATHS = {
        key: CheckMLineageWFNode.OPTIONAL_OUTPUT_PATHS[key]
        for key in PLAN_OUTPUT_ORDER
    }
    DIRECTORY_OUTPUTS = CheckMLineageWFNode.DIRECTORY_OUTPUTS

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._extra_outputs(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f"{out}/bins"
        checkm_out = f"{out}/output"
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        identifiers = cls._element_identifiers(inputs, input_files)

        cmd = ["mkdir", "-p", bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{bins_dir}/{cls._link_name(input_mode, identifier)}"])
        cmd.extend(["&&", "checkm", "tree", bins_dir, checkm_out])
        for name, flag in [
            ("reduced_tree", "--reduced_tree"),
            ("ali", "--ali"),
            ("nt", "--nt"),
            ("genes", "--genes"),
        ]:
            cls._add_bool(cmd, inputs, name, flag)
        threads = str(inputs.get("threads", 1))
        cmd.extend(["--extension", "fasta", "--threads", threads, "--pplacer_threads", threads])
        return cmd

    @classmethod
    def _include_optional_output(cls, option: str, inputs: dict[str, Any]) -> bool:
        return CheckMLineageWFNode._include_optional_output(option, inputs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for output_name, parts in cls.DEFAULT_OUTPUT_PATHS:
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        selected = cls._extra_outputs(inputs)
        for option in cls.PLAN_OUTPUT_ORDER:
            if option not in selected or not cls._include_optional_output(option, inputs):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "min_items": 1,
                        "description": "Genome-bin FASTA files to place in the CheckM tree",
                    },
                ),
            },
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": cls.INPUT_MODES,
                        "description": "Galaxy bin input structure used for naming symlinks",
                    },
                ),
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for bins",
                    },
                ),
                "reduced_tree": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the reduced reference tree for lineage placement"},
                ),
                "ali": ("BOOLEAN", {"default": False, "description": "Generate phylogenetic HMMER alignment files"}),
                "nt": ("BOOLEAN", {"default": False, "description": "Generate nucleotide gene sequences"}),
                "genes": (
                    "BOOLEAN",
                    {"default": False, "description": "Input bins contain amino-acid genes instead of nucleotide contigs"},
                ),
                "extra_outputs": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": cls.EXTRA_OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "Galaxy extra outputs to collect from CheckM tree",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one bins value is required"
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True

class CheckMTreeQANode(CommandNode):
    """Assess phylogenetic markers and placements in the CheckM genome tree."""

    NODE_ID = "checkm_tree_qa"
    DISPLAY_NAME = "CheckM tree_qa"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assess phylogenetic markers and placements in the CheckM genome tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm tree_qa",
        "tree qa",
        "genome tree placement",
        "phylogenetic markers",
        "Newick",
        "alignment",
    ]
    RETURN_TYPES = ("TSV", "TSV", "PHYLOGENY_TREE", "PHYLOGENY_TREE", "ALIGNMENT")
    RETURN_NAMES = ("output_f1", "output_f2", "output_f3", "output_f4", "output_f5")
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    OUT_FORMATS = ["1", "2", "3", "4", "5"]

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return CheckMQANode._as_csv_list(inputs, name)

    @classmethod
    def _hmmer_tree(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, "hmmer_tree")

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        return CheckMQANode._element_identifiers(inputs, files)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        inputs_dir = f"{out}/inputs"
        storage = f"{inputs_dir}/storage"
        tree_storage = f"{storage}/tree"
        hmmer_files = cls._hmmer_tree(inputs)
        identifiers = cls._element_identifiers(inputs, hmmer_files)
        out_format = str(inputs.get("out_format", "1"))

        cmd = [
            "mkdir",
            "-p",
            storage,
            "&&",
            "ln",
            "-sf",
            str(inputs.get("phylo_hmm_info", "")),
            f"{storage}/phylo_hmm_info.pkl.gz",
            "&&",
            "ln",
            "-sf",
            str(inputs.get("bin_stats_tree", "")),
            f"{storage}/bin_stats.tree.tsv",
        ]
        for input_file, identifier in zip(hmmer_files, identifiers, strict=True):
            bin_dir = f"{inputs_dir}/bins/{identifier}"
            cmd.extend(["&&", "mkdir", "-p", bin_dir, "&&", "ln", "-sf", input_file, f"{bin_dir}/hmmer.tree.txt"])
        cmd.extend(["&&", "mkdir", "-p", tree_storage, "&&", "ln", "-sf"])
        if out_format == "5":
            cmd.extend([str(inputs.get("concatenated_fasta", "")), f"{tree_storage}/concatenated.fasta"])
        else:
            cmd.extend([str(inputs.get("concatenated_tre", "")), f"{tree_storage}/concatenated.tre"])
        cmd.extend(
            [
                "&&",
                "checkm",
                "tree_qa",
                inputs_dir,
                "--out_format",
                out_format,
                "--tab_table",
                "--file",
                f"{out}/output_file",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = str(inputs.get("out_format", "1"))
        if out_format in {"3", "4"}:
            return [out / f"output_f{out_format}.nwk"]
        if out_format == "5":
            return [out / "output_f5.aln.fasta"]
        return [out / f"output_f{out_format}.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "phylo_hmm_info": ("FILE", {"description": "Phylogenetic HMM model info from CheckM tree"}),
                "bin_stats_tree": ("TSV", {"description": "Phylogenetic bin stats from CheckM tree"}),
                "hmmer_tree": (
                    "TXT",
                    {"multiple": True, "description": "Phylogenetic HMM hits collection from CheckM tree"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for hmmer_tree entries"},
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.OUT_FORMATS,
                        "description": "CheckM tree_qa report format to emit",
                    },
                ),
                "concatenated_tre": (
                    "PHYLOGENY_TREE",
                    {"default": "", "description": "Concatenated tree from CheckM tree for out_format 1-4"},
                ),
                "concatenated_fasta": (
                    "FASTA",
                    {"default": "", "description": "Concatenated masked sequences from CheckM tree for out_format 5"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ("phylo_hmm_info", "bin_stats_tree"):
            if not str(inputs.get(required, "")).strip():
                return f"{required} is required"
        if not cls._hmmer_tree(inputs):
            return "at least one hmmer_tree value is required"
        out_format = str(inputs.get("out_format", "1"))
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        if out_format == "5":
            if not str(inputs.get("concatenated_fasta", "")).strip():
                return "concatenated_fasta is required when out_format is 5"
        elif not str(inputs.get("concatenated_tre", "")).strip():
            return "concatenated_tre is required unless out_format is 5"
        return True

class CheckMLineageSetNode(CommandNode):
    """Infer lineage-specific marker sets for each genome bin."""

    NODE_ID = "checkm_lineage_set"
    DISPLAY_NAME = "CheckM lineage_set"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Infer lineage-specific marker sets for each genome bin."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm lineage_set",
        "lineage set",
        "lineage-specific marker sets",
        "marker genes",
        "bin marker set",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("marker",)
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    @classmethod
    def _hmmer_tree(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMTreeQANode._hmmer_tree(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        return CheckMTreeQANode._element_identifiers(inputs, files)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        inputs_dir = f"{out}/inputs"
        storage = f"{inputs_dir}/storage"
        tree_storage = f"{storage}/tree"
        hmmer_files = cls._hmmer_tree(inputs)
        identifiers = cls._element_identifiers(inputs, hmmer_files)

        cmd = [
            "mkdir",
            "-p",
            storage,
            "&&",
            "ln",
            "-sf",
            str(inputs.get("phylo_hmm_info", "")),
            f"{storage}/phylo_hmm_info.pkl.gz",
            "&&",
            "ln",
            "-sf",
            str(inputs.get("bin_stats_tree", "")),
            f"{storage}/bin_stats.tree.tsv",
        ]
        for input_file, identifier in zip(hmmer_files, identifiers, strict=True):
            bin_dir = f"{inputs_dir}/bins/{identifier}"
            cmd.extend(["&&", "mkdir", "-p", bin_dir, "&&", "ln", "-sf", input_file, f"{bin_dir}/hmmer.tree.txt"])
        cmd.extend(
            [
                "&&",
                "mkdir",
                "-p",
                tree_storage,
                "&&",
                "ln",
                "-sf",
                str(inputs.get("concatenated_tre", "")),
                f"{tree_storage}/concatenated.tre",
                "&&",
                "checkm",
                "lineage_set",
                inputs_dir,
                f"{out}/marker.tsv",
                "--unique",
                str(inputs.get("unique", 10)),
                "--multi",
                str(inputs.get("multi", 10)),
            ]
        )
        cls._add_bool(cmd, inputs, "force_domain", "--force_domain")
        cls._add_bool(cmd, inputs, "no_refinement", "--no_refinement")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "marker.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "phylo_hmm_info": ("FILE", {"description": "Phylogenetic HMM model info from CheckM tree"}),
                "bin_stats_tree": ("TSV", {"description": "Phylogenetic bin stats from CheckM tree"}),
                "hmmer_tree": (
                    "TXT",
                    {"multiple": True, "description": "Phylogenetic HMM hits collection from CheckM tree"},
                ),
                "concatenated_tre": (
                    "PHYLOGENY_TREE",
                    {"description": "Concatenated tree from CheckM tree"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for hmmer_tree entries"},
                ),
                "unique": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "Minimum unique phylogenetic markers for lineage-specific marker sets",
                    },
                ),
                "multi": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "Maximum multi-copy phylogenetic markers before using domain-level marker sets",
                    },
                ),
                "force_domain": ("BOOLEAN", {"default": False, "description": "Use domain-level marker sets for all bins"}),
                "no_refinement": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable lineage-specific marker set refinement"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ("phylo_hmm_info", "bin_stats_tree"):
            if not str(inputs.get(required, "")).strip():
                return f"{required} is required"
        if not cls._hmmer_tree(inputs):
            return "at least one hmmer_tree value is required"
        if not str(inputs.get("concatenated_tre", "")).strip():
            return "concatenated_tre is required"
        for name in ("unique", "multi"):
            try:
                value = int(inputs.get(name, 10))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be >= 0"
        return True

class CheckMTaxonSetNode(CommandNode):
    """Generate a taxonomic-specific CheckM marker set."""

    NODE_ID = "checkm_taxon_set"
    DISPLAY_NAME = "CheckM taxon_set"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate a taxonomic-specific CheckM marker set."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm taxon_set",
        "taxon set",
        "taxonomic marker set",
        "marker genes",
        "Prokaryote",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("marker",)
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    RANKS = ["life", "domain", "phylum", "order", "family", "genus", "species"]
    DOMAIN_TAXA = ["Archaea", "Bacteria"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "checkm",
            "taxon_set",
            str(inputs.get("rank", "")),
            str(inputs.get("taxon", "")),
            f"{out}/marker.tsv",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "marker.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "rank": (
                    "STRING",
                    {
                        "default": "life",
                        "options": cls.RANKS,
                        "description": "Taxonomic rank for the CheckM marker set",
                    },
                ),
                "taxon": (
                    "STRING",
                    {
                        "default": "Prokaryote",
                        "description": "Taxon value supported by CheckM for the selected rank",
                    },
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        rank = str(inputs.get("rank", "")).strip()
        if not rank:
            return "rank is required"
        if rank not in cls.RANKS:
            return f"rank must be one of: {', '.join(cls.RANKS)}"
        taxon = str(inputs.get("taxon", "")).strip()
        if not taxon:
            return "taxon is required"
        if rank == "life" and taxon != "Prokaryote":
            return "taxon for rank life must be Prokaryote"
        if rank == "domain" and taxon not in cls.DOMAIN_TAXA:
            return f"taxon for rank domain must be one of: {', '.join(cls.DOMAIN_TAXA)}"
        return True

class CheckMTaxonomyWFNode(CommandNode):
    """Analyze genome bins with a shared taxonomic-specific CheckM marker set."""

    NODE_ID = "checkm_taxonomy_wf"
    DISPLAY_NAME = "CheckM taxonomy_wf"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Analyze genome bins with a shared taxonomic-specific marker set."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm taxonomy_wf",
        "taxonomy_wf",
        "taxonomic marker set",
        "genome bin quality",
        "completeness contamination",
    ]
    RETURN_TYPES = ("TSV", "TSV", "DIRECTORY", "TSV", "FILE", "DIRECTORY", "TSV", "TSV")
    RETURN_NAMES = (
        "results",
        "marker_file",
        "hmmer_analyze",
        "bin_stats_analyze",
        "checkm_hmm_info",
        "hmmer_analyze_ali",
        "bin_stats_ext",
        "marker_gene_stats",
    )
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    RANKS = CheckMTaxonSetNode.RANKS
    DOMAIN_TAXA = CheckMTaxonSetNode.DOMAIN_TAXA
    EXTRA_OUTPUT_OPTIONS = [
        "marker_file",
        "hmmer_analyze",
        "bin_stats_analyze",
        "checkm_hmm_info",
        "hmmer_analyze_ali",
        "bin_stats_ext",
        "marker_gene_stats",
    ]
    OPTIONAL_OUTPUT_PATHS = {
        "marker_file": ("marker_file", ("output", "taxon.ms")),
        "hmmer_analyze": ("hmmer_analyze", ("output", "bins", "hmmer_analyze")),
        "bin_stats_analyze": ("bin_stats_analyze", ("output", "storage", "bin_stats.analyze.tsv")),
        "checkm_hmm_info": ("checkm_hmm_info", ("output", "storage", "checkm_hmm_info.pkl.gz")),
        "hmmer_analyze_ali": ("hmmer_analyze_ali", ("output", "bins", "hmmer_analyze_ali")),
        "bin_stats_ext": ("bin_stats_ext", ("output", "storage", "bin_stats_ext.tsv")),
        "marker_gene_stats": ("marker_gene_stats", ("output", "storage", "marker_gene_stats.tsv")),
    }
    DIRECTORY_OUTPUTS = {"hmmer_analyze", "hmmer_analyze_ali"}

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._extra_outputs(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        CheckMLineageWFNode._add_bool(cmd, inputs, name, flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f"{out}/bins"
        checkm_out = f"{out}/output"
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        identifiers = cls._element_identifiers(inputs, input_files)

        cmd = ["mkdir", "-p", bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{bins_dir}/{cls._link_name(input_mode, identifier)}"])
        cmd.extend(
            [
                "&&",
                "checkm",
                "taxonomy_wf",
                str(inputs.get("rank", "")),
                str(inputs.get("taxon", "")),
                bins_dir,
                checkm_out,
            ]
        )
        for name, flag in [("ali", "--ali"), ("nt", "--nt"), ("genes", "--genes")]:
            cls._add_bool(cmd, inputs, name, flag)
        for name, flag in [
            ("individual_markers", "--individual_markers"),
            ("skip_adj_correction", "--skip_adj_correction"),
            ("skip_pseudogene_correction", "--skip_pseudogene_correction"),
        ]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(["--aai_strain", str(inputs.get("aai_strain", 0.9))])
        cls._add_bool(cmd, inputs, "ignore_thresholds", "--ignore_thresholds")
        cmd.extend(
            [
                "--e_value",
                str(inputs.get("e_value", "1e-10")),
                "--length",
                str(inputs.get("length", 0.7)),
                "--file",
                f"{out}/results.tsv",
                "--tab_table",
                "--extension",
                "fasta",
                "--threads",
                str(inputs.get("threads", 1)),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "results.tsv"]
        selected = cls._extra_outputs(inputs)
        for option in cls.EXTRA_OUTPUT_OPTIONS:
            if option not in selected:
                continue
            if option == "hmmer_analyze_ali" and not inputs.get("ali"):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "rank": (
                    "STRING",
                    {
                        "default": "life",
                        "options": cls.RANKS,
                        "description": "Taxonomic rank for the CheckM marker set",
                    },
                ),
                "taxon": (
                    "STRING",
                    {
                        "default": "Prokaryote",
                        "description": "Taxon value supported by CheckM for the selected rank",
                    },
                ),
                "bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "min_items": 1,
                        "description": "Genome-bin FASTA files to analyze",
                    },
                ),
            },
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": cls.INPUT_MODES,
                        "description": "Galaxy bin input structure used for naming symlinks",
                    },
                ),
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for bins",
                    },
                ),
                "ali": ("BOOLEAN", {"default": False, "description": "Generate HMMER alignment files"}),
                "nt": ("BOOLEAN", {"default": False, "description": "Generate nucleotide gene sequences"}),
                "genes": (
                    "BOOLEAN",
                    {"default": False, "description": "Input bins contain amino-acid genes instead of nucleotide contigs"},
                ),
                "individual_markers": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat marker genes as independent during QA"},
                ),
                "skip_adj_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not exclude adjacent marker genes when estimating contamination"},
                ),
                "skip_pseudogene_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip pseudogene identification and filtering"},
                ),
                "aai_strain": (
                    "FLOAT",
                    {"default": 0.9, "min": 0, "max": 1, "description": "AAI threshold for strain heterogeneity"},
                ),
                "ignore_thresholds": (
                    "BOOLEAN",
                    {"default": False, "description": "Ignore model-specific score thresholds"},
                ),
                "e_value": ("FLOAT", {"default": 1e-10, "min": 0, "max": 1, "description": "E-value cutoff"}),
                "length": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "description": "Minimum target-query overlap fraction"},
                ),
                "extra_outputs": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": cls.EXTRA_OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "Galaxy extra outputs to collect from the taxonomy workflow",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        rank = str(inputs.get("rank", "")).strip()
        if not rank:
            return "rank is required"
        if rank not in cls.RANKS:
            return f"rank must be one of: {', '.join(cls.RANKS)}"
        taxon = str(inputs.get("taxon", "")).strip()
        if not taxon:
            return "taxon is required"
        if rank == "life" and taxon != "Prokaryote":
            return "taxon for rank life must be Prokaryote"
        if rank == "domain" and taxon not in cls.DOMAIN_TAXA:
            return f"taxon for rank domain must be one of: {', '.join(cls.DOMAIN_TAXA)}"
        if not cls._input_files(inputs):
            return "at least one bins value is required"
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        for name, default in {"aai_strain": 0.9, "e_value": 1e-10, "length": 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0 or value > 1:
                return f"{name} must be between 0 and 1"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True

class CheckMTetraNode(CommandNode):
    """Calculate tetranucleotide signatures for FASTA sequences."""

    NODE_ID = "checkm_tetra"
    DISPLAY_NAME = "CheckM tetra"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Calculate tetranucleotide signatures for FASTA sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm tetra",
        "tetra",
        "tetranucleotide",
        "tetranucleotide signatures",
        "sequence composition",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("tetra_profile",)
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "checkm",
            "tetra",
            str(inputs.get("seq_file", "")),
            f"{out}/tetra_profile.tsv",
            "--threads",
            str(inputs.get("threads", 1)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "tetra_profile.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seq_file": ("FASTA", {"description": "Sequences used to generate tetranucleotide signatures"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("seq_file", "")).strip():
            return "seq_file is required"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        return True

class CheckMPlotNode(CommandNode):
    """Generate CheckM genome-bin quality assessment plots."""

    NODE_ID = "checkm_plot"
    DISPLAY_NAME = "CheckM plot"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "visualization"
    DESCRIPTION = "Generate CheckM genome-bin quality assessment plots."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm plot",
        "genome bin plots",
        "GC plot",
        "coding density plot",
        "tetranucleotide distance plot",
        "marker gene position plot",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("gc_plot", "coding_plot", "tetra_plot", "dist_plot", "nx_plot", "len_hist", "marker_plot")
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    PLOT_COMMANDS = ["gc_plot", "coding_plot", "tetra_plot", "dist_plot", "nx_plot", "len_hist", "marker_plot"]
    IMAGE_TYPES = ["eps", "pdf", "png", "svg"]
    DIST_VALUE_MODES = {"gc_plot", "coding_plot", "tetra_plot", "dist_plot"}
    GFF_MODES = {"coding_plot", "tetra_plot", "dist_plot"}
    TETRA_PROFILE_MODES = {"tetra_plot", "dist_plot"}
    OUTPUT_DIRECTORIES = {
        "gc_plot": "gc_plot",
        "coding_plot": "coding_plot",
        "tetra_plot": "tetra_plot",
        "dist_plot": "dist_plot",
        "nx_plot": "nx_plot",
        "len_hist": "len_hist",
        "marker_plot": "marker_plot",
    }

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return CheckMQANode._as_csv_list(inputs, name)

    @classmethod
    def _element_ids_for_files(cls, inputs: dict[str, Any], files: list[str], key: str) -> list[str]:
        return CheckMQANode._element_identifiers(inputs, files, key)

    @classmethod
    def _stage_bins(cls, cmd: list[str], inputs: dict[str, Any], bins_dir: str, output_dir: str) -> None:
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd.extend(["mkdir", "-p", bins_dir, output_dir])
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{bins_dir}/{cls._link_name(input_mode, identifier)}"])

    @classmethod
    def _stage_gff_inputs(cls, cmd: list[str], inputs: dict[str, Any], inputs_dir: str) -> None:
        gff_files = cls._as_csv_list(inputs, "gff")
        identifiers = cls._element_ids_for_files(inputs, gff_files, "gff_element_identifiers")
        for input_file, identifier in zip(gff_files, identifiers, strict=True):
            bin_dir = f"{inputs_dir}/bins/{identifier}"
            cmd.extend(["&&", "mkdir", "-p", bin_dir, "&&", "ln", "-sf", input_file, f"{bin_dir}/genes.gff"])

    @classmethod
    def _stage_marker_inputs(cls, cmd: list[str], inputs: dict[str, Any], inputs_dir: str) -> None:
        cmd.extend(
            [
                "&&",
                "mkdir",
                "-p",
                f"{inputs_dir}/storage",
                "&&",
                "cp",
                str(inputs.get("marker_gene_stats", "")),
                f"{inputs_dir}/storage/marker_gene_stats.tsv",
                "&&",
                "cp",
                str(inputs.get("bin_stats_ext", "")),
                f"{inputs_dir}/storage/bin_stats_ext.tsv",
            ]
        )
        genes_files = cls._as_csv_list(inputs, "genes_fna")
        identifiers = cls._element_ids_for_files(inputs, genes_files, "genes_element_identifiers")
        for input_file, identifier in zip(genes_files, identifiers, strict=True):
            bin_dir = f"{inputs_dir}/bins/{identifier}"
            cmd.extend(["&&", "mkdir", "-p", bin_dir, "&&", "cp", input_file, f"{bin_dir}/genes.faa"])

    @classmethod
    def _add_plot_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--extension",
                "fasta",
                "--image_type",
                str(inputs.get("image_type", "png")),
                "--dpi",
                str(inputs.get("dpi", 600)),
                "--font_size",
                str(inputs.get("font_size", 8)),
                "--width",
                str(inputs.get("width", 6.5)),
                "--height",
                str(inputs.get("height", 3.5)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f"{out}/bins"
        checkm_out = f"{out}/output"
        inputs_dir = f"{out}/inputs"
        plot_command = str(inputs.get("plot_command", inputs.get("command", "gc_plot")) or "gc_plot")
        cmd: list[str] = []
        cls._stage_bins(cmd, inputs, bins_dir, checkm_out)

        if plot_command in cls.GFF_MODES:
            cls._stage_gff_inputs(cmd, inputs, inputs_dir)
        elif plot_command == "marker_plot":
            cls._stage_marker_inputs(cmd, inputs, inputs_dir)

        cmd.extend(["&&", "checkm", plot_command])
        if plot_command in {"coding_plot", "tetra_plot", "dist_plot", "marker_plot"}:
            cmd.append(inputs_dir)
        cmd.extend([bins_dir, checkm_out])
        if plot_command in {"tetra_plot", "dist_plot"}:
            cmd.append(str(inputs.get("tetra_profile", "")))
        if plot_command in cls.DIST_VALUE_MODES and str(inputs.get("dist_value", "")) != "":
            cmd.append(str(inputs.get("dist_value")))
        cls._add_plot_options(cmd, inputs)

        if plot_command == "coding_plot":
            cmd.extend(["--cd_window_size", str(inputs.get("cd_window_size", 10000))])
            cmd.extend(["--cd_bin_width", str(inputs.get("cd_bin_width", 0.01))])
        elif plot_command == "tetra_plot":
            cmd.extend(["--td_window_size", str(inputs.get("td_window_size", 5000))])
            cmd.extend(["--td_bin_width", str(inputs.get("td_bin_width", 0.01))])
        elif plot_command == "dist_plot":
            cmd.extend(["--gc_window_size", str(inputs.get("gc_window_size", 5000))])
            cmd.extend(["--gc_bin_width", str(inputs.get("gc_bin_width", 0.01))])
            cmd.extend(["--cd_window_size", str(inputs.get("cd_window_size", 10000))])
            cmd.extend(["--cd_bin_width", str(inputs.get("cd_bin_width", 0.01))])
            cmd.extend(["--td_window_size", str(inputs.get("td_window_size", 5000))])
            cmd.extend(["--td_bin_width", str(inputs.get("td_bin_width", 0.01))])
        elif plot_command == "nx_plot":
            cmd.extend(["--step_size", str(inputs.get("step_size", 0.05))])
        elif plot_command == "marker_plot":
            cmd.extend(["--fig_padding", str(inputs.get("fig_padding", 0.2))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        plot_command = str(inputs.get("plot_command", inputs.get("command", "gc_plot")) or "gc_plot")
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        directory = out / cls.OUTPUT_DIRECTORIES.get(plot_command, plot_command)
        directory.mkdir(parents=True, exist_ok=True)
        return [directory]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "min_items": 1,
                        "description": "Genome-bin FASTA files to plot",
                    },
                ),
                "plot_command": (
                    "STRING",
                    {
                        "default": "gc_plot",
                        "options": cls.PLOT_COMMANDS,
                        "description": "CheckM plot command to run",
                    },
                ),
            },
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": cls.INPUT_MODES,
                        "description": "Galaxy bin input structure used for naming symlinks",
                    },
                ),
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for bins",
                    },
                ),
                "gff": (
                    "GFF_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Gene feature files for coding, tetra, and distribution plots",
                    },
                ),
                "gff_element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for gff entries"},
                ),
                "tetra_profile": ("TSV", {"default": "", "description": "Tetranucleotide profile from CheckM tetra"}),
                "genes_fna": (
                    "FASTA_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Nucleotide gene sequences for marker plots",
                    },
                ),
                "genes_element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for genes_fna entries"},
                ),
                "marker_gene_stats": ("TSV", {"default": "", "description": "Marker gene stats for marker plots"}),
                "bin_stats_ext": ("TSV", {"default": "", "description": "Extended bin stats for marker plots"}),
                "dist_value": ("INT", {"default": "", "min": 0, "max": 100, "description": "Reference distribution to plot"}),
                "image_type": ("STRING", {"default": "png", "options": cls.IMAGE_TYPES, "description": "Image type"}),
                "dpi": ("INT", {"default": 600, "min": 0, "description": "DPI of output image"}),
                "font_size": ("INT", {"default": 8, "min": 0, "description": "Font size"}),
                "width": ("FLOAT", {"default": 6.5, "min": 0, "description": "Output image width"}),
                "height": ("FLOAT", {"default": 3.5, "min": 0, "description": "Output image height"}),
                "gc_window_size": ("INT", {"default": 5000, "min": 0, "description": "GC histogram window size"}),
                "gc_bin_width": ("FLOAT", {"default": 0.01, "min": 0, "description": "GC histogram bin width"}),
                "cd_window_size": ("INT", {"default": 10000, "min": 0, "description": "Coding-density window size"}),
                "cd_bin_width": ("FLOAT", {"default": 0.01, "min": 0, "description": "Coding-density bin width"}),
                "td_window_size": ("INT", {"default": 5000, "min": 0, "description": "Tetranucleotide-distance window size"}),
                "td_bin_width": (
                    "FLOAT",
                    {"default": 0.01, "min": 0, "description": "Tetranucleotide-distance bin width"},
                ),
                "step_size": ("FLOAT", {"default": 0.05, "min": 0, "description": "Nx plot step size"}),
                "fig_padding": ("FLOAT", {"default": 0.2, "min": 0, "description": "White space around figure in inches"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_numeric(cls, inputs: dict[str, Any], name: str, default: Any, *, integer: bool) -> bool | str:
        raw = inputs.get(name, default)
        if raw == "":
            return True
        try:
            value = int(raw) if integer else float(raw)
        except (TypeError, ValueError):
            return f"{name} must be {'an integer' if integer else 'a number'}"
        if value < 0:
            return f"{name} must be >= 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one bins value is required"
        plot_command = str(inputs.get("plot_command", inputs.get("command", "gc_plot")) or "gc_plot")
        if plot_command not in cls.PLOT_COMMANDS:
            return f"plot_command must be one of: {', '.join(cls.PLOT_COMMANDS)}"
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        if plot_command in cls.GFF_MODES and not cls._as_csv_list(inputs, "gff"):
            return f"at least one gff value is required for {plot_command}"
        if plot_command in cls.TETRA_PROFILE_MODES and not str(inputs.get("tetra_profile", "")).strip():
            return f"tetra_profile is required for {plot_command}"
        if plot_command == "marker_plot":
            if not cls._as_csv_list(inputs, "genes_fna"):
                return "at least one genes_fna value is required for marker_plot"
            for required in ("marker_gene_stats", "bin_stats_ext"):
                if not str(inputs.get(required, "")).strip():
                    return f"{required} is required for marker_plot"
        image_type = str(inputs.get("image_type", "png") or "png")
        if image_type not in cls.IMAGE_TYPES:
            return f"image_type must be one of: {', '.join(cls.IMAGE_TYPES)}"
        for name, default in {
            "dist_value": "",
            "dpi": 600,
            "font_size": 8,
            "gc_window_size": 5000,
            "cd_window_size": 10000,
            "td_window_size": 5000,
        }.items():
            result = cls._validate_numeric(inputs, name, default, integer=True)
            if result is not True:
                return result
        for name, default in {
            "width": 6.5,
            "height": 3.5,
            "gc_bin_width": 0.01,
            "cd_bin_width": 0.01,
            "td_bin_width": 0.01,
            "step_size": 0.05,
            "fig_padding": 0.2,
        }.items():
            result = cls._validate_numeric(inputs, name, default, integer=False)
            if result is not True:
                return result
        return True

class CheckMAnalyzeNode(CommandNode):
    """Identify marker genes in genome bins with CheckM analyze."""

    NODE_ID = "checkm_analyze"
    DISPLAY_NAME = "CheckM analyze"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Identify marker genes in genome bins and calculate genome statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm analyze",
        "marker genes",
        "genome bin statistics",
        "MAG quality",
        "completeness contamination",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "FILE", "DIRECTORY")
    RETURN_NAMES = ("hmmer_analyze", "bin_stats_analyze", "checkm_hmm_info", "hmmer_analyze_ali")
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    EXTRA_OUTPUT_OPTIONS = ["hmmer_analyze_ali"]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("extra_outputs", [])
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f"{out}/bins"
        checkm_out = f"{out}/output"
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        identifiers = cls._element_identifiers(inputs, input_files)

        cmd = ["mkdir", "-p", bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{bins_dir}/{cls._link_name(input_mode, identifier)}"])
        cmd.extend([
            "&&",
            "checkm",
            "analyze",
            str(inputs.get("marker_file", "")),
            bins_dir,
            checkm_out,
        ])
        for name, flag in [("ali", "--ali"), ("nt", "--nt"), ("genes", "--genes")]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(["--extension", "fasta", "--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        hmmer_out = out / "output" / "bins" / "hmmer_analyze"
        hmmer_out.mkdir(parents=True, exist_ok=True)
        storage = out / "output" / "storage"
        storage.mkdir(parents=True, exist_ok=True)
        outputs = [
            hmmer_out,
            storage / "bin_stats.analyze.tsv",
            storage / "checkm_hmm_info.pkl.gz",
        ]
        if inputs.get("ali") and "hmmer_analyze_ali" in cls._extra_outputs(inputs):
            ali_out = out / "output" / "bins" / "hmmer_analyze_ali"
            ali_out.mkdir(parents=True, exist_ok=True)
            outputs.append(ali_out)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "marker_file": ("TSV", {"description": "Marker gene set from CheckM lineage_set or taxon_set"}),
                "bins": (
                    "FASTA_LIST",
                    {"multiple": True, "min_items": 1, "description": "Genome-bin FASTA files to analyze"},
                ),
            },
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": cls.INPUT_MODES,
                        "description": "Galaxy bin input structure used for naming symlinks",
                    },
                ),
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for bins",
                    },
                ),
                "ali": ("BOOLEAN", {"default": False, "description": "Generate HMMER alignment files"}),
                "nt": ("BOOLEAN", {"default": False, "description": "Generate nucleotide gene sequences"}),
                "genes": (
                    "BOOLEAN",
                    {"default": False, "description": "Input bins contain amino-acid genes instead of nucleotide contigs"},
                ),
                "extra_outputs": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": cls.EXTRA_OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "Galaxy extra outputs to collect from the analyze run",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("marker_file", "")).strip():
            return "marker_file is required"
        if not cls._input_files(inputs):
            return "at least one bins value is required"
        input_mode = str(inputs.get("input_mode", inputs.get("select", "individual")) or "individual")
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True

class CheckMQANode(CommandNode):
    """Assess CheckM analyze results for genome-bin completeness and contamination."""

    NODE_ID = "checkm_qa"
    DISPLAY_NAME = "CheckM qa"
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assess genome bins for completeness and contamination from CheckM analyze outputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm",
        "CheckM",
        "checkm qa",
        "genome completeness",
        "genome contamination",
        "bin quality",
        "marker gene stats",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "bin_stats_ext", "marker_gene_stats")
    REQUIRED_EXECUTABLES = ["checkm"]
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    CITATION_DOIS = ["10.1101/gr.186072.114"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.186072.114"]
    CITATION_TEXT = (
        "CheckM assesses genome completeness and contamination using lineage-specific marker sets."
    )
    VERSION = "1.2.5+galaxy0"
    SHELL = True

    OUT_FORMATS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    EXTRA_OUTPUT_OPTIONS = ["marker_gene_stats"]

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        raw = inputs.get(name, [])
        if isinstance(raw, str):
            if "," in raw:
                return [part.strip() for part in raw.split(",") if part.strip()]
            return [raw] if raw else []
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _hmmer_analyze(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, "hmmer_analyze")

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, "extra_outputs")

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str], key: str = "element_identifiers") -> list[str]:
        raw = inputs.get(key, inputs.get("identifiers", inputs.get("labels")))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else "" for identifier in raw]
        elif raw is None or raw == "":
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(file)
            for index, file in enumerate(files)
        ]

    @classmethod
    def _stage_collection(cls, cmd: list[str], files: list[str], identifiers: list[str], out: str, filename: str) -> None:
        for input_file, identifier in zip(files, identifiers, strict=True):
            bin_dir = f"{out}/output/bins/{identifier}"
            cmd.extend(["&&", "mkdir", "-p", bin_dir, "&&", "cp", input_file, f"{bin_dir}/{filename}"])

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        checkm_out = f"{out}/output"
        storage = f"{checkm_out}/storage"
        hmmer_files = cls._hmmer_analyze(inputs)
        hmmer_ids = cls._element_identifiers(inputs, hmmer_files)
        cmd = [
            "mkdir",
            "-p",
            storage,
            "&&",
            "cp",
            str(inputs.get("checkm_hmm_info", "")),
            f"{storage}/checkm_hmm_info.pkl.gz",
            "&&",
            "cp",
            str(inputs.get("bin_stats_analyze", "")),
            f"{storage}/bin_stats.analyze.tsv",
        ]
        cls._stage_collection(cmd, hmmer_files, hmmer_ids, out, "hmmer.analyze.txt")
        if str(inputs.get("out_format", "1")) == "9":
            genes_files = cls._as_csv_list(inputs, "genes_faa")
            gene_ids = cls._element_identifiers(inputs, genes_files, "genes_element_identifiers")
            cls._stage_collection(cmd, genes_files, gene_ids, out, "genes.faa")

        cmd.extend(
            [
                "&&",
                "checkm",
                "qa",
                str(inputs.get("marker_file", "")),
                checkm_out,
                "--out_format",
                str(inputs.get("out_format", "1")),
                "--tab_table",
                "--file",
                f"{out}/output.tsv",
            ]
        )
        _add_if_value(cmd, "--exclude_markers", inputs.get("exclude_markers"))
        for name, flag in [
            ("individual_markers", "--individual_markers"),
            ("skip_adj_correction", "--skip_adj_correction"),
            ("skip_pseudogene_correction", "--skip_pseudogene_correction"),
        ]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(["--aai_strain", str(inputs.get("aai_strain", 0.9))])
        cls._add_bool(cmd, inputs, "ignore_thresholds", "--ignore_thresholds")
        cmd.extend(["--e_value", str(inputs.get("e_value", "1e-10")), "--length", str(inputs.get("length", 0.7))])
        _add_if_value(cmd, "--coverage_file", inputs.get("coverage"))
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        storage = out / "output" / "storage"
        storage.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.tsv", storage / "bin_stats_ext.tsv"]
        if "marker_gene_stats" in cls._extra_outputs(inputs):
            outputs.append(storage / "marker_gene_stats.tsv")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "marker_file": ("TSV", {"description": "Marker gene set used for CheckM QA"}),
                "checkm_hmm_info": ("FILE", {"description": "Marker gene HMM info from CheckM analyze"}),
                "bin_stats_analyze": ("TSV", {"description": "Marker gene bin stats from CheckM analyze"}),
                "hmmer_analyze": (
                    "TXT",
                    {"multiple": True, "description": "Marker gene HMM hits collection from CheckM analyze"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for hmmer_analyze entries"},
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.OUT_FORMATS,
                        "description": "CheckM QA report format to emit",
                    },
                ),
                "genes_faa": (
                    "FASTA_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Protein gene sequences required when out_format is 9",
                    },
                ),
                "genes_element_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Optional identifiers for genes_faa entries"},
                ),
                "exclude_markers": ("FILE", {"default": "", "description": "Optional marker IDs to exclude"}),
                "individual_markers": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat marker genes as independent during QA"},
                ),
                "skip_adj_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not exclude adjacent marker genes when estimating contamination"},
                ),
                "skip_pseudogene_correction": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip pseudogene identification and filtering"},
                ),
                "aai_strain": (
                    "FLOAT",
                    {"default": 0.9, "min": 0, "max": 1, "description": "AAI threshold for strain heterogeneity"},
                ),
                "ignore_thresholds": (
                    "BOOLEAN",
                    {"default": False, "description": "Ignore model-specific score thresholds"},
                ),
                "e_value": ("FLOAT", {"default": 1e-10, "min": 0, "max": 1, "description": "E-value cutoff"}),
                "length": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "description": "Minimum target-query overlap fraction"},
                ),
                "coverage": ("FILE", {"default": "", "description": "Optional coverage file generated by CheckM coverage"}),
                "extra_outputs": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": cls.EXTRA_OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "Galaxy extra outputs to collect from CheckM qa",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ("marker_file", "checkm_hmm_info", "bin_stats_analyze"):
            if not str(inputs.get(required, "")).strip():
                return f"{required} is required"
        if not cls._hmmer_analyze(inputs):
            return "at least one hmmer_analyze value is required"
        out_format = str(inputs.get("out_format", "1"))
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        if out_format == "9" and not cls._as_csv_list(inputs, "genes_faa"):
            return "genes_faa is required when out_format is 9"
        for name, default in {"aai_strain": 0.9, "e_value": 1e-10, "length": 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0 or value > 1:
                return f"{name} must be between 0 and 1"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True

class CheckM2Node(CommandNode):
    """Assess MAG, SAG, or isolate genome quality with CheckM2."""

    NODE_ID = "checkm2"
    DISPLAY_NAME = "CheckM2"
    REQUIRED_CONDA_PACKAGES = ["checkm2"]
    CATEGORY = "qc"
    DESCRIPTION = "Rapidly predict genome bin completeness and contamination for MAGs, SAGs, and isolate genomes using CheckM2 machine-learning models."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "checkm2",
        "CheckM2",
        "genome quality",
        "MAG quality",
        "SAG quality",
        "completeness contamination",
        "bin quality",
    ]
    RETURN_TYPES = ("TSV", "FASTA_LIST", "TSV_LIST")
    RETURN_NAMES = ("quality", "protein_files", "diamond_files")
    REQUIRED_EXECUTABLES = ["checkm2"]
    DOCUMENTATION_URL = "https://github.com/chklovski/CheckM2"
    CITATION_DOIS = ["10.1038/s41592-023-01940-w"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-023-01940-w"]
    CITATION_TEXT = "CheckM2: a rapid, scalable and accurate tool for assessing microbial genome quality using machine learning."
    VERSION = "1.1.0"
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input", inputs.get("inputs")))

    @classmethod
    def _link_name(cls, path: str) -> str:
        return f"{_safe_name(path)}.dat"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input_dir"
        output_dir = f"{out}/output"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        for input_file in cls._input_files(inputs):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{input_dir}/{cls._link_name(input_file)}"])
        cmd.extend(["&&", "checkm2", "predict", "--input", input_dir])
        model = str(inputs.get("model", ""))
        if model:
            cmd.append(model)
        if inputs.get("genes"):
            cmd.append("--genes")
        _add_if_value(cmd, "--ttable", inputs.get("ttable"))
        cmd.extend([
            "-x",
            ".dat",
            "--threads",
            str(inputs.get("threads", 1)),
            "--database_path",
            str(inputs.get("database_path", inputs.get("database", ""))),
            "--output-directory",
            output_dir,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        protein_out = out / "protein_files"
        diamond_out = out / "diamond_output"
        protein_out.mkdir(parents=True, exist_ok=True)
        diamond_out.mkdir(parents=True, exist_ok=True)
        return [out / "quality_report.tsv", protein_out, diamond_out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA_LIST", {"description": "Input MAG, SAG, isolate genome, or predicted protein FASTA files"}),
                "database_path": ("FILE", {"description": "CheckM2 DIAMOND database path, such as uniref100.KO.1.dmnd"}),
            },
            "optional": {
                "genes": ("BOOLEAN", {"default": False, "description": "Treat input files as predicted protein FASTA files"}),
                "model": ("STRING", {"default": "", "options": ["", "--general", "--specific", "--allmodels"], "description": "Force general, specific, or both quality prediction models"}),
                "ttable": ("STRING", {"default": "", "options": CHECKM2_TRANSLATION_TABLES, "description": "Prodigal translation table for nucleotide inputs"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CheRRIEvalNode(CommandNode):
    """Evaluate RNA-RNA interaction sites with CheRRI."""

    NODE_ID = "cherri_eval"
    DISPLAY_NAME = "Evaluation of RRIs using CheRRI"
    REQUIRED_CONDA_PACKAGES = ["cherri"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Evaluate RNA-RNA interaction sites with a trained CheRRI model."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CheRRI",
        "cherri_eval",
        "cherri eval",
        "RNA-RNA interaction",
        "RRI evaluation",
        "interaction site filtering",
        "IntaRNA",
    ]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("eval_out",)
    REQUIRED_EXECUTABLES = ["cherri", "tar"]
    DOCUMENTATION_URL = CHERRI_DOCUMENTATION_URL
    CITATION_URLS = [CHERRI_CITATION_URL]
    CITATION_TEXT = CHERRI_CITATION_TEXT
    VERSION = "0.7"
    SHELL = True

    @classmethod
    def _on_off(cls, value: Any, default: bool) -> str:
        if value is None:
            return "on" if default else "off"
        if isinstance(value, str):
            return "off" if value.lower() in {"false", "0", "no", "off", ""} else "on"
        return "on" if bool(value) else "off"

    @classmethod
    def _context(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("context", 150))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "cherri",
            "eval",
            "-i1",
            str(inputs.get("rris_table", "")),
            "-g",
            "genome.fa",
            "-l",
            str(inputs.get("chrom_len_file", "")),
            "-o",
            ".",
            "-on",
            cls.NODE_ID,
            "-c",
            cls._context(inputs),
            "-st",
            cls._on_off(inputs.get("use_structure"), True),
            "-hf",
            cls._on_off(inputs.get("hand_feat"), False),
            "-m",
            "model_dir/final_full.model",
            "-mp",
            "model_dir/features.npz",
        ]
        _add_if_value(cmd, "-i2", inputs.get("occupied_regions"))
        _add_if_value(cmd, "-p", inputs.get("intarna_param_file"))
        setup = [
            _shell_join(["mkdir", "-p", out]),
            f"cd {shlex.quote(out)}",
            "export PYTHONHASHSEED=31337",
            _shell_join(["ln", "-s", str(inputs.get("genome_fasta", "")), "genome.fa"]),
            _shell_join(["mkdir", "model_dir"]),
            f"{_shell_join(['tar', '-C', 'model_dir', '-xvf', str(inputs.get('model_tar', ''))])} > /dev/null",
            _shell_join(cmd),
        ]
        return " && ".join(setup)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / cls.NODE_ID / "evaluation"
        out.mkdir(parents=True, exist_ok=True)
        return [out / "evaluation_results_eval_rri.csv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "rris_table": ("CSV", {"description": "CSV table of RNA-RNA interactions"}),
                "genome_fasta": ("FASTA", {"description": "Reference genome FASTA"}),
                "chrom_len_file": ("TSV", {"description": "Two-column chromosome length table"}),
                "model_tar": ("FILE", {"description": "CheRRI model and feature files tarball"}),
            },
            "optional": {
                "context": ("INT", {"default": 150, "min": 0}),
                "use_structure": ("BOOLEAN", {"default": True}),
                "hand_feat": ("BOOLEAN", {"default": False}),
                "occupied_regions": (
                    "FILE",
                    {"default": "", "description": "Optional occupied-region Python object file"},
                ),
                "intarna_param_file": ("TXT", {"default": "", "description": "Optional IntaRNA parameter file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ("rris_table", "genome_fasta", "chrom_len_file", "model_tar"):
            if not str(inputs.get(required, "")).strip():
                return f"{required} is required"
        try:
            context = int(inputs.get("context", 150))
        except (TypeError, ValueError):
            return "context must be an integer"
        if context < 0:
            return "context must be greater than or equal to 0"
        return True

class CheRRITrainNode(CommandNode):
    """Train a CheRRI model from RNA-RNA interaction summary files."""

    NODE_ID = "cherri_train"
    DISPLAY_NAME = "Train a CheRRI model using RRIs"
    REQUIRED_CONDA_PACKAGES = ["cherri"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Train a CheRRI model from RNA-RNA interaction summary files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CheRRI",
        "cherri_train",
        "cherri train",
        "RNA-RNA interaction",
        "RRI model training",
        "ChiRA interaction summary",
        "mixed model",
        "IntaRNA",
    ]
    RETURN_TYPES = ("TGZ",)
    RETURN_NAMES = ("out_model",)
    REQUIRED_EXECUTABLES = ["cherri", "tar"]
    DOCUMENTATION_URL = CHERRI_DOCUMENTATION_URL
    CITATION_URLS = [CHERRI_CITATION_URL]
    CITATION_TEXT = CHERRI_CITATION_TEXT
    VERSION = "0.7+galaxy0"
    SHELL = True

    @classmethod
    def _context(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("context", 150))

    @classmethod
    def _run_time(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("run_time", 43200))

    @classmethod
    def _on_off(cls, value: Any, default: bool) -> str:
        return CheRRIEvalNode._on_off(value, default)

    @classmethod
    def _safe_experiment_name(cls, value: Any) -> str:
        name = re.sub(r"[^0-9A-Za-z_]", "_", str(value or "myExperiment"))
        return name or "myExperiment"

    @classmethod
    def _experiments(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        experiments = inputs.get("experiments")
        if isinstance(experiments, str) and experiments.strip():
            parsed = json.loads(experiments)
            if isinstance(parsed, list):
                experiments = parsed
        if isinstance(experiments, (list, tuple)) and experiments:
            normalized: list[dict[str, Any]] = []
            for index, experiment in enumerate(experiments):
                if isinstance(experiment, dict):
                    normalized.append(dict(experiment))
                else:
                    normalized.append({"exp_name": f"experiment_{index + 1}", "rep_samples": [str(experiment)]})
            return normalized
        return [
            {
                "exp_name": inputs.get("experiment_name", "myExperiment"),
                "genome_fasta": inputs.get("genome_fasta", ""),
                "chrom_len_file": inputs.get("chrom_len_file", ""),
                "rep_samples": inputs.get("rep_samples", []),
                "occupied_regions": inputs.get("occupied_regions", ""),
            }
        ]

    @classmethod
    def _common_params(cls, inputs: dict[str, Any]) -> list[str]:
        cmd: list[str] = []
        _add_if_value(cmd, "-p", inputs.get("intarna_param_file"))
        cmd.extend(
            [
                "-c",
                cls._context(inputs),
                "-st",
                cls._on_off(inputs.get("use_structure"), True),
                "-t",
                cls._run_time(inputs),
                "-me",
                "${GALAXY_MEMORY_MB_PER_SLOT:-8000}",
                "-j",
                "${GALAXY_SLOTS:-1}",
            ]
        )
        if cls._on_off(inputs.get("filter_hybrid"), False) == "on":
            cmd.extend(["-f", "on"])
        return cmd

    @classmethod
    def _experiment_commands(cls, experiment: dict[str, Any], inputs: dict[str, Any], mixed: bool) -> tuple[str, list[str]]:
        exp_name = cls._safe_experiment_name(experiment.get("exp_name", experiment.get("experiment_name", "myExperiment")))
        rep_samples = _as_list(experiment.get("rep_samples", experiment.get("samples", experiment.get("files"))))
        commands = [
            _shell_join(["mkdir", exp_name]),
            _shell_join(["mkdir", f"{exp_name}/tmp"]),
            _shell_join(["ln", "-s", str(experiment.get("genome_fasta", "")), f"{exp_name}/genome.fa"]),
        ]
        replicate_names: list[str] = []
        for index, sample in enumerate(rep_samples):
            replicate_name = f"{index}.tabular"
            replicate_names.append(replicate_name)
            commands.append(_shell_join(["ln", "-s", sample, f"{exp_name}/{replicate_name}"]))
        cmd = [
            "cherri",
            "train",
            "-i1",
            exp_name,
            "-r",
            *replicate_names,
            "-g",
            f"{exp_name}/genome.fa",
            "-l",
            str(experiment.get("chrom_len_file", "")),
            "-n",
            exp_name,
        ]
        _add_if_value(cmd, "-i2", experiment.get("occupied_regions"))
        cmd.extend(["-o", ".", "-on", exp_name, "-tp", f"{exp_name}/tmp"])
        cmd.extend(cls._common_params(inputs))
        commands.append(_shell_join(cmd).replace("'${GALAXY_MEMORY_MB_PER_SLOT:-8000}'", "${GALAXY_MEMORY_MB_PER_SLOT:-8000}").replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        if mixed:
            commands.extend(
                [
                    _shell_join(["mkdir", "-p", "mixed_model"]),
                    _shell_join(["ln", "-s", f"../{exp_name}", f"mixed_model/{exp_name}"]),
                ]
            )
        return exp_name, commands

    @classmethod
    def _single_model_links(cls, exp_name: str, inputs: dict[str, Any]) -> list[str]:
        context = cls._context(inputs)
        commands = [
            _shell_join(
                [
                    "ln",
                    "-s",
                    f"{exp_name}/model/optimized/full_{exp_name}_context_{context}.model",
                    "final_full.model",
                ]
            )
        ]
        if cls._on_off(inputs.get("use_structure"), True) == "off":
            feature_path = f"{exp_name}/model/features/{exp_name}_context_{context}.npz"
        else:
            feature_path = f"{exp_name}/feature_files/training_data_{exp_name}_context_{context}.npz"
        commands.append(_shell_join(["ln", "-s", feature_path, "features.npz"]))
        return commands

    @classmethod
    def _mixed_model_commands(cls, exp_names: list[str], inputs: dict[str, Any]) -> list[str]:
        context = cls._context(inputs)
        cmd = [
            "cherri",
            "train",
            "-mi",
            "on",
            "-i1",
            "mixed_model",
            "-r",
            *exp_names,
            "-g",
            "/not/needed/",
            "-l",
            "/not/needed/",
            "-n",
            "mixed",
            "-o",
            ".",
            "-on",
            "mixed_model",
            "-tp",
            "mixed_model/tmp",
        ]
        cmd.extend(cls._common_params(inputs))
        command = _shell_join(cmd).replace("'${GALAXY_MEMORY_MB_PER_SLOT:-8000}'", "${GALAXY_MEMORY_MB_PER_SLOT:-8000}").replace(
            "'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"
        )
        commands = [_shell_join(["mkdir", "mixed_model/tmp"]), command]
        commands.append(
            _shell_join(
                [
                    "ln",
                    "-s",
                    f"mixed_model/mixed/model/optimized/full_mixed_context_{context}.model",
                    "final_full.model",
                ]
            )
        )
        if cls._on_off(inputs.get("use_structure"), True) == "off":
            feature_path = f"mixed_model/mixed/model/features/mixed_context_{context}.npz"
        else:
            feature_path = f"mixed_model/mixed/feature_files/training_data_mixed_context_{context}.npz"
        commands.append(_shell_join(["ln", "-s", feature_path, "features.npz"]))
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        experiments = cls._experiments(inputs)
        mixed = len(experiments) > 1
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", "export PYTHONHASHSEED=31337"]
        exp_names: list[str] = []
        for experiment in experiments:
            exp_name, experiment_commands = cls._experiment_commands(experiment, inputs, mixed)
            exp_names.append(exp_name)
            commands.extend(experiment_commands)
        if mixed:
            commands.extend(cls._mixed_model_commands(exp_names, inputs))
        else:
            commands.extend(cls._single_model_links(exp_names[0], inputs))
        commands.append(_shell_join(["tar", "-zhcvf", "model.tgz", "final_full.model", "features.npz"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "model.tgz"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "experiments": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Experiment objects with exp_name, genome_fasta, chrom_len_file, rep_samples, and optional occupied_regions",
                    },
                ),
                "experiment_name": ("STRING", {"default": "myExperiment"}),
                "genome_fasta": ("FASTA", {"default": ""}),
                "chrom_len_file": ("TSV", {"default": ""}),
                "rep_samples": ("TSV", {"default": [], "is_list": True}),
                "occupied_regions": ("BED", {"default": ""}),
                "context": ("INT", {"default": 150, "min": 0}),
                "intarna_param_file": ("TXT", {"default": ""}),
                "use_structure": ("BOOLEAN", {"default": True}),
                "run_time": ("INT", {"default": 43200, "min": 0}),
                "filter_hybrid": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            experiments = cls._experiments(inputs)
        except json.JSONDecodeError:
            return "experiments must be valid JSON"
        for index, experiment in enumerate(experiments):
            prefix = f"experiments[{index}]." if inputs.get("experiments") else ""
            if not str(experiment.get("genome_fasta", "")).strip():
                return f"{prefix}genome_fasta is required"
            if not str(experiment.get("chrom_len_file", "")).strip():
                return f"{prefix}chrom_len_file is required"
            if not _as_list(experiment.get("rep_samples", experiment.get("samples", experiment.get("files")))):
                return f"{prefix}at least one rep_samples value is required"
        for name, default in {"context": 150, "run_time": 43200}.items():
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be greater than or equal to 0"
        return True

class ChiraCollapseNode(CommandNode):
    """Deduplicate FASTQ reads for ChiRA analysis."""

    NODE_ID = "chira_collapse"
    DISPLAY_NAME = "ChiRA collapse"
    REQUIRED_CONDA_PACKAGES = ["chira"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Deduplicate FASTQ reads and write unique sequences with UMI and read counts."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ChiRA",
        "ChiRA collapse",
        "chira_collapse",
        "chira_collapse.py",
        "chimeric read analysis",
        "RNA-RNA interactome",
        "deduplicate fastq reads",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("collapsed_fasta",)
    REQUIRED_EXECUTABLES = ["chira_collapse.py", "gunzip"]
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHIRA_CITATION_DOI}"]
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = "1.4.3+galaxy1"
    SHELL = True

    @classmethod
    def _input_fastq(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_fastq", inputs.get("in", "")) or "")

    @classmethod
    def _command_input(cls, input_fastq: str) -> str:
        if input_fastq.endswith(".gz"):
            return f"<(gunzip -c {shlex.quote(input_fastq)})"
        return shlex.quote(input_fastq)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fastq = cls._input_fastq(inputs)
        command_input = cls._command_input(input_fastq)
        cmd = (
            f"chira_collapse.py -i {command_input} -u {shlex.quote(str(inputs.get('umi_len', 0)))} "
            f"-o {shlex.quote(f'{out}/collapsed.fasta')}"
        )
        return f"{_shell_join(['mkdir', '-p', out])} && {cmd}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "collapsed.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fastq": ("FASTQ", {"description": "Quality- and adapter-trimmed FASTQ reads"}),
            },
            "optional": {
                "umi_len": ("INT", {"default": 0, "min": 0, "description": "5-prime UMI length"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_fastq(inputs).strip():
            return "input_fastq is required"
        try:
            umi_len = int(inputs.get("umi_len", 0))
        except (TypeError, ValueError):
            return "umi_len must be an integer"
        if umi_len < 0:
            return "umi_len must be >= 0"
        return True

class ChiraMapNode(CommandNode):
    """Map ChiRA reads to transcriptome references."""

    NODE_ID = "chira_map"
    DISPLAY_NAME = "ChiRA map"
    REQUIRED_CONDA_PACKAGES = ["chira"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Map collapsed ChiRA reads to single or split transcriptome references."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ChiRA",
        "ChiRA map",
        "chira_map",
        "chira_map.py",
        "chimeric read mapping",
        "RNA-RNA interactome",
        "BWA-MEM",
        "CLAN",
    ]
    RETURN_TYPES = ("BED", "FASTA")
    RETURN_NAMES = ("mapped_bed", "unmapped_fasta")
    REQUIRED_EXECUTABLES = ["chira_map.py"]
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHIRA_CITATION_DOI}"]
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = "1.4.3+galaxy0"
    SHELL = True

    REF_TYPES = ["split", "single"]
    ALIGNERS = ["bwa", "clan"]
    STRANDED_OPTIONS = ["fw", "rc", "both"]
    BWA_INT_DEFAULTS = {
        "seed_length1": 12,
        "seed_length2": 16,
        "align_score1": 18,
        "align_score2": 16,
        "match1": 1,
        "mismatch1": 4,
        "match2": 1,
        "mismatch2": 6,
        "gapo1": 6,
        "gape1": 1,
        "gapo2": 100,
        "gape2": 100,
        "nhits1": 50,
        "nhits2": 100,
    }

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_type", "split") or "split")

    @classmethod
    def _aligner(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("aligner", "bwa") or "bwa")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        aligner = cls._aligner(inputs)
        cmd = ["chira_map.py", "-b", "-a", aligner, "-i", str(inputs.get("query", ""))]
        if aligner == "bwa":
            cmd.extend(
                [
                    "-s",
                    str(inputs.get("stranded", "fw") or "fw"),
                    "-l1",
                    str(inputs.get("seed_length1", 12)),
                    "-l2",
                    str(inputs.get("seed_length2", 16)),
                    "-s1",
                    str(inputs.get("align_score1", 18)),
                    "-s2",
                    str(inputs.get("align_score2", 16)),
                    "-ma1",
                    str(inputs.get("match1", 1)),
                    "-mm1",
                    str(inputs.get("mismatch1", 4)),
                    "-ma2",
                    str(inputs.get("match2", 1)),
                    "-mm2",
                    str(inputs.get("mismatch2", 6)),
                    "-go1",
                    str(inputs.get("gapo1", 6)),
                    "-ge1",
                    str(inputs.get("gape1", 1)),
                    "-go2",
                    str(inputs.get("gapo2", 100)),
                    "-ge2",
                    str(inputs.get("gape2", 100)),
                    "-h1",
                    str(inputs.get("nhits1", 50)),
                    "-h2",
                    str(inputs.get("nhits2", 100)),
                ]
            )
        else:
            cmd.extend(
                [
                    "-s2",
                    str(inputs.get("align_score", 10)),
                    "-co",
                    str(inputs.get("chimeric_overlap", 2)),
                ]
            )
        if cls._ref_type(inputs) == "single":
            cmd.extend(["-f1", str(inputs.get("ref_fasta", ""))])
        else:
            cmd.extend(["-f1", str(inputs.get("ref_fasta1", "")), "-f2", str(inputs.get("ref_fasta2", ""))])
        cmd.extend(["-p", f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}", "-o", "./"])
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "sorted.bed"]
        if cls._aligner(inputs) == "bwa":
            outputs.append(out / "unmapped.fasta")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Collapsed ChiRA read FASTA"}),
                "ref_type": ("STRING", {"default": "split", "options": cls.REF_TYPES, "description": "Single or split reference"}),
                "aligner": ("STRING", {"default": "bwa", "options": cls.ALIGNERS, "description": "Alignment engine"}),
            },
            "optional": {
                "ref_fasta": ("FASTA", {"default": "", "description": "Reference FASTA for single-reference mode"}),
                "ref_fasta1": ("FASTA", {"default": "", "description": "First reference FASTA for split mode"}),
                "ref_fasta2": ("FASTA", {"default": "", "description": "Second reference FASTA for split mode"}),
                "stranded": ("STRING", {"default": "fw", "options": cls.STRANDED_OPTIONS, "description": "BWA strand mode"}),
                "seed_length1": ("INT", {"default": 12, "min": 1}),
                "seed_length2": ("INT", {"default": 16, "min": 1}),
                "align_score1": ("INT", {"default": 18, "min": 1}),
                "align_score2": ("INT", {"default": 16, "min": 1}),
                "match1": ("INT", {"default": 1}),
                "mismatch1": ("INT", {"default": 4}),
                "match2": ("INT", {"default": 1}),
                "mismatch2": ("INT", {"default": 6}),
                "gapo1": ("INT", {"default": 6}),
                "gape1": ("INT", {"default": 1}),
                "gapo2": ("INT", {"default": 100}),
                "gape2": ("INT", {"default": 100}),
                "nhits1": ("INT", {"default": 50}),
                "nhits2": ("INT", {"default": 100}),
                "align_score": ("INT", {"default": 10, "min": 1, "description": "CLAN minimum fragment length"}),
                "chimeric_overlap": ("INT", {"default": 2, "description": "Maximum overlap between chimeric read segments"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum:
            return f"{name} must be >= {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("query", "")).strip():
            return "query is required"
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        aligner = cls._aligner(inputs)
        if aligner not in cls.ALIGNERS:
            return f"aligner must be one of: {', '.join(cls.ALIGNERS)}"
        if ref_type == "single":
            if not str(inputs.get("ref_fasta", "")).strip():
                return "ref_fasta is required when ref_type is single"
        else:
            if not str(inputs.get("ref_fasta1", "")).strip():
                return "ref_fasta1 is required when ref_type is split"
            if not str(inputs.get("ref_fasta2", "")).strip():
                return "ref_fasta2 is required when ref_type is split"
        if aligner == "bwa":
            stranded = str(inputs.get("stranded", "fw") or "fw")
            if stranded not in cls.STRANDED_OPTIONS:
                return f"stranded must be one of: {', '.join(cls.STRANDED_OPTIONS)}"
            for name, default in cls.BWA_INT_DEFAULTS.items():
                result = cls._validate_int_min(inputs, name, default, 1)
                if result is not True:
                    return result
        else:
            for name in ["align_score", "chimeric_overlap"]:
                result = cls._validate_int_min(inputs, name, 10 if name == "align_score" else 2, 1)
                if result is not True:
                    return result
        result = cls._validate_int_min(inputs, "threads", 4, 1)
        if result is not True:
            return result
        return True

class ChiraMergeNode(CommandNode):
    """Merge ChiRA read alignments into loci."""

    NODE_ID = "chira_merge"
    DISPLAY_NAME = "ChiRA merge"
    REQUIRED_CONDA_PACKAGES = ["chira"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Merge overlapping ChiRA read alignments into read-concentrated loci."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ChiRA",
        "ChiRA merge",
        "chira_merge",
        "chira_merge.py",
        "read-concentrated loci",
        "chimeric read loci",
        "blockbuster",
    ]
    RETURN_TYPES = ("BED", "TSV")
    RETURN_NAMES = ("segments_bed", "merged_bed")
    REQUIRED_EXECUTABLES = ["chira_merge.py"]
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHIRA_CITATION_DOI}"]
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = "1.4.3+galaxy0"
    SHELL = True

    ANNOTATION_CHOICES = ["yes", "no"]
    MERGE_MODES = ["overlap", "blockbuster"]
    REF_TYPES = ["single", "split"]

    @classmethod
    def _annotation_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("annotation_choice", inputs.get("choice", "no")) or "no")

    @classmethod
    def _merge_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("merge_mode", inputs.get("mode", "overlap")) or "overlap")

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_type", "single") or "single")

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["chira_merge.py", "-b", str(inputs.get("alignments", ""))]
        if cls._annotation_choice(inputs) == "yes":
            cmd.extend(["-g", str(inputs.get("gtf", ""))])
        cmd.extend(
            [
                "-so",
                str(inputs.get("segment_overlap", 0.7)),
                "-lt",
                str(inputs.get("length_threshold", 0.9)),
                "-ao",
                str(inputs.get("alignment_overlap", 0.7)),
            ]
        )
        if cls._merge_mode(inputs) == "blockbuster":
            cmd.extend(
                [
                    "-bb",
                    "-d",
                    str(inputs.get("distance", 30)),
                    "-mc",
                    str(inputs.get("min_cluster_height", 10)),
                    "-mb",
                    str(inputs.get("min_block_height", 10)),
                    "-sc",
                    str(inputs.get("scale", 0.1)),
                ]
            )
        else:
            cmd.extend(["-ls", str(inputs.get("min_locus_size", 1))])
        if cls._ref_type(inputs) == "split":
            cmd.extend(["-f1", str(inputs.get("ref_fasta1", "")), "-f2", str(inputs.get("ref_fasta2", ""))])
        if cls._bool_flag(inputs.get("chimeric_only", False)):
            cmd.append("-c")
        cmd.extend(["-o", "./"])
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "segments.bed", out / "merged.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignments": ("BED", {"description": "ChiRA alignment BED file"}),
                "annotation_choice": ("STRING", {"default": "no", "options": cls.ANNOTATION_CHOICES}),
                "merge_mode": ("STRING", {"default": "overlap", "options": cls.MERGE_MODES}),
                "ref_type": ("STRING", {"default": "single", "options": cls.REF_TYPES}),
            },
            "optional": {
                "gtf": ("GTF", {"default": "", "description": "GTF/GFF annotation for genomic coordinate conversion"}),
                "segment_overlap": ("FLOAT", {"default": 0.7, "min": 0, "max": 1}),
                "length_threshold": ("FLOAT", {"default": 0.9, "min": 0, "max": 1}),
                "alignment_overlap": ("FLOAT", {"default": 0.7, "min": 0, "max": 1}),
                "min_locus_size": ("INT", {"default": 1, "min": 1}),
                "distance": ("INT", {"default": 30, "min": 0}),
                "min_cluster_height": ("INT", {"default": 10, "min": 0}),
                "min_block_height": ("INT", {"default": 10, "min": 0}),
                "scale": ("FLOAT", {"default": 0.1, "min": 0, "max": 1}),
                "ref_fasta1": ("FASTA", {"default": "", "description": "First split-reference FASTA"}),
                "ref_fasta2": ("FASTA", {"default": "", "description": "Second split-reference FASTA"}),
                "chimeric_only": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if not 0 <= value <= 1:
            return f"{name} must be between 0 and 1"
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum:
            return f"{name} must be >= {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments", "")).strip():
            return "alignments is required"
        annotation_choice = cls._annotation_choice(inputs)
        if annotation_choice not in cls.ANNOTATION_CHOICES:
            return f"annotation_choice must be one of: {', '.join(cls.ANNOTATION_CHOICES)}"
        if annotation_choice == "yes" and not str(inputs.get("gtf", "")).strip():
            return "gtf is required when annotation_choice is yes"
        merge_mode = cls._merge_mode(inputs)
        if merge_mode not in cls.MERGE_MODES:
            return f"merge_mode must be one of: {', '.join(cls.MERGE_MODES)}"
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        if ref_type == "split":
            if not str(inputs.get("ref_fasta1", "")).strip():
                return "ref_fasta1 is required when ref_type is split"
            if not str(inputs.get("ref_fasta2", "")).strip():
                return "ref_fasta2 is required when ref_type is split"
        for name, default in {"segment_overlap": 0.7, "length_threshold": 0.9, "alignment_overlap": 0.7}.items():
            result = cls._validate_float_range(inputs, name, default)
            if result is not True:
                return result
        if merge_mode == "overlap":
            result = cls._validate_int_min(inputs, "min_locus_size", 1, 1)
            if result is not True:
                return result
        else:
            for name, default in {"distance": 30, "min_cluster_height": 10, "min_block_height": 10}.items():
                result = cls._validate_int_min(inputs, name, default, 0)
                if result is not True:
                    return result
            result = cls._validate_float_range(inputs, "scale", 0.1)
            if result is not True:
                return result
        return True

class ChiraQuantifyNode(CommandNode):
    """Quantify ChiRA read-concentrated loci."""

    NODE_ID = "chira_quantify"
    DISPLAY_NAME = "ChiRA quantify"
    REQUIRED_CONDA_PACKAGES = ["chira"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Create and quantify ChiRA read-concentrated loci from merged alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ChiRA",
        "ChiRA quantify",
        "chira_quantify",
        "chira_quantify.py",
        "read-concentrated loci",
        "CRL",
        "CRL TPM",
        "TPM",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("loci",)
    REQUIRED_EXECUTABLES = ["chira_quantify.py"]
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHIRA_CITATION_DOI}"]
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = "1.4.3+galaxy0"
    SHELL = True

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "chira_quantify.py",
            "-b",
            str(inputs.get("segments", "")),
            "-m",
            str(inputs.get("merged", "")),
            "-cs",
            str(inputs.get("crl_share", 0.7)),
            "-ls",
            str(inputs.get("min_locus_size", 10)),
            "-e",
            str(inputs.get("em_threshold", 0.00001)),
        ]
        if cls._bool_flag(inputs.get("crl", True)):
            cmd.append("-crl")
        cmd.extend(["-o", "./"])
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "loci.counts"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "segments": ("BED", {"description": "BED file of aligned ChiRA segments"}),
                "merged": ("TSV", {"description": "Tabular file of merged ChiRA alignments"}),
            },
            "optional": {
                "crl_share": ("FLOAT", {"default": 0.7, "min": 0, "max": 1}),
                "min_locus_size": ("INT", {"default": 10, "min": 1}),
                "em_threshold": ("FLOAT", {"default": 0.00001, "min": 0}),
                "crl": ("BOOLEAN", {"default": True, "description": "Create and quantify CRLs"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if not 0 <= value <= 1:
            return f"{name} must be between 0 and 1"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("segments", "")).strip():
            return "segments is required"
        if not str(inputs.get("merged", "")).strip():
            return "merged is required"
        result = cls._validate_float_range(inputs, "crl_share", 0.7)
        if result is not True:
            return result
        try:
            min_locus_size = int(inputs.get("min_locus_size", 10))
        except (TypeError, ValueError):
            return "min_locus_size must be an integer"
        if min_locus_size < 1:
            return "min_locus_size must be >= 1"
        try:
            em_threshold = float(inputs.get("em_threshold", 0.00001))
        except (TypeError, ValueError):
            return "em_threshold must be numeric"
        if em_threshold < 0:
            return "em_threshold must be >= 0"
        return True

class ChiraExtractNode(CommandNode):
    """Extract ChiRA chimeric alignments and interaction summaries."""

    NODE_ID = "chira_extract"
    DISPLAY_NAME = "ChiRA extract"
    REQUIRED_CONDA_PACKAGES = ["chira"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Extract best ChiRA chimeric alignments and optionally summarize interactions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ChiRA",
        "ChiRA extract",
        "chira_extract",
        "chira_extract.py",
        "chimeric reads",
        "chimeric alignments",
        "RNA-RNA interactions",
        "CRL",
        "IntaRNA",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("chimeras", "interactions")
    REQUIRED_EXECUTABLES = ["chira_extract.py"]
    DOCUMENTATION_URL = CHIRA_DOCUMENTATION_URL
    CITATION_DOIS = [CHIRA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHIRA_CITATION_DOI}"]
    CITATION_TEXT = CHIRA_CITATION_TEXT
    VERSION = "1.4.3+galaxy1"
    SHELL = True

    ANNOTATION_CHOICES = ["yes", "no"]
    FASTA_SOURCE_OPTIONS = ["history", "preloaded"]
    REF_TYPES = ["split", "single"]
    INTARNA_MODES = ["H", "M", "S"]

    @classmethod
    def _annotation_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("annot_choice", inputs.get("annotation_choice", "no")) or "no")

    @classmethod
    def _fasta_source_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("fasta_source_selector", "history") or "history")

    @classmethod
    def _ref_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_type", "split") or "split")

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _genomic_fasta(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("genomic_fasta", inputs.get("fasta", inputs.get("fasta_id", ""))) or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}"]
        annot_choice = cls._annotation_choice(inputs)
        hybridize = cls._bool_flag(inputs.get("hybridize", False))
        genomic_ref = ""
        if annot_choice == "yes":
            if cls._fasta_source_selector(inputs) == "history":
                genomic_fasta = cls._genomic_fasta(inputs)
                if genomic_fasta:
                    commands.append(_shell_join(["ln", "-s", genomic_fasta, "genome.fa"]))
                    genomic_ref = "genome.fa"
            else:
                genomic_ref = cls._genomic_fasta(inputs)
        cmd = [
            "chira_extract.py",
            "--loci",
            str(inputs.get("loci", "")),
        ]
        if annot_choice == "yes":
            cmd.extend(["--gtf", str(inputs.get("gtf", ""))])
            if hybridize:
                cmd.extend(["--ref", genomic_ref])
        cmd.extend(
            [
                "--tpm_cutoff",
                str(inputs.get("tpm_cutoff", 0)),
                "--score_cutoff",
                str(inputs.get("score_cutoff", 0)),
                "--chimeric_overlap",
                str(inputs.get("chimeric_overlap", 2)),
            ]
        )
        if cls._ref_type(inputs) == "single":
            cmd.extend(["-f1", str(inputs.get("ref_fasta", ""))])
        else:
            cmd.extend(["-f1", str(inputs.get("ref_fasta1", "")), "-f2", str(inputs.get("ref_fasta2", ""))])
        if hybridize:
            cmd.append("-r")
        if not cls._bool_flag(inputs.get("seed_interaction", True)):
            cmd.append("--no_seed")
        cmd.extend(
            [
                "--seed_bp",
                str(inputs.get("seed_bp", 5)),
                "--seed_min_pu",
                str(inputs.get("seed_min_pu", 0)),
                "--accessibility",
                "C" if cls._bool_flag(inputs.get("accessibility", False)) else "N",
                "--acc_width",
                str(inputs.get("acc_width", 150)),
                "--intarna_mode",
                str(inputs.get("intarna_mode", "H") or "H"),
                "--temperature",
                str(inputs.get("temperature", 37)),
            ]
        )
        if cls._bool_flag(inputs.get("summarize", False)):
            cmd.append("-s")
        cmd.extend(["--processes", f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}", "--out", "./"])
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        commands.append(command)
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "chimeras"]
        if cls._bool_flag(inputs.get("summarize", False)):
            outputs.append(out / "interactions")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "loci": ("TSV", {"description": "Tabular file containing ChiRA CRL information"}),
                "annot_choice": ("STRING", {"default": "no", "options": cls.ANNOTATION_CHOICES}),
                "ref_type": ("STRING", {"default": "split", "options": cls.REF_TYPES}),
            },
            "optional": {
                "gtf": ("GTF", {"default": "", "description": "GTF/GFF annotation for genomic loci"}),
                "fasta_source_selector": ("STRING", {"default": "history", "options": cls.FASTA_SOURCE_OPTIONS}),
                "genomic_fasta": ("FASTA", {"default": "", "description": "Genomic FASTA for annotated hybridization"}),
                "tpm_cutoff": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "score_cutoff": ("FLOAT", {"default": 0, "min": 0, "max": 2}),
                "chimeric_overlap": ("INT", {"default": 2, "min": 0}),
                "ref_fasta1": ("FASTA", {"default": "", "description": "First split-reference FASTA"}),
                "ref_fasta2": ("FASTA", {"default": "", "description": "Second split-reference FASTA"}),
                "ref_fasta": ("FASTA", {"default": "", "description": "Single-reference FASTA"}),
                "hybridize": ("BOOLEAN", {"default": False}),
                "intarna_mode": ("STRING", {"default": "H", "options": cls.INTARNA_MODES}),
                "seed_interaction": ("BOOLEAN", {"default": True}),
                "seed_bp": ("INT", {"default": 5, "min": 2, "max": 20}),
                "seed_min_pu": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "accessibility": ("BOOLEAN", {"default": False}),
                "acc_width": ("INT", {"default": 150, "min": 0, "max": 99999}),
                "temperature": ("FLOAT", {"default": 37, "min": 0, "max": 100}),
                "summarize": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_float_range(
        cls, inputs: dict[str, Any], name: str, default: float, minimum: float, maximum: float
    ) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if not minimum <= value <= maximum:
            return f"{name} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def _validate_int_range(
        cls, inputs: dict[str, Any], name: str, default: int, minimum: int, maximum: int
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if not minimum <= value <= maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("loci", "")).strip():
            return "loci is required"
        annot_choice = cls._annotation_choice(inputs)
        if annot_choice not in cls.ANNOTATION_CHOICES:
            return f"annot_choice must be one of: {', '.join(cls.ANNOTATION_CHOICES)}"
        fasta_source = cls._fasta_source_selector(inputs)
        if fasta_source not in cls.FASTA_SOURCE_OPTIONS:
            return f"fasta_source_selector must be one of: {', '.join(cls.FASTA_SOURCE_OPTIONS)}"
        hybridize = cls._bool_flag(inputs.get("hybridize", False))
        if annot_choice == "yes":
            if not str(inputs.get("gtf", "")).strip():
                return "gtf is required when annot_choice is yes"
            if hybridize and not cls._genomic_fasta(inputs).strip():
                return (
                    "genomic_fasta is required when annot_choice is yes, hybridize is true, "
                    f"and fasta_source_selector is {fasta_source}"
                )
        for name, default, minimum, maximum in [
            ("tpm_cutoff", 0, 0, 1),
            ("score_cutoff", 0, 0, 2),
            ("seed_min_pu", 0, 0, 1),
            ("temperature", 37, 0, 100),
        ]:
            result = cls._validate_float_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        for name, default, minimum, maximum in [
            ("chimeric_overlap", 2, 0, 99999),
            ("seed_bp", 5, 2, 20),
            ("acc_width", 150, 0, 99999),
            ("threads", 2, 1, 128),
        ]:
            result = cls._validate_int_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        ref_type = cls._ref_type(inputs)
        if ref_type not in cls.REF_TYPES:
            return f"ref_type must be one of: {', '.join(cls.REF_TYPES)}"
        if ref_type == "single":
            if not str(inputs.get("ref_fasta", "")).strip():
                return "ref_fasta is required when ref_type is single"
        else:
            if not str(inputs.get("ref_fasta1", "")).strip():
                return "ref_fasta1 is required when ref_type is split"
            if not str(inputs.get("ref_fasta2", "")).strip():
                return "ref_fasta2 is required when ref_type is split"
        intarna_mode = str(inputs.get("intarna_mode", "H") or "H")
        if intarna_mode not in cls.INTARNA_MODES:
            return f"intarna_mode must be one of: {', '.join(cls.INTARNA_MODES)}"
        return True

class ChewBBACAAlleleCallNode(CommandNode):
    """Determine allelic profiles for genome assemblies with chewBBACA."""

    NODE_ID = "chewbbaca_allelecall"
    DISPLAY_NAME = "ChewBBACA AlleleCall"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Determine allelic profiles for genome assemblies with a chewBBACA schema."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_allelecall",
        "ChewBBACA AlleleCall",
        "AlleleCall",
        "cgMLST",
        "wgMLST",
        "allelic profiles",
        "schema_seed",
        "bacterial typing",
    ]
    RETURN_TYPES = ("TSV_LIST", "TXT_LIST", "FASTA", "FASTA", "FASTA")
    RETURN_NAMES = ("allelecall_results", "allelecall_log", "unclassified_fasta", "missing_fasta", "novel_fasta")
    REQUIRED_EXECUTABLES = ["chewBBACA.py", "unzip"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    OUTPUT_OPTIONS = ["output_unclassified", "output_missing", "output_novel", "hash_profile"]
    PRODIGAL_MODES = ["single", "meta"]
    MODES = ["1", "2", "3", "4"]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_file", inputs.get("input_files")))

    @classmethod
    def _output_selector(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("output_selector"))

    @classmethod
    def _safe_input_name(cls, path: str) -> str:
        name = Path(path).name
        if "." in name:
            stem, ext = name.rsplit(".", 1)
            return f"{_safe_element_identifier(stem)}.{_safe_element_identifier(ext)}"
        return _safe_element_identifier(name)

    @classmethod
    def _prodigal_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("prodigal_mode", "single") or "single")

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("mode", "4") or "4")

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", "mkdir input", "mkdir schema"]
        for input_file in cls._input_files(inputs):
            commands.append(_shell_join(["ln", "-sf", input_file, f"input/{cls._safe_input_name(input_file)}"]))
        commands.append(_shell_join(["unzip", str(inputs.get("input_schema", "")), "-d", "schema"]))
        cmd = ["chewBBACA.py", "AlleleCall"]
        _add_if_value(cmd, "--ptf", inputs.get("training_file"))
        if cls._bool_flag(inputs, "cds_input"):
            cmd.append("--cds-input")
        _add_if_value(cmd, "--gl", inputs.get("genes_list"))
        _add_if_value(cmd, "--bsr", inputs.get("blast_score_ratio"))
        _add_if_value(cmd, "--l", inputs.get("minimum_length"))
        _add_if_value(cmd, "--t", inputs.get("translation_table"))
        _add_if_value(cmd, "--st", inputs.get("size_threshold"))
        if cls._bool_flag(inputs, "no_inferred"):
            cmd.append("--no-inferred")
        cmd.extend(["--pm", cls._prodigal_mode(inputs), "--mode", cls._mode(inputs), "--force-continue"])
        selected = set(cls._output_selector(inputs))
        if "output_unclassified" in selected:
            cmd.append("--output-unclassified")
        if "output_missing" in selected:
            cmd.append("--output-missing")
        if "output_novel" in selected:
            cmd.append("--output-novel")
        if "hash_profile" in selected:
            cmd.extend(["--hash-profile", "md5"])
        cmd.extend(["-i", "input", "-g", "schema/schema_seed/", "-o", "output"])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out, out]
        selected = set(cls._output_selector(inputs))
        if "output_unclassified" in selected:
            outputs.append(out / "unclassified_sequences.fasta")
        if "output_missing" in selected:
            outputs.append(out / "missing_classes.fasta")
        if "output_novel" in selected:
            outputs.append(out / "novel_alleles.fasta")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTA", {"is_list": True, "multiple": True, "description": "Genome assemblies"}),
                "input_schema": ("FILE", {"description": "chewBBACA schema ZIP archive"}),
            },
            "optional": {
                "genes_list": ("TXT", {"default": ""}),
                "training_file": ("FILE", {"default": ""}),
                "cds_input": ("BOOLEAN", {"default": False}),
                "blast_score_ratio": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "minimum_length": ("INT", {"default": "", "min": 0}),
                "translation_table": ("INT", {"default": "", "min": 0}),
                "size_threshold": ("FLOAT", {"default": "", "min": 0}),
                "no_inferred": ("BOOLEAN", {"default": False}),
                "prodigal_mode": ("STRING", {"default": "single", "options": cls.PRODIGAL_MODES}),
                "mode": ("STRING", {"default": "4", "options": cls.MODES}),
                "output_selector": (
                    "STRING_LIST",
                    {"default": [], "options": cls.OUTPUT_OPTIONS, "multiple": True, "display": "checkboxes"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_optional_int(cls, inputs: dict[str, Any], name: str) -> bool | str:
        raw = inputs.get(name, "")
        if raw == "":
            return True
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < 0:
            return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def _validate_optional_float(cls, inputs: dict[str, Any], name: str, upper: float | None = None) -> bool | str:
        raw = inputs.get(name, "")
        if raw == "":
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if value < 0:
            return f"{name} must be greater than or equal to 0"
        if upper is not None and value > upper:
            return f"{name} must be between 0 and {int(upper)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one input_file value is required"
        if not str(inputs.get("input_schema", "")).strip():
            return "input_schema is required"
        if cls._mode(inputs) not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        if cls._prodigal_mode(inputs) not in cls.PRODIGAL_MODES:
            return f"prodigal_mode must be one of: {', '.join(cls.PRODIGAL_MODES)}"
        result = cls._validate_optional_float(inputs, "blast_score_ratio", 1)
        if result is not True:
            return result
        for name in ("minimum_length", "translation_table"):
            result = cls._validate_optional_int(inputs, name)
            if result is not True:
                return result
        result = cls._validate_optional_float(inputs, "size_threshold")
        if result is not True:
            return result
        unsupported = [value for value in cls._output_selector(inputs) if value not in cls.OUTPUT_OPTIONS]
        if unsupported:
            return f"output_selector values must be one or more of: {', '.join(cls.OUTPUT_OPTIONS)}"
        return True

class ChewBBACAAlleleCallEvaluatorNode(CommandNode):
    """Build chewBBACA allele calling evaluation reports."""

    NODE_ID = "chewbbaca_allelecallevaluator"
    DISPLAY_NAME = "chewBBACA AlleleCallEvaluator"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Build an interactive report for chewBBACA allele calling result evaluation."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_allelecallevaluator",
        "chewBBACA AlleleCallEvaluator",
        "AlleleCallEvaluator",
        "AlleleCall",
        "cgMLST",
        "presence absence",
        "distance matrix",
        "Neighbor-Joining tree",
    ]
    RETURN_TYPES = ("HTML_REPORT", "FASTA", "TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = (
        "html_file",
        "cgMLST_MSA",
        "cgMLST_profiles",
        "distance_matrix_symmetric",
        "masked_profiles",
        "presence_absence",
    )
    REQUIRED_EXECUTABLES = ["chewBBACA.py", "unzip", "cp", "mv"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    COMPUTATION_OPTIONS = ["light", "no-pa", "no-dm", "no-tree", "cg-alignment"]
    OUTPUT_OPTIONS = [
        "cgMLST_MSA.fasta",
        "cgMLST_profiles.tsv",
        "distance_matrix_symmetric.tsv",
        "masked_profiles.tsv",
        "presence_absence.tsv",
    ]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_file", inputs.get("input_files")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("element_identifiers"))

    @classmethod
    def _input_name(cls, input_file: str, index: int, inputs: dict[str, Any]) -> str:
        element_identifiers = cls._element_identifiers(inputs)
        if index < len(element_identifiers):
            return f"{_safe_element_identifier(element_identifiers[index])}.tsv"
        return f"{_safe_element_identifier(Path(input_file).stem)}.tsv"

    @classmethod
    def _computation(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("computation"))

    @classmethod
    def _output_selector(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("output_selector"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        html_files = f"{out}/html_files"
        commands = [
            _shell_join(["mkdir", "-p", out]),
            f"cd {shlex.quote(out)}",
            "mkdir input",
            _shell_join(["mkdir", "-p", "schema", html_files]),
        ]
        for index, input_file in enumerate(cls._input_files(inputs)):
            commands.append(_shell_join(["ln", "-sf", input_file, f"input/{cls._input_name(input_file, index, inputs)}"]))
        commands.append(_shell_join(["unzip", str(inputs.get("input_schema", "")), "-d", "schema"]))
        cmd = ["chewBBACA.py", "AlleleCallEvaluator"]
        _add_if_value(cmd, "-a", inputs.get("annotations"))
        selected_computation = set(cls._computation(inputs))
        for option in cls.COMPUTATION_OPTIONS:
            if option in selected_computation:
                cmd.append(f"--{option}")
        cmd.extend(["-i", "input", "-g", "schema/schema_seed/", "-o", html_files])
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["cp", f"{html_files}/allelecall_report.html", f"{out}/output.html"]))
        commands.append(f"mv {html_files}/*.fasta {html_files}/*.tsv .")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.html"]
        selected = set(cls._output_selector(inputs))
        for output_name in cls.OUTPUT_OPTIONS:
            if output_name in selected:
                outputs.append(out / output_name)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("TSV", {"is_list": True, "multiple": True, "description": "AlleleCall result tables"}),
                "input_schema": ("FILE", {"description": "chewBBACA schema ZIP archive"}),
            },
            "optional": {
                "annotations": ("TSV", {"default": ""}),
                "computation": (
                    "STRING_LIST",
                    {"default": [], "options": cls.COMPUTATION_OPTIONS, "multiple": True, "display": "checkboxes"},
                ),
                "output_selector": (
                    "STRING_LIST",
                    {"default": [], "options": cls.OUTPUT_OPTIONS, "multiple": True, "display": "checkboxes"},
                ),
            },
            "hidden": {
                "element_identifiers": ("STRING_LIST", {"default": []}),
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one input_file value is required"
        if not str(inputs.get("input_schema", "")).strip():
            return "input_schema is required"
        unsupported = [value for value in cls._computation(inputs) if value not in cls.COMPUTATION_OPTIONS]
        if unsupported:
            return f"computation values must be one or more of: {', '.join(cls.COMPUTATION_OPTIONS)}"
        unsupported = [value for value in cls._output_selector(inputs) if value not in cls.OUTPUT_OPTIONS]
        if unsupported:
            return f"output_selector values must be one or more of: {', '.join(cls.OUTPUT_OPTIONS)}"
        return True

class ChewBBACACreateSchemaNode(CommandNode):
    """Create chewBBACA gene-by-gene schemas from genome assemblies."""

    NODE_ID = "chewbbaca_createschema"
    DISPLAY_NAME = "chewBBACA CreateSchema"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Create a gene-by-gene schema."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_createschema",
        "chewBBACA CreateSchema",
        "CreateSchema",
        "schema_seed",
        "cgMLST",
        "wgMLST",
        "gene-by-gene schema",
        "bacterial typing",
    ]
    RETURN_TYPES = ("ZIP", "TXT", "TSV")
    RETURN_NAMES = ("schema", "txt_file", "tsv_file")
    REQUIRED_EXECUTABLES = ["chewBBACA.py", "zip"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    PRODIGAL_MODES = ["single", "meta"]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_file", inputs.get("input_files")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("element_identifiers"))

    @classmethod
    def _element_extensions(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("element_extensions"))

    @classmethod
    def _input_name(cls, input_file: str, index: int, inputs: dict[str, Any]) -> str:
        element_identifiers = cls._element_identifiers(inputs)
        base = element_identifiers[index] if index < len(element_identifiers) else Path(input_file).stem
        element_extensions = cls._element_extensions(inputs)
        if index < len(element_extensions) and element_extensions[index]:
            ext = element_extensions[index]
        else:
            suffix = Path(input_file).suffix.lstrip(".")
            ext = suffix or "fasta"
        return f"{_safe_element_identifier(base)}.{_safe_element_identifier(ext)}"

    @classmethod
    def _prodigal_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("prodigal_mode", "single") or "single")

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", "mkdir input"]
        for index, input_file in enumerate(cls._input_files(inputs)):
            commands.append(_shell_join(["ln", "-sf", input_file, f"input/{cls._input_name(input_file, index, inputs)}"]))
        cmd = ["chewBBACA.py", "CreateSchema"]
        _add_if_value(cmd, "--ptf", inputs.get("training_file"))
        if cls._bool_flag(inputs, "cds_input"):
            cmd.append("--cds-input")
        cmd.extend(
            [
                "--bsr",
                str(inputs.get("blast_score_ratio", 0.6)),
                "--l",
                str(inputs.get("minimum_length", 201)),
                "--t",
                str(inputs.get("translation_table", 11)),
                "--st",
                str(inputs.get("size_threshold", 0.2)),
                "--pm",
                cls._prodigal_mode(inputs),
                "-i",
                "input",
                "-o",
                "output",
            ]
        )
        commands.append(_shell_join(cmd))
        commands.extend(["cd output/", "zip -r schema_seed.zip schema_seed"])
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "schema_seed.zip"]
        if cls._bool_flag(inputs, "show_cds_invalid"):
            outputs.append(out / "invalid_cds.txt")
        if cls._bool_flag(inputs, "show_cds_coord"):
            outputs.append(out / "cds_coordinates.tsv")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTA", {"is_list": True, "multiple": True, "description": "Genome assemblies"}),
            },
            "optional": {
                "training_file": ("FILE", {"default": ""}),
                "cds_input": ("BOOLEAN", {"default": False}),
                "minimum_length": ("INT", {"default": 201, "min": 0}),
                "blast_score_ratio": ("FLOAT", {"default": 0.6, "min": 0, "max": 1}),
                "translation_table": ("INT", {"default": 11, "min": 0}),
                "size_threshold": ("FLOAT", {"default": 0.2, "min": 0}),
                "prodigal_mode": ("STRING", {"default": "single", "options": cls.PRODIGAL_MODES}),
                "show_cds_invalid": ("BOOLEAN", {"default": False}),
                "show_cds_coord": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "element_identifiers": ("STRING_LIST", {"default": []}),
                "element_extensions": ("STRING_LIST", {"default": []}),
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum:
            return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_float_min(
        cls, inputs: dict[str, Any], name: str, default: float, minimum: float, maximum: float | None = None
    ) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if value < minimum:
            return f"{name} must be greater than or equal to {minimum:g}"
        if maximum is not None and value > maximum:
            return f"{name} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one input_file value is required"
        if cls._prodigal_mode(inputs) not in cls.PRODIGAL_MODES:
            return f"prodigal_mode must be one of: {', '.join(cls.PRODIGAL_MODES)}"
        result = cls._validate_float_min(inputs, "blast_score_ratio", 0.6, 0, 1)
        if result is not True:
            return result
        result = cls._validate_int_min(inputs, "minimum_length", 201, 0)
        if result is not True:
            return result
        result = cls._validate_int_min(inputs, "translation_table", 11, 0)
        if result is not True:
            return result
        result = cls._validate_float_min(inputs, "size_threshold", 0.2, 0)
        if result is not True:
            return result
        return True

class ChewBBACADownloadSchemaNode(CommandNode):
    """Download chewBBACA schemas from Chewie-NS."""

    NODE_ID = "chewbbaca_downloadschema"
    DISPLAY_NAME = "chewBBACA DownloadSchema"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Download a schema from Chewie-NS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_downloadschema",
        "chewBBACA DownloadSchema",
        "DownloadSchema",
        "Chewie-NS",
        "schema_seed",
        "cgMLST",
        "wgMLST",
        "bacterial typing",
    ]
    RETURN_TYPES = ("ZIP",)
    RETURN_NAMES = ("schema",)
    REQUIRED_EXECUTABLES = ["chewBBACA.py", "mv", "zip"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    SPECIES_OPTIONS = {
        "1": "Streptococcus pyogenes",
        "2": "Acinetobacter baumannii",
        "3": "Arcobacter butzleri",
        "4": "Campylobacter jejuni",
        "5": "Escherichia coli",
        "6": "Listeria monocytogenes",
        "7": "Yersinia enterocolitica",
        "8": "Salmonella enterica",
        "9": "Streptococcus agalactiae",
        "10": "Brucella melitensis",
        "11": "Brucella",
        "12": "Clostridium perfringens",
        "13": "Clostridium chauvoei",
        "14": "Bacillus anthracis",
        "15": "Klebsiella oxytoca",
        "16": "Clostridium neonatale",
    }

    @classmethod
    def _species_id(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("species_id", "") or "")

    @classmethod
    def _schema_id(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("schema_id", 1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["mkdir", "-p", out]),
            f"cd {shlex.quote(out)}",
            _shell_join(
                [
                    "chewBBACA.py",
                    "DownloadSchema",
                    "-sp",
                    cls._species_id(inputs),
                    "-sc",
                    str(cls._schema_id(inputs)),
                    "-o",
                    "output",
                ]
            ),
            "mv output/* schema_seed",
            "zip -r schema_seed.zip schema_seed",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "schema_seed.zip"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "species_id": (
                    "STRING",
                    {
                        "options": list(cls.SPECIES_OPTIONS),
                        "option_labels": cls.SPECIES_OPTIONS,
                        "description": "Chewie-NS species ID",
                    },
                ),
            },
            "optional": {
                "schema_id": ("INT", {"default": 1, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._species_id(inputs).strip():
            return "species_id is required"
        if cls._species_id(inputs) not in cls.SPECIES_OPTIONS:
            return f"species_id must be one of: {', '.join(cls.SPECIES_OPTIONS)}"
        try:
            schema_id = int(cls._schema_id(inputs))
        except (TypeError, ValueError):
            return "schema_id must be an integer"
        if schema_id < 1:
            return "schema_id must be greater than or equal to 1"
        return True

class ChewBBACAExtractCgMLSTNode(CommandNode):
    """Determine core-genome loci from chewBBACA allelic profiles."""

    NODE_ID = "chewbbaca_extractcgmlst"
    DISPLAY_NAME = "chewBBACA ExtractCgMLST"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Determine the set of loci that constitute the core genome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_extractcgmlst",
        "chewBBACA ExtractCgMLST",
        "ExtractCgMLST",
        "core genome",
        "cgMLST",
        "presence threshold",
        "allelic profiles",
        "bacterial typing",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_collection",)
    REQUIRED_EXECUTABLES = ["chewBBACA.py"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("threshold", "0.95 0.99 1") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["chewBBACA.py", "ExtractCgMLST", "--t", cls._threshold(inputs)]
        _add_if_value(cmd, "--r", inputs.get("genes2remove"))
        _add_if_value(cmd, "--g", inputs.get("genomes2remove"))
        cmd.extend(["-i", str(inputs.get("input_file", "")), "-o", "output"])
        return " && ".join([_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output_collection"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("TSV", {"description": "Allelic profiles table"}),
            },
            "optional": {
                "genomes2remove": ("TXT", {"default": ""}),
                "threshold": ("STRING", {"default": "0.95 0.99 1"}),
                "genes2remove": ("TSV", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        threshold = cls._threshold(inputs)
        if not threshold.strip():
            return "threshold is required"
        if re.fullmatch(r"[ .0-9]+", threshold) is None:
            return "threshold may contain only spaces, periods, and digits"
        return True

class ChewBBACAJoinProfilesNode(CommandNode):
    """Join chewBBACA allele calling profiles from multiple runs."""

    NODE_ID = "chewbbaca_joinprofiles"
    DISPLAY_NAME = "chewBBACA JoinProfiles"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Join allele calling results from different runs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_joinprofiles",
        "chewBBACA JoinProfiles",
        "JoinProfiles",
        "allele calling results",
        "common loci",
        "cgMLST",
        "wgMLST",
        "bacterial typing",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("JoinedProfile",)
    REQUIRED_EXECUTABLES = ["chewBBACA.py"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    @classmethod
    def _profiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input1", inputs.get("profiles")))

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["chewBBACA.py", "JoinProfiles", "-p", *cls._profiles(inputs), "-o", "JoinedProfile.tsv"]
        if cls._bool_flag(inputs, "common"):
            cmd.append("--common")
        return " && ".join([_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "JoinedProfile.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("TSV", {"is_list": True, "multiple": True, "description": "AlleleCall result tables"}),
            },
            "optional": {
                "common": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._profiles(inputs):
            return "at least one input1 value is required"
        return True

class ChewBBACANSStatsNode(CommandNode):
    """Retrieve Chewie-NS species and schema statistics with chewBBACA."""

    NODE_ID = "chewbbaca_nsstats"
    DISPLAY_NAME = "chewBBACA NSStats"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Retrieve basic information about the species and schemas in Chewie-NS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_nsstats",
        "chewBBACA NSStats",
        "NSStats",
        "Chewie-NS",
        "species schemas",
        "schema statistics",
        "cgMLST",
        "bacterial typing",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("NSStats",)
    REQUIRED_EXECUTABLES = ["chewBBACA.py"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    MODES = ["species", "schemas"]

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("mode", "") or "")

    @classmethod
    def _species_id(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("species_id", "") or "")

    @classmethod
    def _schema_id(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("schema_id", "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["chewBBACA.py", "NSStats", "-m", cls._mode(inputs)]
        _add_if_value(cmd, "--sp", cls._species_id(inputs))
        _add_if_value(cmd, "--sc", cls._schema_id(inputs))
        _add_shell_redirect(cmd, "NSStats.txt")
        return " && ".join([_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "NSStats.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"options": cls.MODES}),
            },
            "optional": {
                "species_id": (
                    "STRING",
                    {
                        "default": "",
                        "options": list(ChewBBACADownloadSchemaNode.SPECIES_OPTIONS),
                        "option_labels": ChewBBACADownloadSchemaNode.SPECIES_OPTIONS,
                    },
                ),
                "schema_id": ("INT", {"default": "", "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._mode(inputs).strip():
            return "mode is required"
        if cls._mode(inputs) not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        species_id = cls._species_id(inputs)
        if species_id and species_id not in ChewBBACADownloadSchemaNode.SPECIES_OPTIONS:
            return f"species_id must be one of: {', '.join(ChewBBACADownloadSchemaNode.SPECIES_OPTIONS)}"
        schema_id = cls._schema_id(inputs)
        if schema_id != "":
            try:
                schema_id_value = int(schema_id)
            except (TypeError, ValueError):
                return "schema_id must be an integer"
            if schema_id_value < 1:
                return "schema_id must be greater than or equal to 1"
        return True

class ChewBBACAPrepExternalSchemaNode(CommandNode):
    """Adapt external schemas for chewBBACA."""

    NODE_ID = "chewbbaca_prepexternalschema"
    DISPLAY_NAME = "chewBBACA PrepExternalSchema"
    REQUIRED_CONDA_PACKAGES = ["chewbbaca", "blast", "zip", "fasttree"]
    CATEGORY = "typing"
    DESCRIPTION = "Adapt an external schema to be used with chewBBACA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chewBBACA",
        "chewbbaca_prepexternalschema",
        "chewBBACA PrepExternalSchema",
        "PrepExternalSchema",
        "external schema",
        "schema adaptation",
        "schema_seed",
        "cgMLST",
        "bacterial typing",
    ]
    RETURN_TYPES = ("ZIP",)
    RETURN_NAMES = ("schema",)
    REQUIRED_EXECUTABLES = ["unzip", "chewBBACA.py", "zip"]
    DOCUMENTATION_URL = "https://chewbbaca.readthedocs.io/"
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHEWBBACA_CITATION_DOI}"]
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = "3.3.10+galaxy1"
    SHELL = True

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["mkdir", "-p", out]),
            f"cd {shlex.quote(out)}",
            _shell_join(["unzip", str(inputs.get("input_schema", "")), "-d", "schema"]),
        ]
        cmd = ["chewBBACA.py", "PrepExternalSchema"]
        _add_if_value(cmd, "--ptf", inputs.get("training_file"))
        _add_if_value(cmd, "--gl", inputs.get("genes_list"))
        cmd.extend(
            [
                "--bsr",
                str(inputs.get("blast_score_ratio", 0.6)),
                "--l",
                str(inputs.get("minimum_length", 0)),
                "--t",
                str(inputs.get("translation_table", 11)),
                "--st",
                str(inputs.get("size_threshold", 0.2)),
            ]
        )
        if cls._bool_flag(inputs, "size_filter"):
            cmd.append("--size-filter")
        cmd.extend(["-g", "schema/", "-o", "schema_seed"])
        commands.append(_shell_join(cmd))
        commands.append("zip -r PExternalschema_seed.zip schema_seed")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "PExternalschema_seed.zip"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_schema": ("FILE", {"description": "External schema ZIP archive"}),
            },
            "optional": {
                "training_file": ("FILE", {"default": ""}),
                "genes_list": ("TXT", {"default": ""}),
                "minimum_length": ("INT", {"default": 0, "min": 0}),
                "blast_score_ratio": ("FLOAT", {"default": 0.6, "min": 0, "max": 1}),
                "translation_table": ("INT", {"default": 11, "min": 0}),
                "size_threshold": ("FLOAT", {"default": 0.2, "min": 0}),
                "size_filter": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_schema", "")).strip():
            return "input_schema is required"
        result = ChewBBACACreateSchemaNode._validate_float_min(inputs, "blast_score_ratio", 0.6, 0, 1)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_int_min(inputs, "minimum_length", 0, 0)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_int_min(inputs, "translation_table", 11, 0)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_float_min(inputs, "size_threshold", 0.2, 0)
        if result is not True:
            return result
        return True

class DASToolNode(CommandNode):
    """Integrate metagenomic binning predictions with DAS Tool."""

    NODE_ID = "das_tool"
    DISPLAY_NAME = "DAS Tool"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = (
        "Integrate multiple metagenomic binning predictions into an optimized, non-redundant set of genome bins."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "das tool",
        "DAS Tool",
        "DAS_Tool",
        "dastool",
        "genome-resolved metagenomics",
        "bin dereplication",
        "bin aggregation",
        "metagenome binning",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "TSV", "FASTA_LIST", "FASTA", "FASTA")
    RETURN_NAMES = ("summary", "contigs2bin", "log", "eval", "bins", "unbinned_contigs", "proteins")
    REQUIRED_EXECUTABLES = ["DAS_Tool"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _binning_entries(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        repeat = inputs.get("binning")
        if isinstance(repeat, (list, tuple)):
            entries: list[tuple[str, str]] = []
            for item in repeat:
                if isinstance(item, dict):
                    bin_file = str(item.get("bins", ""))
                    label = str(item.get("labels", item.get("label", "")))
                else:
                    bin_file = str(item)
                    label = ""
                if bin_file:
                    entries.append((bin_file, label))
            if entries:
                return entries

        bins = _as_list(inputs.get("bins"))
        raw_labels = inputs.get("labels", inputs.get("bin_labels"))
        if isinstance(raw_labels, (list, tuple)):
            labels = [str(label) if label is not None else "" for label in raw_labels]
        elif raw_labels is None or raw_labels == "":
            labels = []
        else:
            labels = [str(raw_labels)]
        return [(bin_file, labels[index] if index < len(labels) else "") for index, bin_file in enumerate(bins)]

    @classmethod
    def _labels(cls, entries: list[tuple[str, str]]) -> list[str]:
        return [_safe_label(label) if label else _safe_name(bin_file) for bin_file, label in entries]

    @classmethod
    def _write_bins_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("write_bins")
        if isinstance(value, bool):
            return value
        return str(value if value is not None else "--write_bins") != ""

    @classmethod
    def _output_proteins_enabled(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("output_proteins", inputs.get("output_proteins_file", inputs.get("proteins_output"))))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        entries = cls._binning_entries(inputs)
        proteins = str(inputs.get("proteins", ""))
        cmd: list[str] = []
        if proteins:
            cmd.extend(["ln", "-sf", proteins, f"{out}/proteins", "&&"])
        cmd.extend(
            [
                "DAS_Tool",
                "--contigs",
                str(inputs.get("contigs", "")),
                "--outputbasename",
                f"{out}/outputs",
                "--bins",
                ",".join(bin_file for bin_file, _label in entries),
                "--labels",
                ",".join(cls._labels(entries)),
                "--search_engine",
                str(inputs.get("search_engine", "diamond")),
            ]
        )
        if proteins:
            cmd.extend(["--proteins", f"{out}/proteins"])
        cmd.extend(
            [
                "--score_threshold",
                str(inputs.get("score_threshold", 0.5)),
                "--duplicate_penalty",
                str(inputs.get("duplicate_penalty", 0.6)),
                "--megabin_penalty",
                str(inputs.get("megabin_penalty", 0.5)),
                "--max_iter_post_threshold",
                str(inputs.get("max_iter_post_threshold", 10)),
            ]
        )
        if inputs.get("write_bin_evals"):
            cmd.append("--write_bin_evals")
        if cls._write_bins_enabled(inputs):
            cmd.append("--write_bins")
            if inputs.get("write_unbinned"):
                cmd.append("--write_unbinned")
        if inputs.get("debug"):
            cmd.append("--debug")
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "outputs_DASTool_summary.tsv",
            out / "outputs_DASTool_contig2bin.tsv",
            out / "outputs_DASTool.log",
        ]
        if inputs.get("write_bin_evals"):
            outputs.append(out / "outputs_allBins.eval")
        if cls._write_bins_enabled(inputs):
            bins_dir = out / "outputs_DASTool_bins"
            bins_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(bins_dir)
            if inputs.get("write_unbinned"):
                outputs.append(bins_dir / "unbinned.fa")
        if cls._output_proteins_enabled(inputs):
            outputs.append(out / "outputs_proteins.faa")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("FASTA", {"description": "Assembled contig sequences"}),
                "bins": (
                    "TSV",
                    {
                        "list": True,
                        "min_items": 1,
                        "description": "One or more contig-to-bin tables with contig IDs and bin IDs",
                    },
                ),
            },
            "optional": {
                "labels": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Binning prediction labels; blank labels fall back to sanitized table filenames",
                    },
                ),
                "search_engine": (
                    "STRING",
                    {
                        "default": "diamond",
                        "options": ["diamond", "blastp"],
                        "description": "Engine used for single-copy gene identification",
                    },
                ),
                "proteins": (
                    "FASTA",
                    {"default": "", "description": "Optional predicted proteins in Prodigal FASTA format"},
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Score threshold until selection algorithm keeps selecting bins",
                    },
                ),
                "duplicate_penalty": (
                    "FLOAT",
                    {
                        "default": 0.6,
                        "min": 0,
                        "max": 3,
                        "description": "Penalty for duplicate single-copy genes per bin",
                    },
                ),
                "megabin_penalty": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 3, "description": "Penalty for megabins"},
                ),
                "max_iter_post_threshold": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Maximum iterations after reaching the score threshold",
                    },
                ),
                "output_proteins": ("BOOLEAN", {"default": False, "description": "Output predicted proteins"}),
                "write_bin_evals": (
                    "BOOLEAN",
                    {"default": False, "description": "Write evaluation of input bin sets"},
                ),
                "write_bins": (
                    "STRING",
                    {
                        "default": "--write_bins",
                        "options": ["--write_bins", ""],
                        "description": "Export selected bins as FASTA files",
                    },
                ),
                "write_unbinned": (
                    "BOOLEAN",
                    {"default": False, "description": "Export unbinned contigs when writing bins"},
                ),
                "debug": ("BOOLEAN", {"default": False, "description": "Write debug information to the log file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FastaToContig2BinNode(CommandNode):
    """Convert genome-bin FASTA files into a DAS Tool contig-to-bin table."""

    NODE_ID = "fasta_to_contig2bin"
    DISPLAY_NAME = "FASTA to Contig2Bin"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert a list of genome-bin FASTA files into a tabular contig-to-bin assignment table for DAS Tool."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Fasta_to_Contig2Bin",
        "Fasta_to_Contig2Bin.sh",
        "DAS Tool helper",
        "contig2bin",
        "contigs2bin",
        "genome bins",
        "bin FASTA",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("contigs2bin",)
    REQUIRED_EXECUTABLES = ["Fasta_to_Contig2Bin.sh"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool#preparation-of-input-files"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("inputs", inputs.get("input")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get("element_identifiers", inputs.get("identifiers", inputs.get("labels")))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else "" for identifier in raw]
        elif raw is None or raw == "":
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_file)
            for index, input_file in enumerate(input_files)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/inputs"
        input_files = cls._input_files(inputs)
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ["mkdir", "-p", input_dir]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{input_dir}/{identifier}.fasta"])
        cmd.extend(
            [
                "&&",
                "Fasta_to_Contig2Bin.sh",
                "--extension",
                "fasta",
                "--input_folder",
                input_dir,
                ">",
                f"{out}/contigs2bin.tsv",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "contigs2bin.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "FASTA_LIST",
                    {"description": "Genome-bin FASTA files to convert into contig-to-bin assignments"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Optional bin labels matching the FASTA collection element identifiers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BandageInfoNode(CommandNode):
    """Summarize de novo assembly graph statistics with Bandage info."""

    NODE_ID = "bandage_info"
    DISPLAY_NAME = "Bandage Info"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "assembly"
    DESCRIPTION = "Determine node, edge, length, connectivity, and N50 statistics for de novo assembly graphs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bandage",
        "bandage info",
        "assembly graph",
        "GFA statistics",
        "FASTG statistics",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#info"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "info", f"{out}/input.gfa"])
        if inputs.get("tsv"):
            cmd.append("--tsv")
        cmd.extend(["|", "sed", r"s/:\s\+/:\t/g", ">", f"{out}/out.tab"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.tab"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "tsv": (
                    "BOOLEAN",
                    {"default": False, "description": "Output information as a single tab-delimited line"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BandageImageNode(CommandNode):
    """Render de novo assembly graph images with Bandage image."""

    NODE_ID = "bandage_image"
    DISPLAY_NAME = "Bandage Image"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "visualization"
    DESCRIPTION = "Visualize de novo assembly graphs as JPG, PNG, or SVG images using Bandage."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bandage",
        "bandage image",
        "assembly graph image",
        "GFA visualization",
        "FASTG visualization",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#image"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("output_format", "jpg") or "jpg").lower()
        return output_format if output_format in {"jpg", "png", "svg"} else "jpg"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = cls._output_format(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "image", f"{out}/input.gfa", f"{out}/out.{output_format}"])
        _add_if_value(cmd, "--height", inputs.get("height"))
        _add_if_value(cmd, "--width", inputs.get("width"))
        _add_if_value(cmd, "--fontsize", inputs.get("fontsize"))
        _add_if_value(cmd, "--nodewidth", inputs.get("nodewidth"))
        if inputs.get("names"):
            cmd.append("--names")
        if inputs.get("lengths"):
            cmd.append("--lengths")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"out.{cls._output_format(inputs)}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "height": ("INT", {"default": 1000, "min": 1, "description": "Image height in pixels"}),
                "width": ("INT", {"default": "", "min": 1, "description": "Image width in pixels"}),
                "names": ("BOOLEAN", {"default": False, "description": "Show node name labels"}),
                "lengths": ("BOOLEAN", {"default": False, "description": "Show node length labels"}),
                "fontsize": ("INT", {"default": "", "min": 5, "description": "Node label font size"}),
                "nodewidth": ("FLOAT", {"default": "", "min": 5, "description": "Node width for graph image"}),
                "output_format": (
                    "STRING",
                    {"default": "jpg", "options": ["jpg", "png", "svg"], "description": "Output image format"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
