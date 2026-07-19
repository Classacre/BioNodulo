"""Shared Tracy trace analysis contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts import ToolsIUCCommandContract

class _TracyBasecallContract(ToolsIUCCommandContract):
    """Basecall Sanger chromatogram trace files with Tracy."""

    LEGACY_NODE_ID = "tracy_basecall"
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

class _TracyAlignContract(ToolsIUCCommandContract):
    """Align Sanger chromatogram trace files to a reference with Tracy."""

    LEGACY_NODE_ID = "tracy_align"
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

class _TracyAssembleContract(ToolsIUCCommandContract):
    """Assemble overlapping Sanger chromatogram trace files with Tracy."""

    LEGACY_NODE_ID = "tracy_assemble"
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

class _TracyDecomposeContract(ToolsIUCCommandContract):
    """Decompose heterozygous Sanger chromatogram mutations with Tracy."""

    LEGACY_NODE_ID = "tracy_decompose"
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
    OPTION_DEFAULTS = _TracyAlignContract.OPTION_DEFAULTS
    INT_MIN_OPTIONS = _TracyAlignContract.INT_MIN_OPTIONS
    INT_MAX_OPTIONS = _TracyAlignContract.INT_MAX_OPTIONS

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
