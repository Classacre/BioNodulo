"""RSeQC 5.0.3 ``bam2wig.py`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCBam2WigNode(RSeQCCommandNode):
    """Create WIG and BigWig coverage tracks from an indexed BAM."""

    NODE_ID = "rseqc_bam2wig"
    DISPLAY_NAME = "RSeQC BAM to Wiggle"
    DESCRIPTION = "Convert a sorted indexed BAM into WIG and BigWig coverage tracks."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "bam2wig", "BAM to Wiggle", "BigWig"]
    RETURN_TYPES = ("FILE_LIST", "FILE_LIST")
    RETURN_NAMES = ("wiggle_tracks", "bigwig_tracks")
    REQUIRED_EXECUTABLES = ["bam2wig.py", "wigToBigWig"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "ucsc-wigtobigwig"]
    UPSTREAM_SCRIPT = "scripts/bam2wig.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_CONVERTER_SOURCE = "lib/qcmodule/SAM.py:bamTowig"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#bam2wig-py"

    REQUIRED_PATH_INPUTS = ("input", "bam_index", "chromsize")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Sorted BAM alignment file"}),
                "bam_index": ("BAI", {"description": "Exact sibling input BAM index (<bam>.bai)"}),
                "chromsize": (
                    "FILE",
                    {"description": "Two-column chromosome name and size file"},
                ),
            },
            "optional": {
                "wigsum": (
                    "INT",
                    {"default": None, "description": "Target wigsum; omit to disable normalization"},
                ),
                "skip_multi_hits": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "description": "RSeQC strand rule"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        if inputs.get("strand"):
            return [
                node_dir / "outfile.Forward.wig",
                node_dir / "outfile.Reverse.wig",
                node_dir / "outfile.Forward.bw",
                node_dir / "outfile.Reverse.bw",
            ]
        return [node_dir / "outfile.wig", node_dir / "outfile.bw"]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, list[Path]]:
        """Group the native unstranded/stranded files into two stable ports."""
        wiggles = [path for path in planned_paths if path.suffix == ".wig"]
        bigwigs = [path for path in planned_paths if path.suffix == ".bw"]
        if len(wiggles) not in (1, 2) or len(bigwigs) != len(wiggles):
            raise ValueError("bam2wig must plan one or two matching WIG and BigWig tracks")
        if len(wiggles) + len(bigwigs) != len(planned_paths):
            raise ValueError("bam2wig planned an unknown output artifact")
        return {"wiggle_tracks": wiggles, "bigwig_tracks": bigwigs}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = sorted(
            {
                key
                for key in (
                    "strand_specific",
                    "pair_type",
                    "single_type",
                    "normalize",
                    "totalwig",
                )
                if key in inputs
            }
        )
        if stale:
            return f"Legacy RSeQC controls are unsupported: {', '.join(stale)}"
        validation = cls.validate_bam_index(inputs)
        if validation is not True:
            return validation
        if inputs.get("wigsum") not in (None, ""):
            validation = cls.validate_int(inputs["wigsum"], "wigsum")
            if validation is not True:
                return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        return _validate_strand_rule(inputs.get("strand", ""), "strand")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "bam2wig.py",
            "-i",
            str(inputs["input"]),
            "-s",
            str(inputs["chromsize"]),
            "-o",
            str(cls.output_prefix(inputs, "outfile")),
        )
        if inputs.get("wigsum") not in (None, ""):
            command.extend(["-t", str(inputs["wigsum"])])
        if inputs.get("skip_multi_hits"):
            command.append("-u")
        if inputs.get("strand"):
            command.extend(["-d", str(inputs["strand"])])
        command.extend(["-q", str(inputs.get("mapq", 30))])
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: [str(path) for path in paths] for name, paths in mapped.items()}}


def _validate_strand_rule(value: Any, key: str) -> bool | str:
    if value in (None, ""):
        return True
    parts = str(value).split(",")
    if len(parts) == 2:
        if {part[0] for part in parts if len(part) == 2} != {"+", "-"} or any(
            len(part) != 2 or part[1] not in "+-" for part in parts
        ):
            return f"Input '{key}' must map both single-end strands"
    elif len(parts) == 4:
        if {part[:2] for part in parts if len(part) == 3} != {"1+", "1-", "2+", "2-"} or any(
            len(part) != 3 or part[2] not in "+-" for part in parts
        ):
            return f"Input '{key}' must map all four paired-end read/strand combinations"
    else:
        return f"Input '{key}' must contain two or four RSeQC strand mappings"
    return True
