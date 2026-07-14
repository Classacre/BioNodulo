"""view — utils node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class ViewTextFileNode(CommandNode):
    """Mark a text file as a workflow output for viewing."""
    NODE_ID = 'view_text_file'
    DISPLAY_NAME = 'View Text File'
    CATEGORY = 'utils'
    DESCRIPTION = 'Display a text file as a workflow output'
    SEARCH_ALIASES = ['view', 'display', 'cat', 'text', 'output']
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('content',)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = ['cat', '{inputs.file}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'description': 'Text file to display'})}, 'optional': {'max_lines': ('INT', {'default': 1000, 'min': 1, 'description': 'Maximum lines to display'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple:
        """Override to read and return file contents directly."""
        file_path = kwargs.get('file')
        max_lines = kwargs.get('max_lines', 1000)
        if not file_path:
            return ('No file provided',)
        try:
            with open(file_path) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f'... ({max_lines} lines shown)')
                        break
                    lines.append(line.rstrip())
                return ('\n'.join(lines),)
        except Exception as exc:
            return (f'Error reading file: {exc}',)
