"""Focused owner for ``mash_sketch``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class MashSketchNode(ToolsIUCCommandContract):
    """Create Mash MinHash sketches from reads or assemblies."""

    NODE_ID = "mash_sketch"
    DISPLAY_NAME = "Mash Sketch"
    REQUIRED_CONDA_PACKAGES = ["mash"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create reduced MinHash sequence sketches from FASTA/FASTQ reads or assemblies with Mash."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mash",
        "mash sketch",
        "minhash",
        "sketch",
        "msh",
        "genome sketch",
        "metagenome sketch",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("sketch",)
    REQUIRED_EXECUTABLES = ["mash"]
    DOCUMENTATION_URL = "https://mash.readthedocs.io/en/latest/sketches.html"
    CITATION_DOIS = ["10.1186/s13059-016-0997-x"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-016-0997-x"]
    CITATION_TEXT = "Mash: fast genome and metagenome distance estimation using MinHash."
    VERSION = "2.3"
    SHELL = True

    @classmethod
    def _linked_name(cls, value: Any) -> str:
        return _safe_name(str(value or "input"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        mode = str(inputs.get("reads_assembly_selector", inputs.get("mode", "reads")))
        prelude = ""
        input_name = ""

        if mode == "assembly":
            source = str(inputs.get("assembly", ""))
            input_name = cls._linked_name(source)
            prelude = f"ln -sf {shlex.quote(source)} {shlex.quote(input_name)}"
        else:
            reads_input = str(inputs.get("reads_input_selector", "single"))
            if reads_input == "paired":
                read1 = str(inputs.get("reads_1", ""))
                read2 = str(inputs.get("reads_2", ""))
                input_name = cls._linked_name(read1)
                prelude = f"cat {shlex.quote(read1)} {shlex.quote(read2)} > {shlex.quote(input_name)}"
            elif reads_input == "paired_collection":
                reads = inputs.get("reads", {})
                if isinstance(reads, dict):
                    read1 = str(reads.get("forward", reads.get("reads_1", "")))
                    read2 = str(reads.get("reverse", reads.get("reads_2", "")))
                    label = str(reads.get("name", read1 or "paired_reads"))
                else:
                    pair = _as_list(reads)
                    read1 = pair[0] if pair else ""
                    read2 = pair[1] if len(pair) > 1 else ""
                    label = read1 or "paired_reads"
                input_name = cls._linked_name(label)
                prelude = f"cat {shlex.quote(read1)} {shlex.quote(read2)} > {shlex.quote(input_name)}"
            else:
                source = str(inputs.get("reads", ""))
                input_name = cls._linked_name(source)
                prelude = f"ln -sf {shlex.quote(source)} {shlex.quote(input_name)}"

        cmd = [
            "mash",
            "sketch",
            "-s",
            str(inputs.get("sketch_size", 1000)),
            "-k",
            str(inputs.get("kmer_size", 21)),
            "-w",
            str(inputs.get("prob_threshold", 0.01)),
        ]
        if mode == "assembly":
            cmd.extend(["-p", str(inputs.get("threads", 1))])
            if inputs.get("individual_sequences"):
                cmd.append("-i")
        else:
            cmd.extend(["-m", str(inputs.get("minimum_kmer_copies", 1)), "-r"])
            _add_if_value(cmd, "-c", inputs.get("target_coverage"))
            _add_if_value(cmd, "-g", inputs.get("genome_size"))
        cmd.extend([input_name, "-o", f"{out}/sketch"])
        return f"{prelude} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sketch.msh"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = str(inputs.get("reads_assembly_selector", inputs.get("mode", "reads")))
        if mode not in {"reads", "assembly"}:
            return "Mash sketch mode must be reads or assembly"
        if mode == "assembly":
            if not str(inputs.get("assembly", "")).strip():
                return "Mash sketch assembly input is required"
        else:
            layout = str(inputs.get("reads_input_selector", "single"))
            if layout not in {"single", "paired", "paired_collection"}:
                return "Mash sketch read layout must be single, paired, or paired_collection"
            if layout == "single" and not str(inputs.get("reads", "")).strip():
                return "Mash sketch single-read input is required"
            if layout == "paired" and any(not str(inputs.get(key, "")).strip() for key in ("reads_1", "reads_2")):
                return "Mash sketch paired mode requires forward and reverse reads"
            if layout == "paired_collection":
                reads = inputs.get("reads", {})
                pair = (
                    [str(reads.get("forward", reads.get("reads_1", ""))), str(reads.get("reverse", reads.get("reads_2", "")))]
                    if isinstance(reads, dict)
                    else _as_list(reads)[:2]
                )
                if len(pair) != 2 or any(not path.strip() for path in pair):
                    return "Mash sketch paired collection requires forward and reverse reads"
        try:
            minimum_copies = int(inputs.get("minimum_kmer_copies", 1))
            sketch_size = int(inputs.get("sketch_size", 1000))
            kmer_size = int(inputs.get("kmer_size", 21))
            probability = float(inputs.get("prob_threshold", 0.01))
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "Mash sketch numeric options are invalid"
        if minimum_copies < 1 or sketch_size < 1 or threads < 1:
            return "Mash sketch copy count, sketch size, and threads must be positive"
        if not 1 <= kmer_size <= 32:
            return "Mash sketch k-mer size must be between 1 and 32"
        if not 0 <= probability <= 1:
            return "Mash sketch probability threshold must be between 0 and 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads_assembly_selector": ("STRING", {"default": "reads", "options": ["reads", "assembly"], "description": "Sketch reads or assembly input"}),
                "reads_input_selector": ("STRING", {"default": "single", "options": ["paired", "single", "paired_collection"], "description": "Read input layout"}),
                "reads": ("FASTQ", {"description": "Single-end reads or paired collection"}),
                "reads_1": ("FASTQ", {"description": "Forward reads for paired mode"}),
                "reads_2": ("FASTQ", {"description": "Reverse reads for paired mode"}),
                "assembly": ("FASTA", {"description": "Assembly FASTA for assembly mode"}),
            },
            "optional": {
                "minimum_kmer_copies": ("INT", {"default": 1, "min": 1, "max": 1000, "description": "Minimum copies of each k-mer for read noise filtering"}),
                "target_coverage": ("INT", {"default": "", "min": 0, "max": 500, "description": "Stop sketching when this estimated coverage is reached"}),
                "genome_size": ("INT", {"default": "", "min": 1000, "description": "Genome size used for p-value calculations"}),
                "individual_sequences": ("BOOLEAN", {"default": False, "description": "Sketch individual sequences rather than whole assembly files"}),
                "sketch_size": ("INT", {"default": 1000, "min": 10, "max": 1000000, "description": "Maximum non-redundant min-hashes per sketch"}),
                "kmer_size": ("INT", {"default": 21, "min": 1, "max": 32, "description": "k-mer size"}),
                "prob_threshold": ("FLOAT", {"default": 0.01, "min": 0, "max": 1, "description": "Warning threshold for low k-mer size"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
