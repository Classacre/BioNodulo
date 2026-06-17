"""Automatic truncated HEAD previews for arbitrary node outputs.

The executor already auto-collects previews for outputs whose extension is
directly renderable by the frontend (HTML, images, JSON, CSV/TSV). Most
bioinformatics outputs — FASTA, VCF, GFF, GenBank, logs, BAM, … — fall
outside that set and otherwise dead-end with nothing to show on the canvas.

This module renders a *small, truncated* HTML preview for such outputs:

* Text-like / UTF-8-decodable files get the first ~N lines inside a ``<pre>``
  (escaped), capped at ~64 KB so huge files never blow memory.
* Binary files get a compact "file info" card (name, human size, type) — the
  raw bytes are never dumped.

The HTML styling mirrors ``TextPreviewNode`` / ``_write_summary_preview`` so
auto previews look identical to the manual preview nodes.
"""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

# Cap how much of a text file we read for the head preview.
HEAD_MAX_BYTES = 64 * 1024
HEAD_MAX_LINES = 60

# Outputs that the frontend already renders natively — skip auto head previews
# for these so we never override a chart/report/image/table.
SKIP_EXTENSIONS = frozenset({
    ".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".bmp", ".ico", ".csv", ".tsv",
})

# Extensions known to be binary — render an info card, never attempt a head.
BINARY_EXTENSIONS = frozenset({
    ".bam", ".cram", ".bai", ".crai", ".bcf", ".gz", ".bgz", ".zip",
    ".bw", ".bigwig", ".2bit", ".pdf", ".bgzf", ".tbi", ".csi", ".db",
    ".sqlite", ".h5", ".hdf5", ".npy", ".npz", ".pkl", ".parquet",
})

# Extensions we positively know are text — used as a hint, but any file that
# decodes as UTF-8 is also treated as text regardless of extension.
TEXT_EXTENSIONS = frozenset({
    ".fasta", ".fa", ".fna", ".faa", ".fastq", ".fq", ".vcf", ".gff",
    ".gff3", ".gtf", ".bed", ".sam", ".txt", ".tsv", ".csv", ".json",
    ".xml", ".gb", ".gbk", ".genbank", ".embl", ".log", ".md", ".nwk",
    ".newick", ".fai", ".tab", ".yaml", ".yml", ".aln", ".phy", ".dnd",
})

_STYLE = (
    "body{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}"
    "h1{font-size:13px;margin:0 0 4px;color:#475569;word-break:break-all}"
    ".note{font-size:11px;color:#64748b;margin:0 0 8px}"
    "pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;"
    "white-space:pre-wrap;word-break:break-word;background:#f8fafc;"
    "border:1px solid #e2e8f0;border-radius:6px;padding:10px;margin:0;color:#0f172a}"
    "table{border-collapse:collapse;font-size:12px;margin-top:8px}"
    "th,td{border:1px solid #e2e8f0;padding:4px 10px;text-align:left}"
    "th{background:#f1f5f9;color:#475569;font-weight:600}"
)


def _human_size(num: float) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(num)} B"
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def should_skip_extension(path: Path) -> bool:
    """Return True if *path* is already renderable natively (skip head preview)."""
    return path.suffix.lower() in SKIP_EXTENSIONS


def _render_text_head(src: Path, *, max_lines: int, max_bytes: int) -> str | None:
    """Render a text-head HTML body, or None if the file isn't UTF-8 text."""
    try:
        size = src.stat().st_size
        with src.open("rb") as fh:
            raw_bytes = fh.read(max_bytes)
    except OSError as exc:
        logger.debug("head preview: cannot read %s: %s", src, exc)
        return None

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None

    lines = text.splitlines()
    truncated_bytes = size > max_bytes
    truncated_lines = len(lines) > max_lines
    shown = lines[:max_lines]

    notes: list[str] = []
    if truncated_lines:
        notes.append(f"showing first {max_lines:,} of {len(lines):,}+ lines")
    if truncated_bytes:
        notes.append(f"truncated at {max_bytes:,} bytes (file is {size:,})")
    note = " · ".join(notes)
    note_html = f"<p class='note'>{escape(note)}</p>" if note else ""
    body = escape("\n".join(shown))

    return (
        f"<!doctype html><meta charset=utf-8><title>{escape(src.name)}</title>"
        f"<style>{_STYLE}</style>"
        f"<h1>{escape(src.name)}</h1>{note_html}<pre>{body}</pre>"
    )


def _render_info_card(src: Path) -> str:
    """Render a compact file-info card for a binary file."""
    try:
        size = src.stat().st_size
    except OSError:
        size = 0
    ext = src.suffix.lower() or "(none)"
    rows = [
        ("File", src.name),
        ("Size", _human_size(size)),
        ("Type", f"binary {ext}"),
    ]
    body = "".join(
        f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in rows
    )
    return (
        f"<!doctype html><meta charset=utf-8><title>{escape(src.name)}</title>"
        f"<style>{_STYLE}</style>"
        f"<h1>{escape(src.name)}</h1>"
        f"<p class='note'>Binary file — no text head available.</p>"
        f"<table><tbody>{body}</tbody></table>"
    )


def write_head_preview(
    src_path: str | Path,
    out_dir: str | Path,
    *,
    max_lines: int = HEAD_MAX_LINES,
    max_bytes: int = HEAD_MAX_BYTES,
) -> Path | None:
    """Write a truncated HTML head preview for *src_path* into *out_dir*.

    Returns the path to the generated ``.html`` file, or ``None`` if no preview
    could/should be generated (e.g. natively-renderable extension, missing
    file, or an error). Never raises — failures are logged and swallowed so a
    preview problem can never fail the producing node or the run.
    """
    try:
        src = Path(src_path)
        if not src.is_file():
            return None
        if should_skip_extension(src):
            return None

        ext = src.suffix.lower()
        html: str | None = None
        if ext in BINARY_EXTENSIONS:
            html = _render_info_card(src)
        else:
            # Try a text head first (covers known text exts and any
            # UTF-8-decodable file); fall back to an info card on binary bytes.
            html = _render_text_head(src, max_lines=max_lines, max_bytes=max_bytes)
            if html is None:
                html = _render_info_card(src)

        if html is None:
            return None

        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
        out_html = out_dir_path / "head_preview.html"
        out_html.write_text(html, encoding="utf-8")
        return out_html
    except Exception:  # noqa: BLE001 — previews must never break a run
        logger.exception("head preview generation failed for %s", src_path)
        return None
