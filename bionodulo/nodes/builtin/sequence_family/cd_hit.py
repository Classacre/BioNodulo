"""Focused cd hit node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class CDHitNode(CommandNode):
    """Cluster or compare protein and nucleotide FASTA datasets with CD-HIT."""

    NODE_ID = "cd_hit"
    DISPLAY_NAME = "cd-hit"
    REQUIRED_CONDA_PACKAGES = ["cd-hit"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster or compare biological sequence datasets with CD-HIT."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "cd-hit",
        "cd_hit",
        "CD-HIT",
        "cd-hit-est",
        "cd-hit-2d",
        "cd-hit-est-2d",
        "sequence clustering",
        "non-redundant sequences",
        "representative sequences",
    ]
    RETURN_TYPES = ("TXT", "FASTA")
    RETURN_NAMES = ("clusters_out", "fasta_out")
    REQUIRED_EXECUTABLES = ["cd-hit", "cd-hit-est", "cd-hit-2d", "cd-hit-est-2d"]
    DOCUMENTATION_URL = "http://weizhongli-lab.org/cd-hit/"
    CITATION_DOIS = CD_HIT_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CD_HIT_CITATION_DOIS]
    CITATION_TEXT = CD_HIT_CITATION_TEXT
    VERSION = "4.8.1+galaxy0"
    SHELL = True

    SEQUENCE_TYPES = ["protein", "nucleotide"]
    OPERATIONS = ["cluster", "2d"]
    IDENTITY_STYLES = ["global", "local"]

    @classmethod
    def _sequence_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sequence_type", "protein") or "protein")

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "cluster") or "cluster")

    @classmethod
    def _identity_style(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("identity_style", "global") or "global")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rep_seq"

    @classmethod
    def _binary(cls, inputs: dict[str, Any]) -> str:
        binary = "cd-hit"
        if cls._sequence_type(inputs) == "nucleotide":
            binary += "-est"
        if cls._operation(inputs) == "2d":
            binary += "-2d"
        return binary

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str, default: bool = False) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "1" if value.lower() in {"true", "1", "yes"} else "0"
        return "1" if bool(value) else "0"

    @classmethod
    def _inram_flag(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get("inram", True)
        if isinstance(value, str):
            inram = value.lower() in {"true", "1", "yes"}
        else:
            inram = bool(value)
        return "0" if inram else "1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = cls._sequence_type(inputs)
        operation = cls._operation(inputs)
        identity_style = cls._identity_style(inputs)
        cmd = [
            cls._binary(inputs),
            "-i",
            str(inputs.get("fasta_in", "")),
            "-o",
            cls._output_path(inputs),
            "-c",
            str(inputs.get("similarity", 0.9)),
            "-n",
            str(inputs.get("nucleotide_wordsize", 10) if sequence_type == "nucleotide" else inputs.get("protein_wordsize", 5)),
        ]
        if sequence_type == "nucleotide":
            cmd.extend(["-r", cls._bool_flag(inputs, "compare_both_strands", False)])
            _add_if_value(cmd, "-mask", inputs.get("mask"))
            cmd.extend(["-match", str(inputs.get("match", 2))])
            cmd.extend(["-mismatch", str(inputs.get("mismatch", -2))])
            cmd.extend(["-gap", str(inputs.get("gap", -6))])
            cmd.extend(["-gap-ext", str(inputs.get("gap_ext", -1))])
        else:
            cmd.extend(["-t", str(inputs.get("redtol", 2))])

        if operation == "2d":
            cmd.extend(["-i2", str(inputs.get("fasta_in2", ""))])
            if identity_style == "local":
                cmd.extend(["-s2", str(inputs.get("cutoff_diff_len2", 1.0))])
                cmd.extend(["-S2", str(inputs.get("aa_cutoff_diff_len2", 0))])

        cmd.extend(["-b", str(inputs.get("band_width", 20))])
        cmd.extend(["-l", str(inputs.get("throw_away_len", 10))])
        if identity_style == "local":
            cmd.extend(["-G", "0"])
            cmd.extend(["-aL", str(inputs.get("align_coverage_long", 0.0))])
            cmd.extend(["-AL", str(inputs.get("align_coverage_long_control", 99999999))])
            cmd.extend(["-aS", str(inputs.get("align_coverage_short", 0.0))])
            cmd.extend(["-AS", str(inputs.get("align_coverage_short_control", 99999999))])
            cmd.extend(["-A", str(inputs.get("align_coverage_min", 0))])
            cmd.extend(["-s", str(inputs.get("cutoff_diff_len", 0.0))])
            cmd.extend(["-S", str(inputs.get("aa_cutoff_diff_len", 999999))])
        cmd.extend(["-uL", str(inputs.get("max_unmatched_per_l", 1.0))])
        cmd.extend(["-uS", str(inputs.get("max_unmatched_per_s", 1.0))])
        cmd.extend(["-U", str(inputs.get("max_unmatched_len", 99999999))])
        cmd.extend(["-g", cls._bool_flag(inputs, "accurate", False)])
        cmd.extend(["-B", cls._inram_flag(inputs)])
        cmd.extend(["-sc", cls._bool_flag(inputs, "sort_cluster", False)])
        cmd.extend(["-sf", cls._bool_flag(inputs, "sort_fasta", False)])
        if inputs.get("print_alignment_overlap"):
            cmd.extend(["-p", "1", "-d", str(inputs.get("desclen", 20))])
        cmd.extend(["-M", "${GALAXY_MEMORY_MB:-0}", "-T", "${GALAXY_SLOTS:-1}"])
        return _shell_join(cmd).replace("'${GALAXY_MEMORY_MB:-0}'", "${GALAXY_MEMORY_MB:-0}").replace(
            "'${GALAXY_SLOTS:-1}'",
            "${GALAXY_SLOTS:-1}",
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "rep_seq.clstr", out / "rep_seq"]

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
    def _validate_int_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum or (maximum is not None and value > maximum):
            if maximum is None:
                return f"{key} must be greater than or equal to {minimum}"
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta_in", "")).strip():
            return "fasta_in is required"
        sequence_type = cls._sequence_type(inputs)
        if sequence_type not in cls.SEQUENCE_TYPES:
            return f"sequence_type must be one of: {', '.join(cls.SEQUENCE_TYPES)}"
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        if operation == "2d" and not str(inputs.get("fasta_in2", "")).strip():
            return "fasta_in2 is required when operation is 2d"
        style = cls._identity_style(inputs)
        if style not in cls.IDENTITY_STYLES:
            return f"identity_style must be one of: {', '.join(cls.IDENTITY_STYLES)}"
        similarity = inputs.get("similarity", 0.9)
        if sequence_type == "nucleotide":
            validation = cls._validate_float_range({"similarity": similarity}, "similarity", 0.9, 0.8, 1.0)
            if validation is not True:
                return "similarity must be between 0.8 and 1.0 for nucleotide sequences"
            validation = cls._validate_int_range(inputs, "nucleotide_wordsize", 10, 4, 11)
            if validation is not True:
                return validation
        else:
            validation = cls._validate_float_range({"similarity": similarity}, "similarity", 0.9, 0.4, 1.0)
            if validation is not True:
                return "similarity must be between 0.4 and 1.0 for protein sequences"
            validation = cls._validate_int_range(inputs, "protein_wordsize", 5, 2, 5)
            if validation is not True:
                return validation
        for key in ("band_width", "throw_away_len"):
            validation = cls._validate_int_range(inputs, key, 20 if key == "band_width" else 10, 1)
            if validation is not True:
                return validation
        for key in ("max_unmatched_per_l", "max_unmatched_per_s"):
            validation = cls._validate_float_range(inputs, key, 1.0, 0.0, 1.0)
            if validation is not True:
                return validation
        validation = cls._validate_int_range(inputs, "max_unmatched_len", 99999999, 0)
        if validation is not True:
            return validation
        if style == "local":
            for key in ("align_coverage_long", "align_coverage_short", "cutoff_diff_len", "cutoff_diff_len2"):
                validation = cls._validate_float_range(inputs, key, 0.0 if key != "cutoff_diff_len2" else 1.0, 0.0, 1.0)
                if validation is not True:
                    return validation
            for key, default in (
                ("align_coverage_long_control", 99999999),
                ("align_coverage_short_control", 99999999),
                ("align_coverage_min", 0),
                ("aa_cutoff_diff_len", 999999),
                ("aa_cutoff_diff_len2", 0),
            ):
                validation = cls._validate_int_range(inputs, key, default, 0)
                if validation is not True:
                    return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta_in": ("FASTA", {"description": "Primary protein or nucleotide FASTA sequences"}),
            },
            "optional": {
                "operation": (
                    "STRING",
                    {"default": "cluster", "options": cls.OPERATIONS, "description": "Cluster one dataset or compare against a second dataset"},
                ),
                "fasta_in2": ("FASTA", {"default": "", "description": "Second FASTA dataset for cd-hit-2d comparisons"}),
                "sequence_type": (
                    "STRING",
                    {"default": "protein", "options": cls.SEQUENCE_TYPES, "description": "Protein uses cd-hit; nucleotide uses cd-hit-est"},
                ),
                "similarity": ("FLOAT", {"default": 0.9, "min": 0.4, "max": 1.0, "description": "Sequence identity threshold"}),
                "protein_wordsize": ("INT", {"default": 5, "min": 2, "max": 5, "description": "Protein word size"}),
                "nucleotide_wordsize": ("INT", {"default": 10, "min": 4, "max": 11, "description": "Nucleotide word size"}),
                "redtol": ("INT", {"default": 2, "description": "Tolerance for redundancy in protein mode"}),
                "compare_both_strands": ("BOOLEAN", {"default": False, "description": "Compare both strands in nucleotide mode"}),
                "mask": ("STRING", {"default": "", "description": "Masking letters for nucleotide mode, for example NX"}),
                "match": ("INT", {"default": 2, "description": "Nucleotide match score"}),
                "mismatch": ("INT", {"default": -2, "description": "Nucleotide mismatch score"}),
                "gap": ("INT", {"default": -6, "description": "Nucleotide gap opening score"}),
                "gap_ext": ("INT", {"default": -1, "description": "Nucleotide gap extension score"}),
                "band_width": ("INT", {"default": 20, "min": 1, "description": "Alignment band width"}),
                "throw_away_len": ("INT", {"default": 10, "min": 1, "description": "Length threshold for throwing away short sequences"}),
                "identity_style": (
                    "STRING",
                    {"default": "global", "options": cls.IDENTITY_STYLES, "description": "Use global or local sequence identity"},
                ),
                "align_coverage_long": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Local-mode coverage for longer sequence"}),
                "align_coverage_long_control": ("INT", {"default": 99999999, "min": 0, "description": "Maximum uncovered residues for longer sequence"}),
                "align_coverage_short": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Local-mode coverage for shorter sequence"}),
                "align_coverage_short_control": ("INT", {"default": 99999999, "min": 0, "description": "Maximum uncovered residues for shorter sequence"}),
                "align_coverage_min": ("INT", {"default": 0, "min": 0, "description": "Minimum alignment coverage in residues"}),
                "cutoff_diff_len": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Length difference cutoff"}),
                "aa_cutoff_diff_len": ("INT", {"default": 999999, "min": 0, "description": "Length difference cutoff in residues"}),
                "cutoff_diff_len2": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "2D local-mode length difference cutoff"}),
                "aa_cutoff_diff_len2": ("INT", {"default": 0, "min": 0, "description": "2D local-mode length difference cutoff in residues"}),
                "max_unmatched_per_l": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "Maximum unmatched fraction for longer sequence"}),
                "max_unmatched_per_s": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "Maximum unmatched fraction for shorter sequence"}),
                "max_unmatched_len": ("INT", {"default": 99999999, "min": 0, "description": "Maximum unmatched length"}),
                "accurate": ("BOOLEAN", {"default": False, "description": "Use accurate but slower clustering"}),
                "inram": ("BOOLEAN", {"default": True, "description": "Store sequences in RAM"}),
                "sort_cluster": ("BOOLEAN", {"default": False, "description": "Sort clusters by size"}),
                "sort_fasta": ("BOOLEAN", {"default": False, "description": "Sort output FASTA by cluster size"}),
                "print_alignment_overlap": (
                    "BOOLEAN",
                    {"default": False, "description": "Print alignment overlap in the .clstr output"},
                ),
                "desclen": ("INT", {"default": 20, "min": 0, "description": "Description length for .clstr output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(CDHitNode)

__all__ = ['CDHitNode']
