"""Focused InterProScan owner."""

from __future__ import annotations

from typing import Any

from .evidence import attach_evidence
from .legacy import InterProScanNode as _LegacyInterProScanNode


@attach_evidence
class InterProScanNode(_LegacyInterProScanNode):
    NODE_ID = "interproscan"
    SHELL = False

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta", "")).strip():
            return "fasta is required"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"
        return True
