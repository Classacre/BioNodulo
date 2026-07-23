"""Shared VSEARCH command and validation helpers."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


VSEARCH_USERFIELDS = (
    "aln",
    "alnlen",
    "bits",
    "caln",
    "evalue",
    "exts",
    "gaps",
    "id",
    "id0",
    "id1",
    "id2",
    "id3",
    "id4",
    "ids",
    "mism",
    "opens",
    "pairs",
    "pctgaps",
    "pctpv",
    "pv",
    "qcov",
    "qframe",
    "qhi",
    "qihi",
    "qilo",
    "ql",
    "qlo",
    "qrow",
    "qs",
    "qstrand",
    "query",
    "raw",
    "target",
    "tcov",
    "tframe",
    "thi",
    "tihi",
    "tilo",
    "tl",
    "tlo",
    "trow",
    "ts",
    "tstrand",
)


class VSearchNodeBase(CommandNode):
    """Common VSEARCH 2.8.3 process contract."""

    @classmethod
    def _general_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
        ]

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if not 1 <= threads <= 128:
            return "threads must be between 1 and 128"
        return True


__all__ = ["VSEARCH_USERFIELDS", "VSearchNodeBase"]
