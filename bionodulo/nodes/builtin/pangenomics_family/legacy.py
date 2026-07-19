"""Behavior contracts retained behind focused pangenomics owner modules."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import re
import shutil
from typing import Any

from bionodulo.nodes.builtin.pangenomics_family.evidence import PangenomicsCommandContract


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def _stage_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [os.fsdecode(os.fspath(item)) for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[\n,]+", str(value or "")) if item.strip()]


def _path_value(value: Any) -> str:
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def _positive_int(value: Any, name: str, default: int) -> int | str:
    value = default if value in (None, "") else value
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if value < 1:
        return f"{name} must be at least 1"
    return value


def _non_negative_int(value: Any, name: str, default: int = 0) -> int | str:
    value = default if value in (None, "") else value
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if value < 0:
        return f"{name} must be non-negative"
    return value


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


class _VGConstructContract(PangenomicsCommandContract):
    """Construct variation graphs from a reference FASTA and VCF."""
    LEGACY_NODE_ID = "vg_construct"
    DISPLAY_NAME = "vg Construct"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Construct a variation graph from reference FASTA and VCF variants. Foundation for pangenome alignment."
    SEARCH_ALIASES = ["vg", "construct", "variation graph", "pangenome", "graph genome"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("vg_graph",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True
    SIDECAR_POLICY = (
        "vg 1.63.1 fastahack reads <reference>.fai when present and otherwise writes a new sibling index. "
        "BioNodulo stages the reference in a writable node-local directory so no invented reference-index port is needed. "
        "The vendored vcflib/tabixpp path requires an exact <compressed-vcf>.tbi sibling, exposed as vcf_index."
    )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("reference", "vcf"):
            if not _path_value(inputs.get(name)):
                return f"{name} must be a non-empty path-like value"
        reference = _path_value(inputs.get("reference")).lower()
        if reference.endswith((".gz", ".bgz")):
            return "reference must be an uncompressed FASTA because vg fastahack opens it as plain text"
        vcf = _path_value(inputs.get("vcf"))
        compressed_vcf = vcf.lower().endswith((".gz", ".bgz"))
        vcf_index = _path_value(inputs.get("vcf_index"))
        if compressed_vcf and not vcf_index:
            return "vcf_index is required for a bgzip-compressed VCF"
        if not compressed_vcf and vcf_index:
            return "vcf_index is only valid when vcf is bgzip-compressed"
        for name, default in (("max_node_size", 32), ("threads", 1)):
            validation = _positive_int(inputs.get(name, default), name, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        stage_root = outputs[0].parent / "inputs"
        if stage_root.exists():
            shutil.rmtree(stage_root)

        staged_reference = stage_root / "reference.fa"
        _stage_file(Path(_path_value(inputs["reference"])), staged_reference)
        inputs["reference"] = str(staged_reference)

        source_vcf = Path(_path_value(inputs["vcf"]))
        compressed_vcf = source_vcf.name.lower().endswith((".gz", ".bgz"))
        staged_vcf = stage_root / ("variants.vcf.gz" if compressed_vcf else "variants.vcf")
        _stage_file(source_vcf, staged_vcf)
        inputs["vcf"] = str(staged_vcf)
        if compressed_vcf:
            _stage_file(Path(_path_value(inputs["vcf_index"])), Path(f"{staged_vcf}.tbi"))
            inputs["vcf_index"] = f"{staged_vcf}.tbi"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = inputs.get("output", ".")
        cmd = [
            "vg",
            "construct",
            "-r",
            str(inputs.get("reference", "")),
            "-v",
            str(inputs.get("vcf", "")),
        ]
        if inputs.get("alt_paths", True):
            cmd.append("-a")
        if inputs.get("flat_alts", True):
            cmd.append("-f")
        if inputs.get("handle_sv", True):
            cmd.append("-S")
        if inputs.get("region"):
            cmd.extend(["-R", str(inputs["region"])])
        cmd.extend(["-m", str(inputs.get("max_node_size", 32))])
        cmd.extend(["-t", str(inputs.get("threads", 1))])
        if inputs.get("progress"):
            cmd.append("-p")
        cmd.extend([">", f"{out_dir}/vg_graph.vg"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "vg_graph.vg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "vcf": ("FILE", {"description": "Plain or bgzip-compressed VCF to embed"}),
            },
            "optional": {
                "vcf_index": (
                    "VCF_INDEX",
                    {
                        "default": "",
                        "description": "Exact tabix <vcf>.tbi sidecar required when vcf is bgzip-compressed",
                    },
                ),
                "region": ("STRING", {"default": "", "description": "Region (e.g., chr1:1-1000000)"}),
                "max_node_size": ("INT", {"default": 32, "min": 1}),
                "threads": ("INT", {"default": 1, "min": 1}),
                "alt_paths": ("BOOLEAN", {"default": True, "description": "Retain hashed alternate paths (-a)"}),
                "flat_alts": ("BOOLEAN", {"default": True, "description": "Do not chop alternate alleles (-f)"}),
                "handle_sv": ("BOOLEAN", {"default": True, "description": "Include structural variants (-S)"}),
                "progress": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _VGIndexContract(PangenomicsCommandContract):
    """Build vg autoindex artifacts for graph read mapping."""

    LEGACY_NODE_ID = "vg_index"
    DISPLAY_NAME = "vg Autoindex"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build vg autoindex files for Giraffe graph read mapping and downstream graph calling."
    SEARCH_ALIASES = ["vg", "autoindex", "giraffe", "gbz", "minimizer", "distance index", "pangenome index"]
    RETURN_TYPES = ("GBZ", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("gbz_index", "minimizer_index", "zipcode_index", "distance_index", "xg_index")
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg/wiki/Automatic-indexing-for-read-mapping-and-downstream-inference"
    VERSION = "1.62.0"
    SHELL = True

    _WORKFLOWS = {"giraffe"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        if workflow not in cls._WORKFLOWS:
            return f"Unsupported vg Autoindex workflow: {workflow}"
        if not _path_value(inputs.get("graph_gfa")):
            return "graph_gfa must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        target_mem = str(inputs.get("target_mem", "") or "")
        if target_mem and not re.fullmatch(r"[1-9][0-9]*[kMG]?", target_mem):
            return "target_mem must use vg's INT[kMG] format"
        return True

    @classmethod
    def _prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get("graph_gfa"), "graph")
        stem = _safe_output_stem(inputs.get("output_prefix"), fallback_stem)
        return node_out / stem

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        prefix = cls._prefix(inputs, out_dir)
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        gbz_index = f"{prefix}.giraffe.gbz"
        xg_index = f"{prefix}.xg"

        cmd = [
            "vg",
            "autoindex",
            "--workflow",
            workflow,
            "--gfa",
            str(inputs.get("graph_gfa", "")),
        ]
        cmd.extend([
            "--prefix",
            str(prefix),
            "--threads",
            str(inputs.get("threads", 8)),
        ])
        if inputs.get("tmp_dir"):
            cmd.extend(["--tmp-dir", str(inputs["tmp_dir"])])
        if inputs.get("target_mem"):
            cmd.extend(["--target-mem", str(inputs["target_mem"])])
        cmd.extend([
            "&&",
            "vg",
            "convert",
            "-x",
            "--drop-haplotypes",
            gbz_index,
            ">",
            xg_index,
            "&&",
            "test",
            "-s",
            gbz_index,
            "&&",
            "test",
            "-s",
            f"{prefix}.shortread.withzip.min",
            "&&",
            "test",
            "-s",
            f"{prefix}.shortread.zipcodes",
            "&&",
            "test",
            "-s",
            f"{prefix}.dist",
            "&&",
            "test",
            "-s",
            xg_index,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = cls._prefix(inputs, node_out)
        return [
            Path(f"{prefix}.giraffe.gbz"),
            Path(f"{prefix}.shortread.withzip.min"),
            Path(f"{prefix}.shortread.zipcodes"),
            Path(f"{prefix}.dist"),
            Path(f"{prefix}.xg"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "workflow": ("STRING", {"default": "giraffe", "options": ["giraffe"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
                "output_prefix": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "tmp_dir": ("STRING", {"default": "", "description": "Optional temporary directory for vg autoindex"}),
                "target_mem": ("STRING", {"default": "", "description": "Optional target memory limit, for example 64G"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _VGMapContract(PangenomicsCommandContract):
    """Map reads to variation graphs with vg map or giraffe."""
    LEGACY_NODE_ID = "vg_map"
    DISPLAY_NAME = "vg Map/Giraffe"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Map reads to a variation graph using vg map or vg giraffe. Produces GAM alignments."
    SEARCH_ALIASES = ["vg", "map", "giraffe", "pangenome align", "graph alignment", "gam"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("gam_alignment",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True
    SIDECAR_POLICY = (
        "Classic vg map loads the GCSA LCP array from <gcsa_index>.lcp; "
        "gcsa_index and gcsa_lcp are explicit inputs staged under that exact sibling name."
    )

    _MAPPERS = {"giraffe", "map"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not _path_value(inputs.get("reads")):
            return "reads must be a non-empty path-like value"
        mapper = str(inputs.get("mapper", "giraffe") or "giraffe")
        if mapper not in cls._MAPPERS:
            return f"Unsupported vg mapper: {mapper}"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        required = (
            ("gbz_index", "minimizer_index", "distance_index")
            if mapper == "giraffe"
            else ("xg_index", "gcsa_index", "gcsa_lcp")
        )
        for name in required:
            if not _path_value(inputs.get(name)):
                return f"{name} is required for mapper={mapper}"
        min_identity = inputs.get("min_identity", 0.0)
        if isinstance(min_identity, bool) or not isinstance(min_identity, (int, float)):
            return "min_identity must be a number"
        if not 0 <= float(min_identity) <= 1:
            return "min_identity must be between 0 and 1"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if str(inputs.get("mapper", "giraffe") or "giraffe") != "map":
            return
        stage_root = outputs[0].parent / "inputs"
        staged_gcsa = stage_root / "graph.gcsa"
        _stage_file(Path(_path_value(inputs["gcsa_index"])), staged_gcsa)
        staged_lcp = Path(f"{staged_gcsa}.lcp")
        _stage_file(Path(_path_value(inputs["gcsa_lcp"])), staged_lcp)
        inputs["gcsa_index"] = str(staged_gcsa)
        inputs["gcsa_lcp"] = str(staged_lcp)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        mapper = inputs.get("mapper", "giraffe")
        reads = str(inputs.get("reads", ""))
        reads2 = str(inputs.get("reads2", ""))
        threads = str(inputs.get("threads", 8))

        if mapper == "giraffe":
            cmd = [
                "vg",
                "giraffe",
                "-Z",
                str(inputs.get("gbz_index", "")),
                "-m",
                str(inputs.get("minimizer_index", "")),
                "-d",
                str(inputs.get("distance_index", "")),
                "-f",
                reads,
                "-t",
                threads,
            ]
            if reads2:
                cmd.extend(["-f", reads2])
            if inputs.get("zipcode_index"):
                distance_index = cmd.index("-d")
                cmd[distance_index:distance_index] = ["-z", str(inputs["zipcode_index"])]
        else:
            cmd = [
                "vg",
                "map",
                "-x",
                str(inputs.get("xg_index", "")),
                "-g",
                str(inputs.get("gcsa_index", "")),
                "-f",
                reads,
                "-t",
                threads,
            ]
            if reads2:
                cmd.extend(["-f", reads2])
            if float(inputs.get("min_identity", 0.0) or 0.0) > 0:
                cmd.extend(["--min-ident", str(inputs["min_identity"])])
        if inputs.get("progress"):
            cmd.append("-p")
        cmd.extend([">", str(out_dir / "gam_alignment.gam")])
        cmd.extend(["&&", "test", "-s", str(out_dir / "gam_alignment.gam")])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "gam_alignment.gam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Forward/single-end FASTQ"}),
                "mapper": ("STRING", {"default": "giraffe", "options": ["giraffe", "map"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "gbz_index": ("GBZ", {"description": "Giraffe GBZ graph"}),
                "minimizer_index": ("FILE", {"description": "Minimizer index"}),
                "zipcode_index": ("FILE", {"description": "Optional oversized-zipcode distance hints"}),
                "distance_index": ("FILE", {"description": "Distance index"}),
                "xg_index": ("FILE", {"description": "XG index (for vg map)"}),
                "gcsa_index": ("FILE", {"description": "GCSA index (for vg map)"}),
                "gcsa_lcp": (
                    "FILE",
                    {"description": "Exact <gcsa_index>.lcp sidecar required by vg map"},
                ),
                "min_identity": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "progress": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _VGCallContract(PangenomicsCommandContract):
    """Call variants from graph alignments with vg."""
    LEGACY_NODE_ID = "vg_call"
    DISPLAY_NAME = "vg Call Variants"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call variants from graph alignments (GAM) using vg pack + vg call. Produces VCF."
    SEARCH_ALIASES = ["vg", "call", "variant calling", "pangenome", "graph caller"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("calls_vcf",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("xg_graph", "gam"):
            if not _path_value(inputs.get(name)):
                return f"{name} must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 4), "threads", 4)
        if isinstance(validation, str):
            return validation
        min_support = str(inputs.get("min_support", "") or "")
        if min_support and not re.fullmatch(r"[0-9]+,[0-9]+", min_support):
            return "min_support must use vg's M,N format"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        pack = out_dir / "aln.pack"
        calls_vcf = out_dir / "calls_vcf.vcf"
        graph = str(inputs.get("xg_graph", ""))
        threads = str(inputs.get("threads", 4))

        cmd = [
            "vg",
            "pack",
            "-x",
            graph,
            "-g",
            str(inputs.get("gam", "")),
            "-o",
            str(pack),
            "-t",
            threads,
            "&&",
            "test",
            "-s",
            str(pack),
            "&&",
            "vg",
            "call",
            graph,
            "-k",
            str(pack),
            "-t",
            threads,
        ]
        if inputs.get("min_support"):
            cmd.extend(["-m", str(inputs["min_support"])])
        if inputs.get("ref_path"):
            cmd.extend(["-p", str(inputs["ref_path"])])
        if inputs.get("sample"):
            cmd.extend(["-s", str(inputs["sample"])])
        cmd.extend([">", str(calls_vcf)])
        cmd.extend(["&&", "test", "-s", str(calls_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "calls_vcf.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xg_graph": ("FILE", {"description": "Input XG graph index"}),
                "gam": ("FILE", {"description": "Graph alignments in GAM format"}),
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "optional": {
                "ref_path": ("STRING", {"default": "", "description": "Reference path for VCF coordinates"}),
                "sample": ("STRING", {"default": "", "description": "Sample name for genotype calls"}),
                "min_support": ("STRING", {"default": "", "description": "Minimum allele,site support as M,N"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _VCFDecomposeContract(PangenomicsCommandContract):
    """Decompose complex pangenome VCF records into primitive alleles."""

    LEGACY_NODE_ID = "vcf_decompose"
    DISPLAY_NAME = "VCF Decompose"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Decompose complex variants in a pangenome VCF into primitive, normalized records."
    SEARCH_ALIASES = ["vcf", "decompose", "pangenome vcf", "primitive variants", "vcflib", "normalize"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("decomposed_vcf", "decomposed_vcf_index")
    REQUIRED_EXECUTABLES = ["vcfwave", "vcfallelicprimitives", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vcflib", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vcflib/vcflib"
    VERSION = "1.0.9"
    SHELL = True

    _MODES = {"decompose", "normalize"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get("mode", "normalize") or "normalize")
        if mode not in cls._MODES:
            return f"Unsupported VCF decompose mode: {mode}"
        if not _path_value(inputs.get("vcf")):
            return "vcf must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 1), "threads", 1)
        if isinstance(validation, str):
            return validation
        validation = _non_negative_int(inputs.get("max_length", 0), "max_length")
        if isinstance(validation, str):
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        output_vcf = out_dir / "decomposed_vcf.vcf.gz"
        mode = str(inputs.get("mode", "normalize") or "normalize")
        threads = int(inputs.get("threads", 1) or 1)
        max_length = int(inputs.get("max_length", 0) or 0)

        if mode == "normalize":
            cmd = ["vcfwave", "--threads", str(threads)]
            if max_length:
                cmd.extend(["--max-length", str(max_length)])
            cmd.append(str(inputs.get("vcf", "")))
        else:
            cmd = ["vcfallelicprimitives"]
            if inputs.get("keep_info"):
                cmd.append("--keep-info")
            if max_length:
                cmd.extend(["--max-length", str(max_length)])
            cmd.append(str(inputs.get("vcf", "")))

        cmd.extend(["|", "bgzip"])
        cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-c",
            ">",
            str(output_vcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        vcf = node_out / "decomposed_vcf.vcf.gz"
        return [vcf, Path(f"{vcf}.tbi")]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("FILE", {"description": "Plain or compressed complex-variant VCF"}),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "normalize",
                        "options": ["decompose", "normalize"],
                        "description": "normalize uses recommended vcfwave; decompose uses legacy vcfallelicprimitives",
                    },
                ),
                "keep_info": (
                    "BOOLEAN",
                    {"default": False, "description": "Legacy primitives only; vcfwave ignores keep-info"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
                "max_length": ("INT", {"default": 0, "min": 0, "description": "0 means unlimited"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _PangenomeSVContract(PangenomicsCommandContract):
    """Call structural variants from a pangenome graph against a reference path."""

    LEGACY_NODE_ID = "pangenome_sv"
    DISPLAY_NAME = "Pangenome SV"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call structural variants from a pangenome graph against a reference and emit an indexed VCF."
    SEARCH_ALIASES = ["pangenome", "structural variants", "sv", "graph vcf", "pangenome graph", "vg deconstruct"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("sv_vcf", "sv_vcf_index")
    REQUIRED_EXECUTABLES = ["vg", "bcftools", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vg", "bcftools", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _path_value(inputs.get("graph_gfa")):
            return "graph_gfa must be a non-empty path-like value"
        if not str(inputs.get("ref_path", "") or "").strip():
            return "ref_path is required"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        validation = _non_negative_int(inputs.get("min_sv_length", 50), "min_sv_length", 50)
        if isinstance(validation, str):
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        xg_index = out_dir / "graph.xg"
        output_vcf = out_dir / "sv_vcf.vcf.gz"
        threads = int(inputs.get("threads", 8) or 8)
        min_sv_length = int(inputs.get("min_sv_length", 0) or 0)

        cmd: list[str] = [
            "vg",
            "convert",
            "-x",
            str(inputs.get("graph_gfa", "")),
            ">",
            str(xg_index),
            "&&",
            "vg",
            "deconstruct",
            "-P",
            str(inputs.get("ref_path", "")),
            "-a",
            "-t",
            str(threads),
            str(xg_index),
        ]

        if min_sv_length > 0:
            cmd.extend([
                "|",
                "bcftools",
                "view",
                "-i",
                f"ABS(ILEN)>={min_sv_length} || ABS(strlen(ALT)-strlen(REF))>={min_sv_length}",
            ])
        cmd.extend(["|", "bgzip"])
        cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-c",
            ">",
            str(output_vcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        vcf = node_out / "sv_vcf.vcf.gz"
        return [vcf, Path(f"{vcf}.tbi")]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
                "ref_path": ("STRING", {"description": "Reference path prefix passed to vg deconstruct -P"}),
            },
            "optional": {
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "min_sv_length": ("INT", {"default": 50, "min": 0, "description": "Minimum variant length to keep"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _PangenomeStatsContract(PangenomicsCommandContract):
    """Compute graph growth statistics with Panacus histgrowth."""

    LEGACY_NODE_ID = "pangenome_stats"
    DISPLAY_NAME = "Pangenome Stats"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Compute pangenome graph growth curves and a deterministic threshold summary with Panacus."
    SEARCH_ALIASES = ["pangenome", "panacus", "core graph", "growth curve", "coverage", "rarefaction"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("stats", "rarefaction")
    REQUIRED_EXECUTABLES = ["panacus"]
    REQUIRED_CONDA_PACKAGES = ["panacus"]
    DOCUMENTATION_URL = "https://github.com/marschall-lab/panacus"
    VERSION = "0.3.3"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _path_value(inputs.get("graph")):
            return "graph must be a non-empty path-like value"
        try:
            core_threshold = float(inputs.get("core_threshold", 0.9))
            shell_threshold = float(inputs.get("shell_threshold", 0.1))
        except (TypeError, ValueError):
            return "Pangenome thresholds must be numbers"
        if not 0 <= shell_threshold <= 1 or not 0 <= core_threshold <= 1:
            return "Pangenome thresholds must be between 0 and 1"
        if core_threshold <= shell_threshold:
            return "Core threshold must be greater than shell threshold"
        count = str(inputs.get("count", "node") or "node")
        if count not in {"node", "edge", "bp", "all"}:
            return "count must be one of: all, bp, edge, node"
        validation = _non_negative_int(inputs.get("threads", 0), "threads")
        if isinstance(validation, str):
            return validation
        grouping_modes = sum(
            bool(value)
            for value in (
                inputs.get("groupby"),
                inputs.get("groupby_sample", False),
                inputs.get("groupby_haplotype", False),
            )
        )
        if grouping_modes > 1:
            return "groupby, groupby_sample, and groupby_haplotype are mutually exclusive"
        for name, minimum, maximum in (("coverage", 1.0, None), ("quorum", 0.0, 1.0)):
            values = str(inputs.get(name, "1" if name == "coverage" else "0") or "").split(",")
            try:
                numbers = [float(value) for value in values]
            except ValueError:
                return f"{name} must be a comma-separated numeric list"
            if not numbers or any(value < minimum for value in numbers):
                return f"{name} values must be at least {minimum:g}"
            if maximum is not None and any(value > maximum for value in numbers):
                return f"{name} values must be at most {maximum:g}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        rarefaction = out_dir / "rarefaction.tsv"
        stats = out_dir / "stats.json"
        threads = int(inputs.get("threads", 0) or 0)

        cmd = [
            "panacus",
            "histgrowth",
            str(inputs.get("graph", "")),
            "--count",
            str(inputs.get("count", "node") or "node"),
            "--coverage",
            str(inputs.get("coverage", "1") or "1"),
            "--quorum",
            str(inputs.get("quorum", "0") or "0"),
        ]
        if inputs.get("groupby"):
            cmd.extend(["--groupby", str(inputs["groupby"])])
        elif inputs.get("groupby_sample"):
            cmd.append("--groupby-sample")
        elif inputs.get("groupby_haplotype"):
            cmd.append("--groupby-haplotype")
        if inputs.get("include_hist"):
            cmd.append("--hist")
        if threads > 0:
            cmd.extend(["-t", str(threads)])

        cmd.extend([
            ">",
            str(rarefaction),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_stats_summary",
            "--input",
            str(rarefaction),
            "--output",
            str(stats),
            "--core-threshold",
            str(float(inputs.get("core_threshold", 0.9) or 0.9)),
            "--shell-threshold",
            str(float(inputs.get("shell_threshold", 0.1) or 0.1)),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "stats.json", node_out / "rarefaction.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "core_threshold": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
                "shell_threshold": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
                "count": ("STRING", {"default": "node", "options": ["node", "edge", "bp", "all"]}),
                "coverage": ("STRING", {"default": "1", "description": "Comma-separated static coverage thresholds"}),
                "quorum": ("STRING", {"default": "0", "description": "Comma-separated quorum fractions"}),
                "groupby": ("FILE", {"description": "Optional Panacus group-by or path grouping file"}),
                "groupby_sample": ("BOOLEAN", {"default": False}),
                "groupby_haplotype": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64, "display": "slider"}),
                "include_hist": ("BOOLEAN", {"default": False, "description": "Include histogram rows in Panacus output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _PangenomeGeneContract(PangenomicsCommandContract):
    """Extract gene presence/absence matrices from pangenome annotations."""

    LEGACY_NODE_ID = "pangenome_gene"
    DISPLAY_NAME = "Pangenome Gene"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Extract gene presence/absence matrix and summary plot from pangenome annotations."
    SEARCH_ALIASES = ["pangenome", "panaroo", "presence absence", "orthologs", "gene clusters"]
    RETURN_TYPES = ("FILE", "IMAGE")
    RETURN_NAMES = ("presence_matrix", "pan_genome_plot")
    REQUIRED_EXECUTABLES = ["panaroo"]
    REQUIRED_CONDA_PACKAGES = ["panaroo"]
    DOCUMENTATION_URL = "https://github.com/gtonkinhill/panaroo"
    VERSION = "1.5.0"
    SHELL = True

    _CLEAN_MODES = {"strict", "moderate", "sensitive"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _split_path_list(inputs.get("annotations")):
            return "At least one GFF annotation is required"
        clean_mode = str(inputs.get("clean_mode", "strict") or "strict")
        if clean_mode not in cls._CLEAN_MODES:
            return f"Unsupported Panaroo clean mode: {clean_mode}"
        validation = _positive_int(inputs.get("threads", 4), "threads", 4)
        if isinstance(validation, str):
            return validation
        try:
            core_threshold = float(inputs.get("core_threshold", 0.95))
        except (TypeError, ValueError):
            return "Core threshold must be a number"
        if not 0 <= core_threshold <= 1:
            return "Core threshold must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        presence_matrix = out_dir / "presence_matrix.tsv"
        pan_genome_plot = out_dir / "pan_genome_plot.svg"
        annotations = _split_path_list(inputs.get("annotations"))
        threads = int(inputs.get("threads", 4) or 4)
        core_threshold = float(inputs.get("core_threshold", 0.95))

        cmd = [
            "panaroo",
            "-i",
            *annotations,
            "-o",
            str(out_dir),
            "--clean-mode",
            str(inputs.get("clean_mode", "strict") or "strict"),
        ]
        cmd.extend(["-t", str(threads)])
        cmd.extend(["--core_threshold", str(core_threshold)])
        if inputs.get("remove_invalid_genes"):
            cmd.append("--remove-invalid-genes")
        if inputs.get("merge_paralogs"):
            cmd.append("--merge_paralogs")

        cmd.extend([
            "&&",
            "cp",
            str(out_dir / "gene_presence_absence.Rtab"),
            str(presence_matrix),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_gene_plot",
            "--input",
            str(presence_matrix),
            "--output",
            str(pan_genome_plot),
            "&&",
            "test",
            "-s",
            str(presence_matrix),
            "&&",
            "test",
            "-s",
            str(pan_genome_plot),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "presence_matrix.tsv", node_out / "pan_genome_plot.svg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotations": (
                    "GFF",
                    {"multiple": True, "description": "One or more Prokka-style GFF3 annotation files"},
                ),
            },
            "optional": {
                "clean_mode": ("STRING", {"default": "strict", "options": ["strict", "moderate", "sensitive"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "core_threshold": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "remove_invalid_genes": ("BOOLEAN", {"default": True}),
                "merge_paralogs": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _MinigraphContract(PangenomicsCommandContract):
    """Construct or align pangenome graphs with minigraph."""
    LEGACY_NODE_ID = "minigraph"
    DISPLAY_NAME = "Minigraph"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Fast sequence-to-graph aligner and pangenome constructor for large genomes."
    SEARCH_ALIASES = ["minigraph", "graph align", "pangenome", "sv graph", "sequence to graph"]
    RETURN_TYPES = ("GFA", "FILE")
    RETURN_NAMES = ("output_gfa", "alignment_gaf")
    REQUIRED_EXECUTABLES = ["minigraph"]
    REQUIRED_CONDA_PACKAGES = ["minigraph"]
    DOCUMENTATION_URL = "https://github.com/lh3/minigraph"
    VERSION = "0.21"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mode = str(inputs.get("mode", "construct") or "construct")
        if mode not in {"construct", "align"}:
            return "mode must be one of: align, construct"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        preset = str(inputs.get("preset", "ggs" if mode == "construct" else "asm") or "")
        if mode == "construct":
            if preset != "ggs":
                return "construct mode requires the documented ggs preset"
            if len(_split_path_list(inputs.get("assemblies"))) < 2:
                return "construct mode requires a reference plus at least one assembly"
        else:
            if preset not in {"asm", "lr"}:
                return "align mode preset must be one of: asm, lr"
            for name in ("graph_gfa", "query_fasta"):
                if not _path_value(inputs.get(name)):
                    return f"{name} is required for align mode"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        mode = str(inputs.get("mode", "construct") or "construct")
        threads = str(inputs.get("threads", 8))

        if mode == "construct":
            output = out_dir / "output_gfa.gfa"
            cmd = ["minigraph", "-c", "-x", "ggs", "-t", threads]
            cmd.extend(_split_path_list(inputs.get("assemblies")))
        else:
            output = out_dir / "alignment_gaf.gaf"
            cmd = [
                "minigraph",
                "-c",
                "-x",
                str(inputs.get("preset", "asm") or "asm"),
                "-t",
                threads,
                str(inputs.get("graph_gfa", "")),
                str(inputs.get("query_fasta", "")),
            ]
        cmd.extend([">", str(output), "&&", "test", "-s", str(output)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("mode", "construct") or "construct") == "align":
            return [node_out / "alignment_gaf.gaf"]
        return [node_out / "output_gfa.gfa"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"default": "construct", "options": ["construct", "align"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "optional": {
                "assemblies": (
                    "FASTA",
                    {"multiple": True, "description": "Reference first, followed by assembly FASTAs"},
                ),
                "graph_gfa": ("GFA", {"description": "Graph GFA (for align mode)"}),
                "query_fasta": ("FASTA", {"description": "Query FASTA (for align mode)"}),
                "preset": (
                    "STRING",
                    {"default": "ggs", "options": ["ggs", "asm", "lr"], "description": "ggs for construction; asm/lr for mapping"},
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _MinigraphCactusContract(PangenomicsCommandContract):
    """Build pangenome graphs from multiple assemblies with Minigraph-Cactus."""

    LEGACY_NODE_ID = "minigraph_cactus"
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


class _CactusGalaxyContract(PangenomicsCommandContract):
    """Run the Galaxy Cactus whole-genome multiple alignment wrapper."""

    LEGACY_NODE_ID = "cactus_cactus"
    DISPLAY_NAME = "Cactus"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Whole-genome multiple sequence alignment with Progressive Cactus or Minigraph-Cactus."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus",
        "cactus_cactus",
        "Progressive Cactus",
        "Minigraph-Cactus",
        "whole-genome multiple alignment",
        "HAL alignment",
        "pangenome graph",
    ]
    RETURN_TYPES = ("HAL", "GFA")
    RETURN_NAMES = ("out_hal", "out_gfa")
    REQUIRED_EXECUTABLES = ["cactus", "cactus-pangenome"]
    REQUIRED_CONDA_PACKAGES = ["cactus"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    MODES = ["interspecies", "intraspecies"]

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("aln_mode_select", "interspecies") or "interspecies")

    @classmethod
    def _labels(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("labels", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [item for item in re.split(r"[\s,]+", str(value or "")) if item]

    @classmethod
    def _seqs(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("in_seqs", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item)]
        text = str(value or "")
        return [item for item in re.split(r"[\n,]+", text) if item.strip()]

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        seqs = cls._seqs(inputs)
        labels = cls._labels(inputs)
        if not seqs:
            return "at least one input genome FASTA is required"
        if len(labels) != len(seqs):
            return "labels must match in_seqs length"
        if any(not re.fullmatch(r"[0-9A-Za-z_]+", label) for label in labels):
            return "labels may contain only letters, digits, and underscores"
        mode = cls._mode(inputs)
        if mode not in cls.MODES:
            return f"aln_mode_select must be one of: {', '.join(cls.MODES)}"
        if mode == "interspecies" and not str(inputs.get("in_tree", "")).strip():
            return "in_tree is required for interspecies mode"
        if mode == "intraspecies":
            ref_level = str(inputs.get("ref_level", "")).strip()
            if not ref_level:
                return "ref_level is required for intraspecies mode"
            if ref_level not in labels:
                return "ref_level must match one of the labels"
        for key, default in (("max_cores", 4), ("max_memory_mb", 16384)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def _seq_filename(cls, label: str, fasta: str) -> str:
        suffixes = Path(fasta).suffixes
        if suffixes[-2:] == [".fa", ".gz"]:
            ext = "fa.gz"
        elif suffixes[-2:] == [".fasta", ".gz"]:
            ext = "fasta.gz"
        elif suffixes:
            ext = suffixes[-1].lstrip(".")
        else:
            ext = "fasta"
        return f"{label}.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        seqfile = f"{out_dir}/seqfile.txt"
        mode = cls._mode(inputs)
        labels = cls._labels(inputs)
        seqs = cls._seqs(inputs)
        max_cores = cls._positive_int(inputs, "max_cores", 4)
        max_memory = cls._positive_int(inputs, "max_memory_mb", 16384)
        assert isinstance(max_cores, int)
        assert isinstance(max_memory, int)

        cmd = ["mkdir", "-p", out_dir, "&&"]
        if mode == "interspecies":
            cmd.extend(["cat", str(inputs.get("in_tree", "")), ">", seqfile, "&&"])
        else:
            cmd.extend(["rm", "-f", seqfile, "&&", "touch", seqfile, "&&"])

        for label, fasta in zip(labels, seqs):
            seq_name = cls._seq_filename(label, fasta)
            cmd.extend(
                [
                    "ln",
                    "-s",
                    fasta,
                    f"{out_dir}/{seq_name}",
                    "&&",
                    "printf",
                    "%s %s\n",
                    label,
                    seq_name,
                    ">>",
                    seqfile,
                    "&&",
                ]
            )

        cmd.extend(["cd", out_dir, "&&"])
        if mode == "intraspecies":
            cmd.extend(
                [
                    "cactus-pangenome",
                    "--reference",
                    str(inputs.get("ref_level", "")),
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--outDir",
                    "./",
                    "--outName",
                    "alignment",
                    "jobStore",
                    "seqfile.txt",
                ]
            )
        else:
            cmd.extend(
                [
                    "cactus",
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--workDir",
                    "./",
                    "jobStore",
                    "seqfile.txt",
                    "alignment.full.hal",
                ]
            )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / "alignment.full.hal"]
        if cls._mode(inputs) == "intraspecies":
            outputs.append(node_out / "alignment.gfa.gz")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_seqs": ("FASTA_LIST", {"multiple": True, "description": "Input genome FASTA or FASTA.GZ files"}),
                "labels": ("STRING_LIST", {"multiple": True, "description": "Genome labels matching the input FASTA order"}),
            },
            "optional": {
                "aln_mode_select": (
                    "STRING",
                    {
                        "default": "interspecies",
                        "options": cls.MODES,
                        "description": "Between-species Progressive Cactus or within-species Minigraph-Cactus mode",
                    },
                ),
                "in_tree": ("FILE", {"default": "", "description": "Guide tree in Newick/NHX format for interspecies mode"}),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for intraspecies mode"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 16384, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class _CactusExportContract(PangenomicsCommandContract):
    """Export Cactus HAL alignments to Galaxy-supported downstream formats."""

    LEGACY_NODE_ID = "cactus_export"
    DISPLAY_NAME = "Cactus Export"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Convert Cactus HAL whole-genome alignments to MAF, VG, or UCSC Assembly Hub archives."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus Export",
        "cactus_export",
        "HAL export",
        "hal2maf",
        "hal2vg",
        "hal2assemblyHub",
        "MAF alignment",
        "UCSC Assembly Hub",
    ]
    RETURN_TYPES = ("MAF", "VG", "TAR")
    RETURN_NAMES = ("out_maf", "out_vg", "out_ah")
    REQUIRED_EXECUTABLES = ["hal2maf", "hal2vg", "hal2assemblyHub.py", "tar"]
    REQUIRED_CONDA_PACKAGES = ["cactus", "tar"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus#using-the-output"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    FORMATS = ["maf_selector", "vg_selector", "ah_selector"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "maf_selector") or "maf_selector")

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("hal_file", "")).strip():
            return "hal_file is required"
        export_format = cls._format(inputs)
        if export_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if export_format in {"maf_selector", "vg_selector"} and not str(inputs.get("ref_level", "")).strip():
            return "ref_level is required for MAF and VG export"
        for key, default in (("max_cores", 4), ("max_memory_mb", 8196)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        export_format = cls._format(inputs)
        cmd = [
            "ln",
            "-s",
            str(inputs.get("hal_file", "")),
            f"{out_dir}/alignment.hal",
            "&&",
            "cd",
            out_dir,
            "&&",
        ]
        if export_format == "maf_selector":
            cmd.extend([
                "hal2maf",
                "--refGenome",
                str(inputs.get("ref_level", "")),
                "alignment.hal",
                "alignment.maf",
            ])
        elif export_format == "vg_selector":
            cmd.extend([
                "hal2vg",
                "alignment.hal",
                "--progress",
                ">",
                "alignment.pg",
            ])
        else:
            max_cores = cls._positive_int(inputs, "max_cores", 4)
            max_memory = cls._positive_int(inputs, "max_memory_mb", 8196)
            assert isinstance(max_cores, int)
            assert isinstance(max_memory, int)
            cmd.extend([
                "hal2assemblyHub.py",
                "--maxCores",
                str(max_cores),
                "--maxMemory",
                f"{max_memory}M",
                "./jobStore",
                "alignment.hal",
                "assemblyhub",
                "&&",
                "tar",
                "-cv",
                "assemblyhub",
                ">",
                "assemblyhub.tar",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        export_format = cls._format(inputs)
        if export_format == "vg_selector":
            return [node_out / "alignment.pg"]
        if export_format == "ah_selector":
            return [node_out / "assemblyhub.tar"]
        return [node_out / "alignment.maf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hal_file": ("HAL", {"description": "HAL file generated by Cactus"}),
            },
            "optional": {
                "format": (
                    "STRING",
                    {
                        "default": "maf_selector",
                        "options": cls.FORMATS,
                        "description": "Export MAF, VG, or UCSC Assembly Hub format",
                    },
                ),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for MAF and VG exports"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 8196, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
