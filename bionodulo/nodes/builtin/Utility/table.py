"""table — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class TablePreviewNode(CommandNode):
    """Render the head of a CSV/TSV as an inline table on the canvas.

    Keeps the iframe lightweight on huge bioinformatics tables by only
    materialising the first N rows — perfect for variant calls, count
    matrices, stats tables, etc. that have millions of rows.
    """
    NODE_ID = 'table_preview'
    DISPLAY_NAME = 'Table Preview'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Preview the head of a CSV/TSV table inline on the canvas'
    SEARCH_ALIASES = ['table', 'csv', 'tsv', 'head', 'preview', 'data']
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []
    _TABLE_EXTS = {'.csv', '.tsv', '.txt', '.tab'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'label': 'Table file', 'description': 'CSV / TSV / TXT'})}, 'optional': {'rows': ('INT', {'default': 25, 'min': 1, 'max': 500, 'label': 'Head rows'}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', ',', '\t', ';', '|', ' '], 'label': 'Delimiter', 'advanced': True})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get('file')
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._TABLE_EXTS:
            return f"File must be a table ({', '.join(sorted(cls._TABLE_EXTS))}), got: {path.suffix}"
        if not path.exists():
            return f'Table file not found: {file_path}'
        return True

    @staticmethod
    def _sniff_delimiter(line: str) -> str:
        for cand in ('\t', ',', ';', '|', ' '):
            if cand in line:
                return cand
        return ','

    async def run(self, **kwargs: Any) -> tuple:
        from html import escape
        file_path = kwargs.get('file')
        rows_limit = int(kwargs.get('rows') or 25)
        delim_choice = str(kwargs.get('delimiter') or 'auto')
        context = kwargs.pop('context', None)
        node_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = node_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        out_html = out_dir / 'table.html'
        if not file_path:
            return ()
        src = Path(str(file_path))
        total_rows = 0
        header: list[str] = []
        body: list[list[str]] = []
        try:
            with src.open('r', encoding='utf-8', errors='replace') as fh:
                first = fh.readline()
                if not first:
                    return ()
                if delim_choice == 'auto':
                    delim = self._sniff_delimiter(first.rstrip('\n').rstrip('\r'))
                else:
                    delim = '\t' if delim_choice == '\\t' else delim_choice
                header = first.rstrip('\n').rstrip('\r').split(delim)
                for line in fh:
                    total_rows += 1
                    if len(body) < rows_limit:
                        body.append(line.rstrip('\n').rstrip('\r').split(delim))
        except Exception as exc:
            out_html.write_text(f"<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:16px;color:#b91c1c'><strong>Table preview failed:</strong> {escape(str(exc))}</body>", encoding='utf-8')
            if context is not None and hasattr(context, 'register_preview'):
                context.register_preview(out_html, label='Table Preview')
            return ()
        thead = ''.join((f'<th>{escape(h)}</th>' for h in header))
        body_html = ''.join(('<tr>' + ''.join((f'<td>{escape(c)}</td>' for c in row)) + '</tr>' for row in body))
        more = f' — {total_rows - rows_limit:,} more rows not shown' if total_rows > rows_limit else ''
        out_html.write_text(f'<!doctype html><meta charset=utf-8><title>{escape(src.name)}</title>\n<style>body{{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}}\nh1{{font-size:13px;margin:0 0 8px;color:#475569}}\ntable{{border-collapse:collapse;font-size:12px;width:100%}}\nth,td{{border:1px solid #e2e8f0;padding:4px 8px;text-align:left;vertical-align:top}}\nth{{background:#f1f5f9;position:sticky;top:0}}\ntr:nth-child(even) td{{background:#f8fafc}}</style>\n<h1>{escape(src.name)} — head {min(rows_limit, total_rows):,} of {total_rows:,} rows{escape(more)}</h1>\n<table><thead><tr>{thead}</tr></thead><tbody>{body_html}</tbody></table>', encoding='utf-8')
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(out_html, label='Table Preview')
        return ()
