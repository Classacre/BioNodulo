"""Bounded text-to-HTML preview contract."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .adapter import (
    PythonUtilityNode,
    node_output_path,
    path_value,
    validate_int,
    validate_regular_file,
)


BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".ico",
        ".bam",
        ".cram",
        ".bai",
        ".gz",
        ".bgz",
        ".zip",
        ".bcf",
        ".pdf",
    }
)


class TextPreviewNode(PythonUtilityNode):
    """Render a byte- and line-bounded text prefix as escaped HTML."""

    NODE_ID = "text_preview"
    DISPLAY_NAME = "Text Preview"
    DESCRIPTION = "Preview the head of a text file inline on the canvas"
    SEARCH_ALIASES = ["text", "fasta", "genbank", "xml", "log", "view", "preview", "head", "cat"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/html.html"
    UPSTREAM_SOURCE = "Lib/html/__init__.py; Lib/pathlib.py"
    _BINARY_EXTS = set(BINARY_EXTENSIONS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"label": "Text file", "description": "FASTA / GenBank / XML / TXT / log"}),
            },
            "optional": {
                "max_lines": ("INT", {"default": 200, "min": 1, "max": 5000, "label": "Head lines"}),
                "max_bytes": (
                    "INT",
                    {
                        "default": 262144,
                        "min": 1024,
                        "max": 5242880,
                        "label": "Max bytes",
                        "advanced": True,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        raw_path = path_value(inputs.get("file"))
        if raw_path and Path(raw_path).suffix.lower() in BINARY_EXTENSIONS:
            return f"Text Preview cannot display binary/image files ({Path(raw_path).suffix})"
        validation = validate_regular_file(inputs.get("file"), label="Text file")
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("max_lines", 200), "max_lines", minimum=1, maximum=5000)
        if validation is not True:
            return validation
        return validate_int(inputs.get("max_bytes", 262144), "max_bytes", minimum=1024, maximum=5242880)

    async def run(self, **kwargs: Any) -> tuple[()]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        source = Path(path_value(kwargs["file"]))
        max_lines = int(kwargs.get("max_lines", 200))
        max_bytes = int(kwargs.get("max_bytes", 262144))
        with source.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        byte_truncated = len(raw) > max_bytes
        raw = raw[:max_bytes]
        if b"\x00" in raw:
            raise ValueError(f"Text Preview cannot display a NUL-containing binary payload: {source}")
        decoded = raw.decode("utf-8", errors="replace")
        lines = decoded.splitlines()
        line_truncated = len(lines) > max_lines
        shown = lines[:max_lines]

        notes: list[str] = []
        if line_truncated:
            notes.append(f"showing first {max_lines:,} lines")
        if byte_truncated:
            notes.append(f"truncated at {max_bytes:,} bytes")
        note_html = f'<p class="note">{html.escape("; ".join(notes))}</p>' if notes else ""
        output_path = node_output_path(context, self.NODE_ID, "text.html")
        output_path.write_text(
            "<!doctype html><meta charset=utf-8>"
            f"<title>{html.escape(source.name)}</title>"
            "<style>body{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}"
            "h1{font-size:13px;margin:0 0 4px;color:#475569}"
            ".note{font-size:11px;color:#64748b;margin:0 0 8px}"
            "pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;"
            "white-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:6px;padding:10px;margin:0;color:#0f172a}</style>"
            f"<h1>{html.escape(source.name)}</h1>{note_html}<pre>{html.escape(chr(10).join(shown))}</pre>",
            encoding="utf-8",
        )
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Text Preview")
        return ()
