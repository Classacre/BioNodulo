"""RSeQC 5.0.3 ``clipping_profile.py`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCClippingProfileNode(RSeQCCommandNode):
    """Calculate clipped-base profiles for single- or paired-end reads."""

    NODE_ID = "rseqc_clipping_profile"
    DISPLAY_NAME = "RSeQC Clipping Profile"
    DESCRIPTION = "Calculate the distribution of soft-clipped bases across RNA-seq reads."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "clipping_profile", "soft clipping", "CIGAR"]
    RETURN_TYPES = ("TSV", "TEXT", "FILE_LIST")
    RETURN_NAMES = ("clipping_profile", "r_script", "clipping_plots")
    REQUIRED_EXECUTABLES = ["clipping_profile.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/clipping_profile.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:clipping_profile"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#clipping-profile-py"

    REQUIRED_PATH_INPUTS = ("input",)
    LAYOUTS = ("SE", "PE")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (("BAM", "SAM"), {"description": "SAM or BAM alignment file"}),
                "layout": ("STRING", {"options": list(cls.LAYOUTS), "description": "SE or PE"}),
            },
            "optional": {
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            node_dir / "output.clipping_profile.xls",
            node_dir / "output.clipping_profile.r",
        ]
        if inputs.get("layout") == "PE":
            outputs.extend(
                [
                    node_dir / "output.clipping_profile.R1.pdf",
                    node_dir / "output.clipping_profile.R2.pdf",
                ]
            )
        else:
            outputs.append(node_dir / "output.clipping_profile.pdf")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        """Bind the fixed report files and group the layout-dependent PDFs."""
        table = [path for path in planned_paths if path.name == "output.clipping_profile.xls"]
        scripts = [path for path in planned_paths if path.name == "output.clipping_profile.r"]
        plots = [path for path in planned_paths if path.suffix == ".pdf"]
        if len(table) != 1 or len(scripts) != 1 or len(plots) not in (1, 2):
            raise ValueError("clipping_profile planned an invalid native artifact set")
        if len(table) + len(scripts) + len(plots) != len(planned_paths):
            raise ValueError("clipping_profile planned an unknown output artifact")
        return {
            "clipping_profile": table[0],
            "r_script": scripts[0],
            "clipping_plots": plots,
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "rscript_output" in inputs:
            return "Legacy input 'rscript_output' is unsupported; the source always creates its R script"
        validation = cls.validate_choice(inputs.get("layout"), cls.LAYOUTS, "layout")
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "clipping_profile.py",
            "-i",
            str(inputs["input"]),
            "-o",
            str(cls.output_prefix(inputs, "output")),
            "-q",
            str(inputs.get("mapq", 30)),
            "-s",
            str(inputs["layout"]),
        )

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {
            "outputs": {
                name: [str(path) for path in value] if isinstance(value, list) else str(value)
                for name, value in mapped.items()
            }
        }
