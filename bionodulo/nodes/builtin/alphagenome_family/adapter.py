"""AlphaGenome adapter wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import pin_contract

class AlphaGenomeIntervalPredictorNode(CommandNode):
    """Predict regulatory tracks for genomic intervals with AlphaGenome."""

    LEGACY_NODE_ID = "alphagenome_interval_predictor"
    DISPLAY_NAME = "AlphaGenome Interval Predictor"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Predict regulatory tracks for genomic intervals with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome interval prediction",
        "regulatory track prediction",
        "predict_interval",
        "chromatin prediction",
        "expression prediction",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("predictions",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = ["RNA_SEQ", "ATAC", "CAGE", "DNASE", "CHIP_HISTONE", "CHIP_TF", "SPLICE_SITES", "PROCAP"]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]
    OUTPUT_MODES = ["summary", "binned"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/predictions.tsv"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_interval_predictor.py")),
            "--input",
            str(inputs.get("input_bed", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-intervals",
            str(inputs.get("max_intervals", 50)),
            "--output-mode",
            output_mode,
        ]
        if output_mode == "binned":
            cmd.extend(["--bin-size", str(inputs.get("bin_size", 128))])
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "predictions.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bed", "")).strip():
            return "input_bed is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        if output_mode not in cls.OUTPUT_MODES:
            return f"output_mode must be one of: {', '.join(cls.OUTPUT_MODES)}"
        max_intervals = cls._int_range(inputs, "max_intervals", 50, 1, 1000)
        if max_intervals is not True:
            return max_intervals
        if output_mode == "binned":
            bin_size = cls._int_range(inputs, "bin_size", 128, 1, 4096)
            if bin_size is not True:
                return bin_size
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED intervals to characterize with AlphaGenome predict_interval"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks to predict",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size around each interval",
                    },
                ),
                "max_intervals": (
                    "INT",
                    {"default": 50, "min": 1, "max": 1000, "description": "Maximum BED intervals to submit"},
                ),
                "output_mode": (
                    "STRING",
                    {
                        "default": "summary",
                        "options": cls.OUTPUT_MODES,
                        "description": "Write compact interval summaries or binned signal profiles",
                    },
                ),
                "bin_size": (
                    "INT",
                    {
                        "default": 128,
                        "min": 1,
                        "max": 4096,
                        "description": "Bin size in base pairs when output_mode is binned",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_interval_predictor.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome interval predictor wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional test fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeISMScannerNode(CommandNode):
    """Perform in-silico saturation mutagenesis with AlphaGenome."""

    LEGACY_NODE_ID = "alphagenome_ism_scanner"
    DISPLAY_NAME = "AlphaGenome ISM Scanner"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Perform in-silico saturation mutagenesis with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome saturation mutagenesis",
        "in-silico saturation mutagenesis",
        "ISM scanner",
        "score_ism_variants",
        "variant scorer",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("ism_scores",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    SCORERS = [
        "RNA_SEQ",
        "RNA_SEQ_ACTIVE",
        "ATAC",
        "ATAC_ACTIVE",
        "DNASE",
        "DNASE_ACTIVE",
        "CAGE",
        "CAGE_ACTIVE",
        "PROCAP",
        "PROCAP_ACTIVE",
        "CHIP_TF",
        "CHIP_TF_ACTIVE",
        "CHIP_HISTONE",
        "CHIP_HISTONE_ACTIVE",
        "SPLICE_SITES",
        "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS",
        "CONTACT_MAPS",
        "POLYADENYLATION",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/ism_scores.tsv"

    @classmethod
    def _scorers(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "scorers" not in inputs:
            return ["RNA_SEQ", "ATAC"] if use_default else []
        return _as_list(inputs.get("scorers"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        max_workers = inputs.get("max_workers", 1) or 1
        slots = f"${{GALAXY_SLOTS:-{max_workers}}}"
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_ism_scanner.py")),
            "--input",
            str(inputs.get("input_bed", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--scorers",
            *cls._scorers(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-regions",
            str(inputs.get("max_regions", 10)),
            "--max-region-width",
            str(inputs.get("max_region_width", 200)),
            "--max-workers",
            slots,
        ]
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        _add_if_value(cmd, "--mock-ism-results", inputs.get("mock_ism_results"))
        return _shell_join(cmd).replace(shlex.quote(slots), slots)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ism_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bed", "")).strip():
            return "input_bed is required"
        scorers = cls._scorers(inputs, use_default=True)
        if not scorers:
            return "at least one scorer is required"
        unsupported = [value for value in scorers if value not in cls.SCORERS]
        if unsupported:
            return f"scorers contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        for name, default, minimum, maximum in [
            ("max_regions", 10, 1, 100),
            ("max_region_width", 200, 1, 1000),
            ("max_workers", 1, 1, 128),
        ]:
            result = cls._int_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED regions to scan with AlphaGenome saturation mutagenesis"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "scorers": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ", "ATAC"],
                        "multiple": True,
                        "options": cls.SCORERS,
                        "description": "AlphaGenome recommended variant scorers to run",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size around each scanned region",
                    },
                ),
                "max_regions": (
                    "INT",
                    {"default": 10, "min": 1, "max": 100, "description": "Maximum BED regions to scan"},
                ),
                "max_region_width": (
                    "INT",
                    {
                        "default": 200,
                        "min": 1,
                        "max": 1000,
                        "description": "Maximum width per scanned region before center trimming",
                    },
                ),
                "max_workers": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 128,
                        "advanced": True,
                        "description": "Fallback worker count used when GALAXY_SLOTS is unset",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_ism_scanner.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome ISM scanner wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
                "mock_ism_results": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional mock AnnData JSON for exercising ISM post-processing",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeSequencePredictorNode(CommandNode):
    """Predict regulatory tracks from raw DNA sequences with AlphaGenome."""

    LEGACY_NODE_ID = "alphagenome_sequence_predictor"
    DISPLAY_NAME = "AlphaGenome Sequence Predictor"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Predict regulatory tracks from DNA sequence with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome sequence prediction",
        "predict_sequence",
        "synthetic biology",
        "regulatory sequence prediction",
        "designed sequences",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("sequence_predictions",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = ["RNA_SEQ", "ATAC", "CAGE", "DNASE", "CHIP_HISTONE", "CHIP_TF", "SPLICE_SITES", "PROCAP"]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]
    OUTPUT_MODES = ["summary", "binned"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/sequence_predictions.tsv"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_sequence_predictor.py")),
            "--input",
            str(inputs.get("input_fasta", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "16KB") or "16KB"),
            "--max-sequences",
            str(inputs.get("max_sequences", 20)),
            "--output-mode",
            output_mode,
        ]
        if output_mode == "binned":
            cmd.extend(["--bin-size", str(inputs.get("bin_size", 128))])
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sequence_predictions.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fasta", "")).strip():
            return "input_fasta is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "16KB") or "16KB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        if output_mode not in cls.OUTPUT_MODES:
            return f"output_mode must be one of: {', '.join(cls.OUTPUT_MODES)}"
        max_sequences = cls._int_range(inputs, "max_sequences", 20, 1, 1000)
        if max_sequences is not True:
            return max_sequences
        if output_mode == "binned":
            bin_size = cls._int_range(inputs, "bin_size", 128, 1, 4096)
            if bin_size is not True:
                return bin_size
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "FASTA DNA sequences to characterize with AlphaGenome predict_sequence"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks to predict",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "16KB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size; shorter sequences are N-padded and longer sequences are center-trimmed",
                    },
                ),
                "max_sequences": (
                    "INT",
                    {"default": 20, "min": 1, "max": 1000, "description": "Maximum FASTA records to submit"},
                ),
                "output_mode": (
                    "STRING",
                    {
                        "default": "summary",
                        "options": cls.OUTPUT_MODES,
                        "description": "Write compact sequence summaries or binned signal profiles",
                    },
                ),
                "bin_size": (
                    "INT",
                    {
                        "default": 128,
                        "min": 1,
                        "max": 4096,
                        "description": "Bin size in base pairs when output_mode is binned",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_sequence_predictor.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome sequence predictor wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional test fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeVariantEffectNode(CommandNode):
    """Annotate VCF variants with AlphaGenome variant-effect scores."""

    LEGACY_NODE_ID = "alphagenome_variant_effect"
    DISPLAY_NAME = "AlphaGenome Variant Effect"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Annotate VCF variants with AlphaGenome variant-effect scores."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome variant effect",
        "predict_variant",
        "regulatory variant effect",
        "VCF annotation",
        "log fold change",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("annotated_vcf",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = [
        "RNA_SEQ",
        "ATAC",
        "CAGE",
        "DNASE",
        "CHIP_HISTONE",
        "CHIP_TF",
        "SPLICE_SITES",
        "PROCAP",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/annotated.vcf"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_variant_effect.py")),
            "--input",
            str(inputs.get("input_vcf", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-variants",
            str(inputs.get("max_variants", 100)),
        ]
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "annotated.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_vcf", "")).strip():
            return "input_vcf is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        max_variants = cls._int_range(inputs, "max_variants", 100, 1, 10000)
        if max_variants is not True:
            return max_variants
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_vcf": ("VCF", {"description": "VCF containing variants to score with AlphaGenome predict_variant"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks used to compute variant effect scores",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size centered on each variant",
                    },
                ),
                "max_variants": (
                    "INT",
                    {"default": 100, "min": 1, "max": 10000, "description": "Maximum VCF records to score"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_variant_effect.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome variant effect wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional precomputed variant score fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeVariantScorerNode(CommandNode):
    """Score variants with AlphaGenome gene-level quantile-normalized scores."""

    LEGACY_NODE_ID = "alphagenome_variant_scorer"
    DISPLAY_NAME = "AlphaGenome Variant Scorer"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Score variants with AlphaGenome gene-level quantile-normalized scores."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome variant scoring",
        "score_variant",
        "gene-level variant scoring",
        "quantile normalized variant score",
        "tidy_scores",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("variant_scores",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    SCORERS = [
        "RNA_SEQ",
        "RNA_SEQ_ACTIVE",
        "ATAC",
        "ATAC_ACTIVE",
        "DNASE",
        "DNASE_ACTIVE",
        "CAGE",
        "CAGE_ACTIVE",
        "PROCAP",
        "PROCAP_ACTIVE",
        "CHIP_TF",
        "CHIP_TF_ACTIVE",
        "CHIP_HISTONE",
        "CHIP_HISTONE_ACTIVE",
        "SPLICE_SITES",
        "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS",
        "CONTACT_MAPS",
        "POLYADENYLATION",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/variant_scores.tsv"

    @classmethod
    def _scorers(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "scorers" not in inputs:
            return ["RNA_SEQ", "ATAC", "SPLICE_SITES"] if use_default else []
        return _as_list(inputs.get("scorers"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_variant_scorer.py")),
            "--input",
            str(inputs.get("input_vcf", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--scorers",
            *cls._scorers(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-variants",
            str(inputs.get("max_variants", 100)),
        ]
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "variant_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_vcf", "")).strip():
            return "input_vcf is required"
        scorers = cls._scorers(inputs, use_default=True)
        if not scorers:
            return "at least one scorer is required"
        unsupported = [value for value in scorers if value not in cls.SCORERS]
        if unsupported:
            return f"scorers contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        max_variants = cls._int_range(inputs, "max_variants", 100, 1, 10000)
        if max_variants is not True:
            return max_variants
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_vcf": ("VCF", {"description": "VCF containing variants to score with AlphaGenome score_variant"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "scorers": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ", "ATAC", "SPLICE_SITES"],
                        "multiple": True,
                        "options": cls.SCORERS,
                        "description": "AlphaGenome recommended variant scorers for gene-level aggregation",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size centered on each variant before gene-level scoring",
                    },
                ),
                "max_variants": (
                    "INT",
                    {"default": 100, "min": 1, "max": 10000, "description": "Maximum VCF records to score"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_variant_scorer.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome variant scorer wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional precomputed tidy score fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AlphaGenomeIntervalPredictorNode)
pin_contract(AlphaGenomeISMScannerNode)
pin_contract(AlphaGenomeSequencePredictorNode)
pin_contract(AlphaGenomeVariantEffectNode)
pin_contract(AlphaGenomeVariantScorerNode)

__all__ = ["AlphaGenomeIntervalPredictorNode","AlphaGenomeISMScannerNode","AlphaGenomeSequencePredictorNode","AlphaGenomeVariantEffectNode","AlphaGenomeVariantScorerNode"]
