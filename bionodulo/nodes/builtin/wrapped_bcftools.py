"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: E402,F401,F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class BWANode(CommandNode):
    """Map short reads with Galaxy's BWA aln/samse/sampe wrapper."""

    NODE_ID = "bwa"
    DISPLAY_NAME = "Map with BWA"
    REQUIRED_CONDA_PACKAGES = ["bwa", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Map short reads against a reference genome with BWA aln and emit coordinate-sorted BAM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BWA",
        "bwa",
        "bwa aln",
        "bwa samse",
        "bwa sampe",
        "short read mapping",
        "BAM output",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam_output",)
    REQUIRED_EXECUTABLES = ["bwa", "samtools"]
    DOCUMENTATION_URL = "https://bio-bwa.sourceforge.net/bwa.shtml"
    CITATION_DOIS = BWA_CITATION_DOIS
    CITATION_URLS = BWA_CITATION_URLS
    CITATION_TEXT = BWA_CITATION_TEXT
    VERSION = "0.7.19+galaxy1"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]
    INDEX_ALGORITHM_OPTIONS = ["auto", "is", "bwtsw"]
    INPUT_TYPE_OPTIONS = ["paired", "paired_collection", "single", "paired_bam", "single_bam"]
    ANALYSIS_TYPE_OPTIONS = ["illumina", "full"]
    FULL_INT_MIN_KEYS = {
        "o": 1,
        "e": -1,
        "i": 0,
        "d": 0,
        "l": 1,
        "k": 0,
        "m": 1,
        "M": 0,
        "O": 0,
        "E": 0,
        "R": 0,
        "q": 0,
        "B": 0,
    }
    PE_INT_MIN_KEYS = {"a": 1, "pe_o": 1, "pe_n": 0, "N": 0}
    SE_INT_MIN_KEYS = {"se_n": 0}

    @classmethod
    def _out_bam(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/aligned.bam"

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", inputs.get("reference_source", "history")) or "history")

    @classmethod
    def _ref_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_file", inputs.get("reference", "")) or "")

    @classmethod
    def _reference_prelude_and_filename(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        ref_file = cls._ref_file(inputs)
        if cls._reference_source(inputs) == "cached":
            return [], ref_file
        prelude = ["ln", "-s", ref_file, "localref.fa", "&&", "bwa", "index"]
        index_a = str(inputs.get("index_a", "auto") or "auto")
        if index_a != "auto":
            prelude.extend(["-a", index_a])
        prelude.extend(["localref.fa", "&&"])
        return prelude, "localref.fa"

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type_selector", inputs.get("input_type", "single")) or "single")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("fastq_input1", inputs.get("reads_collection", inputs.get("reads", "")))
        if isinstance(collection, dict):
            return str(collection.get("forward", "")), str(collection.get("reverse", ""))
        reads = _as_list(collection)
        return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")

    @classmethod
    def _fastq_reads(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired_collection":
            forward, reverse = cls._paired_collection_reads(inputs)
            return [forward, reverse]
        if input_type == "paired":
            return [str(inputs.get("fastq_input1", "") or ""), str(inputs.get("fastq_input2", "") or "")]
        return [str(inputs.get("fastq_input1", inputs.get("read1", "")) or "")]

    @classmethod
    def _bam_input(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("bam_input", inputs.get("input_bam", "")) or "")

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("analysis_type_selector", "illumina") or "illumina")

    @classmethod
    def _add_full_aln_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._analysis_type(inputs) != "full":
            return
        for flag, key, default in (
            ("-n", "n", "0.04"),
            ("-o", "o", 1),
            ("-e", "e", -1),
            ("-i", "i", 5),
            ("-d", "d", 10),
            ("-l", "l", 32),
            ("-k", "k", 2),
            ("-m", "m", 2000000),
            ("-M", "M", 3),
            ("-O", "O", 11),
            ("-E", "E", 4),
            ("-R", "R", 30),
            ("-q", "q", 0),
        ):
            cmd.extend([flag, str(inputs.get(key, default))])
        _add_if_value(cmd, "-B", inputs.get("B"))
        _add_if_value(cmd, "-L", inputs.get("L"))

    @classmethod
    def _aln_command(
        cls,
        reference: str,
        read: str,
        inputs: dict[str, Any],
        *,
        bam_flag: str | None = None,
        output_sai: str,
    ) -> list[str]:
        cmd = ["bwa", "aln", "-t", "${GALAXY_SLOTS:-1}"]
        if bam_flag:
            cmd.extend(["-b", bam_flag])
        cls._add_full_aln_options(cmd, inputs)
        cmd.extend([reference, read, ">", output_sai])
        return cmd

    @classmethod
    def _read_group_string(cls, inputs: dict[str, Any]) -> str:
        rg_id = str(inputs.get("rg_id", inputs.get("ID", "")) or "")
        tags = [
            ("SM", inputs.get("rg_sm", inputs.get("SM", ""))),
            ("PL", inputs.get("rg_pl", inputs.get("PL", ""))),
            ("LB", inputs.get("rg_lb", inputs.get("LB", ""))),
            ("CN", inputs.get("rg_cn", inputs.get("CN", ""))),
            ("DS", inputs.get("rg_ds", inputs.get("DS", ""))),
            ("DT", inputs.get("rg_dt", inputs.get("DT", ""))),
            ("FO", inputs.get("rg_fo", inputs.get("FO", ""))),
            ("KS", inputs.get("rg_ks", inputs.get("KS", ""))),
            ("PG", inputs.get("rg_pg", inputs.get("PG", ""))),
            ("PI", inputs.get("rg_pi", inputs.get("PI", ""))),
            ("PU", inputs.get("rg_pu", inputs.get("PU", ""))),
        ]
        if not rg_id:
            if cls._input_type(inputs) in {"paired_bam", "single_bam"}:
                seed = cls._bam_input(inputs)
            else:
                seed = cls._fastq_reads(inputs)[0]
            rg_id = _safe_name(seed) if seed else "read_group"
        parts = [f"@RG\\tID:{rg_id}"]
        for tag, value in tags:
            if value is not None and str(value) != "":
                parts.append(f"{tag}:{value}")
        return "\\t".join(parts)

    @classmethod
    def _add_read_group(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("rg_selector", "do_not_set") or "do_not_set") == "do_not_set":
            return
        cmd.extend(["-r", cls._read_group_string(inputs)])

    @classmethod
    def _add_pe_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("adv_pe_options_selector", "do_not_set") or "do_not_set") != "set":
            return
        for flag, key, default in (
            ("-a", "a", 500),
            ("-o", "pe_o", 100000),
            ("-n", "pe_n", 3),
            ("-N", "N", 10),
            ("-c", "c", 0.00005),
        ):
            cmd.extend([flag, str(inputs.get(key, default))])

    @classmethod
    def _add_se_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("adv_se_options_selector", "do_not_set") or "do_not_set") != "set":
            return
        cmd.extend(["-n", str(inputs.get("se_n", inputs.get("samse_n", 3)))])

    @classmethod
    def _add_sort(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "|",
                "samtools",
                "sort",
                "-@${GALAXY_SLOTS:-2}",
                "-T",
                "${TMPDIR:-.}",
                "-O",
                "bam",
                "-o",
                cls._out_bam(inputs),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prelude, reference = cls._reference_prelude_and_filename(inputs)
        input_type = cls._input_type(inputs)
        cmd = ["set", "-o", "pipefail", "&&"]
        cmd.extend(prelude)
        if input_type in {"paired", "paired_collection"}:
            read1, read2 = cls._fastq_reads(inputs)
            cmd.extend(cls._aln_command(reference, read1, inputs, output_sai="first.sai"))
            cmd.append("&&")
            cmd.extend(cls._aln_command(reference, read2, inputs, output_sai="second.sai"))
            cmd.append("&&")
            sam_cmd = ["bwa", "sampe"]
            cls._add_pe_options(sam_cmd, inputs)
            cls._add_read_group(sam_cmd, inputs)
            sam_cmd.extend([reference, "first.sai", "second.sai", read1, read2])
        elif input_type == "single":
            read1 = cls._fastq_reads(inputs)[0]
            cmd.extend(cls._aln_command(reference, read1, inputs, output_sai="first.sai"))
            cmd.append("&&")
            sam_cmd = ["bwa", "samse"]
            cls._add_se_options(sam_cmd, inputs)
            cls._add_read_group(sam_cmd, inputs)
            sam_cmd.extend([reference, "first.sai", read1])
        elif input_type == "paired_bam":
            bam = cls._bam_input(inputs)
            cmd.extend(cls._aln_command(reference, bam, inputs, bam_flag="-1", output_sai="first.sai"))
            cmd.append("&&")
            cmd.extend(cls._aln_command(reference, bam, inputs, bam_flag="-2", output_sai="second.sai"))
            cmd.append("&&")
            sam_cmd = ["bwa", "sampe"]
            cls._add_pe_options(sam_cmd, inputs)
            cls._add_read_group(sam_cmd, inputs)
            sam_cmd.extend([reference, "first.sai", "second.sai", bam, bam])
        else:
            bam = cls._bam_input(inputs)
            cmd.extend(cls._aln_command(reference, bam, inputs, bam_flag="-0", output_sai="first.sai"))
            cmd.append("&&")
            sam_cmd = ["bwa", "samse"]
            cls._add_se_options(sam_cmd, inputs)
            cls._add_read_group(sam_cmd, inputs)
            sam_cmd.extend([reference, "first.sai", bam])
        cls._add_sort(sam_cmd, inputs)
        cmd.extend(sam_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "aligned.bam"]

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ""}:
            return True
        try:
            value = int(inputs[key])
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be at least {minimum}"
        return True

    @classmethod
    def _validate_float(cls, inputs: dict[str, Any], key: str) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ""}:
            return True
        try:
            float(inputs[key])
        except (TypeError, ValueError):
            return f"{key} must be a number"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._ref_file(inputs).strip():
            return "ref_file is required"
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPE_OPTIONS:
            return f"input_type_selector must be one of: {', '.join(cls.INPUT_TYPE_OPTIONS)}"
        if input_type in {"paired_bam", "single_bam"}:
            if not cls._bam_input(inputs).strip():
                return "bam_input is required for BAM input"
        else:
            reads = cls._fastq_reads(inputs)
            if not reads or not reads[0].strip():
                return "fastq_input1 is required"
            if input_type in {"paired", "paired_collection"} and (len(reads) < 2 or not reads[1].strip()):
                return "fastq_input2 is required for paired input"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        index_a = str(inputs.get("index_a", "auto") or "auto")
        if index_a not in cls.INDEX_ALGORITHM_OPTIONS:
            return f"index_a must be one of: {', '.join(cls.INDEX_ALGORITHM_OPTIONS)}"
        analysis_type = cls._analysis_type(inputs)
        if analysis_type not in cls.ANALYSIS_TYPE_OPTIONS:
            return f"analysis_type_selector must be one of: {', '.join(cls.ANALYSIS_TYPE_OPTIONS)}"
        if analysis_type == "full":
            for key, minimum in cls.FULL_INT_MIN_KEYS.items():
                validation = cls._validate_int_min(inputs, key, minimum)
                if validation is not True:
                    return validation
            for key in {"n", "L"}:
                validation = cls._validate_float(inputs, key)
                if validation is not True:
                    return validation
        if input_type in {"paired", "paired_collection", "paired_bam"} and inputs.get("adv_pe_options_selector") == "set":
            for key, minimum in cls.PE_INT_MIN_KEYS.items():
                validation = cls._validate_int_min(inputs, key, minimum)
                if validation is not True:
                    return validation
            validation = cls._validate_float(inputs, "c")
            if validation is not True:
                return validation
        if input_type in {"single", "single_bam"} and inputs.get("adv_se_options_selector") == "set":
            validation = cls._validate_int_min(inputs, "se_n", 0)
            if validation is not True:
                return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": ("FASTA", {"description": "Reference FASTA from history or built-in BWA index prefix"}),
                "input_type_selector": (
                    "STRING",
                    {"default": "paired", "options": cls.INPUT_TYPE_OPTIONS, "description": "Galaxy BWA input layout"},
                ),
                "fastq_input1": ("FASTQ", {"description": "Single, forward, or paired collection FASTQ/FASTA reads"}),
            },
            "optional": {
                "fastq_input2": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Reverse FASTQ/FASTA reads for paired input",
                        "displayOptions": {"show": {"input_type_selector": ["paired"]}},
                    },
                ),
                "bam_input": (
                    "BAM",
                    {
                        "default": "",
                        "description": "Unaligned BAM dataset for paired_bam or single_bam input",
                        "displayOptions": {"show": {"input_type_selector": ["paired_bam", "single_bam"]}},
                    },
                ),
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a built-in index or index a history FASTA before mapping",
                    },
                ),
                "index_a": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": cls.INDEX_ALGORITHM_OPTIONS,
                        "description": "BWA index algorithm used for history FASTA references",
                    },
                ),
                "analysis_type_selector": (
                    "STRING",
                    {"default": "illumina", "options": cls.ANALYSIS_TYPE_OPTIONS, "description": "Simple Illumina or full BWA aln options"},
                ),
                "n": ("FLOAT", {"default": 0.04, "advanced": True, "description": "Maximum edit distance"}),
                "o": ("INT", {"default": 1, "min": 1, "advanced": True, "description": "Maximum gap openings"}),
                "e": ("INT", {"default": -1, "advanced": True, "description": "Maximum gap extensions"}),
                "i": ("INT", {"default": 5, "min": 0, "advanced": True, "description": "Indel end exclusion distance"}),
                "d": ("INT", {"default": 10, "min": 0, "advanced": True, "description": "Maximum occurrences for long deletion extension"}),
                "l": ("INT", {"default": 32, "min": 1, "advanced": True, "description": "Seed length"}),
                "k": ("INT", {"default": 2, "min": 0, "advanced": True, "description": "Maximum seed differences"}),
                "m": ("INT", {"default": 2000000, "min": 1, "advanced": True, "description": "Maximum queue entries"}),
                "M": ("INT", {"default": 3, "min": 0, "advanced": True, "description": "Mismatch penalty"}),
                "O": ("INT", {"default": 11, "min": 0, "advanced": True, "description": "Gap open penalty"}),
                "E": ("INT", {"default": 4, "min": 0, "advanced": True, "description": "Gap extension penalty"}),
                "R": ("INT", {"default": 30, "min": 0, "advanced": True, "description": "Stop equally best hit search threshold"}),
                "q": ("INT", {"default": 0, "min": 0, "advanced": True, "description": "Read trimming quality threshold"}),
                "B": ("INT", {"default": "", "min": 0, "advanced": True, "description": "Barcode length"}),
                "L": ("FLOAT", {"default": "", "advanced": True, "description": "Long deletion gap penalty"}),
                "adv_pe_options_selector": (
                    "STRING",
                    {"default": "do_not_set", "options": ["do_not_set", "set"], "advanced": True},
                ),
                "a": ("INT", {"default": 500, "min": 1, "advanced": True, "description": "Maximum insert size"}),
                "pe_o": ("INT", {"default": 100000, "min": 1, "advanced": True, "description": "Maximum occurrences for pairing"}),
                "pe_n": ("INT", {"default": 3, "min": 0, "advanced": True, "description": "XA alignments for proper pairs"}),
                "N": ("INT", {"default": 10, "min": 0, "advanced": True, "description": "XA alignments for discordant pairs"}),
                "c": ("FLOAT", {"default": 0.00005, "advanced": True, "description": "Prior of chimeric rate"}),
                "adv_se_options_selector": (
                    "STRING",
                    {"default": "do_not_set", "options": ["do_not_set", "set"], "advanced": True},
                ),
                "se_n": ("INT", {"default": 3, "min": 0, "advanced": True, "description": "Maximum XA alignments for single-end reads"}),
                "rg_selector": (
                    "STRING",
                    {"default": "do_not_set", "options": ["do_not_set", "set"], "description": "Set read group information"},
                ),
                "rg_id": ("STRING", {"default": "", "description": "Read group ID"}),
                "rg_sm": ("STRING", {"default": "", "description": "Read group sample"}),
                "rg_pl": ("STRING", {"default": "", "description": "Read group platform"}),
                "rg_lb": ("STRING", {"default": "", "description": "Read group library"}),
                "rg_cn": ("STRING", {"default": "", "description": "Read group sequencing center"}),
                "rg_ds": ("STRING", {"default": "", "description": "Read group description", "advanced": True}),
                "rg_dt": ("STRING", {"default": "", "description": "Read group date", "advanced": True}),
                "rg_fo": ("STRING", {"default": "", "description": "Read group flow order", "advanced": True}),
                "rg_ks": ("STRING", {"default": "", "description": "Read group key sequence", "advanced": True}),
                "rg_pg": ("STRING", {"default": "", "description": "Read group program", "advanced": True}),
                "rg_pi": ("STRING", {"default": "", "description": "Read group predicted insert size", "advanced": True}),
                "rg_pu": ("STRING", {"default": "", "description": "Read group platform unit", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Bowtie2Node(CommandNode):
    """Map reads with Galaxy's Bowtie2 wrapper and emit BAM/SAM alignments."""

    NODE_ID = "bowtie2"
    DISPLAY_NAME = "Bowtie2"
    REQUIRED_CONDA_PACKAGES = ["bowtie2", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Map reads against a reference genome with Bowtie2 and emit BAM or SAM alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bowtie2",
        "bowtie2",
        "bowtie2-build",
        "read mapping",
        "paired-end alignment",
        "BAM output",
        "SAM output",
    ]
    RETURN_TYPES = ("BAM", "TXT", "FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = (
        "alignments",
        "mapping_stats",
        "unaligned_reads",
        "aligned_reads",
        "unaligned_read_pairs",
        "aligned_read_pairs",
    )
    REQUIRED_EXECUTABLES = ["bowtie2", "bowtie2-build", "samtools"]
    DOCUMENTATION_URL = "https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml"
    CITATION_DOIS = [BOWTIE2_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BOWTIE2_CITATION_DOI}"]
    CITATION_TEXT = BOWTIE2_CITATION_TEXT
    VERSION = "2.5.5+galaxy0"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["indexed", "history"]
    LIBRARY_TYPE_OPTIONS = ["single", "paired_collection"]
    ANALYSIS_TYPE_OPTIONS = ["simple", "full"]
    PRESET_OPTIONS = [
        "no_presets",
        "--very-fast",
        "--fast",
        "--sensitive",
        "--very-sensitive",
        "--very-fast-local",
        "--fast-local",
        "--sensitive-local",
        "--very-sensitive-local",
    ]
    SAM_OUTPUT_FORMAT_OPTIONS = ["bam", "sam", "qname_input_sorted_bam"]
    READS_FORMAT_OPTIONS = ["fastq", "fasta"]
    READS_COMPRESSION_OPTIONS = ["", "gz", "bz2"]
    PAIRED_ORIENTATION_OPTIONS = ["--fr", "--rf", "--ff"]
    QV_ENCODING_OPTIONS = ["--phred33", "--phred64"]
    REPORTING_OPTIONS = ["no", "k", "a"]

    INT_MIN_KEYS = {
        "I": 0,
        "X": 0,
        "skip": 0,
        "qupto": 1,
        "trim5": 0,
        "trim3": 0,
        "N": 0,
        "seed_L": 0,
        "dpad": 0,
        "gbar": 0,
        "ma": 0,
        "np": 0,
        "rdg_read_open": 0,
        "rdg_read_extend": 0,
        "rfg_ref_open": 0,
        "rfg_ref_extend": 0,
        "k": 1,
        "D": 0,
        "R": 0,
        "seed": 0,
    }

    @classmethod
    def _out_alignments(cls, inputs: dict[str, Any]) -> str:
        suffix = "sam" if cls._sam_output_format(inputs) == "sam" else "bam"
        return f"{_out(inputs)}/alignments.{suffix}"

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", inputs.get("reference_source", "indexed")) or "indexed")

    @classmethod
    def _ref_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_file", inputs.get("reference", "")) or "")

    @classmethod
    def _reference_prelude_and_index(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        ref_file = cls._ref_file(inputs)
        if cls._reference_source(inputs) == "history":
            return ["bowtie2-build", "--threads", "${GALAXY_SLOTS:-4}", ref_file, "genome", "&&"], "genome"
        return [], ref_file

    @classmethod
    def _library_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("library_type", inputs.get("type", "single")) or "single")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        reads_value = inputs.get("input_1", inputs.get("reads", inputs.get("reads_collection", "")))
        if isinstance(reads_value, dict):
            return str(reads_value.get("forward", "")), str(reads_value.get("reverse", ""))
        reads = _as_list(reads_value)
        return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")

    @classmethod
    def _single_read(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_1", inputs.get("read1", "")) or "")

    @classmethod
    def _reads_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reads_format", "fastq") or "fastq")

    @classmethod
    def _reads_compression(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("reads_compression", "") or "")
        if explicit:
            return explicit
        reads = [cls._single_read(inputs)] if cls._library_type(inputs) == "single" else list(cls._paired_collection_reads(inputs))
        lowered = " ".join(reads).lower()
        if ".gz" in lowered:
            return "gz"
        if ".bz2" in lowered:
            return "bz2"
        return ""

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("analysis_type_selector", "simple") or "simple")

    @classmethod
    def _sam_output_format(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("sam_options_selector", "no") or "no") != "yes":
            return "bam"
        if inputs.get("reorder") is True or inputs.get("reorder") == "--reorder":
            return "qname_input_sorted_bam"
        if inputs.get("sam_opt") is True or str(inputs.get("sam_opt", "")).lower() == "true":
            return "sam"
        return str(inputs.get("sam_output_format", "bam") or "bam")

    @classmethod
    def _flag_path(cls, inputs: dict[str, Any], stem: str, *, paired: bool) -> str:
        if paired:
            return f"{_out(inputs)}/{stem}"
        suffix = "fasta" if cls._reads_format(inputs) == "fasta" else "fastq"
        return f"{_out(inputs)}/{stem}.{suffix}"

    @classmethod
    def _read_pair_output_paths(cls, inputs: dict[str, Any], stem: str) -> list[Path]:
        suffix = "fasta" if cls._reads_format(inputs) == "fasta" else "fastq"
        return [Path(f"{stem}.1.{suffix}"), Path(f"{stem}.2.{suffix}")]

    @classmethod
    def _add_read_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._reads_format(inputs) == "fasta":
            cmd.append("-f")
        if cls._library_type(inputs) == "single":
            cmd.extend(["-U", cls._single_read(inputs)])
            compression = cls._reads_compression(inputs)
            if inputs.get("unaligned_file"):
                cmd.extend([{"gz": "--un-gz", "bz2": "--un-bz2"}.get(compression, "--un"), cls._flag_path(inputs, "unaligned_reads", paired=False)])
            if inputs.get("aligned_file"):
                cmd.extend([{"gz": "--al-gz", "bz2": "--al-bz2"}.get(compression, "--al"), cls._flag_path(inputs, "aligned_reads", paired=False)])
            return

        read1, read2 = cls._paired_collection_reads(inputs)
        cmd.extend(["-1", read1, "-2", read2])
        compression = cls._reads_compression(inputs)
        if inputs.get("unaligned_file"):
            cmd.extend([{"gz": "--un-conc-gz", "bz2": "--un-conc-bz2"}.get(compression, "--un-conc"), cls._flag_path(inputs, "unaligned_reads", paired=True)])
        if inputs.get("aligned_file"):
            cmd.extend([{"gz": "--al-conc-gz", "bz2": "--al-conc-bz2"}.get(compression, "--al-conc"), cls._flag_path(inputs, "aligned_reads", paired=True)])
        if str(inputs.get("paired_options_selector", "no") or "no") == "yes":
            for flag, key, default in (("-I", "I", 0), ("-X", "X", 500)):
                cmd.extend([flag, str(inputs.get(key, default))])
            cmd.append(str(inputs.get("fr_rf_ff", "--fr") or "--fr"))
            for key, flag in (
                ("no_mixed", "--no-mixed"),
                ("no_discordant", "--no-discordant"),
                ("dovetail", "--dovetail"),
                ("no_contain", "--no-contain"),
                ("no_overlap", "--no-overlap"),
            ):
                if inputs.get(key):
                    cmd.append(flag)

    @classmethod
    def _add_read_group(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("rg_selector", "do_not_set") or "do_not_set") == "do_not_set":
            return
        rg_id = str(inputs.get("rg_id", inputs.get("ID", "")) or "")
        if not rg_id:
            seed = cls._single_read(inputs) if cls._library_type(inputs) == "single" else cls._paired_collection_reads(inputs)[0]
            rg_id = _safe_name(seed) if seed else "read_group"
        cmd.extend(["--rg-id", rg_id])
        for tag, key in (
            ("SM", "rg_sm"),
            ("PL", "rg_pl"),
            ("LB", "rg_lb"),
            ("CN", "rg_cn"),
            ("DS", "rg_ds"),
            ("DT", "rg_dt"),
            ("FO", "rg_fo"),
            ("KS", "rg_ks"),
            ("PG", "rg_pg"),
            ("PI", "rg_pi"),
            ("PU", "rg_pu"),
        ):
            value = inputs.get(key, inputs.get(tag, ""))
            if value is not None and str(value) != "":
                cmd.extend(["--rg", f"{tag}:{value}"])

    @classmethod
    def _add_full_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._analysis_type(inputs) == "simple":
            preset = str(inputs.get("preset", "no_presets") or "no_presets")
            if preset != "no_presets":
                cmd.append(preset)
            return
        if str(inputs.get("input_options_selector", "no") or "no") == "yes":
            for flag, key, default in (
                ("--skip", "skip", 0),
                ("--qupto", "qupto", 100000000),
                ("--trim5", "trim5", 0),
                ("--trim3", "trim3", 0),
            ):
                cmd.extend([flag, str(inputs.get(key, default))])
            cmd.append(str(inputs.get("qv_encoding", "--phred33") or "--phred33"))
            for key, flag in (("solexa_quals", "--solexa-quals"), ("int_quals", "--int-quals")):
                if inputs.get(key):
                    cmd.append(flag)
        if str(inputs.get("alignment_options_selector", "no") or "no") == "yes":
            for flag, key, default in (
                ("-N", "N", 0),
                ("-L", "seed_L", 22),
                ("-i", "i", "S,1,1.15"),
                ("--n-ceil", "n_ceil", "L,0,0.15"),
                ("--dpad", "dpad", 15),
                ("--gbar", "gbar", 4),
            ):
                cmd.extend([flag, str(inputs.get(key, default))])
            for key, flag in (
                ("ignore_quals", "--ignore-quals"),
                ("nofw", "--nofw"),
                ("norc", "--norc"),
                ("no_1mm_upfront", "--no-1mm-upfront"),
            ):
                if inputs.get(key):
                    cmd.append(flag)
            align_mode = str(inputs.get("align_mode_selector", "end-to-end") or "end-to-end")
            if align_mode == "local":
                cmd.extend(["--local", "--score-min", str(inputs.get("score_min_loc", "G,20,8"))])
            else:
                cmd.extend(["--end-to-end", "--score-min", str(inputs.get("score_min_ete", "L,-0.6,-0.6"))])
        if str(inputs.get("scoring_options_selector", "no") or "no") == "yes":
            if str(inputs.get("align_mode_selector", "end-to-end") or "end-to-end") == "local":
                cmd.extend(["--ma", str(inputs.get("ma", 2))])
            cmd.extend(
                [
                    "--mp",
                    str(inputs.get("mp", "6,2")),
                    "--np",
                    str(inputs.get("np", 1)),
                    "--rdg",
                    f"{inputs.get('rdg_read_open', 5)},{inputs.get('rdg_read_extend', 3)}",
                    "--rfg",
                    f"{inputs.get('rfg_ref_open', 5)},{inputs.get('rfg_ref_extend', 3)}",
                ]
            )
        reporting = str(inputs.get("reporting_options_selector", "no") or "no")
        if reporting == "k":
            cmd.extend(["-k", str(inputs.get("k", 1))])
        elif reporting == "a":
            cmd.append("-a")
        if str(inputs.get("effort_options_selector", "no") or "no") == "yes":
            cmd.extend(["-D", str(inputs.get("D", 15)), "-R", str(inputs.get("R", 2))])
            if inputs.get("d"):
                cmd.append("-d")
        if str(inputs.get("other_options_selector", "no") or "no") == "yes":
            if inputs.get("non_deterministic"):
                cmd.append("--non-deterministic")
            cmd.extend(["--seed", str(inputs.get("seed", 0))])

    @classmethod
    def _add_sam_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("sam_options_selector", "no") or "no") != "yes":
            return
        for key, flag in (
            ("no_unal", "--no-unal"),
            ("omit_sec_seq", "--omit-sec-seq"),
            ("sam_no_qname_trunc", "--sam-no-qname-trunc"),
            ("xeq", "--xeq"),
            ("soft_clipped_unmapped_tlen", "--soft-clipped-unmapped-tlen"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        if cls._sam_output_format(inputs) == "qname_input_sorted_bam":
            cmd.append("--reorder")

    @classmethod
    def _add_output(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("save_mapping_stats"):
            cmd.extend(["2>", f"{_out(inputs)}/mapping_stats.txt"])
        output_format = cls._sam_output_format(inputs)
        if output_format == "sam":
            cmd.extend([">", cls._out_alignments(inputs)])
        elif output_format == "qname_input_sorted_bam":
            cmd.extend(["|", "samtools", "view", "--no-PG", "-b", "-o", cls._out_alignments(inputs)])
        else:
            cmd.extend(
                [
                    "|",
                    "samtools",
                    "sort",
                    "-l",
                    "0",
                    "-T",
                    "${TMPDIR:-.}",
                    "-O",
                    "bam",
                    "|",
                    "samtools",
                    "view",
                    "--no-PG",
                    "-O",
                    "bam",
                    "-@",
                    "${GALAXY_SLOTS:-1}",
                    "-o",
                    cls._out_alignments(inputs),
                ]
            )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prelude, index_path = cls._reference_prelude_and_index(inputs)
        cmd = ["set", "-o", "pipefail", "&&"]
        cmd.extend(prelude)
        bowtie_cmd = ["bowtie2", "-p", "${GALAXY_SLOTS:-1}", "-x", index_path]
        cls._add_read_inputs(bowtie_cmd, inputs)
        cls._add_read_group(bowtie_cmd, inputs)
        cls._add_full_options(bowtie_cmd, inputs)
        cls._add_sam_options(bowtie_cmd, inputs)
        cls._add_output(bowtie_cmd, inputs)
        cmd.extend(bowtie_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / Path(cls._out_alignments({"output": str(out), **inputs})).name]
        if inputs.get("save_mapping_stats"):
            outputs.append(out / "mapping_stats.txt")
        if cls._library_type(inputs) == "single":
            if inputs.get("unaligned_file"):
                outputs.append(out / cls._read_pair_output_paths({"reads_format": cls._reads_format(inputs)}, "unaligned_reads")[0].name.replace(".1.", "."))
            if inputs.get("aligned_file"):
                outputs.append(out / cls._read_pair_output_paths({"reads_format": cls._reads_format(inputs)}, "aligned_reads")[0].name.replace(".1.", "."))
            return outputs
        if inputs.get("unaligned_file"):
            outputs.extend(out / path for path in cls._read_pair_output_paths(inputs, "unaligned_reads"))
        if inputs.get("aligned_file"):
            outputs.extend(out / path for path in cls._read_pair_output_paths(inputs, "aligned_reads"))
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ""}:
            return True
        try:
            value = int(inputs[key])
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be at least {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._ref_file(inputs).strip():
            return "ref_file is required"
        if cls._library_type(inputs) not in cls.LIBRARY_TYPE_OPTIONS:
            return f"library_type must be one of: {', '.join(cls.LIBRARY_TYPE_OPTIONS)}"
        reads = [cls._single_read(inputs)] if cls._library_type(inputs) == "single" else list(cls._paired_collection_reads(inputs))
        if not reads or not reads[0].strip():
            return "input_1 is required"
        if cls._library_type(inputs) == "paired_collection" and (len(reads) < 2 or not reads[1].strip()):
            return "paired collection requires forward and reverse reads"
        if cls._reference_source(inputs) not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if cls._analysis_type(inputs) not in cls.ANALYSIS_TYPE_OPTIONS:
            return f"analysis_type_selector must be one of: {', '.join(cls.ANALYSIS_TYPE_OPTIONS)}"
        preset = str(inputs.get("preset", "no_presets") or "no_presets")
        if preset not in cls.PRESET_OPTIONS:
            return f"preset must be one of: {', '.join(cls.PRESET_OPTIONS)}"
        if "sam_output_format" in inputs and inputs.get("sam_output_format") not in {None, ""}:
            requested_output_format = str(inputs.get("sam_output_format") or "")
            if requested_output_format not in cls.SAM_OUTPUT_FORMAT_OPTIONS:
                return f"sam_output_format must be one of: {', '.join(cls.SAM_OUTPUT_FORMAT_OPTIONS)}"
        if cls._sam_output_format(inputs) not in cls.SAM_OUTPUT_FORMAT_OPTIONS:
            return f"sam_output_format must be one of: {', '.join(cls.SAM_OUTPUT_FORMAT_OPTIONS)}"
        if cls._reads_format(inputs) not in cls.READS_FORMAT_OPTIONS:
            return f"reads_format must be one of: {', '.join(cls.READS_FORMAT_OPTIONS)}"
        if cls._reads_compression(inputs) not in cls.READS_COMPRESSION_OPTIONS:
            return f"reads_compression must be one of: {', '.join(cls.READS_COMPRESSION_OPTIONS)}"
        if str(inputs.get("fr_rf_ff", "--fr") or "--fr") not in cls.PAIRED_ORIENTATION_OPTIONS:
            return f"fr_rf_ff must be one of: {', '.join(cls.PAIRED_ORIENTATION_OPTIONS)}"
        if str(inputs.get("qv_encoding", "--phred33") or "--phred33") not in cls.QV_ENCODING_OPTIONS:
            return f"qv_encoding must be one of: {', '.join(cls.QV_ENCODING_OPTIONS)}"
        if str(inputs.get("reporting_options_selector", "no") or "no") not in cls.REPORTING_OPTIONS:
            return f"reporting_options_selector must be one of: {', '.join(cls.REPORTING_OPTIONS)}"
        for key, minimum in cls.INT_MIN_KEYS.items():
            validation = cls._validate_int_min(inputs, key, minimum)
            if validation is not True:
                return validation
        if "N" in inputs and inputs.get("N") not in {None, ""} and int(inputs["N"]) > 1:
            return "N must be at most 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": ("BOWTIE2_INDEX", {"description": "Bowtie2 index prefix, or a FASTA when reference_source_selector is history"}),
                "library_type": (
                    "STRING",
                    {"default": "single", "options": cls.LIBRARY_TYPE_OPTIONS, "description": "Single-end or paired collection input"},
                ),
                "input_1": ("FASTQ", {"description": "Single reads, or a paired collection/dict with forward and reverse reads"}),
            },
            "optional": {
                "reference_source_selector": (
                    "STRING",
                    {"default": "indexed", "options": cls.REFERENCE_SOURCE_OPTIONS, "description": "Use a built-in index or build from history FASTA"},
                ),
                "reads_format": (
                    "STRING",
                    {"default": "fastq", "options": cls.READS_FORMAT_OPTIONS, "description": "Treat reads as FASTQ or FASTA"},
                ),
                "reads_compression": (
                    "STRING",
                    {"default": "", "options": cls.READS_COMPRESSION_OPTIONS, "description": "Compression mode for aligned/unaligned read outputs"},
                ),
                "unaligned_file": ("BOOLEAN", {"default": False, "description": "Write reads that fail to align"}),
                "aligned_file": ("BOOLEAN", {"default": False, "description": "Write reads that align at least once"}),
                "paired_options_selector": (
                    "STRING",
                    {"default": "no", "options": ["no", "yes"], "description": "Enable paired-end fragment and orientation options"},
                ),
                "I": ("INT", {"default": 0, "min": 0, "advanced": True, "description": "Minimum paired-end fragment length"}),
                "X": ("INT", {"default": 500, "min": 0, "advanced": True, "description": "Maximum paired-end fragment length"}),
                "fr_rf_ff": ("STRING", {"default": "--fr", "options": cls.PAIRED_ORIENTATION_OPTIONS, "advanced": True}),
                "no_mixed": ("BOOLEAN", {"default": False, "advanced": True, "description": "Disable mixed alignments"}),
                "no_discordant": ("BOOLEAN", {"default": False, "advanced": True, "description": "Disable discordant alignments"}),
                "dovetail": ("BOOLEAN", {"default": False, "advanced": True, "description": "Allow dovetailing mates"}),
                "no_contain": ("BOOLEAN", {"default": False, "advanced": True, "description": "Disallow contained mate alignments"}),
                "no_overlap": ("BOOLEAN", {"default": False, "advanced": True, "description": "Disallow overlapping mates"}),
                "analysis_type_selector": (
                    "STRING",
                    {"default": "simple", "options": cls.ANALYSIS_TYPE_OPTIONS, "description": "Simple presets or full Bowtie2 options"},
                ),
                "preset": ("STRING", {"default": "no_presets", "options": cls.PRESET_OPTIONS, "description": "Bowtie2 simple-mode preset"}),
                "input_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "skip": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "qupto": ("INT", {"default": 100000000, "min": 1, "advanced": True}),
                "trim5": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "trim3": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "qv_encoding": ("STRING", {"default": "--phred33", "options": cls.QV_ENCODING_OPTIONS, "advanced": True}),
                "solexa_quals": ("BOOLEAN", {"default": False, "advanced": True}),
                "int_quals": ("BOOLEAN", {"default": False, "advanced": True}),
                "alignment_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "N": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True, "description": "Seed mismatches"}),
                "seed_L": ("INT", {"default": 22, "min": 0, "max": 32, "advanced": True, "description": "Seed length"}),
                "i": ("STRING", {"default": "S,1,1.15", "advanced": True, "description": "Seed interval function"}),
                "n_ceil": ("STRING", {"default": "L,0,0.15", "advanced": True, "description": "N-ceiling function"}),
                "dpad": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "gbar": ("INT", {"default": 4, "min": 0, "advanced": True}),
                "ignore_quals": ("BOOLEAN", {"default": False, "advanced": True}),
                "nofw": ("BOOLEAN", {"default": False, "advanced": True}),
                "norc": ("BOOLEAN", {"default": False, "advanced": True}),
                "no_1mm_upfront": ("BOOLEAN", {"default": False, "advanced": True}),
                "align_mode_selector": ("STRING", {"default": "end-to-end", "options": ["end-to-end", "local"], "advanced": True}),
                "score_min_ete": ("STRING", {"default": "L,-0.6,-0.6", "advanced": True}),
                "score_min_loc": ("STRING", {"default": "G,20,8", "advanced": True}),
                "scoring_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "ma": ("INT", {"default": 2, "min": 0, "advanced": True}),
                "mp": ("STRING", {"default": "6,2", "advanced": True}),
                "np": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "rdg_read_open": ("INT", {"default": 5, "min": 0, "advanced": True}),
                "rdg_read_extend": ("INT", {"default": 3, "min": 0, "advanced": True}),
                "rfg_ref_open": ("INT", {"default": 5, "min": 0, "advanced": True}),
                "rfg_ref_extend": ("INT", {"default": 3, "min": 0, "advanced": True}),
                "reporting_options_selector": ("STRING", {"default": "no", "options": cls.REPORTING_OPTIONS, "advanced": True}),
                "k": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "effort_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "D": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "R": ("INT", {"default": 2, "min": 0, "advanced": True}),
                "d": ("BOOLEAN", {"default": False, "advanced": True}),
                "other_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "seed": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "non_deterministic": ("BOOLEAN", {"default": False, "advanced": True}),
                "rg_selector": (
                    "STRING",
                    {"default": "do_not_set", "options": ["do_not_set", "set"], "description": "Set read group information"},
                ),
                "rg_id": ("STRING", {"default": "", "description": "Read group ID"}),
                "rg_sm": ("STRING", {"default": "", "description": "Read group sample"}),
                "rg_pl": ("STRING", {"default": "", "description": "Read group platform"}),
                "rg_lb": ("STRING", {"default": "", "description": "Read group library"}),
                "rg_cn": ("STRING", {"default": "", "description": "Read group sequencing center"}),
                "rg_ds": ("STRING", {"default": "", "advanced": True}),
                "rg_dt": ("STRING", {"default": "", "advanced": True}),
                "rg_fo": ("STRING", {"default": "", "advanced": True}),
                "rg_ks": ("STRING", {"default": "", "advanced": True}),
                "rg_pg": ("STRING", {"default": "", "advanced": True}),
                "rg_pi": ("STRING", {"default": "", "advanced": True}),
                "rg_pu": ("STRING", {"default": "", "advanced": True}),
                "sam_options_selector": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Enable SAM/BAM output options"}),
                "sam_output_format": ("STRING", {"default": "bam", "options": cls.SAM_OUTPUT_FORMAT_OPTIONS, "description": "Alignment output format"}),
                "no_unal": ("BOOLEAN", {"default": False, "advanced": True}),
                "omit_sec_seq": ("BOOLEAN", {"default": False, "advanced": True}),
                "sam_no_qname_trunc": ("BOOLEAN", {"default": False, "advanced": True}),
                "xeq": ("BOOLEAN", {"default": False, "advanced": True}),
                "soft_clipped_unmapped_tlen": ("BOOLEAN", {"default": False, "advanced": True}),
                "reorder": ("BOOLEAN", {"default": False, "advanced": True}),
                "save_mapping_stats": ("BOOLEAN", {"default": False, "description": "Save Bowtie2 mapping statistics from stderr"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BWAMem2IndexNode(CommandNode):
    """Build a BWA-MEM2 reference index from a FASTA sequence."""

    NODE_ID = "bwa_mem2_idx"
    DISPLAY_NAME = "BWA-MEM2 Indexer"
    REQUIRED_CONDA_PACKAGES = ["bwa-mem2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Build a BWA-MEM2 reference index from a FASTA sequence."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BWA-MEM2",
        "bwa_mem2_idx",
        "BWA-MEM2 reference index",
        "reference index",
        "bwa-mem2 index",
    ]
    RETURN_TYPES = ("BWA_MEM2_INDEX",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["bwa-mem2"]
    DOCUMENTATION_URL = "https://github.com/bwa-mem2/bwa-mem2"
    CITATION_DOIS = BWA_MEM2_CITATION_DOIS
    CITATION_URLS = BWA_MEM2_CITATION_URLS
    CITATION_TEXT = BWA_MEM2_CITATION_TEXT
    VERSION = "2.3+galaxy0"
    SHELL = True

    @classmethod
    def _index_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/index"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        index_dir = cls._index_dir(inputs)
        return [
            "mkdir",
            "-p",
            index_dir,
            "&&",
            "cd",
            index_dir,
            "&&",
            "bwa-mem2",
            "index",
            "-p",
            "reference",
            str(inputs.get("reference", "")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "index"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reference", "")).strip():
            return "reference is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "FASTA genome sequence to index with BWA-MEM2"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BWAMem2Node(CommandNode):
    """Map reads against a BWA-MEM2 reference index and emit BAM."""

    NODE_ID = "bwa_mem2"
    DISPLAY_NAME = "BWA-MEM2"
    REQUIRED_CONDA_PACKAGES = ["bwa-mem2", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Map medium and long reads against a reference genome with BWA-MEM2 and emit BAM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BWA-MEM2",
        "bwa_mem2",
        "bwa-mem2 mem",
        "read mapping",
        "medium and long reads",
        "BAM output",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam_output",)
    REQUIRED_EXECUTABLES = ["bwa-mem2", "samtools"]
    DOCUMENTATION_URL = "https://github.com/bwa-mem2/bwa-mem2"
    CITATION_DOIS = BWA_MEM2_CITATION_DOIS
    CITATION_URLS = BWA_MEM2_CITATION_URLS
    CITATION_TEXT = BWA_MEM2_CITATION_TEXT
    VERSION = "2.3+galaxy0"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]
    FASTQ_INPUT_OPTIONS = ["paired", "single", "paired_collection", "paired_iv"]
    ANALYSIS_TYPE_OPTIONS = ["illumina", "pacbio", "ont2d", "intractg", "full"]
    OUTPUT_SORT_OPTIONS = ["coordinate", "name", "unsorted"]
    ALGORITHMIC_INT_MIN_KEYS = {
        "k": 1,
        "w": 1,
        "d": 1,
        "y": 1,
        "c": 1,
        "W": 0,
        "m": 0,
    }
    ALGORITHMIC_FLOAT_KEYS = {"r", "D"}
    SCORING_INT_MIN_KEYS = {"A": 0, "B": 0, "U": 0}
    IO_INT_MIN_KEYS = {"T": 0, "h": 0, "K": 1}

    @classmethod
    def _out_bam(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/aligned.bam"

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", inputs.get("reference_source", "history")) or "history")

    @classmethod
    def _ref_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_file", inputs.get("reference", "")) or "")

    @classmethod
    def _ref_file_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_file_type", inputs.get("reference_type", "")) or "").lower()

    @classmethod
    def _is_index_reference(cls, inputs: dict[str, Any]) -> bool:
        ref_type = cls._ref_file_type(inputs)
        if ref_type in {"bwa_mem2_index", "bwa_mem2", "index", "bwa_mem2_index_dir"}:
            return True
        return cls._ref_file(inputs).rstrip("/").endswith((".bwa_mem2_index", ".bwa_mem2_index/"))

    @classmethod
    def _reference_prelude_and_filename(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        ref_file = cls._ref_file(inputs)
        reference_source = cls._reference_source(inputs)
        if reference_source == "cached":
            return [], ref_file
        if cls._is_index_reference(inputs):
            return [], f"{ref_file.rstrip('/')}/reference"
        suffix = "".join(Path(ref_file).suffixes)
        extension = suffix.lstrip(".") or "fasta"
        local_ref = f"localref.{extension}"
        return ["ln", "-s", ref_file, local_ref, "&&", "bwa-mem2", "index", local_ref, "&&"], local_ref

    @classmethod
    def _fastq_input_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("fastq_input_selector", inputs.get("input_type", "single")) or "single")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("fastq_input1", inputs.get("reads_collection", inputs.get("reads", "")))
        if isinstance(collection, dict):
            return str(collection.get("forward", "")), str(collection.get("reverse", ""))
        reads = _as_list(collection)
        return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> list[str]:
        mode = cls._fastq_input_selector(inputs)
        if mode == "paired":
            return [str(inputs.get("fastq_input1", "") or ""), str(inputs.get("fastq_input2", "") or "")]
        if mode == "paired_collection":
            forward, reverse = cls._paired_collection_reads(inputs)
            return [forward, reverse]
        return [str(inputs.get("fastq_input1", inputs.get("read1", "")) or "")]

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("analysis_type_selector", "illumina") or "illumina")

    @classmethod
    def _selector(cls, inputs: dict[str, Any], key: str, default: str = "do_not_set") -> str:
        return str(inputs.get(key, default) or default)

    @classmethod
    def _add_full_mode_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._selector(inputs, "algorithmic_options_selector") == "set":
            for flag, key, default in (
                ("-k", "k", 19),
                ("-w", "w", 100),
                ("-d", "d", 100),
                ("-r", "r", 1.5),
                ("-y", "y", 20),
                ("-c", "c", 500),
                ("-D", "D", 0.5),
                ("-W", "W", 0),
                ("-m", "m", 50),
            ):
                cmd.extend([flag, str(inputs.get(key, default))])
            for key, flag in (("S", "-S"), ("P", "-P"), ("e", "-e")):
                if inputs.get(key):
                    cmd.append(flag)
        if cls._selector(inputs, "scoring_options_selector") == "set":
            for flag, key, default in (
                ("-A", "A", 1),
                ("-B", "B", 4),
                ("-O", "O", "6,6"),
                ("-E", "E", "1,1"),
                ("-L", "L", "5,5"),
                ("-U", "U", 17),
            ):
                cmd.extend([flag, str(inputs.get(key, default))])
        if cls._selector(inputs, "io_options_selector") == "set":
            for flag, key, default in (("-T", "T", 30), ("-h", "h", 5)):
                cmd.extend([flag, str(inputs.get(key, default))])
            for key, flag in (
                ("a", "-a"),
                ("C", "-C"),
                ("V", "-V"),
                ("Y", "-Y"),
                ("M", "-M"),
                ("five", "-5"),
                ("q", "-q"),
            ):
                if inputs.get(key):
                    cmd.append(flag)
            _add_if_value(cmd, "-K", inputs.get("K"))

    @classmethod
    def _read_group_string(cls, inputs: dict[str, Any]) -> str:
        rg_id = str(inputs.get("rg_id", inputs.get("ID", "")) or "")
        tags = [
            ("SM", inputs.get("rg_sm", inputs.get("SM", ""))),
            ("PL", inputs.get("rg_pl", inputs.get("PL", ""))),
            ("LB", inputs.get("rg_lb", inputs.get("LB", ""))),
            ("CN", inputs.get("rg_cn", inputs.get("CN", ""))),
            ("DS", inputs.get("rg_ds", inputs.get("DS", ""))),
            ("DT", inputs.get("rg_dt", inputs.get("DT", ""))),
            ("FO", inputs.get("rg_fo", inputs.get("FO", ""))),
            ("KS", inputs.get("rg_ks", inputs.get("KS", ""))),
            ("PG", inputs.get("rg_pg", inputs.get("PG", ""))),
            ("PI", inputs.get("rg_pi", inputs.get("PI", ""))),
            ("PU", inputs.get("rg_pu", inputs.get("PU", ""))),
        ]
        if not rg_id:
            reads = cls._reads(inputs)
            rg_id = _safe_name(reads[0]) if reads and reads[0] else "read_group"
        parts = [f"@RG\\tID:{rg_id}"]
        for tag, value in tags:
            if value is not None and str(value) != "":
                parts.append(f"{tag}:{value}")
        return "\\t".join(parts)

    @classmethod
    def _add_read_group(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("rg_selector", "do_not_set") or "do_not_set") == "do_not_set":
            return
        cmd.extend(["-R", cls._read_group_string(inputs)])

    @classmethod
    def _add_output_sort(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        if output_sort == "coordinate":
            cmd.extend(["|", "samtools", "sort", "-@${GALAXY_SLOTS:-2}", "-T", "${TMPDIR:-.}", "-O", "bam", "-o", cls._out_bam(inputs)])
        elif output_sort == "name":
            cmd.extend(["|", "samtools", "sort", "-n", "-@${GALAXY_SLOTS:-2}", "-T", "${TMPDIR:-.}", "-O", "bam", "-o", cls._out_bam(inputs)])
        else:
            cmd.extend(["|", "samtools", "view", "-@", "${GALAXY_SLOTS:-2}", "-bS", "-", "-o", cls._out_bam(inputs)])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prelude, reference_fasta = cls._reference_prelude_and_filename(inputs)
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        cmd = ["set", "-o", "pipefail", "&&"]
        cmd.extend(prelude)
        bwa_cmd = [
            "bwa-mem2",
            "mem",
            "-t",
            "1" if output_sort == "unsorted" else "${GALAXY_SLOTS:-1}",
            "-v",
            "1",
        ]
        mode = cls._fastq_input_selector(inputs)
        if mode == "paired_iv":
            bwa_cmd.append("-p")
            _add_if_value(bwa_cmd, "-I", inputs.get("iset_stats"))
        analysis_type = cls._analysis_type(inputs)
        if analysis_type not in {"illumina", "full"}:
            bwa_cmd.extend(["-x", analysis_type])
        elif analysis_type == "full":
            cls._add_full_mode_options(bwa_cmd, inputs)
        cls._add_read_group(bwa_cmd, inputs)
        if mode in {"paired", "paired_collection"}:
            _add_if_value(bwa_cmd, "-I", inputs.get("iset_stats"))
        bwa_cmd.append(reference_fasta)
        bwa_cmd.extend(cls._reads(inputs))
        cls._add_output_sort(bwa_cmd, inputs)
        cmd.extend(bwa_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "aligned.bam"]

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ""}:
            return True
        try:
            value = int(inputs[key])
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be at least {minimum}"
        return True

    @classmethod
    def _validate_float(cls, inputs: dict[str, Any], key: str) -> bool | str:
        if key not in inputs or inputs.get(key) in {None, ""}:
            return True
        try:
            float(inputs[key])
        except (TypeError, ValueError):
            return f"{key} must be a number"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._ref_file(inputs).strip():
            return "ref_file is required"
        mode = cls._fastq_input_selector(inputs)
        if mode not in cls.FASTQ_INPUT_OPTIONS:
            return f"fastq_input_selector must be one of: {', '.join(cls.FASTQ_INPUT_OPTIONS)}"
        reads = cls._reads(inputs)
        if not reads or not reads[0].strip():
            return "fastq_input1 is required"
        if mode in {"paired", "paired_collection"} and (len(reads) < 2 or not reads[1].strip()):
            return "fastq_input2 is required for paired input"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        analysis_type = cls._analysis_type(inputs)
        if analysis_type not in cls.ANALYSIS_TYPE_OPTIONS:
            return f"analysis_type_selector must be one of: {', '.join(cls.ANALYSIS_TYPE_OPTIONS)}"
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        if output_sort not in cls.OUTPUT_SORT_OPTIONS:
            return f"output_sort must be one of: {', '.join(cls.OUTPUT_SORT_OPTIONS)}"
        if analysis_type == "full":
            for key, minimum in cls.ALGORITHMIC_INT_MIN_KEYS.items():
                validation = cls._validate_int_min(inputs, key, minimum)
                if validation is not True:
                    return validation
            for key in cls.ALGORITHMIC_FLOAT_KEYS:
                validation = cls._validate_float(inputs, key)
                if validation is not True:
                    return validation
            for key, minimum in cls.SCORING_INT_MIN_KEYS.items():
                validation = cls._validate_int_min(inputs, key, minimum)
                if validation is not True:
                    return validation
            for key, minimum in cls.IO_INT_MIN_KEYS.items():
                validation = cls._validate_int_min(inputs, key, minimum)
                if validation is not True:
                    return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": (
                    "BWA_MEM2_INDEX",
                    {"description": "BWA-MEM2 reference index directory, or a FASTA/FASTA.GZ when reference_source_selector is history"},
                ),
                "fastq_input_selector": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": cls.FASTQ_INPUT_OPTIONS,
                        "description": "Single, paired, paired collection, or interleaved read input",
                    },
                ),
                "fastq_input1": ("FASTQ", {"description": "Single, forward, interleaved, or paired collection reads"}),
            },
            "optional": {
                "fastq_input2": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Reverse reads for paired input",
                        "displayOptions": {"show": {"fastq_input_selector": ["paired"]}},
                    },
                ),
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a BWA-MEM2 index/FASTA from history or a built-in cached index",
                    },
                ),
                "ref_file_type": (
                    "STRING",
                    {
                        "default": "bwa_mem2_index",
                        "options": ["bwa_mem2_index", "fasta", "fasta.gz"],
                        "description": "Reference dataset type used to mirror Galaxy's history-index handling",
                    },
                ),
                "iset_stats": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Insert size statistics for paired or interleaved reads, matching bwa-mem2 -I",
                    },
                ),
                "analysis_type_selector": (
                    "STRING",
                    {"default": "illumina", "options": cls.ANALYSIS_TYPE_OPTIONS, "description": "Galaxy BWA-MEM2 analysis mode"},
                ),
                "algorithmic_options_selector": (
                    "STRING",
                    {
                        "default": "do_not_set",
                        "options": ["do_not_set", "set"],
                        "advanced": True,
                        "displayOptions": {"show": {"analysis_type_selector": ["full"]}},
                    },
                ),
                "k": ("INT", {"default": 19, "min": 1, "advanced": True, "description": "Minimum seed length"}),
                "w": ("INT", {"default": 100, "min": 1, "advanced": True, "description": "Band width"}),
                "d": ("INT", {"default": 100, "min": 1, "advanced": True, "description": "Off-diagonal X-dropoff"}),
                "r": ("FLOAT", {"default": 1.5, "advanced": True, "description": "Internal seed look-up trigger"}),
                "y": ("INT", {"default": 20, "min": 1, "advanced": True, "description": "Third-round seed occurrence"}),
                "c": ("INT", {"default": 500, "min": 1, "advanced": True, "description": "Skip seeds above this occurrence count"}),
                "D": ("FLOAT", {"default": 0.5, "advanced": True, "description": "Drop short chains threshold"}),
                "W": ("INT", {"default": 0, "min": 0, "advanced": True, "description": "Minimum seeded bases for a chain"}),
                "m": ("INT", {"default": 50, "min": 0, "advanced": True, "description": "Mate rescue rounds"}),
                "S": ("BOOLEAN", {"default": False, "advanced": True, "description": "Skip mate rescue"}),
                "P": ("BOOLEAN", {"default": False, "advanced": True, "description": "Skip pairing"}),
                "e": ("BOOLEAN", {"default": False, "advanced": True, "description": "Discard full-length exact matches"}),
                "scoring_options_selector": (
                    "STRING",
                    {
                        "default": "do_not_set",
                        "options": ["do_not_set", "set"],
                        "advanced": True,
                        "displayOptions": {"show": {"analysis_type_selector": ["full"]}},
                    },
                ),
                "A": ("INT", {"default": 1, "min": 0, "advanced": True, "description": "Match score"}),
                "B": ("INT", {"default": 4, "min": 0, "advanced": True, "description": "Mismatch penalty"}),
                "O": ("STRING", {"default": "6,6", "advanced": True, "description": "Gap open penalties"}),
                "E": ("STRING", {"default": "1,1", "advanced": True, "description": "Gap extension penalties"}),
                "L": ("STRING", {"default": "5,5", "advanced": True, "description": "Clipping penalties"}),
                "U": ("INT", {"default": 17, "min": 0, "advanced": True, "description": "Unpaired read-pair penalty"}),
                "io_options_selector": (
                    "STRING",
                    {
                        "default": "do_not_set",
                        "options": ["do_not_set", "set"],
                        "advanced": True,
                        "displayOptions": {"show": {"analysis_type_selector": ["full"]}},
                    },
                ),
                "T": ("INT", {"default": 30, "min": 0, "advanced": True, "description": "Minimum score to output"}),
                "h": ("INT", {"default": 5, "min": 0, "advanced": True, "description": "XA tag hit threshold"}),
                "a": ("BOOLEAN", {"default": False, "advanced": True, "description": "Output all alignments"}),
                "C": ("BOOLEAN", {"default": False, "advanced": True, "description": "Append read comments"}),
                "V": ("BOOLEAN", {"default": False, "advanced": True, "description": "Output reference header in XR tag"}),
                "Y": ("BOOLEAN", {"default": False, "advanced": True, "description": "Soft-clip supplementary alignments"}),
                "M": ("BOOLEAN", {"default": False, "advanced": True, "description": "Mark shorter split hits as secondary"}),
                "five": ("BOOLEAN", {"default": False, "advanced": True, "description": "Choose smallest coordinate split as primary"}),
                "q": ("BOOLEAN", {"default": False, "advanced": True, "description": "Do not lower MAPQ for split alignment"}),
                "K": ("INT", {"default": "", "min": 1, "advanced": True, "description": "Input bases per batch"}),
                "rg_selector": (
                    "STRING",
                    {"default": "do_not_set", "options": ["do_not_set", "set"], "description": "Set read group information"},
                ),
                "rg_id": ("STRING", {"default": "", "description": "Read group ID"}),
                "rg_sm": ("STRING", {"default": "", "description": "Read group sample"}),
                "rg_pl": ("STRING", {"default": "", "description": "Read group platform"}),
                "rg_lb": ("STRING", {"default": "", "description": "Read group library"}),
                "rg_cn": ("STRING", {"default": "", "description": "Read group sequencing center"}),
                "rg_ds": ("STRING", {"default": "", "description": "Read group description", "advanced": True}),
                "rg_dt": ("STRING", {"default": "", "description": "Read group date", "advanced": True}),
                "rg_fo": ("STRING", {"default": "", "description": "Read group flow order", "advanced": True}),
                "rg_ks": ("STRING", {"default": "", "description": "Read group key sequence", "advanced": True}),
                "rg_pg": ("STRING", {"default": "", "description": "Read group program", "advanced": True}),
                "rg_pi": ("STRING", {"default": "", "description": "Read group predicted insert size", "advanced": True}),
                "rg_pu": ("STRING", {"default": "", "description": "Read group platform unit", "advanced": True}),
                "output_sort": (
                    "STRING",
                    {"default": "coordinate", "options": cls.OUTPUT_SORT_OPTIONS, "description": "BAM sorting mode"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BamLeftAlignNode(CommandNode):
    """Left-realign indels in BAM alignments with FreeBayes bamleftalign."""

    NODE_ID = "bamleftalign"
    DISPLAY_NAME = "BamLeftAlign"
    REQUIRED_CONDA_PACKAGES = ["freebayes", "samtools", "coreutils"]
    CATEGORY = "variant"
    DESCRIPTION = "Left-realign indels in BAM alignments using the FreeBayes bamleftalign utility."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FreeBayes",
        "bamleftalign",
        "left realignment",
        "left-align BAM indels",
        "indel normalization",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("realigned_bam",)
    REQUIRED_EXECUTABLES = ["bamleftalign", "samtools"]
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes#citation"
    CITATION_DOIS = FREEBAYES_CITATION_DOIS
    CITATION_URLS = FREEBAYES_CITATION_URLS
    CITATION_TEXT = FREEBAYES_CITATION_TEXT
    VERSION = "1.3.10+galaxy0"
    SHELL = True
    REFERENCE_SOURCE_OPTIONS = ["history", "cached"]

    @classmethod
    def _input_bam(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_bam", inputs.get("bam", "")) or "")

    @classmethod
    def _reference(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference", inputs.get("ref_file", inputs.get("fasta_ref", ""))) or "")

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source", inputs.get("reference_source_selector", "history")) or "history")

    @classmethod
    def _iterations(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("iterations", 5)
        return 5 if value is None or value == "" else int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reference = cls._reference(inputs)
        cmd: list[str] = []
        if cls._reference_source(inputs) == "history":
            cmd.extend(["samtools", "faidx", reference, "&&"])
        cmd.extend(
            [
                "cat",
                cls._input_bam(inputs),
                "|",
                "bamleftalign",
                "--fasta-reference",
                reference,
                "-c",
                "--max-iterations",
                str(cls._iterations(inputs)),
            ]
        )
        _add_shell_redirect(cmd, f"{_out(inputs)}/realigned.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "realigned.bam", output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_bam(inputs).strip():
            return "input_bam is required"
        if not cls._reference(inputs).strip():
            return "reference is required"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        try:
            iterations = cls._iterations(inputs)
        except (TypeError, ValueError):
            return "iterations must be an integer"
        if iterations < 1:
            return "iterations must be at least 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "BAM dataset to left-realign"}),
                "reference": ("FASTA", {"description": "Reference FASTA used by bamleftalign"}),
            },
            "optional": {
                "reference_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Reference source matching the Galaxy wrapper selector",
                    },
                ),
                "iterations": ("INT", {"default": 5, "min": 1, "description": "Maximum number of left-realignment iterations"}),
                "bam": ("BAM", {"description": "Compatibility alias for input_bam", "advanced": True}),
                "ref_file": ("FASTA", {"description": "Compatibility alias for reference", "advanced": True}),
                "fasta_ref": ("FASTA", {"description": "Compatibility alias for reference", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


from bionodulo.nodes.builtin.bcftools_family.analysis import (
    BCFtoolsCNVNode,
    BCFtoolsCSQNode,
)
from bionodulo.nodes.builtin.bcftools_family.calling import (
    BCFtoolsCallNode,
    BCFtoolsMpileupNode,
)
from bionodulo.nodes.builtin.bcftools_family.conversion import (
    BCFtoolsConvertFromVcfNode,
    BCFtoolsConvertToVcfNode,
)
from bionodulo.nodes.builtin.bcftools_family.plugins import (
    BCFtoolsPluginColorChrsNode,
    BCFtoolsPluginCountsNode,
    BCFtoolsPluginDosageNode,
    BCFtoolsPluginFillAnAcNode,
    BCFtoolsPluginFillTagsNode,
    BCFtoolsPluginFixploidyNode,
    BCFtoolsPluginFrameshiftsNode,
    BCFtoolsPluginImputeInfoNode,
    BCFtoolsPluginMendelianNode,
    BCFtoolsPluginMissing2refNode,
    BCFtoolsPluginSetgtNode,
    BCFtoolsPluginSplitVepNode,
    BCFtoolsPluginTag2tagNode,
)
from bionodulo.nodes.builtin.bcftools_family.reporting import (
    BCFtoolsConsensusNode,
    BCFtoolsGTcheckNode,
    BCFtoolsQueryListSamplesNode,
    BCFtoolsQueryNode,
    BCFtoolsROHNode,
    BCFtoolsStatsNode,
)
from bionodulo.nodes.builtin.bcftools_family.transforms import (
    BCFtoolsConcatNode,
    BCFtoolsFilterNode,
    BCFtoolsIsecNode,
    BCFtoolsMergeNode,
    BCFtoolsNormNode,
    BCFtoolsReheaderNode,
    BCFtoolsViewNode,
)
