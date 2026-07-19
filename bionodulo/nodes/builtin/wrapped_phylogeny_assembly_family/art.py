"""ART read-simulation wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class ARTIlluminaNode(CommandNode):
    """Simulate Illumina reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_illumina"
    DISPLAY_NAME = "ART Illumina"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate Illumina sequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART Illumina",
        "art_illumina",
        "Illumina read simulator",
        "synthetic sequencing reads",
        "NGS read simulation",
        "paired-end simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "SAM", "TEXT", "TEXT", "TEXT")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_sam",
        "output_aln1_single",
        "output_aln1_paired",
        "output_aln2_paired",
    )
    REQUIRED_EXECUTABLES = ["art_illumina"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end", "mate_pair"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_illumina"]
        if inputs.get("sam"):
            cmd.append("--samout")
        if not inputs.get("aln", False):
            cmd.append("--noALN")
        if choice == "paired_end":
            cmd.append("--paired")
            cmd.extend(["--mflen", str(inputs.get("fragment_size", 200)), "--sdev", str(inputs.get("fragment_sd", 0))])
        elif choice == "mate_pair":
            cmd.append("--matepair")
            cmd.extend(["--mflen", str(inputs.get("fragment_size", 200)), "--sdev", str(inputs.get("fragment_sd", 0))])
        cmd.extend(
            [
                "--in",
                str(inputs.get("input_seq_file", "")),
                "--len",
                str(inputs.get("read_length", 100)),
                "--fcov",
                str(inputs.get("fold_coverage", 20)),
            ]
        )
        if inputs.get("amplicon"):
            cmd.append("--amplicon")
        cmd.extend(
            [
                "--insRate",
                str(inputs.get("insRate", "0.00009")),
                "--insRate2",
                str(inputs.get("insRate2", "0.00015")),
                "--delRate",
                str(inputs.get("delRate", "0.00011")),
                "--delRate2",
                str(inputs.get("delRate2", "0.00023")),
            ]
        )
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["--rndSeed", str(rnd_seed)])
        cmd.extend(["--out", f"{_out(inputs)}/output"])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "single_end":
            outputs = [out / "output.fq"]
            if inputs.get("sam"):
                outputs.append(out / "output.sam")
            if inputs.get("aln", False):
                outputs.append(out / "output.aln")
            return outputs

        outputs = [out / "output1.fq", out / "output2.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        if inputs.get("aln", False):
            outputs.extend([out / "output1.aln", out / "output2.aln"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("read_length", 100, 1),
            ("fold_coverage", 20, 1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        for name, default in (
            ("insRate", 0.00009),
            ("insRate2", 0.00015),
            ("delRate", 0.00011),
            ("delRate2", 0.00023),
        ):
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end, paired-end, or mate-pair reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "read_length": ("INT", {"default": 100, "min": 1, "description": "Simulated read length"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "fragment_size": (
                    "INT",
                    {"default": 200, "min": 1, "description": "Average DNA fragment size for paired or mate-pair reads"},
                ),
                "fragment_sd": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Fragment size standard deviation"},
                ),
                "aln": ("BOOLEAN", {"default": False, "description": "Output ART ALN alignment files"}),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "insRate": ("FLOAT", {"default": 0.00009, "min": 0, "description": "First-read insertion rate"}),
                "insRate2": ("FLOAT", {"default": 0.00015, "min": 0, "description": "Second-read insertion rate"}),
                "delRate": ("FLOAT", {"default": 0.00011, "min": 0, "description": "First-read deletion rate"}),
                "delRate2": ("FLOAT", {"default": 0.00023, "min": 0, "description": "Second-read deletion rate"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ART454Node(CommandNode):
    """Simulate Roche 454 reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_454"
    DISPLAY_NAME = "ART 454"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate Roche 454 pyrosequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART 454",
        "art_454",
        "454 pyrosequencing simulator",
        "Roche 454 read simulator",
        "synthetic pyrosequencing reads",
        "amplicon sequencing simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "SAM", "TEXT", "TEXT", "TEXT")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_sam",
        "output_aln1_single",
        "output_aln1_paired",
        "output_aln2_paired",
    )
    REQUIRED_EXECUTABLES = ["art_454"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_454"]
        if inputs.get("t"):
            cmd.append("-t")
        if inputs.get("aln"):
            cmd.append("-a")
        if inputs.get("sam"):
            cmd.append("-s")
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["-r", str(rnd_seed)])
        if inputs.get("c", 100) not in (None, ""):
            cmd.extend(["-c", str(inputs.get("c", 100))])
        if inputs.get("amplicon"):
            cmd.append("-A" if choice == "single_end" else "-B")
        cmd.extend([str(inputs.get("input_seq_file", "")), f"{_out(inputs)}/output", str(inputs.get("fold_coverage", 20))])
        if choice != "single_end":
            cmd.extend([str(inputs.get("fragment_size", 200)), str(inputs.get("fragment_sd", 0))])
        if inputs.get("amplicon"):
            if choice == "single_end":
                cmd.append(str(inputs.get("reads_per_amplicon", 0)))
            else:
                cmd.append(str(inputs.get("read_pairs_per_amplicon", 0)))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "single_end":
            outputs = [out / "output.fq"]
            if inputs.get("sam"):
                outputs.append(out / "output.sam")
            if inputs.get("aln"):
                outputs.append(out / "output.aln")
            return outputs

        outputs = [out / "output1.fq", out / "output2.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        if inputs.get("aln"):
            outputs.append(out / "output1.aln")
        if inputs.get("amplicon"):
            outputs.append(out / "output2.aln")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("fold_coverage", 20, 1),
            ("c", 100, 1),
            ("rndSeed", -1, -1),
        ):
            raw = inputs.get(name, default)
            if raw in (None, "") and name == "c":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        if inputs.get("amplicon"):
            amplicon_count_name = "reads_per_amplicon" if choice == "single_end" else "read_pairs_per_amplicon"
            try:
                amplicon_count = int(inputs.get(amplicon_count_name, 0))
            except (TypeError, ValueError):
                return f"{amplicon_count_name} must be an integer"
            if amplicon_count < 0:
                return f"{amplicon_count_name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end or paired-end 454 reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "fragment_size": ("INT", {"default": 200, "min": 1, "description": "Average DNA fragment size"}),
                "fragment_sd": ("INT", {"default": 0, "min": 0, "description": "Fragment size standard deviation"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "reads_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Reads per amplicon for single-end amplicon sequencing"},
                ),
                "read_pairs_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Read pairs per amplicon for paired-end amplicon sequencing"},
                ),
                "aln": ("BOOLEAN", {"default": False, "description": "Output ART ALN alignment files"}),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "t": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the built-in GS FLX Titanium read profile"},
                ),
                "c": ("INT", {"default": 100, "min": 1, "description": "Number of sequencer flow cycles"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ARTSOLiDNode(CommandNode):
    """Simulate SOLiD reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_solid"
    DISPLAY_NAME = "ART SOLiD"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate SOLiD sequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART SOLiD",
        "art_solid",
        "art_SOLiD",
        "SOLiD read simulator",
        "color-space read simulation",
        "mate-pair simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "SAM")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_fq1_mate",
        "output_fq2_mate",
        "output_sam",
    )
    REQUIRED_EXECUTABLES = ["art_SOLiD"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end", "mate_pair"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_SOLiD"]
        if inputs.get("sam"):
            cmd.append("-s")
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["-r", str(rnd_seed)])
        if inputs.get("amplicon"):
            cmd.extend(["-A", {"single_end": "s", "paired_end": "p", "mate_pair": "m"}.get(choice, "s")])
        cmd.extend([str(inputs.get("input_seq_file", "")), f"{_out(inputs)}/output"])
        if choice == "paired_end":
            cmd.extend(
                [
                    str(inputs.get("LEN_READ_F3", 100)),
                    str(inputs.get("LEN_READ_F5", 100)),
                    str(inputs.get("fold_coverage", 20)),
                    str(inputs.get("fragment_size", 200)),
                    str(inputs.get("fragment_sd", 0)),
                ]
            )
        else:
            cmd.extend(
                [
                    str(inputs.get("LEN_READ", 100)),
                    str(inputs.get("fold_coverage", 20)),
                ]
            )
            if choice == "mate_pair":
                cmd.extend([str(inputs.get("fragment_size", 200)), str(inputs.get("fragment_sd", 0))])
        if inputs.get("amplicon"):
            if choice == "single_end":
                cmd.append(str(inputs.get("reads_per_amplicon", 0)))
            else:
                cmd.append(str(inputs.get("read_pairs_per_amplicon", 0)))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "paired_end":
            outputs = [out / "output_F3.fq", out / "output_F5.fq"]
        elif choice == "mate_pair":
            outputs = [out / "output_F3.fq", out / "output_R3.fq"]
        else:
            outputs = [out / "output.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("fold_coverage", 20, 1),
            ("rndSeed", -1, -1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        read_length_names = ("LEN_READ_F3", "LEN_READ_F5") if choice == "paired_end" else ("LEN_READ",)
        for name in read_length_names:
            try:
                value = int(inputs.get(name, 100))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        if inputs.get("amplicon"):
            amplicon_count_name = "reads_per_amplicon" if choice == "single_end" else "read_pairs_per_amplicon"
            try:
                amplicon_count = int(inputs.get(amplicon_count_name, 0))
            except (TypeError, ValueError):
                return f"{amplicon_count_name} must be an integer"
            if amplicon_count < 0:
                return f"{amplicon_count_name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end, paired-end, or mate-pair SOLiD reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "LEN_READ": ("INT", {"default": 100, "min": 1, "description": "Length of F3/R3 reads"}),
                "LEN_READ_F3": ("INT", {"default": 100, "min": 1, "description": "Length of F3 reads"}),
                "LEN_READ_F5": ("INT", {"default": 100, "min": 1, "description": "Length of F5 reads"}),
                "fragment_size": ("INT", {"default": 200, "min": 1, "description": "Average DNA fragment size"}),
                "fragment_sd": ("INT", {"default": 0, "min": 0, "description": "Fragment size standard deviation"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "reads_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Reads per amplicon for single-end amplicon sequencing"},
                ),
                "read_pairs_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Read pairs per amplicon for paired or mate-pair amplicon sequencing"},
                ),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(ARTIlluminaNode)
pin_contract(ART454Node)
pin_contract(ARTSOLiDNode)

__all__ = ["ARTIlluminaNode","ART454Node","ARTSOLiDNode"]
