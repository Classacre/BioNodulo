"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class BrackenEstAbundanceNode(CommandNode):
    """Re-estimate taxonomic abundance from a Kraken report with Bracken."""

    NODE_ID = "est_abundance"
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

class MagicBlastNode(CommandNode):
    """Map large RNA or DNA reads against a genome or transcriptome with Magic-BLAST."""

    NODE_ID = "magicblast"
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

class BMTaggerNode(CommandNode):
    """Remove contaminant reads with BMTagger."""

    NODE_ID = "bmtagger"
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

class BiomSummarizeTableNode(CommandNode):
    """Summarize sample or observation data in a BIOM table."""

    NODE_ID = "biom_summarize_table"
    DISPLAY_NAME = "BIOM summarize table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Summarize sample or observation data in a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_summarize_table",
        "biom summarize-table",
        "summarize sample data",
        "summarize observation data",
        "microbiome table summary",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#summarize-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "summarize-table",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        if inputs.get("qualitative", True):
            cmd.append("--qualitative")
        if inputs.get("observations", True):
            cmd.append("--observations")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table"}),
            },
            "optional": {
                "qualitative": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Present counts as unique observation ids rather than observation counts",
                    },
                ),
                "observations": (
                    "BOOLEAN",
                    {"default": True, "description": "Summarize over observations instead of samples"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BiomNormalizeTableNode(CommandNode):
    """Normalize a BIOM table over samples or observations."""

    NODE_ID = "biom_normalize_table"
    DISPLAY_NAME = "BIOM normalize table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Normalize a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_normalize_table",
        "biom normalize-table",
        "relative abundance",
        "presence absence",
        "normalize microbiome table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#normalize-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True
    AXES = ["sample", "observation"]

    @classmethod
    def _axis(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("axis", "sample") or "sample")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "normalize-table",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        if inputs.get("relative_abund", True):
            cmd.append("--relative-abund")
        if inputs.get("presence_absence", True):
            cmd.append("--presence-absence")
        cmd.extend(["--axis", cls._axis(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        axis = cls._axis(inputs)
        if axis not in cls.AXES:
            return f"axis must be one of: {', '.join(cls.AXES)}"
        if not inputs.get("relative_abund", True) and not inputs.get("presence_absence", True):
            return "At least one normalization mode must be enabled"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table to normalize"}),
            },
            "optional": {
                "relative_abund": (
                    "BOOLEAN",
                    {"default": True, "description": "Convert table values to relative abundance"},
                ),
                "presence_absence": (
                    "BOOLEAN",
                    {"default": True, "description": "Convert table values to presence or absence"},
                ),
                "axis": (
                    "STRING",
                    {
                        "default": "sample",
                        "options": cls.AXES,
                        "description": "Normalize over samples or observations",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BiomSubsetTableNode(CommandNode):
    """Subset a BIOM table by sample or observation IDs."""

    NODE_ID = "biom_subset_table"
    DISPLAY_NAME = "BIOM subset table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Subset a BIOM table by sample or observation IDs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_subset_table",
        "biom subset-table",
        "sample IDs",
        "observation IDs",
        "subset microbiome table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#subset-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True
    AXES = ["sample", "observation"]

    @classmethod
    def _axis(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("axis", "sample") or "sample")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "subset-table",
            "--input-json-fp",
            str(inputs.get("input_json_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
            "--axis",
            cls._axis(inputs),
            "--ids",
            str(inputs.get("ids", "")),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_json_fp", "")).strip():
            return "input_json_fp is required"
        if not str(inputs.get("ids", "")).strip():
            return "ids is required"
        axis = cls._axis(inputs)
        if axis not in cls.AXES:
            return f"axis must be one of: {', '.join(cls.AXES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_json_fp": ("FILE", {"description": "Input BIOM table to subset"}),
                "ids": ("FILE", {"description": "Single-column text or tabular file of IDs to retain"}),
            },
            "optional": {
                "axis": (
                    "STRING",
                    {
                        "default": "sample",
                        "options": cls.AXES,
                        "description": "Subset sample IDs or observation IDs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BiomFromUcNode(CommandNode):
    """Create a BIOM table from a vsearch, uclust, or usearch UC file."""

    NODE_ID = "biom_from_uc"
    DISPLAY_NAME = "BIOM from UC"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Create a BIOM table from a vsearch, uclust, or usearch UC file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_from_uc",
        "biom from-uc",
        "UC file",
        "vsearch",
        "uclust",
        "usearch",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#from-uc"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "from-uc",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        _add_if_value(cmd, "--rep-set-fp", inputs.get("rep_set_fp"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input vsearch, uclust, or usearch UC file"}),
            },
            "optional": {
                "rep_set_fp": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Optional representative sequences FASTA labeled with OTU identifiers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BiomAddMetadataNode(CommandNode):
    """Add sample and/or observation metadata to a BIOM table."""

    NODE_ID = "biom_add_metadata"
    DISPLAY_NAME = "BIOM add metadata"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add sample and/or observation metadata to a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_add_metadata",
        "biom add-metadata",
        "sample metadata",
        "observation metadata",
        "taxonomy metadata",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/adding_metadata.html"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_as_json(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("output_as_json", True))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = "biom" if cls._output_as_json(inputs) else "h5"
        return f"{_out(inputs)}/output.{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "add-metadata",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        for input_name, flag in (
            ("sample_metadata_fp", "--sample-metadata-fp"),
            ("observation_metadata_fp", "--observation-metadata-fp"),
            ("sc_separated", "--sc-separated"),
            ("sc_pipe_separated", "--sc-pipe-separated"),
            ("int_fields", "--int-fields"),
            ("float_fields", "--float-fields"),
            ("sample_header", "--sample-header"),
            ("observation_header", "--observation-header"),
        ):
            _add_if_value(cmd, flag, inputs.get(input_name))
        if cls._output_as_json(inputs):
            cmd.append("--output-as-json")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        filename = "output.biom" if cls._output_as_json(inputs) else "output.h5"
        return [out / filename]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        text_field_description = "Comma-separated BIOM metadata field list"
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table"}),
            },
            "optional": {
                "sample_metadata_fp": ("TSV", {"default": "", "description": "Optional sample metadata table"}),
                "observation_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional observation metadata table"},
                ),
                "sc_separated": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to split on semicolons"},
                ),
                "sc_pipe_separated": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to split on semicolons and pipes"},
                ),
                "int_fields": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to cast as integers"},
                ),
                "float_fields": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to cast as floating point numbers"},
                ),
                "sample_header": (
                    "STRING",
                    {"default": "", "description": "Comma-separated sample metadata field names"},
                ),
                "observation_header": (
                    "STRING",
                    {"default": "", "description": "Comma-separated observation metadata field names"},
                ),
                "output_as_json": (
                    "BOOLEAN",
                    {"default": True, "description": "Write output as JSON-formatted BIOM1 instead of HDF5"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BiomConvertNode(CommandNode):
    """Convert between BIOM table formats and tabular text."""

    NODE_ID = "biom_convert"
    DISPLAY_NAME = "BIOM convert"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert between BIOM table formats and tabular text."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_convert",
        "biom convert",
        "BIOM1",
        "BIOM2",
        "HDF5",
        "TSV-formatted table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_conversion.html"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    INPUT_TYPES_OPTIONS = ["tsv", "biom"]
    OUTPUT_TYPES = ["tsv", "biom"]
    PROCESS_OBS_METADATA_OPTIONS = ["", "taxonomy", "naive", "sc_separated"]
    TSV_METADATA_FORMATTERS = ["naive", "sc_separated"]
    BIOM_TYPES = ["json", "hdf5"]
    TABLE_TYPES = [
        "OTU table",
        "Pathway table",
        "Function table",
        "Ortholog table",
        "Gene table",
        "Metabolite table",
        "Taxon table",
        "Table",
    ]

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "tsv") or "tsv")

    @classmethod
    def _output_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_type", "biom") or "biom")

    @classmethod
    def _biom_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("biom_type", "json") or "json")

    @classmethod
    def _table_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("table_type", "Table") or "Table")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        if cls._output_type(inputs) == "tsv":
            suffix = "tsv"
        elif cls._biom_type(inputs) == "hdf5":
            suffix = "h5"
        else:
            suffix = "biom"
        return f"{_out(inputs)}/output.{suffix}"

    @classmethod
    def _setup_command(cls, inputs: dict[str, Any]) -> str:
        input_fp = str(inputs.get("input_fp", ""))
        if cls._input_type(inputs) == "tsv":
            return f"sed '1s/^\\([^#].*\\)/#\\1/' {shlex.quote(input_fp)} > input"
        return _shell_join(["ln", "-s", input_fp, "input"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "convert",
            "--input-fp",
            "input",
            "--output-fp",
            cls._output_path(inputs),
        ]
        if cls._input_type(inputs) == "tsv":
            _add_if_value(cmd, "--process-obs-metadata", inputs.get("process_obs_metadata"))

        if cls._output_type(inputs) == "tsv":
            cmd.append("--to-tsv")
            header_key = inputs.get("header_key")
            if header_key:
                cmd.extend(["--header-key", str(header_key)])
                _add_if_value(cmd, "--output-metadata-id", inputs.get("output_metadata_id"))
                cmd.extend(["--tsv-metadata-formatter", str(inputs.get("tsv_metadata_formatter", "naive") or "naive")])
        else:
            cmd.extend(["--table-type", cls._table_type(inputs)])
            if cls._biom_type(inputs) == "hdf5":
                cmd.append("--to-hdf5")
                if inputs.get("collapsed_samples", False):
                    cmd.append("--collapsed-samples")
                if inputs.get("collapsed_observations", False):
                    cmd.append("--collapsed-observations")
            else:
                cmd.append("--to-json")
            _add_if_value(cmd, "--sample-metadata-fp", inputs.get("sample_metadata_fp"))
            _add_if_value(cmd, "--observation-metadata-fp", inputs.get("observation_metadata_fp"))

        return f"{cls._setup_command(inputs)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / Path(cls._output_path(inputs)).name]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        process_obs_metadata = str(inputs.get("process_obs_metadata", "") or "")
        if process_obs_metadata not in cls.PROCESS_OBS_METADATA_OPTIONS:
            return f"process_obs_metadata must be one of: {', '.join(cls.PROCESS_OBS_METADATA_OPTIONS)}"
        output_type = cls._output_type(inputs)
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        if output_type == "biom":
            biom_type = cls._biom_type(inputs)
            if biom_type not in cls.BIOM_TYPES:
                return f"biom_type must be one of: {', '.join(cls.BIOM_TYPES)}"
            table_type = cls._table_type(inputs)
            if table_type not in cls.TABLE_TYPES:
                return f"table_type must be one of: {', '.join(cls.TABLE_TYPES)}"
        formatter = str(inputs.get("tsv_metadata_formatter", "naive") or "naive")
        if formatter not in cls.TSV_METADATA_FORMATTERS:
            return f"tsv_metadata_formatter must be one of: {', '.join(cls.TSV_METADATA_FORMATTERS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input tabular table or BIOM table"}),
            },
            "optional": {
                "input_type": (
                    "STRING",
                    {
                        "default": "tsv",
                        "options": cls.INPUT_TYPES_OPTIONS,
                        "description": "Source format: tabular text or BIOM",
                    },
                ),
                "process_obs_metadata": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.PROCESS_OBS_METADATA_OPTIONS,
                        "description": "Process observation metadata when converting from tabular text",
                    },
                ),
                "output_type": (
                    "STRING",
                    {
                        "default": "biom",
                        "options": cls.OUTPUT_TYPES,
                        "description": "Target format: BIOM or TSV-formatted classic table",
                    },
                ),
                "header_key": (
                    "STRING",
                    {"default": "", "description": "Observation metadata key to include when writing TSV"},
                ),
                "output_metadata_id": (
                    "STRING",
                    {"default": "", "description": "TSV output metadata column name"},
                ),
                "tsv_metadata_formatter": (
                    "STRING",
                    {
                        "default": "naive",
                        "options": cls.TSV_METADATA_FORMATTERS,
                        "description": "Formatter for observation metadata when writing TSV",
                    },
                ),
                "table_type": (
                    "STRING",
                    {
                        "default": "Table",
                        "options": cls.TABLE_TYPES,
                        "description": "BIOM table semantic type",
                    },
                ),
                "biom_type": (
                    "STRING",
                    {
                        "default": "json",
                        "options": cls.BIOM_TYPES,
                        "description": "BIOM output representation: JSON BIOM1 or HDF5 BIOM2",
                    },
                ),
                "collapsed_samples": (
                    "BOOLEAN",
                    {"default": False, "description": "Use collapsed samples when writing HDF5 BIOM"},
                ),
                "collapsed_observations": (
                    "BOOLEAN",
                    {"default": False, "description": "Use collapsed observations when writing HDF5 BIOM"},
                ),
                "sample_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional sample metadata mapping file for BIOM output"},
                ),
                "observation_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional observation metadata mapping file for BIOM output"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsCombineKreportsNode(CommandNode):
    """Combine multiple Kraken-style reports with KrakenTools."""

    NODE_ID = "krakentools_combine_kreports"
    DISPLAY_NAME = "Krakentools Combine Kraken Reports"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Combine multiple Kraken-style taxonomy reports into one summed report."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "combine_kreports.py",
        "Kraken reports",
        "combined report",
        "only combined",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("combined_report",)
    REQUIRED_EXECUTABLES = ["combine_kreports.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _report_names(cls, inputs: dict[str, Any], reports: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, report in enumerate(reports):
            label = labels[index] if index < len(labels) and labels[index] else report
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reports = _as_list(inputs.get("reports"))
        display_headers = bool(inputs.get("display_headers", True))
        report_args = reports
        commands: list[str] = []
        if display_headers:
            report_args = cls._report_names(inputs, reports)
            commands.extend(
                f"ln -s {shlex.quote(report)} {shlex.quote(report_name)}"
                for report, report_name in zip(reports, report_args, strict=False)
            )

        cmd = [
            "combine_kreports.py",
            "--reports",
            *report_args,
            "--output",
            f"{out}/combined_kreport.tsv",
            "--display-headers" if display_headers else "--no-headers",
        ]
        if inputs.get("only_combined", False):
            cmd.append("--only-combined")
        commands.append(shlex.join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "combined_kreport.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reports": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kraken-style report files to combine"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample names used as headers when display_headers is enabled",
                    },
                ),
                "display_headers": (
                    "BOOLEAN",
                    {"default": True, "description": "Display sample headers in the combined output"},
                ),
                "only_combined": (
                    "BOOLEAN",
                    {"default": False, "description": "Display only combined read counts and percentages"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsAlphaDiversityNode(CommandNode):
    """Calculate alpha diversity metrics from Bracken abundance estimates."""

    NODE_ID = "krakentools_alpha_diversity"
    DISPLAY_NAME = "Krakentools Alpha Diversity"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Calculate alpha diversity metrics from a Bracken abundance estimation table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "alpha_diversity.py",
        "alpha diversity",
        "Bracken abundance",
        "Shannon diversity",
    ]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("alpha_diversity",)
    REQUIRED_EXECUTABLES = ["alpha_diversity.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        abundance_file = inputs.get("abundance_file", inputs.get("filename", ""))
        cmd = [
            "alpha_diversity.py",
            "--filename",
            str(abundance_file),
            "--alpha",
            str(inputs.get("alpha", "Sh")),
        ]
        _add_shell_redirect(cmd, f"{out}/alpha_diversity.txt")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "alpha_diversity.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "abundance_file": (
                    "TSV",
                    {"description": "Bracken abundance estimation table used to calculate alpha diversity"},
                ),
            },
            "optional": {
                "alpha": (
                    "STRING",
                    {
                        "default": "Sh",
                        "options": ["Sh", "BP", "Si", "ISi", "F"],
                        "description": "Alpha diversity metric: Shannon, Berger-Parker, Simpson, inverse Simpson, or Fisher",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsBetaDiversityNode(CommandNode):
    """Calculate Bray-Curtis beta diversity from taxonomy tables."""

    NODE_ID = "krakentools_beta_diversity"
    DISPLAY_NAME = "Krakentools Beta Diversity"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Calculate Bray-Curtis beta diversity from Kraken, Krona, Bracken, or tabular taxonomy files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "beta_diversity.py",
        "beta diversity",
        "Bray-Curtis",
        "Krona file",
        "Bracken abundance",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("beta_diversity",)
    REQUIRED_EXECUTABLES = ["beta_diversity.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], taxonomy_files: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, taxonomy_file in enumerate(taxonomy_files):
            label = labels[index] if index < len(labels) and labels[index] else taxonomy_file
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        taxonomy_files = _as_list(inputs.get("taxonomy_files", inputs.get("inputs")))
        input_names = cls._input_names(inputs, taxonomy_files)
        commands = [
            f"ln -s {shlex.quote(taxonomy_file)} {shlex.quote(input_name)}"
            for taxonomy_file, input_name in zip(taxonomy_files, input_names, strict=False)
        ]

        sample_type = str(inputs.get("sample_type", inputs.get("type", "single")))
        cmd = [
            "beta_diversity.py",
            "--inputs",
            *input_names,
            "--type",
            sample_type,
        ]
        if sample_type in {"kreport", "krona"}:
            cmd.extend(["--level", str(inputs.get("level", "all"))])
        _add_shell_redirect(cmd, f"{out}/beta_diversity.tsv")
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "beta_diversity.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "taxonomy_files": (
                    "TSV",
                    {"multiple": True, "description": "Kraken, Krona, Bracken, or tabular taxonomy files"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels used for beta diversity matrix headers",
                    },
                ),
                "sample_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "simple", "bracken", "kreport", "krona"],
                        "description": "Input file type used by KrakenTools beta_diversity.py",
                    },
                ),
                "level": (
                    "STRING",
                    {
                        "default": "all",
                        "options": ["all", "S", "G", "F", "O"],
                        "description": "Taxonomic level used for Kraken report or Krona inputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsKreport2KronaNode(CommandNode):
    """Convert Kraken reports to Krona-compatible text tables."""

    NODE_ID = "krakentools_kreport2krona"
    DISPLAY_NAME = "Krakentools Kreport2Krona"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a Kraken report into a Krona-compatible text table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "kreport2krona.py",
        "Krona-compatible",
        "intermediate ranks",
        "Kraken report",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("krona_text",)
    REQUIRED_EXECUTABLES = ["kreport2krona.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "kreport2krona.py",
            "--report",
            str(inputs.get("report", "")),
            "--output",
            f"{out}/krona_text.tsv",
        ]
        if inputs.get("intermediate_ranks", False):
            cmd.append("--intermediate-ranks")
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona_text.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("TSV", {"description": "Kraken report file to convert to Krona-compatible text"}),
            },
            "optional": {
                "intermediate_ranks": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-standard intermediate ranks in the Krona paths"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TaxonomyKronaChartNode(CommandNode):
    """Render taxonomy or tabular profiles as an interactive Krona chart."""

    NODE_ID = "taxonomy_krona_chart"
    DISPLAY_NAME = "Krona pie chart"
    REQUIRED_CONDA_PACKAGES = ["krona"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Render taxonomic profiles as an interactive Krona HTML pie chart."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Krona",
        "taxonomy_krona_chart",
        "ktImportGalaxy",
        "ktImportText",
        "taxonomy sunburst",
        "metagenomic visualization",
        "taxonomic profile",
    ]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["ktImportGalaxy", "ktImportText"]
    DOCUMENTATION_URL = "https://github.com/marbl/Krona/wiki"
    CITATION_DOIS = KRONA_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in KRONA_CITATION_DOIS]
    CITATION_TEXT = KRONA_CITATION_TEXT
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    TYPE_OPTIONS = ["taxonomy", "text"]
    MAX_RANK_OPTIONS = [
        "8",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
    ]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input"))

    @classmethod
    def _input_labels(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        result: list[str] = []
        for index, input_file in enumerate(input_files):
            label = labels[index] if index < len(labels) and labels[index] else Path(input_file).stem
            result.append(_safe_identifier(label))
        return result

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/krona.html"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = str(inputs.get("type_of_data_selector", "taxonomy") or "taxonomy")
        cmd = ["ktImportGalaxy" if input_type == "taxonomy" else "ktImportText"]
        if input_type == "taxonomy":
            cmd.extend(["-d", str(inputs.get("max_rank", "8") or "8")])
        cmd.extend([
            "-n",
            str(inputs.get("root_name", "Root") or "Root"),
            "-o",
            cls._output_path(inputs),
        ])
        if inputs.get("combine_inputs", False):
            cmd.append("-c")
        input_files = cls._input_files(inputs)
        labels = cls._input_labels(inputs, input_files)
        for input_file, label in zip(input_files, labels, strict=False):
            cmd.append(f"{input_file},{label}")
        return " && ".join([f"mkdir -p {shlex.quote(out)}", _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona.html"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one input file is required"
        input_type = str(inputs.get("type_of_data_selector", "taxonomy") or "taxonomy")
        if input_type not in cls.TYPE_OPTIONS:
            return f"type_of_data_selector must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        max_rank = str(inputs.get("max_rank", "8") or "8")
        if max_rank not in cls.MAX_RANK_OPTIONS:
            return f"max_rank must be one of: {', '.join(cls.MAX_RANK_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"multiple": True, "description": "One or more taxonomy or tabular profile files"}),
            },
            "optional": {
                "type_of_data_selector": (
                    "STRING",
                    {
                        "default": "taxonomy",
                        "options": cls.TYPE_OPTIONS,
                        "description": "Galaxy taxonomy input or generic tabular profile input",
                    },
                ),
                "max_rank": (
                    "STRING",
                    {
                        "default": "8",
                        "options": cls.MAX_RANK_OPTIONS,
                        "description": "Maximum taxonomy rank depth for Galaxy taxonomy input",
                    },
                ),
                "root_name": ("STRING", {"default": "Root", "description": "Name for the basal rank"}),
                "combine_inputs": (
                    "BOOLEAN",
                    {"default": False, "description": "Combine multiple datasets into one Krona chart"},
                ),
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional labels for the input datasets"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MothurTaxonomyToKronaNode(CommandNode):
    """Convert mothur consensus taxonomy tables to Krona text input."""

    NODE_ID = "mothur_taxonomy_to_krona"
    DISPLAY_NAME = "Taxonomy-to-Krona"
    REQUIRED_CONDA_PACKAGES = []
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a mothur consensus taxonomy file to Krona text input format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mothur",
        "mothur_taxonomy_to_krona",
        "Taxonomy-to-Krona",
        "mothur consensus taxonomy",
        "Krona text input",
        "strip confidence values",
        "cons.taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outputfile",)
    REQUIRED_EXECUTABLES = ["cat", "tail", "cut", "sed"]
    DOCUMENTATION_URL = "https://marbl.github.io/Krona/Documentation/"
    CITATION_DOIS = [MOTHUR_DOI, KRONA_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = f"{MOTHUR_CITATION_TEXT} {KRONA_CITATION_TEXT.split(';', 1)[0]}."
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/krona_taxonomy.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        pipeline = [
            f"cat {shlex.quote(str(inputs.get('inputfile', '')))}",
            "tail -n +2",
            "cut -f2,3",
            "sed 's/;/\\t/g'",
            "sed 's/\"//g'",
            "sed 's/[ \\t]*$//'",
        ]
        if inputs.get("stripconfidences", False):
            pipeline.append("sed -r 's/[(][0-9]+[)]//g'")
        return f"{' | '.join(pipeline)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona_taxonomy.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("inputfile", "")).strip():
            return "inputfile is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputfile": (
                    "TSV",
                    {
                        "description": "Mothur consensus taxonomy table with OTU, size, and taxonomy columns",
                    },
                ),
            },
            "optional": {
                "stripconfidences": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Remove taxonomy confidence values such as Bacteria(100)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsKreport2MpaNode(CommandNode):
    """Convert Kraken reports to MetaPhlAn-style profile tables."""

    NODE_ID = "krakentools_kreport2mpa"
    DISPLAY_NAME = "Krakentools Kreport2MPA"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a Kraken report into a MetaPhlAn-style profile table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "kreport2mpa.py",
        "MetaPhlAn-style",
        "percentages",
        "intermediate ranks",
        "Kraken report",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("metaphlan_profile",)
    REQUIRED_EXECUTABLES = ["kreport2mpa.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "kreport2mpa.py",
            "--report",
            str(inputs.get("report", "")),
            "--output",
            f"{out}/metaphlan_profile.tsv",
        ]
        if inputs.get("intermediate_ranks", False):
            cmd.append("--intermediate-ranks")
        if inputs.get("percentages", False):
            cmd.append("--percentages")
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "metaphlan_profile.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("TSV", {"description": "Kraken report file to convert to MetaPhlAn-style format"}),
            },
            "optional": {
                "intermediate_ranks": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-standard intermediate ranks in the output profile"},
                ),
                "percentages": (
                    "BOOLEAN",
                    {"default": False, "description": "Report percentage of total reads instead of raw read counts"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakentoolsExtractKrakenReadsNode(CommandNode):
    """Extract reads assigned to selected taxonomy IDs from Kraken output."""

    NODE_ID = "krakentools_extract_kraken_reads"
    DISPLAY_NAME = "Krakentools Extract Kraken Reads By ID"
    REQUIRED_CONDA_PACKAGES = ["krakentools", "gzip"]
    CATEGORY = "taxonomy"
    DESCRIPTION = (
        "Extract FASTA or FASTQ reads assigned to selected taxonomic IDs from "
        "Kraken, KrakenUniq, or Kraken2 classifications."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "extract_kraken_reads.py",
        "Kraken reads",
        "taxonomic IDs",
        "include children",
        "paired collection",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "DIRECTORY")
    RETURN_NAMES = ("forward_reads", "reverse_reads", "paired_reads")
    REQUIRED_EXECUTABLES = ["extract_kraken_reads.py", "gzip"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _library_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("library_type", inputs.get("type", "single")))

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return cls._library_type(inputs) in {"paired", "paired_collection"}

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        return "fastq" if inputs.get("fastq_output", False) else "fasta"

    @classmethod
    def _temp_output_name(cls, inputs: dict[str, Any], index: int) -> str:
        return f"output_{index}.{cls._output_ext(inputs)}"

    @classmethod
    def _compressed_output_name(cls, inputs: dict[str, Any], index: int) -> str:
        return f"{cls._temp_output_name(inputs, index)}.gz"

    @classmethod
    def _is_gzipped(cls, inputs: dict[str, Any], key: str, path: str) -> bool:
        ext = str(inputs.get(f"{key}_ext", "")).lower()
        return ext.endswith("gz") or path.lower().endswith(".gz")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("paired_collection", inputs.get("input_1", ""))
        if isinstance(collection, dict):
            forward = collection.get("forward", collection.get("input_1", ""))
            reverse = collection.get("reverse", collection.get("input_2", ""))
            return str(forward), str(reverse)
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return str(collection[0]), str(collection[1])
        if collection:
            collection_path = str(collection).rstrip("/")
            return f"{collection_path}/forward", f"{collection_path}/reverse"
        return str(inputs.get("input_1", "")), str(inputs.get("input_2", ""))

    @classmethod
    def _input_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._library_type(inputs) == "paired_collection":
            return cls._paired_collection_reads(inputs)
        return str(inputs.get("input_1", "")), str(inputs.get("input_2", ""))

    @classmethod
    def _linked_inputs(cls, inputs: dict[str, Any]) -> tuple[list[str], str, str]:
        input_1, input_2 = cls._input_paths(inputs)
        commands: list[str] = []
        if cls._is_gzipped(inputs, "input_1", input_1):
            commands.append(f"ln -s {shlex.quote(input_1)} input_1.gz")
            input_1 = "input_1.gz"
        if cls._is_paired(inputs) and cls._is_gzipped(inputs, "input_2", input_2):
            commands.append(f"ln -s {shlex.quote(input_2)} input_2.gz")
            input_2 = "input_2.gz"
        return commands, input_1, input_2

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        taxids = str(inputs.get("taxid", "")).strip().split()
        if not taxids or any(not taxid.isdigit() for taxid in taxids):
            return "Taxonomic ID(s) must be a space-separated list of numeric tax IDs"
        if (inputs.get("include_parents") or inputs.get("include_children")) and not inputs.get("report"):
            return "Report is required when including parent or child taxonomic assignments"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands, input_1, input_2 = cls._linked_inputs(inputs)
        cmd = [
            "extract_kraken_reads.py",
            "-k",
            str(inputs.get("results", "")),
            "-s",
            input_1,
            "-o",
            cls._temp_output_name(inputs, 1),
            "--taxid",
            *str(inputs.get("taxid", "")).strip().split(),
            "--max",
            str(inputs.get("max_reads", inputs.get("max", 100000000))),
        ]
        if inputs.get("include_parents", False):
            cmd.append("--include-parents")
        if inputs.get("include_children", False):
            cmd.append("--include-children")
        if inputs.get("exclude", False):
            cmd.append("--exclude")
        if inputs.get("fastq_output", False):
            cmd.append("--fastq-output")
        if cls._is_paired(inputs):
            cmd.extend(["-s2", input_2, "-o2", cls._temp_output_name(inputs, 2)])
        if inputs.get("include_parents", False) or inputs.get("include_children", False):
            cmd.extend(["--report", str(inputs.get("report", ""))])
        commands.append(shlex.join(cmd))

        gzip_1 = ["gzip", "-cvf", cls._temp_output_name(inputs, 1)]
        _add_shell_redirect(gzip_1, f"{out}/{cls._compressed_output_name(inputs, 1)}")
        commands.append(_shell_join(gzip_1))
        if cls._is_paired(inputs):
            gzip_2 = ["gzip", "-cvf", cls._temp_output_name(inputs, 2)]
            _add_shell_redirect(gzip_2, f"{out}/{cls._compressed_output_name(inputs, 2)}")
            commands.append(_shell_join(gzip_2))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        paired_out = out / "paired_reads"
        paired_out.mkdir(parents=True, exist_ok=True)
        return [
            out / cls._compressed_output_name(inputs, 1),
            out / cls._compressed_output_name(inputs, 2),
            paired_out,
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        sequence_formats = ["fastq", "fasta", "fastq.gz", "fasta.gz"]
        return {
            "required": {
                "library_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired", "paired_collection"],
                        "description": "Single, paired, or paired-collection read input mode",
                    },
                ),
                "input_1": ("FASTQ", {"description": "Single-end input or paired-end forward reads"}),
                "results": ("TSV", {"description": "Kraken, KrakenUniq, or Kraken2 classification results file"}),
                "taxid": (
                    "STRING",
                    {"description": "Space-delimited numeric taxonomy ID list used to select matching reads"},
                ),
            },
            "optional": {
                "input_2": ("FASTQ", {"default": "", "description": "Paired-end reverse reads"}),
                "paired_collection": (
                    "DIRECTORY",
                    {"default": "", "description": "Directory or collection-like value containing forward and reverse reads"},
                ),
                "report": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Kraken report required when include_parents or include_children is enabled",
                    },
                ),
                "max_reads": (
                    "INT",
                    {"default": 100000000, "min": 1, "description": "Maximum number of reads to save for each taxonomic ID"},
                ),
                "exclude": (
                    "BOOLEAN",
                    {"default": False, "description": "Invert output to save reads that do not match the selected tax IDs"},
                ),
                "fastq_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write FASTQ output instead of the default FASTA output"},
                ),
                "include_parents": (
                    "BOOLEAN",
                    {"default": False, "description": "Include reads classified at parent levels of the selected tax IDs"},
                ),
                "include_children": (
                    "BOOLEAN",
                    {"default": False, "description": "Include reads classified below the selected tax IDs"},
                ),
                "input_1_ext": (
                    "STRING",
                    {"default": "fastq", "options": sequence_formats, "advanced": True},
                ),
                "input_2_ext": (
                    "STRING",
                    {"default": "fastq", "options": sequence_formats, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RecentrifugeNode(CommandNode):
    """Run Recentrifuge comparative metagenomics analysis."""

    NODE_ID = "recentrifuge"
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
        if filetype == "generic" and not str(inputs.get("format", "")).strip():
            return "Generic input mode requires a format string"
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

class TaxpastaNode(CommandNode):
    """Standardise and merge taxonomic profiler reports with Taxpasta."""

    NODE_ID = "taxpasta"
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
        if not inputs.get("profiler"):
            return "Taxpasta profiler is required"
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

class TaxonKitName2TaxidNode(CommandNode):
    """Convert taxon names to NCBI taxonomy identifiers with TaxonKit."""

    NODE_ID = "taxonkit_name2taxid"
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

class TaxonKitProfile2CamiNode(CommandNode):
    """Convert taxonomic abundance profiles to CAMI format with TaxonKit."""

    NODE_ID = "taxonkit_profile2cami"
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

class TracyBasecallNode(CommandNode):
    """Basecall Sanger chromatogram trace files with Tracy."""

    NODE_ID = "tracy_basecall"
    DISPLAY_NAME = "tracy Basecall"
    REQUIRED_CONDA_PACKAGES = ["tracy"]
    CATEGORY = "sequence"
    DESCRIPTION = "Basecall a Sanger chromatogram trace file with Tracy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Tracy",
        "tracy Basecall",
        "tracy Sanger basecalling",
        "Sanger chromatogram",
        "AB1 trace",
        "SCF trace",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("basecalls",)
    REQUIRED_EXECUTABLES = ["tracy"]
    DOCUMENTATION_URL = "https://www.gear-genomics.com/docs/tracy/cli/#basecalling-a-chromatogram-trace-file"
    CITATION_DOIS = ["10.1186/s12864-020-6635-8"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s12864-020-6635-8"]
    CITATION_TEXT = "Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files."
    VERSION = "0.7.8"
    FORMATS = ["fasta", "fastq", "tsv", "json"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "fasta") or "fasta")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/basecalls.{cls._format(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "tracy",
            "basecall",
            "--pratio",
            str(inputs.get("pratio", 0.33)),
            "--format",
            cls._format(inputs),
            "--output",
            cls._output_path(inputs),
            str(inputs.get("tracefile", "")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"basecalls.{cls._format(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("tracefile", "")).strip():
            return "tracefile is required"
        raw_pratio = inputs.get("pratio", 0.33)
        try:
            pratio = float(raw_pratio)
        except (TypeError, ValueError):
            return "pratio must be a number"
        if pratio < 0:
            return "pratio must be >= 0"
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tracefile": ("FILE", {"description": "Chromatogram trace file in AB1 or SCF format"}),
            },
            "optional": {
                "pratio": (
                    "FLOAT",
                    {"default": 0.33, "min": 0, "description": "Peak ratio threshold for calling a base"},
                ),
                "format": (
                    "STRING",
                    {"default": "fasta", "options": cls.FORMATS, "description": "Output format"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TracyAlignNode(CommandNode):
    """Align Sanger chromatogram trace files to a reference with Tracy."""

    NODE_ID = "tracy_align"
    DISPLAY_NAME = "tracy Align"
    REQUIRED_CONDA_PACKAGES = ["tracy"]
    CATEGORY = "alignment"
    DESCRIPTION = "Align a Sanger chromatogram trace file to a FASTA, ABI, or SCF reference with Tracy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Tracy",
        "tracy Align",
        "tracy trace alignment",
        "Sanger chromatogram alignment",
        "AB1 trace alignment",
        "SCF trace alignment",
    ]
    RETURN_TYPES = ("TXT", "FASTA", "JSON", "TSV")
    RETURN_NAMES = ("report", "alignment", "json", "stats")
    REQUIRED_EXECUTABLES = ["tracy", "bgzip"]
    DOCUMENTATION_URL = "https://www.gear-genomics.com/docs/tracy/cli/#trace-alignment"
    CITATION_DOIS = ["10.1186/s12864-020-6635-8"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s12864-020-6635-8"]
    CITATION_TEXT = "Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files."
    VERSION = "0.7.8"
    SHELL = True
    OPTIONAL_OUTPUTS = ["json", "tabular"]
    OPTION_DEFAULTS = {
        "kmer": 15,
        "support": 3,
        "maxindel": 1000,
        "trim": 0,
        "trimLeft": 50,
        "trimRight": 50,
        "linelimit": 60,
        "gapopen": -10,
        "gapext": -4,
        "match": 3,
        "mismatch": -5,
    }
    INT_MIN_OPTIONS = {
        "kmer": 1,
        "support": 1,
        "maxindel": 1,
        "linelimit": 1,
        "trimLeft": 0,
        "trimRight": 0,
        "match": 0,
    }
    INT_MAX_OPTIONS = {
        "gapopen": 0,
        "gapext": 0,
        "mismatch": 0,
    }

    @classmethod
    def _optional_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("optional_outputs")
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return _as_list(raw)

    @classmethod
    def _add_alignment_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        options = [
            ("--pratio", "pratio", 0.33),
            ("--kmer", "kmer", cls.OPTION_DEFAULTS["kmer"]),
            ("--support", "support", cls.OPTION_DEFAULTS["support"]),
            ("--maxindel", "maxindel", cls.OPTION_DEFAULTS["maxindel"]),
            ("--trim", "trim", cls.OPTION_DEFAULTS["trim"]),
            ("--trimLeft", "trimLeft", cls.OPTION_DEFAULTS["trimLeft"]),
            ("--trimRight", "trimRight", cls.OPTION_DEFAULTS["trimRight"]),
            ("--linelimit", "linelimit", cls.OPTION_DEFAULTS["linelimit"]),
            ("--gapopen", "gapopen", cls.OPTION_DEFAULTS["gapopen"]),
            ("--gapext", "gapext", cls.OPTION_DEFAULTS["gapext"]),
            ("--match", "match", cls.OPTION_DEFAULTS["match"]),
            ("--mismatch", "mismatch", cls.OPTION_DEFAULTS["mismatch"]),
        ]
        for flag, name, default in options:
            cmd.extend([flag, str(inputs.get(name, default))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reference = str(inputs.get("reference", ""))
        setup: list[str] = []
        if inputs.get("index_genome"):
            indexed_reference = f"{out}/genome.fasta.gz"
            setup = [
                f"bgzip -c {shlex.quote(reference)} > {shlex.quote(indexed_reference)}",
                _shell_join(["tracy", "index", "-o", f"{out}/genome.fasta.fm9", indexed_reference]),
            ]
            reference = indexed_reference

        cmd = ["tracy", "align", "--reference", reference]
        cls._add_alignment_options(cmd, inputs)
        cmd.extend(["--output", out, str(inputs.get("tracefile", ""))])
        return " && ".join([*setup, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out.txt", out / "out.align.fa"]
        optional_outputs = cls._optional_outputs(inputs)
        if "json" in optional_outputs:
            outputs.append(out / "out.json")
        if "tabular" in optional_outputs:
            outputs.append(out / "out.abif")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reference", "")).strip():
            return "reference is required"
        if not str(inputs.get("tracefile", "")).strip():
            return "tracefile is required"
        try:
            pratio = float(inputs.get("pratio", 0.33))
        except (TypeError, ValueError):
            return "pratio must be a number"
        if pratio < 0:
            return "pratio must be >= 0"
        for name, minimum in cls.INT_MIN_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name, maximum in cls.INT_MAX_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value > maximum:
                return f"{name} must be <= {maximum}"
        unsupported = [output for output in cls._optional_outputs(inputs) if output not in cls.OPTIONAL_OUTPUTS]
        if unsupported:
            return f"optional_outputs contains unsupported values: {', '.join(unsupported)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FILE", {"description": "FASTA, ABI, or SCF reference sequence"}),
                "tracefile": ("FILE", {"description": "Sanger chromatogram trace file in AB1 or SCF format"}),
            },
            "optional": {
                "index_genome": (
                    "BOOLEAN",
                    {"default": False, "description": "Pre-index large FASTA references with Tracy FM index"},
                ),
                "pratio": ("FLOAT", {"default": 0.33, "min": 0, "description": "Peak ratio threshold for calling a base"}),
                "kmer": ("INT", {"default": 15, "min": 1, "description": "K-mer size used to anchor the trace"}),
                "support": ("INT", {"default": 3, "min": 1, "description": "Minimum k-mer support"}),
                "maxindel": ("INT", {"default": 1000, "min": 1, "description": "Maximum indel size in the Sanger trace"}),
                "trim": ("INT", {"default": 0, "description": "Trimming stringency; 0 uses trimLeft and trimRight"}),
                "trimLeft": ("INT", {"default": 50, "min": 0, "description": "Fixed bases to trim from the left"}),
                "trimRight": ("INT", {"default": 50, "min": 0, "description": "Fixed bases to trim from the right"}),
                "linelimit": ("INT", {"default": 60, "min": 1, "description": "Alignment line length"}),
                "gapopen": ("INT", {"default": -10, "max": 0, "description": "Gap open penalty"}),
                "gapext": ("INT", {"default": -4, "max": 0, "description": "Gap extension penalty"}),
                "match": ("INT", {"default": 3, "min": 0, "description": "Nucleotide match score"}),
                "mismatch": ("INT", {"default": -5, "max": 0, "description": "Mismatch penalty"}),
                "optional_outputs": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OPTIONAL_OUTPUTS,
                        "description": "Optional JSON and tabular statistics outputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TracyAssembleNode(CommandNode):
    """Assemble overlapping Sanger chromatogram trace files with Tracy."""

    NODE_ID = "tracy_assemble"
    DISPLAY_NAME = "tracy Assemble"
    REQUIRED_CONDA_PACKAGES = ["tracy"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble overlapping Sanger chromatogram trace files into a consensus sequence with Tracy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Tracy",
        "tracy Assemble",
        "tracy trace assembly",
        "Sanger chromatogram assembly",
        "overlapping Sanger traces",
        "consensus sequence",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "JSON")
    RETURN_NAMES = ("consensus", "alignment", "json")
    REQUIRED_EXECUTABLES = ["tracy"]
    DOCUMENTATION_URL = "https://www.gear-genomics.com/docs/tracy/cli/#trace-assembly"
    CITATION_DOIS = ["10.1186/s12864-020-6635-8"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s12864-020-6635-8"]
    CITATION_TEXT = "Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files."
    VERSION = "0.7.8"
    SHELL = True
    FORMATS = ["fasta", "fastq"]
    INT_MIN_OPTIONS = {"trim": 1, "match": 0}
    INT_MAX_OPTIONS = {"gapopen": 0, "gapext": 0, "mismatch": 0}

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "fasta") or "fasta")

    @classmethod
    def _consensus_filename(cls, inputs: dict[str, Any]) -> str:
        return "out.cons.fq" if cls._format(inputs) == "fastq" else "out.cons.fa"

    @classmethod
    def _tracefiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("tracefiles"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["tracy", "assemble"]
        if str(inputs.get("useref", "no") or "no") == "yes":
            cmd.extend(["--reference", str(inputs.get("reference", ""))])
            if inputs.get("incref"):
                cmd.append("--incref")
        cmd.extend(
            [
                "--pratio",
                str(inputs.get("pratio", 0.33)),
                "--trim",
                str(inputs.get("trim", 4)),
                "--fracmatch",
                str(inputs.get("fracmatch", 0.5)),
                "--called",
                str(inputs.get("called", 0.1)),
                "--format",
                cls._format(inputs),
            ]
        )
        if inputs.get("inccons"):
            cmd.append("--inccons")
        cmd.extend(
            [
                "--gapopen",
                str(inputs.get("gapopen", -10)),
                "--gapext",
                str(inputs.get("gapext", -4)),
                "--match",
                str(inputs.get("match", 3)),
                "--mismatch",
                str(inputs.get("mismatch", -5)),
            ]
        )
        cmd.extend(cls._tracefiles(inputs))
        move_cmd = ["mv", cls._consensus_filename(inputs), f"{out}/{cls._consensus_filename(inputs)}"]
        return f"{_shell_join(cmd)} && {_shell_join(move_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._consensus_filename(inputs), out / "out.align.fa"]
        if inputs.get("json_output"):
            outputs.append(out / "out.json")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._tracefiles(inputs):
            return "at least one tracefile is required"
        useref = str(inputs.get("useref", "no") or "no")
        if useref not in {"yes", "no"}:
            return "useref must be one of: yes, no"
        if useref == "yes" and not str(inputs.get("reference", "")).strip():
            return "reference is required when useref is yes"
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        try:
            pratio = float(inputs.get("pratio", 0.33))
        except (TypeError, ValueError):
            return "pratio must be a number"
        if pratio < 0:
            return "pratio must be >= 0"
        try:
            fracmatch = float(inputs.get("fracmatch", 0.5))
        except (TypeError, ValueError):
            return "fracmatch must be a number"
        if fracmatch < 0 or fracmatch > 1:
            return "fracmatch must be between 0 and 1"
        try:
            called = float(inputs.get("called", 0.1))
        except (TypeError, ValueError):
            return "called must be a number"
        if called < 0:
            return "called must be >= 0"
        for name, minimum in cls.INT_MIN_OPTIONS.items():
            try:
                value = int(inputs.get(name, {"trim": 4, "match": 3}[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name, maximum in cls.INT_MAX_OPTIONS.items():
            try:
                value = int(inputs.get(name, {"gapopen": -10, "gapext": -4, "mismatch": -5}[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value > maximum:
                return f"{name} must be <= {maximum}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tracefiles": (
                    "FILE",
                    {"multiple": True, "description": "Sanger chromatogram trace files in AB1 or SCF format"},
                ),
            },
            "optional": {
                "pratio": ("FLOAT", {"default": 0.33, "min": 0, "description": "Peak ratio threshold for calling a base"}),
                "trim": ("INT", {"default": 4, "min": 1, "description": "Automatic trimming stringency"}),
                "fracmatch": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "Minimum fraction of matching positions"},
                ),
                "called": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "description": "Fraction of traces required for consensus"},
                ),
                "format": ("STRING", {"default": "fasta", "options": cls.FORMATS, "description": "Consensus output format"}),
                "inccons": ("BOOLEAN", {"default": False, "description": "Include consensus in the FASTA alignment"}),
                "useref": (
                    "STRING",
                    {"default": "no", "options": ["yes", "no"], "description": "Use a reference to guide assembly"},
                ),
                "reference": ("FASTA", {"default": "", "description": "Optional FASTA reference for guided assembly"}),
                "incref": ("BOOLEAN", {"default": False, "description": "Include reference in the consensus"}),
                "gapopen": ("INT", {"default": -10, "max": 0, "description": "Gap open penalty"}),
                "gapext": ("INT", {"default": -4, "max": 0, "description": "Gap extension penalty"}),
                "match": ("INT", {"default": 3, "min": 0, "description": "Nucleotide match score"}),
                "mismatch": ("INT", {"default": -5, "max": 0, "description": "Mismatch penalty"}),
                "json_output": ("BOOLEAN", {"default": False, "description": "Produce Tracy JSON output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TracyDecomposeNode(CommandNode):
    """Decompose heterozygous Sanger chromatogram mutations with Tracy."""

    NODE_ID = "tracy_decompose"
    DISPLAY_NAME = "tracy Decompose"
    REQUIRED_CONDA_PACKAGES = ["tracy"]
    CATEGORY = "variant"
    DESCRIPTION = "Decompose heterozygous Sanger chromatogram mutations and optionally call variants with Tracy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Tracy",
        "tracy Decompose",
        "tracy heterozygous deconvolution",
        "Sanger chromatogram variants",
        "heterozygous mutations",
        "trace deconvolution",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "FASTA", "JSON", "TSV", "BCF")
    RETURN_NAMES = ("allele1", "allele2", "both_alleles", "json", "stats", "variants")
    REQUIRED_EXECUTABLES = ["tracy", "bgzip"]
    DOCUMENTATION_URL = "https://www.gear-genomics.com/docs/tracy/cli/#deconvolution-of-heterozygous-mutations"
    CITATION_DOIS = ["10.1186/s12864-020-6635-8"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s12864-020-6635-8"]
    CITATION_TEXT = "Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files."
    VERSION = "0.7.8"
    SHELL = True
    OPTIONAL_OUTPUTS = ["json", "tabular"]
    OPTION_DEFAULTS = TracyAlignNode.OPTION_DEFAULTS
    INT_MIN_OPTIONS = TracyAlignNode.INT_MIN_OPTIONS
    INT_MAX_OPTIONS = TracyAlignNode.INT_MAX_OPTIONS

    @classmethod
    def _optional_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("optional_outputs")
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return _as_list(raw)

    @classmethod
    def _add_decompose_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        options = [
            ("--pratio", "pratio", 0.33),
            ("--kmer", "kmer", cls.OPTION_DEFAULTS["kmer"]),
            ("--support", "support", cls.OPTION_DEFAULTS["support"]),
            ("--maxindel", "maxindel", cls.OPTION_DEFAULTS["maxindel"]),
            ("--trim", "trim", cls.OPTION_DEFAULTS["trim"]),
            ("--trimLeft", "trimLeft", cls.OPTION_DEFAULTS["trimLeft"]),
            ("--trimRight", "trimRight", cls.OPTION_DEFAULTS["trimRight"]),
            ("--linelimit", "linelimit", cls.OPTION_DEFAULTS["linelimit"]),
            ("--gapopen", "gapopen", cls.OPTION_DEFAULTS["gapopen"]),
            ("--gapext", "gapext", cls.OPTION_DEFAULTS["gapext"]),
            ("--match", "match", cls.OPTION_DEFAULTS["match"]),
            ("--mismatch", "mismatch", cls.OPTION_DEFAULTS["mismatch"]),
        ]
        for flag, name, default in options:
            cmd.extend([flag, str(inputs.get(name, default))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genome = str(inputs.get("genome", ""))
        setup: list[str] = []
        if inputs.get("index_genome"):
            indexed_genome = f"{out}/genome.fasta.gz"
            setup = [
                f"bgzip -c {shlex.quote(genome)} > {shlex.quote(indexed_genome)}",
                _shell_join(["tracy", "index", "-o", f"{out}/genome.fasta.fm9", indexed_genome]),
            ]
            genome = indexed_genome

        cmd = ["tracy", "decompose", "--genome", genome]
        if inputs.get("callVariants"):
            cmd.append("--callVariants")
        cls._add_decompose_options(cmd, inputs)
        cmd.extend(["--output", out, str(inputs.get("tracefile", ""))])
        return " && ".join([*setup, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out.align1", out / "out.align2", out / "out.align3"]
        optional_outputs = cls._optional_outputs(inputs)
        if "json" in optional_outputs:
            outputs.append(out / "out.json")
        if "tabular" in optional_outputs:
            outputs.append(out / "out.abif")
        if inputs.get("callVariants"):
            outputs.append(out / "out.bcf")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        if not str(inputs.get("tracefile", "")).strip():
            return "tracefile is required"
        try:
            pratio = float(inputs.get("pratio", 0.33))
        except (TypeError, ValueError):
            return "pratio must be a number"
        if pratio < 0:
            return "pratio must be >= 0"
        for name, minimum in cls.INT_MIN_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name, maximum in cls.INT_MAX_OPTIONS.items():
            try:
                value = int(inputs.get(name, cls.OPTION_DEFAULTS[name]))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value > maximum:
                return f"{name} must be <= {maximum}"
        unsupported = [output for output in cls._optional_outputs(inputs) if output not in cls.OPTIONAL_OUTPUTS]
        if unsupported:
            return f"optional_outputs contains unsupported values: {', '.join(unsupported)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("FILE", {"description": "FASTA, ABI, or SCF genome/reference sequence"}),
                "tracefile": ("FILE", {"description": "Sanger chromatogram trace file in AB1 or SCF format"}),
            },
            "optional": {
                "index_genome": (
                    "BOOLEAN",
                    {"default": False, "description": "Pre-index large FASTA references with Tracy FM index"},
                ),
                "callVariants": ("BOOLEAN", {"default": False, "description": "Call variants in the chromatogram"}),
                "pratio": ("FLOAT", {"default": 0.33, "min": 0, "description": "Peak ratio threshold for calling a base"}),
                "kmer": ("INT", {"default": 15, "min": 1, "description": "K-mer size used to anchor the trace"}),
                "support": ("INT", {"default": 3, "min": 1, "description": "Minimum k-mer support"}),
                "maxindel": ("INT", {"default": 1000, "min": 1, "description": "Maximum indel size in the Sanger trace"}),
                "trim": ("INT", {"default": 0, "description": "Trimming stringency; 0 uses trimLeft and trimRight"}),
                "trimLeft": ("INT", {"default": 50, "min": 0, "description": "Fixed bases to trim from the left"}),
                "trimRight": ("INT", {"default": 50, "min": 0, "description": "Fixed bases to trim from the right"}),
                "linelimit": ("INT", {"default": 60, "min": 1, "description": "Alignment line length"}),
                "gapopen": ("INT", {"default": -10, "max": 0, "description": "Gap open penalty"}),
                "gapext": ("INT", {"default": -4, "max": 0, "description": "Gap extension penalty"}),
                "match": ("INT", {"default": 3, "min": 0, "description": "Nucleotide match score"}),
                "mismatch": ("INT", {"default": -5, "max": 0, "description": "Mismatch penalty"}),
                "optional_outputs": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OPTIONAL_OUTPUTS,
                        "description": "Optional JSON and tabular statistics outputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNJoinTablesNode(CommandNode):
    """Join HUMAnN and MetaPhlAn tables into a multi-sample table."""

    NODE_ID = "humann_join_tables"
    DISPLAY_NAME = "HUMAnN Join Tables"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Join gene, pathway, or taxonomy HUMAnN/MetaPhlAn tables into one table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_join_tables",
        "Join merge",
        "gene table",
        "pathway table",
        "taxonomy table",
        "MetaPhlAn table",
        "multi-sample table",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_join_tables"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], tables: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, table in enumerate(tables):
            label = labels[index] if index < len(labels) and labels[index] else table
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tables = _as_list(inputs.get("inputs"))
        input_names = cls._input_names(inputs, tables)
        commands = ["mkdir tmp_dir"]
        commands.extend(
            _shell_join(["ln", "-s", table, f"tmp_dir/{input_name}"])
            for table, input_name in zip(tables, input_names, strict=False)
        )
        commands.append(_shell_join(["humann_join_tables", "-i", "tmp_dir", "-o", f"{out}/joined_tables.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "joined_tables.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("inputs")):
            return "At least one HUMAnN or MetaPhlAn table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "TSV",
                    {"multiple": True, "description": "Gene, pathway, or taxonomy tables to join"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used to name joined samples",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNRenormTableNode(CommandNode):
    """Renormalize HUMAnN gene and pathway tables."""

    NODE_ID = "humann_renorm_table"
    DISPLAY_NAME = "HUMAnN Renormalize Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Renormalize HUMAnN gene or pathway tables to CPM or relative abundance units."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_renorm_table",
        "Renormalize",
        "copies per million",
        "relative abundance",
        "community total",
        "levelwise total",
        "UNMAPPED",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_renorm_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    UNITS = ["cpm", "relab"]
    MODES = ["community", "levelwise"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/renormalized_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_renorm_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
            "--units",
            str(inputs.get("units", "cpm")),
            "--mode",
            str(inputs.get("mode", "community")),
            "--special",
            "y" if inputs.get("special", True) else "n",
        ]
        if inputs.get("update_snames", True):
            cmd.append("--update-snames")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "renormalized_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN gene or pathway table is required"
        units = str(inputs.get("units", "cpm"))
        if units not in cls.UNITS:
            return f"Unsupported HUMAnN normalization units: {units}"
        mode = str(inputs.get("mode", "community"))
        if mode not in cls.MODES:
            return f"Unsupported HUMAnN normalization mode: {mode}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene or pathway table"}),
            },
            "optional": {
                "units": (
                    "STRING",
                    {
                        "default": "cpm",
                        "options": cls.UNITS,
                        "description": "Normalize to copies per million or relative abundance units",
                    },
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "community",
                        "options": cls.MODES,
                        "description": "Normalize using community totals or per-level totals",
                    },
                ),
                "special": (
                    "BOOLEAN",
                    {"default": True, "description": "Include special features such as UNMAPPED and UNINTEGRATED"},
                ),
                "update_snames": (
                    "BOOLEAN",
                    {"default": True, "description": "Update sample-name RPK suffixes to the selected units"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNSplitTableNode(CommandNode):
    """Split a merged HUMAnN table into one file per sample."""

    NODE_ID = "humann_split_table"
    DISPLAY_NAME = "HUMAnN Split Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Split a merged HUMAnN feature table into one table per sample."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_split_table",
        "Split",
        "merged table",
        "one file per sample",
        "taxonomy index",
        "PICRUSt",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("split_tables",)
    REQUIRED_EXECUTABLES = ["humann_split_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    TAXONOMY_LEVELS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split_tables"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_split_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
        ]
        taxonomy_index = inputs.get("taxonomy_index")
        if taxonomy_index is not None and str(taxonomy_index) != "":
            cmd.extend(["--taxonomy_index", str(taxonomy_index)])
        taxonomy_level = inputs.get("taxonomy_level")
        if taxonomy_level is not None and str(taxonomy_level) != "":
            cmd.extend(["--taxonomy_level", str(taxonomy_level)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "split_tables"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Merged HUMAnN table is required"
        taxonomy_level = str(inputs.get("taxonomy_level", ""))
        if taxonomy_level and taxonomy_level not in cls.TAXONOMY_LEVELS:
            return f"Unsupported HUMAnN taxonomy level: {taxonomy_level}"
        taxonomy_index = inputs.get("taxonomy_index")
        if taxonomy_index is not None and str(taxonomy_index) != "":
            try:
                parsed_index = int(taxonomy_index)
            except (TypeError, ValueError):
                return "Taxonomy index must be an integer"
            if parsed_index < 0:
                return "Taxonomy index must be zero or greater"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Merged HUMAnN gene or pathway table"}),
            },
            "optional": {
                "taxonomy_index": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Index of the gene in taxonomy data when splitting PICRUSt-style tables",
                    },
                ),
                "taxonomy_level": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TAXONOMY_LEVELS,
                        "description": "Taxonomy level to use for PICRUSt metagenome contribution output",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNSplitStratifiedTableNode(CommandNode):
    """Split a stratified HUMAnN table into stratified and unstratified files."""

    NODE_ID = "humann_split_stratified_table"
    DISPLAY_NAME = "HUMAnN Split Stratified Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Split a stratified HUMAnN table into stratified and unstratified tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_split_stratified_table",
        "Split a HUMAnN table",
        "stratified table",
        "unstratified table",
        "gene families",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("stratified", "unstratified")
    REQUIRED_EXECUTABLES = ["humann_split_stratified_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split_stratified"

    @staticmethod
    def _split_output_names(input_path: str) -> tuple[str, str]:
        name = Path(input_path).name
        for compression_suffix in (".gz", ".bz2"):
            if name.endswith(compression_suffix):
                name = name[: -len(compression_suffix)]
                break
        path = Path(name)
        extension = path.suffix or ".tsv"
        basename = path.stem if path.suffix else path.name
        if not basename:
            return ("stratified.tsv", "unstratified.tsv")
        return (f"{basename}_stratified{extension}", f"{basename}_unstratified{extension}")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                "humann_split_stratified_table",
                "--input",
                str(inputs.get("input", "")),
                "--output",
                cls._output_dir(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "split_stratified"
        out.mkdir(parents=True, exist_ok=True)
        stratified, unstratified = cls._split_output_names(str(inputs.get("input", "")))
        return [out / stratified, out / unstratified]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Stratified HUMAnN table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Stratified HUMAnN table"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNReduceTableNode(CommandNode):
    """Reduce a joined HUMAnN table with a summary function."""

    NODE_ID = "humann_reduce_table"
    DISPLAY_NAME = "HUMAnN Reduce Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Reduce a joined HUMAnN table by applying a row-wise summary function."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_reduce_table",
        "Reduce",
        "joined HUMAnN table",
        "row-wise summary",
        "max sum mean min",
        "sort by value",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_reduce_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    FUNCTIONS = ["max", "sum", "mean", "min"]
    SORT_OPTIONS = ["name", "value", "level"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/reduced_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                "humann_reduce_table",
                "--input",
                str(inputs.get("input", "")),
                "-o",
                cls._output_path(inputs),
                "--function",
                str(inputs.get("function", "max")),
                "--sort-by",
                str(inputs.get("sort_by", "name")),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "reduced_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Joined HUMAnN table is required"
        function = str(inputs.get("function", "max"))
        if function not in cls.FUNCTIONS:
            return f"Unsupported HUMAnN reduction function: {function}"
        sort_by = str(inputs.get("sort_by", "name"))
        if sort_by not in cls.SORT_OPTIONS:
            return f"Unsupported HUMAnN reduce sort option: {sort_by}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Joined HUMAnN gene, pathway, or taxonomic table"}),
            },
            "optional": {
                "function": (
                    "STRING",
                    {
                        "default": "max",
                        "options": cls.FUNCTIONS,
                        "description": "Summary function to apply across each row",
                    },
                ),
                "sort_by": (
                    "STRING",
                    {
                        "default": "name",
                        "options": cls.SORT_OPTIONS,
                        "description": "Sort reduced rows by feature name, reduced value, or pathway level",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNRegroupTableNode(CommandNode):
    """Regroup HUMAnN gene-family features into functional categories."""

    NODE_ID = "humann_regroup_table"
    DISPLAY_NAME = "HUMAnN Regroup Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Regroup HUMAnN gene-family features into functional categories."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_regroup_table",
        "Regroup",
        "gene families",
        "MetaCyc reactions",
        "UniRef90",
        "custom mapping",
        "UNGROUPED",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_regroup_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    FUNCTIONS = ["sum", "mean"]
    GROUPING_TYPES = ["standard", "large", "custom"]
    STANDARD_GROUPS = ["uniref90_rxn", "uniref50_rxn"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/regrouped_table.tsv"

    @staticmethod
    def _yn(value: Any, default: bool = True) -> str:
        if value is None:
            value = default
        if isinstance(value, str):
            return "Y" if value.upper() == "Y" or value.lower() in {"true", "1", "yes"} else "N"
        return "Y" if bool(value) else "N"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_regroup_table",
            "--input",
            str(inputs.get("input", "")),
            "--output",
            cls._output_path(inputs),
            "--function",
            str(inputs.get("function", "sum")),
        ]
        grouping_type = str(inputs.get("grouping_type", "standard"))
        if grouping_type == "standard":
            cmd.extend(["--groups", str(inputs.get("groups", "uniref90_rxn"))])
        elif grouping_type == "large":
            cmd.extend(["--custom", str(inputs.get("grouping", ""))])
            if inputs.get("reversed", False):
                cmd.append("--reversed")
        else:
            cmd.extend(["--custom", str(inputs.get("custom", ""))])
            if inputs.get("reversed", False):
                cmd.append("--reversed")
        cmd.extend(
            [
                "--precision",
                str(inputs.get("precision", 3)),
                "--ungrouped",
                cls._yn(inputs.get("ungrouped"), default=True),
                "--protected",
                cls._yn(inputs.get("protected"), default=True),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "regrouped_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN gene families table is required"
        function = str(inputs.get("function", "sum"))
        if function not in cls.FUNCTIONS:
            return f"Unsupported HUMAnN regroup function: {function}"
        grouping_type = str(inputs.get("grouping_type", "standard"))
        if grouping_type not in cls.GROUPING_TYPES:
            return f"Unsupported HUMAnN grouping type: {grouping_type}"
        if grouping_type == "standard":
            groups = str(inputs.get("groups", "uniref90_rxn"))
            if groups not in cls.STANDARD_GROUPS:
                return f"Unsupported HUMAnN built-in grouping: {groups}"
        elif grouping_type == "large" and not str(inputs.get("grouping", "")).strip():
            return "HUMAnN utility mapping file is required"
        elif grouping_type == "custom" and not str(inputs.get("custom", "")).strip():
            return "Custom HUMAnN grouping file is required"
        try:
            precision = int(inputs.get("precision", 3))
        except (TypeError, ValueError):
            return "Precision must be an integer"
        if precision < 0:
            return "Precision must be zero or greater"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene families table"}),
            },
            "optional": {
                "function": (
                    "STRING",
                    {
                        "default": "sum",
                        "options": cls.FUNCTIONS,
                        "description": "Combine grouped features by sum or mean",
                    },
                ),
                "grouping_type": (
                    "STRING",
                    {
                        "default": "standard",
                        "options": cls.GROUPING_TYPES,
                        "description": "Use built-in, installed utility mapping, or custom grouping",
                    },
                ),
                "groups": (
                    "STRING",
                    {
                        "default": "uniref90_rxn",
                        "options": cls.STANDARD_GROUPS,
                        "description": "Built-in regrouping from UniRef families to MetaCyc reactions",
                        "displayOptions": {"show": {"grouping_type": ["standard"]}},
                    },
                ),
                "grouping": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Installed HUMAnN utility mapping file for large regrouping",
                        "displayOptions": {"show": {"grouping_type": ["large"]}},
                    },
                ),
                "custom": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Custom groups mapping file",
                        "displayOptions": {"show": {"grouping_type": ["custom"]}},
                    },
                ),
                "reversed": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Treat the mapping as feature-to-groups instead of groups-to-features",
                        "displayOptions": {"show": {"grouping_type": ["large", "custom"]}},
                    },
                ),
                "precision": (
                    "INT",
                    {"default": 3, "min": 0, "description": "Decimal places to round grouped abundances"},
                ),
                "ungrouped": (
                    "BOOLEAN",
                    {"default": True, "description": "Include UNGROUPED for features that did not map to a group"},
                ),
                "protected": (
                    "BOOLEAN",
                    {"default": True, "description": "Carry through protected features such as UNMAPPED"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNRenameTableNode(CommandNode):
    """Attach readable names to HUMAnN table feature identifiers."""

    NODE_ID = "humann_rename_table"
    DISPLAY_NAME = "HUMAnN Rename Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Attach readable names to HUMAnN gene, pathway, or regrouped feature IDs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_rename_table",
        "Rename features",
        "feature names",
        "MetaCyc reactions",
        "UniRef90 name",
        "custom mapping",
        "NO_NAME",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_rename_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    RENAMING_TYPES = ["standard", "advanced", "custom"]
    STANDARD_NAMES = [
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

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/renamed_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_rename_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
        ]
        renaming_type = str(inputs.get("renaming_type", "standard"))
        if renaming_type == "standard":
            cmd.extend(["--names", str(inputs.get("names", "metacyc-rxn"))])
        elif renaming_type == "advanced":
            cmd.extend(["--custom", str(inputs.get("advanced_names", ""))])
        else:
            cmd.extend(["--custom", str(inputs.get("custom", ""))])
        if inputs.get("simplify", False):
            cmd.append("--simplify")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "renamed_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN feature table is required"
        renaming_type = str(inputs.get("renaming_type", "standard"))
        if renaming_type not in cls.RENAMING_TYPES:
            return f"Unsupported HUMAnN renaming type: {renaming_type}"
        if renaming_type == "standard":
            names = str(inputs.get("names", "metacyc-rxn"))
            if names not in cls.STANDARD_NAMES:
                return f"Unsupported HUMAnN built-in name map: {names}"
        elif renaming_type == "advanced" and not str(inputs.get("advanced_names", "")).strip():
            return "HUMAnN utility name mapping file is required"
        elif renaming_type == "custom" and not str(inputs.get("custom", "")).strip():
            return "Custom HUMAnN name mapping file is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene, pathway, or regrouped feature table"}),
            },
            "optional": {
                "renaming_type": (
                    "STRING",
                    {
                        "default": "standard",
                        "options": cls.RENAMING_TYPES,
                        "description": "Use built-in, installed utility mapping, or custom name mapping",
                    },
                ),
                "names": (
                    "STRING",
                    {
                        "default": "metacyc-rxn",
                        "options": cls.STANDARD_NAMES,
                        "description": "Built-in feature namespace to rename",
                        "displayOptions": {"show": {"renaming_type": ["standard"]}},
                    },
                ),
                "advanced_names": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Installed HUMAnN utility name mapping file",
                        "displayOptions": {"show": {"renaming_type": ["advanced"]}},
                    },
                ),
                "custom": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Custom two-column feature-to-name mapping file",
                        "displayOptions": {"show": {"renaming_type": ["custom"]}},
                    },
                ),
                "simplify": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove non-alphanumeric characters from names"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNUnpackPathwaysNode(CommandNode):
    """Unpack HUMAnN pathway abundances to include contributing genes."""

    NODE_ID = "humann_unpack_pathways"
    DISPLAY_NAME = "HUMAnN Unpack Pathways"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add gene-family or EC abundance stratification to HUMAnN pathway abundance tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_unpack_pathways",
        "Unpack pathway abundances",
        "pathway abundance",
        "gene family abundance",
        "EC abundance",
        "reaction mapping",
        "remove taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_unpack_pathways"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/unpacked_pathways.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_unpack_pathways",
            "--input-genes",
            str(inputs.get("input_genes", "")),
            "--input-pathways",
            str(inputs.get("input_pathways", "")),
        ]
        gene_mapping = str(inputs.get("gene_mapping", "")).strip()
        if gene_mapping:
            cmd.extend(["--gene-mapping", gene_mapping])
        pathway_mapping = str(inputs.get("pathway_mapping", "")).strip()
        if pathway_mapping:
            cmd.extend(["--pathway-mapping", pathway_mapping])
        if inputs.get("remove_taxonomy", False):
            cmd.append("--remove-taxonomy")
        cmd.extend(["--output", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "unpacked_pathways.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_genes", "")).strip():
            return "HUMAnN gene family or EC abundance table is required"
        if not str(inputs.get("input_pathways", "")).strip():
            return "HUMAnN pathway abundance table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genes": ("TSV", {"description": "HUMAnN gene family or EC abundance table"}),
                "input_pathways": ("TSV", {"description": "HUMAnN pathway abundance table"}),
            },
            "optional": {
                "gene_mapping": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Optional gene-family-to-reaction mapping table",
                    },
                ),
                "pathway_mapping": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Optional reaction-to-pathway mapping table",
                    },
                ),
                "remove_taxonomy": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove taxonomy stratification from unpacked pathway rows"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HUMAnNBarplotNode(CommandNode):
    """Plot one stratified HUMAnN feature across samples."""

    NODE_ID = "humann_barplot"
    DISPLAY_NAME = "HUMAnN Barplot"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Plot a single stratified HUMAnN feature across samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_barplot",
        "Barplot",
        "stratified HUMAnN features",
        "focal feature",
        "top taxa",
        "Bray-Curtis",
        "metadata sorting",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("barplot",)
    REQUIRED_EXECUTABLES = ["humann_barplot"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    SORT_OPTIONS = ["none", "sum", "dominant", "braycurtis", "braycurtis_w", "metadata"]
    SORT_ALIASES = {"brawcurtis": "braycurtis"}
    SCALING_OPTIONS = ["original", "logstack", "totalsum"]
    OUTPUT_FORMATS = ["pdf", "png", "svg"]
    INT_DEFAULTS = {
        "top_taxa": 18,
        "max_metalevels": 7,
        "legend_cols": 3,
        "legend_rows": 10,
    }
    FLOAT_DEFAULTS = {
        "height": 11.0,
        "width": 6.0,
        "legend_height": 1.0,
    }

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("format", "pdf") or "pdf").lower()
        return output_format if output_format in cls.OUTPUT_FORMATS else "pdf"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.{cls._output_format(inputs)}"

    @classmethod
    def _sort_values(cls, inputs: dict[str, Any]) -> list[str]:
        raw_sort = inputs.get("sort", ["none"])
        if raw_sort is None or raw_sort == "":
            values = ["none"]
        elif isinstance(raw_sort, (list, tuple)):
            values = [str(value) for value in raw_sort if str(value) != ""]
        else:
            values = str(raw_sort).split()
        return [cls.SORT_ALIASES.get(value, value) for value in values] or ["none"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_barplot",
            "--input",
            str(inputs.get("input", "")),
        ]
        last_metadata = str(inputs.get("last_metadata", "")).strip()
        if last_metadata:
            cmd.extend(["--last-metadata", last_metadata])
        cmd.extend(
            [
                "--focal-feature",
                str(inputs.get("focal_feature", "")),
                "--top-taxa",
                str(inputs.get("top_taxa", 18)),
            ]
        )
        if inputs.get("as_genera", False):
            cmd.append("--as-genera")
        if inputs.get("exclude_unclassified", False):
            cmd.append("--exclude-unclassified")
        if inputs.get("remove_zeros", False):
            cmd.append("--remove-zeros")
        cmd.append("--sort")
        cmd.extend(cls._sort_values(inputs))
        taxa_colormap = str(inputs.get("taxa_colormap", "")).strip()
        if taxa_colormap:
            cmd.extend(["--taxa-colormap", taxa_colormap])
        focal_metadata = str(inputs.get("focal_metadata", "")).strip()
        if focal_metadata:
            cmd.extend(["--focal-metadata", focal_metadata])
        meta_colormap = str(inputs.get("meta_colormap", "")).strip()
        if meta_colormap:
            cmd.extend(["--meta-colormap", meta_colormap])
        cmd.extend(
            [
                "--max-metalevels",
                str(inputs.get("max_metalevels", 7)),
                "--scaling",
                str(inputs.get("scaling", "original")),
            ]
        )
        ymin = inputs.get("ymin", "")
        ymax = inputs.get("ymax", "")
        if str(ymin) != "" and str(ymax) != "":
            cmd.extend(["--ylims", str(ymin), str(ymax)])
        if inputs.get("no_grid", True):
            cmd.append("--no-grid")
        cmd.extend(
            [
                "--dimensions",
                str(inputs.get("height", 11.0)),
                str(inputs.get("width", 6.0)),
            ]
        )
        units = str(inputs.get("units", "")).strip()
        if units:
            cmd.extend(["--units", units])
        cmd.extend(
            [
                "--legend-cols",
                str(inputs.get("legend_cols", 3)),
                "--legend-rows",
                str(inputs.get("legend_rows", 10)),
                "--legend-height",
                str(inputs.get("legend_height", 1.0)),
                "--output",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"output.{cls._output_format(inputs)}"]

    @staticmethod
    def _validate_nonnegative_int(value: Any, message: str) -> str | None:
        try:
            if isinstance(value, bool):
                return message
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        if str(value) != str(parsed):
            return message
        return message if parsed < 0 else None

    @staticmethod
    def _validate_positive_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed <= 0 else None

    @staticmethod
    def _validate_nonnegative_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN table is required"
        if not str(inputs.get("focal_feature", "")).strip():
            return "HUMAnN focal feature is required"
        sort_values = cls._sort_values(inputs)
        for sort_value in sort_values:
            if sort_value not in cls.SORT_OPTIONS:
                return f"Unsupported HUMAnN barplot sort method: {sort_value}"
        if any(sort_value in {"braycurtis", "braycurtis_w"} for sort_value in sort_values) and not inputs.get(
            "remove_zeros", False
        ):
            return "HUMAnN Bray-Curtis sorting requires remove_zeros"
        scaling = str(inputs.get("scaling", "original"))
        if scaling not in cls.SCALING_OPTIONS:
            return f"Unsupported HUMAnN barplot scaling: {scaling}"
        output_format = str(inputs.get("format", "pdf") or "pdf").lower()
        if output_format not in cls.OUTPUT_FORMATS:
            return f"Unsupported HUMAnN barplot output format: {output_format}"
        for key, message in (
            ("top_taxa", "Top taxa must be zero or greater"),
            ("max_metalevels", "Maximum metadata levels must be zero or greater"),
            ("legend_cols", "Legend columns must be zero or greater"),
            ("legend_rows", "Legend rows must be zero or greater"),
        ):
            error = cls._validate_nonnegative_int(inputs.get(key, cls.INT_DEFAULTS[key]), message)
            if error:
                return error
        for key, message in (
            ("height", "Plot height must be greater than zero"),
            ("width", "Plot width must be greater than zero"),
        ):
            error = cls._validate_positive_float(inputs.get(key, cls.FLOAT_DEFAULTS[key]), message)
            if error:
                return error
        error = cls._validate_nonnegative_float(
            inputs.get("legend_height", cls.FLOAT_DEFAULTS["legend_height"]),
            "Legend height must be zero or greater",
        )
        if error:
            return error
        ymin = inputs.get("ymin", "")
        ymax = inputs.get("ymax", "")
        if (str(ymin) == "") != (str(ymax) == ""):
            return "Both y-axis limits are required when setting y-axis limits"
        if str(ymin) != "" and str(ymax) != "":
            try:
                float(ymin)
                float(ymax)
            except (TypeError, ValueError):
                return "Y-axis limits must be numeric"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN table with optional metadata"}),
                "focal_feature": ("STRING", {"description": "Feature ID of interest"}),
            },
            "optional": {
                "last_metadata": (
                    "STRING",
                    {"default": "", "description": "Name of the last metadata row before feature rows"},
                ),
                "top_taxa": ("INT", {"default": 18, "min": 0, "description": "Maximum taxa to highlight"}),
                "as_genera": ("BOOLEAN", {"default": False, "description": "Collapse species to genera"}),
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude the unclassified stratum"},
                ),
                "remove_zeros": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove samples with zero sum for the focal feature"},
                ),
                "sort": (
                    "STRING",
                    {
                        "default": ["none"],
                        "multiple": True,
                        "options": cls.SORT_OPTIONS,
                        "description": "Sample sorting methods evaluated in order",
                    },
                ),
                "taxa_colormap": (
                    "STRING",
                    {"default": "", "description": "Named matplotlib colormap or taxa color mapping file"},
                ),
                "focal_metadata": (
                    "STRING",
                    {"default": "", "description": "Metadata row to highlight or group by"},
                ),
                "meta_colormap": (
                    "STRING",
                    {"default": "", "description": "Named matplotlib colormap or metadata color mapping file"},
                ),
                "max_metalevels": (
                    "INT",
                    {"default": 7, "min": 0, "description": "Metadata levels to keep before collapsing rare levels"},
                ),
                "scaling": (
                    "STRING",
                    {
                        "default": "original",
                        "options": cls.SCALING_OPTIONS,
                        "description": "Scale total bar heights while preserving taxon proportions",
                    },
                ),
                "ymin": ("FLOAT", {"default": "", "description": "Minimum y-axis limit"}),
                "ymax": ("FLOAT", {"default": "", "description": "Maximum y-axis limit"}),
                "no_grid": ("BOOLEAN", {"default": True, "description": "Hide y-axis grid lines"}),
                "height": ("FLOAT", {"default": 11.0, "min": 0, "description": "Image height in inches"}),
                "width": ("FLOAT", {"default": 6.0, "min": 0, "description": "Image width in inches"}),
                "units": ("STRING", {"default": "", "description": "Y-axis abundance units"}),
                "legend_cols": ("INT", {"default": 3, "min": 0, "description": "Legend columns"}),
                "legend_rows": ("INT", {"default": 10, "min": 0, "description": "Legend rows"}),
                "legend_height": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "description": "Legend-to-data-axis height ratio"},
                ),
                "format": (
                    "STRING",
                    {
                        "default": "pdf",
                        "options": cls.OUTPUT_FORMATS,
                        "description": "Output plot format",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HybPiperNode(CommandNode):
    """Analyze targeted sequence capture data with HybPiper."""

    NODE_ID = "hybpiper"
    DISPLAY_NAME = "HybPiper"
    REQUIRED_CONDA_PACKAGES = ["hybpiper"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Analyse targeted sequence capture data with HybPiper."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HybPiper",
        "targeted sequence capture",
        "target loci assembly",
        "check targetfile",
        "fix targetfile",
        "retrieve sequences",
        "recovery heatmap",
        "paralog warnings",
    ]
    RETURN_TYPES = (
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
    )
    RETURN_NAMES = (
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
    )
    REQUIRED_EXECUTABLES = ["hybpiper"]
    DOCUMENTATION_URL = "https://github.com/mossmatters/HybPiper"
    CITATION_DOIS = [HYBPIPER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYBPIPER_CITATION_DOI}"]
    CITATION_TEXT = HYBPIPER_CITATION_TEXT
    VERSION = "2.1.6"
    SHELL = True
    JOBS = ["check_and_fix_targetfile", "assemble", "stats"]
    STATS_TYPES = ["gene", "supercontig"]
    SEQUENCE_TYPES = ["dna", "aa", "intron", "supercontig"]

    @classmethod
    def _job(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("hybpiper_job", "assemble") or "assemble")

    @classmethod
    def _stats_types(cls, inputs: dict[str, Any]) -> list[str]:
        if "stats_type_select" not in inputs:
            return ["gene"]
        return _as_list(inputs.get("stats_type_select"))

    @classmethod
    def _sequence_types(cls, inputs: dict[str, Any]) -> list[str]:
        if "sequence_type_select" not in inputs:
            return ["dna"]
        return _as_list(inputs.get("sequence_type_select"))

    @classmethod
    def _archive_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/hybpiper_archive.tar"

    @classmethod
    def _sample_names(cls, inputs: dict[str, Any], archives: list[str]) -> list[str]:
        provided_names = _as_list(inputs.get("sample_names"))
        if len(provided_names) == len(archives):
            return provided_names
        names: list[str] = []
        for archive in archives:
            name = Path(archive).name
            for suffix in (".tar.gz", ".tgz", ".tar"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            names.append(name)
        return names

    @staticmethod
    def _sample_name_error(sample_name: str) -> str | None:
        if not sample_name or sub(r"[^A-Za-z0-9_-]", "", sample_name) != sample_name:
            return "HybPiper sample identifiers may only contain letters, numbers, underscores, and hyphens"
        return None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(["ln", "-s", str(inputs.get("targetfile_dna", "")), "./target_file.fasta"])]
        job = cls._job(inputs)

        if job == "check_and_fix_targetfile":
            commands.extend(
                [
                    _shell_join(["hybpiper", "check_targetfile", "--targetfile_dna", "target_file.fasta"]),
                    "mv fix_targetfile*.ctl hybpiper.ctl",
                    _shell_join(
                        [
                            "hybpiper",
                            "fix_targetfile",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--allow_gene_removal",
                            "hybpiper.ctl",
                        ]
                    ),
                ]
            )
            return " && ".join(commands)

        if job == "assemble":
            sample_name = str(inputs.get("sample_name", "")).strip() or "sample"
            commands.append(
                _shell_join(
                    [
                        "hybpiper",
                        "assemble",
                        "--readfiles",
                        str(inputs.get("paired_forward", "")),
                        str(inputs.get("paired_reverse", "")),
                        "--targetfile_dna",
                        "target_file.fasta",
                        "--diamond",
                        "--cpu",
                        str(inputs.get("threads", 1)),
                        "--prefix",
                        sample_name,
                    ]
                )
            )
            commands.append(
                _shell_join(["tar", "-cvf", cls._archive_path(inputs), f"--directory={sample_name}", "."])
            )
            return " && ".join(commands)

        if job == "stats":
            archives = _as_list(inputs.get("hybpiper_results"))
            sample_names = cls._sample_names(inputs, archives)
            for archive, sample_name in zip(archives, sample_names, strict=False):
                commands.append(_shell_join(["mkdir", "-p", sample_name]))
                commands.append(_shell_join(["tar", "-xf", archive, "-C", sample_name]))
                commands.append(_shell_join(["echo", sample_name]) + " >> namelist.txt")

            for stats_type in cls._stats_types(inputs):
                commands.append(
                    _shell_join(
                        [
                            "hybpiper",
                            "stats",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--stats_filename",
                            f"stats.{stats_type}",
                            "--seq_lengths_filename",
                            f"seq_lengths.{stats_type}",
                            stats_type,
                            "namelist.txt",
                        ]
                    )
                )
                if inputs.get("heatmap", False):
                    commands.append(
                        _shell_join(
                            [
                                "hybpiper",
                                "recovery_heatmap",
                                "--heatmap_filename",
                                f"heatmap.{stats_type}",
                                "--heatmap_filetype",
                                "svg",
                                f"seq_lengths.{stats_type}.tsv",
                            ]
                        )
                    )

            for sequence_type in cls._sequence_types(inputs):
                commands.append(_shell_join(["mkdir", f"fasta.{sequence_type}"]))
                commands.append(
                    _shell_join(
                        [
                            "hybpiper",
                            "retrieve_sequences",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--sample_names",
                            "namelist.txt",
                            "--fasta_dir",
                            f"fasta.{sequence_type}",
                            sequence_type,
                        ]
                    )
                )
            out = _out(inputs)
            stats_types = cls._stats_types(inputs)
            sequence_types = cls._sequence_types(inputs)
            if stats_types:
                commands.append(_shell_join(["mkdir", "-p", f"{out}/hybpiper_stats"]))
                for stats_type in stats_types:
                    commands.append(
                        _shell_join(["cp", f"stats.{stats_type}.tsv", f"{out}/hybpiper_stats/stats.{stats_type}.tsv"])
                    )
                    commands.append(
                        _shell_join(
                            [
                                "cp",
                                f"seq_lengths.{stats_type}.tsv",
                                f"{out}/hybpiper_stats/seq_lengths.{stats_type}.tsv",
                            ]
                        )
                    )
                if inputs.get("heatmap", False):
                    commands.append(_shell_join(["mkdir", "-p", f"{out}/hybpiper_heatmaps"]))
                    for stats_type in stats_types:
                        commands.append(
                            _shell_join(
                                [
                                    "cp",
                                    f"heatmap.{stats_type}.svg",
                                    f"{out}/hybpiper_heatmaps/heatmap.{stats_type}.svg",
                                ]
                            )
                        )
            sequence_outputs = {
                "dna": "dna_sequences",
                "aa": "aa_sequences",
                "intron": "intron_sequences",
                "supercontig": "supercontig_sequences",
            }
            for sequence_type in sequence_types:
                output_name = sequence_outputs.get(sequence_type)
                if output_name:
                    commands.append(_shell_join(["cp", "-r", f"fasta.{sequence_type}", f"{out}/{output_name}"]))
            return " && ".join(commands)

        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        job = cls._job(inputs)
        if job == "check_and_fix_targetfile":
            return [out / "target_file_fixed.fasta", out / "hybpiper.ctl", out / "fix_targetfile_report.tsv"]
        if job == "assemble":
            return [out / "hybpiper_archive.tar"]

        stats_types = cls._stats_types(inputs)
        sequence_types = cls._sequence_types(inputs)
        if not stats_types and not sequence_types:
            return [out / "namelist.txt"]
        outputs: list[Path] = []
        if stats_types:
            outputs.append(out / "hybpiper_stats")
            if inputs.get("heatmap", False):
                outputs.append(out / "hybpiper_heatmaps")
        sequence_outputs = {
            "dna": out / "dna_sequences",
            "aa": out / "aa_sequences",
            "intron": out / "intron_sequences",
            "supercontig": out / "supercontig_sequences",
        }
        for sequence_type in sequence_types:
            if sequence_type in sequence_outputs:
                outputs.append(sequence_outputs[sequence_type])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("targetfile_dna", "")).strip():
            return "HybPiper target FASTA is required"
        job = cls._job(inputs)
        if job not in cls.JOBS:
            return f"Unsupported HybPiper job: {job}"

        if job == "assemble":
            if not str(inputs.get("paired_forward", "")).strip() or not str(inputs.get("paired_reverse", "")).strip():
                return "HybPiper assemble requires paired forward and reverse reads"
            sample_name = str(inputs.get("sample_name", "")).strip()
            if not sample_name:
                return "HybPiper sample name is required"
            sample_error = cls._sample_name_error(sample_name)
            return sample_error or True

        if job == "stats":
            archives = _as_list(inputs.get("hybpiper_results"))
            if not archives:
                return "At least one HybPiper assemble archive is required"
            for sample_name in cls._sample_names(inputs, archives):
                sample_error = cls._sample_name_error(sample_name)
                if sample_error:
                    return sample_error
            stats_types = cls._stats_types(inputs)
            sequence_types = cls._sequence_types(inputs)
            if not stats_types and not sequence_types:
                return "At least one HybPiper statistics or sequence output must be selected"
            if inputs.get("heatmap", False) and not stats_types:
                return "HybPiper heatmap requires at least one statistics output"
            for stats_type in stats_types:
                if stats_type not in cls.STATS_TYPES:
                    return f"Unsupported HybPiper statistics output: {stats_type}"
            for sequence_type in sequence_types:
                if sequence_type not in cls.SEQUENCE_TYPES:
                    return f"Unsupported HybPiper sequence output: {sequence_type}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "targetfile_dna": ("FASTA", {"description": "Target file in FASTA format"}),
            },
            "optional": {
                "hybpiper_job": (
                    "STRING",
                    {
                        "default": "assemble",
                        "options": cls.JOBS,
                        "description": "Galaxy HybPiper run type",
                    },
                ),
                "paired_forward": (
                    "FASTQ",
                    {"default": "", "description": "Forward reads from the Galaxy paired collection"},
                ),
                "paired_reverse": (
                    "FASTQ",
                    {"default": "", "description": "Reverse reads from the Galaxy paired collection"},
                ),
                "sample_name": (
                    "STRING",
                    {"default": "", "description": "Sample identifier used as the HybPiper assembly prefix"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "description": "CPU threads for HybPiper assemble"}),
                "hybpiper_results": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Archives from HybPiper assemble runs",
                    },
                ),
                "sample_names": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Galaxy collection element identifiers for archive extraction",
                    },
                ),
                "stats_type_select": (
                    "STRING",
                    {
                        "default": ["gene"],
                        "multiple": True,
                        "options": cls.STATS_TYPES,
                        "description": "Statistics outputs to report",
                    },
                ),
                "heatmap": (
                    "BOOLEAN",
                    {"default": False, "description": "Produce SVG recovery heatmaps for selected statistics"},
                ),
                "sequence_type_select": (
                    "STRING",
                    {
                        "default": ["dna"],
                        "multiple": True,
                        "options": cls.SEQUENCE_TYPES,
                        "description": "Sequence collections to retrieve",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
