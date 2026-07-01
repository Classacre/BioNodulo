"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class HappySompyNode(CommandNode):
    """Compare truth and query VCFs with hap.py or som.py."""

    NODE_ID = "som.py"
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

class BwaMethNode(CommandNode):
    """Align bisulfite sequencing reads with bwa-meth."""

    NODE_ID = "bwameth"
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

class CrossMapBedNode(CommandNode):
    """Lift BED coordinates between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_bed"
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

class CrossMapBamNode(CommandNode):
    """Lift BAM alignments between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_bam"
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

    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class CrossMapBigWigNode(CommandNode):
    """Lift BigWig signal tracks between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_bw"
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

    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class CrossMapGffNode(CommandNode):
    """Lift GFF/GTF feature annotations between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_gff"
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

    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class CrossMapRegionNode(CommandNode):
    """Lift whole BED regions between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_region"
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
    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class CrossMapVcfNode(CommandNode):
    """Lift VCF variants between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_vcf"
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
    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class CrossMapWigNode(CommandNode):
    """Lift Wiggle signal tracks between genome assemblies with CrossMap."""

    NODE_ID = "crossmap_wig"
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

    INDEX_SOURCE_OPTIONS = CrossMapBedNode.INDEX_SOURCE_OPTIONS

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

class ColumnMakerNode(CommandNode):
    """Compute expressions on tabular rows and add, insert, or replace columns."""

    NODE_ID = "Add_a_column1"
    DISPLAY_NAME = "Compute on rows"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Compute one or more expressions on each tabular row and add, insert, or replace columns."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_maker",
        "Add_a_column1",
        "Compute on rows",
        "computed columns",
        "append columns",
        "insert columns",
        "replace columns",
        "tabular expression",
        "data manipulation",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("out_file1",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = f"{DOI_URL}{COLUMN_MAKER_CITATION_DOI}"
    CITATION_DOIS = [COLUMN_MAKER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{COLUMN_MAKER_CITATION_DOI}"]
    CITATION_TEXT = COLUMN_MAKER_CITATION_TEXT
    VERSION = "2.1+galaxy0"
    SHELL = True

    ADD_COLUMN_MODES = ["", "I", "R"]
    HEADER_OPTIONS = ["no", "yes"]
    NON_COMPUTABLE_ACTIONS = [
        "--fail-on-non-computable",
        "--skip-non-computable",
        "--keep-non-computable",
        "--non-computable-blank",
        "--non-computable-default",
    ]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_file1.tsv"

    @classmethod
    def _actions_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/expressions.txt"

    @classmethod
    def _header_lines_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("header_lines_select", "no") or "no")

    @classmethod
    def _column_types(cls, inputs: dict[str, Any]) -> str:
        column_types = str(inputs.get("column_types", ""))
        if inputs.get("auto_col_types", True):
            return column_types
        return ",".join("str" for _ in column_types.split(","))

    @classmethod
    def _expression_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        expressions = inputs.get("expressions")
        if isinstance(expressions, (list, tuple)) and expressions:
            return [dict(item) for item in expressions if isinstance(item, dict)]
        return [
            {
                "cond": inputs.get("cond", "c3-c2"),
                "mode": inputs.get("add_column_mode", ""),
                "pos": inputs.get("pos", ""),
                "new_column_name": inputs.get("new_column_name", ""),
            }
        ]

    @classmethod
    def _action_spec(cls, item: dict[str, Any]) -> str:
        mode = str(item.get("mode", item.get("add_column_mode", "")) or "")
        pos = str(item.get("pos", "") or "")
        col_add_spec = "" if mode == "" else f"{pos}{mode}"
        return f"{item.get('cond', '')};{col_add_spec};{item.get('new_column_name', '')}"

    @classmethod
    def _action_specs(cls, inputs: dict[str, Any]) -> list[str]:
        return [cls._action_spec(item) for item in cls._expression_items(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        write_actions = ["printf", "%s\\n", *cls._action_specs(inputs)]
        command = f"{_shell_join(['mkdir', '-p', out])} && {_shell_join(write_actions)} > {shlex.quote(cls._actions_path(inputs))}"
        py_cmd = [
            "python",
            str(inputs.get("script_path", "column_maker.py") or "column_maker.py"),
            "--column-types",
            cls._column_types(inputs),
        ]
        if inputs.get("avoid_scientific_notation"):
            py_cmd.append("--avoid-scientific-notation")
        if cls._header_lines_select(inputs) == "yes":
            py_cmd.append("--header")
        py_cmd.extend(["--file", cls._actions_path(inputs)])
        if inputs.get("fail_on_non_existent_columns", True):
            py_cmd.append("--fail-on-non-existent-columns")
        non_computable_action = str(
            inputs.get("non_computable_action", "--fail-on-non-computable") or "--fail-on-non-computable"
        )
        py_cmd.append(non_computable_action)
        if non_computable_action == "--non-computable-default":
            py_cmd.append(str(inputs.get("non_computable_default", "nan") or "nan"))
        py_cmd.extend([str(inputs.get("input", "")), cls._output_path(inputs)])
        return f"{command} && {_shell_join(py_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out_file1.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("column_types", "")).strip():
            return "column_types is required"
        if cls._header_lines_select(inputs) not in cls.HEADER_OPTIONS:
            return f"header_lines_select must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        non_computable_action = str(
            inputs.get("non_computable_action", "--fail-on-non-computable") or "--fail-on-non-computable"
        )
        if non_computable_action not in cls.NON_COMPUTABLE_ACTIONS:
            return f"non_computable_action must be one of: {', '.join(cls.NON_COMPUTABLE_ACTIONS)}"
        for item in cls._expression_items(inputs):
            if not str(item.get("cond", "")).strip():
                return "cond is required for every expression"
            mode = str(item.get("mode", item.get("add_column_mode", "")) or "")
            if mode not in cls.ADD_COLUMN_MODES:
                return f"add_column_mode must be one of: {', '.join(cls.ADD_COLUMN_MODES)}"
            if mode in {"I", "R"}:
                try:
                    pos = int(item.get("pos", 0) or 0)
                except (TypeError, ValueError):
                    return "pos must be an integer when inserting or replacing"
                if pos < 1:
                    return "pos must be at least 1 when inserting or replacing"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Tabular dataset whose rows will receive computed columns"}),
                "column_types": (
                    "STRING",
                    {"description": "Comma-separated Python/Galaxy column types, for example str,int,int,str"},
                ),
            },
            "optional": {
                "expressions": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style expression objects with cond, mode, pos, and new_column_name",
                    },
                ),
                "cond": ("STRING", {"default": "c3-c2", "description": "Single expression used when expressions is empty"}),
                "add_column_mode": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.ADD_COLUMN_MODES,
                        "description": "Append, insert, or replace mode for the single expression",
                    },
                ),
                "pos": ("INT", {"default": 1, "min": 1, "description": "1-based insert/replace column position"}),
                "new_column_name": (
                    "STRING",
                    {"default": "", "description": "Header name for the computed column when header mode is enabled"},
                ),
                "header_lines_select": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.HEADER_OPTIONS,
                        "description": "Whether the input has a header line with column names",
                    },
                ),
                "avoid_scientific_notation": (
                    "BOOLEAN",
                    {"default": False, "description": "Write fully expanded decimal values for new floating-point columns"},
                ),
                "auto_col_types": (
                    "BOOLEAN",
                    {"default": True, "description": "Use supplied Galaxy column types instead of treating all columns as str"},
                ),
                "fail_on_non_existent_columns": (
                    "BOOLEAN",
                    {"default": True, "description": "Fail if an expression references a missing column"},
                ),
                "non_computable_action": (
                    "STRING",
                    {
                        "default": "--fail-on-non-computable",
                        "options": cls.NON_COMPUTABLE_ACTIONS,
                        "description": "How to handle rows where an expression cannot be computed",
                    },
                ),
                "non_computable_default": (
                    "STRING",
                    {"default": "nan", "description": "Replacement value for --non-computable-default"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_maker.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_maker.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CalculateNumericParamNode(BaseNode):
    """Calculate a Galaxy numeric workflow parameter from arithmetic components."""

    NODE_ID = "calculate_numeric_param"
    DISPLAY_NAME = "Calculate numeric parameter value"
    CATEGORY = "data_transform"
    DESCRIPTION = "Calculate an integer or floating-point parameter from simple arithmetic components."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "calculate_numeric_param",
        "Calculate numeric parameter value",
        "numeric parameter",
        "arithmetic parameter",
        "integer parameter",
        "float parameter",
        "workflow expression",
    ]
    RETURN_TYPES = ("FLOAT", "INT")
    RETURN_NAMES = ("float_param", "integer_param")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = CALCULATE_NUMERIC_PARAM_CITATION_URL
    CITATION_URLS = [CALCULATE_NUMERIC_PARAM_CITATION_URL]
    CITATION_TEXT = CALCULATE_NUMERIC_PARAM_CITATION_TEXT
    VERSION = "0.1.0"

    ARITHMETIC_OPERATORS = ["+", "-", "*", "/", "**", "%", ""]
    OUTPUT_TYPES = ["integer", "float"]
    _AST_OPERATORS = (
        ast.Expression,
        ast.BinOp,
        ast.Constant,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
    )

    @classmethod
    def _component_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        components = inputs.get("components")
        if isinstance(components, (list, tuple)):
            return [dict(item) for item in components if isinstance(item, dict)]
        return []

    @classmethod
    def _component_value(cls, component: dict[str, Any]) -> Any:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "component_value" in param_type:
            return param_type["component_value"]
        return component.get("component_value")

    @classmethod
    def _expression(cls, inputs: dict[str, Any]) -> str:
        parts: list[str] = []
        for component in cls._component_items(inputs):
            parts.append(str(cls._component_value(component)))
            operator = str(component.get("arith", "") or "")
            parts.append(operator)
            if operator == "":
                break
        return "".join(parts)

    @classmethod
    def _safe_eval(cls, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("numeric expression is invalid") from exc
        for node in ast.walk(tree):
            if not isinstance(node, cls._AST_OPERATORS):
                raise ValueError("numeric expression contains an unsupported operation")
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                raise ValueError("numeric expression contains a non-numeric value")
        return float(eval(compile(tree, "<calculate_numeric_param>", "eval"), {"__builtins__": {}}, {}))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        components = cls._component_items(inputs)
        if len(components) < 2:
            return "at least two components are required"
        output_type = str(inputs.get("output_type", "integer") or "integer")
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        for component in components:
            try:
                float(cls._component_value(component))
            except (TypeError, ValueError):
                return "component_value must be numeric"
            operator = str(component.get("arith", "") or "")
            if operator not in cls.ARITHMETIC_OPERATORS:
                return f"component arithmetic operator must be one of: {', '.join(cls.ARITHMETIC_OPERATORS)}"
        try:
            cls._safe_eval(cls._expression(inputs))
        except ZeroDivisionError:
            return "division by zero is not allowed"
        except ValueError as exc:
            return str(exc)
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "components": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Galaxy repeat components with component_value and arithmetic operator",
                    },
                ),
            },
            "optional": {
                "component_value": ("FLOAT", {"default": 1.0, "description": "Single numeric component value"}),
                "arith": (
                    "STRING",
                    {
                        "default": "+",
                        "options": cls.ARITHMETIC_OPERATORS,
                        "description": "Arithmetic operator for the single component fallback",
                    },
                ),
                "output_type": (
                    "STRING",
                    {
                        "default": "integer",
                        "options": cls.OUTPUT_TYPES,
                        "description": "Galaxy output type selector",
                    },
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        value = self._safe_eval(self._expression(kwargs))
        if str(kwargs.get("output_type", "integer") or "integer") == "integer":
            value = float(int(value))
        return (value, int(value))

class ComposeTextParamNode(BaseNode):
    """Compose a Galaxy text workflow parameter from repeated components."""

    NODE_ID = "compose_text_param"
    DISPLAY_NAME = "Compose text parameter value"
    CATEGORY = "data_transform"
    DESCRIPTION = "Concatenate text, integer, and float parameters into a workflow text value."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compose_text_param",
        "Compose text parameter value",
        "workflow text parameter",
        "text parameter",
        "integer parameter",
        "float parameter",
        "concatenate parameter values",
    ]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("out1",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = COMPOSE_TEXT_PARAM_CITATION_URL
    CITATION_URLS = [COMPOSE_TEXT_PARAM_CITATION_URL]
    CITATION_TEXT = COMPOSE_TEXT_PARAM_CITATION_TEXT
    VERSION = "0.1.1"

    PARAM_TYPES = ["text", "integer", "float"]

    @classmethod
    def _component_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        components = inputs.get("components")
        if isinstance(components, (list, tuple)):
            return [dict(item) for item in components if isinstance(item, dict)]
        return []

    @classmethod
    def _param_type(cls, component: dict[str, Any]) -> str:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "select_param_type" in param_type:
            return str(param_type["select_param_type"])
        return str(component.get("select_param_type", "text") or "text")

    @classmethod
    def _component_value(cls, component: dict[str, Any]) -> Any:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "component_value" in param_type:
            return param_type["component_value"]
        return component.get("component_value")

    @classmethod
    def _composed_text(cls, inputs: dict[str, Any]) -> str:
        return "".join(str(cls._component_value(component)) for component in cls._component_items(inputs))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        components = cls._component_items(inputs)
        if not components:
            return "at least one component is required"
        for component in components:
            param_type = cls._param_type(component)
            if param_type not in cls.PARAM_TYPES:
                return f"select_param_type must be one of: {', '.join(cls.PARAM_TYPES)}"
            value = cls._component_value(component)
            if value is None:
                return "component_value is required"
            if param_type == "integer":
                try:
                    if int(value) != float(value):
                        return "integer component_value must be an integer"
                except (TypeError, ValueError):
                    return "integer component_value must be an integer"
            elif param_type == "float":
                try:
                    float(value)
                except (TypeError, ValueError):
                    return "float component_value must be numeric"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "components": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Galaxy repeat components with select_param_type and component_value",
                    },
                ),
            },
            "optional": {
                "select_param_type": (
                    "STRING",
                    {
                        "default": "text",
                        "options": cls.PARAM_TYPES,
                        "description": "Parameter type for a single component fallback",
                    },
                ),
                "component_value": ("STRING", {"default": "", "description": "Single component value"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        return (self._composed_text(kwargs),)

class CompressFileNode(CommandNode):
    """Compress a dataset with gzip."""

    NODE_ID = "compress_file"
    DISPLAY_NAME = "Compress file(s)"
    REQUIRED_CONDA_PACKAGES = ["gzip"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Compress a dataset with gzip, preserving the original content in a .gz file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compress_file",
        "Compress file(s)",
        "gzip compression",
        "gzip -cf",
        "gzipped output",
        "compress dataset",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_file",)
    REQUIRED_EXECUTABLES = ["gzip"]
    DOCUMENTATION_URL = COMPRESS_FILE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COMPRESS_FILE_CITATION_URL]
    CITATION_TEXT = COMPRESS_FILE_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_file.gz"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["gzip", "-cf", str(inputs.get("input", "")), ">", cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_file.gz"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Dataset to compress with gzip"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class CollectionColumnJoinNode(CommandNode):
    """Join multiple tabular collection elements on an identifier column."""

    NODE_ID = "collection_column_join"
    DISPLAY_NAME = "Column join"
    REQUIRED_CONDA_PACKAGES = ["coreutils"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Join multiple tabular datasets together on an identifier field."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Column join",
        "collection_column_join",
        "join tabular datasets",
        "identifier column",
        "list collection",
        "coreutils join",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("tabular_output", "script_output")
    REQUIRED_EXECUTABLES = ["sh", "awk", "sort", "join", "paste", "head", "tail"]
    DOCUMENTATION_URL = COLLECTION_COLUMN_JOIN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLLECTION_COLUMN_JOIN_CITATION_URL]
    CITATION_TEXT = COLLECTION_COLUMN_JOIN_CITATION_TEXT
    VERSION = "0.0.3"
    SHELL = True

    OPTIONAL_OUTPUTS = ["output_shell_script"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/tabular_output.tsv"

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/collection_column_join.sh"

    @classmethod
    def _script_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/script_output.txt"

    @classmethod
    def _include_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("include_outputs")
        if isinstance(raw, str):
            return [item.strip() for item in raw.split(",") if item.strip()]
        return _as_list(raw)

    @classmethod
    def _include_shell_script(cls, inputs: dict[str, Any]) -> bool:
        return "output_shell_script" in cls._include_outputs(inputs)

    @classmethod
    def _tabular_items(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw_items = inputs.get("input_tabular")
        if isinstance(raw_items, str):
            items: list[Any] = [item.strip() for item in raw_items.split(",") if item.strip()]
        elif isinstance(raw_items, (list, tuple)):
            items = list(raw_items)
        else:
            items = []

        normalized: list[dict[str, str]] = []
        for item in items:
            if isinstance(item, dict):
                path = next(
                    (
                        str(item[key])
                        for key in ("path", "file", "input", "location")
                        if item.get(key) is not None and str(item[key]).strip()
                    ),
                    "",
                )
                label = next(
                    (
                        str(item[key])
                        for key in ("element_identifier", "name", "identifier", "id")
                        if item.get(key) is not None and str(item[key]).strip()
                    ),
                    Path(path).name,
                )
            else:
                path = str(item)
                label = Path(path).name
            if path:
                normalized.append({"path": path, "label": label})
        return normalized

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], name: str, default: int) -> int:
        return int(inputs.get(name, default))

    @classmethod
    def _awk_text(cls, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def _shell_quote_always(cls, value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @classmethod
    def _script_lines(cls, inputs: dict[str, Any]) -> list[str]:
        identifier_column = cls._positive_int(inputs, "identifier_column", 1)
        has_header = cls._positive_int(inputs, "has_header", 0)
        tail_offset = has_header + 1
        fill_char = str(inputs.get("fill_char", ".") or ".")
        old_col_in_header = bool(inputs.get("old_col_in_header", True))
        literal_tab = "\t"
        lines = [
            "#!/bin/sh",
            "touch header0.tmp &&",
            "touch output0.tmp &&",
        ]
        left_identifier_column = identifier_column
        items = cls._tabular_items(inputs)
        for index, item in enumerate(items):
            path = shlex.quote(item["path"])
            label = cls._awk_text(item["label"])
            if old_col_in_header:
                if has_header:
                    lines.extend(
                        [
                            (
                                f"head -n {has_header} {path} | awk '{{ n = split($0,arr,\"\\t\"); ctr=1; "
                                f"for(i=1;i<=n;i++){{ if( i != {identifier_column} ){{ if( ctr > 1) "
                                f"{{printf(\"\\t\")}}; printf( \"{label}_%s\", arr[i] ); ctr++ }} }}; "
                                'printf( "\\n" ); }\' > input_header.tmp &&'
                            ),
                            (
                                f"tail -n +{tail_offset} {path} | LC_ALL=C sort -t \"{literal_tab}\" -k "
                                f"{identifier_column} > input_file.tmp &&"
                            ),
                        ]
                    )
                else:
                    lines.extend(
                        [
                            (
                                f"awk '{{ n = split($0,arr,\"\\t\"); ctr=1; for(i=1;i<=n;i++){{ "
                                f"if( i != {identifier_column} ){{ if( ctr > 1) {{printf(\"\\t\")}}; "
                                f"printf( \"{label}_%s\", i ); ctr++ }} }}; exit }}' {path} > input_header.tmp &&"
                            ),
                            f"LC_ALL=C sort -t \"{literal_tab}\" -k {identifier_column} {path} > input_file.tmp &&",
                        ]
                    )
            elif has_header:
                lines.extend(
                    [
                        (
                            f"head -n {has_header} {path} | awk '{{ n = split($0,arr,\"\\t\"); ctr=1; "
                            f"for(i=1;i<=n;i++){{ if( i != {identifier_column} ){{ if( ctr > 1) "
                            f"{{printf(\"\\t\")}}; printf( \"{label}\" ); ctr++ }} }}; "
                            'printf( "\\n" ); }\' > input_header.tmp &&'
                        ),
                        (
                            f"tail -n +{tail_offset} {path} | LC_ALL=C sort -t \"{literal_tab}\" -k "
                            f"{identifier_column} > input_file.tmp &&"
                        ),
                    ]
                )
            else:
                lines.extend(
                    [
                        (
                            f"awk '{{ n = split($0,arr,\"\\t\"); ctr=1; for(i=1;i<=n;i++){{ "
                            f"if( i != {identifier_column} ){{ if( ctr > 1) {{printf(\"\\t\")}}; "
                            f"printf( \"{label}\"); ctr++ }} }}; exit }}' {path} > input_header.tmp &&"
                        ),
                        f"LC_ALL=C sort -t \"{literal_tab}\" -k {identifier_column} {path} > input_file.tmp &&",
                    ]
                )

            if index == 0:
                lines.append(f"mv input_file.tmp output{(index + 1) % 2}.tmp &&")
                if has_header:
                    lines.append(f"awk '{{ printf ${identifier_column}; exit }}' {path} > header{index % 2}.tmp &&")
                else:
                    lines.append(f'echo "#KEY" > header{index % 2}.tmp &&')
            else:
                lines.append(
                    f"LC_ALL=C join -o auto -a 1 -a 2 -1 {left_identifier_column} -2 {identifier_column} "
                    f"-t \"{literal_tab}\" -e {cls._shell_quote_always(fill_char)} output{index % 2}.tmp input_file.tmp "
                    f"> output{(index + 1) % 2}.tmp &&"
                )
                left_identifier_column = 1
            lines.append(
                f"paste -d \"{literal_tab}\" header{index % 2}.tmp input_header.tmp > "
                f"header{(index + 1) % 2}.tmp &&"
            )

        final_index = len(items) % 2
        lines.append(f'cat header{final_index}.tmp output{final_index}.tmp > "{cls._output_path(inputs)}"')
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        script_path = cls._script_path(inputs)
        command = (
            f"mkdir -p {shlex.quote(_out(inputs))} && "
            f"cat > {shlex.quote(script_path)} <<'SH'\n"
            + "\n".join(cls._script_lines(inputs))
            + "\nSH\n"
        )
        if cls._include_shell_script(inputs):
            command += f"cp {shlex.quote(script_path)} {shlex.quote(cls._script_output_path(inputs))} && "
        command += f"cd {shlex.quote(_out(inputs))} && sh {shlex.quote(Path(script_path).name)}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "tabular_output.tsv"]
        if cls._include_shell_script(inputs):
            outputs.append(out / "script_output.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(cls._tabular_items(inputs)) < 2:
            return "at least two input_tabular files are required"
        for name, default in (("identifier_column", 1), ("has_header", 0)):
            try:
                value = cls._positive_int(inputs, name, default)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be greater than or equal to 0"
        if not str(inputs.get("fill_char", ".")).strip():
            return "fill_char is required"
        invalid_outputs = [output for output in cls._include_outputs(inputs) if output not in cls.OPTIONAL_OUTPUTS]
        if invalid_outputs:
            return f"include_outputs must be one of: {', '.join(cls.OPTIONAL_OUTPUTS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Tabular collection elements with path and element_identifier metadata",
                    },
                ),
            },
            "optional": {
                "identifier_column": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "description": "One-based column used to join the input datasets",
                    },
                ),
                "has_header": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Number of header lines in each input file"},
                ),
                "old_col_in_header": (
                    "BOOLEAN",
                    {"default": True, "description": "Include original column names in generated headers"},
                ),
                "fill_char": ("STRING", {"default": ".", "description": "Placeholder for empty joined cells"}),
                "include_outputs": (
                    "STRING",
                    {
                        "is_list": True,
                        "default": [],
                        "options": cls.OPTIONAL_OUTPUTS,
                        "description": "Additional datasets to create",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CollectionElementIdentifiersNode(BaseNode):
    """Extract top-level identifiers from collection metadata."""

    NODE_ID = "collection_element_identifiers"
    DISPLAY_NAME = "Extract element identifiers"
    CATEGORY = "data_transform"
    DESCRIPTION = "Extract top-level element identifiers from a list or list:paired collection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "collection_element_identifiers",
        "Extract element identifiers",
        "dataset collection names",
        "element identifiers",
        "list collection",
        "list:paired collection",
        "sample names",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL]
    CITATION_TEXT = COLLECTION_ELEMENT_IDENTIFIERS_CITATION_TEXT
    VERSION = "0.0.3"

    @classmethod
    def _items(cls, inputs: dict[str, Any]) -> list[Any]:
        collection = inputs.get("input_collection")
        if isinstance(collection, (list, tuple)):
            return list(collection)
        return []

    @classmethod
    def _identifier(cls, item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("element_identifier", "name", "identifier", "id"):
                value = item.get(key)
                if value is not None and str(value).strip():
                    return str(value)
        return ""

    @classmethod
    def _output_text(cls, inputs: dict[str, Any]) -> str:
        return "".join(f"{cls._identifier(item)}\n" for item in cls._items(inputs))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        items = cls._items(inputs)
        if not items:
            return "input_collection is required"
        if any(not cls._identifier(item).strip() for item in items):
            return "each collection element requires an identifier"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_collection": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "List or list:paired collection elements with top-level identifiers",
                    },
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        return (self._output_text(kwargs),)

class CalculateContrastThresholdNode(CommandNode):
    """Calculate heatmap contrast thresholds from tag pileup CDT matrices."""

    NODE_ID = "calculate_contrast_threshold"
    DISPLAY_NAME = "Calculate Contrast threshold"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy"]
    CATEGORY = "visualization"
    DESCRIPTION = "Calculate heatmap contrast thresholds from tag pileup CDT matrices."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "calculate_contrast_threshold",
        "Calculate Contrast threshold",
        "tag pileup CDT",
        "heatmap contrast",
        "contrast threshold",
        "calcThreshold.txt",
        "ChIP-QC",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("threshold_output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = CALCULATE_CONTRAST_THRESHOLD_DOCUMENTATION_URL
    CITATION_URLS = CALCULATE_CONTRAST_THRESHOLD_CITATION_URLS
    CITATION_TEXT = CALCULATE_CONTRAST_THRESHOLD_CITATION_TEXT
    VERSION = "1.0.0"
    SHELL = True

    QUANTILE_TYPE_OPTIONS = ["b_option", "t_option"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/threshold_output.txt"

    @classmethod
    def _quantile_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("quantile_type_selector", "b_option") or "b_option")

    @classmethod
    def _header_value(cls, inputs: dict[str, Any]) -> str:
        return "T" if inputs.get("header", True) else "F"

    @classmethod
    def _numeric_at_least(
        cls, inputs: dict[str, Any], name: str, default: int | float, minimum: int | float, *, integer: bool
    ) -> bool | str:
        raw = inputs.get(name, default)
        try:
            value = int(raw) if integer else float(raw)
        except (TypeError, ValueError):
            return f"{name} must be {'an integer' if integer else 'numeric'}"
        if value < minimum:
            return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "python",
            str(inputs.get("script_path", "calculate_contrast_threshold.py") or "calculate_contrast_threshold.py"),
            "-i",
            str(inputs.get("input_file", "")),
        ]
        if cls._quantile_type(inputs) == "t_option":
            cmd.extend(["-t", str(inputs.get("quantile2", 0.0))])
        else:
            cmd.extend(["-q", str(inputs.get("quantile", 95.0)), "-m", str(inputs.get("min_contrast", 0.0))])
        cmd.extend(
            [
                "-d",
                cls._header_value(inputs),
                "-s",
                str(inputs.get("start_col", 2)),
                "-r",
                str(inputs.get("row_num", 600)),
                "-l",
                str(inputs.get("col_num", 300)),
            ]
        )
        return (
            f"{_shell_join(['mkdir', '-p', out])} && "
            f"cd {shlex.quote(out)} && "
            f"{_shell_join(cmd)} && "
            f"{_shell_join(['cp', 'calcThreshold.txt', cls._output_path(inputs)])}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "threshold_output.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        quantile_type = cls._quantile_type(inputs)
        if quantile_type not in cls.QUANTILE_TYPE_OPTIONS:
            return f"quantile_type_selector must be one of: {', '.join(cls.QUANTILE_TYPE_OPTIONS)}"
        for name, default in [("start_col", 2), ("row_num", 600), ("col_num", 300)]:
            result = cls._numeric_at_least(inputs, name, default, 1, integer=True)
            if result is not True:
                return result
        if quantile_type == "t_option":
            result = cls._numeric_at_least(inputs, "quantile2", 0.0, 0, integer=False)
            if result is not True:
                return result
        else:
            try:
                quantile = float(inputs.get("quantile", 95.0))
            except (TypeError, ValueError):
                return "quantile must be numeric"
            if quantile < 0 or quantile > 100:
                return "quantile must be between 0 and 100"
            result = cls._numeric_at_least(inputs, "min_contrast", 0.0, 0, integer=False)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("TXT", {"description": "Tag pileup CDT data matrix"}),
            },
            "optional": {
                "header": ("BOOLEAN", {"default": True, "description": "Whether the input file has a header row"}),
                "start_col": ("INT", {"default": 2, "min": 1, "description": "1-based valid data start column"}),
                "col_num": ("INT", {"default": 300, "min": 1, "description": "Heatmap plot width in pixels"}),
                "row_num": ("INT", {"default": 600, "min": 1, "description": "Heatmap plot height in pixels"}),
                "quantile_type_selector": (
                    "STRING",
                    {
                        "default": "b_option",
                        "options": cls.QUANTILE_TYPE_OPTIONS,
                        "description": "Calculate thresholds from data or enforce an absolute threshold",
                    },
                ),
                "quantile": ("FLOAT", {"default": 95.0, "min": 0, "max": 100, "description": "Percentile threshold"}),
                "min_contrast": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "description": "Minimum upper limit after quantile calculation",
                    },
                ),
                "quantile2": (
                    "FLOAT",
                    {"default": 0.0, "min": 0, "description": "Absolute tag threshold for t_option mode"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "calculate_contrast_threshold.py",
                        "advanced": True,
                        "description": "Path to the Galaxy calculate_contrast_threshold.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CoverageReportNode(CommandNode):
    """Create panel coverage reports from BAM alignments and target BED regions."""

    NODE_ID = "CoverageReport2"
    DISPLAY_NAME = "Panel Coverage Report"
    REQUIRED_CONDA_PACKAGES = [
        "perl-number-format",
        "r-base",
        "bedtools",
        "samtools",
        "tectonic",
        "libcurl",
        "openssl",
    ]
    CATEGORY = "qc"
    DESCRIPTION = "Create a PDF panel coverage report with mapping and target-region statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CoverageReport2",
        "Panel Coverage Report",
        "coverage report",
        "mapping statistics",
        "target region coverage",
        "samtools flagstat",
        "coverageBed",
        "panel resequencing",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("output1",)
    REQUIRED_EXECUTABLES = ["perl", "coverageBed", "samtools", "Rscript", "tectonic"]
    DOCUMENTATION_URL = COVERAGE_REPORT_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COVERAGE_REPORT_CITATION_URL]
    CITATION_TEXT = COVERAGE_REPORT_CITATION_TEXT
    VERSION = "0.0.5+galaxy0"
    SHELL = True

    POSITION_LEVEL_OPTIONS = ["", "-s", "-S", "-A", "-L"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output1.pdf"

    @classmethod
    def _position_level(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("PositionLevel", "") or "")

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        sample_name = str(inputs.get("sample_name", "") or "")
        if sample_name:
            return sample_name
        return Path(str(inputs.get("input1", "sample"))).name.rsplit(".", 1)[0]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "perl",
            str(inputs.get("script_path", "CoverageReport.pl") or "CoverageReport.pl"),
            "-b",
            str(inputs.get("input1", "")),
            "-t",
            str(inputs.get("input2", "")),
            "-o",
            cls._output_path(inputs),
        ]
        if inputs.get("perGene", True):
            cmd.append("-r")
        position_level = cls._position_level(inputs)
        if position_level:
            cmd.append(position_level)
        cmd.extend(
            [
                "-m",
                str(inputs.get("threshold", 40)),
                "-f",
                str(inputs.get("frac", 0.2)),
                "-n",
                cls._sample_name(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output1.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        if not str(inputs.get("input2", "")).strip():
            return "input2 is required"
        try:
            threshold = int(inputs.get("threshold", 40))
        except (TypeError, ValueError):
            return "threshold must be an integer"
        if threshold < 0:
            return "threshold must be >= 0"
        try:
            frac = float(inputs.get("frac", 0.2))
        except (TypeError, ValueError):
            return "frac must be a number"
        if frac < 0:
            return "frac must be >= 0"
        if cls._position_level(inputs) not in cls.POSITION_LEVEL_OPTIONS:
            return f"PositionLevel must be one of: {', '.join(cls.POSITION_LEVEL_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("BAM", {"description": "Mapped reads BAM file"}),
                "input2": ("BED", {"description": "Target regions BED file"}),
            },
            "optional": {
                "threshold": (
                    "INT",
                    {"default": 40, "min": 0, "description": "Minimal coverage threshold"},
                ),
                "frac": (
                    "FLOAT",
                    {"default": 0.2, "min": 0, "description": "Fraction of average coverage used in the plot"},
                ),
                "perGene": (
                    "BOOLEAN",
                    {"default": True, "description": "Plot exon coverages grouped by gene in the target BED"},
                ),
                "PositionLevel": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.POSITION_LEVEL_OPTIONS,
                        "description": "Per-exon analysis mode for failed or all exons",
                    },
                ),
                "sample_name": (
                    "STRING",
                    {"default": "", "description": "Sample name printed in the report; defaults to the BAM basename"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "CoverageReport.pl",
                        "advanced": True,
                        "description": "Path to the Galaxy CoverageReport.pl helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ExtractGenomicDnaNode(CommandNode):
    """Fetch genomic DNA from interval or GFF coordinates."""

    NODE_ID = "Extract genomic DNA 1"
    DISPLAY_NAME = "Extract Genomic DNA"
    REQUIRED_CONDA_PACKAGES = ["bx-python", "six", "ucsc-fatotwobit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Fetch genomic DNA in FASTA or interval format from coordinate datasets."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Extract genomic DNA 1",
        "Extract Genomic DNA",
        "extract_genomic_dna",
        "genomic coordinates",
        "interval",
        "GFF",
        "FASTA",
        "twoBit",
        "faToTwoBit",
        "reference genome",
    ]
    RETURN_TYPES = ("FASTA", "FILE")
    RETURN_NAMES = ("output_fasta", "output_interval")
    REQUIRED_EXECUTABLES = ["python", "faToTwoBit"]
    DOCUMENTATION_URL = EXTRACT_GENOMIC_DNA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [EXTRACT_GENOMIC_DNA_CITATION_URL]
    CITATION_TEXT = EXTRACT_GENOMIC_DNA_CITATION_TEXT
    VERSION = "3.0.3+galaxy3"
    SHELL = True

    INPUT_FORMATS = ["interval", "gff"]
    INTERPRET_FEATURE_OPTIONS = ["yes", "no"]
    REFERENCE_GENOME_SOURCES = ["cached", "history"]
    OUTPUT_FORMATS = ["fasta", "interval"]
    FASTA_HEADER_TYPES = ["bedtools_getfasta_default", "char_delimited"]
    FASTA_HEADER_DELIMITERS = ["underscore", "semicolon", "comma", "tilde", "vertical_bar"]

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_format", "interval") or "interval")

    @classmethod
    def _columns(cls, inputs: dict[str, Any]) -> str:
        columns = str(inputs.get("columns", "") or "")
        if columns:
            return columns
        return "1,4,5,7" if cls._input_format(inputs) == "gff" else "1,2,3,6,4"

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_format", "fasta") or "fasta")

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "output.interval" if cls._output_format(inputs) == "interval" else "output.fasta"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = cls._input_format(inputs)
        output_format = cls._output_format(inputs)
        cmd = [
            "mkdir",
            "-p",
            f"{_out(inputs)}/output_dir",
            "&&",
            "python",
            str(inputs.get("script_path", "extract_genomic_dna.py") or "extract_genomic_dna.py"),
            "--input",
            str(inputs.get("input", "")),
            "--genome",
            str(inputs.get("genome", "")),
            "--input_format",
            input_format,
            "--columns",
            cls._columns(inputs),
        ]
        if input_format == "gff":
            cmd.extend(["--interpret_features", str(inputs.get("interpret_features", "yes") or "yes")])
        cmd.extend(
            [
                "--reference_genome_source",
                str(inputs.get("reference_genome_source", "cached") or "cached"),
                "--reference_genome",
                str(inputs.get("reference_genome", "")),
                "--output_format",
                output_format,
            ]
        )
        if output_format == "fasta":
            fasta_header_type = str(
                inputs.get("fasta_header_type", "bedtools_getfasta_default") or "bedtools_getfasta_default"
            )
            cmd.extend(["--fasta_header_type", fasta_header_type])
            if fasta_header_type == "char_delimited":
                cmd.extend(
                    [
                        "--fasta_header_delimiter",
                        str(inputs.get("fasta_header_delimiter", "underscore") or "underscore"),
                    ]
                )
        cmd.extend(["--output", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def _validate_columns(cls, columns: str, expected_count: int, message: str) -> bool | str:
        parts = columns.split(",")
        if len(parts) != expected_count:
            return message
        try:
            values = [int(part) for part in parts]
        except ValueError:
            return message
        if any(value < 1 for value in values):
            return message
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        if not str(inputs.get("reference_genome", "")).strip():
            return "reference_genome is required"
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        columns = cls._columns(inputs)
        if input_format == "gff":
            column_result = cls._validate_columns(
                columns,
                4,
                "columns must contain 4 comma-separated 1-based columns for gff input",
            )
        else:
            column_result = cls._validate_columns(
                columns,
                5,
                "columns must contain 5 comma-separated 1-based columns for interval input",
            )
        if column_result is not True:
            return column_result
        interpret_features = str(inputs.get("interpret_features", "yes") or "yes")
        if interpret_features not in cls.INTERPRET_FEATURE_OPTIONS:
            return f"interpret_features must be one of: {', '.join(cls.INTERPRET_FEATURE_OPTIONS)}"
        reference_genome_source = str(inputs.get("reference_genome_source", "cached") or "cached")
        if reference_genome_source not in cls.REFERENCE_GENOME_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_GENOME_SOURCES)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        fasta_header_type = str(
            inputs.get("fasta_header_type", "bedtools_getfasta_default") or "bedtools_getfasta_default"
        )
        if fasta_header_type not in cls.FASTA_HEADER_TYPES:
            return f"fasta_header_type must be one of: {', '.join(cls.FASTA_HEADER_TYPES)}"
        fasta_header_delimiter = str(inputs.get("fasta_header_delimiter", "underscore") or "underscore")
        if fasta_header_delimiter not in cls.FASTA_HEADER_DELIMITERS:
            return f"fasta_header_delimiter must be one of: {', '.join(cls.FASTA_HEADER_DELIMITERS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "GFF or interval coordinate dataset"}),
                "genome": (
                    "STRING",
                    {"description": "Genome build key normally supplied by Galaxy dataset metadata"},
                ),
                "reference_genome": (
                    "FILE",
                    {"description": "Cached 2bit reference path or history FASTA reference"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "interval",
                        "options": cls.INPUT_FORMATS,
                        "description": "Input coordinate format; Galaxy infers this from dataset datatype",
                    },
                ),
                "columns": (
                    "STRING",
                    {
                        "default": "1,2,3,6,4",
                        "description": "1-based chrom,start,end,strand,name columns for interval or chrom,start,end,strand for GFF",
                    },
                ),
                "interpret_features": (
                    "STRING",
                    {
                        "default": "yes",
                        "options": cls.INTERPRET_FEATURE_OPTIONS,
                        "description": "Group GFF entries into features before extracting sequences",
                    },
                ),
                "reference_genome_source": (
                    "STRING",
                    {
                        "default": "cached",
                        "options": cls.REFERENCE_GENOME_SOURCES,
                        "description": "Use a cached 2bit reference or convert a history FASTA with faToTwoBit",
                    },
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.OUTPUT_FORMATS,
                        "description": "Write extracted sequences as FASTA or append sequence to interval rows",
                    },
                ),
                "fasta_header_type": (
                    "STRING",
                    {
                        "default": "bedtools_getfasta_default",
                        "options": cls.FASTA_HEADER_TYPES,
                        "description": "Header style for FASTA output",
                    },
                ),
                "fasta_header_delimiter": (
                    "STRING",
                    {
                        "default": "underscore",
                        "options": cls.FASTA_HEADER_DELIMITERS,
                        "description": "Delimiter used when FASTA headers are character-delimited",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "extract_genomic_dna.py",
                        "advanced": True,
                        "description": "Path to the Galaxy extract_genomic_dna.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BarcodeSplitterNode(CommandNode):
    """Split FASTQ files into barcode-specific output files."""

    NODE_ID = "barcode_splitter"
    DISPLAY_NAME = "Barcode Splitter"
    REQUIRED_CONDA_PACKAGES = ["barcode_splitter"]
    CATEGORY = "sequence"
    DESCRIPTION = "Split FASTQ reads into barcode-specific files using one or more index reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Barcode Splitter",
        "barcode_splitter",
        "barcode demultiplexing",
        "index reads",
        "FASTQ splitting",
        "barcodes",
        "dual index",
        "split_all",
    ]
    RETURN_TYPES = ("TSV", "DIRECTORY")
    RETURN_NAMES = ("summary", "split_output")
    REQUIRED_EXECUTABLES = ["barcode_splitter"]
    DOCUMENTATION_URL = BARCODE_SPLITTER_CITATION_URL
    CITATION_DOIS = [BARCODE_SPLITTER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BARCODE_SPLITTER_CITATION_DOI}", BARCODE_SPLITTER_CITATION_URL]
    CITATION_TEXT = BARCODE_SPLITTER_CITATION_TEXT
    VERSION = "0.18.4.0"
    SHELL = True

    RUN_TYPES = ["single", "paired", "flexible"]
    FORMATS = ["fastq", "fastqsanger", "fastqsolexa", "fastqillumina"]
    READ_TYPES = ["single", "forward", "reverse", "index", "singleindex", "forwardindex", "reverseindex"]
    INDEX_READ_TYPES = ["index", "singleindex", "forwardindex", "reverseindex"]

    @classmethod
    def _run_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("run_type", "single") or "single")

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "fastq") or "fastq")

    @classmethod
    def _split_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split"

    @classmethod
    def _summary_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/summary.tsv"

    @classmethod
    def _idxfiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("idxfiles"))

    @classmethod
    def _flexible_seqfiles(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        raw = inputs.get("flexible_seqfiles") or []
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @classmethod
    def _single_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get("snglinput", "")), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(2, len(files) + 1)]
        return files, idx_positions, bool(inputs.get("split_all", False))

    @classmethod
    def _paired_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get("fwdinput", "")), str(inputs.get("revinput", "")), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(3, len(files) + 1)]
        return files, idx_positions, bool(inputs.get("split_all", False))

    @classmethod
    def _flexible_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files: list[str] = []
        idx_positions: list[int] = []
        auto_split_all = bool(inputs.get("split_all", False))
        for index, item in enumerate(cls._flexible_seqfiles(inputs), start=1):
            readtype = str(item.get("readtype", "single") or "single")
            files.append(str(item.get("input", "")))
            if readtype in cls.INDEX_READ_TYPES:
                idx_positions.append(index)
                auto_split_all = True
        return files, idx_positions, auto_split_all

    @classmethod
    def _files_and_indexes(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        run_type = cls._run_type(inputs)
        if run_type == "paired":
            return cls._paired_files(inputs)
        if run_type == "flexible":
            return cls._flexible_files(inputs)
        return cls._single_files(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files, idx_positions, auto_split_all = cls._files_and_indexes(inputs)
        split_dir = cls._split_dir(inputs)
        sequence_format = cls._format(inputs)
        cmd = [
            "mkdir",
            "-p",
            split_dir,
            "&&",
            "barcode_splitter",
            "--bcfile",
            str(inputs.get("bcfile", "")),
            "--mismatches",
            str(inputs.get("mismatches", 1)),
            "--galaxy",
        ]
        if inputs.get("barcodes_at_end", False):
            cmd.append("--barcodes_at_end")
        cmd.extend(["--prefix", f"{split_dir}/"])
        cmd.extend(files)
        cmd.append("--idxread")
        cmd.extend(str(position) for position in idx_positions)
        cmd.extend(["--format", sequence_format, "--suffix", f".{sequence_format}"])
        if auto_split_all:
            cmd.append("--split_all")
        cmd.extend([">", cls._summary_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        split_dir = out / "split"
        split_dir.mkdir(parents=True, exist_ok=True)
        return [out / "summary.tsv", split_dir]

    @classmethod
    def _validate_mismatches(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            mismatches = int(inputs.get("mismatches", 1))
        except (TypeError, ValueError):
            return "mismatches must be an integer"
        if mismatches < 0 or mismatches > 2:
            return "mismatches must be between 0 and 2"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("bcfile", "")).strip():
            return "bcfile is required"
        run_type = cls._run_type(inputs)
        if run_type not in cls.RUN_TYPES:
            return f"run_type must be one of: {', '.join(cls.RUN_TYPES)}"
        mismatches_result = cls._validate_mismatches(inputs)
        if mismatches_result is not True:
            return mismatches_result
        sequence_format = cls._format(inputs)
        if sequence_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if run_type == "single":
            if not str(inputs.get("snglinput", "")).strip():
                return "snglinput is required"
            if not cls._idxfiles(inputs):
                return "at least one index read is required"
        elif run_type == "paired":
            if not str(inputs.get("fwdinput", "")).strip():
                return "fwdinput is required"
            if not str(inputs.get("revinput", "")).strip():
                return "revinput is required"
            if not cls._idxfiles(inputs):
                return "at least one index read is required"
        else:
            seqfiles = cls._flexible_seqfiles(inputs)
            if not seqfiles:
                return "flexible_seqfiles must include at least one read"
            has_index = False
            for item in seqfiles:
                if not str(item.get("input", "")).strip():
                    return "flexible_seqfiles entries require input"
                readtype = str(item.get("readtype", "single") or "single")
                if readtype not in cls.READ_TYPES:
                    return f"readtype must be one of: {', '.join(cls.READ_TYPES)}"
                if readtype in cls.INDEX_READ_TYPES:
                    has_index = True
            if not has_index:
                return "at least one index read is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bcfile": (
                    "TSV",
                    {
                        "description": (
                            "Tab-delimited barcode table: sample identifier followed by one or more barcode columns"
                        ),
                    },
                ),
            },
            "optional": {
                "run_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": cls.RUN_TYPES,
                        "description": "Galaxy run interface: single-end, paired-end, or flexible read layout",
                    },
                ),
                "snglinput": ("FASTQ", {"default": "", "description": "Single-end read file for single run mode"}),
                "fwdinput": ("FASTQ", {"default": "", "description": "Forward read file for paired run mode"}),
                "revinput": ("FASTQ", {"default": "", "description": "Reverse read file for paired run mode"}),
                "idxfiles": (
                    "FASTQ_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Index read files supplied after the main read files",
                    },
                ),
                "idxreadnames": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy index read labels used for collection identifiers",
                    },
                ),
                "flexible_seqfiles": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Flexible-mode read objects with input, readtype, and optional readname fields",
                    },
                ),
                "mismatches": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 2,
                        "description": "Number of allowed mismatches per barcode",
                    },
                ),
                "barcodes_at_end": (
                    "BOOLEAN",
                    {"default": False, "description": "Match barcodes at the end of all index sequences"},
                ),
                "split_all": (
                    "BOOLEAN",
                    {"default": False, "description": "Also split index-only files into the output directory"},
                ),
                "format": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": cls.FORMATS,
                        "description": "FASTQ datatype extension used for discovered split files",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsConvertToBinaryBarcodeNode(CommandNode):
    """Convert FASTQ barcode bases into R/Y-space binary barcodes."""

    NODE_ID = "bctools_convert_to_binary_barcode"
    DISPLAY_NAME = "Create binary barcodes"
    REQUIRED_CONDA_PACKAGES = ["bctools"]
    CATEGORY = "sequence"
    DESCRIPTION = "Convert FASTQ barcode reads from nucleotide bases into binary R/Y barcode codes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bctools",
        "Create binary barcodes",
        "bctools_convert_to_binary_barcode",
        "convert_bc_to_binary_RY.py",
        "binary barcodes",
        "RY-space barcodes",
        "UMI",
        "uvCLAP",
        "FLASH",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("barcodes_ry",)
    REQUIRED_EXECUTABLES = ["convert_bc_to_binary_RY.py"]
    DOCUMENTATION_URL = BCTOOLS_CITATION_URL
    CITATION_DOIS = [BCTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BCTOOLS_CITATION_DOI}", BCTOOLS_CITATION_URL]
    CITATION_TEXT = BCTOOLS_CITATION_TEXT
    VERSION = "0.2.2+galaxy2"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/barcodes_ry.fastq"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            str(inputs.get("script_path", "convert_bc_to_binary_RY.py") or "convert_bc_to_binary_RY.py"),
            str(inputs.get("barcodes", "")),
            ">",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "barcodes_ry.fastq"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("barcodes", "")).strip():
            return "barcodes is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "barcodes": ("FASTQ", {"description": "FASTQ file containing barcode reads to convert"}),
            },
            "optional": {
                "script_path": (
                    "FILE",
                    {
                        "default": "convert_bc_to_binary_RY.py",
                        "advanced": True,
                        "description": "Path to the bctools convert_bc_to_binary_RY.py executable",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsBaseNode(CommandNode):
    """Shared metadata for bctools Galaxy wrappers."""

    REQUIRED_CONDA_PACKAGES = ["bctools"]
    CATEGORY = "sequence"
    REQUIRED_EXECUTABLES: list[str] = []
    DOCUMENTATION_URL = BCTOOLS_CITATION_URL
    CITATION_DOIS = [BCTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BCTOOLS_CITATION_DOI}", BCTOOLS_CITATION_URL]
    CITATION_TEXT = BCTOOLS_CITATION_TEXT
    VERSION = "0.2.2+galaxy2"
    SHELL = True

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("script_path", cls.REQUIRED_EXECUTABLES[0]) or cls.REQUIRED_EXECUTABLES[0])

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _plan_paths(cls, output_dir: str | Path, *filenames: str) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / filename for filename in filenames]

    @classmethod
    def _script_input(cls) -> tuple[str, dict[str, Any]]:
        return (
            "FILE",
            {
                "default": cls.REQUIRED_EXECUTABLES[0],
                "advanced": True,
                "description": f"Path to the bctools {cls.REQUIRED_EXECUTABLES[0]} executable",
            },
        )

    @classmethod
    def _base_aliases(cls, *aliases: str) -> list[str]:
        return [BIONODULO_BUILTIN_ALIAS, "bctools", *aliases, "UMI", "barcodes"]

class BctoolsExtractCrosslinkedNucleotidesNode(_BctoolsBaseNode):
    """Calculate crosslinked nucleotide positions from alignment BED intervals."""

    NODE_ID = "bctools_extract_crosslinked_nucleotides"
    DISPLAY_NAME = "Get crosslinked nucleotides"
    DESCRIPTION = "Calculate crosslinked nucleotide BED coordinates from aligned-read BED intervals."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Get crosslinked nucleotides",
        "bctools_extract_crosslinked_nucleotides",
        "coords2clnt.py",
        "crosslinking coordinates",
        "threeprime",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("crosslinking_coordinates",)
    REQUIRED_EXECUTABLES = ["coords2clnt.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "crosslinking_coordinates.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls._script(inputs)]
        if inputs.get("threeprime", False):
            cmd.append("--threeprime")
        cmd.extend([str(inputs.get("alignment_coordinates", "")), ">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "crosslinking_coordinates.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignment_coordinates", "")).strip():
            return "alignment_coordinates is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"alignment_coordinates": ("BED", {"description": "BED alignments"})},
            "optional": {
                "threeprime": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Set crosslink site one nucleotide downstream of the 3-prime end",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsExtractAlignmentEndsNode(_BctoolsBaseNode):
    """Extract outer alignment coordinates from SAM or BAM."""

    NODE_ID = "bctools_extract_alignment_ends"
    DISPLAY_NAME = "Extract alignment ends"
    DESCRIPTION = "Extract outer alignment-end coordinates from paired SAM or BAM alignments into BED."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Extract alignment ends",
        "bctools_extract_alignment_ends",
        "extract_aln_ends.py",
        "SAM",
        "BAM",
        "outer coordinates",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("alignment_ends",)
    REQUIRED_EXECUTABLES = ["extract_aln_ends.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "alignment_ends.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls._script(inputs), str(inputs.get("alignments", "")), ">", cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "alignment_ends.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments", "")).strip():
            return "alignments is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"alignments": ("FILE", {"description": "SAM or BAM alignments"})},
            "optional": {"script_path": cls._script_input()},
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsExtractBarcodesNode(_BctoolsBaseNode):
    """Extract barcodes from FASTQ reads according to an X/N pattern."""

    NODE_ID = "bctools_extract_barcodes"
    DISPLAY_NAME = "Extract barcodes"
    DESCRIPTION = "Extract barcode nucleotides from FASTQ reads according to an X/N pattern."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Extract barcodes",
        "bctools_extract_barcodes",
        "extract_bcs.py",
        "barcode pattern",
        "cleaned reads",
    )
    RETURN_TYPES = ("FASTQ", "FASTQ")
    RETURN_NAMES = ("reads_cleaned", "extracted_barcodes")
    REQUIRED_EXECUTABLES = ["extract_bcs.py"]

    @classmethod
    def _reads_cleaned_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "reads_cleaned.fastq")

    @classmethod
    def _extracted_barcodes_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "extracted_barcodes.fastq")

    @classmethod
    def _barcode_pattern(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("barcode_pattern", "") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls._script(inputs), str(inputs.get("reads", ""))]
        barcode_pattern = cls._barcode_pattern(inputs)
        if barcode_pattern:
            cmd.append(barcode_pattern)
        cmd.extend(["--bcs", cls._extracted_barcodes_path(inputs), ">", cls._reads_cleaned_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "reads_cleaned.fastq", "extracted_barcodes.fastq")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads", "")).strip():
            return "reads is required"
        barcode_pattern = cls._barcode_pattern(inputs)
        if any(char not in {"X", "N"} for char in barcode_pattern):
            return "barcode_pattern must contain only X and N"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reads": ("FASTQ", {"description": "Barcoded FASTQ reads"})},
            "optional": {
                "barcode_pattern": (
                    "STRING",
                    {
                        "default": "",
                        "pattern": "^[XN]*$",
                        "description": "5-prime pattern where X bases are extracted and N bases are retained",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsMergePcrDuplicatesNode(_BctoolsBaseNode):
    """Merge PCR duplicates by unique molecular identifier."""

    NODE_ID = "bctools_merge_pcr_duplicates"
    DISPLAY_NAME = "Merge PCR duplicates"
    REQUIRED_CONDA_PACKAGES = ["bctools", "coreutils"]
    DESCRIPTION = "Merge PCR duplicates from BED alignments according to FASTQ unique molecular identifiers."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Merge PCR duplicates",
        "bctools_merge_pcr_duplicates",
        "merge_pcr_duplicates.py",
        "PCR duplicates",
        "unique molecular identifiers",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("events",)
    REQUIRED_EXECUTABLES = ["merge_pcr_duplicates.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "events.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("alignments_bed", "")),
                str(inputs.get("barcode_library", "")),
                "--outfile",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "events.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments_bed", "")).strip():
            return "alignments_bed is required"
        if not str(inputs.get("barcode_library", "")).strip():
            return "barcode_library is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignments_bed": ("BED", {"description": "BED6 alignments with read IDs"}),
                "barcode_library": ("FASTQ", {"description": "FASTQ UMI barcode library"}),
            },
            "optional": {"script_path": cls._script_input()},
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsRemoveTailNode(_BctoolsBaseNode):
    """Remove a fixed-length 3-prime tail from FASTQ reads."""

    NODE_ID = "bctools_remove_tail"
    DISPLAY_NAME = "Remove 3'-end nts"
    DESCRIPTION = "Remove a fixed number of nucleotides from the 3-prime tails of FASTQ reads."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Remove 3'-end nts",
        "bctools_remove_tail",
        "remove_tail.py",
        "3-prime tail",
        "FASTQ trimming",
    )
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("default",)
    REQUIRED_EXECUTABLES = ["remove_tail.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "default.fastq")

    @classmethod
    def _length(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("length", 0)
        if value is None or value == "":
            value = 0
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("reads_fastq", "")),
                str(cls._length(inputs)),
                ">",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "default.fastq")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads_fastq", "")).strip():
            return "reads_fastq is required"
        try:
            length = cls._length(inputs)
        except (TypeError, ValueError):
            return "length must be an integer"
        if length < 0:
            return "length must be >= 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reads_fastq": ("FASTQ", {"description": "FASTQ reads"})},
            "optional": {
                "length": ("INT", {"default": 0, "min": 0, "description": "Number of 3-prime bases to remove"}),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BctoolsRemoveSpuriousEventsNode(_BctoolsBaseNode):
    """Remove low-support crosslinking events caused by UMI errors."""

    NODE_ID = "bctools_remove_spurious_events"
    DISPLAY_NAME = "Remove spurious"
    REQUIRED_CONDA_PACKAGES = ["bctools", "coreutils"]
    DESCRIPTION = "Remove spurious crosslinking events caused by UMI errors from BED intervals."
    SEARCH_ALIASES = _BctoolsBaseNode._base_aliases(
        "Remove spurious",
        "bctools_remove_spurious_events",
        "rm_spurious_events.py",
        "spurious events",
        "crosslinking events",
        "threshold",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("events_filtered",)
    REQUIRED_EXECUTABLES = ["rm_spurious_events.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "events_filtered.bed")

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> float:
        value = inputs.get("threshold", 0.1)
        if value is None or value == "":
            value = 0.1
        return float(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("events", "")),
                "--threshold",
                str(cls._threshold(inputs)),
                "--outfile",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "events_filtered.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("events", "")).strip():
            return "events is required"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return "threshold must be a number"
        if threshold < 0:
            return "threshold must be >= 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"events": ("BED", {"description": "BED6 crosslinking events"})},
            "optional": {
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.1,
                        "min": 0,
                        "description": "Fraction of the maximum count used to remove low-support events",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BlastxmlToGappedGff3Node(CommandNode):
    """Convert BLAST XML alignments into gapped GFF3 features."""

    NODE_ID = "blastxml_to_gapped_gff3"
    DISPLAY_NAME = "BlastXML to gapped GFF3"
    REQUIRED_CONDA_PACKAGES = ["bcbiogff"]
    CATEGORY = "annotation"
    DESCRIPTION = "Convert BLAST XML alignments into GFF3 features with Gap attributes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "blastxml_to_gapped_gff3",
        "BlastXML",
        "gapped GFF3",
        "BLAST XML",
        "match_part",
        "Gap",
        "GFF3",
    ]
    RETURN_TYPES = ("GFF3",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = BLASTXML_TO_GAPPED_GFF3_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BLASTXML_TO_GAPPED_GFF3_CITATION_URL]
    CITATION_TEXT = BLASTXML_TO_GAPPED_GFF3_CITATION_TEXT
    VERSION = "1.1"
    SHELL = True

    TRIM_OPTIONS = ["", "--trim", "--trim_end"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.gff3"

    @classmethod
    def _min_gap(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("min_gap", 3)
        if value is None or value == "":
            value = 3
        return int(value)

    @classmethod
    def _trim(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("trim", "--trim_end") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "blastxml_to_gapped_gff3.py") or "blastxml_to_gapped_gff3.py"),
            str(inputs.get("blastxml", "")),
            "--min_gap",
            str(cls._min_gap(inputs)),
        ]
        trim = cls._trim(inputs)
        if trim:
            cmd.append(trim)
        cmd.extend([">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.gff3"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("blastxml", "")).strip():
            return "blastxml is required"
        try:
            min_gap = cls._min_gap(inputs)
        except (TypeError, ValueError):
            return "min_gap must be an integer"
        if min_gap < 0:
            return "min_gap must be >= 0"
        trim = cls._trim(inputs)
        if trim not in cls.TRIM_OPTIONS:
            return f"trim must be one of: {', '.join(cls.TRIM_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "blastxml": ("FILE", {"description": "BLAST XML alignment results"}),
            },
            "optional": {
                "min_gap": (
                    "INT",
                    {
                        "default": 3,
                        "min": 0,
                        "description": "Maximum gap size before generating a new match_part",
                    },
                ),
                "trim": (
                    "STRING",
                    {
                        "default": "--trim_end",
                        "options": cls.TRIM_OPTIONS,
                        "description": "Trim neither end, both ends, or only the alignment end",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "blastxml_to_gapped_gff3.py",
                        "advanced": True,
                        "description": "Path to the Galaxy blastxml_to_gapped_gff3.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CatBaseNode(CommandNode):
    """Shared metadata for CAT/BAT Galaxy wrappers."""

    REQUIRED_CONDA_PACKAGES = ["cat"]
    CATEGORY = "taxonomy"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAT",
        "BAT",
        "Contig Annotation Tool",
        "Bin Annotation Tool",
        "taxonomic classification",
        "metagenomics",
    ]
    REQUIRED_EXECUTABLES = ["CAT", "tabpad.py"]
    DOCUMENTATION_URL = CAT_CITATION_URL
    CITATION_DOIS = CAT_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CAT_CITATION_DOIS]
    CITATION_TEXT = CAT_CITATION_TEXT
    VERSION = "5.2.3+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.tsv"

    @classmethod
    def _tabpad_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("tabpad_path", "tabpad.py") or "tabpad.py")

    @classmethod
    def _tabpad_command(cls, inputs: dict[str, Any], input_txt: str) -> list[str]:
        return [cls._tabpad_path(inputs), "-i", input_txt, "-o", cls._output_path(inputs)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.tsv"]

    @classmethod
    def _tabpad_input(cls) -> tuple[str, dict[str, Any]]:
        return (
            "FILE",
            {
                "default": "tabpad.py",
                "advanced": True,
                "description": "Path to the Galaxy CAT tabpad.py helper script",
            },
        )

class _CatClassifyBaseNode(_CatBaseNode):
    """Shared command rendering for CAT contigs and BAT bins workflows."""

    DB_SRC_OPTIONS = ["cached", "history"]
    USE_PREVIOUS_OPTIONS = ["no", "yes"]
    DIAMOND_OPTIONS = ["no", "yes"]
    ADD_NAMES_OPTIONS = ["no", "orf2lca", "classification", "both"]
    SUMMARISE_OPTIONS = ["no", "classification"]
    CLASSIFICATION_OUTPUT_NAME = "contig2classification"
    CLASSIFICATION_SOURCE = "cat_output.contig2classification.tsv"
    CLASSIFICATION_TXT = "cat_output.contig2classification.txt"
    CLASSIFICATION_DESTINATION = "contig2classification.tsv"
    DEFAULT_RANGE = 10
    DEFAULT_FRACTION = 0.5
    DEFAULT_SELECT_OUTPUTS = ["log", "predicted_proteins_faa", "orf2lca", "contig2classification"]
    SELECTABLE_OUTPUTS = [
        "log",
        "predicted_proteins_faa",
        "predicted_proteins_gff",
        "alignment_diamond",
        "orf2lca",
        "contig2classification",
    ]
    BASE_OUTPUT_FILES = {
        "log": ("cat_output.log", "log.txt"),
        "predicted_proteins_faa": ("cat_output.predicted_proteins.faa", "predicted_proteins.faa"),
        "predicted_proteins_gff": ("cat_output.predicted_proteins.gff", "predicted_proteins.gff"),
        "alignment_diamond": ("cat_output.alignment.diamond", "alignment.diamond.tsv"),
        "orf2lca": ("cat_output.ORF2LCA.tsv", "ORF2LCA.tsv"),
        "contig2classification": ("cat_output.contig2classification.tsv", "contig2classification.tsv"),
    }
    DERIVED_OUTPUT_FILES = {
        "orf2lca_names": "ORF2LCA.names.tsv",
        "classification_names": "classification_names.tsv",
        "classification_summary": "classification_summary.tsv",
    }

    @classmethod
    def _bool_input(cls, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        if "select_outputs" not in inputs or inputs.get("select_outputs") is None:
            return list(cls.DEFAULT_SELECT_OUTPUTS)
        value = inputs.get("select_outputs")
        if isinstance(value, str) and "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        return _as_list(value)

    @classmethod
    def _db_src(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("db_src", "cached") or "cached")

    @classmethod
    def _use_previous(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("use_previous", "no") or "no")

    @classmethod
    def _database_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._db_src(inputs) == "history":
            catdb = str(inputs.get("cat_db_extra_files_path", "") or "")
            return f"{catdb}/CAT_database", f"{catdb}/taxonomy"
        return str(inputs.get("database_folder", "") or ""), str(inputs.get("taxonomy_folder", "") or "")

    @classmethod
    def _range_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("range", cls.DEFAULT_RANGE)

    @classmethod
    def _fraction_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("fraction", cls.DEFAULT_FRACTION)

    @classmethod
    def _set_diamond_opts(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("set_diamond_opts", "no") or "no")

    @classmethod
    def _add_names(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("add_names", "no") or "no")

    @classmethod
    def _summarise(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("summarise", "no") or "no")

    @classmethod
    def _out_file(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _base_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        selected = set(cls._selected_outputs(inputs))
        outputs = []
        if "log" in selected:
            outputs.append("log")
        if cls._use_previous(inputs) != "yes":
            for name in ("predicted_proteins_faa", "predicted_proteins_gff", "alignment_diamond"):
                if name in selected:
                    outputs.append(name)
        for name in ("orf2lca", cls.CLASSIFICATION_OUTPUT_NAME):
            if name in selected:
                outputs.append(name)
        return outputs

    @classmethod
    def _derived_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = []
        add_names = cls._add_names(inputs)
        if add_names in {"orf2lca", "both"}:
            outputs.append("orf2lca_names")
        if add_names in {"classification", "both"}:
            outputs.append("classification_names")
        if cls._summarise(inputs) == "classification":
            outputs.append("classification_summary")
        return outputs

    @classmethod
    def _planned_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        return [*cls._base_output_names(inputs), *cls._derived_output_names(inputs)]

    @classmethod
    def _names_options(cls, inputs: dict[str, Any]) -> list[str]:
        options = []
        if cls._bool_input(inputs.get("only_official"), True):
            options.append("--only_official")
        if cls._bool_input(inputs.get("exclude_scores"), False):
            options.append("--exclude_scores")
        return options

    @classmethod
    def _add_names_command(
        cls,
        inputs: dict[str, Any],
        input_file: str,
        output_file: str,
        extra_options: list[str] | None = None,
    ) -> str:
        _database_folder, taxonomy_folder = cls._database_paths(inputs)
        cmd = [
            "CAT",
            "add_names",
            *(extra_options if extra_options is not None else cls._names_options(inputs)),
            "--taxonomy_folder",
            taxonomy_folder,
            "-i",
            input_file,
            "-o",
            output_file,
        ]
        return _shell_join(cmd)

    @classmethod
    def _tabpad_to_output(cls, inputs: dict[str, Any], input_file: str, output_filename: str) -> str:
        return _shell_join(
            [
                cls._tabpad_path(inputs),
                "-i",
                input_file,
                "-o",
                cls._out_file(inputs, output_filename),
            ]
        )

    @classmethod
    def _workflow_setup_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return []

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    @classmethod
    def _after_tabpad_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return []

    @classmethod
    def _tabpad_classification_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls._tabpad_path(inputs), "cat_output.ORF2LCA.txt", cls.CLASSIFICATION_TXT])

    @classmethod
    def _summarise_command(cls, inputs: dict[str, Any], summary_input: str) -> str:
        return _shell_join(
            [
                "CAT",
                "summarise",
                "-c",
                str(inputs.get("contigs_fasta", "")),
                "-i",
                summary_input,
                "-o",
                "classification_summary.txt",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = cls._workflow_command(inputs)
        cmd.extend(
            [
                "--out_prefix",
                "cat_output",
                "--range",
                str(cls._range_value(inputs)),
                "--fraction",
                str(cls._fraction_value(inputs)),
            ]
        )
        if cls._set_diamond_opts(inputs) == "yes":
            if cls._bool_input(inputs.get("sensitive"), False):
                cmd.append("--sensitive")
            block_size = inputs.get("block_size", 2.0)
            index_chunks = inputs.get("index_chunks", 4)
            top = inputs.get("top", 50)
            cmd.extend(["--block_size", str(block_size), "--index_chunks", str(index_chunks)])
            if float(top) < 50:
                cmd.extend(["--I_know_what_Im_doing", "--top", str(top)])

        commands = [
            *cls._workflow_setup_commands(inputs),
            _shell_join(cmd),
            cls._tabpad_classification_command(inputs),
            *cls._after_tabpad_commands(inputs),
        ]

        add_names = cls._add_names(inputs)
        if add_names in {"classification", "both"}:
            commands.append(cls._add_names_command(inputs, cls.CLASSIFICATION_SOURCE, "classification_names.txt"))
            commands.append(cls._tabpad_to_output(inputs, "classification_names.txt", "classification_names.tsv"))
        if add_names in {"orf2lca", "both"}:
            commands.append(cls._add_names_command(inputs, "cat_output.ORF2LCA.tsv", "orf2lca_names.txt"))
            commands.append(cls._tabpad_to_output(inputs, "orf2lca_names.txt", "ORF2LCA.names.tsv"))
        if cls._summarise(inputs) == "classification":
            if add_names in {"classification", "both"} and cls._bool_input(inputs.get("only_official"), True):
                summary_input = cls._out_file(inputs, "classification_names.tsv")
            else:
                summary_input = "classification_offical_names"
                commands.append(
                    cls._add_names_command(
                        inputs,
                        cls.CLASSIFICATION_SOURCE,
                        summary_input,
                        extra_options=["--only_official"],
                    )
                )
            commands.append(cls._summarise_command(inputs, summary_input))
            commands.append(cls._tabpad_to_output(inputs, "classification_summary.txt", "classification_summary.tsv"))

        for output_name in cls._base_output_names(inputs):
            source, destination = cls.BASE_OUTPUT_FILES[output_name]
            commands.append(_shell_join(["cp", source, cls._out_file(inputs, destination)]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        for output_name in cls._planned_output_names(inputs):
            if output_name in cls.BASE_OUTPUT_FILES:
                outputs.append(out / cls.BASE_OUTPUT_FILES[output_name][1])
            else:
                outputs.append(out / cls.DERIVED_OUTPUT_FILES[output_name])
        return outputs

    @classmethod
    def _validate_choice(cls, value: str, name: str, options: list[str]) -> bool | str:
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum or parsed > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def _validate_float_range(
        cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float
    ) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if parsed < minimum or parsed > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("contigs_fasta", "")).strip():
            return "contigs_fasta is required"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        required = cls._validate_required_inputs(inputs)
        if required is not True:
            return required

        db_src = cls._db_src(inputs)
        choice = cls._validate_choice(db_src, "db_src", cls.DB_SRC_OPTIONS)
        if choice is not True:
            return choice
        if db_src == "history":
            if not str(inputs.get("cat_db_extra_files_path", "")).strip():
                return "cat_db_extra_files_path is required when db_src is history"
        else:
            if not str(inputs.get("database_folder", "")).strip():
                return "database_folder is required"
            if not str(inputs.get("taxonomy_folder", "")).strip():
                return "taxonomy_folder is required"

        use_previous = cls._use_previous(inputs)
        choice = cls._validate_choice(use_previous, "use_previous", cls.USE_PREVIOUS_OPTIONS)
        if choice is not True:
            return choice
        if use_previous == "yes":
            if not str(inputs.get("proteins_fasta", "")).strip():
                return "proteins_fasta is required when use_previous is yes"
            if not str(inputs.get("diamond_alignment", "")).strip():
                return "diamond_alignment is required when use_previous is yes"

        for validation in (
            cls._validate_int_range(inputs, "range", cls.DEFAULT_RANGE, 0, 49),
            cls._validate_float_range(inputs, "fraction", cls.DEFAULT_FRACTION, 0, 0.99),
        ):
            if validation is not True:
                return validation

        set_diamond_opts = cls._set_diamond_opts(inputs)
        choice = cls._validate_choice(set_diamond_opts, "set_diamond_opts", cls.DIAMOND_OPTIONS)
        if choice is not True:
            return choice
        if set_diamond_opts == "yes":
            for validation in (
                cls._validate_float_range(inputs, "block_size", 2.0, 1, 10),
                cls._validate_int_range(inputs, "index_chunks", 4, 1, 10),
                cls._validate_int_range(inputs, "top", 50, 1, 50),
            ):
                if validation is not True:
                    return validation

        choice = cls._validate_choice(cls._add_names(inputs), "add_names", cls.ADD_NAMES_OPTIONS)
        if choice is not True:
            return choice
        choice = cls._validate_choice(cls._summarise(inputs), "summarise", cls.SUMMARISE_OPTIONS)
        if choice is not True:
            return choice

        if not cls._planned_output_names(inputs):
            return "at least one selected output is required"
        return True

    @classmethod
    def _common_optional_inputs(cls) -> dict[str, Any]:
        return {
            "db_src": ("STRING", {"default": "cached", "options": cls.DB_SRC_OPTIONS}),
            "cat_db": ("TXT", {"default": "", "description": "CAT prepare history dataset marker"}),
            "cat_db_extra_files_path": (
                "DIRECTORY",
                {"default": "", "description": "Extra files path from a CAT prepare history dataset"},
            ),
            "use_previous": ("STRING", {"default": "no", "options": cls.USE_PREVIOUS_OPTIONS}),
            "proteins_fasta": (
                "FASTA",
                {"default": "", "description": "Previous Prodigal predicted proteins FASTA"},
            ),
            "diamond_alignment": (
                "TSV",
                {"default": "", "description": "Previous DIAMOND alignment table"},
            ),
            "range": (
                "INT",
                {"default": cls.DEFAULT_RANGE, "min": 0, "max": 49, "description": "CAT/BAT range cutoff"},
            ),
            "fraction": (
                "FLOAT",
                {
                    "default": cls.DEFAULT_FRACTION,
                    "min": 0,
                    "max": 0.99,
                    "description": "Bit-score support fraction",
                },
            ),
            "set_diamond_opts": ("STRING", {"default": "no", "options": cls.DIAMOND_OPTIONS}),
            "sensitive": (
                "BOOLEAN",
                {"default": False, "description": "Run DIAMOND in sensitive mode"},
            ),
            "block_size": ("FLOAT", {"default": 2.0, "min": 1, "max": 10}),
            "index_chunks": ("INT", {"default": 4, "min": 1, "max": 10}),
            "top": ("INT", {"default": 50, "min": 1, "max": 50}),
            "add_names": ("STRING", {"default": "no", "options": cls.ADD_NAMES_OPTIONS}),
            "only_official": (
                "BOOLEAN",
                {"default": True, "description": "Only output official taxonomic rank names"},
            ),
            "exclude_scores": (
                "BOOLEAN",
                {"default": False, "description": "Exclude bit-score support scores in lineage columns"},
            ),
            "summarise": ("STRING", {"default": "no", "options": cls.SUMMARISE_OPTIONS}),
            "select_outputs": (
                "STRING",
                {
                    "default": cls.DEFAULT_SELECT_OUTPUTS,
                    "options": cls.SELECTABLE_OUTPUTS,
                    "multiple": True,
                },
            ),
            "tabpad_path": cls._tabpad_input(),
        }

class CatPrepareNode(_CatBaseNode):
    """Prepare CAT reference data for CAT/BAT classification workflows."""

    NODE_ID = "cat_prepare"
    DISPLAY_NAME = "CAT prepare"
    DESCRIPTION = "Prepare CAT reference data for classifying metagenomic contigs or genome assemblies."
    SEARCH_ALIASES = [
        *_CatBaseNode.SEARCH_ALIASES,
        "cat_prepare",
        "CAT prepare",
        "CAT database",
        "CAT reference data",
        "CAT prepare database",
        "NCBI taxonomy",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("cat_db",)
    REQUIRED_EXECUTABLES = ["CAT"]

    @classmethod
    def _database_folder_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs["database_folder"]) if "database_folder" in inputs else "CAT_database"

    @classmethod
    def _taxonomy_folder_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs["taxonomy_folder"]) if "taxonomy_folder" in inputs else "taxonomy"

    @classmethod
    def _database_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._database_folder_name(inputs)}"

    @classmethod
    def _taxonomy_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._taxonomy_folder_name(inputs)}"

    @classmethod
    def _cat_db_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/cat_db.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        database_name = cls._database_folder_name(inputs)
        taxonomy_name = cls._taxonomy_folder_name(inputs)
        database_path = cls._database_path(inputs)
        taxonomy_path = cls._taxonomy_path(inputs)
        setup = _shell_join(["mkdir", "-p", database_path, taxonomy_path])
        marker = (
            "echo CAT_DB $(date '+%Y-%m-%d') "
            f"{shlex.quote(database_name)} {shlex.quote(taxonomy_name)} > {shlex.quote(cls._cat_db_path(inputs))}"
        )
        cmd = [
            "CAT",
            "prepare",
            "--fresh",
            "--database_folder",
            database_path,
            "--taxonomy_folder",
            taxonomy_path,
        ]
        return f"{setup} && {marker} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "cat_db.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._database_folder_name(inputs).strip():
            return "database_folder is required"
        if not cls._taxonomy_folder_name(inputs).strip():
            return "taxonomy_folder is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "database_folder": (
                    "STRING",
                    {"default": "CAT_database", "description": "Prepared CAT database folder name"},
                ),
                "taxonomy_folder": (
                    "STRING",
                    {"default": "taxonomy", "description": "Prepared CAT taxonomy folder name"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CatContigsNode(_CatClassifyBaseNode):
    """Classify metagenomic contigs with CAT taxonomic assignments."""

    NODE_ID = "cat_contigs"
    DISPLAY_NAME = "CAT contigs"
    DESCRIPTION = "Classify metagenomic contigs with CAT taxonomic assignments."
    SEARCH_ALIASES = [
        *_CatBaseNode.SEARCH_ALIASES,
        "cat_contigs",
        "CAT contigs",
        "contig classification",
        "contig2classification",
        "ORF2LCA",
        "predicted_proteins",
        "classification.summary.txt",
    ]
    RETURN_TYPES = ("TXT", "FASTA", "GFF", "TSV", "TSV", "TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = (
        "log",
        "predicted_proteins_faa",
        "predicted_proteins_gff",
        "alignment_diamond",
        "orf2lca",
        "contig2classification",
        "orf2lca_names",
        "classification_names",
        "classification_summary",
    )

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        database_folder, taxonomy_folder = cls._database_paths(inputs)
        cmd = [
            "CAT",
            "contigs",
            "-c",
            str(inputs.get("contigs_fasta", "")),
            "--database_folder",
            database_folder,
            "--taxonomy_folder",
            taxonomy_folder,
        ]
        if cls._use_previous(inputs) == "yes":
            cmd.extend(
                [
                    "--proteins_fasta",
                    str(inputs.get("proteins_fasta", "")),
                    "--diamond_alignment",
                    str(inputs.get("diamond_alignment", "")),
                ]
            )
        return cmd

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("contigs_fasta", "")).strip():
            return "contigs_fasta is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs_fasta": ("FASTA", {"description": "Contigs fasta file"}),
                "database_folder": (
                    "DIRECTORY",
                    {"description": "CAT database folder for cached database mode"},
                ),
                "taxonomy_folder": (
                    "DIRECTORY",
                    {"description": "CAT taxonomy folder for cached database mode"},
                ),
            },
            "optional": {
                **cls._common_optional_inputs(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CatBinsNode(_CatClassifyBaseNode):
    """Classify genome bins with BAT taxonomic assignments."""

    NODE_ID = "cat_bins"
    DISPLAY_NAME = "CAT bins"
    DESCRIPTION = "Classify metagenome-assembled genome bins with BAT taxonomic assignments."
    SEARCH_ALIASES = [
        *_CatBaseNode.SEARCH_ALIASES,
        "cat_bins",
        "CAT bins",
        "CAT bin",
        "BAT",
        "Bin Annotation Tool",
        "bin classification",
        "bin2classification",
        "metagenome assembled genomes",
        "MAGs",
    ]
    RETURN_TYPES = CatContigsNode.RETURN_TYPES
    RETURN_NAMES = (
        "log",
        "predicted_proteins_faa",
        "predicted_proteins_gff",
        "alignment_diamond",
        "orf2lca",
        "bin2classification",
        "orf2lca_names",
        "classification_names",
        "classification_summary",
    )
    CLASSIFICATION_OUTPUT_NAME = "bin2classification"
    CLASSIFICATION_SOURCE = "cat_output.bin2classification.tsv"
    CLASSIFICATION_TXT = "cat_output.bin2classification.txt"
    CLASSIFICATION_DESTINATION = "bin2classification.tsv"
    DEFAULT_RANGE = 5
    DEFAULT_FRACTION = 0.3
    DEFAULT_SELECT_OUTPUTS = ["log", "predicted_proteins_faa", "orf2lca", "bin2classification"]
    SELECTABLE_OUTPUTS = [
        "log",
        "predicted_proteins_faa",
        "predicted_proteins_gff",
        "alignment_diamond",
        "orf2lca",
        "bin2classification",
    ]
    BASE_OUTPUT_FILES = {
        **{
            key: value
            for key, value in _CatClassifyBaseNode.BASE_OUTPUT_FILES.items()
            if key != "contig2classification"
        },
        "bin2classification": ("cat_output.bin2classification.tsv", "bin2classification.tsv"),
    }

    @classmethod
    def _mag_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("mags"))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], mag_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("element_identifiers"))
        return [
            identifiers[index] if index < len(identifiers) and identifiers[index] else Path(path).name
            for index, path in enumerate(mag_files)
        ]

    @staticmethod
    def _galaxy_bin_identifier(value: str) -> str:
        return re.sub(r"[^\s\w\-]", "_", value)

    @classmethod
    def _workflow_setup_commands(cls, inputs: dict[str, Any]) -> list[str]:
        mag_files = cls._mag_files(inputs)
        identifiers = cls._element_identifiers(inputs, mag_files)
        if len(mag_files) > 1:
            commands = [_shell_join(["mkdir", "-p", "inputs"])]
            for mag_file, identifier in zip(mag_files, identifiers, strict=True):
                commands.append(_shell_join(["ln", "-s", mag_file, f"inputs/{cls._galaxy_bin_identifier(identifier)}.FASTA"]))
            return commands
        if not mag_files:
            return []
        return [_shell_join(["ln", "-s", mag_files[0], cls._galaxy_bin_identifier(identifiers[0])])]

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        database_folder, taxonomy_folder = cls._database_paths(inputs)
        mag_files = cls._mag_files(inputs)
        if len(mag_files) > 1:
            cmd = ["CAT", "bins", "-s", ".FASTA", "-b", "inputs"]
        else:
            identifiers = cls._element_identifiers(inputs, mag_files)
            bin_file = cls._galaxy_bin_identifier(identifiers[0]) if identifiers else ""
            cmd = ["CAT", "bin", "-b", bin_file]
        cmd.extend(["--database_folder", database_folder, "--taxonomy_folder", taxonomy_folder])
        if cls._use_previous(inputs) == "yes":
            cmd.extend(
                [
                    "--proteins_fasta",
                    str(inputs.get("proteins_fasta", "")),
                    "--diamond_alignment",
                    str(inputs.get("diamond_alignment", "")),
                ]
            )
        return cmd

    @classmethod
    def _after_tabpad_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if len(cls._mag_files(inputs)) <= 1:
            return []
        return ['(for i in *.concatenated.*; do ln -s "$i" "${i/concatenated./}"; done)']

    @classmethod
    def _tabpad_classification_command(cls, inputs: dict[str, Any]) -> str:
        if len(cls._mag_files(inputs)) <= 1:
            return super()._tabpad_classification_command(inputs)
        return f"{shlex.quote(cls._tabpad_path(inputs))} *.ORF2LCA.txt *.bin2classification.txt"

    @classmethod
    def _summarise_command(cls, inputs: dict[str, Any], summary_input: str) -> str:
        return _shell_join(["CAT", "summarise", "-i", summary_input, "-o", "classification_summary.txt"])

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._mag_files(inputs):
            return "at least one mags value is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mags": (
                    "FASTA",
                    {"multiple": True, "min_items": 1, "description": "Metagenome-assembled genome FASTA files"},
                ),
                "database_folder": (
                    "DIRECTORY",
                    {"description": "CAT database folder for cached database mode"},
                ),
                "taxonomy_folder": (
                    "DIRECTORY",
                    {"description": "CAT taxonomy folder for cached database mode"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy collection element identifiers for MAG files",
                    },
                ),
                **cls._common_optional_inputs(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CatAddNamesNode(_CatBaseNode):
    """Add taxonomic names to CAT or BAT classification outputs."""

    NODE_ID = "cat_add_names"
    DISPLAY_NAME = "CAT add_names"
    DESCRIPTION = "Annotate CAT or BAT classification tables with taxonomic names."
    SEARCH_ALIASES = [
        *_CatBaseNode.SEARCH_ALIASES,
        "cat_add_names",
        "CAT add_names",
        "taxonomic names",
        "official taxonomic ranks",
        "ORF2LCA",
        "contig2classification",
        "bin2classification",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)

    @classmethod
    def _names_txt_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_names.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        names_txt = cls._names_txt_path(inputs)
        cmd = [
            "CAT",
            "add_names",
            "-i",
            str(inputs.get("input", "")),
            "--taxonomy_folder",
            str(inputs.get("taxonomy_folder", "")),
        ]
        if inputs.get("only_official", True):
            cmd.append("--only_official")
        if inputs.get("exclude_scores", False):
            cmd.append("--exclude_scores")
        cmd.extend(["-o", names_txt])
        return f"{_shell_join(cmd)} && {_shell_join(cls._tabpad_command(inputs, names_txt))}"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("taxonomy_folder", "")).strip():
            return "taxonomy_folder is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "CAT or BAT classification table or ORF2LCA output"}),
                "taxonomy_folder": (
                    "DIRECTORY",
                    {"description": "CAT taxonomy folder containing NCBI taxonomy files"},
                ),
            },
            "optional": {
                "only_official": (
                    "BOOLEAN",
                    {"default": True, "description": "Only output official taxonomic rank names"},
                ),
                "exclude_scores": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude bit-score support scores in the lineage columns"},
                ),
                "tabpad_path": cls._tabpad_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CatSummariseNode(_CatBaseNode):
    """Summarise CAT or BAT taxonomic assignments by official name."""

    NODE_ID = "cat_summarise"
    DISPLAY_NAME = "CAT summarise"
    DESCRIPTION = "Summarise CAT or BAT assignments by official taxonomic name."
    SEARCH_ALIASES = [
        *_CatBaseNode.SEARCH_ALIASES,
        "cat_summarise",
        "CAT summarise",
        "classification.summary.txt",
        "number of assignments",
        "taxonomic summary",
        "official taxonomic names",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)

    @classmethod
    def _summary_txt_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_names_summary.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        summary_txt = cls._summary_txt_path(inputs)
        cmd = ["CAT", "summarise"]
        if str(inputs.get("contigs_fasta", "")).strip():
            cmd.extend(["-c", str(inputs.get("contigs_fasta", ""))])
        cmd.extend(["-i", str(inputs.get("input", "")), "-o", summary_txt])
        return f"{_shell_join(cmd)} && {_shell_join(cls._tabpad_command(inputs, summary_txt))}"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Official-name CAT/BAT classification table from CAT add_names"}),
            },
            "optional": {
                "contigs_fasta": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Contigs FASTA used for CAT contigs summaries; optional for BAT bin summaries",
                    },
                ),
                "tabpad_path": cls._tabpad_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CawlignNode(CommandNode):
    """Codon-aware pairwise alignment with cawlign."""

    NODE_ID = "cawlign"
    DISPLAY_NAME = "cawlign"
    REQUIRED_CONDA_PACKAGES = ["cawlign"]
    CATEGORY = "alignment"
    DESCRIPTION = "Codon-aware pairwise alignment of FASTA sequences to a reference."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "cawlign",
        "codon-aware alignment",
        "pairwise alignment",
        "reference alignment",
        "bealign",
        "HXB2_pol",
        "CoV2-S",
        "reverse complement",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["cawlign"]
    DOCUMENTATION_URL = CAWLIGN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [CAWLIGN_CITATION_URL]
    CITATION_TEXT = CAWLIGN_CITATION_TEXT
    VERSION = "0.1.15+galaxy0"
    SHELL = True

    REFERENCE_OPTIONS = [
        "CoV2-E",
        "CoV2-endornase",
        "CoV2-exonuclease",
        "CoV2-helicase",
        "CoV2-leader",
        "CoV2-M",
        "CoV2-methyltransferase",
        "CoV2-N",
        "CoV2-nsp10",
        "CoV2-nsp2",
        "CoV2-nsp3",
        "CoV2-nsp4",
        "CoV2-nsp6",
        "CoV2-nsp7",
        "CoV2-nsp8",
        "CoV2-nsp9",
        "CoV2-ORF10",
        "CoV2-ORF1a",
        "CoV2-ORF1b",
        "CoV2-ORF3a",
        "CoV2-ORF5",
        "CoV2-ORF6",
        "CoV2-ORF7a",
        "CoV2-ORF7b",
        "CoV2-ORF8",
        "CoV2-RdRp",
        "CoV2-S",
        "CoV2-threeC",
        "HXB2_gag",
        "HXB2_int",
        "HXB2_nef",
        "HXB2_pol",
        "HXB2_pr",
        "HXB2_prrt",
        "HXB2_rev",
        "HXB2_rt",
        "HXB2_tat",
        "HXB2_vif",
    ]
    REFERENCE_SOURCE_OPTIONS = ["builtin", "history"]
    DATATYPE_OPTIONS = ["codon", "nucleotide", "protein"]
    SCORING_MATRIX_SOURCE_OPTIONS = ["builtin", "history"]
    BUILTIN_MATRIX_OPTIONS = ["BLOSUM62", "HIV_BETWEEN_F", "NUC4.4"]
    MATRIX_OPTIONS_BY_DATATYPE = {
        "codon": ["BLOSUM62", "HIV_BETWEEN_F"],
        "nucleotide": ["NUC4.4"],
    }
    LOCAL_ALIGNMENT_OPTIONS = ["trim", "global", "local"]
    FORMAT_OPTIONS = ["refmap", "refalign", "pairwise"]
    REVERSE_COMPLEMENT_OPTIONS = ["none", "silent", "annotated"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fasta"

    @classmethod
    def _bool_input(cls, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source", "builtin") or "builtin")

    @classmethod
    def _reference_value(cls, inputs: dict[str, Any]) -> str:
        if cls._reference_source(inputs) == "history":
            return str(inputs.get("reference_history", "") or "")
        return str(inputs.get("reference_builtin", "HXB2_pol") or "HXB2_pol")

    @classmethod
    def _datatype(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("datatype", "codon") or "codon")

    @classmethod
    def _scoring_matrix_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("scoring_matrix_source", "builtin") or "builtin")

    @classmethod
    def _scoring_matrix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("scoring_matrix", "BLOSUM62") or "BLOSUM62")

    @classmethod
    def _choice_validation(cls, value: str, name: str, options: list[str]) -> bool | str:
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "cawlign",
            "-r",
            cls._reference_value(inputs),
            "-s",
            cls._scoring_matrix(inputs),
            "-t",
            cls._datatype(inputs),
            "-l",
            str(inputs.get("local_alignment", "trim") or "trim"),
            "-f",
            str(inputs.get("format", "refmap") or "refmap"),
            "-R",
            str(inputs.get("reverse_complement", "none") or "none"),
        ]
        if cls._bool_input(inputs.get("affine_gap"), False):
            cmd.append("-a")
        if cls._bool_input(inputs.get("write_reference"), False):
            cmd.append("-I")
        cmd.extend([str(inputs.get("fasta", "")), ">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta", "")).strip():
            return "fasta is required"

        reference_source = cls._reference_source(inputs)
        choice = cls._choice_validation(reference_source, "reference_source", cls.REFERENCE_SOURCE_OPTIONS)
        if choice is not True:
            return choice
        if reference_source == "history":
            if not str(inputs.get("reference_history", "")).strip():
                return "reference_history is required when reference_source is history"
        elif cls._reference_value(inputs) not in cls.REFERENCE_OPTIONS:
            return "reference_builtin must be one of the built-in cawlign references"

        datatype = cls._datatype(inputs)
        choice = cls._choice_validation(datatype, "datatype", cls.DATATYPE_OPTIONS)
        if choice is not True:
            return choice

        matrix_source = cls._scoring_matrix_source(inputs)
        choice = cls._choice_validation(matrix_source, "scoring_matrix_source", cls.SCORING_MATRIX_SOURCE_OPTIONS)
        if choice is not True:
            return choice
        if datatype == "protein" and matrix_source == "builtin":
            return "protein alignments require scoring_matrix_source history"
        if matrix_source == "history":
            if not str(inputs.get("scoring_matrix", "")).strip():
                return "scoring_matrix is required when scoring_matrix_source is history"
        else:
            matrix_options = cls.MATRIX_OPTIONS_BY_DATATYPE.get(datatype, [])
            if cls._scoring_matrix(inputs) not in matrix_options:
                return f"scoring_matrix must be one of for {datatype}: {', '.join(matrix_options)}"

        for key, options in (
            ("local_alignment", cls.LOCAL_ALIGNMENT_OPTIONS),
            ("format", cls.FORMAT_OPTIONS),
            ("reverse_complement", cls.REVERSE_COMPLEMENT_OPTIONS),
        ):
            choice = cls._choice_validation(str(inputs.get(key, options[0]) or options[0]), key, options)
            if choice is not True:
                return choice
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Input FASTA file containing sequences to align"}),
            },
            "optional": {
                "reference_source": ("STRING", {"default": "builtin", "options": cls.REFERENCE_SOURCE_OPTIONS}),
                "reference_builtin": (
                    "STRING",
                    {"default": "HXB2_pol", "options": cls.REFERENCE_OPTIONS},
                ),
                "reference_history": (
                    "FASTA",
                    {"default": "", "description": "Custom reference sequence FASTA from history"},
                ),
                "datatype": ("STRING", {"default": "codon", "options": cls.DATATYPE_OPTIONS}),
                "scoring_matrix_source": (
                    "STRING",
                    {"default": "builtin", "options": cls.SCORING_MATRIX_SOURCE_OPTIONS},
                ),
                "scoring_matrix": (
                    "FILE",
                    {
                        "default": "BLOSUM62",
                        "options": cls.BUILTIN_MATRIX_OPTIONS,
                        "description": "Built-in scoring matrix name or custom matrix file",
                    },
                ),
                "local_alignment": ("STRING", {"default": "trim", "options": cls.LOCAL_ALIGNMENT_OPTIONS}),
                "format": ("STRING", {"default": "refmap", "options": cls.FORMAT_OPTIONS}),
                "reverse_complement": (
                    "STRING",
                    {"default": "none", "options": cls.REVERSE_COMPLEMENT_OPTIONS},
                ),
                "affine_gap": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable affine gap scoring"},
                ),
                "write_reference": (
                    "BOOLEAN",
                    {"default": False, "description": "Include the reference sequence in the output"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
