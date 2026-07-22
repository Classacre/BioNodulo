"""Multi-FASTA PGGB 0.7.4 operation retaining the stable pggb_build contract."""

from __future__ import annotations

import gzip
import os
import shutil
from pathlib import Path
from typing import Any

from .pggb import PGGBNode


class PGGBBuildNode(PGGBNode):
    """Concatenate separate haplotype FASTAs and build one pangenome graph."""

    NODE_ID = "pggb_build"
    DISPLAY_NAME = "PGGB Build (Multiple FASTAs)"
    DESCRIPTION = "Build a pangenome graph from two or more materialized haplotype FASTA files"
    RETURN_NAMES = ("graph_gfa", "graph_odgi")
    GFA_FILENAME = "graph_gfa.gfa"
    ODGI_FILENAME = "graph_odgi.odgi"
    LEGACY_MULTI_FASTA_CONTRACT = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        parent = PGGBNode.INPUT_TYPES()
        optional = dict(parent["optional"])
        optional.pop("num_haplotypes", None)
        return {
            "required": {
                "input_fasta": (
                    "FASTA",
                    {
                        "multiple": True,
                        "description": "Two or more haplotype FASTA files in deterministic order",
                    },
                ),
                "threads": parent["required"]["threads"],
            },
            "optional": optional,
            "hidden": dict(parent["hidden"]),
        }

    @staticmethod
    def _input_fastas(value: Any) -> list[Path]:
        raw_values = list(value) if isinstance(value, (list, tuple)) else [value]
        paths: list[Path] = []
        for raw_value in raw_values:
            try:
                text = os.fsdecode(os.fspath(raw_value))
            except TypeError as exc:
                raise TypeError("each input_fasta entry must be path-like") from exc
            if not text.strip():
                raise ValueError("input_fasta paths must be non-empty")
            paths.append(Path(text))
        return paths

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            fastas = cls._input_fastas(inputs.get("input_fasta"))
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(fastas) < 2:
            return "pggb_build requires at least two haplotype FASTA files"
        for fasta in fastas:
            if not fasta.is_file():
                return f"input_fasta does not exist: {fasta}"
            if fasta.stat().st_size == 0:
                return f"input_fasta is empty: {fasta}"
        normalized = dict(inputs)
        normalized["input_fasta"] = fastas[0]
        return PGGBNode.VALIDATE_INPUTS(normalized)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        fastas = cls._input_fastas(inputs.get("input_fasta"))
        stage_root = outputs[0].parent / "_inputs"
        if stage_root.exists():
            shutil.rmtree(stage_root)
        stage_root.mkdir(parents=True)
        staged = stage_root / "input.fa"
        with staged.open("wb") as destination:
            for index, source in enumerate(fastas):
                if index:
                    destination.write(b"\n")
                handle_context = gzip.open(source, "rb") if source.name.lower().endswith(".gz") else source.open("rb")
                with handle_context as handle:
                    shutil.copyfileobj(handle, destination)
        inputs["input_fasta"] = str(staged)
        inputs["num_haplotypes"] = len(fastas)
