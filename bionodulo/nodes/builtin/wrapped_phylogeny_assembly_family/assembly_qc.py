"""Assembly classification and QC wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class PlasClassNode(CommandNode):
    """Classify assembled contigs as plasmid or chromosome sequences."""

    NODE_ID = "plasclass"
    DISPLAY_NAME = "PlasClass"
    REQUIRED_CONDA_PACKAGES = ["plasclass"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Classify plasmid and chromosome sequences in metagenomic or isolate assemblies with PlasClass."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasClass",
        "plasclass",
        "plasmid sequence classification",
        "plasmid classifier",
        "chromosome classification",
        "metagenomic contigs",
        "isolate assemblies",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("classification_scores",)
    REQUIRED_EXECUTABLES = ["classify_fasta.py"]
    DOCUMENTATION_URL = "https://github.com/Shamir-Lab/PlasClass"
    CITATION_DOIS = [PLASCLASS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASCLASS_CITATION_DOI}"]
    CITATION_TEXT = PLASCLASS_CITATION_TEXT
    VERSION = "0.1.1+galaxy0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "classify_fasta.py",
            "--fasta",
            str(inputs.get("fasta", "")),
            "--outfile",
            f"{_out(inputs)}/classification_scores.tsv",
            "--num_processes",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "classification_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("fasta"):
            return "input FASTA is required"
        threads = inputs.get("threads", 1)
        try:
            if int(threads) < 1:
                return "threads must be >= 1"
        except (TypeError, ValueError):
            return "threads must be an integer"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "FASTA sequences to classify as plasmid or chromosome contigs"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PlasFlowNode(CommandNode):
    """Predict plasmid-origin contigs with PlasFlow."""

    NODE_ID = "plasflow"
    DISPLAY_NAME = "PlasFlow"
    REQUIRED_CONDA_PACKAGES = ["plasflow"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Predict plasmid sequences in metagenomic contigs with PlasFlow genome-signature models."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasFlow",
        "plasflow",
        "plasmid prediction",
        "metagenomic contigs",
        "genome signatures",
        "chromosome classification",
    ]
    RETURN_TYPES = ("TSV", "FASTA", "FASTA", "FASTA")
    RETURN_NAMES = ("probability_table", "chromosomes", "plasmids", "unclassified")
    REQUIRED_EXECUTABLES = ["PlasFlow.py"]
    DOCUMENTATION_URL = "https://github.com/smaegol/PlasFlow"
    CITATION_DOIS = [PLASFLOW_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASFLOW_CITATION_DOI}"]
    CITATION_TEXT = PLASFLOW_CITATION_TEXT
    VERSION = "1.1.0+galaxy0"
    SHELL = True

    @classmethod
    def _is_gzipped_fasta(cls, input_path: Any) -> bool:
        return Path(str(input_path or "")).suffixes[-2:] == [".fasta", ".gz"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        read_file = str(inputs.get("read_file", ""))
        if cls._is_gzipped_fasta(read_file):
            stage = f"gunzip -c {shlex.quote(read_file)} > reads.fasta"
        else:
            stage = f"ln -s {shlex.quote(read_file)} reads.fasta"
        cmd = [
            "PlasFlow.py",
            "--input",
            "reads.fasta",
            "--output",
            f"{_out(inputs)}/output",
            "--threshold",
            str(inputs.get("threshold", 0.7)),
        ]
        return f"{stage} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output",
            out / "output_chromosomes.fasta",
            out / "output_plasmids.fasta",
            out / "output_unclassified.fasta",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("read_file"):
            return "contig FASTA is required"
        try:
            threshold = float(inputs.get("threshold", 0.7))
        except (TypeError, ValueError):
            return "threshold must be a number"
        if not 0 <= threshold <= 1:
            return "threshold must be between 0 and 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "read_file": ("FASTA", {"description": "Metagenomic contig sequences in FASTA or FASTA.GZ format"}),
            },
            "optional": {
                "threshold": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "description": "Probability threshold for classification"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MiniaNode(CommandNode):
    """Assemble short reads with the Minia de Bruijn graph assembler."""

    NODE_ID = "minia"
    DISPLAY_NAME = "Minia"
    REQUIRED_CONDA_PACKAGES = ["minia"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble short reads into contigs with Minia, a compact de Bruijn graph assembler."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Minia",
        "minia",
        "short-read assembler",
        "de Bruijn graph",
        "Bloom filter",
        "contig assembly",
        "k-mer assembler",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("contigs",)
    REQUIRED_EXECUTABLES = ["minia"]
    DOCUMENTATION_URL = "https://github.com/GATB/minia"
    CITATION_DOIS = [MINIA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{MINIA_CITATION_DOI}"]
    CITATION_TEXT = MINIA_CITATION_TEXT
    VERSION = "3.2.6"
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or "")).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"infile{suffixes[-2]}{suffixes[-1]}"
        suffix = suffixes[-1] if suffixes else ".fa"
        return f"infile{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get("in"))
        cmd = [
            "minia",
            "-in",
            staged,
            "-kmer-size",
            str(inputs.get("kmer_size", 31)),
        ]
        if inputs.get("abundance_min") not in (None, ""):
            cmd.extend(["-abundance-min", str(inputs.get("abundance_min"))])
        if inputs.get("abundance_max") not in (None, ""):
            cmd.extend(["-abundance-max", str(inputs.get("abundance_max"))])
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd.extend(
            [
                "-nb-cores",
                slots,
                "-out",
                f"{_out(inputs)}/output",
            ]
        )
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"ln -s {shlex.quote(str(inputs.get('in', '')))} {staged} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.contigs.fa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("in"):
            return "input reads are required"
        for key, message in (
            ("kmer_size", "kmer_size must be >= 1"),
            ("threads", "threads must be >= 1"),
        ):
            try:
                value = int(inputs.get(key, 31 if key == "kmer_size" else 1))
            except (TypeError, ValueError):
                return message.replace(">=", "must be an integer >=")
            if value < 1:
                return message
        for key in ("abundance_min", "abundance_max"):
            if inputs.get(key) in (None, ""):
                continue
            try:
                value = int(inputs.get(key))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in": ("FASTQ", {"description": "Reads in FASTA, FASTQ, or compressed FASTA/FASTQ format"}),
            },
            "optional": {
                "kmer_size": ("INT", {"default": 31, "min": 1, "description": "K-mer size"}),
                "abundance_min": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum abundance threshold for solid k-mers"},
                ),
                "abundance_max": (
                    "INT",
                    {"default": "", "min": 0, "description": "Maximum abundance threshold for solid k-mers"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GenomeScopeNode(CommandNode):
    """Profile genomes from k-mer spectra with GenomeScope 2.0."""

    NODE_ID = "genomescope"
    DISPLAY_NAME = "GenomeScope"
    REQUIRED_CONDA_PACKAGES = ["genomescope2"]
    CATEGORY = "assembly"
    DESCRIPTION = "Profile genomes from k-mer frequency histograms with the GenomeScope 2.0 model."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GenomeScope",
        "GenomeScope 2.0",
        "genomescope2",
        "reference-free genome profiling",
        "k-mer spectrum",
        "kmer histogram",
        "polyploid genome profiling",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "TEXT", "TEXT", "TEXT", "TSV")
    RETURN_NAMES = (
        "linear_plot",
        "log_plot",
        "transformed_linear_plot",
        "transformed_log_plot",
        "model",
        "summary",
        "progress",
        "model_params",
    )
    REQUIRED_EXECUTABLES = ["genomescope2"]
    DOCUMENTATION_URL = "https://github.com/tbenavi1/genomescope2.0"
    CITATION_DOIS = GENOMESCOPE_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in GENOMESCOPE_CITATION_DOIS]
    CITATION_TEXT = GENOMESCOPE_CITATION_TEXT
    VERSION = "2.1.0+galaxy0"
    OUTPUT_CHOICES = ["model_output", "summary_output", "progress_output"]
    OUTPUT_FILES = {
        "model_output": "model.txt",
        "summary_output": "summary.txt",
        "progress_output": "progress.txt",
    }

    @classmethod
    def _output_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("output_files"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "genomescope2",
            "--input",
            str(inputs.get("input", "")),
            "--output",
            _out(inputs),
            "--kmer_length",
            str(inputs.get("kmer_length", 21)),
        ]
        if inputs.get("no_unique_sequence"):
            cmd.append("--no_unique_sequence")
        if inputs.get("testing"):
            cmd.append("--testing")
        if inputs.get("trace_flag"):
            cmd.append("--trace_flag")
        for name, flag in (
            ("ploidy", "--ploidy"),
            ("lambda", "--lambda"),
            ("max_kmercov", "--max_kmercov"),
            ("topology", "--topology"),
            ("initial_repetitiveness", "--initial_repetitiveness"),
            ("initial_heterozygosities", "--initial_heterozygosities"),
            ("transform_exp", "--transform_exp"),
            ("true_params", "--true_params"),
            ("num_rounds", "--num_rounds"),
        ):
            _add_if_value(cmd, flag, inputs.get(name))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "linear_plot.png",
            out / "log_plot.png",
            out / "transformed_linear_plot.png",
            out / "transformed_log_plot.png",
        ]
        outputs.extend(out / cls.OUTPUT_FILES[output] for output in cls._output_files(inputs) if output in cls.OUTPUT_FILES)
        if inputs.get("testing"):
            outputs.append(out / "SIMULATED_testing.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input histogram is required"
        for name, default, minimum, maximum in (
            ("kmer_length", 21, 1, None),
            ("ploidy", None, 1, 6),
            ("lambda", None, 1, None),
            ("max_kmercov", None, 1, None),
            ("topology", None, 1, None),
            ("transform_exp", None, 1, None),
            ("num_rounds", None, 1, None),
        ):
            raw = inputs.get(name, default)
            if raw in (None, ""):
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if minimum is not None and value < minimum:
                return f"{name} must be >= {minimum}"
            if maximum is not None and value > maximum:
                return f"{name} must be between {minimum} and {maximum}"
        repetitiveness = inputs.get("initial_repetitiveness")
        if repetitiveness not in (None, ""):
            try:
                repetitiveness_value = float(repetitiveness)
            except (TypeError, ValueError):
                return "initial_repetitiveness must be a number"
            if repetitiveness_value < 0 or repetitiveness_value > 1:
                return "initial_repetitiveness must be between 0 and 1"
        unsupported_outputs = [output for output in cls._output_files(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"output_files contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Two-column k-mer histogram, such as a Jellyfish histo output"}),
                "kmer_length": ("INT", {"default": 21, "min": 1, "description": "K-mer length used to calculate the spectra"}),
            },
            "optional": {
                "ploidy": ("INT", {"default": "", "min": 1, "max": 6, "description": "Ploidy for the GenomeScope model"}),
                "lambda": ("INT", {"default": "", "min": 1, "description": "Initial k-mer coverage estimate"}),
                "max_kmercov": ("INT", {"default": "", "min": 1, "description": "Maximum k-mer coverage threshold"}),
                "output_files": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OUTPUT_CHOICES,
                        "description": "Optional model, summary, and optimization progress reports",
                    },
                ),
                "no_unique_sequence": (
                    "BOOLEAN",
                    {"default": False, "description": "Turn off the yellow unique-sequence line in plots"},
                ),
                "topology": (
                    "INT",
                    {"default": "", "min": 1, "description": "Ploidy topology flag for homologous chromosome relationships"},
                ),
                "initial_repetitiveness": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Initial repetitiveness value"},
                ),
                "initial_heterozygosities": (
                    "STRING",
                    {"default": "", "description": "Comma-separated initial nucleotide heterozygosity rates"},
                ),
                "transform_exp": (
                    "INT",
                    {"default": "", "min": 1, "description": "Exponent for transformed k-mer histogram fitting"},
                ),
                "testing": ("BOOLEAN", {"default": False, "description": "Create SIMULATED_testing.tsv with model parameters"}),
                "true_params": (
                    "STRING",
                    {"default": "", "description": "Comma-separated true simulated parameters for testing mode"},
                ),
                "trace_flag": (
                    "BOOLEAN",
                    {"default": False, "description": "Print nlsLM iteration progress"},
                ),
                "num_rounds": ("INT", {"default": "", "min": 1, "description": "Number of optimization rounds"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(PlasClassNode)
pin_contract(PlasFlowNode)
pin_contract(MiniaNode)
pin_contract(GenomeScopeNode)

__all__ = ["PlasClassNode","PlasFlowNode","MiniaNode","GenomeScopeNode"]
