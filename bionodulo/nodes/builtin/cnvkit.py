"""CNVkit BioNodulo built-in nodes."""
from __future__ import annotations

import shlex
from pathlib import Path
from re import sub
from typing import Any

from bionodulo.nodes.command_node import CommandNode, _shell_join


BIONODULO_BUILTIN_ALIAS = "BioNodulo builtin"
DOI_URL = "https://doi.org/"
CNVKIT_CITATION_DOI = "10.1371/journal.pcbi.1004873"
CNVKIT_CITATION_TEXT = (
    "CNVkit: Genome-Wide Copy Number Detection and Visualization from Targeted DNA Sequencing."
)


def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))


def _safe_label(value: str) -> str:
    return sub(r"[^\w\-.]", "_", value)


class CNVkitAccessNode(CommandNode):
    """Calculate CNVkit sequence-accessible genome coordinates."""

    NODE_ID = "cnvkit_access"
    DISPLAY_NAME = "CNVkit Access"
    REQUIRED_CONDA_PACKAGES = ["cnvkit", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Calculate sequence-accessible reference genome coordinates for CNVkit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CNVkit",
        "CNVkit Access",
        "cnvkit.py access",
        "sequence-accessible coordinates",
        "copy number variation",
        "accessible genome regions",
        "masked N regions",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_sample_access",)
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#access"
    CITATION_DOIS = [CNVKIT_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CNVKIT_CITATION_DOI}"]
    CITATION_TEXT = CNVKIT_CITATION_TEXT
    VERSION = "0.9.12+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/access-excludes.bed"

    @classmethod
    def _exclude_items(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw = inputs.get("exclude")
        if raw is None or raw == "":
            values: list[Any] = []
        elif isinstance(raw, str):
            values = [item.strip() for item in raw.split(",") if item.strip()]
        elif isinstance(raw, (list, tuple)):
            values = list(raw)
        else:
            values = [raw]

        items: list[dict[str, str]] = []
        for index, value in enumerate(values, start=1):
            if isinstance(value, dict):
                path = next(
                    (
                        str(value[key])
                        for key in ("path", "file", "input", "location")
                        if value.get(key) is not None and str(value[key]).strip()
                    ),
                    "",
                )
                label = next(
                    (
                        str(value[key])
                        for key in ("element_identifier", "name", "identifier", "id")
                        if value.get(key) is not None and str(value[key]).strip()
                    ),
                    Path(path).stem or f"exclude_{index}",
                )
            else:
                path = str(value)
                label = Path(path).stem or f"exclude_{index}"
            items.append({"path": path, "label": _safe_label(label)})
        return items

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [f"ln -s {shlex.quote(str(inputs.get('fa_fname', '')))} ./genome.fasta"]
        exclude_names: list[str] = []
        for item in cls._exclude_items(inputs):
            link_name = f"{item['label']}.bed"
            exclude_names.append(link_name)
            commands.append(f"ln -s {shlex.quote(item['path'])} {shlex.quote(link_name)}")

        cmd = ["cnvkit.py", "access", "./genome.fasta"]
        for exclude_name in exclude_names:
            cmd.extend(["--exclude", exclude_name])
        min_gap_size = inputs.get("min_gap_size", 5000)
        if min_gap_size is not None and str(min_gap_size) != "":
            cmd.extend(["--min-gap-size", str(min_gap_size)])
        cmd.extend(["--output", cls._output_path(inputs)])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "access-excludes.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fa_fname", "")).strip():
            return "fa_fname is required"
        try:
            min_gap_size = int(inputs.get("min_gap_size", 5000))
        except (TypeError, ValueError):
            return "min_gap_size must be an integer"
        if min_gap_size < 0:
            return "min_gap_size must be greater than or equal to 0"
        if any(not item["path"].strip() for item in cls._exclude_items(inputs)):
            return "each exclude BED requires a path"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fa_fname": ("FASTA", {"description": "Reference genome FASTA file"}),
            },
            "optional": {
                "min_gap_size": (
                    "INT",
                    {
                        "default": 5000,
                        "min": 0,
                        "description": "Minimum gap size between accessible regions; smaller gaps are joined",
                    },
                ),
                "exclude": (
                    "BED",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Additional BED regions to exclude from accessible coordinates",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class CNVkitAntitargetNode(CommandNode):
    """Derive CNVkit antitarget BED intervals from capture targets."""

    NODE_ID = "cnvkit_antitarget"
    DISPLAY_NAME = "CNVkit Antitarget"
    REQUIRED_CONDA_PACKAGES = ["cnvkit", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Derive CNVkit antitarget BED intervals from targeted resequencing regions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CNVkit",
        "CNVkit Antitarget",
        "cnvkit.py antitarget",
        "antitarget regions",
        "off-target bins",
        "targeted resequencing",
        "copy number variation",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_capture_antitarget",)
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#antitarget"
    CITATION_DOIS = [CNVKIT_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CNVKIT_CITATION_DOI}"]
    CITATION_TEXT = CNVKIT_CITATION_TEXT
    VERSION = "0.9.12+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/capture.antitarget.bed"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [f"ln -s {shlex.quote(str(inputs.get('targets_file', '')))} ./capture.bed"]
        access = inputs.get("access")
        if access:
            commands.append(f"ln -s {shlex.quote(str(access))} ./access.bed")

        cmd = ["cnvkit.py", "antitarget", "./capture.bed"]
        if access:
            cmd.extend(["--access", "./access.bed"])
        avg_size = inputs.get("avg_size", 150000)
        if avg_size is not None and str(avg_size) != "":
            cmd.extend(["--avg-size", str(avg_size)])
        min_size = inputs.get("min_size", 25000)
        if min_size is not None and str(min_size) != "":
            cmd.extend(["--min-size", str(min_size)])
        cmd.extend(["--output", cls._output_path(inputs)])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "capture.antitarget.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("targets_file", "")).strip():
            return "targets_file is required"
        for field in ("avg_size", "min_size"):
            value = inputs.get(field)
            if value is None or str(value) == "":
                continue
            try:
                integer_value = int(value)
            except (TypeError, ValueError):
                return f"{field} must be an integer"
            if integer_value < 1:
                return f"{field} must be at least 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "targets_file": ("BED", {"description": "Input BED or interval file with target regions"}),
            },
            "optional": {
                "access": ("BED", {"description": "Regions of accessible sequence on chromosomes"}),
                "avg_size": (
                    "INT",
                    {
                        "default": 150000,
                        "min": 1,
                        "description": "Average size of antitarget bins",
                    },
                ),
                "min_size": (
                    "INT",
                    {
                        "default": 25000,
                        "min": 1,
                        "description": "Minimum size of antitarget bins",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class CNVkitTargetNode(CommandNode):
    """Prepare CNVkit target BED intervals from capture bait regions."""

    NODE_ID = "cnvkit_target"
    DISPLAY_NAME = "CNVkit Target"
    REQUIRED_CONDA_PACKAGES = ["cnvkit", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Prepare CNVkit target BED intervals from capture bait regions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CNVkit",
        "CNVkit Target",
        "cnvkit.py target",
        "baited regions",
        "capture targets",
        "target BED",
        "split target bins",
        "copy number variation",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_capture_target",)
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#target"
    CITATION_DOIS = [CNVKIT_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CNVKIT_CITATION_DOI}"]
    CITATION_TEXT = CNVKIT_CITATION_TEXT
    VERSION = "0.9.12+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/capture.split.bed"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get("input_file", ""))
        commands = [f"ln -s {shlex.quote(input_file)} ./capture.bed"]
        annotate = inputs.get("annotate")
        if annotate:
            commands.append(f"ln -s {shlex.quote(str(annotate))} ./annotate.bed")

        cmd = ["cnvkit.py", "target", input_file, "--output", cls._output_path(inputs)]
        if annotate:
            cmd.extend(["--annotate", "./annotate.bed"])
        if inputs.get("short_names"):
            cmd.append("--short-names")
        if inputs.get("split"):
            cmd.append("--split")
        avg_size = inputs.get("avg_size", 266)
        if avg_size is not None and str(avg_size) != "":
            cmd.extend(["--avg-size", str(avg_size)])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "capture.split.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        avg_size = inputs.get("avg_size")
        if avg_size is not None and str(avg_size) != "":
            try:
                integer_value = int(avg_size)
            except (TypeError, ValueError):
                return "avg_size must be an integer"
            if integer_value < 1:
                return "avg_size must be at least 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("BED", {"description": "Capture or target BED file"}),
            },
            "optional": {
                "annotate": (
                    "FILE",
                    {"description": "Gene model file used to assign names to target regions"},
                ),
                "short_names": (
                    "BOOLEAN",
                    {"default": False, "description": "Reduce multi-accession bait labels to short names"},
                ),
                "split": (
                    "BOOLEAN",
                    {"default": False, "description": "Split large tiled intervals into smaller targets"},
                ),
                "avg_size": (
                    "INT",
                    {
                        "default": 266,
                        "min": 1,
                        "description": "Average size of split target bins",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
