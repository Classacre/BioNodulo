"""Convert papers to Markdown before handing them to a model.

A PDF text dump loses exactly what matters for reproducing a method: the
boundary between the Methods section and everything else, the structure of
figure captions, and above all tables — sample sheets, accession lists, tool
versions and parameters all live in tables, and raw extraction interleaves their
cells into unreadable prose.

Microsoft's markitdown converts PDF, DOCX, HTML and XLSX into Markdown with
headings, lists and pipe tables preserved, which is both shorter and far easier
for a model to read. It is an optional dependency: when it is absent, or fails
on a particular file, the existing per-page text extraction still runs. Losing
structure degrades the answer; losing the paper entirely would not be a
degradation, it would be a failure.
"""

from __future__ import annotations

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

#: Markdown is denser than a raw dump, so the same budget carries more paper.
DEFAULT_MAX_CHARS = 24000


def markitdown_available() -> bool:
    """Whether the optional converter is installed."""
    try:
        import markitdown  # noqa: F401
    except Exception:
        return False
    return True


def to_markdown(
    data: bytes,
    *,
    filename: str = "paper.pdf",
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str | None:
    """Convert a document to Markdown, or return None if that is not possible.

    ``filename`` only supplies the extension markitdown uses to choose a
    converter, so a caller that knows the media type should pass a matching
    name rather than the user's original one.
    """
    if not data:
        return None
    try:
        from markitdown import MarkItDown
    except Exception:
        # Not installed: the caller falls back to plain text extraction.
        return None

    try:
        converter = MarkItDown(enable_plugins=False)
        # Convert from memory: papers arrive as uploaded bytes or an HTTP body,
        # and writing them to disk to read them back would be a needless
        # round-trip through the filesystem.
        result = converter.convert_stream(BytesIO(data), file_extension=_extension(filename))
    except Exception as exc:
        logger.info("markitdown could not convert %s: %s", filename, exc)
        return None

    text = (getattr(result, "text_content", "") or "").strip()
    if not text or not _looks_like_prose(text):
        # markitdown falls back to reading unknown bytes as plain text, so a
        # corrupt or misnamed file yields mojibake rather than an error. Sending
        # that as "the paper" wastes a paid call and produces a confident answer
        # about noise.
        return None
    return text[:max_chars]


def _looks_like_prose(text: str, sample: int = 2000) -> bool:
    """Whether text is plausibly readable rather than decoded binary."""
    head = text[:sample]
    if not head:
        return False
    printable = sum(1 for ch in head if ch.isprintable() or ch in "\n\r\t")
    return printable / len(head) >= 0.9


def _extension(filename: str) -> str:
    """Extension including the dot, defaulting to PDF."""
    _, _, tail = filename.rpartition(".")
    return f".{tail.lower()}" if tail and tail != filename else ".pdf"
