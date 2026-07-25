"""Shared Biopython 1.87 authority, validation, and artifact helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


BIOPYTHON_VERSION = "1.87"
BIOPYTHON_GIT_URL = "https://github.com/biopython/biopython.git"
BIOPYTHON_GIT_COMMIT = "7a9c76cce8c6a58db791be2b12a135af210cedf2"
BIOPYTHON_SOURCE_URL = (
    "https://github.com/biopython/biopython/tree/"
    "7a9c76cce8c6a58db791be2b12a135af210cedf2"
)
BIOPYTHON_SOURCE_REF = "biopython-187"
BIOPYTHON_PACKAGE_CONSTRAINTS = ("biopython==1.87",)

# Hashes from the immutable release checkout at BIOPYTHON_GIT_COMMIT. They let
# focused tests prove the locally exercised 1.87 package is the audited source.
BIOPYTHON_SOURCE_FILE_SHA256 = {
    "Bio/AlignIO/ClustalIO.py": "07d548f2db29f78db77a131441ec981fed1c680b97fb0a86e4ee8f489f964147",
    "Bio/AlignIO/NexusIO.py": "357695ca336e182d9117a5811e2b3a3f8868d97af8bb89257a6e9ce6b10377b9",
    "Bio/AlignIO/PhylipIO.py": "f5d931811f99e948de84bf906b2a9b51211d319abac99502bb6cd3b146106d5c",
    "Bio/AlignIO/StockholmIO.py": "3ec96011cc3214b6979a4da0c60be578d4ba4f0febc162ecfd5be241d6bbd7b2",
    "Bio/AlignIO/__init__.py": "1fa9b9f3b5a58a3f7a063318d3a1b8c766364602a80e421bba88eb94a1702aa9",
    "Bio/Blast/NCBIXML.py": "2f9d990cfafada73bdd1287d77d833c4be2a19b357d5cb30c164c0139ade71c2",
    "Bio/Data/CodonTable.py": "810286c0fc96df0a853dd1178814595cff1f39cb096029f9546463746f1492b4",
    "Bio/Seq.py": "ad2a2c85e44c74456dc9dd6f457cbd4e7b0f0b2c4dc0f6bc28a71a867cbe156b",
    "Bio/SeqIO/FastaIO.py": "83e686baeb6b9beaf7e09c2a23f8f94d8fce452467f7d50071d038101b04fa75",
    "Bio/SeqIO/InsdcIO.py": "d51403eccb9cb9daf7c328795deb206f9ccae43f5c89a025ee0d9767b03c4fcd",
    "Bio/SeqIO/Interfaces.py": "ec842f5000dc48a23becc85af8c00ccc915cee0f9c12b8cad7598cbcbebbdec9",
    "Bio/SeqIO/__init__.py": "a2b454b3ebe6066af2b0d653423b25c03c842c081bef4f3643d34f0a570bb11f",
    "Bio/SeqUtils/__init__.py": "bd6e3676fdbc01c88e19313f1babf65c96697019460f1e73e1d136392dcf7d6a",
}


class BiopythonNode(BaseNode):
    """Shared source and environment contract for in-process Biopython nodes."""

    CATEGORY = "biopython"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    CONDA_PACKAGE_CONSTRAINTS = {"biopython": BIOPYTHON_VERSION}
    PACKAGE_CONSTRAINTS = BIOPYTHON_PACKAGE_CONSTRAINTS
    PACKAGE_CONSTRAINT = "; ".join(BIOPYTHON_PACKAGE_CONSTRAINTS)
    VERSION = BIOPYTHON_VERSION
    RUNTIME_VERSION = BIOPYTHON_VERSION
    GIT_URL = BIOPYTHON_GIT_URL
    GIT_COMMIT = BIOPYTHON_GIT_COMMIT
    SOURCE_REF = BIOPYTHON_SOURCE_REF
    SOURCE_URL = BIOPYTHON_SOURCE_URL
    SOURCE_PATHS: tuple[str, ...] = ()
    SOURCE_FILE_SHA256 = BIOPYTHON_SOURCE_FILE_SHA256
    DOCUMENTATION_URL = "https://biopython.org/docs/1.87/api/"
    AUDIT_STATUS = "contract-checked-with-synthetic-biopython-1.87-fixtures"
    EXIT_SEMANTICS = (
        "Input validation and Biopython parsing or transformation errors fail the node; "
        "only declared return paths are successful artifacts."
    )

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))


def validate_path(value: Any, key: str) -> bool | str:
    """Validate a staged path value without requiring it to exist yet."""

    if not str(value or "").strip():
        return f"Input '{key}' must be a non-empty path"
    return True


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    if str(value) not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


def validate_output_name(value: Any) -> bool | str:
    name = str(value or "")
    if not name or Path(name).name != name or name in {".", ".."}:
        return "Input 'output_name' must be a filename without directory components"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        return "Input 'output_name' contains unsupported filename characters"
    return True


def node_output_dir(node_id: str, context: Any) -> Path:
    root = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = root / node_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def atomic_seqio_write(records: Sequence[Any], output_path: Path, format_name: str) -> int:
    """Write a complete SeqIO artifact before atomically publishing its path."""

    from Bio import SeqIO

    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        count = SeqIO.write(records, str(temporary_path), format_name)
        if count != len(records):
            raise RuntimeError(
                f"Biopython wrote {count} record(s), expected {len(records)}"
            )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return count


def write_summary_preview(
    context: Any,
    output_dir: Path,
    *,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    note: str = "",
    label: str = "Summary",
) -> Path:
    """Render a deterministic HTML summary and register it as a preview."""

    output_dir.mkdir(parents=True, exist_ok=True)
    thead = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    note_html = f"<p class='note'>{escape(note)}</p>" if note else ""
    html_path = output_dir / "summary.html"
    html_path.write_text(
        f"""<!doctype html><meta charset=utf-8><title>{escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}}
h1{{font-size:13px;margin:0 0 8px;color:#475569}}
.note{{font-size:11px;color:#64748b;margin:0 0 8px}}
table{{border-collapse:collapse;font-size:12px;width:100%}}
th,td{{border:1px solid #e2e8f0;padding:4px 8px;text-align:left;vertical-align:top}}
th{{background:#f1f5f9;position:sticky;top:0}}
tr:nth-child(even) td{{background:#f8fafc}}</style>
<h1>{escape(title)}</h1>{note_html}
<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>""",
        encoding="utf-8",
    )
    if context is not None and hasattr(context, "register_preview"):
        context.register_preview(html_path, label=label)
    return html_path
