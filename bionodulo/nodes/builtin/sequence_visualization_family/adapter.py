"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from .contracts import ToolsIUCCommandContract


class _MappedOutputContract(ToolsIUCCommandContract):
    """Return named artifacts even when wrapper conditions suppress earlier ports."""

    OUTPUT_NAME_BY_BASENAME: dict[str, str] = {}

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        if cls.OUTPUT_NAME_BY_BASENAME:
            mapped: dict[str, Any] = {}
            for path in planned_paths:
                try:
                    output_name = cls.OUTPUT_NAME_BY_BASENAME[path.name]
                except KeyError as exc:
                    raise ValueError(f"{cls.NODE_ID} planned an unknown artifact: {path.name}") from exc
                if output_name in mapped:
                    raise ValueError(f"{cls.NODE_ID} planned duplicate output port: {output_name}")
                mapped[output_name] = path
            return mapped
        return {
            name: path
            for name, path in zip(cls.RETURN_NAMES, planned_paths, strict=False)
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        planned = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in planned])
        return {
            "outputs": {
                name: [str(path) for path in value] if isinstance(value, list) else str(value)
                for name, value in mapped.items()
            }
        }


class _BarrnapContract(_MappedOutputContract):
    """Locate ribosomal RNA genes in FASTA assemblies with barrnap."""

    LEGACY_NODE_ID = "barrnap"
    DISPLAY_NAME = "barrnap"
    REQUIRED_CONDA_PACKAGES = ["barrnap"]
    CATEGORY = "annotation"
    DESCRIPTION = "Locate 5S, 16S, and 23S ribosomal RNA genes in FASTA sequences and emit GFF3 annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "barrnap",
        "BActerial Ribosomal RNA Predictor",
        "rRNA prediction",
        "ribosomal RNA",
        "5S 16S 23S",
        "GFF3 rRNA",
        "NHMMER",
    ]
    RETURN_TYPES = ("GFF", "FASTA")
    RETURN_NAMES = ("rrna_gff", "rrna_sequences")
    REQUIRED_EXECUTABLES = ["barrnap"]
    DOCUMENTATION_URL = BARRNAP_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BARRNAP_CITATION_URL]
    CITATION_TEXT = BARRNAP_CITATION_TEXT
    VERSION = "1.2.2"
    SHELL = True

    KINGDOM_OPTIONS = ["bac", "euk", "mito", "arc"]

    @classmethod
    def _gff_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rrna.gff3"

    @classmethod
    def _fasta_out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rrna_sequences.fasta"

    @classmethod
    def _query_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/query.fa"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "barrnap",
            "--quiet",
            "--threads",
            "${GALAXY_SLOTS:-1}",
            "--reject",
            str(inputs.get("reject", 0.5)),
            "--lencutoff",
            str(inputs.get("lencutoff", 0.8)),
            "--evalue",
            str(inputs.get("evalue", "1e-06")),
        ]
        if inputs.get("incseq"):
            cmd.append("--incseq")
        if inputs.get("outseq"):
            cmd.extend(["--outseq", cls._fasta_out_path(inputs)])
        cmd.extend(["--kingdom", str(inputs.get("kingdom", "bac") or "bac"), cls._query_path(inputs)])
        barrnap_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}")
        return (
            f"ln -s {shlex.quote(str(inputs.get('fasta_file', '')))} {shlex.quote(cls._query_path(inputs))} && "
            f"{barrnap_cmd} > {shlex.quote(cls._gff_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "rrna.gff3"]
        if inputs.get("outseq"):
            outputs.append(out / "rrna_sequences.fasta")
        return outputs

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < 0 or value > 1:
            return f"{key} must be between 0 and 1"
        return True

    @classmethod
    def _validate_float(cls, inputs: dict[str, Any], key: str, default: str) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value <= 0:
            return f"{key} must be greater than 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta_file", "")).strip():
            return "fasta_file is required"
        kingdom = str(inputs.get("kingdom", "bac") or "bac")
        if kingdom not in cls.KINGDOM_OPTIONS:
            return f"kingdom must be one of: {', '.join(cls.KINGDOM_OPTIONS)}"
        for key, default in (("reject", 0.5), ("lencutoff", 0.8)):
            validation = cls._validate_float_range(inputs, key, default)
            if validation is not True:
                return validation
        validation = cls._validate_float(inputs, "evalue", "1e-06")
        if validation is not True:
            return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta_file": ("FASTA", {"description": "FASTA file to scan for ribosomal RNA genes"}),
            },
            "optional": {
                "kingdom": (
                    "STRING",
                    {
                        "default": "bac",
                        "options": cls.KINGDOM_OPTIONS,
                        "description": "Barrnap kingdom model: bacteria, eukaryote, mitochondria, or archaea",
                    },
                ),
                "reject": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Proportional length threshold below which predictions are rejected",
                    },
                ),
                "lencutoff": (
                    "FLOAT",
                    {
                        "default": 0.8,
                        "min": 0,
                        "max": 1,
                        "description": "Proportional length threshold below which predictions are tagged as pseudo",
                    },
                ),
                "evalue": ("FLOAT", {"default": 1e-6, "min": 0, "description": "Similarity e-value cutoff"}),
                "incseq": ("BOOLEAN", {"default": False, "description": "Include original FASTA sequences after a #FASTA tag in the GFF3 output"}),
                "outseq": ("BOOLEAN", {"default": False, "description": "Write predicted rRNA sequences to a FASTA output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _FastaStatsContract(_MappedOutputContract):
    """Display summary statistics for FASTA assemblies with Galaxy's fasta-stats helper."""

    LEGACY_NODE_ID = "fasta-stats"
    DISPLAY_NAME = "Fasta Statistics"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy", "biopython"]
    CATEGORY = "qc"
    DESCRIPTION = "Display summary statistics for a FASTA or Multi-FASTA file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "fasta-stats",
        "Fasta Statistics",
        "FASTA statistics",
        "Multi-FASTA",
        "N50",
        "NG50",
        "GC content",
        "gap stats",
        "BED gaps",
    ]
    RETURN_TYPES = ("TSV", "BED")
    RETURN_NAMES = ("stats_output", "gaps_output")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = FASTA_STATS_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FASTA_STATS_CITATION_URL]
    CITATION_TEXT = FASTA_STATS_CITATION_TEXT
    VERSION = "2.0"
    SHELL = True

    @classmethod
    def _stats_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/stats.tsv"

    @classmethod
    def _gaps_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gaps.bed"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "fasta-stats.py")),
            "--fasta",
            str(inputs.get("fasta", "")),
            "--stats_output",
            cls._stats_path(inputs),
        ]
        if inputs.get("gaps_option"):
            cmd.extend(["--gaps_output", cls._gaps_path(inputs)])
        if inputs.get("genome_size") is not None and str(inputs.get("genome_size")) != "":
            cmd.extend(["--genome_size", str(inputs.get("genome_size"))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "stats.tsv"]
        if inputs.get("gaps_option"):
            outputs.append(out / "gaps.bed")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta", "")).strip():
            return "fasta is required"
        genome_size = inputs.get("genome_size")
        if genome_size is not None and str(genome_size) != "":
            if isinstance(genome_size, bool):
                return "genome_size must be an integer"
            try:
                parsed_genome_size = int(genome_size)
            except (TypeError, ValueError):
                return "genome_size must be an integer"
            if parsed_genome_size < 0:
                return "genome_size must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "FASTA or Multi-FASTA file"}),
            },
            "optional": {
                "genome_size": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Estimated genome size used to calculate NG50",
                    },
                ),
                "gaps_option": (
                    "BOOLEAN",
                    {"default": False, "description": "Generate an optional BED file describing N-gap ranges"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "fasta-stats.py",
                        "advanced": True,
                        "description": "Path to the Galaxy fasta-stats.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ChopperContract(_MappedOutputContract):
    """Filter and trim long-read FASTQ files with Chopper."""

    LEGACY_NODE_ID = "chopper"
    DISPLAY_NAME = "Chopper"
    REQUIRED_CONDA_PACKAGES = ["chopper"]
    CATEGORY = "trimming"
    DESCRIPTION = "Filter and trim long-read FASTQ data with Chopper."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Chopper",
        "chopper",
        "long-read filtering",
        "long-read trimming",
        "Nanopore",
        "PacBio",
        "NanoFilt",
        "NanoLyse",
        "quality filtering",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("fq_filt",)
    REQUIRED_EXECUTABLES = ["chopper", "gzip"]
    DOCUMENTATION_URL = "https://github.com/wdecoster/chopper"
    CITATION_DOIS = [CHOPPER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHOPPER_CITATION_DOI}"]
    CITATION_TEXT = CHOPPER_CITATION_TEXT
    VERSION = "0.13.0"
    SHELL = True

    TRIM_APPROACHES = ["", "fixed-crop", "trim-by-quality", "best-read-segment", "split-by-low-quality"]

    @classmethod
    def _input_is_gzip(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get("input", "")).lower().endswith(".gz")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = ".fastq.gz" if cls._input_is_gzip(inputs) else ".fastq"
        return f"{_out(inputs)}/fq_filt{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chopper",
            "--input",
            str(inputs.get("input", "")),
            "--threads",
            "${GALAXY_SLOTS:-1}",
        ]
        _add_if_value(cmd, "--contam", inputs.get("contam"))
        cmd.extend(["--quality", str(inputs.get("quality", 0))])
        cmd.extend(["--maxqual", str(inputs.get("maxqual", 60))])
        cmd.extend(["--minlength", str(inputs.get("minlength", 1))])
        _add_if_value(cmd, "--maxlength", inputs.get("maxlength"))
        cmd.extend(["--mingc", str(inputs.get("mingc", 0.0))])
        cmd.extend(["--maxgc", str(inputs.get("maxgc", 1.0))])

        trim_approach = str(inputs.get("trim_approach", "") or "")
        if trim_approach:
            cmd.extend(["--trim-approach", trim_approach])
            if trim_approach == "fixed-crop":
                cmd.extend(["--headcrop", str(inputs.get("headcrop", 0))])
                cmd.extend(["--tailcrop", str(inputs.get("tailcrop", 0))])
            elif trim_approach in {"trim-by-quality", "best-read-segment"}:
                cmd.extend(["--cutoff", str(inputs.get("cutoff", 10))])
            elif trim_approach == "split-by-low-quality":
                cmd.extend(["--cutoff", str(inputs.get("cutoff", 10))])
                cmd.extend(["--split-window", str(inputs.get("split_window", 1))])

        if inputs.get("inverse"):
            cmd.append("--inverse")

        chopper_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}")
        output_path = shlex.quote(cls._output_path(inputs))
        if cls._input_is_gzip(inputs):
            return f"{chopper_cmd} | gzip > {output_path}"
        return f"{chopper_cmd} > {output_path}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = ".fastq.gz" if cls._input_is_gzip(inputs) else ".fastq"
        return [out / f"fq_filt{suffix}"]

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        for key, default in (("quality", 0), ("maxqual", 60), ("cutoff", 10)):
            validation = cls._validate_int_range(inputs, key, default, 0, 60)
            if validation is not True:
                return validation
        for key, default in (("minlength", 1), ("maxlength", "")):
            if key == "maxlength" and str(inputs.get(key, "")) == "":
                continue
            validation = cls._validate_int_min(inputs, key, default, 1)
            if validation is not True:
                return validation
        for key, default in (("headcrop", 0), ("tailcrop", 0)):
            validation = cls._validate_int_min(inputs, key, default, 0)
            if validation is not True:
                return validation
        for key, default in (("mingc", 0.0), ("maxgc", 1.0)):
            validation = cls._validate_float_range(inputs, key, default, 0.0, 1.0)
            if validation is not True:
                return validation
        validation = cls._validate_int_min(inputs, "split_window", 1, 1)
        if validation is not True:
            return validation
        trim_approach = str(inputs.get("trim_approach", "") or "")
        if trim_approach not in cls.TRIM_APPROACHES:
            return f"trim_approach must be one of: {', '.join(cls.TRIM_APPROACHES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ", {"description": "Long-read FASTQ file to filter or trim"}),
            },
            "optional": {
                "contam": (
                    "FASTA",
                    {"default": "", "description": "Optional contaminant reference FASTA for NanoLyse-style filtering"},
                ),
                "quality": ("INT", {"default": 0, "min": 0, "max": 60, "description": "Minimum average Phred quality"}),
                "maxqual": ("INT", {"default": 60, "min": 0, "max": 60, "description": "Maximum average Phred quality"}),
                "minlength": ("INT", {"default": 1, "min": 1, "description": "Minimum read length to keep"}),
                "maxlength": ("INT", {"default": "", "min": 1, "description": "Maximum read length to keep"}),
                "mingc": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Minimum read GC fraction"}),
                "maxgc": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "Maximum read GC fraction"}),
                "trim_approach": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TRIM_APPROACHES,
                        "description": "Optional trimming mode applied after filtering",
                    },
                ),
                "headcrop": ("INT", {"default": 0, "min": 0, "description": "Bases to crop from read starts"}),
                "tailcrop": ("INT", {"default": 0, "min": 0, "description": "Bases to crop from read ends"}),
                "cutoff": ("INT", {"default": 10, "min": 0, "max": 60, "description": "Quality cutoff for trimming modes"}),
                "split_window": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Consecutive low-quality bases required before splitting a read",
                    },
                ),
                "inverse": ("BOOLEAN", {"default": False, "description": "Write reads that fail the normal filters"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _Chopin2Contract(_MappedOutputContract):
    """Classify tabular datasets with CHOPIN2 hyperdimensional computing."""

    LEGACY_NODE_ID = "chopin2"
    DISPLAY_NAME = "chopin2"
    REQUIRED_CONDA_PACKAGES = ["chopin2"]
    CATEGORY = "ai"
    DESCRIPTION = "Domain-agnostic supervised learning with hyperdimensional computing."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chopin2",
        "CHOPIN2",
        "hyperdimensional computing",
        "supervised learning",
        "feature selection",
        "backward variable selection",
        "cross-validation",
        "DNA methylation classification",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("summary", "selection")
    REQUIRED_EXECUTABLES = ["chopin2"]
    DOCUMENTATION_URL = "https://github.com/cumbof/chopin2"
    CITATION_DOIS = [CHOPIN2_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHOPIN2_CITATION_DOI}"]
    CITATION_TEXT = CHOPIN2_CITATION_TEXT
    VERSION = "1.0.9.post1+galaxy0"
    SHELL = True

    DATASET_EXTENSIONS = ["csv", "tabular"]

    @classmethod
    def _dataset_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("dataset_ext", "csv") or "csv")

    @classmethod
    def _dataset_identifier(cls, inputs: dict[str, Any]) -> str:
        identifier = str(inputs.get("dataset_identifier", "") or "")
        if identifier:
            return _safe_element_identifier(identifier)
        return _safe_element_identifier(str(inputs.get("dataset", "")))

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        dataset_identifier = cls._dataset_identifier(inputs)
        tab_token = "__CHOPIN2_TAB__"
        cmd = [
            "chopin2",
            "--dataset",
            dataset_identifier,
            "--fieldsep",
            tab_token if cls._dataset_ext(inputs) == "tabular" else ",",
            "--dimensionality",
            str(inputs.get("dimensionality", 10000)),
            "--levels",
            str(inputs.get("levels", 1000)),
            "--retrain",
            str(inputs.get("retrain", 0)),
            "--stop",
            "--crossv_k",
            str(inputs.get("folds", 2)),
        ]
        if cls._bool_flag(inputs.get("enable_fs", False)):
            cmd.extend(
                [
                    "--select_features",
                    "--group_min",
                    str(inputs.get("group_min", 1)),
                    "--accuracy_threshold",
                    str(inputs.get("accuracy_threshold", 60.0)),
                    "--accuracy_uncertainty_perc",
                    str(inputs.get("accuracy_uncertainty_perc", 5.0)),
                ]
            )
        threads = cls._threads(inputs)
        cmd.extend(["--dump", "--cleanup", "--nproc", threads, "--verbose"])
        command = _shell_join(cmd).replace(tab_token, "$'\\t'").replace(shlex.quote(threads), threads)
        return (
            f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && "
            f"{_shell_join(['ln', '-s', str(inputs.get('dataset', '')), dataset_identifier])} && {command}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "summary.txt"]
        if cls._bool_flag(inputs.get("enable_fs", False)):
            outputs.append(out / "selection.txt")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be numeric"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("dataset", "")).strip():
            return "dataset is required"
        dataset_ext = cls._dataset_ext(inputs)
        if dataset_ext not in cls.DATASET_EXTENSIONS:
            return f"dataset_ext must be one of: {', '.join(cls.DATASET_EXTENSIONS)}"
        for key, default, minimum in [
            ("dimensionality", 10000, 100),
            ("levels", 1000, 2),
            ("retrain", 0, 0),
            ("folds", 2, 2),
            ("threads", 4, 1),
        ]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get("enable_fs", False)):
            result = cls._validate_int_min(inputs, "group_min", 1, 1)
            if result is not True:
                return result
            for key, default in {"accuracy_threshold": 60.0, "accuracy_uncertainty_perc": 5.0}.items():
                result = cls._validate_float_range(inputs, key, default, 0.0, 100.0)
                if result is not True:
                    return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "dataset": ("FILE", {"description": "CSV or tabular matrix with observation IDs and class labels"}),
            },
            "optional": {
                "dataset_ext": ("STRING", {"default": "csv", "options": cls.DATASET_EXTENSIONS}),
                "dataset_identifier": (
                    "STRING",
                    {"default": "", "description": "Optional staged dataset filename used by chopin2"},
                ),
                "dimensionality": ("INT", {"default": 10000, "min": 100}),
                "levels": ("INT", {"default": 1000, "min": 2}),
                "retrain": ("INT", {"default": 0, "min": 0}),
                "folds": ("INT", {"default": 2, "min": 2}),
                "enable_fs": ("BOOLEAN", {"default": False, "description": "Enable feature selection"}),
                "group_min": ("INT", {"default": 1, "min": 1}),
                "accuracy_threshold": ("FLOAT", {"default": 60.0, "min": 0, "max": 100}),
                "accuracy_uncertainty_perc": ("FLOAT", {"default": 5.0, "min": 0, "max": 100}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CiteSeqCountContract(_MappedOutputContract):
    """Count CITE-seq and cell-hashing tags from paired FASTQ reads."""

    LEGACY_NODE_ID = "cite_seq_count"
    DISPLAY_NAME = "CITE-seq-Count"
    REQUIRED_CONDA_PACKAGES = [
        "cite-seq-count",
        "python",
        "umi_tools",
        "python-levenshtein",
        "levenshtein",
        "pandas",
        "bzip2",
        "expat",
        "multiprocess",
        "numpy",
        "pysam",
        "scipy",
    ]
    CATEGORY = "single_cell"
    DESCRIPTION = "Count CMO/HTO tags from raw CITE-seq or cell-hashing FASTQ reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CITE-seq-Count",
        "cite_seq_count",
        "CITE-seq",
        "cell hashing",
        "CMO",
        "HTO",
        "hashtag oligo",
        "cell multiplexing oligo",
        "UMI and read counts",
        "raw FASTQ CITE-seq",
    ]
    RETURN_TYPES = ("YAML", "TSV", "TSV", "FILE", "TSV", "TSV", "FILE", "TSV")
    RETURN_NAMES = (
        "report",
        "output_features",
        "output_barcodes",
        "output_matrix",
        "output_features_filtered",
        "output_barcodes_filtered",
        "output_matrix_filtered",
        "dense_output_matrix",
    )
    REQUIRED_EXECUTABLES = ["CITE-seq-Count", "gunzip"]
    DOCUMENTATION_URL = "https://hoohm.github.io/CITE-seq-Count/"
    CITATION_DOIS = [CITE_SEQ_COUNT_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CITE_SEQ_COUNT_CITATION_DOI}"]
    CITATION_TEXT = CITE_SEQ_COUNT_CITATION_TEXT
    VERSION = "1.4.4+galaxy0"
    SHELL = True

    INPUT_TYPES_OPTIONS = ["repeat", "list_paired"]
    CHEMISTRY_OPTIONS = ["v2", "v3", "custom"]
    OUTPUT_MOVES = [
        ("Results/run_report.yaml", "run_report.yaml"),
        ("Results/read_count/features.tsv", "read_count_features.tsv"),
        ("Results/read_count/barcodes.tsv", "read_count_barcodes.tsv"),
        ("Results/read_count/matrix.mtx", "read_count_matrix.mtx"),
        ("Results/umi_count/features.tsv", "umi_count_features.tsv"),
        ("Results/umi_count/barcodes.tsv", "umi_count_barcodes.tsv"),
        ("Results/umi_count/matrix.mtx", "umi_count_matrix.mtx"),
    ]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "repeat") or "repeat")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("input_collection")
        if isinstance(collection, dict):
            return (
                str(collection.get("forward", collection.get("read1", collection.get("reads_1", "")))),
                str(collection.get("reverse", collection.get("read2", collection.get("reads_2", "")))),
            )
        reads = _as_list(collection)
        return reads[0] if reads else "", reads[1] if len(reads) > 1 else ""

    @staticmethod
    def _repeat_reads(value: Any) -> list[str]:
        if isinstance(value, str):
            return [item for item in value.split(",") if item]
        return _as_list(value)

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if cls._input_type(inputs) == "list_paired":
            read1, read2 = cls._paired_collection_reads(inputs)
            return ([read1] if read1 else [], [read2] if read2 else [])
        return cls._repeat_reads(inputs.get("input1")), cls._repeat_reads(inputs.get("input2"))

    @classmethod
    def _chemistry_bases(cls, inputs: dict[str, Any]) -> tuple[int, int, int, int]:
        chemistry = str(inputs.get("chemistry", "v2") or "v2")
        if chemistry == "v3":
            return 1, 16, 17, 28
        if chemistry == "custom":
            return (
                int(inputs.get("cell_barcode_first_base", 1)),
                int(inputs.get("cell_barcode_last_base", 16)),
                int(inputs.get("umi_first_base", 17)),
                int(inputs.get("umi_last_base", 26)),
            )
        return 1, 16, 17, 26

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reads1, reads2 = cls._reads(inputs)
        cell_first, cell_last, umi_first, umi_last = cls._chemistry_bases(inputs)
        threads = cls._threads(inputs)
        cmd = [
            "CITE-seq-Count",
            "--threads",
            threads,
            "--read1",
            ",".join(reads1),
            "--read2",
            ",".join(reads2),
            "--tags",
            str(inputs.get("tags", "")),
            "--cell_barcode_first_base",
            str(cell_first),
            "--cell_barcode_last_base",
            str(cell_last),
            "--umi_first_base",
            str(umi_first),
            "--umi_last_base",
            str(umi_last),
            "--bc_collapsing_dist",
            str(inputs.get("bc_collapsing_dist", 1)),
            "--umi_collapsing_dist",
            str(inputs.get("umi_collapsing_dist", 2)),
        ]
        if cls._bool_flag(inputs.get("no_umi_correction", False)):
            cmd.append("--no_umi_correction")
        cmd.extend(["--expected_cells", str(inputs.get("expected_cells", 3000))])
        if str(inputs.get("whitelist", "")).strip():
            cmd.extend(["--whitelist", str(inputs.get("whitelist", ""))])
        cmd.extend(["--max-error", str(inputs.get("max_error", 2))])
        if int(inputs.get("start_trim", 0)) != 0:
            cmd.extend(["--start-trim", str(inputs.get("start_trim", 0))])
        if cls._bool_flag(inputs.get("sliding_window", False)):
            cmd.append("--sliding-window")
        if cls._bool_flag(inputs.get("dense", False)):
            cmd.append("--dense")
        if int(inputs.get("first_n", 0)) != 0:
            cmd.extend(["--first_n", str(inputs.get("first_n", 0))])
        if cls._bool_flag(inputs.get("unknown_tags_output", False)):
            cmd.extend(["--unknown-top-tags", str(inputs.get("unknown_top_tags", 100))])

        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}"]
        cite_command = _shell_join(cmd).replace(shlex.quote(threads), threads)
        commands.append(cite_command)
        commands.extend(
            _shell_join(["gunzip", path])
            for path in [
                "Results/read_count/barcodes.tsv.gz",
                "Results/read_count/features.tsv.gz",
                "Results/read_count/matrix.mtx.gz",
                "Results/umi_count/barcodes.tsv.gz",
                "Results/umi_count/features.tsv.gz",
                "Results/umi_count/matrix.mtx.gz",
            ]
        )
        commands.extend(_shell_join(["mv", source, target]) for source, target in cls.OUTPUT_MOVES)
        if cls._bool_flag(inputs.get("dense", False)):
            commands.append(_shell_join(["mv", "Results/dense_umis.tsv", "dense_umis.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / target for _, target in cls.OUTPUT_MOVES]
        if cls._bool_flag(inputs.get("dense", False)):
            outputs.append(out / "dense_umis.tsv")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("tags", "")).strip():
            return "tags is required"
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        reads1, reads2 = cls._reads(inputs)
        if input_type == "list_paired":
            if not reads1 or not reads2:
                return "input_collection with forward and reverse reads is required for list_paired input"
        else:
            if not reads1 or not reads2:
                return "input1 and input2 are required for repeat input"
            if len(reads1) != len(reads2):
                return "input1 and input2 must contain the same number of FASTQ files"
        chemistry = str(inputs.get("chemistry", "v2") or "v2")
        if chemistry not in cls.CHEMISTRY_OPTIONS:
            return f"chemistry must be one of: {', '.join(cls.CHEMISTRY_OPTIONS)}"
        if chemistry == "custom":
            for key, default in [
                ("cell_barcode_first_base", 1),
                ("cell_barcode_last_base", 16),
                ("umi_first_base", 17),
                ("umi_last_base", 26),
            ]:
                result = cls._validate_int_min(inputs, key, default, 1)
                if result is not True:
                    return result
        for key, default, minimum in [
            ("bc_collapsing_dist", 1, 0),
            ("umi_collapsing_dist", 2, 0),
            ("expected_cells", 3000, 1),
            ("max_error", 2, 0),
            ("start_trim", 0, 0),
            ("first_n", 0, 0),
            ("threads", 4, 1),
        ]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get("unknown_tags_output", False)):
            result = cls._validate_int_min(inputs, "unknown_top_tags", 100, 1)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "repeat",
                        "options": cls.INPUT_TYPES_OPTIONS,
                        "description": "Use separate repeated barcode/HTO reads or a paired read collection",
                    },
                ),
                "tags": (
                    "CSV",
                    {"description": "CMO/HTO barcode table with sequence in the first column and tag name in the second"},
                ),
            },
            "optional": {
                "input1": (
                    "FASTQ",
                    {"default": [], "is_list": True, "description": "Barcode read 1 FASTQ files for repeat input"},
                ),
                "input2": (
                    "FASTQ",
                    {"default": [], "is_list": True, "description": "HTO/CMO read 2 FASTQ files for repeat input"},
                ),
                "input_collection": (
                    "JSON",
                    {"default": {}, "description": "Paired collection with forward/read1 and reverse/read2 FASTQ entries"},
                ),
                "chemistry": ("STRING", {"default": "v2", "options": cls.CHEMISTRY_OPTIONS}),
                "cell_barcode_first_base": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "cell_barcode_last_base": ("INT", {"default": 16, "min": 1, "advanced": True}),
                "umi_first_base": ("INT", {"default": 17, "min": 1, "advanced": True}),
                "umi_last_base": ("INT", {"default": 26, "min": 1, "advanced": True}),
                "bc_collapsing_dist": ("INT", {"default": 1, "min": 0}),
                "umi_collapsing_dist": ("INT", {"default": 2, "min": 0}),
                "no_umi_correction": ("BOOLEAN", {"default": False, "description": "Deactivate UMI correction"}),
                "expected_cells": ("INT", {"default": 3000, "min": 1}),
                "whitelist": ("FILE", {"default": "", "description": "Optional whitelist of cell barcodes"}),
                "max_error": ("INT", {"default": 2, "min": 0}),
                "start_trim": ("INT", {"default": 0, "min": 0}),
                "sliding_window": ("BOOLEAN", {"default": False}),
                "dense": ("BOOLEAN", {"default": False, "description": "Also emit dense UMI-count TSV output"}),
                "first_n": ("INT", {"default": 0, "min": 0}),
                "unknown_tags_output": ("BOOLEAN", {"default": False, "description": "Write top unmapped tags"}),
                "unknown_top_tags": ("INT", {"default": 100, "min": 1}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CIAlignContract(_MappedOutputContract):
    """Clean, visualise, and interpret multiple sequence alignments with CIAlign."""

    LEGACY_NODE_ID = "cialign"
    DISPLAY_NAME = "CIAlign"
    REQUIRED_CONDA_PACKAGES = ["cialign"]
    CATEGORY = "alignment"
    DESCRIPTION = "Clean, visualise, and interpret multiple sequence alignments with CIAlign."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CIAlign",
        "cialign",
        "multiple sequence alignment",
        "MSA cleaning",
        "alignment visualisation",
        "alignment interpretation",
        "sequence logo",
        "consensus sequence",
        "position weight matrix",
    ]
    RETURN_TYPES = (
        "FASTA",
        "TXT",
        "TXT",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "DIRECTORY",
        "DIRECTORY",
        "FASTA",
        "FASTA",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "FASTA",
        "FASTA",
        "FASTA",
        "FASTA",
        "FASTA",
        "FASTA",
    )
    RETURN_NAMES = (
        "output_cleaned",
        "output_removed",
        "output_log",
        "plot_input",
        "plot_output",
        "plot_markup",
        "plot_markup_legend",
        "plot_consensus_identity",
        "plot_consensus_similarity",
        "logo_bar",
        "logo_text",
        "plot_stats_input",
        "plot_stats_outputs",
        "output_consensus",
        "output_with_consensus",
        "pwm_input",
        "ppm_input",
        "pfm_input",
        "ppm_meme_input",
        "blamm_input",
        "pwm_output",
        "ppm_output",
        "pfm_output",
        "ppm_meme_output",
        "blamm_output",
        "input_similarity",
        "output_similarity",
        "output_output_column_stats",
        "output_input_column_stats",
        "U_input",
        "T_input",
        "U_output",
        "T_output",
        "unaligned_input",
        "unaligned_output",
    )
    REQUIRED_EXECUTABLES = ["CIAlign", "gunzip"]
    DOCUMENTATION_URL = "https://github.com/KatyBrown/CIAlign"
    CITATION_DOIS = [CIALIGN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CIALIGN_CITATION_DOI}"]
    CITATION_TEXT = CIALIGN_CITATION_TEXT
    VERSION = "1.1.4+galaxy1"
    SHELL = True

    OUTPUT_NAME_BY_BASENAME = {
        "output_cleaned.fasta": "output_cleaned",
        "output_removed.txt": "output_removed",
        "output_log.txt": "output_log",
        "output_input.png": "plot_input",
        "output_output.png": "plot_output",
        "output_markup.png": "plot_markup",
        "output_markup_legend.png": "plot_markup_legend",
        "output_consensus_identity.png": "plot_consensus_identity",
        "output_consensus_similarity.png": "plot_consensus_similarity",
        "output_logo_bar.png": "logo_bar",
        "output_logo_text.png": "logo_text",
        "input_stats_plots": "plot_stats_input",
        "output_stats_plots": "plot_stats_outputs",
        "output_consensus.fasta": "output_consensus",
        "output_with_consensus.fasta": "output_with_consensus",
        "output_pwm_input.txt": "pwm_input",
        "output_ppm_input.txt": "ppm_input",
        "output_pfm_input.txt": "pfm_input",
        "output_ppm_meme_input.txt": "ppm_meme_input",
        "output_pfm_blamm_input.txt": "blamm_input",
        "output_pwm_output.txt": "pwm_output",
        "output_ppm_output.txt": "ppm_output",
        "output_pfm_output.txt": "pfm_output",
        "output_ppm_meme_output.txt": "ppm_meme_output",
        "output_pfm_blamm_output.txt": "blamm_output",
        "output_input_similarity.tsv": "input_similarity",
        "output_output_similarity.tsv": "output_similarity",
        "output_output_column_stats.tsv": "output_output_column_stats",
        "output_input_column_stats.tsv": "output_input_column_stats",
        "output_U_input.fasta": "U_input",
        "output_T_input.fasta": "T_input",
        "output_U_output.fasta": "U_output",
        "output_T_output.fasta": "T_output",
        "output_unaligned_input.fasta": "unaligned_input",
        "output_unaligned_output.fasta": "unaligned_output",
    }

    SEQUENCE_LOGO_TYPES = ["bar", "text", "both"]
    CONSENSUS_TYPES = ["majority", "majority_nongap"]
    SIMMATRIX_KEEPGAPS = ["0", "1", "2"]
    DUPORDERS = ["first", "last"]
    SUB_MATRIX_NAMES = ["BLOSUM62", "NUC.4.4"]
    PALETTES = ["CBS"]
    PWM_FREQTYPES = ["user", "equal", "calc", "calc2"]
    PWM_ALPHATYPES = ["user", "calc"]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @staticmethod
    def _values(value: Any) -> list[str]:
        return _as_list(value)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str | None = None) -> None:
        if cls._bool_flag(inputs.get(key, False)):
            cmd.append(flag or f"--{key}")

    @classmethod
    def _add_list(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str) -> None:
        for value in cls._values(inputs.get(key)):
            cmd.extend([flag, value])

    @classmethod
    def _has_any(cls, inputs: dict[str, Any], keys: list[str]) -> bool:
        return any(cls._bool_flag(inputs.get(key, False)) for key in keys)

    @classmethod
    def _basic_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ["all", "clean", "visualise", "interpret"]:
            cls._add_bool(cmd, inputs, key)

    @classmethod
    def _cleaning_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get("remove_divergent", False)):
            cmd.extend(["--remove_divergent", "--remove_divergent_minperc", str(inputs.get("remove_divergent_minperc", 0.65))])
            cls._add_list(cmd, inputs, "remove_divergent_retain", "--remove_divergent_retain")
            cls._add_list(cmd, inputs, "remove_divergent_retain_str", "--remove_divergent_retain_str")
        if cls._bool_flag(inputs.get("remove_insertions", False)):
            cmd.extend(
                [
                    "--remove_insertions",
                    "--insertion_min_size",
                    str(inputs.get("insertion_min_size", 3)),
                    "--insertion_max_size",
                    str(inputs.get("insertion_max_size", 200)),
                    "--insertion_min_flank",
                    str(inputs.get("insertion_min_flank", 5)),
                    "--insertion_min_perc",
                    str(inputs.get("insertion_min_perc", 0.5)),
                ]
            )
        if cls._bool_flag(inputs.get("crop_ends", False)):
            cmd.extend(
                [
                    "--crop_ends",
                    "--crop_ends_mingap_perc",
                    str(inputs.get("crop_ends_mingap_perc", 0.05)),
                    "--crop_ends_redefine_perc",
                    str(inputs.get("crop_ends_redefine_perc", 0.1)),
                ]
            )
            cls._add_list(cmd, inputs, "crop_ends_retain", "--crop_ends_retain")
            cls._add_list(cmd, inputs, "crop_ends_retain_str", "--crop_ends_retain_str")
        if cls._bool_flag(inputs.get("remove_short", False)):
            cmd.extend(["--remove_short", "--remove_min_length", str(inputs.get("remove_min_length", 50))])
            cls._add_list(cmd, inputs, "remove_short_retain", "--remove_short_retain")
            cls._add_list(cmd, inputs, "remove_short_retain_str", "--remove_short_retain_str")
        if cls._bool_flag(inputs.get("crop_divergent", False)):
            cmd.extend(
                [
                    "--crop_divergent",
                    "--crop_divergent_min_prop_ident",
                    str(inputs.get("crop_divergent_min_prop_ident", 0.5)),
                    "--crop_divergent_min_prop_nongap",
                    str(inputs.get("crop_divergent_min_prop_nongap", 0.5)),
                    "--crop_divergent_buffer_size",
                    str(inputs.get("crop_divergent_buffer_size", 5)),
                ]
            )
        cls._add_list(cmd, inputs, "retain", "--retain")
        cls._add_list(cmd, inputs, "retain_str", "--retain_str")
        cls._add_bool(cmd, inputs, "keep_gaponly")

    @classmethod
    def _visualisation_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key in ["plot_input", "plot_output", "plot_markup", "plot_consensus_identity", "plot_consensus_similarity"]:
            cls._add_bool(cmd, inputs, key)
        if cls._bool_flag(inputs.get("output_settings", False)):
            cmd.extend(
                [
                    "--plot_width",
                    str(inputs.get("plot_width", 5)),
                    "--plot_height",
                    str(inputs.get("plot_height", 3)),
                    "--plot_dpi",
                    str(inputs.get("plot_dpi", 300)),
                ]
            )
            cls._add_bool(cmd, inputs, "plot_keep_numbers")
            cls._add_bool(cmd, inputs, "plot_force_numbers")
            cmd.extend(
                [
                    "--plot_identity_palette",
                    str(inputs.get("plot_identity_palette", "bone")),
                    "--plot_identity_gap_col",
                    str(inputs.get("plot_identity_gap_col", "#ffffff")),
                    "--plot_similarity_palette",
                    str(inputs.get("plot_similarity_palette", "bone")),
                    "--plot_similarity_gap_col",
                    str(inputs.get("plot_similarity_gap_col", "#ffffff")),
                    "--plot_sub_matrix_name",
                    str(inputs.get("plot_sub_matrix_name", "NUC.4.4")),
                    "--palette",
                    str(inputs.get("palette", "CBS")),
                ]
            )
        if cls._bool_flag(inputs.get("make_sequence_logo", False)):
            cmd.extend(
                [
                    "--make_sequence_logo",
                    "--sequence_logo_type",
                    str(inputs.get("sequence_logo_type", "text")),
                    "--sequence_logo_dpi",
                    str(inputs.get("sequence_logo_dpi", 300)),
                    "--sequence_logo_font",
                    str(inputs.get("sequence_logo_font", "monospace")),
                    "--sequence_logo_nt_per_row",
                    str(inputs.get("sequence_logo_nt_per_row", 50)),
                ]
            )
            _add_if_value(cmd, "--logo_start", inputs.get("logo_start"))
            _add_if_value(cmd, "--logo_end", inputs.get("logo_end"))
        stats_requested = cls._has_any(inputs, ["plot_stats_input", "plot_stats_output"])
        cls._add_bool(cmd, inputs, "plot_stats_input")
        cls._add_bool(cmd, inputs, "plot_stats_output")
        if stats_requested:
            cmd.extend(
                [
                    "--plot_stats_dpi",
                    str(inputs.get("plot_stats_dpi", 300)),
                    "--plot_stats_height",
                    str(inputs.get("plot_stats_width", 5)),
                    "--plot_stats_width",
                    str(inputs.get("plot_stats_height", 3)),
                    "--plot_stats_colour",
                    str(inputs.get("plot_stats_colour", "#0000ff")),
                ]
            )

    @classmethod
    def _interpretation_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get("make_consensus", False)):
            cmd.extend(["--make_consensus", "--consensus_type", str(inputs.get("consensus_type", "majority"))])
            cls._add_bool(cmd, inputs, "consensus_keep_gaps")
        cls._add_bool(cmd, inputs, "pwm_input")
        cls._add_bool(cmd, inputs, "pwm_output")
        _add_if_value(cmd, "--pwm_start", inputs.get("pwm_start"))
        _add_if_value(cmd, "--pwm_end", inputs.get("pwm_end"))
        if cls._has_any(inputs, ["pwm_input", "pwm_output"]):
            cmd.extend(
                [
                    "--pwm_freqtype",
                    str(inputs.get("pwm_freqtype", "equal")),
                    "--pwm_alphatype",
                    str(inputs.get("pwm_alphatype", "calc")),
                    "--pwm_alphaval",
                    str(inputs.get("pwm_alphaval", 1)),
                ]
            )
        cls._add_bool(cmd, inputs, "pwm_output_blamm")
        cls._add_bool(cmd, inputs, "pwm_output_meme")
        sim_requested = cls._has_any(inputs, ["make_similarity_matrix_input", "make_similarity_matrix_output"])
        cls._add_bool(cmd, inputs, "make_similarity_matrix_input")
        cls._add_bool(cmd, inputs, "make_similarity_matrix_output")
        if sim_requested:
            cmd.extend(
                [
                    "--make_simmatrix_keepgaps",
                    str(inputs.get("make_simmatrix_keepgaps", "0")),
                    "--make_simmatrix_dp",
                    str(inputs.get("make_simmatrix_dp", 4)),
                    "--make_simmatrix_minoverlap",
                    str(inputs.get("make_simmatrix_minoverlap", 1)),
                ]
            )

    @classmethod
    def _editing_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if cls._bool_flag(inputs.get("get_section", False)):
            cmd.extend(
                [
                    "--get_section",
                    "--section_start",
                    str(inputs.get("section_start", "")),
                    "--section_end",
                    str(inputs.get("section_end", "")),
                ]
            )
        for key in [
            "replace_input_tu",
            "replace_input_ut",
            "replace_output_tu",
            "replace_output_ut",
            "unalign_input",
            "unalign_output",
            "deduplicate_ids",
        ]:
            cls._add_bool(cmd, inputs, key)
        if cls._bool_flag(inputs.get("deduplicate_ids", False)):
            cmd.extend(["--duporder", str(inputs.get("duporder", "first"))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}"]
        infile = str(inputs.get("input", ""))
        if cls._bool_flag(inputs.get("input_is_gz", False)):
            setup.append(f"{_shell_join(['gunzip', '-c', infile])} > input.fasta")
            infile = "input.fasta"
        cmd = ["CIAlign", "--infile", infile, "--outfile_stem", "output"]
        cls._basic_args(cmd, inputs)
        cls._cleaning_args(cmd, inputs)
        cls._visualisation_args(cmd, inputs)
        cls._interpretation_args(cmd, inputs)
        cls._editing_args(cmd, inputs)
        setup.append(_shell_join(cmd))
        return " && ".join(setup)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output_cleaned.fasta", out / "output_removed.txt"]
        if cls._bool_flag(inputs.get("log_out", False)):
            outputs.append(out / "output_log.txt")
        all_mode = cls._bool_flag(inputs.get("all", False))
        visualise = cls._bool_flag(inputs.get("visualise", False))
        interpret = cls._bool_flag(inputs.get("interpret", False))
        if cls._bool_flag(inputs.get("plot_input", False)) or visualise or all_mode:
            outputs.append(out / "output_input.png")
        if cls._bool_flag(inputs.get("plot_output", False)) or visualise or all_mode:
            outputs.append(out / "output_output.png")
        if cls._bool_flag(inputs.get("plot_markup", False)) or visualise or all_mode:
            outputs.extend([out / "output_markup.png", out / "output_markup_legend.png"])
        if cls._bool_flag(inputs.get("plot_consensus_identity", False)) or all_mode:
            outputs.append(out / "output_consensus_identity.png")
        if cls._bool_flag(inputs.get("plot_consensus_similarity", False)):
            outputs.append(out / "output_consensus_similarity.png")
        logo_type = str(inputs.get("sequence_logo_type", "text") or "text")
        if cls._bool_flag(inputs.get("make_sequence_logo", False)):
            if logo_type in {"bar", "both"}:
                outputs.append(out / "output_logo_bar.png")
            if logo_type in {"text", "both"}:
                outputs.append(out / "output_logo_text.png")
        if cls._bool_flag(inputs.get("plot_stats_input", False)) or interpret or all_mode:
            outputs.append(out / "input_stats_plots")
        if cls._bool_flag(inputs.get("plot_stats_output", False)) or interpret or all_mode:
            outputs.append(out / "output_stats_plots")
        if cls._bool_flag(inputs.get("make_consensus", False)) or interpret or all_mode:
            outputs.extend([out / "output_consensus.fasta", out / "output_with_consensus.fasta"])
        pwm_input = cls._bool_flag(inputs.get("pwm_input", False))
        pwm_output = cls._bool_flag(inputs.get("pwm_output", False))
        if pwm_input:
            outputs.extend([out / "output_pwm_input.txt", out / "output_ppm_input.txt", out / "output_pfm_input.txt"])
            if cls._bool_flag(inputs.get("pwm_output_meme", False)):
                outputs.append(out / "output_ppm_meme_input.txt")
            if cls._bool_flag(inputs.get("pwm_output_blamm", False)):
                outputs.append(out / "output_pfm_blamm_input.txt")
        if pwm_output:
            outputs.extend([out / "output_pwm_output.txt", out / "output_ppm_output.txt", out / "output_pfm_output.txt"])
            if cls._bool_flag(inputs.get("pwm_output_meme", False)):
                outputs.append(out / "output_ppm_meme_output.txt")
            if cls._bool_flag(inputs.get("pwm_output_blamm", False)):
                outputs.append(out / "output_pfm_blamm_output.txt")
        if cls._bool_flag(inputs.get("make_similarity_matrix_input", False)) or interpret or all_mode:
            outputs.append(out / "output_input_similarity.tsv")
        if cls._bool_flag(inputs.get("make_similarity_matrix_output", False)) or interpret or all_mode:
            outputs.append(out / "output_output_similarity.tsv")
        if interpret or all_mode:
            outputs.extend([out / "output_output_column_stats.tsv", out / "output_input_column_stats.tsv"])
        for key, filename in {
            "replace_input_tu": "output_U_input.fasta",
            "replace_input_ut": "output_T_input.fasta",
            "replace_output_tu": "output_U_output.fasta",
            "replace_output_ut": "output_T_output.fasta",
            "unalign_input": "output_unaligned_input.fasta",
            "unalign_output": "output_unaligned_output.fasta",
        }.items():
            if cls._bool_flag(inputs.get(key, False)):
                outputs.append(out / filename)
        return outputs

    @classmethod
    def _validate_int_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> bool | str:
        value = inputs.get(key, default)
        if str(value) == "":
            return f"{key} is required"
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum}" if maximum is None else f"{key} must be between {minimum} and {maximum}"
        if maximum is not None and parsed > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be numeric"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def _validate_options(cls, inputs: dict[str, Any], key: str, default: str, options: list[str]) -> bool | str:
        value = str(inputs.get(key, default) or default)
        if value not in options:
            return f"{key} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        for key, default, minimum, maximum in [
            ("remove_divergent_minperc", 0.65, 0.0, 1.0),
            ("insertion_min_perc", 0.5, 0.0, 1.0),
            ("crop_ends_mingap_perc", 0.05, 0.0, 0.6),
            ("crop_ends_redefine_perc", 0.1, 0.0, 0.5),
            ("crop_divergent_min_prop_ident", 0.5, 0.01, 1.0),
            ("crop_divergent_min_prop_nongap", 0.5, 0.01, 1.0),
        ]:
            result = cls._validate_float_range(inputs, key, default, minimum, maximum)
            if result is not True:
                return result
        for key, default, minimum, maximum in [
            ("insertion_min_size", 3, 1, None),
            ("insertion_max_size", 200, 1, 10000),
            ("insertion_min_flank", 5, 0, None),
            ("remove_min_length", 50, 0, None),
            ("crop_divergent_buffer_size", 5, 1, None),
            ("plot_width", 5, 2, 20),
            ("plot_height", 3, 2, 15),
            ("plot_dpi", 300, 72, 1200),
            ("sequence_logo_dpi", 300, 72, 1200),
            ("sequence_logo_nt_per_row", 50, 1, None),
            ("plot_stats_dpi", 300, 72, 1200),
            ("plot_stats_width", 5, 2, 20),
            ("plot_stats_height", 3, 2, 15),
            ("pwm_alphaval", 1, 0, None),
            ("make_simmatrix_dp", 4, 0, 10),
            ("make_simmatrix_minoverlap", 1, 1, None),
        ]:
            result = cls._validate_int_range(inputs, key, default, minimum, maximum)
            if result is not True:
                return result
        for key, options, default in [
            ("sequence_logo_type", cls.SEQUENCE_LOGO_TYPES, "text"),
            ("consensus_type", cls.CONSENSUS_TYPES, "majority"),
            ("make_simmatrix_keepgaps", cls.SIMMATRIX_KEEPGAPS, "0"),
            ("duporder", cls.DUPORDERS, "first"),
            ("plot_sub_matrix_name", cls.SUB_MATRIX_NAMES, "NUC.4.4"),
            ("palette", cls.PALETTES, "CBS"),
            ("pwm_freqtype", cls.PWM_FREQTYPES, "equal"),
            ("pwm_alphatype", cls.PWM_ALPHATYPES, "calc"),
        ]:
            result = cls._validate_options(inputs, key, default, options)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get("get_section", False)):
            for key in ["section_start", "section_end"]:
                if str(inputs.get(key, "")).strip() == "":
                    return f"{key} is required when get_section is enabled"
                result = cls._validate_int_range(inputs, key, 1, 1)
                if result is not True:
                    return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Multiple sequence alignment in FASTA or compressed FASTA format"}),
            },
            "optional": {
                "input_is_gz": ("BOOLEAN", {"default": False, "description": "Input FASTA is gzip-compressed"}),
                "all": ("BOOLEAN", {"default": False, "description": "Enable all CIAlign functions"}),
                "clean": ("BOOLEAN", {"default": False, "description": "Enable all cleaning functions"}),
                "visualise": ("BOOLEAN", {"default": False, "description": "Enable all visualisation functions"}),
                "interpret": ("BOOLEAN", {"default": False, "description": "Enable all interpretation functions"}),
                "log_out": ("BOOLEAN", {"default": False, "description": "Plan CIAlign log output"}),
                "remove_divergent": ("BOOLEAN", {"default": False}),
                "remove_divergent_minperc": ("FLOAT", {"default": 0.65, "min": 0, "max": 1}),
                "remove_divergent_retain": ("STRING", {"default": [], "is_list": True}),
                "remove_divergent_retain_str": ("STRING", {"default": [], "is_list": True}),
                "remove_insertions": ("BOOLEAN", {"default": False}),
                "insertion_min_size": ("INT", {"default": 3, "min": 1}),
                "insertion_max_size": ("INT", {"default": 200, "min": 1, "max": 10000}),
                "insertion_min_flank": ("INT", {"default": 5, "min": 0}),
                "insertion_min_perc": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "crop_ends": ("BOOLEAN", {"default": False}),
                "crop_ends_mingap_perc": ("FLOAT", {"default": 0.05, "min": 0, "max": 0.6}),
                "crop_ends_redefine_perc": ("FLOAT", {"default": 0.1, "min": 0, "max": 0.5}),
                "crop_ends_retain": ("STRING", {"default": [], "is_list": True}),
                "crop_ends_retain_str": ("STRING", {"default": [], "is_list": True}),
                "remove_short": ("BOOLEAN", {"default": False}),
                "remove_min_length": ("INT", {"default": 50, "min": 0}),
                "remove_short_retain": ("STRING", {"default": [], "is_list": True}),
                "remove_short_retain_str": ("STRING", {"default": [], "is_list": True}),
                "crop_divergent": ("BOOLEAN", {"default": False}),
                "crop_divergent_min_prop_ident": ("FLOAT", {"default": 0.5, "min": 0.01, "max": 1}),
                "crop_divergent_min_prop_nongap": ("FLOAT", {"default": 0.5, "min": 0.01, "max": 1}),
                "crop_divergent_buffer_size": ("INT", {"default": 5, "min": 1}),
                "retain": ("STRING", {"default": [], "is_list": True}),
                "retain_str": ("STRING", {"default": [], "is_list": True}),
                "keep_gaponly": ("BOOLEAN", {"default": False}),
                "plot_input": ("BOOLEAN", {"default": False}),
                "plot_output": ("BOOLEAN", {"default": False}),
                "plot_markup": ("BOOLEAN", {"default": False}),
                "plot_consensus_identity": ("BOOLEAN", {"default": False}),
                "plot_consensus_similarity": ("BOOLEAN", {"default": False}),
                "output_settings": ("BOOLEAN", {"default": False}),
                "plot_width": ("INT", {"default": 5, "min": 2, "max": 20}),
                "plot_height": ("INT", {"default": 3, "min": 2, "max": 15}),
                "plot_dpi": ("INT", {"default": 300, "min": 72, "max": 1200}),
                "plot_keep_numbers": ("BOOLEAN", {"default": False}),
                "plot_force_numbers": ("BOOLEAN", {"default": False}),
                "plot_identity_palette": ("STRING", {"default": "bone"}),
                "plot_identity_gap_col": ("STRING", {"default": "#ffffff"}),
                "plot_similarity_palette": ("STRING", {"default": "bone"}),
                "plot_similarity_gap_col": ("STRING", {"default": "#ffffff"}),
                "plot_sub_matrix_name": ("STRING", {"default": "NUC.4.4", "options": cls.SUB_MATRIX_NAMES}),
                "palette": ("STRING", {"default": "CBS", "options": cls.PALETTES}),
                "make_sequence_logo": ("BOOLEAN", {"default": False}),
                "sequence_logo_type": ("STRING", {"default": "text", "options": cls.SEQUENCE_LOGO_TYPES}),
                "sequence_logo_dpi": ("INT", {"default": 300, "min": 72, "max": 1200}),
                "sequence_logo_font": ("STRING", {"default": "monospace"}),
                "sequence_logo_nt_per_row": ("INT", {"default": 50, "min": 1}),
                "logo_start": ("INT", {"default": "", "min": 1}),
                "logo_end": ("INT", {"default": "", "min": 1}),
                "plot_stats_input": ("BOOLEAN", {"default": False}),
                "plot_stats_output": ("BOOLEAN", {"default": False}),
                "plot_stats_dpi": ("INT", {"default": 300, "min": 72, "max": 1200}),
                "plot_stats_width": ("INT", {"default": 5, "min": 2, "max": 20}),
                "plot_stats_height": ("INT", {"default": 3, "min": 2, "max": 15}),
                "plot_stats_colour": ("STRING", {"default": "#0000ff"}),
                "make_consensus": ("BOOLEAN", {"default": False}),
                "consensus_type": ("STRING", {"default": "majority", "options": cls.CONSENSUS_TYPES}),
                "consensus_keep_gaps": ("BOOLEAN", {"default": False}),
                "pwm_input": ("BOOLEAN", {"default": False}),
                "pwm_output": ("BOOLEAN", {"default": False}),
                "pwm_start": ("INT", {"default": "", "min": 1}),
                "pwm_end": ("INT", {"default": "", "min": 1}),
                "pwm_freqtype": ("STRING", {"default": "equal", "options": cls.PWM_FREQTYPES}),
                "pwm_alphatype": ("STRING", {"default": "calc", "options": cls.PWM_ALPHATYPES}),
                "pwm_alphaval": ("INT", {"default": 1, "min": 0}),
                "pwm_output_blamm": ("BOOLEAN", {"default": False}),
                "pwm_output_meme": ("BOOLEAN", {"default": False}),
                "make_similarity_matrix_input": ("BOOLEAN", {"default": False}),
                "make_similarity_matrix_output": ("BOOLEAN", {"default": False}),
                "make_simmatrix_keepgaps": ("STRING", {"default": "0", "options": cls.SIMMATRIX_KEEPGAPS}),
                "make_simmatrix_dp": ("INT", {"default": 4, "min": 0, "max": 10}),
                "make_simmatrix_minoverlap": ("INT", {"default": 1, "min": 1}),
                "get_section": ("BOOLEAN", {"default": False}),
                "section_start": ("INT", {"default": "", "min": 1}),
                "section_end": ("INT", {"default": "", "min": 1}),
                "replace_input_tu": ("BOOLEAN", {"default": False}),
                "replace_input_ut": ("BOOLEAN", {"default": False}),
                "replace_output_tu": ("BOOLEAN", {"default": False}),
                "replace_output_ut": ("BOOLEAN", {"default": False}),
                "unalign_input": ("BOOLEAN", {"default": False}),
                "unalign_output": ("BOOLEAN", {"default": False}),
                "deduplicate_ids": ("BOOLEAN", {"default": False}),
                "duporder": ("STRING", {"default": "first", "options": cls.DUPORDERS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ChromapContract(_MappedOutputContract):
    """Align and preprocess chromatin profiling reads with Chromap."""

    LEGACY_NODE_ID = "chromap"
    DISPLAY_NAME = "chromap"
    REQUIRED_CONDA_PACKAGES = ["chromap"]
    CATEGORY = "alignment"
    DESCRIPTION = "Fast alignment and preprocessing of chromatin profiling reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "chromap",
        "Chromap",
        "chromatin profiles",
        "ATAC-seq",
        "scATAC-seq",
        "ChIP-seq",
        "Hi-C",
        "TagAlign",
        "4DN pairs",
    ]
    RETURN_TYPES = ("BED", "TXT")
    RETURN_NAMES = ("mapping_out", "summary_out")
    REQUIRED_EXECUTABLES = ["chromap"]
    DOCUMENTATION_URL = "https://github.com/haowenz/chromap"
    CITATION_DOIS = [CHROMAP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CHROMAP_CITATION_DOI}"]
    CITATION_TEXT = CHROMAP_CITATION_TEXT
    VERSION = "0.3.2+galaxy0"
    SHELL = True

    READ_TYPES = ["single", "paired"]
    PRESETS = ["atac", "chip", "hic"]
    OUTPUT_FORMATS = {
        "--SAM": ("SAM", "sam"),
        "--BED": ("BED", "bed"),
        "--TagAlign": ("TSV", "tsv"),
        "--pairs": ("4DN_PAIRS", "pairs"),
    }

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _read_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("read_type", "single") or "single")

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("out_format", "--BED") or "--BED")

    @classmethod
    def _single_reads(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("single_reads", inputs.get("single_read")))

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        pair = inputs.get("paired_collection", inputs.get("input_collection", inputs.get("input_pair", {})))
        if isinstance(pair, dict):
            forward = str(pair.get("forward", pair.get("r1", pair.get("left", ""))) or "")
            reverse = str(pair.get("reverse", pair.get("r2", pair.get("right", ""))) or "")
            return forward, reverse
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return str(pair[0]), str(pair[1])
        return "", ""

    @classmethod
    def _mapping_filename(cls, inputs: dict[str, Any]) -> str:
        ext = cls.OUTPUT_FORMATS.get(cls._out_format(inputs), cls.OUTPUT_FORMATS["--BED"])[1]
        return f"mapping.{ext}"

    @classmethod
    def _mapping_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._mapping_filename(inputs)}"

    @classmethod
    def _summary_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/summary.txt"

    @classmethod
    def _index_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chromap",
            "-i",
            "-r",
            str(inputs.get("ref", "")),
            "-o",
            "chromap_index",
            "-k",
            str(inputs.get("kmer", 17)),
            "-w",
            str(inputs.get("window", 7)),
        ]
        _add_if_value(cmd, "--min-frag-length", inputs.get("min_frag_length"))
        return _shell_join(cmd)

    @classmethod
    def _mapping_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["chromap", "--preset", str(inputs.get("preset", "atac") or "atac")]
        if cls._read_type(inputs) == "paired":
            forward, reverse = cls._paired_reads(inputs)
            cmd.extend(["-1", forward, "-2", reverse])
        else:
            cmd.extend(["-1", *cls._single_reads(inputs)])
        cmd.extend(["-r", str(inputs.get("ref", "")), "-x", "chromap_index"])
        _add_if_value(cmd, "-b", inputs.get("barcode"))
        _add_if_value(cmd, "--barcode-whitelist", inputs.get("barcode_whitelist"))
        _add_if_value(cmd, "--read-format", inputs.get("read_format"))
        _add_if_value(cmd, "--barcode-translate", inputs.get("barcode_translate"))
        if cls._bool_flag(inputs.get("split_alignment", False)):
            cmd.append("--split-alignment")
        cmd.extend(
            [
                "--error-threshold",
                str(inputs.get("error_threshold", 8)),
                "--min-num-seeds",
                str(inputs.get("min_num_seeds", 2)),
            ]
        )
        _add_if_value(cmd, "--max-seed-frequencies", inputs.get("max_seed_frequencies", "500,1000"))
        cmd.extend(
            [
                "--max-insert-size",
                str(inputs.get("max_insert_size", 1000)),
                "--MAPQ-threshold",
                str(inputs.get("MAPQ_threshold", 30)),
                "--min-read-length",
                str(inputs.get("min_read_length", 30)),
            ]
        )
        if cls._bool_flag(inputs.get("trim_adapters", False)):
            cmd.append("--trim-adapters")
        if cls._bool_flag(inputs.get("Tn5_shift", False)):
            cmd.append("--Tn5-shift")
        _add_if_value(cmd, "--bc-error-threshold", inputs.get("bc_error_threshold"))
        _add_if_value(cmd, "--bc-probability-threshold", inputs.get("bc_probability_threshold"))
        _add_if_value(cmd, "--chr-order", inputs.get("chr_order"))
        _add_if_value(cmd, "--pairs-natural-chr-order", inputs.get("pairs_natural_chr_order"))
        cmd.append(cls._out_format(inputs))
        if cls._bool_flag(inputs.get("summary", True)):
            cmd.extend(["--summary", cls._summary_path(inputs)])
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"
        cmd.extend(["-t", threads, "-o", cls._mapping_path(inputs)])
        return _shell_join(cmd).replace(shlex.quote(threads), threads)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        return (
            f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && "
            f"{cls._index_command(inputs)} && {cls._mapping_command(inputs)}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._mapping_filename(inputs)]
        if cls._bool_flag(inputs.get("summary", True)):
            outputs.append(out / "summary.txt")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_int_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be numeric"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("ref", "")).strip():
            return "ref is required"
        read_type = cls._read_type(inputs)
        if read_type not in cls.READ_TYPES:
            return f"read_type must be one of: {', '.join(cls.READ_TYPES)}"
        if read_type == "single":
            if not cls._single_reads(inputs):
                return "at least one single_reads value is required"
        else:
            forward, reverse = cls._paired_reads(inputs)
            if not forward or not reverse:
                return "paired_collection with forward and reverse reads is required"
        preset = str(inputs.get("preset", "atac") or "atac")
        if preset not in cls.PRESETS:
            return f"preset must be one of: {', '.join(cls.PRESETS)}"
        out_format = cls._out_format(inputs)
        if out_format not in cls.OUTPUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        for key, default, minimum in [
            ("kmer", 17, 1),
            ("window", 7, 1),
            ("error_threshold", 8, 0),
            ("min_num_seeds", 2, 1),
            ("max_insert_size", 1000, 1),
            ("min_read_length", 30, 1),
            ("threads", 8, 1),
        ]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if str(inputs.get("min_frag_length", "")) != "":
            result = cls._validate_int_min(inputs, "min_frag_length", 30, 1)
            if result is not True:
                return result
        result = cls._validate_int_range(inputs, "MAPQ_threshold", 30, 0, 60)
        if result is not True:
            return result
        for key in ["bc_error_threshold"]:
            if str(inputs.get(key, "")) != "":
                result = cls._validate_int_min(inputs, key, 1, 0)
                if result is not True:
                    return result
        if str(inputs.get("bc_probability_threshold", "")) != "":
            result = cls._validate_float_range(inputs, "bc_probability_threshold", 0.9, 0.0, 1.0)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "read_type": ("STRING", {"default": "single", "options": cls.READ_TYPES}),
                "ref": ("FASTA", {"description": "Reference genome FASTA used to build the Chromap index"}),
            },
            "optional": {
                "single_reads": (
                    "FASTQ",
                    {"default": [], "is_list": True, "description": "One or more single-end FASTQ reads"},
                ),
                "paired_collection": (
                    "JSON",
                    {"default": {}, "description": "Paired collection with forward and reverse FASTQ reads"},
                ),
                "barcode": ("FASTQ", {"default": "", "description": "Optional barcode FASTQ for single-cell assays"}),
                "barcode_whitelist": ("TXT", {"default": "", "description": "Optional valid barcode whitelist"}),
                "read_format": ("STRING", {"default": "", "description": "Read/barcode layout such as r1:0:-1,bc:0:-1"}),
                "barcode_translate": ("TSV", {"default": "", "description": "Optional barcode translation table"}),
                "min_frag_length": ("INT", {"default": 30, "min": 1}),
                "kmer": ("INT", {"default": 17, "min": 1}),
                "window": ("INT", {"default": 7, "min": 1}),
                "preset": ("STRING", {"default": "atac", "options": cls.PRESETS}),
                "split_alignment": ("BOOLEAN", {"default": False}),
                "error_threshold": ("INT", {"default": 8, "min": 0}),
                "min_num_seeds": ("INT", {"default": 2, "min": 1}),
                "max_seed_frequencies": ("STRING", {"default": "500,1000"}),
                "max_insert_size": ("INT", {"default": 1000, "min": 1}),
                "MAPQ_threshold": ("INT", {"default": 30, "min": 0, "max": 60}),
                "min_read_length": ("INT", {"default": 30, "min": 1}),
                "trim_adapters": ("BOOLEAN", {"default": False}),
                "Tn5_shift": ("BOOLEAN", {"default": False}),
                "bc_error_threshold": ("INT", {"default": "", "min": 0}),
                "bc_probability_threshold": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "chr_order": ("TSV", {"default": ""}),
                "pairs_natural_chr_order": ("TSV", {"default": ""}),
                "out_format": ("STRING", {"default": "--BED", "options": list(cls.OUTPUT_FORMATS)}),
                "summary": ("BOOLEAN", {"default": True}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CIRCexplorer2Contract(_MappedOutputContract):
    """Run CIRCexplorer2 circular RNA analysis modules."""

    LEGACY_NODE_ID = "circexplorer2"
    DISPLAY_NAME = "CIRCexplorer2"
    REQUIRED_CONDA_PACKAGES = ["circexplorer2"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Circular RNA analysis with CIRCexplorer2 modules."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CIRCexplorer2",
        "circexplorer2",
        "circular RNA",
        "circRNA",
        "back-splicing",
        "alternative splicing",
        "TopHat-Fusion",
        "STAR",
        "MapSplice",
    ]
    RETURN_TYPES = (
        "TGZ",
        "BIGWIG",
        "BED",
        "TSV",
        "TSV",
        "TGZ",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
    )
    RETURN_NAMES = (
        "alignment",
        "fusion_junction_bw",
        "parse",
        "annotate",
        "annotate_low",
        "assemble",
        "denovo_combined",
        "denovo_circularRNA",
        "denovo_annotated",
        "denovo_novel",
        "denovo_abs5",
        "denovo_abs3",
        "denovo_all_exon",
        "denovo_all_intron",
        "denovo_a5ss",
        "denovo_a3ss",
    )
    REQUIRED_EXECUTABLES = ["CIRCexplorer2"]
    DOCUMENTATION_URL = "https://circexplorer2.readthedocs.io/en/latest/"
    CITATION_DOIS = [CIRCEXPLORER2_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CIRCEXPLORER2_CITATION_DOI}"]
    CITATION_TEXT = CIRCEXPLORER2_CITATION_TEXT
    VERSION = "2.3.8+galaxy0"
    SHELL = True

    OUTPUT_NAME_BY_BASENAME = {
        "alignment.tgz": "alignment",
        "accepted_hits.bw": "fusion_junction_bw",
        "back_spliced_junction.bed": "parse",
        "circularRNA_known.txt": "annotate",
        "low_conf_circularRNA_known.txt": "annotate_low",
        "assemble.tgz": "assemble",
        "combined_ref.txt": "denovo_combined",
        "circularRNA_full.txt": "denovo_circularRNA",
        "annotated_circ.txt": "denovo_annotated",
        "novel_circ.txt": "denovo_novel",
        "a5bs.txt": "denovo_abs5",
        "a3bs.txt": "denovo_abs3",
        "all_exon_info.txt": "denovo_all_exon",
        "all_intron_info.txt": "denovo_all_intron",
        "all_A5SS_info.txt": "denovo_a5ss",
        "all_A3SS_info.txt": "denovo_a3ss",
    }

    MODES = ["align", "parse", "annotate", "assemble", "denovo"]
    ALIGNERS = ["TopHat-Fusion", "STAR", "MapSplice", "BWA", "segemehl"]
    TYPE_MAPPINGS = ["-m", "-n"]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("mode", "align") or "align")

    @classmethod
    def _out_dir(cls, output_dir: str | Path) -> Path:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return out

    @classmethod
    def _threads_arg(cls, inputs: dict[str, Any]) -> str:
        return f"--thread=${{GALAXY_SLOTS:-{inputs.get('threads', 10)}}}"

    @classmethod
    def _fastq_stage_path(cls, index: int, fastq: str) -> str:
        suffixes = Path(fastq).suffixes
        ext = "".join(suffixes).lstrip(".") or "fastq"
        return f"reads/file{index}.{ext}"

    @classmethod
    def _align_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(["mkdir", "-p", "reads"])]
        fastqs = _as_list(inputs.get("fastq"))
        staged: list[str] = []
        for index, fastq in enumerate(fastqs):
            file_path = cls._fastq_stage_path(index, fastq)
            staged.append(file_path)
            commands.append(_shell_join(["ln", "-s", fastq, file_path]))
        cmd = [
            "CIRCexplorer2",
            "align",
            cls._threads_arg(inputs),
            "--gtf",
            str(inputs.get("gtf", "")),
            "-g",
            str(inputs.get("genome", "")),
            "--fastq",
            ",".join(staged),
        ]
        if cls._bool_flag(inputs.get("bw", False)):
            cmd.append("--bw")
        if cls._bool_flag(inputs.get("scale", False)):
            cmd.append("--scale")
        if cls._bool_flag(inputs.get("skip_tophat", False)):
            cmd.append("--skip-tophat")
        if cls._bool_flag(inputs.get("skip_tophat_fusion", False)):
            cmd.append("--skip-tophat-fusion")
        commands.append(_shell_join(cmd).replace(shlex.quote(cls._threads_arg(inputs)), cls._threads_arg(inputs)))
        commands.append(_shell_join(["tar", "-zcvf", "alignment.tgz", "./alignment"]))
        return " && ".join(commands)

    @classmethod
    def _parse_command(cls, inputs: dict[str, Any]) -> str:
        aligner = str(inputs.get("aligner", "TopHat-Fusion") or "TopHat-Fusion")
        cmd = ["CIRCexplorer2", "parse", "-t", aligner, str(inputs.get("fusion_file", ""))]
        if aligner == "TopHat-Fusion" and cls._bool_flag(inputs.get("pe", False)):
            cmd.append("--pe")
        if cls._bool_flag(inputs.get("f", False)):
            cmd.append("-f")
        return _shell_join(cmd)

    @classmethod
    def _annotate_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "CIRCexplorer2",
            "annotate",
            "-r",
            str(inputs.get("ref", "")),
            "-g",
            "reference_genome.fa",
            "-b",
            str(inputs.get("bed", "")),
        ]
        if cls._bool_flag(inputs.get("no_fix", False)):
            cmd.append("--no-fix")
        if cls._bool_flag(inputs.get("low_confidence", False)):
            cmd.append("--low-confidence")
        return (
            f"{_shell_join(['ln', '-s', str(inputs.get('genome', '')), 'reference_genome.fa'])} && "
            f"{_shell_join(cmd)}"
        )

    @classmethod
    def _assemble_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "CIRCexplorer2",
            "assemble",
            cls._threads_arg(inputs),
            "-r",
            str(inputs.get("ref", "")),
            "-m",
            "./alignment",
        ]
        if cls._bool_flag(inputs.get("remove_rRNA", False)):
            cmd.append("--remove-rRNA")
        command = _shell_join(cmd).replace(shlex.quote(cls._threads_arg(inputs)), cls._threads_arg(inputs))
        return (
            f"{_shell_join(['tar', '-zxf', str(inputs.get('tophat', ''))])} && "
            f"{command} && {_shell_join(['tar', '-zcvf', 'assemble.tgz', './assemble'])}"
        )

    @classmethod
    def _denovo_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(["ln", "-s", str(inputs.get("genome", "")), "reference_genome.fa"])]
        assemble_file = str(inputs.get("assemble_file", ""))
        tar_flag = "-zxf" if Path(assemble_file).suffix == ".gz" or assemble_file.endswith(".tgz") else "-xf"
        commands.append(_shell_join(["tar", tar_flag, assemble_file]))
        if str(inputs.get("as_option", "disabled") or "disabled") == "enabled":
            commands.append(_shell_join(["tar", "-zxf", str(inputs.get("tophat", ""))]))
        cmd = [
            "CIRCexplorer2",
            "denovo",
            "-d",
            "./assemble",
            "-r",
            str(inputs.get("ref", "")),
            "-b",
            str(inputs.get("bed", "")),
            "-g",
            "reference_genome.fa",
        ]
        if cls._bool_flag(inputs.get("abs", False)):
            cmd.extend(["--abs", "abs"])
        if str(inputs.get("as_option", "disabled") or "disabled") == "enabled":
            cmd.extend(["--as", "as", str(inputs.get("type_mapping", "-m") or "-m"), "./alignment"])
        if cls._bool_flag(inputs.get("no_fix", False)):
            cmd.append("--no-fix")
        if cls._bool_flag(inputs.get("rpkm", False)):
            cmd.append("--rpkm")
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = cls._mode(inputs)
        module_commands = {
            "align": cls._align_command,
            "parse": cls._parse_command,
            "annotate": cls._annotate_command,
            "assemble": cls._assemble_command,
            "denovo": cls._denovo_command,
        }
        command = module_commands.get(mode, cls._align_command)(inputs)
        out = _out(inputs)
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = cls._out_dir(output_dir)
        mode = cls._mode(inputs)
        if mode == "align":
            outputs = [out / "alignment.tgz"]
            if cls._bool_flag(inputs.get("bw", False)):
                outputs.append(out / "accepted_hits.bw")
            return outputs
        if mode == "parse":
            return [out / "back_spliced_junction.bed"]
        if mode == "annotate":
            outputs = [out / "circularRNA_known.txt"]
            if cls._bool_flag(inputs.get("low_confidence", False)):
                outputs.append(out / "low_conf_circularRNA_known.txt")
            return outputs
        if mode == "assemble":
            return [out / "assemble.tgz"]
        outputs = [
            out / "combined_ref.txt",
            out / "circularRNA_full.txt",
            out / "annotated_circ.txt",
            out / "novel_circ.txt",
        ]
        if cls._bool_flag(inputs.get("abs", False)):
            outputs.extend([out / "a5bs.txt", out / "a3bs.txt"])
        if str(inputs.get("as_option", "disabled") or "disabled") == "enabled":
            outputs.extend(
                [
                    out / "all_exon_info.txt",
                    out / "all_intron_info.txt",
                    out / "all_A5SS_info.txt",
                    out / "all_A3SS_info.txt",
                ]
            )
        return outputs

    @classmethod
    def _require(cls, inputs: dict[str, Any], key: str, mode: str) -> bool | str:
        if not str(inputs.get(key, "")).strip():
            return f"{key} is required when mode is {mode}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = cls._mode(inputs)
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        if mode == "align":
            for key in ["gtf", "genome"]:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            if not _as_list(inputs.get("fastq")):
                return "at least one fastq value is required when mode is align"
            return True
        if mode == "parse":
            aligner = str(inputs.get("aligner", "TopHat-Fusion") or "TopHat-Fusion")
            if aligner not in cls.ALIGNERS:
                return f"aligner must be one of: {', '.join(cls.ALIGNERS)}"
            return cls._require(inputs, "fusion_file", mode)
        if mode == "annotate":
            for key in ["ref", "genome", "bed"]:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            return True
        if mode == "assemble":
            for key in ["ref", "tophat"]:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            return True
        for key in ["ref", "bed", "genome", "assemble_file"]:
            result = cls._require(inputs, key, mode)
            if result is not True:
                return result
        as_option = str(inputs.get("as_option", "disabled") or "disabled")
        if as_option not in {"disabled", "enabled"}:
            return "as_option must be one of: disabled, enabled"
        if as_option == "enabled":
            if not str(inputs.get("tophat", "")).strip():
                return "tophat is required when as_option is enabled"
            type_mapping = str(inputs.get("type_mapping", "-m") or "-m")
            if type_mapping not in cls.TYPE_MAPPINGS:
                return f"type_mapping must be one of: {', '.join(cls.TYPE_MAPPINGS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"default": "align", "options": cls.MODES}),
            },
            "optional": {
                "gtf": ("GTF", {"default": "", "description": "Annotation GTF for align mode"}),
                "genome": ("FASTA", {"default": "", "description": "Reference genome FASTA"}),
                "fastq": ("FASTQ", {"default": [], "is_list": True, "description": "Single-read RNA-seq FASTQ files"}),
                "bw": ("BOOLEAN", {"default": False, "description": "Create BigWig output in align mode"}),
                "scale": ("BOOLEAN", {"default": False, "description": "Scale BigWig signal to HPB"}),
                "skip_tophat": ("BOOLEAN", {"default": False}),
                "skip_tophat_fusion": ("BOOLEAN", {"default": False}),
                "aligner": ("STRING", {"default": "TopHat-Fusion", "options": cls.ALIGNERS}),
                "fusion_file": ("FILE", {"default": "", "description": "Fusion junction file for parse mode"}),
                "pe": ("BOOLEAN", {"default": False, "description": "Parse paired-end TopHat-Fusion alignments"}),
                "f": ("BOOLEAN", {"default": False, "description": "Count fragments instead of reads in parse mode"}),
                "ref": ("TXT", {"default": "", "description": "Gene annotation in GenePred/RefSeq format"}),
                "bed": ("BED", {"default": "", "description": "Back-spliced junction BED file"}),
                "no_fix": ("BOOLEAN", {"default": False}),
                "low_confidence": ("BOOLEAN", {"default": False}),
                "tophat": ("TGZ", {"default": "", "description": "TopHat alignment archive from align mode"}),
                "remove_rRNA": ("BOOLEAN", {"default": False}),
                "assemble_file": ("TGZ", {"default": "", "description": "Assemble archive for denovo mode"}),
                "abs": ("BOOLEAN", {"default": False, "description": "Detect alternative back-splicing"}),
                "as_option": ("STRING", {"default": "disabled", "options": ["disabled", "enabled"]}),
                "type_mapping": ("STRING", {"default": "-m", "options": cls.TYPE_MAPPINGS}),
                "rpkm": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 10, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosContract(_MappedOutputContract):
    """Render Galaxy IUC Circos plots from karyotype, data, and link tracks."""

    LEGACY_NODE_ID = "circos"
    DISPLAY_NAME = "Circos"
    REQUIRED_CONDA_PACKAGES = [
        "circos",
        "bcbiogff",
        "biopython",
        "pybigwig",
        "circos-tools",
        "grep",
        "tar",
    ]
    CATEGORY = "visualization"
    DESCRIPTION = "Visualize genomic data in a circular layout with the Galaxy IUC Circos wrapper."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos",
        "circular layout",
        "circular genome plot",
        "karyotype",
        "2D data tracks",
        "link tracks",
        "comparative genomics",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "TAR", "TSV")
    RETURN_NAMES = ("output_png", "output_svg", "output_tar", "karyotype_txt")
    REQUIRED_EXECUTABLES = ["python", "grep", "cp", "ln", "head", "tar", "circos"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    OUTPUT_NAME_BY_BASENAME = {
        "circos.png": "output_png",
        "circos.svg": "output_svg",
        "circos.tar.gz": "output_tar",
        "karyotype.txt": "karyotype_txt",
    }

    REFERENCE_SOURCES = ["preset", "history", "cached", "karyotype", "lengths"]
    UNITS = ["bases", "kb", "mb", "gb"]
    PRESET_KARYOTYPES = [
        "karyotype.arabidopsis.tair10.txt",
        "karyotype.chimp.pt4.txt",
        "karyotype.drosophila.dm6.hires.txt",
        "karyotype.drosophila.hires.dm3.txt",
        "karyotype.human.hg38.txt",
        "karyotype.human.hg19.txt",
        "karyotype.human.hg18.txt",
        "karyotype.human.hg17.txt",
        "karyotype.human.hg16.txt",
        "karyotype.mouse.mm10.txt",
        "karyotype.mouse.mm9.txt",
        "karyotype.oryzasativa.txt",
        "karyotype.rat.rn4.txt",
        "karyotype.sorghum.txt",
        "karyotype.yeast.txt",
        "karyotype.zeamays.txt",
    ]
    LIMIT_DEFAULTS = {
        "max_ticks": 5000,
        "max_ideograms": 200,
        "max_links": 25000,
        "max_points_per_track": 25000,
    }
    LIMIT_MINIMUM = 200

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source", "preset") or "preset")

    @classmethod
    def _output_enabled(cls, inputs: dict[str, Any], key: str) -> bool:
        if key not in inputs:
            return key == "output_png"
        return bool(inputs.get(key))

    @classmethod
    def _outputs_plot(cls, inputs: dict[str, Any]) -> bool:
        return cls._output_enabled(inputs, "output_png") or cls._output_enabled(inputs, "output_svg")

    @classmethod
    def _outputs_karyotype(cls, inputs: dict[str, Any]) -> bool:
        return cls._reference_source(inputs) not in {"karyotype", "preset"}

    @classmethod
    def _conf_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/circos/conf"

    @classmethod
    def _data_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/circos/data"

    @classmethod
    def _karyotype_path(cls, inputs: dict[str, Any]) -> str:
        return f"{cls._conf_dir(inputs)}/karyotype.txt"

    @classmethod
    def _reference_commands(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        karyotype = cls._karyotype_path(inputs)
        source = cls._reference_source(inputs)
        if source == "history":
            genome_ref = f"{out}/genomeref.fa"
            return [
                _shell_join(["ln", "-s", str(inputs.get("genome_fasta", "") or ""), genome_ref]),
                f"{_shell_join(['python', 'karyotype-from-fasta.py', genome_ref])} > {shlex.quote(karyotype)}",
            ]
        if source == "lengths":
            return (
                f"{_shell_join(['python', 'karyotype-from-lengths.py', str(inputs.get('input_lengths', '') or '')])} "
                f"> {shlex.quote(karyotype)}"
            ).split(" && ")
        if source == "cached":
            lengths = str(inputs.get("cached_lengths", "") or "")
            if inputs.get("limit_chromosomes"):
                length_source = lengths
            else:
                length_source = f"<(head -n 50 {shlex.quote(lengths)})"
            return [
                f"{_shell_join(['python', 'karyotype-from-lengths.py', length_source])} > {shlex.quote(karyotype)}"
            ]
        if source == "karyotype":
            return [_shell_join(["cp", str(inputs.get("input_karyotype", "") or ""), karyotype])]
        return [
            _shell_join(
                [
                    "cp",
                    f"karyotype/{str(inputs.get('preset_karyotype', 'karyotype.human.hg38.txt') or 'karyotype.human.hg38.txt')}",
                    karyotype,
                ]
            )
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        karyotype = cls._karyotype_path(inputs)
        commands = [
            _shell_join(["mkdir", "-p", cls._conf_dir(inputs), cls._data_dir(inputs)]),
            *cls._reference_commands(inputs),
            (
                f"python karyotype-colors.py `grep -c '^chr\\s' {shlex.quote(karyotype)}` "
                f"> {shlex.quote(f'{cls._conf_dir(inputs)}/karyotype-colors.conf')}"
            ),
            _shell_join(["touch", f"{cls._conf_dir(inputs)}/karyotype-colors.conf"]),
        ]
        if str(inputs.get("colour_profile", "") or "") == "cg":
            commands.append(f"cat colours/cg.conf >> {shlex.quote(f'{cls._conf_dir(inputs)}/karyotype-colors.conf')}")
        if cls._outputs_karyotype(inputs):
            commands.append(_shell_join(["cp", karyotype, f"{out}/karyotype.txt"]))
        for source, target in [
            ("circos.conf", "circos.conf"),
            ("ticks.conf", "ticks.conf"),
            ("ideogram.conf", "ideogram.conf"),
            ("data.conf", "data.conf"),
            ("links.conf", "links.conf"),
            ("galaxy_test_case.json", "galaxy_test_case.json"),
        ]:
            commands.append(_shell_join(["cp", source, f"{cls._conf_dir(inputs)}/{target}"]))
        for idx, track in enumerate(_as_list(inputs.get("data_tracks"))):
            commands.append(_shell_join(["cp", track, f"{cls._data_dir(inputs)}/data-{idx}.txt"]))
        for idx, track in enumerate(_as_list(inputs.get("link_tracks"))):
            commands.append(_shell_join(["cp", track, f"{cls._data_dir(inputs)}/links-{idx}.txt"]))
        if cls._output_enabled(inputs, "output_tar"):
            commands.append(_shell_join(["tar", "-czf", f"{out}/circos.tar.gz", "-C", out, "circos"]))
        if cls._outputs_plot(inputs):
            commands.append(_shell_join(["cd", out]))
            commands.append(_shell_join(["circos", "-conf", "circos/conf/circos.conf", "-noparanoid"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if cls._output_enabled(inputs, "output_png"):
            outputs.append(out / "circos.png")
        if cls._output_enabled(inputs, "output_svg"):
            outputs.append(out / "circos.svg")
        if cls._output_enabled(inputs, "output_tar"):
            outputs.append(out / "circos.tar.gz")
        if cls._outputs_karyotype(inputs):
            outputs.append(out / "karyotype.txt")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int = 0) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_track_list(cls, inputs: dict[str, Any], key: str) -> bool | str:
        raw = inputs.get(key)
        if isinstance(raw, (list, tuple)) and any(str(value) == "" for value in raw):
            return f"{key} values must not be empty"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        required_by_source = {
            "history": "genome_fasta",
            "cached": "cached_lengths",
            "karyotype": "input_karyotype",
            "lengths": "input_lengths",
        }
        required = required_by_source.get(source)
        if required and not str(inputs.get(required, "") or "").strip():
            return f"{required} is required when reference_source is {source}"
        preset = str(inputs.get("preset_karyotype", "karyotype.human.hg38.txt") or "karyotype.human.hg38.txt")
        if source == "preset" and preset not in cls.PRESET_KARYOTYPES:
            return f"preset_karyotype must be one of: {', '.join(cls.PRESET_KARYOTYPES)}"
        if not any(
            [
                cls._output_enabled(inputs, "output_png"),
                cls._output_enabled(inputs, "output_svg"),
                cls._output_enabled(inputs, "output_tar"),
                cls._outputs_karyotype(inputs),
            ]
        ):
            return "at least one of output_png, output_svg, output_tar, or generated karyotype_txt must be selected"
        units = str(inputs.get("units", "mb") or "mb")
        if units not in cls.UNITS:
            return f"units must be one of: {', '.join(cls.UNITS)}"
        for key, default in cls.LIMIT_DEFAULTS.items():
            validation = cls._validate_int_min(inputs, key, default, cls.LIMIT_MINIMUM)
            if validation is not True:
                return validation
        for key in ("data_tracks", "link_tracks"):
            validation = cls._validate_track_list(inputs, key)
            if validation is not True:
                return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_source": ("STRING", {"default": "preset", "options": cls.REFERENCE_SOURCES}),
            },
            "optional": {
                "preset_karyotype": (
                    "STRING",
                    {
                        "default": "karyotype.human.hg38.txt",
                        "options": cls.PRESET_KARYOTYPES,
                        "description": "Bundled Circos karyotype preset",
                    },
                ),
                "genome_fasta": ("FASTA", {"default": "", "description": "Reference FASTA for history mode"}),
                "input_karyotype": ("TSV", {"default": "", "description": "Custom Circos karyotype table"}),
                "input_lengths": ("TSV", {"default": "", "description": "Sequence lengths table"}),
                "cached_lengths": ("TSV", {"default": "", "description": "Cached reference lengths table"}),
                "limit_chromosomes": ("STRING", {"default": "", "description": "Limit, filter, and order chromosomes"}),
                "chromosomes_reverse": ("STRING", {"default": "", "description": "Chromosomes to draw in reverse order"}),
                "units": ("STRING", {"default": "mb", "options": cls.UNITS}),
                "data_tracks": ("TSV", {"default": [], "is_list": True, "description": "2D Circos data tracks"}),
                "link_tracks": ("TSV", {"default": [], "is_list": True, "description": "Six-column Circos link tracks"}),
                "output_png": ("BOOLEAN", {"default": True, "description": "Output PNG plot"}),
                "output_svg": ("BOOLEAN", {"default": False, "description": "Output SVG plot"}),
                "output_tar": ("BOOLEAN", {"default": False, "description": "Output configuration archive"}),
                "colour_profile": ("STRING", {"default": "", "options": ["", "cg"]}),
                "image_radius": ("INT", {"default": 1500, "min": 500, "max": 5000}),
                "ideogram_radius": ("FLOAT", {"default": 0.90, "min": 0}),
                "ideogram_thickness": ("FLOAT", {"default": 30, "min": 0}),
                "angle_offset": ("INT", {"default": -90, "min": -180, "max": 180}),
                "max_ticks": ("INT", {"default": 5000, "min": cls.LIMIT_MINIMUM}),
                "max_ideograms": ("INT", {"default": 200, "min": cls.LIMIT_MINIMUM}),
                "max_links": ("INT", {"default": 25000, "min": cls.LIMIT_MINIMUM}),
                "max_points_per_track": ("INT", {"default": 25000, "min": cls.LIMIT_MINIMUM}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosResampleContract(_MappedOutputContract):
    """Reduce dense Circos data tracks with the Circos tools resample utility."""

    LEGACY_NODE_ID = "circos_resample"
    DISPLAY_NAME = "Circos: Resample 1/2D data"
    REQUIRED_CONDA_PACKAGES = ["circos", "circos-tools"]
    CATEGORY = "visualization"
    DESCRIPTION = "Reduce dense 1D/2D Circos data tracks before plotting."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_resample",
        "resample",
        "downsample",
        "1D track",
        "2D track",
        "bin size",
        "comparative genomics",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["resample", "sed"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    METHODS = ["-avg", "-min", "-max", "-sum", "-count"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/resampled.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "resample",
            "-bin",
            str(inputs.get("bins", 1000000)),
            str(inputs.get("method", "-avg") or "-avg"),
        ]
        return (
            f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('input', '')))} "
            f"| sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "resampled.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        try:
            bins = int(inputs.get("bins", 1000000))
        except (TypeError, ValueError):
            return "bins must be an integer"
        if bins < 1:
            return "bins must be greater than or equal to 1"
        method = str(inputs.get("method", "-avg") or "-avg")
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "1D/2D Circos data track"}),
            },
            "optional": {
                "bins": ("INT", {"default": 1000000, "min": 1, "description": "Bin size for resampling"}),
                "method": ("STRING", {"default": "-avg", "options": cls.METHODS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosGCSkewContract(_MappedOutputContract):
    """Calculate GC skew over a reference genome for Circos BigWig tracks."""

    LEGACY_NODE_ID = "circos_gc_skew"
    DISPLAY_NAME = "GC Skew"
    REQUIRED_CONDA_PACKAGES = ["circos", "pybigwig", "biopython"]
    CATEGORY = "visualization"
    DESCRIPTION = "Calculate GC skew over genomic sequences for Circos tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "GC skew",
        "circos_gc_skew",
        "genomic sequences",
        "BigWig",
        "comparative genomics",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python", "ln"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    REFERENCE_SOURCES = ["history", "builtin"]

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_genome_source", "history") or "history")

    @classmethod
    def _reference_path(cls, inputs: dict[str, Any]) -> str:
        if cls._reference_source(inputs) == "builtin":
            return str(inputs.get("builtin_path", inputs.get("builtin", "")) or "")
        return str(inputs.get("history_item", "") or "")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gc_skew.bw"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reference = cls._reference_path(inputs)
        return (
            f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && "
            f"{_shell_join(['ln', '-s', '-f', reference, 'reference.fa'])} && "
            f"{_shell_join(['python', 'gc_skew.py', 'reference.fa', str(inputs.get('window', 100000)), cls._output_path(inputs)])}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gc_skew.bw"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if not cls._reference_path(inputs).strip():
            key = "builtin_path" if source == "builtin" else "history_item"
            return f"{key} is required when reference_genome_source is {source}"
        try:
            window = int(inputs.get("window", 100000))
        except (TypeError, ValueError):
            return "window must be an integer"
        if window < 1:
            return "window must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_genome_source": ("STRING", {"default": "history", "options": cls.REFERENCE_SOURCES}),
            },
            "optional": {
                "history_item": ("FASTA", {"default": "", "description": "Reference genome FASTA from history"}),
                "builtin_path": ("FASTA", {"default": "", "description": "Built-in reference genome FASTA path"}),
                "window": ("INT", {"default": 100000, "min": 1, "description": "Window size for GC skew"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosWiggleToScatterContract(_MappedOutputContract):
    """Convert bigWig intervals into Circos scatter track rows."""

    LEGACY_NODE_ID = "circos_wiggle_to_scatter"
    DISPLAY_NAME = "Circos: bigWig to Scatter"
    REQUIRED_CONDA_PACKAGES = ["circos", "pybigwig"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert bigWig data into Circos scatter, line, or histogram tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "bigWig",
        "scatter",
        "line plot",
        "histogram",
        "wiggle",
        "2D track",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/scatter.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["python", "scatter-from-wiggle.py", str(inputs.get("input", ""))]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "scatter.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BIGWIG", {"description": "bigWig data file to convert"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosIntervalToTextContract(_MappedOutputContract):
    """Convert BED6+ or GFF3 intervals into Circos text label rows."""

    LEGACY_NODE_ID = "circos_interval_to_text"
    DISPLAY_NAME = "Circos: Interval to Circos Text Labels"
    REQUIRED_CONDA_PACKAGES = ["circos", "bcbiogff", "biopython"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert BED6+ or GFF3 intervals into Circos text-label tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "text labels",
        "interval labels",
        "BED6",
        "GFF3",
        "annotation labels",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    REF_SOURCES = ["bed", "gff3"]

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_source", "bed") or "bed")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/text_labels.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        if cls._ref_source(inputs) == "gff3":
            cmd = ["python", "text-from-gff3.py", str(inputs.get("input", "")), str(inputs.get("attr", ""))]
        else:
            cmd = ["python", "text-from-bed.py", str(inputs.get("input", ""))]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "text_labels.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.REF_SOURCES:
            return f"ref_source must be one of: {', '.join(cls.REF_SOURCES)}"
        if ref_source == "gff3" and not str(inputs.get("attr", "")).strip():
            return "attr is required when ref_source is gff3"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_source": ("STRING", {"default": "bed", "options": cls.REF_SOURCES}),
            },
            "optional": {
                "input": ("FILE", {"default": "", "description": "BED6+ or GFF3 interval file"}),
                "attr": ("STRING", {"default": "", "description": "GFF3 attribute to use as the text label"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosIntervalToTileContract(_MappedOutputContract):
    """Convert BED3+ or GFF3 intervals into Circos tile track rows."""

    LEGACY_NODE_ID = "circos_interval_to_tile"
    DISPLAY_NAME = "Circos: Interval to Tiles"
    REQUIRED_CONDA_PACKAGES = ["circos", "bcbiogff", "biopython"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert BED3+ or GFF3 intervals into Circos tile tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "tile tracks",
        "interval tiles",
        "BED3",
        "BED6",
        "GFF3",
        "annotation tiles",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    REF_SOURCES = ["bed", "gff3"]

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_source", "bed") or "bed")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/tiles.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        if cls._ref_source(inputs) == "gff3":
            cmd = ["python", "tiles-from-gff3.py", str(inputs.get("input", "")), str(inputs.get("attr", ""))]
        else:
            cmd = ["python", "tiles-from-bed.py", str(inputs.get("input", ""))]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "tiles.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.REF_SOURCES:
            return f"ref_source must be one of: {', '.join(cls.REF_SOURCES)}"
        if ref_source == "gff3" and not str(inputs.get("attr", "")).strip():
            return "attr is required when ref_source is gff3"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_source": ("STRING", {"default": "bed", "options": cls.REF_SOURCES}),
            },
            "optional": {
                "input": ("FILE", {"default": "", "description": "BED3+ or GFF3 interval file"}),
                "attr": ("STRING", {"default": "", "description": "GFF3 attribute to use as tile name"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosAlignmentsToLinksContract(_MappedOutputContract):
    """Convert multiple-alignment blocks into Circos link track rows."""

    LEGACY_NODE_ID = "circos_aln_to_links"
    DISPLAY_NAME = "Circos: Alignments to links"
    REQUIRED_CONDA_PACKAGES = ["circos", "biopython"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert MAF, XMFA, or Stockholm alignments into Circos link tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_aln_to_links",
        "alignments to links",
        "alignment links",
        "MAF",
        "XMFA",
        "Stockholm",
        "comparative genomics",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    INPUT_EXTENSIONS = ["maf", "xmfa", "stockholm"]

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_ext", "maf") or "maf")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/links.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["python", "alignments-to-links.py", str(inputs.get("input", "")), cls._input_ext(inputs)]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "links.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXTENSIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Alignment file in MAF, XMFA, or Stockholm format"}),
            },
            "optional": {
                "input_ext": ("STRING", {"default": "maf", "options": cls.INPUT_EXTENSIONS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosBinlinksContract(_MappedOutputContract):
    """Reduce Circos links into binned density track rows."""

    LEGACY_NODE_ID = "circos_binlinks"
    DISPLAY_NAME = "Circos: Link Density Track"
    REQUIRED_CONDA_PACKAGES = ["circos", "circos-tools"]
    CATEGORY = "visualization"
    DESCRIPTION = "Reduce Circos links to binned density tracks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_binlinks",
        "binlinks",
        "link density",
        "density track",
        "stacked histogram",
        "comparative genomics",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["binlinks", "sed"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    LINK_END_OPTIONS = ["", "0", "1", "2"]
    OUTPUT_STYLE_OPTIONS = ["", "0", "1", "2", "3"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/link_density.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["binlinks", "-bin_size", str(inputs.get("bin_size", 1000000))]
        _add_if_value(cmd, "-link_end", inputs.get("link_end"))
        _add_if_value(cmd, "-output_style", inputs.get("output_style"))
        if inputs.get("num"):
            cmd.append("-num")
        if inputs.get("log"):
            cmd.append("-log")
        if inputs.get("normalize"):
            cmd.append("-normalize")
        return (
            f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('linksfile', '')))} "
            f"| sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "link_density.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("linksfile", "")).strip():
            return "linksfile is required"
        try:
            bin_size = int(inputs.get("bin_size", 1000000))
        except (TypeError, ValueError):
            return "bin_size must be an integer"
        if bin_size < 0:
            return "bin_size must be greater than or equal to 0"
        link_end = str(inputs.get("link_end", "") or "")
        if link_end not in cls.LINK_END_OPTIONS:
            return f"link_end must be one of: {', '.join(cls.LINK_END_OPTIONS)}"
        output_style = str(inputs.get("output_style", "") or "")
        if output_style not in cls.OUTPUT_STYLE_OPTIONS:
            return f"output_style must be one of: {', '.join(cls.OUTPUT_STYLE_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "linksfile": ("TSV", {"description": "Six-column Circos links table"}),
            },
            "optional": {
                "bin_size": ("INT", {"default": 1000000, "min": 0, "description": "Bin size"}),
                "link_end": ("STRING", {"default": "", "options": cls.LINK_END_OPTIONS}),
                "output_style": ("STRING", {"default": "", "options": cls.OUTPUT_STYLE_OPTIONS}),
                "num": ("BOOLEAN", {"default": False, "description": "Use number of links rather than sum"}),
                "log": ("BOOLEAN", {"default": False, "description": "Calculate log10 of values"}),
                "normalize": ("BOOLEAN", {"default": False, "description": "Normalize stacked histograms"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosBundlelinksContract(_MappedOutputContract):
    """Bundle adjacent Circos links into reduced link rows."""

    LEGACY_NODE_ID = "circos_bundlelinks"
    DISPLAY_NAME = "Circos: Bundle Links"
    REQUIRED_CONDA_PACKAGES = ["circos", "circos-tools"]
    CATEGORY = "visualization"
    DESCRIPTION = "Bundle adjacent Circos links before plotting."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_bundlelinks",
        "bundlelinks",
        "bundle links",
        "ribbon",
        "link reduction",
        "comparative genomics",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["bundlelinks", "sed"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    OPTIONAL_INT_MINIMUMS = {
        "max_gap": 1,
        "min_bundle_extent": 0,
        "min_bundle_size": 0,
    }

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/bundled_links.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["bundlelinks"]
        _add_if_value(cmd, "-max_gap", inputs.get("max_gap"))
        cmd.extend(["-min_bundle_membership", str(inputs.get("min_bundle_membership", 0))])
        _add_if_value(cmd, "-min_bundle_extent", inputs.get("min_bundle_extent"))
        _add_if_value(cmd, "-min_bundle_size", inputs.get("min_bundle_size"))
        _add_if_value(cmd, "-min_bundle_identity", inputs.get("min_bundle_identity"))
        return (
            f"{_shell_join(cmd)} < {shlex.quote(str(inputs.get('linksfile', '')))} "
            f"| sed 's/ /\\t/g' > {shlex.quote(cls._output_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "bundled_links.tabular"]

    @classmethod
    def _validate_optional_int_min(cls, inputs: dict[str, Any], key: str, minimum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == "":
            return True
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == "":
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if parsed < minimum or parsed > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("linksfile", "")).strip():
            return "linksfile is required"
        validation = cls._validate_optional_int_min(inputs, "min_bundle_membership", 0)
        if validation is not True:
            return validation
        for key, minimum in cls.OPTIONAL_INT_MINIMUMS.items():
            validation = cls._validate_optional_int_min(inputs, key, minimum)
            if validation is not True:
                return validation
        return cls._validate_float_range(inputs, "min_bundle_identity", 0, 1)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "linksfile": ("TSV", {"description": "Six-column Circos links table"}),
            },
            "optional": {
                "max_gap": ("INT", {"default": "", "min": 1, "description": "Maximum gap between adjacent links"}),
                "min_bundle_membership": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Minimum number of links in a bundle"},
                ),
                "min_bundle_extent": ("INT", {"default": "", "min": 0, "description": "Minimum bundle extent"}),
                "min_bundle_size": ("INT", {"default": "", "min": 0, "description": "Minimum bundle size"}),
                "min_bundle_identity": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Minimum bundle identity"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosWiggleToStackedContract(_MappedOutputContract):
    """Convert bigWig tracks into Circos stacked histogram rows."""

    LEGACY_NODE_ID = "circos_wiggle_to_stacked"
    DISPLAY_NAME = "Circos: Stack bigWigs as Histogram"
    REQUIRED_CONDA_PACKAGES = ["circos", "pybigwig"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert multiple bigWig tracks into Circos stacked-histogram rows."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_wiggle_to_stacked",
        "stacked histogram",
        "bigWig",
        "histogram",
        "track stacking",
        "comparative genomics",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/stacked_histogram.tabular"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["python", "stack-histogram.py", *_as_list(inputs.get("input"))]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "stacked_histogram.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        raw_input = inputs.get("input")
        input_files = _as_list(raw_input)
        if not input_files:
            return "at least one input value is required"
        if isinstance(raw_input, (list, tuple)) and any(str(value) == "" for value in raw_input):
            return "input values must not be empty"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BIGWIG",
                    {
                        "is_list": True,
                        "description": "bigWig files with identical chromosomes and intervals",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CircosTableviewerContract(_MappedOutputContract):
    """Create Circos tableviewer plots from tabular matrix data."""

    LEGACY_NODE_ID = "circos_tableviewer"
    DISPLAY_NAME = "Circos: Table viewer"
    REQUIRED_CONDA_PACKAGES = ["circos", "circos-tools", "tar"]
    CATEGORY = "visualization"
    DESCRIPTION = "Create Circos tableviewer plots from tabular matrix data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Circos",
        "circos_tableviewer",
        "tableviewer",
        "table viewer",
        "matrix table",
        "ribbon plot",
        "comparative genomics",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "TAR")
    RETURN_NAMES = ("output_png", "output_svg", "output_tar")
    REQUIRED_EXECUTABLES = ["parse-table", "make-conf", "circos", "tar"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/circos"
    CITATION_DOIS = CIRCOS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CIRCOS_CITATION_DOIS]
    CITATION_TEXT = CIRCOS_CITATION_TEXT
    VERSION = "0.69.8+galaxy12"
    SHELL = True

    OUTPUT_NAME_BY_BASENAME = {
        "circos.png": "output_png",
        "circos.svg": "output_svg",
        "circos.tar.gz": "output_tar",
    }

    FONT_OPTIONS = ["light", "normal", "default", "semibold", "bold", "italic", "bolditalic", "italicbold"]
    LIMIT_DEFAULTS = {
        "max_ticks": 5000,
        "max_ideograms": 200,
        "max_links": 25000,
        "max_points_per_track": 25000,
    }
    LIMIT_MINIMUM = 200

    @classmethod
    def _output_enabled(cls, inputs: dict[str, Any], key: str) -> bool:
        if key not in inputs:
            return key == "output_png"
        return bool(inputs.get(key))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["mkdir", "-p", f"{out}/circos/data", f"{out}/circos/etc"]),
            _shell_join(["cp", "circos_tableviewer.conf", f"{out}/circos/etc/circos.conf"]),
            (
                f"{_shell_join(['parse-table', '-file', str(inputs.get('table', '')), '-conf', 'circos_tableviewer_parse_table.conf'])} "
                f"> {shlex.quote(f'{out}/tmp')}"
            ),
            (
                f"{_shell_join(['make-conf', '-dir', f'{out}/circos/data'])} "
                f"< {shlex.quote(f'{out}/tmp')}"
            ),
            _shell_join(["tar", "-czf", f"{out}/circos.tar.gz", "-C", out, "circos"]),
            _shell_join(["cd", f"{out}/circos"]),
            _shell_join(["circos", "-conf", "etc/circos.conf"]),
        ]
        if cls._output_enabled(inputs, "output_png"):
            commands.append(_shell_join(["mv", "circos.png", "../circos.png"]))
        if cls._output_enabled(inputs, "output_svg"):
            commands.append(_shell_join(["mv", "circos.svg", "../circos.svg"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if cls._output_enabled(inputs, "output_png"):
            outputs.append(out / "circos.png")
        if cls._output_enabled(inputs, "output_svg"):
            outputs.append(out / "circos.svg")
        if cls._output_enabled(inputs, "output_tar"):
            outputs.append(out / "circos.tar.gz")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int = 0) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("table", "")).strip():
            return "table is required"
        if not any(cls._output_enabled(inputs, key) for key in ("output_png", "output_svg", "output_tar")):
            return "at least one of output_png, output_svg, or output_tar must be selected"
        for key, default in cls.LIMIT_DEFAULTS.items():
            validation = cls._validate_int_min(inputs, key, default, cls.LIMIT_MINIMUM)
            if validation is not True:
                return validation
        for key, default in (("segment_label_size", 50), ("tick_label_size", 24)):
            validation = cls._validate_int_min(inputs, key, default, 0)
            if validation is not True:
                return validation
        for key in ("segment_font", "tick_font"):
            font = str(inputs.get(key, "bold" if key == "segment_font" else "normal") or "")
            if font not in cls.FONT_OPTIONS:
                return f"{key} must be one of: {', '.join(cls.FONT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("TSV", {"description": "Tableviewer matrix with header row and column"}),
            },
            "optional": {
                "output_png": ("BOOLEAN", {"default": True, "description": "Output PNG plot"}),
                "output_svg": ("BOOLEAN", {"default": False, "description": "Output SVG plot"}),
                "output_tar": ("BOOLEAN", {"default": False, "description": "Output configuration archive"}),
                "segment_show_label": ("BOOLEAN", {"default": True, "description": "Show segment labels"}),
                "segment_parallel": ("BOOLEAN", {"default": False, "description": "Draw segment labels parallel"}),
                "segment_label_size": ("INT", {"default": 50, "min": 0, "description": "Segment label font size"}),
                "segment_font": ("STRING", {"default": "bold", "options": cls.FONT_OPTIONS}),
                "segment_color": ("STRING", {"default": "#000000", "description": "Segment label color"}),
                "tick_show_label": ("BOOLEAN", {"default": True, "description": "Show tick labels"}),
                "tick_parallel": ("BOOLEAN", {"default": False, "description": "Draw tick labels parallel"}),
                "tick_label_size": ("INT", {"default": 24, "min": 0, "description": "Tick label font size"}),
                "tick_font": ("STRING", {"default": "normal", "options": cls.FONT_OPTIONS}),
                "tick_color": ("STRING", {"default": "#000000", "description": "Tick label color"}),
                "max_ticks": ("INT", {"default": 5000, "min": cls.LIMIT_MINIMUM}),
                "max_ideograms": ("INT", {"default": 200, "min": cls.LIMIT_MINIMUM}),
                "max_links": ("INT", {"default": 25000, "min": cls.LIMIT_MINIMUM}),
                "max_points_per_track": ("INT", {"default": 25000, "min": cls.LIMIT_MINIMUM}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _FiltlongContract(_MappedOutputContract):
    """Filter long reads by quality, length, and optional references with Filtlong."""

    LEGACY_NODE_ID = "filtlong"
    DISPLAY_NAME = "filtlong"
    REQUIRED_CONDA_PACKAGES = ["filtlong"]
    CATEGORY = "trimming"
    DESCRIPTION = "Filter long reads by quality, length, and optional external references with Filtlong."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "filtlong",
        "Filtlong",
        "long-read filtering",
        "long-read quality",
        "Nanopore",
        "PacBio",
        "target bases",
        "read identity",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["filtlong"]
    DOCUMENTATION_URL = FILTLONG_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FILTLONG_CITATION_URL]
    CITATION_TEXT = FILTLONG_CITATION_TEXT
    VERSION = "0.3.1"
    SHELL = True

    LENGTH_PATTERN = re.compile(r"^[0-9]+(?:[KMG](?:B)?)?$", re.IGNORECASE)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fastq"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["filtlong"]
        for key in ("target_bases", "keep_percent", "min_length", "min_mean_q", "min_window_q", "max_length"):
            _add_if_value(cmd, f"--{key}", inputs.get(key))
        for key in ("assembly", "short_1", "short_2"):
            _add_if_value(cmd, f"--{key}", inputs.get(key))
        cmd.extend(["--length_weight", str(inputs.get("length_weight", 1))])
        cmd.extend(["--mean_q_weight", str(inputs.get("mean_q_weight", 1))])
        cmd.extend(["--window_q_weight", str(inputs.get("window_q_weight", 1))])
        if inputs.get("trim"):
            cmd.append("--trim")
        _add_if_value(cmd, "--split", inputs.get("split"))
        cmd.extend(["--window_size", str(inputs.get("window_size", 250))])
        cmd.append(str(inputs.get("input_file", "")))
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fastq"]

    @classmethod
    def _validate_float_min(cls, inputs: dict[str, Any], key: str, default: float | str, minimum: float) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == "":
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum:g}"
        return True

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float | str,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == "":
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if parsed < minimum or parsed > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def _validate_length_value(cls, inputs: dict[str, Any], key: str) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == "":
            return True
        if not cls.LENGTH_PATTERN.fullmatch(str(value)):
            return f"{key} must be a positive integer with optional k/kb/m/mb/g/gb suffix"
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == "":
            return True
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        for key in ("target_bases", "min_length", "max_length", "split"):
            validation = cls._validate_length_value(inputs, key)
            if validation is not True:
                return validation
        validation = cls._validate_float_range(inputs, "keep_percent", "", 0, 100)
        if validation is not True:
            return validation
        for key in ("min_mean_q", "min_window_q", "length_weight", "mean_q_weight", "window_q_weight"):
            validation = cls._validate_float_min(inputs, key, 1 if key.endswith("_weight") else "", 0)
            if validation is not True:
                return validation
        validation = cls._validate_int_min(inputs, "window_size", 250, 0)
        if validation is not True:
            return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTQ", {"description": "Long-read FASTQ input reads"}),
            },
            "optional": {
                "target_bases": (
                    "STRING",
                    {"default": "", "description": "Keep the best reads up to this total bases threshold"},
                ),
                "keep_percent": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 100, "description": "Keep this percentage of best read bases"},
                ),
                "min_length": (
                    "STRING",
                    {"default": "", "description": "Minimum read length, with optional k/kb/m/mb/g/gb suffix"},
                ),
                "max_length": (
                    "STRING",
                    {"default": "", "description": "Maximum read length, with optional k/kb/m/mb/g/gb suffix"},
                ),
                "min_mean_q": ("FLOAT", {"default": "", "min": 0, "description": "Minimum mean read quality"}),
                "min_window_q": ("FLOAT", {"default": "", "min": 0, "description": "Minimum sliding-window quality"}),
                "assembly": (
                    "FASTA",
                    {"default": "", "description": "Optional reference assembly for identity-based scoring"},
                ),
                "short_1": ("FASTQ", {"default": "", "description": "Optional first Illumina reference read set"}),
                "short_2": ("FASTQ", {"default": "", "description": "Optional second Illumina reference read set"}),
                "length_weight": ("FLOAT", {"default": 1.0, "min": 0, "description": "Weight assigned to read length"}),
                "mean_q_weight": ("FLOAT", {"default": 1.0, "min": 0, "description": "Weight assigned to mean quality"}),
                "window_q_weight": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "description": "Weight assigned to window quality"},
                ),
                "trim": (
                    "BOOLEAN",
                    {"default": False, "description": "Trim non-k-mer-matching bases from read ends"},
                ),
                "split": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Split reads at this many consecutive non-k-mer-matching bases",
                    },
                ),
                "window_size": ("INT", {"default": 250, "min": 0, "description": "Sliding window size"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
