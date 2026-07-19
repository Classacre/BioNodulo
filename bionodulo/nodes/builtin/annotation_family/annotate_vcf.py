"""Focused vcfanno and BCFtools multi-source annotation pipeline."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import attach_evidence
from .staging import stage_file


def _path_values(value: Any, *, key: str) -> list[str] | str:
    if value is None:
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        decoded = os.fsdecode(os.fspath(value))
        values = re.split(r"[\n,]+", decoded)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = list(value)
    else:
        return f"Input '{key}' must contain path-like values"

    paths: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item)).strip()
        except TypeError:
            return f"Input '{key}' must contain path-like values"
        if path:
            paths.append(path)
    return paths


def _index_suffix(annotation: Path, index: Path) -> str | None:
    for suffix in (".csi", ".tbi"):
        if index.name == f"{annotation.name}{suffix}":
            return suffix
    return None


def _safe_output_stem(value: str, default: str) -> str:
    stem = "_".join(str(value or "").strip().split())
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
    stem = stem.strip("._-")
    return stem or default


def _split_annotation_files(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]


def _split_annotation_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@attach_evidence
class AnnotateVCFNode(CommandNode):
    """Annotate with either vcfanno 0.3.9 or BCFtools 1.24."""

    NODE_ID = "annotate_vcf"
    DISPLAY_NAME = "Annotate VCF"
    CATEGORY = "annotation"
    DESCRIPTION = (
        "Annotate VCF records with gene names, consequences, and frequencies from multiple sources."
    )
    SEARCH_ALIASES = [
        "annotate vcf",
        "variant annotation",
        "multi-source annotation",
        "vcfanno",
        "bcftools annotate",
        "roadmap",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("annotated_vcf", "annotated_vcf_index")
    REQUIRED_EXECUTABLES = ["vcfanno", "bcftools"]
    REQUIRED_CONDA_PACKAGES = ["vcfanno", "bcftools", "htslib"]
    DOCUMENTATION_URL = "https://github.com/brentp/vcfanno"
    SHELL = True
    SECONDARY_SOURCE_URL = "https://github.com/samtools/bcftools/tree/fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    SECONDARY_GIT_COMMIT = "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input bgzipped VCF"}),
                "annotation_files": (
                    "FILE_LIST",
                    {"multiple": True, "description": "Ordered bgzip-compressed annotation sources"},
                ),
                "annotation_indexes": (
                    "FILE_LIST",
                    {
                        "multiple": True,
                        "description": "One matching .tbi or .csi per annotation source",
                    },
                ),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "vcfanno",
                        "options": ["vcfanno", "bcftools"],
                        "description": "Annotation backend",
                    },
                ),
                "vcfanno_config": (
                    "FILE",
                    {"default": "", "description": "vcfanno TOML configuration"},
                ),
                "columns": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Newline-separated bcftools column specs matching annotation_files, "
                            "e.g. CHROM,FROM,TO,GENE"
                        ),
                    },
                ),
                "header_lines": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Newline-separated bcftools header files matching annotation_files; "
                            "use '-' to skip a source"
                        ),
                    },
                ),
                "output_name": (
                    "STRING",
                    {"default": "", "description": "Optional output filename stem"},
                ),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _paired_sources(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]] | str:
        files = _path_values(inputs.get("annotation_files"), key="annotation_files")
        if isinstance(files, str):
            return files
        indexes = _path_values(inputs.get("annotation_indexes"), key="annotation_indexes")
        if isinstance(indexes, str):
            return indexes
        if not files:
            return "annotation_files must contain at least one path"
        if len(indexes) != len(files):
            return "annotation_indexes must contain one index for each annotation_files value"

        basenames = [Path(path).name for path in files]
        if len(set(basenames)) != len(basenames):
            return "annotation_files must have unique basenames for deterministic staging"
        for annotation_value, index_value in zip(files, indexes, strict=True):
            annotation = Path(annotation_value)
            index = Path(index_value)
            if _index_suffix(annotation, index) is None:
                return (
                    "Each annotation index basename must equal its annotation basename "
                    "followed by .tbi or .csi"
                )
        return files, indexes

    @classmethod
    def _validate_vcfanno_config(cls, config_path: str, annotation_files: list[str]) -> bool | str:
        config = Path(config_path)
        if not config.is_file():
            return f"vcfanno_config does not exist: {config}"
        try:
            payload = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            return f"vcfanno_config is not valid TOML: {exc}"

        annotations = payload.get("annotation", [])
        if not isinstance(annotations, list) or not annotations:
            return "vcfanno_config must contain at least one [[annotation]] block"
        configured_files: list[str] = []
        for annotation in annotations:
            if not isinstance(annotation, dict) or not str(annotation.get("file", "")).strip():
                return "Every vcfanno [[annotation]] block must declare file"
            configured = str(annotation["file"]).strip()
            if Path(configured).name != configured:
                return "vcfanno_config annotation files must use staged basenames without directories"
            configured_files.append(configured)

        expected = {Path(path).name for path in annotation_files}
        if set(configured_files) != expected:
            return "vcfanno_config annotation basenames must exactly match annotation_files"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation

        mode = str(inputs.get("mode", "vcfanno") or "vcfanno").lower()
        if mode not in {"vcfanno", "bcftools"}:
            return f"Unsupported annotation mode: {mode}"
        if mode == "vcfanno":
            config = str(inputs.get("vcfanno_config", "") or "").strip()
            if not config:
                return "vcfanno_config is required in vcfanno mode"
        else:
            annotation_files = _split_annotation_files(inputs.get("annotation_files"))
            columns = _split_annotation_lines(inputs.get("columns"))
            header_lines = _split_annotation_lines(inputs.get("header_lines"))
            if not annotation_files:
                return "At least one annotation file is required in bcftools mode"
            if not columns:
                return "columns is required in bcftools mode"
            if len(columns) != len(annotation_files):
                return "columns must provide one newline-separated entry per bcftools annotation file"
            if header_lines and len(header_lines) != len(annotation_files):
                return (
                    "header_lines must provide one newline-separated entry per bcftools "
                    "annotation file, using '-' to skip a source"
                )

        paired = cls._paired_sources(inputs)
        if isinstance(paired, str):
            return paired
        if mode == "vcfanno":
            return cls._validate_vcfanno_config(config, paired[0])
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_vcf = cls._output_vcf_path(inputs, inputs.get("output", inputs.get("output_dir", ".")))
        mode = str(inputs.get("mode", "vcfanno") or "vcfanno").lower()
        threads = int(inputs.get("threads", 4) or 0)
        if mode == "vcfanno":
            source_dir = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "annotation_sources"
            command = ["set", "-euo", "pipefail", "&&", "vcfanno"]
            if threads > 0:
                command.extend(["-p", str(threads)])
            command.extend(
                [
                    "-base-path",
                    str(source_dir),
                    str(inputs["vcfanno_config"]),
                    str(inputs["vcf"]),
                    "|",
                    "bcftools",
                    "view",
                    "-Oz",
                    "-o",
                    str(output_vcf),
                    "&&",
                    "bcftools",
                    "index",
                    "-f",
                    "-t",
                    str(output_vcf),
                ]
            )
            return command
        return cls._render_bcftools_command(inputs, output_vcf, threads)

    @classmethod
    def _render_vcfanno_command(
        cls,
        inputs: dict[str, Any],
        output_vcf: Path,
        threads: int,
    ) -> list[str]:
        command = ["set", "-euo", "pipefail", "&&", "vcfanno"]
        if threads > 0:
            command.extend(["-p", str(threads)])
        command.extend(
            [
                str(inputs.get("vcfanno_config", "")),
                str(inputs.get("vcf", "")),
                "|",
                "bcftools",
                "view",
                "-Oz",
                "-o",
                str(output_vcf),
                "&&",
                "bcftools",
                "index",
                "-f",
                "-t",
                str(output_vcf),
            ]
        )
        return command

    @classmethod
    def _render_bcftools_command(
        cls,
        inputs: dict[str, Any],
        output_vcf: Path,
        threads: int,
    ) -> list[str]:
        annotation_files = _split_annotation_files(inputs.get("annotation_files"))
        columns = _split_annotation_lines(inputs.get("columns"))
        header_lines = _split_annotation_lines(inputs.get("header_lines"))
        command: list[str] = ["set", "-euo", "pipefail", "&&"]
        for index, annotation_file in enumerate(annotation_files):
            if index > 0:
                command.append("|")
            command.extend(["bcftools", "annotate", "-a", annotation_file])
            command.extend(["-c", columns[index]])
            if header_lines and header_lines[index] != "-":
                command.extend(["-h", header_lines[index]])
            if threads > 0:
                command.extend(["--threads", str(threads)])
            command.append("-Oz" if index == len(annotation_files) - 1 else "-Ou")
            if index == len(annotation_files) - 1:
                command.extend(["-o", str(output_vcf)])
            if index == 0:
                command.append(str(inputs.get("vcf", "")))
            else:
                command.append("-")
        command.extend(["&&", "bcftools", "index", "-f", "-t", str(output_vcf)])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_vcf = cls._output_vcf_path(inputs, Path(output_dir) / cls.NODE_ID)
        output_index = Path(f"{output_vcf}.tbi")
        output_vcf.parent.mkdir(parents=True, exist_ok=True)
        return [output_vcf, output_index]

    @classmethod
    def _output_vcf_path(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        stem = _safe_output_stem(str(inputs.get("output_name", "") or ""), "annotated_vcf")
        return Path(output_dir) / f"{stem}.annotated.vcf.gz"

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        paired = cls._paired_sources(inputs)
        if isinstance(paired, str):
            raise ValueError(paired)
        files, indexes = paired
        source_dir = outputs[0].parent / "annotation_sources"
        staged_files: list[str] = []
        staged_indexes: list[str] = []
        for annotation_value, index_value in zip(files, indexes, strict=True):
            annotation = Path(annotation_value)
            index = Path(index_value)
            suffix = _index_suffix(annotation, index)
            if suffix is None:
                raise ValueError("Invalid annotation/index pair")
            staged_annotation = stage_file(annotation, source_dir / annotation.name)
            staged_index = stage_file(index, Path(f"{staged_annotation}{suffix}"))
            staged_files.append(str(staged_annotation))
            staged_indexes.append(str(staged_index))
        inputs["annotation_files"] = staged_files
        inputs["annotation_indexes"] = staged_indexes

        if str(inputs.get("mode", "vcfanno") or "vcfanno").lower() == "vcfanno":
            staged_config = stage_file(str(inputs["vcfanno_config"]), source_dir / "vcfanno.toml")
            inputs["vcfanno_config"] = str(staged_config)
