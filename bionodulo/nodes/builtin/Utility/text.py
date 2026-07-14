"""text — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class TextPreviewNode(CommandNode):
    """Render the head of any text file inline on the canvas.

    Fills the gap left by the image/table preview nodes: FASTA, GenBank, BLAST
    XML, logs, and other plain-text outputs that otherwise have no viewer, so
    sequence/analysis nodes don't dead-end with results you can't see.
    """
    NODE_ID = 'text_preview'
    DISPLAY_NAME = 'Text Preview'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Preview the head of any text file (FASTA, GenBank, XML, logs, …) inline'
    SEARCH_ALIASES = ['text', 'fasta', 'genbank', 'xml', 'log', 'view', 'preview', 'head', 'cat']
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []
    _BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.bam', '.cram', '.bai', '.gz', '.bgz', '.zip', '.bcf', '.pdf'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'label': 'Text file', 'description': 'FASTA / GenBank / XML / TXT / log / …'})}, 'optional': {'max_lines': ('INT', {'default': 200, 'min': 1, 'max': 5000, 'label': 'Head lines'}), 'max_bytes': ('INT', {'default': 262144, 'min': 1024, 'max': 5242880, 'label': 'Max bytes', 'advanced': True})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get('file')
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() in cls._BINARY_EXTS:
            return f'Text Preview cannot display binary/image files ({path.suffix})'
        if not path.exists():
            return f'File not found: {file_path}'
        return True

    async def run(self, **kwargs: Any) -> tuple:
        from html import escape
        file_path = kwargs.get('file')
        max_lines = int(kwargs.get('max_lines') or 200)
        max_bytes = int(kwargs.get('max_bytes') or 262144)
        context = kwargs.pop('context', None)
        node_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = node_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        out_html = out_dir / 'text.html'
        if not file_path:
            return ()
        src = Path(str(file_path))
        try:
            size = src.stat().st_size
            with src.open('r', encoding='utf-8', errors='replace') as fh:
                raw = fh.read(max_bytes)
            lines = raw.splitlines()
            truncated_bytes = size > max_bytes
            truncated_lines = len(lines) > max_lines
            shown = lines[:max_lines]
        except OSError as exc:
            out_html.write_text(f"<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:16px;color:#b91c1c'><strong>Text preview failed:</strong> {escape(str(exc))}</body>", encoding='utf-8')
            if context is not None and hasattr(context, 'register_preview'):
                context.register_preview(out_html, label='Text Preview')
            return ()
        notes = []
        if truncated_lines:
            notes.append(f'showing first {max_lines:,} of {len(lines):,}+ lines')
        if truncated_bytes:
            notes.append(f'truncated at {max_bytes:,} bytes (file is {size:,})')
        note = ' · '.join(notes)
        note_html = f"<p class='note'>{escape(note)}</p>" if note else ''
        body = escape('\n'.join(shown))
        out_html.write_text(f'<!doctype html><meta charset=utf-8><title>{escape(src.name)}</title>\n<style>body{{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}}\nh1{{font-size:13px;margin:0 0 4px;color:#475569}}\n.note{{font-size:11px;color:#64748b;margin:0 0 8px}}\npre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;\nwhite-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid #e2e8f0;\nborder-radius:6px;padding:10px;margin:0;color:#0f172a}}</style>\n<h1>{escape(src.name)}</h1>{note_html}<pre>{body}</pre>', encoding='utf-8')
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(out_html, label='Text Preview')
        return ()
