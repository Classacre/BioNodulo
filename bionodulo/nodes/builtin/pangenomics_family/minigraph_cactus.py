"""Stable owner for ``minigraph_cactus``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int, _safe_output_stem, _split_path_list, _stage_file
from .evidence import PangenomicsCommandContract


class MinigraphCactusNode(PangenomicsCommandContract):
    """Build pangenome graphs from multiple assemblies with Minigraph-Cactus."""

    NODE_ID = "minigraph_cactus"
    DISPLAY_NAME = "Minigraph-Cactus"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build pangenome graphs from assemblies using the Cactus Minigraph-Cactus pipeline."
    SEARCH_ALIASES = [
        "minigraph-cactus",
        "cactus-pangenome",
        "HPRC",
        "pangenome construction",
        "whole-genome alignment",
        "giraffe",
    ]
    RETURN_TYPES = ("GBZ", "VCF_GZ", "VCF_INDEX", "GFA", "ODGI")
    RETURN_NAMES = ("graph_gbz", "variants_vcf", "variants_vcf_index", "graph_gfa", "graph_odgi")
    REQUIRED_EXECUTABLES = ["cactus-pangenome"]
    REQUIRED_CONDA_PACKAGES = ["cactus"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/pangenome.md"
    VERSION = "2.9.0"
    SIDECAR_POLICY = (
        "Every FASTA path referenced by the Cactus seqFile is an explicit assemblies input; "
        "BioNodulo stages the files and rewrites a node-local seqFile before execution."
    )

    _OUTPUT_FLAGS = ("gbz", "vcf", "gfa", "odgi")
    _OUTPUT_DEFAULTS = {"gbz": True, "vcf": True, "gfa": True, "odgi": False}

    @classmethod
    def _enabled(cls, inputs: dict[str, Any], flag: str) -> bool:
        return bool(inputs.get(flag, cls._OUTPUT_DEFAULTS[flag]))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        for name in ("seq_file", "reference"):
            if not str(inputs.get(name, "") or "").strip():
                return f"{name} is required"
        if len(_split_path_list(inputs.get("assemblies"))) < 2:
            return "assemblies must contain at least two FASTA paths in seqFile order"
        validation = _positive_int(inputs.get("threads", 16), "threads", 16)
        if isinstance(validation, str):
            return validation
        max_cores = inputs.get("max_cores", 0)
        if isinstance(max_cores, bool) or not isinstance(max_cores, int) or max_cores < 0:
            return "max_cores must be a non-negative integer"
        cons_cores = inputs.get("cons_cores", 0)
        if isinstance(cons_cores, bool) or not isinstance(cons_cores, int) or cons_cores < 0:
            return "cons_cores must be a non-negative integer"
        effective_max = max_cores or int(inputs.get("threads", 16))
        if cons_cores and cons_cores > effective_max:
            return "cons_cores must not exceed max_cores or threads"
        if not any(cls._enabled(inputs, flag) for flag in cls._OUTPUT_FLAGS):
            return "Minigraph-Cactus requires at least one graph or variant output flag."
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        seq_file = Path(_path_value(inputs["seq_file"]))
        if not seq_file.is_file():
            raise ValueError("seq_file must be an existing file")
        entries: list[tuple[str, str]] = []
        for raw_line in seq_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split(maxsplit=1)
            if len(fields) != 2 or fields[0].startswith("("):
                raise ValueError("Minigraph-Cactus seq_file must contain only sample-name and FASTA-path rows")
            entries.append((fields[0], fields[1]))

        assemblies = _split_path_list(inputs["assemblies"])
        if len(entries) != len(assemblies):
            raise ValueError("assemblies count must exactly match seq_file rows")
        labels = [label for label, _path in entries]
        if len(set(labels)) != len(labels):
            raise ValueError("seq_file sample names must be unique")
        if str(inputs["reference"]) not in labels:
            raise ValueError("reference must match a sample name in seq_file")

        stage_root = outputs[0].parent / "inputs"
        prepared_rows: list[str] = []
        staged_names: set[str] = set()
        for (label, _original_path), assembly in zip(entries, assemblies, strict=True):
            source = Path(assembly)
            suffix = "".join(source.suffixes) or ".fa"
            staged = stage_root / f"{_safe_output_stem(label, 'assembly')}{suffix}"
            if staged.name in staged_names:
                raise ValueError("seq_file sample names collide after safe staging")
            staged_names.add(staged.name)
            _stage_file(source, staged)
            prepared_rows.append(f"{label} {staged.absolute()}")

        prepared_seq_file = stage_root / "seqfile.txt"
        prepared_seq_file.write_text("\n".join(prepared_rows) + "\n", encoding="utf-8")
        inputs["seq_file"] = str(prepared_seq_file)
        inputs["assemblies"] = [row.split(maxsplit=1)[1] for row in prepared_rows]

    @classmethod
    def _out_name(cls, inputs: dict[str, Any]) -> str:
        return _safe_output_stem(inputs.get("out_name"), "pangenome")

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any], out_dir: Path) -> Path:
        if inputs.get("work_dir"):
            return Path(str(inputs["work_dir"]))
        return out_dir / "work"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        work_dir = cls._work_dir(inputs, out_dir)
        max_cores = int(inputs.get("max_cores", 0) or 0)
        if max_cores <= 0:
            max_cores = int(inputs.get("threads", 1) or 1)

        cmd = [
            "cactus-pangenome",
            str(work_dir),
            str(inputs.get("seq_file", "")),
            "--outDir",
            str(out_dir),
            "--outName",
            cls._out_name(inputs),
            "--reference",
            str(inputs.get("reference", "")),
            "--binariesMode",
            "local",
            "--maxCores",
            str(max_cores),
        ]

        cons_cores = int(inputs.get("cons_cores", 0) or 0)
        if cons_cores > 0:
            cmd.extend(["--consCores", str(cons_cores)])

        for flag in cls._OUTPUT_FLAGS:
            if cls._enabled(inputs, flag):
                cmd.append(f"--{flag}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        out_name = cls._out_name(inputs)
        outputs: list[Path] = []
        if cls._enabled(inputs, "gbz"):
            outputs.append(node_out / f"{out_name}.gbz")
        if cls._enabled(inputs, "vcf"):
            vcf = node_out / f"{out_name}.vcf.gz"
            outputs.extend([vcf, Path(f"{vcf}.tbi")])
        if cls._enabled(inputs, "gfa"):
            outputs.append(node_out / f"{out_name}.gfa.gz")
        if cls._enabled(inputs, "odgi"):
            outputs.append(node_out / f"{out_name}.full.og")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seq_file": ("FILE", {"description": "Cactus seqFile listing assembly names and FASTA paths"}),
                "assemblies": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "description": "Assembly FASTAs in the same order as seq_file rows",
                    },
                ),
                "reference": ("STRING", {"description": "Reference genome name from the seqFile"}),
            },
            "optional": {
                "out_name": ("STRING", {"default": "pangenome", "description": "Output filename prefix"}),
                "work_dir": ("STRING", {"default": "", "description": "Optional Cactus working directory"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 512, "display": "slider"}),
                "max_cores": ("INT", {"default": 0, "min": 0, "max": 512, "display": "slider"}),
                "cons_cores": ("INT", {"default": 0, "min": 0, "max": 512, "display": "slider"}),
                "gbz": ("BOOLEAN", {"default": True}),
                "vcf": ("BOOLEAN", {"default": True}),
                "gfa": ("BOOLEAN", {"default": True}),
                "odgi": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        mapped: dict[str, Path] = {}
        for path in planned_paths:
            name = path.name
            if name.endswith(".vcf.gz.tbi"):
                port = "variants_vcf_index"
            elif name.endswith(".vcf.gz"):
                port = "variants_vcf"
            elif name.endswith(".gfa.gz"):
                port = "graph_gfa"
            elif name.endswith(".full.og"):
                port = "graph_odgi"
            elif name.endswith(".gbz"):
                port = "graph_gbz"
            else:
                raise ValueError(f"{cls.NODE_ID} planned an unknown artifact: {name}")
            mapped[port] = path
        return mapped
