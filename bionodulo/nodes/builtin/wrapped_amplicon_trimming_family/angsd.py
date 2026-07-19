"""Focused ANGSD contamination-analysis nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .assets import asset_path
from .evidence import pin_contract

class ANGSDNode(CommandNode):
    """Generate ANGSD internal counts for X-contamination analysis."""

    NODE_ID = "angsd"
    DISPLAY_NAME = "ANGSD"
    REQUIRED_CONDA_PACKAGES = ["angsd", "samtools", "python"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Extract internal counts for ANGSD X-contamination analysis."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ANGSD",
        "angsd",
        "ANGSD internal counts",
        "X-contamination",
        "low coverage sequencing",
        "population genetics",
        "BAM internal counts",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("internal_counts",)
    REQUIRED_EXECUTABLES = ["angsd", "samtools"]
    DOCUMENTATION_URL = "http://www.popgen.dk/angsd/index.php/ANGSD"
    CITATION_DOIS = ANGSD_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ANGSD_CITATION_DOIS]
    CITATION_TEXT = ANGSD_CITATION_TEXT
    VERSION = "0.940+galaxy0"
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_bams"))

    @classmethod
    def _bam_indices(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("bam_indices"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        bam_filelist = f"{out}/bam.filelist"
        commands = [_shell_join(["mkdir", "-p", out]), f"touch {shlex.quote(bam_filelist)}"]
        bam_indices = cls._bam_indices(inputs)
        for index, bam in enumerate(cls._bam_files(inputs)):
            staged_bam = f"{out}/sample_{index}.bam"
            commands.append(_shell_join(["ln", "-s", bam, staged_bam]))
            if bam_indices:
                commands.append(_shell_join(["ln", "-s", bam_indices[index], f"{staged_bam}.bai"]))
            else:
                commands.append(_shell_join(["samtools", "index", staged_bam]))
            commands.append(f"echo {shlex.quote(staged_bam)} >> {shlex.quote(bam_filelist)}")
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = [
            "angsd",
            "-bam",
            bam_filelist,
            "-out",
            f"{out}/output",
            "-nThreads",
            slots,
            "-doCounts",
            "1",
            "-iCounts",
            "1",
            "-minMapQ",
            str(inputs.get("min_mapq", 20)),
            "-minQ",
            str(inputs.get("min_q", 20)),
            "-r",
            str(inputs.get("region", "")),
        ]
        commands.append(_shell_join(cmd).replace(shlex.quote(slots), slots))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.icnts.gz"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_bams = cls._bam_files(inputs)
        if not input_bams:
            return "at least one input BAM is required"
        region = str(inputs.get("region", "")).strip()
        if not region:
            return "region is required"
        if not re.fullmatch(r"[\w\d\._:-]+", region):
            return "region format must be like 'chr' or 'chr:start-end'"
        bam_indices = cls._bam_indices(inputs)
        if bam_indices and len(bam_indices) != len(input_bams):
            return "bam_indices must be empty or match input_bams length"
        for name, default, minimum in (
            ("min_mapq", 20, 0),
            ("min_q", 20, 0),
            ("threads", 1, 1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM", {"multiple": True, "description": "Coordinate-sorted BAM files"}),
                "region": (
                    "STRING",
                    {
                        "description": "Target region in ANGSD format, such as chr or chr:start-end",
                        "regex": r"^[\w\d\._:-]+$",
                    },
                ),
            },
            "optional": {
                "bam_indices": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "advanced": True,
                        "description": "Optional BAM index files aligned with input_bams",
                    },
                ),
                "min_mapq": (
                    "INT",
                    {"default": 20, "min": 0, "description": "Discard reads below this mapping quality"},
                ),
                "min_q": (
                    "INT",
                    {"default": 20, "min": 0, "description": "Discard bases below this quality"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "description": "ANGSD thread count"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ANGSDContaminationNode(CommandNode):
    """Estimate X-chromosome nuclear contamination from ANGSD internal counts."""

    NODE_ID = "angsd_contamination"
    DISPLAY_NAME = "ANGSD X-Contamination"
    REQUIRED_CONDA_PACKAGES = ["angsd", "samtools", "python"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Estimate nuclear contamination on the X chromosome for biologically male samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ANGSD X-Contamination",
        "angsd_contamination",
        "X chromosome contamination",
        "nuclear contamination",
        "ancient DNA contamination",
        "HapMap ChrX",
        "EAGER contamination",
    ]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("contamination_report", "multiqc_json")
    REQUIRED_EXECUTABLES = ["contamination", "python3"]
    DOCUMENTATION_URL = "https://nf-co.re/modules/angsd_contamination/"
    CITATION_DOIS = ANGSD_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ANGSD_CITATION_DOIS]
    CITATION_TEXT = ANGSD_CITATION_TEXT
    VERSION = "0.940+galaxy0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("icnts_file", "")), f"{out}/counts.icnts.gz"]),
            _shell_join(["ln", "-s", str(inputs.get("hapmap_file", "")), f"{out}/hapmap.gz"]),
            f"cd {shlex.quote(out)}",
            "contamination -a counts.icnts.gz -h hapmap.gz 2> contamination_report.out",
            _shell_join(
                [
                    "python3",
                    str(inputs.get("script_path") or asset_path("print_x_contamination.py")),
                    "contamination_report.out",
                ]
            ),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "nuclear_contamination.txt"]
        if inputs.get("generate_json"):
            outputs.append(out / "nuclear_contamination_mqc.json")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        icnts_file = str(inputs.get("icnts_file", "")).strip()
        if not icnts_file:
            return "icnts_file is required"
        hapmap_file = str(inputs.get("hapmap_file", "")).strip()
        if not hapmap_file:
            return "hapmap_file is required"
        if not icnts_file.endswith(".gz"):
            return "icnts_file must be a .gz file"
        if not hapmap_file.endswith(".gz"):
            return "hapmap_file must be a .gz file"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "icnts_file": ("FILE", {"description": "ANGSD internal counts output (.icnts.gz)"}),
                "hapmap_file": ("FILE", {"description": "HapMap ChrX reference file (.gz)"}),
            },
            "optional": {
                "generate_json": (
                    "BOOLEAN",
                    {"default": False, "description": "Also expose the MultiQC JSON report generated by the parser"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": asset_path("print_x_contamination.py"),
                        "advanced": True,
                        "description": "Pinned Galaxy contamination report parser",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(ANGSDNode)
pin_contract(ANGSDContaminationNode)
