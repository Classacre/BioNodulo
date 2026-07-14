"""html — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class HtmlPreviewNode(CommandNode):
    """Display an HTML report inline in the canvas — a visual sink node."""
    NODE_ID = 'html_preview'
    DISPLAY_NAME = 'HTML Preview'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Preview an HTML report directly in the workflow canvas'
    SEARCH_ALIASES = ['html', 'report', 'preview', 'multiqc', 'fastqc', 'viewer']
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []
    _HTML_EXTS = {'.html', '.htm'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'label': 'HTML File', 'description': 'Path to an HTML report file'})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get('file')
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._HTML_EXTS:
            return f"File must be an HTML report ({', '.join(cls._HTML_EXTS)}), got: {path.suffix}"
        if not path.exists():
            return f'HTML file not found: {file_path}'
        return True

    async def run(self, **kwargs: Any) -> tuple:
        file_path = kwargs.get('file')
        context = kwargs.pop('context', None)
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(Path(str(file_path or '.')), label='HTML Preview')
        return ()
