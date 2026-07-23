"""Shared classification, filtering, and taxonomy conversion contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from .contracts import ToolsIUCCommandContract

class _BrackenEstAbundanceContract(ToolsIUCCommandContract):
    """Re-estimate taxonomic abundance from a Kraken report with Bracken."""

    LEGACY_NODE_ID = "est_abundance"
    DISPLAY_NAME = "Bracken"
    REQUIRED_CONDA_PACKAGES = ["bracken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Re-estimate taxonomic abundance from a Kraken report with Bracken."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bracken",
        "est_abundance",
        "est_abundance.py",
        "Kraken report",
        "taxonomy abundance",
        "Kraken-style Bracken report",
        "Bayesian abundance",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TXT")
    RETURN_NAMES = ("report", "kraken_report", "logfile")
    REQUIRED_EXECUTABLES = ["est_abundance.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/Bracken"
    CITATION_DOIS = [BRACKEN_DOI]
    CITATION_URLS = [f"{DOI_URL}{BRACKEN_DOI}"]
    CITATION_TEXT = BRACKEN_CITATION_TEXT
    VERSION = "3.1+galaxy0"
    SHELL = True

    LEVELS = ["S2", "S1", "S", "G", "F", "O", "C", "P", "D"]

    @classmethod
    def _level(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("level", "S") or "S")

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("threshold", 10)
        if value is None or value == "":
            value = 10
        return int(value)

    @classmethod
    def _report_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/report.tsv"

    @classmethod
    def _kraken_report_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/kraken_report.tsv"

    @classmethod
    def _logfile_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/logfile.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "set",
            "-o",
            "pipefail",
            "&&",
            "est_abundance.py",
            "-i",
            str(inputs.get("input", "")),
            "-k",
            str(inputs.get("kmer_distr", "")),
            "-l",
            cls._level(inputs),
            "-t",
            str(cls._threshold(inputs)),
            "-o",
            cls._report_path(inputs),
            "--out-report",
            "bracken.report",
        ]
        if inputs.get("logfile_output", False):
            cmd.extend(["|", "tee", cls._logfile_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "report.tsv"]
        if inputs.get("out_report", False):
            outputs.append(out / "kraken_report.tsv")
        if inputs.get("logfile_output", False):
            outputs.append(out / "logfile.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("kmer_distr", "")).strip():
            return "kmer_distr is required"
        level = cls._level(inputs)
        if level not in cls.LEVELS:
            return f"level must be one of: {', '.join(cls.LEVELS)}"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return "threshold must be an integer"
        if threshold < 0:
            return "threshold must be >= 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Kraken report file"}),
                "kmer_distr": (
                    "FILE",
                    {"description": "Bracken k-mer distribution file matching the Kraken database and read length"},
                ),
            },
            "optional": {
                "level": (
                    "STRING",
                    {
                        "default": "S",
                        "options": cls.LEVELS,
                        "description": "Taxonomic level to estimate abundance at",
                    },
                ),
                "threshold": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "Minimum Kraken-assigned read count for taxa considered in abundance estimation",
                    },
                ),
                "out_report": (
                    "BOOLEAN",
                    {"default": False, "description": "Plan the optional Kraken-style Bracken report output"},
                ),
                "logfile_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Capture Bracken stdout and stderr into a log file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MagicBlastContract(ToolsIUCCommandContract):
    """Map large RNA or DNA reads against a genome or transcriptome with Magic-BLAST."""

    LEGACY_NODE_ID = "magicblast"
    DISPLAY_NAME = "Magic-BLAST"
    REQUIRED_CONDA_PACKAGES = ["magicblast", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Map large RNA or DNA sequencing reads against a whole genome or transcriptome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Magic-BLAST",
        "magicblast",
        "RNA-seq aligner",
        "long and short reads",
        "whole genome mapping",
        "transcriptome mapping",
        "spliced alignments",
        "BLAST mapper",
    ]
    RETURN_TYPES = ("BAM", "FILE")
    RETURN_NAMES = ("output", "output_unaligned")
    REQUIRED_EXECUTABLES = ["magicblast", "samtools", "gunzip"]
    DOCUMENTATION_URL = "https://ncbi.github.io/magicblast/"
    CITATION_DOIS = [MAGICBLAST_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{MAGICBLAST_CITATION_DOI}"]
    CITATION_TEXT = MAGICBLAST_CITATION_TEXT
    VERSION = "1.7.0+galaxy2"
    SHELL = True

    DB_OPTIONS = ["histdb", "db", "file"]
    OUTFMTS = ["bam", "tabular"]
    SORT_OPTIONS = ["coordinate", "name", "unsorted"]
    UNALIGNED_FORMATS = ["bam", "tabular", "fasta"]
    REFTYPES = ["genome", "transcriptome"]

    @classmethod
    def _outfmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("outfmt", "bam") or "bam")

    @classmethod
    def _output_sort(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_sort", "coordinate") or "coordinate")

    @classmethod
    def _unaligned_output_sort(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("unaligned_output_sort", inputs.get("output_sort", "coordinate")) or "coordinate")

    @classmethod
    def _unaligned_fmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("unaligned_fmt", "bam") or "bam")

    @classmethod
    def _is_gzip(cls, path: Any, explicit_type: Any = "") -> bool:
        value = str(explicit_type or path or "").lower()
        return value.endswith(".gz") or value in {"fasta.gz", "fastqsanger.gz"}

    @classmethod
    def _is_fastq(cls, path: Any, explicit_type: Any = "") -> bool:
        value = str(explicit_type or path or "").lower()
        return "fastq" in value or "fastqsanger" in value or value.endswith((".fq", ".fq.gz"))

    @classmethod
    def _file_arg(cls, path: str, *, compressed: bool) -> str:
        quoted = shlex.quote(path)
        return f"<(gunzip -c {quoted})" if compressed else quoted

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None or value == "":
            value = default
        if isinstance(value, str):
            return "false" if value.lower() in {"false", "0", "no"} else "true"
        return "true" if bool(value) else "false"

    @classmethod
    def _main_output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = "bam" if cls._outfmt(inputs) == "bam" else "tabular"
        return f"{_out(inputs)}/output.{suffix}"

    @classmethod
    def _unaligned_output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = {"bam": "bam", "tabular": "tabular", "fasta": "fasta"}[cls._unaligned_fmt(inputs)]
        return f"{_out(inputs)}/output_unaligned.{suffix}"

    @classmethod
    def _add_restrict_search(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ("gilist", "negative_gilist", "seqidlist", "negative_seqidlist", "taxidlist", "negative_taxidlist"):
            _add_if_value(cmd, f"-{key}", inputs.get(key))
        _add_if_value(cmd, "--taxids", inputs.get("taxids"))
        _add_if_value(cmd, "--negative_taxids", inputs.get("negative_taxids"))

    @classmethod
    def _samtools_bam_conversion(cls, input_sam: str, output_bam: str, sort_mode: str) -> str:
        if sort_mode == "coordinate":
            return f"samtools sort -@${{GALAXY_SLOTS:-4}} -O bam {shlex.quote(input_sam)} > {shlex.quote(output_bam)}"
        if sort_mode == "name":
            return f"samtools sort -n -@${{GALAXY_SLOTS:-4}} -O bam {shlex.quote(input_sam)} > {shlex.quote(output_bam)}"
        return f"samtools view -@${{GALAXY_SLOTS:-4}} -bS {shlex.quote(input_sam)} > {shlex.quote(output_bam)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        query = str(inputs.get("query", ""))
        query_type = inputs.get("query_type", inputs.get("query_ext", ""))
        threads = int(inputs.get("threads", 8) or 8)
        cmd = [
            "magicblast",
            "-num_threads",
            f"${{GALAXY_SLOTS:-{threads}}}",
            "-query",
            cls._file_arg(query, compressed=cls._is_gzip(query, query_type)),
        ]
        query_mate = str(inputs.get("query_mate", "") or "")
        if query_mate:
            mate_type = inputs.get("query_mate_type", query_type)
            cmd.extend(["-paired", "-query_mate", cls._file_arg(query_mate, compressed=cls._is_gzip(query_mate, mate_type))])
        if cls._is_fastq(query, query_type):
            cmd.extend(["-infmt", "fastq"])

        db_selector = str(inputs.get("db_opts_selector", "histdb") or "histdb")
        if db_selector == "histdb":
            histdb = str(inputs.get("histdb", inputs.get("db", "")))
            cmd.extend(["-db", f"{histdb.rstrip('/')}/blastdb" if histdb and not histdb.endswith("blastdb") else histdb])
        elif db_selector == "db":
            cmd.extend(["-db", str(inputs.get("database", ""))])
        else:
            subject = str(inputs.get("subject", ""))
            subject_type = inputs.get("subject_type", inputs.get("subject_ext", ""))
            cmd.extend(["-subject", cls._file_arg(subject, compressed=cls._is_gzip(subject, subject_type))])

        for key, default in (
            ("word_size", 18),
            ("gapopen", 0),
            ("gapextend", 0),
            ("penalty", -4),
            ("max_intron_length", 500000),
        ):
            cmd.extend([f"-{key}", str(inputs.get(key, default))])
        if inputs.get("lcase_masking"):
            cmd.append("-lcase_masking")
        cmd.extend(["-validate_seqs", cls._bool_text(inputs.get("validate_seqs"), True)])
        cmd.extend(["-limit_lookup", cls._bool_text(inputs.get("limit_lookup"), True)])
        cmd.extend(["-max_db_word_count", str(inputs.get("max_db_word_count", 30))])
        cmd.extend(["-lookup_stride", str(inputs.get("lookup_stride", 0))])
        cls._add_restrict_search(cmd, inputs)
        cmd.extend(["-score", str(inputs.get("score", 0))])
        max_edit_dist = int(inputs.get("max_edit_dist", 0) or 0)
        if max_edit_dist > 0:
            cmd.extend(["-max_edit_dist", str(max_edit_dist)])
        cmd.extend(["-splice", cls._bool_text(inputs.get("splice"), True)])
        cmd.extend(["-reftype", str(inputs.get("reftype", "genome") or "genome")])

        report_unaligned = str(inputs.get("report_unaligned", "yes") or "yes")
        report_separately = str(inputs.get("report_unaligned_separately", "no") or "no")
        if report_unaligned == "yes" and report_separately == "yes":
            cmd.extend(["-out_unaligned", "out_unaligned"])
            unaligned_arg = "sam" if cls._unaligned_fmt(inputs) == "bam" else cls._unaligned_fmt(inputs)
            cmd.extend(["-unaligned_fmt", unaligned_arg])
        elif report_unaligned == "no":
            cmd.append("-no_unaligned")
        if inputs.get("no_discordant"):
            cmd.append("-no_discordant")

        post_commands: list[str] = []
        if cls._outfmt(inputs) == "bam":
            if inputs.get("md_tag"):
                cmd.append("-md_tag")
            if query_mate and inputs.get("no_query_id_trim"):
                cmd.append("-no_query_id_trim")
            cmd.extend(["-out", "output.sam"])
            post_commands.append(cls._samtools_bam_conversion("output.sam", cls._main_output_path(inputs), cls._output_sort(inputs)))
        else:
            cmd.extend(["-out", cls._main_output_path(inputs), "-outfmt", cls._outfmt(inputs)])

        if report_unaligned == "yes" and report_separately == "yes":
            if cls._unaligned_fmt(inputs) == "bam":
                post_commands.append(cls._samtools_bam_conversion("out_unaligned", cls._unaligned_output_path(inputs), cls._unaligned_output_sort(inputs)))
            else:
                post_commands.append(f"mv out_unaligned {shlex.quote(cls._unaligned_output_path(inputs))}")
        rendered = _shell_join(cmd)
        slots_var = f"${{GALAXY_SLOTS:-{threads}}}"
        rendered = rendered.replace(shlex.quote(slots_var), slots_var)
        if post_commands:
            rendered = " && ".join([rendered, *post_commands])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = "bam" if cls._outfmt(inputs) == "bam" else "tabular"
        outputs = [out / f"output.{suffix}"]
        if str(inputs.get("report_unaligned", "yes") or "yes") == "yes" and str(
            inputs.get("report_unaligned_separately", "no") or "no"
        ) == "yes":
            unaligned_suffix = {"bam": "bam", "tabular": "tabular", "fasta": "fasta"}[cls._unaligned_fmt(inputs)]
            outputs.append(out / f"output_unaligned.{unaligned_suffix}")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("query", "")).strip():
            return "query is required"
        db_selector = str(inputs.get("db_opts_selector", "histdb") or "histdb")
        if db_selector not in cls.DB_OPTIONS:
            return f"db_opts_selector must be one of: {', '.join(cls.DB_OPTIONS)}"
        if db_selector == "histdb" and not str(inputs.get("histdb", inputs.get("db", ""))).strip():
            return "histdb is required when db_opts_selector is histdb"
        if db_selector == "db" and not str(inputs.get("database", "")).strip():
            return "database is required when db_opts_selector is db"
        if db_selector == "file" and not str(inputs.get("subject", "")).strip():
            return "subject is required when db_opts_selector is file"
        outfmt = cls._outfmt(inputs)
        if outfmt not in cls.OUTFMTS:
            return f"outfmt must be one of: {', '.join(cls.OUTFMTS)}"
        output_sort = cls._output_sort(inputs)
        if output_sort not in cls.SORT_OPTIONS:
            return f"output_sort must be one of: {', '.join(cls.SORT_OPTIONS)}"
        unaligned_sort = cls._unaligned_output_sort(inputs)
        if unaligned_sort not in cls.SORT_OPTIONS:
            return f"unaligned_output_sort must be one of: {', '.join(cls.SORT_OPTIONS)}"
        if cls._unaligned_fmt(inputs) not in cls.UNALIGNED_FORMATS:
            return f"unaligned_fmt must be one of: {', '.join(cls.UNALIGNED_FORMATS)}"
        if str(inputs.get("reftype", "genome") or "genome") not in cls.REFTYPES:
            return f"reftype must be one of: {', '.join(cls.REFTYPES)}"
        if int(inputs.get("word_size", 18) or 18) < 12:
            return "word_size must be >= 12"
        for key in ("gapopen", "gapextend", "max_intron_length", "max_db_word_count", "lookup_stride", "score", "max_edit_dist"):
            if int(inputs.get(key, 0) or 0) < 0:
                return f"{key} must be >= 0"
        if int(inputs.get("penalty", -4) or -4) > 0:
            return "penalty must be <= 0"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": (
                    "FASTQ",
                    {"description": "FASTA or fastqsanger query reads, optionally gzip-compressed"},
                ),
            },
            "optional": {
                "query_mate": ("FASTQ", {"default": "", "description": "Optional mate reads for paired-end mapping"}),
                "query_type": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz"],
                        "advanced": True,
                    },
                ),
                "query_mate_type": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz"],
                        "advanced": True,
                    },
                ),
                "db_opts_selector": ("STRING", {"default": "histdb", "options": cls.DB_OPTIONS}),
                "histdb": ("DIRECTORY", {"default": "", "description": "History BLAST database directory"}),
                "database": ("FILE", {"default": "", "description": "Locally installed nucleotide BLAST database path"}),
                "subject": ("FASTA", {"default": "", "description": "Subject FASTA file to search instead of a database"}),
                "subject_type": ("STRING", {"default": "", "options": ["", "fasta", "fasta.gz"], "advanced": True}),
                "word_size": ("INT", {"default": 18, "min": 12}),
                "gapopen": ("INT", {"default": 0, "min": 0}),
                "gapextend": ("INT", {"default": 0, "min": 0}),
                "penalty": ("INT", {"default": -4, "max": 0}),
                "max_intron_length": ("INT", {"default": 500000, "min": 0}),
                "lcase_masking": ("BOOLEAN", {"default": False}),
                "validate_seqs": ("BOOLEAN", {"default": True}),
                "limit_lookup": ("BOOLEAN", {"default": True}),
                "max_db_word_count": ("INT", {"default": 30, "min": 0}),
                "lookup_stride": ("INT", {"default": 0, "min": 0}),
                "gilist": ("TSV", {"default": ""}),
                "negative_gilist": ("TSV", {"default": ""}),
                "seqidlist": ("TSV", {"default": ""}),
                "negative_seqidlist": ("TSV", {"default": ""}),
                "taxids": ("STRING", {"default": ""}),
                "taxidlist": ("TSV", {"default": ""}),
                "negative_taxids": ("STRING", {"default": ""}),
                "negative_taxidlist": ("TSV", {"default": ""}),
                "score": ("INT", {"default": 0, "min": 0}),
                "max_edit_dist": ("INT", {"default": 0, "min": 0}),
                "splice": ("BOOLEAN", {"default": True}),
                "reftype": ("STRING", {"default": "genome", "options": cls.REFTYPES}),
                "report_unaligned": ("STRING", {"default": "yes", "options": ["yes", "no"]}),
                "report_unaligned_separately": ("STRING", {"default": "no", "options": ["no", "yes"]}),
                "unaligned_fmt": ("STRING", {"default": "bam", "options": cls.UNALIGNED_FORMATS}),
                "unaligned_output_sort": ("STRING", {"default": "coordinate", "options": cls.SORT_OPTIONS}),
                "outfmt": ("STRING", {"default": "bam", "options": cls.OUTFMTS}),
                "output_sort": ("STRING", {"default": "coordinate", "options": cls.SORT_OPTIONS}),
                "md_tag": ("BOOLEAN", {"default": False}),
                "no_query_id_trim": ("BOOLEAN", {"default": False}),
                "no_discordant": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BMTaggerContract(ToolsIUCCommandContract):
    """Remove contaminant reads with BMTagger."""

    LEGACY_NODE_ID = "bmtagger"
    DISPLAY_NAME = "bmtagger"
    REQUIRED_CONDA_PACKAGES = ["bmtagger"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Filter contaminant sequences from input FASTA or FASTQ reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BMTagger",
        "bmtagger",
        "contaminant reads",
        "host read removal",
        "human read filtering",
        "metagenomics contamination",
        "Best Match Tagger",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ")
    RETURN_NAMES = ("out_single", "out_pair")
    REQUIRED_EXECUTABLES = ["bmtagger.sh", "extract_fullseq", "bmtool", "srprism", "makeblastdb", "gunzip"]
    DOCUMENTATION_URL = BMTAGGER_CITATION_URL
    CITATION_URLS = [BMTAGGER_CITATION_URL]
    CITATION_TEXT = BMTAGGER_CITATION_TEXT
    VERSION = "3.101+galaxy0"
    SHELL = True

    SEQUENCE_TYPES = ["single", "paired"]
    HOST_SOURCES = ["cached", "history"]
    READ_FORMATS = ["", "fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz", "fastqillumina", "fastqillumina.gz"]
    HOST_FORMATS = ["", "fasta", "fasta.gz"]

    @classmethod
    def _sequence_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sequence_type", inputs.get("type", "single")) or "single")

    @classmethod
    def _host_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("host_source", inputs.get("source", "cached")) or "cached")

    @classmethod
    def _reads_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reads_ext", "") or "")

    @classmethod
    def _host_sequence_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("host_sequence_ext", "") or "")

    @classmethod
    def _is_gzip(cls, path: Any, explicit_type: Any = "") -> bool:
        value = str(explicit_type or path or "").lower()
        return value.endswith(".gz") or value in {"fasta.gz", "fastqsanger.gz", "fastqillumina.gz"}

    @classmethod
    def _is_fasta(cls, path: Any, explicit_type: Any = "") -> bool:
        value = str(explicit_type or path or "").lower()
        return value.startswith("fasta") or value.endswith((".fa", ".fasta", ".fa.gz", ".fasta.gz"))

    @classmethod
    def _is_test(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("test", "")
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return bool(value)

    @classmethod
    def _stage_file_command(cls, source: str, target: str, *, compressed: bool) -> str:
        quoted_source = shlex.quote(source)
        quoted_target = shlex.quote(target)
        if compressed:
            return f"gunzip -c {quoted_source} > {quoted_target}"
        return f"ln -s {quoted_source} {quoted_target}"

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".fastq.gz" if cls._is_gzip(inputs.get("reads"), cls._reads_ext(inputs)) else ".fastq"

    @classmethod
    def _single_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_single{cls._output_suffix(inputs)}"

    @classmethod
    def _forward_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/forward{cls._output_suffix(inputs)}"

    @classmethod
    def _reverse_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/reverse{cls._output_suffix(inputs)}"

    @classmethod
    def _reference_prefix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference", inputs.get("host_reference", "")) or "")

    @classmethod
    def _host_sequence(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("host_sequence", inputs.get("sequence", "")) or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = cls._sequence_type(inputs)
        reads = str(inputs.get("reads", "") or "")
        reads_reverse = str(inputs.get("reads_reverse", inputs.get("reverse", "")) or "")
        reads_ext = cls._reads_ext(inputs)
        gzipped_reads = cls._is_gzip(reads, reads_ext)
        fasta_reads = cls._is_fasta(reads, reads_ext)

        commands = []
        commands.append(cls._stage_file_command(reads, "forward", compressed=gzipped_reads))
        if sequence_type == "paired":
            commands.append(cls._stage_file_command(reads_reverse, "reverse", compressed=gzipped_reads))

        host_source = cls._host_source(inputs)
        if host_source == "cached":
            reference = cls._reference_prefix(inputs)
            if cls._is_test(inputs):
                commands.append(f"srprism mkindex -i {shlex.quote(reference + '.fa')} -o reference.srprism")
            bitmask = f"{reference}.bitmask"
            srprism = "reference.srprism" if cls._is_test(inputs) else f"{reference}.srprism"
            database = reference
        else:
            host_sequence = cls._host_sequence(inputs)
            commands.append(
                cls._stage_file_command(
                    host_sequence,
                    "reference.fa",
                    compressed=cls._is_gzip(host_sequence, cls._host_sequence_ext(inputs)),
                )
            )
            word_size = 10 if cls._is_test(inputs) else 18
            commands.extend(
                [
                    f"bmtool -d reference.fa -o reference.bitmask -w {word_size}",
                    "srprism mkindex -i reference.fa -o reference.srprism",
                    "makeblastdb -in reference.fa -dbtype nucl",
                ]
            )
            bitmask = "reference.bitmask"
            srprism = "reference.srprism"
            database = "reference"

        tagger_cmd = [
            "bmtagger.sh",
            "-q",
            "0" if fasta_reads else "1",
            "-1",
            "forward",
        ]
        if sequence_type == "paired":
            tagger_cmd.extend(["-2", "reverse"])
        tagger_cmd.extend(
            [
                "-b",
                bitmask,
                "-x",
                srprism,
                "-d",
                database,
                "-o",
                "host_ids",
            ]
        )
        commands.append(_shell_join(tagger_cmd))

        gzip_pipe = " | gzip -c" if gzipped_reads else ""
        if sequence_type == "single":
            commands.append(
                f"extract_fullseq host_ids -keep -fastq -single forward{gzip_pipe} > "
                f"{shlex.quote(cls._single_output_path(inputs))}"
            )
        else:
            commands.extend(
                [
                    f"extract_fullseq host_ids -keep -fastq -mate1 forward{gzip_pipe} > "
                    f"{shlex.quote(cls._forward_output_path(inputs))}",
                    f"extract_fullseq host_ids -keep -fastq -mate2 reverse{gzip_pipe} > "
                    f"{shlex.quote(cls._reverse_output_path(inputs))}",
                ]
            )

        return "set -eo pipefail; " + " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = cls._output_suffix(inputs)
        if cls._sequence_type(inputs) == "paired":
            return [out / f"forward{suffix}", out / f"reverse{suffix}"]
        return [out / f"out_single{suffix}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads", "")).strip():
            return "reads is required"
        sequence_type = cls._sequence_type(inputs)
        if sequence_type not in cls.SEQUENCE_TYPES:
            return f"sequence_type must be one of: {', '.join(cls.SEQUENCE_TYPES)}"
        if sequence_type == "paired" and not str(inputs.get("reads_reverse", inputs.get("reverse", ""))).strip():
            return "reads_reverse is required for paired sequence_type"
        reads_ext = cls._reads_ext(inputs)
        if reads_ext and reads_ext not in cls.READ_FORMATS:
            return f"reads_ext must be one of: {', '.join(cls.READ_FORMATS)}"
        host_source = cls._host_source(inputs)
        if host_source not in cls.HOST_SOURCES:
            return f"host_source must be one of: {', '.join(cls.HOST_SOURCES)}"
        if host_source == "cached" and not cls._reference_prefix(inputs).strip():
            return "reference is required when host_source is cached"
        if host_source == "history" and not cls._host_sequence(inputs).strip():
            return "host_sequence is required when host_source is history"
        host_ext = cls._host_sequence_ext(inputs)
        if host_ext and host_ext not in cls.HOST_FORMATS:
            return f"host_sequence_ext must be one of: {', '.join(cls.HOST_FORMATS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Single-end reads or forward reads for paired-end filtering"}),
            },
            "optional": {
                "sequence_type": ("STRING", {"default": "single", "options": cls.SEQUENCE_TYPES}),
                "reads_reverse": ("FASTQ", {"default": "", "description": "Reverse reads for paired-end filtering"}),
                "reads_ext": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.READ_FORMATS,
                        "description": "Galaxy datatype extension for input reads",
                        "advanced": True,
                    },
                ),
                "host_source": ("STRING", {"default": "cached", "options": cls.HOST_SOURCES}),
                "reference": ("FILE", {"default": "", "description": "Prefix for a precomputed BMTagger reference"}),
                "host_sequence": ("FASTA", {"default": "", "description": "Host FASTA sequence for on-the-fly indexing"}),
                "host_sequence_ext": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.HOST_FORMATS,
                        "description": "Galaxy datatype extension for the host sequence",
                        "advanced": True,
                    },
                ),
                "test": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "advanced": True,
                        "description": "Use the Galaxy wrapper's small-index test mode",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class _RecentrifugeContract(ToolsIUCCommandContract):
    """Run Recentrifuge comparative metagenomics analysis."""

    LEGACY_NODE_ID = "recentrifuge"
    DISPLAY_NAME = "Recentrifuge"
    REQUIRED_CONDA_PACKAGES = ["recentrifuge"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Robust comparative analysis and contamination removal for metagenomics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
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
    RETURN_TYPES = ("HTML_REPORT", "TEXT", "TSV", "TSV", "FILE")
    RETURN_NAMES = ("html_report", "logfile", "data_table", "stat_table", "xlsx_report")
    REQUIRED_EXECUTABLES = ["rcf"]
    DOCUMENTATION_URL = "https://github.com/khyox/recentrifuge"
    CITATION_DOIS = ["10.1371/journal.pcbi.1006967"]
    CITATION_URLS = [f"{DOI_URL}10.1371/journal.pcbi.1006967"]
    CITATION_TEXT = "Recentrifuge: Robust comparative analysis and contamination removal for metagenomics."
    VERSION = "1.16.1"
    SHELL = True

    _FILETYPE_FLAGS = {
        "centrifuge": ("-f", ".out", "SHEL"),
        "clark": ("-r", ".csv", "SHEL"),
        "generic": ("-g", "", "GENERIC"),
        "lmat": ("-l", "", "LMAT"),
        "kraken": ("-k", ".krk", "KRAKEN"),
    }

    @classmethod
    def _input_identifier(cls, value: str) -> str:
        return sub(r"[^\s\w\-]", "_", value)

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        filetype = str(inputs.get("filetype", "centrifuge"))
        _flag, extension, _scoring = cls._FILETYPE_FLAGS.get(filetype, cls._FILETYPE_FLAGS["centrifuge"])
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, input_file in enumerate(input_files):
            label = labels[index] if index < len(labels) and labels[index] else Path(input_file).name
            names.append(f"{cls._input_identifier(label)}{extension}")
        return names

    @classmethod
    def _log_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/logfile.txt"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_files = _as_list(inputs.get("input_file"))
        if not input_files:
            return "At least one taxonomy input file is required"
        if not str(inputs.get("database_name", "")).strip():
            return "NCBI taxonomy database is required"
        filetype = str(inputs.get("filetype", ""))
        if filetype not in cls._FILETYPE_FLAGS:
            return f"Unsupported Recentrifuge filetype: {filetype}"
        if filetype == "generic" and not str(inputs.get("format", "")).strip():
            return "Generic input mode requires a format string"
        if str(inputs.get("extra", "CSV")) not in {"CSV", "DYNOMICS", "FULL", "TSV"}:
            return "Unsupported Recentrifuge extra output format"
        if str(inputs.get("summary", "ADD")) not in {"ADD", "ONLY", "AVOID"}:
            return "Unsupported Recentrifuge summary mode"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        filetype = str(inputs.get("filetype", "centrifuge"))
        input_flag, _extension, default_scoring = cls._FILETYPE_FLAGS.get(filetype, cls._FILETYPE_FLAGS["centrifuge"])
        input_files = _as_list(inputs.get("input_file"))
        input_names = cls._input_names(inputs, input_files)
        commands = ["mkdir -p input_dir"]
        commands.extend(
            _shell_join(["ln", "-s", input_file, f"input_dir/{input_name}"])
            for input_file, input_name in zip(input_files, input_names, strict=False)
        )

        cmd = [
            "rcf",
            "-n",
            str(inputs.get("database_name", "")),
            input_flag,
            "input_dir",
        ]
        if filetype == "generic":
            cmd.extend(["--format", str(inputs.get("format", ""))])
        cmd.extend(["-e", str(inputs.get("extra", "CSV")), "-o", "output"])
        if inputs.get("nohtml", False):
            cmd.append("--nohtml")

        _add_if_value(cmd, "--controls", inputs.get("controls"))
        cmd.extend(["--scoring", str(inputs.get("scoring") or default_scoring)])
        _add_if_value(cmd, "--minscore", inputs.get("minscore_value"))
        _add_if_value(cmd, "--mintaxa", inputs.get("mintaxa"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude_taxa_name"))
        _add_if_value(cmd, "--include", inputs.get("include_taxa_name"))
        if inputs.get("avoidcross", False):
            cmd.append("--avoidcross")
        _add_if_value(cmd, "--ctrlminscore", inputs.get("ctrlminscore"))
        _add_if_value(cmd, "--ctrlmintaxa", inputs.get("ctrlmintaxa"))
        cmd.extend(["--summary", str(inputs.get("summary", "ADD"))])
        if inputs.get("takeoutroot", False):
            cmd.append("--takeoutroot")
        if inputs.get("nokollapse", False):
            cmd.append("--nokollapse")
        if inputs.get("strain", False):
            cmd.append("--strain")
        if inputs.get("sequential", False):
            cmd.append("--sequential")

        if inputs.get("no_logfile", False):
            _add_shell_redirect(cmd, cls._log_path(inputs))
        else:
            cmd.extend(["|", "tee", cls._log_path(inputs)])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if not inputs.get("nohtml", False):
            outputs.append(out / "output.rcf.html")
        if not inputs.get("no_logfile", False):
            outputs.append(out / "logfile.txt")

        extra = str(inputs.get("extra", "CSV"))
        if extra == "TSV":
            outputs.extend([out / "output.rcf.data.tsv", out / "output.rcf.stat.tsv"])
        elif extra in {"FULL", "DYNOMICS"}:
            outputs.append(out / "output.rcf.xlsx")
        else:
            outputs.extend([out / "output.rcf.data.csv", out / "output.rcf.stat.csv"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        filetypes = ["centrifuge", "clark", "generic", "lmat", "kraken"]
        scoring_options = [
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
        return {
            "required": {
                "input_file": (
                    "TSV",
                    {"multiple": True, "description": "One or more tabular classifier outputs for Recentrifuge"},
                ),
                "filetype": (
                    "STRING",
                    {
                        "default": "centrifuge",
                        "options": filetypes,
                        "description": "Input classifier output type: Centrifuge, CLARK, Generic, LMAT, or Kraken",
                    },
                ),
                "database_name": (
                    "DIRECTORY",
                    {"description": "NCBI taxonomy database directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels used for linked Recentrifuge input filenames",
                    },
                ),
                "format": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Generic classifier format string such as TYP:csv,TID:1,LEN:3,SCO:6,UNC:0",
                        "displayOptions": {"show": {"filetype": ["generic"]}},
                    },
                ),
                "extra": (
                    "STRING",
                    {
                        "default": "CSV",
                        "options": ["CSV", "DYNOMICS", "FULL", "TSV"],
                        "description": "Additional Recentrifuge output format",
                    },
                ),
                "nohtml": (
                    "BOOLEAN",
                    {"default": False, "description": "Suppress the HTML report output"},
                ),
                "no_logfile": (
                    "BOOLEAN",
                    {"default": False, "description": "Suppress the Galaxy logfile output"},
                ),
                "controls": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "scoring": (
                    "STRING",
                    {
                        "default": "",
                        "options": scoring_options,
                        "description": "Override Recentrifuge scoring; blank uses the wrapper default for the input type",
                    },
                ),
                "minscore_value": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mintaxa": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "exclude_taxa_name": (
                    "STRING",
                    {"default": "", "description": "Comma-separated NCBI tax IDs to exclude", "advanced": True},
                ),
                "include_taxa_name": (
                    "STRING",
                    {"default": "", "description": "Comma-separated NCBI tax IDs to include", "advanced": True},
                ),
                "avoidcross": (
                    "BOOLEAN",
                    {"default": False, "description": "Avoid cross analysis", "advanced": True},
                ),
                "ctrlminscore": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "ctrlmintaxa": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "summary": (
                    "STRING",
                    {
                        "default": "ADD",
                        "options": ["ADD", "ONLY", "AVOID"],
                        "description": "Add, only show, or avoid summary samples",
                    },
                ),
                "takeoutroot": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove counts directly assigned to root", "advanced": True},
                ),
                "nokollapse": (
                    "BOOLEAN",
                    {"default": False, "description": "Show the cellular organisms taxon", "advanced": True},
                ),
                "strain": (
                    "BOOLEAN",
                    {"default": False, "description": "Use strain-level resolution", "advanced": True},
                ),
                "sequential": (
                    "BOOLEAN",
                    {"default": False, "description": "Deactivate parallel processing", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _TaxpastaContract(ToolsIUCCommandContract):
    """Standardise and merge taxonomic profiler reports with Taxpasta."""

    LEGACY_NODE_ID = "taxpasta"
    DISPLAY_NAME = "Taxpasta"
    REQUIRED_CONDA_PACKAGES = ["taxpasta"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Standardise and merge taxonomic profiles from common metagenomic profilers."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "taxpasta",
        "taxonomic profile standardisation",
        "taxonomy aggregation",
        "BIOM",
        "Kraken2 report",
        "MetaPhlAn",
        "DIAMOND taxonomy",
    ]
    RETURN_TYPES = ("TSV", "BIOM")
    RETURN_NAMES = ("tabular_output", "biom_output")
    REQUIRED_EXECUTABLES = ["taxpasta"]
    DOCUMENTATION_URL = "https://taxpasta.readthedocs.io/en/latest/"
    CITATION_DOIS = [TAXPASTA_DOI]
    CITATION_URLS = [f"{DOI_URL}{TAXPASTA_DOI}"]
    CITATION_TEXT = TAXPASTA_CITATION_TEXT
    VERSION = "0.7.0"
    SHELL = True
    PROFILERS = [
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

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("action", "standardise")) == "merge":
            return str(inputs.get("output_format", "TSV"))
        return "TSV"

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return "biom_output.biom" if cls._output_format(inputs) == "BIOM" else "tabular_output.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        action = str(inputs.get("action", "standardise"))
        output_format = cls._output_format(inputs)
        cmd = [
            "taxpasta",
            action,
            "--profiler",
            str(inputs.get("profiler", "")),
            "--taxonomy",
            str(inputs.get("taxonomy", "")),
            "--output-format",
            output_format,
            "--output",
            f"{out}/{cls._output_filename(inputs)}",
        ]

        if action == "merge" and output_format == "TSV":
            cmd.append("--wide" if inputs.get("wide", True) else "--long")

        for input_name, flag in (
            ("add_name", "--add-name"),
            ("add_rank", "--add-rank"),
            ("add_lineage", "--add-lineage"),
            ("add_id_lineage", "--add-id-lineage"),
            ("add_rank_lineage", "--add-rank-lineage"),
        ):
            default = input_name == "add_name"
            if inputs.get(input_name, default):
                cmd.append(flag)

        cmd.extend(_as_list(inputs.get("infile")))
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("infile")):
            return "At least one Taxpasta input report is required"
        action = str(inputs.get("action", "standardise"))
        if action not in {"standardise", "merge"}:
            return f"Unsupported Taxpasta action: {action}"
        profiler = str(inputs.get("profiler", ""))
        if not profiler:
            return "Taxpasta profiler is required"
        if profiler not in cls.PROFILERS:
            return f"Unsupported Taxpasta profiler: {profiler}"
        if not inputs.get("taxonomy"):
            return "NCBI taxonomy directory is required"
        output_format = str(inputs.get("output_format", "TSV"))
        if output_format not in {"TSV", "BIOM"}:
            return f"Unsupported Taxpasta output format: {output_format}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "action": (
                    "STRING",
                    {
                        "default": "standardise",
                        "options": ["standardise", "merge"],
                        "description": "Taxpasta action matching the Galaxy wrapper",
                    },
                ),
                "profiler": (
                    "STRING",
                    {
                        "default": "kraken2",
                        "options": cls.PROFILERS,
                        "description": "Profiler that produced the input taxonomic report",
                    },
                ),
                "infile": (
                    "TSV",
                    {"multiple": True, "description": "One or more taxonomic reports from the same profiler"},
                ),
                "taxonomy": (
                    "DIRECTORY",
                    {"description": "NCBI taxonomy directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "output_format": (
                    "STRING",
                    {
                        "default": "TSV",
                        "options": ["TSV", "BIOM"],
                        "description": "Desired output format when merging profiles",
                        "displayOptions": {"show": {"action": ["merge"]}},
                    },
                ),
                "wide": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Output merged TSV abundance data in wide format instead of long format",
                        "displayOptions": {"show": {"action": ["merge"], "output_format": ["TSV"]}},
                    },
                ),
                "add_name": ("BOOLEAN", {"default": True, "description": "Add taxon names to the output"}),
                "add_rank": ("BOOLEAN", {"default": False, "description": "Add taxon ranks to the output"}),
                "add_lineage": (
                    "BOOLEAN",
                    {"default": False, "description": "Add semicolon-separated taxon name lineages"},
                ),
                "add_id_lineage": (
                    "BOOLEAN",
                    {"default": False, "description": "Add semicolon-separated taxon identifier lineages"},
                ),
                "add_rank_lineage": (
                    "BOOLEAN",
                    {"default": False, "description": "Add semicolon-separated taxon rank lineages"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _TaxonKitName2TaxidContract(ToolsIUCCommandContract):
    """Convert taxon names to NCBI taxonomy identifiers with TaxonKit."""

    LEGACY_NODE_ID = "taxonkit_name2taxid"
    DISPLAY_NAME = "Name2taxid"
    REQUIRED_CONDA_PACKAGES = ["taxonkit", "tar"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert NCBI taxon names in a tabular column to taxids with TaxonKit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "TaxonKit",
        "Name2taxid",
        "TaxonKit name2taxid",
        "NCBI taxid lookup",
        "taxon names to taxids",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["taxonkit", "tar"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/taxonkit/"
    CITATION_DOIS = ["10.1016/j.jgg.2021.03.006"]
    CITATION_URLS = [f"{DOI_URL}10.1016/j.jgg.2021.03.006"]
    CITATION_TEXT = "TaxonKit: a practical and efficient NCBI taxonomy toolkit."
    VERSION = "0.20.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [shlex.join(["mkdir", "-p", out, ".taxonkit"])]
        data_source = str(inputs.get("data_source", "cached") or "cached")
        if data_source == "history":
            taxdump = str(inputs.get("taxdump", ""))
            setup.extend(
                [
                    shlex.join(["ln", "-s", taxdump, "taxdump.tar.gz"]),
                    shlex.join(["tar", "-xf", "taxdump.tar.gz", "-C", "."]),
                ]
            )
        else:
            taxonomy_dir = str(inputs.get("taxonomy_dir", ""))
            for filename in ["names.dmp", "merged.dmp", "nodes.dmp", "delnodes.dmp"]:
                setup.append(shlex.join(["ln", "-s", f"{taxonomy_dir}/{filename}", filename]))

        cmd = [
            "taxonkit",
            "name2taxid",
            "--data-dir",
            ".",
            "--name-field",
            str(inputs.get("name_field", "")),
        ]
        if inputs.get("sci_name"):
            cmd.append("--sci-name")
        if inputs.get("show_rank"):
            cmd.append("--show-rank")
        cmd.append(str(inputs.get("input", "")))
        return " && ".join([*setup, f"{shlex.join(cmd)} > {shlex.quote(f'{out}/names2taxid.tsv')}"])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "names2taxid.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        raw_name_field = inputs.get("name_field")
        if raw_name_field is None or str(raw_name_field) == "":
            return "name_field is required"
        try:
            name_field = int(raw_name_field)
        except (TypeError, ValueError):
            return "name_field must be an integer"
        if name_field < 1:
            return "name_field must be >= 1"
        data_source = str(inputs.get("data_source", "cached") or "cached")
        if data_source not in {"cached", "history"}:
            return "data_source must be one of: cached, history"
        if data_source == "history" and not str(inputs.get("taxdump", "")).strip():
            return "taxdump is required when data_source is history"
        if data_source == "cached" and not str(inputs.get("taxonomy_dir", "")).strip():
            return "taxonomy_dir is required when data_source is cached"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Tabular or one-name-per-line input containing NCBI taxon names"}),
                "name_field": ("INT", {"min": 1, "default": 1, "description": "One-based column containing taxon names"}),
                "data_source": (
                    "STRING",
                    {"default": "cached", "options": ["cached", "history"], "description": "Use cached taxonomy files or a taxdump archive"},
                ),
            },
            "optional": {
                "taxonomy_dir": (
                    "DIRECTORY",
                    {"default": "", "description": "Cached NCBI taxonomy directory containing names.dmp, nodes.dmp, merged.dmp, and delnodes.dmp"},
                ),
                "taxdump": ("FILE", {"default": "", "description": "NCBI taxdump.tar.gz archive when data_source is history"}),
                "sci_name": ("BOOLEAN", {"default": False, "description": "Only search scientific names"}),
                "show_rank": ("BOOLEAN", {"default": False, "description": "Include the resolved taxon rank in the output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _TaxonKitProfile2CamiContract(ToolsIUCCommandContract):
    """Convert taxonomic abundance profiles to CAMI format with TaxonKit."""

    LEGACY_NODE_ID = "taxonkit_profile2cami"
    DISPLAY_NAME = "Profile2CAMI"
    REQUIRED_CONDA_PACKAGES = ["taxonkit"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert metagenomic taxonomic profile tables to CAMI format with TaxonKit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "TaxonKit",
        "Profile2CAMI",
        "TaxonKit profile2cami",
        "CAMI profile format",
        "taxonomic profile conversion",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("cami_output",)
    REQUIRED_EXECUTABLES = ["taxonkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/taxonkit/"
    CITATION_DOIS = ["10.1016/j.jgg.2021.03.006"]
    CITATION_URLS = [f"{DOI_URL}10.1016/j.jgg.2021.03.006"]
    CITATION_TEXT = "TaxonKit: a practical and efficient NCBI taxonomy toolkit."
    VERSION = "0.20.0"
    SHELL = True
    RANKS = ["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "taxonkit",
            "profile2cami",
            "--data-dir",
            str(inputs.get("taxonomy", "")),
            "--abundance-field",
            str(inputs.get("abundance_field", 2)),
            "--taxid-field",
            str(inputs.get("taxid_field", 1)),
        ]
        for input_name, flag in (
            ("percentage", "-p"),
            ("recompute_abd", "-R"),
            ("keep_zero", "-0"),
            ("no_sum_up", "-S"),
        ):
            if inputs.get(input_name):
                cmd.append(flag)
        _add_if_value(cmd, "-s", inputs.get("sample_id"))
        _add_if_value(cmd, "-t", inputs.get("taxonomy_id"))
        ranks = _as_list(inputs.get("ranks"))
        if ranks:
            cmd.extend(["--show-rank", ",".join(ranks)])
        cmd.append(str(inputs.get("input_file", "")))
        return f"{shlex.join(cmd)} > {shlex.quote(f'{out}/cami_profile.tsv')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "cami_profile.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        if not str(inputs.get("taxonomy", "")).strip():
            return "taxonomy is required"
        for name in ["abundance_field", "taxid_field"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        unsupported_ranks = [rank for rank in _as_list(inputs.get("ranks")) if rank not in cls.RANKS]
        if unsupported_ranks:
            return f"ranks contains unsupported values: {', '.join(unsupported_ranks)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("TSV", {"description": "Tab-delimited profile table with TaxId and abundance columns"}),
                "taxonomy": ("DIRECTORY", {"description": "NCBI taxonomy directory used by TaxonKit"}),
            },
            "optional": {
                "abundance_field": ("INT", {"default": 2, "min": 1, "description": "One-based abundance field index"}),
                "taxid_field": ("INT", {"default": 1, "min": 1, "description": "One-based TaxId field index"}),
                "percentage": ("BOOLEAN", {"default": False, "description": "Input abundances are percentages"}),
                "recompute_abd": (
                    "BOOLEAN",
                    {"default": False, "description": "Recompute abundance when deleted TaxIds are encountered"},
                ),
                "keep_zero": ("BOOLEAN", {"default": False, "description": "Keep taxa with zero abundance"}),
                "no_sum_up": ("BOOLEAN", {"default": False, "description": "Do not sum abundance from children to parents"}),
                "sample_id": ("STRING", {"default": "", "description": "Optional sample ID to include in the CAMI output"}),
                "taxonomy_id": ("STRING", {"default": "", "description": "Optional taxonomy ID to include in the CAMI output"}),
                "ranks": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.RANKS,
                        "description": "Ranks to show in the CAMI output",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
