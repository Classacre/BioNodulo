"""Shared hap.py, bwa-meth, and CrossMap contracts for final owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin._alignment_taxonomy_contracts import ToolsIUCCommandContract

class _HappySompyContract(ToolsIUCCommandContract):
    """Compare truth and query VCFs with hap.py or som.py."""

    LEGACY_NODE_ID = "som.py"
    DISPLAY_NAME = "som.py and hap.py"
    REQUIRED_CONDA_PACKAGES = ["hap.py", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Compare truth and query VCF callsets with hap.py haplotype benchmarking or som.py allele matching."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hap.py",
        "som.py",
        "happy",
        "Haplotype Comparison Tools",
        "variant benchmarking",
        "VCF comparison",
        "truth query comparison",
    ]
    RETURN_TYPES = ("TSV", "JSON", "JSON", "CSV", "CSV")
    RETURN_NAMES = ("results", "sompy_metrics", "happy_metrics", "stats", "summary")
    REQUIRED_EXECUTABLES = ["som.py", "hap.py", "samtools"]
    DOCUMENTATION_URL = HAPPY_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [HAPPY_CITATION_URL]
    CITATION_TEXT = HAPPY_CITATION_TEXT
    VERSION = "0.3.15+galaxy0"
    SHELL = True

    PROGRAM_OPTIONS = ["som.py", "hap.py"]
    REFERENCE_SOURCE_OPTIONS = ["indexed", "history"]

    @classmethod
    def _program(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("program_select", "som.py") or "som.py")

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source", "indexed") or "indexed")

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output"

    @classmethod
    def _reference_path(cls, inputs: dict[str, Any]) -> str:
        if cls._reference_source(inputs) == "history":
            return f"{_out(inputs)}/reference.fasta"
        return str(inputs.get("reference_path", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reference_path = cls._reference_path(inputs)
        setup: list[str] = []
        if cls._reference_source(inputs) == "history":
            setup.extend(
                [
                    _shell_join(["ln", "-sf", str(inputs.get("history_item", "")), reference_path]),
                    _shell_join(["samtools", "faidx", reference_path]),
                ]
            )
        cmd = [
            cls._program(inputs),
            str(inputs.get("truth", "")),
            str(inputs.get("query", "")),
            "-r",
            reference_path,
            "-o",
            cls._out_prefix(inputs),
        ]
        sed_whitespace_to_tab = shlex.quote(r"s/\s\+/\t/g")
        results_path = shlex.quote(f"{out}/results.tsv")
        compare_cmd = (
            f"export HGREF={shlex.quote(reference_path)} && {_shell_join(cmd)} | "
            f"sed {sed_whitespace_to_tab} | tail -n+2 > {results_path}"
        )
        setup.append(compare_cmd)
        return " && ".join(setup)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "results.tsv"]
        if cls._program(inputs) == "hap.py":
            outputs.extend([out / "output.metrics.json.gz", out / "output.summary.csv"])
        else:
            outputs.extend([out / "output.metrics.json", out / "output.stats.csv"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("truth", "")).strip():
            return "truth VCF is required"
        if not str(inputs.get("query", "")).strip():
            return "query VCF is required"
        program = cls._program(inputs)
        if program not in cls.PROGRAM_OPTIONS:
            return f"program_select must be one of: {', '.join(cls.PROGRAM_OPTIONS)}"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if reference_source == "indexed" and not str(inputs.get("reference_path", "")).strip():
            return "reference_path is required for indexed reference_source"
        if reference_source == "history" and not str(inputs.get("history_item", "")).strip():
            return "history_item is required for history reference_source"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "truth": ("VCF", {"description": "Ground-truth variant calls"}),
                "query": ("VCF", {"description": "Query variant calls to benchmark"}),
            },
            "optional": {
                "program_select": (
                    "STRING",
                    {
                        "default": "som.py",
                        "options": cls.PROGRAM_OPTIONS,
                        "description": "Comparison method: som.py allele matching or hap.py haplotype benchmarking",
                    },
                ),
                "reference_source": (
                    "STRING",
                    {
                        "default": "indexed",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use an indexed reference path or stage a history FASTA",
                    },
                ),
                "reference_path": (
                    "FASTA",
                    {"default": "", "description": "Indexed reference FASTA path for built-in/reference data mode"},
                ),
                "history_item": (
                    "FASTA",
                    {"default": "", "description": "History reference FASTA to stage and index before comparison"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BwaMethContract(ToolsIUCCommandContract):
    """Align bisulfite sequencing reads with bwa-meth."""

    LEGACY_NODE_ID = "bwameth"
    DISPLAY_NAME = "bwameth"
    REQUIRED_CONDA_PACKAGES = ["bwameth", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Align bisulfite-sequencing FASTQ reads to a genome with bwa-meth."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bwameth",
        "bwa-meth",
        "BWA methylation",
        "BS-Seq alignment",
        "bisulfite sequencing",
        "WGBS",
        "RRBS",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["bwameth.py", "samtools"]
    DOCUMENTATION_URL = BWA_METH_DOCUMENTATION_URL
    CITATION_DOIS = BWA_METH_CITATION_DOIS
    CITATION_URLS = BWA_METH_CITATION_URLS
    CITATION_TEXT = BWA_METH_CITATION_TEXT
    VERSION = "0.2.9+galaxy0"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["history", "indexed"]
    READ_MODE_OPTIONS = ["single", "paired", "paired_collection"]

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source", "history") or "history")

    @classmethod
    def _read_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("single_or_paired_opts", "single") or "single")

    @classmethod
    def _reference_path(cls, inputs: dict[str, Any]) -> str:
        if cls._reference_source(inputs) == "indexed":
            return str(inputs.get("reference_path", ""))
        return f"{_out(inputs)}/index_dir/genome.fa"

    @staticmethod
    def _fastq_stage_name(prefix: str, path: Any) -> str:
        suffixes = Path(str(path or "")).suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == [".fastq", ".gz"]:
            return f"{prefix}.fastq.gz"
        if len(suffixes) >= 2 and suffixes[-2:] == [".fastq", ".bz2"]:
            return f"{prefix}.fastq.bz2"
        if suffixes and suffixes[-1] == ".gz":
            return f"{prefix}.fastq.gz"
        if suffixes and suffixes[-1] == ".bz2":
            return f"{prefix}.fastq.bz2"
        return f"{prefix}.fastq"

    @classmethod
    def _staged_reads(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        out = _out(inputs)
        mode = cls._read_mode(inputs)
        links: list[str] = []
        reads: list[str] = []
        if mode == "single":
            source = str(inputs.get("input_singles", ""))
            staged = f"{out}/{cls._fastq_stage_name('input_f', source)}"
            links.append(_shell_join(["ln", "-sf", source, staged]))
            reads.append(staged)
            return links, reads
        if mode == "paired_collection":
            mate1 = str(inputs.get("input_mate1_forward", inputs.get("input_mate1", "")))
            mate2 = str(inputs.get("input_mate1_reverse", inputs.get("input_mate2", "")))
        else:
            mate1 = str(inputs.get("input_mate1", ""))
            mate2 = str(inputs.get("input_mate2", ""))
        staged1 = f"{out}/{cls._fastq_stage_name('input_f', mate1)}"
        staged2 = f"{out}/{cls._fastq_stage_name('input_r', mate2)}"
        links.extend([_shell_join(["ln", "-sf", mate1, staged1]), _shell_join(["ln", "-sf", mate2, staged2])])
        reads.extend([staged1, staged2])
        return links, reads

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands: list[str] = []
        reference_path = cls._reference_path(inputs)
        if cls._reference_source(inputs) == "history":
            index_dir = f"{out}/index_dir"
            commands.extend(
                [
                    _shell_join(["mkdir", "-p", index_dir]),
                    _shell_join(["ln", "-sf", str(inputs.get("reference", "")), reference_path]),
                    _shell_join(["bwameth.py", "index", reference_path]),
                ]
            )
        links, reads = cls._staged_reads(inputs)
        commands.extend(links)
        cmd = ["bwameth.py", "-t", "${GALAXY_SLOTS:-4}", "--reference", reference_path]
        read_group = str(inputs.get("readGroup", "") or "").strip()
        if read_group:
            cmd.extend(["--read-group", read_group])
        cmd.extend(reads)
        align_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-4}'", "${GALAXY_SLOTS:-4}")
        sort_cmd = "samtools sort -l 0 -T ${TMPDIR:-.} -O bam"
        view_cmd = f"samtools view -O bam -@ ${{GALAXY_SLOTS:-1}} -o {shlex.quote(f'{out}/output.bam')}"
        commands.append(f"{align_cmd} | {sort_cmd} | {view_cmd}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if reference_source == "indexed" and not str(inputs.get("reference_path", "")).strip():
            return "reference_path is required for indexed reference_source"
        if reference_source == "history" and not str(inputs.get("reference", "")).strip():
            return "reference is required for history reference_source"
        mode = cls._read_mode(inputs)
        if mode not in cls.READ_MODE_OPTIONS:
            return f"single_or_paired_opts must be one of: {', '.join(cls.READ_MODE_OPTIONS)}"
        if mode == "single" and not str(inputs.get("input_singles", "")).strip():
            return "input_singles FASTQ is required for single-end mode"
        if mode == "paired":
            if not str(inputs.get("input_mate1", "")).strip():
                return "input_mate1 FASTQ is required for paired mode"
            if not str(inputs.get("input_mate2", "")).strip():
                return "input_mate2 FASTQ is required for paired mode"
        if mode == "paired_collection":
            if not str(inputs.get("input_mate1_forward", inputs.get("input_mate1", ""))).strip():
                return "input_mate1_forward FASTQ is required for paired_collection mode"
            if not str(inputs.get("input_mate1_reverse", inputs.get("input_mate2", ""))).strip():
                return "input_mate1_reverse FASTQ is required for paired_collection mode"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_singles": ("FASTQ", {"description": "Single-end FASTQ reads"}),
            },
            "optional": {
                "reference_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a history FASTA or an indexed bwa-meth reference",
                    },
                ),
                "reference": ("FASTA", {"default": "", "description": "History reference FASTA to index with bwa-meth"}),
                "reference_path": (
                    "FASTA",
                    {"default": "", "description": "Built-in/indexed bwa-meth reference FASTA path"},
                ),
                "single_or_paired_opts": (
                    "STRING",
                    {
                        "default": "single",
                        "options": cls.READ_MODE_OPTIONS,
                        "description": "Single-end, paired-end, or paired collection input mode",
                    },
                ),
                "input_mate1": ("FASTQ", {"default": "", "description": "First paired-end FASTQ read"}),
                "input_mate2": ("FASTQ", {"default": "", "description": "Second paired-end FASTQ read"}),
                "input_mate1_forward": (
                    "FASTQ",
                    {"default": "", "description": "Forward FASTQ read from a paired collection"},
                ),
                "input_mate1_reverse": (
                    "FASTQ",
                    {"default": "", "description": "Reverse FASTQ read from a paired collection"},
                ),
                "readGroup": (
                    "STRING",
                    {"default": "", "description": "Optional complete SAM read group string, such as @RG\\tID:foo\\tSM:bar"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapBedContract(ToolsIUCCommandContract):
    """Lift BED coordinates between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_bed"
    DISPLAY_NAME = "CrossMap BED"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "annotation"
    DESCRIPTION = "Lift BED genome coordinates between assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_bed",
        "liftover BED",
        "coordinate conversion",
        "genome assembly conversion",
        "chain file",
    ]
    RETURN_TYPES = ("BED", "BED", "BED")
    RETURN_NAMES = ("output_valid", "output_failed", "output_combined")
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    CHROMID_OPTIONS = ["a", "l", "s"]
    INDEX_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _chromid(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("chromid", "a") or "a")

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @classmethod
    def _merge_unmapped(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("merge_unmapped_entries", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["CrossMap", "bed", str(inputs.get("input_chain", "")), str(inputs.get("input", ""))]
        if cls._merge_unmapped(inputs):
            cmd.extend(["--chromid", cls._chromid(inputs), ">", f"{out}/output_combined.bed"])
        else:
            cmd.extend([f"{out}/output", "--unmap-file", f"{out}/output.unmap", "--chromid", cls._chromid(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._merge_unmapped(inputs):
            return [out / "output_combined.bed"]
        return [out / "output", out / "output.unmap"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input BED is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        chromid = cls._chromid(inputs)
        if chromid not in cls.CHROMID_OPTIONS:
            return f"chromid must be one of: {', '.join(cls.CHROMID_OPTIONS)}"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED file with 3 to 12 columns"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
                "chromid": (
                    "STRING",
                    {
                        "default": "a",
                        "options": cls.CHROMID_OPTIONS,
                        "description": "Chromosome ID style: as-is, long chrN, or short N",
                    },
                ),
                "merge_unmapped_entries": (
                    "BOOLEAN",
                    {"default": False, "description": "Merge failed and converted BED entries into one output"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapBamContract(ToolsIUCCommandContract):
    """Lift BAM alignments between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_bam"
    DISPLAY_NAME = "CrossMap BAM"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "alignment"
    DESCRIPTION = "Lift BAM alignments between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_bam",
        "liftover BAM",
        "coordinate conversion",
        "BAM assembly conversion",
        "chain file",
        "optional BAM tags",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged_bam = f"{out}/input.bam"
        cmd = ["CrossMap", "bam", str(inputs.get("input_chain", ""))]
        if inputs.get("optional_tags"):
            cmd.append("-a")
        cmd.extend(
            [
                "-m",
                str(inputs.get("insert_size", 200.0)),
                "-s",
                str(inputs.get("insert_size_stdev", 30.0)),
                "-t",
                str(inputs.get("insert_size_fold", 3.0)),
                staged_bam,
                f"{out}/output",
            ]
        )
        return " && ".join([_shell_join(["ln", "-sf", str(inputs.get("input", "")), staged_bam]), _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.sorted.bam"]

    @classmethod
    def _validate_nonnegative_number(cls, inputs: dict[str, Any], key: str) -> bool | str:
        value = inputs.get(key)
        if value is None or value == "":
            return True
        try:
            number = float(value)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if number < 0:
            return f"{key} must be greater than or equal to 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input BAM is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        for key in ("insert_size", "insert_size_stdev", "insert_size_fold"):
            result = cls._validate_nonnegative_number(inputs, key)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignments to lift over"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
                "optional_tags": ("BOOLEAN", {"default": False, "description": "Add CrossMap optional BAM mapping tags"}),
                "insert_size": (
                    "FLOAT",
                    {"default": 200.0, "min": 0, "description": "Average paired-end insert size in bp"},
                ),
                "insert_size_stdev": (
                    "FLOAT",
                    {"default": 30.0, "min": 0, "description": "Standard deviation of paired-end insert size"},
                ),
                "insert_size_fold": (
                    "FLOAT",
                    {
                        "default": 3.0,
                        "min": 0,
                        "description": "Proper-pair distance threshold as a multiple of insert-size stdev",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapBigWigContract(ToolsIUCCommandContract):
    """Lift BigWig signal tracks between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_bw"
    DISPLAY_NAME = "CrossMap BigWig"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "genomics"
    DESCRIPTION = "Lift BigWig signal tracks between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_bw",
        "liftover BigWig",
        "coordinate conversion",
        "BigWig assembly conversion",
        "chain file",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["CrossMap", "bigwig", str(inputs.get("input_chain", "")), str(inputs.get("input", "")), f"{out}/output"]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bw"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input BigWig is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BIGWIG", {"description": "BigWig signal track to lift over"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapGffContract(ToolsIUCCommandContract):
    """Lift GFF/GTF feature annotations between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_gff"
    DISPLAY_NAME = "CrossMap GFF"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "annotation"
    DESCRIPTION = "Lift GFF/GTF feature annotations between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_gff",
        "liftover GFF",
        "liftover GTF",
        "coordinate conversion",
        "GFF assembly conversion",
        "GTF assembly conversion",
        "chain file",
    ]
    RETURN_TYPES = ("GFF_GTF",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @staticmethod
    def _include_fails(inputs: dict[str, Any]) -> bool:
        value = inputs.get("include_fails", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_path = f"{_out(inputs)}/output"
        cmd = ["CrossMap", "gff", str(inputs.get("input_chain", "")), str(inputs.get("input", ""))]
        if cls._include_fails(inputs):
            cmd.append(out_path)
        else:
            _add_shell_redirect(cmd, out_path)
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input GFF/GTF is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("GFF_GTF", {"description": "GFF3, GFF, or GTF feature annotation to lift over"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
                "include_fails": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Include failed liftovers in the output with CrossMap fail markers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapRegionContract(ToolsIUCCommandContract):
    """Lift whole BED regions between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_region"
    DISPLAY_NAME = "CrossMap region"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "annotation"
    DESCRIPTION = "Lift whole BED regions between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_region",
        "liftover BED regions",
        "whole region liftover",
        "coordinate conversion",
        "BED assembly conversion",
        "chain file",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    CHROMID_OPTIONS = ["a", "s", "l"]
    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @classmethod
    def _chromid(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("chromid", "a") or "a")

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @staticmethod
    def _ratio(inputs: dict[str, Any]) -> Any:
        return inputs.get("ratio", 0.85)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "CrossMap",
            "region",
            str(inputs.get("input_chain", "")),
            str(inputs.get("input", "")),
            f"{out}/output",
            "--chromid",
            cls._chromid(inputs),
            "--ratio",
            str(cls._ratio(inputs)),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input BED is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        chromid = cls._chromid(inputs)
        if chromid not in cls.CHROMID_OPTIONS:
            return f"chromid must be one of: {', '.join(cls.CHROMID_OPTIONS)}"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        try:
            ratio = float(cls._ratio(inputs))
        except (TypeError, ValueError):
            return "ratio must be a number"
        if ratio < 0 or ratio > 1:
            return "ratio must be between 0 and 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED regions to lift over as whole intervals"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
                "ratio": (
                    "FLOAT",
                    {
                        "default": 0.85,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum ratio of bases that must remap",
                    },
                ),
                "chromid": (
                    "STRING",
                    {
                        "default": "a",
                        "options": cls.CHROMID_OPTIONS,
                        "description": "Chromosome ID style: as-is, short N, or long chrN",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapVcfContract(ToolsIUCCommandContract):
    """Lift VCF variants between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_vcf"
    DISPLAY_NAME = "CrossMap VCF"
    REQUIRED_CONDA_PACKAGES = ["crossmap", "coreutils"]
    CATEGORY = "variant"
    DESCRIPTION = "Lift VCF variants between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_vcf",
        "liftover VCF",
        "variant coordinate conversion",
        "reference allele liftover",
        "VCF assembly conversion",
        "chain file",
    ]
    RETURN_TYPES = ("VCF", "VCF")
    RETURN_NAMES = ("output", "output_unmapped")
    REQUIRED_EXECUTABLES = ["CrossMap", "ln"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    SOURCE_OPTIONS = ["cached", "history"]
    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @classmethod
    def _index_source_s(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source_s", "history") or "history")

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @staticmethod
    def _no_comp_alleles(inputs: dict[str, Any]) -> bool:
        value = inputs.get("no_comp_alleles", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genome_fasta = f"{out}/genome.fasta"
        link_cmd = ["ln", "-s", str(inputs.get("input_fasta", "")), genome_fasta]
        crossmap_cmd = [
            "CrossMap",
            "vcf",
            str(inputs.get("input_chain", "")),
            str(inputs.get("input", "")),
            genome_fasta,
        ]
        if cls._no_comp_alleles(inputs):
            crossmap_cmd.append("--no-comp-alleles")
        crossmap_cmd.append(f"{out}/output")
        return " && ".join([_shell_join(link_cmd), _shell_join(crossmap_cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output", out / "output.unmap"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input VCF is required"
        if not str(inputs.get("input_fasta", "")).strip():
            return "input_fasta FASTA is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        index_source_s = cls._index_source_s(inputs)
        if index_source_s not in cls.SOURCE_OPTIONS:
            return f"index_source_s must be one of: {', '.join(cls.SOURCE_OPTIONS)}"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("VCF", {"description": "VCF variants to lift over"}),
                "input_fasta": ("FASTA", {"description": "Target assembly genome FASTA"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source_s": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.SOURCE_OPTIONS,
                        "description": "Galaxy source selector for input VCF and target FASTA",
                    },
                ),
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
                "no_comp_alleles": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Pass --no-comp-alleles to skip reference/alternate allele comparison",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CrossMapWigContract(ToolsIUCCommandContract):
    """Lift Wiggle signal tracks between genome assemblies with CrossMap."""

    LEGACY_NODE_ID = "crossmap_wig"
    DISPLAY_NAME = "CrossMap Wig"
    REQUIRED_CONDA_PACKAGES = ["crossmap"]
    CATEGORY = "genomics"
    DESCRIPTION = "Lift Wiggle signal tracks between genome assemblies with CrossMap."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CrossMap",
        "crossmap_wig",
        "liftover Wiggle",
        "liftover WIG",
        "coordinate conversion",
        "Wiggle assembly conversion",
        "bedGraph output",
        "chain file",
    ]
    RETURN_TYPES = ("BIGWIG", "BEDGRAPH")
    RETURN_NAMES = ("output", "output_bedgraph")
    REQUIRED_EXECUTABLES = ["CrossMap"]
    DOCUMENTATION_URL = f"{DOI_URL}{CROSSMAP_CITATION_DOI}"
    CITATION_DOIS = [CROSSMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CROSSMAP_CITATION_DOI}"]
    CITATION_TEXT = CROSSMAP_CITATION_TEXT
    VERSION = "0.7.3+galaxy0"
    SHELL = True

    INDEX_SOURCE_OPTIONS = _CrossMapBedContract.INDEX_SOURCE_OPTIONS

    @classmethod
    def _index_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("index_source", "history") or "history")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["CrossMap", "wig", str(inputs.get("input_chain", "")), str(inputs.get("input", "")), f"{out}/output"]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bw", out / "output.sorted.bgr"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input Wiggle is required"
        if not str(inputs.get("input_chain", "")).strip():
            return "input_chain is required"
        index_source = cls._index_source(inputs)
        if index_source not in cls.INDEX_SOURCE_OPTIONS:
            return f"index_source must be one of: {', '.join(cls.INDEX_SOURCE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Wiggle signal track to lift over"}),
                "input_chain": ("TXT", {"description": "LiftOver chain file"}),
            },
            "optional": {
                "index_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.INDEX_SOURCE_OPTIONS,
                        "description": "Galaxy source selector for cached or history chain files",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
