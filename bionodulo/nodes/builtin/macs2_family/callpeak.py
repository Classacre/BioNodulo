"""MACS2 callpeak node pinned to the 2.2.9.1 command contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MACS2_SOURCE_ROOT, MACS2CommandNode, macs2_source_urls


class MACS2CallpeakNode(MACS2CommandNode):
    """Call narrow ChIP-seq peaks and expose all stable narrow-mode artifacts."""

    NODE_ID = "macs2_callpeak"
    DISPLAY_NAME = "MACS2 Callpeak"
    DESCRIPTION = "Call narrow ChIP-seq peaks, tables, summits, and pileup tracks with MACS2"
    SEARCH_ALIASES = ["macs2", "callpeak", "peak calling", "chip-seq", "narrowpeak"]
    RETURN_TYPES = ("NARROW_PEAK", "BEDGRAPH", "TSV", "BED", "BEDGRAPH")
    RETURN_NAMES = ("peaks", "signal", "peak_table", "summits", "control_lambda")
    DOCUMENTATION_URL = f"{MACS2_SOURCE_ROOT}/README.md"
    UPSTREAM_SOURCE = "MACS2/callpeak_cmd.py"
    SOURCE_PATHS = (
        "README.md",
        "bin/macs2",
        "MACS2/OptValidator.py",
        "MACS2/callpeak_cmd.py",
        "MACS2/PeakDetect.pyx",
        "MACS2/IO/CallPeakUnit.pyx",
    )
    SOURCE_URLS = macs2_source_urls(*SOURCE_PATHS)
    EVIDENCE_PRECEDENCE = "Pinned executable parser and command source, then the pinned README."
    PREVIOUS_VERSIONS = ["2.2.9.2"]
    MIGRATIONS = [
        {
            "from_version": "2.2.9.2",
            "to_version": "2.2.9.1",
            "description": (
                "Pin the node to the published v2.2.9.1 source contract; this focused "
                "node calls narrow peaks and rejects the legacy broad flag instead of "
                "silently changing output formats."
            ),
        }
    ]

    FORMATS = ("AUTO", "BAM", "BAMPE")
    GENOME_SHORTCUTS = ("hs", "mm", "ce", "dm")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "treatment": ("BAM", {"description": "Treatment or ChIP alignment BAM"}),
                "name": ("STRING", {"default": "NA", "description": "MACS2 output name"}),
                "genome_size": (
                    "STRING",
                    {"default": "hs", "description": "hs, mm, ce, dm, or a positive effective genome size"},
                ),
            },
            "optional": {
                "control": ("BAM", {"default": "", "description": "Optional control or input BAM"}),
                "format": ("STRING", {"default": "AUTO", "options": list(cls.FORMATS)}),
                "qvalue": (
                    "FLOAT",
                    {"default": 0.05, "min": 0.0, "max": 1.0, "description": "Ignored when pvalue is set"},
                ),
                "pvalue": ("FLOAT", {"default": None, "min": 0.0, "max": 1.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.require_nonempty_file(inputs, "treatment")
        if validation is not True:
            return validation
        if inputs.get("control") not in (None, ""):
            validation = cls.require_nonempty_file(inputs, "control")
            if validation is not True:
                return validation
        if inputs.get("broad") not in (None, False):
            return (
                "legacy broad=True is not supported by the focused macs2_callpeak "
                "contract; broadPeak and gappedPeak require a dedicated output contract"
            )
        if not str(inputs.get("name", "NA")).strip():
            return "name must be non-empty"

        genome_size = str(inputs.get("genome_size", "hs") or "").strip()
        if genome_size not in cls.GENOME_SHORTCUTS:
            try:
                if float(genome_size) <= 0:
                    raise ValueError
            except ValueError:
                return "genome_size must be hs, mm, ce, dm, or a positive number"

        fmt = str(inputs.get("format", "AUTO") or "AUTO").upper()
        if fmt not in cls.FORMATS:
            return f"Unsupported MACS2 BAM format: {fmt}"
        for key in ("qvalue", "pvalue"):
            value = inputs.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"{key} must be a number"
            if not 0 < float(value) <= 1:
                return f"{key} must be greater than 0 and at most 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        stem = cls.safe_output_stem(inputs.get("name"), "NA")
        command = ["macs2", "callpeak", "-t", str(inputs.get("treatment", ""))]
        if inputs.get("control"):
            command.extend(["-c", str(inputs["control"])])
        command.extend(
            [
                "-f",
                str(inputs.get("format", "AUTO") or "AUTO").upper(),
                "-g",
                str(inputs.get("genome_size", "hs")),
                "-n",
                stem,
                "--outdir",
                str(cls.output_dir(inputs)),
                "--bdg",
            ]
        )
        if inputs.get("pvalue") is not None:
            command.extend(["-p", str(inputs["pvalue"])])
        else:
            command.extend(["-q", str(inputs.get("qvalue", 0.05))])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = cls.safe_output_stem(inputs.get("name"), "NA")
        return [
            node_out / f"{stem}_peaks.narrowPeak",
            node_out / f"{stem}_treat_pileup.bdg",
            node_out / f"{stem}_peaks.xls",
            node_out / f"{stem}_summits.bed",
            node_out / f"{stem}_control_lambda.bdg",
        ]
