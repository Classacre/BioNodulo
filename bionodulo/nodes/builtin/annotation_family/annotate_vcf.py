"""Focused vcfanno and BCFtools multi-source annotation pipeline."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .evidence import attach_evidence
from .legacy import AnnotateVCFNode as _LegacyAnnotateVCFNode
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


@attach_evidence
class AnnotateVCFNode(_LegacyAnnotateVCFNode):
    """Annotate with either vcfanno 0.3.9 or BCFtools 1.24."""

    NODE_ID = "annotate_vcf"
    REQUIRED_EXECUTABLES = ["vcfanno", "bcftools"]
    REQUIRED_CONDA_PACKAGES = ["vcfanno", "bcftools", "htslib"]
    SECONDARY_SOURCE_URL = "https://github.com/samtools/bcftools/tree/fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    SECONDARY_GIT_COMMIT = "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        contract = super().INPUT_TYPES()
        required = dict(contract["required"])
        required["annotation_files"] = (
            "FILE_LIST",
            {"multiple": True, "description": "Ordered bgzip-compressed annotation sources"},
        )
        required["annotation_indexes"] = (
            "FILE_LIST",
            {"multiple": True, "description": "One matching .tbi or .csi per annotation source"},
        )
        optional = dict(contract["optional"])
        optional.pop("annotation_files", None)
        return {**contract, "required": required, "optional": optional}

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
        paired = cls._paired_sources(inputs)
        if isinstance(paired, str):
            return paired

        mode = str(inputs.get("mode", "vcfanno") or "vcfanno").lower()
        if mode == "vcfanno":
            config = str(inputs.get("vcfanno_config", "") or "").strip()
            if not config:
                return "vcfanno_config is required in vcfanno mode"
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
        return super().render_command(inputs)

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
