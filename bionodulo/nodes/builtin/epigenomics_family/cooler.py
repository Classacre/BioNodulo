"""Cooler 0.10.2 operation modes with exact conditional artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .adapter import SparseOutputEpigenomicsNode, path_value


def _split_uri(value: Any) -> tuple[str, str | None]:
    path, separator, group = str(value).partition("::")
    return path, group if separator else None


class CoolerNode(SparseOutputEpigenomicsNode):
    """Load/zoomify, sort/index, or balance a cooler artifact."""

    NODE_ID = "cooler"
    DISPLAY_NAME = "Cooler Matrix"
    DESCRIPTION = "Create, sort/index, or balance Hi-C contact matrices with cooler."
    SEARCH_ALIASES = ["cooler", "hic", "contact matrix", "cool", "mcool", "ice normalization"]
    RETURN_TYPES = ("FILE", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("base_cool", "mcool", "sorted_pairs", "sorted_pairs_index", "balanced_cooler")
    REQUIRED_EXECUTABLES = ["cooler"]
    REQUIRED_CONDA_PACKAGES = ["cooler"]
    TRANSITIVE_EXECUTABLES = ("sort", "bgzip", "pairix")
    CONDITIONAL_OUTPUTS = {
        "cload": ("base_cool", "mcool"),
        "csort": ("sorted_pairs", "sorted_pairs_index"),
        "balance": ("balanced_cooler",),
    }
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("FILE", {"description": "Pairs input for cload/csort or a .cool URI for balance"}),
                "mode": ("STRING", {"default": "cload", "options": ["cload", "csort", "balance"]}),
            },
            "optional": {
                "chrom_sizes": ("FILE", {"description": "Required for cload and csort"}),
                "bin_size": ("INT", {"default": 10000, "min": 1}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "chrom1": ("INT", {"default": 2, "min": 1}),
                "pos1": ("INT", {"default": 3, "min": 1}),
                "chrom2": ("INT", {"default": 4, "min": 1}),
                "pos2": ("INT", {"default": 5, "min": 1}),
                "cis_only": ("BOOLEAN", {"default": True, "description": "Balance only intra-chromosomal contacts"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(_split_uri(inputs.get("input_data", ""))[0]) is None:
            return "input_data is required"
        mode = str(inputs.get("mode", "cload"))
        if mode not in cls.CONDITIONAL_OUTPUTS:
            return "mode must be one of: cload, csort, balance"
        if mode in {"cload", "csort"} and path_value(inputs.get("chrom_sizes")) is None:
            return f"chrom_sizes is required for {mode}"
        if int(inputs.get("threads", 4)) < 1:
            return "threads must be at least 1"
        if mode == "cload" and int(inputs.get("bin_size", 10000)) < 1:
            return "bin_size must be at least 1"
        if mode in {"cload", "csort"}:
            fields = [int(inputs.get(name, default)) for name, default in (("chrom1", 2), ("pos1", 3), ("chrom2", 4), ("pos2", 5))]
            if any(field < 1 for field in fields) or len(set(fields)) != 4:
                return f"{mode} column numbers must be four distinct positive integers"
        return True

    @classmethod
    def _mode_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir)
        mode = str(inputs.get("mode", "cload"))
        if mode == "cload":
            return [out_dir / "matrix.cool", out_dir / "mcool.mcool"]
        if mode == "csort":
            pairs = out_dir / "sorted.pairs.gz"
            return [pairs, Path(f"{pairs}.px2")]
        return [out_dir / "balanced.cool"]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return cls._mode_paths(inputs, node_out)

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, inputs: dict[str, Any], planned_paths: list[Path]) -> dict[str, Path]:
        names = cls.CONDITIONAL_OUTPUTS[str(inputs.get("mode", "cload"))]
        return dict(zip(names, planned_paths, strict=True))

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if inputs.get("mode", "cload") != "balance":
            return
        source, group = _split_uri(inputs["input_data"])
        outputs[0].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, outputs[0])
        inputs["input_data"] = f"{outputs[0]}::{group}" if group else str(outputs[0])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        mode = str(inputs.get("mode", "cload"))
        paths = cls._mode_paths(inputs, inputs.get("output", "."))
        threads = str(inputs.get("threads", 4))
        if mode == "cload":
            balance_args = f"--nproc {threads} --convergence-policy error"
            return [
                "cooler",
                "cload",
                "pairs",
                "--chrom1",
                str(inputs.get("chrom1", 2)),
                "--pos1",
                str(inputs.get("pos1", 3)),
                "--chrom2",
                str(inputs.get("chrom2", 4)),
                "--pos2",
                str(inputs.get("pos2", 5)),
                f"{inputs['chrom_sizes']}:{inputs.get('bin_size', 10000)}",
                str(inputs["input_data"]),
                str(paths[0]),
                "&&",
                "cooler",
                "zoomify",
                "--nproc",
                threads,
                "--balance",
                "--balance-args",
                balance_args,
                "--out",
                str(paths[1]),
                str(paths[0]),
            ]
        if mode == "csort":
            return [
                "cooler",
                "csort",
                str(inputs["input_data"]),
                str(inputs["chrom_sizes"]),
                "--chrom1",
                str(inputs.get("chrom1", 2)),
                "--pos1",
                str(inputs.get("pos1", 3)),
                "--chrom2",
                str(inputs.get("chrom2", 4)),
                "--pos2",
                str(inputs.get("pos2", 5)),
                "--index",
                "pairix",
                "--nproc",
                threads,
                "--out",
                str(paths[0]),
            ]
        cmd = ["cooler", "balance"]
        if inputs.get("cis_only", True):
            cmd.append("--cis-only")
        cmd.extend(["--convergence-policy", "error", "--nproc", threads, str(inputs["input_data"])])
        return cmd
