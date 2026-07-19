"""Source-pinned mosdepth 0.3.14 coverage contract."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._reference_sidecars import validate_colocated_reference_index
from bionodulo.nodes.builtin.annotation_family.staging import stage_file
from bionodulo.nodes.command_node import CommandNode


def _path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _add_value(command: list[str], flag: str, value: Any) -> None:
    if _has_value(value):
        command.extend([flag, str(value)])


def _window_mode(inputs: dict[str, Any]) -> str:
    return str(inputs.get("window_mode", "no") or "no")


def _split_labels(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("\n", ",").split(",") if item.strip()]


def _quantize_from_repeat(inputs: dict[str, Any]) -> tuple[str, list[str]]:
    groups = inputs.get("quantize")
    if not isinstance(groups, (list, tuple)):
        return "", []
    depths: list[str] = []
    labels: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        depth = group.get("quant_group_mindepth", group.get("min_depth"))
        if not _has_value(depth):
            continue
        depths.append(str(depth))
        label = group.get("quant_group_name", group.get("name"))
        if _has_value(label):
            labels.append(str(label))
    return (":".join(depths) + ":" if depths else ""), labels


def _quantize_args(inputs: dict[str, Any]) -> tuple[str, list[str]]:
    depths, labels = _quantize_from_repeat(inputs)
    if not depths:
        depths = str(inputs.get("quantize_depths", "") or "")
        labels = _split_labels(inputs.get("quantize_labels"))
    if depths and not depths.endswith(":"):
        depths = f"{depths}:"
    return depths, labels


def _validate_int(value: Any, name: str, *, minimum: int | None = None, maximum: int | None = None) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if minimum is not None and value < minimum:
        return f"{name} must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"{name} must be at most {maximum}"
    return True


def _alignment_index_candidates(alignment: str) -> tuple[Path, ...]:
    path = Path(os.path.abspath(os.path.normpath(alignment)))
    if path.suffix.lower() == ".cram":
        return (Path(f"{path}.crai"),)
    return (Path(f"{path}.bai"), Path(f"{path}.csi"))


class MosdepthNode(CommandNode):
    """Compute indexed BAM/CRAM coverage and preserve native BGZF BED artifacts."""

    NODE_ID = "mosdepth"
    DISPLAY_NAME = "mosdepth"
    CATEGORY = "qc"
    DESCRIPTION = "Calculate indexed BAM/CRAM depth summaries and native BGZF/tabix coverage tracks."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "mosdepth",
        "BAM CRAM depth",
        "coverage depth",
        "per-base coverage",
        "genome coverage",
    ]
    RETURN_TYPES = (
        "TSV",
        "TSV",
        "TSV",
        "BEDGRAPH",
        "FILE",
        "BED",
        "FILE",
        "BED",
        "FILE",
        "BED",
        "FILE",
    )
    RETURN_NAMES = (
        "global_distribution",
        "summary",
        "region_distribution",
        "per_base_depth",
        "per_base_depth_index",
        "regions_bed",
        "regions_bed_index",
        "quantized_bed",
        "quantized_bed_index",
        "thresholds_bed",
        "thresholds_bed_index",
    )
    REQUIRED_EXECUTABLES = ["mosdepth"]
    REQUIRED_CONDA_PACKAGES = ["mosdepth"]
    PACKAGE_CONSTRAINTS = ("mosdepth==0.3.14",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "0.3.14"
    GIT_URL = "https://github.com/brentp/mosdepth.git"
    GIT_COMMIT = "821fddb12860d024fef4cf0bfe86918f2413d4e4"
    DOCUMENTATION_URL = "https://github.com/brentp/mosdepth/tree/v0.3.14"
    CITATION_DOIS = ["10.1093/bioinformatics/btx699"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btx699"]
    CITATION_TEXT = "Mosdepth: quick coverage calculation for genomes and exomes."
    UPSTREAM_SOURCE = "mosdepth.nim"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_alignment": ("BAM,CRAM", {"description": "Coordinate-sorted BAM or CRAM"}),
                "alignment_index": (
                    "FILE",
                    {"description": "Explicit colocated BAI/CSI/CRAI required by mosdepth"},
                ),
            },
            "optional": {
                "reference": ("FASTA", {"default": "", "description": "Reference FASTA required for CRAM"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"default": "", "description": "Exact <reference>.fai required for CRAM"},
                ),
                "threads": ("INT", {"default": 0, "min": 0, "max": 64}),
                "per_base_coverage": ("BOOLEAN", {"default": False}),
                "window_mode": ("STRING", {"default": "no", "options": ["no", "window", "bed"]}),
                "window_size": ("INT", {"default": 400, "min": 1}),
                "region_file": ("BED", {"default": ""}),
                "chrom": ("STRING", {"default": ""}),
                "exclude_flag": ("INT", {"default": "", "min": 0}),
                "include_flag": ("INT", {"default": "", "min": 0}),
                "mapq": ("INT", {"default": 0, "min": 0}),
                "fast_mode": ("BOOLEAN", {"default": False}),
                "fragment_mode": ("BOOLEAN", {"default": False}),
                "thresholds": ("STRING", {"default": ""}),
                "use_median": ("BOOLEAN", {"default": False}),
                "read_groups": ("STRING", {"default": ""}),
                "quantize_depths": ("STRING", {"default": ""}),
                "quantize_labels": ("STRING", {"default": ""}),
                "min_frag_len": ("INT", {"default": "", "min": -1}),
                "max_frag_len": ("INT", {"default": "", "min": -1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        alignment = _path_value(inputs.get("input_alignment"))
        if alignment is None:
            return "input_alignment must be a non-empty path"
        index = _path_value(inputs.get("alignment_index"))
        candidates = _alignment_index_candidates(alignment)
        if index is None:
            rendered = ", ".join(str(path) for path in candidates)
            return f"alignment_index is required; expected one of: {rendered}"
        absolute_index = Path(os.path.abspath(os.path.normpath(index)))
        if absolute_index not in candidates:
            rendered = ", ".join(str(path) for path in candidates)
            return f"alignment_index must be colocated with input_alignment; expected one of: {rendered}"
        if Path(alignment).suffix.lower() == ".cram":
            validation = validate_colocated_reference_index(inputs)
            if validation is not True:
                return validation
        for name, default, minimum, maximum in (
            ("threads", 0, 0, 64),
            ("window_size", 400, 1, None),
            ("mapq", 0, 0, None),
        ):
            validation = _validate_int(inputs.get(name, default), name, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        for name in ("exclude_flag", "include_flag", "min_frag_len", "max_frag_len"):
            if _has_value(inputs.get(name)):
                validation = _validate_int(inputs[name], name, minimum=-1 if "frag_len" in name else 0)
                if validation is not True:
                    return validation
        if inputs.get("fast_mode", False) and inputs.get("fragment_mode", False):
            return "fast_mode and fragment_mode cannot both be enabled"
        min_frag_len = int(inputs["min_frag_len"]) if _has_value(inputs.get("min_frag_len")) else -1
        max_frag_len = int(inputs["max_frag_len"]) if _has_value(inputs.get("max_frag_len")) else -1
        if max_frag_len >= 0 and max_frag_len < min_frag_len:
            return "max_frag_len cannot be lower than min_frag_len"
        mode = _window_mode(inputs)
        if mode not in {"no", "window", "bed"}:
            return "window_mode must be one of: no, window, bed"
        if mode == "bed" and _path_value(inputs.get("region_file")) is None:
            return "region_file is required when window_mode=bed"
        if str(inputs.get("thresholds") or "").strip() and mode == "no":
            return "thresholds require window_mode=window or window_mode=bed"
        thresholds = str(inputs.get("thresholds") or "").strip()
        if thresholds:
            try:
                if any(int(value.strip()) < 0 for value in thresholds.split(",")):
                    return "thresholds must contain non-negative integers"
            except ValueError:
                return "thresholds must contain comma-separated integers"
        quantize_depths, _ = _quantize_args(inputs)
        if quantize_depths:
            try:
                values = [int(value) for value in quantize_depths.split(":") if value]
            except ValueError:
                return "quantize_depths must contain colon-separated integers"
            if any(value < 0 for value in values):
                return "quantize_depths must contain non-negative integers"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source_alignment = Path(str(inputs["input_alignment"]))
        extension = ".cram" if source_alignment.suffix.lower() == ".cram" else ".bam"
        staged_alignment = outputs[0].parent / "input" / f"alignment{extension}"
        index_suffix = Path(str(inputs["alignment_index"])).suffix.lower()
        staged_index = Path(f"{staged_alignment}{index_suffix}")
        inputs["input_alignment"] = str(stage_file(source_alignment, staged_alignment))
        inputs["alignment_index"] = str(stage_file(str(inputs["alignment_index"]), staged_index))
        if extension == ".cram":
            reference = outputs[0].parent / "reference" / "reference.fa"
            reference_index = Path(f"{reference}.fai")
            inputs["reference"] = str(stage_file(str(inputs["reference"]), reference))
            inputs["reference_index"] = str(stage_file(str(inputs["reference_index"]), reference_index))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        quantize_depths, quantize_labels = _quantize_args(inputs)
        command: list[str] = []
        for index, label in enumerate(quantize_labels):
            command.extend(["export", f"MOSDEPTH_Q{index}={label}", "&&"])
        command.extend(["mosdepth", "--threads", str(inputs.get("threads", 0))])
        mode = _window_mode(inputs)
        if mode == "window":
            command.extend(["--by", str(inputs.get("window_size", 400))])
        elif mode == "bed":
            command.extend(["--by", str(inputs.get("region_file", ""))])
        if not inputs.get("per_base_coverage", False):
            command.append("--no-per-base")
        if Path(str(inputs.get("input_alignment", ""))).suffix.lower() == ".cram":
            command.extend(["--fasta", str(inputs.get("reference", ""))])
        _add_value(command, "--chrom", inputs.get("chrom"))
        _add_value(command, "--flag", inputs.get("exclude_flag"))
        _add_value(command, "--include-flag", inputs.get("include_flag"))
        if inputs.get("mapq", 0) != 0:
            command.extend(["--mapq", str(inputs["mapq"])])
        if inputs.get("fast_mode", False):
            command.append("--fast-mode")
        if inputs.get("fragment_mode", False):
            command.append("--fragment-mode")
        _add_value(command, "--thresholds", inputs.get("thresholds"))
        if inputs.get("use_median", False):
            command.append("--use-median")
        _add_value(command, "--read-groups", inputs.get("read_groups"))
        _add_value(command, "--quantize", quantize_depths)
        _add_value(command, "--min-frag-len", inputs.get("min_frag_len"))
        _add_value(command, "--max-frag-len", inputs.get("max_frag_len"))
        command.extend([str(output_dir / "output"), str(inputs.get("input_alignment", ""))])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [
            node_out / "output.mosdepth.global.dist.txt",
            node_out / "output.mosdepth.summary.txt",
        ]
        mode = _window_mode(inputs)
        if mode in {"window", "bed"}:
            outputs.append(node_out / "output.mosdepth.region.dist.txt")
        if inputs.get("per_base_coverage", False):
            outputs.extend([node_out / "output.per-base.bed.gz", node_out / "output.per-base.bed.gz.csi"])
        if mode in {"window", "bed"}:
            outputs.extend([node_out / "output.regions.bed.gz", node_out / "output.regions.bed.gz.csi"])
        quantize_depths, _ = _quantize_args(inputs)
        if quantize_depths:
            outputs.extend([node_out / "output.quantized.bed.gz", node_out / "output.quantized.bed.gz.csi"])
        if str(inputs.get("thresholds") or "").strip():
            outputs.extend([node_out / "output.thresholds.bed.gz", node_out / "output.thresholds.bed.gz.csi"])
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        names = {
            "output.mosdepth.global.dist.txt": "global_distribution",
            "output.mosdepth.summary.txt": "summary",
            "output.mosdepth.region.dist.txt": "region_distribution",
            "output.per-base.bed.gz": "per_base_depth",
            "output.per-base.bed.gz.csi": "per_base_depth_index",
            "output.regions.bed.gz": "regions_bed",
            "output.regions.bed.gz.csi": "regions_bed_index",
            "output.quantized.bed.gz": "quantized_bed",
            "output.quantized.bed.gz.csi": "quantized_bed_index",
            "output.thresholds.bed.gz": "thresholds_bed",
            "output.thresholds.bed.gz.csi": "thresholds_bed_index",
        }
        for path in planned_paths:
            mapping[names[path.name]] = path
        return mapping

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
