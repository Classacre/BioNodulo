"""RSeQC ``insertion_profile.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCInsertionProfileNode(RSeQCCommandNode):
    """Calculate inserted-nucleotide profiles for single- or paired-end reads."""

    NODE_ID = "rseqc_insertion_profile"
    DISPLAY_NAME = "RSeQC Insertion Profile"
    DESCRIPTION = "Calculate inserted-nucleotide distributions from BAM or SAM CIGAR strings."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "insertion_profile.py",
        "insertion profile",
        "inserted nucleotides",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "FILE_LIST")
    RETURN_NAMES = ("insertion_profile", "r_script", "insertion_profile_plots")
    REQUIRED_EXECUTABLES = ["insertion_profile.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#insertion-profile-py"
    UPSTREAM_SCRIPT = "scripts/insertion_profile.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:insertion_profile"
    REQUIRED_PATH_INPUTS = ("input",)
    LAYOUTS = ("SE", "PE")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "BAM or SAM alignment file with insertion CIGAR operations"},
                ),
                "layout": (
                    "STRING",
                    {
                        "options": list(cls.LAYOUTS),
                        "description": "Sequencing layout (SE or PE)",
                    },
                ),
            },
            "optional": {
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
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
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        layout = str(inputs.get("layout", "SE"))
        if layout == "PE":
            filenames = (
                "output.insertion_profile.xls",
                "output.insertion_profile.r",
                "output.insertion_profile.R1.pdf",
                "output.insertion_profile.R2.pdf",
            )
        else:
            filenames = (
                "output.insertion_profile.xls",
                "output.insertion_profile.r",
                "output.insertion_profile.pdf",
            )
        return [node_dir / filename for filename in filenames]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        """Group the layout-dependent PDFs into one stable logical output port."""

        paths = [Path(path) for path in planned_paths]
        if len(paths) not in (3, 4):
            raise ValueError("insertion_profile must plan a table, R script, and one or two plots")
        if paths[0].name != "output.insertion_profile.xls":
            raise ValueError("insertion_profile planned an unexpected table artifact")
        if paths[1].name != "output.insertion_profile.r":
            raise ValueError("insertion_profile planned an unexpected R script artifact")
        plots = paths[2:]
        if any(path.suffix.lower() != ".pdf" for path in plots):
            raise ValueError("insertion_profile planned a non-PDF plot artifact")
        return {
            "insertion_profile": paths[0],
            "r_script": paths[1],
            "insertion_profile_plots": plots,
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Return the variable physical plot set through one fixed list port."""

        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            raise TypeError("insertion_profile command execution must return planned paths")
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {
            "outputs": {
                "insertion_profile": str(mapped["insertion_profile"]),
                "r_script": str(mapped["r_script"]),
                "insertion_profile_plots": [str(path) for path in mapped["insertion_profile_plots"]],
            }
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "insertion_profile.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-o",
                str(cls.output_prefix(inputs)),
                "-q",
                str(inputs.get("mapq", 30)),
                "-s",
                str(inputs.get("layout")),
            ]
        )
        return command
